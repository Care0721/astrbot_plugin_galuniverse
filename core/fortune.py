"""Daily draw. Same scope + same day always lands on the same result.

Not using random() on purpose: its string seeding follows the CPython version,
so results would shift after a Python upgrade.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_FORTUNES = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶"]

DEFAULT_ADVICE = [
    "记得存档。",
    "今天别熬太晚。",
    "适合把没推完的那条线推完。",
    "去把 OP 再听一遍。",
    "想见的人就发条消息。",
    "路过便利店买瓶热饮。",
    "先把桌面收拾一下再开工。",
    "别跳过 ED。",
    "手边放杯水，别光顾着推线。",
    "抽空把存档备份一下。",
    "早点睡，明天还有新剧情。",
    "今天适合重看喜欢的 CG。",
]


def now_in(tz_name: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:  # bad tz name, fall back to server local time
        return datetime.now(timezone.utc).astimezone()


def today_key(tz_name: str) -> str:
    return now_in(tz_name).strftime("%Y-%m-%d")


def _digest(*parts: str) -> bytes:
    raw = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(raw).digest()


def pick_index(seed: str, size: int) -> int:
    if size <= 0:
        return 0
    return int.from_bytes(_digest(seed)[:8], "big") % size


def pick_fortune(seed: str, pool: list[str] | None = None) -> str:
    options = [str(x).strip() for x in (pool or DEFAULT_FORTUNES) if str(x).strip()]
    if not options:
        options = DEFAULT_FORTUNES
    return options[pick_index(f"{seed}|fortune", len(options))]


def pick_advice(seed: str, pool: list[str] | None = None) -> str:
    options = [str(x).strip() for x in (pool or []) if str(x).strip()]
    if not options:
        options = DEFAULT_ADVICE
    return options[pick_index(f"{seed}|advice", len(options))]


def daily_seed(scope_key: str, date_key: str, reroll: int = 0) -> str:
    return f"{scope_key}|{date_key}|{reroll}"
