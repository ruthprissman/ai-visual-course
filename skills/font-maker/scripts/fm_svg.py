"""Read one-SVG-per-character folders (Illustrator exports) into outlines.

The SVG artboard is the em box of glyph-template.svg: viewBox 0 0 1000 1250,
baseline at y=900. Anything drawn is placed relative to that baseline.
Only filled shapes count; guide lines, text and stroke-only paths are ignored
(stroke-only paths are reported, because they usually mean "forgot to
Expand").
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from fontTools.svgLib.path.shapes import PathBuilder

import fm_common as C
from fm_outline import ContourPen, bounds, map_points, normalize_directions, reverse_contour

SKIP_TAGS = {"defs", "clipPath", "mask", "symbol", "pattern", "linearGradient", "radialGradient",
             "filter", "metadata", "title", "desc", "style", "marker", "script", "foreignObject"}
SHAPE_TAGS = {"path", "rect", "circle", "ellipse", "polygon", "polyline"}
STYLE_PROPS = ("fill", "stroke", "display", "visibility", "fill-rule", "opacity", "fill-opacity")
INHERITED = ("fill", "stroke", "visibility", "fill-rule", "fill-opacity")

_NAMED = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "blue": (0, 0, 255),
          "green": (0, 128, 0), "gray": (128, 128, 128), "grey": (128, 128, 128)}


@dataclass
class SvgGlyph:
    char: str
    path: Path
    contours: list = field(default_factory=list)
    notes: set = field(default_factory=set)   # stroke_only, white_shapes, text, image, use, no_artboard


def _local(tag) -> str:
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else str(tag)


def _parse_css(text: str) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", text):
        props = _parse_decl(body)
        for s in sel.split(","):
            s = s.strip()
            if s.startswith(".") and re.fullmatch(r"\.[\w-]+", s):
                rules.setdefault(s[1:], {}).update(props)
    return rules


def _parse_decl(body: str) -> dict[str, str]:
    out = {}
    for part in body.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def _num(v, default=0.0) -> float:
    if v is None:
        return default
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)", str(v))
    return float(m.group(1)) if m else default


def _parse_transform(s: str | None) -> Transform:
    t = Transform()
    if not s:
        return t
    for name, args in re.findall(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", s):
        v = [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)]
        if name == "matrix" and len(v) == 6:
            t = t.transform(v)
        elif name == "translate" and v:
            t = t.translate(v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale" and v:
            t = t.scale(v[0], v[1] if len(v) > 1 else v[0])
        elif name == "rotate" and v:
            import math

            a = math.radians(v[0])
            if len(v) == 3:
                t = t.translate(v[1], v[2]).rotate(a).translate(-v[1], -v[2])
            else:
                t = t.rotate(a)
        elif name == "skewX" and v:
            import math

            t = t.skew(math.radians(v[0]), 0)
        elif name == "skewY" and v:
            import math

            t = t.skew(0, math.radians(v[0]))
    return t


def _color_lum(v: str) -> float | None:
    v = v.strip().lower()
    if v in _NAMED:
        r, g, b = _NAMED[v]
    elif re.fullmatch(r"#[0-9a-f]{3}", v):
        r, g, b = (int(c * 2, 16) for c in v[1:])
    elif re.fullmatch(r"#[0-9a-f]{6}", v):
        r, g, b = int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)
    elif v.startswith("rgb"):
        nums = [float(x) for x in re.findall(r"[\d.]+", v)[:3]]
        if len(nums) < 3:
            return None
        r, g, b = nums
    else:
        return None
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _is_guide(el) -> bool:
    for attr in ("id", "class", "data-name"):
        v = el.get(attr)
        if v and re.search(r"guide|קווי", v, re.I):
            return True
    return False


def _element_contours(el, xform: Transform) -> list:
    clean = ET.Element(el.tag, {k: v for k, v in el.attrib.items() if k != "transform"})
    pb = PathBuilder()
    try:
        if not pb.add_path_from_element(clean) or not pb.paths:
            return []
    except Exception:
        return []
    pen = ContourPen()
    tpen = TransformPen(pen, xform)
    for d in pb.paths:
        try:
            parse_path(d, tpen)
        except Exception:
            continue
    return pen.contours


def _guide_like(contours, box: tuple[float, float]) -> bool:
    """A long thin horizontal/vertical line, or the artboard frame."""
    b = bounds(contours)
    if not b:
        return True
    w, h = b[2] - b[0], b[3] - b[1]
    bw, bh = box
    return ((w > 0.8 * bw and h < 0.02 * bh) or (h > 0.8 * bh and w < 0.02 * bw)
            or (w > 0.95 * bw and h > 0.95 * bh))


def _collect(root, css: dict, to_font: Transform, notes: set, box: tuple[float, float]) -> list:
    """Walk the SVG and return the filled shapes as contours in font units."""
    shapes: list[tuple[list, bool]] = []    # (contours, is_eraser)

    def walk(el, ctm: Transform, style: dict):
        tag = _local(el.tag)
        if tag in SKIP_TAGS or _is_guide(el):
            return
        st = {k: v for k, v in style.items() if k in INHERITED}
        for prop in STYLE_PROPS:
            if el.get(prop) is not None:
                st[prop] = el.get(prop)
        for cls in (el.get("class") or "").split():
            st.update({k: v for k, v in css.get(cls, {}).items() if k in STYLE_PROPS})
        st.update({k: v for k, v in _parse_decl(el.get("style") or "").items() if k in STYLE_PROPS})
        if st.get("display") == "none" or st.get("visibility") in ("hidden", "collapse"):
            return
        if _num(st.get("opacity"), 1.0) == 0:
            return
        t = ctm.transform(_parse_transform(el.get("transform")))
        if tag in ("svg", "g", "a", "switch"):
            for child in el:
                walk(child, t, st)
            return
        if tag in ("text", "image", "use"):
            notes.add(tag)
            return
        if tag not in SHAPE_TAGS and tag != "line":
            return
        cs = _element_contours(el, to_font.transform(t))
        if not cs:
            return
        fill = "none" if tag == "line" else st.get("fill", "black").strip()
        if fill == "none" or _num(st.get("fill-opacity"), 1.0) == 0:
            # an outline-only shape: fine if it is a guide line or the frame,
            # otherwise the letter was drawn with strokes and never expanded
            if st.get("stroke", "none") not in ("none", "") and not _guide_like(cs, box):
                notes.add("stroke_only")
            return
        lum = _color_lum(fill)
        shapes.append((cs, lum is not None and lum > 0.85))

    walk(root, Transform(), {})
    contours = []
    for cs, eraser in shapes:
        cs = normalize_directions(cs)
        if eraser:
            if not contours:
                continue          # white shape behind everything: a background
            notes.add("white_shapes")
            cs = [reverse_contour(c) for c in cs]
        contours.extend(cs)
    return contours


def _to_font(k: float, vx: float, vy: float) -> Transform:
    """SVG user units (y down, artboard top = em-box top) -> font units."""
    return Transform(k, 0, 0, -k, -vx * k, C.BOX_TOP_UNITS + vy * k)


def _fills_viewbox(contours, w: float, h: float) -> bool:
    """True when the drawing touches all four artboard edges: the file was
    exported cropped to the artwork, not on the template artboard."""
    b = bounds(contours)
    if not b:
        return False
    tx, ty = 0.015 * w, 0.015 * h
    return (abs(b[0]) < tx and abs(b[2] - w) < tx and
            abs(b[3] - C.BOX_TOP_UNITS) < ty and abs(b[1] - (C.BOX_TOP_UNITS - h)) < ty)


def read_svg(path: Path, char: str) -> SvgGlyph:
    g = SvgGlyph(char=char, path=path)
    root = ET.parse(str(path)).getroot()
    css: dict = {}
    for el in root.iter():
        if _local(el.tag) == "style" and el.text:
            for k, v in _parse_css(el.text).items():
                css.setdefault(k, {}).update(v)
    vb = root.get("viewBox")
    if vb:
        vx, vy, vw, vh = [float(x) for x in re.split(r"[\s,]+", vb.strip())[:4]]
    else:
        vx, vy, vw, vh = 0.0, 0.0, _num(root.get("width"), 1000), _num(root.get("height"), 1250)
    template_ratio = C.UNITS_PER_BOX_H / C.BOX_W_UNITS
    on_artboard = vw > 0 and vh > 0 and abs((vh / vw) / template_ratio - 1) <= 0.04
    k = C.UNITS_PER_BOX_H / vh if on_artboard else 1.0
    contours = _collect(root, css, _to_font(k, vx, vy), g.notes, (vw * k, vh * k))
    if contours and on_artboard and _fills_viewbox(contours, vw * k, vh * k):
        on_artboard = False
        contours = _collect(root, css, _to_font(1.0, vx, vy), set(), (vw, vh))
    if contours and not on_artboard:
        # The baseline is unknown. Assume template units (1 unit = 1 font
        # unit) and stand the drawing on the baseline; letters with a tail
        # hang down to the descender line.
        g.notes.add("no_artboard")
        b = bounds(contours)
        floor = C.DESCENDER_GUIDE if char in C.DESCENDERS else 0
        contours = map_points(contours, lambda p, dy=floor - b[1]: (p[0], p[1] + dy))
    g.contours = contours
    return g


def read_svg_dir(folder: Path, chars: list[str]):
    """Returns (glyphs: dict char -> SvgGlyph, unknown: list[Path], duplicates: list)."""
    alias = C.build_alias_map(chars)
    glyphs: dict[str, SvgGlyph] = {}
    unknown, duplicates = [], []
    files = sorted((f for f in Path(folder).iterdir() if f.is_file() and f.suffix.lower() == ".svg"),
                   key=lambda f: (f.stat().st_mtime, f.name))
    for f in files:
        if f.stem.lower().startswith("glyph-template"):
            continue
        ch = C.resolve_svg_name(f.stem, chars, alias)
        if ch is None:
            unknown.append(f)
            continue
        try:
            sg = read_svg(f, ch)
        except ET.ParseError:
            sg = SvgGlyph(char=ch, path=f, notes={"unreadable"})
        if ch in glyphs:
            duplicates.append((ch, glyphs[ch].path.name, f.name))
        glyphs[ch] = sg      # newest file wins
    return glyphs, unknown, duplicates
