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


class _Resp:
    def __init__(self, status: int, body: bytes = b"", ctype: str = "image/jpeg") -> None:
        self.status = status
        self._body = body
        self.headers = {"Content-Type": ctype}

    async def read(self) -> bytes:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    """只对 ok_url 返回图片，其余 404。"""

    def __init__(self, ok_url: str) -> None:
        self.ok_url = ok_url
        self.hits: list[str] = []

    def get(self, url: str):
        self.hits.append(url)
        if url == self.ok_url:
            return _Resp(200, b"\xff\xd8fakejpeg")
        return _Resp(404)


class TestDownloadFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.fetcher = ImageFetcher(
            cache_dir=self.cache, mirrors=["https://m1.example.com"]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_falls_through_to_second_size(self):
        big = "https://lain.bgm.tv/pic/big.jpg"
        small = "https://lain.bgm.tv/pic/small.jpg"
        session = _Session(ok_url=small)
        path = asyncio.run(self.fetcher._download(session, [big, small], "古河渚"))
        self.assertIsNotNone(path)
        self.assertIn(big, session.hits)
        self.assertIn(small, session.hits)

    def test_tries_mirror_before_origin(self):
        url = "https://lain.bgm.tv/pic/a.jpg"
        session = _Session(ok_url=url)
        asyncio.run(self.fetcher._download(session, [url], "古河渚"))
        self.assertEqual(session.hits[0], "https://m1.example.com/pic/a.jpg")
        self.assertEqual(session.hits[-1], url)

    def test_all_fail_sets_reason(self):
        session = _Session(ok_url="https://never.example.com/x.jpg")
        path = asyncio.run(
            self.fetcher._download(session, ["https://lain.bgm.tv/pic/a.jpg"], "古河渚")
        )
        self.assertIsNone(path)
        self.assertTrue(self.fetcher.last_reason)

    def test_string_url_still_supported(self):
        url = "https://lain.bgm.tv/pic/a.jpg"
        session = _Session(ok_url=url)
        self.assertIsNotNone(
            asyncio.run(self.fetcher._download(session, url, "古河渚"))
        )


class TestMissMarker(ImageTestBase):
    def test_miss_expires_quickly(self):
        from core.images import MISS_TTL

        self.assertLessEqual(MISS_TTL, 3600)

    def test_success_clears_miss(self):
        f = self.fetcher("bangumi")
        f._mark_miss("古河渚")
        self.assertTrue(f._is_miss("古河渚"))
        f._clear_miss("古河渚")
        self.assertFalse(f._is_miss("古河渚"))

    def test_known_url_skips_search(self):
        f = self.fetcher("bangumi")
        key = f._cache_prefix("古河渚")
        f._urls[key] = "https://img.example.com/a.jpg"

        calls: list[str] = []
        hit = self.cache / "hit.jpg"
        hit.write_bytes(b"img")

        async def fake_direct(name: str, url: str):
            calls.append(url)
            return hit

        async def boom(name: str):
            raise AssertionError("已知地址成功时不应再走搜索")

        f._download_direct = fake_direct  # type: ignore[assignment]
        f._download_from_bangumi = boom  # type: ignore[assignment]
        self.assertEqual(asyncio.run(f.fetch("古河渚")), hit)
        self.assertEqual(calls, ["https://img.example.com/a.jpg"])


try:
    import PIL  # noqa: F401

    HAS_PIL = True
except ImportError:  # pragma: no cover
    HAS_PIL = False


@unittest.skipUnless(HAS_PIL, "需要 Pillow")
class TestUpscale(unittest.TestCase):
    def _png(self, w: int, h: int) -> bytes:
        from io import BytesIO

        from PIL import Image as PILImage

        buf = BytesIO()
        PILImage.new("RGB", (w, h), (200, 100, 50)).save(buf, format="PNG")
        return buf.getvalue()

    def test_small_image_upscaled(self):
        from io import BytesIO

        from PIL import Image as PILImage

        from core.images import upscale_image

        data, ext = upscale_image(self._png(200, 300))
        self.assertEqual(ext, ".jpg")
        with PILImage.open(BytesIO(data)) as im:
            # 200px 起放大，受 max_scale=2.5 限制 → 500px
            self.assertGreaterEqual(im.size[0], 480)
            self.assertLess(im.size[0], 720)

    def test_reaches_target_when_source_big_enough(self):
        from io import BytesIO

        from PIL import Image as PILImage

        from core.images import upscale_image

        data, _ = upscale_image(self._png(400, 600))
        with PILImage.open(BytesIO(data)) as im:
            self.assertEqual(im.size[0], 720)

    def test_large_image_untouched(self):
        from core.images import upscale_image

        raw = self._png(900, 1200)
        data, ext = upscale_image(raw)
        self.assertEqual(data, raw)
        self.assertEqual(ext, "")

    def test_scale_capped(self):
        from io import BytesIO

        from PIL import Image as PILImage

        from core.images import upscale_image

        data, _ = upscale_image(self._png(100, 100), min_width=720, max_scale=2.5)
        with PILImage.open(BytesIO(data)) as im:
            self.assertLessEqual(im.size[0], 260)

    def test_garbage_bytes_survive(self):
        from core.images import upscale_image

        data, ext = upscale_image(b"not an image")
        self.assertEqual(data, b"not an image")
        self.assertEqual(ext, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
