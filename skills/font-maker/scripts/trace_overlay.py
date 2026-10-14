# -*- coding: utf-8 -*-
"""Contact sheet: every traced letter drawn in red over its piece of the scan,
so the tracing can be checked by eye (shape, size, slant, where it starts and
ends). Letters without a scan box (designed ones) are shown in black.

    python trace_overlay.py "<font folder>" [--only "אבג"] [--out <png>]
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

import fm_core as core

CELL_H = 300
LABEL_H = 34


def polylines(paths, m):
    pen = core._FlattenPen(0.6)
    tp = TransformPen(pen, m)
    for d in paths:
        parse_path(d, tp)
    return [c for c in pen.contours if c]


def main():
    core.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--only")
    ap.add_argument("--out")
    ap.add_argument("--cols", type=int, default=6)
    a = ap.parse_args()
    folder = Path(a.folder)
    d = core.load_design(folder)
    glyphs = d["glyphs"]
    chars = [c for c in glyphs if glyphs[c].get("paths") and (not a.only or c in a.only)]
    chars = [c for c in chars if core.glyph_frame(d, glyphs[c]) == "scan"] or chars
    if not chars:
        core.fail("nothing to show (no traced letters yet)")
    scan = core.load_scan(folder / d["scan"]) if d.get("scan") else None
    pen_px = d["pen"]["width"] / d["scale"]
    margin = max(4, int(d.get("x_height", 30) * 0.35))
    font = core.hebrew_font(22)
    small = core.hebrew_font(14)
    cells = []
    items = []
    for c in chars:
        items.append((c, glyphs[c]))
        if glyphs[c].get("alt", {}).get("paths"):  # the alternate form, next to its letter
            alt = {k: glyphs[c][k] for k in ("frame", "baseline", "slant") if k in glyphs[c]}
            alt.update(glyphs[c]["alt"], designed=True, **{"from": c})
            items.append((c + " alt", alt))
    for c, g in items:
        box = g.get("box")
        if not box and g.get("from") in glyphs and glyphs[g["from"]].get("box"):
            base = glyphs[g["from"]]
            # show the designed letter next to the letter it was made from
            box = list(base["box"])
        lines = polylines(g["paths"], (1, 0, 0, 1, 0, 0))
        pts = np.array([p for ln in lines for p in ln])
        if box and not g.get("box"):
            bx0, by0, bx1, by1 = box  # a designed letter drawn somewhere else: show it on its own
            if pts[:, 0].max() < bx0 or pts[:, 0].min() > bx1 or pts[:, 1].max() < by0 or pts[:, 1].min() > by1:
                box = None
        if box:
            x0, y0, x1, y1 = box
            x0, y0 = min(x0, pts[:, 0].min()), min(y0, pts[:, 1].min())
            x1, y1 = max(x1, pts[:, 0].max()), max(y1, pts[:, 1].max())
        else:
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
        x0, y0, x1, y1 = int(x0 - margin), int(y0 - margin), int(x1 + margin), int(y1 + margin)
        z = CELL_H / max(1, (y1 - y0))
        w = max(int((x1 - x0) * z), 120)
        cell = Image.new("RGB", (w, CELL_H + LABEL_H), "white")
        dr = ImageDraw.Draw(cell, "RGBA")
        designed = not g.get("box")
        if scan is not None and not designed:
            crop = scan.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * z), CELL_H), Image.LANCZOS)
            cell.paste(crop, (0, LABEL_H))
        base = g.get("baseline")
        if base is not None:
            Y = (base - y0) * z + LABEL_H
            dr.line([(0, Y), (w, Y)], fill=(0, 160, 60, 200), width=2)
        if designed and box and g.get("from") in glyphs and scan is not None and glyphs[g["from"]].get("box"):
            # faint picture of the base letter, for comparison
            crop = scan.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * z), CELL_H), Image.LANCZOS)
            faint = Image.blend(Image.new("RGB", crop.size, "white"), crop, 0.35)
            cell.paste(faint, (0, LABEL_H))
            if base is not None:
                dr.line([(0, Y), (w, Y)], fill=(0, 160, 60, 200), width=2)
        width = max(1, int(round(pen_px * z)))
        color = (0, 0, 0, 200) if designed else (230, 20, 20, 110)
        for ln in lines:
            q = [((x - x0) * z, (y - y0) * z + LABEL_H) for x, y in ln]
            if len(q) > 1:
                dr.line(q, fill=color, width=width, joint="curve")
            r = width / 2
            for (X, Y2) in (q[0], q[-1]):
                dr.ellipse([X - r, Y2 - r, X + r, Y2 + r], fill=color)
            dr.line(q, fill=(200, 0, 0, 255) if not designed else (255, 255, 255, 230), width=1)
            sx, sy = q[0]
            dr.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], outline=(0, 90, 255, 255), width=2)
        dr.rectangle([0, 0, w, LABEL_H - 1], fill=(245, 242, 235, 255))
        src = g.get("from") if g.get("from") in glyphs else None
        dr.text((8, 4), c + (f" < {src}" if designed and src else ""), fill=(20, 30, 50), font=font)
        dr.text((w - 70, 9), "designed" if designed else "traced", fill=(150, 80, 30) if designed else (90, 90, 90), font=small)
        dr.rectangle([0, 0, w - 1, CELL_H + LABEL_H - 1], outline=(200, 200, 200))
        cells.append(cell)
    cols = max(1, a.cols)
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    W = max(sum(c.width for c in r) + 8 * (len(r) + 1) for r in rows)
    H = len(rows) * (CELL_H + LABEL_H + 8) + 8
    sheet = Image.new("RGB", (W, H), (230, 230, 230))
    y = 8
    for r in rows:
        x = W - 8  # right to left, like Hebrew
        for c in r:
            x -= c.width
            sheet.paste(c, (x, y))
            x -= 8
        y += CELL_H + LABEL_H + 8
    out = Path(a.out) if a.out else folder / "work" / "overlay.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"OVERLAY {out}  ({len(cells)} letters; red = traced line over the scan, blue ring = start)")


if __name__ == "__main__":
    main()
