# -*- coding: utf-8 -*-
"""כל הסימונים שבקובץ וורד: מרקר, צבע רקע, צבע גופן והדגשה, וגם ההערות בצד.

    python _כלים/חילוץ_סימונים.py "<קובץ>.docx"                הפלט נכתב ליד הקובץ: "<שם> - סימונים.txt"
    python _כלים/חילוץ_סימונים.py "<קובץ>.docx" "<פלט>.txt"
    (במק: python3 במקום python)

למה: לקוחה מסמנת לפעמים בצבע בלי לכתוב מילה, וסימון כזה הוא הערה. כך אף סימון לא נופל.

איך קוראים את הפלט:
- שורה לכל פסקה, לפי הסדר. לפני פסקה עם סגנון כתוב <הסגנון>, ו־#num כשהיא ברשימה ממוספרת.
- טקסט מסומן עטוף בתגית: {[hl:yellow][c:FF0000][b]}הטקסט{/}
    hl   מרקר (צבע סימון טקסט), עם שם הצבע
    shd  צבע רקע (הצללה), בקוד צבע
    c    צבע גופן, בקוד צבע. שחור ו"אוטומטי" לא מסומנים
    b    מודגש
    u    קו תחתון
    s    קו חוצה (גם כפול)
- טבלה מופיעה בין "=== TABLE ===" ל־"=== END TABLE ===": שורה לכל שורה בטבלה, || בין תאים, | בין פסקאות בתא.
- "--- SECTION ---" הוא סוף מקטע.
- בסוף, בין "=== COMMENTS ===" ל־"=== END COMMENTS ===": כל הערה בצד. מי כתבה, מתי, באיזו פסקה (¶N, אותו
  מספור של מספור_פסקאות.py), על איזה טקסט היא עומדת, ומה כתוב בה.
נקראים רק סימונים שנעשו ישירות על הטקסט, ולא סימונים שבאים מסגנון.

מודפסים רק מספר השורות, מספר ההערות והנתיב של הפלט.
בלי ספריות חיצוניות: רק פייתון עצמו. יוצא בקוד 1 כשאי אפשר לקרוא את הקובץ.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import מספור_פסקאות as mp  # noqa: E402

W = mp.W
OFF = ("0", "false", "off", "none")


def run_tags(rpr):
    """התגיות של ריצת טקסט, לפי הסדר הקבוע: hl, shd, c, b, u, s."""
    tags = []
    if rpr is None:
        return tags
    hl = rpr.find(W + "highlight")
    sh = rpr.find(W + "shd")
    col = rpr.find(W + "color")
    b = rpr.find(W + "b")
    u = rpr.find(W + "u")
    st = rpr.find(W + "strike")
    dst = rpr.find(W + "dstrike")
    if hl is not None and hl.get(W + "val") not in (None, "none"):
        tags.append("hl:" + hl.get(W + "val"))
    if sh is not None and sh.get(W + "fill") not in (None, "auto", "FFFFFF"):
        tags.append("shd:" + sh.get(W + "fill"))
    if col is not None and col.get(W + "val") not in (None, "000000", "auto"):
        tags.append("c:" + col.get(W + "val"))
    if b is not None and b.get(W + "val") not in OFF:
        tags.append("b")
    if u is not None and (u.get(W + "val") or "single") not in OFF:
        tags.append("u")
    if any(x is not None and x.get(W + "val") not in OFF for x in (st, dst)):
        tags.append("s")
    return tags


def tag_string(tags):
    return "".join("[" + t + "]" for t in tags)


def para_marked(p):
    """הטקסט של הפסקה עם התגיות. אותו פורמט כמו בכלי המקורי."""
    parts = []
    for r in p.iter(W + "r"):
        tag = tag_string(run_tags(r.find(W + "rPr")))
        t = "".join((x.text or "") for x in r.iter(W + "t"))
        if r.find(W + "tab") is not None:
            t = "\t" + t
        if r.find(W + "br") is not None:
            t = t + " / "
        if t:
            parts.append((tag, t))
    s, last = "", None
    for tag, t in parts:
        if tag != last:
            if tag:
                s += "{" + tag + "}"
            elif last:
                s += "{/}"
            last = tag
        s += t
    if last:
        s += "{/}"
    return s


def walk_lines(body):
    lines = []

    def walk(el, depth=0):
        for ch in el:
            if ch.tag == W + "p":
                ppr = ch.find(W + "pPr")
                style = ""
                if ppr is not None:
                    ps = ppr.find(W + "pStyle")
                    if ps is not None:
                        style = ps.get(W + "val")
                    if ppr.find(W + "numPr") is not None:
                        style += "#num"
                lines.append(("  " * depth) + (f"<{style}> " if style else "") + para_marked(ch))
            elif ch.tag == W + "tbl":
                lines.append(("  " * depth) + "=== TABLE ===")
                for tr in ch.iter(W + "tr"):
                    cells = []
                    for tc in tr.findall(W + "tc"):
                        cells.append(" | ".join(para_marked(p) for p in tc.iter(W + "p")))
                    lines.append(("  " * depth) + " || ".join(cells))
                lines.append(("  " * depth) + "=== END TABLE ===")
            elif ch.tag == W + "sdt":
                c = ch.find(W + "sdtContent")
                if c is not None:
                    walk(c, depth)
            elif ch.tag == W + "sectPr":
                lines.append("--- SECTION ---")

    walk(body)
    return lines


# ---------- הערות בצד ----------

def short_date(iso):
    """'2026-11-05T06:47:00Z' -> '5.11.2026'. וורד כותב שעה מקומית, ולכן התאריך נלקח כמו שהוא."""
    if not iso or len(iso) < 10:
        return ""
    y, m, d = iso[:4], iso[5:7], iso[8:10]
    if not (y.isdigit() and m.isdigit() and d.isdigit()):
        return ""
    return f"{int(d)}.{int(m)}.{y}"


def read_comments(z, body, paras):
    """ההערות בצד, לפי הסדר במסמך. לכל הערה: id, author, initials, date, text, anchor (הטקסט שהיא
    מסמנת), para (¶ של הפסקה שבה היא מתחילה, או None)."""
    root = mp.read_part(z, "word/comments.xml")
    if root is None:
        return []
    comments = {}
    order = []
    for c in root.findall(W + "comment"):
        cid = c.get(W + "id")
        text = "\n".join("".join(t.text or "" for t in p.iter(W + "t")) for p in c.iter(W + "p")).strip()
        comments[cid] = {"id": cid, "author": c.get(W + "author") or "", "initials": c.get(W + "initials") or "",
                         "date": c.get(W + "date") or "", "text": text, "anchor": "", "para": None}
        order.append(cid)

    idx_of = {id(p): i for i, p in enumerate(paras)}
    open_ids, pieces, seen = [], {}, []

    def note_para(cid, cur):
        if cid in comments and comments[cid]["para"] is None and cur is not None:
            comments[cid]["para"] = cur

    def walk(el, cur):
        for ch in el:
            here = idx_of.get(id(ch), cur)
            tag = ch.tag
            if tag == W + "commentRangeStart":
                cid = ch.get(W + "id")
                open_ids.append(cid)
                pieces.setdefault(cid, [])
                note_para(cid, cur)
                if cid not in seen:
                    seen.append(cid)
            elif tag == W + "commentRangeEnd":
                cid = ch.get(W + "id")
                if cid in open_ids:
                    open_ids.remove(cid)
            elif tag == W + "commentReference":
                cid = ch.get(W + "id")
                note_para(cid, cur)
                if cid not in seen:
                    seen.append(cid)
            elif tag == W + "t" and ch.text:
                for cid in open_ids:
                    pieces[cid].append(ch.text)
                    note_para(cid, cur)
            walk(ch, here)

    walk(body, None)
    for cid, ps in pieces.items():
        if cid in comments:
            comments[cid]["anchor"] = "".join(ps).strip()
    ordered = [cid for cid in seen if cid in comments] + [cid for cid in order if cid not in seen]
    return [comments[cid] for cid in ordered]


def comment_lines(comments):
    lines = ["=== COMMENTS ==="]
    for n, c in enumerate(comments, 1):
        where = f"¶{c['para']}" if c["para"] is not None else "בלי מקום במסמך"
        anchor = f' על "{c["anchor"]}"' if c["anchor"] else ""
        who = ", ".join(x for x in (c["author"], short_date(c["date"])) if x)
        text = c["text"].replace("\n", " / ")
        lines.append(f"[הערה {n}] {who}, {where}{anchor}: {text}")
    lines.append("=== END COMMENTS ===")
    return lines


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if not args or len(args) > 2 or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args and args[0] in ("-h", "--help") else 1)
    src = args[0]
    out = args[1] if len(args) > 1 else mp.default_out(src, "סימונים")
    try:
        z = mp.open_docx(src)
        body = mp.body_of(z)
    except mp.DocxError as e:
        print(str(e))
        sys.exit(1)
    lines = walk_lines(body)
    comments = read_comments(z, body, mp.body_paragraphs(body))
    n_body = len(lines)
    if comments:
        lines += comment_lines(comments)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    marked = sum(1 for l in lines[:n_body] if "{[" in l)
    lines_he = "שורה אחת" if n_body == 1 else f"{n_body} שורות"
    marked_he = "אין סימונים" if not marked else ("בשורה אחת יש סימון" if marked == 1 else f"ב־{marked} מהן יש סימון")
    print(f"{lines_he}, {marked_he}. "
          + ("אין הערות בצד." if not comments else
             ("הערה אחת בצד." if len(comments) == 1 else f"{len(comments)} הערות בצד.")))
    print(f"הפלט: {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
