#!/usr/bin/env node
// Builds the portfolio PDF from portfolio.json (written by Claude after collect.mjs and the interview).
//
//   node build.mjs ["פרויקטים/תיק עבודות"] [--check]
//
// A4 landscape: cover, about, one page per work (or a pair), video pages, contact page with a clickable mailto link.
// Output: עבודות/<studio> - תיק עבודות.pdf (never overwrites), and <project>/_check.png (all pages, small) to look at.
// Prints the file size, and warns above 20MB (too big for an email attachment).
import fs from "node:fs";
import path from "node:path";
import { MM, copyFonts, freshPath, parseArgs, pdf, shot } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const dir = path.resolve(opts._[0] || path.join("פרויקטים", "תיק עבודות"));
const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, ""));
const inv = readJson(path.join(dir, "inventory.json"));
const P = readJson(path.join(dir, "portfolio.json"));
const esc = (s = "") => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
// Latin runs (file names, fonts, emails) are isolated so they don't scramble the Hebrew order.
const bidi = (s = "") => esc(s).replace(/([A-Za-z0-9@][A-Za-z0-9@._\-+/: ]*[A-Za-z0-9])/g, '<bdi dir="ltr">$1</bdi>');

// ---------- colors & fonts ----------
const hexes = (P.palette?.length ? P.palette : inv.colors.map((c) => c.hex)).filter((v, i, a) => a.indexOf(v) === i).slice(0, 5);
const role = (words, fb) => inv.colors.find((c) => words.some((w) => c.role.includes(w)))?.hex || fb;
const paper = P.paper || role(["רקע"], "#FAFAF7"), ink = P.ink || role(["ראשי", "טקסט"], "#24282B"), accent = P.accent || role(["משני", "הדגשה"], ink);
const head = P.headFont || inv.head || "Heebo", body = P.bodyFont || inv.body || "Noto Sans Hebrew";
copyFonts([...new Set([head, body, "Heebo", "Noto Sans Hebrew"])], path.join(dir, "fonts"));

const studio = P.studio || "הסטודיו שלי";
let pageNo = 0;
const foot = () => `<div class="foot"><span>${esc(studio)} · תיק עבודות</span><span>${String(++pageNo).padStart(2, "0")}</span></div>`;
const bsd = P.bsd === false ? "" : '<div class="bsd">בס״ד</div>';
const img = (src, alt) => `<img src="${esc(src)}" alt="${esc(alt || "")}">`;

const pages = [];
// cover
pages.push(`<section class="pg cover">${bsd}
  <div class="c-in">${inv.logo ? `<div class="logo">${img(inv.logo, studio)}</div>` : `<div class="name">${esc(studio)}</div>`}
  ${P.tagline ? `<p class="tag">${bidi(P.tagline)}</p>` : ""}<p class="sub">תיק עבודות${P.year ? ` · ${esc(P.year)}` : ""}</p></div></section>`);
pageNo++;
// about
if (P.about?.length) {
  const sw = hexes.map((h) => `<div class="sw"><i style="background:${h}"></i><bdi dir="ltr">${h}</bdi></div>`).join("");
  pages.push(`<section class="pg about">${bsd}<div class="ab">
    <div><span class="kick">על הסטודיו</span>${P.about.map((s) => `<p class="big">${bidi(s)}</p>`).join("")}</div>
    <div class="side">
      ${hexes.length ? `<span class="kick">הצבעים</span><div class="sws">${sw}</div>` : ""}
      <span class="kick">הגופנים</span><p class="font" style="font-family:'${head}'">${esc(head)}</p>${body !== head ? `<p class="font sm" style="font-family:'${body}'">${esc(body)}</p>` : ""}
      ${P.language ? `<span class="kick">השפה העיצובית</span><p class="lang">${bidi(P.language)}</p>` : ""}
    </div></div>${foot()}</section>`);
}
// works
let workNo = 0, flip = false;
const meta = (w) => `${w.kind ? `<p class="kind">${bidi(w.kind)}</p>` : ""}<h2>${bidi(w.title || "")}</h2>${w.caption ? `<p class="cap">${bidi(w.caption)}</p>` : ""}`;
for (const pg of P.pages || []) {
  if (pg.type === "pair") {
    const cells = pg.works.map((w) => `<figure><div class="frame half">${img(w.media, w.title)}</div><div class="m"><span class="num">${String(++workNo).padStart(2, "0")}</span>${meta(w)}</div></figure>`).join("");
    pages.push(`<section class="pg pair">${bsd}<div class="two">${cells}</div>${foot()}</section>`);
  } else {
    const isVid = pg.type === "video";
    const extra = isVid ? `<p class="vid">סרטון${pg.duration ? ` · ${esc(pg.duration)}` : ""} · מצורף בנפרד</p>` : "";
    flip = !flip;
    pages.push(`<section class="pg work${flip ? "" : " flip"}">${bsd}<div class="wk">
      <div class="frame${isVid ? " video" : ""}">${img(pg.media, pg.title)}${isVid ? '<span class="play"></span>' : ""}</div>
      <div class="m"><span class="num">${String(++workNo).padStart(2, "0")}</span>${meta(pg)}${extra}</div></div>${foot()}</section>`);
  }
}
// contact
const mail = P.email ? `mailto:${P.email}` : null;
pages.push(`<section class="pg contact">${bsd}<div class="c-in">
  ${inv.logo ? `<div class="logo sm">${img(inv.logo, studio)}</div>` : ""}
  <h2>${esc(P.contactTitle || "לעבודה משותפת")}</h2>
  ${P.contactLine ? `<p class="tag">${bidi(P.contactLine)}</p>` : ""}
  ${mail ? `<a class="mail" href="${esc(mail)}"><bdi dir="ltr">${esc(P.email)}</bdi></a><a class="send" href="${esc(mail)}">שלחו מייל</a>` : ""}
  ${P.example ? '<p class="ex">פרטים לדוגמה</p>' : ""}</div>${foot()}</section>`);

const css = `@page{size:297mm 210mm;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
:root{--paper:${paper};--ink:${ink};--accent:${accent};--muted:color-mix(in srgb,${ink} 55%,${paper});--frame:color-mix(in srgb,${ink} 4%,${paper});
  --head:"${head}",sans-serif;--text:"${body}",sans-serif}
html,body{background:#d9d9d4;direction:rtl;font-family:var(--text);color:var(--ink);-webkit-print-color-adjust:exact;print-color-adjust:exact}
@media print{html,body{background:none}}
.pg{position:relative;width:297mm;height:210mm;background:var(--paper);overflow:hidden;page-break-after:always;padding:20mm 22mm 22mm;margin:0 auto 6mm}
@media print{.pg{margin:0}}
.bsd{position:absolute;top:9mm;right:12mm;font:400 7pt var(--text);color:var(--muted)}
.foot{position:absolute;bottom:9mm;left:22mm;right:22mm;display:flex;justify-content:space-between;font:400 7.5pt var(--text);color:var(--muted);letter-spacing:.06em}
.kick{display:block;font:500 8pt var(--text);letter-spacing:.14em;color:var(--muted);margin:0 0 3mm}
.cover .c-in,.contact .c-in{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:6mm}
.logo img{max-height:72mm;max-width:150mm;display:block}
.logo.sm img{max-height:30mm}
.name{font:600 40pt var(--head)}
.tag{font:400 13pt/1.5 var(--text);max-width:170mm}
.sub{font:400 8.5pt var(--text);letter-spacing:.2em;color:var(--muted);margin-top:4mm}
.ab{display:grid;grid-template-columns:1.5fr 1fr;gap:22mm;height:100%;align-items:center}
.big{font:400 17pt/1.55 var(--head);margin-bottom:5mm;text-wrap:pretty}
.side .kick{margin-top:7mm}
.sws{display:flex;gap:5mm;flex-wrap:wrap}
.sw{display:flex;flex-direction:column;align-items:center;gap:1.5mm;font:400 6.5pt var(--text);color:var(--muted)}
.sw i{width:13mm;height:13mm;border-radius:50%;box-shadow:inset 0 0 0 .2mm rgba(0,0,0,.12)}
.font{font-size:16pt;line-height:1.3}.font.sm{font-size:12pt}
.lang{font:400 11pt/1.5 var(--text)}
.wk{display:grid;grid-template-columns:1.7fr 1fr;gap:14mm;height:100%;align-items:center}
.work.flip .wk{grid-template-columns:1fr 1.7fr}.work.flip .frame{order:2}
.frame{position:relative;height:150mm;background:var(--frame);display:flex;align-items:center;justify-content:center;padding:8mm}
.frame img{max-width:100%;max-height:100%;object-fit:contain;display:block;box-shadow:0 1mm 3mm rgba(0,0,0,.08)}
.frame.video img{box-shadow:none}
.play{position:absolute;left:12mm;bottom:12mm;width:16mm;height:16mm;border-radius:50%;background:rgba(255,255,255,.92);box-shadow:0 1mm 4mm rgba(0,0,0,.18)}
.play::after{content:"";position:absolute;left:6mm;top:4.2mm;border-style:solid;border-width:3.8mm 0 3.8mm 6mm;border-color:transparent transparent transparent var(--ink)}
.num{display:block;font:300 22pt var(--head);color:var(--accent);margin-bottom:3mm}
.kind{font:500 7.5pt var(--text);letter-spacing:.14em;color:var(--muted);margin-bottom:2mm}
h2{font:600 19pt/1.25 var(--head);margin-bottom:3mm;text-wrap:balance}
.cap{font:400 10.5pt/1.6 var(--text);text-wrap:pretty}
.vid{font:400 8.5pt var(--text);color:var(--muted);margin-top:4mm}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14mm;height:100%;align-items:center}
.two figure{display:flex;flex-direction:column;gap:5mm}
.frame.half{height:112mm}
.two .num{font-size:15pt;margin-bottom:1mm}.two h2{font-size:14pt}.two .cap{font-size:9.5pt}
.contact h2{font-size:24pt;margin:2mm 0 0}
.mail{font:400 17pt var(--text);color:var(--ink);text-decoration:none;border-bottom:.3mm solid var(--accent);padding-bottom:1mm}
.send{font:500 10pt var(--text);color:var(--accent);text-decoration:none;letter-spacing:.06em}
.ex{font:400 8pt var(--text);color:var(--muted)}`;

const html = `<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><title>${esc(studio)} · תיק עבודות</title>
<link rel="stylesheet" href="fonts/fonts.css"><style>${css}</style></head><body>${pages.join("\n")}</body></html>`;
const file = path.join(dir, "portfolio.html");
fs.writeFileSync(file, html);

const W = Math.round(297 * MM), H = Math.round(210 * MM);
if (opts.check) {
  // every page, one under the other, small enough to look at in one go
  shot(file, path.join(dir, "_check.png"), { w: W + 40, h: Math.round((H + 6 * MM) * pages.length), scale: 0.5 });
  console.log(`saved: ${path.join(dir, "_check.png")} (${pages.length} עמודים)`);
} else {
  const out = freshPath(path.resolve("עבודות", `${studio} - תיק עבודות.pdf`));
  pdf(file, out, { wait: 10000 });
  const mb = fs.statSync(out).size / 1024 / 1024;
  const hasLink = mail ? fs.readFileSync(out).includes("mailto:") : null;
  console.log(`עמודים: ${pages.length} · גודל: ${mb.toFixed(1)} MB${mb > 20 ? "  ! מעל 20MB, גדול מדי לצירוף למייל. מריצים collect.mjs --max 1400 --q 6 ובונים שוב" : " ✓ אפשר לצרף למייל"}`);
  if (mail) console.log(hasLink ? "הקישור למייל לחיץ ב-PDF ✓" : "! הקישור למייל לא נמצא ב-PDF");
  console.log(`saved: ${out}`);
}
