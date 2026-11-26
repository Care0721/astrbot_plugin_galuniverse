"""核心逻辑单测（不依赖 AstrBot，可直接 python -m unittest 运行）。

    cd astrbot_plugin_galuniverse
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.fortune import daily_seed, pick_fortune, pick_index, today_key  # noqa: E402
from core.models import Heroine, Spot, split_name_work  # noqa: E402
from core.parser import chunk_text, split_fields, strip_command  # noqa: E402
from core.store import GalStore, StateStore  # noqa: E402


class TestModels(unittest.TestCase):
    def test_split_halfwidth(self):
        self.assertEqual(split_name_work("古河渚 (CLANNAD)"), ("古河渚", "CLANNAD"))

    def test_split_fullwidth(self):
        self.assertEqual(split_name_work("冬马和纱（白色相簿2）"), ("冬马和纱", "白色相簿2"))

    def test_split_dash(self):
        self.assertEqual(split_name_work("远坂凛 - Fate/stay night"), ("远坂凛", "Fate/stay night"))

    def test_no_work(self):
        self.assertEqual(split_name_work("无名角色"), ("无名角色", ""))

    def test_display_and_dedupe_key(self):
        a = Heroine(name="古河渚", work="CLANNAD")
        b = Heroine(name="古河渚 ", work="clannad")
        self.assertEqual(a.display, "古河渚 (CLANNAD)")
        self.assertEqual(a.key, b.key)


class TestParser(unittest.TestCase):
    def test_strip_command_with_prefix(self):
        self.assertEqual(strip_command("/圣地巡礼 CLANNAD", "圣地巡礼"), "CLANNAD")

    def test_strip_command_without_prefix(self):
        self.assertEqual(strip_command("gal 添加老婆 古河渚", "gal"), "添加老婆 古河渚")

    def test_fullwidth_space(self):
        self.assertEqual(strip_command("／圣地巡礼　Summer Pockets", "圣地巡礼"), "Summer Pockets")

    def test_split_fields(self):
        self.assertEqual(split_fields("CLANNAD|古河面包店|https://x"), ["CLANNAD", "古河面包店", "https://x"])
        self.assertEqual(split_fields("A｜B"), ["A", "B"])

    def test_chunk_text(self):
        text = "\n".join("x" * 100 for _ in range(50))
        chunks = chunk_text(text, 600)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 600 for c in chunks))
        self.assertEqual("".join(chunks).count("x"), 5000)


class TestFortune(unittest.TestCase):
    def test_deterministic(self):
        seed = daily_seed("u:aiocqhttp:123", "2026-11-26", 0)
        self.assertEqual(pick_index(seed, 310), pick_index(seed, 310))
        self.assertEqual(pick_fortune(seed, ["大吉", "凶"]), pick_fortune(seed, ["大吉", "凶"]))

    def test_reroll_changes_result(self):
        base = daily_seed("u:1", "2026-11-26", 0)
        reroll = daily_seed("u:1", "2026-11-26", 1)
        self.assertNotEqual(base, reroll)

    def test_today_key_format(self):
        self.assertRegex(today_key("Asia/Shanghai"), r"^\d{4}-\d{2}-\d{2}$")


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data_dir = root / "data"
        self.assets = root / "assets"
        self.legacy = root / "legacy"
        for d in (self.data_dir, self.assets, self.legacy):
            d.mkdir(parents=True, exist_ok=True)
        (self.assets / "wives.default.json").write_text(
            json.dumps({"heroines": [{"name": "古河渚", "work": "CLANNAD"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.assets / "spots.default.json").write_text(
            json.dumps(
                {
                    "spots": [
                        {"work": "CLANNAD", "name": "古河面包店", "link": ""},
                        {"work": "CLANNAD", "name": "光坂高校", "link": ""},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _store(self) -> GalStore:
        return GalStore(self.data_dir, self.assets, legacy_dirs=(self.legacy,))

    def test_first_run_copies_defaults(self):
        store = self._store()
        report = store.load()
        self.assertTrue(report.created)
        self.assertEqual(report.heroines, 1)
        self.assertEqual(report.spots, 2)
        self.assertTrue(store.path.exists())

    def test_multi_spots_per_work_preserved(self):
        store = self._store()
        store.load()
        hits = store.find_spots("CLANNAD", limit=10)
        self.assertEqual(len(hits), 2, "同一作品的多个地点必须全部保留")

    def test_legacy_import_and_dedupe(self):
        (self.legacy / "wives.txt").write_text(
            "古河渚 (CLANNAD)\n古河渚 (CLANNAD)\n冬马和纱 (白色相簿2)\n", encoding="utf-8"
        )
        (self.legacy / "spots.txt").write_text(
            "CLANNAD|古河面包店|https://a\nCLANNAD|光坂高校|\nCLANNAD|古河面包店|https://a\n",
            encoding="utf-8",
        )
        store = self._store()
        report = store.load()
        self.assertTrue(report.migrated)
        self.assertEqual(report.heroines, 2)
        self.assertEqual(report.spots, 2)
        self.assertEqual(report.dropped, 0)

    def test_add_and_remove_heroine(self):
        store = self._store()
        store.load()
        ok, msg = store.add_heroine("牧濑红莉栖 (命运石之门)")
        self.assertTrue(ok, msg)
        ok, _ = store.add_heroine("牧濑红莉栖 (命运石之门)")
        self.assertFalse(ok, "重复添加应被拒绝")
        count, removed = store.remove_heroine("牧濑")
        self.assertEqual(count, 1)
        self.assertEqual(removed, ["牧濑红莉栖 (命运石之门)"])

    def test_add_spot_requires_both_fields(self):
        store = self._store()
        store.load()
        ok, _ = store.add_spot("", "地点")
        self.assertFalse(ok)
        ok, _ = store.add_spot("AIR", "美滨町", "https://x")
        self.assertTrue(ok)
        self.assertEqual(len(store.find_spots("AIR")), 1)

    def test_fuzzy_scoring_prefers_exact(self):
        store = self._store()
        store.load()
        store.add_spot("Fate/stay night", "柳洞寺")
        store.add_spot("FATE", "冬木市")
        hits = store.find_spots("FATE", fuzzy=True, limit=5)
        self.assertEqual(hits[0].work, "FATE", "精确匹配应排在包含匹配之前")

    def test_fuzzy_disabled(self):
        store = self._store()
        store.load()
        self.assertEqual(store.find_spots("CLA", fuzzy=False), [])

    def test_reload_does_not_duplicate(self):
        store = self._store()
        store.load()
        store.load()
        self.assertEqual(len(store.heroines), 1)
        self.assertEqual(len(store.spots), 2)

    def test_corrupted_file_falls_back(self):
        store = self._store()
        store.load()
        store.path.write_text("{not json", encoding="utf-8")
        store2 = self._store()
        report = store2.load()
        self.assertEqual(report.spots, 2, "损坏文件应回退到内置资产而不是崩溃")

    def test_state_reroll_limit(self):
        state = StateStore(self.data_dir)
        key, today = "u:1|2026-11-26", "2026-11-26"
        self.assertEqual(state.reroll_used(key, today), 0)
        self.assertEqual(state.mark_reroll(key, today), 1)
        self.assertEqual(state.reroll_used(key, today), 1)
        state2 = StateStore(self.data_dir)
        self.assertEqual(state2.reroll_used(key, today), 1, "重抽次数需跨进程持久化")


class TestSpotModel(unittest.TestCase):
    def test_spot_id_stable(self):
        a = Spot(work="CLANNAD", name="古河面包店", link="https://a")
        b = Spot(work="CLANNAD", name="古河面包店", link="https://a")
        self.assertEqual(a.id, b.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
