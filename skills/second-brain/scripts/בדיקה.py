# -*- coding: utf-8 -*-
"""כלי הבדיקה של המוח. מריצים אותו בסוף כל עבודה:

    python _כלים/בדיקה.py        (במק: python3 _כלים/בדיקה.py)

מה נבדק. שגיאה עוצרת את הבדיקה, ואזהרה רק מודפסת:
1. ההגדרות ב"_כלים/הגדרות.json" שלמות.
2. יש ".gitignore", והוא משאיר מחוץ לגיט את "מקורות/" ואת "90_חומר_חדש/". אף קובץ משם לא נשמר בגיט.
3. אין סרטון, הקלטה או קובץ מתיקייה רגישה בין הקבצים שעולים לגיטהאב. קובץ מעל 50MB הוא אזהרה.
4. אין מספר IBAN או מספר שנראה כמו כרטיס אשראי בקבצי הטקסט שעולים. מודפסים רק הקובץ והשורה, לא המספר.
5. אם יש רשימת שמות ("מקורות/_רגיש/שמות.txt"), אף שם מהרשימה לא מופיע בקבצים שעולים או בשמות שלהם.
   מודפס רק המיקום ומספר השורה ברשימה, אף פעם לא השם עצמו.
6. יש "00_ליבה/הכללים.md". לכל כלל בו יש מקור עם תאריך בסוגריים מרובעים, ואף מספר לא חוזר פעמיים.
7. יש "שאלות_פתוחות.md". לכל שאלה פתוחה בו יש מקור עם תאריך. הבדיקה נעצרת בכותרת "## נענו".
8. לכל כרטיס עבודה ב"50_עבודות" יש מצב מהרשימה, ועבודה שיצאה כוללת טבלת "בדיקה מול הכללים".
9. כל הפניה [#מספר] בכרטיסים ובליבה קיימת בקטלוג של הספרייה. נבדק רק כשיש קטלוג.
10. לכל כרטיס ב"10_ידע", "15_תוצרים" ו"20_מוצרים" יש שורת "**עודכן:**" (אזהרה).
11. לא נשאר בקובץ מקום למילוי מהתבניות («…»).
12. אזהרה כשיש קבצים שמחכים ב"90_חומר_חדש", וכשבתיקייה הרגישה יש קבצים אבל רשימת השמות ריקה.
גם "יוצא/" (מה שיוצא לאנשים, עם השמות שלהם) לא עולה לגיט.

כשהכול תקין, הבדיקה בונה מחדש את הלוח (לוח.html), ואומרת את זה.
יוצאת בקוד 1 כשיש שגיאה. עובדת גם בלי גיט, וגם כשהתיקייה עוד לא מאגר:
אז נבדקים כל הקבצים בתיקייה, חוץ ממה שה־.gitignore משאיר בחוץ.
"""
import fnmatch
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import לוח  # noqa: E402

NAMES = os.path.join(BRAIN, "מקורות", "_רגיש", "שמות.txt")
CATALOG = os.path.join(BRAIN, "30_ספרייה", "קטלוג.tsv")
GITIGNORE = os.path.join(BRAIN, ".gitignore")
LOCAL_ONLY = ("מקורות", "90_חומר_חדש", "יוצא")
CARD_DIRS = ("10_ידע", "15_תוצרים", "20_מוצרים")
REF_DIRS = CARD_DIRS + ("00_ליבה",)
BOARD = "לוח.html"  # נבנה מהקבצים שנבדקים, ולכן לא נסרק בעצמו
ALWAYS_SKIP = {".git", "__pycache__"}
TEXT_EXT = {".md", ".txt", ".html", ".htm", ".json", ".csv", ".tsv", ".py", ".yml", ".yaml"}
MEDIA_EXT = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv", ".wmv", ".3gp", ".wav", ".mp3", ".m4a", ".aac",
             ".ogg", ".flac", ".opus", ".wma", ".amr"}
BIG_MB = 50

# IBAN ישראלי: IL ועוד 21 ספרות, אפשר עם רווחים. כרטיס: 13 עד 19 ספרות, עם רווח או מקף, שעוברות בדיקת לוהן.
# בשני הצדדים אין אות או ספרה, כדי שטביעת אצבע (md5) או מספר ארוך לא ייתפסו בטעות.
IBAN_RE = re.compile(r"(?<![A-Za-z0-9])IL\d\d(?: ?\d){19}(?![0-9])", re.I)
CARD_RE = re.compile(r"(?<![A-Za-z0-9])\d(?:[ -]?\d){12,18}(?![A-Za-z0-9])")

errors, warnings = [], []
NAME_PATS = []
NAME_LINES = []  # מספר השורה של כל שם בקובץ, כדי להדפיס מיקום ולא שם


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


def safe(rel):
    """נתיב להדפסה: שם מהרשימה הרגישה מוחלף בשלוש נקודות."""
    for pat in NAME_PATS:
        rel = pat.sub("…", rel)
    return rel


# ---------- הקבצים שעולים לגיטהאב ----------

def git(*args):
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=BRAIN,
                          capture_output=True, check=True).stdout


def git_state():
    """"repo" כשהתיקייה בתוך מאגר, "no-repo" כשגיט מותקן ואין מאגר, "no-git" כשגיט לא מותקן."""
    try:
        out = git("rev-parse", "--is-inside-work-tree").strip()
        return "repo" if out == b"true" else "no-repo"
    except OSError:
        return "no-git"
    except subprocess.CalledProcessError:
        return "no-repo"


def split_z(out):
    return [p.decode("utf-8", errors="replace") for p in out.split(b"\0") if p]


def read_ignore_patterns():
    if not os.path.exists(GITIGNORE):
        return []
    with open(GITIGNORE, encoding="utf-8-sig", errors="replace") as f:
        return [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]


def ignored_by(rel, patterns, is_dir):
    """קירוב של כללי .gitignore, לעבודה בלי גיט. בלי שלילה (!)."""
    parts = rel.split("/")
    for raw in patterns:
        if raw.startswith("!"):
            continue
        dir_only = raw.endswith("/")
        p = raw.strip("/")
        if not p:
            continue
        anchored = raw.startswith("/") or "/" in p
        if dir_only and not is_dir:
            continue
        if anchored:
            if fnmatch.fnmatchcase(rel, p) or fnmatch.fnmatchcase(rel, p + "/**"):
                return True
        elif any(fnmatch.fnmatchcase(part, p) for part in parts[-1:]):
            return True
    return False


def walk_files(patterns):
    """בלי גיט: כל הקבצים חוץ מהתיקיות שלא עולות ומה שה־.gitignore משאיר בחוץ."""
    files = []
    for root, dirs, names in os.walk(BRAIN):
        rel_root = os.path.relpath(root, BRAIN).replace(os.sep, "/")
        rel_root = "" if rel_root == "." else rel_root + "/"
        keep = []
        for d in sorted(dirs):
            rel = rel_root + d
            if d in ALWAYS_SKIP or (not rel_root and d in LOCAL_ONLY) or ignored_by(rel, patterns, True):
                continue
            keep.append(d)
        dirs[:] = keep
        for n in sorted(names):
            rel = rel_root + n
            if not ignored_by(rel, patterns, False):
                files.append(rel)
    return files


def check_gitignore(state, tracked):
    patterns = read_ignore_patterns()
    missing = []
    for folder in LOCAL_ONLY:
        ok = None
        if state == "repo":
            r = subprocess.run(["git", "-c", "core.quotepath=off", "check-ignore", "-q", "--no-index", "--",
                                folder + "/x.txt"], cwd=BRAIN, capture_output=True)
            ok = {0: True, 1: False}.get(r.returncode)
        if ok is None:
            ok = any(re.sub(r"(/\*\*?|/)$", "", p.lstrip("/")) == folder for p in patterns if not p.startswith("!"))
        if not ok:
            if not os.path.exists(GITIGNORE):
                missing.append(folder + "/")
            else:
                errors.append(f'ה־.gitignore לא משאיר מחוץ לגיט את "{folder}/". צריך להוסיף לו את השורה "{folder}/".')
        inside = [rel for rel in tracked if rel.startswith(folder + "/")]
        if inside:
            shown = ", ".join(safe(r) for r in inside[:5])
            more = f" ועוד {len(inside) - 5}" if len(inside) > 5 else ""
            errors.append(f'גיט שומר {לוח.count(len(inside), "קובץ אחד", "קבצים")} מתוך "{folder}/": {shown}{more}. '
                          + ("צריך להוציא אותו מגיט בלי למחוק אותו מהמחשב: " if len(inside) == 1 else
                             "צריך להוציא אותם מגיט בלי למחוק אותם מהמחשב: ")
                          + 'git rm -r --cached "' + folder + '"')
    if missing:
        errors.insert(0, 'חסר הקובץ ".gitignore". הוא צריך להיות שם לפני שהחומר הראשון נכנס, ובו השורות: '
                      + ", ".join(f'"{m}"' for m in missing) + ".")


def check_files(files):
    for rel in files:
        if rel.split("/")[0] in LOCAL_ONLY:
            continue  # מטופל בבדיקת ה־.gitignore
        ext = os.path.splitext(rel)[1].lower()
        if "_רגיש" in rel:
            errors.append("קובץ מתיקייה רגישה עולה לגיטהאב: " + safe(rel))
        if ext in MEDIA_EXT:
            errors.append("סרטון או הקלטה עולים לגיטהאב: " + safe(rel))
        try:
            size = os.path.getsize(os.path.join(BRAIN, rel))
        except OSError:
            continue
        if size > BIG_MB * 1024 * 1024:
            warnings.append(f"קובץ גדול ({size // (1024 * 1024)}MB) עולה לגיטהאב: {safe(rel)}. "
                            "גיטהאב חוסם קבצים מעל 100MB.")


def text_files(files):
    for rel in files:
        if rel == BOARD or rel.split("/")[0] in LOCAL_ONLY or os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        try:
            with open(os.path.join(BRAIN, rel), encoding="utf-8", errors="ignore") as f:
                yield rel, f.read()
        except OSError:
            continue


def check_numbers(files):
    for rel, text in text_files(files):
        for i, line in enumerate(text.splitlines(), 1):
            if IBAN_RE.search(line):
                errors.append(f"מספר IBAN בקובץ שעולה לגיטהאב: {safe(rel)}, שורה {i}. צריך להחליף אותו ב[הוסתר].")
            for m in CARD_RE.finditer(IBAN_RE.sub(" ", line)):
                digits = re.sub(r"\D", "", m.group(0))
                if luhn(digits):
                    errors.append(f"מספר שנראה כמו כרטיס אשראי בקובץ שעולה לגיטהאב: {safe(rel)}, שורה {i}. "
                                  "אם זה באמת כרטיס, צריך להחליף אותו ב[הוסתר].")
                    break


def load_names():
    if not os.path.exists(NAMES):
        return
    with open(NAMES, encoding="utf-8-sig") as f:
        for number, line in enumerate(f, 1):
            n = line.strip()
            if n and not n.startswith("#"):
                NAME_PATS.append(re.compile(r"(?<![א-תA-Za-z])%s(?![א-תA-Za-z])" % re.escape(n), re.I))
                NAME_LINES.append(number)


def check_names(files):
    if not NAME_PATS:
        return
    for rel in files:
        for i, pat in enumerate(NAME_PATS):
            if pat.search(rel):
                errors.append(f"שם מהרשימה הרגישה (שורה {NAME_LINES[i]} ב־שמות.txt) בשם של קובץ שעולה לגיטהאב: {safe(rel)}")
    for rel, text in text_files(files):
        for i, pat in enumerate(NAME_PATS):
            hits = list(pat.finditer(text))
            if hits:
                line = text.count("\n", 0, hits[0].start()) + 1
                more = f" (ועוד {len(hits) - 1} פעמים בקובץ)" if len(hits) > 1 else ""
                errors.append(f"שם מהרשימה הרגישה (שורה {NAME_LINES[i]} ב־שמות.txt): {safe(rel)}, שורה {line}{more}")


# ---------- התוכן של המוח ----------

def check_sources(path, label, first):
    if not os.path.exists(path):
        errors.append(f'חסר הקובץ "{label}". לפי המבנה הוא נמצא בכל מוח, גם לפני {first}: '
                      'כותרת, "מה זה" ו"עודכן".')
        return 0
    count = 0
    today = לוח.dt.date.today()
    blocks = לוח.read_blocks(path)
    for block in blocks:
        if block["chapter"].startswith("נענו") or block["cancelled"]:
            continue
        count += 1
        if not לוח.source_dates(" ".join(block["lines"]), today):
            errors.append(f'{label}: ל־{block["id"]} אין מקור עם תאריך בסוגריים מרובעים, למשל [מייל 3.11.2026]')
    ids = [b["id"] for b in blocks]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append(f"{label}: אותו מספר מופיע פעמיים: {', '.join(dup)}. מספר לא חוזר, גם כשכלל בוטל.")
    return count


def check_works(s):
    if not os.path.isdir(לוח.WORK):
        return 0
    statuses = לוח.all_statuses(s)
    products_dir = os.path.join(BRAIN, "15_תוצרים")
    products = {n[:-3] for n in os.listdir(products_dir) if n.endswith(".md")} if os.path.isdir(products_dir) else None
    names = לוח.work_files()
    for file_name in names:
        with open(os.path.join(לוח.WORK, file_name), encoding="utf-8-sig") as f:
            text = f.read()
        name = safe(file_name)
        status = לוח.field(text, "מצב")
        if status not in statuses:
            errors.append(f'כרטיס העבודה "{name}": המצב "{safe(status) or "חסר"}" לא מהרשימה '
                          f'({", ".join(statuses)})')
        if status in לוח.statuses_needing_check(s) and not לוח.table_rows(text, "בדיקה מול הכללים"):
            errors.append(f'כרטיס העבודה "{name}": במצב "{safe(status)}" חייבת להיות טבלת "בדיקה מול הכללים", '
                          'עם שורה לכל כלל שנוגע לתוצר')
        product = לוח.field(text, "תוצר")
        if products is not None and product and product not in products:
            warnings.append(f'כרטיס העבודה "{name}": אין ב־15_תוצרים כרטיס בשם "{safe(product)}", '
                            'ולכן העבודה לא מתחברת אליו במפה.')
    return len(names)


def card_files(folders):
    for folder in folders:
        path = os.path.join(BRAIN, folder)
        if not os.path.isdir(path):
            continue
        for n in sorted(os.listdir(path)):
            if n.endswith(".md") and not n.startswith("_") and os.path.isfile(os.path.join(path, n)):
                with open(os.path.join(path, n), encoding="utf-8-sig") as f:
                    yield f"{folder}/{n}", f.read()


def catalog_ids():
    with open(CATALOG, encoding="utf-8-sig") as f:
        lines = [l.rstrip("\r\n") for l in f]
    if not lines:
        return set()
    head = lines[0].split("\t")
    if "id" not in head:
        errors.append('בקטלוג של הספרייה אין עמודה "id". צריך להריץ מחדש את מצאי.py.')
        return set()
    col = head.index("id")
    ids = set()
    for l in lines[1:]:
        cells = l.split("\t")
        if len(cells) > col and cells[col].strip().isdigit():
            ids.add(int(cells[col]))
    return ids


def check_refs():
    if not os.path.exists(CATALOG):
        return
    ids = catalog_ids()
    for rel, text in card_files(REF_DIRS):
        for m in re.finditer(r"\[([^\]\n]*)\]", text):
            for ref in re.findall(r"#(\d+)", m.group(1)):
                if int(ref) not in ids:
                    line = text.count("\n", 0, m.start()) + 1
                    errors.append(f"{safe(rel)}, שורה {line}: ההפניה #{ref} לא קיימת בקטלוג של הספרייה.")


def check_updated():
    for rel, text in card_files(CARD_DIRS):
        if not re.search(r"^\*\*עודכן:\*\*\s*\S", text, re.M):
            warnings.append(f'בכרטיס "{safe(rel)}" חסרה השורה "**עודכן:**" עם תאריך.')


PLACEHOLDER_RE = re.compile(r"«[^»\n]{1,80}»")


def check_placeholders(files):
    """מקום למילוי מהתבניות («…») שנשאר בקובץ. מה שעוד לא ידוע נכתב כ"פתוח"."""
    for rel, text in text_files(files):
        if not rel.endswith(".md") or os.path.basename(rel).startswith("_תבנית"):
            continue  # התבנית של כרטיס עבודה נשארת עם מקומות למילוי בכוונה
        m = PLACEHOLDER_RE.search(text)
        if m:
            line = text.count("\n", 0, m.start()) + 1
            errors.append(f'נשאר מקום למילוי מהתבנית ב־{safe(rel)}, שורה {line}. ממלאים אותו, או כותבים "פתוח".')


def real_files(folder):
    out = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in ALWAYS_SKIP]
        out += [os.path.join(root, n) for n in names
                if not (n.startswith("~$") or n.startswith("._") or n.lower() in ("desktop.ini", "thumbs.db", ".ds_store"))]
    return out


def check_inbox_and_sensitive():
    inbox = os.path.join(BRAIN, "90_חומר_חדש")
    waiting = real_files(inbox) if os.path.isdir(inbox) else []
    if waiting:
        warnings.append(f'{לוח.count(len(waiting), "קובץ אחד מחכה", "קבצים מחכים")} ב־90_חומר_חדש. '
                        "כשהקליטה נגמרת, הקבצים עוברים ל־מקורות/ והתיקייה ריקה.")
    sensitive = os.path.join(BRAIN, "מקורות", "_רגיש")
    if os.path.isdir(sensitive) and not NAME_PATS:
        lists = {"שמות.txt", "לא_לחלץ.txt"}
        others = [p for p in real_files(sensitive) if os.path.basename(p) not in lists]
        if others:
            warnings.append("בתיקייה הרגישה יש קבצים, אבל רשימת השמות (מקורות/_רגיש/שמות.txt) ריקה. "
                            "אם יש בהם שמות של אנשים פרטיים, מוסיפים אותם לרשימה, כדי שהבדיקה תתפוס שם שדלף.")


def main():
    s, problems = לוח.load_settings()
    errors.extend(problems)
    if not problems and s["same"] and s["sent_status"] != "יצא":
        warnings.append('המקור ומי שמקלידה הן אותה אישה, ולכן המצב של עבודה שיצאה צריך להיות "יצא" '
                        f'(בהגדרות כתוב "{s["sent_status"]}").')
    load_names()

    state = git_state()
    if state == "repo":
        try:
            files = split_z(git("ls-files", "-co", "--exclude-standard", "-z"))
            tracked = split_z(git("ls-files", "-z"))
        except (OSError, subprocess.CalledProcessError):
            state = "no-repo"
    if state != "repo":
        files, tracked = walk_files(read_ignore_patterns()), []

    check_gitignore(state, tracked)
    check_files(files)
    check_numbers(files)
    check_names(files)
    n_rules = check_sources(לוח.RULES, "00_ליבה/הכללים.md", "הכלל הראשון")
    n_q = check_sources(לוח.QUESTIONS, "שאלות_פתוחות.md", "השאלה הראשונה")
    n_works = check_works(s)
    check_refs()
    check_updated()
    check_placeholders(files)
    check_inbox_and_sensitive()

    where ={"repo": "שעולים לגיטהאב",
             "no-repo": "בתיקייה (היא עוד לא מאגר גיט)",
             "no-git": "בתיקייה (גיט לא מותקן במחשב הזה)"}[state]
    print(f"נבדקו {לוח.count(len(files), 'קובץ אחד', 'קבצים')} {where}, "
          f"{לוח.count(n_rules, 'כלל אחד', 'כללים')}, {לוח.count(n_q, 'שאלה פתוחה אחת', 'שאלות פתוחות')} "
          f"ו{'־' if n_works != 1 else ''}{לוח.count(n_works, 'כרטיס עבודה אחד', 'כרטיסי עבודה')}.")
    for w in warnings:
        print("אזהרה: " + w)
    if errors:
        print(("נמצאה בעיה אחת" if len(errors) == 1 else f"נמצאו {len(errors)} בעיות") + ", ולכן הלוח לא עודכן:")
        for e in errors:
            print("  ✗ " + e)
        sys.exit(1)
    try:
        לוח.build()
    except Exception as e:  # noqa: BLE001 - הבדיקה עברה; תקלה בלוח לא צריכה להיראות כמו בעיה בתוכן
        print(f"הבדיקה עברה, אבל בניית הלוח נכשלה ({type(e).__name__}). צריך לבדוק את לוח.py.")
        sys.exit(1)
    if לוח.LONELY:
        print("אזהרה: במפת המוח יש כרטיסים בלי אף קשר: " + ", ".join(safe(t) for t in לוח.LONELY))
    print("✓ הכול תקין. הלוח נבנה מחדש: לוח.html")


if __name__ == "__main__":
    main()
