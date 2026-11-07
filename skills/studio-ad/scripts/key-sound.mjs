#!/usr/bin/env node
// One sound effect from ElevenLabs through an API key. No packages: only Node.
// The key is read from a file in the open folder and is never printed.
//
//   node key-sound.mjs --prompt "Soft gentle whoosh of a calm wave, airy" --seconds 1.5 --out "צלילים/whoosh.mp3"
//
// Options: --key-file "<path>" (default: "מפתח ElevenLabs.txt" in the open folder). Prints one JSON line.

import fs from "node:fs";
import path from "node:path";

const API = "https://api.elevenlabs.io/v1/sound-generation";
const KEY_FILE = "מפתח ElevenLabs.txt";

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
function fail(msg) {
  console.error(msg);
  process.exit(1);
}

const prompt = opt("prompt");
const seconds = Number(opt("seconds", "1.5"));
const outArg = opt("out");
const keyFile = opt("key-file", KEY_FILE);
if (!prompt || !outArg) fail("צריך --prompt ו---out.");
if (!fs.existsSync(keyFile)) fail(`לא מצאתי את הקובץ "${keyFile}" בתיקייה הפתוחה. יוצרות מפתח, ושומרות אותו בקובץ הזה.`);
const key = fs.readFileSync(keyFile, "utf8").replace(/^﻿/, "").trim();
if (!key || /\s/.test(key)) fail(`בקובץ "${keyFile}" צריך להיות רק המפתח, בשורה אחת.`);

let res;
try {
  res = await fetch(API, {
    method: "POST",
    headers: { "xi-api-key": key, "Content-Type": "application/json" },
    body: JSON.stringify({ text: prompt, duration_seconds: seconds, prompt_influence: 0.3, model_id: "eleven_text_to_sound_v2" }),
  });
} catch (e) {
  const why = `${e.cause?.code || ""} ${e.cause?.message || e.message}`;
  if (/CERT|SELF_SIGNED|ISSUER/i.test(why)) fail("רשת מסוננת: Node צריך את תעודת הסינון (NODE_EXTRA_CA_CERTS). זה תפקיד של מי שאחראית על המחשב.");
  fail(`אין חיבור ל-ElevenLabs (${why.trim()}).`);
}
if (!res.ok) {
  const raw = (await res.text()).slice(0, 300);
  if (res.status === 401 && /permission/i.test(raw)) fail("למפתח אין הרשאה לאפקטים: בעמוד המפתחות מסמנות Access ליד Sound Effects.");
  if (res.status === 401) fail("המפתח לא נכון, או שפג תוקפו. יוצרות חדש, ושומרות אותו בקובץ.");
  if (/quota|credit/i.test(raw)) fail("נגמרו הנקודות, או שהגעתן לתקרה של המפתח.");
  if (res.status === 429) fail("יותר מדי בקשות בבת אחת. מחכים חצי דקה, ומנסים שוב.");
  fail(`ElevenLabs החזירה שגיאה ${res.status}: ${raw}`);
}

const { dir, name, ext } = path.parse(outArg);
let out = outArg;
for (let n = 2; fs.existsSync(out); n++) out = path.join(dir, `${name}-${n}${ext}`);
fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
fs.writeFileSync(out, Buffer.from(await res.arrayBuffer()));
console.log(JSON.stringify({ ok: true, file: out, seconds }));
