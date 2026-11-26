#!/usr/bin/env node
// Lays a narration file over a finished video. The video stays as it is; music and sounds drop while the voice speaks.
//
//   node mix.mjs --video "סרטונים/פרסומת.mp4" --voice "קריינות/פתיח.mp3" --at 1 --out "סרטונים/פרסומת - עם קריינות.mp4"
//
// Options: --at <seconds> (when the voice starts, default 0), --hold (if the voice ends after the video,
// the last frame stays on screen until it finishes). A new version never overwrites an old one.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
function fail(msg) {
  console.error(msg);
  process.exit(1);
}

const video = opt("video");
const voice = opt("voice");
const outArg = opt("out");
const at = Number(opt("at", "0"));
if (!video || !voice || !outArg) fail("צריך --video, --voice ו---out.");
for (const f of [video, voice]) if (!fs.existsSync(f)) fail(`לא מצאתי את הקובץ "${f}".`);

function probe(file, entries, stream) {
  const a = ["-v", "error", ...(stream ? ["-select_streams", stream] : []), "-show_entries", entries, "-of", "csv=p=0", file];
  const r = spawnSync("ffprobe", a, { encoding: "utf8" });
  if (r.error) fail("FFmpeg לא נמצא. מריצות קודם: /studio-ad הכנה.");
  return r.stdout.trim();
}

const videoSeconds = Number(probe(video, "format=duration"));
const voiceSeconds = Number(probe(voice, "format=duration"));
const hasAudio = probe(video, "stream=codec_type", "a:0") === "audio";
const over = at + voiceSeconds - videoSeconds;
if (over > 0.05 && !args.includes("--hold")) {
  fail(`הקריינות ארוכה מהסרטון ב-${over.toFixed(1)} שניות. מקצרות את הטקסט, מקדימות את ההתחלה, או מוסיפות --hold כדי שהפריים האחרון יישאר.`);
}

const { dir, name, ext } = path.parse(outArg);
let out = outArg;
for (let n = 2; fs.existsSync(out); n++) out = path.join(dir, `${name} - ${n}${ext}`);
fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });

const delay = Math.round(at * 1000);
const hold = over > 0.05 ? over + 0.4 : 0;
const vo = `[1:a]aresample=48000,aformat=channel_layouts=stereo,adelay=${delay}:all=1,apad[vo]`;
const filters = [];
if (hasAudio) {
  // One steady dip under the whole narration: the sounds go down 0.6 s before the voice, stay low
  // (about -14 dB) through every pause between sentences, and come back over 1 s after the voice ends.
  // A sidechain here let the music jump back to full volume in each short pause.
  const LOW = 0.2, down0 = Math.max(0, at - 0.6), down1 = at, up0 = at + voiceSeconds, up1 = up0 + 1;
  const ramp = (a, b, from, to) => (b - a < 0.01 ? `${to}` : `${from}+(${to - from})*(t-${a.toFixed(3)})/${(b - a).toFixed(3)}`);
  const gain = `if(lt(t,${down0.toFixed(3)}),1,if(lt(t,${down1.toFixed(3)}),${ramp(down0, down1, 1, LOW)},` +
    `if(lt(t,${up0.toFixed(3)}),${LOW},if(lt(t,${up1.toFixed(3)}),${ramp(up0, up1, LOW, 1)},1))))`;
  filters.push(`[0:a]aresample=48000,aformat=channel_layouts=stereo,apad,volume='${gain}':eval=frame[duck]`, vo);
  filters.push(`[duck][vo]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]`);
} else {
  filters.push(vo.replace("[vo]", "[a]"));
}
if (hold) filters.push(`[0:v]tpad=stop_mode=clone:stop_duration=${hold.toFixed(2)}[v]`);

const ffArgs = ["-y", "-loglevel", "error", "-i", video, "-i", voice, "-filter_complex", filters.join(";")];
ffArgs.push("-map", hold ? "[v]" : "0:v:0", "-map", "[a]", "-t", (videoSeconds + hold).toFixed(3));
ffArgs.push(...(hold ? ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20"] : ["-c:v", "copy"]));
ffArgs.push("-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out);
const r = spawnSync("ffmpeg", ffArgs, { encoding: "utf8" });
if (r.status !== 0) fail(`FFmpeg לא הצליח לחבר את הקריינות. ${r.error?.message || r.stderr}`);
console.log(JSON.stringify({ ok: true, file: out, seconds: +(videoSeconds + hold).toFixed(1), voiceStarts: at, voiceEnds: +(at + voiceSeconds).toFixed(1), lastFrameHeld: +hold.toFixed(1) }));
