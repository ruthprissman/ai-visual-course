// Shared helpers for studio-style: browser, render, fonts, brand palette. Node only, no npm packages.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const SKILL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const FONTS_DIR = path.join(SKILL, "assets", "fonts");

// Hebrew fonts bundled in assets/fonts (SIL OFL, from Google Fonts via Fontsource).
export const FONTS = {
  "Heebo": { id: "heebo", kind: "סן־סריף נקי" },
  "Assistant": { id: "assistant", kind: "סן־סריף רך" },
  "Rubik": { id: "rubik", kind: "סן־סריף מעוגל" },
  "Noto Sans Hebrew": { id: "noto-sans-hebrew", kind: "סן־סריף לטקסט" },
  "Varela Round": { id: "varela-round", kind: "מעוגל וידידותי" },
  "Frank Ruhl Libre": { id: "frank-ruhl-libre", kind: "סריף קלאסי" },
  "David Libre": { id: "david-libre", kind: "סריף ספרותי" },
  "Noto Serif Hebrew": { id: "noto-serif-hebrew", kind: "סריף לטקסט" },
  "Miriam Libre": { id: "miriam-libre", kind: "גאומטרי קלאסי" },
  "Bellefair": { id: "bellefair", kind: "סריף אלגנטי דק" },
  "Suez One": { id: "suez-one", kind: "סריף כבד לכותרות" },
  "Secular One": { id: "secular-one", kind: "כותרת עבה" },
  "Karantina": { id: "karantina", kind: "צר ודחוס לכותרות" },
  "Amatic SC": { id: "amatic-sc", kind: "כתב יד" },
};

const HEBREW_RANGE = "U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F";
const LATIN_RANGE = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD";

/** @font-face rules for the given family names. urlBase: folder (relative URL or file URL) that holds the .woff2 files. */
export function fontFaceCss(families, urlBase = "fonts") {
  const files = fs.readdirSync(FONTS_DIR);
  const rules = [];
  for (const fam of families) {
    const f = FONTS[fam];
    if (!f) continue;
    for (const file of files.filter((x) => x.startsWith(`${f.id}-`) && x.endsWith(".woff2"))) {
      const m = file.match(/-(hebrew|latin)-(\d+)\.woff2$/);
      if (!m) continue;
      rules.push(`@font-face{font-family:"${fam}";font-weight:${m[2]};font-display:block;` +
        `src:url("${urlBase}/${file}") format("woff2");unicode-range:${m[1] === "hebrew" ? HEBREW_RANGE : LATIN_RANGE}}`);
    }
  }
  return rules.join("\n");
}

/** Copies the font files of the given families into dir. */
export function copyFonts(families, dir) {
  fs.mkdirSync(dir, { recursive: true });
  const ids = families.map((f) => FONTS[f]?.id).filter(Boolean);
  for (const file of fs.readdirSync(FONTS_DIR)) {
    if (ids.some((id) => file.startsWith(`${id}-`))) fs.copyFileSync(path.join(FONTS_DIR, file), path.join(dir, file));
  }
}

/** A Chrome or Edge on this computer, for turning HTML into PNG and PDF. */
export function findBrowser() {
  const env = process.env;
  const local = env.LOCALAPPDATA || "";
  const pf = env.PROGRAMFILES || "C:\\Program Files";
  const pf86 = env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)";
  const list = [
    env.CHROME_PATH,
    path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
    path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
    path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
    path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
    path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
  ].filter(Boolean);
  const hit = list.find((p) => fs.existsSync(p));
  if (!hit) {
    console.error("לא מצאתי Chrome או Edge במחשב. צריך אחד מהם כדי להפוך את העיצוב לתמונה.");
    process.exit(2);
  }
  return hit;
}

function runBrowser(args) {
  const browser = findBrowser();
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "studio-style-"));
  const res = spawnSync(browser, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--allow-file-access-from-files", `--user-data-dir=${profile}`, ...args],
  { encoding: "utf8", timeout: 120000 });
  try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 }); } catch {}
  return res;
}

/** HTML file → PNG. w/h in CSS pixels; scale multiplies the pixels (2 = sharp, 300 DPI print uses dpiScale). */
export function shot(html, out, { w, h, scale = 1, wait = 5000 } = {}) {
  out = path.resolve(out);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const res = runBrowser([`--force-device-scale-factor=${scale}`, `--window-size=${w},${h}`,
    `--virtual-time-budget=${wait}`, `--screenshot=${out}`, pathToFileURL(path.resolve(html)).href]);
  if (!fs.existsSync(out)) throw new Error(`הצילום לא נוצר: ${res.stderr || res.error}`);
  return out;
}

/** HTML file → PDF. The page size comes from @page in the HTML. Text stays text (sharp at any size). */
export function pdf(html, out, { wait = 5000 } = {}) {
  out = path.resolve(out);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const res = runBrowser(["--no-pdf-header-footer", `--virtual-time-budget=${wait}`, `--print-to-pdf=${out}`,
    pathToFileURL(path.resolve(html)).href]);
  if (!fs.existsSync(out)) throw new Error(`ה-PDF לא נוצר: ${res.stderr || res.error}`);
  return out;
}

/** 1 mm in CSS pixels, and the device scale that gives 300 DPI. */
export const MM = 96 / 25.4;
export const dpiScale = (dpi = 300) => dpi / 96;

/** Never overwrite: "x.png" → "x - 2.png" when x.png exists. */
export function freshPath(p) {
  if (!fs.existsSync(p)) return p;
  const ext = path.extname(p);
  const base = p.slice(0, -ext.length);
  for (let i = 2; ; i++) if (!fs.existsSync(`${base} - ${i}${ext}`)) return `${base} - ${i}${ext}`;
}

// ---------- colors ----------
const toRgb = (h) => {
  let x = String(h).trim().replace("#", "");
  if (x.length === 3) x = x.split("").map((c) => c + c).join("");
  return [0, 2, 4].map((i) => parseInt(x.slice(i, i + 2), 16));
};
const toHex = (rgb) => "#" + rgb.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("").toUpperCase();
export const mix = (a, b, t) => { const A = toRgb(a), B = toRgb(b); return toHex(A.map((v, i) => v + (B[i] - v) * t)); };
export const lum = (h) => { const [r, g, b] = toRgb(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
export const rgbOf = toRgb;

/** Reads brand.md (written by studio-ad): name, colors with roles, heading and text fonts. */
export function readBrand(dir = process.cwd()) {
  const file = ["brand.md", "מותג.md"].map((f) => path.join(dir, f)).find((f) => fs.existsSync(f));
  if (!file) return null;
  const text = fs.readFileSync(file, "utf8");
  const colors = [...text.matchAll(/^\|\s*([^|\n]+?)\s*\|\s*(#[0-9A-Fa-f]{6})\b/gm)].map((m) => ({ role: m[1], hex: m[2].toUpperCase() }));
  const name = text.match(/^-\s*שם:\s*(.+)$/m)?.[1]?.trim() || text.match(/^#\s*המותג של\s+(.+)$/m)?.[1]?.trim() || "";
  const fontIn = (label) => {
    const line = text.split("\n").find((l) => l.includes(label)) || "";
    return Object.keys(FONTS).find((f) => line.includes(f)) || null;
  };
  return { file, name, colors, head: fontIn("כותרות"), body: fontIn("טקסט") };
}

/** Turns a list of colors (with roles if known) into the 7 roles every sample uses. */
export function palette(colors) {
  const list = colors.map((c) => (typeof c === "string" ? { role: "", hex: c.toUpperCase() } : c));
  const take = (words) => { const i = list.findIndex((c) => words.some((w) => c.role.includes(w))); return i >= 0 ? list.splice(i, 1)[0].hex : null; };
  let bg = take(["רקע"]), ink = take(["ראשי", "טקסט", "כהה"]);
  take(["טקסט"]); // a second "text" row usually repeats the main color
  const named = { a1: take(["משני", "הדגשה"]), soft: take(["רך"]), light: take(["בהיר"]) };
  const rest = list.map((c) => c.hex).sort((a, b) => lum(a) - lum(b));
  if (!ink) ink = rest.shift() || "#24324A";
  if (!bg) bg = rest.pop() || "#F7F5F0";
  const a1 = named.a1 || rest.shift() || mix(ink, "#3E8FB0", 0.6);
  const a2 = rest.shift() || mix(a1, "#FFFFFF", 0.25);
  const a3 = rest.shift() || mix(a1, ink, 0.45);
  const soft = named.soft || mix(a1, bg, 0.55);
  const light = named.light || mix(a1, bg, 0.82);
  return { bg, ink, a1, a2, a3, soft, light };
}

export const DEFAULT_COLORS = ["#F6F2EA", "#24324A", "#3E7C8C", "#D9A05B", "#9FC5C8"];

export function parseArgs(argv) {
  const opts = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      const k = argv[i].slice(2);
      opts[k] = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : true;
    } else opts._.push(argv[i]);
  }
  return opts;
}
