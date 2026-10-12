# homeframe

A 13.3" e-paper home dashboard. An ESP32 mounted behind an A4-sized e-ink panel
shows the family's day at a glance — clock, weather, starred calendar events,
to-dos, and how the house is doing — and updates quietly in place.

The same server is also a live web dashboard on top of one or more Home
Assistant instances: temperature gauges, history charts, doors and motion, and
an Attention column for everything that needs a look. One core reads Home
Assistant; the frame and the web dashboard are two views of it.

```
homeframe/
├── firmware/   ESP32 firmware (PlatformIO + Arduino + GxEPD2)
├── server/     Home Assistant core, web dashboard, e-paper renderer (Python)
├── hardware/   Enclosure and mount models
└── docs/       Hardware notes, wiring, datasheets
```

## Hardware

| Part | Detail |
| --- | --- |
| Panel | Good Display **GDEM133T91** — 13.3", 960×680, monochrome |
| Controller | **SSD1677**, 4-wire SPI, 24-pin 0.5 mm FPC, 3.3 V |
| Board | Good Display **ESP32-L(C02)** — ESP32-WROOM-32D, USB-C (CH340), DESPI-C02 adapter |
| Refresh | ~4 s full, ~0.4 s partial |
| Active area | 275.52 × 195.16 mm (0.287 mm pitch, ~88 dpi) |

Wiring is fixed by the ESP32-L board and matches GxEPD2's documented pinout:

| Panel | BUSY | RST | DC | CS | SCK | MOSI |
| --- | --- | --- | --- | --- | --- | --- |
| GPIO | 13 | 12 | 14 | 27 | 18 | 23 |

## How it works

The server polls every Home Assistant instance and keeps their state in memory.
The frame is rendered from that as HTML, converted to a packed 1-bit image, and
fetched by the ESP32, which streams it straight into the panel's controller
RAM. Browsers get the web dashboard from the same process.

```
 ┌───────────── server (any always-on box) ─────────────┐
 │  Home Assistant × N → core (state, attention rules,  │
 │  weather, calendar, to-dos)                          │
 │    ├─ /        web dashboard, live in a browser      │
 │    └─ /frame   → headless Chromium → PNG → greyscale │
 │                → 1bpp pack → /frame.bin + ETag       │
 └──────────────────────┬───────────────────────────────┘
                        │ HTTP, 81600 bytes (or 304)
 ┌──────────────────────▼───────────────────────────────┐
 │  ESP32 → SSD1677 controller RAM → partial refresh    │
 │  no server? → draws its own clock + status screen    │
 └──────────────────────────────────────────────────────┘
```

Why this split: at 960×680 you want real typography and layout, and doing that
in `Adafruit_GFX` drawing calls means recompiling and reflashing for every
tweak. Rendering HTML server-side turns design iteration into a browser reload.

The device is not wholly dependent on the server, though. After
`HF_FALLBACK_AFTER_FAILURES` failed polls it draws its own screen — live clock,
date, and a diagnosis (WiFi state, last error, how long since the last good
frame) — so an outage looks like an outage rather than a frozen panel.

### Bandwidth and refresh

`/frame.bin` is content-addressed with an `ETag`. The device sends
`If-None-Match`, so an unchanged dashboard costs one `304` and the panel is
left alone — no needless refresh, no visible flicker. Partial refreshes are
used by default, with a full refresh every `HF_FULL_REFRESH_EVERY` updates to
clear accumulated ghosting.

## Quick start

```bash
# 1. Server
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m homeframe --demo     # synthetic data, no Home Assistant needed
open http://localhost:8080/preview.png   # exactly what the panel will show
open http://localhost:8080/              # the web dashboard

cp config.example.yaml config.yaml       # then: your Home Assistant URLs + tokens
.venv/bin/python -m homeframe            # the real thing; config.yaml is git-ignored

# 2. Firmware
cd ../firmware
cp include/secrets.h.example include/secrets.h   # fill in WiFi + server URL
pio run --target upload && pio device monitor
```

## Status

Working end to end on hardware. Measured on the real panel:

| | measured | GxEPD2 budget |
| --- | --- | --- |
| Full refresh | 2.97 s | 4.5 s |
| Fast partial refresh | 0.48 s | 0.6 s |
| Frame transfer (81600 B over WiFi) | 2.7-10 s | - |

Everything on the frame is live from Home Assistant: weather, temperatures,
doors and motion, attention items, starred calendar events and to-do lists —
see [server/README.md](server/README.md).

Long-run behaviour is unproven: ghosting over days of partial refreshes, and
whether the frame-transfer time drifts, both still need watching.

## Reference

- [GDEM133T91 product page](https://www.good-display.com/product/480.html) ·
  [ESP32-L driver board](https://www.good-display.com/product/338.html)
- [GxEPD2](https://github.com/ZinggJM/GxEPD2) — panel driver
  (`GxEPD2_1330_GDEM133T91`) and the source of the pinout above
