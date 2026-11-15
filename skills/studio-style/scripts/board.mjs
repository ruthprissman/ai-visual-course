#!/usr/bin/env node
// Boards, read right to left.
//
// 1. The design-language board, every language drawn in HER colors:
//    node board.mjs languages [--colors "#hex,#hex,..."] [--name "תכלת"] [--fams light,line] [--ids 1,5,12] [--out "לוחות/לוח שפות.png"]
//    Without --colors it reads brand.md in the current folder. Without --fams/--ids: two boards (families 1–4, 5–8).
//
// 2. One language as an SVG in her colors (the starting point for a piece):
//    node board.mjs sample --id 31 --out "פרויקטים/<name>/art.svg" [--px 1200]
//
// 3. A board of finished options (directions), with a label under each:
//    node board.mjs images --labels "רך,גאומטרי,מסורתי" --out "לוחות/לוח כיוונים.png" a.png b.png c.png
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { DEFAULT_COLORS, FONTS, FONTS_DIR, fontFaceCss, freshPath, palette, parseArgs, readBrand, shot } from "./common.mjs";
import { FAMILIES, STYLES } from "./styles.mjs";

const opts = parseArgs(process.argv.slice(2));
const mode = opts._[0];
const work = fs.mkdtempSync(path.join(os.tmpdir(), "style-board-"));
const fontUrl = pathToFileURL(FONTS_DIR).href;
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");

function page(css, body, families) {
  return `<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><style>${fontFaceCss(families, fontUrl)}
  *{box-sizing:border-box;margin:0;padding:0} body{direction:rtl;font-family:Heebo,sans-serif;width:1920px} ${css}</style></head><body>${body}</body></html>`;
}

function context() {
  const brand = readBrand(process.cwd());
  const colors = opts.colors ? String(opts.colors).split(",").map((s) => s.trim()) : brand?.colors?.length ? brand.colors : DEFAULT_COLORS;
  const p = palette(colors);
  const name = opts.name || brand?.name || "";
  const head = brand?.head && FONTS[brand.head] ? brand.head : "Heebo";
  const o = { initial: (name.match(/[א-ת]/) || ["א"])[0], head, serif: "Frank Ruhl Libre" };
  return { p, name, head, o };
}

// One language as a standalone SVG in her colors: the starting point for a piece.
function sample() {
  const s = STYLES.find((x) => x.id === Number(opts.id));
  if (!s) { console.error("usage: node board.mjs sample --id 31 --out art.svg"); process.exit(1); }
  const { p, o } = context();
  const px = Number(opts.px || 1200);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="${px}" height="${px}" style="direction:ltr">\n<!-- ${s.id} · ${s.he} · ${s.en} -->\n${s.draw(p, `s${s.id}_`, o)}\n</svg>\n`;
  const out = freshPath(path.resolve(opts.out || `${s.id} - ${s.he}.svg`));
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, svg);
  console.log(`saved: ${out}`);
}

function languages() {
  const { p, name, head, o } = context();

  let groups = FAMILIES.map((f) => ({ ...f, items: STYLES.filter((s) => s.fam === f.key) }));
  if (opts.fams) { const keep = String(opts.fams).split(","); groups = groups.filter((g) => keep.includes(g.key)); }
  if (opts.ids) {
    // A curated pick: one centered group, in the order she (or I) listed them.
    const keep = String(opts.ids).split(",").map(Number);
    const items = keep.map((id) => STYLES.find((s) => s.id === id)).filter(Boolean);
    const rows = [];
    for (let i = 0; i < items.length; i += 6) rows.push(items.slice(i, i + 6));
    groups = rows.map((r, i) => ({ key: `pick${i}`, he: i === 0 ? "בחירה ממוקדת" : "", line: i === 0 ? "השפות שמתאימות למה שתיארת" : "", items: r, center: true }));
  }
  const parts = !opts.fams && !opts.ids ? [groups.slice(0, 4), groups.slice(4)] : [groups];
  const outBase = path.resolve(opts.out || path.join("לוחות", "לוח שפות עיצוביות.png"));
  const chips = Object.entries(p).map(([k, v]) => `<span class="chip"><i style="background:${v}"></i><bdi>${v}</bdi></span>`).join("");
  const css = `body{padding:40px 40px 50px;background:#F4F5F6;color:#1D2733}
    header{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:18px}
    h1{font:700 44px/1.15 Heebo} .sub{font:400 21px Heebo;color:#5A6673;margin-top:6px}
    .chips{display:flex;gap:10px;flex-wrap:wrap;max-width:760px;justify-content:flex-end;direction:ltr}
    .chip{display:flex;align-items:center;gap:6px;font:400 14px Heebo;color:#5A6673;background:#fff;border-radius:20px;padding:4px 10px 4px 4px}
    .chip i{width:22px;height:22px;border-radius:50%;box-shadow:inset 0 0 0 1px rgba(0,0,0,.12)}
    h2{font:700 30px Heebo;margin:26px 0 12px} h2 span{font:400 22px Heebo;color:#5A6673;margin-inline-start:10px}
    .row{display:grid;grid-template-columns:repeat(6,280px);gap:32px}
    figure{display:flex;flex-direction:column;gap:8px}
    svg.t{width:280px;height:280px;border-radius:10px;display:block;box-shadow:0 1px 2px rgba(0,0,0,.08),0 8px 22px rgba(0,0,0,.08);background:#fff;direction:ltr}
    .cap{display:flex;align-items:center;gap:8px;white-space:nowrap} .n{font:700 20px Heebo;color:#fff;background:#1D2733;border-radius:14px;min-width:34px;text-align:center;padding:1px 8px}
    .he{font:700 22px Heebo} .en{font:400 16px Heebo;color:#6B7785;text-align:right}
    .fits{font:400 16px/1.35 Heebo;color:#5A6673;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}`;
  const outs = [];
  parts.forEach((gs, k) => {
    const body = `<header><div><h1>שפות עיצוביות${name ? ` · ${esc(name)}` : ""}${parts.length > 1 ? ` · לוח ${k + 1} מתוך ${parts.length}` : ""}</h1>
      <div class="sub">כל דוגמה מצוירת בקוד, בצבעים שלך. בוחרות לפי המספר, ואפשר לשלב שתיים או שלוש.</div></div><div class="chips">${chips}</div></header>` +
      gs.map((g) => `${g.he ? `<h2>${g.he}<span>${g.line}</span></h2>` : ""}<div class="row"${g.center ? ' style="justify-content:center"' : ""}>${g.items.map((s) =>
        `<figure><svg class="t" viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">${s.draw(p, `s${s.id}_`, o)}</svg>
        <div class="cap"><span class="n">${s.id}</span><span class="he">${s.he}</span></div><div class="en"><bdi>${s.en}</bdi></div><div class="fits">${s.fits}</div></figure>`).join("")}</div>`).join("");
    const rows = gs.length;
    const h = 40 + 110 + rows * (26 + 46 + 280 + 100) + 40;
    const html = path.join(work, `b${k}.html`);
    fs.writeFileSync(html, page(css, body, ["Heebo", head, "Frank Ruhl Libre"]));
    let out = parts.length > 1 ? outBase.replace(/\.png$/i, ` ${k + 1}.png`) : outBase;
    out = freshPath(out);
    shot(html, out, { w: 1920, h, wait: 8000 });
    outs.push(out);
  });
  outs.forEach((o) => console.log(`saved: ${o}`));
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString("ascii", 1, 4) === "PNG") return [b.readUInt32BE(16), b.readUInt32BE(20)];
  return [1600, 1000];
}

function images() {
  const files = opts._.slice(1).map((f) => path.resolve(f));
  if (files.length < 2) { console.error('usage: node board.mjs images --labels "a,b,c" --out board.png a.png b.png [c.png]'); process.exit(1); }
  const labels = String(opts.labels || "").split(",").map((s) => s.trim());
  const [w0, h0] = pngSize(files[0]);
  const gap = 28, maxW = (1840 - gap * (files.length - 1)) / files.length;
  const cellW = Math.min(h0 > w0 ? 520 : 860, maxW), cellH = Math.round((cellW * h0) / w0);
  const css = `body{background:#1D2733;padding:30px 40px 40px;display:flex;justify-content:center;gap:${gap}px}
    figure{display:flex;flex-direction:column;align-items:center;gap:16px} img{width:${cellW}px;height:${cellH}px;object-fit:contain;border-radius:12px;background:#fff;display:block}
    figcaption{font:700 36px Heebo;color:#fff}`;
  // Latin words (model names, terms) are isolated so they don't scramble the Hebrew order.
  const bidi = (s) => esc(s).replace(/([A-Za-z][A-Za-z0-9.]*(?:\s+[A-Za-z0-9.]+)*)/g, '<bdi dir="ltr">$1</bdi>');
  const body = files.map((f, i) => `<figure><img src="${pathToFileURL(f).href}"><figcaption>${i + 1}${labels[i] ? ` · ${bidi(labels[i])}` : ""}</figcaption></figure>`).join("");
  const html = path.join(work, "dir.html");
  fs.writeFileSync(html, page(css, body, ["Heebo"]));
  const out = freshPath(path.resolve(opts.out || path.join("לוחות", "לוח כיוונים.png")));
  shot(html, out, { w: 1920, h: cellH + 140, wait: 4000 });
  console.log(`saved: ${out}`);
}

if (mode === "languages") languages();
else if (mode === "images") images();
else if (mode === "sample") sample();
else { console.error("usage: node board.mjs languages | sample | images ..."); process.exit(1); }
try { fs.rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 }); } catch {}
