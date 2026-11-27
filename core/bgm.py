"""Draws characters that are not in the bundled list, via a Bangumi mirror.

The daily draw must not depend on the network, so every failure here returns
None and the caller falls back to the local list. Results are cached on disk,
which keeps a day's pick stable and reproducible offline.

bgm_pool.json holds two maps:
  works: subject name -> character list (7 day TTL)
  picks: seed hash -> the character picked for it (kept forever)
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
from typing import Any

from .fortune import pick_index
from .models import Heroine
from .store import name_key as _name_key
from .store import norm as _norm

BGM_API_BASE = "https://api.bgm.tv"
"""Official API. Gets a shorter timeout, it is unreachable far more often."""

POOL_FILE = "bgm_pool.json"
WORKS_TTL = 7 * 86400
"""Character lists are cached for 7 days."""

BASE_COOLDOWN = 600
"""Skip an API base for 10 minutes after it times out. The characters endpoint
of the public mirror has been dead for hours at a time; without this every
draw would sit through the same timeout."""

FAIL_TTL = 600
"""Back off for 10 minutes after a failure. An hour is too long: one bad
request used to disable the mirror pool for the rest of the day."""

MAX_ITEMS = 40
"""Cap per subject so the cache file stays small."""

MIN_POOL = 6
"""Subjects with fewer usable characters are skipped, or the same face keeps showing up."""


def _host(url: str) -> str:
    """Bare host for log lines."""
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _has_kana(text: str) -> bool:
    """True if the text contains kana, i.e. a transliteration rather than a kanji name."""
    return any(
        "\u3040" <= ch <= "\u30ff" or "\uff66" <= ch <= "\uff9f" for ch in text
    )


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _subject_score(item: dict, target: str) -> int:
    """Similarity score for a subject; 0 means no relation.

    Bangumi's subject search is loose and often ranks an unrelated title
    first, so the score has to be computed locally.
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
    """Fetches characters per subject and picks one from the seed."""

    def __init__(
        self,
        cache_dir: Path,
        api_bases: list[str],
        timeout: float = 7.0,
    ) -> None:
        self.path = Path(cache_dir) / POOL_FILE
        self.api_bases = [b.rstrip("/") for b in api_bases if str(b).strip()]
        self.timeout = max(1.0, float(timeout))
        self.last_reason = ""
        """Why the last API call failed. The caller logs it."""
        self._cooldown: dict[str, float] = {}
        """base -> timestamp until which it is skipped."""
        self._locks: dict[str, asyncio.Lock] = {}
        self.data: dict[str, dict[str, Any]] = {"works": {}, "picks": {}, "subjects": {}}
        self._load()

    # ---------------- persistence ----------------

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

    # ---------------- draw ----------------

    async def draw(self, work: str, seed: str) -> tuple[Heroine, str] | None:
        """Pick one character of this subject by seed. Returns (heroine, url).

        None means "cannot use this subject", the caller falls back to the
        local list.
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
            # skip subjects with too few characters
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
        # keep only the most recent picks so the file does not grow forever
        for old in list(picks)[: len(picks) - 2000]:
            picks.pop(old, None)

    # ---------------- image lookup by subject ----------------

    async def find_image(self, work: str, name: str) -> str:
        """Find this character inside the subject, return its image url or "".

        Exact name first, then a looser prefix match (冬马和纱 -> 冬馬かずさ).
        Staying inside one subject is what makes the loose match safe; a
        global search is where the wrong character gets picked.
        """
        if not work or not name:
            return ""
        try:
            items = await self._characters(work)
        except Exception:
            return ""
        if not items:
            return ""

        target = _name_key(name)
        for item in items:
            if _name_key(str(item.get("name") or "")) == target:
                return str(item.get("image") or "")

        if len(target) >= 2:
            head = target[:2]
            hits = [
                item
                for item in items
                if _name_key(str(item.get("name") or "")).startswith(head)
            ]
            # only accept "same surname + kana given name":
            #   冬马和纱 -> 冬馬かずさ  (kana; the Chinese name never matches literally)
            #   水无月椰子 -> 水無月妙子 is someone else, must not match
            if len(hits) == 1:
                rest = _name_key(str(hits[0].get("name") or ""))[len(head) :]
                if _has_kana(rest):
                    return str(hits[0].get("image") or "")
        return ""

    # ---------------- api ----------------

    def _usable_bases(self) -> list[str]:
        """Bases not cooling down. An empty list means give up immediately."""
        now = time.time()
        return [b for b in self.api_bases if self._cooldown.get(b, 0) <= now]

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
            # double check: another coroutine may have filled it while we waited
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
        """Resolve the subject name to an id, then list its characters.

        /v0/search/characters matches character names only, so searching a
        subject title there returns nothing. Two steps are required.
        """
        try:
            import aiohttp
        except ImportError:
            return []

        headers = {
            "User-Agent": "CareGalUniverse/2.1.4 (+https://github.com/Care0721/astrbot_plugin_galuniverse)",
            "Content-Type": "application/json",
        }
        # connect is capped separately: a dead mirror should fail fast,
        # but the two chained requests need room to finish on a slow one.
        # the official host gets a shorter budget, it is unreachable far more often
        mirror_timeout = aiohttp.ClientTimeout(total=self.timeout, connect=5)
        official_timeout = aiohttp.ClientTimeout(total=3, connect=3)
        subjects = self.data.setdefault("subjects", {})
        for base in self._usable_bases():
            timeout = official_timeout if base == BGM_API_BASE else mirror_timeout
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
            except asyncio.TimeoutError:
                self.last_reason = f"{_host(base)} 响应超时"
                self._cooldown[base] = time.time() + BASE_COOLDOWN
                continue
            except Exception as exc:
                self.last_reason = f"{_host(base)} 连接失败（{type(exc).__name__}）"
                self._cooldown[base] = time.time() + BASE_COOLDOWN
                continue
            if items:
                self.last_reason = ""
                return items[:MAX_ITEMS]
            self.last_reason = f"{_host(base)} 没有可用角色"
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
        # no decent match -> treat as not found and fall back to the local list
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
