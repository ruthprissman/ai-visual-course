// Shared helpers for the video skills (video-insights, video-captions, video-cut).
// The same file sits in each skill's scripts folder, so every skill installs on its own.
// No packages: only Node 22 and FFmpeg.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export function fail(msg) {
  console.error(msg);
  process.exit(1);
}

export function args() {
  const list = process.argv.slice(2);
  const opt = (name, fallback) => {
    const i = list.indexOf(`--${name}`);
    return i >= 0 && list[i + 1] !== undefined && !list[i + 1].startsWith("--") ? list[i + 1] : fallback;
  };
  const flag = (name) => list.includes(`--${name}`);
  return { list, opt, flag, command: list[0] && !list[0].startsWith("--") ? list[0] : null };
}

// Runs FFmpeg or FFprobe and returns stdout and stderr. FFmpeg writes its reports to stderr.
export function run(tool, argv, { cwd, quiet = true } = {}) {
  const r = spawnSync(tool, argv, { cwd, encoding: "utf8", maxBuffer: 1 << 28 });
  if (r.error?.code === "ENOENT") fail(`${tool} לא נמצא במחשב. מריצות קודם: /studio-ad הכנה (מתקין את FFmpeg).`);
  if (r.status !== 0 && !quiet) fail(`${tool} נכשל:\n${(r.stderr || "").slice(-1500)}`);
  return { ok: r.status === 0, out: r.stdout || "", err: r.stderr || "" };
}

export function ffmpeg(argv, opts = {}) {
  return run("ffmpeg", ["-hide_banner", "-nostdin", ...argv], { quiet: false, ...opts });
}

// What the video really is: size after phone rotation, length, frame rate, sound, and HDR.
export function probe(file) {
  if (!fs.existsSync(file)) fail(`לא מצאתי את הקובץ "${file}".`);
  const r = run("ffprobe", ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", file]);
  if (!r.ok) fail(`לא הצלחתי לקרוא את "${file}". זה קובץ וידאו או שמע?`);
  const j = JSON.parse(r.out);
  const v = j.streams.find((s) => s.codec_type === "video" && !s.disposition?.attached_pic);
  const a = j.streams.find((s) => s.codec_type === "audio");
  let width = v?.width || 0;
  let height = v?.height || 0;
  const rot = Number(v?.side_data_list?.find((d) => d.rotation !== undefined)?.rotation ?? v?.tags?.rotate ?? 0);
  if (Math.abs(rot) % 180 === 90) [width, height] = [height, width];
  const [n, d] = (v?.avg_frame_rate || "0/1").split("/").map(Number);
  const fps = d ? n / d : 0;
  return {
    file,
    duration: Number(j.format.duration || v?.duration || a?.duration || 0),
    size: Number(j.format.size || 0),
    width,
    height,
    fps: fps > 0 && fps < 121 ? fps : 30,
    hasVideo: !!v,
    hasAudio: !!a,
    hdr: ["arib-std-b67", "smpte2084"].includes(v?.color_transfer),
    vertical: height > width,
  };
}

// iPhone HDR videos look washed out once saved as a normal video. This brings them back to normal colours.
export function sdrFilter(info) {
  return info.hdr
    ? "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
    : "format=yuv420p";
}

export function clock(sec, { ms = false } = {}) {
  const s = Math.max(0, sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const sPart = ms ? r.toFixed(1).padStart(4, "0") : String(Math.floor(r)).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sPart}` : `${String(m).padStart(2, "0")}:${sPart}`;
}

// "1:05", "01:05.4", "1:02:03", "65" -> seconds
export function seconds(text) {
  const t = String(text).trim();
  if (/^\d+(\.\d+)?$/.test(t)) return Number(t);
  const parts = t.split(":").map(Number);
  if (parts.some(Number.isNaN)) fail(`לא הבנתי את הזמן "${text}". כותבים כך: 1:05 או 01:05.4`);
  return parts.reduce((acc, p) => acc * 60 + p, 0);
}

// A new version never overwrites an old one: "x.mp4", "x - 2.mp4", ...
export function freePath(file) {
  if (!fs.existsSync(file)) return file;
  const { dir, name, ext } = path.parse(file);
  for (let n = 2; ; n++) {
    const next = path.join(dir, `${name} - ${n}${ext}`);
    if (!fs.existsSync(next)) return next;
  }
}

export function baseName(file) {
  return path.parse(file).name;
}

// Keys live in a text file in the open folder. They are read here and never printed.
export function readKey(file) {
  if (!fs.existsSync(file)) return null;
  const key = fs.readFileSync(file, "utf8").replace(/^﻿/, "").trim();
  if (!key) fail(`הקובץ "${file}" ריק. מדביקות בו את המפתח, ושומרות (Ctrl+S).`);
  if (/\s/.test(key)) fail(`בקובץ "${file}" צריך להיות רק המפתח, בשורה אחת, בלי מילים נוספות.`);
  return key;
}

export const KEY_FILES = { elevenlabs: "מפתח ElevenLabs.txt", google: "מפתח Google.txt" };

export function netError(e, service) {
  const why = `${e.cause?.code || ""} ${e.cause?.message || e.message}`;
  if (/CERT|SELF_SIGNED|ISSUER/i.test(why)) {
    fail("רשת מסוננת: Node צריך את תעודת הסינון (NODE_EXTRA_CA_CERTS). זה תפקיד של מי שאחראית על המחשב. לא מכבים בדיקת אבטחה.");
  }
  fail(`אין חיבור ל-${service} (${why.trim()}). בודקות אינטרנט, ושהאתר פתוח בסינון.`);
}

// ---- transcripts: one JSON per video in "תמלולים/", shared by the three skills
export const TRANSCRIPTS = "תמלולים";

export function transcriptPath(video, dir = TRANSCRIPTS) {
  return path.join(dir, `${baseName(video)}.json`);
}

export function loadTranscript(file) {
  if (!fs.existsSync(file)) fail(`לא מצאתי תמלול: "${file}". קודם מתמללות.`);
  const t = JSON.parse(fs.readFileSync(file, "utf8"));
  if (!Array.isArray(t.words)) fail(`הקובץ "${file}" הוא לא תמלול של הסקילים האלה.`);
  return t;
}

// Lines for reading: a new line after a sentence ends, a pause, a speaker change, or a long line.
export function transcriptLines(words, { maxWords = 22, pause = 0.8 } = {}) {
  const lines = [];
  let cur = [];
  words.forEach((w, i) => {
    const prev = words[i - 1];
    const breakHere = cur.length && (cur.length >= maxWords || w.s - prev.e > pause || (w.spk && w.spk !== prev.spk) || /[.?!]$/.test(prev.w));
    if (breakHere) {
      lines.push(cur);
      cur = [];
    }
    cur.push(w);
  });
  if (cur.length) lines.push(cur);
  return lines;
}

export function writeTranscript(file, t) {
  fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(t, null, 1));
  const speakers = new Set(t.words.map((w) => w.spk).filter(Boolean)).size > 1;
  const body = transcriptLines(t.words)
    .map((line) => {
      const who = speakers ? `(דובר/ת ${line[0].spk}) ` : "";
      return `[${clock(line[0].s, { ms: true })}–${clock(line.at(-1).e, { ms: true })}] ${who}${line.map((w) => w.w).join(" ")}`;
    })
    .join("\n");
  const head = `תמלול: ${path.basename(t.source.file)} · ${clock(t.source.duration)} · ${t.words.length} מילים · ${t.engine}\n`;
  const txt = file.replace(/\.json$/, ".txt");
  fs.writeFileSync(txt, "﻿" + head + "\n" + body + "\n");
  return txt;
}

// The transcript belongs to this exact file (same size and length)?
export function sameSource(t, info) {
  return t?.source && t.source.size === info.size && Math.abs(t.source.duration - info.duration) < 0.5;
}
