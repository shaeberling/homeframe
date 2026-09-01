# homeframe server

Renders `views/dashboard.html` in headless Chrome, thresholds it to pure black
and white, and packs it into the 81600-byte frame the panel expects.

```bash
npm install
npx puppeteer browsers install chrome   # npm >=11 blocks the postinstall that
                                        # would normally do this
npm start
```

| Route | Purpose |
| --- | --- |
| `/preview.png` | The exact two-tone image the panel will show. Use this while designing. |
| `/dashboard` | The live HTML, in your browser. Edit and reload — no restart needed. |
| `/frame.bin` | What the device fetches: 81600 raw bytes, `ETag` + `304`. |
| `/api/data` | The JSON the page renders from. |
| `/healthz` | Liveness. |

Append `?fresh=1` to `/preview.png` or `/frame.bin` to bypass the render cache.

## Configuration

All optional, all environment variables:

| Variable | Default | Notes |
| --- | --- | --- |
| `HF_PORT` | `8080` | |
| `HF_ORIENTATION` | `landscape` | `portrait` renders 680×960 and rotates into the panel's native scanline order. Must match how the frame is hung. |
| `HF_THRESHOLD` | `160` | Greyscale cutoff, 0–255. Lower = more black. |
| `HF_DITHER` | off | `1` enables Floyd–Steinberg. Turn on only for photos; it makes text fuzzy. |
| `HF_RENDER_TTL_MS` | `30000` | Cache window. Concurrent requests share one render. |
| `HF_TOKEN` | none | Must match `HF_SERVER_TOKEN` in the firmware. Guards `/frame.bin` only. |
| `HF_TZ` | `America/Los_Angeles` | IANA zone, used for the clock and the forecast. |
| `HF_LOCALE` | `en-US` | |
| `HF_LAT` / `HF_LON` | `37.7749` / `-122.4194` | Forecast location. |
| `HF_LOCATION` | `San Francisco` | Label shown beside the Weather heading. |
| `HF_UNITS` | `metric` | Or `imperial`. Metric implies Celsius and a 24-hour clock; imperial implies Fahrenheit and a 12-hour one. |
| `HF_HOST` | `0.0.0.0` | Bind address. The IPv4 wildcard is deliberate — see below. |
| `HF_CHROME_PATH` | none | Pin a specific browser binary. |

## Still images

Drop a PNG into `server/images/` and it is immediately available to the panel:

| File | Device endpoint | Preview |
| --- | --- | --- |
| `server/images/chalk.png` | `/chalk.bin` | `/chalk.png` |

`GET /images` lists what is there. The source must be 960x680, or 680x960 for
a portrait mount (it gets rotated into the panel's native scanline order).

Both endpoints accept per-request overrides, so a texture can be tuned without
touching how the dashboard renders:

```
/chalk.png?dither=1              # error diffusion, for anything photographic
/chalk.png?dither=1&threshold=140
```

Use `?dither=1` for photographs, textures and anything with tonal range —
a hard threshold collapses a gradient into two flat regions. Leave it off for
text and line art, where dithering just makes edges fuzzy.

`images/testramp.png` is a gradient-and-steps calibration target for comparing
the two.

To put a still on the real panel, point the firmware at it: set
`HF_FRAME_PATH` in `firmware/include/secrets.h` to `/chalk.bin` and reflash.
It is a compile-time constant, so switching back to the dashboard means
another flash.

## Designing for 1 bit

The panel has no greys. Everything above the threshold is paper, everything
below is ink, and there is nothing in between.

- Pure `#000` on `#fff`. Mid-tones become threshold noise, not shading.
- Body text 18px and up, weight 600+. Antialiasing eats thin strokes.
- Borders 2–3px. A 1px hairline may vanish entirely.
- No shadows, gradients, or opacity. They threshold into hard-edged blobs.
- Convey hierarchy with size, weight and rules — not colour or tone.

Check every change against `/preview.png`, not `/dashboard`. The browser view
lies to you: it has antialiasing and greys the panel does not.

`views/dashboard.html` is laid out for landscape. Switching `HF_ORIENTATION` to
portrait rotates correctly but the layout needs reworking for the taller shape.

## Wiring real data

`src/data.js` holds one function per panel. `weather()` is live against
Open-Meteo (no API key, cached 10 minutes); `agenda()` and `notes()` still
return placeholders — Home Assistant's REST API covers calendars and to-do
lists.

`collect()` settles each source independently, so one dead upstream blanks its
own panel rather than the whole frame.

## Running it for real

Any always-on box on the LAN works: a Pi, a NAS, whatever runs Home Assistant.
Plain HTTP is deliberate — it keeps ~40KB of TLS buffers free on a no-PSRAM
ESP32, and the traffic never leaves your network. Use `HF_TOKEN` if you want
the endpoint authenticated.

On a headless Linux host, install fonts (`fonts-dejavu`, or Inter) or the
dashboard will render in a fallback face.

The server binds `0.0.0.0` rather than Node's default IPv6 wildcard. On the
dual-stack socket Node opens by default, the ESP32's IPv4 SYNs went unanswered
— the device saw a 20-second connect timeout while `curl` from the host itself
still worked, because macOS routes a host's own IP over loopback. Binding IPv4
explicitly avoids the whole question.
