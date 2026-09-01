# First bring-up

The firmware compiles but has never driven the physical panel. Work through
this in order; each step isolates one class of failure.

## 1. Board talks to the host

Connect USB-C. The board uses a **CH340** serial chip — macOS has a driver
built in, but if no port appears, install WCH's.

```bash
ls /dev/cu.*                      # expect /dev/cu.wchusbserial* or usbserial
pio device list
```

Nothing there means driver or cable (many USB-C cables are power-only).

## 2. Flash and watch the log

```bash
cd firmware
cp include/secrets.h.example include/secrets.h   # WiFi + server URL first
pio run --target upload
pio device monitor
```

Expect: `homeframe 0.1.0 starting`, then the splash screen, then a WiFi line
with an IP.

## 3. Panel

The splash is the real test — it exercises init, the paged buffer and a full
refresh.

- **Nothing at all, no hang:** check the FPC is seated in the DESPI-C02 and
  latched. This is by far the most common failure.
- **Hangs at boot:** BUSY is stuck. The panel holds BUSY high while refreshing;
  if it never releases, the panel is not powered or not connected.
- **Garbage or a shifted image:** wrong panel class. Confirm the part is
  GDEM133T91 and not a same-size variant with a different controller.
- **Very faint image:** normal on a first refresh after long storage. Run a few
  full refreshes.

## 4. Server

With the server running on the same network:

```bash
curl -sI http://<server>:8080/frame.bin    # expect 200 and 81600 bytes
```

The device polls every 60 s. Watch the serial log — `frame:` lines carry the
error text, which is also what the fallback screen displays.

## 5. Fallback path

Stop the server. After three failed polls (~3 minutes) the panel should switch
to the on-device clock and status screen. Restart the server and it should
switch back on the next poll.

This is worth testing deliberately — it is the one path that only runs when
something is already broken.

## Timing to sanity-check

| | expected |
| --- | --- |
| Full refresh | ~4 s, panel flashes |
| Partial refresh | ~0.4–0.6 s, no flash |
| Frame download | 81600 bytes over LAN, well under a second |

If partial refreshes leave ghosts, lower `HF_FULL_REFRESH_EVERY` in
`firmware/include/config.h`.
