"""Turns a letter, a word or a short line into vector outlines (SVG paths) from a font in the skill.

For Illustrator: outlined text needs no installed font and always looks exactly like the preview.

    python text-to-path.py --font heebo --weight 600 --text "ת" --size 40 --fill "#B38C36" --id gold-tav --out "פרויקטים/<שם>/ת.svg"

--font    font file name as in assets/fonts (heebo, frank-ruhl-libre, assistant, bellefair ...)
--weight  300 / 400 / 600 / 700 ... (must exist in assets/fonts)
--size    font size in mm (the em square). A capital-height letter comes out at about 70% of it.
--fill    colour (explicit HEX, never a variable). Default #000000.
--id      group name, shows as the layer/group name in Illustrator.
--out     the SVG to write. Sized in mm to the ink of the text, with --pad mm around it (default 0).

Prints one JSON line: file and width/height in mm. A character the font lacks (Bellefair has no ״,
for example) stops it with exit code 3 and the missing characters: choose another font for that text.
The SVG holds one <g id> with one <path> per glyph, in mm. To place it inside another SVG,
copy the <g> and wrap it in transform="translate(x y)" (both in mm).

Needs: Python 3 + fonttools + brotli (pip install fonttools brotli). See references/build.md.
Hebrew is set right to left; digits and Latin runs inside it stay left to right. No kerning.
"""
import argparse
import json
import os
import sys
import unicodedata

try:
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.boundsPen import BoundsPen
except ImportError:
    print(json.dumps({"error": "missing fonttools", "fix": "python -m pip install --user fonttools brotli"}))
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")


def load(font, weight):
    """Both subsets (hebrew + latin) of one family/weight; each char goes to the subset that has it."""
    out = []
    for sub in ("hebrew", "latin"):
        p = os.path.join(FONTS, f"{font}-{sub}-{weight}.woff2")
        if os.path.exists(p):
            try:
                f = TTFont(p)
            except Exception as e:  # brotli missing gives an ImportError inside fontTools
                print(json.dumps({"error": f"cannot read {os.path.basename(p)}: {e}",
                                  "fix": "python -m pip install --user fonttools brotli"}))
                sys.exit(2)
            out.append(f)
    if not out:
        have = sorted({n.rsplit("-", 2)[0] + " " + n.rsplit("-", 1)[1].split(".")[0]
                       for n in os.listdir(FONTS) if n.endswith(".woff2")})
        print(json.dumps({"error": f"no font {font} {weight}", "available": have}, ensure_ascii=False))
        sys.exit(2)
    return out


def is_rtl(ch):
    return unicodedata.bidirectional(ch) in ("R", "AL")


def is_ltr(ch):
    return unicodedata.bidirectional(ch) in ("L", "EN", "AN")


def visual_order(text):
    """Very small bidi: a Hebrew line is right to left; runs of digits/Latin inside it keep their order."""
    if not any(is_rtl(c) for c in text):
        return list(text)
    runs, cur, cur_ltr = [], [], None
    for c in text:
        ltr = bool(is_ltr(c) or (cur_ltr and cur and c in ".,:/-"))  # 20:00, 1.5, 12/3 stay together
        if cur and ltr != cur_ltr:
            runs.append((cur_ltr, cur))
            cur = []
        cur_ltr = ltr
        cur.append(c)
    if cur:
        runs.append((cur_ltr, cur))
    vis = []
    for ltr, chars in reversed(runs):
        vis.extend(chars if ltr else reversed(chars))
    return vis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True)
    ap.add_argument("--weight", default="400")
    ap.add_argument("--text", required=True)
    ap.add_argument("--size", type=float, default=20)
    ap.add_argument("--fill", default="#000000")
    ap.add_argument("--id", default="text")
    ap.add_argument("--pad", type=float, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    fonts = load(a.font.lower().replace(" ", "-"), a.weight)
    upm = fonts[0]["head"].unitsPerEm
    k = a.size / upm  # font units -> mm
    asc = fonts[0]["hhea"].ascent

    glyphs, missing, x = [], [], 0.0
    for ch in visual_order(a.text):
        f = next((f for f in fonts if ord(ch) in f.getBestCmap()), None)
        if f is None:
            missing.append(ch)
            continue
        gs = f.getGlyphSet()
        name = f.getBestCmap()[ord(ch)]
        glyphs.append((gs, name, x))
        x += gs[name].width

    if missing or not glyphs:
        # never write a word with a hole in it: choose another font (or weight) for this text
        print(json.dumps({"error": f"missing in {a.font} {a.weight}", "missing": missing,
                          "fix": "another font for this text, e.g. heebo / assistant / frank-ruhl-libre"},
                         ensure_ascii=False))
        sys.exit(3)

    # ink bounds, in font units, y up
    bx0 = by0 = float("inf")
    bx1 = by1 = float("-inf")
    for gs, name, gx in glyphs:
        bp = BoundsPen(gs)
        gs[name].draw(TransformPen(bp, (1, 0, 0, 1, gx, 0)))
        if bp.bounds:
            x0, y0, x1, y1 = bp.bounds
            bx0, by0, bx1, by1 = min(bx0, x0), min(by0, y0), max(bx1, x1), max(by1, y1)
    if bx0 == float("inf"):  # only spaces
        bx0, by0, bx1, by1 = 0, 0, x, asc

    pad = a.pad
    w = (bx1 - bx0) * k + 2 * pad
    h = (by1 - by0) * k + 2 * pad
    paths = []
    for gs, name, gx in glyphs:
        sp = SVGPathPen(gs, ntos=lambda v: f"{v:.3f}".rstrip("0").rstrip("."))
        # font units (y up) -> mm (y down), ink top-left at (pad, pad)
        t = (k, 0, 0, -k, (gx - bx0) * k + pad, by1 * k + pad)
        gs[name].draw(TransformPen(sp, t))
        d = sp.getCommands()
        if d:
            paths.append(f'    <path d="{d}"/>')

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{w:.2f}mm" height="{h:.2f}mm" '
        f'viewBox="0 0 {w:.3f} {h:.3f}">\n'
        f'  <title>{a.text}</title>\n'
        f'  <g id="{a.id}" fill="{a.fill}">\n' + "\n".join(paths) + "\n  </g>\n</svg>\n"
    )
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(json.dumps({"file": a.out, "width_mm": round(w, 2), "height_mm": round(h, 2),
                      "glyphs": len(paths), "missing": missing}, ensure_ascii=False))


if __name__ == "__main__":
    main()
