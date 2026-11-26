"""角色立绘获取：本地优先，其次 Bangumi，失败静默降级。

设计原则：
- 任何网络异常都不能影响「今日老婆」正常出卡；
- 本地 ``data/plugin_data/<plugin>/images/`` 可放同名图片覆盖在线源；
- 下载结果落盘缓存，命中缓存不发请求；
- 搜索失败写 miss 标记，一天内不再重试，避免拖慢每次抽签。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from .store import norm

BGM_API_BASE = "https://api.bgm.tv"
"""Bangumi 官方 API，始终作为最后一层兜底。"""

BGM_API_MIRRORS = ("https://bgmapi.sakuraspark.fun",)
"""Bangumi API 反代。官方域名在部分网络环境下不可达，优先走镜像。"""

BGM_IMAGE_MIRRORS = (
    "https://bgmimg.sakuraspark.fun",
    "https://bgmlain.waterbee.cc",
    "https://bgm.sakuraspark.fun",
)
"""图片镜像：按顺序尝试，全部失败后回源官方。"""

USER_AGENT = "CareGalUniverse/2.0.3 (https://github.com/Care0721/astrbot_plugin_galuniverse)"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_BYTES = 8 * 1024 * 1024
MISS_TTL = 86400


def to_mirror(url: str, mirror: str) -> str:
    """把 lain.bgm.tv 的图片地址改写到镜像站，保留 path 与 query。

    镜像站按原路径反代 ``lain.bgm.tv``，所以只替换 host：
    ``https://lain.bgm.tv/pic/crt/l/00/01/1_crt.jpg?r=1``
    → ``https://bgmlain.waterbee.cc/pic/crt/l/00/01/1_crt.jpg?r=1``
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
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_dir = Path(local_dir) if local_dir else None
        self.source = source if source in {"auto", "bangumi", "local", "off"} else "auto"
        self.api_bases = self._normalize_api_bases(api_bases, api_base)
        self.mirrors = self._normalize_mirrors(mirrors)
        self.cache_seconds = max(1, int(cache_days)) * 86400
        self.timeout = max(1.0, float(timeout))
        self._locks: dict[str, asyncio.Lock] = {}

    # ---------------- 对外入口 ----------------

    async def fetch(self, name: str, work: str = "", image_url: str = "") -> Path | None:
        """取立绘：本地 → 缓存 → miss → 在线下载。

        ``image_url`` 由 Bangumi 角色池直接给出时跳过搜索，少打一次接口。
        """
        if self.source == "off" or not name.strip():
            return None

        local = self._find_local(name, work)
        if local:
            return local
        if self.source == "local":
            return None

        cached = self._find_cached(name)
        if cached:
            return cached
        if self._is_miss(name):
            return None

        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            cached = self._find_cached(name)
            if cached:
                return cached
            if image_url:
                path = await self._download_direct(name, image_url)
                if path:
                    return path
            path = await self._download_from_bangumi(name)
            if path is None:
                self._mark_miss(name)
            return path

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

    # ---------------- 本地 ----------------

    def _find_local(self, name: str, work: str) -> Path | None:
        if not self.local_dir or not self.local_dir.is_dir():
            return None
        candidates = [f"{name}{ext}" for ext in ALLOWED_EXT]
        candidates += [f"{name} ({work}){ext}" for ext in ALLOWED_EXT if work]
        for filename in candidates:
            path = self.local_dir / filename
            if path.is_file() and path.stat().st_size > 0:
                return path
        # 大小写/空格差异兜底：按归一化名匹配
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

    # ---------------- 镜像 ----------------

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
        """API 地址列表：镜像优先，官方恒定兜底。

        - 未配置 → 内置镜像 + 官方；
        - 配置了 ``api_bases``（列表）→ 配置项 + 官方；
        - 只配置了旧版 ``api_base``（字符串）→ 该地址 + 官方。
        """
        configured = cls._split_values(api_bases)
        if not configured:
            legacy = cls._split_values(api_base)
            configured = legacy or list(BGM_API_MIRRORS)
        if BGM_API_BASE not in configured:
            configured.append(BGM_API_BASE)
        return configured

    def api_candidates(self) -> list[str]:
        """角色搜索的接口候选顺序。"""
        return list(self.api_bases)

    def mirror_candidates(self, url: str) -> list[str]:
        """按配置顺序生成候选地址，最后回源官方。"""
        candidates: list[str] = []
        for mirror in self.mirrors:
            candidate = to_mirror(url, mirror)
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        if url and url not in candidates:
            candidates.append(url)
        return candidates

    # ---------------- 缓存 ----------------

    def _cache_prefix(self, name: str) -> str:
        return hashlib.sha1(norm(name).encode("utf-8")).hexdigest()

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

    # ---------------- 网络 ----------------

    async def _download_from_bangumi(self, name: str) -> Path | None:
        """接口按「镜像 → 官方」逐个试；取到图片地址后再按镜像顺序下载。"""
        try:
            import aiohttp
        except ImportError:
            return None

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                for base in self.api_candidates():
                    image_url = await self._search_image_url(session, base, name)
                    if not image_url:
                        continue
                    path = await self._download(session, image_url, name)
                    if path:
                        return path
        except Exception:
            return None
        return None

    async def _search_image_url(self, session, base: str, name: str) -> str:
        payload = {"keyword": name, "filter": {"nsfw": False}}
        try:
            async with session.post(
                f"{base.rstrip('/')}/v0/search/characters?limit=5", json=payload
            ) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json(content_type=None)
        except Exception:
            return ""

        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            return ""

        target = norm(name)
        chosen = next(
            (it for it in items if isinstance(it, dict) and norm(it.get("name", "")) == target),
            items[0] if isinstance(items[0], dict) else None,
        )
        if not chosen:
            return ""
        images = chosen.get("images") or {}
        for key in ("large", "medium", "small", "grid"):
            url = images.get(key)
            if isinstance(url, str) and url.startswith("http"):
                return url
        return ""

    async def _download(self, session, url: str, name: str) -> Path | None:
        """按镜像顺序依次尝试，最后回源官方，任一成功即落盘。"""
        for candidate in self.mirror_candidates(url):
            content = await self._read_image(session, candidate)
            if content is None:
                continue
            ext = self._guess_ext(content[1])
            return self._write_atomic(
                self.cache_dir / f"{self._cache_prefix(name)}{ext}", content[0]
            )
        return None

    async def _read_image(self, session, url: str) -> tuple[bytes, str] | None:
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
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
