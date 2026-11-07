#!/usr/bin/env node
// Hebrew captions from a transcript (see transcribe.mjs): a board of styles to choose from, a fix for a wrong word,
// an SRT file for Premiere or DaVinci, and the captions burned into a new copy of the video.
//
//   node captions.mjs preview --video "<v>" --transcript "<t.json>" --style "a.json,b.json,c.json" --at 12.5 --out "<board.jpg>"
//   node captions.mjs fix --transcript "<t.json>" --find "מיכאל" --replace "מיכל" [--at 45.2]
//   node captions.mjs srt --transcript "<t.json>" --style "<s.json>" --out "<x.srt>"
//   node captions.mjs burn --video "<v>" --transcript "<t.json>" --style "<s.json>" --out "<o.mp4>"
//
// A style file holds only what differs from its preset. Presets: "status", "classic", "podcast".

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { args, baseName, clock, fail, ffmpeg, freePath, loadTranscript, probe, run, sameSource, sdrFilter, writeTranscript } from "./common.mjs";

const SKILL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FONT_CACHE = path.join(SKILL, "fonts");
const FILLERS = new Set(["אה", "אהה", "אההה", "אמ", "אממ", "אמממ", "הממ", "אה,", "אממ,", "אה.", "אממ."]);

// Sizes are in percent of the short side of the video, margins in percent of its height.
const PRESETS = {
  status: { font: "Heebo", bold: true, size: 8.5, color: "#FFFFFF", highlight: "#FFD84D", background: "outline", backColor: "#000000", backOpacity: 0.9, position: "bottom", margin: 24, maxWords: 3, maxChars: 18, lines: 1 },
  classic: { font: "Heebo", bold: true, size: 4.8, color: "#FFFFFF", highlight: null, background: "box", backColor: "#000000", backOpacity: 0.6, position: "bottom", margin: 7, maxWords: 0, maxChars: 40, lines: 1 },
  podcast: { font: "Heebo", bold: false, size: 4.4, color: "#FFFFFF", highlight: null, background: "box", backColor: "#000000", backOpacity: 0.7, position: "bottom", margin: 6, maxWords: 0, maxChars: 76, lines: 2 },
};
// Hebrew fonts from Google Fonts that are known to work. Any other Google font name works too.
const FONTS = ["Heebo", "Assistant", "Rubik", "Secular One", "Suez One", "Varela Round", "Karantina", "Noto Sans Hebrew", "Frank Ruhl Libre", "Alef"];

const { command, opt } = args();
if (!command) fail("צריך פקודה: preview, fix, srt או burn.");

function loadStyle(file, info) {
  const own = file ? JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "")) : {};
  const preset = PRESETS[own.preset || opt("preset", "classic")];
  if (!preset) fail(`אין סגנון בשם "${own.preset}". יש status, classic, podcast.`);
  const style = { ...preset, ...own };
  // A narrow (vertical) video fits fewer letters in a line.
  if (info?.vertical && !own.maxChars) style.maxChars = Math.round(style.maxChars * (own.preset === "podcast" ? 0.45 : 0.62));
  return style;
}

// ---- grouping the words into captions
function captionsOf(t, style) {
  const words = t.words.filter((w) => !FILLERS.has(w.w.replace(/[.,]$/, "")) && !FILLERS.has(w.w));
  const caps = [];
  let cur = [];
  const len = (list) => list.reduce((a, w) => a + w.w.length + 1, 0);
  words.forEach((w, i) => {
    const prev = words[i - 1];
    const full = (style.maxWords && cur.length >= style.maxWords) || (cur.length && len(cur) + w.w.length > style.maxChars);
    const pause = prev && w.s - prev.e > 0.6;
    const sentence = prev && /[.?!]$/.test(prev.w);
    const comma = prev && /,$/.test(prev.w) && len(cur) > style.maxChars * 0.45;
    const speaker = prev && w.spk && w.spk !== prev.spk;
    if (cur.length && (full || pause || sentence || comma || speaker)) {
      caps.push(cur);
      cur = [];
    }
    cur.push(w);
  });
  if (cur.length) caps.push(cur);
  return caps.map((ws, i) => {
    const next = caps[i + 1];
    let end = ws.at(-1).e + 0.35;
    if (next) end = Math.min(end, next[0].s - 0.04);
    if (next && next[0].s - end < 0.3) end = next[0].s - 0.04; // no flicker between close captions
    if (end - ws[0].s < 0.8) end = next ? Math.min(ws[0].s + 0.8, next[0].s - 0.04) : ws[0].s + 0.8;
    return { s: ws[0].s, e: Math.max(end, ws.at(-1).e), words: ws, spk: ws[0].spk };
  });
}

const clean = (w) => w.replace(/[.,;:]+$/, "");
const textOf = (words) => words.map((w) => clean(w.w)).join(" ");

// Two lines, split near the middle, for the podcast style.
function lineBreak(words, style) {
  if (style.lines < 2 || textOf(words).length <= style.maxChars / 2) return null;
  const total = textOf(words).length;
  let best = 1;
  let bestDiff = Infinity;
  for (let k = 1; k < words.length; k++) {
    const diff = Math.abs(textOf(words.slice(0, k)).length - total / 2);
    if (diff < bestDiff) [best, bestDiff] = [k, diff];
  }
  return best;
}

// ---- SRT
const srtTime = (x) => {
  const ms = Math.round(x * 1000);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(ms % 1000).padStart(3, "0")}`;
};
function srtOf(caps, style) {
  return caps
    .map((c, i) => {
      const k = lineBreak(c.words, style);
      const text = k ? `${textOf(c.words.slice(0, k))}\n${textOf(c.words.slice(k))}` : textOf(c.words);
      return `${i + 1}\n${srtTime(c.s)} --> ${srtTime(c.e)}\n${text}\n`;
    })
    .join("\n");
}

// ---- ASS (what FFmpeg burns into the picture)
const assColor = (hex, opacity = 1) => {
  const h = hex.replace("#", "");
  const a = Math.round((1 - opacity) * 255).toString(16).padStart(2, "0");
  return `&H${a}${h.slice(4, 6)}${h.slice(2, 4)}${h.slice(0, 2)}&`.toUpperCase();
};
const assTime = (x) => {
  const cs = Math.round(x * 100);
  return `${Math.floor(cs / 360000)}:${String(Math.floor((cs % 360000) / 6000)).padStart(2, "0")}:${String(Math.floor((cs % 6000) / 100)).padStart(2, "0")}.${String(cs % 100).padStart(2, "0")}`;
};
const RLM = "\u200F"; // starts every line right to left, even when it opens with a number or an English word

function assOf(caps, style, info, fontName) {
  const short = Math.min(info.width, info.height);
  const size = Math.round((style.size / 100) * short);
  const align = { bottom: 2, middle: 5, top: 8 }[style.position] || 2;
  const marginV = style.position === "middle" ? 0 : Math.round((style.margin / 100) * info.height);
  const marginH = Math.round(info.width * 0.06);
  let borderStyle = 1;
  let outline = 0;
  let shadow = 0;
  let outlineColor = assColor(style.backColor, style.backOpacity);
  let backColor = assColor(style.backColor, 0.5);
  if (style.background === "box") [borderStyle, outline] = [3, Math.round(size * 0.28)];
  if (style.background === "outline") [outline, shadow, backColor] = [Math.max(2, Math.round(size * 0.07)), Math.max(1, Math.round(size * 0.04)), assColor(style.backColor, 0.45)];
  if (style.background === "shadow") [shadow, outlineColor] = [Math.max(2, Math.round(size * 0.06)), assColor(style.backColor, 0)];
  const header = `[Script Info]
ScriptType: v4.00+
PlayResX: ${info.width}
PlayResY: ${info.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,${fontName},${size},${assColor(style.color)},${assColor(style.color)},${outlineColor},${backColor},${style.bold ? -1 : 0},0,0,0,100,100,0,0,${borderStyle},${outline},${shadow},${align},${marginH},${marginH},${marginV},177

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;
  const lines = [];
  for (const c of caps) {
    const base = style.speakerColors && c.spk ? style.speakerColors[(Number(c.spk) - 1) % style.speakerColors.length] : style.color;
    const k = lineBreak(c.words, style);
    const render = (hi) =>
      RLM +
      c.words
        .map((w, i) => {
          const word = clean(w.w).replace(/[{}\\]/g, "");
          const colored = i === hi ? `{\\1c${assColor(style.highlight)}}${word}{\\1c${assColor(base)}}` : word;
          return (k && i === k ? `\\N${RLM}` : i ? " " : "") + colored;
        })
        .join("");
    const lead = base !== style.color ? `{\\1c${assColor(base)}}` : "";
    if (style.highlight) {
      // The word being said changes colour: one event per word, the same text, so nothing jumps.
      c.words.forEach((w, i) => {
        const s = i === 0 ? c.s : w.s;
        const e = i === c.words.length - 1 ? c.e : c.words[i + 1].s;
        if (e > s) lines.push(`Dialogue: 0,${assTime(s)},${assTime(e)},Cap,,0,0,0,,${lead}${render(i)}`);
      });
    } else {
      lines.push(`Dialogue: 0,${assTime(c.s)},${assTime(c.e)},Cap,,0,0,0,,${lead}${render(-1)}`);
    }
  }
  return header + lines.join("\n") + "\n";
}

// ---- fonts: a TTF from Google Fonts, kept in the skill's "fonts" folder. Without internet: Arial.
async function ensureFont(name, bold) {
  fs.mkdirSync(FONT_CACHE, { recursive: true });
  for (const weight of bold ? [700, 400] : [400]) {
    const file = path.join(FONT_CACHE, `${name.replace(/\s+/g, "")}-${weight}.ttf`);
    if (fs.existsSync(file)) return { file, family: name, bold: weight === 700 };
    try {
      const css = await (await fetch(`https://fonts.googleapis.com/css2?family=${encodeURIComponent(name).replace(/%20/g, "+")}:wght@${weight}`)).text();
      const url = css.match(/url\((https:[^)]+\.ttf)\)/)?.[1];
      if (!url) continue;
      const bytes = Buffer.from(await (await fetch(url)).arrayBuffer());
      fs.writeFileSync(file, bytes);
      return { file, family: name, bold: weight === 700 };
    } catch {
      break;
    }
  }
  console.error(`לא הצלחתי להוריד את הגופן "${name}" מ-Google Fonts (אין אינטרנט, או שהשם לא נכון). ממשיך עם Arial.`);
  return { file: null, family: "Arial", bold };
}

// Everything FFmpeg reads sits in one work folder, with plain names, so no path ever needs escaping.
async function prepare(video, transcriptFile, styleFile, work) {
  const info = probe(video);
  const t = loadTranscript(transcriptFile);
  if (!sameSource(t, info)) console.error("שימי לב: התמלול נעשה על קובץ אחר (גודל או אורך שונים). אם הסרטון נערך, מתמללות שוב או משתמשות בתמלול שהעריכה כתבה.");
  const style = loadStyle(styleFile, info);
  if (t.timing === "approx" && style.highlight) console.error("שימי לב: התמלול נעשה במחשב, והזמן של כל מילה משוער. המילה הנדלקת יכולה להקדים או לאחר קצת. בשורות שלמות (קלאסי, פודקאסט) זה לא מורגש.");
  const font = await ensureFont(style.font, style.bold);
  fs.mkdirSync(path.join(work, "fonts"), { recursive: true });
  if (font.file) fs.copyFileSync(font.file, path.join(work, "fonts", path.basename(font.file)));
  const caps = captionsOf(t, { ...style, bold: font.bold });
  return { info, t, style: { ...style, bold: font.bold }, caps, fontName: font.family };
}

const subtitles = (assName) => `subtitles=${assName}:fontsdir=fonts`;

if (command === "fix") {
  const file = opt("transcript");
  const find = opt("find");
  const replace = opt("replace");
  if (!file || !find || replace === undefined) fail("צריך --transcript, --find ו---replace.");
  const t = loadTranscript(file);
  const at = opt("at") !== undefined ? Number(opt("at")) : null;
  const findWords = find.trim().split(/\s+/);
  let count = 0;
  for (let i = 0; i + findWords.length <= t.words.length; i++) {
    const slice = t.words.slice(i, i + findWords.length);
    const same = slice.every((w, k) => clean(w.w) === clean(findWords[k]));
    if (!same || (at !== null && Math.abs(slice[0].s - at) > 2)) continue;
    const tail = slice.at(-1).w.match(/[.,?!]$/)?.[0] || "";
    slice[0].w = replace.trim() + (/[.,?!]$/.test(replace) ? "" : tail);
    slice[0].e = slice.at(-1).e;
    t.words.splice(i + 1, findWords.length - 1);
    count++;
  }
  if (!count) fail(`לא מצאתי "${find}" בתמלול${at !== null ? ` ליד ${clock(at)}` : ""}.`);
  writeTranscript(file, t);
  console.log(JSON.stringify({ ok: true, replaced: count, find, replace }));
} else if (command === "srt") {
  const t = loadTranscript(opt("transcript"));
  const style = loadStyle(opt("style"), opt("video") ? probe(opt("video")) : null);
  const out = opt("out") || fail("חסר --out.");
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, "\uFEFF" + srtOf(captionsOf(t, style), style));
  console.log(JSON.stringify({ ok: true, file: out }));
} else if (command === "preview") {
  const video = opt("video");
  const out = opt("out");
  const styles = (opt("style") || "").split(",").filter(Boolean);
  if (!video || !out || !styles.length) fail("צריך --video, --transcript, --style (אחד או כמה, מופרדים בפסיק) ו---out.");
  const work = path.resolve(path.dirname(out), `_preview-${process.pid}`);
  fs.mkdirSync(work, { recursive: true });
  try {
    const frames = [];
    for (const [i, styleFile] of styles.entries()) {
      const p = await prepare(video, opt("transcript"), styleFile, work);
      const at = opt("at") !== undefined ? Number(opt("at")) : (p.caps[Math.min(2, p.caps.length - 1)].s + p.caps[Math.min(2, p.caps.length - 1)].e) / 2;
      fs.writeFileSync(path.join(work, `s${i}.ass`), assOf(p.caps, p.style, p.info, p.fontName));
      const label = fs.existsSync("C:/Windows/Fonts/arialbd.ttf") ? "C:/Windows/Fonts/arialbd.ttf" : null;
      if (label && i === 0) fs.copyFileSync(label, path.join(work, "label.ttf"));
      const num = label ? `,drawtext=fontfile=label.ttf:text='${i + 1}':x=w*0.04:y=w*0.04:fontsize=w*0.09:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=w*0.02` : "";
      const scale = p.info.vertical ? "scale=-2:900" : "scale=900:-2";
      run("ffmpeg", ["-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-ss", String(at), "-copyts", "-i", path.resolve(video), "-frames:v", "1", "-vf", `${sdrFilter(p.info)},${subtitles(`s${i}.ass`)},${scale}${num}`, "-q:v", "3", "-strict", "unofficial", `f${i}.jpg`], { cwd: work });
      if (!fs.existsSync(path.join(work, `f${i}.jpg`))) fail("לא הצלחתי ליצור תמונה עם כתוביות. מריצים שוב, ואם זה חוזר: FFmpeg בלי libass.");
      frames.push(`f${i}.jpg`);
    }
    const inputs = frames.flatMap((f) => ["-i", f]);
    const stack = frames.length > 1 ? `${frames.map((_, i) => `[${i}:v]pad=iw+16:ih+16:8:8:white[p${i}]`).join(";")};${frames.map((_, i) => `[p${frames.length - 1 - i}]`).join("")}hstack=inputs=${frames.length}` : "pad=iw+16:ih+16:8:8:white";
    run("ffmpeg", ["-hide_banner", "-nostdin", "-y", "-loglevel", "error", ...inputs, "-filter_complex", stack, "-q:v", "3", "-strict", "unofficial", "board.jpg"], { cwd: work });
    fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
    fs.copyFileSync(path.join(work, "board.jpg"), out);
    console.log(JSON.stringify({ ok: true, file: out, styles: styles.length, note: "סגנון 1 מימין" }));
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
  }
} else if (command === "burn") {
  const video = opt("video");
  const outArg = opt("out");
  if (!video || !outArg || !opt("transcript")) fail("צריך --video, --transcript, --style ו---out.");
  const work = path.resolve("כתוביות", baseName(video));
  fs.mkdirSync(work, { recursive: true });
  const p = await prepare(video, opt("transcript"), opt("style"), work);
  fs.writeFileSync(path.join(work, "captions.ass"), assOf(p.caps, p.style, p.info, p.fontName));
  const srt = path.resolve("כתוביות", `${baseName(video)}.srt`);
  fs.writeFileSync(srt, "\uFEFF" + srtOf(p.caps, p.style));
  const out = path.resolve(freePath(outArg));
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const started = Date.now();
  ffmpeg(["-y", "-loglevel", "error", "-i", path.resolve(video), "-vf", `${sdrFilter(p.info)},${subtitles("captions.ass")}`, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", out], { cwd: work });
  console.log(JSON.stringify({ ok: true, file: path.relative(process.cwd(), out), srt: path.relative(process.cwd(), srt), captions: p.caps.length, font: p.fontName, seconds: Math.round((Date.now() - started) / 1000) }));
} else {
  fail(`אין פקודה בשם "${command}". יש preview, fix, srt, burn.`);
}
