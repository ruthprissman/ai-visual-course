"""Specimen page (HTML, font embedded) and a PNG preview of a built font.

Usage:
  python specimen.py --font "<file.otf>" [--out <folder>] [--name "<family>"]

specimen.html - right-to-left page: the name, a pangram at 96/64/40/24/16 px,
                every character, sample sentences. Open it in any browser.
preview.png   - a glyph grid with the baseline drawn in red and the
                x-height in blue, plus sample lines, for a quick visual check.
"""
from __future__ import annotations

import argparse
import base64
import html
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

import fm_common as C

PANGRAM = "עטלף אבק נס דרך מזגן שהתפוצץ כי חם"
SENTENCES = [
    "הפונט הזה נכתב ביד, נסרק והפך לגופן אמיתי: אפשר לכתוב בו כותרות, הזמנות ופוסטים!",
    "כמה עולה ג׳ירפה? בערך 1,250 ש״ח (כולל משלוח); הזמנה עד 31.12 - בלבד.",
]
LATIN_SAMPLES = ["The quick brown fox jumps over the lazy dog.", "SPHINX OF BLACK QUARTZ, JUDGE MY VOW!"]


def _family(tt: TTFont) -> str:
    return tt["name"].getDebugName(1) or "My Font"


def _wrap_missing(text: str, cmap: dict) -> str:
    out = []
    for ch in text:
        if ch == " " or ord(ch) in cmap:
            out.append(html.escape(ch))
        else:
            out.append(f'<span class="miss" title="missing">{html.escape(ch)}</span>')
    return "".join(out)


def make_html(font_path: Path, out_dir: Path, family: str, chars: list[str], cmap: dict) -> Path:
    b64 = base64.b64encode(font_path.read_bytes()).decode("ascii")
    fmt, mime = ("opentype", "font/otf") if font_path.suffix.lower() == ".otf" else ("truetype", "font/ttf")
    has_latin = any(ord(c) in cmap for c in C.LATIN_LOWER + C.LATIN_UPPER)
    missing = [c for c in chars if ord(c) not in cmap]
    sizes = "".join(
        f'<div class="row"><span class="lab"><bdi>{s}px</bdi></span>'
        f'<p class="f" style="font-size:{s}px">{_wrap_missing(PANGRAM, cmap)}</p></div>'
        for s in (96, 64, 40, 24, 16)
    )
    tiles = "".join(
        f'<div class="tile{" gone" if ord(c) not in cmap else ""}"><div class="f g" dir="ltr">{html.escape(c)}</div>'
        f'<div class="n"><bdi>{html.escape(C.latin_name(c))}</bdi></div></div>'
        for c in chars
    )
    sentences = "".join(f'<p class="f para">{_wrap_missing(s, cmap)}</p>' for s in SENTENCES)
    latin = ""
    if has_latin:
        latin = "<h2>אנגלית</h2>" + "".join(
            f'<p class="f para" dir="ltr" lang="en">{_wrap_missing(s, cmap)}</p>' for s in LATIN_SAMPLES)
    miss_note = ""
    if missing:
        miss_note = ('<p class="warn">חסרים בפונט: <bdi>' + html.escape(" ".join(missing)) +
                     "</bdi>. בטקסט הם מסומנים באדום.</p>")
    page = f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(family)} · דוגמת פונט</title>
<style>
@font-face {{ font-family: "FM Specimen"; src: url(data:{mime};base64,{b64}) format("{fmt}"); }}
:root {{ --ink:#1f1d1a; --muted:#6f6a63; --line:#e6e1d9; --bg:#fbf9f5; --card:#ffffff; --miss:#fde2e2; --missink:#b42318; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI", Arial, sans-serif; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:40px 16px 64px; }}
.f {{ font-family:"FM Specimen", sans-serif; }}
h1 {{ font-weight:normal; font-size:96px; line-height:1.25; margin:0 0 4px; }}
.sub {{ color:var(--muted); margin:0 0 32px; font-size:15px; }}
h2 {{ font-size:15px; letter-spacing:.02em; color:var(--muted); font-weight:600; margin:40px 0 12px; }}
.row {{ display:flex; gap:16px; align-items:baseline; border-top:1px solid var(--line); padding:10px 0; }}
.row p {{ margin:0; line-height:1.3; overflow-wrap:anywhere; }}
.lab {{ flex:none; width:56px; color:var(--muted); font-size:13px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(92px, 1fr)); gap:8px; }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:10px; text-align:center; padding:6px 4px 8px; }}
.tile .g {{ font-size:56px; line-height:1.35; }}
.tile .n {{ font-size:11px; color:var(--muted); }}
.tile.gone {{ background:var(--miss); }}
.tile.gone .g {{ color:var(--missink); font-family:sans-serif; opacity:.5; }}
.para {{ font-size:32px; line-height:1.5; margin:0 0 12px; }}
.miss {{ background:var(--miss); color:var(--missink); font-family:sans-serif; }}
.warn {{ background:var(--miss); color:var(--missink); padding:10px 14px; border-radius:8px; }}
footer {{ margin-top:48px; color:var(--muted); font-size:14px; border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:600px) {{ h1 {{ font-size:56px; }} .lab {{ width:44px; }} }}
</style>
</head>
<body>
<main class="wrap">
<h1 class="f">{_wrap_missing(family, cmap)}</h1>
<p class="sub"><bdi>{html.escape(family)}</bdi> · {len(chars) - len(missing)} מתוך {len(chars)} תווים</p>
{miss_note}
<h2>גדלים</h2>
{sizes}
<h2>כל התווים</h2>
<div class="grid">{tiles}</div>
<h2>משפטים לדוגמה</h2>
{sentences}
<p class="f para">0123456789 . , ! ? - : ; ( ) ״ ׳</p>
{latin}
<footer>להתקנה: קליק ימני על קובץ הפונט, ואז "התקנה". אחרי ההתקנה סוגרים ופותחים מחדש את פוטושופ או אילוסטרייטור.</footer>
</main>
</body>
</html>
"""
    path = out_dir / "specimen.html"
    path.write_text(page, encoding="utf-8")
    return path


def make_png(font_path: Path, out_dir: Path, family: str, chars: list[str], cmap: dict, tt: TTFont) -> Path:
    W, margin = 1640, 20
    cols, cell_w, cell_h = 10, 160, 205
    em = 120                                   # px per em in the grid
    k = em / tt["head"].unitsPerEm
    x_height = getattr(tt["OS/2"], "sxHeight", 0) or C.XHEIGHT_UNITS
    rows = (len(chars) + cols - 1) // cols
    samples = [(PANGRAM, 64), (SENTENCES[0], 34), (SENTENCES[1], 34)]
    if any(ord(c) in cmap for c in C.LATIN_LOWER):
        samples.append((LATIN_SAMPLES[0], 40))
    H = 90 + rows * cell_h + 30 + sum(int(s * 1.6) for _, s in samples) + 30
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    ui_path = C.find_ui_font()
    ui = C.pil_font(ui_path, 18)
    ui_small = C.pil_font(ui_path, 12)
    ui_big = C.pil_font(C.find_ui_font(bold=True) or ui_path, 30)
    f_grid = C.pil_font(font_path, em)
    d.text((W - margin, 45), C.visual_order(f"{family} · תצוגה מקדימה"), font=ui_big, fill=(30, 30, 30), anchor="rm")
    d.text((margin, 45), "red = baseline   blue = x-height   orange box = glyph leaves its cell",
           font=ui, fill=(110, 110, 110), anchor="lm")
    top0 = 90
    for i, ch in enumerate(chars):
        r, c = divmod(i, cols)
        x0 = W - margin - (c + 1) * cell_w          # right-to-left, like the template
        y0 = top0 + r * cell_h
        base = y0 + 28 + round(950 * k)
        d.rectangle([x0, y0, x0 + cell_w - 6, y0 + cell_h - 6], outline=(225, 225, 225))
        d.text((x0 + cell_w - 12, y0 + 6), ch, font=ui, fill=(120, 120, 120), anchor="ra")
        d.text((x0 + 6, y0 + 8), C.latin_name(ch), font=ui_small, fill=(160, 160, 160), anchor="la")
        d.line([x0 + 4, base, x0 + cell_w - 10, base], fill=(225, 50, 50), width=2)
        xh = base - round(x_height * k)
        d.line([x0 + 4, xh, x0 + cell_w - 10, xh], fill=(90, 150, 240), width=2)
        if ord(ch) not in cmap:
            d.text((x0 + (cell_w - 6) / 2, y0 + cell_h / 2), C.visual_order("חסר"), font=ui_big,
                   fill=(200, 40, 40), anchor="mm")
            continue
        adv = f_grid.getlength(ch)
        gx = x0 + (cell_w - 6) / 2 - adv / 2
        d.text((gx, base), ch, font=f_grid, fill=(0, 0, 0), anchor="ls")
        bb = d.textbbox((gx, base), ch, font=f_grid, anchor="ls")
        if bb[0] < x0 or bb[2] > x0 + cell_w - 6 or bb[1] < y0 + 22 or bb[3] > y0 + cell_h - 6:
            d.rectangle([x0, y0, x0 + cell_w - 6, y0 + cell_h - 6], outline=(240, 140, 0), width=3)
    y = top0 + rows * cell_h + 30
    for text, size in samples:
        f = C.pil_font(font_path, size)
        line = text if text.isascii() else C.visual_order(text)
        anchor_x = margin if text.isascii() else W - margin
        d.text((anchor_x, y + size), line, font=f, fill=(0, 0, 0), anchor="ls" if text.isascii() else "rs")
        y += int(size * 1.6)
    path = out_dir / "preview.png"
    im.save(path)
    return path


def make_specimen(font_path, out_dir, family: str | None = None):
    font_path, out_dir = Path(font_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tt = TTFont(str(font_path))
    cmap = tt.getBestCmap()
    family = family or _family(tt)
    latin = any(ord(c) in cmap for c in C.LATIN_UPPER + C.LATIN_LOWER)
    chars = C.charset(latin)
    return (make_html(font_path, out_dir, family, chars, cmap),
            make_png(font_path, out_dir, family, chars, cmap, tt))


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description="Specimen page and preview for a font")
    ap.add_argument("--font", required=True)
    ap.add_argument("--out", default=None, help="folder (default: next to the font)")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    font = Path(a.font)
    html_path, png = make_specimen(font, Path(a.out) if a.out else font.parent, a.name)
    C.say("SPECIMEN", str(html_path))
    C.say("PREVIEW", str(png))


if __name__ == "__main__":
    main()
