"""Builds the text cards: title / divider / body / footer, that's it.

No tables, no space padding - CJK and emoji widths differ per client,
so alignment always breaks. Plain line breaks are safer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import Heroine, Spot
from .theme import DIVIDER, fortune_bar, fortune_style, numbered, short_link, short_path


def card(header: str, body: Iterable[str], footer: Sequence[str] = ()) -> str:
    """Assemble one card. Blank lines are dropped so we never get double dividers."""
    body_lines = [line.rstrip() for line in body if line and line.strip()]
    footer_lines = [line.rstrip() for line in footer if line and line.strip()]

    lines = [header.strip(), DIVIDER]
    if body_lines:
        lines.extend(body_lines)
        if footer_lines:
            lines.append(DIVIDER)
    if footer_lines:
        lines.extend(footer_lines)
    return "\n".join(lines)


# ---------------- daily draw ----------------

DAILY_TITLE = "🌙 今日老婆"

MARKDOWN_IMAGE_W = 240
MARKDOWN_IMAGE_H = 320
"""Size hint for QQ markdown images (3:4, most character art is portrait)."""


def _fortune_line(fortune: str, markdown: bool = False) -> str:
    emoji, _ = fortune_style(fortune)
    bar = fortune_bar(fortune)
    return f"{emoji} **{fortune}** {bar}" if markdown else f"{emoji} {fortune} {bar}"


def _daily_name(heroine: Heroine, markdown: bool = False) -> str:
    """The name is the headline: boxed in plain text, H1 in markdown."""
    label = heroine.label
    return f"# {label}" if markdown else f"【{label}】"


def _daily_body_lines(
    fortune: str,
    advice: str,
    spot: Spot | None,
    link_style: str,
    markdown: bool = False,
) -> list[str]:
    lines = [_fortune_line(fortune, markdown)]
    if advice:
        lines.append(f"> {advice}" if markdown else advice)
    if spot is not None:
        lines.append(f"📍 {spot.name}")
        link = short_link(spot.link, link_style)
        if link:
            # markdown: wrap in <url> so the full address shows and stays tappable
            # plain text: bare URL, clients linkify it themselves
            lines.append(f"<{link}>" if markdown else f"🔗 {link}")
    return lines


def _daily_footer_lines(
    date_key: str,
    reroll: int,
    can_reroll: bool,
    spot: Spot | None,
    spot_total: int,
) -> list[str]:
    tail = date_key + (f" · 第 {reroll + 1} 抽" if reroll else "")
    hint = "换一位发 /换老婆" if can_reroll else "明天再来"
    lines = [f"{tail} · {hint}"]
    if spot is not None and spot_total > 1:
        lines.append(f"这部作品还有 {spot_total} 处 · /圣地巡礼 {spot.work}")
    return lines


def daily_parts(
    heroine: Heroine,
    fortune: str,
    advice: str,
    date_key: str,
    reroll: int = 0,
    can_reroll: bool = True,
    spot: Spot | None = None,
    spot_total: int = 0,
    link_style: str = "full",
) -> tuple[str, str]:
    """Split the card right after the name so the image can go in between.

    OneBot 这类支持图文混排的平台用它实现「图片插在名字下面、只发一条消息」。
    """
    head = "\n".join([DAILY_TITLE, DIVIDER, _daily_name(heroine)]) + "\n"
    tail = "\n".join(
        _daily_body_lines(fortune, advice, spot, link_style)
        + [DIVIDER]
        + _daily_footer_lines(date_key, reroll, can_reroll, spot, spot_total)
    )
    return head, tail


def daily_card(
    heroine: Heroine,
    fortune: str,
    advice: str,
    date_key: str,
    reroll: int = 0,
    can_reroll: bool = True,
    spot: Spot | None = None,
    spot_total: int = 0,
    link_style: str = "full",
) -> str:
    head, tail = daily_parts(
        heroine,
        fortune,
        advice,
        date_key,
        reroll=reroll,
        can_reroll=can_reroll,
        spot=spot,
        spot_total=spot_total,
        link_style=link_style,
    )
    return head + tail


def daily_markdown(
    heroine: Heroine,
    fortune: str,
    advice: str,
    date_key: str,
    reroll: int = 0,
    can_reroll: bool = True,
    spot: Spot | None = None,
    spot_total: int = 0,
    link_style: str = "full",
    image_url: str = "",
) -> str:
    """Markdown variant for QQ official: image inlined via ![](url) under the name.

    注意 QQ 的图片语法**必须带尺寸**（``![alt #宽px #高px](url)``），
    只写 ``![alt](url)`` 会被当成链接、图不出来。
    """
    lines = [f"## {DAILY_TITLE}", _daily_name(heroine, markdown=True)]
    if image_url:
        lines.append(f"![{heroine.name} #{MARKDOWN_IMAGE_W}px #{MARKDOWN_IMAGE_H}px]({image_url})")
    lines.extend(_daily_body_lines(fortune, advice, spot, link_style, markdown=True))
    lines.append("***")
    lines.extend(_daily_footer_lines(date_key, reroll, can_reroll, spot, spot_total))
    return "\n".join(lines)


# ---------------- pilgrimage ----------------


def spot_card(
    work: str,
    spots: list[Spot],
    page: int,
    total_pages: int,
    link_style: str = "full",
    keyword: str = "",
) -> str:
    body: list[str] = []
    for index, spot in enumerate(spots, 1):
        body.append(f"{numbered(index)} {spot.name}")
        if spot.region:
            body.append(f"   📍 {spot.region}")
        link = short_link(spot.link, link_style)
        if link:
            body.append(f"   🔗 {link}")

    footer = [f"📍 共 {len(spots)} 处 · 第 {page}/{total_pages} 页"]
    if total_pages > 1:
        next_page = page + 1 if page < total_pages else 1
        footer.append(f"💡 /圣地巡礼 {keyword or work} {next_page} 翻页")
    return card(f"🗺️ {work} · 圣地巡礼", body, footer)


def works_card(
    works: list[tuple[str, int]],
    page: int,
    total_pages: int,
    total_works: int,
) -> str:
    body = [f"· {name} · {count} 处" for name, count in works]
    if total_pages > 1:
        next_page = page + 1 if page < total_pages else 1
        footer = [f"📄 第 {page}/{total_pages} 页", f"💡 /圣地列表 {next_page} 翻页"]
    else:
        footer = ["💡 /圣地巡礼 作品名 查看详情"]
    return card(f"📚 圣地作品库 · {total_works} 部", body, footer)


# ---------------- notices ----------------


def not_found(query: str, suggestions: list[str]) -> str:
    if suggestions:
        footer = ["💡 试试：" + "、".join(suggestions)]
    else:
        footer = ["💡 发送 /圣地列表 查看全部作品"]
    return card(f"🔍 没有《{query}》的巡礼记录", [], footer)


def empty_heroines() -> str:
    return card(
        "📭 角色名单是空的",
        [],
        ["💡 管理员：/gal 添加老婆 古河渚 (CLANNAD)"],
    )


def no_permission() -> str:
    return card(
        "🔒 这个指令仅限管理员",
        [],
        ["💡 请在 AstrBot 管理面板确认你的管理员身份"],
    )


def reroll_exhausted(limit: int) -> str:
    if limit <= 0:
        return card("🚫 换人功能已关闭", [], ["管理员可在插件配置里打开"])
    return card(
        f"⏳ 今天的 {limit} 次换人用完了",
        [],
        ["明天 0 点刷新"],
    )


def unknown_sub(sub: str) -> str:
    return card(f"❓ 没有「{sub}」这个子指令", [], ["💡 发送 /gal 帮助 查看全部指令"])


def usage(text: str) -> str:
    return card("📎 参数不对", [], [f"💡 {text}"])


def no_image() -> str:
    """Shown instead of a card when no art could be fetched at all."""
    return card(
        "🖼️ 这次没拉到立绘",
        [],
        ["再发一次 /今日老婆 试试"],
    )


def error_card() -> str:
    return card("💥 出了点小问题", [], ["💡 请稍后再试，或让管理员查看日志"])


def info_card(title: str, message: str) -> str:
    """Result receipt: verdict in the title, details in the body."""
    return card(title, [message] if message else [])


def tip_card(title: str, tip: str) -> str:
    """Status notice: state in the title, one hint in the footer."""
    return card(title, [], [f"💡 {tip}"] if tip else [])


# ---------------- help / stats ----------------


def help_card(stats: dict[str, int] | None = None, prefix: str = "/") -> str:
    p = prefix
    body = [
        "【 陪伴 】",
        f"· {p}今日老婆 — 每日一抽",
        f"· {p}换老婆 — 重抽一次",
        "【 巡礼 】",
        f"· {p}圣地巡礼 <作品> [页码]",
        f"· {p}圣地列表 [页码]",
        "【 管理 · 仅管理员 】",
        f"· {p}gal 添加老婆 <名字>",
        f"· {p}gal 添加圣地 作品|地点|链接",
        f"· {p}gal 删除老婆|圣地 <关键词>",
        f"· {p}gal 重载 / 导入 / 统计 / 诊断",
    ]
    footer: list[str] = []
    if stats:
        footer.append(
            f"📦 {stats.get('heroines', 0)} 位角色 · {stats.get('spots', 0)} 条圣地"
        )
    return card("🌸 GalUniverse", body, footer)


def stats_card(stats: dict[str, int], data_path: str) -> str:
    body = [
        f"👤 女主 {stats.get('heroines', 0)} 位",
        f"🗺️ 圣地 {stats.get('spots', 0)} 条",
        f"📚 作品 {stats.get('works', 0)} 部",
    ]
    return card("📊 GalUniverse 数据", body, [f"💾 {short_path(data_path)}"])


def diagnose_card(rows: list[tuple[str, str]], warnings: list[str]) -> str:
    """Self-check card: dumps the facts needed to debug update / image issues."""
    body = [f"{key} · {value}" for key, value in rows]
    footer = [f"⚠️ {w}" for w in warnings]
    if not footer:
        footer = ["✅ 未发现遗留目录冲突"]
    return card("🩺 GalUniverse 自检", body, footer)


# ---------------- paging ----------------


def page_slice(items: list, page: int, page_size: int) -> tuple[list, int, int]:
    """Return (page items, page, total pages); page is 1-based and clamped."""
    size = max(1, page_size)
    total_pages = max(1, (len(items) + size - 1) // size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * size
    return items[start : start + size], page, total_pages
