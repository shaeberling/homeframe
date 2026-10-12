# chalk — hand-written chalkboard text for the panel

Standalone experiment, nothing here touches `server/`. It turns a string into
pen strokes that look hand-written (different on every run), draws them with a
physically motivated chalk model, and shows what the 1-bit panel would make of
it.

```bash
cd experiments/chalk
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python main.py                    # random seed, printed so you can reproduce it
.venv/bin/python main.py --seed 7
.venv/bin/python main.py --sheet 6          # six seeds of one phrase, to see the variation
.venv/bin/python main.py --text "Milk, eggs & bread" --x-height 64 --size 960x300
.venv/bin/python main.py --fit --text "Milk, eggs\n& bread" --width 12   # fill the panel, 5% border, centred
.venv/bin/python main.py --mess 2 --sheet 6 # how erratic the writer is: 0.5 neat, 1 normal, 2 scrawl
.venv/bin/python main.py --help             # every Chalk parameter is a flag
```

Outputs in `out/`:

| File | What |
| --- | --- |
| `chalk.png` | The render: chalk on a dark board with faint erasing haze. |
| `panel_threshold.png` | 1-bit as the server binarises today (`HF_THRESHOLD=160`). |
| `panel_dither.png` | 1-bit with Floyd–Steinberg (`HF_DITHER=1`). Keeps the dust and soft rims. |
| `strokes.png` | Centrelines coloured by pressure (blue light → red heavy), green dot per pen-down. |
| `sheet.png` | Contact sheet from `--sheet N`. |

## How it works

Four files, three stages. `noise.py` is value-noise helpers; `svgfont.py`
loads single-line SVG fonts.

### `handwriting.py` — text → pen strokes

An outline font only says where the ink is. A chalk model needs to know how
the hand moved, so letterforms come from a **Hershey single-line script font**
(`cursive`, or `scripts`): genuine cursive shapes stored as pen centrelines,
with the entry and exit connectors drawn in. On top of that:

- **A "hand" per run** — size, slant, spacing, sloppiness, habitual pressure,
  warp strength, join probability — sampled from the seed, with `--mess`
  scaling the erratic ones. Every run is a different writer.
- **Shape variation per glyph** — each instance gets its own ascender and
  descender lengths and a smooth quadratic warp over its box, so two "a"s are
  different shapes rather than rotated copies. This is what stops it reading
  as a font.
- **Drift, not dice** — size, slant and rotation wander along the line with
  low-frequency noise (a mood) plus a small independent kick per letter; the
  baseline wanders and each line tilts a little. Real irregularity is
  correlated, not white noise. On top of that each letter gets an
  independent position offset (`jitter_x`, `jitter_y`, sigma in x-heights —
  a few percent by default) and its advance is jittered.
- **Cursive joins** — Hershey is drawn so that at nominal spacing one letter's
  exit lands exactly on the next letter: at the stroke start for n/m/i/u-types,
  on the left of the bowl for a/o/d/g-types. The first case is concatenated into
  one movement; in the second both strokes lose their landing/lift-off effects.
  Joins are probabilistic (`join_prob`, lower with more mess): real writers
  lift the pen between some letters.
- **Squiggle** — smooth noise applied normal to the path at two scales. AlMeraj
  et al. found this deviation is what makes a synthetic line read as
  hand-drawn; their generated lines passed for real ones in a user study.
- **Kinematics** — tangential speed from curvature via the two-thirds power law
  (v ∝ κ^-1/3: the hand slows in tight turns), a bell-shaped start where a
  movement really begins (Flash & Hogan minimum jerk), and pressure that
  follows speed.
- **Touchdown and lift-off** — chalk is not planted like a pen. It lands on a
  corner of the tip and settles flat over the first 0.1–0.3 x-heights
  (`touchdown`), and lifts away while still moving over the last 0.2–0.45
  (`liftoff`), so strokes fade in and out thin and sparse rather than
  starting with a blob and stopping in a blunt ribbon. Both are per-hand,
  overridable with `--touchdown` / `--liftoff` (in x-heights). On a closed
  loop the tail runs on over the start, as a writer's does, so the faint
  touchdown is covered.

Each stroke comes out as an `(N, 4)` array of `x, y, pressure, speed` at ~1 px
spacing. `--dump-strokes` writes them as JSON, which is the hand-off point if
the renderer is ever moved into the server.

### `chalk.py` — strokes → coverage

The board is a **height field**: fine grain plus mottling at two coarser
scales, roughly normal around 0.5. Deposition follows Sousa & Buchanan's
observational model of pencil on paper (chalk on slate is the same physics,
inverted): the tip presses down to a level set by local pressure, and every
grain that reaches above that level is coated. High grains get chalk first;
heavier pressure fills the valleys. That one rule gives the solid centres,
the speckled rims, the way a light or fast stroke skips, and the way a second
pass over the same spot fills in what the first missed.

The texture **follows the stroke** because local pressure is evaluated in
stroke coordinates `(s along, t across)`, not screen space. A worn chalk tip
has facets, so pressure across the tip varies with `t` and drifts slowly with
`s`; each facet leaves its own continuous trail — the striations in real chalk
lettering — bending with the letters. Pressure across the tip also falls off
at the rounded rim (Sousa & Buchanan's pressure-distribution coefficients),
fast movement adds dropouts, pigment picked up by a grain is dragged into the
grains that follow it along the movement (a decaying running max down the
`s` axis — this is what makes heavy strokes streaky rather than flat), and a
final pass adds loose dust: a faint halo and stray specks beside the strokes.

`Chalk` parameters (all `--flags`):

| Param | Default | Effect |
| --- | --- | --- |
| `width` | 7 px | Contact width. 7 px ≈ 2 mm on the 88 dpi panel. |
| `edge` | 0.45 | Fraction of the half-width over which the rim fades — rim speckle. |
| `min_width` | 0.25 | Contact width at zero pressure. The patch grows with √pressure, so fading ends narrow as well as lighten. |
| `facet_scale` | 1.3 px | Striation width across the stroke. |
| `facet_drift` | 40 px | How far along a stroke a striation persists. |
| `facet_depth` | 0.4 | Contrast between facets. 0 = flat tip, no streaks. |
| `softness` | 0.15 | Transition from untouched to coated grain. Lower = more binary. |
| `transfer` | 0.92 | Pigment per pass. |
| `skip` | 0.4 | Dropouts when the hand is fast. |
| `drag` | 0.85 | Pigment carried forward along the movement (per ½ px). Turns specks into streaks; 0 = off. |
| `dust` | 0.6 | Halo + stray specks. Shows up as sparse dots after dithering. |

### `main.py` — layout and panel preview

Lays the text out from the font metrics (line height 1.05 × ascent+descent —
the cursive face has tall ascenders, ~3.85 × x-height per line) and writes the
outputs. `--size WxH` is the canvas in px (default the panel's 960x680);
`--x-height` is the lowercase letter height in px. With `--fit` the x-height
is ignored: the text is laid out at unit size, measured, and scaled so the
block fills the canvas inside `--border` (default 5 % of each edge), with each
line centred (`--align left` to keep a ragged left edge). Chalk width does not
scale with the text — pick `--width` to taste (12 px looks right at title size). The panel views are computed from coverage directly: on the panel the
board is black and the chalk white, so the greyscale the server would see *is*
the coverage. Haze is preview-only; through the dither it would become noise
over the whole panel.

## Fonts

`--font` takes a Hershey face name or the file stem of any single-line SVG
font in `fonts/`. `--fonts` renders every text face with the same hand to
`out/fonts.png` for comparison.

**Hershey** (built into the Python package): `cursive` (schoolbook cursive —
reads as a third-grader's), `scripts` (its slightly more adult sibling),
`futural`/`rowmans` (plain single-line print; with the motor model, casual
adult print), `timesi` (slanted serif, doubled by the chalk into quick italic
lettering), `rowmand`/`futuram` (duplex, bold café-sign print), `gothiceng`
(blackletter). The duplex/triplex faces are drawn with two or three parallel
strokes, which chalk turns into a heavy, slightly doubled letter.

**EMS** (`fonts/*.svg`, from Inkscape's Hershey Text extension, SIL Open Font
License, by Sheldon B. Michaels / Evil Mad Scientist): real handwriting
styles drawn as pen centrelines for plotters. `EMSFelix` (casual bold hand),
`EMSNixish` / `EMSNixishItalic` (neat architect print), `EMSReadability` /
`EMSReadabilityItalic` (clean print), `EMSElfin` (small quick scribble),
`EMSAllure` (flowing adult script, from Allura), `EMSOsmotron`, `EMSTech`.
Joins are on by default only for script faces (`cursive`, `scripts`,
`EMSAllure`); `--join` forces them.

To add a face: drop any single-line SVG font into `fonts/`. Inkscape's
extension and the AxiDraw software ship more (EMS Casual Hand, EMS Pancakes,
…), and any font in that format works. An outline TTF does not — it only
tells you where the ink is, not how the pen moved.

## What the panel does to it

Chalk is a good match for a 1-bit display: the texture is already
high-frequency speckle, so binarising costs little. Two options:

- **Threshold (server default, 160)** — keeps only grains ≥ 63 % coverage.
  Strokes come out slightly thinner and more broken, no dust. Crisp.
- **Floyd–Steinberg (`HF_DITHER=1`)** — keeps the rims and dust as sparse dots.
  Closer to the colour render. Worth testing on the real panel: the server
  README warns dithering fuzzes text, but chalk is fuzzy by design.

## Prior work this draws on

Handwriting
- Hershey fonts via [apshu/HersheyFonts](https://github.com/apshu/HersheyFonts) — single-stroke fonts, `cursive`/`scripts` are the script faces.
- AlMeraj, Wyvill, Isenberg, Gooch, Guy, *Mimicking Hand-Drawn Pencil Lines*, CAe 2008 ([pdf](https://webhome.cs.uvic.ca/~blob/publications/cae08.pdf)) — Flash–Hogan arm trajectory + random normal "squiggle" + pencil texture; the human-vs-generated study.
- Lacquaniti, Terzuolo, Viviani 1983 — the [two-thirds power law](https://www.sciencedirect.com/science/article/abs/pii/S0001691898000274) relating speed to curvature in handwriting.
- Plamondon's [sigma-lognormal / kinematic theory](https://pmc.ncbi.nlm.nih.gov/articles/PMC3867641/) — the fuller neuromotor model; velocity profiles as sums of lognormals. Not used here, but the natural upgrade for the ramps.
- Alex Graves, *Generating Sequences with RNNs* (2013) — learned handwriting synthesis. Implementations with pretrained weights: [sjvasquez/handwriting-synthesis](https://github.com/sjvasquez/handwriting-synthesis) (TF1), [nblasgen/handwriting-synthesis-2025](https://github.com/nblasgen/handwriting-synthesis-2025) (TF 2.15), [X-rayLaser/pytorch-handwriting-synthesis-toolkit](https://github.com/X-rayLaser/pytorch-handwriting-synthesis-toolkit) (PyTorch, checkpoints in repo). Produces real-looking print/cursive with a `bias` knob for neatness. Not used: heavy dependency, and the models don't expose pressure — but their `(dx, dy, pen-up)` output could be fed to `chalk.py` as-is if the font-based script ever feels too regular.

Chalk / pencil media
- Sousa & Buchanan, *Observational Models of Graphite Pencil Materials*, CGF 2000 ([pdf](https://ires.cpsc.ucalgary.ca/publ/papers/2000/refs/Costa%20Sousa%20&%20Buchanan%20'00.pdf)) and *Computer-Generated Graphite Pencil Rendering of 3D Polygonal Models*, EG 1999 — paper as a grain height field, pressure distributed over a polygonal tip, lead "bitten" by grains above the pressure-set depth, saturation. The deposition rule in `chalk.py` is a per-pixel simplification of §5.
- Lee, Kwon, Lee, *Real-time pencil rendering*, NPAR 2006 — GPU version of the same idea.
- *Simulating Chalk Art Style Painting* ([ResearchGate](https://www.researchgate.net/publication/345740368_Simulating_Chalk_Art_Style_Painting)) — image-to-chalk-art via DoG edges + line integral convolution for the stroke texture. Photo filter, not stroke-based, but LIC along the stroke direction is the same "texture follows the stroke" trick.
- Majumder & Gopi, *Real-Time Charcoal Rendering Using Contrast Enhancement Operators* ([ResearchGate](https://www.researchgate.net/publication/2377841_Real-Time_Charcoal_Rendering_Using_Contrast_Enhancement_Operators)) — broad grainy strokes for 3D models.
- Shadertoy [lslGR4 "Chalk stroke"](https://www.shadertoy.com/view/lslGR4) — a GLSL take (login-walled, not read).

## Making it more (or less) human

Every `Hand` parameter is sampled per seed, and any of them can be pinned
from the CLI: `--jitter-x 0.1 --jitter-y 0.1` for visibly uneven letter
placement, `--spacing 0.9` to tighten a print face, `--slant 0`,
`--touchdown` / `--liftoff`, `--squiggle`, `--warp`, `--sloppiness`,
`--pressure`, `--join-prob`. `--help` lists them with units.

`--mess` is the one knob: 0.5 is a careful schoolbook hand, 1 the default, 2
a scrawl that is still mostly parseable, 3 illegible. It scales squiggle,
sloppiness (all per-letter jitter), the glyph warp, the line tilt and lowers
the join probability. What it does *not* change is the letterforms
themselves — every "a" is still the Hershey "a" underneath. The ceiling for
"looks like a real person wrote it" is therefore the stroke source: a Graves
RNN (see below) produces genuinely different letterforms per instance and
would slot in ahead of `refine()` with everything else unchanged.

## Ideas not done yet

- Sigma-lognormal velocity profiles instead of smoothstep ramps.
- Retrace darkening inside a letter (the cursive m/n humps are retraced in real writing).
- Occasional pen-lift mid-word and a re-entry blob — real writers do it, especially with chalk.
- Per-line pressure (titles pressed harder) and a slightly worn/blunter tip as the text goes on.
- An RNN stroke source behind the same `refine()`/`chalk.py` pipeline.
- Port: everything is numpy; the stroke generation is small and would move to JS easily. The deposition step is the heavier bit — a `<canvas>` with per-stroke ImageData would work, or keep Python as a sidecar the server calls for a PNG.
