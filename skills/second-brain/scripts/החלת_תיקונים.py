# -*- coding: utf-8 -*-
"""מכניס תיקונים לקובץ וורד: כל תיקון כמעקב שינויים וכל הערה כהערה בצד, ועוד עותק נקי בלי מעקב ובלי הערות.

    python _כלים/החלת_תיקונים.py "<קובץ>.docx" findings.json "<עם מעקב>.docx" "<נקי>.docx" log.json [קטגוריות]
    (במק: python3 במקום python)

findings.json:
    {"findings": [
      {"para": 12, "type": "change",  "find": "קטנטנים", "replace": "ילדים", "note": "כלל 1.1", "category": "מילים"},
      {"para": 15, "type": "comment", "find": "20% הנחה", "note": "להשאיר את המבצע?"}
    ]}
- para: מספר הפסקה, ¶N, כמו בפלט של מספור_פסקאות.py ובדוח של השוואת_גרסאות.py, באותו קובץ שמקבל את התיקונים.
- type: change מחליף את find ב־replace. replace ריק מוחק. comment מוסיף הערה בצד על find.
- find: הטקסט המדויק מתוך הפסקה. גם כשסדר סימני הניקוד שונה, הוא נמצא.
- note: ההסבר. בשינוי, ההסבר נכנס כהערה בצד, ליד השינוי.
- category: לא חובה. כשכותבים בסוף הפקודה רשימת קטגוריות מופרדת בפסיקים (למשל: מילים,חתימה),
  רק לשינויים מהקטגוריות האלה נכנסת הערה בצד. בלי הרשימה, לכל שינוי שיש לו note נכנסת הערה.
אפשר גם רשימה של ממצאים בלי {"findings": ...} מסביב.

מה יוצא:
- הקובץ עם המעקב: כל שינוי כמחיקה והוספה במעקב שינויים, וכל הערה כהערה בצד, בשם של מי שמקלידה
  ("operator" ב"_כלים/הגדרות.json"), ובתאריך של היום.
- הקובץ הנקי: אותם שינויים, כבר בפנים, בלי מעקב ובלי הערות.
- log.json: מה נכנס, ומה לא ולמה. במסך מודפסים רק מספרים: כמה נכנסו, ומספר הממצא שלא נכנס.
  מספר ממצא הוא המקום שלו ברשימה, החל מ־0, כמו "n" ב־log.json.
תיקונים באותה פסקה נכנסים מהסוף להתחלה, כדי שהמקומות לא יזוזו. שני ממצאים על אותו טקסט: נכנס רק הראשון.
הקובץ המקורי לא משתנה.

צריך python-docx בגרסה 1.2 ומעלה (בה יש הערות בצד). כשהוא חסר, הכלי מסביר מה להתקין ויוצא בקוד 2.
יוצא בקוד 1 כשחסר קובץ, כשההגדרות חסרות או כשיש ממצא שלא נכנס.
"""
import copy
import datetime
import importlib.util
import json
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "הגדרות.json")

MISSING = """python-docx לא מותקן במחשב הזה, ולכן אי אפשר להכניס מעקב שינויים והערות.

ל־Claude: קודם שואלים את מי שעובדת עם המוח אם להתקין. אומרים לה שזה חינם, ושזו ספרייה לקריאה ולכתיבה
של קובצי וורד. אחרי שהיא מאשרת:

    pip install python-docx

אם pip לא נמצא:  python -m pip install python-docx    (במק: python3 -m pip install python-docx)
אחר כך מריצים שוב את אותה פקודה."""

OLD = """python-docx מותקן במחשב הזה, אבל בגרסה ישנה מ־1.2, ובה אין הערות בצד.

ל־Claude: קודם שואלים את מי שעובדת עם המוח אם לעדכן. אחרי שהיא מאשרת:

    pip install -U python-docx

אחר כך מריצים שוב את אותה פקודה."""

STATUS_HE = {
    "bad para": "אין פסקה במספר הזה",
    "not found": "הטקסט לא נמצא בפסקה",
    "overlap": "חופף לממצא אחר באותה פסקה",
    "error": "לא הצליח להיכנס",
    "note not attached": "השינוי נכנס, אבל לא נמצא מקום להערה שלידו",
    "ambiguous-first-used": "הטקסט מופיע כמה פעמים בפסקה, ונבחר הראשון",
}


def need_docx():
    if importlib.util.find_spec("docx") is None:
        print(MISSING)
        sys.exit(2)
    from docx.document import Document as _D
    if not hasattr(_D, "add_comment"):
        print(OLD)
        sys.exit(2)


def load_operator():
    """(שם, ראשי תיבות) מתוך "_כלים/הגדרות.json". כשחסר, מדפיס הסבר ויוצא בקוד 1."""
    try:
        with open(SETTINGS, encoding="utf-8-sig") as f:
            data = json.load(f)
    except OSError:
        print('חסר הקובץ "_כלים/הגדרות.json". בלעדיו אין שם למעקב השינויים ולהערות. '
              "הוא צריך להיות כמו הדוגמה שבחוזה, עם השדה \"operator\".")
        sys.exit(1)
    except ValueError:
        print('אי אפשר לקרוא את "_כלים/הגדרות.json": יש בו טעות בכתיבה. הוא צריך להיות כמו הדוגמה שבחוזה.')
        sys.exit(1)
    name = data.get("operator") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        print('ב"_כלים/הגדרות.json" חסר השדה "operator", או שהוא ריק. זה השם שיופיע במעקב השינויים ובהערות.')
        sys.exit(1)
    name = name.strip()
    letters = [w[0] for w in name.split() if w][:3]
    initials = letters[0] + "'" if len(letters) == 1 else "".join(letters[:-1]) + '"' + letters[-1]
    return name, initials


def clusters(s):
    out, cur = [], ""
    for ch in s:
        if cur and unicodedata.combining(ch):
            cur += ch
        else:
            if cur:
                out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out


def norm_cluster(c):
    return unicodedata.normalize("NFC", c)


def locate(text, find):
    """(התחלה, סוף) של find בתוך text, גם כשסדר סימני הניקוד שונה, ומספר ההופעות. (None, 0) כשאין."""
    i = text.find(find)
    if i >= 0:
        return (i, i + len(find)), text.count(find)
    tc = clusters(text)
    fc = [norm_cluster(c) for c in clusters(find)]
    tcn = [norm_cluster(c) for c in tc]
    hits = [k for k in range(len(tcn) - len(fc) + 1) if tcn[k:k + len(fc)] == fc]
    if not hits:
        return None, 0
    k = hits[0]
    start = sum(len(c) for c in tc[:k])
    end = start + sum(len(c) for c in tc[k:k + len(fc)])
    return (start, end), len(hits)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if len(args) < 5 or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args and args[0] in ("-h", "--help") else 1)
    need_docx()
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.text.run import Run

    src, fpath, out_tracked, out_clean, log_path = args[:5]
    note_cats = set(c.strip() for c in args[5].split(",") if c.strip()) if len(args) > 5 else None
    author, initials = load_operator()
    date = datetime.date.today().strftime("%Y-%m-%dT12:00:00Z")  # יום הבנייה
    for p, what in ((src, "הקובץ"), (fpath, "קובץ הממצאים")):
        if not os.path.isfile(p):
            print(f'{what} "{os.path.basename(p)}" לא נמצא. צריך לבדוק את הנתיב.')
            sys.exit(1)
    try:
        with open(fpath, encoding="utf-8-sig") as f:
            data = json.load(f)
    except ValueError as e:
        print(f'אי אפשר לקרוא את "{os.path.basename(fpath)}": יש טעות בכתיבה בשורה {getattr(e, "lineno", "?")}.')
        sys.exit(1)
    findings = data["findings"] if isinstance(data, dict) else data

    def body_paragraphs(doc):
        body = doc.element.body
        res = []
        for p in body.iter(qn("w:p")):
            anc, skip = p.getparent(), False
            while anc is not None and anc is not body:
                if anc.tag == qn("w:txbxContent"):
                    skip = True
                    break
                anc = anc.getparent()
            if not skip:
                res.append(p)
        return res

    def live_runs(p):
        """ריצות הטקסט לפי הסדר, בלי מה שבתוך מחיקה במעקב."""
        out = []
        for r in p.iter(qn("w:r")):
            anc, dead = r.getparent(), False
            while anc is not None and anc is not p:
                if anc.tag == qn("w:del"):
                    dead = True
                    break
                anc = anc.getparent()
            if not dead:
                out.append(r)
        return out

    def run_text(r):
        return "".join(t.text or "" for t in r.findall(qn("w:t")))

    def para_text(p):
        return "".join(run_text(r) for r in live_runs(p))

    def split_run(r, off):
        ts = r.findall(qn("w:t"))
        if len(ts) != 1:
            raise ValueError("run with %d w:t" % len(ts))
        t = ts[0]
        s = t.text or ""
        right = copy.deepcopy(r)
        t.text = s[:off]
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        rt = right.find(qn("w:t"))
        rt.text = s[off:]
        rt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.addnext(right)
        return right

    def isolate(p, start, end):
        """הטווח [start, end) מכוסה בדיוק בריצות שלמות. מחזיר את הריצות האלה."""
        for cut in (end, start):
            pos = 0
            for r in live_runs(p):
                n = len(run_text(r))
                if pos < cut < pos + n:
                    split_run(r, cut - pos)
                    break
                pos += n
        covered, pos = [], 0
        for r in live_runs(p):
            n = len(run_text(r))
            if n and pos >= start and pos + n <= end:
                covered.append(r)
            pos += n
        return covered

    _id = [9000]

    def next_id():
        _id[0] += 1
        return str(_id[0])

    def make_run_like(r, text):
        nr = OxmlElement("w:r")
        rpr = r.find(qn("w:rPr"))
        if rpr is not None:
            nr.append(copy.deepcopy(rpr))
        t = OxmlElement("w:t")
        t.text = text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        nr.append(t)
        return nr

    def neighbour_run(el):
        """ריצה חיה עם טקסט ליד מחיקה, כדי שתהיה להערה נקודת עיגון: אחריה, ואם אין, לפניה."""
        for sib in list(el.itersiblings()) + list(el.itersiblings(preceding=True)):
            if sib.tag == qn("w:r") and run_text(sib):
                return sib
        return None

    def apply_change(p, start, end, replace, tracked):
        runs = isolate(p, start, end)
        if not runs:
            raise ValueError("no runs covered")
        if len({r.getparent() for r in runs}) != 1:
            raise ValueError("span crosses containers")
        first = runs[0]
        new_run = make_run_like(first, replace) if replace else None
        if tracked:
            last_del = None
            for r in runs:
                d = OxmlElement("w:del")
                d.set(qn("w:id"), next_id())
                d.set(qn("w:author"), author)
                d.set(qn("w:date"), date)
                r.addprevious(d)
                d.append(r)
                for t in r.findall(qn("w:t")):
                    t.tag = qn("w:delText")
                last_del = d
            if new_run is not None:
                ins = OxmlElement("w:ins")
                ins.set(qn("w:id"), next_id())
                ins.set(qn("w:author"), author)
                ins.set(qn("w:date"), date)
                ins.append(new_run)
                last_del.addnext(ins)
                return [new_run]
            nb = neighbour_run(last_del)
            return [nb] if nb is not None else []
        if new_run is not None:
            first.addprevious(new_run)
        for r in runs:
            r.getparent().remove(r)
        return [new_run] if new_run is not None else []

    def rtl_comment(c):
        for par in c.paragraphs:
            ppr = par._p.get_or_add_pPr()
            if ppr.find(qn("w:bidi")) is None:
                ppr.insert(0, OxmlElement("w:bidi"))
            for r in par.runs:
                rpr = r._r.get_or_add_rPr()
                if rpr.find(qn("w:rtl")) is None:
                    rpr.append(OxmlElement("w:rtl"))

    def wants_note(f):
        if not f.get("note"):
            return False
        return note_cats is None or f.get("category") in note_cats

    def build(tracked):
        doc = Document(src)
        for e in list(doc.element.body.iter(qn("w:proofErr"))):
            e.getparent().remove(e)
        paras = body_paragraphs(doc)
        log, by_para = [], {}
        for n, f in enumerate(findings):
            f["_n"] = n
            try:
                by_para.setdefault(int(f["para"]), []).append(f)
            except (KeyError, TypeError, ValueError):
                log.append({"n": n, "status": "bad para"})
        for pi, fs in by_para.items():
            if pi < 0 or pi >= len(paras):
                log += [{"n": f["_n"], "para": pi, "status": "bad para"} for f in fs]
                continue
            p = paras[pi]
            text = para_text(p)
            placed = []
            for f in fs:
                span, cnt = locate(text, f["find"]) if f.get("find") else (None, 0)
                if span is None:
                    log.append({"n": f["_n"], "para": pi, "status": "not found", "find": f.get("find")})
                    continue
                if any(not (span[1] <= a or span[0] >= b) for a, b, _ in placed):
                    log.append({"n": f["_n"], "para": pi, "status": "overlap", "find": f.get("find")})
                    continue
                if cnt > 1:
                    log.append({"n": f["_n"], "para": pi, "status": "ambiguous-first-used", "count": cnt})
                placed.append((span[0], span[1], f))
            for a, b, f in sorted(placed, key=lambda x: -x[0]):
                try:
                    if f.get("type") == "change":
                        new_runs = apply_change(p, a, b, f.get("replace", ""), tracked)
                        status = "ok"
                        if tracked and wants_note(f):
                            rr = [Run(x, None) for x in new_runs if x.tag == qn("w:r")]
                            if rr:
                                rtl_comment(doc.add_comment(rr, text=f["note"], author=author, initials=initials))
                            else:
                                status = "note not attached"
                        log.append({"n": f["_n"], "para": pi, "status": status})
                    elif f.get("type") == "comment":
                        if tracked:
                            runs = isolate(p, a, b)
                            c = doc.add_comment([Run(r, None) for r in runs], text=f.get("note", ""),
                                                author=author, initials=initials)
                            rtl_comment(c)
                        log.append({"n": f["_n"], "para": pi, "status": "ok"})
                    else:
                        log.append({"n": f["_n"], "para": pi, "status": "error", "err": "unknown type"})
                except Exception as e:  # noqa: BLE001 - ממצא אחד שנכשל לא עוצר את השאר, ונרשם ביומן
                    log.append({"n": f["_n"], "para": pi, "status": "error", "err": str(e)})
        return doc, log

    try:
        doc_t, log_t = build(True)
        doc_t.save(out_tracked)
        doc_c, log_c = build(False)
        doc_c.save(out_clean)
    except PermissionError:
        print("אי אפשר לשמור: אחד מקובצי הפלט פתוח בוורד. סוגרים אותו ומריצים שוב.")
        sys.exit(1)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({"tracked": log_t, "clean": log_c}, f, ensure_ascii=False, indent=1)

    ok = sum(1 for x in log_t if x["status"] == "ok")
    warn = [x for x in log_t if x["status"] in ("ambiguous-first-used", "note not attached")]
    bad = [x for x in log_t if x["status"] not in ("ok", "ambiguous-first-used", "note not attached")]
    print(f"{len(findings)} ממצאים. נכנסו: {ok + sum(1 for x in warn if x['status'] == 'note not attached')}. "
          f"לא נכנסו: {len(bad)}.")
    for x in warn + bad:
        where = f" (¶{x['para']})" if "para" in x else ""
        print(f"  ממצא {x['n']}{where}: {STATUS_HE.get(x['status'], x['status'])}")
    print(f"עם מעקב: {os.path.abspath(out_tracked)}")
    print(f"נקי: {os.path.abspath(out_clean)}")
    print(f"הפירוט: {os.path.abspath(log_path)}")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
