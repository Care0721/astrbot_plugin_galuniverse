"""Bangumi 角色池：从镜像 API 抽取「名单外」的角色。

为什么单独一个模块：
- 抽签是核心功能，必须离线可用 —— 任何网络失败都只返回空，由调用方回落本地名单；
- 同一天的结果必须稳定 —— 命中过的抽签结果落盘，即使接口改了也不会变；
- 接口优先走镜像，官方作为最后一层兜底，和立绘下载保持一致。

缓存结构（``bgm_pool.json``）::

    {
      "works": {"CLANNAD": {"at": 1690000000, "items": [...]}},
      "picks": {"<sha1(seed)>": {"name": "古河渚", "work": "CLANNAD", "image": "https://..."}}
    }
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from .fortune import pick_index
from .models import Heroine
from .store import norm as _norm

POOL_FILE = "bgm_pool.json"
WORKS_TTL = 7 * 86400
"""作品角色表缓存 7 天，避免每次抽签都打接口。"""

FAIL_TTL = 3600
"""接口失败后 1 小时内不再重试，防止网络异常时每条消息都卡住。"""

MAX_ITEMS = 40
"""单个作品最多缓存多少个角色，控制文件体积。"""

MIN_POOL = 6
"""作品可用角色少于这个数就不用它抽 —— 否则每次都抽到同一两个人。"""


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _subject_score(item: dict, target: str) -> int:
    """作品匹配打分：完全同名 > 前缀相同 > 互相包含；0 表示不匹配。

    Bangumi 的作品搜索是按关键词模糊匹配的，直接取第一条经常张冠李戴
    （例如搜「缘之空」会先返回「缘之绳」），所以必须自己算相似度。
    """
    if not target:
        return 0
    best = 0
    for field in ("name", "name_cn"):
        name = _norm(item.get(field) or "")
        if not name:
            continue
        if name == target:
            return 100
        if name.startswith(target) or target.startswith(name):
            best = max(best, 80)
        elif len(target) >= 2 and (target in name or name in target):
            best = max(best, 60)
    return best


class BangumiPool:
    """按作品名从 Bangumi（镜像优先）拉角色，并做确定性抽取。"""

    def __init__(
        self,
        cache_dir: Path,
        api_bases: list[str],
        timeout: float = 3.5,
    ) -> None:
        self.path = Path(cache_dir) / POOL_FILE
        self.api_bases = [b.rstrip("/") for b in api_bases if str(b).strip()]
        self.timeout = max(1.0, float(timeout))
        self._locks: dict[str, asyncio.Lock] = {}
        self.data: dict[str, dict[str, Any]] = {"works": {}, "picks": {}, "subjects": {}}
        self._load()

    # ---------------- 持久化 ----------------

    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(data, dict):
            return
        works = data.get("works")
        picks = data.get("picks")
        subjects = data.get("subjects")
        self.data = {
            "works": works if isinstance(works, dict) else {},
            "picks": picks if isinstance(picks, dict) else {},
            "subjects": subjects if isinstance(subjects, dict) else {},
        }

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=str(self.path.parent), prefix=".pool-", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # ---------------- 抽取 ----------------

    async def draw(self, work: str, seed: str) -> tuple[Heroine, str] | None:
        """在 ``work`` 的角色里确定性地取一个，返回 (角色, 立绘地址)。

        失败返回 ``None``，调用方应回落到本地名单。
        """
        work = (work or "").strip()
        if not work:
            return None

        key = _digest(seed)
        cached = self.data["picks"].get(key)
        if isinstance(cached, dict) and cached.get("name"):
            return (
                Heroine(name=str(cached["name"]), work=str(cached.get("work") or work)),
                str(cached.get("image") or ""),
            )

        items = await self._characters(work)
        if len(items) < MIN_POOL:
            # 角色太少的作品直接弃用，避免「一抽就是那一个」
            return None

        chosen = items[pick_index(seed, len(items))]
        name = str(chosen.get("name") or "").strip()
        if not name:
            return None
        image = str(chosen.get("image") or "")

        self.data["picks"][key] = {"name": name, "work": work, "image": image}
        self._trim_picks()
        self.save()
        return Heroine(name=name, work=work), image

    def _trim_picks(self) -> None:
        picks = self.data["picks"]
        if len(picks) <= 2000:
            return
        # 只保留最近写入的一批，避免文件无限膨胀
        for old in list(picks)[: len(picks) - 2000]:
            picks.pop(old, None)

    # ---------------- 接口 ----------------

    async def _characters(self, work: str) -> list[dict[str, str]]:
        entry = self.data["works"].get(work)
        now = time.time()
        if isinstance(entry, dict):
            age = now - float(entry.get("at") or 0)
            items = entry.get("items")
            ttl = FAIL_TTL if entry.get("fail") else WORKS_TTL
            if age <= ttl and isinstance(items, list):
                return [it for it in items if isinstance(it, dict) and it.get("name")]

        lock = self._locks.setdefault(work, asyncio.Lock())
        async with lock:
            # 双检：等锁期间可能已被别的协程填好
            entry = self.data["works"].get(work)
            if isinstance(entry, dict):
                age = time.time() - float(entry.get("at") or 0)
                items = entry.get("items")
                ttl = FAIL_TTL if entry.get("fail") else WORKS_TTL
                if age <= ttl and isinstance(items, list):
                    return [it for it in items if isinstance(it, dict) and it.get("name")]

            items = await self._fetch_characters(work)
            self.data["works"][work] = {
                "at": time.time(),
                "items": items,
                "fail": not items,
            }
            self.save()
            return items

    async def _fetch_characters(self, work: str) -> list[dict[str, str]]:
        """作品名 → 作品 ID → 角色列表。

        注意 Bangumi 的 ``/v0/search/characters`` 是按**角色名**搜的，
        用作品名去搜会返回空，所以这里走「搜作品 → 取作品角色」两步。
        """
        try:
            import aiohttp
        except ImportError:
            return []

        headers = {
            "User-Agent": "CareGalUniverse/2.1.0 (+https://github.com/Care0721/astrbot_plugin_galuniverse)",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        subjects = self.data.setdefault("subjects", {})
        for base in self.api_bases:
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    subject_id = subjects.get(work)
                    if not isinstance(subject_id, int):
                        subject_id = await self._search_subject(session, base, work)
                        if subject_id:
                            subjects[work] = subject_id
                    if not subject_id:
                        continue
                    items = await self._subject_characters(session, base, subject_id)
            except Exception:
                continue
            if items:
                return items[:MAX_ITEMS]
        return []

    async def _search_subject(self, session, base: str, work: str) -> int | None:
        payload = {"keyword": work, "filter": {"type": [4]}}
        async with session.post(f"{base}/v0/search/subjects?limit=10", json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)

        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            return None

        target = _norm(work)
        best: tuple[int, dict] | None = None
        for item in items:
            if not isinstance(item, dict):
                continue
            score = _subject_score(item, target)
            if score and (best is None or score > best[0]):
                best = (score, item)
        # 完全没有像样的匹配就当作查不到，宁可回落本地名单也不要张冠李戴
        if best is None:
            return None
        try:
            return int(best[1].get("id"))
        except (TypeError, ValueError):
            return None

    async def _subject_characters(self, session, base: str, subject_id: int) -> list[dict[str, str]]:
        async with session.get(f"{base}/v0/subjects/{subject_id}/characters") as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)

        if not isinstance(data, list):
            return []

        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            relation = str(item.get("relation") or "").strip()
            if relation and relation not in ("主角", "配角"):
                continue  # 客串角色对「今日老婆」没意义
            name = str(item.get("name") or "").strip()
            if not name or name in seen:
                continue
            images = item.get("images") or {}
            image = ""
            if isinstance(images, dict):
                for field in ("large", "medium", "small", "grid"):
                    url = images.get(field)
                    if isinstance(url, str) and url.startswith("http"):
                        image = url
                        break
            if not image:
                continue  # 没立绘的角色出卡体验差，直接跳过
            seen.add(name)
            result.append({"name": name, "image": image})
        return result
