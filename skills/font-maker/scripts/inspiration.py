# -*- coding: utf-8 -*-
"""Inspiration page for mode B: the student's own word in well-known Hebrew
fonts, grouped by style, each with a number she can pick.

    python inspiration.py "<out.html>" --word "סטודיו שירה" [--styles rounded,clean,serif,calligraphic,display]

Google Fonts families load from fonts.googleapis.com (allowed in NetFree);
Windows fonts are used only if they are on this computer. A card whose font
did not load says so. Every family below has a Hebrew character set.
"""
import argparse
import html
import json
from pathlib import Path

import fm_core as core

STYLES = {
    "rounded": ("עגול ורך", "פינות עגולות, מראה ידידותי", [
        ("Varela Round", "google", "עגול ונקי, עובי אחיד"),
        ("Fredoka", "google", "עגול ושמנמן, שמח"),
        ("Rubik", "google", "פינות מעוגלות קלות, מודרני"),
    ]),
    "clean": ("נקי וגיאומטרי", "קווים ישרים, בלי קישוטים", [
        ("Heebo", "google", "פשוט וברור, מתאים לכל דבר"),
        ("Assistant", "google", "צר ואלגנטי"),
        ("IBM Plex Sans Hebrew", "google", "טכני ומדויק"),
        ("Alef", "google", "עגלגל ופתוח"),
        ("Miriam Libre", "google", "קלאסי-מודרני, שקט"),
        ("Gisha", "local", "של ווינדוס: נקי ורחב"),
    ]),
    "serif": ("קלאסי עם סריפים", "קצוות מעוטרים, כמו בספר", [
        ("Frank Ruhl Libre", "google", "ספרותי, ניגוד עדין"),
        ("David Libre", "google", "דוד הקלאסי"),
        ("Noto Serif Hebrew", "google", "שמרני ומאוזן"),
        ("Bellefair", "google", "דק ויוקרתי"),
        ("Narkisim", "local", "של ווינדוס: נרקיסים"),
        ("FrankRuehl", "local", "של ווינדוס: פרנק-ריהל"),
    ]),
    "calligraphic": ("קליגרפי וכתב יד", "כאילו נכתב בעט", [
        ("Solitreo", "google", "כתב יד עתיק, זורם"),
        ("Noto Rashi Hebrew", "google", "כתב רש\"י, עט רחב"),
        ("Gveret Levin", "google", "כתב יד שמח"),
        ("Playpen Sans Hebrew", "google", "כתב יד עגול וקריא"),
        ("Amatic SC", "google", "צר, מצויר ביד"),
    ]),
    "display": ("רטרו וכותרות", "חזק ובולט, לכותרות ולוגו", [
        ("Secular One", "google", "עבה ועגלגל"),
        ("Suez One", "google", "עבה עם סריפים, רטרו"),
        ("Karantina", "google", "צר מאוד וגבוה"),
        ("Aharoni", "local", "של ווינדוס: אהרוני, עבה"),
        ("Levenim MT", "local", "של ווינדוס: לבנים"),
    ]),
}


def main():
    core.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--word", required=True)
    ap.add_argument("--styles", default=",".join(STYLES))
    a = ap.parse_args()
    word = html.escape(a.word)
    keys = [k.strip() for k in a.styles.split(",") if k.strip() in STYLES]
    links, sections, numbered = [], [], []
    n = 0
    for key in keys:
        title, sub, fonts = STYLES[key]
        cards = []
        for fam, src, desc in fonts:
            n += 1
            numbered.append({"n": n, "family": fam, "source": src, "style": key})
            if src == "google":
                links.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family='
                             f'{fam.replace(" ", "+")}&amp;display=swap">')
            cards.append(
                f'<article class="card" data-font="{fam}"><span class="num">{n}</span>'
                f'<p class="word" style="font-family:\'{fam}\',serif">{word}</p>'
                f'<p class="abc" style="font-family:\'{fam}\',serif">אבגדהוזחטיכלמנסעפצקרשת 123</p>'
                f'<p class="meta"><bdi>{fam}</bdi> · {desc}</p><p class="miss" hidden>הפונט לא נטען כאן'
                f'{" (אין חיבור לאינטרנט?)" if src == "google" else " (לא מותקן במחשב הזה)"}, ומה שמוצג הוא פונט רגיל.</p></article>')
        sections.append(f'<section><h2>{title}</h2><p class="sub">{sub}</p><div class="grid">{"".join(cards)}</div></section>')
    page = f"""<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>השראה · {word}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{"".join(links)}
<style>
:root{{--bg:#f7f4ee;--card:#fff;--ink:#1d2a3a;--muted:#5d6672;--line:#e3ddd2;--accent:#b4532a}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 "Segoe UI",Arial,sans-serif}}
main{{max-inline-size:1150px;margin-inline:auto;padding:28px 20px 60px}} h1{{margin:0 0 4px;font-size:28px}}
h2{{margin:34px 0 0;font-size:21px}} .sub{{margin:0 0 12px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 18px 10px;position:relative}}
.num{{position:absolute;inset-inline-end:12px;inset-block-start:10px;background:var(--accent);color:#fff;border-radius:50%;inline-size:30px;block-size:30px;display:grid;place-items:center;font-weight:700}}
.word{{font-size:54px;line-height:1.35;margin:6px 0 0;overflow-wrap:anywhere}} .abc{{font-size:20px;margin:0;color:#333}}
.meta{{font-size:14px;color:var(--muted);margin:6px 0 0}} .miss{{font-size:13px;color:#b00020;margin:4px 0 0}}
</style></head><body><main>
<h1>איזה סגנון את אוהבת?</h1>
<p class="sub">המילה שלך בפונטים מוכרים. בחרי מספר אחד או שניים, ואמרי מה אהבת בהם (עגול? צר? עבה? הקצוות?). הפונט שלך יהיה חדש, רק בהשראתם.</p>
{"".join(sections)}
</main>
<script>
function check(){{const c=document.createElement('canvas').getContext('2d');const t='אבגדה שלום 123';
document.querySelectorAll('.card').forEach(el=>{{const f=el.dataset.font;let same=true;
for(const fb of ['monospace','serif']){{c.font='40px '+fb;const a=c.measureText(t).width;c.font='40px "'+f+'",'+fb;const b=c.measureText(t).width;if(Math.abs(a-b)>0.5)same=false;}}
if(same)el.querySelector('.miss').hidden=false;}});}}
document.fonts.ready.then(()=>setTimeout(check,1200));
</script></body></html>"""
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    (out.with_suffix(".json")).write_text(json.dumps(numbered, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"PAGE {out}")
    print("FONTS " + "  ".join(f"{f['n']}={f['family']}" for f in numbered))


if __name__ == "__main__":
    main()
