"""wechat-sticker-kit - turn PNG/JPG images and videos into WeChat-ready stickers."""

from .core import (
    ANCHORS,
    BUDGETS,
    INPUT_SUFFIXES,
    OUTPUT_FORMATS,
    Result,
    StickerError,
    convert_file,
    encode,
    load_image,
    to_square,
)
from .video import (
    VIDEO_SUFFIXES,
    assemble_gif,
    extract_frames,
    ffmpeg_path,
    frames_to_sticker,
    probe_duration,
    video_to_gif,
)

__version__ = "0.4.0"

__all__ = [
    "ANCHORS",
    "BUDGETS",
    "INPUT_SUFFIXES",
    "OUTPUT_FORMATS",
    "Result",
    "StickerError",
    "VIDEO_SUFFIXES",
    "assemble_gif",
    "convert_file",
    "encode",
    "extract_frames",
    "ffmpeg_path",
    "frames_to_sticker",
    "load_image",
    "probe_duration",
    "to_square",
    "video_to_gif",
    "__version__",
]
