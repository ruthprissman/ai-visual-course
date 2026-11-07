#!/usr/bin/env node
// Hebrew transcript with a time for every word, from a video or a sound file. Three engines:
//   local       on the computer itself, with FFmpeg's built-in Whisper and ivrit-ai's Hebrew model. Free, no key,
//               nothing leaves the computer. Downloads the model once (1.6 GB). Slow: about 1.5x the length of the video.
//   elevenlabs  ElevenLabs Scribe, with "מפתח ElevenLabs.txt". The most accurate, fast, writes "אה". 330 credits a minute.
//   google      Gemini Transcribe, with "מפתח Google.txt". Up to 30 minutes, a daily limit.
// The transcript goes to "תמלולים/<name>.json" (for the skills) and ".txt" (for reading).
//
//   node transcribe.mjs --video "סרטונים/הפודקאסט.mp4" [--engine local|elevenlabs|google] [--speakers] [--force]
//   node transcribe.mjs --video "..." --estimate     how long, what it costs, what is ready. Sends nothing.
//
// The same file sits in the three video skills.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { KEY_FILES, TRANSCRIPTS, args, clock, fail, ffmpeg, loadTranscript, netError, probe, readKey, run, sameSource, transcriptPath, writeTranscript } from "./common.mjs";

const EL_CREDITS_PER_MINUTE = 330;
const GOOGLE_MAX_MINUTES = 30;
const LOCAL_SPEED = 1.6; // minutes of work per minute of video, measured on a strong computer; slower ones take longer
// The local model lives once per computer, outside the studio folder. A copy from a USB stick can go in "מודל תמלול/".
const MODEL_DIR = path.join(os.homedir(), ".claude", "whisper");
const USB_DIR = "מודל תמלול";
const LOCAL = {
  model: { file: "ivrit-turbo.bin", url: "https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ggml/resolve/main/ggml-model.bin", size: 1624555275, usb: ["ggml-model.bin", "ivrit-turbo.bin"] },
  vad: { file: "silero-vad.bin", url: "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin", size: 885098, usb: ["ggml-silero-v5.1.2.bin", "silero-vad.bin"] },
};
const localReady = () => Object.values(LOCAL).every((m) => fs.existsSync(path.join(MODEL_DIR, m.file)) && fs.statSync(path.join(MODEL_DIR, m.file)).size === m.size);
const hasWhisper = () => /\bwhisper\b/.test(run("ffmpeg", ["-hide_banner", "-filters"]).out);

const { opt, flag } = args();
const video = opt("video");
if (!video) fail("חסר --video: איזה סרטון לתמלל.");
const info = probe(video);
if (!info.hasAudio) fail("אין בסרטון הזה צליל, אז אין מה לתמלל.");
const outFile = opt("out", transcriptPath(video, opt("dir", TRANSCRIPTS)));
const minutes = info.duration / 60;
const keys = {
  elevenlabs: fs.existsSync(KEY_FILES.elevenlabs),
  google: fs.existsSync(KEY_FILES.google),
};

if (flag("estimate")) {
  const existing = fs.existsSync(outFile) && sameSource(loadTranscript(outFile), info);
  console.log(JSON.stringify({
    file: video,
    length: clock(info.duration),
    minutes: +minutes.toFixed(1),
    alreadyTranscribed: existing ? outFile : false,
    keys,
    local: { modelInstalled: localReady(), ffmpegHasWhisper: hasWhisper(), downloadGB: localReady() ? 0 : 1.6, minutesOfWork: +(minutes * LOCAL_SPEED).toFixed(1) },
    elevenlabsCredits: Math.ceil(minutes * EL_CREDITS_PER_MINUTE),
    elevenlabsFreeMonth: 10000,
    googleOk: minutes <= GOOGLE_MAX_MINUTES,
    googleRequests: 1,
  }));
  process.exit(0);
}

if (!flag("force") && fs.existsSync(outFile) && sameSource(loadTranscript(outFile), info)) {
  console.log(JSON.stringify({ ok: true, reused: true, file: outFile, text: outFile.replace(/\.json$/, ".txt") }));
  process.exit(0);
}

let engine = opt("engine", keys.elevenlabs ? "elevenlabs" : localReady() ? "local" : keys.google ? "google" : null);
if (!engine) {
  fail(`אין עדיין דרך לתמלל. אפשר אחת מהשלוש:\n- במחשב, בחינם ובלי מפתח: --engine local (הורדה חד-פעמית של 1.6GB, ואיטי).\n- "${KEY_FILES.elevenlabs}": מפתח של ElevenLabs, עם Access ל-Speech to Text. הכי מדויק.\n- "${KEY_FILES.google}": מפתח של Google AI Studio.`);
}
if (!["local", "elevenlabs", "google"].includes(engine)) fail(`אין מנוע בשם "${engine}". אפשר local, elevenlabs או google.`);
let key = null;
if (engine !== "local") {
  key = readKey(KEY_FILES[engine]);
  if (!key) fail(`ביקשת ${engine}, אבל אין בתיקייה את הקובץ "${KEY_FILES[engine]}".`);
}
if (engine === "google" && minutes > GOOGLE_MAX_MINUTES) {
  fail(`Google מתמללת עם זמנים רק עד ${GOOGLE_MAX_MINUTES} דקות, והקובץ ${clock(info.duration)}. מקצרות קודם (/video-cut), או מתמללות ב-ElevenLabs.`);
}

// Only the voice is used: mono, 16 kHz. A 20-minute video becomes a small file.
const tmp = path.join(os.tmpdir(), `transcribe-${process.pid}.${engine === "local" ? "wav" : "mp3"}`);
ffmpeg(["-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", ...(engine === "local" ? [] : ["-c:a", "libmp3lame", "-b:a", "48k"]), tmp]);
const speakers = flag("speakers") && engine !== "local";
if (flag("speakers") && engine === "local") console.error("בתמלול במחשב אין הפרדה בין דוברים. ממשיך בלי.");
let words;
try {
  words = engine === "elevenlabs" ? await elevenlabs(tmp) : engine === "google" ? await google(tmp) : await local(tmp);
} finally {
  fs.rmSync(tmp, { force: true });
}
if (!words.length) fail("התמלול חזר ריק. יש דיבור בסרטון? אם יש, בודקות שהצליל לא שקט מדי.");

const transcript = {
  version: 1,
  engine: { elevenlabs: "ElevenLabs Scribe", google: "Google Gemini Transcribe", local: "Whisper במחשב (ivrit-ai)" }[engine],
  language: "he",
  ...(engine === "local" ? { timing: "approx" } : {}),
  created: new Date().toISOString(),
  source: { file: path.basename(video), size: info.size, duration: info.duration },
  speakers,
  words,
};
const txt = writeTranscript(outFile, transcript);
const nSpeakers = new Set(words.map((w) => w.spk).filter(Boolean)).size;
// Letters from another alphabet inside a Hebrew word are a transcription slip: shown to her before captions.
const suspicious = [...new Set(words.filter((w) => /[\u0600-\u06FF]/.test(w.w) || (/[\u05D0-\u05EA]/.test(w.w) && /[A-Za-z]/.test(w.w))).map((w) => `${clock(w.s)} ${w.w}`))].slice(0, 20);
console.log(JSON.stringify({
  ok: true,
  file: outFile,
  text: txt,
  words: words.length,
  length: clock(info.duration),
  wordsPerMinute: Math.round(words.length / Math.max(minutes, 0.1)),
  speakers: nSpeakers || undefined,
  engine: transcript.engine,
  credits: engine === "elevenlabs" ? Math.ceil(minutes * EL_CREDITS_PER_MINUTE) : 0,
  ...(engine === "local" ? { note: "בתמלול במחשב הזמן של כל מילה משוער (לפי המשפט), ו\"אה\" לא נכתב." } : {}),
  ...(suspicious.length ? { suspicious } : {}),
}));

async function elevenlabs(file) {
  const form = new FormData();
  form.append("model_id", "scribe_v2");
  form.append("language_code", "heb");
  form.append("timestamps_granularity", "word");
  form.append("tag_audio_events", "false");
  form.append("diarize", speakers ? "true" : "false");
  form.append("file", await fs.openAsBlob(file, { type: "audio/mpeg" }), "audio.mp3");
  let res;
  try {
    res = await fetch("https://api.elevenlabs.io/v1/speech-to-text", { method: "POST", headers: { "xi-api-key": key }, body: form });
  } catch (e) {
    netError(e, "ElevenLabs");
  }
  const raw = await res.text();
  if (!res.ok) {
    if (/missing_permissions/i.test(raw)) fail("למפתח אין הרשאה לתמלול: בעמוד המפתחות של ElevenLabs מסמנות Access ליד Speech to Text, או יוצרות מפתח חדש.");
    if (res.status === 401) fail("המפתח של ElevenLabs לא נכון, או שפג תוקפו. יוצרות חדש, ושומרות אותו בקובץ.");
    if (/quota|credit/i.test(raw)) fail(`נגמרו הנקודות ב-ElevenLabs, או שהגעתן לתקרה של המפתח. התמלול הזה צריך בערך ${Math.ceil(minutes * EL_CREDITS_PER_MINUTE)} נקודות.`);
    if (res.status === 429) fail("ElevenLabs עמוסה, או יותר מדי בקשות. מחכים דקה, ומנסים שוב.");
    fail(`ElevenLabs החזירה שגיאה ${res.status}: ${raw.slice(0, 300)}`);
  }
  const data = JSON.parse(raw);
  return (data.words || [])
    .filter((w) => w.type === "word" && w.text.trim())
    .map((w) => ({ w: w.text.trim(), s: +w.start.toFixed(3), e: +w.end.toFixed(3), ...(speakers && w.speaker_id ? { spk: String(Number(String(w.speaker_id).replace(/\D/g, "") || 0) + 1) } : {}) }));
}

async function google(file) {
  const mode = { type: "verbatim", timestamp_granularities: ["word"] };
  if (speakers) mode.diarization_mode = "speaker";
  const body = {
    model: "gemini-3.5-transcribe",
    input: [{ type: "audio", data: fs.readFileSync(file).toString("base64"), mime_type: "audio/mp3" }],
    generation_config: { transcription_config: { mode } },
  };
  for (let attempt = 1; ; attempt++) {
    let res;
    try {
      res = await fetch("https://generativelanguage.googleapis.com/v1beta/interactions", {
        method: "POST",
        headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (e) {
      netError(e, "Google");
    }
    const raw = await res.text();
    if (res.ok) {
      const data = JSON.parse(raw);
      const parts = (data.steps || []).flatMap((s) => s.content || []).filter((c) => c.type === "text");
      const spk = {};
      return parts
        .flatMap((c) => c.annotations || [])
        .filter((a) => a.type === "word_info" && a.text?.trim())
        .map((a) => {
          const word = { w: a.text.trim(), s: +parseFloat(a.start_offset).toFixed(3), e: +parseFloat(a.end_offset).toFixed(3) };
          if (speakers && a.speaker) word.spk = spk[a.speaker] ||= String(Object.keys(spk).length + 1);
          return word;
        });
    }
    let message = raw.slice(0, 300);
    try {
      message = JSON.parse(raw).error?.message || message;
    } catch {}
    if (res.status === 429 && /per.?day|daily/i.test(message)) fail("נגמרה המכסה היומית של Google לתמלול. ממשיכות מחר, או מתמללות ב-ElevenLabs.");
    if ((res.status === 429 || res.status >= 500) && attempt < 4) {
      console.error(`Google עמוסה. מחכה ${20 * attempt} שניות ומנסה שוב.`);
      await new Promise((r) => setTimeout(r, 20000 * attempt));
      continue;
    }
    if (res.status === 400 && /api key/i.test(message)) fail("המפתח של Google לא תקין. בודקות שהועתק עד הסוף, ושהקובץ נשמר.");
    if (res.status === 402) fail("נגמר הקרדיט בחשבון Google. קונות עוד ב-aistudio.google.com/billing, או עוברות ל-ElevenLabs.");
    fail(`Google החזירה שגיאה ${res.status}: ${message}`);
  }
}

// ---- on the computer: FFmpeg's built-in Whisper with ivrit-ai's Hebrew model
async function local(file) {
  if (!hasWhisper()) fail("ה-FFmpeg במחשב הזה בלי Whisper (צריך FFmpeg 8 ומעלה, בגרסה המלאה). ב-Windows: winget install --id Gyan.FFmpeg -e. אחרת מתמללות ב-ElevenLabs.");
  fs.mkdirSync(MODEL_DIR, { recursive: true });
  for (const m of Object.values(LOCAL)) await ensureModel(m);
  // FFmpeg reads the model by a plain name from its own folder, so no path in the filter needs escaping.
  const out = `tx-${process.pid}.json`;
  console.error(`מתמלל במחשב. זה לוקח בערך ${Math.max(1, Math.round(minutes * LOCAL_SPEED))} דקות, ובמחשב חלש יותר גם יותר. לא סוגרים את החלון.`);
  try {
    const r = run("ffmpeg", ["-hide_banner", "-nostdin", "-loglevel", "error", "-i", path.resolve(file), "-af", `whisper=model=${LOCAL.model.file}:language=he:queue=5:destination=${out}:format=json:vad_model=${LOCAL.vad.file}`, "-f", "null", "-"], { cwd: MODEL_DIR });
    const outPath = path.join(MODEL_DIR, out);
    if (!r.ok || !fs.existsSync(outPath)) fail(`התמלול במחשב נכשל. ${r.err.slice(-400)}`);
    const segments = fs.readFileSync(outPath, "utf8").split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l));
    // Whisper gives a time for each short sentence. Inside it, every word gets a share by its length.
    const words = [];
    segments.forEach((seg, g) => {
      const parts = seg.text.trim().split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
      const s0 = seg.start / 1000;
      const span = Math.max(0.1, seg.end / 1000 - s0);
      const weights = parts.map((w) => w.length + 1);
      const total = weights.reduce((a, b) => a + b, 0);
      let acc = 0;
      parts.forEach((w, i) => {
        const s = s0 + (acc / total) * span;
        acc += weights[i];
        words.push({ w: w.replace(/[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g, "").replace(/^\.+/, ""), s: +s.toFixed(3), e: +(s0 + (acc / total) * span - 0.02).toFixed(3), g });
      });
    });
    return words;
  } finally {
    fs.rmSync(path.join(MODEL_DIR, out), { force: true });
  }
}

async function ensureModel(m) {
  const dest = path.join(MODEL_DIR, m.file);
  if (fs.existsSync(dest) && fs.statSync(dest).size === m.size) return;
  const usb = m.usb.map((n) => path.join(USB_DIR, n)).find((f) => fs.existsSync(f) && fs.statSync(f).size === m.size);
  if (usb) {
    console.error(`מעתיק את ${path.basename(usb)} מהתיקייה "${USB_DIR}"...`);
    fs.copyFileSync(usb, dest);
    return;
  }
  console.error(`מוריד את ${m.file} (${m.size > 1e8 ? (m.size / 1e9).toFixed(1) + "GB" : Math.round(m.size / 1e3) + "KB"}), פעם אחת בלבד במחשב הזה...`);
  const part = `${dest}.part`;
  let res;
  try {
    res = await fetch(m.url);
  } catch (e) {
    netError(e, "Hugging Face");
  }
  if (!res.ok) fail(`ההורדה נכשלה (${res.status}). בודקות ש-huggingface.co פתוח בסינון, או מעתיקות את המודל מדיסק-און-קי לתיקייה "${USB_DIR}".`);
  let got = 0;
  let shown = 0;
  const counter = new TransformStream({
    transform(chunk, ctl) {
      got += chunk.length;
      const pct = Math.floor((got / m.size) * 100);
      if (m.size > 1e8 && pct >= shown + 10) {
        shown = pct - (pct % 10);
        console.error(`  ${shown}%`);
      }
      ctl.enqueue(chunk);
    },
  });
  await pipeline(Readable.fromWeb(res.body.pipeThrough(counter)), fs.createWriteStream(part));
  if (fs.statSync(part).size !== m.size) {
    fs.rmSync(part, { force: true });
    fail("ההורדה נקטעה באמצע. מריצות שוב.");
  }
  fs.renameSync(part, dest);
}
