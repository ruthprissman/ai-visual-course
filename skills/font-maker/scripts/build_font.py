"""Build an installable font from scanned template pages or a folder of SVGs.

Usage:
  python build_font.py --scan <files or folders...> --name "<family>" --out <folder>
  python build_font.py --svg-dir <folder>           --name "<family>" --out <folder>

Options:
  --latin                 include English A-Z a-z (auto-detected from the page code / file names)
  --spacing tight|normal|airy   space around each letter (default normal)
  --sidebearing N         exact space on each side of a letter, font units (overrides --spacing)
  --space N               width of the word space, font units (overrides --spacing)
  --scale F               make every glyph bigger/smaller, e.g. 1.1 or 0.9 (default 1)
  --ttf                   also write a .ttf next to the .otf
  --debug                 save straightened pages with the box grid drawn on them (_debug folder)
  --no-specimen           skip specimen.html / preview.png

Output (in --out): <family>.otf, build_report.json, specimen.html, preview.png.
Status lines start with a tag: OK, FONT, PAGE, MISSING, FAINT, EDGE, CHECK, WARN, ERROR.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import fm_common as C
from fm_outline import bounds, draw, map_points

SPACING = {"tight": (25, 230), "normal": (55, 290), "airy": (95, 360)}   # (side bearing, space)
REGULAR_HEIGHT = set("אבגדהוזחטכמםנסעפצרשת")    # letters that sit between baseline and x-height


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def from_scans(paths: list[str], force_latin: bool, debug_dir: Path | None, report: dict):
    import fm_scan as S

    files, skipped = S.collect_inputs(paths)
    for f in skipped:
        C.say("WARN", f"{f.name}: iPhone HEIC photo - save it as JPG and try again")
        report["warnings"].append({"file": f.name, "reason": "heic"})
    if not files:
        C.say("ERROR", "NO_FILES: no scans (JPG / PNG / PDF) found")
        sys.exit(2)
    reads = []
    for f in files:
        try:
            images = S.load_images(f)
        except S.ScanError:
            C.say("ERROR", f"{f.name}: PDF_UNREADABLE - save the scan as JPG/PNG, or install pymupdf")
            report["warnings"].append({"file": f.name, "reason": "pdf_unreadable"})
            continue
        except Exception:
            C.say("ERROR", f"{f.name}: UNREADABLE image file")
            report["warnings"].append({"file": f.name, "reason": "unreadable"})
            continue
        for label, img in images:
            reads.append(S.read_page(label, img))
    if not reads:
        C.say("ERROR", "NO_PAGES: none of the files could be read")
        sys.exit(2)
    latin = force_latin or any(r.latin for r in reads)
    chars = C.charset(latin)
    n_pages = C.pages_needed(len(chars))
    seen = {r.page_no for r in reads if r.page_no}
    for r in reads:
        if r.page_no is None:
            free = [p for p in range(1, n_pages + 1) if p not in seen]
            r.page_no = free[0] if free else 1
            seen.add(r.page_no)
            r.notes.append("GUESSED_PAGE")
    cells: dict[str, object] = {}
    for r in reads:
        extra = []
        if r.rotation:
            extra.append(f"turned {r.rotation} deg")
        if "NO_MARKS" in r.notes:
            extra.append("NO_MARKS: corner squares not found, used the whole image")
        if "NO_PAGE_CODE" in r.notes:
            extra.append("NO_PAGE_CODE: page number unreadable")
        if "GUESSED_PAGE" in r.notes:
            extra.append(f"assumed page {r.page_no}")
        if r.page_no > n_pages:
            C.say("WARN", f"{r.label}: page {r.page_no} is not part of this template - skipped")
            continue
        C.say("PAGE", f"{r.label} -> page {r.page_no}/{n_pages}" + (f" ({'; '.join(extra)})" if extra else ""))
        report["pages"].append({"source": r.label, "page": r.page_no, "rotation": r.rotation, "notes": r.notes})
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            S.debug_overlay(r, chars).save(debug_dir / f"page{r.page_no}-{len(report['pages'])}.jpg", quality=85)
        rank = {"empty": 0, "faint": 1, "ok": 2}
        for cell in S.extract_cells(r, chars):
            prev = cells.get(cell.char)
            # newer scans win, but a pale or empty box never replaces a good one
            if prev is None or rank[cell.status] >= rank[prev.status]:
                cells[cell.char] = cell
    missing_pages = [p for p in range(1, n_pages + 1) if p not in seen]
    for p in missing_pages:
        C.say("MISSING", f"page {p} was not found among the scans")
    glyphs, problems = {}, []
    for ch in chars:
        cell = cells.get(ch)
        if cell is None:
            page = chars.index(ch) // C.PER_PAGE + 1
            problems.append(dict(char=ch, kind="missing", reason="page_not_scanned", page=page))
            continue
        if cell.status == "empty":
            problems.append(dict(char=ch, kind="missing", reason="empty_box", page=cell.page))
            continue
        glyphs[ch] = cell.contours
        if cell.status == "faint":
            problems.append(dict(char=ch, kind="faint", reason="very_light", page=cell.page))
        elif cell.light:
            problems.append(dict(char=ch, kind="faint", reason="light_ink", page=cell.page))
        for e in cell.edges:
            problems.append(dict(char=ch, kind="edge", reason=e, page=cell.page))
    return chars, glyphs, problems


def from_svgs(folder: str, force_latin: bool, report: dict):
    import fm_svg as V

    folder = Path(folder)
    if not folder.is_dir():
        C.say("ERROR", f"NO_FOLDER: {folder}")
        sys.exit(2)
    all_chars = C.charset(True)
    found, unknown, dups = V.read_svg_dir(folder, all_chars)
    latin = force_latin or any(ch in C.LATIN_UPPER or ch in C.LATIN_LOWER for ch in found)
    chars = C.charset(latin)
    C.say("PAGE", f"{len(found)} SVG files matched to characters in {folder.name}")
    for f in unknown:
        C.say("WARN", f"{f.name}: UNKNOWN_NAME - file name is not a character or a known name")
        report["warnings"].append({"file": f.name, "reason": "unknown_name"})
    for ch, old, new in dups:
        C.say("WARN", f"{C.describe(ch)}: two files ({old}, {new}) - using the newer one, {new}")
    glyphs, problems = {}, []
    for ch in chars:
        sg = found.get(ch)
        if sg is None:
            problems.append(dict(char=ch, kind="missing", reason="no_file"))
            continue
        if sg.contours:
            for note in sorted(sg.notes & {"stroke_only", "white_shapes", "no_artboard", "image", "use"}):
                kind = "check" if note in ("white_shapes", "no_artboard") else "svg"
                problems.append(dict(char=ch, kind=kind, reason=note, file=sg.path.name))
        else:
            reason = "stroke_only" if "stroke_only" in sg.notes else ("only_text" if "text" in sg.notes else
                                                                      "image_only" if "image" in sg.notes else "empty_svg")
            problems.append(dict(char=ch, kind="missing", reason=reason, file=sg.path.name))
            continue
        if sg.contours:
            glyphs[ch] = sg.contours
    return chars, glyphs, problems


# ---------------------------------------------------------------------------
# Font assembly
# ---------------------------------------------------------------------------


def _notdef(pen_factory, width=500):
    pen = pen_factory(width)
    for rect, rev in (((50, 0, 450, 700), False), ((100, 50, 400, 650), True)):
        x0, y0, x1, y1 = rect
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if rev:
            pts = pts[::-1]
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    return pen


def assemble(glyphs: dict, chars: list[str], family: str, out_dir: Path, sb: float, space: float,
             scale: float, want_ttf: bool) -> tuple[list[Path], dict]:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.t2CharStringPen import T2CharStringPen

    placed = {}     # char -> (contours shifted, advance)
    for ch in chars:
        if ch not in glyphs:
            continue
        cs = glyphs[ch]
        if scale != 1.0:
            cs = map_points(cs, lambda p: (p[0] * scale, p[1] * scale))
        b = bounds(cs)
        if b is None:
            continue
        dx = sb - b[0]
        cs = map_points(cs, lambda p, dx=dx: (p[0] + dx, p[1]))
        adv = max(1, round(b[2] - b[0] + 2 * sb))
        placed[ch] = (cs, adv, b)
    if not placed:
        C.say("ERROR", "NOTHING_TO_BUILD: no character had any drawing")
        sys.exit(3)

    order = [".notdef", "space"] + [C.glyph_name(ch) for ch in chars if ch in placed]
    cmap = {0x20: "space", 0xA0: "space"}
    for ch in placed:
        cmap[ord(ch)] = C.glyph_name(ch)
    aliases = {0x22: "״", 0x27: "׳", 0x05BE: "-"}     # keyboard " and ' ; Hebrew maqaf
    for cp, ch in aliases.items():
        if ch in placed and cp not in cmap:
            cmap[cp] = C.glyph_name(ch)

    ys_min = min(p[2][1] for p in placed.values())
    ys_max = max(p[2][3] for p in placed.values())
    ascent = max(round(ys_max) + 20, round(850 * scale))
    descent = min(round(ys_min) - 20, round(-300 * scale))
    heights = [placed[ch][2][3] for ch in placed if ch in REGULAR_HEIGHT]
    x_height = round(statistics.median(heights)) if heights else round(C.XHEIGHT_UNITS * scale)
    cap_src = [placed[ch][2][3] for ch in placed if ch in C.LATIN_UPPER or ch in C.DIGITS]
    cap_height = round(statistics.median(cap_src)) if cap_src else x_height

    ps = C.postscript_name(family)
    ps_family = ps.rsplit("-", 1)[0]
    stamp = time.strftime("%Y-%m-%d %H:%M")
    names = {
        "familyName": {"en": family, "he": family},
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{ps};{int(time.time())}",
        "fullName": {"en": family, "he": family},
        "version": f"Version 1.000; font-maker {stamp}",
        "psName": ps,
        "description": "Made with font-maker",
    }
    space_w = round(space * scale)
    written = []

    def common_tables(fb, metrics):
        fb.setupHorizontalMetrics(metrics)
        fb.setupHorizontalHeader(ascent=ascent, descent=descent, lineGap=0)
        fb.setupNameTable(names, mac=False)
        fb.setupOS2(
            version=4, achVendID="FMKR", usWeightClass=400, fsType=0,
            fsSelection=0x40 | 0x80,          # REGULAR | USE_TYPO_METRICS
            sTypoAscender=ascent, sTypoDescender=descent, sTypoLineGap=0,
            usWinAscent=ascent, usWinDescent=-descent,
            sxHeight=x_height, sCapHeight=cap_height,
            ulCodePageRange1=(1 << 0) | (1 << 5),     # Latin 1 + Hebrew (1255)
            ulCodePageRange2=0,
            usDefaultChar=0, usBreakChar=32, usMaxContext=0,
        )
        fb.setupPost()

    # --- OTF (CFF, cubic curves straight from potrace / Illustrator)
    fb = FontBuilder(C.UPM, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    charstrings, metrics = {}, {}
    nd = _notdef(lambda w: T2CharStringPen(w, None))
    charstrings[".notdef"] = nd.getCharString()
    metrics[".notdef"] = (500, 50)
    charstrings["space"] = T2CharStringPen(space_w, None).getCharString()
    metrics["space"] = (space_w, 0)
    for ch, (cs, adv, _b) in placed.items():
        pen = T2CharStringPen(adv, None)
        draw(cs, pen)
        bp = BoundsPen(None)
        draw(cs, bp)
        metrics[C.glyph_name(ch)] = (adv, round(bp.bounds[0]) if bp.bounds else 0)
        charstrings[C.glyph_name(ch)] = pen.getCharString()
    fb.setupCFF(ps, {"FullName": ps_family, "FamilyName": ps_family, "Weight": "Regular",
                     "version": "1.000"}, charstrings, {})
    common_tables(fb, metrics)
    base = C.safe_filename(family)
    otf = out_dir / f"{base}.otf"
    fb.save(str(otf))
    written.append(otf)

    # --- optional TTF (quadratic curves via cu2qu)
    if want_ttf:
        from fontTools.pens.cu2quPen import Cu2QuPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        fb2 = FontBuilder(C.UPM, isTTF=True)
        fb2.setupGlyphOrder(order)
        fb2.setupCharacterMap(cmap)
        tt_glyphs, metrics2 = {}, {}

        def tt_pen_glyph(cs):
            p = TTGlyphPen(None)
            draw(cs, Cu2QuPen(p, max_err=1.0, reverse_direction=True))
            return p.glyph()

        p = TTGlyphPen(None)
        _notdef(lambda w: Cu2QuPen(p, max_err=1.0, reverse_direction=True))
        tt_glyphs[".notdef"] = p.glyph()
        metrics2[".notdef"] = (500, 50)
        tt_glyphs["space"] = TTGlyphPen(None).glyph()
        metrics2["space"] = (space_w, 0)
        for ch, (cs, adv, _b) in placed.items():
            g = tt_pen_glyph(cs)
            tt_glyphs[C.glyph_name(ch)] = g
            metrics2[C.glyph_name(ch)] = (adv, 0)
        fb2.setupGlyf(tt_glyphs)
        glyf = fb2.font["glyf"]
        for gname in metrics2:
            g = glyf[gname]
            metrics2[gname] = (metrics2[gname][0], getattr(g, "xMin", 0) if g.numberOfContours else 0)
        common_tables(fb2, metrics2)
        ttf = out_dir / f"{base}.ttf"
        fb2.save(str(ttf))
        written.append(ttf)

    info = dict(ascent=ascent, descent=descent, x_height=x_height, cap_height=cap_height,
                sidebearing=sb, space=space_w, scale=scale, ps_name=ps)
    return written, info, placed


def sanity_checks(placed: dict, scale: float) -> list[dict]:
    """Letters much bigger/smaller than the rest, or floating off the line."""
    out = []
    regular = {ch: placed[ch][2] for ch in placed if ch in REGULAR_HEIGHT}
    if len(regular) < 5:
        return out
    hs = {ch: b[3] - b[1] for ch, b in regular.items()}
    med = statistics.median(hs.values())
    for ch, h in hs.items():
        if h > 1.45 * med:
            out.append(dict(char=ch, kind="check", reason="much_bigger"))
        elif h < 0.6 * med:
            out.append(dict(char=ch, kind="check", reason="much_smaller"))
    for ch, b in regular.items():
        if b[1] > 0.22 * med:
            out.append(dict(char=ch, kind="check", reason="floats_above_line"))
        elif b[1] < -0.3 * med:
            out.append(dict(char=ch, kind="check", reason="drops_below_line"))
    for ch in C.DESCENDERS:
        if ch in placed and placed[ch][2][1] > -0.1 * med:
            out.append(dict(char=ch, kind="check", reason="descender_not_below_line"))
    return out


REASONS = {
    "empty_box": "box is empty",
    "page_not_scanned": "page not scanned",
    "no_file": "no SVG file",
    "stroke_only": "drawn with lines only (stroke) - needs Object > Expand",
    "only_text": "the SVG holds live text, not shapes - needs Type > Create Outlines",
    "image_only": "the SVG holds a picture, not shapes",
    "empty_svg": "the SVG has no filled shapes",
    "very_light": "very light - traced anyway, a darker marker is better",
    "light_ink": "ink looks pale (pencil/light pen?) - check the preview",
    "top": "touches the TOP edge of its box - may be cut off",
    "bottom": "touches the BOTTOM edge of its box - may be cut off",
    "left": "touches the LEFT edge of its box - may be cut off",
    "right": "touches the RIGHT edge of its box - may be cut off",
    "white_shapes": "uses white shapes to erase - better to use Pathfinder > Minus Front",
    "no_artboard": "exported without the artboard - height guessed, re-export with 'Use Artboards'",
    "unreadable": "the SVG file is broken",
    "image": "also holds a picture, which was ignored",
    "use": "also holds an Illustrator symbol, which was ignored - break the link to the symbol",
    "much_bigger": "much bigger than the other letters",
    "much_smaller": "much smaller than the other letters",
    "floats_above_line": "floats above the baseline",
    "drops_below_line": "drops below the baseline",
    "descender_not_below_line": "should hang below the baseline but does not",
}
TAGS = {"missing": "MISSING", "faint": "FAINT", "edge": "EDGE", "svg": "WARN", "check": "CHECK"}


def main():
    C.setup_console()
    ap = argparse.ArgumentParser(description="Build a font from scans or SVGs")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--scan", nargs="+", help="scan files and/or folders")
    src.add_argument("--svg-dir", help="folder with one SVG per character")
    ap.add_argument("--name", required=True, help="font family name (Hebrew is fine)")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--latin", action="store_true")
    ap.add_argument("--spacing", choices=list(SPACING), default="normal")
    ap.add_argument("--sidebearing", type=float, default=None)
    ap.add_argument("--space", type=float, default=None)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--ttf", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--no-specimen", action="store_true")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"family": a.name, "source": "scan" if a.scan else "svg", "pages": [], "warnings": []}
    if a.scan:
        chars, glyphs, problems = from_scans(a.scan, a.latin, out / "_debug" if a.debug else None, report)
    else:
        chars, glyphs, problems = from_svgs(a.svg_dir, a.latin, report)

    sb_default, space_default = SPACING[a.spacing]
    sb = a.sidebearing if a.sidebearing is not None else sb_default * a.scale
    space = a.space / a.scale if a.space is not None else space_default
    written, info, placed = assemble(glyphs, chars, a.name, out, sb, space, a.scale, a.ttf)
    problems += sanity_checks(placed, a.scale)

    for f in written:
        C.say("FONT", str(f))
    C.say("OK", f"{len(placed)}/{len(chars)} characters in the font")
    grouped: dict[str, list] = {}
    for p in problems:
        if p["kind"] == "missing" and p["reason"] in ("no_file", "page_not_scanned"):
            grouped.setdefault(p["reason"], []).append(p["char"])
    grouped = {r: chs for r, chs in grouped.items() if len(chs) > 3}
    for reason, chs in grouped.items():
        C.say("MISSING", f"{len(chs)} characters - {REASONS[reason]}: {' '.join(chs)}")
    for p in problems:
        if p["kind"] == "missing" and p["reason"] in grouped:
            continue
        where = f" [page {p['page']}]" if p.get("page") else (f" [{p['file']}]" if p.get("file") else "")
        C.say(TAGS[p["kind"]], f"{C.describe(p['char'])} {C.hebrew_name(p['char'])}: "
                               f"{REASONS.get(p['reason'], p['reason'])}{where}")
    C.say("SIZE", f"letter height {info['x_height']} (guide line = {round(C.XHEIGHT_UNITS * a.scale)}), "
                  f"side space {round(info['sidebearing'])}, word space {info['space']}")

    report.update(
        font=[str(f) for f in written],
        characters=len(chars), built=len(placed),
        built_chars="".join(ch for ch in chars if ch in placed),
        missing="".join(p["char"] for p in problems if p["kind"] == "missing"),
        problems=[dict(p, name=C.latin_name(p["char"]), he_name=C.hebrew_name(p["char"]),
                       text=REASONS.get(p["reason"], p["reason"])) for p in problems],
        metrics=info,
    )
    if not a.no_specimen:
        import specimen

        html, png = specimen.make_specimen(written[0], out, a.name)
        C.say("SPECIMEN", str(html))
        C.say("PREVIEW", str(png))
        report.update(specimen=str(html), preview=str(png))
    (out / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
