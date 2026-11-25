# -*- coding: utf-8 -*-
"""פסקאות ממוספרות מקובץ וורד, כדי שכל מי שעובדת על הקובץ תדבר על אותו מספר פסקה.

    python _כלים/מספור_פסקאות.py "<קובץ>.docx"                הפלט נכתב ליד הקובץ: "<שם> - פסקאות.txt"
    python _כלים/מספור_פסקאות.py "<קובץ>.docx" "<פלט>.txt"
    (במק: python3 במקום python)

כל שורה בפלט היא פסקה אחת: "¶N: הטקסט".
- N הוא המקום של הפסקה בגוף המסמך, לפי הסדר, החל מ־0.
  נספרות גם פסקאות ריקות וגם פסקאות בתוך טבלאות.
  פסקה בתוך תיבת טקסט לא נספרת. הטקסט שלה מופיע בפסקה שהתיבה עומדת בה.
- זה המספור של השוואת_גרסאות.py ושל החלת_תיקונים.py. ¶N בדוח ההשוואה וב־findings.json הוא אותו N.
- טקסט שנמחק במעקב שינויים לא מופיע. טקסט שנוסף במעקב שינויים מופיע.
- כותרות עליונות, כותרות תחתונות, הערות שוליים והערות בצד לא נכנסות. את ההערות בצד מוציא חילוץ_סימונים.py.

מודפסים רק מספר הפסקאות והנתיב של הפלט, ולא הטקסט עצמו.
בלי ספריות חיצוניות: רק פייתון עצמו. יוצא בקוד 1 כשאי אפשר לקרוא את הקובץ.
"""
import os
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TXBX = W + "txbxContent"


class DocxError(Exception):
    """בעיה בקובץ, עם הסבר בעברית שאפשר להדפיס כמו שהוא."""


def open_docx(path):
    """פותח קובץ docx לקריאה. כשזה לא docx, זורק DocxError עם הסבר."""
    name = os.path.basename(path)
    if not os.path.isfile(path):
        raise DocxError(f'הקובץ "{name}" לא נמצא. צריך לבדוק את הנתיב.')
    if path.lower().endswith(".doc"):
        raise DocxError(f'"{name}" הוא קובץ וורד ישן (doc). פותחים אותו בוורד ושומרים בשם, '
                        'כ"מסמך Word (docx)", ואז מריצים שוב על הקובץ החדש.')
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise DocxError(f'"{name}" הוא לא קובץ docx תקין. אם הוא פתוח בוורד, סוגרים אותו ומנסים שוב.')
    if "word/document.xml" not in z.namelist():
        raise DocxError(f'"{name}" הוא לא קובץ וורד: אין בו את גוף המסמך.')
    return z


def read_part(z, part):
    """XML של חלק בתוך הקובץ, או None כשהחלק לא קיים."""
    try:
        data = z.read(part)
    except KeyError:
        return None
    return ET.fromstring(data)


def body_of(z):
    root = read_part(z, "word/document.xml")
    body = root.find(W + "body")
    if body is None:
        raise DocxError("אין גוף מסמך בקובץ.")
    return body


def body_paragraphs(body):
    """כל הפסקאות בגוף המסמך, לפי הסדר, כולל פסקאות בטבלאות, בלי פסקאות בתוך תיבות טקסט.
    זה בדיוק הסדר של body.iter(w:p) בכלים המקוריים, בלי מה שיש לו אב txbxContent."""
    out = []

    def walk(el):
        for ch in el:
            if ch.tag == TXBX:
                continue
            if ch.tag == W + "p":
                out.append(ch)
            walk(ch)

    walk(body)
    return out


def para_text(p):
    """הטקסט של הפסקה: כל ה־w:t שבתוכה, לפי הסדר. זה הטקסט שהחלת_תיקונים.py מחפש בו."""
    return "".join(t.text or "" for t in p.iter(W + "t"))


def default_out(path, suffix):
    stem = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(os.path.dirname(os.path.abspath(path)), f"{stem} - {suffix}.txt")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if not args or len(args) > 2 or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args and args[0] in ("-h", "--help") else 1)
    src = args[0]
    out = args[1] if len(args) > 1 else default_out(src, "פסקאות")
    try:
        paras = body_paragraphs(body_of(open_docx(src)))
    except DocxError as e:
        print(str(e))
        sys.exit(1)
    lines = [f"¶{i}: {para_text(p)}" for i, p in enumerate(paras)]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    empty = sum(1 for p in paras if not para_text(p).strip())
    if not paras:
        print("אין פסקאות בגוף המסמך.")
    else:
        total = "פסקה אחת" if len(paras) == 1 else f"{len(paras)} פסקאות"
        blank = "" if not empty else (", מתוכן פסקה ריקה אחת" if empty == 1 else f", מתוכן {empty} ריקות")
        print(f"{total}{blank}. המספור: מ־¶0 עד ¶{len(paras) - 1}.")
    print(f"הפלט: {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
