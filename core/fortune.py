"""确定性抽签：同一用户同一天结果固定，跨进程、跨重启都一致。

不用 ``random`` 的字符串种子（实现细节依赖 CPython 版本），
直接对 sha256 摘要取模，行为可预测、可复现。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_FORTUNES = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶"]


def now_in(tz_name: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:  # 时区名写错时退回服务器本地时间
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
        return "记得存档。"
    return options[pick_index(f"{seed}|advice", len(options))]


def daily_seed(scope_key: str, date_key: str, reroll: int = 0) -> str:
    return f"{scope_key}|{date_key}|{reroll}"
