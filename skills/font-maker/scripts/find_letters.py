# -*- coding: utf-8 -*-
"""Look at a handwriting scan: find the ink, the lines and the letters, and
make pictures with a coordinate grid so letters can be traced by eye.

    python find_letters.py "<scan>" "<out dir>"                    overview + lines
    python find_letters.py "<scan>" "<out dir>" --line 3           one line, numbered boxes
    python find_letters.py "<scan>" "<out dir>" --box x0 y0 x1 y1  enlarged crop, fine grid
    python find_letters.py "<scan>" "<out dir>" --comp 57          enlarged crop around box 57

All coordinates are pixels of the original scan (x right, y down).
Writes letters.json (boxes, lines, pen thickness, letter height).
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fm_core as core

COLORS = [(214, 39, 40), (31, 119, 180), (44, 160, 44), (148, 103, 189), (255, 127, 14), (23, 190, 207)]


def ink_mask(im):
    a = np.asarray(im, dtype=np.float32)
    gray = a.min(axis=2)  # coloured pens are dark in at least one channel
    h, w = gray.shape
    f = max(4, int(max(h, w) / 160))
    small = Image.fromarray(gray.astype(np.uint8)).resize((max(1, w // f), max(1, h // f)), Image.BOX)
    small = small.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2))
    bg = np.asarray(small.resize((w, h), Image.BILINEAR), dtype=np.float32)
    dark = bg - gray
    hi = np.percentile(dark, 99.7)
    # pieces: a low threshold keeps faint strokes. pen width: half of full
    # darkness, the visible core of the line (the soft edge is not ink)
    return dark > max(18.0, 0.33 * hi), dark > max(18.0, 0.5 * hi)


def label(mask):
    """Connected ink pieces (8-connected), via runs and union-find."""
    runs, row_runs = [], []
    for y in range(mask.shape[0]):
        r = mask[y]
        if not r.any():
            row_runs.append([])
            continue
        d = np.diff(np.r_[0, r.astype(np.int8), 0])
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        row_runs.append(list(range(len(runs), len(runs) + len(starts))))
        runs.extend((y, int(s), int(e)) for s, e in zip(starts, ends))
    parent = list(range(len(runs)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for y in range(1, len(row_runs)):
        prev, cur = row_runs[y - 1], row_runs[y]
        i = j = 0
        while i < len(prev) and j < len(cur):
            _, ps, pe = runs[prev[i]]
            _, cs, ce = runs[cur[j]]
            if ps <= ce and cs <= pe:
                ra, rb = find(prev[i]), find(cur[j])
                if ra != rb:
                    parent[rb] = ra
            if pe < ce:
                i += 1
            else:
                j += 1
    comps = {}
    for idx, (y, s, e) in enumerate(runs):
        r = find(idx)
        c = comps.setdefault(r, [s, y, e, y, 0, []])
        c[0], c[1], c[2], c[3] = min(c[0], s), min(c[1], y), max(c[2], e), max(c[3], y + 1)
        c[4] += e - s
        c[5].append((y, s, e))
    return list(comps.values())


def analyse(im):
    mask, core_mask = ink_mask(im)
    h, w = mask.shape
    raw = label(mask)
    cm = core_mask
    inner = cm.copy()
    inner[1:-1, 1:-1] = cm[1:-1, 1:-1] & cm[:-2, 1:-1] & cm[2:, 1:-1] & cm[1:-1, :-2] & cm[1:-1, 2:]
    edge = cm & ~inner
    comps, widths = [], []
    min_area = max(6, int(h * w / 400000))
    for x0, y0, x1, y1, area, rr in raw:
        bw, bh = x1 - x0, y1 - y0
        if area < min_area:
            continue
        mx, my = max(2, w // 200), max(2, h // 200)
        touches = x0 <= mx or y0 <= my or x1 >= w - mx or y1 >= h - my
        if (touches and (bw > 0.2 * w or bh > 0.2 * h)) or bw > 0.5 * w or bh > 0.3 * h:
            continue  # table edge, shadow or page border
        per = sum(int(edge[y, s:e].sum()) for y, s, e in rr)
        core_area = sum(int(cm[y, s:e].sum()) for y, s, e in rr)
        if core_area >= 25 and per:
            widths.append(2.0 * core_area / per)
        comps.append({"box": [int(x0), int(y0), int(x1), int(y1)], "area": int(area)})
    # lines: merge vertical spans of the pieces
    hs = sorted(c["box"][3] - c["box"][1] for c in comps if c["area"] > 3 * min_area)
    med_h = hs[len(hs) // 2] if hs else 20
    spans = sorted((c["box"][1], c["box"][3], i) for i, c in enumerate(comps))
    lines = []
    for y0, y1, i in spans:
        if lines and y0 <= lines[-1]["y1"] - 0.35 * med_h:
            ln = lines[-1]
            ln["y1"] = max(ln["y1"], y1)
            ln["members"].append(i)
        else:
            lines.append({"y0": y0, "y1": y1, "members": [i]})
    merged = []
    for ln in lines:
        if merged and len(ln["members"]) == 1 and ln["y1"] - ln["y0"] < 0.5 * med_h:
            merged[-1]["members"] += ln["members"]
            continue
        merged.append(ln)
    lines = merged
    out_lines = []
    for ln in lines:
        mem = [comps[i] for i in ln["members"]]
        big = [c for c in mem if c["area"] > 3 * min_area] or mem
        if sum(c["area"] for c in mem) < 8 * min_area:
            continue
        bottoms = sorted(c["box"][3] for c in big)
        heights = sorted(c["box"][3] - c["box"][1] for c in big)
        n = len(out_lines) + 1
        base = int(np.percentile(bottoms, 60))
        out_lines.append({
            "line": n,
            "box": [min(c["box"][0] for c in mem), min(c["box"][1] for c in mem),
                    max(c["box"][2] for c in mem), max(c["box"][3] for c in mem)],
            "baseline": base, "letter_height": int(np.median(heights)), "pieces": len(mem)})
        # number pieces right to left inside the line (Hebrew reading order)
        for c in sorted(mem, key=lambda c: -c["box"][2]):
            c["line"] = n
    numbered = [c for c in comps if "line" in c]
    numbered.sort(key=lambda c: (c["line"], -c["box"][2]))
    for i, c in enumerate(numbered, 1):
        c["id"] = i
    pen = float(np.median(widths)) if widths else 3.0
    xh = int(np.median([ln["letter_height"] for ln in out_lines])) if out_lines else int(med_h)
    return {"size": [w, h], "pen_px": round(pen, 1), "x_height_px": xh,
            "lines": out_lines, "pieces": numbered}


def draw_grid(d, x0, y0, x1, y1, z, ox, oy, step, label_every, font, color=(0, 150, 200)):
    first = int(math.ceil(x0 / step) * step)
    for x in range(first, int(x1) + 1, step):
        X = (x - x0) * z + ox
        strong = x % label_every == 0
        d.line([(X, oy), (X, oy + (y1 - y0) * z)], fill=color + ((150,) if strong else (60,)), width=1)
        if strong:
            d.text((X + 2, oy - 14), str(x), fill=(0, 90, 140), font=font)
    first = int(math.ceil(y0 / step) * step)
    for y in range(first, int(y1) + 1, step):
        Y = (y - y0) * z + oy
        strong = y % label_every == 0
        d.line([(ox, Y), (ox + (x1 - x0) * z, Y)], fill=color + ((150,) if strong else (60,)), width=1)
        if strong:
            d.text((2, Y - 7), str(y), fill=(0, 90, 140), font=font)


def crop_view(im, box, out, info, z=None, pieces=None, baseline=None):
    x0, y0, x1, y1 = box
    w, h = im.size
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if z is None:
        z = max(1, min(24, int(1400 / max(1, x1 - x0)), int(900 / max(1, y1 - y0))))
    crop = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * z, (y1 - y0) * z), Image.NEAREST if z >= 6 else Image.LANCZOS)
    ox, oy = 44, 20
    canvas = Image.new("RGB", (crop.width + ox + 10, crop.height + oy + 10), "white")
    canvas.paste(crop, (ox, oy))
    d = ImageDraw.Draw(canvas, "RGBA")
    font = core.hebrew_font(12)
    step = 1 if z >= 16 else 2 if z >= 10 else 5 if z >= 4 else 10
    label_every = 10 if z >= 6 else 50 if step == 5 else 100
    draw_grid(d, x0, y0, x1, y1, z, ox, oy, step, label_every, font)
    if baseline is not None and y0 <= baseline <= y1:
        Y = (baseline - y0) * z + oy
        d.line([(ox, Y), (ox + crop.width, Y)], fill=(0, 170, 60, 200), width=2)
    for p in pieces or []:
        bx0, by0, bx1, by1 = p["box"]
        col = COLORS[p["id"] % len(COLORS)]
        d.rectangle([(bx0 - x0) * z + ox, (by0 - y0) * z + oy, (bx1 - x0) * z + ox, (by1 - y0) * z + oy],
                    outline=col + (220,), width=2)
        d.text(((bx0 - x0) * z + ox + 2, (by1 - y0) * z + oy + 1), str(p["id"]), fill=col, font=core.hebrew_font(14))
    canvas.save(out)
    print(f"{info} {out}  (zoom x{z}, grid every {step}px)")


def main():
    core.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("out")
    ap.add_argument("--line", type=int)
    ap.add_argument("--box", type=int, nargs=4)
    ap.add_argument("--comp", type=int)
    ap.add_argument("--zoom", type=int)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    im = core.load_scan(a.scan)
    cache = out / "letters.json"
    if cache.exists() and json.loads(cache.read_text(encoding="utf-8")).get("scan") == str(Path(a.scan).resolve()):
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        data = analyse(im)
        data["scan"] = str(Path(a.scan).resolve())
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    pieces = data["pieces"]
    if a.box:
        x0, y0, x1, y1 = a.box
        ln = next((l for l in data["lines"] if l["box"][1] <= (y0 + y1) / 2 <= l["box"][3]), None)
        crop_view(im, a.box, out / f"crop-{x0}-{y0}.png", "CROP", a.zoom, None, ln and ln["baseline"])
        return
    if a.comp:
        p = next((p for p in pieces if p["id"] == a.comp), None)
        if not p:
            core.fail(f"no piece number {a.comp}")
        m = max(6, int(data["x_height_px"] * 0.4))
        bx = p["box"]
        ln = next(l for l in data["lines"] if l["line"] == p["line"])
        crop_view(im, [bx[0] - m, bx[1] - m, bx[2] + m, bx[3] + m], out / f"piece-{a.comp}.png", "CROP", a.zoom,
                  None, ln["baseline"])
        return
    if a.line:
        ln = next((l for l in data["lines"] if l["line"] == a.line), None)
        if not ln:
            core.fail(f"no line {a.line} (there are {len(data['lines'])})")
        m = int(data["x_height_px"] * 0.6)
        b = ln["box"]
        crop_view(im, [b[0] - m, b[1] - m, b[2] + m, b[3] + m], out / f"line-{a.line:02d}.png", "LINE", a.zoom,
                  [p for p in pieces if p.get("line") == a.line], ln["baseline"])
        return
    # overview: whole page, line boxes and numbers
    w, h = im.size
    s = min(1.0, 1600 / max(w, h))
    view = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
    d = ImageDraw.Draw(view, "RGBA")
    font = core.hebrew_font(max(14, int(22 * s)))
    for ln in data["lines"]:
        x0, y0, x1, y1 = [v * s for v in ln["box"]]
        col = COLORS[ln["line"] % len(COLORS)]
        d.rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], outline=col + (230,), width=2)
        d.text((x1 + 6, y0), str(ln["line"]), fill=col, font=font)
    for p in pieces:
        x0, y0, x1, y1 = [v * s for v in p["box"]]
        d.rectangle([x0, y0, x1, y1], outline=(0, 0, 0, 60), width=1)
    view.save(out / "overview.png")
    print(f"SCAN {w}x{h}px  lines {len(data['lines'])}  pieces {len(pieces)}")
    print(f"PEN about {data['pen_px']}px thick   LETTER HEIGHT about {data['x_height_px']}px")
    for ln in data["lines"]:
        print(f"  line {ln['line']:2d}: y {ln['box'][1]}-{ln['box'][3]}, baseline {ln['baseline']}, "
              f"letters ~{ln['letter_height']}px, {ln['pieces']} pieces")
    print(f"OVERVIEW {out / 'overview.png'}")


if __name__ == "__main__":
    main()
