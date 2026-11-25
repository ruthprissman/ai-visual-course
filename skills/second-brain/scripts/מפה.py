# -*- coding: utf-8 -*-
"""מפת המוח: כרטיס לכל חלק במוח, הקשרים ביניהם, והתוכן המלא בלחיצה.

לא מריצים אותו לבד. הלוח (לוח.py) קורא לו ומכניס את המפה ללשונית "מפת המוח".

החלקים שהמפה מכירה (חלק שאין לו קובץ או תיקייה במוח הזה פשוט לא מופיע):
- תחומי הכללים, מתוך "00_ליבה/הכללים.md";
- שאר הקבצים בליבה, למשל "על_העסק.md" ו"הקול.md";
- כרטיסי סוגי התוצרים ב"15_תוצרים", כרטיסי הידע ב"10_ידע" וכרטיסי המוצרים ב"20_מוצרים";
- כרטיסי העבודות ב"50_עבודות";
- השאלות הפתוחות, לפי נושא, מתוך "שאלות_פתוחות.md";
- היומן.

הקשרים נבנים מהטקסט עצמו: מספר של כלל, שם של כרטיס אחר, והשורה "תוצר:" בכרטיס עבודה.
"""
import html
import json
import os
import re

BRAIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(BRAIN, "00_ליבה")
RULES_NAME = "הכללים.md"

# (מזהה הקבוצה, התיקייה, התווית הקצרה בחלון הקריאה)
CARD_FOLDERS = [
    ("products", "15_תוצרים", "תוצרים"),
    ("knowledge", "10_ידע", "ידע"),
    ("offerings", "20_מוצרים", "מוצרים"),
]

RULE_ID = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(?![\d])(?!\.\d)")


def esc(text):
    return html.escape(text, quote=False)


def attr(text):
    return html.escape(text, quote=True)


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def md_files(folder):
    path = folder if os.path.isabs(folder) else os.path.join(BRAIN, folder)
    if not os.path.isdir(path):
        return []
    return [os.path.join(path, n) for n in sorted(os.listdir(path))
            if n.endswith(".md") and not n.startswith("_") and os.path.isfile(os.path.join(path, n))]


def first_date(text):
    m = re.search(r"\*\*עודכן:\*\*\s*(\d{1,2}\.\d{1,2}(?:\.\d{4})?)", text)
    return m.group(1) if m else ""


def field(text, name):
    m = re.search(r"^\*\*%s:\*\*\s*(.+)$" % re.escape(name), text, re.M)
    return m.group(1).strip() if m else ""


def count(n, one, many):
    """"כלל אחד", "3 כללים". המספר נעטף ב־bdi בשלב האחרון."""
    return one if n == 1 else f"{n} {many}"


# ---------- כיוון הטקסט: מספרים ואותיות לטיניות בתוך עברית ----------

LATIN = r"[A-Za-z][A-Za-z0-9.@_+#&'/\-]*(?:(?: | & | [-–] )[A-Za-z0-9][A-Za-z0-9.@_+#&'/\-]*)*"
NUMBER = r"\d(?:[\d.,:/\-–]*\d)?%?"
RUN = re.compile(r"(?<![A-Za-z0-9])(?:%s|%s)" % (LATIN, NUMBER))
TRAIL = ".,:;'/-&#+@_"
NO_BDI = {"bdi", "code", "pre", "script", "style", "textarea"}


def _wrap_runs(text):
    raw = html.unescape(text)
    out, last = [], 0
    for m in RUN.finditer(raw):
        start, end = m.start(), m.end()
        while end > start and raw[end - 1] in TRAIL:
            end -= 1
        if end <= start:
            continue
        out.append(esc(raw[last:start]))
        out.append("<bdi>" + esc(raw[start:end]) + "</bdi>")
        last = end
    out.append(esc(raw[last:]))
    return "".join(out)


def bdi_html(fragment):
    """עוטף ב־<bdi> מספרים, תאריכים ומילים בלטינית, רק בטקסט שבין התגיות.
    לא נוגע בתוך תגית (מזהים, data-*), ולא בתוך bdi, code או pre שכבר קיימים."""
    out, skip = [], []
    for part in re.split(r"(<[^>]+>)", fragment):
        if part.startswith("<"):
            m = re.match(r"^<(/?)([a-zA-Z0-9]+)", part)
            if m:
                name = m.group(2).lower()
                if name in NO_BDI:
                    if m.group(1):
                        if name in skip:
                            skip.remove(name)
                    elif not part.endswith("/>"):
                        skip.append(name)
            out.append(part)
        elif skip or not part:
            out.append(part)
        else:
            out.append(_wrap_runs(part))
    return "".join(out)


# ---------- מארקדאון לתצוגה ----------

class Ctx:
    def __init__(self, rule_ids, domains):
        self.rule_ids = rule_ids      # {"1.4": "d1"}
        self.domains = domains        # {"1": "d1"}
        self.titles = []              # [(שם הכרטיס, מזהה)], מהארוך לקצר
        self.current = None           # הכרטיס שמוצג עכשיו: לא מקשרים אותו לעצמו
        self.mentioned = set()        # הכרטיסים שהטקסט של הכרטיס הנוכחי מזכיר


def link_titles(text, ctx):
    """שם של כרטיס אחר בתוך הטקסט הופך לקישור. לא נוגעים בתוך תגיות או בתוך קישור קיים."""
    names = [(t, cid) for t, cid in ctx.titles if cid != ctx.current]
    if not names:
        return text
    pattern = re.compile("|".join(re.escape(esc(t)) for t, _ in names))
    lookup = {esc(t): cid for t, cid in names}
    out, in_a = [], 0
    for part in re.split(r"(<[^>]+>)", text):
        if part.startswith("<"):
            if part.startswith("<a "):
                in_a += 1
            elif part == "</a>":
                in_a = max(0, in_a - 1)
            out.append(part)
            continue
        if in_a:
            out.append(part)
            continue

        def repl(m):
            cid = lookup[m.group(0)]
            ctx.mentioned.add(cid)
            return f'<a href="#" class="ref" data-card="{cid}">{m.group(0)}</a>'
        out.append(pattern.sub(repl, part))
    return "".join(out)


def link_refs(text, ctx):
    """מספר כלל אחרי "כלל" או בסוגריים עגולים הופך לקישור. בתוך מקור [..] לא נוגעים: שם יש תאריכים."""
    out, last = [], 0
    for m in RULE_ID.finditer(text):
        rid = f"{int(m.group(1))}.{int(m.group(2))}"
        if rid not in ctx.rule_ids:
            continue
        before = text[:m.start()]
        if before.count("[") > before.count("]"):
            continue
        near = before[-30:]
        if not (re.search(r"כלל", near) or re.search(r"\(\s*$", near) or re.search(r"\(\s*\d{1,2}\.\d{1,2}[^)]*$", near)):
            continue
        if re.search(r"[במ]־$", before[-2:]):
            continue
        out.append(text[last:m.start()])
        dom = ctx.rule_ids[rid]
        out.append(f'<a href="#" class="ref" data-card="{dom}" data-anchor="r-{rid.replace(".", "-")}">'
                   f'<bdi>{m.group(0)}</bdi></a>')
        last = m.end()
    out.append(text[last:])
    text = "".join(out)
    # טווח כללים ("1.5–1.6") נשאר בסדר הנכון בתוך טקסט עברי
    text = re.sub(r"(<a href=\"#\" class=\"ref\"[^>]*>.*?</a>)–(<a href=\"#\" class=\"ref\"[^>]*>.*?</a>)",
                  r'<bdi dir="ltr">\1–\2</bdi>', text)

    # "תחום 2" מוביל לכרטיס התחום
    def domain_link(m):
        card = ctx.domains.get(m.group(2))
        if not card:
            return m.group(0)
        return f'{m.group(1)}<a href="#" class="ref" data-card="{card}"><bdi>{m.group(2)}</bdi></a>'
    return re.sub(r"(תחום\s+)(\d{1,2})(?![\d.])", domain_link, text)


def inline(md, ctx):
    text = esc(md)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return link_titles(link_refs(text, ctx), ctx)


def md_to_html(md, ctx, skip_title=True):
    lines = md.splitlines()
    out, para, stack = [], [], []
    in_code = False
    table = []

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para), ctx) + "</p>")
            para.clear()

    def close_lists():
        while stack:
            out.append(f"</li></{stack.pop()[0]}>")

    def flush_table():
        if not table:
            return
        rows = [r for r in table if not re.match(r"^\|[\s:|-]+\|$", r.strip())]
        out.append('<div class="tablewrap"><table>')
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            tag = "th" if i == 0 else "td"
            out.append("<tr>" + "".join(f"<{tag}>{inline(c, ctx)}</{tag}>" for c in cells) + "</tr>")
        out.append("</table></div>")
        table.clear()

    for idx, line in enumerate(lines):
        if line.strip().startswith("```"):
            flush_para(); close_lists(); flush_table()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(esc(line))
            continue
        if line.strip().startswith("<!--"):
            continue
        if line.strip().startswith("|"):
            flush_para(); close_lists()
            table.append(line)
            continue
        flush_table()
        h = re.match(r"^(#{1,4})\s+(.*)$", line)
        if h:
            flush_para(); close_lists()
            if skip_title and len(h.group(1)) == 1 and idx < 3:
                continue
            level = min(len(h.group(1)) + 1, 5)
            out.append(f"<h{level}>{inline(h.group(2), ctx)}</h{level}>")
            continue
        if line.strip() == "---":
            flush_para(); close_lists()
            out.append("<hr>")
            continue
        item = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if item:
            flush_para()
            indent = len(item.group(1))
            tag = "ol" if item.group(2)[0].isdigit() else "ul"
            content = item.group(3)
            rid = re.match(r"^(?:~~)?\*\*(?:★\s*)?(\d+\.\d+)", content)
            anchor = f' id="r-{rid.group(1).replace(".", "-")}"' if rid else ""
            if not stack or indent > stack[-1][1]:
                out.append(f"<{tag}>")
                stack.append([tag, indent])
            else:
                while len(stack) > 1 and indent < stack[-1][1]:
                    out.append(f"</li></{stack.pop()[0]}>")
                out.append("</li>")
            out.append(f"<li{anchor}>{inline(content, ctx)}")
            continue
        if not line.strip():
            flush_para()
            continue
        if stack and line.startswith("  "):
            out.append("<p>" + inline(line.strip(), ctx) + "</p>")
            continue
        close_lists()
        para.append(line.strip())
    flush_para(); close_lists(); flush_table()
    if in_code:
        out.append("</pre>")
    return bdi_html("\n".join(out))


# ---------- הכרטיסים ----------

FINALS = str.maketrans("ךםןףץ", "כמנפצ")
# מילים כלליות מדי בשם של כרטיס: הן לא יוצרות קשר
STOP = {"של", "על", "את", "עם", "שלה", "שהיא", "כתבה", "כלל", "עבוד", "שאל", "חומר", "מתוך",
        "כרטיס", "תוצר", "מוצר", "רשימ", "דוגמ", "חדש"}


def title_words(title):
    """המילים המשמעותיות בשם של כרטיס, בצורה בסיסית: בלי ה' ו' ל' ב' ש' בהתחלה, ובלי ים/ות/י/ה/ת בסוף."""
    words = set()
    for w in re.findall(r"[א-ת]+", title.replace("יי", "י")):
        w = w.translate(FINALS)
        if len(w) >= 5 and w[0] in "הולבש":
            w = w[1:]
        for suf in ("ים", "ות"):
            if len(w) > 4 and w.endswith(suf):
                w = w[:-2]
                break
        if len(w) > 3 and w[-1] in "יהת":
            w = w[:-1]
        if len(w) >= 3 and w not in STOP:
            words.add(w)
    return words


def rule_ids_in(text, valid):
    """מספרי הכללים שהטקסט מזכיר, מחוץ למקורות ובלי תאריכים."""
    found = set()
    for m in RULE_ID.finditer(text):
        rid = f"{int(m.group(1))}.{int(m.group(2))}"
        before = text[:m.start()]
        if rid not in valid or before.count("[") > before.count("]"):
            continue
        if re.search(r"[בממו]־$", before[-2:]) or re.search(r"(?:עודכן|נפתח|מ־|עד)\D{0,3}$", before[-8:]):
            continue
        found.add(rid)
    return found


def groups_for(settings):
    """הקבוצות במפה, לפי הסדר: (מזהה, כותרת, משפט הסבר, תווית קצרה)."""
    d = settings["decider"]
    return [
        ("rules", f"הכללים של {d}", f"כל תחום אוסף את התיקונים, ההעדפות וההחלטות של {d} בנושא אחד.", "כללים"),
        ("core", "הליבה", "מה שנקרא בכל בקשה, חוץ מהכללים.", "ליבה"),
        ("products", "סוגי התוצרים", "איך בונים כל סוג של תוצר, ומה בודקים לפני שהוא יוצא.", "תוצרים"),
        ("knowledge", "הידע", "כרטיס לכל נושא, ולכל טענה יש מקור.", "ידע"),
        ("offerings", "המוצרים", "מה יש בכל מוצר, למי הוא, ומה מוביל אליו.", "מוצרים"),
        ("works", "העבודות", "כרטיס לכל עבודה: מה התבקש, באיזה מצב היא, ומה נבדק.", "עבודות"),
        ("questions", f"שאלות {settings['to_decider']}", f"מה שרק {d} יכולה להכריע.", "שאלות"),
        ("more", "עוד במוח", "", "עוד"),
    ]


def build_map(settings, rules_path, questions_path, journal_path):
    """מחזיר את ה־HTML של המפה, את התוכן של הכרטיסים (JSON), ואת שמות הכרטיסים שאין להם אף קשר."""
    rules_text = read(rules_path)
    # התחומים והכללים
    domains, rule_ids, domain_sections = {}, {}, {}
    current = None
    for line in rules_text.splitlines():
        h = re.match(r"^## (\d+)\.\s*(.+)$", line)
        if h:
            current = h.group(1)
            domains[current] = f"d{current}"
            domain_sections[current] = {"title": h.group(2).strip(), "lines": []}
            continue
        if line.startswith("## "):
            current = None
            continue
        if current is None:
            continue
        domain_sections[current]["lines"].append(line)
        m = re.match(r"^- (?:~~)?\*\*(\d+\.\d+)", line)
        if m:
            rule_ids[m.group(1)] = f"d{current}"
    ctx = Ctx(rule_ids, domains)

    cards = []

    def add(cid, group, title, meta, body_md, text_for_links=""):
        cards.append({"id": cid, "group": group, "title": title, "meta": meta,
                      "body": body_md, "text": text_for_links or body_md, "links": set()})

    for num, sec in domain_sections.items():
        body = "\n".join(sec["lines"])
        live = [l for l in sec["lines"] if re.match(r"^- \*\*\d+\.\d+", l)]
        add(f"d{num}", "rules", f"{num}. {sec['title']}", count(len(live), "כלל אחד", "כללים"), body)

    for i, path in enumerate(p for p in md_files(CORE) if os.path.basename(p) != RULES_NAME):
        text = read(path)
        name = os.path.basename(path)[:-3].replace("_", " ")
        meta = f"עודכן {first_date(text)}" if first_date(text) else "בליבה"
        add(f"c{i}", "core", name, meta, text)

    for gid, folder, _label in CARD_FOLDERS:
        for i, path in enumerate(md_files(folder)):
            text = read(path)
            name = os.path.basename(path)[:-3]
            meta = f"עודכן {first_date(text)}" if first_date(text) else "בלי תאריך עדכון"
            add(f"{gid[0]}{i}", gid, name, meta, text)

    for i, path in enumerate(md_files("50_עבודות")):
        text = read(path)
        title = re.search(r"^# (.+)$", text, re.M)
        status = field(text, "מצב")
        add(f"w{i}", "works", title.group(1).strip() if title else os.path.basename(path)[:-3],
            status or "בלי מצב", text)

    q_text = read(questions_path)
    chapters = re.split(r"^## ", q_text, flags=re.M)[1:]
    for i, ch in enumerate(chapters):
        title, _, body = ch.partition("\n")
        title = re.sub(r"^\d+\.\s*", "", title.strip())
        if title.startswith("נענו"):
            continue
        items = re.findall(r"^- (?:~~)?\*\*(★)?", body, re.M)
        stars = len(re.findall(r"^- (?:~~)?\*\*[^*\n]*★", body, re.M))
        meta = count(len(items), "שאלה אחת", "שאלות")
        if stars:
            meta += ", " + ("והיא עוצרת עבודה" if len(items) == 1 else
                            count(stars, "ואחת מהן עוצרת עבודה", "מהן עוצרות עבודה"))
        add(f"q{i}", "questions", title, meta, body)

    journal = read(journal_path)
    if journal:
        entries = re.findall(r"^## (.+)$", journal, re.M)
        add("journal", "more", "היומן", count(len(entries), "רשומה אחת", "רשומות"), journal)

    # התוכן של כל כרטיס. שמות של כרטיסים אחרים בטקסט הופכים לקישורים
    by_id = {c["id"]: c for c in cards}
    named_groups = ("products", "knowledge", "offerings", "core")
    ctx.titles = sorted(((c["title"], c["id"]) for c in cards
                         if c["group"] in named_groups and len(c["title"]) >= 6),
                        key=lambda t: -len(t[0]))
    for c in cards:
        ctx.current, ctx.mentioned = c["id"], set()
        c["html"] = md_to_html(c["body"], ctx)
        for other in ctx.mentioned:
            c["links"].add(other)
            by_id[other]["links"].add(c["id"])

    # הקשרים: כרטיס שמזכיר כלל מתחבר לתחום שלו; כרטיס שמזכיר שם של כרטיס אחר מתחבר אליו
    for c in cards:
        if c["group"] in ("rules", "more"):
            continue
        for rid in rule_ids_in(c["text"], rule_ids):
            dom = rule_ids[rid]
            c["links"].add(dom)
            by_id[dom]["links"].add(c["id"])
    named = [c for c in cards if c["group"] in named_groups and len(c["title"]) >= 6]
    for c in cards:
        if c["group"] == "more":
            continue
        for other in named:
            if other["id"] != c["id"] and other["title"] in c["text"]:
                c["links"].add(other["id"])
                other["links"].add(c["id"])
    # קשרים לפי נושא: שני כרטיסים מקבוצות שונות שחולקים מילה משמעותית בשם
    for a in cards:
        for b in cards:
            if a["id"] >= b["id"] or a["group"] == b["group"] or "more" in (a["group"], b["group"]):
                continue
            if title_words(a["title"]) & title_words(b["title"]):
                a["links"].add(b["id"])
                b["links"].add(a["id"])
    # עבודה מתחברת לסוג התוצר שלה, לפי השורה "תוצר:". ליומן אין קשרים: הוא רשימה של מה שקרה
    for c in cards:
        if c["group"] == "works":
            kind = field(c["text"], "תוצר")
            for other in cards:
                if other["group"] == "products" and kind and kind == other["title"]:
                    c["links"].add(other["id"])
                    other["links"].add(c["id"])

    if not cards:
        return "", "{}", []

    # ה־HTML של המפה
    groups = groups_for(settings)
    parts = ['<p class="maphint">לחיצה על כרטיס פותחת אותו, וגם Enter או רווח. '
             'הכרטיסים שקשורים אליו נשארים בולטים.</p>',
             '<div class="map" id="mapgrid">']
    for gid, gtitle, gsub, _label in groups:
        group = [c for c in cards if c["group"] == gid]
        if not group:
            continue
        sub = f'<p class="gsub">{esc(gsub)}</p>' if gsub else ""
        parts.append(f'<section class="grp" aria-labelledby="g-{gid}"><h2 id="g-{gid}">{esc(gtitle)}</h2>{sub}'
                     '<div class="cards">')
        for c in group:
            n_links = len(c["links"])
            linked = (f'<span class="lk">{count(n_links, "קשור לכרטיס אחד", "כרטיסים קשורים")}</span>'
                      if n_links else "")
            parts.append(f'<button type="button" class="card" data-id="{attr(c["id"])}" aria-pressed="false" '
                         f'aria-controls="reader">'
                         f'<span class="t">{esc(c["title"])}</span>'
                         f'<span class="m">{esc(c["meta"])}</span>{linked}</button>')
        parts.append("</div></section>")
    parts.append("</div>")

    data = {
        "labels": [[gid, label] for gid, _t, _s, label in groups],
        "cards": {c["id"]: {"title": c["title"], "title_html": bdi_html(esc(c["title"])),
                            "meta_html": bdi_html(esc(c["meta"])), "html": c["html"],
                            "group": c["group"], "links": sorted(c["links"])} for c in cards},
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    lonely = [c["title"] for c in cards if not c["links"] and c["id"] != "journal"]
    return bdi_html("\n".join(parts)), payload, lonely
