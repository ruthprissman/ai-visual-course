#!/usr/bin/env node
// Opens a work folder for one piece, with the fonts inside it and the brand colors as CSS variables.
//
//   Screen:  node new-piece.mjs "רקע נקודות אור" --size 1920x1080 [--fonts "Heebo,Frank Ruhl Libre"]
//   Print:   node new-piece.mjs "הזמנה לבר מצווה" --print 148x210 [--bleed 3] [--marks]
//
// Creates פרויקטים/<name>/ with index.html, fonts/, piece.json. Never overwrites an existing folder.
import fs from "node:fs";
import path from "node:path";
import { DEFAULT_COLORS, FONTS, copyFonts, fontFaceCss, palette, parseArgs, readBrand } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const name = opts._[0];
if (!name) { console.error('usage: node new-piece.mjs "<name>" --size 1920x1080 | --print 148x210 [--bleed 3] [--marks] [--fonts "Heebo,Frank Ruhl Libre"]'); process.exit(1); }

const brand = readBrand(process.cwd());
const p = palette(brand?.colors?.length ? brand.colors : opts.colors ? String(opts.colors).split(",") : DEFAULT_COLORS);
const head = brand?.head && FONTS[brand.head] ? brand.head : "Heebo";
const body = brand?.body && FONTS[brand.body] ? brand.body : "Noto Sans Hebrew";
const fonts = [...new Set([head, body, ...String(opts.fonts || "").split(",").map((s) => s.trim()).filter((f) => FONTS[f])])];

let dir = path.resolve("פרויקטים", name);
for (let i = 2; fs.existsSync(dir); i++) dir = path.resolve("פרויקטים", `${name} - ${i}`);
fs.mkdirSync(dir, { recursive: true });
copyFonts(fonts, path.join(dir, "fonts"));
fs.writeFileSync(path.join(dir, "fonts", "fonts.css"), fontFaceCss(fonts, "."));

const vars = `--bg:${p.bg};--ink:${p.ink};--a1:${p.a1};--a2:${p.a2};--a3:${p.a3};--soft:${p.soft};--light:${p.light};
    --head:"${head}",sans-serif;--text:"${body}",sans-serif;`;

let html, meta;
if (opts.print) {
  const [tw, th] = String(opts.print).split("x").map(Number);
  const b = opts.bleed !== undefined ? Number(opts.bleed) : 3;
  const slug = opts.marks ? 10 : 0;
  const pw = tw + 2 * b + 2 * slug, ph = th + 2 * b + 2 * slug;
  // Crop marks: 5 mm lines at each trim line, starting 2 mm outside the bleed.
  const off = slug - b - 2; // from the page edge to where a mark ends
  const marks = !opts.marks ? "" : [
    [slug + b, 0, 0.25, off], [slug + b + tw, 0, 0.25, off], [slug + b, ph - off, 0.25, off], [slug + b + tw, ph - off, 0.25, off],
    [0, slug + b, off, 0.25], [0, slug + b + th, off, 0.25], [pw - off, slug + b, off, 0.25], [pw - off, slug + b + th, off, 0.25],
  ].map(([x, y, w, h]) => `<i class="mark" style="left:${x}mm;top:${y}mm;width:${w}mm;height:${h}mm"></i>`).join("");
  html = `<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>${name}</title>
<link rel="stylesheet" href="fonts/fonts.css">
<style>
  /* דף להדפסה: ${tw}×${th} מ״מ אחרי חיתוך, גלישה ${b} מ״מ${opts.marks ? ", סימני חיתוך" : ""}. */
  :root{${vars}
    --trim-w:${tw}mm;--trim-h:${th}mm;--bleed:${b}mm;}
  @page{size:${pw}mm ${ph}mm;margin:0}
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:${pw}mm;height:${ph}mm;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{position:relative;direction:rtl;font-family:var(--text);color:var(--ink)}
  /* .sheet = הדף כולל הגלישה. רקע ותמונה מגיעים עד הקצה של .sheet. */
  .sheet{position:absolute;left:${slug}mm;top:${slug}mm;width:${tw + 2 * b}mm;height:${th + 2 * b}mm;overflow:hidden;background:var(--bg)}
  /* .safe = אזור בטוח לטקסט: ${b + 5} מ״מ מהקצה של .sheet (5 מ״מ בתוך קו החיתוך). */
  .safe{position:absolute;inset:${b + 5}mm}
  .mark{position:absolute;background:#000}
</style>
</head>
<body>
<div class="sheet">
  <!-- העבודה כאן -->
  <div class="safe"></div>
</div>
${marks}
</body>
</html>
`;
  meta = { name, kind: "print", trim: [tw, th], bleed: b, slug, page: [pw, ph], fonts };
} else {
  const [w, h] = String(opts.size || "1920x1080").split("x").map(Number);
  html = `<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>${name}</title>
<link rel="stylesheet" href="fonts/fonts.css">
<style>
  :root{${vars}}
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:${w}px;height:${h}px;overflow:hidden;background:var(--bg)}
  body{direction:rtl;font-family:var(--text);color:var(--ink)}
  .piece{position:relative;width:${w}px;height:${h}px;overflow:hidden}
  /* SVG בתוך הדף: direction:ltr כדי ש-text-anchor יעבוד לפי צד פיזי. טקסט עברי בתוכו עדיין נכתב מימין לשמאל. */
  .piece svg{direction:ltr}
</style>
</head>
<body>
<div class="piece">
  <!-- העבודה כאן -->
</div>
</body>
</html>
`;
  meta = { name, kind: "screen", size: [w, h], fonts };
}
fs.writeFileSync(path.join(dir, "index.html"), html);
fs.writeFileSync(path.join(dir, "piece.json"), JSON.stringify(meta, null, 2));
console.log(`created: ${dir}`);
console.log(`fonts: ${fonts.join(", ")}`);
