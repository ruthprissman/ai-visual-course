"""Shared constants and helpers for the font-maker scripts.

Everything that the template, the scan reader and the font builder must agree
on lives here: the character set, the page layout, the em-box mapping and the
glyph / file names.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Console: Windows terminals default to a legacy code page. Force UTF-8 so
# Hebrew characters in status lines never crash the script.
# ---------------------------------------------------------------------------


def setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def say(tag: str, msg: str) -> None:
    """One short status line, easy for Claude to relay: 'TAG  message'."""
    print(f"{tag:<9}{msg}", flush=True)


# ---------------------------------------------------------------------------
# Character set
# ---------------------------------------------------------------------------

HEBREW = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
DIGITS = "0123456789"
PUNCT = ".,!?-:;()״׳"
LATIN_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"

DESCENDERS = set("קךןףץ")
ASCENDERS = set("ל")
FINALS = set("ךםןףץ")


def charset(latin: bool = False) -> list[str]:
    chars = list(HEBREW + DIGITS + PUNCT)
    if latin:
        chars += list(LATIN_UPPER + LATIN_LOWER)
    return chars


# Latin file-name stem and Hebrew display name for every character.
_HEB_INFO = {
    "א": ("alef", "אל״ף"), "ב": ("bet", "בי״ת"), "ג": ("gimel", "גימ״ל"),
    "ד": ("dalet", "דל״ת"), "ה": ("he", "ה״א"), "ו": ("vav", "וי״ו"),
    "ז": ("zayin", "זי״ן"), "ח": ("het", "חי״ת"), "ט": ("tet", "טי״ת"),
    "י": ("yod", "יו״ד"), "כ": ("kaf", "כ״ף"), "ך": ("final_kaf", "כ״ף סופית"),
    "ל": ("lamed", "למ״ד"), "מ": ("mem", "מ״ם"), "ם": ("final_mem", "מ״ם סופית"),
    "נ": ("nun", "נו״ן"), "ן": ("final_nun", "נו״ן סופית"), "ס": ("samekh", "סמ״ך"),
    "ע": ("ayin", "עי״ן"), "פ": ("pe", "פ״א"), "ף": ("final_pe", "פ״א סופית"),
    "צ": ("tsadi", "צד״י"), "ץ": ("final_tsadi", "צד״י סופית"), "ק": ("qof", "קו״ף"),
    "ר": ("resh", "רי״ש"), "ש": ("shin", "שי״ן"), "ת": ("tav", "תי״ו"),
}
_DIGIT_NAMES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_PUNCT_INFO = {
    ".": ("period", "נקודה"), ",": ("comma", "פסיק"), "!": ("exclam", "סימן קריאה"),
    "?": ("question", "סימן שאלה"), "-": ("hyphen", "מקף"), ":": ("colon", "נקודתיים"),
    ";": ("semicolon", "נקודה ופסיק"), "(": ("parenleft", "סוגר, בצורה הזאת"),
    ")": ("parenright", "סוגר, בצורה הזאת"), "״": ("gershayim", "גרשיים"), "׳": ("geresh", "גרש"),
}


def latin_name(ch: str) -> str:
    """The recommended file-name stem for a character (e.g. 'alef', 'A_upper')."""
    if ch in _HEB_INFO:
        return _HEB_INFO[ch][0]
    if ch in DIGITS:
        return ch
    if ch in _PUNCT_INFO:
        return _PUNCT_INFO[ch][0]
    if ch in LATIN_UPPER:
        return f"{ch}_upper"
    if ch in LATIN_LOWER:
        return ch
    return f"u{ord(ch):04X}"


def hebrew_name(ch: str) -> str:
    if ch in _HEB_INFO:
        return _HEB_INFO[ch][1]
    if ch in _PUNCT_INFO:
        return _PUNCT_INFO[ch][1]
    if ch in DIGITS:
        return f"הספרה {ch}"
    if ch in LATIN_UPPER:
        return f"האות האנגלית הגדולה {ch}"
    if ch in LATIN_LOWER:
        return f"האות האנגלית הקטנה {ch}"
    return ch


def glyph_name(ch: str) -> str:
    """PostScript glyph name (AGL-friendly)."""
    if ch == " ":
        return "space"
    if ch in DIGITS:
        return _DIGIT_NAMES[int(ch)]
    if ch in _PUNCT_INFO and ord(ch) < 128:
        return _PUNCT_INFO[ch][0]
    if ch in LATIN_UPPER or ch in LATIN_LOWER:
        return ch
    return f"uni{ord(ch):04X}"


def describe(ch: str) -> str:
    """'ש (shin)' style label for status lines."""
    return f"{ch} ({latin_name(ch)})"


# ---------------------------------------------------------------------------
# SVG file-name aliases: file name = the character itself, or a Latin name.
# ---------------------------------------------------------------------------

_EXTRA_ALIASES = {
    "ב": ["bet", "beit", "bait", "beth", "vet"],
    "ג": ["gimmel", "gimel"],
    "ד": ["daled", "dalet", "daleth"],
    "ה": ["he", "hei", "heh", "hey"],
    "ו": ["vav", "vaw", "waw"],
    "ז": ["zayin", "zain", "zayn"],
    "ח": ["het", "chet", "khet", "heth", "cheth"],
    "ט": ["tet", "teth"],
    "י": ["yod", "yud", "yodh", "jod"],
    "כ": ["kaf", "kaph", "khaf", "chaf", "caf"],
    "ל": ["lamed", "lamedh", "lamad"],
    "מ": ["mem"],
    "נ": ["nun", "noon"],
    "ס": ["samekh", "samech", "samek"],
    "ע": ["ayin", "ain", "ayn"],
    "פ": ["pe", "pei", "peh", "fe", "fei", "feh"],
    "צ": ["tsadi", "tsadik", "tzadi", "tzadik", "tsade", "sadi", "tsadiq", "tzade"],
    "ק": ["qof", "kof", "kuf", "qoph", "koof"],
    "ר": ["resh", "reish"],
    "ש": ["shin", "sin", "schin"],
    "ת": ["tav", "taf", "taw"],
    "א": ["alef", "aleph", "alif"],
}
_FINAL_BASE = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}


def _norm(stem: str) -> str:
    return re.sub(r"[^0-9a-z\u0590-\u05ff]", "", stem.lower())


def build_alias_map(chars: list[str]) -> dict[str, str]:
    """Normalised alias -> character. Case-sensitive single Latin letters are
    handled separately in resolve_svg_name()."""
    m: dict[str, str] = {}
    for ch in chars:
        m[_norm(latin_name(ch))] = ch
        if not (ch in LATIN_UPPER or ch in LATIN_LOWER):
            m[_norm(glyph_name(ch))] = ch
        m[f"u{ord(ch):04x}"] = ch
        m[f"uni{ord(ch):04x}"] = ch
        if not (ch in LATIN_UPPER or ch in LATIN_LOWER):
            m[ch] = ch
        if ch in DIGITS:
            m[_DIGIT_NAMES[int(ch)]] = ch
        if ch in LATIN_UPPER:
            lo = ch.lower()
            for pat in ("{}upper", "upper{}", "{}cap", "cap{}", "capital{}", "big{}", "{}big", "uc{}", "{}uc"):
                m[pat.format(lo)] = ch
        if ch in LATIN_LOWER:
            for pat in ("{}lower", "lower{}", "small{}", "{}small", "lc{}", "{}lc"):
                m[pat.format(ch)] = ch
    for ch, names in _EXTRA_ALIASES.items():
        if ch in chars:
            for n in names:
                m.setdefault(_norm(n), ch)
    for fin, base in _FINAL_BASE.items():
        if fin not in chars:
            continue
        bases = [_HEB_INFO[base][0]] + _EXTRA_ALIASES.get(base, [])
        for b in bases:
            b = _norm(b)
            for pat in ("final{}", "{}final", "{}sofit", "sofit{}", "{}sofi", "fin{}", "{}fin"):
                m[pat.format(b)] = fin
        m[f"{fin}"] = fin
    return m


def resolve_svg_name(stem: str, chars: list[str], alias: dict[str, str]) -> str | None:
    """Map a file-name stem (without .svg) to a character, or None."""
    stem = stem.strip()
    stem = re.sub(r"@\d+(\.\d+)?x$", "", stem)        # Illustrator '@1x' suffix
    # exact single character, case-sensitive (A.svg vs a.svg)
    if len(stem) == 1 and stem in chars:
        return stem
    key = _norm(stem)
    if key in alias:
        return alias[key]
    # 'myfont_alef', 'Artboard-final_kaf': try trailing token groups
    tokens = [t for t in re.split(r"[\s_\-\.]+", stem) if t]
    for i in range(1, len(tokens)):
        tail = tokens[i:]
        if len(tail) == 1 and len(tail[0]) == 1 and tail[0] in chars:
            return tail[0]
        k = _norm("".join(tail))
        if k in alias:
            return alias[k]
    return None


# ---------------------------------------------------------------------------
# Template page layout (A4 at 300 dpi). Coordinates are in pixels of the
# 300-dpi page unless a name ends in _MM.
# ---------------------------------------------------------------------------

DPI = 300
MM = DPI / 25.4
PAGE_W_MM, PAGE_H_MM = 210.0, 297.0
PAGE_W, PAGE_H = round(PAGE_W_MM * MM), round(PAGE_H_MM * MM)   # 2480 x 3508

MARK_SIZE_MM = 10.0
# centres of the registration marks: top-left, top-right, bottom-right, bottom-left
MARK_CENTERS_MM = [(15.0, 15.0), (195.0, 15.0), (195.0, 282.0), (15.0, 282.0)]

COLS, ROWS = 5, 5
PER_PAGE = COLS * ROWS
BOX_W_MM, BOX_H_MM = 28.0, 35.0
GRID_LEFT_MM, GRID_RIGHT_MM = 20.0, 190.0
COL_GAP_MM = (GRID_RIGHT_MM - GRID_LEFT_MM - COLS * BOX_W_MM) / (COLS - 1)
GRID_TOP_MM = 40.0
LABEL_H_MM = 5.0
ROW_PITCH_MM = 44.0

# Page code: a row of squares between the two top marks. It tells the reader
# which page this is, whether the Latin set is included, and which way is up.
CODE_SQ_MM = 4.0
CODE_GAP_MM = 1.5
CODE_Y_MM = 15.0
CODE_BITS = 9

# Em-box mapping: the writing box spans these font units vertically.
UPM = 1000
BOX_TOP_UNITS = 900
BOX_BOTTOM_UNITS = -350
XHEIGHT_UNITS = 550        # the dashed guide: top of a regular Hebrew letter
ASCENDER_GUIDE = 750       # SVG template only
DESCENDER_GUIDE = -250     # SVG template only
UNITS_PER_BOX_H = BOX_TOP_UNITS - BOX_BOTTOM_UNITS   # 1250
BOX_W_UNITS = UNITS_PER_BOX_H * BOX_W_MM / BOX_H_MM   # 1000


def mm(v: float) -> float:
    return v * MM


def box_rect_mm(slot: int) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of writing box `slot` (0..24) on its page.
    Slots run right-to-left, top-to-bottom, like Hebrew text."""
    row, col = divmod(slot, COLS)
    right = GRID_RIGHT_MM - col * (BOX_W_MM + COL_GAP_MM)
    left = right - BOX_W_MM
    top = GRID_TOP_MM + row * ROW_PITCH_MM + LABEL_H_MM
    return left, top, right, top + BOX_H_MM


def box_rect_px(slot: int) -> tuple[float, float, float, float]:
    return tuple(v * MM for v in box_rect_mm(slot))


def code_square_centers_mm() -> list[tuple[float, float]]:
    total = CODE_BITS * CODE_SQ_MM + (CODE_BITS - 1) * CODE_GAP_MM
    x0 = PAGE_W_MM / 2 - total / 2 + CODE_SQ_MM / 2
    return [(x0 + i * (CODE_SQ_MM + CODE_GAP_MM), CODE_Y_MM) for i in range(CODE_BITS)]


def encode_page_code(page_no: int, latin: bool) -> list[int]:
    """[1, 0, p3, p2, p1, p0, latin, parity, 1] -- page_no is 1..15."""
    p = [(page_no >> s) & 1 for s in (3, 2, 1, 0)]
    lat = 1 if latin else 0
    parity = (sum(p) + lat) % 2
    return [1, 0, *p, lat, parity, 1]


def decode_page_code(bits: list[int]) -> tuple[int, bool] | None:
    if len(bits) != CODE_BITS or bits[0] != 1 or bits[1] != 0 or bits[8] != 1:
        return None
    p = bits[2:6]
    lat = bits[6]
    if (sum(p) + lat) % 2 != bits[7]:
        return None
    page_no = p[0] * 8 + p[1] * 4 + p[2] * 2 + p[3]
    if page_no < 1:
        return None
    return page_no, bool(lat)


def pages_needed(n_chars: int) -> int:
    return (n_chars + PER_PAGE - 1) // PER_PAGE


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_LTR_RUN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9 .,:/%+\-]*[A-Za-z0-9])?")
_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "<": ">", ">": "<", "{": "}", "}": "{"}


def visual_order(text: str) -> str:
    """Minimal bidi for one right-to-left line, so Pillow (which draws strictly
    left-to-right without libraqm) shows Hebrew in the right order. Digit and
    Latin runs keep their own left-to-right order."""
    parts: list[tuple[str, bool]] = []      # (text, is_ltr)
    pos = 0
    for m in _LTR_RUN.finditer(text):
        if m.start() > pos:
            parts.append((text[pos:m.start()], False))
        parts.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], False))
    out = []
    for chunk, is_ltr in reversed(parts):
        if is_ltr:
            out.append(chunk)
        else:
            out.append("".join(_MIRROR.get(c, c) for c in reversed(chunk)))
    return "".join(out)


def find_ui_font(bold: bool = False) -> str | None:
    """A system font with Hebrew glyphs, for labels on the template and preview."""
    windir = os.environ.get("WINDIR", r"C:\Windows")
    names = (["arialbd.ttf", "segoeuib.ttf", "tahomabd.ttf"] if bold else []) + [
        "arial.ttf", "segoeui.ttf", "tahoma.ttf", "david.ttf", "gisha.ttf",
    ]
    candidates = [Path(windir) / "Fonts" / n for n in names] + [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def pil_font(path: str | None, size: int):
    """Pillow font with the basic layout engine: text is already in visual
    order (see visual_order), so libraqm must not reorder it again."""
    from PIL import ImageFont

    if not path:
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)


def safe_filename(name: str) -> str:
    """Windows-safe file name that keeps Hebrew."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().rstrip(".")
    return s or "MyFont"


_TRANSLIT = dict(zip("אבגדהוזחטיכךלמםנןסעפףצץקרשת",
                     ["a", "b", "g", "d", "h", "v", "z", "h", "t", "y", "k", "k", "l", "m", "m",
                      "n", "n", "s", "a", "p", "f", "tz", "tz", "k", "r", "sh", "t"]))


def postscript_name(family: str) -> str:
    """ASCII PostScript name (no spaces, max 63 chars) derived from any name."""
    words = re.split(r"\s+", family.strip())
    out = []
    for w in words:
        t = "".join(_TRANSLIT.get(c, c) for c in w)
        t = re.sub(r"[^A-Za-z0-9]", "", t)
        if t:
            out.append(t[0].upper() + t[1:])
    ps = "".join(out)[:50] or "MyFont"
    if ps[0].isdigit():
        ps = "F" + ps
    return ps + "-Regular"
