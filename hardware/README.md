# hardware

Enclosure and mount for the 13.3" panel. Nothing modelled yet — these are the
numbers to design against.

## Panel — Good Display GDEM133T91

| | mm |
| --- | --- |
| Outline | 286.32 × 212.26 × 1.20 |
| Active area | 275.52 × 195.16 |
| Pixel pitch | 0.287 × 0.287 (~88 dpi) |
| Weight | ~0.32 kg (module as shipped) |

The glass is thin and unsupported — 1.2 mm — so the design needs a full backing
plate, not just an edge bezel. Leave the FPC tail an unstressed exit path;
repeated flexing at the glass boundary is the usual way these panels die.

Bezel overlap: the outline is 5.4 mm wider and 8.6 mm taller than the active
area, so a bezel needs at least ~5 mm of overlap per side to hide the border,
and the tail side needs more.

## Board — Good Display ESP32-L(C02)

70 × 54 mm, ESP32-WROOM-32D, USB-C. Needs a cutout or side access for the
connector, since the frame is mains-powered and the cable stays attached.

## Open questions

- Portrait or landscape mount? It changes the enclosure and the dashboard
  layout, and must match `frame.orientation` in the server's `config.yaml`.
- Magnetic, cleat, or standoff mounting?
- Front glazing, or bare panel? E-ink has no backlight, so glazing costs
  contrast and adds reflections.

## To confirm before cutting

The dimensions above come from the vendor listing. Measure the physical part
and check the datasheet in `docs/` before committing a bezel — particularly the
FPC tail position and length, which the listing does not specify.
