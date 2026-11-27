"""Character art. Local files first, then Bangumi, and give up quietly.

A network error must never break the daily draw: everything here returns
None on failure and the caller just posts the card without a picture.
Images are cached on disk; a failed lookup leaves a miss marker so we do
not hit the API again for every draw.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from .store import name_key, norm

BGM_API_BASE = "https://api.bgm.tv"
"""Official API, always the last fallback."""

BGM_API_MIRRORS = ("https://bgmapi.sakuraspark.fun",)
"""API mirrors. The official domain is often unreachable, so try these first."""

BGM_IMAGE_MIRRORS = (
    "https://bgmimg.sakuraspark.fun",
    "https://bgmlain.waterbee.cc",
    "https://bgm.sakuraspark.fun",
)
"""Image mirrors, tried in order, official host last."""

USER_AGENT = "CareGalUniverse/2.1.2 (https://github.com/Care0721/astrbot_plugin_galuniverse)"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_BYTES = 8 * 1024 * 1024
MISS_TTL = 1800

CACHE_VERSION = 2
"""Part of the cache filename. Bump it when the matching rules change."""


def to_mirror(url: str, mirror: str) -> str:
    """Point an image url at a mirror, keeping path and query.

    The mirrors proxy lain.bgm.tv by path, so only the host changes:
      https://lain.bgm.tv/pic/crt/l/00/01/1_crt.jpg?r=1
      -> https://bgmlain.waterbee.cc/pic/crt/l/00/01/1_crt.jpg?r=1
    """
    url = (url or "").strip()
    mirror = (mirror or "").strip().rstrip("/")
    if not url or not mirror:
        return url
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    suffix = f"?{parsed.query}" if parsed.query else ""
    return f"{mirror}{parsed.path}{suffix}"


def upscale_image(
    data: bytes, min_width: int = 720, max_scale: float = 2.5
) -> tuple[bytes, str]:
    """Upscale narrow art, otherwise QQ renders it as a tiny thumbnail.

    Returns the input unchanged (with an empty extension) when Pillow is
    missing, the image is already wide enough, or anything goes wrong.
    """
    try:
        from io import BytesIO

        from PIL import Image as PILImage
    except Exception:
        return data, ""
    try:
        with PILImage.open(BytesIO(data)) as im:
            width, height = im.size
            if width <= 0 or height <= 0 or width >= min_width:
                return data, ""
            scale = min(max_scale, min_width / width)
            resized = im.convert("RGB").resize(
                (int(width * scale), int(height * scale)), PILImage.LANCZOS
            )
            buf = BytesIO()
            resized.save(buf, format="JPEG", quality=88)
            return buf.getvalue(), ".jpg"
    except Exception:
        return data, ""


class ImageFetcher:
    def __init__(
        self,
        cache_dir: Path,
        local_dir: Path | None = None,
        source: str = "auto",
        cache_days: int = 30,
        timeout: float = 6.0,
        api_bases: list[str] | str | None = None,
        api_base: str | None = None,
        mirrors: list[str] | str | None = None,
        upscale: bool = True,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_dir = Path(local_dir) if local_dir else None
        self.source = source if source in {"auto", "bangumi", "local", "off"} else "auto"
        self.api_bases = self._normalize_api_bases(api_bases, api_base)
        self.mirrors = self._normalize_mirrors(mirrors)
        self.cache_seconds = max(1, int(cache_days)) * 86400
        self.timeout = max(1.0, float(timeout))
        self.upscale = bool(upscale)
        self.url_cache_path = self.cache_dir / "image_urls.json"
        self._urls: dict[str, str] = {}
        self._load_urls()
        self._locks: dict[str, asyncio.Lock] = {}
        self.last_reason = ""
        """Why the last fetch failed. The caller logs it."""

    # ---------------- public entry ----------------

    async def fetch(self, name: str, work: str = "", image_url: str = "") -> Path | None:
        """local -> cache -> known url -> search and download. None if all fail.

        image_url comes straight from the character pool, so no search needed.
        A failure only blocks retries for 30 minutes: one bad minute of
        network should not cost a character a whole day.
        """
        if self.source == "off" or not name.strip():
            return None

        local = self._find_local(name, work)
        if local:
            return local
        if self.source == "local":
            self.last_reason = "仅本地模式，且 images/ 里没有同名图片"
            return None

        cached = self._find_cached(name)
        if cached:
            return cached
        if self._is_miss(name):
            self.last_reason = "miss 标记（30 分钟内失败过，跳过重试）"
            return None

        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            cached = self._find_cached(name)
            if cached:
                return cached

            # reuse a url from resolve_url and skip the search
            known = image_url or self._urls.get(self._cache_prefix(name), "")
            if known:
                path = await self._download_direct(name, known)
                if path:
                    self._clear_miss(name)
                    return path

            path = await self._download_from_bangumi(name)
            if path is None:
                self._mark_miss(name)
            else:
                self._clear_miss(name)
            return path

    def _clear_miss(self, name: str) -> None:
        try:
            self._miss_path(name).unlink(missing_ok=True)
        except OSError:
            pass

    async def _download_direct(self, name: str, image_url: str) -> Path | None:
        try:
            import aiohttp
        except ImportError:
            return None
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {"User-Agent": USER_AGENT}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                return await self._download(session, image_url, name)
        except Exception:
            return None

    async def resolve_url(self, name: str, work: str = "", image_url: str = "") -> str:
        """Return the public url only, no download.

        QQ markdown needs ![](url) to inline an image; the platform fetches
        and rehosts it on its own.
        """
        if image_url.startswith("http"):
            return image_url
        if not name.strip():
            return ""

        key = self._cache_prefix(name)
        cached = self._urls.get(key)
        if isinstance(cached, str) and cached.startswith("http"):
            return cached

        try:
            import aiohttp
        except ImportError:
            return ""

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                for base in self.api_candidates():
                    url = await self._search_image_url(session, base, name)
                    if url:
                        self._urls[key] = url
                        self._save_urls()
                        return url
        except Exception:
            return ""
        return ""

    def _save_urls(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=str(self.cache_dir), prefix=".urls-", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._urls, f, ensure_ascii=False)
            os.replace(tmp, self.url_cache_path)
        except OSError:
            pass

    def _load_urls(self) -> None:
        try:
            data = json.loads(self.url_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            self._urls = {}
            return
        if isinstance(data, dict):
            self._urls = {
                str(k): str(v) for k, v in data.items() if isinstance(v, str)
            }
        else:
            self._urls = {}

    # ---------------- local files ----------------

    def _find_local(self, name: str, work: str) -> Path | None:
        if not self.local_dir or not self.local_dir.is_dir():
            return None
        candidates = [f"{name}{ext}" for ext in ALLOWED_EXT]
        candidates += [f"{name} ({work}){ext}" for ext in ALLOWED_EXT if work]
        for filename in candidates:
            path = self.local_dir / filename
            if path.is_file() and path.stat().st_size > 0:
                return path
        # fall back to normalized-name matching for case / spacing differences
        target = norm(name)
        for path in self.local_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in ALLOWED_EXT:
                continue
            if path.stat().st_size <= 0:
                continue
            stem = norm(path.stem)
            if stem == target or stem.startswith(target + "("):
                return path
        return None

    # ---------------- mirrors ----------------

    @staticmethod
    def _split_values(values: list[str] | str | None) -> list[str]:
        if values is None:
            return []
        if isinstance(values, str):
            raw = values.replace("，", ",").replace("\n", ",").split(",")
        else:
            raw = list(values)
        result: list[str] = []
        for item in raw:
            value = str(item).strip().rstrip("/")
            if value and value not in result:
                result.append(value)
        return result

    @classmethod
    def _normalize_mirrors(cls, mirrors: list[str] | str | None) -> list[str]:
        if mirrors is None:
            return list(BGM_IMAGE_MIRRORS)
        return cls._split_values(mirrors)

    @classmethod
    def _normalize_api_bases(
        cls,
        api_bases: list[str] | str | None,
        api_base: str | None = None,
    ) -> list[str]:
        """API candidates: configured bases with the official one appended last.

        Nothing configured -> built-in mirrors + official.
        Legacy single ``api_base`` string is still honoured.
        """
        configured = cls._split_values(api_bases)
        if not configured:
            legacy = cls._split_values(api_base)
            configured = legacy or list(BGM_API_MIRRORS)
        if BGM_API_BASE not in configured:
            configured.append(BGM_API_BASE)
        return configured

    def api_candidates(self) -> list[str]:
        """Order in which the API bases are tried."""
        return list(self.api_bases)

    def mirror_candidates(self, url: str) -> list[str]:
        """Rewrite one url onto every mirror, original last."""
        candidates: list[str] = []
        for mirror in self.mirrors:
            candidate = to_mirror(url, mirror)
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        if url and url not in candidates:
            candidates.append(url)
        return candidates

    # ---------------- cache ----------------

    def _cache_prefix(self, name: str) -> str:
        # versioned, so stale (possibly wrong) images stop being reused
        return hashlib.sha1(f"v{CACHE_VERSION}|{norm(name)}".encode("utf-8")).hexdigest()

    def _find_cached(self, name: str) -> Path | None:
        prefix = self._cache_prefix(name)
        for ext in ALLOWED_EXT:
            path = self.cache_dir / f"{prefix}{ext}"
            if path.is_file() and path.stat().st_size > 0:
                if time.time() - path.stat().st_mtime <= self.cache_seconds:
                    return path
        return None

    def _miss_path(self, name: str) -> Path:
        return self.cache_dir / f"{self._cache_prefix(name)}.miss"

    def _is_miss(self, name: str) -> bool:
        path = self._miss_path(name)
        return path.is_file() and time.time() - path.stat().st_mtime <= MISS_TTL

    def _mark_miss(self, name: str) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._miss_path(name).write_text("", encoding="utf-8")
        except OSError:
            pass

    # ---------------- network ----------------

    async def _download_from_bangumi(self, name: str) -> Path | None:
        """Try each API base, then download from the url it returns."""
        try:
            import aiohttp
        except ImportError:
            self.last_reason = "缺少 aiohttp"
            return None

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                for base in self.api_candidates():
                    urls = await self._search_image_urls(session, base, name)
                    if not urls:
                        continue
                    path = await self._download(session, urls, name)
                    if path:
                        return path
        except Exception as exc:
            self.last_reason = f"请求异常：{exc}"
            return None
        return None

    async def _search_image_urls(self, session, base: str, name: str) -> list[str]:
        """Search characters by name, return image urls, largest first.

        Exact name only. When nothing matches we return empty instead of
        falling back to the first hit, which used to attach the wrong
        character's picture to the card.
        """
        payload = {"keyword": name, "filter": {"nsfw": False}}
        try:
            async with session.post(
                f"{base.rstrip('/')}/v0/search/characters?limit=5", json=payload
            ) as resp:
                if resp.status != 200:
                    self.last_reason = f"搜索接口 {base} 返回 {resp.status}"
                    return []
                data = await resp.json(content_type=None)
        except Exception as exc:
            self.last_reason = f"搜索接口 {base} 异常：{exc}"
            return []

        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            self.last_reason = f"搜索接口 {base} 无结果"
            return []

        target = name_key(name)
        chosen = next(
            (
                it
                for it in items
                if isinstance(it, dict) and name_key(it.get("name", "")) == target
            ),
            None,
        )
        if chosen is None:
            self.last_reason = "没有同名角色（拒绝用近似结果凑数）"
            return []
        images = chosen.get("images") or {}
        urls: list[str] = []
        for key in ("large", "medium", "small", "grid"):
            url = images.get(key)
            if isinstance(url, str) and url.startswith("http") and url not in urls:
                urls.append(url)
        if not urls:
            self.last_reason = "角色没有立绘字段"
        return urls

    async def _search_image_url(self, session, base: str, name: str) -> str:
        """Legacy helper, single url only."""
        urls = await self._search_image_urls(session, base, name)
        return urls[0] if urls else ""

    async def _download(self, session, urls: list[str] | str, name: str) -> Path | None:
        """Try size by size, mirror by mirror, keep the first that lands."""
        candidates: list[str] = []
        for url in [urls] if isinstance(urls, str) else urls:
            for candidate in self.mirror_candidates(url):
                if candidate not in candidates:
                    candidates.append(candidate)

        for candidate in candidates:
            content = await self._read_image(session, candidate)
            if content is None:
                continue
            data, content_type = content
            forced_ext = ""
            if self.upscale:
                data, forced_ext = upscale_image(data)
            ext = forced_ext or self._guess_ext(content_type)
            path = self._write_atomic(
                self.cache_dir / f"{self._cache_prefix(name)}{ext}", data
            )
            if path:
                return path
        if not self.last_reason:
            self.last_reason = "所有镜像都下载失败"
        return None

    async def _read_image(self, session, url: str) -> tuple[bytes, str] | None:
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    self.last_reason = f"图片返回 {resp.status}（{url[:60]}…）"
                    return None
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
                    self.last_reason = f"返回的不是图片（{content_type}）"
                    return None
                content = await resp.read()
        except Exception:
            return None
        if not content or len(content) > MAX_BYTES:
            return None
        return content, content_type

    @staticmethod
    def _guess_ext(content_type: str) -> str:
        for marker, ext in (("png", ".png"), ("webp", ".webp"), ("gif", ".gif")):
            if marker in content_type:
                return ext
        return ".jpg"

    @staticmethod
    def _write_atomic(path: Path, content: bytes) -> Path | None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".img-", suffix=".tmp")
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.replace(tmp, path)
            return path
        except OSError:
            return None
