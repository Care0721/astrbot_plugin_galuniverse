"""Style constants: divider, fortune levels, link and path formatting.

Do not fight the clients over character widths - just stack lines.
"""

from __future__ import annotations

from urllib.parse import urlparse

DIVIDER = "━" * 12
"""12 full-width chars, fits one line on mobile."""

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
    """Fortune bar: 凶 is 1 block, 超大吉 is 7."""
    _, filled = fortune_style(fortune)
    filled = max(1, min(size, filled))
    return "▰" * filled + "▱" * (size - filled)


def numbered(index: int) -> str:
    """1 -> ①; past 20 fall back to plain "21."."""
    if 1 <= index <= len(CIRCLED):
        return CIRCLED[index - 1]
    return f"{index}."


def clickable(url: str) -> str:
    """Add the scheme so clients turn it into a tappable link.

    With https:// most clients auto-linkify; without it you just get text.
    """
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if "://" in url:
        return url
    return "https://" + url.lstrip("/")


def short_link(url: str, style: str = "full") -> str:
    """Render a link: full URL (default) / domain + first segment / nothing."""
    url = (url or "").strip()
    if not url or style == "hidden":
        return ""
    if style == "full":
        return clickable(url)

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
    """Keep the last two segments, full paths are too noisy."""
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else str(path)
