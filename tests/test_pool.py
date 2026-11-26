"""镜像角色池与数据补录逻辑单测：全部离线，不触网。"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.bgm import FAIL_TTL, WORKS_TTL, BangumiPool  # noqa: E402
from core.models import Heroine, Spot  # noqa: E402
from core.store import GalStore, StateStore  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def make_pool(cache: Path, items=None, fail: bool = False) -> BangumiPool:
    pool = BangumiPool(cache_dir=cache, api_bases=["https://mirror.example.com"])

    async def fake_fetch(work: str):
        if fail:
            return []
        return list(items or [{"name": f"{work}-角色{i}", "image": ""} for i in range(6)])

    pool._fetch_characters = fake_fetch  # type: ignore[assignment]
    return pool


class TestPoolDraw(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_draw_returns_character(self):
        pool = make_pool(self.cache)
        got = asyncio.run(pool.draw("CLANNAD", "seed-1"))
        self.assertIsNotNone(got)
        heroine, image = got
        self.assertTrue(heroine.name.startswith("CLANNAD-"))
        self.assertEqual(heroine.work, "CLANNAD")
        self.assertEqual(image, "")

    def test_same_seed_same_result(self):
        pool = make_pool(self.cache)
        first = asyncio.run(pool.draw("CLANNAD", "seed-1"))
        second = asyncio.run(pool.draw("CLANNAD", "seed-1"))
        self.assertEqual(first[0].name, second[0].name)

    def test_seeds_spread_over_pool(self):
        pool = make_pool(self.cache)
        names = {
            asyncio.run(pool.draw("CLANNAD", f"seed-{i}"))[0].name for i in range(40)
        }
        # 6 个候选角色，40 个不同 seed 至少覆盖 5 个，说明不是固定取第一个
        self.assertGreaterEqual(len(names), 5)

    def test_pick_persisted_and_reused(self):
        pool = make_pool(self.cache)
        got = asyncio.run(pool.draw("CLANNAD", "seed-1"))
        self.assertTrue((self.cache / "bgm_pool.json").is_file())

        # 新实例不再调用接口也能拿到同一个结果
        reloaded = BangumiPool(cache_dir=self.cache, api_bases=["https://x.example.com"])

        async def boom(work: str):
            raise AssertionError("不应再次请求接口")

        reloaded._fetch_characters = boom  # type: ignore[assignment]
        again = asyncio.run(reloaded.draw("CLANNAD", "seed-1"))
        self.assertEqual(again[0].name, got[0].name)

    def test_empty_work_returns_none(self):
        pool = make_pool(self.cache)
        self.assertIsNone(asyncio.run(pool.draw("  ", "seed")))

    def test_failure_returns_none(self):
        pool = make_pool(self.cache, fail=True)
        self.assertIsNone(asyncio.run(pool.draw("CLANNAD", "seed-1")))

    def test_failure_cached_for_one_hour(self):
        pool = make_pool(self.cache, fail=True)
        asyncio.run(pool.draw("CLANNAD", "seed-1"))
        entry = pool.data["works"]["CLANNAD"]
        self.assertTrue(entry["fail"])
        self.assertEqual(entry["items"], [])
        self.assertLess(time.time() - entry["at"], FAIL_TTL)

    def test_success_cached_for_seven_days(self):
        pool = make_pool(self.cache)
        asyncio.run(pool.draw("CLANNAD", "seed-1"))
        entry = pool.data["works"]["CLANNAD"]
        self.assertFalse(entry["fail"])
        self.assertEqual(len(entry["items"]), 6)
        self.assertLess(time.time() - entry["at"], WORKS_TTL)

    def test_stale_cache_refetched(self):
        pool = make_pool(self.cache)
        asyncio.run(pool.draw("CLANNAD", "seed-1"))
        pool.data["works"]["CLANNAD"]["at"] = time.time() - (WORKS_TTL + 10)
        calls: list[str] = []

        async def counting(work: str):
            calls.append(work)
            return [{"name": "新角色", "image": ""}]

        pool._fetch_characters = counting  # type: ignore[assignment]
        got = asyncio.run(pool.draw("CLANNAD", "seed-2"))
        self.assertEqual(calls, ["CLANNAD"])
        self.assertEqual(got[0].name, "新角色")

    def test_corrupt_cache_file_ignored(self):
        (self.cache / "bgm_pool.json").write_text("{ not json", encoding="utf-8")
        pool = make_pool(self.cache)
        self.assertEqual(pool.data, {"works": {}, "picks": {}, "subjects": {}})
        self.assertIsNotNone(asyncio.run(pool.draw("CLANNAD", "seed-1")))


class StoreTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, data_dir: Path | None = None) -> GalStore:
        return GalStore(data_dir=data_dir or self.data, assets_dir=ASSETS)


class TestMergeBuiltin(StoreTestBase):
    def test_thin_pool_filled(self):
        store = self.store()
        store.heroines = [Heroine(name="古河渚", work="CLANNAD")]
        store._rebuild_index()
        added = store.merge_builtin_defaults()
        self.assertGreater(added, 100)
        self.assertGreater(len(store.heroines), 100)

    def test_thin_pool_keeps_user_entries(self):
        store = self.store()
        store.heroines = [Heroine(name="自定义角色", work="自定义")]
        store._rebuild_index()
        store.merge_builtin_defaults()
        names = {h.name for h in store.heroines}
        self.assertIn("自定义角色", names)

    def test_healthy_pool_untouched(self):
        store = self.store()
        store.heroines = [Heroine(name=f"角色{i}") for i in range(80)]
        store._rebuild_index()
        self.assertEqual(store.merge_builtin_defaults(), 0)
        self.assertEqual(len(store.heroines), 80)

    def test_idempotent(self):
        store = self.store()
        store.heroines = []
        store._rebuild_index()
        first = store.merge_builtin_defaults()
        second = store.merge_builtin_defaults()
        self.assertGreater(first, 0)
        self.assertEqual(second, 0)


class TestImportFromDirs(StoreTestBase):
    def _write(self, directory: Path, heroines, spots=()) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "heroines": [h.to_dict() for h in heroines],
            "spots": [s.to_dict() for s in spots],
        }
        (directory / "gal.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def test_merge_old_dir(self):
        old = self.root / "astrbot_plugin_galuniverse"
        self._write(
            old,
            [Heroine(name="旧角色", work="旧作")],
            [Spot(work="旧作", name="旧圣地")],
        )
        store = self.store()
        store.heroines = []
        store.spots = []
        store._rebuild_index()
        added_h, added_s = store.import_from_dirs([old])
        self.assertEqual((added_h, added_s), (1, 1))
        self.assertEqual(store.heroines[0].name, "旧角色")
        self.assertEqual(store.spots[0].name, "旧圣地")

    def test_merge_is_idempotent(self):
        old = self.root / "old"
        self._write(old, [Heroine(name="旧角色")])
        store = self.store()
        store.heroines = []
        store._rebuild_index()
        self.assertEqual(store.import_from_dirs([old]), (1, 0))
        self.assertEqual(store.import_from_dirs([old]), (0, 0))

    def test_missing_dir_ignored(self):
        store = self.store()
        self.assertEqual(store.import_from_dirs([self.root / "nope"]), (0, 0))

    def test_self_dir_skipped(self):
        self._write(self.data, [Heroine(name="自己")])
        store = self.store()
        store.heroines = []
        store._rebuild_index()
        self.assertEqual(store.import_from_dirs([self.data]), (0, 0))


class TestStateStore(StoreTestBase):
    def test_reroll_roundtrip(self):
        state = StateStore(self.data)
        self.assertEqual(state.reroll_used("k", "2026-11-26"), 0)
        self.assertEqual(state.mark_reroll("k", "2026-11-26"), 1)
        self.assertEqual(state.reroll_used("k", "2026-11-26"), 1)

    def test_other_day_resets(self):
        state = StateStore(self.data)
        state.mark_reroll("k", "2026-11-26")
        self.assertEqual(state.reroll_used("k", "2026-11-27"), 0)

    def test_save_keeps_only_given_day(self):
        state = StateStore(self.data)
        state.data = {
            "a": {"date": "2026-11-26", "reroll": 1},
            "b": {"date": "2026-11-25", "reroll": 2},
        }
        state.save("2026-11-26")
        self.assertEqual(list(state.data), ["a"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
