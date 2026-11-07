#!/usr/bin/env node
// The analysis as one page that opens in the browser: the video, the insights, frames along the way,
// numbers about the sound and the pace, and the transcript. Every time on the page (like 01:23) jumps the video there.
//
//   node report.mjs --scan "ניתוח/<name>/scan.json" --insights "ניתוח/<name>/insights.md" [--transcript "תמלולים/<name>.json"] --out "ניתוח/<name> - ניתוח.html"

import fs from "node:fs";
import path from "node:path";
import { args, clock, fail, transcriptLines } from "./common.mjs";

const { opt } = args();
const scanFile = opt("scan");
const insightsFile = opt("insights");
const outArg = opt("out");
if (!scanFile || !insightsFile || !outArg) fail("צריך --scan, --insights ו---out.");
for (const f of [scanFile, insightsFile]) if (!fs.existsSync(f)) fail(`לא מצאתי את "${f}".`);
const scan = JSON.parse(fs.readFileSync(scanFile, "utf8"));
const md = fs.readFileSync(insightsFile, "utf8").replace(/^﻿/, "");
const transcript = opt("transcript") && fs.existsSync(opt("transcript")) ? JSON.parse(fs.readFileSync(opt("transcript"), "utf8")) : null;
const out = outArg;
const outDir = path.dirname(path.resolve(out));
const scanDir = path.dirname(path.resolve(scanFile));
const rel = (abs) => encodeURI(path.relative(outDir, abs).replace(/\\/g, "/")).replace(/#/g, "%23").replace(/\?/g, "%3F");
const videoSrc = rel(path.resolve(scanDir, scan.video));

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const toSec = (t) => t.split(":").map(Number).reduce((a, p) => a * 60 + p, 0);
const TIME = /(?<![\d:.])(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)(?![\d:])/g;
const link = (m) => `<a class="t" href="#" data-t="${toSec(m)}">${m}</a>`;
// A time, or a range of two times. A range reads left to right, like numbers in Hebrew text: 01:20–01:45.
const T = TIME.source;
const TIME_OR_RANGE = new RegExp(String.raw`${T}(?:\s*[–-]\s*${T})?`, "g");
const inline = (s) =>
  esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(TIME_OR_RANGE, (_, a, b) => `<bdi dir="ltr">${link(a)}${b ? `–${link(b)}` : ""}</bdi>`);

function markdown(src) {
  const html = [];
  const lines = src.split(/\r?\n/);
  let list = null;
  let para = [];
  const flush = () => {
    if (para.length) html.push(`<p>${inline(para.join(" "))}</p>`);
    para = [];
    if (list) html.push(`</${list}>`);
    list = null;
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    let m;
    if (!line.trim()) {
      flush();
    } else if ((m = line.match(/^(#{1,3})\s+(.*)/))) {
      flush();
      const level = Math.min(m[1].length + 1, 4);
      html.push(`<h${level}>${inline(m[2])}</h${level}>`);
    } else if (/^\s*\|.*\|\s*$/.test(line)) {
      flush();
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++].trim());
      i--;
      const cells = (r) => r.slice(1, -1).split("|").map((c) => c.trim());
      const body = rows.filter((r) => !/^\|[\s:|-]+\|$/.test(r));
      const [head, ...rest] = body;
      html.push(`<div class="tbl"><table><thead><tr>${cells(head).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rest.map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
    } else if ((m = line.match(/^\s*([-*•]|\d+[.)])\s+(.*)/))) {
      if (para.length) {
        html.push(`<p>${inline(para.join(" "))}</p>`);
        para = [];
      }
      const kind = /\d/.test(m[1]) ? "ol" : "ul";
      if (list !== kind) {
        if (list) html.push(`</${list}>`);
        html.push(`<${kind}>`);
        list = kind;
      }
      html.push(`<li>${inline(m[2])}</li>`);
    } else {
      if (list) {
        html.push(`</${list}>`);
        list = null;
      }
      para.push(line.trim());
    }
  }
  flush();
  return html.join("\n");
}

const a = scan.audio;
const chips = [
  ["אורך", scan.length],
  ["גודל", `${scan.orientation} · ${scan.size}`],
  ["חיתוכים בין שוטים", `${scan.shots.cuts} (שוט ממוצע: ${scan.shots.averageShotSeconds} שנ')`],
  a && ["עוצמה", `${a.loudnessLUFS} LUFS`],
  a && ["שקט של שנייה ומעלה", `${a.silences.length} פעמים, ${a.silentSeconds} שנ'`],
  transcript && ["קצב דיבור", `${Math.round(transcript.words.length / (scan.duration / 60))} מילים בדקה`],
].filter(Boolean);

const frames = scan.frames
  .map((f) => `<button class="frame" data-t="${f.t}" aria-label="קפיצה ל-${clock(f.t)}"><img src="${rel(path.join(scanDir, f.file))}" alt="${clock(f.t)}" loading="lazy"></button>`)
  .join("");

const transcriptHtml = transcript
  ? transcriptLines(transcript.words)
      .map((l) => `<p><a class="t" href="#" data-t="${l[0].s}"><bdi dir="ltr">${clock(l[0].s)}</bdi></a> ${esc(l.map((w) => w.w).join(" "))}</p>`)
      .join("\n")
  : "";

const page = `<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ניתוח: ${esc(path.parse(scan.name).name)}</title>
<style>
:root { --ink: #1d2b33; --muted: #5d6c74; --line: #dfe5e8; --tint: #eef5f6; --accent: #2f716d; --paper: #fbfcfc; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.65 "Segoe UI", Arial, "Arial Hebrew", sans-serif; }
header { padding: 22px 24px 12px; border-block-end: 1px solid var(--line); }
header h1 { margin: 0 0 4px; font-size: 24px; }
header .sub { color: var(--muted); font-size: 14px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-block-start: 12px; }
.chip { background: var(--tint); border-radius: 99px; padding: 4px 12px; font-size: 13px; }
.chip b { color: var(--accent); font-weight: 600; margin-inline-end: 6px; }
main { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 42%); gap: 28px; padding: 20px 24px 48px; max-width: 1400px; margin: 0 auto; }
aside { position: sticky; top: 12px; align-self: start; }
video { width: 100%; max-height: 78vh; background: #000; border-radius: 10px; display: block; }
.hint { color: var(--muted); font-size: 13px; margin-block-start: 6px; }
article h2 { font-size: 20px; margin: 26px 0 8px; color: var(--accent); }
article h3, article h4 { font-size: 17px; margin: 18px 0 6px; }
article ul, article ol { padding-inline-start: 22px; margin: 6px 0; }
article li { margin: 3px 0; }
a.t { color: var(--accent); text-decoration: none; background: var(--tint); border-radius: 6px; padding: 0 5px; font-variant-numeric: tabular-nums; }
a.t:hover, a.t:focus-visible { background: var(--accent); color: #fff; }
.tbl { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 15px; }
th, td { border: 1px solid var(--line); padding: 6px 10px; text-align: start; vertical-align: top; }
th { background: var(--tint); }
code { background: var(--tint); padding: 0 4px; border-radius: 4px; }
section.frames { padding: 0 24px 24px; max-width: 1400px; margin: 0 auto; }
.strip { display: flex; gap: 6px; overflow-x: auto; padding-block-end: 8px; }
.frame { flex: none; border: 0; padding: 0; background: none; cursor: pointer; border-radius: 6px; overflow: hidden; }
.frame img { height: 110px; display: block; }
.frame:focus-visible { outline: 3px solid var(--accent); }
details { margin-block-start: 24px; border-block-start: 1px solid var(--line); padding-block-start: 12px; }
summary { cursor: pointer; font-weight: 600; color: var(--accent); }
details p { margin: 4px 0; }
@media (max-width: 860px) { main { grid-template-columns: minmax(0, 1fr); } aside { position: static; order: -1; } }
</style>
</head>
<body>
<header>
  <h1>ניתוח: <bdi>${esc(path.parse(scan.name).name)}</bdi></h1>
  <div class="sub">כל זמן בדף (כמו <bdi dir="ltr">01:23</bdi>) מקפיץ את הסרטון לשם.</div>
  <div class="chips">${chips.map(([k, v]) => `<span class="chip"><b>${k}</b><bdi>${esc(String(v))}</bdi></span>`).join("")}</div>
</header>
<main>
  <article>
${markdown(md)}
${transcriptHtml ? `<details><summary>התמלול המלא</summary>\n${transcriptHtml}\n</details>` : ""}
  </article>
  <aside>
    <video id="v" src="${videoSrc}" controls preload="metadata"></video>
    <div class="hint">הסרטון לא מופיע? הדף מחפש אותו במקום המקורי שלו. לא מזיזות את הסרטון או את התיקייה "ניתוח".</div>
  </aside>
</main>
<section class="frames" aria-label="תמונות לאורך הסרטון">
  <h2 style="font-size:18px;color:var(--accent)">לאורך הסרטון</h2>
  <div class="strip">${frames}</div>
</section>
<script>
const v = document.getElementById("v");
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-t]");
  if (!el) return;
  e.preventDefault();
  v.currentTime = Number(el.dataset.t);
  v.play().catch(() => {});
  if (window.innerWidth < 860) v.scrollIntoView({ behavior: "smooth", block: "center" });
});
</script>
</body>
</html>
`;
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(out, page);
console.log(JSON.stringify({ ok: true, file: out }));
