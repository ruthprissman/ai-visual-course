#!/usr/bin/env node
// Optional deeper look: Google Gemini watches AND listens to the whole video (tone of voice, music, movement),
// and answers one question about it. Needs "מפתח Google.txt". A light copy (480p) is uploaded, not the original.
//
//   node gemini-watch.mjs --video "סרטונים/הפודקאסט.mp4" --prompt-file "ניתוח/<name>/question.txt" --out "ניתוח/<name>/gemini.md"

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { KEY_FILES, args, fail, ffmpeg, netError, probe, readKey } from "./common.mjs";

const API = "https://generativelanguage.googleapis.com";
const MODELS = ["gemini-3.8-flash", "gemini-2.5-flash"];
const { opt, flag } = args();
const video = opt("video");
const out = opt("out");
const prompt = opt("prompt-file") ? fs.readFileSync(opt("prompt-file"), "utf8").replace(/^﻿/, "") : opt("prompt");
if (!video || !out || !prompt) fail("צריך --video, --out, ו---prompt-file (או --prompt).");
const key = readKey(KEY_FILES.google);
if (!key) fail(`לניתוח העמוק צריך את הקובץ "${KEY_FILES.google}" (מהבונוס של שיעור 3). בלי זה, הניתוח הרגיל עובד בלי מפתח.`);
const info = probe(video);
if (info.duration > 45 * 60) fail("הסרטון ארוך מ-45 דקות. בניתוח העמוק בודקים קטע: מקצרות קודם עם /video-cut.");

// A light copy: 480p, 2 frames a second, mono sound. Gemini looks at about one frame a second anyway.
const light = path.join(os.tmpdir(), `watch-${process.pid}.mp4`);
const scale = info.vertical ? "scale=-2:480" : "scale=480:-2";
ffmpeg(["-y", "-loglevel", "error", "-i", video, "-vf", `${scale},fps=2`, "-c:v", "libx264", "-preset", "veryfast", "-crf", "32", "-c:a", "aac", "-b:a", "48k", "-ac", "1", light]);

async function call(url, init) {
  try {
    return await fetch(url, init);
  } catch (e) {
    netError(e, "Google");
  }
}

let fileName;
try {
  const bytes = fs.readFileSync(light);
  const start = await call(`${API}/upload/v1beta/files`, {
    method: "POST",
    headers: {
      "x-goog-api-key": key,
      "X-Goog-Upload-Protocol": "resumable",
      "X-Goog-Upload-Command": "start",
      "X-Goog-Upload-Header-Content-Length": String(bytes.length),
      "X-Goog-Upload-Header-Content-Type": "video/mp4",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ file: { display_name: "video" } }),
  });
  if (!start.ok) explain(start.status, await start.text());
  const uploadUrl = start.headers.get("x-goog-upload-url");
  const up = await call(uploadUrl, {
    method: "POST",
    headers: { "X-Goog-Upload-Command": "upload, finalize", "X-Goog-Upload-Offset": "0", "Content-Length": String(bytes.length) },
    body: bytes,
  });
  if (!up.ok) explain(up.status, await up.text());
  let file = (await up.json()).file;
  fileName = file.name;
  for (let i = 0; file.state === "PROCESSING" && i < 90; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    file = await (await call(`${API}/v1beta/${file.name}`, { headers: { "x-goog-api-key": key } })).json();
  }
  if (file.state !== "ACTIVE") fail(`Google לא הצליחה לעבד את הסרטון (${file.state}). מנסות שוב, או מוותרות על הניתוח העמוק.`);

  let answer;
  for (const model of MODELS) {
    const body = {
      contents: [{ parts: [{ file_data: { mime_type: "video/mp4", file_uri: file.uri } }, { text: prompt }] }],
      generationConfig: { mediaResolution: "MEDIA_RESOLUTION_LOW", ...(flag("think") ? {} : { thinkingConfig: { thinkingBudget: 0 } }) },
    };
    const res = await call(`${API}/v1beta/models/${model}:generateContent`, {
      method: "POST",
      headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const raw = await res.text();
    if (res.ok) {
      const data = JSON.parse(raw);
      answer = { model, text: (data.candidates?.[0]?.content?.parts || []).map((p) => p.text || "").join("").trim(), tokens: data.usageMetadata?.totalTokenCount };
      break;
    }
    // On the free plan a model may be missing or out of quota: the next model in the list gets a try.
    if (![403, 404, 429].includes(res.status) || model === MODELS.at(-1)) explain(res.status, raw);
  }
  if (!answer?.text) fail("Google לא החזירה תשובה. מנסות שוב בעוד דקה.");
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, answer.text + "\n");
  console.log(JSON.stringify({ ok: true, file: out, model: answer.model, tokens: answer.tokens }));
} finally {
  fs.rmSync(light, { force: true });
  if (fileName) await fetch(`${API}/v1beta/${fileName}`, { method: "DELETE", headers: { "x-goog-api-key": key } }).catch(() => {});
}

function explain(status, raw) {
  let message = raw.slice(0, 300);
  try {
    message = JSON.parse(raw).error?.message || message;
  } catch {}
  if (status === 400 && /api key/i.test(message)) fail("המפתח של Google לא תקין. בודקות שהועתק עד הסוף, ושהקובץ נשמר.");
  if (status === 402) fail("נגמר הקרדיט בחשבון Google. קונות עוד ב-aistudio.google.com/billing.");
  if (status === 429) fail("נגמרה המכסה של Google (בחינם יש מגבלה יומית). ממשיכות מחר, והניתוח הרגיל עובד גם בלי זה.");
  fail(`Google החזירה שגיאה ${status}: ${message}`);
}
