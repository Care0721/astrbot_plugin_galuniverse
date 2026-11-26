"""GalUniverse 核心逻辑包（纯标准库，可脱离 AstrBot 单测）。"""

from .fortune import DEFAULT_FORTUNES, daily_seed, pick_advice, pick_fortune, today_key
from .models import Heroine, Spot
from .parser import chunk_text, normalize, split_fields, split_first, strip_command
from .store import GalStore, StateStore

__all__ = [
    "DEFAULT_FORTUNES",
    "GalStore",
    "Heroine",
    "Spot",
    "StateStore",
    "chunk_text",
    "daily_seed",
    "normalize",
    "pick_advice",
    "pick_fortune",
    "split_fields",
    "split_first",
    "strip_command",
    "today_key",
]
