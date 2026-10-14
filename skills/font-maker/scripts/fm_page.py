# -*- coding: utf-8 -*-
"""The test page (index.html): self-contained, Hebrew, RTL."""
import base64
import html
import io
import json
from pathlib import Path

import fm_core as core

FINAL_WORDS = ["מלך", "שלום", "גן", "כסף", "ארץ"]
PARAGRAPH = ("כתיבה ביד היא דרך אישית לומר תודה. כל אות נושאת את הקצב של היד שכתבה אותה, "
             "ובכל מילה יש משהו מהאדם. עם הפונט הזה אפשר לכתוב הזמנות, ברכות וכותרות, "
             "ולשמור על החום של כתב היד גם על המסך ובדפוס.")
WEIGHT_HE = {"Light": "דק", "Regular": "רגיל", "Bold": "עבה"}
CSS_WEIGHT = core.WEIGHT_CLASS


def _crop_uri(img_path, box):
    from PIL import Image
    im = Image.open(img_path).convert("RGB").crop(tuple(int(v) for v in box))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), im.size


def _compare_section(folder, design):
    cpath = folder / "compare.json"
    if not cpath.exists():
        return ""
    try:
        comp = json.loads(cpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"WARN compare.json is not valid JSON (line {e.lineno}) - comparison skipped")
        return ""
    rows = []
    if comp.get("strips"):
        scan = folder / comp.get("scan", design.get("scan", ""))
        if not scan.exists():
            print(f"WARN scan not found for comparison: {scan}")
            return ""
        for s in comp["strips"]:
            uri, (w, h) = _crop_uri(scan, s["box"])
            t = html.escape(s["text"])
            rows.append(
                f'<figure class="strip"><img src="{uri}" alt="המקור: {t}" width="{2 * w}" height="{2 * h}">'
                f'<p class="sample matched" lang="he">{t}</p><figcaption>למעלה: המקור. למטה: הפונט.</figcaption></figure>')
        intro = "כל שורה מהדף המקורי, ומתחתיה אותן מילים בפונט החדש, באותו גודל."
    elif comp.get("inspiration"):
        fams = comp["inspiration"]
        words = comp.get("words") or [design["name"]]
        links = "".join(
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={f["family"].replace(" ", "+")}&display=swap">'
            for f in fams if f.get("google", True))
        for f in fams:
            fam = html.escape(f["family"])
            for wd in words:
                t = html.escape(wd)
                rows.append(
                    f'<figure class="strip insp"><p class="sample ref" style="font-family:\'{fam}\'" data-font="{fam}">{t}</p>'
                    f'<p class="sample">{t}</p><figcaption>למעלה: <bdi>{fam}</bdi> (ההשראה). למטה: הפונט החדש.'
                    f' <span class="netnote" hidden>הפונט להשוואה לא נטען (אין חיבור לרשת?) ומוצג בפונט רגיל.</span></figcaption></figure>')
        intro = "הפונט שבחרת כהשראה, ומתחתיו הפונט החדש. הצורות חדשות, רק הרוח דומה."
        rows.insert(0, links)
    else:
        return ""
    return (f'<section aria-labelledby="h-comp"><h2 id="h-comp">השוואה</h2><p class="note">{intro}</p>'
            + "".join(rows) + "</section>")


def make_page(folder, design, results, chars):
    folder = Path(folder)
    name = html.escape(design["name"])
    faces, radios = [], []
    for i, (w, path) in enumerate(results):
        src = path.with_suffix(".woff2") if path.with_suffix(".woff2").exists() else path
        fmt = "woff2" if src.suffix == ".woff2" else "truetype"
        data = base64.b64encode(src.read_bytes()).decode()
        cw = CSS_WEIGHT.get(w, 400)
        faces.append(f"@font-face{{font-family:'TestFont';src:url(data:font/{'woff2' if fmt == 'woff2' else 'ttf'};base64,{data}) format('{fmt}');"
                     f"font-weight:{cw};font-style:normal}}")
        checked = " checked" if w == "Regular" or len(results) == 1 else ""
        radios.append(f'<label class="chip"><input type="radio" name="weight" value="{cw}"{checked}>'
                      f'{WEIGHT_HE.get(w, w)}</label>')
    glyphs = design["glyphs"]
    handwriting = design.get("mode", "handwriting") == "handwriting"
    cells = []
    for c in core.HEBREW:
        if c not in chars:
            cells.append(f'<div class="cell missing"><span class="letter">{c}</span><span class="tag">חסרה</span></div>')
            continue
        cls = ["cell"]
        tags = []
        if c in core.FINALS:
            cls.append("final")
            tags.append("סופית")
        if glyphs.get(c, {}).get("designed") and handwriting:
            cls.append("designed")
            tags.append("עוצבה")
        tag = f'<span class="tag">{" · ".join(tags)}</span>' if tags else ""
        cells.append(f'<div class="{" ".join(cls)}"><span class="letter sample">{c}</span>{tag}</div>')
    digits = "".join(c for c in core.DIGITS if c in chars)
    punct = " ".join(html.escape(c) for c in chars if not c.isalnum() and c != " ")
    has_latin = any(c in chars for c in core.LATIN_LOWER)
    latin = ""
    if has_latin:
        latin = ('<section aria-labelledby="h-en"><h2 id="h-en">אנגלית</h2><div class="card">'
                 '<p class="sample" dir="ltr" lang="en">ABCDEFGHIJKLMNOPQRSTUVWXYZ</p>'
                 '<p class="sample" dir="ltr" lang="en">abcdefghijklmnopqrstuvwxyz</p>'
                 '<p class="sample" dir="ltr" lang="en">Hello! Written with love, 2026.</p></div></section>')
    weights_rows = "".join(
        f'<div class="wrow"><span class="wlabel">{WEIGHT_HE.get(w, w)}</span>'
        f'<p class="sample" style="font-weight:{CSS_WEIGHT.get(w, 400)}">תודה מכל הלב, שנה טובה</p></div>'
        for w, _ in results)
    downloads = " ".join(f'<a href="fonts/{html.escape(p.name)}" download><bdi>{html.escape(p.name)}</bdi></a>'
                         for _, p in results)
    supported = json.dumps([ord(c) for c in chars] + [10, 0xA0])
    menu_name = html.escape(design["name"])
    latin_name = html.escape(core.latin_name(design))
    light_note = ""
    if any(w == "Light" for w, _ in results):
        light_note = f"<li>המשקל הדק מופיע ברשימה בשם נפרד: <b>{menu_name} Light</b>.</li>"
    page = TEMPLATE.format(
        title=name, name=name, faces="".join(faces), radios="".join(radios),
        compare=_compare_section(folder, design), cells="".join(cells),
        finals=" ".join(FINAL_WORDS), digits=digits, punct=punct, latin=latin,
        paragraph=PARAGRAPH, weights=weights_rows, downloads=downloads, supported=supported,
        menu_name=menu_name, latin_name=latin_name, light_note=light_note,
        abc_note=("האותיות הסופיות מסומנות בכתום. \"עוצבה\" = האות לא הופיעה בדף המקורי ועוצבה באותו סגנון."
                  if handwriting else "האותיות הסופיות מסומנות בכתום."),
        scale=1000.0 / design["scale"] if design["frame"] == "scan" else 0)
    out = folder / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


TEMPLATE = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · דף בדיקה</title>
<style>
{faces}
:root{{--bg:#f7f4ee;--card:#fff;--ink:#1d2a3a;--muted:#5d6672;--line:#e3ddd2;--accent:#b4532a;--final:#fff1e6;--w:400}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 "Segoe UI",Arial,sans-serif}}
main{{max-inline-size:1100px;margin-inline:auto;padding:28px 20px 60px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:36px 0 10px}}
.note{{color:var(--muted);margin:4px 0 14px}}
.sample{{font-family:'TestFont',sans-serif;font-weight:var(--w);font-synthesis:none;font-kerning:normal;margin:0;line-height:1.5;font-size:48px;overflow-wrap:anywhere}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 24px;margin-block:10px}}
main.dark .card,main.dark .strip,main.dark .cell,main.dark #live{{background:#1e2530;color:#f3efe6;border-color:#38404c}}
.controls{{display:flex;flex-wrap:wrap;gap:18px;align-items:center;margin-block:10px}}
.chip{{display:inline-flex;gap:6px;align-items:center;border:1px solid var(--line);border-radius:20px;padding:6px 14px;background:#fff;cursor:pointer;min-block-size:40px}}
textarea{{inline-size:100%;min-block-size:80px;font:18px/1.5 "Segoe UI",Arial;padding:10px;border:1px solid #c9c2b5;border-radius:8px}}
#live{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 22px;min-block-size:120px;white-space:pre-wrap}}
.miss{{font-family:Arial;color:#b00020;background:#ffe3e3}}
button{{font:inherit;min-block-size:40px;border:1px solid #c9c2b5;border-radius:8px;background:#fff;padding-inline:14px;cursor:pointer}}
.strip{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 20px;margin:0 0 12px}}
.strip img{{display:block;max-inline-size:100%;block-size:auto;margin-inline-start:0}}
.strip .matched{{line-height:1.25}}
.strip figcaption{{font-size:13px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:8px}}
.cell{{background:var(--card);border:1px solid var(--line);border-radius:10px;text-align:center;padding:4px 2px 6px;position:relative}}
.cell .letter{{display:block;font-size:64px;line-height:1.6}}
.cell .tag{{display:block;font-size:12px;color:var(--accent)}}
.cell.final{{background:var(--final);border-color:#f0c9a8}}
.cell.missing .letter{{font-family:Arial;color:#bbb}}
.wrow{{display:flex;gap:18px;align-items:baseline;border-block-end:1px solid var(--line);padding-block:6px}}
.wlabel{{min-inline-size:48px;color:var(--muted)}}
.install{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
.install ol{{padding-inline-start:22px;margin:6px 0}}
a{{color:#1d5fa0}}
:focus-visible{{outline:3px solid #2f6db3;outline-offset:3px}}
@media (max-width:600px){{.sample{{font-size:36px}}.cell .letter{{font-size:44px}}}}
</style>
</head>
<body>
<main id="main">
<h1>{name}</h1>
<p class="note">דף בדיקה לפונט. כותבים, משווים, ומחליטים מה לתקן. הורדה: {downloads}</p>

<section aria-labelledby="h-try"><h2 id="h-try">נסי בעצמך</h2>
<label for="try">מה לכתוב?</label>
<textarea id="try">תודה מכל הלב
שנה טובה ומתוקה</textarea>
<div class="controls">
<fieldset class="chip" style="border:none;padding:0;background:none"><legend class="note" style="margin:0">עובי</legend>{radios}</fieldset>
<label>גודל <input id="size" type="range" min="18" max="140" value="56" aria-label="גודל האותיות"></label>
<button id="dark" type="button" aria-pressed="false">רקע כהה</button>
</div>
<p id="live" class="sample" aria-live="polite"></p>
<p id="missing" class="note" role="status"></p>
</section>

{compare}

<section aria-labelledby="h-abc"><h2 id="h-abc">כל האותיות</h2>
<p class="note">{abc_note}</p>
<div class="grid">{cells}</div>
<div class="card"><p class="sample">{finals}</p></div>
</section>

<section aria-labelledby="h-num"><h2 id="h-num">ספרות וסימנים</h2><div class="card">
<p class="sample" dir="ltr">{digits}</p>
<p class="sample">{punct}</p>
<p class="sample">מחיר: <bdi>1,250.50</bdi> ₪ (הנחה <bdi>15%</bdi>), בתאריך <bdi>04/10/2026</bdi></p>
</div></section>

{latin}

<section aria-labelledby="h-par"><h2 id="h-par">פסקה</h2><div class="card">
<p class="sample" style="font-size:30px;line-height:1.7">{paragraph}</p></div></section>

<section aria-labelledby="h-w"><h2 id="h-w">כל העוביים</h2><div class="card">{weights}</div></section>

<section aria-labelledby="h-inst"><h2 id="h-inst">איך מתקינים</h2><div class="install">
<div class="card"><h3>ווינדוס</h3><ol>
<li>פותחים את קובץ ה-ZIP: לחיצה ימנית, "חלץ הכל".</li>
<li>לחיצה ימנית על כל קובץ שמסתיים ב-<bdi>.ttf</bdi>, ואז "התקן". אם לא רואים "התקן", בוחרים קודם "הצג אפשרויות נוספות". לא צריך הרשאות מנהל.</li>
<li>סוגרים ופותחים מחדש את וורד, פוטושופ או קנבה בדסקטופ.</li>
<li>הפונט מופיע ברשימה בשם <b>{menu_name}</b> (או <bdi>{latin_name}</bdi>).</li>{light_note}
</ol></div>
<div class="card"><h3>מק</h3><ol>
<li>לחיצה כפולה על קובץ ה-ZIP כדי לפתוח אותו.</li>
<li>לחיצה כפולה על כל קובץ <bdi>.ttf</bdi>, ואז "התקן גופן" (<bdi>Install Font</bdi>).</li>
<li>סוגרים ופותחים מחדש את התוכנה.</li>
</ol></div>
</div></section>
</main>
<script>
const supported=new Set({supported});
const main=document.getElementById('main'),txt=document.getElementById('try'),live=document.getElementById('live'),miss=document.getElementById('missing'),size=document.getElementById('size');
function render(){{live.replaceChildren();let run='';const bad=new Set();const flush=()=>{{if(run){{live.append(document.createTextNode(run));run='';}}}};
for(const c of txt.value){{if(supported.has(c.codePointAt(0))||c===' '){{run+=c;}}else{{flush();const s=document.createElement('span');s.className='miss';s.textContent=c;live.append(s);bad.add(c);}}}}
flush();live.style.fontSize=size.value+'px';miss.textContent=bad.size?'אין בפונט: '+[...bad].join(' '):'';}}
txt.addEventListener('input',render);size.addEventListener('input',render);
document.querySelectorAll('input[name=weight]').forEach(r=>r.addEventListener('change',()=>main.style.setProperty('--w',r.value)));
const checked=document.querySelector('input[name=weight]:checked');if(checked)main.style.setProperty('--w',checked.value);
document.getElementById('dark').addEventListener('click',e=>{{const on=main.classList.toggle('dark');e.currentTarget.setAttribute('aria-pressed',String(on));}});
const unitsPerPx={scale};
function fit(){{document.querySelectorAll('.strip img').forEach(img=>{{const p=img.parentElement.querySelector('.matched');if(!p||!unitsPerPx||!img.naturalHeight)return;p.style.fontSize=(unitsPerPx*img.clientHeight/img.naturalHeight)+'px';}});}}
window.addEventListener('load',fit);window.addEventListener('resize',fit);
function match(){{const c=document.createElement('canvas').getContext('2d');document.querySelectorAll('.strip.insp').forEach(fig=>{{const ref=fig.querySelector('.ref'),mine=fig.querySelector('.ref + .sample');if(!ref||!mine)return;
const h=f=>{{c.font='100px '+f;const m=c.measureText('ה');return m.actualBoundingBoxAscent;}};const a=h('"'+ref.dataset.font+'"'),b=h('TestFont');if(a>0&&b>0)mine.style.fontSize=(48*a/b)+'px';}});}}
function netcheck(){{const c=document.createElement('canvas').getContext('2d');document.querySelectorAll('.ref').forEach(el=>{{const f=el.dataset.font;c.font='40px monospace';const a=c.measureText('אבגדה abc').width;c.font='40px "'+f+'",monospace';const b=c.measureText('אבגדה abc').width;if(Math.abs(a-b)<0.5){{const n=el.parentElement.querySelector('.netnote');if(n)n.hidden=false;}}}});}}
document.fonts.ready.then(()=>{{render();fit();setTimeout(()=>{{netcheck();match();}},1500);}});
</script>
</body>
</html>
"""
