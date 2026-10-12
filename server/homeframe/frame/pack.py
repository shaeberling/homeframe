"""Greyscale -> 1bpp packing in the panel's native bit order.

MSB is the leftmost pixel, 1 is white, rows are width/8 bytes with no padding.
This is exactly what SSD1677 RAM expects, so the ESP32 streams it through
without decoding or a second buffer.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image

PANEL_WIDTH = 960
PANEL_HEIGHT = 680
FRAME_BYTES = PANEL_WIDTH // 8 * PANEL_HEIGHT


@dataclass
class Packed:
    frame: bytes  # what the device fetches
    png: bytes  # the same two-tone image, for previews
    etag: str


def pack_image(image: Image.Image, threshold: int, dither: bool) -> Packed:
    """Pack an image that is already in the panel's native orientation and size."""
    if image.size != (PANEL_WIDTH, PANEL_HEIGHT):
        raise ValueError(f"image is {image.width}x{image.height}, panel needs {PANEL_WIDTH}x{PANEL_HEIGHT}")
    grey = image.convert("L")
    mono = _diffuse(grey, threshold) if dither else grey.point(lambda v: 255 if v >= threshold else 0, mode="1")

    # Mode "1" is stored the way the panel wants it: MSB first, set bit = white.
    frame = mono.tobytes()
    if len(frame) != FRAME_BYTES:
        raise ValueError(f"packed {len(frame)} bytes, expected {FRAME_BYTES}")

    # The preview is the binarized result, not the smooth image that preceded it.
    png = io.BytesIO()
    mono.save(png, format="PNG")
    return Packed(
        frame=frame,
        png=png.getvalue(),
        # Content-addressed, so an unchanged frame costs the device a 304 and
        # the panel stays untouched.
        etag=f'"{hashlib.sha1(frame).hexdigest()}"',
    )


def _diffuse(grey: Image.Image, threshold: int) -> Image.Image:
    """Floyd-Steinberg error diffusion around the given threshold."""
    width, height = grey.size
    # Ints, so accumulated error can leave 0-255; truncated like the Int16Array
    # of the original implementation, so stills keep packing to the same pixels.
    src = list(grey.tobytes())
    out = bytearray(width * height)
    for y in range(height):
        row = y * width
        below = y + 1 < height
        for x in range(width):
            i = row + x
            value = src[i]
            white = value >= threshold
            if white:
                out[i] = 255
            err = value - (255 if white else 0)
            if not err:
                continue
            # Clipped at the edges.
            if x + 1 < width:
                src[i + 1] = int(src[i + 1] + err * 7 / 16)
            if below:
                if x > 0:
                    src[i + width - 1] = int(src[i + width - 1] + err * 3 / 16)
                src[i + width] = int(src[i + width] + err * 5 / 16)
                if x + 1 < width:
                    src[i + width + 1] = int(src[i + width + 1] + err / 16)
    return Image.frombytes("L", (width, height), bytes(out)).convert("1", dither=Image.Dither.NONE)
