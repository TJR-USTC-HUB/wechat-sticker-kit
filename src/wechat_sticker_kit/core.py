"""Core conversion pipeline.

Everything WeChat cares about lives here:

* a square canvas (custom stickers are shown square in the chat list)
* a 240x240 / 500x500 preset (240 is the official sticker size)
* PNG / JPG / GIF output, hard-capped at a byte budget
* metadata stripped, EXIF rotation applied, first frame only for animated input
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

INPUT_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".apng",
    ".heic", ".heif", ".bmp", ".tif", ".tiff", ".gif",
)
OUTPUT_FORMATS = ("png", "jpg", "gif")

#: byte budgets, the first one is what WeChat itself enforces
BUDGETS = {
    "gif": 1024 * 1024,        # 动图表情常见上限 1 MB
    "chat": 5 * 1024 * 1024,   # 微信「添加的单个表情」上限 5 MB
    "platform": 500 * 1024,    # 微信表情开放平台主图建议 <= 500 KB
    "tiny": 100 * 1024,        # 聊天列表 / 老设备友好
}

#: vertical anchor used by the square crop, 0 = top, 1 = bottom
ANCHORS = {"center": 0.5, "top": 0.25, "bottom": 0.75, "face": 0.42}


class StickerError(RuntimeError):
    """Raised when an input file cannot be turned into a sticker."""


@dataclass
class Result:
    """One converted file."""

    src: Path
    dst: Optional[Path]
    width: int
    height: int
    size: int
    fmt: str
    note: str = ""

    @property
    def kb(self) -> float:
        return round(self.size / 1024, 1)


def safe_stem(name: str) -> str:
    """Sanitise a file name into a usable output stem.

    CDN names such as 'x.png@406w_270h_1s.avif' or 'shot.png.webp' would
    otherwise produce output like 'x.png@406w_270h_1s.gif'.
    """
    base = str(name).split("@", 1)[0]
    exts = sorted({e for e in INPUT_SUFFIXES} | {".jpeg"}, key=len, reverse=True)
    shrinking = True
    while shrinking:
        shrinking = False
        low = base.lower()
        for ext in exts:
            if low.endswith(ext) and len(base) > len(ext):
                base = base[: -len(ext)]
                shrinking = True
                break
    return base or "sticker"


def load_image(path):
    """Open the file, honour EXIF rotation and collapse animations to frame 0."""
    path = Path(path)
    try:
        im = Image.open(path)
        im.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise StickerError("cannot read image: %s" % path) from exc

    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    try:
        rotated = ImageOps.exif_transpose(im)
        if rotated is not None:      # very old Pillow returned None on some builds
            im = rotated
    except Exception:  # pragma: no cover - broken EXIF is not fatal
        pass
    return im


def _has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info


def _edge_color(im: Image.Image) -> Tuple[int, int, int]:
    """Average colour of the frame border, used for the 'auto' background."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    band = max(1, h // 12)
    top = rgb.crop((0, 0, w, band)).resize((32, 4), Image.BILINEAR)
    bottom = rgb.crop((0, h - band, w, h)).resize((32, 4), Image.BILINEAR)
    strip = Image.new("RGB", (32, 8))
    strip.paste(top, (0, 0))
    strip.paste(bottom, (0, 4))
    pixels = list(strip.getdata())
    n = float(len(pixels))
    return (
        int(sum(p[0] for p in pixels) / n),
        int(sum(p[1] for p in pixels) / n),
        int(sum(p[2] for p in pixels) / n),
    )


def _background(im: Image.Image, size: int, anchor: float, style: str, fill) -> Image.Image:
    """Build the square backdrop for the 'pad' / 'fit' modes."""
    if style == "blur":
        cover = ImageOps.fit(im.convert("RGB"), (size, size), Image.LANCZOS, centering=(0.5, anchor))
        radius = max(6, size // 14)
        bg = cover.filter(ImageFilter.GaussianBlur(radius))
        # darken a little so the pasted picture always reads on top
        return bg.point(lambda v: int(v * 0.72))

    if style == "transparent":
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))

    if fill is None:
        fill = _edge_color(im)
    return Image.new("RGB", (size, size), tuple(fill))


def to_square(
    im: Image.Image,
    size: int = 240,
    mode: str = "cover",
    anchor: str = "center",
    bg: str = "blur",
    fill=None,
) -> Image.Image:
    """Return the picture as a square sticker of size x size pixels.

    mode:
        cover  fill the square, crop the overflow (best for memes)
        pad    keep the whole picture, fill the sides with a blurred backdrop
        fit    keep the whole picture, fill the sides with a flat colour
        ...    pass bg="transparent" to any of them for a transparent backdrop
        keep   do not square at all, just cap the longest side at size
    """
    if mode not in ("cover", "pad", "fit", "keep"):
        raise ValueError("unknown mode: %s" % mode)
    if size < 16:
        raise ValueError("size must be >= 16")

    anchor_y = ANCHORS.get(anchor, anchor if isinstance(anchor, (int, float)) else 0.5)

    if mode == "keep":
        w, h = im.size
        longest = max(w, h)
        if longest <= size:
            return im.copy()
        scale = size / float(longest)
        return im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)

    if mode == "cover":
        return ImageOps.fit(im, (size, size), Image.LANCZOS, centering=(0.5, float(anchor_y)))

    if bg == "transparent":
        style = "transparent"
    elif mode == "pad" and bg == "blur":
        style = "blur"
    else:
        style = "flat"
    canvas = _background(im, size, float(anchor_y), style, fill).convert("RGBA")
    w, h = im.size
    scale = min(size / float(w), size / float(h))
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    pic = im.convert("RGBA").resize((tw, th), Image.LANCZOS)
    canvas.alpha_composite(pic, ((size - tw) // 2, (size - th) // 2))
    return canvas


def _quantize(im: Image.Image, colors: int) -> Image.Image:
    """Quantize to a GIF palette, reserving one index for full transparency."""
    q = getattr(Image, "Quantize", Image)
    dither = getattr(getattr(Image, "Dither", Image), "FLOYDSTEINBERG", 1)

    if _has_alpha(im):
        rgba = im.convert("RGBA")
        alpha = rgba.split()[-1]
        if alpha.getextrema()[0] < 128:            # there is something to keep transparent
            idx = max(2, min(colors, 256)) - 1
            p = rgba.convert("RGB").quantize(
                colors=max(2, idx), method=getattr(q, "MEDIANCUT", 0), dither=dither
            )
            p.paste(idx, mask=alpha.point(lambda a: 255 if a < 128 else 0))
            p.info["transparency"] = idx
            return p
        im = rgba

    return im.convert("RGB").quantize(colors=colors, method=getattr(q, "MEDIANCUT", 0), dither=dither)


def _save_bytes(im: Image.Image, fmt: str, quality=None) -> bytes:
    buf = io.BytesIO()
    params = {}
    if fmt == "png":
        params = {"optimize": True}
    elif fmt == "jpg":
        params = {"optimize": True, "progressive": True}
        if quality:
            params["quality"] = quality
    elif fmt == "gif":
        if im.mode != "P":
            im = _quantize(im, 256)
        params = {"optimize": True}
        if "transparency" in im.info:
            params["transparency"] = im.info["transparency"]
    im.save(buf, "JPEG" if fmt == "jpg" else fmt.upper(), **params)
    return buf.getvalue()


def _fits(data: bytes, budget) -> bool:
    return budget is None or len(data) <= budget


def encode(im: Image.Image, fmt: str = "png", budget=None) -> Tuple[bytes, str]:
    """Encode the image and squeeze it until it fits the byte budget.

    Returns (payload, note); note explains what had to be sacrificed.
    """
    fmt = fmt.lower()
    if fmt not in OUTPUT_FORMATS:
        raise ValueError("unsupported output format: %s" % fmt)

    work = im
    if fmt == "jpg" and _has_alpha(work):
        rgba = work.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        work = flat

    data = _save_bytes(work, fmt)
    if _fits(data, budget):
        return data, ""

    if fmt in ("png", "gif"):
        for colors in (256, 128, 64, 32):
            data = _save_bytes(_quantize(work, colors), fmt)
            if _fits(data, budget):
                return data, "palette reduced to %d colours" % colors

    if fmt == "jpg":
        for quality in (88, 80, 72, 64, 56, 48, 40):
            data = _save_bytes(work, fmt, quality=quality)
            if _fits(data, budget):
                return data, "jpeg quality %d" % quality

    w, h = work.size
    while min(w, h) > 32:
        w, h = max(1, int(w * 0.9)), max(1, int(h * 0.9))
        work = work.resize((w, h), Image.LANCZOS)
        data = _save_bytes(work, fmt)
        if _fits(data, budget):
            return data, "downscaled to %dx%d" % (w, h)

    return data, "budget unreachable, returned the smallest result"


def convert_file(
    src,
    out_dir,
    size: int = 240,
    mode: str = "keep",
    fmt: str = "gif",
    budget=BUDGETS["gif"],
    anchor: str = "center",
    bg: str = "blur",
    fill=None,
    suffix: str = "",
) -> Result:
    """Convert one file and write it into out_dir."""
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower()
    if fmt not in OUTPUT_FORMATS:
        raise ValueError("unsupported output format: %s" % fmt)

    im = load_image(src)
    sticker = to_square(im, size=size, mode=mode, anchor=anchor, bg=bg, fill=fill)
    data, note = encode(sticker, fmt=fmt, budget=budget)

    dst = out_dir / ("%s%s.%s" % (safe_stem(src.name), suffix, fmt))
    if dst.resolve() == src.resolve():  # never eat the file we were given
        dst = out_dir / ("%s%s-sticker.%s" % (safe_stem(src.name), suffix, fmt))
    dst.write_bytes(data)
    w, h = sticker.size
    return Result(src=src, dst=dst, width=w, height=h, size=len(data), fmt=fmt, note=note)
