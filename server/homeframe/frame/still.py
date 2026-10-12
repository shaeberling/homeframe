"""Static images packed for the panel.

Anything dropped into server/images as a PNG becomes available at /<name>.bin,
ready for the device, and /<name>.png as a preview of what the panel will
actually show. Meant for experiments (textures, photographs, hand-drawn
layouts) without disturbing the frame pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from .pack import PANEL_HEIGHT, PANEL_WIDTH, Packed, pack_image

IMAGE_DIR = Path(__file__).resolve().parents[2] / "images"

# Keyed by name + file mtime + render options, so editing the PNG or changing
# the dithering invalidates automatically.
_cache: dict[tuple, Packed] = {}


class StillError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def pack_still(name: str, threshold: int, dither: bool) -> Packed:
    # Defend the obvious traversal: only bare names, resolved inside IMAGE_DIR.
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise StillError(400, "bad image name")
    file = IMAGE_DIR / f"{name}.png"
    try:
        mtime = file.stat().st_mtime_ns
    except OSError:
        raise StillError(404, f"no image at server/images/{name}.png") from None

    key = (name, mtime, threshold, dither)
    if key in _cache:
        return _cache[key]

    with Image.open(file) as image:
        # The panel always wants native-orientation scanlines. Accept an image
        # in either orientation and rotate a portrait one into place.
        if image.size == (PANEL_HEIGHT, PANEL_WIDTH):
            image = image.transpose(Image.Transpose.ROTATE_270)
        elif image.size != (PANEL_WIDTH, PANEL_HEIGHT):
            raise StillError(
                422,
                f"{name}.png is {image.width}x{image.height}, need {PANEL_WIDTH}x{PANEL_HEIGHT} "
                f"(or {PANEL_HEIGHT}x{PANEL_WIDTH} portrait)",
            )
        packed = pack_image(image, threshold, dither)
    _cache[key] = packed
    return packed


def list_images() -> list[str]:
    try:
        return sorted(f.stem for f in IMAGE_DIR.glob("*.png"))
    except OSError:
        return []
