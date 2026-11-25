# -*- coding: utf-8 -*-
"""השוואה של קובץ וורד שחזר מהמקור לגרסה שלנו שהיא קיבלה. מריצים אותה לפני שקוראים את הקובץ שחזר.

    python _כלים/השוואת_גרסאות.py "<הקובץ שחזר>.docx" "<שלנו 1>.docx" ["<שלנו 2>.docx" ...] [--out "<דוח>.md"]
    (במק: python3 במקום python)

את הגרסאות שלנו כותבים מהישנה לחדשה. הדוח נכתב ליד הקובץ שחזר, בשם "<השם שלו> - השוואה.md".
במסך מודפסות רק שורת הסיכום והנתיב של הדוח. איזו גרסה נבחרה, וכל אזהרה עליה, כתובות בראש הדוח.

למה: היא מתקנת בתוך הקובץ, ולרוב בלי מעקב שינויים. היא מוחקת בשקט, מוסיפה, מסמנת בצבע וכותבת הערות בצד,
וכל דבר כזה הוא הערה שצריכה להפוך לכלל. השוואה של טקסט בלבד מפספסת הערות, ולכן משווים גם את הסימונים.

איך זה עובד:
1. איזו גרסה: הקובץ שלה מושווה לכל אחת מהגרסאות שלנו, ונבחרת הדומה ביותר. בדוח מופיע הדמיון לכל גרסה.
   כשהיא ערכה גרסה ישנה, ולא את האחרונה ברשימה, זה כתוב בדוח ובמסך. מה שנוסף אחרי הגרסה שלה לא מופיע
   כמחיקה, כי היא לא ראתה אותו. כששתי גרסאות קרובות מדי, או שאף אחת לא דומה, גם זה כתוב.
2. נרמול לפני ההשוואה: Unicode NFD, בלי סימנים נלווים (ניקוד וטעמים), בלי סימני כיווניות,
   מירכאות וגרשיים בצורה אחת (״ “ ” ← ", ׳ ‘ ’ ← '), ורווחים מצומצמים לרווח אחד.
   פסקה שהשתנו בה רק ניקוד, מירכאות או רווחים לא נספרת כשינוי, אבל המספר שלה כתוב בדוח.
3. פסקה מול פסקה (difflib), בלי פסקאות ריקות. כשכמה פסקאות השתנו באותו מקום, כל אחת מוצמדת לדומה לה.
4. מה נכנס לדוח, וכל פריט ממוספר:
   - מחיקות: פסקאות שלנו שהיא מחקה, עם ¶N שלנו והטקסט שלנו.
   - תוספות: פסקאות שהיא הוסיפה, ואחרי איזו פסקה שלנו.
   - שינויי נוסח: הבדל ברמת המילה. [-טקסט שלנו-]{+הטקסט שלה+}
   - הזזות: פסקה שעברה למקום אחר בלי שינוי.
   - סימונים: מרקר, צבע רקע, צבע גופן והדגשה שהיא הוסיפה או הסירה, על טקסט שהיה כבר אצלנו.
     הסימונים נבדקים תו מול תו, ולכן חלוקה אחרת של הטקסט לריצות בוורד לא נראית כשינוי.
     אותו שינוי ביותר משמונה מקומות (למשל, היא הסירה את כל המרקרים שלנו) הוא פריט אחד, עם רשימת הפסקאות.
   - הערות בוורד: כל הערה שלה בצד, עם הטקסט שהיא מסמנת. הערה שהייתה כבר בקובץ שלנו לא נכנסת.
   - מעקב שינויים: שינויים שהיא עשתה עם מעקב שינויים. הם מוצגים רק כאן, ולא שוב בשינויי הנוסח.
     שינוי במעקב שהיה כבר בקובץ שלנו לא נכנס.
5. ¶N הוא מספר הפסקה בגרסה שלנו, כמו בפלט של מספור_פסקאות.py, וזה המספר שנכנס ל־findings.json של
   החלת_תיקונים.py. בסוגריים: המספר אצלה, כשצריך לעבוד על הקובץ שלה.

בלי ספריות חיצוניות: רק פייתון עצמו. יוצא בקוד 1 כשאי אפשר לקרוא אחד הקבצים.
"""
import argparse
import datetime
import difflib
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import מספור_פסקאות as mp  # noqa: E402
import חילוץ_סימונים as ms  # noqa: E402

W = mp.W
SETTINGS = os.path.join(HERE, "הגדרות.json")
INS_TAGS = (W + "ins", W + "moveTo")
DEL_TAGS = (W + "del", W + "moveFrom")
SKIP_TAGS = (W + "pPr", W + "rPr")
BREAK_TAGS = (W + "tab", W + "br", W + "cr")
SOFT_TAGS = (W + "proofErr", W + "bookmarkStart", W + "bookmarkEnd", W + "commentRangeStart",
             W + "commentRangeEnd", W + "permStart", W + "permEnd")
PAIR_MIN = 0.5      # מתחת לדמיון הזה, שתי פסקאות באותו מקום הן מחיקה ותוספת, ולא שינוי נוסח
CLOSE = 0.02        # שתי גרסאות שההפרש בדמיון שלהן קטן מזה: אומרים שהן קרובות מדי
LOW = 0.6           # מתחת לזה: אף גרסה שלנו לא דומה במיוחד לקובץ שלה
CONTEXT = 6         # כמה מילים מסביב לשינוי נוסח
MANY = 8            # אותו שינוי סימון ביותר מקומות מזה נכנס לדוח כפריט אחד
LONG = 300          # טקסט מסביב (עוגן של הערה, הזזה) ארוך מזה מקוצר בדוח
FULL = 3000         # טקסט שנמחק, שנוסף או שנכתב בהערה מקוצר רק כשהוא ארוך מזה

QUOTES = str.maketrans({"״": '"', "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
                        "׳": "'", "‘": "'", "’": "'", "‚": "'", "‛": "'", "`": "'", "´": "'"})

HL_NAMES = {"yellow": "צהוב", "green": "ירוק", "cyan": "תכלת", "magenta": "ורוד", "blue": "כחול",
            "red": "אדום", "darkBlue": "כחול כהה", "darkCyan": "טורקיז כהה", "darkGreen": "ירוק כהה",
            "darkMagenta": "סגול", "darkRed": "אדום כהה", "darkYellow": "חרדל", "darkGray": "אפור כהה",
            "lightGray": "אפור בהיר", "black": "שחור", "white": "לבן"}


# ---------- נרמול ----------

def norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)
                and unicodedata.category(c) not in ("Mn", "Me", "Cf"))
    s = s.translate(QUOTES)
    return re.sub(r"\s+", " ", s).strip()


def color_name(hexval):
    """שם קרוב לצבע בקוד, כדי שיהיה קל לקרוא. 'FF0000' -> 'אדום'."""
    try:
        r, g, b = (int(hexval[k:k + 2], 16) / 255 for k in (0, 2, 4))
    except (ValueError, TypeError, IndexError):
        return ""
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 0.12:
        return "שחור" if mx < 0.25 else "לבן" if mn > 0.9 else "אפור"
    d = mx - mn
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h *= 60
    if h < 15 or h >= 340:
        name = "אדום"
    elif h < 40:
        name = "כתום" if mx > 0.6 else "חום"
    elif h < 70:
        name = "צהוב"
    elif h < 165:
        name = "ירוק"
    elif h < 200:
        name = "תכלת"
    elif h < 255:
        name = "כחול"
    elif h < 290:
        name = "סגול"
    else:
        name = "ורוד"
    return name + (" כהה" if mx < 0.45 and name not in ("חום",) else "")


def describe(tag):
    kind, _, val = tag.partition(":")
    if kind == "hl":
        return f"מרקר {HL_NAMES.get(val, val)}"
    if kind == "shd":
        n = color_name(val)
        return f"רקע {n}" if n else "רקע צבעוני"
    if kind == "c":
        n = color_name(val)
        return f"גופן {n}" if n else "גופן צבעוני"
    if kind == "b":
        return "מודגש"
    if kind == "u":
        return "קו תחתון"
    if kind == "s":
        return "קו חוצה"
    return tag


TAG_ORDER = ("hl", "shd", "c", "b", "u", "s")


def describe_set(tags):
    tags = sorted(tags, key=lambda t: TAG_ORDER.index(t.partition(":")[0])
                  if t.partition(":")[0] in TAG_ORDER else 9)
    return ", ".join(f"{describe(t)} `[{t}]`" for t in tags)


# ---------- קריאת הקובץ ----------

def tracked_key(el):
    kind = "ins" if el.tag in INS_TAGS else "del"
    text = "".join(x.text or "" for x in el.iter() if x.tag in (W + "t", W + "delText"))
    return (kind, el.get(W + "author") or "", el.get(W + "date") or "", norm(text))


class Doc:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.zip = mp.open_docx(path)
        self.body = mp.body_of(self.zip)
        self.paras = mp.body_paragraphs(self.body)
        self.tracked = [el for p in self.paras for el in p.iter() if el.tag in INS_TAGS + DEL_TAGS]
        self.tracked_keys = {tracked_key(el) for el in self.tracked}
        self.comments = ms.read_comments(self.zip, self.body, self.paras)
        self.comment_keys = {(c["author"], norm(c["text"])) for c in self.comments}


class Para:
    """פסקה אחת: הטקסט (בדיוק כמו בפלט של מספור_פסקאות.py), הסימונים של כל תו, והטקסט המנורמל."""

    def __init__(self, idx, text, marks, spaced):
        self.idx = idx
        self.text = text
        self.marks = marks
        self.norm = norm(spaced)
        self.words = self.norm.split()


def read_paras(doc, is_new):
    """הפסקאות של הקובץ. is_new(el) אומר אם שינוי במעקב הוא חדש (שלה): שינוי חדש מוצג כמו לפניו,
    כדי שייכנס רק לפרק מעקב השינויים. כל שינוי אחר במעקב מוצג כאילו התקבל."""
    out = []
    for i, p in enumerate(doc.paras):
        chars, marks, spaced = [], [], []

        def walk(el, cur):
            for ch in el:
                tag = ch.tag
                if tag in SKIP_TAGS:
                    continue
                if tag in INS_TAGS:
                    if not is_new(ch):
                        walk(ch, cur)
                    continue
                if tag in DEL_TAGS:
                    if is_new(ch):
                        walk(ch, cur)
                    continue
                if tag == W + "r":
                    walk(ch, frozenset(ms.run_tags(ch.find(W + "rPr"))))
                    continue
                if tag in (W + "t", W + "delText"):
                    s = ch.text or ""
                    chars.append(s)
                    marks.extend([cur] * len(s))
                    spaced.append(s)
                    continue
                if tag in BREAK_TAGS:
                    spaced.append(" ")
                    continue
                walk(ch, cur)

        walk(p, frozenset())
        out.append(Para(i, "".join(chars), marks, "".join(spaced)))
    return out


# ---------- יישור ----------

def tokens(p):
    """המילים של הפסקה: (התחלה, סוף, מנורמל), לפי רווחים. מילה שאין בה כלום אחרי נרמול לא נספרת."""
    out = []
    for m in re.finditer(r"\S+", p.text):
        n = norm(m.group())
        if n:
            out.append((m.start(), m.end(), n))
    return out


def similarity(a, b, floor=0.0):
    """דמיון בין שתי פסקאות. בפסקה קצרה לפי אותיות, ובארוכה לפי מילים. מתחת ל־floor מחזיר 0 מהר."""
    if len(a.words) < 4 or len(b.words) < 4:
        sm = difflib.SequenceMatcher(None, a.norm, b.norm, autojunk=False)
    else:
        sm = difflib.SequenceMatcher(None, a.words, b.words, autojunk=False)
    if floor and (sm.real_quick_ratio() < floor or sm.quick_ratio() < floor):
        return 0.0
    return sm.ratio()


def pair_block(A, B):
    """בתוך מקום שבו כמה פסקאות השתנו: מצמידים כל פסקה שלנו לפסקה שלה הדומה לה, לפי הסדר.
    מחזיר רשימת צעדים: ('changed', i, j), ('deleted', i, None), ('added', None, j)."""
    n, m = len(A), len(B)
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            s = similarity(A[i], B[j], PAIR_MIN)
            if s >= PAIR_MIN:
                sim[i][j] = s
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            v = max(best[i + 1][j], best[i][j + 1])
            if sim[i][j]:
                v = max(v, best[i + 1][j + 1] + sim[i][j])
            best[i][j] = v
    steps, i, j = [], 0, 0
    while i < n or j < m:
        if i < n and j < m and sim[i][j] and best[i][j] == best[i + 1][j + 1] + sim[i][j]:
            steps.append(("changed", i, j))
            i, j = i + 1, j + 1
        elif i < n and (j >= m or best[i][j] == best[i + 1][j]):
            steps.append(("deleted", i, None))
            i += 1
        else:
            steps.append(("added", None, j))
            j += 1
    return steps


def align(ours, hers):
    """יישור פסקה מול פסקה, בלי פסקאות ריקות. מחזיר רשימת צעדים לפי הסדר, עם Para (או None)."""
    A = [p for p in ours if p.norm]
    B = [p for p in hers if p.norm]
    sm = difflib.SequenceMatcher(None, [p.norm for p in A], [p.norm for p in B], autojunk=False)
    steps = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            steps += [("equal", A[i1 + k], B[j1 + k]) for k in range(i2 - i1)]
        elif tag == "delete":
            steps += [("deleted", A[i], None) for i in range(i1, i2)]
        elif tag == "insert":
            steps += [("added", None, B[j]) for j in range(j1, j2)]
        else:
            for kind, i, j in pair_block(A[i1:i2], B[j1:j2]):
                steps.append((kind, A[i1 + i] if i is not None else None, B[j1 + j] if j is not None else None))
    # הזזה: פסקה שנמחקה במקום אחד ונוספה, בדיוק כמו שהיא, במקום אחר
    added_by_norm = {}
    for k, (kind, a, b) in enumerate(steps):
        if kind == "added":
            added_by_norm.setdefault(b.norm, []).append(k)
    for k, (kind, a, b) in enumerate(steps):
        if kind == "deleted" and added_by_norm.get(a.norm):
            k2 = added_by_norm[a.norm].pop(0)
            steps[k] = ("moved", a, steps[k2][2])
            steps[k2] = ("moved-here", None, steps[k2][2])
    return steps


def word_ops(a, b):
    ta, tb = tokens(a), tokens(b)
    sm = difflib.SequenceMatcher(None, [t[2] for t in ta], [t[2] for t in tb], autojunk=False)
    return ta, tb, sm.get_opcodes()


def score(ours, hers, steps):
    """דמיון בין 0 ל־1: כמה מילים משותפות, מתוך כל המילים בשני הקבצים."""
    total = sum(len(p.words) for p in ours) + sum(len(p.words) for p in hers)
    if not total:
        return 1.0
    same = 0
    for kind, a, b in steps:
        if kind in ("equal", "moved"):
            same += len(a.words)
        elif kind == "changed":
            sm = difflib.SequenceMatcher(None, a.words, b.words, autojunk=False)
            same += sum(blk.size for blk in sm.get_matching_blocks())
    return 2 * same / total


# ---------- ממצאים ----------

def clip(s, n=LONG):
    s = s.strip()
    return s if len(s) <= n else s[:n].rstrip() + " …"


def span(text, toks, i1, i2):
    return text[toks[i1][0]:toks[i2 - 1][1]] if i2 > i1 else ""


def word_diff(a, b):
    """שינוי הנוסח בתוך פסקה: [-שלנו-]{+שלה+}, עם כמה מילים מסביב. הטקסט מסביב הוא שלנו, כמו שהוא,
    כדי שאפשר יהיה להעתיק ממנו find ל־findings.json. מחזיר גם את הסימונים שעל הטקסט החדש שלה."""
    ta, tb, ops = word_ops(a, b)
    pieces, new_marks = [], set()
    for k, (tag, i1, i2, j1, j2) in enumerate(ops):
        if tag == "equal":
            n = i2 - i1
            first, last = k == 0, k == len(ops) - 1
            if first and last:
                pieces.append(span(a.text, ta, i1, i2))
            elif first:
                pieces.append(("… " if n > CONTEXT else "") + span(a.text, ta, max(i1, i2 - CONTEXT), i2))
            elif last:
                pieces.append(span(a.text, ta, i1, min(i2, i1 + CONTEXT)) + (" …" if n > CONTEXT else ""))
            elif n > 2 * CONTEXT:
                pieces.append(span(a.text, ta, i1, i1 + CONTEXT) + " … " + span(a.text, ta, i2 - CONTEXT, i2))
            else:
                pieces.append(span(a.text, ta, i1, i2))
            continue
        old, new = span(a.text, ta, i1, i2), span(b.text, tb, j1, j2)
        pieces.append((f"[-{old}-]" if old else "") + (f"{{+{new}+}}" if new else ""))
        if new:
            s, e = tb[j1][0], tb[j2 - 1][1]
            nb = b.marks[s - 1] if s > 0 else (b.marks[e] if e < len(b.marks) else frozenset())
            for pos in range(s, e):
                if not b.text[pos].isspace():
                    new_marks |= b.marks[pos] - nb
    return " ".join(x for x in pieces if x), new_marks


def mark_changes(a, b):
    """סימונים שהיא הוסיפה או הסירה על טקסט שנשאר כמו שהיה. נבדק תו מול תו.
    מחזיר רשימה של (טקסט, נוספו, הוסרו)."""
    ta, tb, ops = word_ops(a, b)
    diff = {}
    for tag, i1, i2, j1, j2 in ops:
        if tag != "equal" or i2 == i1:
            continue
        sa, ea = ta[i1][0], ta[i2 - 1][1]
        sb, eb = tb[j1][0], tb[j2 - 1][1]
        if a.text[sa:ea] == b.text[sb:eb]:
            pairs = ((sa + k, sb + k) for k in range(ea - sa))
        else:
            sm = difflib.SequenceMatcher(None, a.text[sa:ea], b.text[sb:eb], autojunk=False)
            pairs = ((sa + blk.a + k, sb + blk.b + k) for blk in sm.get_matching_blocks() for k in range(blk.size))
        for pa, pb in pairs:
            ma, mb = a.marks[pa], b.marks[pb]
            if ma != mb:
                diff[pb] = (mb - ma, ma - mb)
    groups = []
    for pb in sorted(diff):
        if groups:
            g = groups[-1]
            gap = b.text[g[1]:pb]
            if diff[pb] == g[2] and (pb == g[1] or not gap.strip()):
                g[1] = pb + 1
                continue
        groups.append([pb, pb + 1, diff[pb]])
    out = []
    for s, e, (added, removed) in groups:
        t = b.text[s:e].strip()
        if t:
            out.append((t, added, removed))
    return out


def tracked_groups(doc, is_new):
    """שינויים חדשים במעקב, לפי פסקה. שינויים צמודים של אותה כותבת מתחברים לפריט אחד.
    מחזיר (¶ אצלה, כותבת, תאריך, טקסט עם [-…-]{+…+})."""
    out = []
    for i, p in enumerate(doc.paras):
        found, state = [], {"gap": True}

        def walk(el):
            for ch in el:
                if ch.tag in SKIP_TAGS:
                    continue
                if ch.tag in INS_TAGS + DEL_TAGS and is_new(ch):
                    found.append((ch, not state["gap"]))
                    state["gap"] = False
                    continue
                if ch.tag == W + "r" and any((t.text or "").strip() for t in ch.iter(W + "t")):
                    state["gap"] = True
                    continue
                walk(ch)

        walk(p)
        groups = []
        for el, adjacent in found:
            text = "".join(x.text or "" for x in el.iter() if x.tag in (W + "t", W + "delText"))
            if not text.strip():
                continue
            piece = f"{{+{text}+}}" if el.tag in INS_TAGS else f"[-{text}-]"
            author, date = el.get(W + "author") or "", el.get(W + "date") or ""
            if groups and adjacent and groups[-1][1] == author:
                groups[-1][3] += piece
            else:
                groups.append([i, author, date, piece])
        out += [tuple(g) for g in groups]
    return out


class Ref:
    """לכל פסקה שלה: מה המספר שלה אצלנו, או אחרי איזו פסקה שלנו היא עומדת."""

    def __init__(self, steps):
        self.exact, self.after, self.added = {}, {}, set()
        last = None
        for kind, a, b in steps:
            if b is not None and kind in ("equal", "changed", "moved"):
                self.exact[b.idx] = a.idx
            elif b is not None:
                self.after[b.idx] = last
                self.added.add(b.idx)
            if a is not None:
                last = a.idx

    def of(self, j, show_hers=True):
        """(¶ שלנו או None, תיאור המקום)."""
        if j is None:
            return None, "בלי מקום במסמך"
        hers = f" (אצלה ¶{j})" if show_hers else ""
        if j in self.exact:
            n = self.exact[j]
            return n, f"¶{n}" + (hers if j != n else "")
        if j in self.after:
            prev = self.after[j]
        else:  # פסקה ריקה אצלה: לפי הפסקה הקודמת לה
            prev = None
            for k in range(j - 1, -1, -1):
                if k in self.exact or k in self.after:
                    prev = self.exact.get(k, self.after.get(k))
                    break
        where = f"אחרי ¶{prev}" if prev is not None else "בתחילת המסמך"
        if j in self.added:
            where = f"בפסקה שהיא הוסיפה, {where}"
        return prev, where + hers


def compare(her_path, our_path):
    ours_doc = Doc(our_path)
    hers_doc = Doc(her_path)
    keys = ours_doc.tracked_keys
    cache = {}

    def is_new(el):
        k = id(el)
        if k not in cache:
            cache[k] = tracked_key(el) not in keys
        return cache[k]

    ours = read_paras(ours_doc, lambda el: False)
    hers = read_paras(hers_doc, is_new)
    steps = align(ours, hers)
    return {"ours_doc": ours_doc, "hers_doc": hers_doc, "ours": ours, "hers": hers, "steps": steps,
            "score": score([p for p in ours if p.norm], [p for p in hers if p.norm], steps), "is_new": is_new}


def findings(res):
    steps, hers_doc, ours_doc = res["steps"], res["hers_doc"], res["ours_doc"]
    ref = Ref(steps)
    F = {k: [] for k in ("del", "add", "chg", "mov", "fmt", "cmt", "trk")}
    minor = []

    # מחיקות ותוספות: פסקאות צמודות הן פריט אחד
    run_kind, run = None, []

    def flush():
        if run:
            F["del" if run_kind == "deleted" else "add"].append(list(run))

    for kind, a, b in steps:
        if kind in ("deleted", "added"):
            if kind != run_kind:
                flush()
                run_kind, run = kind, []
            run.append((a, b))
            continue
        flush()
        run_kind, run = None, []
        if kind == "changed":
            text, new_marks = word_diff(a, b)
            F["chg"].append((a, b, text, new_marks))
        elif kind == "moved":
            F["mov"].append((a, b))
        if kind == "equal" and a.text != b.text:
            minor.append(a.idx)
        if kind in ("equal", "changed", "moved"):
            for t, added, removed in mark_changes(a, b):
                F["fmt"].append((a, b, t, added, removed))
    flush()

    # אותו שינוי סימון בהרבה מקומות, למשל כשהיא הסירה את כל המרקרים שלנו, הוא פריט אחד
    by_sig = {}
    for it in F["fmt"]:
        by_sig.setdefault((it[3], it[4]), []).append(it)
    fmt, done = [], set()
    for it in F["fmt"]:
        sig = (it[3], it[4])
        if len(by_sig[sig]) <= MANY:
            fmt.append(it)
        elif sig not in done:
            fmt.append(("many", sig, by_sig[sig]))
            done.add(sig)
    F["fmt"] = fmt

    for c in hers_doc.comments:
        if (c["author"], norm(c["text"])) in ours_doc.comment_keys:
            continue
        F["cmt"].append((c, ref.of(c["para"])))
    for j, author, date, text in tracked_groups(hers_doc, res["is_new"]):
        F["trk"].append((j, author, date, text, ref.of(j)))
    return F, minor, ref


# ---------- הדוח ----------

CATS = [  # מפתח, כותרת בדוח, אחד, רבים
    ("del", "מחיקות", "מחיקה אחת", "מחיקות"),
    ("add", "תוספות", "תוספת אחת", "תוספות"),
    ("chg", "שינויי נוסח", "שינוי נוסח אחד", "שינויי נוסח"),
    ("mov", "הזזות", "הזזה אחת", "הזזות"),
    ("fmt", "סימונים: מרקר, צבע והדגשה", "סימון אחד", "סימונים"),
    ("cmt", "הערות בוורד", "הערה אחת בוורד", "הערות בוורד"),
    ("trk", "מעקב שינויים", "שינוי אחד במעקב שינויים", "שינויים במעקב שינויים"),
]


def count(n, one, many):
    return one if n == 1 else f"{n} {many}"


def summary(F, minor=()):
    total = sum(len(v) for v in F.values())
    if not total and minor:
        return ("לא נמצא אף שינוי בטקסט או בסימונים, חוץ מניקוד, מירכאות או רווחים ב"
                + ("פסקה אחת" if len(minor) == 1 else f"־{len(minor)} פסקאות") + ". הפירוט בדוח.")
    if not total:
        return "לא נמצא אף שינוי: הקובץ שחזר זהה לגרסה שלנו, גם בטקסט וגם בסימונים."
    parts = [count(len(F[k]), one, many) for k, _, one, many in CATS if F[k]]
    head = "נמצא שינוי אחד" if total == 1 else f"נמצאו {total} שינויים"
    return f"{head}: " + ", ".join(parts)


def tagged(p):
    """הטקסט עם תגיות הסימונים, באותו פורמט כמו בחילוץ_סימונים.py: {[hl:yellow][b]}טקסט{/}"""
    out, last = "", frozenset()
    for ch, mk in zip(p.text, p.marks):
        if mk != last:
            if mk:
                out += "{" + describe_tags(mk) + "}"
            elif last:
                out += "{/}"
            last = mk
        out += ch
    return out + ("{/}" if last else "")


def describe_tags(mk):
    return ms.tag_string(sorted(mk, key=lambda t: TAG_ORDER.index(t.partition(":")[0])
                                if t.partition(":")[0] in TAG_ORDER else 9))


def mark_parts(added, removed):
    parts = []
    if added:
        parts.append("הוסיפה " + describe_set(added))
    if removed:
        parts.append("הסירה " + describe_set(removed))
    return "; ".join(parts)


def q(s, n=LONG):
    return '"' + clip(s, n).replace("\n", " / ") + '"'


def load_decider():
    try:
        with open(SETTINGS, encoding="utf-8-sig") as f:
            name = json.load(f).get("decider")
        return name.strip() if isinstance(name, str) and name.strip() else None
    except (OSError, ValueError, AttributeError):
        return None


def version_notes(results, chosen, our_paths):
    notes = []
    ranked = sorted(results, key=lambda r: -r["score"])
    if len(ranked) > 1 and ranked[0]["score"] - ranked[1]["score"] < CLOSE:
        other = ranked[1] if ranked[0] is chosen else ranked[0]
        notes.append(f'שתי גרסאות קרובות מאוד לקובץ שלה: "{chosen["ours_doc"].name}" ו־"{other["ours_doc"].name}". '
                     "ההשוואה נעשתה מול הראשונה. אם היא ערכה את השנייה, מריצים שוב רק איתה.")
    if len(our_paths) > 1 and os.path.abspath(chosen["ours_doc"].path) != os.path.abspath(our_paths[-1]):
        notes.append(f'היא ערכה את "{chosen["ours_doc"].name}", ולא את הגרסה האחרונה ברשימה '
                     f'("{os.path.basename(our_paths[-1])}"). מה שנוסף אחרי הגרסה שלה לא מופיע כאן כמחיקה, '
                     "כי היא לא ראתה אותו. כשמכניסים את התיקונים שלה, מכניסים אותם לגרסה האחרונה.")
    if chosen["score"] < LOW:
        notes.append("אף גרסה שלנו לא דומה במיוחד לקובץ שלה. אולי חסרה הגרסה שהיא קיבלה. "
                     "לפני שסומכים על הדוח, בודקים איזה קובץ נשלח אליה.")
    return notes


def build_report(results, chosen, our_paths, F, minor, ref, decider):
    hers_doc, ours_doc = chosen["hers_doc"], chosen["ours_doc"]
    who = decider or "היא"
    of_her = f"של {decider}" if decider else "שלה"
    today = datetime.date.today()
    summ = summary(F, minor)
    L = [f"# מה השתנה בקובץ שחזר: {os.path.splitext(hers_doc.name)[0]}", "",
         f"**הקובץ שחזר:** `{hers_doc.name}`",
         f"**הגרסה שלנו שהיא ערכה:** `{ours_doc.name}` (דמיון {round(chosen['score'] * 100)}%)",
         f"**נבדק:** {today.day}.{today.month}.{today.year}",
         f"**בקצרה:** {summ}" + ("" if summ.endswith(".") else "."), "",
         f"**כל פריט כאן הוא הערה {of_her}:** גם מחיקה בלי מילה, גם סימון בצבע, וגם הערה שנכתבה כשאלה. "
         "על כל פריט שואלים: יש לו כבר כלל?",
         "- **יש כלל:** הבדיקה פספסה אותו. מחדדים את הכלל, ורושמים במבחן וביומן.",
         "- **אין כלל:** מוסיפים כלל חדש, עם מקור ותאריך.",
         f"- **מחיקה או סימון בלי מילים** הם הסקה. הכלל נכתב \"לאשר עם {who}\", ונשאלת שאלה סגורה. "
         "את מה שנשאר אחרי מחיקה לא מוחקים על דעתנו.", "",
         "**איך קוראים:** ¶N הוא מספר הפסקה בגרסה שלנו, כמו בפלט של `מספור_פסקאות.py`, וזה המספר שנכנס "
         "ל־`findings.json` של `החלת_תיקונים.py`. בסוגריים, המספר אצלה. `[-טקסט-]` הוא מה שהיה אצלנו, "
         "ו־`{+טקסט+}` הוא מה שכתוב אצלה.", ""]
    notes = version_notes(results, chosen, our_paths)
    if notes:
        L += ["> **שימי לב:** " + n for n in notes] + [""]
    L += ["## איזו גרסה שלנו היא ערכה", "", "| הגרסה שלנו | דמיון לקובץ שלה |", "|---|---|"]
    for r in results:
        mark = " ← מולה ההשוואה" if r is chosen else ""
        L.append(f"| `{r['ours_doc'].name}` | {round(r['score'] * 100)}%{mark} |")
    L.append("")

    n = 0
    missing = []
    for key, title, _one, _many in CATS:
        items = F[key]
        if not items:
            missing.append(title.split(":")[0])
            continue
        L += [f"## {title} ({len(items)})", ""]
        for it in items:
            n += 1
            if key == "del":
                nums = [a.idx for a, _ in it]
                head = f"¶{nums[0]}" if len(nums) == 1 else f"¶{nums[0]}–¶{nums[-1]}"
                L.append(f"**{n}. {head}: {who} מחקה " + ("פסקה אחת" if len(nums) == 1 else f"{len(nums)} פסקאות")
                         + ".**")
                L += [f"- ¶{a.idx}: {q(a.text, FULL)}" for a, _ in it]
            elif key == "add":
                js = [b.idx for _, b in it]
                _, where = ref.of(js[0], show_hers=False)
                where = where.replace("בפסקה שהיא הוסיפה, ", "")
                L.append(f"**{n}. {where}: {who} הוסיפה " + ("פסקה אחת" if len(js) == 1 else f"{len(js)} פסקאות")
                         + ".**")
                for _, b in it:
                    L.append(f"- אצלה ¶{b.idx}: {q(tagged(b), FULL)}")
            elif key == "chg":
                a, b, text, new_marks = it
                _, where = ref.of(b.idx)
                L.append(f"**{n}. {where}:** {text}")
                if new_marks:
                    L.append(f"- הטקסט החדש שלה מסומן: {describe_set(new_marks)}")
            elif key == "mov":
                a, b = it
                _, where = ref.of(b.idx, show_hers=False)
                L.append(f"**{n}. ¶{a.idx} הוזזה.** אצלה היא ¶{b.idx}. {q(a.text)}")
            elif key == "fmt" and it[0] == "many":
                (added, removed), items = it[1], it[2]
                nums = sorted({a.idx for a, *_ in items})
                shown = ", ".join(f"¶{i}" for i in nums[:40]) + (" …" if len(nums) > 40 else "")
                examples = ", ".join(q(t, 80) for *_, t, _a, _r in items[:3])
                L.append(f"**{n}. אותו שינוי ב־{len(items)} מקומות "
                         f"({count(len(nums), 'בפסקה אחת', 'פסקאות')}):** {mark_parts(added, removed)}. "
                         f"לדוגמה: {examples}. הפסקאות: {shown}")
            elif key == "fmt":
                a, b, t, added, removed = it
                _, where = ref.of(b.idx)
                L.append(f"**{n}. {where}:** {mark_parts(added, removed)}, על {q(t)}")
            elif key == "cmt":
                c, (_num, where) = it
                meta = ", ".join(x for x in (c["author"], ms.short_date(c["date"])) if x)
                anchor = f", על {q(c['anchor'])}" if c["anchor"] else ""
                L.append(f"**{n}. {where}** · {meta}{anchor}:")
                L.append("> " + clip(c["text"], FULL).replace("\n", "\n> "))
            elif key == "trk":
                j, author, date, text, (_num, where) = it
                meta = ", ".join(x for x in (author, ms.short_date(date)) if x)
                L.append(f"**{n}. {where}** · {meta}: {clip(text, FULL)}")
            L.append("")
    if minor:
        shown = ", ".join(f"¶{i}" for i in minor[:30]) + (" …" if len(minor) > 30 else "")
        L += [f"**השתנו רק ניקוד, מירכאות או רווחים** ({count(len(minor), 'פסקה אחת', 'פסקאות')}), "
              f"ולכן זה לא נספר כשינוי: {shown}. אם זה חשוב בתוצר הזה, בודקים ביד.", ""]
    if missing:
        L += ["**נבדק ולא נמצא:** " + ", ".join(missing) + ".", ""]
    return "\n".join(L)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="השוואה של קובץ שחזר לגרסאות שלנו. ראו את ההסבר בראש הקובץ.")
    ap.add_argument("hers", help="הקובץ שחזר ממנה")
    ap.add_argument("ours", nargs="+", help="הגרסאות שלנו, מהישנה לחדשה")
    ap.add_argument("--out", help='הדוח. ברירת המחדל: ליד הקובץ שחזר, "<שם> - השוואה.md"')
    args = ap.parse_args()

    if any(os.path.abspath(o) == os.path.abspath(args.hers) for o in args.ours):
        print("הקובץ שחזר מופיע גם ברשימת הגרסאות שלנו. צריך לתת אותו רק פעם אחת, ראשון.")
        sys.exit(1)
    results = []
    try:
        for o in args.ours:
            results.append(compare(args.hers, o))
    except mp.DocxError as e:
        print(str(e))
        sys.exit(1)
    # הדומה ביותר. בשוויון: המאוחרת ברשימה
    chosen = max(reversed(results), key=lambda r: r["score"])
    F, minor, ref = findings(chosen)
    report = build_report(results, chosen, args.ours, F, minor, ref, load_decider())
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.hers)),
                                   os.path.splitext(os.path.basename(args.hers))[0] + " - השוואה.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    print(summary(F, minor))
    print(f"הדוח: {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
