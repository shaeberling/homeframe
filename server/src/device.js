// Last-known health of the panel, as reported by the device itself.
//
// The dashboard renders here, not on the ESP32, so anything the frame should
// say about the device has to arrive as request headers on /frame.bin. The
// device reports just before we render, so the status bar shows current values
// rather than the previous poll's.

let last = null;

function number(req, header) {
  const raw = req.get(header);
  if (raw === undefined) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function recordTelemetry(req) {
  const t = {
    rssi: number(req, 'X-Homeframe-Rssi'),
    heapFree: number(req, 'X-Homeframe-Heap'),
    socTemp: number(req, 'X-Homeframe-Temp'),
    // Rounded to whole minutes: the frame's ETag is a hash of its pixels, so a
    // value that ticks every second would defeat the 304 path entirely.
    uptimeMin: Math.floor((number(req, 'X-Homeframe-Uptime') ?? 0) / 60),
    transferMs: number(req, 'X-Homeframe-Transfer'),
    version: req.get('X-Homeframe-Version') ?? null,
    at: Date.now(),
  };

  // Zero means the device has not completed a transfer yet (first poll after
  // boot), which is absence rather than a measurement of zero.
  if (t.transferMs === 0) t.transferMs = null;

  // A browser hitting /frame.bin sends none of these; don't let it wipe the
  // real device's status.
  if (t.rssi === null && t.heapFree === null) return;
  last = t;
}

// Standard four-level mapping. -55 and better is a strong link; below -85 is
// effectively unusable.
export function signalBars(rssi) {
  if (rssi === null || rssi === undefined) return 0;
  if (rssi >= -55) return 4;
  if (rssi >= -65) return 3;
  if (rssi >= -75) return 2;
  if (rssi >= -85) return 1;
  return 0;
}

export function deviceStatus() {
  if (!last) return null;
  return { ...last, bars: signalBars(last.rssi) };
}
