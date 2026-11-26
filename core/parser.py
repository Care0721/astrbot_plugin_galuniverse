"""Small helpers for parsing command arguments.

event.message_str already has CQ codes stripped, but the wake prefix
(/ ! # ...) is still there depending on the AstrBot config, so we peel it here.
"""

from __future__ import annotations

import re

_PREFIX_CHARS = "/!#／！＃.。、~～"
_WS = re.compile(r"[\s\u3000]+")


def normalize(text: str) -> str:
    """Collapse runs of whitespace (incl. full-width space) and trim."""
    return _WS.sub(" ", str(text or "")).strip()


def strip_prefix(text: str) -> str:
    return normalize(text).lstrip(_PREFIX_CHARS).strip()


def strip_command(text: str, *names: str) -> str:
    """Strip the prefix and command name, return the rest."""
    body = strip_prefix(text)
    for name in names:
        if not name:
            continue
        if body.lower().startswith(name.lower()):
            return body[len(name) :].strip()
    return body


def split_first(text: str) -> tuple[str, str]:
    """Split on the first space."""
    body = normalize(text)
    if not body:
        return "", ""
    parts = body.split(" ", 1)
    return parts[0], (parts[1].strip() if len(parts) > 1 else "")


def split_fields(text: str) -> list[str]:
    """Split on | or ｜, used for "work|place|link"."""
    return [p.strip() for p in re.split(r"[|｜]", normalize(text)) if p.strip()]


def parse_int(text: str, default: int) -> int:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return default


def chunk_text(text: str, limit: int = 1500) -> list[str]:
    """Split long text by lines. QQ drops messages that are too long."""
    limit = max(200, int(limit))
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for line in text.splitlines():
        # hard cut when a single line is over the limit
        while len(line) > limit:
            if buf:
                chunks.append("\n".join(buf))
                buf, size = [], 0
            chunks.append(line[:limit])
            line = line[limit:]
        if size + len(line) + 1 > limit and buf:
            chunks.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return [c for c in chunks if c.strip()]
