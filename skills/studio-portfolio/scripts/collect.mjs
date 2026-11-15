#!/usr/bin/env node
// Collects everything in "הסטודיו שלי" that can go into the portfolio, and prepares small JPEG copies.
//
//   node collect.mjs [--max 1800] [--q 4] [--out "פרויקטים/תיק עבודות"]
//
// Looks in: לוגו/, עבודות/, סרטונים/, תמונות/ (and their sub-folders). Skips פרויקטים/, לוחות/ and check images.
// Images → JPEG on white, longest side --max (FFmpeg; quality --q: 2 best … 6 smaller).
// SVG → rendered in Chrome/Edge first. Videos → one frame + length (FFmpeg).
// PDF → uses its "- תצוגה.png" / "- עמוד 1.png" if there is one; otherwise it is listed as "no preview".
// Writes <out>/inventory.json and <out>/media/*, and prints a numbered list.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { parseArgs, readBrand, shot } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const root = process.cwd();
const out = path.resolve(opts.out || path.join("פרויקטים", "תיק עבודות"));
const media = path.join(out, "media");
fs.rmSync(media, { recursive: true, force: true });
fs.mkdirSync(media, { recursive: true });
const MAX = Number(opts.max || 1800), Q = String(opts.q || 4);

const IMG = /\.(png|jpe?g|webp|gif)$/i, SVG = /\.svg$/i, VID = /\.(mp4|webm|mov|m4v)$/i, PDF = /\.pdf$/i;
const SKIP_DIR = /^(פרויקטים|לוחות|node_modules|fonts|\.claude|\.git)$/;
const SKIP_FILE = /^_|_check|^לוח |לוח כיוונים|השוואת לוגו|תיק עבודות/;

function walk(dir, list = []) {
  if (!fs.existsSync(dir)) return list;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) { if (!SKIP_DIR.test(e.name)) walk(path.join(dir, e.name), list); }
    else if (!SKIP_FILE.test(e.name)) list.push(path.join(dir, e.name));
  }
  return list;
}
function findTool(name) {
  const r = spawnSync(process.platform === "win32" ? "where" : "which", [name], { encoding: "utf8" });
  return r.status === 0 ? r.stdout.split(/\r?\n/)[0].trim() : null;
}
const ffmpeg = findTool("ffmpeg"), ffprobe = findTool("ffprobe");
const run = (bin, args) => spawnSync(bin, args, { encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
const probe = (file, entries) => (ffprobe ? run(ffprobe, ["-v", "error", "-select_streams", "v:0", "-show_entries", entries, "-of", "csv=p=0", file]).stdout.trim() : "");
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
const rel = (p) => path.relative(out, p).replace(/\\/g, "/");
const scale = `scale='if(gt(iw,ih),min(${MAX},iw),-2)':'if(gt(iw,ih),-2,min(${MAX},ih))'`;

/** Any picture → JPEG on white (transparent areas become white, not black). */
function toJpeg(src, dest) {
  if (!ffmpeg) { const d = dest.replace(/\.jpg$/, path.extname(src)); fs.copyFileSync(src, d); return d; }
  run(ffmpeg, ["-y", "-loglevel", "error", "-i", src, "-filter_complex",
    `[0:v]format=rgba,split[a][b];[a]drawbox=c=white@1:t=fill[w];[w][b]overlay=format=auto,${scale}`, "-frames:v", "1", "-q:v", Q, dest]);
  return fs.existsSync(dest) ? dest : null;
}
function dims(file) {
  const v = probe(file, "stream=width,height").split(",").map(Number);
  return v.length === 2 && v[0] ? { w: v[0], h: v[1] } : {};
}
/** SVG → PNG through the browser (fonts and filters render like on screen). */
function svgToPng(src, dest) {
  const html = dest.replace(/\.png$/, ".html");
  const text = fs.readFileSync(src, "utf8");
  const vb = text.match(/viewBox="[\d.\s-]+?([\d.]+)\s+([\d.]+)"/);
  const ratio = vb ? +vb[2] / +vb[1] : 1, w = 1600, h = Math.round(1600 * ratio);
  fs.writeFileSync(html, `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#fff}img{width:${w}px;height:${h}px;display:block}</style><img src="${path.basename(src)}">`);
  const tmpSvg = path.join(path.dirname(html), path.basename(src));
  fs.copyFileSync(src, tmpSvg);
  try { shot(html, dest, { w, h }); } catch {}
  fs.rmSync(html, { force: true }); fs.rmSync(tmpSvg, { force: true });
  return fs.existsSync(dest) ? dest : null;
}

// ---------- logo, brand, language ----------
const logoDir = path.join(root, "לוגו");
const logo = ["logo-clean.png", "logo.png", "logo.svg", "logo-crop.png"].map((f) => path.join(logoDir, f)).find((f) => fs.existsSync(f)) || null;
const brand = readBrand(root);
const langFile = fs.readdirSync(root).find((f) => /^שפה עיצובית.*\.md$/.test(f)) || null;

// ---------- works ----------
const files = ["עבודות", "סרטונים", "תמונות"].flatMap((d) => walk(path.join(root, d)));
const items = [];
for (const f of files.filter((x) => PDF.test(x))) {
  const stem = f.replace(/\.pdf$/i, "").replace(/ - להדפסה$/, "");
  const prev = [`${stem} - תצוגה.png`, `${stem} - עמוד 1.png`, `${stem}.png`, `${stem}.jpg`].find((p) => fs.existsSync(p));
  items.push({ kind: "pdf", file: f, preview: prev || null });
}
const owned = new Set(items.map((i) => i.preview).filter(Boolean));
for (const f of files.filter((x) => (IMG.test(x) || SVG.test(x)) && !owned.has(x))) items.push({ kind: SVG.test(f) ? "svg" : "image", file: f });
for (const f of files.filter((x) => VID.test(x))) items.push({ kind: "video", file: f });

let n = 0;
for (const it of items) {
  it.id = String(++n).padStart(2, "0");
  const dest = path.join(media, `${it.id}.jpg`);
  let done = null;
  if (it.kind === "pdf") done = it.preview ? toJpeg(it.preview, dest) : null;
  else if (it.kind === "image") done = toJpeg(it.file, dest);
  else if (it.kind === "svg") { const png = svgToPng(it.file, path.join(media, `${it.id}.png`)); done = png ? toJpeg(png, dest) : null; if (png && done !== png) fs.rmSync(png, { force: true }); }
  else if (it.kind === "video" && ffmpeg) {
    const dur = +probe(it.file, "format=duration") || +run(ffprobe || "ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", it.file]).stdout || 0;
    if (dur) it.duration = fmt(dur);
    const t = Math.max(0.5, Math.min(dur * (Number(opts.frame) || 0.6) || 1.5, (dur || 2) - 0.3)); // later in the clip: animations have settled
    run(ffmpeg, ["-y", "-loglevel", "error", "-ss", String(t), "-i", it.file, "-frames:v", "1", "-vf", scale, "-q:v", Q, dest]);
    done = fs.existsSync(dest) ? dest : null;
  }
  if (done) { it.media = rel(done); Object.assign(it, dims(done)); }
  else it.problem = it.kind === "pdf" ? "אין תמונת תצוגה ל-PDF הזה" : it.kind === "video" ? "אין FFmpeg, אז אין תמונה מהסרטון" : "לא הצלחתי לפתוח את הקובץ";
  it.rel = path.relative(root, it.file).replace(/\\/g, "/");
  if (it.preview) it.preview = path.relative(root, it.preview).replace(/\\/g, "/");
  delete it.file;
}

let logoRel = null;
if (logo) {
  const dest = path.join(media, "logo.png");
  if (SVG.test(logo)) logoRel = svgToPng(logo, dest) ? rel(dest) : null;
  else if (ffmpeg) { run(ffmpeg, ["-y", "-loglevel", "error", "-i", logo, "-vf", "scale='min(1200,iw)':-2", dest]); logoRel = fs.existsSync(dest) ? rel(dest) : null; }
  else { fs.copyFileSync(logo, dest); logoRel = rel(dest); }
}

const inventory = { logo: logoRel, logoSource: logo ? path.relative(root, logo) : null, brandFile: brand?.file ? path.basename(brand.file) : null,
  colors: brand?.colors || [], head: brand?.head, body: brand?.body, language: langFile, ffmpeg: !!ffmpeg, items };
fs.writeFileSync(path.join(out, "inventory.json"), JSON.stringify(inventory, null, 2));

const sizeKB = fs.readdirSync(media).reduce((s, f) => s + fs.statSync(path.join(media, f)).size, 0) / 1024;
console.log(`לוגו: ${logo ? path.relative(root, logo) : "לא נמצא"} · מותג: ${brand ? "brand.md" : "לא נמצא"} · שפה עיצובית: ${langFile || "לא נמצאה"}`);
if (!ffmpeg) console.log("! FFmpeg לא נמצא: התמונות נכנסות כמו שהן (הקובץ יהיה גדול), ואין תמונות מהסרטונים.");
for (const it of items) {
  const what = it.kind === "video" ? `סרטון${it.duration ? ` ${it.duration}` : ""}` : it.kind === "pdf" ? "PDF" : "תמונה";
  console.log(`${it.id}  ${what.padEnd(10)}  ${it.rel}${it.problem ? `   ✗ ${it.problem}` : ""}`);
}
console.log(`תמונות מוכנות: ${items.filter((i) => i.media).length} מתוך ${items.length} · ${Math.round(sizeKB)} KB`);
console.log(`saved: ${path.join(out, "inventory.json")}`);
