#!/usr/bin/env node
// Opens a work folder for ONE item (the template every row will fill).
//
//   node new-item.mjs "כרטיסי הושבה" --size 90x55 --data "data.json" [--fonts "Frank Ruhl Libre"]
//
// Creates פרויקטים/<name>/ with item.html, data.json, fonts/, piece.json. Never overwrites an existing folder.
import fs from "node:fs";
import path from "node:path";
import { FONTS, brandVars, copyFonts, parseArgs, readBrand } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const name = opts._[0];
if (!name || !opts.size || !opts.data) { console.error('usage: node new-item.mjs "<name>" --size 90x55 --data data.json [--fonts "Frank Ruhl Libre"]'); process.exit(1); }
const [w, h] = String(opts.size).split("x").map(Number);
const data = JSON.parse(fs.readFileSync(opts.data, "utf8").replace(/^﻿/, ""));
const brand = readBrand(process.cwd());
const head = brand?.head && FONTS[brand.head] ? brand.head : "Heebo";
const body = brand?.body && FONTS[brand.body] ? brand.body : "Noto Sans Hebrew";
const fonts = [...new Set([head, body, ...String(opts.fonts || "").split(",").map((s) => s.trim()).filter((f) => FONTS[f])])];

let dir = path.resolve("פרויקטים", name);
for (let i = 2; fs.existsSync(dir); i++) dir = path.resolve("פרויקטים", `${name} - ${i}`);
fs.mkdirSync(dir, { recursive: true });
copyFonts(fonts, path.join(dir, "fonts"));
fs.writeFileSync(path.join(dir, "data.json"), JSON.stringify(data, null, 2));
fs.writeFileSync(path.join(dir, "piece.json"), JSON.stringify({ name, size: [w, h], fonts }, null, 2));

const first = data.columns[0];
fs.writeFileSync(path.join(dir, "item.html"), `<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>${name} · פריט אחד</title>
<link rel="stylesheet" href="fonts/fonts.css">
<style>
  /* פריט אחד בגודל ${w}×${h} מ״מ. כל שורה באקסל ממלאת אותו.
     העמודות: ${data.columns.map((c) => `{{${c}}}`).join(" ")}  ·  ועוד: {{_n}} מספר השורה, {{_seed}} מספר ייחודי לשורה */
  :root{${brandVars(brand)}
    --head:"${head}",sans-serif;--text:"${body}",sans-serif;--w:${w}mm;--h:${h}mm;--bleed:0mm;}
  *{box-sizing:border-box;margin:0;padding:0}
  .item{position:relative;width:var(--w);height:var(--h);overflow:hidden;direction:rtl;font-family:var(--text);color:var(--ink);background:var(--bg)}
  /* רקע שצריך להגיע עד הקצה: בתוך .bleed-bg. בהדפסה אחד בעמוד הוא ממשיך לתוך הגלישה. */
  .item .bleed-bg{position:absolute;inset:calc(var(--bleed) * -1)}
  /* טקסט שמשתנה מאוד באורך (שם, כותרת): class="fit". אם הוא לא נכנס, הגופן קטן לבד, עד data-min מהגודל. */
  .item .fit{white-space:nowrap;overflow:hidden}
  .item svg{direction:ltr}
</style>
</head>
<body>
<!-- item -->
<div class="item">
  <div class="bleed-bg"></div>
  <div class="fit" data-min="0.6" style="position:absolute;inset:16mm 6mm auto;text-align:center;font:600 8mm var(--head)">{{${first}}}</div>
</div>
<!-- /item -->
</body>
</html>
`);
console.log(`created: ${dir}`);
console.log(`columns: ${data.columns.join(", ")}`);
console.log(`fonts: ${fonts.join(", ")}`);
