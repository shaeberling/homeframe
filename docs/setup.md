# Setting up homeframe

A walk-through from nothing to a live dashboard of your own houses, and
optionally the e-paper frame. Expect half an hour for the dashboard; the frame
is extra.

## What you need

- **Home Assistant**, one or more instances, each reachable over the network
  from where the server runs.
- **An always-on Linux box** on the same network for the server: a Raspberry
  Pi 4/5, a NAS, or the machine that runs Home Assistant. Python 3.11 or newer.
- **A screen** for the dashboard: any browser. It is laid out for 1920×1080;
  4K gets the same layout magnified, phones get it stacked.
- **Optional:** the e-paper frame (see the main [README](../README.md#the-e-paper-frame)
  for parts), and a Chromium on the server to render it.

## 1. Install the server

```sh
git clone https://github.com/shaeberling/homeframe.git ~/source/homeframe
cd ~/source/homeframe/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Try it with made-up data before touching any config:

```sh
.venv/bin/python -m homeframe --demo
```

Open `http://<server>:8080/`. Everything you see is synthetic: two houses,
gauges, lights, doors, people.

The frame preview (`/preview.png`) needs a Chromium. A system one is used if
installed (`sudo apt install chromium` on Raspberry Pi OS / Debian); otherwise
run `.venv/bin/playwright install chromium` once. Install fonts too
(`fonts-dejavu`) on a headless box. The dashboard itself needs none of this.

## 2. Get a token from each Home Assistant

In Home Assistant: your profile (bottom left) → **Security** → **Long-lived
access tokens** → **Create token**. Copy it right away; it is shown once.

A token can do anything its user can. If you want to limit that, create a
separate Home Assistant user for the dashboard and make the token there. The
server only reads from Home Assistant; it never switches or changes anything.

## 3. Write the config

```sh
cp config.example.yaml config.yaml
chmod 600 config.yaml
```

`config.yaml` is git-ignored: it holds your tokens, and everything that says
where you live — house names, entity ids, people, places. Keep it that way;
nothing personal belongs in the code.

Start minimal: one entry per Home Assistant, nothing else.

```yaml
server:
  port: 8080

instances:
  - id: home                 # short key, used elsewhere in the config
    name: Home               # shown on the dashboard
    url: http://homeassistant.local:8123
    token: "eyJ..."
  - id: cabin
    name: Cabin
    url: https://cabin.example.com
    token: "eyJ..."
    # verify_ssl: false      # only for a self-signed certificate
```

Run it (`.venv/bin/python -m homeframe`) and open the dashboard. With no
panels configured, each house shows every temperature sensor it has, plus its
weather and, when any battery runs low, an attention item. Both houses' chips
in the top bar should say **Live**.

Then refine, one section at a time, restarting after each edit. Every key is
described in `config.example.yaml`; here is what each one is for.

### Temperatures: `panels`

Pick the sensors and their order. Each card can also carry a humidity sensor
and a thermostat; the detail chart (click a gauge) finds a humidity on the
sensor's own device by itself.

```yaml
panels:
  - title: Home
    instance: home
    sensors:
      - entity: sensor.bedroom_temperature
        name: Bedroom
      - entity: sensor.living_room_temperature
        name: Living room
        climate: climate.downstairs     # heating mode and target on the card
      - entity: sensor.garage_temperature
        alerts: false                   # shown, never raises attention
```

### Doors, motion and shades: `activity` (per instance)

Named explicitly, because "is this a door?" is not something Home Assistant
answers reliably. `activity: []` shows an empty panel as a placeholder.

```yaml
instances:
  - id: home
    # ...
    activity:
      - entity: binary_sensor.front_door
        name: Front door
      - entity: binary_sensor.hallway_motion
        name: Hallway
      - cover.garage_door
```

Changes arrive within a second if the integration behind the sensor pushes
them (Zigbee, Matter, Z-Wave, ESPHome). Cloud-polled integrations only report
when they poll, and can miss a door that opens and closes in between.

### Lights: `lights` (per instance)

```yaml
    lights: all                  # every light.* entity
    # or:
    lights:
      exclude: [light.*_indicator]
      include: [switch.floor_lamp]   # a lamp on a smart plug
```

Lights are grouped by Home Assistant's **floors** and **areas**, so assign
those in Home Assistant (Settings → Areas, labels & zones) for a tidy panel.

### Power: `power` (per instance)

What the house draws right now, from an energy monitor in the electrical
panel (an Emporia Vue, a Shelly EM, an IoTaWatt): the mains in large type,
energy used today beside it, and a row per circuit with its share.

```yaml
    power:
      total: sensor.mains_power             # W or kW
      energy: sensor.mains_energy_today     # kWh, optional
      circuits:
        - sensor.heat_pump_power
        - entity: sensor.ev_charger_power
          name: EV charger
          status: sensor.ev_charger_status  # shown under the name, e.g. "Charging"
```

Without `total`, the circuits are added up instead. A cloud-polled monitor
updates about once a minute.

### Batteries: `batteries` (per instance)

Without the key, every battery sensor is watched and a low one raises
attention. `batteries: all` also lists them all in a box, new devices
included. A list of ids or globs limits both to those.

### People and places

```yaml
people:
  - person.alex
  - entity: person.sam
    name: Sam

places:
  - name: Office
    latitude: 52.5200
    longitude: 13.4050
    radius: 150
    people: [alex]          # only counts for Alex
```

A person shows as their Home Assistant zone, else a place from this list,
else street and town, else the distance from home. Street and town need the
**Geocoded location** sensor enabled in the Home Assistant companion app on
their phone.

### Attention

```yaml
attention:
  battery_low: 20
  temperature_low: 16          # orange below this
  temperature_critical: 8      # red below this
  watch: [binary_sensor.*_door]
  ignore: [sensor.freezer_*]
```

Thresholds are in the sensor's own unit. An unheated house wants lower ones.

## 4. Run it as a service

```sh
mkdir -p ~/.config/systemd/user
cp deploy/homeframe.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now homeframe
sudo loginctl enable-linger $USER      # start at boot without a login
```

The unit expects the repository at `~/source/homeframe`; edit its paths if
yours is elsewhere. Afterwards:

```sh
systemctl --user restart homeframe     # after editing config.yaml
journalctl --user-unit homeframe -f    # the log
```

The dashboard has no login. It binds to every interface so the frame can
reach it, which puts it on your LAN; set `server.host: 127.0.0.1` if no frame
needs it and you only view it on the box itself. Don't expose the port to the
internet.

## 5. A wall screen

Any browser in kiosk mode pointed at the server works. On a Raspberry Pi with
a desktop:

```sh
chromium --kiosk --noerrdialogs --disable-infobars http://localhost:8080/
```

Put that in the desktop's autostart to come up after a reboot.

## 6. The e-paper frame (optional)

1. In `config.yaml`, set `frame.home` to the house the frame hangs in, and
   `frame.token` to a random string if you want `/frame.bin` protected.
2. Check `http://<server>:8080/preview.png`: that is exactly what the panel
   will show.
3. For a calendar on the frame, add Home Assistant's **Google Calendar**
   integration and start event titles with ⭐. To-dos come from any `todo.*`
   list. See [server/README.md](../server/README.md#calendar-and-to-dos).
4. Flash the firmware:

   ```sh
   cd firmware
   cp include/secrets.h.example include/secrets.h
   # WiFi credentials, HF_SERVER_BASE = http://<server>:<port>, HF_SERVER_TOKEN = frame.token
   pio run --target upload && pio device monitor
   ```

Hardware bring-up is in [bringup.md](bringup.md).

## When something is off

- **A house shows an error in the top bar**: hover it for the reason. Usually
  a wrong URL, an expired token, or a self-signed certificate
  (`verify_ssl: false`). Slow DNS can also delay the first connection.
- **"Polling" instead of "Live"**: the WebSocket to that Home Assistant is
  down; the dashboard still updates every `poll_interval` seconds and
  reconnects on its own.
- **A sensor or light is missing**: check its entity id in Home Assistant
  (Developer tools → States); disabled entities don't appear.
- **Rooms or floors look wrong**: they come from Home Assistant's areas and
  floors, cached for half an hour; restart the server to pick up changes
  sooner.
- **Try without your config**: `--demo` shows whether a problem is the setup
  or the data.
