#!/usr/bin/env node
// A board of video directions, read right to left: option 1 on the right, with a Hebrew label under each.
//
//   node directions-board.mjs --at 2.6 --labels "זורם,טיפוגרפי,לוגו במרכז" --out "board.png" <dir1> <dir2> <dir3>
//
// Each <dir> is a HyperFrames project. The frame at --at seconds is taken from each one.

import { execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HF = "npx --yes hyperframes@0.8.147";
const args = process.argv.slice(2);
const opts = {};
const dirs = [];
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith("--")) opts[args[i].slice(2)] = args[++i];
  else dirs.push(path.resolve(args[i]));
}
const at = opts.at || "2";
const labels = (opts.labels || "").split(",").map((s) => s.trim());
const out = path.resolve(opts.out || "לוח כיוונים.png");
if (dirs.length < 2) {
  console.error('usage: node directions-board.mjs --at 2.6 --labels "a,b,c" --out board.png <dir1> <dir2> [<dir3>]');
  process.exit(1);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const work = fs.mkdtempSync(path.join(os.tmpdir(), "board-"));

// Frame size of the first project, so portrait and landscape both lay out well.
const first = fs.readFileSync(path.join(dirs[0], "index.html"), "utf8");
const fw = Number(first.match(/data-width="(\d+)"/)?.[1] || 1080);
const fh = Number(first.match(/data-height="(\d+)"/)?.[1] || 1920);
const cellW = fh > fw ? 540 : 860;
const cellH = Math.round((cellW * fh) / fw);
const W = dirs.length * (cellW + 28) + 60;
const H = cellH + 150;

execSync(`node "${path.join(here, "new-project.mjs")}" "${work}" --size ${W}x${H} --fonts Heebo`, { stdio: "ignore" });

const figs = dirs.map((d, i) => {
  const snaps = path.join(work, `s${i}`);
  execSync(`${HF} snapshot --at ${at} --no-end -o "${snaps}"`, { cwd: d, stdio: "ignore" });
  const shot = fs.readdirSync(snaps).find((f) => f.startsWith("frame-"));
  fs.copyFileSync(path.join(snaps, shot), path.join(work, "assets", `d${i}.png`));
  const label = labels[i] ? `${i + 1} · ${labels[i]}` : `${i + 1}`;
  return `<figure><img src="assets/d${i}.png"><figcaption>${label}</figcaption></figure>`;
});

let html = fs.readFileSync(path.join(work, "index.html"), "utf8");
html = html
  .replace(/<div id="s1"[\s\S]*?<div id="bsd"[\s\S]*?<\/div>/, `<div id="s1" class="layer clip board" data-start="0" data-duration="1" data-track-index="1">${figs.join("")}</div>`)
  .replaceAll('data-duration="5"', 'data-duration="1"')
  .replace(/tl\.from\([^\n]*\n/, "\n")
  .replace(
    "</style>",
    `.board { display: flex; flex-direction: row; justify-content: center; gap: 28px; padding-top: 30px; background: #11201e; direction: rtl; }
      figure { display: flex; flex-direction: column; align-items: center; gap: 18px; }
      figure img { width: ${cellW}px; height: ${cellH}px; border-radius: 14px; display: block; }
      figcaption { font: 600 44px/1 var(--font-title); color: #fff; }
    </style>`,
  );
fs.writeFileSync(path.join(work, "index.html"), html);

execSync(`${HF} snapshot --at 0.5 --no-end -o snaps`, { cwd: work, stdio: "ignore" });
const shot = fs.readdirSync(path.join(work, "snaps")).find((f) => f.startsWith("frame-"));
fs.copyFileSync(path.join(work, "snaps", shot), out);
// On Windows the browser can hold the temp files a moment longer; a leftover temp folder is harmless.
try {
  fs.rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
} catch {}
console.log(`saved: ${out}`);
