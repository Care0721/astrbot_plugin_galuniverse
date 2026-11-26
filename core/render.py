"""纯文本卡片渲染。

统一结构：``标题 → 分隔线 → 主体 → 分隔线 → 页脚``。
刻意不用 Markdown、不用表格、不用对齐空格：
QQ / 微信 / OneBot 客户端对中文与 emoji 的宽度处理不一致，对齐必然错位。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import Heroine, Spot
from .theme import DIVIDER, fortune_bar, fortune_style, numbered, short_link, short_path


def card(header: str, body: Iterable[str], footer: Sequence[str] = ()) -> str:
    """拼装一张卡片；自动丢弃空行，保证不出现连续空行。"""
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


# ---------------- 今日老婆 ----------------


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
    emoji, _ = fortune_style(fortune)
    body = [
        f"👤 {heroine.label}",
        f"{emoji} {fortune} {fortune_bar(fortune)}",
        f"📖 {advice}",
    ]
    if spot is not None:
        body.append(f"🗺️ 圣地 · {spot.name}")
        link = short_link(spot.link, link_style)
        if link:
            body.append(f"🔗 {link}")

    tail = f"🕒 {date_key}" + (f" · 第 {reroll + 1} 抽" if reroll else "")
    footer = [tail]
    if can_reroll:
        footer.append("💡 /换老婆 换一位")
    else:
        footer.append("💡 明天再来抽一次")
    if spot is not None and spot_total > 1:
        footer.append(f"💡 /圣地巡礼 {spot.work} 共 {spot_total} 处")
    return card("🌙 今日 Gal 运势", body, footer)


# ---------------- 圣地 ----------------


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


# ---------------- 提示类 ----------------


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
        return card("🚫 重抽功能已关闭", [], ["💡 管理员可在插件配置中开启"])
    return card(
        f"⏳ 今日重抽次数已用完（{limit}/{limit}）",
        [],
        ["🌙 明天 00:00 刷新"],
    )


def unknown_sub(sub: str) -> str:
    return card(f"❓ 没有「{sub}」这个子指令", [], ["💡 发送 /gal 帮助 查看全部指令"])


def usage(text: str) -> str:
    return card("📎 参数不对", [], [f"💡 {text}"])


def error_card() -> str:
    return card("💥 出了点小问题", [], ["💡 请稍后再试，或让管理员查看日志"])


def info_card(title: str, message: str) -> str:
    """结果回执：标题给结论，正文给细节，不再重复「💡」。"""
    return card(title, [message] if message else [])


def tip_card(title: str, tip: str) -> str:
    """状态提示：标题说明状态，页脚给一条建议。"""
    return card(title, [], [f"💡 {tip}"] if tip else [])


# ---------------- 帮助 / 统计 ----------------


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
    """自检卡片：把运行环境的关键事实摊开，方便排查「更新不了 / 没图」类问题。"""
    body = [f"{key} · {value}" for key, value in rows]
    footer = [f"⚠️ {w}" for w in warnings]
    if not footer:
        footer = ["✅ 未发现遗留目录冲突"]
    return card("🩺 GalUniverse 自检", body, footer)


# ---------------- 分页 ----------------


def page_slice(items: list, page: int, page_size: int) -> tuple[list, int, int]:
    """返回 (当前页内容, 页码, 总页数)，页码从 1 开始并自动收敛。"""
    size = max(1, page_size)
    total_pages = max(1, (len(items) + size - 1) // size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * size
    return items[start : start + size], page, total_pages
