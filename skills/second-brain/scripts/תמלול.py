# -*- coding: utf-8 -*-
"""תמלול של הקלטות וסרטונים במחשב עצמו, בלי לשלוח אותם לשום שירות.

    python _כלים/תמלול.py                        כל ההקלטות והסרטונים ב"מקורות/" שעוד אין להם תמלול
    python _כלים/תמלול.py "מקורות/שיחה.m4a"      רק הקבצים האלה (אפשר גם תיקייה בתוך "מקורות/")
    python _כלים/תמלול.py --dry-run              רק מראה מה יתומלל, וכמה זמן ההקלטות
    (במק: python3 במקום python)

איך זה עובד:
- faster-whisper על המעבד (int8), עם המודל העברי ivrit-ai/whisper-large-v3-turbo-ct2.
  בפעם הראשונה המודל יורד מהאינטרנט, פעם אחת, כ־1.6GB. אחר כך התמלול עובד גם בלי אינטרנט.
  זה איטי: בערך פי 1.5 עד 3 מאורך ההקלטה.
- התמלול הגולמי נכתב קודם לתיקייה הרגישה:
  "מקורות/_רגיש/תמלול גולמי/<8 התווים הראשונים של md5> <שם>.md", עם זמן [דקות:שניות] לכל משפט.
  השם מתחיל בטביעת האצבע, ולכן הקלטה שעברה תיקייה או שינתה שם לא מתומללת שוב.
- הרצה שנעצרה ממשיכה מאיפה שעצרה: הקלטה שכבר יש לה תמלול גולמי מדלגים עליה.
- בדיקת אורך: משווים את אורך ההקלטה לסוף המשפט האחרון. האורך נלקח מ־ffprobe כשהוא מותקן, כי האורך
  ש־faster-whisper מחשב נקטע יחד עם הפענוח. כשהתמלול מכסה פחות מ־90%, ממירים ל־wav עם ffmpeg
  (כשהוא מותקן) ומתמללים שוב, פעם אחת. אם עדיין חסר, מודפסת אזהרה בולטת, והיא נכתבת גם בראש התמלול.

השלב הבא הוא של Claude, והוא שלב נפרד:
1. לקרוא את התמלול הגולמי, ולהחליף כל שם של אדם פרטי (לפי "מקורות/_רגיש/שמות.txt" ולפי ההקשר)
   בתיאור, כמו "הלקוחה" או "המשתתפת".
2. להריץ את מצאי.py, כדי לדעת את המספר של ההקלטה בקטלוג.
3. רק אז לשמור עותק נקי ב"30_ספרייה/תמלולים/<מספר> <שם>.md". המצאי מקשר אותו לשורה של ההקלטה.
התמלול הגולמי לא יוצא מהתיקייה הרגישה ולא עולה לגיט.
הקלטה שנמצאת בתוך "מקורות/_רגיש/" מתומללת, אבל אין לה מספר בקטלוג, והתמלול שלה נשאר רק בתיקייה הרגישה.

כש־faster-whisper לא מותקן, הכלי מדפיס מה להתקין, ויוצא בקוד 2. לפני ההתקנה שואלים את מי שעובדת עם המוח.
יוצא בקוד 1 כשתמלול של קובץ נכשל.
"""
import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.dirname(HERE)
SRC = os.path.join(BRAIN, "מקורות")
RAW_DIR = os.path.join(SRC, "_רגיש", "תמלול גולמי")
NAMES = os.path.join(SRC, "_רגיש", "שמות.txt")
MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"
MIN_COVER = 0.9
MEDIA_EXT = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".opus", ".wma", ".amr",
             ".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv", ".wmv", ".3gp"}

MISSING = """faster-whisper לא מותקן במחשב הזה, ולכן אי אפשר לתמלל.

ל־Claude: קודם שואלים את מי שעובדת עם המוח אם להתקין. אומרים לה שזה חינם, ששום דבר לא יוצא מהמחשב,
ושבפעם הראשונה יורד מודל עברי, פעם אחת, כ־1.6GB. אחרי שהיא מאשרת:

    pip install faster-whisper

אם pip לא נמצא:  python -m pip install faster-whisper    (במק: python3 -m pip install faster-whisper)
אחר כך מריצים שוב את תמלול.py. ההורדה של המודל קורית בהרצה הראשונה, ולא סוגרים את החלון עד שהיא נגמרת."""

NAME_PATS = []


def load_names():
    if os.path.exists(NAMES):
        with open(NAMES, encoding="utf-8-sig") as f:
            for n in (l.strip() for l in f):
                if n and not n.startswith("#"):
                    NAME_PATS.append(re.compile(r"(?<![א-תA-Za-z])%s(?![א-תA-Za-z])" % re.escape(n), re.I))


def mask(text):
    """שם מהרשימה הרגישה מוחלף בשלוש נקודות, לפני שמדפיסים."""
    for pat in NAME_PATS:
        text = pat.sub("…", text)
    return text


def shown(path):
    """נתיב להדפסה, יחסית למוח, בלי שמות מהרשימה הרגישה."""
    return mask(os.path.relpath(path, BRAIN).replace(os.sep, "/"))


def stamp(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_name(name):
    name = re.sub(r"[‎‏‪-‮⁦-⁩]", "", name)
    name = re.sub(r'[\\/:*?"<>|\t\r\n]', "_", name).strip(" .")
    return name[:60].strip() or "הקלטה"


def is_media(name):
    return (os.path.splitext(name)[1].lower() in MEDIA_EXT
            and not name.startswith(("~$", "._")) and name.lower() not in ("desktop.ini", "thumbs.db"))


def inside(path, folder):
    path, folder = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
    return path == folder or path.startswith(folder + os.sep)


def find_inputs(args):
    """הקבצים לתמלול. בלי ארגומנטים: כל ההקלטות והסרטונים ב"מקורות/"."""
    roots, problems = [], []
    if args:
        for a in args:
            cand = [a, os.path.join(BRAIN, a)]
            path = next((os.path.abspath(c) for c in cand if os.path.exists(c)), None)
            if path is None:
                problems.append(f"לא מצאתי את הקובץ: {mask(a)}")
            elif not inside(path, SRC):
                problems.append(f'הקובץ לא בתוך "מקורות/". קודם מעבירים אותו לשם: {mask(a)}')
            else:
                roots.append(path)
    else:
        roots = [SRC]
    files = []
    for root in roots:
        if os.path.isfile(root):
            if is_media(os.path.basename(root)):
                files.append(root)
            else:
                problems.append(f"זה לא קובץ הקלטה או סרטון: {shown(root)}")
            continue
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".")
                             and not inside(os.path.join(dirpath, d), RAW_DIR))
            files += [os.path.join(dirpath, n) for n in sorted(names) if is_media(n)]
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out, problems


def done_prefixes():
    if not os.path.isdir(RAW_DIR):
        return set()
    return {n[:8] for n in os.listdir(RAW_DIR) if n.endswith(".md") and re.match(r"^[0-9a-f]{8} ", n)}


def probe_duration(path):
    """האורך לפי ffprobe, בשניות. None כש־ffprobe לא מותקן או לא הצליח."""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=noprint_wrappers=1:nokey=1", path],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        return float(out) if out and out != "N/A" else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def to_wav(path, folder):
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    out = os.path.join(folder, "audio.wav")
    try:
        subprocess.run([exe, "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", out],
                       capture_output=True, check=True, timeout=3600)
        return out
    except (OSError, subprocess.SubprocessError):
        return None


def transcribe(model, path):
    segments, info = model.transcribe(path, language="he", beam_size=2, vad_filter=True)
    lines, last_end = [], 0.0
    for s in segments:
        text = s.text.strip()
        if text:
            lines.append(f"[{stamp(s.start)}] {text}")
        last_end = max(last_end, float(s.end))
    return lines, float(info.duration or 0), last_end


def main():
    ap = argparse.ArgumentParser(description="תמלול במחשב, לתיקייה הרגישה")
    ap.add_argument("files", nargs="*", help='קבצים או תיקיות בתוך "מקורות/"')
    ap.add_argument("--dry-run", action="store_true", help="רק להראות מה יתומלל")
    ap.add_argument("--model", default=MODEL, help="מודל אחר של faster-whisper")
    args = ap.parse_args()
    load_names()

    if not os.path.isdir(SRC):
        print('אין במוח הזה תיקייה בשם "מקורות". ההקלטות צריכות להיות שם.')
        sys.exit(1)
    files, problems = find_inputs(args.files)
    for p in problems:
        print("בעיה: " + p)
    done = done_prefixes()
    todo = []
    for f in files:
        h = md5_of(f)
        if h[:8] in done:
            continue
        todo.append((f, h))
    skipped = len(files) - len(todo)

    installed = importlib.util.find_spec("faster_whisper") is not None
    if args.dry_run:
        total = 0.0
        for f, _h in todo:
            d = probe_duration(f)
            total += d or 0
            print(f"  יתומלל: {shown(f)}" + (f" ({stamp(d)})" if d else ""))
        print(f"מחכים לתמלול: {len(todo)}. כבר יש תמלול: {skipped}."
              + (f" אורך כולל: {stamp(total)}." if total else ""))
        print("faster-whisper: " + ("מותקן." if installed else "לא מותקן. ההרצה האמיתית תסביר מה להתקין."))
        sys.exit(1 if problems else 0)

    if not todo:
        print(f"אין מה לתמלל. כבר יש תמלול: {skipped}.")
        sys.exit(1 if problems else 0)
    if not installed:
        print(MISSING)
        sys.exit(2)

    from faster_whisper import WhisperModel
    try:
        model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    except Exception as e:  # noqa: BLE001 - בדרך כלל הורדה שנכשלה
        print(f"המודל לא נטען ({type(e).__name__}). בפעם הראשונה הוא יורד מ־huggingface.co, כ־1.6GB. "
              "אם האינטרנט מסונן או שאין חיבור, צריך חיבור פתוח להורדה הראשונה.")
        sys.exit(1)

    os.makedirs(RAW_DIR, exist_ok=True)
    failed = 0
    for n, (path, h) in enumerate(todo, 1):
        name = f"{h[:8]} {clean_name(os.path.splitext(os.path.basename(path))[0])}"
        dst = os.path.join(RAW_DIR, name + ".md")
        reference = probe_duration(path)
        print(f"[{n}/{len(todo)}] מתמללת: {shown(path)}" + (f" ({stamp(reference)})" if reference else ""),
              flush=True)
        t0 = time.time()
        try:
            lines, decoded, last_end = transcribe(model, path)
            length = max(reference or 0, decoded)
            cover = last_end / length if length else 1.0
            retried = False
            if cover < MIN_COVER:
                with tempfile.TemporaryDirectory() as tmp:
                    wav = to_wav(path, tmp)
                    if wav:
                        retried = True
                        print(f"  התמלול הגיע רק עד {stamp(last_end)} מתוך {stamp(length)}. "
                              "ממירה ל־wav ומתמללת שוב.", flush=True)
                        lines2, decoded2, last2 = transcribe(model, wav)
                        length = max(length, decoded2)
                        if last2 > last_end:
                            lines, last_end = lines2, last2
                cover = last_end / length if length else 1.0
        except Exception as e:  # noqa: BLE001 - קובץ בלי פס קול לא עוצר את התור
            failed += 1
            print(f"  ✗ התמלול נכשל ({type(e).__name__}). אולי אין בקובץ פס קול. לא נכתב תמלול.", flush=True)
            continue

        warning = ""
        if cover < MIN_COVER:
            why = "גם אחרי המרה ל־wav" if retried else "ו־ffmpeg לא מותקן, ולכן לא היה ניסיון שני"
            warning = (f"התמלול מכסה רק {round(cover * 100)}% מההקלטה (עד {stamp(last_end)} מתוך {stamp(length)}), "
                       f"{why}. אולי בסוף יש שקט או מוזיקה. אם לא, התמלול נקטע, ואסור לסמוך עליו כשלם.")
        head = [f"# תמלול גולמי: {os.path.splitext(os.path.basename(path))[0]}", "",
                f"**הקובץ:** {os.path.relpath(path, BRAIN).replace(os.sep, '/')}",
                f"**md5:** {h}",
                f"**אורך ההקלטה:** {stamp(length)}" + ("" if reference else " (לפי הפענוח: ffprobe לא מותקן)"),
                f"**התמלול מגיע עד:** {stamp(last_end)}",
                f"**מודל:** {args.model}",
                "**נבדק לשמות:** לא. זה תמלול גולמי. הוא נשאר כאן עד ש־Claude מחליף בו שמות של אנשים פרטיים, "
                "ורק אז נשמר עותק נקי ב־30_ספרייה/תמלולים/."]
        if warning:
            head.append(f"**אזהרה:** {warning}")
        tmp = dst + ".part"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(head + ["", "---", ""] + lines) + "\n")
        os.replace(tmp, dst)
        minutes = (time.time() - t0) / 60
        print(f"  ✓ נכתב תמלול גולמי עד {stamp(last_end)}, תוך {minutes:.1f} דקות.", flush=True)
        if warning:
            print("  " + "!" * 60)
            print("  אזהרה: " + warning)
            print("  " + "!" * 60, flush=True)

    print(f"סיום: {len(todo) - failed} תמלולים חדשים ב־מקורות/_רגיש/תמלול גולמי/. נכשלו: {failed}. "
          f"כבר היו: {skipped}.")
    print("השלב הבא (Claude): לבדוק כל תמלול גולמי לשמות של אנשים פרטיים, להריץ את מצאי.py, "
          "ורק אז לשמור עותק נקי ב־30_ספרייה/תמלולים/<מספר> <שם>.md.")
    sys.exit(1 if failed or problems else 0)


if __name__ == "__main__":
    main()
