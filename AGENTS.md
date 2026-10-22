# Working on homeframe

Notes for coding agents (and people) changing this repository. What the
project is: [README.md](README.md). Setting it up: [docs/setup.md](docs/setup.md).
Server internals and routes: [server/README.md](server/README.md).

## Privacy: nothing personal in the repository

The repository is public. Everything that identifies the owner's homes lives
only in `server/config.yaml`, which is git-ignored: house names, Home
Assistant URLs and tokens, entity ids, device and room names, people, place
names and coordinates, time zones.

- Code, tests, comments, docs and commit messages use generic examples
  (`home`, `cabin`, `person.alex`, `sensor.living_room_temperature`).
- Before every commit, read the staged diff (`git diff --cached`) with this in
  mind, not only the files you meant to change.
- Never commit `server/config.yaml`, `firmware/include/secrets.h`, or
  screenshots of the live dashboard. Screenshots from `--demo` are fine.

## Layout

- `server/` — Python 3.11+, FastAPI. One process: Home Assistant client
  (`ha.py`), state and push updates (`hub.py`), the dashboard's data
  (`dashboard.py`, `weather.py`, `people.py`, `lights.py`, `power.py`,
  `services.py`),
  the e-paper frame (`frame/`), config parsing (`config.py`), synthetic data
  (`demo.py`).
- `server/web/dashboard/` — the web dashboard: plain HTML, CSS and JS
  modules, no build step, no framework. Static files are served as they are on
  disk; open dashboards reload themselves when one is saved, and after a
  server restart (`/api/stream` sends a `version` event).
- `server/web/frame/` — the 960×680 page rendered for the e-paper panel.
- `firmware/` — ESP32 (PlatformIO). Its protocol with the server
  (`/frame.bin`, `ETag`, `X-Homeframe-*` headers) is fixed; don't change one
  side alone.

## Running and checking

```sh
cd server
.venv/bin/python -m pytest -q tests              # unit tests
.venv/bin/python -c "import homeframe.app"       # import check before a restart
.venv/bin/python -m homeframe --demo --port 8091 # synthetic data, no Home Assistant
```

- Config changes: every option is documented in `config.example.yaml` —
  add new ones there, with a comment, and parse them in `config.py`. Keep
  `demo.py` able to show new features.
- Dashboard changes: load the page in a headless Chromium (Playwright is
  installed in the venv) and check for page errors. A JS syntax error blanks
  the whole dashboard.
- **The dashboard must fit one 1920×1080 screen without scrolling**
  (`document.documentElement.scrollHeight === 1080` at that viewport). 4K is
  the same layout zoomed 2×; at 1040 px and below it stacks for phones.
- Frame changes: judge them on `/preview.png` (the real 1-bit output), not
  `/frame` in a browser.
- On a deployed box the server runs as the systemd user unit `homeframe`
  (`deploy/homeframe.service`); `systemctl --user restart homeframe` after
  Python or config changes.

## Conventions

- Match the surrounding code: small functions, few comments that explain why,
  no new dependencies without a good reason.
- Dashboard JS builds DOM with the `h()` / `s()` helpers and re-renders a
  section only when its data signature changes. Colours are CSS custom
  properties on `:root`.
- Home Assistant is only read, never written to.
- Commit messages: `area: what changed`, lower case (`dashboard: …`,
  `server: …`, `docs: …`), with a body that says why.
