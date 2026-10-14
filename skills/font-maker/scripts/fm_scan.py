"""Read scanned / photographed template pages and turn each box into outlines.

Steps per page: find the four black corner squares, undo rotation and
perspective, read the page code (page number + which way is up), slice the
writing boxes, threshold (the light-blue guides drop out), vectorize with
potracer and place the outline relative to the box baseline.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

import fm_common as C
from fm_outline import normalize_directions

try:  # optional, faster and sturdier; everything works without it
    if os.environ.get("FONTMAKER_NO_OPENCV"):
        raise ImportError
    import cv2  # type: ignore

    HAVE_CV2 = True
except Exception:  # pragma: no cover
    cv2 = None
    HAVE_CV2 = False

Image.MAX_IMAGE_PIXELS = 300_000_000

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
PDF_EXT = {".pdf"}
HEIC_EXT = {".heic", ".heif"}


class ScanError(Exception):
    pass


# ---------------------------------------------------------------------------
# Loading files
# ---------------------------------------------------------------------------


def collect_inputs(paths: list[str]) -> tuple[list[Path], list[Path]]:
    """Expand folders, keep readable files, oldest first. Returns (files, skipped)."""
    files, skipped = [], []
    for p in paths:
        p = Path(p)
        items = sorted(p.iterdir()) if p.is_dir() else [p]
        for f in items:
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext in IMAGE_EXT or ext in PDF_EXT:
                files.append(f)
            elif ext in HEIC_EXT:
                skipped.append(f)
    files = sorted(set(files), key=lambda f: (f.stat().st_mtime, f.name))
    return files, skipped


def load_images(path: Path) -> list[tuple[str, Image.Image]]:
    if path.suffix.lower() in PDF_EXT:
        return [(f"{path.name} p{i + 1}", im) for i, im in enumerate(_pdf_pages(path))]
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)
        return [(path.name, im.convert("RGB"))]


def _pdf_pages(path: Path) -> list[Image.Image]:
    try:
        import fitz  # PyMuPDF, optional

        pages = []
        with fitz.open(str(path)) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=300, alpha=False)
                pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        if pages:
            return pages
    except ImportError:
        pass
    # No PDF library: scanner apps store each page as one JPEG; pull those out.
    data = path.read_bytes()
    pages = []
    for m in re.finditer(rb"stream\r?\n", data):
        head = data[max(0, m.start() - 1500):m.start()]
        obj_start = head.rfind(b" obj")
        if obj_start >= 0:
            head = head[obj_start:]
        if b"/DCTDecode" not in head:
            continue
        start = m.end()
        length = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", head)
        end = start + int(length.group(1)) if length else data.find(b"endstream", start)
        blob = data[start:end]
        if not blob.startswith(b"\xff\xd8"):
            continue
        try:
            from io import BytesIO

            im = Image.open(BytesIO(blob))
            im.load()
            if min(im.size) >= 700:
                pages.append(im.convert("RGB"))
        except Exception:
            continue
    if not pages:
        raise ScanError("PDF_UNREADABLE")
    return pages


# ---------------------------------------------------------------------------
# Small image-processing helpers (numpy only)
# ---------------------------------------------------------------------------


def _gray(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.uint8)


def _otsu(values: np.ndarray) -> float:
    hist = np.bincount(values.ravel().astype(np.uint8), minlength=256).astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 128.0
    omega = np.cumsum(hist) / total
    mu = np.cumsum(hist * np.arange(256)) / total
    mu_t = mu[-1]
    denom = omega * (1 - omega)
    denom[denom == 0] = np.nan
    sigma = (mu_t * omega - mu) ** 2 / denom
    return float(np.nanargmax(sigma))


def _components(mask: np.ndarray) -> list[dict]:
    """8-connected components with area, bbox and centroid."""
    if HAVE_CV2:
        n, _labels, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        out = []
        for i in range(1, n):
            x, y, w, h, a = stats[i]
            out.append(dict(area=int(a), x0=int(x), y0=int(y), x1=int(x + w), y1=int(y + h),
                            cx=float(cents[i][0]), cy=float(cents[i][1])))
        return out
    # run-length union-find
    parent: list[int] = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs = []          # (row, start, end)
    prev: list[int] = []
    for r in range(mask.shape[0]):
        row = mask[r]
        if not row.any():
            prev = []
            continue
        d = np.diff(np.concatenate(([0], row.view(np.uint8) if row.dtype == bool else row.astype(np.uint8), [0])))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        cur = []
        j = 0
        for s, e in zip(starts.tolist(), ends.tolist()):
            idx = len(runs)
            runs.append((r, s, e))
            parent.append(idx)
            # 8-connectivity: overlap with previous row runs, widened by one
            while j < len(prev) and runs[prev[j]][2] < s:
                j += 1
            k = j
            while k < len(prev) and runs[prev[k]][1] <= e:
                a, b = find(idx), find(prev[k])
                if a != b:
                    parent[b] = a
                k += 1
            cur.append(idx)
        prev = cur
    comps: dict[int, list] = {}
    for idx, (r, s, e) in enumerate(runs):
        root = find(idx)
        c = comps.get(root)
        n = e - s
        sx = (s + e - 1) * n / 2.0
        if c is None:
            comps[root] = [n, s, r, e, r + 1, sx, r * n]
        else:
            c[0] += n
            c[1] = min(c[1], s)
            c[2] = min(c[2], r)
            c[3] = max(c[3], e)
            c[4] = max(c[4], r + 1)
            c[5] += sx
            c[6] += r * n
    return [dict(area=a, x0=x0, y0=y0, x1=x1, y1=y1, cx=sx / a, cy=sy / a)
            for a, x0, y0, x1, y1, sx, sy in comps.values()]


def _homography(src, dst) -> np.ndarray:
    """3x3 matrix mapping the 4 src points onto the 4 dst points."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -x * u, -y * u])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -x * v, -y * v])
        b.append(v)
    h = np.linalg.solve(np.array(a, dtype=np.float64), np.array(b, dtype=np.float64))
    return np.append(h, 1.0).reshape(3, 3)


def _apply(hm: np.ndarray, x: float, y: float) -> tuple[float, float]:
    p = hm @ np.array([x, y, 1.0])
    return p[0] / p[2], p[1] / p[2]


# ---------------------------------------------------------------------------
# Registration marks and page code
# ---------------------------------------------------------------------------


@dataclass
class PageFit:
    corners: list            # 4 image points TL, TR, BR, BL (image order)
    threshold: float         # dark threshold on the gray image
    found_marks: bool = True


def find_marks(img: Image.Image) -> PageFit | None:
    w, h = img.size
    scale = 1000.0 / max(w, h)
    small = img.convert("L").resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.BOX)
    a = np.asarray(small, dtype=np.uint8)
    thr = min(max(_otsu(a), 70.0), 160.0)
    mask = a < thr
    sh, sw = a.shape
    expected = (C.MARK_SIZE_MM / C.PAGE_W_MM) * min(sw, sh)
    cands = []
    for c in _components(mask):
        bw, bh = c["x1"] - c["x0"], c["y1"] - c["y0"]
        side = (bw + bh) / 2
        if not (0.3 * expected <= side <= 1.8 * expected):
            continue
        if not (0.6 <= bw / max(bh, 1) <= 1.67):
            continue
        if c["area"] / max(bw * bh, 1) < 0.6:
            continue
        if c["x0"] <= 0 or c["y0"] <= 0 or c["x1"] >= sw or c["y1"] >= sh:
            continue
        cands.append(c)
    if len(cands) < 4:
        return None
    img_corners = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
    diag = (sw ** 2 + sh ** 2) ** 0.5
    chosen = []
    for cx, cy in img_corners:
        best = min(cands, key=lambda c: (c["cx"] - cx) ** 2 + (c["cy"] - cy) ** 2)
        if ((best["cx"] - cx) ** 2 + (best["cy"] - cy) ** 2) ** 0.5 > 0.35 * diag:
            return None
        chosen.append(best)
    if len({id(c) for c in chosen}) < 4:
        return None
    quad = [(c["cx"], c["cy"]) for c in chosen]
    area = 0.5 * abs(sum(quad[i][0] * quad[(i + 1) % 4][1] - quad[(i + 1) % 4][0] * quad[i][1] for i in range(4)))
    if area < 0.15 * sw * sh:
        return None
    # refine each centre at full resolution
    g = _gray(img)
    corners = []
    for c in chosen:
        pad = 0.5 * max(c["x1"] - c["x0"], c["y1"] - c["y0"])
        x0 = int(max(0, (c["x0"] - pad) / scale))
        y0 = int(max(0, (c["y0"] - pad) / scale))
        x1 = int(min(w, (c["x1"] + pad) / scale))
        y1 = int(min(h, (c["y1"] + pad) / scale))
        crop = g[y0:y1, x0:x1].astype(np.float64)
        t = (crop.min() + np.percentile(crop, 90)) / 2
        ys, xs = np.nonzero(crop < t)
        if len(xs) == 0:
            corners.append((c["cx"] / scale, c["cy"] / scale))
        else:
            corners.append((x0 + xs.mean() + 0.5, y0 + ys.mean() + 0.5))
    return PageFit(corners=corners, threshold=thr)


def _template_mark_px():
    return [(x * C.MM, y * C.MM) for x, y in C.MARK_CENTERS_MM]


def _read_code(gray: np.ndarray, hm: np.ndarray, thr: float) -> tuple[int, bool] | None:
    bits = []
    half = C.CODE_SQ_MM * C.MM * 0.28
    for cx, cy in C.code_square_centers_mm():
        tx, ty = cx * C.MM, cy * C.MM
        ix, iy = _apply(hm, tx, ty)
        ex, ey = _apply(hm, tx + half, ty + half)
        r = max(2, int(max(abs(ex - ix), abs(ey - iy))))
        x0, y0 = int(round(ix)) - r, int(round(iy)) - r
        if x0 < 0 or y0 < 0 or x0 + 2 * r >= gray.shape[1] or y0 + 2 * r >= gray.shape[0]:
            return None
        win = gray[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
        frac = float((win < thr).mean())
        if frac > 0.6:
            bits.append(1)
        elif frac < 0.2:
            bits.append(0)
        else:
            return None
    return C.decode_page_code(bits)


@dataclass
class PageRead:
    label: str
    page_no: int | None
    latin: bool | None
    rotation: int
    warped: Image.Image
    notes: list = field(default_factory=list)


def read_page(label: str, img: Image.Image) -> PageRead:
    notes = []
    fit = find_marks(img)
    if fit is None:
        notes.append("NO_MARKS")
        w, h = img.size
        # assume the image is the page itself, upright (or turned on its side)
        if w > h:
            img = img.rotate(90, expand=True)
            w, h = img.size
        fit = PageFit(corners=[(0, 0), (w, 0), (w, h), (0, h)], threshold=128.0, found_marks=False)
        dst_template = [(0, 0), (C.PAGE_W, 0), (C.PAGE_W, C.PAGE_H), (0, C.PAGE_H)]
    else:
        dst_template = _template_mark_px()
    gray = _gray(img)
    choice = None
    if fit.found_marks:
        decoded = []
        for rot in range(4):
            img_pts = [fit.corners[(k + rot) % 4] for k in range(4)]
            hm = _homography(dst_template, img_pts)
            res = _read_code(gray, hm, fit.threshold)
            if res is not None:
                decoded.append((rot, hm, res))
        if decoded:
            choice = decoded[0]
    if choice is None:
        if fit.found_marks:
            notes.append("NO_PAGE_CODE")
        w, h = img.size
        rot = 0 if h >= w else 1
        img_pts = [fit.corners[(k + rot) % 4] for k in range(4)]
        choice = (rot, _homography(dst_template, img_pts), (None, None))
    rot, hm, (page_no, latin) = choice
    warped = _warp(img, hm)
    return PageRead(label=label, page_no=page_no, latin=latin, rotation=rot * 90, warped=warped, notes=notes)


def _warp(img: Image.Image, hm: np.ndarray) -> Image.Image:
    size = (C.PAGE_W, C.PAGE_H)
    if HAVE_CV2:
        arr = np.asarray(img)
        out = cv2.warpPerspective(arr, hm, size, flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
        return Image.fromarray(out)
    coeffs = tuple((hm / hm[2, 2]).ravel()[:8])
    return img.transform(size, Image.Transform.PERSPECTIVE, coeffs,
                         resample=Image.Resampling.BICUBIC, fillcolor=(255, 255, 255))


# ---------------------------------------------------------------------------
# Boxes -> bitmaps -> outlines
# ---------------------------------------------------------------------------

INSET_MM = 1.0
MIN_INK_PX = 80          # below this a box counts as empty (300 dpi)
FAINT_MIN_PX = 250


@dataclass
class Cell:
    char: str
    status: str                  # ok | faint | empty
    contours: list = field(default_factory=list)
    edges: list = field(default_factory=list)   # top / bottom / left / right
    ink_px: int = 0
    light: bool = False          # traced fine, but the ink looked pale
    source: str = ""
    page: int = 0


def _ink_crop(rgb: np.ndarray) -> np.ndarray:
    """One box -> 'ink' image. White-balance on the paper colour first (warm
    lamp light makes blue guides look dark otherwise), then take the brightest
    of R, G, B: black ink stays dark, the light-blue guides turn white."""
    a = rgb.astype(np.float64)
    paper = np.median(a.reshape(-1, 3), axis=0)
    paper[paper < 40] = 40
    a = np.clip(a * (235.0 / paper), 0, 255)
    return a.max(axis=2)


def _drop_guides(mask: np.ndarray, rows: list[int]) -> np.ndarray:
    """Remove a guide line that survived thresholding (e.g. a template printed
    in black and white): only where it runs across nearly the whole box, and
    never in columns where a stroke crosses it."""
    h, w = mask.shape
    out = mask.copy()
    band, reach = 7, 11
    for y in rows:
        y0, y1 = max(0, y - band), min(h, y + band + 1)
        if y0 >= y1:
            continue
        cols = mask[y0:y1].any(axis=0)
        if cols.mean() < 0.85:
            continue
        above = mask[max(0, y - reach)] if y - reach >= 0 else np.zeros(w, bool)
        below = mask[min(h - 1, y + reach)] if y + reach < h else np.zeros(w, bool)
        crossing = above | below
        out[y0:y1, ~crossing] = False
    return out


def _clean(mask: np.ndarray) -> np.ndarray:
    im = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8))
    im = im.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    return np.asarray(im) > 127


def _smooth(mask: np.ndarray) -> np.ndarray:
    im = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8))
    im = im.filter(ImageFilter.GaussianBlur(1.0))
    return np.asarray(im) > 127


def extract_cells(page: PageRead, chars: list[str]) -> list[Cell]:
    import potrace

    rgb = np.asarray(page.warped.convert("RGB"), dtype=np.uint8)
    inset = INSET_MM * C.MM
    slots = []
    first = (page.page_no - 1) * C.PER_PAGE
    for slot in range(C.PER_PAGE):
        idx = first + slot
        if idx >= len(chars):
            break
        l, t, r, b = C.box_rect_px(slot)
        x0, y0, x1, y1 = int(round(l + inset)), int(round(t + inset)), int(round(r - inset)), int(round(b - inset))
        crop = _ink_crop(rgb[y0:y1, x0:x1])
        slots.append((chars[idx], (l, t, r, b), (x0, y0, x1, y1), crop))
    if not slots:
        return []
    sample = np.concatenate([c[::2, ::2].ravel() for *_, c in slots]).astype(np.uint8)
    bg_page = float(np.median(sample))
    thr_page = _otsu(sample)
    thr_page = min(max(thr_page, bg_page - 160), bg_page - 50)
    delta = bg_page - thr_page
    units_per_px = C.UNITS_PER_BOX_H / (C.BOX_H_MM * C.MM)
    cells = []
    box_h = C.BOX_H_MM * C.MM
    for ch, (l, t, r, b), (x0, y0, x1, y1), crop in slots:
        guide_rows = [round(t + box_h * (C.BOX_TOP_UNITS - u) / C.UNITS_PER_BOX_H) - y0
                      for u in (0, C.XHEIGHT_UNITS)]
        bg = float(np.median(crop))
        mask = _drop_guides(_clean(crop < bg - delta), guide_rows)
        status, light = "ok", False
        if mask.sum() < MIN_INK_PX:
            # a pale drawing? blur first so camera noise can't pass as ink
            soft = np.asarray(Image.fromarray(crop.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.5)),
                              dtype=np.float64)
            faint = _drop_guides(_clean(soft < bg - 30), guide_rows)
            if faint.sum() >= FAINT_MIN_PX:
                mask, status = faint, "faint"
            else:
                cells.append(Cell(ch, "empty", ink_px=int(mask.sum()), page=page.page_no, source=page.label))
                continue
        else:
            if float(np.median(crop[mask])) > bg - 90:
                light = True
        edges = []
        for name, strip in (("top", mask[:3]), ("bottom", mask[-3:]), ("right", mask[:, -3:]), ("left", mask[:, :3])):
            if strip.sum() > 10:
                edges.append(name)
        smooth = _smooth(mask)
        bm = potrace.Bitmap(np.where(smooth, 0, 255).astype(np.uint8))
        path = bm.trace(turdsize=30, alphamax=1.0, opticurve=True, opttolerance=0.2)
        contours = []
        ox, oy = x0 - l, y0 - t   # crop origin inside the box, px

        def tf(p, ox=ox, oy=oy):
            return ((ox + p.x) * units_per_px, C.BOX_TOP_UNITS - (oy + p.y) * units_per_px)

        for curve in path:
            c = [("M", tf(curve.start_point))]
            for seg in curve:
                if seg.is_corner:
                    c.append(("L", tf(seg.c)))
                    c.append(("L", tf(seg.end_point)))
                else:
                    c.append(("C", tf(seg.c1), tf(seg.c2), tf(seg.end_point)))
            contours.append(c)
        contours = normalize_directions(contours)
        if not contours:
            cells.append(Cell(ch, "empty", page=page.page_no, source=page.label))
            continue
        cells.append(Cell(ch, status, contours=contours, edges=edges, ink_px=int(mask.sum()),
                          light=light, source=page.label, page=page.page_no))
    return cells


def debug_overlay(page: PageRead, chars: list[str]) -> Image.Image:
    from PIL import ImageDraw

    im = page.warped.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    for slot in range(C.PER_PAGE):
        if page.page_no is None or (page.page_no - 1) * C.PER_PAGE + slot >= len(chars):
            break
        l, t, r, b = C.box_rect_px(slot)
        d.rectangle([l, t, r, b], outline=(255, 0, 0), width=3)
        base_y = t + (C.BOX_TOP_UNITS / C.UNITS_PER_BOX_H) * (b - t)
        d.line([l, base_y, r, base_y], fill=(0, 160, 0), width=2)
    for x, y in _template_mark_px():
        d.ellipse([x - 12, y - 12, x + 12, y + 12], outline=(255, 0, 255), width=4)
    return im
