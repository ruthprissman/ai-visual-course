// Shared helpers for studio-merge: browser, render, fonts, brand palette. Node only, no npm packages.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const SKILL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
// If studio-style is installed next to this skill, its 14 fonts are used too.
const SIBLING_FONTS = path.resolve(SKILL, "..", "studio-style", "assets", "fonts");
const OWN_FONTS = path.join(SKILL, "assets", "fonts");
export const FONT_DIRS = [OWN_FONTS, SIBLING_FONTS].filter((d) => fs.existsSync(d));

export const FONTS = {
  "Heebo": "heebo", "Assistant": "assistant", "Rubik": "rubik", "Noto Sans Hebrew": "noto-sans-hebrew",
  "Varela Round": "varela-round", "Frank Ruhl Libre": "frank-ruhl-libre", "David Libre": "david-libre",
  "Noto Serif Hebrew": "noto-serif-hebrew", "Miriam Libre": "miriam-libre", "Bellefair": "bellefair",
  "Suez One": "suez-one", "Secular One": "secular-one", "Karantina": "karantina", "Amatic SC": "amatic-sc",
};
const HEBREW_RANGE = "U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F";
const LATIN_RANGE = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD";

function fontFiles(fam) {
  const id = FONTS[fam];
  const seen = new Map();
  for (const dir of FONT_DIRS) for (const f of fs.readdirSync(dir)) if (f.startsWith(`${id}-`) && f.endsWith(".woff2") && !seen.has(f)) seen.set(f, path.join(dir, f));
  return [...seen.entries()];
}
export const availableFonts = () => Object.keys(FONTS).filter((f) => fontFiles(f).length);

/** Copies the font files of the given families into dir, and writes dir/fonts.css. */
export function copyFonts(families, dir) {
  fs.mkdirSync(dir, { recursive: true });
  const rules = [];
  for (const fam of families) {
    for (const [file, from] of fontFiles(fam)) {
      fs.copyFileSync(from, path.join(dir, file));
      const m = file.match(/-(hebrew|latin)-(\d+)\.woff2$/);
      if (m) rules.push(`@font-face{font-family:"${fam}";font-weight:${m[2]};font-display:block;src:url("./${file}") format("woff2");unicode-range:${m[1] === "hebrew" ? HEBREW_RANGE : LATIN_RANGE}}`);
    }
  }
  fs.writeFileSync(path.join(dir, "fonts.css"), rules.join("\n"));
}

export function findBrowser() {
  const env = process.env;
  const pf = env.PROGRAMFILES || "C:\\Program Files", pf86 = env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)";
  const list = [env.CHROME_PATH,
    path.join(pf, "Google", "Chrome", "Application", "chrome.exe"), path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
    path.join(env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"), path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean);
  const hit = list.find((p) => fs.existsSync(p));
  if (!hit) { console.error("לא מצאתי Chrome או Edge במחשב. צריך אחד מהם כדי ליצור PDF ותמונות."); process.exit(2); }
  return hit;
}

function runBrowser(args) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "studio-merge-"));
  const res = spawnSync(findBrowser(), ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
    "--allow-file-access-from-files", `--user-data-dir=${profile}`, ...args], { encoding: "utf8", timeout: 300000, maxBuffer: 64 * 1024 * 1024 });
  try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 }); } catch {}
  return res;
}
const url = (html) => pathToFileURL(path.resolve(html)).href;

export function shot(html, out, { w, h, scale = 1, wait = 6000 } = {}) {
  out = path.resolve(out);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const res = runBrowser([`--force-device-scale-factor=${scale}`, `--window-size=${w},${h}`, `--virtual-time-budget=${wait}`, `--screenshot=${out}`, url(html)]);
  if (!fs.existsSync(out)) throw new Error(`הצילום לא נוצר: ${res.stderr || res.error}`);
  return out;
}
export function pdf(html, out, { wait = 8000 } = {}) {
  out = path.resolve(out);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const res = runBrowser(["--no-pdf-header-footer", `--virtual-time-budget=${wait}`, `--print-to-pdf=${out}`, url(html)]);
  if (!fs.existsSync(out)) throw new Error(`ה-PDF לא נוצר: ${res.stderr || res.error}`);
  return out;
}
/** The page's DOM after its scripts ran (used to read the fit report). */
export function dumpDom(html, { wait = 8000 } = {}) {
  return runBrowser([`--virtual-time-budget=${wait}`, "--dump-dom", url(html)]).stdout || "";
}

export const MM = 96 / 25.4;
export function freshPath(p) {
  if (!fs.existsSync(p)) return p;
  const ext = path.extname(p), base = p.slice(0, -ext.length);
  for (let i = 2; ; i++) if (!fs.existsSync(`${base} - ${i}${ext}`)) return `${base} - ${i}${ext}`;
}

// ---------- brand ----------
export function readBrand(dir = process.cwd()) {
  const file = ["brand.md", "מותג.md"].map((f) => path.join(dir, f)).find((f) => fs.existsSync(f));
  if (!file) return null;
  const text = fs.readFileSync(file, "utf8");
  const colors = [...text.matchAll(/^\|\s*([^|\n]+?)\s*\|\s*(#[0-9A-Fa-f]{6})\b/gm)].map((m) => ({ role: m[1], hex: m[2].toUpperCase() }));
  const fontIn = (label) => { const line = text.split("\n").find((l) => l.includes(label)) || ""; return Object.keys(FONTS).find((f) => line.includes(f)) || null; };
  return { colors, head: fontIn("כותרות"), body: fontIn("טקסט") };
}
export function brandVars(brand) {
  const pick = (words, fb) => brand?.colors?.find((c) => words.some((w) => c.role.includes(w)))?.hex || fb;
  const bg = pick(["רקע"], "#FFFFFF"), ink = pick(["ראשי", "טקסט"], "#24324A"), a1 = pick(["משני", "הדגשה"], "#3E7C8C");
  const soft = pick(["רך"], "#C9DCE0"), light = pick(["בהיר"], "#EEF4F5");
  return `--bg:${bg};--ink:${ink};--a1:${a1};--soft:${soft};--light:${light};`;
}

export function parseArgs(argv) {
  const opts = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) { const k = argv[i].slice(2); opts[k] = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : true; }
    else opts._.push(argv[i]);
  }
  return opts;
}
