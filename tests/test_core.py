"""Tests for wechat-sticker-kit (stdlib unittest, no extra deps)."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wechat_sticker_kit import BUDGETS, encode, to_square  # noqa: E402
from wechat_sticker_kit.cli import main  # noqa: E402
from wechat_sticker_kit.core import convert_file, load_image  # noqa: E402


def make_image(w=800, h=450, color=(30, 90, 160), alpha=False):
    mode = "RGBA" if alpha else "RGB"
    im = Image.new(mode, (w, h), color if not alpha else color + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([w // 4, h // 4, w // 2, h // 2], fill=(240, 60, 80) if not alpha else (240, 60, 80, 255))
    return im


def noisy(w=600, h=600):
    im = Image.effect_noise((w, h), 96).convert("RGB")
    return im


class SquareTests(unittest.TestCase):
    def test_cover_is_square(self):
        out = to_square(make_image(), size=240, mode="cover")
        self.assertEqual(out.size, (240, 240))

    def test_keep_preserves_aspect(self):
        out = to_square(make_image(1200, 600), size=240, mode="keep")
        self.assertEqual(out.size, (240, 120))

    def test_pad_keeps_whole_picture_and_fills_backdrop(self):
        out = to_square(make_image(1000, 500, (250, 250, 250)), size=240, mode="pad", bg="blur")
        self.assertEqual(out.size, (240, 240))
        corner = out.convert("RGB").getpixel((2, 2))
        # the backdrop is a darkened blur of the picture, never transparent
        self.assertNotEqual(out.getpixel((2, 2))[3], 0)
        self.assertLess(sum(corner), 3 * 250 * 0.95)

    def test_fit_uses_flat_colour(self):
        out = to_square(make_image(1000, 500, (10, 20, 30)), size=240, mode="fit", fill=(255, 255, 0))
        self.assertEqual(out.convert("RGB").getpixel((2, 2)), (255, 255, 0))

    def test_transparent_backdrop(self):
        out = to_square(make_image(1000, 500, (30, 90, 160)), size=240, mode="pad", bg="transparent")
        self.assertEqual(out.size, (240, 240))
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((2, 2))[3], 0)      # the pad is fully transparent
        self.assertGreater(out.getpixel((120, 120))[3], 0)  # the picture itself stays opaque

    def test_cover_keeps_alpha(self):
        out = to_square(make_image(600, 600, (0, 0, 0), alpha=True), size=240, mode="cover")
        self.assertIn(out.mode, ("RGBA", "LA", "P"))


class EncodeTests(unittest.TestCase):
    def test_png_without_budget_is_lossless_sized(self):
        data, note = encode(noisy(240, 240), "png", None)
        self.assertEqual(note, "")
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.size, (240, 240))

    def test_budget_is_enforced_by_palette(self):
        img = noisy(240, 240)
        data, note = encode(img, "png", BUDGETS["tiny"])
        self.assertLessEqual(len(data), BUDGETS["tiny"])
        self.assertTrue(note)

    def test_budget_is_enforced_by_downscale(self):
        img = noisy(512, 512)
        data, note = encode(img, "png", 30 * 1024)
        self.assertLessEqual(len(data), 30 * 1024)

    def test_jpeg_flattens_alpha(self):
        data, _ = encode(make_image(240, 240, alpha=True), "jpg", None)
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.mode, "RGB")

    def test_gif_output(self):
        data, _ = encode(make_image(240, 240), "gif", None)
        self.assertTrue(data.startswith(b"GIF8"))


class ConvertTests(unittest.TestCase):
    def test_convert_file_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "photo.jpg"
            make_image(900, 600).save(src, "JPEG")
            res = convert_file(src, tmp / "out", size=240, mode="cover")
            self.assertTrue(res.dst.exists())
            self.assertEqual(res.dst.suffix, ".png")
            self.assertEqual((res.width, res.height), (240, 240))
            self.assertLessEqual(res.size, BUDGETS["chat"])
            with Image.open(res.dst) as im:
                self.assertEqual(im.size, (240, 240))

    def test_in_place_conversion_never_overwrites_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "meme.png"
            make_image(600, 400).save(src)
            before = src.read_bytes()
            res = convert_file(src, tmp, size=240, mode="cover")
            self.assertNotEqual(res.dst, src)
            self.assertEqual(src.read_bytes(), before)
            self.assertIn("-sticker", res.dst.name)

    def test_convert_file_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bad = tmp / "bad.png"
            bad.write_bytes(b"not an image")
            with self.assertRaises(Exception):
                convert_file(bad, tmp / "out")


class CliTests(unittest.TestCase):
    def test_cli_converts_a_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src_dir = tmp / "src"
            src_dir.mkdir()
            make_image(600, 400).save(src_dir / "a.png")
            make_image(400, 600).save(src_dir / "b.jpg", "JPEG")
            rc = main([str(src_dir), "-o", str(tmp / "out"), "-q"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(list((tmp / "out").glob("*.png"))), 2)

    def test_cli_json_summary(self):
        import contextlib

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "c.png"
            make_image(300, 300).save(src)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main([str(src), "-o", str(tmp / "out"), "--json", "--size", "500", "-m", "pad"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["files"][0]["width"], 500)
            self.assertEqual(payload["files"][0]["height"], 500)

    def test_cli_missing_input(self):
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(["definitely-not-here.png"])
        self.assertEqual(rc, 2)


class VideoTests(unittest.TestCase):
    def test_assemble_gif_keeps_every_frame(self):
        from wechat_sticker_kit import assemble_gif

        frames = [make_image(120, 120, (i * 30, 90, 200)) for i in range(6)]
        data = assemble_gif(frames, fps=10)
        self.assertTrue(data.startswith(b"GIF8"))
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.n_frames, 6)

    def test_frames_squeeze_under_budget(self):
        from wechat_sticker_kit import frames_to_sticker

        frames = [noisy(240, 240) for _ in range(8)]
        data, note = frames_to_sticker(frames, fps=12, budget=80 * 1024)
        self.assertLessEqual(len(data), 80 * 1024)
        self.assertIsInstance(note, str)

    def test_missing_ffmpeg_raises_with_hint(self):
        from wechat_sticker_kit import StickerError, video_to_gif

        old = os.environ.get("WXSTICKER_FFMPEG")
        os.environ["WXSTICKER_FFMPEG"] = "definitely-missing-ffmpeg.exe"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(StickerError) as ctx:
                    video_to_gif("whatever.mp4", Path(tmp) / "o.gif")
            self.assertIn("WXSTICKER_FFMPEG", str(ctx.exception))
        finally:
            if old is None:
                os.environ.pop("WXSTICKER_FFMPEG", None)
            else:
                os.environ["WXSTICKER_FFMPEG"] = old

    def test_cli_video_without_ffmpeg_fails_cleanly(self):
        import contextlib

        old = os.environ.get("WXSTICKER_FFMPEG")
        os.environ["WXSTICKER_FFMPEG"] = "definitely-missing-ffmpeg.exe"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                clip = tmp / "clip.mp4"
                clip.write_bytes(b"\x00\x00\x00\x18ftypmp42")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = main([str(clip), "-o", str(tmp / "out"), "-q"])
                self.assertEqual(rc, 1)
                self.assertIn("WXSTICKER_FFMPEG", err.getvalue())
        finally:
            if old is None:
                os.environ.pop("WXSTICKER_FFMPEG", None)
            else:
                os.environ["WXSTICKER_FFMPEG"] = old


if __name__ == "__main__":
    unittest.main()
