"""Video -> GIF sticker pipeline.

ffmpeg does the decoding (we never link against a codec library), Pillow does
the palette and the GIF assembly so we stay inside the sticker byte budget.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

from PIL import Image

from .core import BUDGETS, StickerError, encode, to_square

VIDEO_SUFFIXES = (
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi",
    ".wmv", ".flv", ".mpg", ".mpeg", ".3gp",
)

INSTALL_HINT = (
    "ffmpeg not found. Install it and make sure it is on PATH "
    "(Windows: winget install Gyan.FFmpeg | macOS: brew install ffmpeg | "
    "Debian/Ubuntu: sudo apt install ffmpeg), or run "
    'pip install "wechat-sticker-kit[video]", or point WXSTICKER_FFMPEG at the binary.'
)


def ffmpeg_path() -> str:
    """Locate a usable ffmpeg binary, or raise a friendly error."""
    env = os.environ.get("WXSTICKER_FFMPEG")
    if env:
        if Path(env).is_file():
            return env
        raise StickerError("WXSTICKER_FFMPEG points at a missing file: %s" % env)

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:  # optional dependency, ships a static build
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    raise StickerError(INSTALL_HINT)


def probe_duration(path, ffmpeg: Optional[str] = None) -> float:
    """Read the clip duration in seconds from ffmpeg's banner."""
    ffmpeg = ffmpeg or ffmpeg_path()
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, errors="replace",
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    if not match:
        return 0.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def extract_frames(
    src,
    out_dir,
    fps: float = 12,
    width: int = 480,
    start: float = 0.0,
    duration: Optional[float] = None,
    ffmpeg: Optional[str] = None,
    max_frames: int = 120,
) -> List[Path]:
    """Decode a time range into PNG frames and return them in order."""
    ffmpeg = ffmpeg or ffmpeg_path()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    width = int(width)
    if width % 2:  # yuv420 needs even dimensions
        width += 1

    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", "%.3f" % max(0.0, start),
        "-i", str(src),
    ]
    if duration:
        cmd += ["-t", "%.3f" % duration]
    cmd += [
        "-vf", "fps=%s,scale=%d:-2:flags=lanczos" % (fps, width),
        "-frames:v", str(max_frames),
        str(out_dir / "frame_%04d.png"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise StickerError("ffmpeg failed: %s" % (proc.stderr.strip().splitlines() or ["unknown error"])[-1])

    frames = sorted(out_dir.glob("frame_*.png"))
    if not frames:
        raise StickerError("no frames decoded, is this really a video? %s" % src)
    return frames


def _global_palette(frames: Sequence[Image.Image], colors: int) -> Image.Image:
    """Build one palette for the whole clip so colours do not flicker."""
    sample = list(frames[:12])
    w, h = sample[0].size
    strip = Image.new("RGB", (w, h * len(sample)))
    for i, f in enumerate(sample):
        strip.paste(f.convert("RGB"), (0, i * h))
    return strip.quantize(colors=colors, method=Image.MEDIANCUT)


def assemble_gif(
    frames: Sequence[Image.Image],
    fps: float = 12,
    colors: int = 256,
    step: int = 1,
    dither: bool = True,
) -> bytes:
    """Turn RGB frames into a looping GIF payload."""
    import io

    picked = list(frames)[::max(1, step)]
    if len(picked) < 2:
        picked = list(frames)[:1] * 2

    palette = _global_palette(picked, colors)
    d = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    p_frames = [f.convert("RGB").quantize(palette=palette, dither=d) for f in picked]

    buf = io.BytesIO()
    p_frames[0].save(
        buf, "GIF", save_all=True, append_images=p_frames[1:],
        duration=int(1000 / max(1.0, fps)) * max(1, step), loop=0,
        optimize=True, disposal=2,
    )
    return buf.getvalue()


def frames_to_sticker(
    frames: Sequence[Image.Image],
    fps: float = 12,
    budget: int = BUDGETS["gif"],
    dither: bool = True,
):
    """Squeeze the clip under the byte budget, cheapest quality loss first."""
    attempts = []
    for colors in (256, 128, 64, 32):
        attempts.append((colors, 1))
    for colors in (128, 64, 32):
        attempts.append((colors, 2))
        attempts.append((colors, 3))
    for colors in (64, 32):
        attempts.append((colors, 4))

    data = b""
    note = ""
    for colors, step in attempts:
        data = assemble_gif(frames, fps=fps / step, colors=colors, step=step, dither=dither)
        if len(data) <= budget:
            note = "" if (colors, step) == (256, 1) else "gif %d colours, every %d frame(s)" % (colors, step)
            return data, note

    # last resort: shrink the frames
    scale = 0.8
    work = list(frames)
    while scale > 0.3:
        work = [f.resize((max(1, int(f.width * 0.8)), max(1, int(f.height * 0.8))), Image.LANCZOS) for f in work]
        data = assemble_gif(work, fps=fps, colors=64, step=2)
        if len(data) <= budget:
            return data, "downscaled to %dx%d" % work[0].size
        scale *= 0.8

    return data, "budget unreachable, returned the smallest gif"


def video_to_gif(
    src,
    dst,
    size: int = 240,
    fps: float = 12,
    start: float = 0.0,
    duration: Optional[float] = None,
    budget: int = BUDGETS["gif"],
    mode: str = "cover",
    bg: str = "blur",
    dither: bool = True,
):
    """Decode, square-crop and encode a video into a WeChat GIF sticker."""
    src = Path(src)
    dst = Path(dst)
    ffmpeg = ffmpeg_path()

    clip_len = probe_duration(src, ffmpeg) or 0.0
    if duration is None:
        duration = 5.0
        if clip_len:
            duration = min(5.0, max(1.0, clip_len - start))
    if clip_len and start >= clip_len:
        raise StickerError("start %.2fs is beyond the end of the clip (%.2fs)" % (start, clip_len))

    with tempfile.TemporaryDirectory(prefix="wxsticker_") as tmp:
        paths = extract_frames(
            src, tmp, fps=fps, width=min(720, max(size * 2, 240)),
            start=start, duration=duration, ffmpeg=ffmpeg,
        )
        frames = []
        for p in paths:
            with Image.open(p) as im:
                frames.append(im.convert("RGB"))
        if mode != "keep":
            frames = [to_square(f, size=size, mode=mode, bg=bg).convert("RGB") for f in frames]

    data, note = frames_to_sticker(frames, fps=fps, budget=budget, dither=dither)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return dst, len(data), note, len(frames)
