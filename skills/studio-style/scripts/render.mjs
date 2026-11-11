#!/usr/bin/env node
// Exports a piece made with new-piece.mjs into עבודות/, never overwriting.
//
//   node render.mjs "פרויקטים/<name>" [--scale 2] [--check]
//
// Screen piece → PNG (scale 1 = exact size, 2 = extra sharp).
// Print piece  → PDF with bleed (and crop marks if made with --marks) + a 300 DPI PNG preview of the trimmed result.
// Any .svg file in the project folder is copied too (vector, for Illustrator).
// --check     → only a small preview into the project folder (_check.png), for a quick look before exporting.
import fs from "node:fs";
import path from "node:path";
import { MM, freshPath, parseArgs, pdf, shot } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const dir = path.resolve(opts._[0] || ".");
const meta = JSON.parse(fs.readFileSync(path.join(dir, "piece.json"), "utf8"));
const outDir = path.resolve(opts.out || "עבודות");
const index = path.join(dir, "index.html");
const saved = [];

if (meta.kind === "screen") {
  const [w, h] = meta.size;
  if (opts.check) saved.push(shot(index, path.join(dir, "_check.png"), { w, h, scale: Math.min(1, 1200 / Math.max(w, h)) }));
  else saved.push(shot(index, freshPath(path.join(outDir, `${meta.name}.png`)), { w, h, scale: Number(opts.scale || 1) }));
} else {
  const [tw, th] = meta.trim, b = meta.bleed, slug = meta.slug;
  // Preview of the trimmed piece: same page, shifted so only the area inside the trim lines shows.
  const prev = path.join(dir, "_preview.html");
  const css = `<style>html,body{width:${tw}mm!important;height:${th}mm!important;overflow:hidden}.sheet{left:${-b}mm!important;top:${-b}mm!important}.mark{display:none}</style>`;
  fs.writeFileSync(prev, fs.readFileSync(index, "utf8").replace("</head>", `${css}</head>`));
  const w = Math.round(tw * MM), h = Math.round(th * MM);
  if (opts.check) {
    saved.push(shot(prev, path.join(dir, "_check.png"), { w, h, scale: Math.min(2, 1200 / Math.max(w, h)) }));
  } else {
    const scale = Math.min(300 / 96, 8000 / Math.max(w, h)); // 300 DPI, capped for very large posters
    saved.push(shot(prev, freshPath(path.join(outDir, `${meta.name} - תצוגה.png`)), { w, h, scale }));
    saved.push(pdf(index, freshPath(path.join(outDir, `${meta.name} - להדפסה.pdf`))));
  }
  try { fs.rmSync(prev); } catch {}
}
if (!opts.check) {
  for (const f of fs.readdirSync(dir).filter((x) => x.toLowerCase().endsWith(".svg"))) {
    const to = freshPath(path.join(outDir, `${meta.name} - ${path.basename(f, ".svg")}.svg`));
    fs.copyFileSync(path.join(dir, f), to);
    saved.push(to);
  }
}
saved.forEach((s) => console.log(`saved: ${s}`));
