"""End-to-end smoke test: build a few images, run the CLI, check the GIFs.

    python scripts/smoke.py

No external files needed; exits non-zero when anything is off.
"""

import io
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wechat_sticker_kit.cli import main  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  " + detail) if detail else ""))
    if not cond:
        FAILED.append(name)


def make(path, size=(900, 600), alpha=False):
    mode = "RGBA" if alpha else "RGB"
    im = Image.new(mode, size, (28, 84, 160) if not alpha else (28, 84, 160, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2], fill=(240, 80, 90, 255) if alpha else (240, 80, 90))
    im.save(path)
    return path


def gif_info(path):
    with Image.open(path) as im:
        return im.format, im.size, getattr(im, "n_frames", 1), path.stat().st_size


def main_smoke():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        out = tmp / "out"

        img = make(tmp / "photo.png")
        rc = main([str(img), "-o", str(out), "-q"])
        fmt, size, frames, nbytes = gif_info(out / "photo.gif")
        check("image -> gif", rc == 0 and fmt == "GIF", "%s %s" % (fmt, size))
        check("image stays static", frames == 1, "frames=%d" % frames)
        check("aspect ratio kept", size == (240, 160), str(size))
        check("under 1 MB", nbytes <= 1024 * 1024, "%.1f KB" % (nbytes / 1024))

        rc = main([str(img), "-o", str(out / "sq"), "-m", "cover", "-q"])
        fmt, size, frames, _ = gif_info(out / "sq" / "photo.gif")
        check("cover mode is square", size == (240, 240), str(size))

        alpha = make(tmp / "alpha.png", (900, 600), alpha=True)
        rc = main([str(alpha), "-o", str(out / "tr"), "-m", "pad", "--bg", "transparent", "-q"])
        with Image.open(out / "tr" / "alpha.gif") as im:
            corner = im.convert("RGBA").getpixel((1, 1))
        check("transparent pad survives gif", corner[3] == 0, "corner=%s" % (corner,))

        rc = main([str(img), "-o", str(out / "png"), "-f", "png", "-q"])
        check("png still available", (out / "png" / "photo.png").exists())

        big = make(tmp / "big.png", (1600, 1200))
        rc = main([str(big), "-o", str(out / "tiny"), "-b", "tiny", "-q"])
        check("budget enforced", (out / "tiny" / "big.gif").stat().st_size <= 100 * 1024,
              "%.1f KB" % ((out / "tiny" / "big.gif").stat().st_size / 1024))

    print()
    if FAILED:
        print("%d check(s) failed: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("all smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_smoke())
