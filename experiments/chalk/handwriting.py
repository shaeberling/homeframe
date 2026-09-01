"""Text -> pen strokes that look hand-written, different on every run.

Letterforms come from a Hershey single-line script font: real cursive shapes
stored as pen centrelines (with entry/exit strokes), which is what a chalk
model needs — an outline font only tells you where the ink is, not how the
hand moved. On top of that sits a small motor model:

  * a per-run "hand" (size, slant, spacing, sloppiness, pressure habit)
  * per-letter variation: scale, rotation, baseline bounce, advance jitter,
    plus a slow baseline drift across the line
  * letters within a word are joined into continuous strokes when the exit
    of one lands on the entry of the next, like real cursive
  * corner rounding and a "squiggle" — smooth noise applied normal to the
    path, which AlMeraj et al. (CAe 2008) found is what makes a synthetic
    line read as human-drawn
  * kinematics: tangential speed from curvature via the two-thirds power law
    (Lacquaniti, Terzuolo & Viviani 1983), accelerate/decelerate at stroke
    ends (Flash & Hogan 1985 minimum-jerk), and pressure that follows speed
    with a heavier landing spot and a lift-off taper

The output is a list of strokes, each an (N, 4) float array of
x, y, pressure, speed sampled every ~1 px along the path, in image
coordinates (y down). Pressure is 0..1, speed is relative (mean ~1).
"""
import glob
import math
import os
from dataclasses import dataclass, asdict, field

import numpy as np
from HersheyFonts import HersheyFonts

from noise import noise1d, smooth1d, smoothstep
from svgfont import SvgFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


@dataclass
class Hand:
    x_height: float        # px
    slant: float           # degrees, positive leans right
    spacing: float         # letter advance multiplier
    word_gap: float        # space advance multiplier
    squiggle: float        # wobble amplitude normal to the path, fraction of x-height
    sloppiness: float      # scales all per-letter jitter
    pressure: float        # habitual pressure 0..1
    pressure_var: float    # amplitude of slow pressure drift along a stroke
    smoothing: float       # corner rounding, fraction of x-height
    warp: float            # per-glyph shape deformation, fraction of x-height
    join_prob: float       # chance of keeping the pen down between two letters
    touchdown: float       # x-heights over which the chalk settles onto the board at a stroke start
    liftoff: float         # x-heights over which it lifts away at the end
    mess: float = 1.0      # the knob everything above was sampled with
    join: bool = True      # connect letters into continuous strokes at all

    @classmethod
    def random(cls, rng, x_height, mess=1.0):
        """Sample a writer. mess=0.5 is a careful schoolbook hand, 1 is normal,
        2 is scrawl."""
        return cls(
            x_height=x_height,
            slant=float(rng.uniform(0.0, 18.0)),
            spacing=float(rng.uniform(0.9, 1.15)),
            word_gap=float(rng.uniform(0.9, 1.4)),
            squiggle=float(rng.uniform(0.025, 0.05)) * mess,
            sloppiness=float(rng.uniform(0.7, 1.2)) * mess,
            pressure=float(rng.uniform(0.62, 0.85)),
            pressure_var=float(rng.uniform(0.1, 0.25)),
            smoothing=float(rng.uniform(0.05, 0.12)),
            warp=float(rng.uniform(0.04, 0.08)) * mess,
            join_prob=float(np.clip(rng.uniform(0.8, 1.0) - 0.3 * (mess - 1.0), 0.3, 1.0)),
            touchdown=float(rng.uniform(0.12, 0.3)),
            liftoff=float(rng.uniform(0.2, 0.45)),
            mess=mess,
        )

    def describe(self):
        return ', '.join(f'{k}={v:.3g}' if isinstance(v, float) else f'{k}={v}'
                         for k, v in asdict(self).items())


@dataclass(eq=False)
class RawStroke:
    pts: np.ndarray                 # (N, 2) image coordinates
    joined_start: bool = False      # a previous letter's connector lands here: no landing spot
    joined_end: bool = False        # continues into the next letter: no lift-off taper


class ScriptFont:
    """Hershey font wrapper that hands out raw glyph strokes in font units.

    Hershey coordinates are y-down with the baseline at `render_options.base_line`
    and caps at `cap_line` (negative), i.e. the same orientation as an image.
    All Hershey fonts share this unit system, so digits can be borrowed from a
    plainer face (cursive numerals are hard to read) at the same scale.
    """

    def __init__(self, name='cursive', digits=None):
        self.font = HersheyFonts()
        self.font.load_default_font(name)
        self.digit_font = None
        if digits and digits != name:
            self.digit_font = HersheyFonts()
            self.digit_font.load_default_font(digits)
        opts = self.font.render_options
        self.baseline = float(opts.base_line)
        self.ascent_units = self.baseline - float(opts.cap_line)
        self.descent_units = float(opts.bottom_line) - self.baseline
        self._cache = {}
        x = self.glyph('x')
        self.x_units = self.baseline - min(y for s in x.strokes for _, y in s)
        self.space_advance = self.glyph(' ').char_width

    def glyph(self, ch):
        if ch not in self._cache:
            font = self.digit_font if (self.digit_font and (ch.isdigit() or ch in ':.,-')) else self.font
            try:
                g = next(iter(font.glyphs_for_text(ch)))
            except Exception:
                g = next(iter(self.font.glyphs_for_text('?')))
            self._cache[ch] = g
        return self._cache[ch]

    def nominal_advance(self, text, hand):
        s = hand.x_height / self.x_units
        return sum(self.glyph(c).char_width for c in text) * s * hand.spacing


def svg_fonts():
    """Single-line SVG fonts available in ./fonts, by file stem."""
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(FONT_DIR, '*.svg')))


def load_font(name, digits=None):
    """A Hershey face by name, or an SVG font from ./fonts by file stem (case-insensitive)."""
    for stem in svg_fonts():
        if stem.lower() == name.lower():
            return SvgFont(os.path.join(FONT_DIR, stem + '.svg'))
    return ScriptFont(name, digits=digits)


def _place_glyph(font, ch, hand, rng, pen_x, base_y, mood):
    """Transform one glyph's strokes into image space.

    `mood` carries slow variation along the line (size, slant, rotation in
    -1..1); a smaller independent kick is added per letter. On top of the
    affine jitter the glyph gets its own ascender/descender proportions and a
    smooth quadratic warp over its box, so two instances of the same letter
    are different shapes, not rotated copies.
    """
    g = font.glyph(ch)
    slop = hand.sloppiness
    xu = font.x_units
    s = hand.x_height / xu
    size = 1 + 0.08 * slop * mood['size'] + 0.04 * slop * rng.normal()
    sx = s * size * (1 + 0.04 * slop * rng.normal())
    sy = s * size * (1 + 0.04 * slop * rng.normal())
    slant = math.tan(math.radians(hand.slant + 5.0 * slop * mood['slant'] + 2.0 * slop * rng.normal()))
    rot = math.radians(3.0 * slop * mood['rot'] + 1.5 * slop * rng.normal())
    cr, sr = math.cos(rot), math.sin(rot)
    bounce = 0.05 * slop * hand.x_height * rng.normal()
    # Ascenders/descenders vary a lot between instances, but an 'l' that
    # shrinks to x-height reads as an 'i', so keep them clearly longer.
    asc = float(np.clip(1 + 0.12 * slop * rng.normal(), 0.8, 1.35))
    desc = float(np.clip(1 + 0.15 * slop * rng.normal(), 0.75, 1.4))
    amp = hand.warp * xu
    wx = rng.normal(0.0, amp, 3)
    wy = rng.normal(0.0, amp, 3)
    width = max(g.char_width, 1)

    strokes = []
    for stroke in g.strokes:
        pts = np.asarray(stroke, np.float64).reshape(-1, 2)
        if len(pts) == 1:  # a dot: give it a tiny extent so it survives resampling
            pts = np.vstack([pts, pts + [0.6, 0.4]])
        u = pts[:, 0] - g.left_offset             # font units from the glyph's left edge
        v = pts[:, 1] - font.baseline             # font units, negative above the baseline
        # Ascenders and descenders get their own length.
        v = np.where(v < -xu, -xu + (v + xu) * asc, v)
        v = np.where(v > 0, v * desc, v)
        # Shape warp: a quadratic displacement field over the letter box,
        # normalised so the x-height zone spans -1..1 vertically.
        uu = u / width * 2 - 1
        vv = np.clip((v + xu / 2) / (xu / 2), -1.2, 1.2)
        u = u + wx[0] * uu * vv + wx[1] * uu * uu + wx[2] * vv * vv
        v = v + wy[0] * uu * vv + wy[1] * uu * uu + wy[2] * vv * vv
        u, v = u * sx, v * sy
        u = u - v * slant                         # shear: tops move right
        x = pen_x + u * cr - v * sr
        y = base_y + bounce + u * sr + v * cr
        strokes.append(np.stack([x, y], 1))

    # Hershey glyphs often split one pen movement into several strokes at a
    # retrace. If the next starts where the last ended, the pen never lifted.
    merged = []
    for st in strokes:
        if merged and np.hypot(*(st[0] - merged[-1][-1])) < 0.12 * hand.x_height:
            merged[-1] = np.vstack([merged[-1], st[1:]])
        else:
            merged.append(st)

    advance = g.char_width * s * size * hand.spacing * (1 + 0.06 * slop * rng.normal())
    return [RawStroke(st) for st in merged], advance


def _join(prev, letter, xh):
    """Connect the previous letter into this one if its exit lands on it.

    Hershey cursive is drawn so that, at nominal spacing, a letter's exit
    connector ends exactly on the next letter: at the *start* of its stroke
    for n/m/i/u-type letters, or on the left side of the bowl for a/o/d/g-type
    letters. The first case is one continuous pen movement, so the strokes are
    concatenated; in the second the connector touches the bowl, so both strokes
    just lose their end effects. Returns the stroke that absorbed one of the
    letter's strokes, if any.
    """
    best = None
    for p in prev:
        for st in letter:
            d = np.hypot(*(st.pts - p.pts[-1]).T)
            k = int(d.argmin())
            if best is None or d[k] < best[0]:
                best = (d[k], k, p, st)
    if best is None or best[0] > 0.45 * xh:
        return None
    dist, k, p, st = best
    if k <= 1:
        p.pts = np.vstack([p.pts, st.pts[k + 1:]])
        p.joined_end = st.joined_end
        letter[:] = [s for s in letter if s is not st]
        return p
    p.joined_end = True
    st.joined_start = True
    return None


def write(text, font, hand, rng, x0, y0, max_width, line_height, align='left', wrap=True):
    """Lay out text (\\n = new line; wraps on words unless wrap=False).

    Returns a list of RawStroke. Geometry is proportional to hand.x_height, so
    a layout made at x_height=1 can be measured and scaled afterwards (see
    main.render's fit mode). align='center' centres each visual line on
    x0 + max_width / 2.
    """
    strokes = []
    xh = hand.x_height
    slop = hand.sloppiness
    s = xh / font.x_units

    def flush(line_strokes):
        if line_strokes and align == 'center':
            xs = np.concatenate([st.pts[:, 0] for st in line_strokes])
            shift = x0 + max_width / 2 - (xs.min() + xs.max()) / 2
            for st in line_strokes:
                st.pts = st.pts + [shift, 0.0]
        strokes.extend(line_strokes)
        return []

    y = y0
    for line in text.split('\n'):
        pen = x0
        line_strokes = []
        # The line as a whole tilts a little, the baseline wanders along it,
        # and the writer's size/slant/rotation drift rather than jump.
        n = len(line) + 1
        tilt = math.tan(math.radians(rng.uniform(-1.5, 1.5) * hand.mess))
        drift = noise1d(n, 10.0, rng) * 0.08 * xh * slop
        moods = {k: noise1d(n, sc, rng) for k, sc in (('size', 8.0), ('slant', 12.0), ('rot', 9.0))}
        col = 0
        for wi, word in enumerate(line.split(' ')):
            if wi > 0:
                if wrap and pen + font.nominal_advance(word, hand) > x0 + max_width:
                    line_strokes = flush(line_strokes)
                    y += line_height
                    pen = x0
                else:
                    pen += font.space_advance * s * hand.word_gap * (1 + 0.15 * slop * rng.normal())
            prev = None    # the previous letter's strokes, still open for joining
            for ch in word:
                c = min(col, n - 1)
                mood = {k: float(v[c]) for k, v in moods.items()}
                base = y + drift[c] + (pen - x0) * tilt
                letter, adv = _place_glyph(font, ch, hand, rng, pen, base, mood)
                col += 1
                pen += adv
                joining = hand.join and prev and ch.isalpha() and rng.random() < hand.join_prob
                absorbed = _join(prev, letter, xh) if joining else None
                line_strokes.extend(letter)
                prev = (letter + ([absorbed] if absorbed else [])) if ch.isalpha() else None
            col += 1
        flush(line_strokes)
        y += line_height
    return strokes


def refine(raw, hand, rng):
    """Turn a RawStroke into a dense (N, 4) [x, y, pressure, speed] stroke."""
    xh = hand.x_height
    pts = np.asarray(raw.pts, np.float64)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    keep = np.concatenate([[True], seg > 1e-6])
    pts, seg = pts[keep], seg[keep[1:]]
    total = seg.sum()
    if len(pts) < 2 or total < 1.0:
        return None

    # 1. Resample at 1 px and round the polygonal Hershey corners.
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(total)) + 1, 3)
    s = np.linspace(0.0, total, n)
    x = np.interp(s, cum, pts[:, 0])
    y = np.interp(s, cum, pts[:, 1])
    x = smooth1d(x, hand.smoothing * xh)
    y = smooth1d(y, hand.smoothing * xh)

    # 2. Squiggle: smooth deviation normal to the path, two scales.
    tx, ty = np.gradient(x), np.gradient(y)
    norm = np.hypot(tx, ty) + 1e-9
    nx, ny = -ty / norm, tx / norm
    amp = hand.squiggle * xh * hand.sloppiness
    d = amp * (0.45 * noise1d(n, 0.6 * xh, rng) + 0.55 * noise1d(n, 2.0 * xh, rng))
    x, y = x + d * nx, y + d * ny

    # Closed loops (o, 0, bowls): the writer does not stop dead where the
    # stroke began, the chalk runs on over the start and lifts off there, so
    # the faint touchdown gets covered by the solid body of the tail.
    if not raw.joined_end and np.hypot(x[-1] - x[0], y[-1] - y[0]) < 0.25 * xh:
        k = int(min(hand.liftoff * xh, 0.3 * n))
        if k > 2:
            x = np.concatenate([x, x[1:k]])
            y = np.concatenate([y, y[1:k]])
            n = len(x)

    # 3. Kinematics. Speed from curvature (two-thirds power law: v ~ k^-1/3),
    #    with bell-shaped ramps where the movement actually starts or stops.
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    tx, ty = np.gradient(x, s), np.gradient(y, s)
    norm = np.hypot(tx, ty) + 1e-9
    tx, ty = smooth1d(tx / norm, 1.5), smooth1d(ty / norm, 1.5)
    curvature = np.hypot(np.gradient(tx, s), np.gradient(ty, s))
    curvature = smooth1d(curvature, 2.0)
    v = (curvature * xh + 0.08) ** (-1.0 / 3.0)
    ramp = 0.45 * xh
    if not raw.joined_start:
        v *= 0.15 + 0.85 * smoothstep(s / ramp)          # starts from rest
    if not raw.joined_end:
        v *= 0.5 + 0.5 * smoothstep((total - s) / ramp)  # slows, but lifts away while still moving
    v /= v.mean()

    # 4. Pressure: slower -> heavier, slow drift. Chalk does not get planted
    #    like a pen: it lands on a corner of the tip and settles flat over the
    #    first bit of the stroke, and lifts away gradually at the end, so the
    #    ends fade out thin and sparse. The profiles are concave so pressure
    #    stays up over most of a ramp and only the last third thins out; on
    #    short strokes (dots, dabs) the ramps are capped so they still mark.
    p = hand.pressure * v ** (-0.3)
    p *= 1 + hand.pressure_var * noise1d(n, 1.5 * xh, rng)
    p *= 1 + 0.1 * rng.normal()
    if not raw.joined_start:
        length = min(hand.touchdown * xh, 0.2 * total)
        p *= 0.05 + 0.95 * np.clip(s / max(length, 1e-6), 0.0, 1.0) ** 0.5
    if not raw.joined_end:
        length = min(hand.liftoff * xh, 0.2 * total)
        p *= 0.03 + 0.97 * np.clip((total - s) / max(length, 1e-6), 0.0, 1.0) ** 0.45
    p = np.clip(p, 0.02, 1.0)

    return np.stack([x, y, p, v], 1).astype(np.float32)
