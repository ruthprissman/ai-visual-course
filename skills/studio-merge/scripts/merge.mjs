#!/usr/bin/env node
// Fills the item template with every row, and lays the items out for print.
//
//   One item to check (the longest row by default):
//     node merge.mjs "פרויקטים/<name>" --one [longest|<row number>]
//   Many on a sheet, with crop marks (abutting; or with a gap between items):
//     node merge.mjs "פרויקטים/<name>" --paper A4 [--marks] [--gap 0]
//   One per page, with bleed (invitations, certificates):
//     node merge.mjs "פרויקטים/<name>" --paper item --bleed 3 [--marks]
//   Also one image per row (300 DPI):  add --each
//
// Output (never overwriting): עבודות/<name> - להדפסה.pdf, עבודות/<name> - עמוד 1.png, and עבודות/<name>/ for --each.
// Prints a report: items vs rows, names that had to shrink, and text that still doesn't fit.
import fs from "node:fs";
import path from "node:path";
import { MM, dumpDom, freshPath, parseArgs, pdf, shot } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const dir = path.resolve(opts._[0] || ".");
// A file saved by another program may start with a BOM; JSON.parse doesn't accept it.
const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, ""));
const meta = readJson(path.join(dir, "piece.json"));
const data = readJson(path.join(dir, opts.data || "data.json"));
const src = fs.readFileSync(path.join(dir, "item.html"), "utf8");
const [W, H] = meta.size;
const outDir = path.resolve(opts.out || "עבודות");

const styles = [...src.matchAll(/<style[^>]*>[\s\S]*?<\/style>/g)].map((m) => m[0]).join("\n");
const links = [...src.matchAll(/<link[^>]+>/g)].map((m) => m[0]).join("\n");
const frag = src.match(/<!--\s*item\s*-->([\s\S]*?)<!--\s*\/item\s*-->/)?.[1];
if (!frag) { console.error("ב-item.html חסרים הסימנים <!-- item --> ו-<!-- /item --> מסביב לפריט."); process.exit(1); }

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const seedOf = (row) => { let h = 2166136261; for (const ch of Object.values(row).join("|")) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) % 1000000; };
const used = [...new Set([...frag.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)].map((m) => m[1]))];
const missing = used.filter((u) => !u.startsWith("_") && !data.columns.includes(u));
if (missing.length) console.log(`! בתבנית יש מקום לעמודה שלא קיימת בקובץ: ${missing.join(", ")}`);

function fill(row, n) {
  let html = frag.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (all, key) => (key === "_n" ? String(n) : key === "_seed" ? String(seedOf(row)) : key in row ? esc(row[key]) : all));
  // ids inside the item (SVG gradients, filters) must be unique for every copy
  const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
  for (const id of ids) {
    const e = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    html = html.replace(new RegExp(`(\\sid=")${e}(")`, "g"), `$1${id}_r${n}$2`).replace(new RegExp(`url\\(#${e}\\)`, "g"), `url(#${id}_r${n})`)
      .replace(new RegExp(`href="#${e}"`, "g"), `href="#${id}_r${n}"`);
  }
  return html.replace(/class="item(\s|")/, `data-row="${n}" class="item$1`);
}

const FIT = `<script>
document.fonts.ready.then(() => {
  const rep = [];
  document.querySelectorAll('.item').forEach((it) => it.querySelectorAll('.fit').forEach((el) => {
    const base = parseFloat(getComputedStyle(el).fontSize), min = base * parseFloat(el.dataset.min || '0.6');
    let fs = base;
    const over = () => el.scrollWidth > el.clientWidth + 0.5 || el.scrollHeight > el.clientHeight + 0.5;
    while (over() && fs > min) { fs -= 0.25; el.style.fontSize = fs + 'px'; }
    if (fs < base || over()) rep.push({ row: +it.dataset.row, text: el.textContent.trim(), ratio: +(fs / base).toFixed(2), over: over() });
  }));
  document.body.setAttribute('data-report', JSON.stringify({ items: document.querySelectorAll('.item').length, fit: rep }));
});
</script>`;

function page({ css, body }) {
  return `<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">${links}${styles}<style>${css}</style></head><body>${body}${FIT}</body></html>`;
}

function report(html, rowsCount) {
  const dom = dumpDom(html);
  const m = dom.match(/data-report="([^"]*)"/);
  if (!m) { console.log("! לא הצלחתי לקרוא את דוח הבדיקה."); return; }
  const r = JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, "&"));
  console.log(`בדיקה: ${r.items} פריטים מתוך ${rowsCount} שורות${r.items === rowsCount ? " ✓" : "  ✗ חסרים פריטים!"}`);
  const small = r.fit.filter((f) => !f.over && f.ratio < 0.85), over = r.fit.filter((f) => f.over);
  if (small.length) console.log(`הוקטנו כדי להיכנס: ${small.map((f) => `שורה ${f.row} "${f.text}" (${Math.round(f.ratio * 100)}%)`).join(" · ")}`);
  if (over.length) console.log(`! עדיין לא נכנס, צריך לתקן: ${over.map((f) => `שורה ${f.row} "${f.text}"`).join(" · ")}`);
  if (!small.length && !over.length) console.log("כל הטקסטים נכנסו בגודל המקורי.");
}

const rows = data.rows;
const writeTmp = (file, html) => { const p = path.join(dir, file); fs.writeFileSync(p, html); return p; };

// ---------- one item ----------
if (opts.one) {
  const len = (r) => used.reduce((s, k) => s + (r[k] || "").length, 0);
  const idx = opts.one === true || opts.one === "longest" ? rows.reduce((bi, r, i) => (len(r) > len(rows[bi]) ? i : bi), 0) : Number(opts.one) - 1;
  const html = writeTmp("_one.html", page({ css: `html,body{margin:0;width:${W}mm;height:${H}mm;overflow:hidden}`, body: fill(rows[idx], idx + 1) }));
  const out = shot(html, path.join(dir, "_one.png"), { w: Math.round(W * MM), h: Math.round(H * MM), scale: 3 });
  console.log(`שורה ${idx + 1}: ${Object.values(rows[idx]).join(" | ")}`);
  report(html, 1);
  console.log(`saved: ${out}`);
  process.exit(0);
}

// ---------- sheet or one per page ----------
const PAPERS = { A4: [210, 297], A3: [297, 420], SRA3: [320, 450], A5: [148, 210] };
const marks = !!opts.marks, gap = Number(opts.gap || 0), slug = marks ? 10 : 0;
let css, pages = [], pw, ph;
const tick = (x, y, w, h) => `<i class="mk" style="left:${x}mm;top:${y}mm;width:${w}mm;height:${h}mm"></i>`;

if (opts.paper === "item") {
  const b = Number(opts.bleed ?? 3);
  pw = W + 2 * b + 2 * slug; ph = H + 2 * b + 2 * slug;
  css = `@page{size:${pw}mm ${ph}mm;margin:0} html,body{margin:0} body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .pg{position:relative;width:${pw}mm;height:${ph}mm;overflow:hidden;page-break-after:always}
    .pg>.item{position:absolute;left:${slug + b}mm;top:${slug + b}mm;overflow:visible;--bleed:${b}mm}
    .clip{position:absolute;left:${slug}mm;top:${slug}mm;width:${W + 2 * b}mm;height:${H + 2 * b}mm;overflow:hidden}
    .clip>.item{position:absolute;left:${b}mm;top:${b}mm;overflow:visible;--bleed:${b}mm} .mk{position:absolute;background:#000}`;
  const m = marks ? [slug + b, slug + b + W].map((x) => tick(x - 0.125, 0, 0.25, slug - 2) + tick(x - 0.125, ph - slug + 2, 0.25, slug - 2)).join("") +
    [slug + b, slug + b + H].map((y) => tick(0, y - 0.125, slug - 2, 0.25) + tick(pw - slug + 2, y - 0.125, slug - 2, 0.25)).join("") : "";
  pages = rows.map((r, i) => `<div class="pg"><div class="clip">${fill(r, i + 1)}</div>${m}</div>`);
} else {
  let [PW, PH] = PAPERS[String(opts.paper || "A4").toUpperCase()] || PAPERS.A4;
  const margin = Math.max(10, slug + 2);
  const fitCount = (pw, ph) => [Math.floor((pw - 2 * margin + gap) / (W + gap)), Math.floor((ph - 2 * margin + gap) / (H + gap))];
  let [cols, rws] = fitCount(PW, PH);
  const [c2, r2] = fitCount(PH, PW);
  if (c2 * r2 > cols * rws) { [PW, PH] = [PH, PW]; [cols, rws] = [c2, r2]; }
  if (cols * rws < 1) { console.error("הפריט גדול מהדף. נסי --paper A3, או --paper item."); process.exit(1); }
  pw = PW; ph = PH;
  const per = cols * rws, bw = cols * W + (cols - 1) * gap, bh = rws * H + (rws - 1) * gap;
  const x0 = (PW - bw) / 2, y0 = (PH - bh) / 2;
  const xs = [...new Set(Array.from({ length: cols }, (_, c) => [x0 + c * (W + gap), x0 + c * (W + gap) + W]).flat().map((v) => +v.toFixed(3)))];
  const ys = [...new Set(Array.from({ length: rws }, (_, r) => [y0 + r * (H + gap), y0 + r * (H + gap) + H]).flat().map((v) => +v.toFixed(3)))];
  const m = marks ? xs.map((x) => tick(x - 0.125, y0 - 8, 0.25, 5) + tick(x - 0.125, y0 + bh + 3, 0.25, 5)).join("") +
    ys.map((y) => tick(x0 - 8, y - 0.125, 5, 0.25) + tick(x0 + bw + 3, y - 0.125, 5, 0.25)).join("") : "";
  css = `@page{size:${PW}mm ${PH}mm;margin:0} html,body{margin:0} body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .pg{position:relative;width:${PW}mm;height:${PH}mm;overflow:hidden;page-break-after:always}
    .grid{position:absolute;left:${x0}mm;top:${y0}mm;display:grid;grid-template-columns:repeat(${cols},${W}mm);grid-auto-rows:${H}mm;gap:${gap}mm;direction:rtl}
    .grid>.item{outline:${marks || gap ? "none" : "0.1mm dotted #ccd"}} .mk{position:absolute;background:#000}`;
  for (let i = 0; i < rows.length; i += per) pages.push(`<div class="pg"><div class="grid">${rows.slice(i, i + per).map((r, k) => fill(r, i + k + 1)).join("")}</div>${m}</div>`);
  console.log(`פריסה: ${cols}×${rws} = ${per} בעמוד ${PW}×${PH} מ״מ · ${pages.length} עמודים`);
}

const sheet = writeTmp("_sheet.html", page({ css, body: pages.join("") }));
report(sheet, rows.length);
const saved = [];
saved.push(pdf(sheet, freshPath(path.join(outDir, `${meta.name} - להדפסה.pdf`))));
saved.push(shot(sheet, freshPath(path.join(outDir, `${meta.name} - עמוד 1.png`)), { w: Math.round(pw * MM), h: Math.round(ph * MM), scale: 1.5 }));

if (opts.each) {
  const eachDir = path.join(outDir, meta.name);
  rows.forEach((r, i) => {
    const html = writeTmp("_each.html", page({ css: `html,body{margin:0;width:${W}mm;height:${H}mm;overflow:hidden}`, body: fill(r, i + 1) }));
    const label = String(Object.values(r)[0] || "").replace(/[\\/:*?"<>|]/g, "").slice(0, 40);
    saved.push(shot(html, freshPath(path.join(eachDir, `${String(i + 1).padStart(2, "0")} - ${label}.png`)), { w: Math.round(W * MM), h: Math.round(H * MM), scale: 300 / 96 }));
  });
}
saved.forEach((s) => console.log(`saved: ${s}`));
