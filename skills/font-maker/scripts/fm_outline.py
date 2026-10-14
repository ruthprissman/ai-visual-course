"""Tiny outline toolkit: contours as lists of segments, in font units (y up).

A contour is a list of tuples:
    ("M", (x, y))                      start point (always first)
    ("L", (x, y))                      line to
    ("C", (x1, y1), (x2, y2), (x, y))  cubic curve to
Every contour is closed implicitly.
"""
from __future__ import annotations

from fontTools.pens.basePen import BasePen

Point = tuple[float, float]


class ContourPen(BasePen):
    """Collects pen calls into contours (quadratics become cubics)."""

    def __init__(self):
        super().__init__(None)
        self.contours: list[list[tuple]] = []
        self._cur: list[tuple] | None = None

    def _moveTo(self, p):
        self._finish()
        self._cur = [("M", tuple(p))]

    def _lineTo(self, p):
        if self._cur is not None:
            self._cur.append(("L", tuple(p)))

    def _curveToOne(self, p1, p2, p3):
        if self._cur is not None:
            self._cur.append(("C", tuple(p1), tuple(p2), tuple(p3)))

    def _closePath(self):
        self._finish()

    def _endPath(self):
        self._finish()

    def _finish(self):
        if self._cur and len(self._cur) > 1:
            self.contours.append(self._cur)
        self._cur = None


def flatten(contour, steps: int = 8) -> list[Point]:
    pts: list[Point] = []
    cur = contour[0][1]
    pts.append(cur)
    for seg in contour[1:]:
        if seg[0] == "L":
            cur = seg[1]
            pts.append(cur)
        else:
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = cur, seg[1], seg[2], seg[3]
            for i in range(1, steps + 1):
                t = i / steps
                mt = 1 - t
                a, b, c, d = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
                pts.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
            cur = seg[3]
    return pts


def signed_area(pts: list[Point]) -> float:
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def point_in_poly(x: float, y: float, pts: list[Point]) -> bool:
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            xc = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xc:
                inside = not inside
        j = i
    return inside


def reverse_contour(contour):
    """Same shape, opposite direction."""
    points_at = [contour[0][1]]
    for seg in contour[1:]:
        points_at.append(seg[-1])
    out = [("M", points_at[-1])]
    for i in range(len(contour) - 1, 0, -1):
        seg = contour[i]
        start = points_at[i - 1]
        if seg[0] == "L":
            out.append(("L", start))
        else:
            out.append(("C", seg[2], seg[1], start))
    return out


def normalize_directions(contours, min_area: float = 4.0):
    """Outer contours counter-clockwise, holes clockwise (PostScript/CFF
    convention), decided by how deeply each contour is nested. Drops
    degenerate slivers."""
    polys = [flatten(c) for c in contours]
    areas = [signed_area(p) for p in polys]
    keep = [i for i, a in enumerate(areas) if abs(a) >= min_area]
    out = []
    for i in keep:
        # a point just inside the contour's first vertex is representative
        x, y = polys[i][0]
        depth = 0
        for j in keep:
            if j != i and abs(areas[j]) > abs(areas[i]) and point_in_poly(x, y, polys[j]):
                depth += 1
        want_ccw = depth % 2 == 0
        is_ccw = areas[i] > 0
        out.append(contours[i] if want_ccw == is_ccw else reverse_contour(contours[i]))
    return out


def map_points(contours, fn):
    out = []
    for c in contours:
        nc = []
        for seg in c:
            nc.append((seg[0],) + tuple(fn(p) for p in seg[1:]))
        out.append(nc)
    return out


def bounds(contours):
    xs, ys = [], []
    for c in contours:
        for x, y in flatten(c, steps=6):
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def total_area(contours) -> float:
    return sum(signed_area(flatten(c)) for c in contours)


def draw(contours, pen, dx: float = 0.0, dy: float = 0.0):
    for c in contours:
        x, y = c[0][1]
        pen.moveTo((x + dx, y + dy))
        for seg in c[1:]:
            if seg[0] == "L":
                pen.lineTo((seg[1][0] + dx, seg[1][1] + dy))
            else:
                pen.curveTo(*[(p[0] + dx, p[1] + dy) for p in seg[1:]])
        pen.closePath()
