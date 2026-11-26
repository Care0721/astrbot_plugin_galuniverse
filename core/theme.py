"""视觉规范常量：分隔线、签运映射、链接与路径压缩。

约束来源：QQ/微信客户端中文字符与 emoji 宽度不一致，
因此所有模板都避免表格对齐，只用线性排列 + 固定宽度分隔线。
"""

from __future__ import annotations

from urllib.parse import urlparse

DIVIDER = "━" * 12
"""统一分隔线：12 个全角字符，手机端不会折行。"""

FORTUNE_STYLES: dict[str, tuple[str, int]] = {
    "超大吉": ("🌈", 7),
    "大吉": ("✨", 6),
    "中吉": ("🍀", 5),
    "小吉": ("🌤️", 4),
    "末吉": ("🌥️", 3),
    "平": ("☁️", 2),
    "凶": ("🌧", 1),
}
DEFAULT_FORTUNE_STYLE = ("🎐", 4)

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def fortune_style(fortune: str) -> tuple[str, int]:
    return FORTUNE_STYLES.get(fortune.strip(), DEFAULT_FORTUNE_STYLE)


def fortune_bar(fortune: str, size: int = 7) -> str:
    """签运进度条，凶=1 格，超大吉=7 格。"""
    _, filled = fortune_style(fortune)
    filled = max(1, min(size, filled))
    return "▰" * filled + "▱" * (size - filled)


def numbered(index: int) -> str:
    """1 → ①；超过 20 时退回 "21."。"""
    if 1 <= index <= len(CIRCLED):
        return CIRCLED[index - 1]
    return f"{index}."


def short_link(url: str, style: str = "domain") -> str:
    """把长链接压缩成 域名/首段路径，省字符且仍可辨识。"""
    url = (url or "").strip()
    if not url or style == "hidden":
        return ""
    if style == "full":
        return url

    candidate = url if "://" in url else f"https://{url}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return url
    host = parsed.netloc
    if not host:
        return url
    segments = [s for s in parsed.path.split("/") if s]
    return f"{host}/{segments[0]}" if segments else host


def short_path(path: str) -> str:
    """只保留最后两段路径，避免刷屏。"""
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else str(path)
