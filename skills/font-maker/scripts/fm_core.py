# -*- coding: utf-8 -*-
"""font-maker core: design file, pens, outlines, profiles and spacing.

Letters live in design.json as centerline pen strokes (SVG path strings).
A pen turns each centerline into a closed outline; the spacing engine then
sets sidebearings and kerning from the shapes themselves.
"""
import json
import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pathops
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

HEBREW = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
DIGITS = "0123456789"
LATIN_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"
# Punctuation every font gets (drawn in the same pen as the letters).
PUNCT = ".,:;!?'\"()-–/%₪׳״־+=&@*"

SPACING = {  # fractions of the x-height
    #          letter gap  min clearance  word space
    "touching": (0.08, -0.03, 0.55),
    "close":    (0.19, 0.07, 0.62),
    "airy":     (0.30, 0.12, 0.75),
}
DEFAULT_WEIGHTS = {"Light": 0.62, "Regular": 1.0, "Bold": 1.65}
WEIGHT_CLASS = {"Thin": 100, "ExtraLight": 200, "Light": 300, "Regular": 400,
                "Medium": 500, "SemiBold": 600, "Bold": 700, "ExtraBold": 800, "Black": 900}


def utf8_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def fail(msg):
    print("ERROR " + msg)
    sys.exit(1)


# ---------------------------------------------------------------- design file

def load_design(folder):
    folder = Path(folder)
    path = folder / "design.json"
    if not path.exists():
        fail(f"no design.json in {folder}")
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"design.json is not valid JSON (line {e.lineno}): {e.msg}")
    d.setdefault("version", "1.000")
    d.setdefault("frame", "scan" if d.get("mode", "handwriting") == "handwriting" else "font")
    d.setdefault("font_x_height", 450)
    d.setdefault("pen", {"type": "round", "width": 32})
    d.setdefault("weights", dict(DEFAULT_WEIGHTS))
    d.setdefault("spacing", "close")
    d.setdefault("slant", 0)
    d.setdefault("glyphs", {})
    if d["spacing"] not in SPACING:
        fail(f'spacing must be one of {list(SPACING)}, got "{d["spacing"]}"')
    if not d.get("name"):
        fail("design.json needs a name")
    if "scale" not in d or not d["scale"]:
        if d["frame"] == "scan":
            if not d.get("x_height"):
                fail("design.json needs x_height (scan pixels) or scale")
            d["scale"] = d["font_x_height"] / float(d["x_height"])
        else:
            d["scale"] = 1.0
    d["xh"] = float(d["x_height"]) * d["scale"] if d["frame"] == "scan" and d.get("x_height") else float(d["font_x_height"])
    return d


def glyph_frame(design, g):
    return g.get("frame", design["frame"])


# ------------------------------------------------------------ centerlines

class _CubicCollector(BasePen):
    """Collects subpaths as lists of cubic segments (p0, p1, p2, p3)."""

    def __init__(self):
        super().__init__(None)
        self.subpaths = []  # (segments, closed, start_point)
        self._cur = None
        self._segs = None
        self._start = None

    def _moveTo(self, p):
        self._flush(False)
        self._segs, self._start, self._cur = [], p, p

    def _lineTo(self, p):
        a = np.array(self._cur, float)
        b = np.array(p, float)
        self._segs.append((a, a + (b - a) / 3, a + 2 * (b - a) / 3, b))
        self._cur = p

    def _curveToOne(self, p1, p2, p3):
        self._segs.append(tuple(np.array(q, float) for q in (self._cur, p1, p2, p3)))
        self._cur = p3

    def _qCurveToOne(self, p1, p2):
        a, c, b = (np.array(q, float) for q in (self._cur, p1, p2))
        self._segs.append((a, a + 2 / 3 * (c - a), b + 2 / 3 * (c - b), b))
        self._cur = p2

    def _closePath(self):
        if self._segs is not None and self._cur != self._start:
            self._lineTo(self._start)
        self._flush(True)

    def _endPath(self):
        self._flush(False)

    def _flush(self, closed):
        if self._segs and not closed and math.dist(self._cur, self._start) < 0.5:
            closed = True  # ends where it started: a ring (the round ends would overlap exactly)
        if self._segs is not None:
            self.subpaths.append((self._segs, closed, np.array(self._start, float)))
        self._segs = None


def centerlines(design, ch, g):
    """Centerline subpaths of glyph `ch` in font units (y up, baseline 0)."""
    s = design["scale"]
    frame = glyph_frame(design, g)
    if frame == "scan":
        base = float(g.get("baseline", 0))
        t = (s, 0, 0, -s, 0, base * s)
    else:
        base = float(g.get("baseline", 0))
        t = (1, 0, 0, 1, 0, -base)
    slant = g.get("slant", design["slant"] if frame == "font" else 0)
    col = _CubicCollector()
    pen = TransformPen(col, t)
    if slant:
        pen = TransformPen(pen, (1, 0, math.tan(math.radians(slant)), 1, 0, 0))
    for d in g.get("paths", []):
        try:
            parse_path(d, pen)
        except Exception as e:  # noqa: BLE001 - report which glyph is broken
            fail(f'glyph "{ch}": cannot read path "{d[:40]}..." ({e})')
    col._flush(False)
    return col.subpaths


def _num(v):
    s = ("%.1f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def transform_svg(d, m):
    """Apply an affine matrix (a, b, c, d, e, f) to an SVG path string."""
    from fontTools.pens.svgPathPen import SVGPathPen
    sp = SVGPathPen(None, ntos=_num)
    parse_path(d, TransformPen(sp, m))
    return sp.getCommands()


# ------------------------------------------------------------------ pens

def _subpath_to_path(segs, closed, start):
    p = pathops.Path()
    pen = p.getPen()
    if not segs:  # a single point: a dot
        pen.moveTo(tuple(start))
        pen.lineTo((start[0] + 0.05, start[1]))
        pen.endPath()
        return p
    pen.moveTo(tuple(segs[0][0]))
    for _, c1, c2, e in segs:
        pen.curveTo(tuple(c1), tuple(c2), tuple(e))
    if closed:
        pen.closePath()
    else:
        pen.endPath()
    return p


def _simple(path):
    return pathops.simplify(path, fix_winding=True, keep_starting_points=False)


def _union2(a, b):
    """Union of two clean shapes, checked: pathops sometimes returns a counter
    with the wrong direction (a filled D). The true union can never have more
    ink than both parts together, so such a result is retried."""
    aa, ab = _area(a), _area(b)
    hi = aa + ab + 1.0
    u = None
    for kw in ({"fix_winding": True, "keep_starting_points": False},
               {"fix_winding": True, "keep_starting_points": True},
               {"fix_winding": False, "keep_starting_points": True}):
        for x, y in ((a, b), (b, a)):
            u = pathops.op(x, y, pathops.PathOp.UNION, **kw)
            if _area(u) <= hi:
                return u
    return u


def _union(paths):
    """Union of clean (already simplified) shapes, two at a time."""
    items = [p for p in paths]
    if not items:
        return pathops.Path()
    while len(items) > 1:
        nxt = [_union2(items[i], items[i + 1]) for i in range(0, len(items) - 1, 2)]
        if len(items) % 2:
            nxt.append(items[-1])
        items = nxt
    return items[0]


def _stroked(path, width):
    q = pathops.Path(path)
    q.stroke(width, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    q.convertConicsToQuads(0.1)
    return q


def _area(path):
    from fontTools.pens.areaPen import AreaPen
    ap = AreaPen()
    path.draw(ap)
    return abs(ap.value)


def _stroke_sub(sp, width):
    """Stroke one subpath with a round pen. A ring that crosses itself (an 8)
    can come out with a filled loop when stroked as a closed shape; then it is
    stroked as an open line whose round ends overlap instead."""
    segs, closed, start = sp
    q = _simple(_stroked(_subpath_to_path(segs, closed, start), width))
    if not closed or not segs:
        return q
    expected = stroke_length([sp]) * width + math.pi * (width / 2) ** 2
    if _area(q) <= 1.3 * expected + 4 * width * width:
        return q
    p0, p1, p2, p3 = segs[-1]
    nudged = segs[:-1] + [(p0, p1, p2, p3 + (p2 - p3) * min(1.0, 0.5 / max(1e-6, np.linalg.norm(p2 - p3))))]
    return _simple(_stroked(_subpath_to_path(nudged, False, start), width))


def round_pen(subpaths, width):
    return _union(_stroke_sub(sp, width) for sp in subpaths)


def _split_cubic(seg, t):
    p0, p1, p2, p3 = seg
    a = p0 + (p1 - p0) * t
    b = p1 + (p2 - p1) * t
    c = p2 + (p3 - p2) * t
    d = a + (b - a) * t
    e = b + (c - b) * t
    f = d + (e - d) * t
    return (p0, a, d, f), (f, e, c, p3)


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _nib_split(seg, v):
    """Split a cubic where its direction is parallel to the nib edge."""
    p0, p1, p2, p3 = seg
    A, B, C = _cross(p1 - p0, v), _cross(p2 - p1, v), _cross(p3 - p2, v)
    a, b, c = A - 2 * B + C, 2 * (B - A), A
    roots = []
    if abs(a) < 1e-9:
        if abs(b) > 1e-9:
            roots = [-c / b]
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            r = math.sqrt(disc)
            roots = [(-b - r) / (2 * a), (-b + r) / (2 * a)]
    roots = sorted(t for t in roots if 0.002 < t < 0.998)
    pieces, rest, used = [], seg, 0.0
    for t in roots:
        local = (t - used) / (1 - used)
        first, rest = _split_cubic(rest, local)
        pieces.append(first)
        used = t
    pieces.append(rest)
    return pieces


def nib_pen(subpaths, width, thin, angle):
    """Broad-nib pen: the nib edge (length `width`, at `angle` degrees from
    horizontal) is swept along the path; `thin` is the hairline thickness."""
    a = math.radians(angle)
    v = np.array([math.cos(a), math.sin(a)]) * (width / 2.0)
    parts = []
    for segs, closed, start in subpaths:
        parts.append(_stroke_sub((segs, closed, start), thin))
        if not segs:
            dot = pathops.Path()
            pen = dot.getPen()
            pen.moveTo(tuple(start - v))
            pen.lineTo(tuple(start + v))
            pen.endPath()
            parts.append(_simple(_stroked(dot, thin)))
            continue
        for seg in segs:
            for q0, q1, q2, q3 in _nib_split(seg, v):
                rib = pathops.Path()
                pen = rib.getPen()
                pen.moveTo(tuple(q0 + v))
                pen.curveTo(tuple(q1 + v), tuple(q2 + v), tuple(q3 + v))
                pen.lineTo(tuple(q3 - v))
                pen.curveTo(tuple(q2 - v), tuple(q1 - v), tuple(q0 - v))
                pen.closePath()
                parts.append(_union2(_simple(rib), _simple(_stroked(rib, thin))))
    return _union(parts)


def pen_for_weight(design, weight):
    pen = design["pen"]
    f = design["weights"][weight]
    if pen.get("type", "round") == "nib":
        return dict(type="nib", width=pen["width"] * f, thin=pen.get("thin", pen["width"] * 0.18) * f ** 0.8,
                    angle=pen.get("angle", 30))
    return dict(type="round", width=pen["width"] * f)


def outline(design, ch, g, pen):
    subs = centerlines(design, ch, g)
    w = pen["width"] * g.get("pen_scale", 1.0)
    if pen["type"] == "nib":
        return nib_pen(subs, w, pen["thin"] * g.get("pen_scale", 1.0), pen["angle"])
    return round_pen(subs, w)


def stroke_length(subpaths):
    total = 0.0
    for segs, _, _ in subpaths:
        for p0, p1, p2, p3 in segs:
            t = np.linspace(0, 1, 24)[:, None]
            pts = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
            total += float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    return total


def looks_filled(design, ch, g, pen, path):
    """True when the outline has much more ink than its strokes can make
    (a loop that came out filled)."""
    from fontTools.pens.areaPen import AreaPen
    ap = AreaPen()
    path.draw(ap)
    w = pen["width"]
    subs = centerlines(design, ch, g)
    expected = stroke_length(subs) * w + len(subs) * math.pi * (w / 2) ** 2
    return abs(ap.value) > 1.5 * expected + 4 * w * w


# ---------------------------------------------------------- flatten, profile

class _FlattenPen(BasePen):
    def __init__(self, step=2.0):
        super().__init__(None)
        self.step = step
        self.contours = []
        self.cur = None

    def _moveTo(self, p):
        self.contours.append([p])

    def _lineTo(self, p):
        a = self.contours[-1][-1]
        n = max(1, int(math.hypot(p[0] - a[0], p[1] - a[1]) / self.step))
        for i in range(1, n + 1):
            t = i / n
            self.contours[-1].append((a[0] + (p[0] - a[0]) * t, a[1] + (p[1] - a[1]) * t))

    def _curveToOne(self, p1, p2, p3):
        p0 = self.contours[-1][-1]
        approx = math.dist(p0, p1) + math.dist(p1, p2) + math.dist(p2, p3)
        n = max(2, int(approx / self.step))
        for i in range(1, n + 1):
            t = i / n
            mt = 1 - t
            self.contours[-1].append((
                mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.contours[-1][-1]
        n = max(2, int((math.dist(p0, p1) + math.dist(p1, p2)) / self.step))
        for i in range(1, n + 1):
            t = i / n
            mt = 1 - t
            self.contours[-1].append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                                      mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        pass


def flatten(path, step=2.0):
    p = pathops.Path(path)
    p.convertConicsToQuads(0.1)
    pen = _FlattenPen(step)
    p.draw(pen)
    pts = [np.array(c, float) for c in pen.contours if len(c) > 1]
    return np.concatenate(pts) if pts else np.zeros((0, 2))


class Rows:
    """A shared grid of horizontal bands used for every glyph profile."""

    def __init__(self, ymin, ymax, step):
        self.step = step
        self.y0 = math.floor(ymin / step) * step
        self.n = int(math.ceil((ymax - self.y0) / step)) + 1
        self.centers = self.y0 + (np.arange(self.n) + 0.5) * step

    def profile(self, pts):
        left = np.full(self.n, np.nan)
        right = np.full(self.n, np.nan)
        if len(pts):
            idx = np.clip(((pts[:, 1] - self.y0) // self.step).astype(int), 0, self.n - 1)
            order = np.argsort(idx, kind="stable")
            idx, xs = idx[order], pts[order, 0]
            bounds = np.flatnonzero(np.diff(idx)) + 1
            starts = np.r_[0, bounds]
            ends = np.r_[bounds, len(idx)]
            for s, e in zip(starts, ends):
                left[idx[s]] = xs[s:e].min()
                right[idx[s]] = xs[s:e].max()
        return left, right

    def mask(self, lo, hi):
        return (self.centers >= lo) & (self.centers <= hi)


# ------------------------------------------------------------------ spacing

def char_class(ch):
    ch = ch[:1]  # "ל.alt" is spaced like "ל"
    if ch in HEBREW:
        return "hebrew"
    if ch in LATIN_LOWER:
        return "lower"
    if ch in LATIN_UPPER or ch in DIGITS:
        return "tall"
    return "mark"


def gap_measure(lr, rl, step, depth, w=0.3):
    """Gap between two letters, given per-row ink edges already in place:
    `lr` = right edge of the left letter, `rl` = left edge of the right one.
    Returns (nearest 2D distance, effective gap). The effective gap mixes the
    nearest approach with the average row gap, where open space deeper than
    `depth` counts no more (so open letters do not look far away)."""
    yi = np.flatnonzero(~np.isnan(lr))
    yj = np.flatnonzero(~np.isnan(rl))
    if not len(yi) or not len(yj):
        return None, None
    dx = rl[yj][None, :] - lr[yi][:, None]
    dy = (yj[None, :] - yi[:, None]) * step
    d = np.where(dy == 0, dx, np.hypot(np.maximum(dx, 0), dy))
    nearest = float(d.min())
    g = rl - lr
    cap = nearest + depth
    clipped = np.where(np.isnan(g), cap, np.minimum(g, cap))
    return nearest, w * nearest + (1 - w) * float(clipped.mean())


class Spacer:
    """Sets sidebearings and kerning so that letters sit at an even optical
    distance. Parts outside the letter body (ascenders, descenders, the arm of
    lamed) may overhang; clearance checks keep them from hitting neighbours."""

    DEPTH = 0.25   # open space deeper than this (x x-height) counts no more
    NEAREST = 0.3  # weight of the nearest approach in the gap measure

    def __init__(self, design, shapes):
        self.d = design
        xh = design["xh"]
        self.xh = xh
        gap, clear, word = SPACING[design["spacing"]]
        self.target = design.get("letter_gap", gap * xh)
        self.clear = design.get("min_clearance", clear * xh)
        self.clear_out = self.clear if self.clear <= 0 else 0.4 * self.clear
        self.clear2 = max(self.clear, 0.05 * xh)
        self.word = design.get("word_space", word * xh)
        self.shapes = shapes  # ch -> pathops.Path
        self.pts = {ch: flatten(p) for ch, p in shapes.items()}
        allp = [p for p in self.pts.values() if len(p)]
        cat = np.concatenate(allp) if allp else np.zeros((1, 2))
        self.rows = Rows(cat[:, 1].min() - 20, cat[:, 1].max() + 20, max(4.0, xh / 45))
        self.prof = {ch: self.rows.profile(p) for ch, p in self.pts.items()}
        self.k_win = int(math.ceil(max(abs(self.clear), 0.06 * xh) / self.rows.step)) + 1
        self.body_mask = self.rows.mask(-0.05 * xh, 1.1 * xh)
        self.depth = self.DEPTH * xh
        self.layout = {}
        self.kern = {}       # (visual left, visual right) -> units
        self.guards = {}     # logical glyph tuple -> units, applied on its first glyph
        self.alt_ctx = {}    # "ל" -> letters after which "ל.alt" is used
        self.zone = {ch: self._zone(ch) for ch in shapes}

    # -- glyph zones and sidebearings
    def _zone(self, ch):
        pts = self.pts[ch]
        if not len(pts):
            return None
        cls = char_class(ch)
        top, bot = pts[:, 1].max(), pts[:, 1].min()
        if cls in ("hebrew", "lower"):
            lo, hi = 0.0, self.xh
            if not self.rows.mask(lo, hi)[~np.isnan(self.prof[ch][0])].any():
                lo, hi = bot, top
        elif cls == "tall":
            lo, hi = 0.0, max(top, 1.0)
        else:
            lo, hi = bot, top
        return lo, hi

    def _sides(self, ch):
        left, right = self.prof[ch]
        lo, hi = self.zone[ch]
        m = self.rows.mask(lo, hi)
        if not (m & ~np.isnan(left)).any():
            m = ~np.isnan(left)
        L, R = left[m], right[m]
        ext_l, ext_r = np.nanmin(L), np.nanmax(R)
        dl = np.where(np.isnan(L), self.depth, np.minimum(L - ext_l, self.depth))
        dr = np.where(np.isnan(R), self.depth, np.minimum(ext_r - R, self.depth))
        return ext_l, ext_r, dl.mean(), dr.mean()

    def set_metrics(self):
        half = self.target / 2.0
        for ch in self.shapes:
            g = self.d["glyphs"].get(ch[:1], {})
            extra = g.get("space", {})
            if self.zone[ch] is None:
                adv = g.get("advance", self.word if ch == " " else 0.5 * self.xh)
                self.layout[ch] = dict(shift=0.0, adv=float(adv))
                continue
            ext_l, ext_r, ml, mr = self._sides(ch)
            cls = char_class(ch)
            k = 1.0 if cls in ("hebrew", "lower", "tall") else 0.8
            lsb = max(half * k - ml * (1 - self.NEAREST), -0.3 * self.xh) + extra.get("left", 0)
            rsb = max(half * k - mr * (1 - self.NEAREST), -0.3 * self.xh) + extra.get("right", 0)
            # A glyph's own advance is never smaller than a sliver of its body.
            adv = max(lsb + (ext_r - ext_l) + rsb, 0.12 * self.xh)
            self.layout[ch] = dict(shift=lsb - ext_l, adv=adv)

    # -- pair measures (L is visually left, R visually right)
    def placed(self, ch, dx=0.0):
        left, right = self.prof[ch]
        s = self.layout[ch]["shift"] + dx
        return left + s, right + s

    def body_rows(self, L, R):
        lo = max(self.zone[L][0], self.zone[R][0])
        hi = min(self.zone[L][1], self.zone[R][1])
        if hi - lo < 0.3 * self.xh:
            lo, hi = min(self.zone[L][0], self.zone[R][0]), max(self.zone[L][1], self.zone[R][1])
        return self.rows.mask(lo, hi)

    def body_measure(self, L, R, offset):
        m = self.body_rows(L, R)
        _, lr = self.placed(L)
        rl, _ = self.placed(R, offset)
        return gap_measure(lr[m], rl[m], self.rows.step, self.depth, self.NEAREST)

    def clearance(self, L, R, offset):
        """Closest approach of the two letters (2D, row by row and a few rows
        up and down). Strokes outside the letter body (ascenders, descenders)
        may come closer than strokes inside it. Returned relative to
        `self.clear`: a value below it means "too close"."""
        _, lr = self.placed(L)
        rl, _ = self.placed(R, offset)
        need = np.where(self.body_mask, self.clear, self.clear_out)
        best = np.inf
        n = len(lr)
        for s in range(-self.k_win, self.k_win + 1):
            if s >= 0:
                a, b, nd = lr[:n - s], rl[s:], need[s:]
            else:
                a, b, nd = lr[-s:], rl[:n + s], need[:n + s]
            dx = b - a
            ok = ~np.isnan(dx)
            if not ok.any():
                continue
            dx = dx[ok]
            d = dx if s == 0 else np.hypot(np.maximum(dx, 0), abs(s) * self.rows.step)
            best = min(best, float((d - nd[ok]).min()))
        return None if best == np.inf else best + self.clear

    def pair_kern(self, L, R):
        base = self.layout[L]["adv"]
        lo, hi = base - 0.8 * self.xh, base + 0.6 * self.xh
        if self.body_measure(L, R, base)[1] is None:
            off = base
        else:
            for _ in range(12):  # the effective gap grows with the offset
                mid = (lo + hi) / 2
                if self.body_measure(L, R, mid)[1] < self.target:
                    lo = mid
                else:
                    hi = mid
            off = (lo + hi) / 2
        # the right letter's origin never moves left of the left letter's origin
        off = max(off, 0.0)
        c = self.clearance(L, R, off)
        if c is not None and c < self.clear:
            off += self.clear - c
        k = off - base
        # and the pen never runs backwards
        return max(k, -0.9 * self.layout[R]["adv"])

    def space_kern(self, chars, rtl):
        """Next to a word space only the nearest ink counts. Letters that
        tuck into their neighbours (a high yud, an open side) and strokes
        that reach out of the body would make the space look small."""
        sp = " "
        if sp not in self.layout:
            return
        half = self.target / 2.0
        for c in chars:
            if c not in self.shapes or self.zone[c] is None:
                continue
            left, right = self.placed(c)
            adv = self.layout[c]["adv"]
            m = self.rows.mask(-0.1 * self.xh, 1.15 * self.xh)
            near_r = adv - np.nanmax(right[m]) if (~np.isnan(right[m])).any() else half
            near_l = np.nanmin(left[m]) if (~np.isnan(left[m])).any() else half
            over_r = max(0.0, np.nanmax(right) - np.nanmax(right[m]))
            over_l = max(0.0, np.nanmin(left[m]) - np.nanmin(left))
            for (L, R), near, over in (((c, sp), near_r, over_r), ((sp, c), near_l, over_l)):
                k = max(0.0, half - near) + min(0.35 * over, 0.2 * self.xh)
                if k >= 0.02 * self.xh:
                    self.kern[(L, R)] = int(round(k))

    def kern_all(self, chars, rtl):
        chars = [c for c in chars if c in self.shapes and self.zone[c] is not None]
        thresh = 0.015 * self.xh
        for a in chars:
            for b in chars:
                L, R = (b, a) if rtl else (a, b)  # a is logically first
                k = self.pair_kern(L, R)
                if abs(k) >= thresh:
                    self.kern[(L, R)] = int(round(k))

    def offset(self, L, R):
        return self.layout[L]["adv"] + self.kern.get((L, R), 0)

    def guard_all(self, chars, middles, max_mid=2):
        """Clearance between letters two or more apart (e.g. the arm of lamed
        reaching over a short letter towards a tall one). Works in visual
        order: A is leftmost, Z rightmost; the RTL logical order is reversed."""
        chars = [c for c in chars if c in self.shapes and self.zone[c] is not None]
        if not chars:
            return
        middles = [c for c in middles if c in self.layout]
        adv = {c: self.layout[c]["adv"] for c in self.layout}
        over_r, over_l = {}, {}
        for c in chars:
            left, right = self.placed(c)
            over_r[c] = np.nanmax(right) - adv[c]
            over_l[c] = -np.nanmin(left)
        max_l = max(over_l.values())

        def off(a, b):
            return adv[a] + self.kern.get((a, b), 0)

        for A in chars:
            reach = over_r[A] + max_l
            if reach <= 0:
                continue
            stack = [([A], 0.0)]
            while stack:
                seq, pos = stack.pop()
                for m in middles:
                    if m == " " and " " in seq:
                        continue
                    p = pos + off(seq[-1], m)
                    if p - adv[A] > reach:
                        continue
                    nxt = seq + [m]
                    for Z in chars:
                        zpos = p + off(m, Z)
                        if zpos - adv[A] > over_r[A] + over_l[Z]:
                            continue
                        c = self.clearance(A, Z, zpos)
                        if c is not None and c < self.clear2:
                            key = tuple(reversed(nxt + [Z]))  # logical order
                            self.guards[key] = int(math.ceil(self.clear2 - c))
                    if len(nxt) - 1 < max_mid:
                        stack.append((nxt, p))

    # -- layout of a whole string (visual, LTR coordinates) as GPOS will do it
    def choose_alts(self, chars):
        """Use a glyph's alternate (e.g. a lamed with a shorter arm) after the
        letters where it closes a gap the main form cannot."""
        for key in [k for k in self.shapes if k.endswith(".alt")]:
            base = key[:1]
            if base not in self.shapes:
                continue
            ctx = []
            for X in chars:
                if X not in self.shapes or self.zone.get(X) is None:
                    continue
                e_main = self.body_measure(base, X, self.layout[base]["adv"] + self.pair_kern(base, X))[1]
                e_alt = self.body_measure(key, X, self.layout[key]["adv"] + self.pair_kern(key, X))[1]
                if e_main is not None and e_alt is not None and e_main - e_alt > 0.08 * self.xh:
                    ctx.append(X)
            if ctx:
                self.alt_ctx[base] = ctx

    def glyph_keys(self, text):
        """Characters to glyphs, with the alternates the font will substitute."""
        keys = []
        for i, c in enumerate(text):
            if c not in self.layout:
                continue
            if i and c in self.alt_ctx and text[i - 1] in self.alt_ctx[c]:
                keys.append(c + ".alt")
            else:
                keys.append(c)
        return keys

    def wide_pairs(self, chars, limit=12):
        """Logical pairs whose gap stays clearly wider than the target (a
        reaching stroke meets a tall neighbour)."""
        out = []
        for a in chars:
            for b in chars:
                if a not in self.shapes or b not in self.shapes:
                    continue
                L = b + ".alt" if b in self.alt_ctx and a in self.alt_ctx[b] else b
                e = self.body_measure(L, a, self.offset(L, a))[1]
                if e is not None and e > self.target + 0.3 * self.xh:
                    out.append((e, a + b))
        return [p for _, p in sorted(out, reverse=True)[:limit]]

    def place_word(self, text, rtl=True):
        glyphs = self.glyph_keys(text)
        vis = list(reversed(glyphs)) if rtl else glyphs
        xs, pen = [], 0.0
        for i, c in enumerate(vis):
            if i:
                prev = vis[i - 1]
                pen += self.layout[prev]["adv"] + self.kern.get((prev, c), 0)
            xs.append(pen)
        if rtl:  # contextual guards on the logical first glyph
            logical = glyphs
            for key, k in self.guards.items():
                n = len(key)
                for i in range(len(logical) - n + 1):
                    if tuple(logical[i:i + n]) == key:
                        vi = len(vis) - 1 - i
                        for j in range(vi, len(vis)):
                            xs[j] += k
        return vis, xs

    def word_gaps(self, text, rtl=True):
        """Nearest and effective body gaps between neighbouring letters."""
        out = []
        for word in text.split():
            vis, xs = self.place_word(word, rtl)
            for i in range(len(vis) - 1):
                L, R = vis[i], vis[i + 1]
                if self.zone.get(L) is None or self.zone.get(R) is None:
                    continue
                if char_class(L) == "mark" or char_class(R) == "mark":
                    continue
                n, e = self.body_measure(L, R, xs[i + 1] - xs[i])
                if n is not None:
                    out.append((L[:1] + R[:1], n, e))
        return out


def spread(values):
    v = np.array(values, float)
    if not len(v):
        return {}
    q1, q3 = np.percentile(v, [25, 75])
    return {"n": int(len(v)), "mean": round(float(v.mean()), 1), "std": round(float(v.std()), 1),
            "iqr": round(float(q3 - q1), 1), "min": round(float(v.min()), 1), "max": round(float(v.max()), 1)}


# ------------------------------------------------------------------ names

_TRANSLIT = {"א": "a", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ch", "ט": "t",
             "י": "y", "כ": "k", "ך": "ch", "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s",
             "ע": "a", "פ": "p", "ף": "f", "צ": "tz", "ץ": "tz", "ק": "k", "ר": "r", "ש": "sh", "ת": "t"}


def latin_name(design):
    """English family name; transliterates a Hebrew name if none was given."""
    n = design.get("name_latin")
    if not n:
        words = []
        for w in design["name"].split():
            t = "".join(_TRANSLIT.get(c, c) for c in w)
            t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
            t = "".join(c for c in t if c.isalnum())
            if t:
                words.append(t[0].upper() + t[1:])
        n = " ".join(words) or "My Font"
    return n


def ps_name(family):
    s = "".join(c for c in family if c.isalnum() and c.isascii())
    return (s or "MyFont")[:40]


def has_hebrew(s):
    return any("֐" <= c <= "׿" for c in s)


# ------------------------------------------------------------------ scans

def load_scan(path):
    """Open a scan or phone photo upright (phones store rotation separately)."""
    from PIL import Image, ImageOps
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def hebrew_font(size):
    """A PIL font that can draw Hebrew labels (Windows/Mac system fonts)."""
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()
