"""wechat-sticker-kit - turn PNG/JPG images into WeChat-ready stickers."""

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

__version__ = "0.1.0"

__all__ = [
    "ANCHORS",
    "BUDGETS",
    "INPUT_SUFFIXES",
    "OUTPUT_FORMATS",
    "Result",
    "StickerError",
    "convert_file",
    "encode",
    "load_image",
    "to_square",
    "__version__",
]
