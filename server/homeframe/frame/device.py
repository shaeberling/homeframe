"""Last-known health of the panel, as reported by the device itself.

The frame renders here, not on the ESP32, so anything it should say about the
device has to arrive as request headers on /frame.bin. The device reports just
before we render, so the status bar shows current values rather than the
previous poll's.
"""

from __future__ import annotations

import math
import time

_last: dict | None = None


def _number(headers, name: str) -> float | None:
    try:
        value = float(headers[name])
    except (KeyError, ValueError):
        return None
    return value if math.isfinite(value) else None


def record_telemetry(headers) -> None:
    global _last
    rssi = _number(headers, "X-Homeframe-Rssi")
    heap_free = _number(headers, "X-Homeframe-Heap")
    # A browser hitting /frame.bin sends none of these; don't let it wipe the
    # real device's status.
    if rssi is None and heap_free is None:
        return
    _last = {
        "rssi": rssi,
        "heapFree": heap_free,
        "socTemp": _number(headers, "X-Homeframe-Temp"),
        # Rounded to whole minutes: the frame's ETag is a hash of its pixels, so
        # a value that ticks every second would defeat the 304 path entirely.
        "uptimeMin": int((_number(headers, "X-Homeframe-Uptime") or 0) // 60),
        # Zero means the device has not completed a transfer yet (first poll
        # after boot), which is absence rather than a measurement of zero.
        "transferMs": _number(headers, "X-Homeframe-Transfer") or None,
        "version": headers.get("X-Homeframe-Version"),
        "at": time.time(),
    }


def signal_bars(rssi: float | None) -> int:
    """Standard four-level mapping: -55 and better is a strong link, below -85 is effectively unusable."""
    if rssi is None:
        return 0
    return sum(rssi >= level for level in (-85, -75, -65, -55))


def device_status() -> dict | None:
    if not _last:
        return None
    return {**_last, "bars": signal_bars(_last["rssi"])}
