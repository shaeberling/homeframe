"""Chalk on a board: a stroke-following deposition model.

The board is a height field. Following Sousa & Buchanan's observational pencil
model (Computer Graphics Forum 2000) — chalk on slate is the same physics as
graphite on paper, just inverted — the tip presses down to a depth set by the
local pressure and pigment is left on every grain that reaches up to it. High
grains get chalk first; heavier pressure fills the valleys. That single rule
produces the speckled edges, the way a light stroke skips, and the way a
second pass over the same spot brightens it.

Texture follows the stroke because the local pressure is evaluated in stroke
coordinates (s along, t across): a worn chalk tip is not flat, it has facets,
so pressure across the tip varies with t and drifts slowly with s. Each facet
therefore leaves its own continuous trail — the striations you see in real
chalk lettering — which bend with the letters instead of being a fixed
screen-space grain stamped on top.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from noise import fbm, noise1d, value_noise


@dataclass
class Chalk:
    width: float = 7.0        # px: full contact width of the tip
    edge: float = 0.45        # fraction of the half-width over which the rounded rim's pressure falls off
    min_width: float = 0.25   # contact width at zero pressure, as a fraction of `width` (tip geometry)
    facet_scale: float = 1.3  # px across the tip: facet size, i.e. striation width
    facet_drift: float = 40.0 # px along the stroke over which facets evolve (stick rotates, wears)
    facet_depth: float = 0.4  # pressure difference between high and low facets (0 = perfectly flat tip)
    softness: float = 0.15    # height range over which a grain goes from untouched to fully covered
    transfer: float = 0.92    # pigment left by one pass on a grain the tip fully reaches
    skip: float = 0.4         # dropout strength when the hand moves fast
    drag: float = 0.85        # pigment carried forward per half-pixel step: 0 = none, 0.9 = long streaks
    dust: float = 0.6         # loose dust: halo and stray specks around strokes


def make_board(shape, rng, spread=0.12):
    """Board surface height: fine slate grain plus mottling at two coarser scales.

    Heights are roughly normal around 0.5 with the given spread, so the
    coverage a stroke leaves rises steeply with pressure: ~20% at P=0.4, ~80%
    at P=0.6, solid above 0.75. At 88 dpi the real micro-roughness is
    sub-pixel; what survives at pixel scale is that steep response — solid
    centres, speckled rims and visible facet streaks.
    """
    h, w = shape
    fine = cv2.GaussianBlur(rng.random((h, w), dtype=np.float32), (0, 0), 0.7)
    medium = fbm((h, w), 3.0, rng, octaves=2)
    coarse = value_noise((h, w), 16.0, rng)
    height = 0.5 * fine + 0.35 * medium + 0.15 * coarse
    height = (height - height.mean()) / height.std() * spread + 0.5
    return np.clip(height, 0.0, 1.0).astype(np.float32)


def _deposit_stroke(board, stroke, chalk, rng):
    """Coverage layer (bbox-cropped) from one stroke, or None if it misses the board."""
    H, W = board.shape
    x, y, p, v = stroke.T

    # Resample along the path at half-pixel steps so no pixel under the
    # ribbon is skipped, even on tight curves.
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    if total <= 0:
        return None
    m = int(total / 0.5) + 2
    su = np.linspace(0.0, total, m)
    x, y, p, v = (np.interp(su, s, a) for a in (x, y, p, v))
    tx, ty = np.gradient(x, su), np.gradient(y, su)
    norm = np.hypot(tx, ty) + 1e-9
    nx, ny = -ty / norm, tx / norm

    # Across the tip.
    half = chalk.width / 2.0
    nl = int(chalk.width / 0.5) + 1
    t = np.linspace(-half, half, nl)
    X = x[:, None] + t[None, :] * nx[:, None]
    Y = y[:, None] + t[None, :] * ny[:, None]

    # Pressure distribution over the tip: flat centre, rounded rim that fades
    # to nothing (Sousa & Buchanan's pressure distribution coefficients). The
    # contact patch grows with pressure - a lightly held chalk touches the
    # board with a corner, not its whole face - so the stroke narrows as it
    # fades in and out.
    contact = half * (chalk.min_width + (1.0 - chalk.min_width) * np.sqrt(np.clip(p, 0.0, 1.0)))
    rim = np.clip((1.0 - np.abs(t)[None, :] / contact[:, None]) / chalk.edge, 0.0, 1.0) ** 0.8

    # Facets: pressure varies across the tip and drifts slowly along the
    # stroke. Evaluated in (s, t) space so each facet's trail follows the path.
    facets = 1.0 - chalk.facet_depth * value_noise(
        (m, nl), (chalk.facet_drift / 0.5, chalk.facet_scale / 0.5), rng)

    # Fast movement makes the tip bounce and skip.
    fast = np.clip(v - 0.9, 0.0, 1.0)
    skip = 1.0 - chalk.skip * np.clip(noise1d(m, 8.0 / 0.5, rng), 0.0, 1.0) * fast

    P = p[:, None] * rim * facets * skip[:, None]

    xi = np.rint(X).astype(np.int32)
    yi = np.rint(Y).astype(np.int32)
    inside = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    if not inside.any():
        return None
    grain = np.where(inside, board[np.clip(yi, 0, H - 1), np.clip(xi, 0, W - 1)], 0.0)

    # The tip reaches down to height 1-P; grains above that level are coated.
    level = 1.0 - P
    d = np.clip((grain - level) / chalk.softness, 0.0, 1.0) * chalk.transfer

    # Drag: pigment picked up by a grain is smeared into the grains that follow
    # it along the movement, so isolated specks become short streaks. A decaying
    # running max down the s axis, done in the log domain so it vectorises.
    if chalk.drag > 0 and m > 1:
        with np.errstate(divide='ignore'):
            lg = np.log(d) - (np.arange(m) * np.log(chalk.drag))[:, None]
        lg = np.maximum.accumulate(lg, axis=0) + (np.arange(m) * np.log(chalk.drag))[:, None]
        d = np.exp(lg)

    xi, yi, d = xi[inside], yi[inside], d[inside]

    x0, x1 = xi.min(), xi.max() + 1
    y0, y1 = yi.min(), yi.max() + 1
    layer = np.zeros((y1 - y0, x1 - x0), np.float32)
    flat = (yi - y0) * (x1 - x0) + (xi - x0)
    order = np.argsort(d, kind='stable')     # last write wins -> per-pixel max
    layer.flat[flat[order]] = d[order]
    return layer, (y0, y1, x0, x1)


def render_strokes(board, strokes, chalk, rng):
    """Chalk coverage in [0, 1] for all strokes on the given board."""
    coverage = np.zeros_like(board)
    for stroke in strokes:
        result = _deposit_stroke(board, stroke, chalk, rng)
        if result is None:
            continue
        layer, (y0, y1, x0, x1) = result
        region = coverage[y0:y1, x0:x1]
        # Chalk on chalk: a second pass fills what the first one missed.
        region += layer * (1.0 - region)
    return coverage


def add_dust(coverage, chalk, rng):
    """Loose chalk dust: a faint halo and stray specks next to the strokes."""
    if chalk.dust <= 0:
        return coverage
    near = cv2.GaussianBlur(coverage, (0, 0), 2.5)
    out = coverage + chalk.dust * 0.08 * near * (1.0 - coverage)
    speck = rng.random(coverage.shape, dtype=np.float32) < chalk.dust * 0.06 * near * (1.0 - coverage)
    out[speck] += rng.uniform(0.2, 0.6, int(speck.sum())).astype(np.float32)
    return np.clip(out, 0.0, 1.0)


def make_haze(shape, rng, amount=0.06):
    """Residue of earlier erasing: low-frequency cloudiness plus faint diagonal wipe streaks."""
    h, w = shape
    cloud = fbm((h, w), 90.0, rng, octaves=3)
    streaks = value_noise((h, w), (6.0, 180.0), rng)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-25, 25), 1.4)
    streaks = cv2.warpAffine(streaks, M, (w, h), borderMode=cv2.BORDER_REFLECT)
    haze = 0.6 * cloud + 0.4 * streaks * cloud
    return (amount * haze).astype(np.float32)


def composite(coverage, haze=None, board_rgb=(30, 34, 31), chalk_rgb=(238, 240, 234)):
    """Coverage -> BGR uint8 image of chalk on a dark board."""
    board = np.array(board_rgb[::-1], np.float32)
    chalk = np.array(chalk_rgb[::-1], np.float32)
    c = coverage[..., None]
    if haze is not None:
        c = np.clip(c + haze[..., None] * (1.0 - c), 0.0, 1.0)
    img = board * (1.0 - c) + chalk * c
    return np.clip(img, 0, 255).astype(np.uint8)
