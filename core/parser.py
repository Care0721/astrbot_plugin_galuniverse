"""消息解析与文本工具。

OneBot（aiocqhttp）下 ``event.message_str`` 是去掉 CQ 码后的纯文本，
但会保留唤醒前缀（``/``、``!``、``#`` 等，取决于 AstrBot 配置），
因此这里统一做前缀剥离和全角空格归一化，避免参数解析错位。
"""

from __future__ import annotations

import re

_PREFIX_CHARS = "/!#／！＃.。、~～"
_WS = re.compile(r"[\s\u3000]+")


def normalize(text: str) -> str:
    """合并连续空白（含全角空格），去掉首尾空白。"""
    return _WS.sub(" ", str(text or "")).strip()


def strip_prefix(text: str) -> str:
    return normalize(text).lstrip(_PREFIX_CHARS).strip()


def strip_command(text: str, *names: str) -> str:
    """剥离唤醒前缀和指令名，返回参数部分。"""
    body = strip_prefix(text)
    for name in names:
        if not name:
            continue
        if body.lower().startswith(name.lower()):
            return body[len(name) :].strip()
    return body


def split_first(text: str) -> tuple[str, str]:
    """按第一个空白切成 (头, 剩余)。"""
    body = normalize(text)
    if not body:
        return "", ""
    parts = body.split(" ", 1)
    return parts[0], (parts[1].strip() if len(parts) > 1 else "")


def split_fields(text: str) -> list[str]:
    """按 ``|`` / ``｜`` 切分，用于 游戏|地点|链接 格式。"""
    return [p.strip() for p in re.split(r"[|｜]", normalize(text)) if p.strip()]


def parse_int(text: str, default: int) -> int:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return default


def chunk_text(text: str, limit: int = 1500) -> list[str]:
    """按行切分长文本，避免 OneBot 单条消息过长被截断或拒发。"""
    limit = max(200, int(limit))
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for line in text.splitlines():
        # 单行超长时硬切
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
