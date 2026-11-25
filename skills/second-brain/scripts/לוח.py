# -*- coding: utf-8 -*-
"""הלוח של המוח: דף אחד שמראה מה מחכה למקור, מה נכנס למוח לאחרונה, ואיפה עומדת כל עבודה.
בלשונית השנייה, "מפת המוח", יש כרטיס לכל חלק במוח, והקשרים ביניהם.

בדרך כלל לא מריצים אותו לבד: "בדיקה.py" בונה את הלוח בסוף, כשהכול תקין.
אפשר גם לבנות אותו ישירות:

    python _כלים/לוח.py        (במק: python3 _כלים/לוח.py)

הדף נכתב ל"לוח.html" בתיקייה הראשית של המוח, ונפתח בכל דפדפן, גם בלי אינטרנט.
השמות (הכותרת, המקור, השם של המצב "יצא") נקראים מ"_כלים/הגדרות.json".
חלק שאין לו קובץ במוח הזה (למשל אין עדיין עבודות) פשוט לא מופיע בלוח.
"""
import datetime as dt
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import מפה  # noqa: E402

BRAIN = os.path.dirname(HERE)
SETTINGS_FILE = os.path.join(HERE, "הגדרות.json")
RULES = os.path.join(BRAIN, "00_ליבה", "הכללים.md")
QUESTIONS = os.path.join(BRAIN, "שאלות_פתוחות.md")
WORK = os.path.join(BRAIN, "50_עבודות")
JOURNAL = os.path.join(BRAIN, "יומן_עדכונים.md")
OUT = os.path.join(BRAIN, "לוח.html")
LONELY = []  # כרטיסים במפה בלי אף קשר. הבדיקה מדפיסה אותם כאזהרה

KINDS = ("כללים", "ידע", "ידיים")
REQUIRED = ("brain_title", "decider", "operator", "kinds", "sent_status")

DATE_RE = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(?:\.(\d{4}|\d{2}))?(?![\d])")
RULE_REF = re.compile(r"(?:כלל|כללים|שאלה|שאלות|סעיף|תחום|עמ'|עמוד)\s*$")
ITEM_RE = re.compile(r"^- (?:~~)?\*\*(?:★\s*)?(\d+\.\d+)\s*(★)?\s*(.*)$")


# ---------- ההגדרות ----------

def le(name):
    """"לדקלה". לפני שם שלא מתחיל באות עברית: "ל־"."""
    return ("ל" if re.match(r"[א-ת]", name) else "ל־") + name


def load_settings():
    """קורא את _כלים/הגדרות.json. מחזיר (הגדרות, רשימת בעיות). כשיש בעיה, יש ערכים זמניים כדי שהלוח ייבנה."""
    problems, data = [], {}
    if not os.path.exists(SETTINGS_FILE):
        problems.append('חסר הקובץ "_כלים/הגדרות.json". בלעדיו הכלים לא יודעים את שם המוח, '
                        'מי המקור ומה שם המצב של עבודה שיצאה.')
    else:
        try:
            with open(SETTINGS_FILE, encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except json.JSONDecodeError as e:
            problems.append(f'אי אפשר לקרוא את "_כלים/הגדרות.json": יש טעות בכתיבה בשורה {e.lineno}. '
                            'בדרך כלל זו מירכאה או פסיק שחסרים.')
            data = {}
        except (OSError, ValueError):
            problems.append('אי אפשר לקרוא את "_כלים/הגדרות.json". הוא צריך להיות כמו הדוגמה שבחוזה.')
            data = {}
    s = {"brain_title": "המוח", "decider": "המקור", "operator": "", "kinds": [],
         "sent_status": "יצא", "today_note": ""}
    if data:
        for key in REQUIRED:
            if key not in data:
                problems.append(f'ב"_כלים/הגדרות.json" חסר השדה "{key}".')
        for key in ("brain_title", "decider", "operator", "sent_status", "today_note"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                s[key] = value.strip()
            elif key in data and key != "today_note":
                problems.append(f'ב"_כלים/הגדרות.json" השדה "{key}" ריק או לא טקסט.')
        kinds = data.get("kinds")
        if isinstance(kinds, list) and kinds and all(k in KINDS for k in kinds):
            s["kinds"] = kinds
        elif "kinds" in data:
            problems.append('ב"_כלים/הגדרות.json" השדה "kinds" צריך להיות רשימה של אחד או יותר מתוך: '
                            + ", ".join(KINDS) + ".")
    if not s["operator"]:
        s["operator"] = s["decider"]
    s["same"] = s["decider"] == s["operator"]
    s["to_decider"] = le(s["decider"])
    return s, problems


def status_groups(s):
    """המצבים של עבודה, לפי הסדר שבו הם מוצגים."""
    return [
        ("מחכה " + s["to_decider"], (s["sent_status"],)),
        ("בעבודה", ("בעבודה", "חזרו הערות")),
        ("הסתיים", ("אושר", "נסגר")),
    ]


def all_statuses(s):
    return tuple(st for _, group in status_groups(s) for st in group)


def statuses_needing_check(s):
    """עבודה במצבים האלה חייבת טבלת "בדיקה מול הכללים"."""
    return (s["sent_status"], "חזרו הערות", "אושר")


# ---------- קריאה ----------

def esc(text):
    return html.escape(text, quote=False)


def inline(md):
    """מעט מארקדאון לשורה אחת: מודגש, קוד וקו מחיקה. מספרים ולטינית נעטפים ב־bdi בסוף."""
    text = esc(md)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def parse_dates(text, today):
    """כל התאריכים בטקסט. תאריך בלי שנה מקבל את השנה שבה הוא לא בעתיד.
    מספר שבא אחרי "כלל" או "שאלה" הוא מספר של כלל, לא תאריך."""
    found = []
    for m in DATE_RE.finditer(text):
        if RULE_REF.search(text[max(0, m.start() - 8):m.start()]):
            continue
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= day <= 31 and 1 <= month <= 12):
            continue
        if year:
            year = int(year) + (2000 if len(year) == 2 else 0)
        else:
            year = today.year
            try:
                if dt.date(year, month, day) > today + dt.timedelta(days=1):
                    year -= 1
            except ValueError:
                continue
        try:
            found.append(dt.date(year, month, day))
        except ValueError:
            continue
    return found


def source_dates(text, today):
    """התאריכים שבתוך המקורות, כלומר בסוגריים המרובעים."""
    dates = []
    for part in re.findall(r"\[([^\]]+)\]", text):
        dates += parse_dates(part, today)
    return dates


def read_blocks(path):
    """מחלק קובץ של כללים או שאלות לפריטים. פריט = שורה שמתחילה ב"- **N.M" והשורות המוזחות אחריה."""
    if not os.path.exists(path):
        return []
    blocks, chapter, current = [], "", None
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    for line in lines:
        if line.startswith("## "):
            chapter = line[3:].strip()
            current = None
            continue
        m = ITEM_RE.match(line)
        if m:
            current = {"id": m.group(1), "star": bool(m.group(2)) or line.startswith("- **★"),
                       "chapter": chapter, "first": line, "lines": [line],
                       "cancelled": line.startswith("- ~~")}
            blocks.append(current)
        elif current is not None and (line.startswith("  ") or not line.strip()):
            current["lines"].append(line)
        else:
            current = None
    return blocks


def title_of(block):
    """הכותרת של פריט: החלק המודגש, או תחילת המשפט."""
    line = block["first"]
    m = re.match(r"^- (?:~~)?\*\*(?:★\s*)?\d+\.\d+\s*★?\s*(.*?)\*\*(.*)$", line)
    if m and m.group(1).strip():
        return m.group(1).strip().rstrip(":.")
    rest = re.sub(r"^- (?:~~)?\*\*(?:★\s*)?\d+\.\d+\s*★?\s*\*\*\s*", "", line)
    rest = re.sub(r"\s*\[[^\]]*\]\s*", " ", rest).strip()
    first = re.split(r"(?<=[.!?:])\s", rest, maxsplit=1)[0]
    return first[:140] + ("…" if len(first) > 140 else "")


def quote_of(block):
    """הציטוט הראשון של המקור בפריט, אם יש."""
    text = " ".join(block["lines"])
    # ראשי תיבות (ס"מ, תשפ"ז) הם גרשיים ולא מירכאות: אחרי המירכאות יש עד שתי אותיות וסוף מילה
    text = re.sub(r"(?<=[א-ת])\"(?=[א-ת][֑-ׇ]*(?:[א-ת][֑-ׇ]*)?(?![א-ת֑-ׇ]))", "״", text)
    # מזווגים מירכאות לפי הסדר: פותחת, סוגרת, פותחת, סוגרת
    pieces = text.split("\"")
    paired = pieces[1::2] if len(pieces) % 2 == 1 else pieces[1:-1:2]
    quotes = [q.strip() for q in paired
              if 15 <= len(q.strip()) <= 220 and not q.strip().startswith("(") and "לאשר עם" not in q]
    if not quotes:
        return ""
    best = max(quotes, key=len)
    return best if len(best) <= 160 else best[:157].rsplit(" ", 1)[0] + "…"


def chapter_name(chapter):
    """שם הפרק בלי המספר שלו."""
    return re.sub(r"^\d+\.\s*", "", chapter)


def split_questions(blocks):
    open_q, answered = [], []
    for b in blocks:
        (answered if b["chapter"].startswith("נענו") else open_q).append(b)
    return open_q, answered


def count_answered(path):
    """כמה תשובות יש בפרק "נענו". כל שורה שמתחילה ב"- " היא תשובה."""
    if not os.path.exists(path):
        return 0
    inside, n = False, 0
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("## "):
                inside = line[3:].strip().startswith("נענו")
            elif inside and line.startswith("- "):
                n += 1
    return n


def field(text, name):
    m = re.search(r"^\*\*%s:\*\*\s*(.+)$" % re.escape(name), text, re.M)
    return m.group(1).strip() if m else ""


def table_rows(text, heading):
    """השורות של הטבלה הראשונה מתחת לכותרת."""
    m = re.search(r"^## %s\s*$(.*?)(?=^## |\Z)" % re.escape(heading), text, re.M | re.S)
    if not m:
        return []
    rows = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|[\s:|-]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    return rows[1:] if rows else []  # בלי שורת הכותרת


def work_files():
    if not os.path.isdir(WORK):
        return []
    return [n for n in sorted(os.listdir(WORK))
            if n.endswith(".md") and not n.startswith("_") and os.path.isfile(os.path.join(WORK, n))]


def read_works(today):
    works = []
    for name in work_files():
        with open(os.path.join(WORK, name), encoding="utf-8-sig") as f:
            text = f.read()
        title = re.search(r"^# (.+)$", text, re.M)
        updated = parse_dates(field(text, "עודכן"), today)
        checks = table_rows(text, "בדיקה מול הכללים")
        notes = table_rows(text, "הערות שלה")
        works.append({
            "file": name,
            "title": title.group(1).strip() if title else name[:-3],
            "status": field(text, "מצב"),
            "product": field(text, "תוצר"),
            "next": field(text, "הצעד הבא"),
            "updated": max(updated) if updated else None,
            "fixed": sum(1 for r in checks if len(r) > 1 and r[1].startswith("תוקן")),
            "checked": len(checks),
            "notes": len(notes),
            "known": sum(1 for r in notes if len(r) > 2 and r[2].startswith("כן")),
        })
    return works


def read_journal(today, limit=6):
    if not os.path.exists(JOURNAL):
        return []
    entries = []
    with open(JOURNAL, encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("## "):
                head = line[3:].strip()
                date, _, title = head.partition("◆")
                dates = parse_dates(date, today)
                entries.append((dates[0] if dates else None, (title or head).strip()))
    return entries[:limit]


def fmt(date):
    return f"{date.day}.{date.month}.{date.year}" if date else ""


def count(n, one, many):
    return מפה.count(n, one, many)


def join_he(items):
    """"א, ב ו־ג". לפני מספר: "ו־"."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    last = items[-1]
    joiner = "ו־" if re.match(r"[\d<]", last) else "ו"
    return ", ".join(items[:-1]) + " " + joiner + last


# ---------- הדף ----------

def build(today=None):
    s, _problems = load_settings()
    today = today or dt.date.today()
    now = dt.datetime.now()
    groups = status_groups(s)
    statuses = all_statuses(s)
    d, to_d = s["decider"], s["to_decider"]

    has_rules, has_q = os.path.exists(RULES), os.path.exists(QUESTIONS)
    has_work, has_journal = os.path.isdir(WORK), os.path.exists(JOURNAL)

    rules = [b for b in read_blocks(RULES) if not b["cancelled"]]
    open_q, _answered = split_questions(read_blocks(QUESTIONS))
    works = read_works(today)
    journal = read_journal(today)

    for r in rules:
        dates = source_dates(" ".join(r["lines"]), today)
        r["date"] = max(dates) if dates else None
    recent = sorted([r for r in rules if r["date"]], key=lambda r: (r["date"], r["id"]), reverse=True)[:8]
    domains = {}
    for r in rules:
        domains.setdefault(r["chapter"], 0)
        domains[r["chapter"]] += 1

    starred = [q for q in open_q if q["star"]]
    others = [q for q in open_q if not q["star"]]
    waiting_works = [w for w in works if w["status"] in groups[0][1]]

    parts = []
    add = parts.append

    # מפת המוח נבנית קודם, כדי לדעת אם יש לה בכלל כרטיסים
    map_html, map_data, lonely = מפה.build_map(s, RULES, QUESTIONS, JOURNAL)
    LONELY[:] = lonely

    # הכותרת: משפט אחד שאומר מה המצב
    add(f'<header><h1>{esc(s["brain_title"])}</h1>')
    have = []
    if rules:
        have.append(count(len(rules), "כלל אחד", "כללים"))
    if works:
        have.append(count(len(works), "עבודה אחת", "עבודות"))
    sentence = f"במוח יש {join_he(have)}." if have else ""
    if has_q:
        if not open_q:
            sentence += f" אין שאלות פתוחות {to_d}."
        else:
            sentence += " " + (f"שאלה אחת פתוחה מחכה {to_d}." if len(open_q) == 1
                               else f"{len(open_q)} שאלות פתוחות מחכות {to_d}.")
    if sentence.strip():
        add(f'<p class="sum">{esc(sentence.strip())}</p>')
    add(f'<p class="stamp">הלוח עודכן ב־{fmt(today)}, בשעה {now:%H:%M}</p>')
    if s["today_note"]:
        add(f'<p class="note">{inline(s["today_note"])}</p>')
    if map_html:
        add('<nav class="tabs" aria-label="תצוגה">'
            '<a href="#status" data-view="status" aria-current="page">מה קורה עכשיו</a>'
            '<a href="#map" data-view="map">מפת המוח</a></nav>')
    add('</header>')
    add('<div class="view" id="v-status">')

    # 1. מה מחכה למקור
    if has_q or has_work:
        add(f'<section aria-labelledby="h-wait"><h2 id="h-wait">מחכה {esc(to_d)}</h2>')
        if not open_q and not waiting_works:
            add(f'<p class="empty">שום דבר לא מחכה {esc(to_d)} עכשיו.</p>')
        if waiting_works:
            label = "עבודות שיצאו ומחכות לתשובה" if s["same"] else "עבודות שנשלחו אליה"
            verb = "יצא" if s["same"] else "נשלח"
            add(f'<h3>{label}</h3><ul class="list">')
            for w in waiting_works:
                when = f' <span class="meta">{verb} ב־{fmt(w["updated"])}</span>' if w["updated"] else ""
                add(f'<li><strong>{inline(w["title"])}</strong>{when}</li>')
            add('</ul>')
        if starred:
            add('<h3>שאלות שעוצרות עבודה עכשיו</h3><ol class="list">')
            for q in starred:
                add(f'<li><span class="id">{q["id"]}</span> {inline(title_of(q))}'
                    f' <span class="meta">בנושא {esc(chapter_name(q["chapter"]))}</span></li>')
            add('</ol>')
        if others:
            by_chapter = {}
            for q in others:
                by_chapter.setdefault(q["chapter"], []).append(q)
            if starred:
                label = "עוד שאלה אחת, שלא עוצרת עבודה" if len(others) == 1 else \
                    f"עוד {len(others)} שאלות, שלא עוצרות עבודה, לפי נושא"
            else:
                label = "שאלה אחת פתוחה" if len(others) == 1 else f"{len(others)} שאלות פתוחות, לפי נושא"
            add(f'<details><summary>{label}</summary>')
            for chapter, items in by_chapter.items():
                add(f'<h4>{esc(chapter_name(chapter))}</h4><ul class="list">')
                for q in items:
                    add(f'<li><span class="id">{q["id"]}</span> {inline(title_of(q))}</li>')
                add('</ul>')
            add('</details>')
        add('</section>')

    # 2. מה נכנס למוח לאחרונה, במילים שלה. קובץ כללים ריק לא מקבל מקטע ריק
    if rules:
        add('<section aria-labelledby="h-new"><h2 id="h-new">מה נכנס למוח לאחרונה</h2>')
        if not recent:
            add('<p class="empty">עוד אין כללים עם תאריך.</p>')
        else:
            add('<ul class="list rules">')
            for r in recent:
                quote = quote_of(r)
                q_html = f'<span class="quote">"{inline(quote)}"</span>' if quote else ""
                add(f'<li><span class="id">{r["id"]}</span> {inline(title_of(r))}'
                    f' <span class="meta">מ־{fmt(r["date"])}</span>{q_html}</li>')
            add('</ul>')
        answered = count_answered(QUESTIONS)
        if answered:
            add(f'<p class="meta">{esc(d)} ענתה עד היום על {count(answered, "שאלה אחת", "שאלות")}. '
                'התשובות נכנסו לכללים ולכרטיסים.</p>')
        add('</section>')

    # 3. העבודות לפי מצב
    if has_work:
        add('<section aria-labelledby="h-work"><h2 id="h-work">העבודות</h2>')
        if not works:
            add('<p class="empty">עוד אין עבודות. כל עבודה חדשה מקבלת כרטיס ב־50_עבודות, והיא תופיע כאן.</p>')
        else:
            for label, sts in groups[1:]:
                group = [w for w in works if w["status"] in sts]
                if not group:
                    continue
                add(f'<h3>{label}</h3><ul class="list">')
                for w in group:
                    extra = []
                    if w["status"] == "חזרו הערות":
                        extra.append("חזרו הערות")
                    elif w["status"] in ("אושר", "נסגר"):
                        extra.append(w["status"])
                    if w["next"]:
                        extra.append("הצעד הבא: " + inline(w["next"]))
                    meta = f' <span class="meta">{". ".join(extra)}</span>' if extra else ""
                    add(f'<li><strong>{inline(w["title"])}</strong>{meta}</li>')
                add('</ul>')
            odd = [w for w in works if w["status"] not in statuses]
            if odd:
                add('<h3>עבודות בלי מצב ברור</h3><ul class="list">')
                for w in odd:
                    add(f'<li><strong>{inline(w["title"])}</strong> <span class="meta warn">'
                        f'המצב בכרטיס: "{esc(w["status"]) or "חסר"}"</span></li>')
                add('</ul>')
            # רק עבודות שכבר יצאו: שם יש משמעות ל"תוקן לפני שיצאו"
            out_states = (s["sent_status"], "חזרו הערות", "אושר", "נסגר")
            gone = [w for w in works if w["status"] in out_states]
            fixed = sum(w["fixed"] for w in gone)
            checked = sum(w["checked"] for w in gone)
            notes = sum(w["notes"] for w in gone)
            known = sum(w["known"] for w in gone)
            if checked or notes:
                if fixed == 0:
                    line = "הבדיקה מול הכללים עברה על העבודות שיצאו, ולא היה מה לתקן."
                else:
                    things = count(fixed, "דבר אחד", "דברים")
                    line = f"הבדיקה מול הכללים תיקנה {things} לפני שהעבודות יצאו."
                if notes:
                    if s["same"]:
                        who = "חזרה" if notes == 1 else "חזרו"
                    else:
                        who = f"{esc(d)} העירה"
                    line += f" אחרי שהן יצאו {who} {count(notes, 'הערה אחת', 'הערות')}."
                    if notes == 1:
                        line += (" היא כבר הייתה כתובה בכללים, והבדיקה פספסה אותה." if known
                                 else " היא לא הייתה כתובה בכללים.")
                    elif known == 1:
                        line += " אחת מהן כבר הייתה כתובה בכללים, והבדיקה פספסה אותה."
                    elif known > 1:
                        line += f" {known} מהן כבר היו כתובות בכללים, והבדיקה פספסה אותן."
                    else:
                        line += " אף אחת מהן לא הייתה כתובה בכללים."
                add(f'<p class="proof">{line}</p>')
        add('</section>')

    # 4. מה יש במוח, ומה השתנה בו (מקופל)
    if (has_rules and domains) or journal:
        add('<section aria-labelledby="h-know"><h2 id="h-know" class="quiet">מה יש במוח</h2>')
        if has_rules and domains:
            add(f'<details><summary>הכללים לפי תחום: {count(len(domains), "תחום אחד", "תחומים")}</summary>'
                '<ul class="list cols">')
            for chapter, n in domains.items():
                add(f'<li>{esc(chapter_name(chapter))} <span class="meta">{count(n, "כלל אחד", "כללים")}'
                    '</span></li>')
            add('</ul></details>')
        if journal:
            last = journal[0]
            when = f", האחרונה מ־{fmt(last[0])}" if last[0] else ""
            add(f'<details><summary>הרשומות האחרונות ביומן{when}</summary><ul class="list">')
            for date, title in journal:
                add(f'<li><span class="meta">{fmt(date)}</span> {inline(title)}</li>')
            add('</ul></details>')
        add('</section>')

    add('</div>')

    if map_html:
        add('<div class="view" id="v-map" hidden>' + map_html + '</div>')
        add('<aside id="reader" hidden aria-labelledby="reader-title" tabindex="-1">'
            '<div class="rhead"><div><h2 id="reader-title"></h2><p class="meta" id="reader-meta"></p></div>'
            '<button type="button" class="close" id="reader-close" aria-label="סגירת הכרטיס">✕</button></div>'
            '<div class="rlinks" id="reader-links"></div><div class="rbody" id="reader-body"></div></aside>')
        add('<script type="application/json" id="map-data">' + map_data + '</script>')

    body = מפה.bdi_html("\n".join(parts))
    page = TEMPLATE.replace("{{TITLE}}", esc(s["brain_title"])).replace("{{BODY}}", body)
    tmp = OUT + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    os.replace(tmp, OUT)
    return OUT


TEMPLATE = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
  :root { --ink:#1c2430; --soft:#5b6472; --line:#e6e8ec; --edge:#cfd4db; --accent:#1f5fae;
          --accent-bg:#eef4fb; --dim-bg:#f7f8fa; --warn:#9a3412; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #fff; color: var(--ink);
         font: 1rem/1.6 "Segoe UI", "Arial Hebrew", Arial, system-ui, sans-serif; }
  main { max-width: 52rem; margin-inline: auto; padding-block: 2rem 4rem; padding-inline: 1rem; }
  header { border-block-end: 1px solid var(--line); padding-block-end: 1rem; margin-block-end: 1.5rem; }
  h1 { font-size: 1.6rem; margin: 0; }
  .sum { margin-block: .25rem 0; font-size: 1.05rem; }
  .stamp { margin-block: .1rem 0; color: var(--soft); font-size: .875rem; }
  .note { margin-block: .6rem 0; }
  section { margin-block: 0 2.25rem; }
  h2 { font-size: 1.25rem; margin-block: 0 .75rem; }
  h2.quiet { font-size: 1.05rem; color: var(--soft); }
  h3 { font-size: 1rem; margin-block: 1.1rem .4rem; color: var(--soft); font-weight: 600; }
  h4 { font-size: .95rem; margin-block: .9rem .3rem; }
  .list { margin: 0; padding: 0; list-style: none; }
  .list li { padding-block: .45rem; border-block-end: 1px solid var(--line); }
  .list li:last-child { border-block-end: 0; }
  .id { display: inline-block; min-inline-size: 2.6rem; color: var(--soft); font-variant-numeric: tabular-nums; }
  .meta { color: var(--soft); font-size: .875rem; margin-inline-start: .35rem; }
  .warn { color: var(--warn); }
  .quote { display: block; color: var(--soft); margin-inline-start: 2.6rem; font-size: .95rem; }
  .empty { color: var(--soft); }
  .proof { margin-block-start: 1rem; padding: .75rem 1rem; background: var(--accent-bg); border-radius: .5rem; }
  details { margin-block: .6rem; }
  summary { cursor: pointer; padding-block: .4rem; font-weight: 600; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
  .cols { columns: 2 16rem; }
  .cols li { break-inside: avoid; }
  code { background: #f4f5f7; padding-inline: .25rem; border-radius: 3px; font-size: .9em; }
  body.wide main { max-width: 84rem; }
  .tabs { display: flex; gap: .25rem; margin-block-start: 1rem; flex-wrap: wrap; }
  .tabs a { padding: .45rem .9rem; border-radius: .5rem; color: var(--soft); text-decoration: none; font-weight: 600; }
  .tabs a[aria-current="page"] { background: var(--accent-bg); color: var(--accent); box-shadow: inset 0 0 0 1px #c9dbf1; }
  .maphint { color: var(--soft); margin-block: 0 1.25rem; }
  .grp { margin-block: 0 1.75rem; }
  .grp h2 { font-size: 1.1rem; margin-block-end: .1rem; }
  .gsub { color: var(--soft); font-size: .9rem; margin-block: 0 .6rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(12.5rem, 1fr)); gap: .75rem; }
  .card { text-align: start; font: inherit; color: inherit; cursor: pointer;
          background: #fff; border: 1px solid var(--edge);
          border-radius: .6rem; padding: .7rem .85rem; display: flex; flex-direction: column; gap: .15rem;
          min-block-size: 5.2rem; transition: background-color .15s, box-shadow .15s, color .15s; }
  .card:hover { box-shadow: 0 2px 10px rgba(20,30,50,.08); }
  .card .t { font-weight: 600; line-height: 1.35; }
  .card .m { color: var(--soft); font-size: .875rem; }
  .card .lk { color: var(--soft); font-size: .8rem; margin-block-start: auto; }
  .map.focus .card { background: var(--dim-bg); color: var(--soft); border-color: var(--line); }
  .map.focus .card .t { font-weight: 500; }
  .map.focus .card.linked { background: var(--accent-bg); color: var(--ink); border-color: #9dbbe3; }
  .map.focus .card.linked .t { font-weight: 600; }
  .map.focus .card[aria-pressed="true"] { background: #fff; color: var(--ink); border-color: var(--accent);
                                          box-shadow: 0 0 0 2px var(--accent); }
  .map.focus .card[aria-pressed="true"] .t { font-weight: 700; }
  #reader { position: fixed; inset-block: 0; inset-inline-end: 0; inline-size: min(44rem, 52vw); background: #fff;
            border-inline-start: 1px solid var(--line); box-shadow: 0 0 24px rgba(20,30,50,.10);
            overflow-y: auto; padding-block: 1.25rem 3rem; padding-inline: 1.5rem; z-index: 10; }
  #reader:focus { outline: none; }
  .rhead { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start;
           border-block-end: 1px solid var(--line); padding-block-end: .6rem; }
  .rhead h2 { margin: 0; font-size: 1.3rem; }
  .close { font: inherit; font-size: 1.1rem; background: #fff; color: var(--ink); border: 1px solid var(--edge);
           border-radius: .5rem; inline-size: 2.75rem; block-size: 2.75rem; cursor: pointer; flex: none; }
  .rlinks { margin-block: .75rem; display: grid; gap: .35rem; }
  .rlinks .row { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem; }
  .rlinks .lbl { color: var(--soft); font-size: .85rem; min-inline-size: 4.5rem; }
  .rlinks button { font: inherit; font-size: .85rem; color: var(--ink); border: 1px solid var(--edge);
                   background: #fafbfc; border-radius: .5rem; padding: .15rem .7rem; cursor: pointer; }
  .rbody { font-size: .98rem; }
  .rbody h3 { color: var(--ink); font-size: 1.05rem; margin-block-start: 1.4rem; }
  .rbody h4, .rbody h5 { font-size: .98rem; margin-block: 1rem .3rem; }
  .rbody ul, .rbody ol { padding-inline-start: 1.3rem; }
  .rbody li { margin-block: .3rem; }
  .rbody li.flash { background: #fff6d6; border-radius: .3rem; transition: background-color 1.5s; }
  .rbody .tablewrap { overflow-x: auto; }
  .rbody table { border-collapse: collapse; margin-block: .6rem; font-size: .92rem; }
  .rbody th, .rbody td { border: 1px solid var(--line); padding: .3rem .5rem; text-align: start; vertical-align: top; }
  .rbody pre { background: #f6f7f9; padding: .6rem .8rem; border-radius: .4rem; white-space: pre-wrap; }
  .ref { color: var(--accent); }
  @media (max-width: 52rem) { #reader { inline-size: 100vw; } }
  @media print {
    .tabs, #reader, .maphint { display: none !important; }
    .view[hidden] { display: block !important; }
    main, body.wide main { max-width: none; padding: 0; }
    details > *:not(summary) { display: block !important; }
    summary { list-style: none; }
    .card, .map.focus .card { background: #fff !important; color: var(--ink) !important; box-shadow: none !important;
                              border-color: var(--edge) !important; break-inside: avoid; }
    .grp { break-inside: avoid-page; }
    #v-map { break-before: page; }
  }
  /* דפדפנים חדשים: גם מקטע מקופל מודפס פתוח. בישנים, הסקריפט פותח אותם לפני ההדפסה */
  @media print { details::details-content { content-visibility: visible; display: block; } }
</style>
</head>
<body>
<main>
{{BODY}}
</main>
<script>
  // בהדפסה כל המקטעים המקופלים נפתחים
  window.addEventListener("beforeprint", () => document.querySelectorAll("details").forEach(d => d.open = true));

  const dataEl = document.getElementById("map-data");
  const map = document.getElementById("mapgrid");
  const reader = document.getElementById("reader");
  const PAYLOAD = dataEl ? JSON.parse(dataEl.textContent) : { labels: [], cards: {} };
  const DATA = PAYLOAD.cards;

  // שתי התצוגות: "מה קורה עכשיו" ו"מפת המוח"
  const views = { status: document.getElementById("v-status"), map: document.getElementById("v-map") };
  function show(view) {
    if (!views[view]) view = "status";
    for (const [k, el] of Object.entries(views)) if (el) el.hidden = k !== view;
    document.querySelectorAll(".tabs a").forEach(a =>
      a.dataset.view === view ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    document.body.classList.toggle("wide", view === "map");
    if (view !== "map") closeReader(false, false);
  }
  function route() {
    const [view, id] = decodeURIComponent(location.hash.slice(1)).split(":");
    show(view);
    if (view === "map" && id) openCard(id);
  }
  window.addEventListener("hashchange", route);

  // המפה: בחירת כרטיס מדגישה את הקשורים אליו ופותחת את התוכן
  let lastCard = null;
  function openCard(id, anchor) {
    const d = DATA[id];
    if (!d || !map) return;
    if (!location.hash.startsWith("#map")) show("map");
    history.replaceState(null, "", "#map:" + id);
    map.classList.add("focus");
    map.querySelectorAll(".card").forEach(c => {
      const on = c.dataset.id === id;
      c.setAttribute("aria-pressed", on ? "true" : "false");
      c.classList.toggle("linked", d.links.includes(c.dataset.id));
      if (on) lastCard = c;
    });
    document.getElementById("reader-title").innerHTML = d.title_html;
    document.getElementById("reader-meta").innerHTML = d.meta_html;
    const links = document.getElementById("reader-links");
    links.innerHTML = "";
    for (const [g, label] of PAYLOAD.labels) {
      const ids = d.links.filter(l => DATA[l] && DATA[l].group === g);
      if (!ids.length) continue;
      const row = document.createElement("div");
      row.className = "row";
      const lbl = document.createElement("span");
      lbl.className = "lbl"; lbl.textContent = label + ":";
      row.append(lbl);
      ids.forEach(l => {
        const b = document.createElement("button");
        b.type = "button"; b.innerHTML = DATA[l].title_html;
        b.addEventListener("click", () => openCard(l));
        row.append(b);
      });
      links.append(row);
    }
    document.getElementById("reader-body").innerHTML = d.html;
    reader.hidden = false;
    reader.scrollTop = 0;
    if (anchor) {
      const el = document.getElementById(anchor);
      if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600); }
    }
    reader.focus();
  }
  // סגירה בתוך המפה (Esc או ✕) מחזירה את הכתובת ל"#map". מעבר ללשונית אחרת משאיר את הכתובת שלה
  function closeReader(refocus = true, resetHash = true) {
    if (!reader || reader.hidden) return;
    reader.hidden = true;
    map.classList.remove("focus");
    map.querySelectorAll(".card").forEach(c => { c.setAttribute("aria-pressed", "false"); c.classList.remove("linked"); });
    if (resetHash) history.replaceState(null, "", "#map");
    if (refocus && lastCard) lastCard.focus();
  }
  if (map) {
    map.addEventListener("click", e => { const c = e.target.closest(".card"); if (c) openCard(c.dataset.id); });
    document.getElementById("reader-close").addEventListener("click", () => closeReader());
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeReader(); });
    reader.addEventListener("click", e => {
      const a = e.target.closest("a.ref");
      if (!a) return;
      e.preventDefault();
      openCard(a.dataset.card, a.dataset.anchor);
    });
  }
  route();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    settings, problems = load_settings()
    for p in problems:
        print("אזהרה: " + p)
    print("הלוח נכתב: " + build())
