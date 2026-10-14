# -*- coding: utf-8 -*-
"""Build the font family from <folder>/design.json.

    python build_font.py "<folder>"            all weights, test page, ZIP
    python build_font.py "<folder>" --quick    Regular only + test page (for proofs)

Writes <folder>/fonts/*.ttf + *.woff2, <folder>/index.html, <folder>/<Name>.zip
and <folder>/work/spacing.json. Prints short tagged lines (OK / WARN / ERROR).
"""
import argparse
import json
import math
import zipfile
from pathlib import Path

from fontTools.agl import UV2AGL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.maxContextCalc import maxCtxFont
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

import fm_core as core
import fm_page

UPM = 1000
TEST_WORDS = ["שמי אורלי", "תודה מכל הלב", "מילים טובות נכתבות מהלב", "צילום", "צוללת",
              "שלום לכם", "המלך הולך בדרך", "אוסף פרחים ליד העץ", "בית ספר לעיצוב",
              "כל הכבוד", "שנה טובה ומתוקה", "חג שמח", "ברכה והצלחה", "יום הולדת שמח",
              "ללמוד לכתוב", "נכנסים אל בית המלאכה", "גן קטן", "כסף", "ארץ", "מלך"]
LATIN_WORDS = ["Hello world", "minimum", "Typography", "handwritten letters"]


def gname(ch):
    if len(ch) > 1:  # "ל.alt"
        return gname(ch[0]) + ch[1:]
    cp = ord(ch)
    if cp < 0x250 and cp in UV2AGL:
        return UV2AGL[cp]
    return f"uni{cp:04X}"


def tt_glyph(path, shift):
    pen = TTGlyphPen(None)
    if path is not None:
        cu = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
        path.draw(TransformPen(cu, (1, 0, 0, 1, shift, 0)))
    return pen.glyph()


def notdef(xh):
    import pathops
    w, h, t = int(0.55 * xh), int(1.4 * xh), max(20, int(0.07 * xh))
    p = pathops.Path()
    pen = p.getPen()
    for (x0, y0, x1, y1, cw) in ((0, 0, w, h, False), (t, t, w - t, h - t, True)):
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if cw:
            pts.reverse()
        pen.moveTo(pts[0])
        for q in pts[1:]:
            pen.lineTo(q)
        pen.closePath()
    return p, w


def features(sp):
    lines = ["languagesystem DFLT dflt;", "languagesystem hebr dflt;", "languagesystem latn dflt;", ""]
    heb_lookups, lat_lookups = [], []
    hs = core.HEBREW + " "
    pairs = [(L, R, k) for (L, R), k in sorted(sp.kern.items()) if L[:1] in hs and R[:1] in hs]
    if pairs:
        lines.append("lookup HebrewPairs {")
        # RTL: the logically first glyph is the visual right one. Moving it
        # (placement) and its advance together changes only this gap and
        # never skips the next pair.
        for L, R, k in pairs:
            lines.append(f"  pos {gname(R)} {gname(L)} <{k} 0 {k} 0>;")
        lines.append("} HebrewPairs;")
        heb_lookups.append("HebrewPairs")
    by_len = {}
    for key, k in sp.guards.items():
        by_len.setdefault(len(key), []).append((key, k))
    for n in sorted(by_len):
        name = f"HebrewReach{n}"
        lines.append(f"lookup {name} {{")
        for key, k in sorted(by_len[n]):
            rest = " ".join(gname(c) for c in key[1:])
            lines.append(f"  pos {gname(key[0])}' <{k} 0 {k} 0> {rest};")
        lines.append(f"}} {name};")
        heb_lookups.append(name)
    lat = [(L, R, k) for (L, R), k in sorted(sp.kern.items()) if L[:1] not in hs and R[:1] not in hs]
    subs = []
    for base, ctx in sorted(sp.alt_ctx.items()):
        cls = " ".join(gname(c) for c in ctx) + " " + " ".join(gname(c + ".alt") for c in ctx if c + ".alt" in sp.shapes)
        subs.append(f"  sub [{cls.strip()}] {gname(base)}' by {gname(base + '.alt')};")
    if subs:
        lines.append("lookup Alternates {")
        lines.extend(subs)
        lines.append("} Alternates;")
    if lat:
        lines.append("lookup LatinPairs {")
        for L, R, k in lat:
            lines.append(f"  pos {gname(L)} {gname(R)} {k};")
        lines.append("} LatinPairs;")
        lat_lookups.append("LatinPairs")
    if not heb_lookups and not lat_lookups:
        return "\n".join(lines)
    lines.append("feature kern {")
    for script, looks in (("DFLT", heb_lookups + lat_lookups), ("hebr", heb_lookups), ("latn", lat_lookups)):
        lines.append(f"  script {script}; language dflt;")
        for lk in looks:
            lines.append(f"    lookup {lk};")
    lines.append("} kern;")
    if subs:
        lines.append("feature calt {")
        for script in ("DFLT", "hebr"):
            lines.append(f"  script {script}; language dflt;")
            lines.append("    lookup Alternates;")
        lines.append("} calt;")
    return "\n".join(lines) + "\n"


def name_records(design, weight, weights):
    fam = core.latin_name(design)
    heb = design["name"] if core.has_hebrew(design["name"]) else None
    ribbi = weight in ("Regular", "Bold")
    fam1 = fam if ribbi else f"{fam} {weight}"
    sub2 = weight if ribbi else "Regular"
    ps = f"{core.ps_name(fam)}-{core.ps_name(weight)}"
    version = design["version"]
    full = f"{fam} {weight}"
    eng = {
        "familyName": fam1, "styleName": sub2, "fullName": full, "psName": ps,
        "uniqueFontIdentifier": f"{version};NONE;{ps}", "version": f"Version {version}",
        "typographicFamily": fam, "typographicSubfamily": weight,
        "copyright": design.get("copyright", f"Copyright {design.get('author', '')}".strip()),
        "description": "Made with font-maker. Letterforms drawn as pen strokes; no outlines copied from other fonts.",
    }
    he = None
    if heb:
        he = {1: heb if ribbi else f"{heb} {weight}", 2: sub2, 4: f"{heb} {weight}", 16: heb, 17: weight}
    return eng, he, ps


def build_weight(design, weight, shapes, sp, chars, vm, out):
    xh = design["xh"]
    alts = sorted(k for k in shapes if k.endswith(".alt"))
    order = [".notdef"] + [gname(c) for c in chars] + [gname(k) for k in alts]
    nd_path, nd_w = notdef(xh)
    glyphs = {".notdef": tt_glyph(nd_path, int(0.08 * xh))}
    adv = {".notdef": nd_w + int(0.16 * xh)}
    for c in list(chars) + alts:
        lay = sp.layout[c]
        glyphs[gname(c)] = tt_glyph(shapes.get(c), lay["shift"])
        adv[gname(c)] = int(round(lay["adv"]))
    cmap = {ord(c): gname(c) for c in chars}
    if " " in chars:
        cmap[0xA0] = gname(" ")
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    metrics = {}
    for gn in order:
        g = glyf[gn]
        g.recalcBounds(glyf)
        metrics[gn] = (adv[gn], g.xMin if g.numberOfContours else 0)
    fb.setupHorizontalMetrics(metrics)
    asc, desc = vm
    fb.setupHorizontalHeader(ascent=asc, descent=-desc, lineGap=0)
    eng, he, ps = name_records(design, weight, design["weights"])
    fb.setupNameTable(eng, windows=True, mac=True)
    if he:
        for nid, s in he.items():
            fb.font["name"].setName(s, nid, 3, 1, 0x040D)
    wc = core.WEIGHT_CLASS.get(weight, 400)
    bold = weight == "Bold"
    fs = (1 << 7) | ((1 << 5) if bold else (1 << 6))  # USE_TYPO_METRICS + BOLD/REGULAR
    cap = int(round(max((shapes[c].bounds[3] for c in "HEIT0" if c in shapes), default=1.4 * xh)))
    fb.setupOS2(version=4, usWeightClass=wc, usWidthClass=5, fsType=0, fsSelection=fs,
                sTypoAscender=asc, sTypoDescender=-desc, sTypoLineGap=0,
                usWinAscent=asc, usWinDescent=desc, sxHeight=int(round(xh)), sCapHeight=cap,
                achVendID="NONE", usDefaultChar=0, usBreakChar=32)
    fb.setupPost(keepGlyphNames=True, underlinePosition=-int(0.25 * xh), underlineThickness=max(20, int(design["pen"]["width"])))
    fb.font["head"].fontRevision = float(design["version"])
    fb.font["head"].macStyle = 1 if bold else 0
    fea = features(sp)
    addOpenTypeFeaturesFromString(fb.font, fea)
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: 0x000A}
    fb.font["gasp"] = gasp
    os2 = fb.font["OS/2"]
    os2.recalcUnicodeRanges(fb.font)
    os2.recalcCodePageRanges(fb.font)
    if any(c in chars for c in core.LATIN_LOWER + core.LATIN_UPPER):
        os2.ulCodePageRange1 |= 1  # Latin 1 (the heuristic wants accented letters too)
    if any(c in chars for c in core.HEBREW):
        os2.ulCodePageRange1 |= 1 << 5  # Hebrew
    os2.recalcAvgCharWidth(fb.font)
    os2.usMaxContext = maxCtxFont(fb.font)
    fname = f"{ps}.ttf"
    fb.save(out / fname)
    try:
        web = TTFont(out / fname)
        web.flavor = "woff2"
        web.save(out / f"{ps}.woff2")
    except Exception as e:  # noqa: BLE001 - brotli missing: the TTF is still fine
        print(f"WARN no web font (WOFF2) for {weight}: {e.__class__.__name__}")
    (out.parent / "work" / f"features-{weight}.fea").write_text(fea, encoding="utf-8")
    return out / fname


def check_font(path, design, weight, chars):
    """Re-open the TTF and verify names, weight bits and metrics."""
    f = TTFont(path)
    problems = []
    name = f["name"]
    fam = core.latin_name(design)
    ribbi = weight in ("Regular", "Bold")
    exp1 = fam if ribbi else f"{fam} {weight}"
    exp2 = weight if ribbi else "Regular"
    if name.getName(1, 3, 1, 0x409).toUnicode() != exp1:
        problems.append("nameID1")
    if name.getName(2, 3, 1, 0x409).toUnicode() != exp2:
        problems.append("nameID2")
    if name.getName(16, 3, 1, 0x409).toUnicode() != fam:
        problems.append("nameID16")
    if not name.getName(6, 3, 1, 0x409).toUnicode().isascii():
        problems.append("PostScript name not ASCII")
    if core.has_hebrew(design["name"]) and not name.getName(1, 3, 1, 0x40D):
        problems.append("Hebrew name missing")
    os2 = f["OS/2"]
    if os2.usWeightClass != core.WEIGHT_CLASS.get(weight, 400):
        problems.append("usWeightClass")
    bold = weight == "Bold"
    if bool(os2.fsSelection & 32) != bold or bool(os2.fsSelection & 64) == bold or not os2.fsSelection & 128:
        problems.append("fsSelection")
    if bool(f["head"].macStyle & 1) != bold:
        problems.append("macStyle")
    if not os2.ulCodePageRange1 & (1 << 5) and any(c in core.HEBREW for c in chars):
        problems.append("Hebrew code page bit")
    hh = f["hhea"]
    if not (hh.ascent == os2.sTypoAscender == os2.usWinAscent and -hh.descent == -os2.sTypoDescender == os2.usWinDescent):
        problems.append("vertical metrics differ between tables")
    glyf = f["glyf"]
    ymax = max(glyf[g].yMax for g in f.getGlyphOrder() if glyf[g].numberOfContours)
    ymin = min(glyf[g].yMin for g in f.getGlyphOrder() if glyf[g].numberOfContours)
    if ymax > os2.usWinAscent or -ymin > os2.usWinDescent:
        problems.append("glyphs taller than the line (would clip)")
    cmap = f.getBestCmap()
    gs = f.getGlyphSet()
    for c in chars:
        if c == " ":
            continue
        gn = cmap.get(ord(c))
        if gn is None or not glyf[gn].numberOfContours:
            problems.append(f"empty glyph {c}")
            continue
        ap = AreaPen(gs)
        gs[gn].draw(ap)
        if ap.value > 0:
            problems.append(f"contour direction {c}")
    return problems


def spacing_report(design, sp, naive):
    words = TEST_WORDS + design.get("test_words", [])
    rep = {}
    for label, s in (("before", naive), ("after", sp)):
        g = s.word_gaps(" ".join(words))
        rep[label] = {"nearest": core.spread([x[1] for x in g]), "effective": core.spread([x[2] for x in g])}
    return rep


def naive_spacer(design, shapes, chars):
    """Plain box spacing (fixed margin around each letter, no kerning) as a
    baseline for the spacing report."""
    s = core.Spacer(design, shapes)
    m = 0.12 * design["xh"]
    for c in shapes:
        b = shapes[c].bounds if c != " " else None
        if not b or b[2] <= b[0]:
            s.layout[c] = dict(shift=0.0, adv=s.word)
        else:
            s.layout[c] = dict(shift=m - b[0], adv=b[2] - b[0] + 2 * m)
    return s


def make_shapes(design, drawn, pen):
    """Outlines of every drawn glyph (and its alternate) for one pen."""
    shapes = {c: core.outline(design, c, drawn[c], pen) for c in drawn}
    for c, g in drawn.items():
        if g.get("alt", {}).get("paths"):
            alt = {k: g[k] for k in ("frame", "baseline", "box", "slant", "pen_scale") if k in g}
            alt.update(g["alt"])
            shapes[c + ".alt"] = core.outline(design, c, alt, pen)
    return shapes


def space(design, shapes, chars):
    """Sidebearings, kerning, alternates and reach rules for one weight."""
    heb = [c for c in chars if c in core.HEBREW]
    lat = [c for c in chars if c in core.LATIN_LOWER + core.LATIN_UPPER]
    sp = core.Spacer(design, shapes)
    sp.set_metrics()
    sp.layout.setdefault(" ", dict(shift=0.0, adv=sp.word))
    heb_all = heb + [c + ".alt" for c in heb if c + ".alt" in shapes]
    sp.choose_alts(heb)
    sp.kern_all(heb_all, rtl=True)
    sp.kern_all(lat, rtl=False)
    sp.space_kern(heb_all, rtl=True)
    sp.guard_all(heb_all, heb_all + [" "])
    return sp


def main():
    core.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--quick", action="store_true", help="Regular only, no ZIP")
    a = ap.parse_args()
    folder = Path(a.folder).resolve()
    design = core.load_design(folder)
    (folder / "work").mkdir(exist_ok=True)
    fonts_dir = folder / "fonts"
    fonts_dir.mkdir(exist_ok=True)

    drawn = {c: g for c, g in design["glyphs"].items() if g.get("paths")}
    for c in list(drawn):
        if len(c) != 1:
            print(f'WARN skipped glyph key "{c}" (must be one character)')
            drawn.pop(c)
    chars = sorted(set(drawn) | {" "}, key=ord)
    missing = [c for c in core.HEBREW + core.DIGITS + core.PUNCT if c not in drawn]
    if missing:
        print("MISSING " + " ".join(missing))

    weights = list(design["weights"])
    if a.quick:
        weights = ["Regular"] if "Regular" in weights else weights[:1]
    built = {}
    for w in weights:
        pen = core.pen_for_weight(design, w)
        shapes = make_shapes(design, drawn, pen)
        for c, p in shapes.items():
            b = p.bounds
            if b[2] - b[0] <= 0:
                print(f'WARN glyph "{c}" came out empty')
            elif len(c) == 1 and core.looks_filled(design, c, drawn[c], pen, p):
                print(f'WARN glyph "{c}" looks filled in - check its path (a loop that crosses itself?)')
        built[w] = shapes
    ys = [p.bounds for shapes in built.values() for p in shapes.values() if p.bounds[2] > p.bounds[0]]
    ymax, ymin = max(b[3] for b in ys), min(b[1] for b in ys)
    pad = 0.04 * UPM
    asc, desc = int(math.ceil(ymax + pad)), int(math.ceil(-ymin + pad))
    if asc + desc < 1.2 * UPM:  # comfortable line height without a line gap
        extra = int(1.2 * UPM - asc - desc)
        asc, desc = asc + extra // 2, desc + extra - extra // 2

    results, report = [], {}
    heb = [c for c in chars if c in core.HEBREW]
    for w in weights:
        shapes = built[w]
        sp = space(design, shapes, chars)
        path = build_weight(design, w, shapes, sp, chars, (asc, desc), fonts_dir)
        problems = check_font(path, design, w, chars)
        if w == "Regular" or len(weights) == 1:
            report = spacing_report(design, sp, naive_spacer(design, shapes, chars))
            report["pairs"] = len(sp.kern)
            report["reach_rules"] = len(sp.guards)
            report["alternates"] = {k: "".join(v) for k, v in sp.alt_ctx.items()}
            report["wide_pairs"] = sp.wide_pairs(heb)
        tag = "OK" if not problems else "WARN"
        print(f"{tag} {path.name}: {len(chars)} chars, {len(sp.kern)} pairs, {len(sp.guards)} reach rules"
              + ("" if not problems else " | " + ", ".join(problems)))
        results.append((w, path))
    (folder / "work" / "spacing.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if report and report["before"]["nearest"] and report["after"]["nearest"]:
        for kind in ("nearest", "effective"):
            b, f = report["before"][kind], report["after"][kind]
            print(f"SPACING {kind} gap (font units): plain spacing {b['mean']}±{b['std']} (IQR {b['iqr']}) -> "
                  f"this font {f['mean']}±{f['std']} (IQR {f['iqr']})")
    if report.get("wide_pairs"):
        print("WIDE " + " ".join(report["wide_pairs"]) + "  (a reaching stroke meets a tall letter; an 'alt' with a shorter stroke can close these)")
    if report.get("alternates"):
        print("ALT " + "  ".join(f"{k} after {v}" for k, v in report["alternates"].items()))
    page = fm_page.make_page(folder, design, results, chars)
    print(f"PAGE {page}")
    if not a.quick:
        fam = core.ps_name(core.latin_name(design))
        zpath = folder / f"{fam}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for w, p in results:
                z.write(p, f"{fam}/{p.name}")
                if p.with_suffix(".woff2").exists():
                    z.write(p.with_suffix(".woff2"), f"{fam}/web/{p.with_suffix('.woff2').name}")
            z.write(page, f"{fam}/index.html")
        print(f"ZIP {zpath}")


if __name__ == "__main__":
    main()
