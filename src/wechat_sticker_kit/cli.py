"""Command line entry point for wechat-sticker-kit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import BUDGETS, INPUT_SUFFIXES, OUTPUT_FORMATS, Result, StickerError, convert_file, safe_stem
from .video import VIDEO_SUFFIXES, video_to_gif

PRESET_SIZES = {240: "WeChat standard", 500: "high-res chat", 1000: "master copy"}
ALL_SUFFIXES = tuple(sorted(set(INPUT_SUFFIXES) | set(VIDEO_SUFFIXES)))


def _parse_color(value):
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("auto", "none", "blur"):
        return v
    if v.startswith("#"):
        v = v[1:]
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise argparse.ArgumentTypeError("bad colour: %s" % value)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _parse_budget(value):
    v = str(value).strip().lower()
    if v in BUDGETS:
        return BUDGETS[v]
    if v.endswith("kb"):
        return int(float(v[:-2]) * 1024)
    if v.endswith("mb"):
        return int(float(v[:-2]) * 1024 * 1024)
    if v in ("none", "0", "off"):
        return None
    return int(float(v))


def _iter_inputs(paths, recursive):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            for f in sorted(it):
                if f.is_file() and f.suffix.lower() in ALL_SUFFIXES:
                    yield f
        elif p.is_file():
            yield p
        else:
            raise StickerError("no such file or directory: %s" % p)


def _configure_stdio():
    """Windows consoles default to cp936/cp1252; CJK paths would crash print()."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_parser():
    p = argparse.ArgumentParser(
        prog="wxsticker",
        description="Convert PNG/JPG images and MP4/MOV videos into GIF stickers WeChat accepts: "
                    "images become a single static frame, videos a looping clip, aspect ratio untouched "
                    "and the file squeezed under the size limit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wxsticker meme.png                     # -> meme.gif, one static frame\n"
            "  wxsticker meme.png -m cover            # opt-in square crop\n"
            "  wxsticker photos/ -r -o out --size 240 --mode cover --budget platform\n"
            "  wxsticker clip.mp4 -s 240 --fps 12 --duration 3\n"
            "  wxsticker a.jpg b.png -m pad --bg blur -f png\n"
        ),
    )
    p.add_argument("inputs", nargs="+", metavar="IMAGE", help="images, videos or folders")
    p.add_argument("-o", "--out", default="stickers", help="output folder (default: stickers)")
    p.add_argument("-s", "--size", type=int, default=240, choices=sorted(PRESET_SIZES),
                   help="sticker edge in px, 240 = WeChat standard (default)")
    p.add_argument("-m", "--mode", default="keep", choices=("cover", "pad", "fit", "keep"),
                   help="keep = keep the original aspect ratio (default, no padding); "
                        "cover/pad/fit force a square canvas if you really want one")
    p.add_argument("-f", "--format", default="gif", choices=OUTPUT_FORMATS,
                   help="output format (default: gif, the only one WeChat accepts reliably); "
                        "images become a single-frame gif, videos a looping gif")
    p.add_argument("-b", "--budget", default=None, type=_parse_budget,
                   help="byte budget: gif (1 MB), chat (5 MB), platform (500 KB), tiny (100 KB), or 800kb")
    p.add_argument("--max-kb", type=float, default=None, help="shortcut for --budget, in KB")
    p.add_argument("--bg", default="blur",
                   help="backdrop for pad/fit: blur, auto, transparent, #rrggbb")
    p.add_argument("--anchor", default="center", choices=("center", "top", "bottom", "face"),
                   help="where to anchor the square crop (default: center)")
    p.add_argument("-r", "--recursive", action="store_true", help="walk folders recursively")
    p.add_argument("--dry-run", action="store_true", help="report what would happen, write nothing")
    p.add_argument("--json", action="store_true", help="machine readable summary on stdout")
    p.add_argument("-q", "--quiet", action="store_true", help="only print errors")

    v = p.add_argument_group("video")
    v.add_argument("--fps", type=float, default=12.0, help="frames per second to sample (default: 12)")
    v.add_argument("--start", type=float, default=0.0, help="start offset in seconds (default: 0)")
    v.add_argument("--duration", type=float, default=None, help="clip length in seconds (default: up to 5)")
    v.add_argument("--no-dither", action="store_true", help="disable dithering, smaller but banded gif")

    p.add_argument("--version", action="version", version="wechat-sticker-kit %s" % __version__)
    return p


def main(argv=None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    budget = args.budget if args.max_kb is None else int(args.max_kb * 1024)

    try:
        files = list(_iter_inputs(args.inputs, args.recursive))
    except StickerError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if not files:
        print("error: no supported files found (looked for %s)" % ", ".join(ALL_SUFFIXES), file=sys.stderr)
        return 2

    bg = args.bg
    fill = None
    if bg not in ("blur", "auto", "transparent"):
        try:
            fill = _parse_color(bg)
        except argparse.ArgumentTypeError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        bg = "auto"

    out_dir = Path(args.out)
    results = []
    failures = []
    seen = {}

    for src in files:
        is_video = src.suffix.lower() in VIDEO_SUFFIXES
        wants_gif = is_video or args.format == "gif"
        file_budget = budget if budget is not None else (BUDGETS["gif"] if wants_gif else BUDGETS["chat"])

        if args.dry_run:
            suffix = ".gif" if is_video else "." + args.format
            if not args.quiet:
                print("%-40s -> %s (dry run)" % (src.name, out_dir / (safe_stem(src.name) + suffix)))
            continue

        stem = safe_stem(src.name)
        count = seen.get(stem, 0) + 1
        seen[stem] = count
        suffix = "" if count == 1 else "-%d" % count

        try:
            if is_video:
                dst = out_dir / (stem + suffix + ".gif")
                _, nbytes, note, nframes = video_to_gif(
                    src, dst, size=args.size, fps=args.fps, start=args.start,
                    duration=args.duration, budget=file_budget, mode=args.mode,
                    bg=bg, dither=not args.no_dither,
                )
                results.append(Result(src=src, dst=dst, width=args.size, height=args.size,
                                      size=nbytes, fmt="gif",
                                      note=(note + ", " if note else "") + "%d frames" % nframes))
            else:
                results.append(convert_file(
                    src, out_dir,
                    size=args.size, mode=args.mode, fmt=args.format,
                    budget=file_budget, anchor=args.anchor, bg=bg, fill=fill,
                    suffix=suffix,
                ))
        except (StickerError, ValueError, OSError) as exc:
            failures.append((src, str(exc)))
            print("FAILED %s: %s" % (src, exc), file=sys.stderr)
            continue

    if args.json:
        payload = {
            "output": str(out_dir),
            "size": args.size,
            "mode": args.mode,
            "format": args.format,
            "budget": budget,
            "files": [
                {
                    "src": str(r.src),
                    "dst": str(r.dst),
                    "width": r.width,
                    "height": r.height,
                    "bytes": r.size,
                    "note": r.note,
                }
                for r in results
            ],
            "failures": [{"src": str(s), "error": e} for s, e in failures],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if failures else 0

    if not args.quiet:
        for r in results:
            name = r.src.name
            if len(name) > 34:
                name = name[:31] + "..."
            note = ("  [" + r.note + "]") if r.note else ""
            print("%-36s -> %-24s %dx%d  %8.1f KB%s" % (name, r.dst.name, r.width, r.height, r.kb, note))
        if results:
            total = sum(r.size for r in results)
            print("\n%d sticker(s) written to %s, %.1f KB total" % (len(results), out_dir, total / 1024))
    if failures:
        print("%d file(s) failed" % len(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
