#!/usr/bin/env node
// Looks at a whole video before the analysis: frames along the way, the cuts between shots, loudness and silences.
// Writes to "ניתוח/<name>/": scan.json, frames/ (one picture every few seconds), and sheet-N.jpg
// (12 frames on one page, each with its time), so the whole video can be seen in a few pictures.
//
//   node scan.mjs --video "סרטונים/הפודקאסט.mp4" [--frames 24]

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { args, baseName, clock, fail, ffmpeg, probe, run } from "./common.mjs";

const { opt } = args();
const video = opt("video");
if (!video) fail("חסר --video: איזה סרטון לבדוק.");
const info = probe(video);
if (!info.hasVideo) fail("זה קובץ שמע, בלי תמונה. לניתוח של שמע בלבד: מתמללות, וקוראות את התמלול.");
const work = path.resolve(opt("dir", path.join("ניתוח", baseName(video))));
const framesDir = path.join(work, "frames");
fs.rmSync(framesDir, { recursive: true, force: true });
fs.mkdirSync(framesDir, { recursive: true });

// A font for the time labels: copied next to the frames, so FFmpeg gets a plain relative path.
const FONTS = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"];
const fontSrc = FONTS.find((f) => fs.existsSync(f));
if (fontSrc) fs.copyFileSync(fontSrc, path.join(framesDir, "label.ttf"));

// 1. Frames, spread evenly. Long videos get more frames, up to 48.
const wanted = Number(opt("frames", Math.round(Math.min(48, Math.max(12, info.duration / 8)))));
const step = info.duration / wanted;
const long = 480;
const scale = info.vertical ? `scale=-2:${long}` : `scale=${long}:-2`;
const frames = [];
for (let i = 0; i < wanted; i++) {
  const t = Math.min(info.duration - 0.1, step * (i + 0.5));
  const name = `f${String(i + 1).padStart(3, "0")}.jpg`;
  const label = clock(t).replace(/:/g, "\\:");
  const draw = fontSrc ? `,drawtext=fontfile=label.ttf:text='${label}':x=10:y=10:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6` : "";
  const r = run("ffmpeg", ["-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-ss", t.toFixed(2), "-i", path.resolve(video), "-frames:v", "1", "-vf", scale + draw, "-q:v", "4", "-strict", "unofficial", name], { cwd: framesDir });
  if (r.ok && fs.existsSync(path.join(framesDir, name))) frames.push({ file: `frames/${name}`, t: +t.toFixed(2) });
}
if (!frames.length) fail("לא הצלחתי להוציא תמונות מהסרטון. ייתכן שהקובץ פגום.");
fs.rmSync(path.join(framesDir, "label.ttf"), { force: true });

// 2. Sheets: 12 frames per page (4 by 3), for one quick look at the whole video.
for (const old of fs.readdirSync(work).filter((f) => /^sheet-\d+\.jpg$/.test(f))) fs.rmSync(path.join(work, old));
const sheets = [];
const perSheet = 12;
for (let k = 0; k * perSheet < frames.length; k++) {
  const group = frames.slice(k * perSheet, (k + 1) * perSheet);
  const list = path.join(os.tmpdir(), `sheet-${process.pid}-${k}.txt`);
  fs.writeFileSync(list, group.map((f) => `file '${path.join(work, f.file).replace(/\\/g, "/").replace(/'/g, "'\\''")}'`).join("\n"));
  const name = `sheet-${k + 1}.jpg`;
  run("ffmpeg", ["-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-vf", "tile=4x3:padding=6:margin=6:color=white", "-frames:v", "1", "-q:v", "4", "-strict", "unofficial", name], { cwd: work });
  fs.rmSync(list, { force: true });
  if (fs.existsSync(path.join(work, name))) sheets.push({ file: name, from: group[0].t, to: group.at(-1).t });
}

// 3. Cuts between shots (scene changes), on a small copy of the picture so it runs fast.
const sc = run("ffmpeg", ["-hide_banner", "-nostdin", "-i", path.resolve(video), "-an", "-vf", "scale=160:-2,select='gt(scene,0.32)',showinfo", "-f", "null", "-"]);
const cuts = [...sc.err.matchAll(/pts_time:([\d.]+)/g)].map((m) => +Number(m[1]).toFixed(2));

// 4. Sound: overall loudness, peaks, and silences longer than a second.
let audio = null;
if (info.hasAudio) {
  const a = run("ffmpeg", ["-hide_banner", "-nostdin", "-i", path.resolve(video), "-vn", "-af", "silencedetect=n=-38dB:d=1,ebur128=peak=true", "-f", "null", "-"]);
  const summary = a.err.slice(a.err.lastIndexOf("Summary:"));
  const num = (re) => {
    const m = summary.match(re);
    return m ? Number(m[1]) : null;
  };
  const starts = [...a.err.matchAll(/silence_start: ([\d.]+)/g)].map((m) => Number(m[1]));
  const ends = [...a.err.matchAll(/silence_end: ([\d.]+) \| silence_duration: ([\d.]+)/g)].map((m) => ({ e: Number(m[1]), d: Number(m[2]) }));
  const silences = starts.map((s, i) => ({ s: +s.toFixed(1), e: +(ends[i]?.e ?? info.duration).toFixed(1), d: +(ends[i]?.d ?? info.duration - s).toFixed(1) }));
  audio = {
    loudnessLUFS: num(/I:\s+(-?[\d.]+) LUFS/),
    peakDBFS: num(/Peak:\s+(-?[\d.]+) dBFS/),
    rangeLU: num(/LRA:\s+([\d.]+) LU/),
    silences,
    silentSeconds: +silences.reduce((acc, x) => acc + x.d, 0).toFixed(1),
  };
}

const scan = {
  video: path.relative(work, path.resolve(video)).replace(/\\/g, "/"),
  name: path.basename(video),
  length: clock(info.duration),
  duration: +info.duration.toFixed(2),
  size: `${info.width}x${info.height}`,
  orientation: info.vertical ? "אנכי" : info.width === info.height ? "ריבוע" : "רוחבי",
  fps: +info.fps.toFixed(2),
  hdr: info.hdr,
  megabytes: +(info.size / 1048576).toFixed(1),
  shots: { cuts: cuts.length, averageShotSeconds: +(info.duration / (cuts.length + 1)).toFixed(1), times: cuts },
  audio,
  frames,
  sheets,
};
fs.writeFileSync(path.join(work, "scan.json"), JSON.stringify(scan, null, 1));

const tips = [];
if (audio?.loudnessLUFS != null && audio.loudnessLUFS < -24) tips.push("הצליל שקט מהרגיל");
if (audio?.loudnessLUFS != null && audio.loudnessLUFS > -10) tips.push("הצליל חזק מאוד");
if (audio?.peakDBFS != null && audio.peakDBFS > -0.5) tips.push("יש רגעים שהצליל נשרף (מגיע לתקרה)");
if (info.hdr) tips.push("סרטון HDR (צבעים מורחבים): בעריכה הצבעים יומרו לרגילים");
console.log(JSON.stringify({
  ok: true,
  dir: work,
  sheets: sheets.map((s) => path.join(work, s.file)),
  length: scan.length,
  size: scan.size,
  orientation: scan.orientation,
  cuts: cuts.length,
  averageShotSeconds: scan.shots.averageShotSeconds,
  loudnessLUFS: audio?.loudnessLUFS,
  silentSeconds: audio?.silentSeconds,
  notes: tips,
}));
