"""Render hand-written chalk text and preview it as the 1-bit e-ink panel would show it.

    .venv/bin/python main.py --seed 3
    .venv/bin/python main.py --text "Milk, eggs & bread" --x-height 60
    .venv/bin/python main.py --sheet 8          # 8 seeds of the same phrase, side by side

Outputs go to ./out: chalk.png (the render), panel_dither.png and
panel_threshold.png (960x680 1-bit, the two ways the server can binarise),
strokes.png (centrelines coloured by pressure).
"""
import argparse
import json
import os
import time

import cv2
import numpy as np
from PIL import Image

from chalk import Chalk, add_dust, composite, make_board, make_haze, render_strokes
from handwriting import Hand, load_font, refine, svg_fonts, write

DEFAULT_TEXT = ("Today\n"
                "9:00  Standup\n"
                "13:30  Dentist\n"
                "18:00  Football\n"
                "Bins out tonight!\n"
                "Order more coffee")


def render(text, seed, size=(960, 680), x_height=26, font_name='cursive', digits_font=None,
           chalk=None, margin=50, haze=True, join=True, fit=False, border=0.05, align=None, mess=1.0,
           hand_overrides=None):
    """fit=True ignores x_height and margin: the text block is scaled to fill the
    canvas inside `border` (fraction of each edge) and centred, lines centred
    unless align says otherwise. Otherwise text starts at `margin` and wraps."""
    rng = np.random.default_rng(seed)
    w, h = size
    font = load_font(font_name, digits=digits_font)
    hand = Hand.random(rng, x_height, mess=mess)
    hand.join = join
    for k, v in (hand_overrides or {}).items():
        setattr(hand, k, v)
    chalk = chalk or Chalk()
    align = align or ('center' if fit else 'left')

    units_per_line = 1.05 * (font.ascent_units + font.descent_units) / font.x_units
    if fit:
        # Lay out at x-height 1, measure, then scale into the available box.
        # The layout is proportional to x-height, so this is exact.
        hand.x_height = 1.0
        raw = write(text, font, hand, rng, 0.0, 0.0, 1e9, units_per_line, align=align, wrap=False)
        pts = np.vstack([r.pts for r in raw])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        pad = chalk.width / 2 + 3                  # rim + dust
        avail = np.array([w * (1 - 2 * border), h * (1 - 2 * border)]) - 2 * pad
        scale = float((avail / np.maximum(hi - lo, 1e-6)).min())
        offset = np.array([w, h]) / 2 - (lo + hi) / 2 * scale
        for r in raw:
            r.pts = r.pts * scale + offset
        hand.x_height = scale
    else:
        scale = x_height / font.x_units
        raw = write(text, font, hand, rng, margin, margin + font.ascent_units * scale,
                    w - 2 * margin, units_per_line * x_height, align=align)
    strokes = [st for st in (refine(r, hand, rng) for r in raw) if st is not None]

    board = make_board((h, w), rng)
    coverage = render_strokes(board, strokes, chalk, rng)
    coverage = add_dust(coverage, chalk, rng)
    img = composite(coverage, make_haze((h, w), rng) if haze else None)
    return {'image': img, 'coverage': coverage, 'strokes': strokes, 'hand': hand}


def panel_views(coverage, threshold=160):
    """What the panel would show. On the panel the board is black and the chalk
    white, so the greyscale the server sees is just the coverage; it then
    thresholds (its default) or Floyd-Steinberg dithers (HF_DITHER=1)."""
    gray = np.clip(coverage * 255, 0, 255).astype(np.uint8)
    thresholded = ((gray >= threshold) * 255).astype(np.uint8)
    dithered = np.array(Image.fromarray(gray).convert('1'), dtype=np.uint8) * 255
    return thresholded, dithered


def stroke_debug(strokes, size):
    """Centrelines on white, coloured by pressure (blue light -> red heavy), green dot at each pen-down."""
    w, h = size
    img = np.full((h, w, 3), 255, np.uint8)
    for st in strokes:
        pts = st[:, :2]
        for i in range(len(pts) - 1):
            p = float(st[i, 2])
            color = (int(255 * (1 - p)), 40, int(255 * p))
            cv2.line(img, tuple(np.rint(pts[i]).astype(int)), tuple(np.rint(pts[i + 1]).astype(int)),
                     color, 1, cv2.LINE_AA)
        cv2.circle(img, tuple(np.rint(pts[0]).astype(int)), 2, (0, 160, 0), -1)
    return img


def contact_sheet(text, seeds, x_height, font_name, digits_font, chalk, mess=1.0, cell=(480, 240)):
    tiles = []
    for seed in seeds:
        r = render(text, seed, size=cell, x_height=x_height, font_name=font_name, digits_font=digits_font,
                   chalk=chalk, margin=16, haze=False, mess=mess)
        tile = r['image'].copy()
        cv2.putText(tile, f'seed {seed}', (8, cell[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)
        tiles.append(tile)
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    while len(tiles) < rows * cols:
        tiles.append(np.zeros_like(tiles[0]))
    return np.vstack([np.hstack(tiles[i * cols:(i + 1) * cols]) for i in range(rows)])


# Hershey faces that carry the Latin alphabet. Simplex = single line; duplex,
# triplex and the Times/gothic faces are drawn with two or three parallel
# strokes, which chalk turns into a bold, slightly doubled letter.
# The EMS faces in ./fonts are single-line SVG fonts from Inkscape's Hershey
# Text extension (SIL OFL); they include real handwriting styles.
TEXT_FONTS = tuple(svg_fonts()) + ('futural', 'rowmans', 'timesi', 'rowmand', 'scripts', 'cursive', 'gothiceng')
SCRIPT_FONTS = ('cursive', 'scripts', 'scriptc', 'EMSAllure')


def font_sheet(text, seed, chalk, mess, cell=(480, 118), x_height=20):
    tiles = []
    for name in TEXT_FONTS:
        r = render(text, seed, size=cell, x_height=x_height, font_name=name, chalk=chalk,
                   margin=12, haze=False, mess=mess, join=name in SCRIPT_FONTS)
        tile = r['image'].copy()
        cv2.putText(tile, name, (8, cell[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)
        tiles.append(tile)
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    while len(tiles) < rows * cols:
        tiles.append(np.zeros_like(tiles[0]))
    return np.vstack([np.hstack(tiles[i * cols:(i + 1) * cols]) for i in range(rows)])


# Hand parameters that can be pinned from the CLI instead of sampled per seed.
HAND_FIELDS = {
    'slant': 'degrees, positive leans right',
    'spacing': 'letter advance multiplier',
    'word_gap': 'space advance multiplier',
    'jitter_x': 'per-letter horizontal offset, sigma in x-heights',
    'jitter_y': 'per-letter vertical offset, sigma in x-heights',
    'squiggle': 'wobble normal to the path, in x-heights',
    'warp': 'per-glyph shape deformation, in x-heights',
    'sloppiness': 'scales scale/rotation/advance jitter',
    'pressure': 'habitual pressure 0..1',
    'touchdown': 'x-heights for the chalk to settle at a stroke start',
    'liftoff': 'x-heights for the chalk to lift away at the end',
    'join_prob': 'chance of keeping the pen down between letters (script faces)',
}

CHALK_FIELDS = ('width', 'edge', 'min_width', 'facet_scale', 'facet_drift', 'facet_depth', 'softness', 'transfer', 'skip', 'drag', 'dust')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--text', default=DEFAULT_TEXT, help='literal \\n starts a new line')
    ap.add_argument('--seed', type=int, default=None, help='default: random, printed so you can reproduce')
    ap.add_argument('--size', default='960x680')
    ap.add_argument('--x-height', type=float, default=26, help='lowercase letter height in px (line pitch is ~3.85x)')
    ap.add_argument('--mess', type=float, default=1.0, help='0.5 careful schoolbook hand, 1 normal, 2 scrawl')
    ap.add_argument('--fit', action='store_true', help='scale the text block to fill the canvas inside --border, centred')
    ap.add_argument('--border', type=float, default=0.05, help='with --fit: empty fraction of each edge')
    ap.add_argument('--align', choices=['left', 'center'], default=None, help='default: center with --fit, else left')
    ap.add_argument('--font', default='cursive', help=f'Hershey face; text faces: {", ".join(TEXT_FONTS)}')
    ap.add_argument('--fonts', action='store_true', help='render every text face with the same hand to out/fonts.png')
    ap.add_argument('--join', action='store_true', help='connect letters even in a non-script face')
    ap.add_argument('--digits-font', default='', help='Hershey face for digits/punctuation, "" = same as --font')
    ap.add_argument('--threshold', type=int, default=160, help='panel threshold (server default 160)')
    ap.add_argument('--no-haze', action='store_true')
    ap.add_argument('--no-join', action='store_true', help='do not connect cursive letters')
    ap.add_argument('--sheet', type=int, default=0, help='render N seeds of a short phrase as a grid')
    ap.add_argument('--dump-strokes', default=None, help='write the stroke arrays as JSON')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    for f in CHALK_FIELDS:
        ap.add_argument(f'--{f.replace("_", "-")}', type=float, default=None, help=f'Chalk.{f}')
    for f, doc in HAND_FIELDS.items():
        ap.add_argument(f'--{f.replace("_", "-")}', type=float, default=None, help=f'pin Hand.{f}: {doc}')
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    args.text = args.text.replace('\\n', '\n')
    seed = args.seed if args.seed is not None else int(np.random.SeedSequence().entropy % (2 ** 31))
    size = tuple(int(v) for v in args.size.lower().split('x'))
    chalk = Chalk()
    for f in CHALK_FIELDS:
        if getattr(args, f) is not None:
            setattr(chalk, f, getattr(args, f))
    digits_font = args.digits_font or None
    hand_overrides = {f: getattr(args, f) for f in HAND_FIELDS if getattr(args, f) is not None}

    t0 = time.time()
    if args.fonts:
        sheet = font_sheet(args.text if args.text != DEFAULT_TEXT else 'Milk, eggs & bread 13:30',
                           seed, chalk, args.mess)
        path = os.path.join(args.out, 'fonts.png')
        cv2.imwrite(path, sheet)
        print(f'seed {seed}  {time.time() - t0:.1f}s  -> {path}')
        return
    if args.sheet:
        sheet = contact_sheet(args.text if args.text != DEFAULT_TEXT else 'Milk, eggs & bread',
                              list(range(seed, seed + args.sheet)), args.x_height, args.font, digits_font, chalk, mess=args.mess)
        path = os.path.join(args.out, 'sheet.png')
        cv2.imwrite(path, sheet)
        print(f'seed {seed}  {time.time() - t0:.1f}s  -> {path}')
        return

    r = render(args.text, seed, size=size, x_height=args.x_height, font_name=args.font, digits_font=digits_font,
               chalk=chalk, haze=not args.no_haze, join=(args.font in SCRIPT_FONTS or args.join) and not args.no_join,
               fit=args.fit, border=args.border, align=args.align, mess=args.mess,
               hand_overrides=hand_overrides)
    thresholded, dithered = panel_views(r['coverage'], args.threshold)
    cv2.imwrite(os.path.join(args.out, 'chalk.png'), r['image'])
    cv2.imwrite(os.path.join(args.out, 'panel_threshold.png'), thresholded)
    cv2.imwrite(os.path.join(args.out, 'panel_dither.png'), dithered)
    cv2.imwrite(os.path.join(args.out, 'strokes.png'), stroke_debug(r['strokes'], size))
    if args.dump_strokes:
        with open(args.dump_strokes, 'w') as fh:
            json.dump([st.tolist() for st in r['strokes']], fh)

    print(f'seed {seed}  {len(r["strokes"])} strokes  {time.time() - t0:.1f}s')
    print(f'hand: {r["hand"].describe()}')
    if args.fit:
        print(f'fitted x-height {r["hand"].x_height:.1f} px')
    print(f'-> {args.out}/chalk.png, panel_dither.png, panel_threshold.png, strokes.png')


if __name__ == '__main__':
    main()
