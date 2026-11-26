"""渲染快照测试：锁定最终发给用户的文案与排版。

改动模板后这些用例会失败，提醒同步更新预期，避免线上样式被误改。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import render  # noqa: E402
from core.models import Heroine, Spot  # noqa: E402
from core.theme import fortune_bar, numbered, short_link, short_path  # noqa: E402

D = "━" * 12


class TestTheme(unittest.TestCase):
    def test_fortune_bar(self):
        self.assertEqual(fortune_bar("超大吉"), "▰▰▰▰▰▰▰")
        self.assertEqual(fortune_bar("大吉"), "▰▰▰▰▰▰▱")
        self.assertEqual(fortune_bar("凶"), "▰▱▱▱▱▱▱")
        self.assertEqual(len(fortune_bar("未知签")), 7)

    def test_numbered(self):
        self.assertEqual(numbered(1), "①")
        self.assertEqual(numbered(20), "⑳")
        self.assertEqual(numbered(21), "21.")

    def test_short_link(self):
        self.assertEqual(
            short_link("https://zh.moegirl.org.cn/CLANNAD/圣地巡礼"),
            "zh.moegirl.org.cn/CLANNAD",
        )
        self.assertEqual(short_link("https://example.com"), "example.com")
        self.assertEqual(short_link("https://a.com/b/c", "full"), "https://a.com/b/c")
        self.assertEqual(short_link("https://a.com/b", "hidden"), "")
        self.assertEqual(short_link(""), "")

    def test_short_path(self):
        self.assertEqual(
            short_path(r"C:\data\plugin_data\astrbot_plugin_galuniverse\gal.json"),
            "astrbot_plugin_galuniverse/gal.json",
        )


class TestDailyCard(unittest.TestCase):
    def test_first_draw(self):
        text = render.daily_card(
            Heroine(name="古河渚", work="CLANNAD"), "大吉", "测试建议", "2026-11-26"
        )
        self.assertEqual(
            text,
            f"🌙 今日 Gal 运势\n{D}\n👤 古河渚 · CLANNAD\n✨ 大吉 ▰▰▰▰▰▰▱\n"
            f"📖 测试建议\n{D}\n🕒 2026-11-26\n💡 /换老婆 换一位",
        )

    def test_reroll_count(self):
        text = render.daily_card(
            Heroine(name="古河渚", work="CLANNAD"), "凶", "建议", "2026-11-26", reroll=1
        )
        self.assertIn("🕒 2026-11-26 · 第 2 抽", text)
        self.assertIn("🌧 凶 ▰▱▱▱▱▱▱", text)

    def test_no_reroll(self):
        text = render.daily_card(
            Heroine(name="古河渚"), "平", "建议", "2026-11-26", can_reroll=False
        )
        self.assertIn("💡 明天再来抽一次", text)
        self.assertNotIn("/换老婆", text)

    def test_name_without_work(self):
        text = render.daily_card(Heroine(name="无名"), "中吉", "建议", "2026-11-26")
        self.assertIn("👤 无名\n", text)

    def test_with_spot_single(self):
        spot = Spot(work="Fate", name="冬木市", link="https://zh.moegirl.org.cn/Fate")
        text = render.daily_card(
            Heroine(name="阿尔托莉雅", work="Fate"),
            "超大吉",
            "给喜欢的人发一句晚安。",
            "2026-11-26",
            spot=spot,
            spot_total=1,
        )
        self.assertEqual(
            text,
            f"🌙 今日 Gal 运势\n{D}\n👤 阿尔托莉雅 · Fate\n🌈 超大吉 ▰▰▰▰▰▰▰\n"
            f"📖 给喜欢的人发一句晚安。\n🗺️ 圣地 · 冬木市\n"
            f"🔗 zh.moegirl.org.cn/Fate\n{D}\n🕒 2026-11-26\n💡 /换老婆 换一位",
        )

    def test_with_spot_multiple_adds_hint(self):
        spot = Spot(work="Fate", name="冬木市", link="https://zh.moegirl.org.cn/Fate")
        text = render.daily_card(
            Heroine(name="阿尔托莉雅", work="Fate"),
            "大吉",
            "建议",
            "2026-11-26",
            spot=spot,
            spot_total=3,
        )
        self.assertIn("💡 /圣地巡礼 Fate 共 3 处", text)

    def test_spot_without_link(self):
        spot = Spot(work="Fate", name="冬木市", link="")
        text = render.daily_card(
            Heroine(name="阿尔托莉雅", work="Fate"), "大吉", "建议", "2026-11-26", spot=spot
        )
        self.assertIn("🗺️ 圣地 · 冬木市", text)
        self.assertNotIn("🔗", text)

    def test_spot_hidden_link_style(self):
        spot = Spot(work="Fate", name="冬木市", link="https://zh.moegirl.org.cn/Fate")
        text = render.daily_card(
            Heroine(name="阿尔托莉雅", work="Fate"),
            "大吉",
            "建议",
            "2026-11-26",
            spot=spot,
            link_style="hidden",
        )
        self.assertNotIn("🔗", text)


class TestSpotCard(unittest.TestCase):
    def setUp(self):
        self.spots = [
            Spot(work="CLANNAD", name="古河面包店", link="https://zh.moegirl.org.cn/CLANNAD/圣地巡礼"),
            Spot(work="CLANNAD", name="光坂高校", link=""),
        ]

    def test_single_page(self):
        text = render.spot_card("CLANNAD", self.spots, 1, 1)
        self.assertEqual(
            text,
            f"🗺️ CLANNAD · 圣地巡礼\n{D}\n① 古河面包店\n"
            f"   🔗 zh.moegirl.org.cn/CLANNAD\n② 光坂高校\n"
            f"{D}\n📍 共 2 处 · 第 1/1 页",
        )

    def test_multi_page_footer(self):
        text = render.spot_card("CLANNAD", self.spots[:1], 1, 3, keyword="CL")
        self.assertIn("💡 /圣地巡礼 CL 2 翻页", text)

    def test_last_page_wraps_to_first(self):
        text = render.spot_card("CLANNAD", self.spots[:1], 3, 3)
        self.assertIn("💡 /圣地巡礼 CLANNAD 1 翻页", text)

    def test_hidden_link(self):
        text = render.spot_card("CLANNAD", self.spots[:1], 1, 1, link_style="hidden")
        self.assertNotIn("🔗", text)

    def test_full_link(self):
        text = render.spot_card("CLANNAD", self.spots[:1], 1, 1, link_style="full")
        self.assertIn("https://zh.moegirl.org.cn/CLANNAD/圣地巡礼", text)


class TestOtherCards(unittest.TestCase):
    def test_works_card(self):
        text = render.works_card([("CLANNAD", 2), ("AIR", 1)], 1, 2, 2)
        self.assertIn("📚 圣地作品库 · 2 部", text)
        self.assertIn("· CLANNAD · 2 处", text)
        self.assertIn("📄 第 1/2 页", text)
        self.assertIn("💡 /圣地列表 2 翻页", text)

    def test_help_card_with_stats(self):
        text = render.help_card({"heroines": 310, "spots": 68})
        self.assertIn("🌸 GalUniverse", text)
        self.assertIn("· /gal 添加圣地 作品|地点|链接", text)
        self.assertIn("📦 310 位角色 · 68 条圣地", text)

    def test_stats_card(self):
        text = render.stats_card(
            {"heroines": 312, "spots": 69, "works": 52},
            "/data/plugin_data/astrbot_plugin_galuniverse/gal.json",
        )
        self.assertIn("👤 女主 312 位", text)
        self.assertIn("💾 astrbot_plugin_galuniverse/gal.json", text)

    def test_not_found_with_suggestions(self):
        text = render.not_found("clannad", ["CLANNAD"])
        self.assertEqual(text, f"🔍 没有《clannad》的巡礼记录\n{D}\n💡 试试：CLANNAD")

    def test_not_found_without_suggestions(self):
        text = render.not_found("xx", [])
        self.assertIn("💡 发送 /圣地列表 查看全部作品", text)

    def test_tip_cards_have_no_empty_lines(self):
        for text in (
            render.empty_heroines(),
            render.no_permission(),
            render.reroll_exhausted(1),
            render.reroll_exhausted(0),
            render.unknown_sub("xx"),
            render.error_card(),
        ):
            self.assertNotIn("\n\n", text)
            self.assertTrue(text.strip())

    def test_card_drops_blank_lines(self):
        text = render.card("T", ["a", "", "  ", "b"], ["", "f"])
        self.assertEqual(text, f"T\n{D}\na\nb\n{D}\nf")

    def test_card_without_footer(self):
        self.assertEqual(render.card("T", ["a"]), f"T\n{D}\na")

    def test_no_trailing_spaces(self):
        text = render.daily_card(Heroine(name="古河渚", work="CLANNAD"), "大吉", "建议", "2026-11-26")
        for line in text.splitlines():
            self.assertEqual(line, line.rstrip())


class TestPageSlice(unittest.TestCase):
    def test_clamp(self):
        items, page, total = render.page_slice(list(range(10)), 99, 6)
        self.assertEqual((page, total), (2, 2))
        self.assertEqual(items, [6, 7, 8, 9])

    def test_zero_page(self):
        items, page, total = render.page_slice(list(range(3)), 0, 6)
        self.assertEqual((page, total), (1, 1))
        self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
