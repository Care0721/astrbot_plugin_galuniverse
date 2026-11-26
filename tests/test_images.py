"""立绘获取逻辑单测：只测本地与缓存分支，不触网。"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.images import ImageFetcher, to_mirror  # noqa: E402
from core.store import norm  # noqa: E402


class TestMirror(unittest.TestCase):
    MIRROR = "https://bgmlain.waterbee.cc"

    def test_rewrite_host_keep_path(self):
        url = "https://lain.bgm.tv/pic/crt/l/00/01/1_crt.jpg"
        self.assertEqual(
            to_mirror(url, self.MIRROR),
            "https://bgmlain.waterbee.cc/pic/crt/l/00/01/1_crt.jpg",
        )

    def test_query_preserved(self):
        url = "https://lain.bgm.tv/pic/crt/l/00/01/1_crt.jpg?r=1234"
        self.assertTrue(to_mirror(url, self.MIRROR).endswith("1_crt.jpg?r=1234"))

    def test_trailing_slash_in_mirror(self):
        url = "https://lain.bgm.tv/pic/a.jpg"
        self.assertEqual(
            to_mirror(url, "https://bgmlain.waterbee.cc/"),
            "https://bgmlain.waterbee.cc/pic/a.jpg",
        )

    def test_empty_mirror_keeps_original(self):
        url = "https://lain.bgm.tv/pic/a.jpg"
        self.assertEqual(to_mirror(url, ""), url)
        self.assertEqual(to_mirror(url, "   "), url)

    def test_relative_url_untouched(self):
        self.assertEqual(to_mirror("/pic/a.jpg", self.MIRROR), "/pic/a.jpg")
        self.assertEqual(to_mirror("", self.MIRROR), "")

    def test_constructor_defaults(self):
        f = ImageFetcher(cache_dir=Path(tempfile.mkdtemp()))
        # 镜像优先，官方恒定兜底
        self.assertEqual(
            f.api_candidates(),
            ["https://bgmapi.sakuraspark.fun", "https://api.bgm.tv"],
        )
        self.assertEqual(
            f.mirrors,
            [
                "https://bgmimg.sakuraspark.fun",
                "https://bgmlain.waterbee.cc",
                "https://bgm.sakuraspark.fun",
            ],
        )

    def test_constructor_custom_list(self):
        f = ImageFetcher(
            cache_dir=Path(tempfile.mkdtemp()),
            api_bases=["https://api.example.com/", "https://api2.example.com"],
            mirrors=["https://img.example.com/", "https://img2.example.com"],
        )
        self.assertEqual(
            f.api_candidates(),
            ["https://api.example.com", "https://api2.example.com", "https://api.bgm.tv"],
        )
        self.assertEqual(
            f.mirrors, ["https://img.example.com", "https://img2.example.com"]
        )

    def test_official_always_last(self):
        f = ImageFetcher(
            cache_dir=Path(tempfile.mkdtemp()), api_bases=["https://api.bgm.tv"]
        )
        self.assertEqual(f.api_candidates(), ["https://api.bgm.tv"])

    def test_legacy_single_api_base(self):
        f = ImageFetcher(
            cache_dir=Path(tempfile.mkdtemp()), api_base="https://legacy.example.com"
        )
        self.assertEqual(
            f.api_candidates(), ["https://legacy.example.com", "https://api.bgm.tv"]
        )

    def test_api_bases_from_string(self):
        f = ImageFetcher(
            cache_dir=Path(tempfile.mkdtemp()),
            api_bases="https://a.com/ ，https://b.com , ,https://a.com",
        )
        self.assertEqual(
            f.api_candidates(), ["https://a.com", "https://b.com", "https://api.bgm.tv"]
        )

    def test_mirrors_from_string(self):
        f = ImageFetcher(
            cache_dir=Path(tempfile.mkdtemp()),
            mirrors=" https://a.com/ ，https://b.com , ,https://a.com",
        )
        self.assertEqual(f.mirrors, ["https://a.com", "https://b.com"])

    def test_empty_mirrors_only_official(self):
        f = ImageFetcher(cache_dir=Path(tempfile.mkdtemp()), mirrors=[])
        url = "https://lain.bgm.tv/pic/a.jpg"
        self.assertEqual(f.mirror_candidates(url), [url])

    def test_candidates_order(self):
        f = ImageFetcher(
            cache_dir=Path(tempfile.mkdtemp()),
            mirrors=["https://m1.com", "https://m2.com"],
        )
        url = "https://lain.bgm.tv/pic/a.jpg?r=1"
        self.assertEqual(
            f.mirror_candidates(url),
            [
                "https://m1.com/pic/a.jpg?r=1",
                "https://m2.com/pic/a.jpg?r=1",
                "https://lain.bgm.tv/pic/a.jpg?r=1",
            ],
        )

    def test_candidates_skip_invalid_url(self):
        f = ImageFetcher(cache_dir=Path(tempfile.mkdtemp()))
        self.assertEqual(f.mirror_candidates(""), [])


class ImageTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache = root / "cache"
        self.local = root / "images"
        self.cache.mkdir()
        self.local.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def fetcher(self, source: str = "auto", days: int = 30) -> ImageFetcher:
        return ImageFetcher(
            cache_dir=self.cache, local_dir=self.local, source=source, cache_days=days
        )


class TestLocalImages(ImageTestBase):
    def test_exact_name(self):
        (self.local / "古河渚.jpg").write_bytes(b"x")
        path = asyncio.run(self.fetcher("local").fetch("古河渚", "CLANNAD"))
        self.assertIsNotNone(path)
        self.assertEqual(path.name, "古河渚.jpg")

    def test_name_with_work_suffix(self):
        (self.local / "古河渚 (CLANNAD).png").write_bytes(b"x")
        path = asyncio.run(self.fetcher("local").fetch("古河渚", "CLANNAD"))
        self.assertIsNotNone(path)
        self.assertEqual(path.suffix, ".png")

    def test_case_and_space_insensitive(self):
        (self.local / "阿尔托莉雅 (fate).jpg").write_bytes(b"x")
        path = asyncio.run(self.fetcher("local").fetch("阿尔托莉雅", "Fate"))
        self.assertIsNotNone(path)

    def test_missing_local_returns_none_without_network(self):
        path = asyncio.run(self.fetcher("local").fetch("不存在角色", "X"))
        self.assertIsNone(path)

    def test_off_disables_everything(self):
        (self.local / "古河渚.jpg").write_bytes(b"x")
        self.assertIsNone(asyncio.run(self.fetcher("off").fetch("古河渚")))

    def test_empty_name(self):
        self.assertIsNone(asyncio.run(self.fetcher("auto").fetch("   ")))

    def test_empty_file_ignored(self):
        (self.local / "古河渚.jpg").write_bytes(b"")
        self.assertIsNone(asyncio.run(self.fetcher("local").fetch("古河渚")))


class TestCache(ImageTestBase):
    def _cache_file(self, name: str, ext: str = ".jpg", age: float = 0) -> Path:
        key = hashlib.sha1(norm(name).encode("utf-8")).hexdigest()
        path = self.cache / f"{key}{ext}"
        path.write_bytes(b"img")
        if age:
            old = time.time() - age
            import os

            os.utime(path, (old, old))
        return path

    def test_cache_hit_skips_network(self):
        cached = self._cache_file("古河渚")
        path = asyncio.run(self.fetcher("bangumi").fetch("古河渚", "CLANNAD"))
        self.assertEqual(path, cached)

    def test_cache_expired_is_ignored(self):
        self._cache_file("古河渚", age=40 * 86400)
        f = self.fetcher("bangumi", days=30)
        self.assertIsNone(f._find_cached("古河渚"))

    def test_miss_marker(self):
        f = self.fetcher("bangumi")
        self.assertFalse(f._is_miss("古河渚"))
        f._mark_miss("古河渚")
        self.assertTrue(f._is_miss("古河渚"))
        # miss 命中后直接返回 None，不会发起网络请求
        self.assertIsNone(asyncio.run(f.fetch("古河渚")))

    def test_miss_expires(self):
        f = self.fetcher("bangumi")
        f._mark_miss("古河渚")
        import os

        old = time.time() - 2 * 86400
        os.utime(f._miss_path("古河渚"), (old, old))
        self.assertFalse(f._is_miss("古河渚"))

    def test_atomic_write(self):
        path = ImageFetcher._write_atomic(self.cache / "a.jpg", b"123")
        self.assertIsNotNone(path)
        self.assertEqual(path.read_bytes(), b"123")


if __name__ == "__main__":
    unittest.main(verbosity=2)
