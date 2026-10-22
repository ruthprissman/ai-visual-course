#!/usr/bin/env node
// One comparison image of the logo: the original crop, the clean PNG and the redrawn SVG, side by side.
//
//   node logo-sheet.mjs <logo folder> [--font Heebo]
//
// Reads logo-crop.png (or any original), logo-clean.png and logo.svg from the folder, and writes
// "השוואת לוגו.png" into it. Missing files are simply left out of the sheet.

import { execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HF = "npx --yes hyperframes@0.8.147";
const args = process.argv.slice(2);
const dir = path.resolve(args[0] || "לוגו");
const fi = args.indexOf("--font");
const font = fi >= 0 ? args[fi + 1] : "Heebo";
const here = path.dirname(fileURLToPath(import.meta.url));

const pick = (...names) => names.map((n) => path.join(dir, n)).find((p) => fs.existsSync(p));
const orig = pick("logo-crop.png", "logo.png", "logo.jpg", "logo-orig.png");
const clean = pick("logo-clean.png");
const svg = pick("logo.svg");
if (!orig && !clean && !svg) {
  console.error(`no logo files in ${dir}`);
  process.exit(1);
}

const work = fs.mkdtempSync(path.join(os.tmpdir(), "logo-sheet-"));
const cols = [orig, clean, svg].filter(Boolean).length;
const W = 440 * cols + 80;
const H = 600;
execSync(`node "${path.join(here, "new-project.mjs")}" "${work}" --size ${W}x${H} --fonts "${font}"`, { stdio: "ignore" });

const figs = [];
if (orig) {
  fs.copyFileSync(orig, path.join(work, "assets", "orig.png"));
  figs.push(`<figure><img src="assets/orig.png"><figcaption>המקור</figcaption></figure>`);
}
if (clean) {
  fs.copyFileSync(clean, path.join(work, "assets", "clean.png"));
  figs.push(`<figure class="checker"><img src="assets/clean.png"><figcaption>נקי, בלי רקע</figcaption></figure>`);
}
if (svg) {
  const inline = fs.readFileSync(svg, "utf8").replace(/<\?xml[^>]*>/, "").replace("<svg ", '<svg class="art" ');
  figs.push(`<figure>${inline}<figcaption>משורטט, <bdi>SVG</bdi></figcaption></figure>`);
}

let html = fs.readFileSync(path.join(work, "index.html"), "utf8");
html = html
  .replace(/<div id="s1"[\s\S]*?<div id="bsd"[\s\S]*?<\/div>/, `<div id="s1" class="layer clip sheet" data-start="0" data-duration="1" data-track-index="1">${figs.join("")}</div>`)
  .replaceAll('data-duration="5"', 'data-duration="1"')
  .replace(/tl\.from\([^\n]*\n/, "\n")
  .replace(
    "</style>",
    `.sheet { display: flex; flex-direction: row-reverse; justify-content: space-around; align-items: center; background: #fff; direction: ltr; }
      figure { width: 400px; display: flex; flex-direction: column; align-items: center; gap: 14px; }
      figure img, figure .art { width: 400px; height: 460px; object-fit: contain; }
      .checker img { background: repeating-conic-gradient(#e4e4e4 0 25%, #fff 0 50%) 0 0 / 24px 24px; }
      figcaption { font: 500 30px var(--font-text); color: #333; direction: rtl; }
    </style>`,
  );
fs.writeFileSync(path.join(work, "index.html"), html);

execSync(`${HF} snapshot --at 0.5 --no-end -o snaps`, { cwd: work, stdio: "ignore" });
const shot = fs.readdirSync(path.join(work, "snaps")).find((f) => f.startsWith("frame-"));
const out = path.join(dir, "השוואת לוגו.png");
fs.copyFileSync(path.join(work, "snaps", shot), out);
fs.rmSync(work, { recursive: true, force: true });
console.log(`saved: ${out}`);
