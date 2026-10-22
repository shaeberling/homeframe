# homeframe server

One core on top of one or more Home Assistant instances, shown two ways:

- **The web dashboard** — a dark, live, at-a-glance view of every house:
  weather, people, temperature gauges with history, lights, doors and motion,
  power, batteries, and an **Attention** column.
- **The frame** — a dense page for the e-paper panel, rendered in headless
  Chromium, thresholded to pure black and white, and packed into the
  81600-byte frame the panel expects.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m homeframe --demo     # synthetic data, no Home Assistant needed
```

Then open http://localhost:8080 for the web dashboard and
http://localhost:8080/preview.png for what the panel will show.

Rendering needs a Chromium. A system one (`chromium`, `chromium-browser`,
`google-chrome`) is used when there is one; otherwise run
`.venv/bin/playwright install chromium` once. On a headless Linux host, install
fonts (`fonts-dejavu`, or Inter) or the frame renders in a fallback face.

To use your own instances:

```sh
cp config.example.yaml config.yaml    # add URLs + long-lived access tokens
.venv/bin/python -m homeframe
```

`config.yaml` is git-ignored. Tokens stay in the Python process; browsers and
the frame only ever talk to this server.

| Route | Purpose |
| --- | --- |
| `/` | The web dashboard. |
| `/preview.png` | The exact two-tone image the panel will show. Use this while designing. |
| `/frame` | The frame's live HTML, in your browser. Edit `web/frame/index.html` and reload — no restart needed. |
| `/frame.bin` | What the device fetches: 81600 raw bytes, `ETag` + `304`. |
| `/api/frame` | The JSON the frame renders from. |
| `/api/dashboard`, `/api/history`, `/api/events` | The JSON behind the web dashboard. |
| `/api/stream` | Server-sent events: a `change` whenever a door or motion sensor changes, and the server's `version`. |
| `/healthz` | Liveness. |

Append `?fresh=1` to `/preview.png` or `/frame.bin` to bypass the render cache.

## Configuration

See `config.example.yaml` for every option. In short:

- `server` — bind address and port, and how often Home Assistant is polled.
  The default binds `0.0.0.0:8080` so the frame can reach it, which also puts
  the (read-only, unauthenticated) web dashboard on your LAN.
- `instances` — name, URL and token for each Home Assistant. Each instance
  with a `weather.*` entity gets a forecast; set `weather:` to pick a specific
  entity or `false` to hide it. A `batteries:` list limits battery monitoring
  to those sensors, and an `activity:` list names the door and motion sensors
  to show.
- `lights` (per instance) — a Lights module beside the temperature gauges: a
  box per light with its state, colour and when it last switched, by floor and
  room as Home Assistant has them. Every `light.*` entity is shown, minus an
  `exclude` list, plus an `include` list for lamps that are really switches.
- `power` (per instance) — a Power module under the batteries: the house's
  power draw now, energy used today, and a row per circuit with its share,
  from an energy monitor's sensors.
- `panels` — which temperature sensors to show, grouped as you like. An
  instance without a panel shows all of its temperature sensors.
- `attention` — thresholds for what needs a look, plus `watch` / `ignore`
  glob patterns.
- `screen` — the monitor of a wall screen on this computer: in standby while
  a Home Assistant entity is off, switched with `wlopm`.
- `people`, `places` — whose location to show next to the weather, and the
  known places to name it by.
- `frame` — which house the frame hangs in, orientation, threshold, dithering,
  locale and clock, and the token guarding `/frame.bin`.
- `services` — where the frame's calendar and to-do list come from.

Restart the server after editing the config.

## What the frame shows

Everything at once, on one screen. Family content gets the large type; the
house is a compact strip; problems only take space when there are any.

| Area | Source |
| --- | --- |
| Clock, date | The server's clock, in the home instance's time zone. |
| Weather | The `weather.*` entity of the house the frame hangs in (`frame.home`). |
| Coming up | Calendar events whose title starts with ⭐, soonest first. |
| To do | Open items of Home Assistant to-do lists. |
| House strip | The home instance's panel temperatures (up to twelve; a low reading is inverted, a heating thermostat shows its target) and, of its `activity:` sensors, the doors that are open. |
| Black band | The attention items of **every** house. Absent when all is well. |
| Bottom line | One summary per other house (temperature range, open doors, items to check), then the device's own WiFi, memory and uptime. |

When the lower bands grow, the columns above shrink and drop whole rows — the
forecast strip first, then to-dos, then later events — rather than clipping.

### Calendar and to-dos

Both are read through Home Assistant, so the server holds no Google
credentials:

1. In Home Assistant, add the **Google Calendar** integration (Settings →
   Devices & services → Add integration). Each calendar becomes a
   `calendar.*` entity.
2. Start an event's title with ⭐ to put it on the frame. The star is stripped
   before display; everything unstarred stays private to the calendar.
3. To-do lists (the built-in *Local to-do*, Google Tasks, Todoist, …) are
   `todo.*` entities and need no marker.

By default every `calendar.*` and `todo.*` entity of the frame's home instance
is read; `services.calendar.entities` and `services.todo.entities` narrow that
down. `homeframe/services.py` is the seam: the two fetch functions there are
all the rest of the server knows about either source.

## The web dashboard

The layout is sized to fit one screen: on a 4K display at native resolution it
is the 1920px layout magnified 2×. Every gauge carries a sparkline of the range
picked in the top bar (6H / 24H / 7D); the **Charts** button next to it adds
one large history chart per panel, with a line per sensor.

Next to the weather, the dashboard says where each person in `people` is: at
home, in another Home Assistant zone, within the radius of one of the
`places`, or else by street and town, with how long ago the position was
reported. Street and town come from the phone itself, through the companion
app's "Geocoded location" sensor, so no coordinates are sent anywhere to be
looked up; without that sensor the distance from home is shown instead.

Doors and motion show up as they happen. The server keeps a WebSocket open to
each Home Assistant, which pushes every state change, and tells open browsers
over `/api/stream` (server-sent events) the moment a door or motion sensor
changes. Polling (`server.poll_interval`, and the browser's own five-second
refresh) stays as the fallback when either connection drops.

Open dashboards reload themselves when the server restarts (after a config or
code change) or a file under `web/dashboard/` is saved: the stream sends a
`version` on connecting and again when it changes.

Click a gauge to open that sensor's history as a large chart (24H / 7D / 30D;
`←` / `→` switch, `Esc` closes). Ranges up to ten days come from Home
Assistant's history; 30D uses its long-term statistics (hourly averages).
Click a door or motion sensor to list its recent events.

Keyboard: `?` help, `F` fullscreen, `H` history charts, `1`–`4` or `←` / `→`
history range, `R` refresh now.

### What raises attention

The same rules feed the Attention column and the frame's black band.

| Condition | Severity |
|---|---|
| Instance unreachable or token rejected | critical |
| Shown sensor, door/motion sensor, watched battery sensor or `watch`ed entity is `unavailable` | critical |
| Temperature below `temperature_critical` | critical |
| Temperature below `temperature_low` | warning |
| Battery at or below `battery_low` | warning |

Entities that belong to the same Home Assistant device count as one: a dead
sensor raises a single "offline" entry, and its battery is listed under the
name the device has elsewhere on the dashboard.

If updates stop arriving, the last values stay on screen, so the dashboard
warns about that separately: after `server.stale_after` minutes without an
answer from an instance, its chip in the top bar and a banner pulse red. On
the frame, the house is marked "not answering".

## Still images

Drop a PNG into `server/images/` and it is immediately available to the panel:

| File | Device endpoint | Preview |
| --- | --- | --- |
| `server/images/chalk.png` | `/chalk.bin` | `/chalk.png` |

`GET /images` lists what is there. The source must be 960x680, or 680x960 for
a portrait mount (it gets rotated into the panel's native scanline order).

Both endpoints accept per-request overrides, so a texture can be tuned without
touching how the frame renders:

```
/chalk.png?dither=1              # error diffusion, for anything photographic
/chalk.png?dither=1&threshold=140
```

Use `?dither=1` for photographs, textures and anything with tonal range —
a hard threshold collapses a gradient into two flat regions. Leave it off for
text and line art, where dithering just makes edges fuzzy.

To put a still on the real panel, point the firmware at it: set
`HF_FRAME_PATH` in `firmware/include/secrets.h` to `/chalk.bin` and reflash.
It is a compile-time constant, so switching back to the frame means another
flash.

## Designing for 1 bit

The panel has no greys. Everything above the threshold is paper, everything
below is ink, and there is nothing in between.

- Pure `#000` on `#fff`. Mid-tones become threshold noise, not shading.
- Body text 18px and up, weight 600+. Antialiasing eats thin strokes.
- Borders 2–3px. A 1px hairline may vanish entirely.
- No shadows, gradients, or opacity. They threshold into hard-edged blobs.
- Convey hierarchy with size, weight and rules — not colour or tone. A
  problem is inverted (white on black); an absence is a dashed border.

Check every change against `/preview.png`, not `/frame`. The browser view
lies to you: it has antialiasing and greys the panel does not.

`web/frame/index.html` is laid out for landscape. Setting `frame.orientation`
to portrait rotates correctly but the layout needs reworking for the taller
shape.

## Running it for real

Any always-on box on the LAN works: a Pi, a NAS, whatever runs Home Assistant.
Plain HTTP is deliberate — it keeps ~40KB of TLS buffers free on a no-PSRAM
ESP32, and the traffic never leaves your network. Set `frame.token` if you
want `/frame.bin` authenticated.

`deploy/homeframe.service` is a systemd user service. It expects the
repository in `~/source/homeframe` and needs no root, apart from enabling
lingering once so it starts at boot:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/homeframe.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now homeframe
sudo loginctl enable-linger $USER
```

```sh
systemctl --user restart homeframe         # after changing config.yaml or the code
journalctl --user-unit homeframe -f        # follow the log
```

The server binds the IPv4 wildcard on purpose. On a dual-stack socket the
ESP32's IPv4 SYNs once went unanswered — the device saw a 20-second connect
timeout while `curl` from the host itself still worked. Binding IPv4
explicitly avoids the whole question.

## Layout

```
homeframe/app.py           entry point, HTTP routes
homeframe/config.py        config.yaml loading + validation
homeframe/ha.py            Home Assistant REST + WebSocket client
homeframe/hub.py           polling + push updates, state cache, history
homeframe/dashboard.py     panels, doors and motion, batteries, attention rules
homeframe/weather.py       weather entity selection + forecast shaping
homeframe/people.py        where people are: zones, known places, addresses
homeframe/lights.py        lights by floor and room
homeframe/power.py         power draw: the mains and its circuits
homeframe/screen.py        the wall screen's monitor, switched by an entity
homeframe/services.py      starred calendar events, to-do items
homeframe/demo.py          synthetic instances for --demo
homeframe/frame/view.py    what the frame shows, from the same state
homeframe/frame/render.py  headless Chromium render, cache
homeframe/frame/pack.py    greyscale → 1bpp in the panel's bit order
homeframe/frame/still.py   static images for the panel
homeframe/frame/device.py  telemetry the device reports with each fetch
web/dashboard/             the web dashboard (plain HTML/CSS/JS, no build step)
web/frame/                 the frame page
tests/                     pytest
```
