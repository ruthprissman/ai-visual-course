#!/usr/bin/env node
// Edits a video by a plan: removes parts, keeps parts, or saves parts as separate short videos.
// The plan is a small JSON file, so it can be read and approved before anything is cut.
//
//   node cut.mjs plan  --transcript "<t.json>" [--gaps 0.6] [--fillers] --out "<plan.json>"   pauses and "אה" to remove
//   node cut.mjs show  --plan "<plan.json>" [--transcript "<t.json>"]                           a table of what goes, with the words
//   node cut.mjs apply --video "<v>" --plan "<plan.json>" --out "<o.mp4>" [--transcript "<t.json>"]
//                      [--end "<logo.mp4>"] [--vertical blur|crop] [--loud] [--clean] [--pad-color "#FFFFFF"]
//   node cut.mjs clips --video "<v>" --plan "<plan.json>" --out-dir "סרטונים" [--transcript ...] [--vertical blur|crop] [--loud] [--end "<logo.mp4>"]
//
// Plan file: { "remove": [{ "s": 0, "e": 12.4, "why": "..." }], "keep": [...], "clips": [{ "s": .., "e": .., "name": ".." }] }
// Times are seconds or "mm:ss.s". With "keep", only those parts stay. The original video is never changed.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { args, baseName, clock, fail, ffmpeg, freePath, loadTranscript, probe, sameSource, sdrFilter, seconds, transcriptPath, writeTranscript } from "./common.mjs";

const FILLERS = new Set(["אה", "אהה", "אההה", "אמ", "אממ", "אמממ", "הממ", "אהמ"]);
const { command, opt, flag } = args();
if (!command) fail("צריך פקודה: plan, show, apply או clips.");

const num = (x) => (typeof x === "number" ? x : seconds(x));
const bare = (w) => w.replace(/[.,?!]+$/, "");

function readPlan(file) {
  if (!file || !fs.existsSync(file)) fail(`לא מצאתי את תוכנית העריכה "${file}".`);
  const p = JSON.parse(fs.readFileSync(file, "utf8").replace(/^﻿/, ""));
  const norm = (list) => (list || []).map((r) => ({ ...r, s: num(r.s), e: num(r.e) })).filter((r) => r.e > r.s);
  return { remove: norm(p.remove), keep: norm(p.keep), clips: norm(p.clips) };
}

function merge(ranges) {
  const sorted = [...ranges].sort((a, b) => a.s - b.s);
  const out = [];
  for (const r of sorted) {
    const last = out.at(-1);
    if (last && r.s <= last.e + 0.02) last.e = Math.max(last.e, r.e);
    else out.push({ s: r.s, e: r.e });
  }
  return out;
}

// A cut edge that falls inside a word moves to the quiet between words, so no word is cut in half.
function snap(t, words, side, approx) {
  if (approx) {
    // Word times are estimated, so the sentence is the unit: an edge that falls inside a sentence moves out to its edge.
    // The kept part only grows, so no speech is lost. An edge in a pause stays where it is.
    const groups = new Map();
    for (const w of words) {
      const g = groups.get(w.g) || { s: w.s, e: w.e };
      groups.set(w.g, { s: Math.min(g.s, w.s), e: Math.max(g.e, w.e) });
    }
    const seg = [...groups.values()].find((g) => t > g.s + 0.02 && t < g.e - 0.02);
    if (!seg) return t;
    return side === "start" ? Math.max(0, seg.s - 0.05) : seg.e + 0.05;
  }
  const w = words.find((x) => t > x.s + 0.02 && t < x.e - 0.02);
  if (!w) return t;
  const i = words.indexOf(w);
  if (side === "start") return i > 0 ? (words[i - 1].e + w.s) / 2 : Math.max(0, w.s - 0.05);
  return i < words.length - 1 ? (w.e + words[i + 1].s) / 2 : w.e + 0.05;
}

function keepRanges(plan, duration, words, approx = false) {
  let keep = plan.keep.length ? merge(plan.keep) : [{ s: 0, e: duration }];
  for (const r of merge(plan.remove)) {
    keep = keep.flatMap((k) => {
      if (r.e <= k.s || r.s >= k.e) return [k];
      return [k.s < r.s ? { s: k.s, e: r.s } : null, r.e < k.e ? { s: r.e, e: k.e } : null].filter(Boolean);
    });
  }
  if (words) keep = keep.map((k) => ({ s: snap(k.s, words, "start", approx), e: snap(k.e, words, "end", approx) }));
  return merge(keep.map((k) => ({ s: Math.max(0, k.s), e: Math.min(duration, k.e) }))).filter((k) => k.e - k.s >= 0.15);
}

// Words that stay, with their new times after the cut.
function remap(words, keep) {
  const out = [];
  let offset = 0;
  for (const k of keep) {
    for (const w of words) if (w.s >= k.s - 0.01 && w.e <= k.e + 0.01) out.push({ ...w, s: +(w.s - k.s + offset).toFixed(3), e: +(Math.min(w.e, k.e) - k.s + offset).toFixed(3) });
    offset += k.e - k.s;
  }
  return out;
}

function transcriptFor(video, info) {
  const file = opt("transcript") || transcriptPath(video);
  if (!fs.existsSync(file)) return null;
  const t = loadTranscript(file);
  if (!sameSource(t, info)) {
    console.error("שימי לב: התמלול שייך לגרסה אחרת של הסרטון, אז לא משתמש בו לחיתוך.");
    return null;
  }
  return t;
}

// ---- one FFmpeg run: cut and join, then the optional vertical frame, the ending video, and the sound.
function render(video, info, keep, out, { end, vertical, loud, clean, padColor }) {
  const parts = [];
  const vin = info.hdr ? `[0:v]${sdrFilter(info)}[src];` : "";
  const vsrc = info.hdr ? "[src]" : "[0:v]";
  if (info.hdr && keep.length > 1) parts.push(`${vin.slice(0, -1)},split=${keep.length}${keep.map((_, i) => `[vs${i}]`).join("")}`);
  const fade = 0.02;
  keep.forEach((k, i) => {
    const vIn = info.hdr ? (keep.length > 1 ? `[vs${i}]` : vsrc) : "[0:v]";
    const len = k.e - k.s;
    parts.push(`${vIn}trim=start=${k.s.toFixed(3)}:end=${k.e.toFixed(3)},setpts=PTS-STARTPTS[v${i}]`);
    parts.push(info.hasAudio
      ? `[0:a]atrim=start=${k.s.toFixed(3)}:end=${k.e.toFixed(3)},asetpts=PTS-STARTPTS,afade=t=in:d=${fade},afade=t=out:st=${Math.max(0, len - fade).toFixed(3)}:d=${fade}[a${i}]`
      : `anullsrc=r=48000:cl=stereo,atrim=duration=${len.toFixed(3)}[a${i}]`);
  });
  const head = info.hdr && keep.length === 1 ? vin : "";
  parts.push(`${keep.map((_, i) => `[v${i}][a${i}]`).join("")}concat=n=${keep.length}:v=1:a=1[vc][ac]`);

  let W = info.width;
  let H = info.height;
  let v = "[vc]";
  if (vertical && !info.vertical) {
    [W, H] = [1080, 1920];
    if (vertical === "crop") parts.push(`${v}crop=ih*9/16:ih,scale=${W}:${H},setsar=1[vv]`);
    else parts.push(`${v}split[bg0][fg0];[bg0]scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H},boxblur=24:2[bg];[fg0]scale=${W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[vv]`);
    v = "[vv]";
  }
  W -= W % 2;
  H -= H % 2;
  const fps = Math.round(info.fps * 100) / 100;
  parts.push(`${v}scale=${W}:${H},setsar=1,fps=${fps},format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[vm]`);
  let a = "[ac]";
  parts.push(`${a}aresample=48000,aformat=channel_layouts=stereo[am]`);
  v = "[vm]";
  a = "[am]";
  const inputs = ["-i", path.resolve(video)];
  if (end) {
    const e = probe(end);
    inputs.push("-i", path.resolve(end));
    parts.push(`[1:v]${sdrFilter(e)},scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=${padColor},setsar=1,fps=${fps},format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[ve]`);
    parts.push(e.hasAudio ? `[1:a]aresample=48000,aformat=channel_layouts=stereo[ae]` : `anullsrc=r=48000:cl=stereo,atrim=duration=${e.duration.toFixed(3)}[ae]`);
    parts.push(`${v}${a}[ve][ae]concat=n=2:v=1:a=1[vj][aj]`);
    v = "[vj]";
    a = "[aj]";
  }
  const sound = [clean ? "afftdn=nf=-25" : null, loud ? "loudnorm=I=-16:TP=-1.5:LRA=11" : null].filter(Boolean);
  if (sound.length) {
    parts.push(`${a}${sound.join(",")},aresample=48000[af]`);
    a = "[af]";
  }
  // A filter script, not a long command line: Windows limits command length, and a long edit has many cuts.
  const script = path.join(os.tmpdir(), `cut-${process.pid}-${Date.now()}.txt`);
  fs.writeFileSync(script, head + parts.join(";\n"));
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  try {
    ffmpeg(["-y", "-loglevel", "error", ...inputs, "-/filter_complex", script, "-map", v, "-map", a, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", path.resolve(out)]);
  } finally {
    fs.rmSync(script, { force: true });
  }
  return { width: W, height: H };
}

function saveTranscript(t, keep, out) {
  if (!t) return null;
  const info = probe(out);
  const words = remap(t.words, keep);
  const file = transcriptPath(out);
  writeTranscript(file, { ...t, created: new Date().toISOString(), source: { file: path.basename(out), size: info.size, duration: info.duration }, editedFrom: t.source.file, words });
  return file;
}

const options = () => ({ end: opt("end"), vertical: opt("vertical"), loud: flag("loud"), clean: flag("clean"), padColor: opt("pad-color", "black") });

if (command === "plan") {
  const t = loadTranscript(opt("transcript") || fail("חסר --transcript."));
  const out = opt("out") || fail("חסר --out.");
  const gap = Number(opt("gaps", "0"));
  const leave = 0.25;
  const remove = [];
  const words = t.words;
  if (gap > 0) {
    // A pause longer than "gap" seconds is shortened, leaving a short breath on each side.
    for (let i = 1; i < words.length; i++) {
      const g = words[i].s - words[i - 1].e;
      if (g > gap) remove.push({ s: +(words[i - 1].e + leave / 2).toFixed(3), e: +(words[i].s - leave / 2).toFixed(3), why: `שתיקה של ${g.toFixed(1)} שנ'` });
    }
    if (words[0].s > gap) remove.push({ s: 0, e: +(words[0].s - leave / 2).toFixed(3), why: "שקט בהתחלה" });
    const last = words.at(-1).e;
    if (t.source.duration - last > gap) remove.push({ s: +(last + leave).toFixed(3), e: +t.source.duration.toFixed(3), why: "שקט בסוף" });
  }
  if (flag("fillers")) {
    words.forEach((w, i) => {
      if (!FILLERS.has(bare(w.w))) return;
      const before = words[i - 1]?.e ?? 0;
      const after = words[i + 1]?.s ?? t.source.duration;
      remove.push({ s: +Math.max(before + 0.03, w.s - 0.04).toFixed(3), e: +Math.min(after - 0.03, w.e + 0.04).toFixed(3), why: `"${bare(w.w)}"` });
    });
  }
  let plan = { remove };
  if (fs.existsSync(out)) {
    const old = JSON.parse(fs.readFileSync(out, "utf8"));
    plan = { ...old, remove: [...(old.remove || []), ...remove] };
  }
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(plan, null, 1));
  const saved = merge(remove).reduce((a, r) => a + r.e - r.s, 0);
  console.log(JSON.stringify({ ok: true, file: out, cuts: remove.length, pauses: remove.filter((r) => r.why.startsWith("שתיקה") || r.why.startsWith("שקט")).length, fillers: remove.filter((r) => r.why.startsWith('"')).length, secondsSaved: +saved.toFixed(1), newLength: clock(t.source.duration - saved) }));
} else if (command === "show") {
  const plan = readPlan(opt("plan"));
  const t = opt("transcript") ? loadTranscript(opt("transcript")) : null;
  const said = (r) => (t ? t.words.filter((w) => w.s >= r.s - 0.05 && w.e <= r.e + 0.05).map((w) => w.w).join(" ") : "");
  const row = (r, i) => `| ${i + 1} | ${clock(r.s, { ms: true })} | ${clock(r.e, { ms: true })} | ${(r.e - r.s).toFixed(1)} | ${said(r).slice(0, 90) || "—"} | ${r.why || r.name || ""} |`;
  const table = (title, list) => (list.length ? `### ${title}\n| # | מ- | עד | שניות | מה נאמר שם | למה |\n|---|---|---|---|---|---|\n${list.map(row).join("\n")}\n` : "");
  const big = plan.remove.filter((r) => !/^(שתיקה|שקט|")/.test(r.why || ""));
  const small = plan.remove.length - big.length;
  console.log([
    table("מורידים", big),
    small ? `ועוד ${small} קיצורים קטנים: שתיקות ו"אה" (${merge(plan.remove.filter((r) => /^(שתיקה|שקט|")/.test(r.why || ""))).reduce((a, r) => a + r.e - r.s, 0).toFixed(1)} שניות ביחד).\n` : "",
    table("משאירים רק את", plan.keep),
    table("סרטונים קצרים", plan.clips),
  ].join("\n"));
} else if (command === "apply") {
  const video = opt("video");
  const outArg = opt("out");
  if (!video || !outArg) fail("צריך --video, --plan ו---out.");
  const info = probe(video);
  const t = transcriptFor(video, info);
  const keep = keepRanges(readPlan(opt("plan")), info.duration, t?.words, t?.timing === "approx");
  if (!keep.length) fail("התוכנית מורידה את כל הסרטון. בודקות את הזמנים בתוכנית.");
  const out = freePath(outArg);
  const started = Date.now();
  const size = render(video, info, keep, out, options());
  const newT = saveTranscript(t, keep, out);
  const after = probe(out);
  console.log(JSON.stringify({ ok: true, file: out, before: clock(info.duration), after: clock(after.duration), parts: keep.length, size: `${size.width}x${size.height}`, transcript: newT, seconds: Math.round((Date.now() - started) / 1000) }));
} else if (command === "clips") {
  const video = opt("video");
  const dir = opt("out-dir", "סרטונים");
  if (!video) fail("צריך --video, --plan ו---out-dir.");
  const info = probe(video);
  const t = transcriptFor(video, info);
  const plan = readPlan(opt("plan"));
  if (!plan.clips.length) fail('בתוכנית אין "clips". כל סרטון קצר: { "s": התחלה, "e": סוף, "name": שם }.');
  const done = [];
  for (const [i, c] of plan.clips.entries()) {
    const keep = keepRanges({ keep: [c], remove: plan.remove }, info.duration, t?.words, t?.timing === "approx");
    const out = freePath(path.join(dir, `${baseName(video)} - ${c.name || `קטע ${i + 1}`}.mp4`));
    render(video, info, keep, out, options());
    done.push({ file: out, length: clock(probe(out).duration), transcript: saveTranscript(t, keep, out) });
  }
  console.log(JSON.stringify({ ok: true, clips: done }));
} else {
  fail(`אין פקודה בשם "${command}". יש plan, show, apply, clips.`);
}
