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

from .store import norm

BGM_SEARCH_URL = "https://api.bgm.tv/v0/search/characters"
USER_AGENT = "CareGalUniverse/2.0 (https://github.com/Care0721/astrbot_plugin_galuniverse)"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_BYTES = 8 * 1024 * 1024
MISS_TTL = 86400


class ImageFetcher:
    def __init__(
        self,
        cache_dir: Path,
        local_dir: Path | None = None,
        source: str = "auto",
        cache_days: int = 30,
        timeout: float = 6.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_dir = Path(local_dir) if local_dir else None
        self.source = source if source in {"auto", "bangumi", "local", "off"} else "auto"
        self.cache_seconds = max(1, int(cache_days)) * 86400
        self.timeout = max(1.0, float(timeout))
        self._locks: dict[str, asyncio.Lock] = {}

    # ---------------- 对外入口 ----------------

    async def fetch(self, name: str, work: str = "") -> Path | None:
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
            path = await self._download_from_bangumi(name)
            if path is None:
                self._mark_miss(name)
            return path

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
        try:
            import aiohttp
        except ImportError:
            return None

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                image_url = await self._search_image_url(session, name)
                if not image_url:
                    return None
                return await self._download(session, image_url, name)
        except Exception:
            return None

    async def _search_image_url(self, session, name: str) -> str:
        payload = {"keyword": name, "filter": {"nsfw": False}}
        async with session.post(
            f"{BGM_SEARCH_URL}?limit=5", json=payload
        ) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json(content_type=None)

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
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                return None
            content = await resp.read()
        if not content or len(content) > MAX_BYTES:
            return None

        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"

        return self._write_atomic(self.cache_dir / f"{self._cache_prefix(name)}{ext}", content)

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
