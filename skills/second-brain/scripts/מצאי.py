# -*- coding: utf-8 -*-
"""המצאי של הספרייה: שורה בקטלוג לכל קובץ ב"מקורות/", מספר קבוע לכל קובץ, וטקסט נקי לקריאה.

מריצים אותו אחרי שנכנס חומר חדש ל"מקורות/":

    python _כלים/מצאי.py              (במק: python3 _כלים/מצאי.py)
    python _כלים/מצאי.py --dry-run    רק מראה מה ישתנה, ולא כותב כלום

מה הוא עושה:
- עובר על כל הקבצים ב"מקורות/", חוץ מ"מקורות/_רגיש/" ומקובצי מערכת (~$..., desktop.ini, Thumbs.db, ._..., .DS_Store).
  לכן ב"_רגיש" נשמרים רק רשימת השמות, "לא_לחלץ.txt", הקלטות פרטיות ותמלול גולמי. רשימת אנשי קשר, מסמך עם פרטי בנק
  וקובץ עלויות נשארים ב"מקורות/", והמצאי מגן עליהם: מזהה רשימה, מסתיר מספרים ומדלג על מה שב"לא_לחלץ.txt".
- כל שם מ"מקורות/_רגיש/שמות.txt" מוחלף ב[שם] בטקסט שנכתב לספרייה (השם הארוך קודם), וכל כתובת מייל ב[מייל].
- python _כלים/מצאי.py --names-from "מקורות/<גיליון>.xlsx" "<כותרת עמודת השמות>"
  מוסיף לרשימת השמות את העמודה הזאת, בלי להדפיס אף שם. כך ממלאים את הרשימה מרשימת אנשי קשר או הזמנות.
- python _כלים/מצאי.py --columns "מקורות/<גיליון>.xlsx" "מוצר,ספק,זמן אספקה"
  מחלץ רק את העמודות האלה ל"30_ספרייה/עמודות/". לקובץ שיש בו גם מידע לעבודה וגם עלויות או טלפונים.
- python _כלים/מצאי.py --names-from-email "מקורות/<מייל>.eml" [עוד מיילים]
  מוסיף לרשימת השמות את השמות מכותרות המיילים, בלי להדפיס. השמות של המקור ושל מי שמקלידה לא נכנסים.
- python _כלים/מצאי.py --mask-file "<תמלול גולמי>" "30_ספרייה/תמלולים/<id> <שם>.md"
  עותק נקי של תמלול: שמות מהרשימה, מיילים ומספרי בנק מוסתרים. בלי להקליד שם בפקודה.
- נותן לכל קובץ מספר בן שלוש ספרות (001). המספר לא משתנה: קובץ שעבר תיקייה או שינה שם נשאר עם המספר שלו
  (לפי טביעת האצבע, md5), וקובץ שנערך באותו מקום נשאר עם המספר שלו (לפי הנתיב). מספר שניתן לא עובר לקובץ אחר.
- שני קבצים זהים: אחד מקבל את הטקסט, והשני מסומן "כפיל", עם המספר של הראשון ב"כפיל_של".
- קובץ שנעלם נשאר בקטלוג, עם הטקסט שלו, במצב "חסר במקורות", כדי שההפניות אליו לא יישברו.
- "מקורות/_רגיש/לא_לחלץ.txt": נתיב או תבנית בכל שורה (למשל: חוזים/*). קובץ שמתאים מסומן "לא לחלץ", בלי טקסט.
- רשימת אנשי קשר (גיליון או CSV שרובו מיילים וטלפונים, או שהשם שלו אומר את זה) מסומנת "רשימת אנשי קשר".
  ממנה לא מחלצים כלום, ולא מדפיסים ממנה כלום.
- מחלץ טקסט ל"30_ספרייה/טקסט/<מספר> <שם>.md", עם כרטיס זיהוי בראש. סוגים: txt, md, csv, html, eml,
  docx (עם תיבות הטקסט, ההערות שבקובץ והסימונים בצבע), pptx, xlsx, ו־pdf כשמותקן pypdf.
  בלי pypdf, ליד PDF כתוב "לקריאה ב־Claude": Claude קורא PDF בעצמו.
- מסתיר בטקסט IBAN, מספרי כרטיס אשראי, תעודת זהות, מספר חשבון ומספר סניף. במקומם כתוב [הוסתר].
  הקובץ המקורי לא משתנה.
- כותב את "30_ספרייה/קטלוג.tsv". את "מחברת" ואת "הערות" ממלאות ביד (או Claude), והמצאי לא דורס אותן.
  "מחברת" הוא השדה החשוב ביותר: של מי החומר.

אחרי שתי הרצות ברצף, בלי שינוי במקורות, הקטלוג והטקסטים זהים בדיוק.
לא מדפיס אף פעם תוכן של קובץ: רק ספירות, ומספרים של שורות בקטלוג.
"""
import argparse
import csv
import datetime as dt
import email
import email.header
import email.policy
import email.utils
import fnmatch
import hashlib
import html
import io
import json
import logging
import os
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:  # לא חובה. בלעדיו PDF מסומן "לקריאה ב־Claude"
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)
except ImportError:
    pypdf = None

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.dirname(HERE)
SRC = os.path.join(BRAIN, "מקורות")
SENSITIVE = "_רגיש"
NO_EXTRACT_FILE = os.path.join(SRC, SENSITIVE, "לא_לחלץ.txt")
LIB = os.path.join(BRAIN, "30_ספרייה")
TEXT_DIR = os.path.join(LIB, "טקסט")
TRANS_DIR = os.path.join(LIB, "תמלולים")
CATALOG = os.path.join(LIB, "קטלוג.tsv")

COLS = ["id", "מצב", "סוג_קובץ", "md5", "KB", "מילים", "תאריך_מסמך", "נתיב", "כפיל_של", "טקסט", "מחברת", "הערות"]

ACTIVE, OLD, DUP, MISSING, NO_EXTRACT, CONTACTS = "פעיל", "ישן", "כפיל", "חסר במקורות", "לא לחלץ", "רשימת אנשי קשר"
STATUS_ORDER = [ACTIVE, OLD, DUP, MISSING, NO_EXTRACT, CONTACTS]

READ_IN_CLAUDE = "לקריאה ב־Claude"
IMAGE_NOTE = "תמונה"
MEDIA_NOTE = "הקלטה: להריץ תמלול.py"
UNSUPPORTED_NOTE = "סוג קובץ שהמצאי לא קורא"
EMPTY_NOTE = "אין טקסט בקובץ"
ERROR_NOTE = "החילוץ נכשל"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".svg"}
MEDIA_EXT = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".opus", ".wma", ".amr",
             ".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv", ".wmv", ".3gp"}
SHEET_EXT = {".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".ods", ".numbers"}
KIND = {".txt": "טקסט", ".md": "טקסט", ".csv": "גיליון CSV", ".tsv": "גיליון", ".html": "דף אינטרנט",
        ".htm": "דף אינטרנט", ".eml": "מייל", ".docx": "מסמך Word", ".docm": "מסמך Word", ".dotx": "מסמך Word",
        ".pptx": "מצגת", ".xlsx": "גיליון Excel", ".xlsm": "גיליון Excel", ".pdf": "PDF"}
CONTACT_WORDS = ("אנשי קשר", "רשימת לקוחות", "מתעניינ", "נרשמ", "רוכשות", "לקוחות")
OLD_DIRS = {"ישן", "ישנים", "גרסה ישנה", "גירסה ישנה", "ארכיון"}
JUNK_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


def junk(name):
    return name.startswith("~$") or name.startswith("._") or name.lower() in JUNK_NAMES


# ---------- הסתרה של מספרים אישיים ----------

HIDDEN = "[הוסתר]"
IBAN_RE = re.compile(r"(?<![A-Za-z0-9])IL\d\d(?: ?\d){19}(?![0-9])", re.I)
CARD_RE = re.compile(r"(?<![A-Za-z0-9])\d(?:[ -]?\d){12,18}(?![A-Za-z0-9])")
ID_RE = re.compile(r"((?:ת\.ז\.?|ת[\"״'׳]ז|תעודת\s+זהות)[^\d\n]{0,20}?)(\d{8}-?\d)(?!\d)")
ACCOUNT_RE = re.compile(r"((?<![א-ת])[ובלהמ]?חשבון(?![א-ת])[^\d\n]{0,20}?)(\d[\d\-/ ]*\d)")
BRANCH_RE = re.compile(r"((?<![א-ת])[ובלהמ]?סניף(?![א-ת])[^\d\n]{0,20}?)(\d{1,4})(?!\d)")
BANK_WINDOW = 3  # חשבון וסניף נכתבים לפעמים בשורות נפרדות, ליד המילה "בנק"
# בטבלה: בעמודה שהכותרת שלה אומרת חשבון, סניף, תעודת זהות או כרטיס, המספרים מוסתרים
SENSITIVE_HEADER = re.compile(r"חשבון|סניף|ת\.?ז|ת[\"״'׳]ז|תעודת\s*זהות|IBAN|אשראי|כרטיס", re.I)


def luhn(digits):
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


NAMES_FILE = os.path.join(SRC, SENSITIVE, "שמות.txt")
NAME_MASK = "[שם]"
_NAME_PATS = None


def name_patterns():
    """השמות מ"מקורות/_רגיש/שמות.txt". כל שם מוחלף ב[שם] בטקסט שנכתב לספרייה, גם עם אות מוספית (ל, ו, ש…)."""
    global _NAME_PATS
    if _NAME_PATS is None:
        _NAME_PATS = []
        if os.path.exists(NAMES_FILE):
            with open(NAMES_FILE, encoding="utf-8-sig") as f:
                names = {l.strip() for l in f if l.strip() and not l.startswith("#")}
            # הארוך קודם: "שם פרטי ומשפחה" לפני "שם פרטי", אחרת שם המשפחה נשאר גלוי
            for n in sorted(names, key=len, reverse=True):
                _NAME_PATS.append(re.compile(r"(?<![א-תA-Za-z])([ובלהמשכ]?)%s(?![א-תA-Za-z])" % re.escape(n), re.I))
    return _NAME_PATS


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
EMAIL_MASK = "[מייל]"


def redact(text):
    for pat in name_patterns():
        text = pat.sub(lambda m: m.group(1) + NAME_MASK, text)
    text = EMAIL_RE.sub(EMAIL_MASK, text)
    text = IBAN_RE.sub(HIDDEN, text)
    text = CARD_RE.sub(lambda m: HIDDEN if luhn(re.sub(r"\D", "", m.group(0))) else m.group(0), text)
    text = ID_RE.sub(lambda m: m.group(1) + HIDDEN, text)

    def account(m):
        return m.group(1) + HIDDEN if len(re.sub(r"\D", "", m.group(2))) >= 4 else m.group(0)
    lines = text.split("\n")
    near = [i for i, line in enumerate(lines) if re.search(r"חשבון|בנק", line)]
    for i, line in enumerate(lines):
        if any(abs(i - j) <= BANK_WINDOW for j in near):
            line = ACCOUNT_RE.sub(account, line)
            lines[i] = BRANCH_RE.sub(lambda m: m.group(1) + HIDDEN, line)
    return "\n".join(lines)


# ---------- קריאה של טקסט ----------

def decode(raw):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    for enc in ("utf-8-sig", "cp1255"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def t_plain(path):
    with open(path, "rb") as f:
        return decode(f.read())


def read_table(path):
    """CSV או TSV: רשימה של שורות, וכל שורה רשימה של תאים."""
    with open(path, "rb") as f:
        text = decode(f.read())
    if path.lower().endswith(".tsv"):
        dialect = csv.excel_tab
    else:
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def t_table(rows):
    """שורות של טבלה, תא אחרי תא. בעמודה רגישה (לפי הכותרת) מספר מוחלף ב[הוסתר]."""
    out, hidden = [], set()
    for row in rows:
        cells = [c.strip() for c in row]
        if not any(cells):
            continue
        if not out:
            hidden = {i for i, c in enumerate(cells) if SENSITIVE_HEADER.search(c)}
        elif hidden:
            cells = [HIDDEN if i in hidden and re.search(r"\d{2}", c) else c for i, c in enumerate(cells)]
        out.append(" | ".join(c for c in cells if c))
    return "\n".join(out)


class _Html(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer",
             "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "hr", "title", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(markup):
    p = _Html()
    p.feed(markup)
    p.close()
    lines = [re.sub(r"[ \t\r\f\v]+", " ", l).strip(" |") for l in "".join(p.out).split("\n")]
    return "\n".join(l.strip() for l in lines if l.strip())


def t_html(path):
    return html_to_text(t_plain(path))


def _bytes_text(raw, charset):
    cs = re.sub(r"-[ie]$", "", (charset or "").lower())  # iso-8859-8-i: פייתון מכיר רק iso-8859-8
    for enc in (cs, "utf-8", "cp1255"):
        if not enc or enc == "unknown-8bit":
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _header(raw):
    """כותרת של מייל, מפוענחת (=?...?=), גם בקידוד עברי שפייתון לא מכיר בשמו."""
    if raw is None:
        return ""
    raw = str(raw)
    if any("\udc80" <= ch <= "\udcff" for ch in raw):  # בתים של 8 סיביות בלי קידוד מוצהר
        raw = _bytes_text(raw.encode("ascii", "surrogateescape"), None)
    try:
        parts = email.header.decode_header(raw)
    except (ValueError, LookupError):
        return re.sub(r"\s+", " ", raw).strip()
    out = [_bytes_text(p, cs) if isinstance(p, bytes) else p for p, cs in parts]
    return re.sub(r"\s+", " ", "".join(out)).strip()


def read_eml(path):
    with open(path, "rb") as f:
        return email.message_from_binary_file(f, policy=email.policy.compat32)


def t_eml(path):
    msg = read_eml(path)
    lines = []
    for h, label in (("From", "מאת"), ("To", "אל"), ("Date", "תאריך"), ("Subject", "נושא")):
        value = _header(msg.get(h))
        if value:
            lines.append(f"**{label}:** {value}")
    plain = rich = None
    names = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename or (part.get("Content-Disposition") or "").lower().startswith("attachment"):
            if filename:
                names.append(_header(filename))
            continue
        if part.get_content_type() == "text/plain" and plain is None:
            plain = part
        elif part.get_content_type() == "text/html" and rich is None:
            rich = part
    body = plain or rich
    text = _bytes_text(body.get_payload(decode=True) or b"", body.get_content_charset()) if body else ""
    if body is not None and body is rich:
        text = html_to_text(text)
    lines += ["", text.replace("\r\n", "\n").strip()]
    if names:
        lines += ["", "## קבצים מצורפים", ""] + [f"- {n}" for n in names]
    return "\n".join(lines)


def eml_date(path):
    try:
        d = email.utils.parsedate_to_datetime(str(read_eml(path).get("Date", "")))
        return fmt_date(d.date()) if d else ""
    except (TypeError, ValueError, IndexError):
        return ""


# ---------- קובצי אופיס, בלי ספריות חיצוניות ----------

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DC = "{http://purl.org/dc/terms/}"


def _rels(z, part):
    """הקשרים של חלק בקובץ: {rId: (סוג, הנתיב המלא בתוך הקובץ)}."""
    folder, name = posixpath.split(part)
    rels_path = posixpath.join(folder, "_rels", name + ".rels")
    if rels_path not in z.namelist():
        return {}
    out = {}
    for rel in ET.fromstring(z.read(rels_path)).findall(PKG + "Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        target = rel.get("Target") or ""
        full = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
        out[rel.get("Id")] = (rel.get("Type") or "", full)
    return out


def office_date(path):
    try:
        with zipfile.ZipFile(path) as z:
            if "docProps/core.xml" not in z.namelist():
                return ""
            root = ET.fromstring(z.read("docProps/core.xml"))
        for tag in ("modified", "created"):
            el = root.find(DC + tag)
            if el is not None and el.text:
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})", el.text.strip())
                if m:
                    return f"{int(m.group(3))}.{int(m.group(2))}.{m.group(1)}"
    except (zipfile.BadZipFile, ET.ParseError, OSError, KeyError):
        return ""
    return ""


def _w_text(el):
    """הטקסט של קטע בוורד, בלי תיבות טקסט, בלי העתק הגיבוי שלהן, ובלי טקסט שנמחק במעקב שינויים."""
    out = []

    def rec(e):
        for c in e:
            if c.tag in (MC_FALLBACK, W + "txbxContent", W + "delText", W + "instrText"):
                continue
            if c.tag == W + "t":
                out.append(c.text or "")
            elif c.tag == W + "tab":
                out.append("\t")
            elif c.tag in (W + "br", W + "cr"):
                out.append("\n")
            elif c.tag == W + "noBreakHyphen":
                out.append("-")
            rec(c)
    rec(el)
    return "".join(out)


def _boxes(el):
    """תיבות הטקסט בתוך קטע, בלי העתק הגיבוי, ובלי תיבה שבתוך תיבה (היא נקראת עם התיבה שלה)."""
    for c in el:
        if c.tag == MC_FALLBACK:
            continue
        if c.tag == W + "txbxContent":
            yield c
            continue
        yield from _boxes(c)


def _w_block(el, lines, seen):
    """פסקאות וטבלאות לפי הסדר. תיבת טקסט נכתבת מיד אחרי הפסקה שהיא מעוגנת בה."""
    for c in el:
        if c.tag == W + "p":
            lines.append(_w_text(c).rstrip())
            for box in _boxes(c):
                sub = []
                _w_block(box, sub, seen)
                for line in sub:
                    if line.strip() and line not in seen:
                        seen.add(line)
                        lines.append(line)
        elif c.tag == W + "tbl":
            for tr in c.findall(W + "tr"):
                cells = []
                for tc in tr.findall(W + "tc"):
                    sub = []
                    _w_block(tc, sub, seen)
                    cells.append(" / ".join(l.strip() for l in sub if l.strip()))
                if any(cells):
                    lines.append(" | ".join(cells))
        elif c.tag in (W + "sdt", W + "sdtContent", W + "customXml", W + "smartTag"):
            _w_block(c, lines, seen)


def _iter_skip(el, tag, skip):
    for c in el:
        if c.tag in skip:
            continue
        if c.tag == tag:
            yield c
        yield from _iter_skip(c, tag, skip)


HIGHLIGHT = {"yellow": "צהוב", "green": "ירוק", "cyan": "תכלת", "magenta": "ורוד", "blue": "כחול", "red": "אדום",
             "darkBlue": "כחול כהה", "darkCyan": "טורקיז כהה", "darkGreen": "ירוק כהה", "darkMagenta": "סגול",
             "darkRed": "אדום כהה", "darkYellow": "חרדל", "darkGray": "אפור כהה", "lightGray": "אפור בהיר",
             "black": "שחור", "white": "לבן"}
COLORS = {"FF0000": "אדום", "C00000": "אדום כהה", "FFC000": "כתום", "FFFF00": "צהוב", "92D050": "ירוק בהיר",
          "00B050": "ירוק", "00B0F0": "תכלת", "0070C0": "כחול", "002060": "כחול כהה", "7030A0": "סגול"}


def _color(hexv):
    return COLORS.get(hexv, "#" + hexv)


def _mark(rpr):
    """איך רצף טקסט מסומן: מרקר, צבע רקע או צבע גופן. ריק כשהוא רגיל."""
    if rpr is None:
        return ""
    parts = []
    h = rpr.find(W + "highlight")
    if h is not None and h.get(W + "val") not in (None, "none"):
        parts.append("מרקר " + HIGHLIGHT.get(h.get(W + "val"), h.get(W + "val")))
    shd = rpr.find(W + "shd")
    if shd is not None:
        fill = (shd.get(W + "fill") or "").upper()
        if fill and fill not in ("AUTO", "FFFFFF"):
            parts.append("רקע " + _color(fill))
    col = rpr.find(W + "color")
    if col is not None:
        theme = col.get(W + "themeColor") or ""
        val = (col.get(W + "val") or "").upper()
        if theme and theme not in ("text1", "dark1", "background1", "light1", "hyperlink", "followedHyperlink"):
            parts.append(f"צבע גופן מערכת הנושא ({theme})")
        elif not theme and val and val not in ("AUTO", "000000"):
            parts.append("צבע גופן " + _color(val))
    return ", ".join(parts)


def _w_marks(root):
    items, seen = [], set()
    for p in _iter_skip(root, W + "p", {MC_FALLBACK}):
        label, buf = "", []

        def flush():
            text = re.sub(r"\s+", " ", "".join(buf)).strip()
            if label and text and (label, text) not in seen:
                seen.add((label, text))
                items.append((label, text if len(text) <= 300 else text[:297] + "…"))
        for r in _iter_skip(p, W + "r", {MC_FALLBACK, W + "txbxContent"}):
            run_label = _mark(r.find(W + "rPr"))
            if run_label != label:
                flush()
                label, buf = run_label, []
            buf.append(_w_text(r))
        flush()
    return items


def _w_comments(z, root):
    if "word/comments.xml" not in z.namelist():
        return []
    # המילים שההערה מסמנת, והפסקה שבה היא מתחילה
    active, anchors, paras = [], {}, {}

    def rec(e, para):
        for c in e:
            if c.tag in (MC_FALLBACK, W + "delText"):
                continue
            if c.tag == W + "p":
                for cid in active:
                    anchors[cid].append(" ")
                rec(c, c)
                continue
            if c.tag == W + "commentRangeStart":
                cid = c.get(W + "id")
                active.append(cid)
                anchors.setdefault(cid, [])
                paras.setdefault(cid, para)
            elif c.tag == W + "commentRangeEnd":
                if c.get(W + "id") in active:
                    active.remove(c.get(W + "id"))
            elif c.tag == W + "commentReference":
                paras.setdefault(c.get(W + "id"), para)
            elif c.tag == W + "t":
                for cid in active:
                    anchors[cid].append(c.text or "")
            rec(c, para)
    rec(root, None)
    out = []
    for c in ET.fromstring(z.read("word/comments.xml")).findall(W + "comment"):
        cid = c.get(W + "id")
        lines = []
        _w_block(c, lines, set())
        text = " / ".join(l.strip() for l in lines if l.strip())
        date = c.get(W + "date") or ""
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date)
        when = f"{int(m.group(3))}.{int(m.group(2))}.{m.group(1)}" if m else ""
        anchor = re.sub(r"\s+", " ", "".join(anchors.get(cid, []))).strip()
        para = paras.get(cid)
        para_text = re.sub(r"\s+", " ", _w_text(para)).strip() if para is not None else ""
        out.append((c.get(W + "author") or "", when, text, anchor, para_text))
    return out


def t_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        body = root.find(W + "body")
        lines = []
        _w_block(body if body is not None else root, lines, set())
        comments = _w_comments(z, root)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    marks = _w_marks(root)
    parts = [text]
    if comments:
        parts += ["", "## הערות בקובץ", ""]
        for author, when, note, anchor, para in comments:
            who = ", ".join(x for x in (f"**{author}**" if author else "", when) if x)
            parts.append(f"- {who}: {note}" if who else f"- {note}")
            if anchor:
                parts.append(f'  על המילים: "{anchor}"')
            if para and para != anchor:
                short = para if len(para) <= 200 else para[:197] + "…"
                parts.append(f'  בפסקה: "{short}"')
    if marks:
        parts += ["", "## סימונים", ""] + [f'- {label}: "{text}"' for label, text in marks]
    return "\n".join(parts)


def _a_lines(el):
    lines = []
    for p in el.iter(A + "p"):
        bits = []
        for c in p.iter():
            if c.tag == A + "t":
                bits.append(c.text or "")
            elif c.tag == A + "br":
                bits.append("\n")
        line = "".join(bits).strip()
        if line:
            lines.append(line)
    return lines


def t_pptx(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        rels = _rels(z, "ppt/presentation.xml")
        slides = []
        lst = ET.fromstring(z.read("ppt/presentation.xml")).find(P + "sldIdLst")
        for sid in (lst if lst is not None else []):
            rid = sid.get(R + "id")
            if rid in rels and rels[rid][1] in names:
                slides.append(rels[rid][1])
        if not slides:  # בלי רשימה: לפי המספר בשם, ולא לפי סדר האותיות (10 אחרי 9)
            slides = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                            key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        parts = []
        for i, part in enumerate(slides, 1):
            root = ET.fromstring(z.read(part))
            hidden = " (שקופית מוסתרת)" if root.get("show") == "0" else ""
            parts += [f"## שקופית {i}{hidden}", ""] + _a_lines(root)
            for typ, target in _rels(z, part).values():
                if typ.endswith("/notesSlide") and target in names:
                    notes = []
                    for sp in ET.fromstring(z.read(target)).iter(P + "sp"):
                        ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                        if ph is not None and ph.get("type") == "body":
                            notes += _a_lines(sp)
                    if notes:
                        parts += ["", "הערות הדובר:"] + notes
            parts.append("")
    return "\n".join(parts).strip()


def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref or "")
    n = 0
    for ch in (letters.group(0) if letters else ""):
        n = n * 26 + ord(ch) - 64
    return max(n - 1, 0)


def _s_text(el):
    """טקסט של מחרוזת באקסל, גם כשהיא בנויה מכמה קטעים. בלי ההגייה (rPh)."""
    t = el.find(S + "t")
    if t is not None:
        return t.text or ""
    return "".join((r.find(S + "t").text or "") for r in el.findall(S + "r") if r.find(S + "t") is not None)


def read_xlsx(path, max_rows=None):
    """[(שם הגיליון, מוסתר?, שורות, כמה שורות היו בסך הכול)]. כל שורה היא רשימה של תאים לפי העמודה."""
    sheets = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = [_s_text(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(S + "si")]
        rels = _rels(z, "xl/workbook.xml")
        book = ET.fromstring(z.read("xl/workbook.xml"))
        for sh in book.iter(S + "sheet"):
            rid = sh.get(R + "id")
            if rid not in rels or rels[rid][1] not in names:
                continue
            root = ET.fromstring(z.read(rels[rid][1]))
            rows, total = [], 0
            for row in root.iter(S + "row"):
                total += 1
                if max_rows is not None and len(rows) >= max_rows:
                    continue
                cells = {}
                for c in row.findall(S + "c"):
                    kind, v = c.get("t"), c.find(S + "v")
                    if kind == "s" and v is not None and (v.text or "").isdigit() and int(v.text) < len(shared):
                        value = shared[int(v.text)]
                    elif kind == "inlineStr" and c.find(S + "is") is not None:
                        value = _s_text(c.find(S + "is"))
                    else:
                        value = v.text if v is not None and v.text else ""
                    if value.strip():
                        cells[_col_index(c.get("r"))] = value
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            sheets.append((sh.get("name") or "", sh.get("state") in ("hidden", "veryHidden"), rows, total))
    return sheets


SHEET_ROWS = 1000


def t_xlsx(path):
    parts = []
    for name, hidden, rows, total in read_xlsx(path, SHEET_ROWS):
        parts += [f"## גיליון: {name}" + (" (מוסתר)" if hidden else ""), "", t_table(rows)]
        if total > SHEET_ROWS:
            parts.append(f"(בגיליון יש עוד {total - SHEET_ROWS} שורות, והן לא נכתבו כאן)")
        parts.append("")
    return "\n".join(parts).strip()


# ---------- PDF ----------

UNI = re.compile(r"(?:/uni[0-9A-Fa-f]{4})+")
PUNCT = ".?!:,;"


def fix_glyph_names(text):
    """יש PDF שבו העברית שמורה כשמות של תווים (/uni05E9/uni05DC...) בסדר הפוך: מפענחים והופכים."""
    def dec(m):
        chars = [chr(int(c, 16)) for c in re.findall(r"/uni([0-9A-Fa-f]{4})", m.group(0))]
        return "".join(reversed(chars))
    return UNI.sub(dec, text)


def reverse_visual_line(line):
    """שורה שיצאה בסדר חזותי: מילים מופרדות בשני רווחים, והמילה האחרונה ראשונה.
    סימן פיסוק בתחילת מילה שייך לסוף שלה; סימן בסוף מילה שייך למילה שלפניה."""
    tokens = [t for t in re.split(r" {2,}", line.strip()) if t]
    out = []
    for tok in reversed(tokens):
        trail = len(tok) - len(tok.rstrip(PUNCT))
        if trail and out:
            out[-1] += tok[len(tok) - trail:]
            tok = tok[:len(tok) - trail]
        lead = len(tok) - len(tok.lstrip(PUNCT))
        if lead:
            tok = tok[lead:] + tok[:lead]
        out.append(tok)
    return " ".join(out)


def fix_visual_order(text):
    """כשיותר מחצי משורות העברית בנויות ממילים שמופרדות ברווח כפול, הדף יצא בסדר חזותי: הופכים כל שורה כזאת."""
    lines = text.splitlines()
    heb = [ln for ln in lines if len(re.findall(r"[֐-׿]+", ln)) >= 4]
    visual = [ln for ln in heb if len(re.findall(r" {2,}", ln.strip())) >= 0.6 * (len(ln.split()) - 1)]
    if not heb or len(visual) * 2 <= len(heb):
        return text
    return "\n".join(reverse_visual_line(ln) if re.search(r"[֐-׿]", ln) and re.search(r"\S {2,}\S", ln)
                     else ln for ln in lines)


def t_pdf(path):
    reader = pypdf.PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, 1):
        pages += [f"## עמוד {i}", "", fix_visual_order(fix_glyph_names(page.extract_text() or "")), ""]
    return "\n".join(pages).strip()


def pdf_date(path):
    try:
        info = pypdf.PdfReader(path).metadata or {}
        m = re.search(r"(\d{4})(\d{2})(\d{2})", str(info.get("/ModDate") or info.get("/CreationDate") or ""))
        return f"{int(m.group(3))}.{int(m.group(2))}.{m.group(1)}" if m else ""
    except Exception:  # noqa: BLE001 - תאריך הוא תוספת, לא סיבה לעצור
        return ""


# ---------- רשימות אנשי קשר ----------

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _contactish(value):
    v = value.strip()
    if EMAIL.search(v):
        return True
    digits = re.sub(r"\D", "", v)
    return 9 <= len(digits) <= 13 and re.fullmatch(r"[+\d\s\-().]+", v) is not None


def looks_like_contacts(rows):
    """רוב התאים מיילים או טלפונים, או שיש עמודה שרובה מיילים או טלפונים."""
    cells = [c for row in rows for c in row if c and c.strip()]
    if not cells:
        return False
    hits = sum(1 for c in cells if _contactish(c))
    if hits * 2 > len(cells):
        return True
    columns = {}
    for row in rows:
        for i, c in enumerate(row):
            if c and c.strip():
                columns.setdefault(i, []).append(c)
    for values in columns.values():
        h = sum(1 for c in values if _contactish(c))
        if h >= 2 and h * 2 > len(values):
            return True
    return False


def sheet_rows(path, ext):
    if ext in (".csv", ".tsv"):
        return read_table(path)[:2000]
    if ext in (".xlsx", ".xlsm"):
        return [row for _n, _h, rows, _t in read_xlsx(path, 2000) for row in rows]
    return []


# ---------- עזרים ----------

def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_date(d):
    return f"{d.day}.{d.month}.{d.year}"


def clean_name(name):
    name = re.sub(r"[‎‏‪-‮⁦-⁩]", "", name)
    name = re.sub(r'[\\/:*?"<>|\t\r\n]', "_", name).strip(" .")
    return name[:60].strip() or "קובץ"


def cell(value):
    return re.sub(r"[\t\r\n]+", " ", str(value or "")).strip()


def is_old(rel):
    return any(part in OLD_DIRS for part in rel.split("/")[1:-1])


def load_no_extract():
    if not os.path.exists(NO_EXTRACT_FILE):
        return []
    with open(NO_EXTRACT_FILE, encoding="utf-8-sig") as f:
        pats = [l.strip().replace("\\", "/") for l in f if l.strip() and not l.lstrip().startswith("#")]
    return [p[len("מקורות/"):] if p.startswith("מקורות/") else p for p in pats]


def no_extract(rel, patterns):
    inner = rel[len("מקורות/"):]
    base = posixpath.basename(inner)
    for p in patterns:
        folder = p.rstrip("/")
        if fnmatch.fnmatchcase(inner, p) or inner.startswith(folder + "/"):
            return True
        if "/" not in p and fnmatch.fnmatchcase(base, p):
            return True
    return False


def read_catalog():
    if not os.path.exists(CATALOG):
        return []
    with open(CATALOG, encoding="utf-8-sig", newline="") as f:
        lines = [l.rstrip("\r\n") for l in f.read().split("\n")]
    lines = [l for l in lines if l.strip()]
    if not lines:
        return []
    head = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        cells += [""] * (len(head) - len(cells))
        row = {c: "" for c in COLS}
        row.update({k: v.strip() for k, v in zip(head, cells)})
        if row["id"].isdigit():
            rows.append(row)
    return rows


def read_card(path):
    """כרטיס הזיהוי בראש קובץ טקסט קיים: {שדה: ערך}, והטקסט שאחריו."""
    with open(path, encoding="utf-8-sig") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.S)
    if not m:
        return {}, content
    card = {}
    for line in m.group(1).split("\n"):
        mm = re.match(r"^([^:]+):\s?(.*)$", line)
        if mm:
            card[mm.group(1).strip()] = mm.group(2).strip()
    return card, m.group(2).lstrip("\n")


def card_text(row, kind, body):
    fields = [("id", row["id"]), ("נתיב", row["נתיב"]), ("סוג", kind), ("md5", row["md5"]),
              ("תאריך", row["תאריך_מסמך"]), ("מצב", row["מצב"]), ("מחברת", row["מחברת"]), ("הערות", row["הערות"])]
    head = "\n".join(f"{k}: {v}".rstrip() for k, v in fields)
    return f"---\n{head}\n---\n\n{body.strip()}\n"


def text_files_by_id():
    found = {}
    if os.path.isdir(TEXT_DIR):
        for n in sorted(os.listdir(TEXT_DIR)):
            m = re.match(r"^(\d{3,}) .*\.md$", n)
            if m:
                found.setdefault(m.group(1), []).append(n)
    return found


def transcript_for(fid):
    if not os.path.isdir(TRANS_DIR):
        return ""
    for n in sorted(os.listdir(TRANS_DIR)):
        if n.startswith(fid + " ") and n.endswith(".md"):
            return n
    return ""


def write_if_changed(path, content, dry):
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == content:
                return False
    if not dry:
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, path)
    return True


def words_in(text):
    return len(re.findall(r"\S+", text))


# ---------- החילוץ ----------

EXTRACT = {".txt": t_plain, ".md": t_plain, ".html": t_html, ".htm": t_html, ".eml": t_eml,
           ".docx": t_docx, ".docm": t_docx, ".dotx": t_docx, ".pptx": t_pptx, ".xlsx": t_xlsx, ".xlsm": t_xlsx}


def extract(path, ext, rows=None):
    """מחזיר ("text", הטקסט) או ("note", מה לכתוב בעמודה "טקסט")."""
    if ext in IMAGE_EXT:
        return "note", IMAGE_NOTE
    if ext in MEDIA_EXT:
        return "note", MEDIA_NOTE
    if ext == ".pdf":
        if pypdf is None:
            return "note", READ_IN_CLAUDE
        text = t_pdf(path)
        if words_in(re.sub(r"^## עמוד \d+$", "", text, flags=re.M)) < 5:
            return "note", READ_IN_CLAUDE  # כנראה סרוק: Claude קורא אותו כתמונה
        return "text", text
    if ext in (".csv", ".tsv"):
        text = t_table(rows if rows is not None else read_table(path))
    elif ext in EXTRACT:
        text = EXTRACT[ext](path)
    else:
        return "note", UNSUPPORTED_NOTE
    if not text.strip():
        return "note", EMPTY_NOTE
    return "text", text


def doc_date(path, ext):
    if ext in (".docx", ".docm", ".dotx", ".pptx", ".xlsx", ".xlsm"):
        return office_date(path)
    if ext == ".pdf" and pypdf is not None:
        return pdf_date(path)
    if ext == ".eml":
        return eml_date(path)
    return ""


# ---------- הריצה ----------

def scan():
    files = []
    for root, dirs, names in os.walk(SRC):
        rel_root = os.path.relpath(root, BRAIN).replace(os.sep, "/")
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (rel_root == "מקורות" and d == SENSITIVE))
        for n in sorted(names):
            if not junk(n):
                full = os.path.join(root, n)
                if os.path.isfile(full):
                    files.append({"rel": rel_root + "/" + n, "path": full, "ext": os.path.splitext(n)[1].lower()})
    files.sort(key=lambda f: f["rel"])
    return files


def assign_ids(files, prev):
    """מספר לכל קובץ: קודם נתיב ותוכן זהים, אחר כך אותו תוכן, ואחר כך אותו נתיב. כל שורה ישנה נתבעת פעם אחת."""
    claimed = set()

    def claim(f, rows):
        for r in sorted(rows, key=lambda r: (r["מצב"] == DUP or bool(r["כפיל_של"]), int(r["id"]))):
            if r["id"] not in claimed:
                claimed.add(r["id"])
                f["id"], f["prev"] = r["id"], r
                return

    by_both, by_md5, by_path = {}, {}, {}
    for r in prev:
        by_both.setdefault((r["נתיב"], r["md5"]), []).append(r)
        by_md5.setdefault(r["md5"], []).append(r)
        by_path.setdefault(r["נתיב"], []).append(r)
    for index, key in ((by_both, lambda f: (f["rel"], f["md5"])), (by_md5, lambda f: f["md5"]),
                       (by_path, lambda f: f["rel"])):
        for f in files:
            if "id" not in f:
                claim(f, index.get(key(f), []))
    next_id = max([int(r["id"]) for r in prev] + [0]) + 1
    for f in files:
        if "id" not in f:
            f["id"], f["prev"] = f"{next_id:03d}", None
            next_id += 1
    return [r for r in prev if r["id"] not in claimed]


def pick_primaries(files):
    """בכל קבוצה של קבצים זהים: הקובץ שכבר היה הראשי נשאר ראשי. אחרת, הראשון לפי הנתיב."""
    groups = {}
    for f in files:
        groups.setdefault(f["md5"], []).append(f)
    for group in groups.values():
        was_primary = [f for f in group if f["prev"] and f["prev"]["md5"] == f["md5"]
                       and not f["prev"]["כפיל_של"] and f["prev"]["מצב"] != DUP]
        primary = min(was_primary, key=lambda f: int(f["id"])) if was_primary else group[0]
        for f in group:
            f["dup_of"] = "" if f is primary else primary["id"]


def header_hint(rows):
    """שורת הכותרות של גיליון, בלי נתונים: השורה הראשונה (מתוך עשר) שיש בה לפחות שלושה תאים קצרים,
    בלי ספרות, בלי מייל ובלי טלפון. כותרות אפשר להראות; שורות של אנשים לא."""
    for row in rows[:10]:
        cells = [c.strip() for c in row if c and c.strip()]
        if len(cells) >= 3 and all(len(c) <= 30 and not re.search(r"\d", c) and not _contactish(c) for c in cells):
            return " | ".join(cells)
    return "(לא נמצאה שורה שנראית כמו כותרות)"


def names_from(rel, header):
    """מוסיף ל"מקורות/_רגיש/שמות.txt" את כל הערכים בעמודה אחת של גיליון, בלי להדפיס אותם.
    כך רשימת השמות מתמלאת מרשימת אנשי קשר, בלי ששם אחד יופיע בשיחה או במסוף."""
    path = os.path.join(BRAIN, rel) if not os.path.isabs(rel) else rel
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path) or ext not in (".csv", ".tsv", ".xlsx", ".xlsm"):
        print("לא נמצא גיליון בנתיב הזה (csv, tsv או xlsx). שום דבר לא נכתב.")
        sys.exit(1)
    rows = sheet_rows(path, ext)
    col = None
    for r, row in enumerate(rows[:10]):
        for i, c in enumerate(row):
            if c and header.strip() and header.strip() in c:
                col, start = i, r + 1
                break
        if col is not None:
            break
    if col is None:
        print(f'לא נמצאה עמודה שהכותרת שלה כוללת "{header}". שורת הכותרות: ' + header_hint(rows))
        sys.exit(1)
    values = [(row[col] if col < len(row) else "") or "" for row in rows[start:]]
    n = add_names(values)
    print(("נוסף שם אחד" if n == 1 else f"נוספו {count_he(n)}") + " לרשימת השמות (מקורות/_רגיש/שמות.txt). השמות עצמם לא הודפסו.")


def count_he(n):
    return "שם אחד" if n == 1 else f"{n} שמות"


def own_names():
    """המקור ומי שמקלידה, מ"_כלים/הגדרות.json". השמות שלהן לא נכנסים לרשימת השמות הרגישים."""
    try:
        with open(os.path.join(HERE, "הגדרות.json"), encoding="utf-8-sig") as f:
            s = json.load(f)
        return {w for k in ("decider", "operator") for w in str(s.get(k, "")).split() if w}
    except (OSError, ValueError):
        return set()


def add_names(new):
    """מוסיף שמות לרשימה, בלי כפילויות ובלי להדפיס אותם. מחזיר כמה נוספו."""
    existing = set()
    if os.path.exists(NAMES_FILE):
        with open(NAMES_FILE, encoding="utf-8-sig") as f:
            existing = {l.strip() for l in f if l.strip() and not l.startswith("#")}
    mine = own_names()
    added = []
    for v in new:
        v = re.sub(r"\s+", " ", v).strip().strip('"\'')
        if not v or v in existing or v in added or _contactish(v) or set(v.split()) & mine:
            continue
        added.append(v)
    os.makedirs(os.path.dirname(NAMES_FILE), exist_ok=True)
    with open(NAMES_FILE, "a", encoding="utf-8") as f:
        for v in added:
            f.write(v + "\n")
    return len(added)


def names_from_email(paths):
    """מוסיף לרשימת השמות את השמות שבכותרות של מיילים (מאת, אל, עותק), בלי להדפיס.
    השמות של המקור ושל מי שמקלידה (מההגדרות) לא נכנסים."""
    from email.utils import getaddresses
    found = []
    for rel in paths:
        path = os.path.join(BRAIN, rel) if not os.path.isabs(rel) else rel
        if not os.path.isfile(path) or not path.lower().endswith(".eml"):
            print(f"לא נמצא מייל (eml) בנתיב: {rel}")
            continue
        msg = read_eml(path)
        heads = [_header(msg.get(h)) for h in ("From", "To", "Cc", "Reply-To") if msg.get(h)]
        for name, _addr in getaddresses(heads):
            if name and re.search(r"[א-תA-Za-z]", name):
                found.append(name)
    n = add_names(found)
    print(("נוסף שם אחד" if n == 1 else f"נוספו {count_he(n)}") + " לרשימת השמות (מקורות/_רגיש/שמות.txt). השמות עצמם לא הודפסו.")


def mask_file(src, dst):
    """כותב עותק של קובץ טקסט שבו כל שם מהרשימה הוא [שם], וכל מייל ומספר בנק מוסתרים.
    כך מכינים עותק נקי של תמלול, בלי להקליד שם בפקודה."""
    src_p = os.path.join(BRAIN, src) if not os.path.isabs(src) else src
    dst_p = os.path.join(BRAIN, dst) if not os.path.isabs(dst) else dst
    with open(src_p, encoding="utf-8-sig") as f:
        text = f.read()
    os.makedirs(os.path.dirname(dst_p), exist_ok=True)
    with open(dst_p, "w", encoding="utf-8") as f:
        f.write(redact(text))
    print(f"נכתב עותק נקי: {os.path.relpath(dst_p, BRAIN)}")


COLUMNS_DIR = os.path.join(LIB, "עמודות")


def columns_from(rel, wanted):
    """מחלץ מגיליון רק את העמודות שהעבודה צריכה, לקובץ ב"30_ספרייה/עמודות/". השאר (עלות, איש קשר, טלפון)
    נשאר בקובץ המקורי. השורות לא מודפסות: רק כמה שורות נכתבו ולאן."""
    path = os.path.join(BRAIN, rel) if not os.path.isabs(rel) else rel
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path) or ext not in (".csv", ".tsv", ".xlsx", ".xlsm"):
        print("לא נמצא גיליון בנתיב הזה (csv, tsv או xlsx). שום דבר לא נכתב.")
        sys.exit(1)
    names = [w.strip() for w in wanted.split(",") if w.strip()]
    rows = sheet_rows(path, ext)
    header_row, idx = None, []
    for r, row in enumerate(rows[:10]):
        found = []
        for w in names:
            col = next((i for i, c in enumerate(row) if c and w in c), None)
            found.append(col)
        if all(c is not None for c in found):
            header_row, idx = r, found
            break
    if header_row is None:
        print("לא נמצאה שורת כותרות שיש בה את כל העמודות: " + ", ".join(names) + ". שום דבר לא נכתב. "
              "שורת הכותרות: " + header_hint(rows))
        sys.exit(1)
    out_rows = []
    for row in rows[header_row + 1:]:
        cells = [(row[i] if i < len(row) else "") or "" for i in idx]
        cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
        if not any(cells) or any(_contactish(c) for c in cells):
            continue  # שורה ריקה, או עמודה שנבחרה בטעות ויש בה טלפון או מייל
        out_rows.append([redact(c).replace("|", "/") for c in cells])
    prev = {r["נתיב"]: r for r in read_catalog()}
    rel_norm = os.path.relpath(path, BRAIN).replace(os.sep, "/")
    fid = (prev.get(rel_norm) or {}).get("id", "")
    stem = clean_name(os.path.splitext(os.path.basename(path))[0])
    os.makedirs(COLUMNS_DIR, exist_ok=True)
    out = os.path.join(COLUMNS_DIR, f"{stem} - עמודות נבחרות.md")
    lines = [f"# {stem}: עמודות נבחרות", "",
             f"**מקור:** {('[#' + fid + '] ') if fid else ''}{rel_norm}",
             "**מה כאן:** רק העמודות " + ", ".join(names) + ". השאר נשאר בקובץ המקורי, ולא מצוטט.", "",
             "| " + " | ".join(names) + " |", "|" + "---|" * len(names)]
    lines += ["| " + " | ".join(c) + " |" for c in out_rows]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"נכתבו {len(out_rows)} שורות, רק בעמודות שנבחרו, ל־30_ספרייה/עמודות/{os.path.basename(out)}. הן לא הודפסו כאן.")


def main():
    ap = argparse.ArgumentParser(description="המצאי של הספרייה")
    ap.add_argument("--dry-run", action="store_true", help="רק להראות מה ישתנה, בלי לכתוב")
    ap.add_argument("--names-from", nargs=2, metavar=("גיליון", "כותרת_העמודה"),
                    help='מוסיף לרשימת השמות את העמודה הזאת מגיליון, בלי להדפיס. למשל: --names-from "מקורות/הזמנות.xlsx" "שם"')
    ap.add_argument("--columns", nargs=2, metavar=("גיליון", "עמודות"),
                    help='מחלץ רק את העמודות האלה מגיליון, בלי להדפיס. למשל: --columns "מקורות/ספקים.xlsx" "מוצר,ספק,זמן אספקה"')
    ap.add_argument("--names-from-email", nargs="+", metavar="מייל",
                    help="מוסיף לרשימת השמות את השמות מכותרות המיילים (מאת, אל, עותק), בלי להדפיס")
    ap.add_argument("--mask-file", nargs=2, metavar=("מקור", "יעד"),
                    help="עותק נקי של קובץ טקסט: שמות מהרשימה, מיילים ומספרי בנק מוסתרים. לתמלול")
    args = ap.parse_args()
    if args.names_from_email:
        names_from_email(args.names_from_email)
        return
    if args.mask_file:
        mask_file(*args.mask_file)
        return
    if args.names_from:
        names_from(*args.names_from)
        return
    if args.columns:
        columns_from(*args.columns)
        return
    dry = args.dry_run

    if not os.path.isdir(SRC):
        print('אין במוח הזה תיקייה בשם "מקורות". המצאי עובר על הקבצים שבה, ולכן לא נעשה כלום.')
        sys.exit(1)

    prev = read_catalog()
    files = scan()
    for f in files:
        f["md5"] = md5_of(f["path"])
    missing = assign_ids(files, prev)
    pick_primaries(files)
    patterns = load_no_extract()
    existing_text = text_files_by_id()

    rows, problems, counts = [], [], {"new": 0, "written": 0, "removed": 0}
    keep_text = {}  # id -> שם קובץ הטקסט שנשאר
    cache = {}
    for f in files:
        old = f["prev"] or {}
        ext, rel = f["ext"], f["rel"]
        if not old:
            counts["new"] += 1
        row = {c: "" for c in COLS}
        row.update({"id": f["id"], "סוג_קובץ": ext.lstrip("."), "md5": f["md5"], "נתיב": rel,
                    "KB": str((os.path.getsize(f["path"]) + 1023) // 1024), "כפיל_של": f["dup_of"]})
        # מחברת והערות: מה שנכתב ביד נשאר. "?" נחשב ריק
        card = {}
        for name in existing_text.get(f["id"], []):
            card = read_card(os.path.join(TEXT_DIR, name))[0]
            break
        author = old.get("מחברת", "")
        if author in ("", "?"):
            author = card.get("מחברת", "")
        row["מחברת"] = cell(author) if author not in ("", "?") else "?"
        row["הערות"] = cell(old.get("הערות", "") or card.get("הערות", ""))

        sheet = None
        if no_extract(rel, patterns):
            row["מצב"] = NO_EXTRACT
        elif ext == ".vcf":
            row["מצב"] = CONTACTS
        elif ext in SHEET_EXT:
            base = os.path.basename(rel)
            if any(w in base for w in CONTACT_WORDS):
                row["מצב"] = CONTACTS
            else:
                try:
                    sheet = sheet_rows(f["path"], ext)
                except Exception:  # noqa: BLE001 - גיליון שלא נקרא: גם החילוץ ייכשל, ולא ייכתב ממנו טקסט
                    sheet = None
                if sheet and looks_like_contacts(sheet):
                    row["מצב"] = CONTACTS
        if not row["מצב"]:
            if f["dup_of"]:
                row["מצב"] = DUP
            elif is_old(rel) or old.get("מצב") == OLD:
                row["מצב"] = OLD
            else:
                row["מצב"] = ACTIVE

        if row["מצב"] in (ACTIVE, OLD):
            row["תאריך_מסמך"] = doc_date(f["path"], ext)
            if f["md5"] not in cache:
                try:
                    cache[f["md5"]] = extract(f["path"], ext, sheet if ext in (".csv", ".tsv") else None)
                except Exception as e:  # noqa: BLE001 - קובץ פגום לא עוצר את המצאי
                    cache[f["md5"]] = ("note", f"{ERROR_NOTE} ({type(e).__name__})")
                    problems.append(f"קובץ {f['id']}: {ERROR_NOTE} ({type(e).__name__}).")
            kind, value = cache[f["md5"]]
            if kind == "text":
                body = redact(value)
                row["מילים"] = str(words_in(body))
                name = f"{f['id']} {clean_name(os.path.splitext(os.path.basename(rel))[0])}.md"
                row["טקסט"] = "30_ספרייה/טקסט/" + name
                keep_text[f["id"]] = (name, card_text(row, KIND.get(ext, ext.lstrip(".")), body))
            elif value == MEDIA_NOTE and transcript_for(f["id"]):
                t = transcript_for(f["id"])
                row["טקסט"] = "30_ספרייה/תמלולים/" + t
                spoken = read_card(os.path.join(TRANS_DIR, t))[1].split("\n---\n", 1)[-1]  # בלי שורות הראש
                row["מילים"] = str(words_in(re.sub(r"^\[\d+:\d\d\]", "", spoken, flags=re.M)))
            else:
                row["טקסט"] = value
        rows.append(row)

    # קובץ שנעלם: השורה והטקסט נשארים, במצב "חסר במקורות"
    for r in missing:
        r = dict(r)
        r["מצב"] = MISSING
        names = existing_text.get(r["id"], [])
        if names:
            content = read_card(os.path.join(TEXT_DIR, names[0]))
            if content[0]:
                keep_text[r["id"]] = (names[0], card_text(r, content[0].get("סוג", r["סוג_קובץ"]), content[1]))
            else:
                keep_text[r["id"]] = (names[0], None)
        rows.append({c: cell(r.get(c, "")) for c in COLS})

    rows.sort(key=lambda r: int(r["id"]))

    if not dry:
        os.makedirs(TEXT_DIR, exist_ok=True)
    for fid, (name, content) in keep_text.items():
        if content is not None and write_if_changed(os.path.join(TEXT_DIR, name), content, dry):
            counts["written"] += 1
    for fid, names in existing_text.items():
        for name in names:
            if fid not in keep_text or keep_text[fid][0] != name:
                counts["removed"] += 1
                if not dry:
                    os.remove(os.path.join(TEXT_DIR, name))

    table = "\t".join(COLS) + "\n" + "".join("\t".join(cell(r[c]) for c in COLS) + "\n" for r in rows)
    catalog_changed = write_if_changed(CATALOG, table, dry)

    # הסיכום: רק ספירות
    by_status = {}
    for r in rows:
        by_status[r["מצב"]] = by_status.get(r["מצב"], 0) + 1
    summary = ", ".join(f"{s}: {by_status[s]}" for s in STATUS_ORDER if s in by_status)
    print(("הרצה יבשה, שום דבר לא נכתב. " if dry else "") + f"בקטלוג {len(rows)} שורות. {summary}.")
    print(f"קבצים חדשים: {counts['new']}. קובצי טקסט שנכתבו או עודכנו: {counts['written']}. "
          f"קובצי טקסט שנמחקו: {counts['removed']}. "
          + ("הקטלוג השתנה." if catalog_changed else "הקטלוג לא השתנה."))
    in_claude = sum(1 for r in rows if r["טקסט"] == READ_IN_CLAUDE and r["מצב"] != MISSING)
    waiting = sum(1 for r in rows if r["טקסט"] == MEDIA_NOTE and r["מצב"] != MISSING)
    if in_claude:
        print(f"קובצי PDF לקריאה ב־Claude (אין pypdf, או שהקובץ סרוק): {in_claude}.")
    if waiting:
        print(f"הקלטות שעוד אין להן תמלול בספרייה: {waiting}. להריץ את תמלול.py.")
    unknown = sum(1 for r in rows if r["מחברת"] == "?" and r["מצב"] in (ACTIVE, OLD))
    if unknown:
        print(f'בעמודה "מחברת" עוד כתוב "?" ב־{unknown} שורות. זה השדה החשוב ביותר: של מי החומר.')
    for p in problems:
        print("בעיה: " + p)


if __name__ == "__main__":
    main()
