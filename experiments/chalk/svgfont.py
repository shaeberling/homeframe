"""Single-line SVG fonts (the EMS faces shipped with Inkscape's Hershey Text
extension) as pen strokes, with the same interface as handwriting.ScriptFont.

SVG fonts store each glyph as path data in a y-up, 1000-units-per-em space
with the origin on the baseline at the left edge. The EMS faces are single
line: M/L polylines plus the odd cubic Bezier, which we flatten.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np

_TOKEN = re.compile(r'[MLHVCSQTZmlhvcsqtz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_NS = {'svg': 'http://www.w3.org/2000/svg'}


@dataclass
class Glyph:
    strokes: list           # (N, 2) arrays in font units, y down, baseline at 0
    char_width: float       # advance
    left_offset: float = 0.0


def _cubic(p0, p1, p2, p3, n=10):
    t = np.linspace(0.0, 1.0, n + 1)[1:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def parse_path(d):
    """SVG path data -> list of (N, 2) polylines, coordinates as in the file (y up)."""
    toks = _TOKEN.findall(d)
    strokes, cur = [], []
    pos = start = np.zeros(2)
    last_ctrl = None
    i, cmd = 0, 'M'

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    def pt():
        p = np.array([num(), num()])
        return pos + p if rel else p

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
        rel, c = cmd.islower(), cmd.upper()
        if c == 'M':
            if len(cur) > 1:
                strokes.append(cur)
            pos = start = pt()
            cur = [pos]
            cmd = 'l' if rel else 'L'      # further pairs are implicit linetos
        elif c == 'L':
            pos = pt()
            cur.append(pos)
        elif c == 'H':
            x = num()
            pos = np.array([pos[0] + x if rel else x, pos[1]])
            cur.append(pos)
        elif c == 'V':
            y = num()
            pos = np.array([pos[0], pos[1] + y if rel else y])
            cur.append(pos)
        elif c in 'CS':
            if c == 'C':
                p1 = pt()
            else:
                p1 = 2 * pos - last_ctrl if last_ctrl is not None else pos
            p2 = pt()
            p3 = pt()
            cur.extend(_cubic(pos, p1, p2, p3))
            pos, last_ctrl = p3, p2
            continue
        elif c in 'QT':
            if c == 'Q':
                q1 = pt()
            else:
                q1 = 2 * pos - last_ctrl if last_ctrl is not None else pos
            p3 = pt()
            cur.extend(_cubic(pos, pos + 2 / 3 * (q1 - pos), p3 + 2 / 3 * (q1 - p3), p3))
            pos, last_ctrl = p3, q1
            continue
        elif c == 'Z':
            cur.append(start)
            strokes.append(cur)
            pos, cur = start, [start]
        else:
            raise ValueError(f'unsupported path command {cmd}')
        last_ctrl = None
    if len(cur) > 1:
        strokes.append(cur)
    return [np.array(s, np.float64) for s in strokes if len(s) > 1]


class SvgFont:
    def __init__(self, path):
        root = ET.parse(path).getroot()
        font = root.find('.//svg:font', _NS)
        face = font.find('svg:font-face', _NS)
        upm = float(face.get('units-per-em', 1000))
        self.name = face.get('font-family', path)
        self.baseline = 0.0
        self.ascent_units = float(face.get('ascent', 0.8 * upm))
        self.descent_units = -float(face.get('descent', -0.2 * upm))
        self.default_advance = float(font.get('horiz-adv-x', upm / 2))
        self._glyphs = {}
        for g in font.findall('svg:glyph', _NS):
            u = g.get('unicode')
            if not u or len(u) != 1:
                continue
            strokes = [s * np.array([1.0, -1.0]) for s in parse_path(g.get('d', ''))]
            self._glyphs[u] = Glyph(strokes, float(g.get('horiz-adv-x', self.default_advance)))
        # Measure the x-height rather than trust the declared one: hand-drawn
        # faces overshoot, and everything (line pitch, warp, joins) keys off it.
        x = self._glyphs.get('x')
        self.x_units = -min(p[1] for s in x.strokes for p in s) if x and x.strokes else float(face.get('x-height', 0.3 * upm))
        self.space_advance = self._glyphs[' '].char_width if ' ' in self._glyphs else self.default_advance

    def glyph(self, ch):
        return self._glyphs.get(ch) or self._glyphs.get('?') or Glyph([], self.default_advance)

    def nominal_advance(self, text, hand):
        s = hand.x_height / self.x_units
        return sum(self.glyph(c).char_width for c in text) * s * hand.spacing
