# -*- coding: utf-8 -*-
"""Start a font folder, add starter letters, or reshape letters.

    python design_tool.py new "<work dir>" --name "הכתב של נועה" --latin-name "Noa Hand"
                          --mode handwriting --scan "<scan.jpg>" [--english] [--spacing close]
    python design_tool.py new "<work dir>" --name "שירה" --latin-name "Shira" --mode inspired
                          [--pen round|nib] [--english]
    python design_tool.py add "<font folder>" latin|digits|punct|hebrew [--replace]
    python design_tool.py reshape "<font folder>" "בכ" [--width 0.9] [--height 1.1] [--slant 5] [--up 2]

Starter letters are plain skeletons drawn for font-maker; they get the font's
pen and slant and are meant to be reshaped to match the style.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path

import fm_core as core

SKILL = Path(__file__).resolve().parents[1]
GROUPS = {
    "hebrew": core.HEBREW,
    "digits": core.DIGITS,
    "punct": core.PUNCT,
    "latin": core.LATIN_LOWER + core.LATIN_UPPER,
}


def starter_glyphs(groups, font_xh):
    st = json.loads((SKILL / "assets" / "starter.json").read_text(encoding="utf-8"))
    f = font_xh / float(st["x_height"])
    out = {}
    for grp in groups:
        for c in GROUPS[grp]:
            g = st["glyphs"].get(c)
            if not g:
                continue
            paths = [core.transform_svg(d, (f, 0, 0, f, 0, 0)) for d in g["paths"]]
            out[c] = {"frame": "font", "paths": paths, "designed": True, "from": "starter"}
    return out


def cmd_new(a):
    safe = re.sub(r'[<>:"/\\|?*]', "", a.name).strip() or "font"
    folder = Path(a.work) / safe
    if (folder / "design.json").exists() and not a.force:
        core.fail(f"{folder} already has design.json (use the existing one, or --force)")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "work").mkdir(exist_ok=True)
    font_xh = 450
    d = {"name": a.name, "name_latin": a.latin_name or core.latin_name({"name": a.name}),
         "version": "1.000", "mode": a.mode, "font_x_height": font_xh,
         "spacing": a.spacing, "weights": {w: core.DEFAULT_WEIGHTS.get(w, 1.0) for w in a.weights.split(",")},
         "slant": 0}
    groups = ["digits", "punct"] + (["latin"] if a.english else [])
    compare = {}
    if a.mode == "handwriting":
        if not a.scan:
            core.fail("--scan is needed for a handwriting font")
        import find_letters
        src = folder / "source"
        src.mkdir(exist_ok=True)
        dst = src / Path(a.scan).name
        if Path(a.scan).resolve() != dst.resolve():
            shutil.copy2(a.scan, dst)
        info = find_letters.analyse(core.load_scan(dst))
        xpx = max(8, info["x_height_px"])
        scale = font_xh / xpx
        d.update({"frame": "scan", "scan": f"source/{dst.name}", "x_height": xpx,
                  "scale": round(scale, 4), "pen": {"type": "round", "width": round(info["pen_px"] * scale)}})
        compare = {"scan": f"source/{dst.name}", "strips": []}
        print(f"SCAN letters about {xpx}px tall, pen about {info['pen_px']}px -> pen width {d['pen']['width']} units")
    else:
        groups = ["hebrew"] + groups
        if a.pen == "nib":
            d["pen"] = {"type": "nib", "width": 95, "thin": 16, "angle": 75}
        else:
            d["pen"] = {"type": "round", "width": 62}
        d["frame"] = "font"
        compare = {"inspiration": [], "words": [a.name]}
    d["glyphs"] = starter_glyphs(groups, font_xh)
    (folder / "design.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "compare.json").write_text(json.dumps(compare, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FOLDER {folder}")
    print(f"STARTER {len(d['glyphs'])} letters/signs from the starter set ({', '.join(groups)})")


def cmd_add(a):
    folder = Path(a.folder)
    path = folder / "design.json"
    d = core.load_design(folder)
    raw = json.loads(path.read_text(encoding="utf-8"))
    new = starter_glyphs([a.what], d["xh"] if d["frame"] == "scan" else d["font_x_height"])
    added = 0
    for c, g in new.items():
        if c in raw["glyphs"] and raw["glyphs"][c].get("paths") and not a.replace:
            continue
        raw["glyphs"][c] = g
        added += 1
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ADDED {added} starter glyphs ({a.what}) to {path}")


def cmd_reshape(a):
    """Narrower/wider, shorter/taller, more slanted or raised letters. Works
    around each letter's own left edge and baseline, in its own frame."""
    import math
    folder = Path(a.folder)
    path = folder / "design.json"
    d = core.load_design(folder)
    raw = json.loads(path.read_text(encoding="utf-8"))
    t = math.tan(math.radians(a.slant))
    done = []
    for c in a.letters:
        g = raw["glyphs"].get(c)
        if not g or not g.get("paths"):
            continue
        targets = [g] + ([g["alt"]] if a.alt_too and g.get("alt", {}).get("paths") else [])
        frame = g.get("frame", d["frame"])
        base = float(g.get("baseline", 0))
        bp = BoundsPen(None)  # left edge, in the letter's own drawing units
        for dd in g["paths"]:
            parse_path(dd, bp)
        x0 = bp.bounds[0]
        for tg in targets:
            if frame == "scan":  # y down
                m = (a.width, 0, -t * a.height, a.height, x0 * (1 - a.width) + t * a.height * base,
                     base * (1 - a.height) - a.up)
            else:  # y up
                m = (a.width, 0, t * a.height, a.height, x0 * (1 - a.width) - t * a.height * base,
                     base * (1 - a.height) + a.up)
            tg["paths"] = [core.transform_svg(dd, m) for dd in tg["paths"]]
        done.append(c)
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"RESHAPED {' '.join(done) or 'nothing'}")


def main():
    core.utf8_console()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("work")
    n.add_argument("--name", required=True)
    n.add_argument("--latin-name")
    n.add_argument("--mode", choices=["handwriting", "inspired"], default="handwriting")
    n.add_argument("--scan")
    n.add_argument("--english", action="store_true")
    n.add_argument("--spacing", choices=list(core.SPACING), default="close")
    n.add_argument("--weights", default="Light,Regular,Bold")
    n.add_argument("--pen", choices=["round", "nib"], default="round")
    n.add_argument("--force", action="store_true")
    ad = sub.add_parser("add")
    ad.add_argument("folder")
    ad.add_argument("what", choices=list(GROUPS))
    ad.add_argument("--replace", action="store_true")
    r = sub.add_parser("reshape")
    r.add_argument("folder")
    r.add_argument("letters")
    r.add_argument("--width", type=float, default=1.0)
    r.add_argument("--height", type=float, default=1.0)
    r.add_argument("--slant", type=float, default=0.0, help="degrees, positive leans the top to the right")
    r.add_argument("--up", type=float, default=0.0, help="move up, in the design's own units")
    r.add_argument("--alt-too", action="store_true")
    a = ap.parse_args()
    {"new": cmd_new, "add": cmd_add, "reshape": cmd_reshape}[a.cmd](a)


if __name__ == "__main__":
    main()
