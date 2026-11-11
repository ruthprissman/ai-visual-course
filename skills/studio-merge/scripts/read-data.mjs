#!/usr/bin/env node
// Reads an Excel file (.xlsx) or a CSV, with no extra software, and writes data.json.
//
//   node read-data.mjs "מוזמנים.xlsx" [--sheet "גיליון1"] [--out "פרויקטים/<name>/data.json"]
//
// Prints: how many rows, the column names, the first rows, the longest value in each column, and empty cells.
// CSV: UTF-8 (with or without BOM), or the older Hebrew encoding (Windows-1255). Separator: comma, semicolon or tab.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { parseArgs } from "./common.mjs";

const opts = parseArgs(process.argv.slice(2));
const src = opts._[0];
if (!src || !fs.existsSync(src)) { console.error('usage: node read-data.mjs "<file.xlsx|file.csv>" [--sheet "<name>"] [--out data.json]'); process.exit(1); }

// ---------- CSV ----------
function decodeText(buf) {
  if (buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) buf = buf.subarray(3);
  try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); }
  catch { return new TextDecoder("windows-1255").decode(buf); }
}
function parseCsv(text) {
  const first = text.split(/\r?\n/)[0] || "";
  const sep = [",", ";", "\t"].map((s) => [s, first.split(s).length]).sort((a, b) => b[1] - a[1])[0][0];
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') q = false;
      else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === sep) { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((r) => r.some((c) => c.trim() !== ""));
}

// ---------- XLSX (a zip of XML files) ----------
function unzip(buf) {
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("זה לא נראה כמו קובץ אקסל תקין (xlsx).");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  const files = {};
  for (let k = 0; k < count; k++) {
    const method = buf.readUInt16LE(p + 10), csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28), xlen = buf.readUInt16LE(p + 30), clen = buf.readUInt16LE(p + 32), off = buf.readUInt32LE(p + 42);
    const name = buf.toString("utf8", p + 46, p + 46 + nlen);
    const lnlen = buf.readUInt16LE(off + 26), lxlen = buf.readUInt16LE(off + 28);
    const data = buf.subarray(off + 30 + lnlen + lxlen, off + 30 + lnlen + lxlen + csize);
    files[name] = () => (method === 8 ? zlib.inflateRawSync(data) : data).toString("utf8");
    p += 46 + nlen + xlen + clen;
  }
  return files;
}
const unxml = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'")
  .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16))).replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d)).replace(/&amp;/g, "&");
const colIndex = (ref) => { let n = 0; for (const ch of ref.replace(/\d+/g, "")) n = n * 26 + (ch.charCodeAt(0) - 64); return n - 1; };
const excelDate = (n) => { const d = new Date(Math.round((n - 25569) * 86400000)); return `${d.getUTCDate()}.${d.getUTCMonth() + 1}.${d.getUTCFullYear()}`; };

function readXlsx(buf) {
  const z = unzip(buf);
  const wb = z["xl/workbook.xml"]();
  const sheets = [...wb.matchAll(/<sheet\b[^>]*name="([^"]*)"[^>]*r:id="([^"]*)"/g)].map((m) => ({ name: unxml(m[1]), rid: m[2] }));
  const want = opts.sheet ? sheets.find((s) => s.name === opts.sheet) : sheets[0];
  if (!want) throw new Error(`לא מצאתי גיליון בשם "${opts.sheet}". הגיליונות: ${sheets.map((s) => s.name).join(", ")}`);
  const rels = z["xl/_rels/workbook.xml.rels"]();
  const target = rels.match(new RegExp(`Id="${want.rid}"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Id="${want.rid}"`));
  const file = "xl/" + (target[1] || target[2]).replace(/^\/?xl\//, "");
  const shared = z["xl/sharedStrings.xml"] ? [...z["xl/sharedStrings.xml"]().matchAll(/<si>([\s\S]*?)<\/si>/g)]
    .map((m) => unxml([...m[1].replace(/<rPh[\s\S]*?<\/rPh>/g, "").matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((t) => t[1]).join(""))) : [];
  const rows = [];
  for (const rm of z[file]().matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)) {
    const row = [];
    for (const cm of rm[1].matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const attrs = cm[1], inner = cm[2] || "";
      const ref = attrs.match(/r="([A-Z]+\d+)"/)?.[1], t = attrs.match(/t="(\w+)"/)?.[1];
      let v = inner.match(/<v>([\s\S]*?)<\/v>/)?.[1];
      let val = "";
      if (t === "s") val = shared[+v] ?? "";
      else if (t === "inlineStr") val = unxml([...inner.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((x) => x[1]).join(""));
      else if (t === "b") val = v === "1" ? "כן" : "לא";
      else if (v !== undefined) val = unxml(v);
      row[ref ? colIndex(ref) : row.length] = val;
    }
    rows.push(Array.from(row, (c) => c ?? ""));
  }
  return { rows: rows.filter((r) => r.some((c) => String(c).trim() !== "")), sheet: want.name, sheets: sheets.map((s) => s.name) };
}

// ---------- main ----------
const buf = fs.readFileSync(src);
const ext = path.extname(src).toLowerCase();
let table, sheet = null, sheets = [];
if (ext === ".xlsx") ({ rows: table, sheet, sheets } = readXlsx(buf));
else if (ext === ".xls") { console.error("זה קובץ אקסל ישן (xls). פותחות אותו באקסל ושומרות בשם ← Excel Workbook (xlsx), או ← CSV UTF-8."); process.exit(1); }
else table = parseCsv(decodeText(buf));
if (!table.length) { console.error("הקובץ ריק."); process.exit(1); }

const head = table[0].map((h, i) => String(h).trim() || `עמודה ${i + 1}`);
const rows = table.slice(1).map((r) => Object.fromEntries(head.map((h, i) => {
  let v = r[i] ?? "";
  if (/תאריך|date/i.test(h) && /^\d{5}(\.\d+)?$/.test(String(v)) && +v > 30000 && +v < 60000) v = excelDate(+v);
  return [h, String(v).trim()];
})));

const out = path.resolve(opts.out || "data.json");
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify({ source: path.basename(src), sheet, columns: head, rows }, null, 2));

console.log(`קובץ: ${path.basename(src)}${sheet ? `  · גיליון: ${sheet}${sheets.length > 1 ? ` (יש עוד: ${sheets.filter((s) => s !== sheet).join(", ")})` : ""}` : ""}`);
console.log(`שורות: ${rows.length}`);
console.log(`עמודות: ${head.join(" | ")}`);
for (const r of rows.slice(0, 3)) console.log(`  ${head.map((h) => r[h]).join(" | ")}`);
for (const h of head) {
  const vals = rows.map((r) => r[h]);
  const longest = vals.reduce((a, b) => (b.length > a.length ? b : a), "");
  const empty = vals.filter((v) => !v).length;
  console.log(`  ${h}: הכי ארוך "${longest}" (${longest.length} תווים)${empty ? ` · ${empty} תאים ריקים` : ""}`);
}
console.log(`saved: ${out}`);
