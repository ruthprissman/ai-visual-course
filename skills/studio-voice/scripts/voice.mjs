#!/usr/bin/env node
// Hebrew narration with Google's Gemini TTS. No packages: only Node 22 and FFmpeg (mp3 output).
// The key is read from a file in the open folder and is never printed.
//
//   node voice.mjs --text-file "קריינות/טקסט.txt" --voice Sulafat --style "חם ורגוע" --out "קריינות/פתיח.mp3"
//   node voice.mjs --text "משפט קצר" --voice Kore --out "קריינות/בחירת קול/Kore.mp3"
//
// Options: --lite (the cheaper model), --key-file "<path>" (default: "מפתח Google.txt" in the open folder).
// Prints one JSON line. Errors go out in plain Hebrew, with exit code 1.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const API = "https://generativelanguage.googleapis.com/v1beta/interactions";
const MODEL = "gemini-3.8-flash-tts";
const LITE = "gemini-3.8-flash-lite-tts";
const KEY_FILE = "מפתח Google.txt";
const CHUNK_CHARS = 4000;
const BYTES_PER_SECOND = 48000; // 24 kHz, mono, 16 bit

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
function fail(msg) {
  console.error(msg);
  process.exit(1);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function readKey() {
  const file = opt("key-file", KEY_FILE);
  if (fs.existsSync(file)) {
    const key = fs.readFileSync(file, "utf8").replace(/^﻿/, "").trim();
    if (!key) fail(`הקובץ "${file}" ריק. מדביקות בו את המפתח, ושומרות (Ctrl+S).`);
    if (/\s/.test(key)) fail(`בקובץ "${file}" צריך להיות רק המפתח, בשורה אחת, בלי מילים נוספות.`);
    return key;
  }
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;
  fail(`לא מצאתי את הקובץ "${file}" בתיקייה הפתוחה. יוצרות מפתח (במדריך, "יוצרות מפתח"), ושומרות אותו בקובץ הזה.`);
}

function splitText(text) {
  if (text.length <= CHUNK_CHARS) return [text];
  const chunks = [];
  let current = "";
  for (const part of text.split(/(?<=[.!?:\n])\s+/)) {
    if (current && current.length + part.length + 1 > CHUNK_CHARS) {
      chunks.push(current);
      current = "";
    }
    current = current ? `${current} ${part}` : part;
  }
  if (current) chunks.push(current);
  return chunks;
}

function explain(status, message) {
  if (status === 400 && /api key/i.test(message)) return "המפתח לא תקין. בודקות שהועתק עד הסוף, בלי רווחים, ושהקובץ נשמר.";
  if (status === 401 || status === 403) return "המפתח לא מורשה. בודקות שהועתק עד הסוף, ושלא נמחק באתר.";
  if (status === 402) return "נגמר הקרדיט בחשבון Google. קונות עוד ב-aistudio.google.com/billing (במדריך, החלק על תשלום).";
  if (status === 404) return `Google לא מזהה את המודל או את הקול. הפרטים: ${message}`;
  if (status === 429) return "נגמרה המכסה להיום: בחינם יש 10 בקשות ביום. ממשיכות מחר, או מוסיפות תשלום (במדריך, החלק על תשלום).";
  return `Google החזירה שגיאה ${status}: ${message}`;
}

async function request(key, text, voice, style, model) {
  const block = { type: "text", text };
  if (style) block.annotations = [{ type: "speech_metadata", style }];
  const body = {
    model,
    input: [{ type: "user_input", content: [block] }],
    response_format: { type: "audio" },
    generation_config: { speech_config: [{ voice }] },
  };
  for (let attempt = 1; ; attempt++) {
    let res;
    try {
      res = await fetch(API, {
        method: "POST",
        headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (e) {
      const why = `${e.cause?.code || ""} ${e.cause?.message || e.message}`;
      if (/CERT|SELF_SIGNED|ISSUER/i.test(why)) {
        fail("רשת מסוננת: Node צריך את תעודת הסינון (NODE_EXTRA_CA_CERTS). זה תפקיד של מי שאחראית על המחשב. לא מכבים בדיקת אבטחה.");
      }
      fail(`אין חיבור ל-Google (${why.trim()}). בודקות אינטרנט, ושהאתר generativelanguage.googleapis.com פתוח בסינון.`);
    }
    if (res.ok) {
      const data = await res.json();
      const steps = (data.steps || []).filter((s) => s.type === "model_output");
      const audio = steps.flatMap((s) => s.content || []).filter((c) => c.type === "audio").pop();
      if (!audio?.data) fail(`לא חזר קול. ${JSON.stringify(data).slice(0, 300)}`);
      return Buffer.from(audio.data, "base64");
    }
    const raw = await res.text();
    let message = raw.slice(0, 400);
    try {
      message = JSON.parse(raw).error?.message || message;
    } catch {}
    const perDay = /per.?day|daily/i.test(message);
    const busy = (res.status === 429 && !perDay) || res.status >= 500;
    if (!busy || attempt >= 4) fail(explain(res.status, message));
    const wait = res.status === 429 ? 25 : 5 * attempt;
    console.error(`Google עמוסה או שהגענו לשלוש בקשות בדקה. מחכה ${wait} שניות ומנסה שוב.`);
    await sleep(wait * 1000);
  }
}

function pcmOf(wav) {
  // Finds the "data" chunk instead of assuming a 44-byte header.
  let at = 12;
  while (at + 8 <= wav.length) {
    const size = wav.readUInt32LE(at + 4);
    if (wav.toString("latin1", at, at + 4) === "data") return wav.subarray(at + 8, at + 8 + size);
    at += 8 + size + (size % 2);
  }
  return wav;
}

function wavOf(pcm) {
  const head = Buffer.alloc(44);
  head.write("RIFF", 0, "latin1");
  head.writeUInt32LE(36 + pcm.length, 4);
  head.write("WAVEfmt ", 8, "latin1");
  head.writeUInt32LE(16, 16);
  head.writeUInt16LE(1, 20);
  head.writeUInt16LE(1, 22);
  head.writeUInt32LE(24000, 24);
  head.writeUInt32LE(BYTES_PER_SECOND, 28);
  head.writeUInt16LE(2, 32);
  head.writeUInt16LE(16, 34);
  head.write("data", 36, "latin1");
  head.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([head, pcm]);
}

// A new take never overwrites an old one: "פתיח.mp3", "פתיח - 2.mp3", ...
function freePath(file) {
  if (!fs.existsSync(file)) return file;
  const { dir, name, ext } = path.parse(file);
  for (let n = 2; ; n++) {
    const next = path.join(dir, `${name} - ${n}${ext}`);
    if (!fs.existsSync(next)) return next;
  }
}

const textFile = opt("text-file");
const text = (textFile ? fs.readFileSync(textFile, "utf8") : opt("text", "")).replace(/^﻿/, "").trim();
const voice = opt("voice", "Sulafat");
const style = opt("style");
const outArg = opt("out");
if (!text) fail("אין טקסט. צריך --text או --text-file.");
if (!outArg) fail("חסר --out: לאן לשמור.");
const model = args.includes("--lite") ? LITE : MODEL;
const key = readKey();

const chunks = splitText(text);
const pcm = [];
for (const chunk of chunks) pcm.push(pcmOf(await request(key, chunk, voice, style, model)));
const audio = Buffer.concat(pcm);

const out = freePath(outArg);
fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
if (path.extname(out).toLowerCase() === ".wav") {
  fs.writeFileSync(out, wavOf(audio));
} else {
  const tmp = `${out}.tmp.wav`;
  fs.writeFileSync(tmp, wavOf(audio));
  const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", tmp, "-b:a", "160k", out], { encoding: "utf8" });
  fs.rmSync(tmp, { force: true });
  if (r.status !== 0) fail(`FFmpeg לא הצליח לשמור את הקובץ. ${r.error?.message || r.stderr}`);
}

const seconds = audio.length / BYTES_PER_SECOND;
const words = text.replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).length;
const pauses = (text.match(/<[^>]*pause[^>]*>/g) || []).length;
const wps = words / Math.max(seconds - pauses * 1.5, 1);
const result = { ok: true, file: out, seconds: +seconds.toFixed(1), words, wordsPerSecond: +wps.toFixed(2), voice, model, requests: chunks.length };
// A narrator that skipped or invented a sentence shows up as an odd pace.
if (words >= 6 && (wps < 1.2 || wps > 3.6)) result.warning = "הקצב לא רגיל: ייתכן שהקול דילג על מילים או הוסיף מילים. מאזינות עם הטקסט ביד.";
console.log(JSON.stringify(result));
