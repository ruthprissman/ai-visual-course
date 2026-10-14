"""Make the templates for font-maker.

  scan (default): printable A4 pages (PDF + one PNG per page). Every box has
                  its character printed small and light above it, a light-blue
                  baseline and a dashed x-height line (both drop out when the
                  font is built), four black corner squares for straightening
                  the scan, and a page code + page number.
  svg:            glyph-template.svg for Illustrator (one em box with
                  baseline / x-height / ascender / descender guides) and
                  svg-file-names.txt (which file name to give each character).

Usage:
  python make_template.py --out "<folder>" [--latin] [--kind scan|svg|both] [--name "<font name>"]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

import fm_common as C

INK = (0, 0, 0)
LABEL = (120, 120, 120)
LABEL_LIGHT = (165, 165, 165)
BOX = (165, 195, 235)
BASELINE = (140, 190, 245)
XLINE = (160, 205, 248)
TEXT = (60, 60, 60)


def _font(size_px: int, bold: bool = False):
    return C.pil_font(C.find_ui_font(bold=bold), size_px)


def _dashed(d: ImageDraw.ImageDraw, x0, x1, y, color, width, on=18, off=14):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + on, x1), y)], fill=color, width=width)
        x += on + off


def draw_page(page_no: int, n_pages: int, chars: list[str], latin: bool, name: str | None) -> Image.Image:
    im = Image.new("RGB", (C.PAGE_W, C.PAGE_H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    mm = C.mm

    # registration marks
    half = mm(C.MARK_SIZE_MM) / 2
    for cx, cy in C.MARK_CENTERS_MM:
        d.rectangle([mm(cx) - half, mm(cy) - half, mm(cx) + half, mm(cy) + half], fill=INK)

    # page code
    sq = mm(C.CODE_SQ_MM) / 2
    for bit, (cx, cy) in zip(C.encode_page_code(page_no, latin), C.code_square_centers_mm()):
        if bit:
            d.rectangle([mm(cx) - sq, mm(cy) - sq, mm(cx) + sq, mm(cy) + sq], fill=INK)

    # header
    title = f"תבנית פונט · עמוד {page_no} מתוך {n_pages}"
    if name:
        title = f"{name} · " + title
    d.text((C.PAGE_W / 2, mm(25.5)), C.visual_order(title), font=_font(round(mm(4.6)), bold=True),
           fill=TEXT, anchor="mm")
    small = _font(round(mm(3.0)))
    lines = [
        "כתבי כל תו בתוך המשבצת שלו, בטוש שחור. האותיות עומדות על הקו הכחול הרציף.",
        "הקו המקווקו הוא גובה האות. ק ך ן ף ץ יורדות מתחת לקו, ל עולה מעליו. לא לצאת מהמשבצת.",
    ]
    for i, line in enumerate(lines):
        d.text((C.PAGE_W / 2, mm(31.0 + i * 4.3)), C.visual_order(line), font=small, fill=TEXT, anchor="mm")

    # boxes
    label_font = _font(round(mm(4.4)), bold=True)
    name_font = _font(round(mm(2.6)))
    first = (page_no - 1) * C.PER_PAGE
    for slot in range(C.PER_PAGE):
        idx = first + slot
        if idx >= len(chars):
            break
        ch = chars[idx]
        l, t, r, b = C.box_rect_px(slot)
        d.rectangle([l, t, r, b], outline=BOX, width=3)
        base_y = t + (C.BOX_TOP_UNITS / C.UNITS_PER_BOX_H) * (b - t)
        x_y = t + ((C.BOX_TOP_UNITS - C.XHEIGHT_UNITS) / C.UNITS_PER_BOX_H) * (b - t)
        d.line([(l + 4, base_y), (r - 4, base_y)], fill=BASELINE, width=5)
        _dashed(d, l + 4, r - 4, x_y, XLINE, 3)
        label_y = t - mm(1.2)
        d.text((r, label_y), ch, font=label_font, fill=LABEL, anchor="rs")
        if ch in C.PUNCT:
            w = d.textlength(ch, font=label_font)
            d.text((r - w - mm(2), label_y), C.visual_order(C.hebrew_name(ch)), font=name_font,
                   fill=LABEL_LIGHT, anchor="rs")

    # footer
    foot = _font(round(mm(3.0)))
    d.text((C.PAGE_W / 2, mm(268)), C.visual_order(f"עמוד {page_no} מתוך {n_pages}"),
           font=_font(round(mm(3.6)), bold=True), fill=TEXT, anchor="mm")
    d.text((C.PAGE_W / 2, mm(274)),
           C.visual_order("סורקים את כל הדף, עם ארבעת הריבועים השחורים בפינות. לא לכתוב עליהם."),
           font=foot, fill=TEXT, anchor="mm")
    return im


def make_scan_template(out: Path, latin: bool, name: str | None) -> list[Path]:
    chars = C.charset(latin)
    n = C.pages_needed(len(chars))
    pages = [draw_page(p, n, chars, latin, name) for p in range(1, n + 1)]
    written = []
    pdf = out / "font-template.pdf"
    pages[0].save(pdf, "PDF", save_all=True, append_images=pages[1:], resolution=C.DPI, quality=92)
    written.append(pdf)
    for i, im in enumerate(pages, 1):
        p = out / f"font-template-page-{i}.png"
        im.save(p, dpi=(C.DPI, C.DPI))
        written.append(p)
    return written


def svg_template_text() -> str:
    w, h = int(C.BOX_W_UNITS), int(C.UNITS_PER_BOX_H)
    y = lambda units: C.BOX_TOP_UNITS - units      # font units -> svg y
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- font-maker glyph template. Draw ONE character as filled black shapes.
     The artboard is the em box: keep it as is and export with "Use Artboards".
     Red line = baseline (letters stand on it). Blue dashed = x-height (top of a
     regular Hebrew letter). Dotted lines = ascender (top of ל) and descender
     (bottom of ק ך ן ף ץ). The "guides" layer is ignored by the font builder. -->
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <g id="guides">
    <rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="none" stroke="#a5c3eb" stroke-width="2"/>
    <line x1="0" y1="{y(0)}" x2="{w}" y2="{y(0)}" fill="none" stroke="#e5484d" stroke-width="3"/>
    <line x1="0" y1="{y(C.XHEIGHT_UNITS)}" x2="{w}" y2="{y(C.XHEIGHT_UNITS)}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="16 10"/>
    <line x1="0" y1="{y(C.ASCENDER_GUIDE)}" x2="{w}" y2="{y(C.ASCENDER_GUIDE)}" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4 8"/>
    <line x1="0" y1="{y(C.DESCENDER_GUIDE)}" x2="{w}" y2="{y(C.DESCENDER_GUIDE)}" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4 8"/>
    <text x="12" y="{y(0) - 10}" font-family="Arial" font-size="22" fill="#e5484d">baseline</text>
    <text x="12" y="{y(C.XHEIGHT_UNITS) - 10}" font-family="Arial" font-size="22" fill="#3b82f6">x-height</text>
    <text x="12" y="{y(C.ASCENDER_GUIDE) - 10}" font-family="Arial" font-size="22" fill="#94a3b8">ascender</text>
    <text x="12" y="{y(C.DESCENDER_GUIDE) - 10}" font-family="Arial" font-size="22" fill="#94a3b8">descender</text>
  </g>
</svg>
"""


def make_svg_template(out: Path, latin: bool) -> list[Path]:
    svg = out / "glyph-template.svg"
    svg.write_text(svg_template_text(), encoding="utf-8")
    names = out / "svg-file-names.txt"
    rows = ["Character -> file name (either form works; English is safest)", ""]
    for ch in C.charset(latin):
        alt = "" if ch in '.?:' or ch in C.LATIN_UPPER else f"{ch}.svg"
        rows.append(f"{ch}\t{C.latin_name(ch)}.svg\t{alt}")
    names.write_text("\n".join(rows) + "\n", encoding="utf-8-sig")
    return [svg, names]


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description="Make font-maker templates")
    ap.add_argument("--out", default=".", help="folder for the template files")
    ap.add_argument("--latin", action="store_true", help="add English A-Z a-z")
    ap.add_argument("--kind", choices=["scan", "svg", "both"], default="scan")
    ap.add_argument("--name", default=None, help="font name to print in the page header")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    if a.kind in ("scan", "both"):
        written += make_scan_template(out, a.latin, a.name)
    if a.kind in ("svg", "both"):
        written += make_svg_template(out, a.latin)
    n_chars = len(C.charset(a.latin))
    C.say("OK", f"{n_chars} characters, {C.pages_needed(n_chars)} pages" if a.kind != "svg" else f"{n_chars} characters")
    for p in written:
        C.say("FILE", str(p))


if __name__ == "__main__":
    main()
