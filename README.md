# homeframe

A 13.3" e-paper home dashboard. An ESP32 mounted behind an A4-sized e-ink panel
shows the day at a glance — clock, weather, calendar, notes — and updates
quietly in place.

```
homeframe/
├── firmware/   ESP32 firmware (PlatformIO + Arduino + GxEPD2)
├── server/     Renders the dashboard to a 1bpp frame (Node + Puppeteer)
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

The dashboard is rendered as HTML on a server on your network, converted to a
packed 1-bit image, and fetched by the ESP32, which streams it straight into
the panel's controller RAM.

```
 ┌───────────── server (any always-on box) ─────────────┐
 │  data sources → dashboard.html → headless Chrome     │
 │  → PNG → greyscale → 1bpp pack → /frame.bin + ETag   │
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
npm install && npx puppeteer browsers install chrome
npm start
open http://localhost:8080/preview.png   # exactly what the panel will show

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

Weather is live from Open-Meteo. The agenda and notes panels are still
placeholders — see `server/src/data.js`.

Long-run behaviour is unproven: ghosting over days of partial refreshes, and
whether the frame-transfer time drifts, both still need watching.

## Reference

- [GDEM133T91 product page](https://www.good-display.com/product/480.html) ·
  [ESP32-L driver board](https://www.good-display.com/product/338.html)
- [GxEPD2](https://github.com/ZinggJM/GxEPD2) — panel driver
  (`GxEPD2_1330_GDEM133T91`) and the source of the pinout above
