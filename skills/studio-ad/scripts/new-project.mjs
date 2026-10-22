#!/usr/bin/env node
// Creates a HyperFrames project for one video, with GSAP and the Hebrew fonts saved locally,
// so the render never depends on a CDN or a font site.
//
//   node new-project.mjs <folder> --size 1080x1920 --fonts "Heebo,Noto Sans Hebrew" [--title "..."]
//
// Fonts come from npm (@fontsource/<name>), which works even where font sites are blocked.

import { execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HF_VERSION = "0.8.147";
const GSAP_VERSION = "3.14.2";
const WEIGHTS = [300, 400, 500, 600, 700, 800];

const args = process.argv.slice(2);
const dir = args.find((a) => !a.startsWith("--") && !isValue(a));
function opt(name, fallback) {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
function isValue(a) {
  const i = args.indexOf(a);
  return i > 0 && args[i - 1].startsWith("--");
}

if (!dir) {
  console.error('usage: node new-project.mjs <folder> --size 1080x1920 --fonts "Heebo,Noto Sans Hebrew"');
  process.exit(1);
}

const [W, H] = opt("size", "1080x1920").split("x").map(Number);
const fonts = opt("fonts", "Heebo").split(",").map((f) => f.trim()).filter(Boolean);
const title = opt("title", path.basename(dir));
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(dir);
const assets = path.join(root, "assets");
const fontDir = path.join(assets, "fonts");
fs.mkdirSync(fontDir, { recursive: true });

// npm pack downloads a package tarball without installing anything globally.
function unpack(pkg) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "studio-ad-"));
  const out = execSync(`npm pack ${pkg} --silent`, { cwd: tmp, encoding: "utf8" }).trim().split("\n").pop();
  execSync(`tar -xzf "${out}"`, { cwd: tmp });
  return path.join(tmp, "package");
}

if (!fs.existsSync(path.join(assets, "gsap.min.js"))) {
  const gsap = unpack(`gsap@${GSAP_VERSION}`);
  fs.copyFileSync(path.join(gsap, "dist", "gsap.min.js"), path.join(assets, "gsap.min.js"));
}

const faces = [];
for (const family of fonts) {
  const slug = family.toLowerCase().replace(/\s+/g, "-");
  let pkg;
  try {
    pkg = unpack(`@fontsource/${slug}`);
  } catch {
    console.error(`font not found on npm: ${family} (@fontsource/${slug})`);
    continue;
  }
  for (const subset of ["hebrew", "latin"]) {
    for (const w of WEIGHTS) {
      const file = `${slug}-${subset}-${w}-normal.woff2`;
      const src = path.join(pkg, "files", file);
      if (!fs.existsSync(src)) continue;
      fs.copyFileSync(src, path.join(fontDir, file));
      // Two families per font: the Hebrew subset first, the Latin one for digits and punctuation.
      faces.push(`@font-face { font-family: "${family} ${subset}"; src: url("assets/fonts/${file}") format("woff2"); font-weight: ${w}; }`);
    }
  }
}
const stack = (family) => `"${family} hebrew", "${family} latin", sans-serif`;

const starter = fs.readFileSync(path.join(here, "..", "assets", "starter.html"), "utf8");
const html = starter
  .replaceAll("{{W}}", String(W))
  .replaceAll("{{H}}", String(H))
  .replaceAll("{{TITLE}}", title)
  .replace("{{FONT_FACES}}", faces.join("\n      "))
  .replaceAll("{{FONT_TITLE}}", stack(fonts[0]))
  .replaceAll("{{FONT_TEXT}}", stack(fonts[1] || fonts[0]));

if (!fs.existsSync(path.join(root, "index.html"))) fs.writeFileSync(path.join(root, "index.html"), html);
fs.writeFileSync(
  path.join(root, "package.json"),
  JSON.stringify(
    {
      name: "studio-ad-video",
      private: true,
      type: "module",
      scripts: {
        dev: `npx --yes hyperframes@${HF_VERSION} preview`,
        check: `npx --yes hyperframes@${HF_VERSION} check`,
        render: `npx --yes hyperframes@${HF_VERSION} render`,
      },
    },
    null,
    2,
  ),
);
fs.writeFileSync(
  path.join(root, "meta.json"),
  JSON.stringify({ id: "studio-ad-video", name: title, createdAt: new Date().toISOString() }, null, 2),
);

console.log(`ready: ${root}  (${W}x${H}, fonts: ${fonts.join(", ")})`);
