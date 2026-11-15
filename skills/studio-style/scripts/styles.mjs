// The design-language catalog: every language as a small live sample, drawn in code in HER colors.
// Each draw(p, u, o) returns the inside of a 400×400 SVG. p = palette roles, u = unique id prefix,
// o = { initial, head, serif } (studio initial letter and fonts). The samples are also the starting
// point for a full piece: copy the function's SVG, scale it up, and build on it.
import { mix, rgbOf } from "./common.mjs";

export const rng = (seed) => () => {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
export function noise2(seed) {
  const r = rng(seed);
  const tab = Array.from({ length: 1024 }, () => r());
  const v = (i, j) => tab[((i * 374761393 + j * 668265263) >>> 0) % 1024];
  const s = (t) => t * t * (3 - 2 * t);
  return (x, y) => {
    const i = Math.floor(x), j = Math.floor(y), fx = s(x - i), fy = s(y - j);
    const a = v(i, j), b = v(i + 1, j), c = v(i, j + 1), d = v(i + 1, j + 1);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  };
}
const f1 = (n) => Math.round(n * 10) / 10;
const pts = (arr) => arr.map(([x, y]) => `${f1(x)},${f1(y)}`).join(" ");
const pathOf = (arr) => "M" + arr.map(([x, y]) => `${f1(x)} ${f1(y)}`).join(" L");
const bgRect = (c) => `<rect width="400" height="400" fill="${c}"/>`;
const grain = (u, op = 0.35, freq = 0.85) =>
  `<filter id="${u}gr" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="${freq}" numOctaves="2" seed="5"/>` +
  `<feColorMatrix type="matrix" values="0 0 0 0 .2  0 0 0 0 .2  0 0 0 0 .2  0 0 0 -1.4 1"/></filter>` +
  `<rect width="400" height="400" filter="url(#${u}gr)" opacity="${op}" style="mix-blend-mode:multiply"/>`;
const leaf = (x, y, a, len, extra = "") =>
  `<path transform="translate(${x} ${y}) rotate(${a})" d="M0 0 C${len * 0.3} ${-len * 0.3} ${len * 0.72} ${-len * 0.3} ${len} 0 C${len * 0.72} ${len * 0.3} ${len * 0.3} ${len * 0.3} 0 0Z" ${extra}/>`;
const T = (o, size, weight, fill, x, y, txt, extra = "") =>
  `<text x="${x}" y="${y}" font-family="${o.head}, Heebo, sans-serif" font-weight="${weight}" font-size="${size}" fill="${fill}" text-anchor="middle" ${extra}>${txt}</text>`;

export const FAMILIES = [
  { key: "light", he: "אור", line: "אור, זוהר והשתקפות" },
  { key: "line", he: "קו", line: "קו, קווי מתאר ותבנית קווית" },
  { key: "dot", he: "נקודה ורסטר", line: "נקודות, רסטר ושבבים" },
  { key: "shape", he: "צורה וגאומטריה", line: "צורה, גריד ותבנית" },
  { key: "matter", he: "חומר ומרקם", line: "נייר, אבן, זהב וצבעי מים" },
  { key: "color", he: "צבע ומשטח", line: "מעברי צבע, שקיפות ונפח" },
  { key: "heritage", he: "מסורת וכתב", line: "אמנות יהודית וטיפוגרפיה עברית" },
  { key: "scene", he: "סצנה ומוקאפ", line: "תמונה שלמה מקוד: משטח, נוף, במה" },
];

export const STYLES = [
  // ---------------- light ----------------
  { id: 1, fam: "light", he: "נקודות אור", en: "Bokeh", fits: "רקע חגיגי, הזמנת ערב",
    draw(p, u) {
      const r = rng(11), cols = [p.a2, p.soft, p.light, "#FFFFFF", p.a1];
      const layer = (n, a, b, op, blur, ring) => {
        let g = `<g${blur ? ` filter="url(#${u}${blur})"` : ""}>`;
        for (let i = 0; i < n; i++) {
          const c = cols[Math.floor(r() * cols.length)];
          g += `<circle cx="${f1(r() * 400)}" cy="${f1(r() * 400)}" r="${f1(a + r() * (b - a))}" fill="${c}" fill-opacity="${(op * (0.5 + r() * 0.5)).toFixed(2)}"${ring ? ` stroke="${c}" stroke-opacity=".7" stroke-width="1.5"` : ""}/>`;
        }
        return g + "</g>";
      };
      return `<defs><linearGradient id="${u}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${mix(p.ink, "#000", 0.25)}"/><stop offset="1" stop-color="${mix(p.ink, p.a1, 0.45)}"/></linearGradient>
        <filter id="${u}b1" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
        <filter id="${u}b2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/>${layer(14, 30, 72, 0.35, "b1")}${layer(16, 14, 34, 0.45, "b2")}${layer(10, 6, 15, 0.75, null, true)}`;
    } },
  { id: 2, fam: "light", he: "זוהר והילה", en: "Glow / Halo", fits: "כותרת על רקע כהה, לוגו",
    draw(p, u, o) {
      return `<defs><radialGradient id="${u}h"><stop offset="0" stop-color="${p.a2}" stop-opacity=".55"/><stop offset="1" stop-color="${p.a2}" stop-opacity="0"/></radialGradient>
        <filter id="${u}b1" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="16"/></filter>
        <filter id="${u}b2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter></defs>
        ${bgRect(mix(p.ink, "#000", 0.3))}<circle cx="200" cy="200" r="170" fill="url(#${u}h)"/>
        <g filter="url(#${u}b1)">${T(o, 150, 700, p.a2, 200, 252, "אור")}</g>
        <g filter="url(#${u}b2)" opacity=".8">${T(o, 150, 700, p.soft, 200, 252, "אור")}</g>
        ${T(o, 150, 700, mix(p.light, "#fff", 0.5), 200, 252, "אור")}`;
    } },
  { id: 3, fam: "light", he: "דליפת אור", en: "Light leak", fits: "נוסטלגיה, חום, רקע לציטוט",
    draw(p, u) {
      const blob = (cx, cy, r, c, op) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#${u}${c})" opacity="${op}"/>`;
      return `<defs>
        <radialGradient id="${u}w1"><stop offset="0" stop-color="#FFE2A0"/><stop offset="1" stop-color="#FFE2A0" stop-opacity="0"/></radialGradient>
        <radialGradient id="${u}w2"><stop offset="0" stop-color="#FF9A62"/><stop offset="1" stop-color="#FF9A62" stop-opacity="0"/></radialGradient>
        <radialGradient id="${u}w3"><stop offset="0" stop-color="${p.a2}"/><stop offset="1" stop-color="${p.a2}" stop-opacity="0"/></radialGradient>
        <linearGradient id="${u}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(p.a1, p.ink, 0.35)}"/><stop offset="1" stop-color="${mix(p.ink, "#000", 0.2)}"/></linearGradient>
        <filter id="${u}b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/>
        <g filter="url(#${u}b)" opacity=".55"><rect x="40" y="150" width="90" height="190" rx="10" fill="${p.soft}"/><circle cx="210" cy="250" r="55" fill="${p.light}"/></g>
        <g style="mix-blend-mode:screen">${blob(420, 60, 210, "w2", 0.9)}${blob(400, 230, 150, "w1", 0.95)}${blob(-30, 400, 190, "w3", 0.7)}${blob(360, 380, 120, "w2", 0.6)}
        <rect x="300" y="-20" width="40" height="440" fill="#FFF3D0" opacity=".25" filter="url(#${u}b)"/></g>
        ${grain(u, 0.25)}`;
    } },
  { id: 4, fam: "light", he: "קרני אור", en: "Light rays", fits: "חג, התרוממות, שער",
    draw(p, u) {
      const r = rng(4), sx = 320, sy = -40;
      let rays = "";
      for (let k = 0; k < 9; k++) {
        const a = (100 + k * 8 + r() * 4) * Math.PI / 180, w = (2.5 + r() * 4) * Math.PI / 180;
        rays += `<polygon points="${pts([[sx, sy], [sx + 640 * Math.cos(a - w), sy + 640 * Math.sin(a - w)], [sx + 640 * Math.cos(a + w), sy + 640 * Math.sin(a + w)]])}" fill="url(#${u}rg)" opacity="${(0.35 + r() * 0.4).toFixed(2)}"/>`;
      }
      let dust = "";
      for (let i = 0; i < 40; i++) dust += `<circle cx="${f1(120 + r() * 260)}" cy="${f1(r() * 380)}" r="${f1(0.6 + r() * 1.6)}" fill="#fff" opacity="${(0.3 + r() * 0.6).toFixed(2)}"/>`;
      return `<defs><linearGradient id="${u}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.light}"/><stop offset="1" stop-color="${p.a1}"/></linearGradient>
        <radialGradient id="${u}rg" gradientUnits="userSpaceOnUse" cx="${sx}" cy="${sy}" r="520"><stop offset="0" stop-color="#fff" stop-opacity=".95"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
        <filter id="${u}b"><feGaussianBlur stdDeviation="3"/></filter></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/><g filter="url(#${u}b)">${rays}</g>${dust}`;
    } },
  { id: 5, fam: "light", he: "ריצוד מים", en: "Caustics", fits: "רעננות, מים, קיץ",
    draw(p, u) {
      const caus = (id, freq, seed, op) => `<filter id="${u}${id}" x="0" y="0" width="100%" height="100%"><feTurbulence type="turbulence" baseFrequency="${freq}" numOctaves="2" seed="${seed}"/>
        <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  -2.6 0 0 0 1.05"/><feComponentTransfer><feFuncA type="gamma" exponent="3.2"/></feComponentTransfer><feGaussianBlur stdDeviation=".6"/></filter>
        <rect width="400" height="400" filter="url(#${u}${id})" opacity="${op}"/>`;
      return `<defs><linearGradient id="${u}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${mix(p.a1, "#fff", 0.15)}"/><stop offset="1" stop-color="${mix(p.a1, p.ink, 0.45)}"/></linearGradient></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/>${caus("c1", 0.022, 3, 0.85)}${caus("c2", 0.035, 8, 0.45)}`;
    } },
  { id: 6, fam: "light", he: "זוהר צפוני", en: "Aurora", fits: "לילה, קסם, מודרני־רך",
    draw(p, u) {
      const r = rng(6);
      let stars = "";
      for (let i = 0; i < 70; i++) stars += `<circle cx="${f1(r() * 400)}" cy="${f1(r() * 260)}" r="${f1(0.4 + r() * 1.2)}" fill="#fff" opacity="${(0.3 + r() * 0.7).toFixed(2)}"/>`;
      // A curtain = many thin vertical strokes standing on a wavy base line, each fading upward.
      const n = noise2(66);
      let rays = "";
      for (let x = -10; x <= 410; x += 2.5) {
        const base = 210 + 45 * Math.sin(x / 70) + 20 * Math.sin(x / 23);
        const h = 90 + 110 * n(x * 0.02, 1.5), op = Math.max(0, n(x * 0.035, 7) - 0.25) * 1.3;
        if (op > 0.02) rays += `<line x1="${f1(x)}" y1="${f1(base)}" x2="${f1(x + 6)}" y2="${f1(base - h)}" stroke="url(#${u}${x % 5 < 2.5 ? "c1" : "c2"})" stroke-width="3" opacity="${op.toFixed(2)}"/>`;
      }
      return `<defs><linearGradient id="${u}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(p.ink, "#000", 0.55)}"/><stop offset="1" stop-color="${mix(p.ink, p.a1, 0.25)}"/></linearGradient>
        <linearGradient id="${u}c1" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${p.a2}" stop-opacity=".95"/><stop offset=".35" stop-color="${p.soft}" stop-opacity=".7"/><stop offset="1" stop-color="${p.light}" stop-opacity="0"/></linearGradient>
        <linearGradient id="${u}c2" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${p.light}" stop-opacity=".9"/><stop offset=".5" stop-color="${p.a2}" stop-opacity=".5"/><stop offset="1" stop-color="${p.a1}" stop-opacity="0"/></linearGradient>
        <filter id="${u}b" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2"/></filter><filter id="${u}b2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="16"/></filter></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/>${stars}
        <g style="mix-blend-mode:screen"><g filter="url(#${u}b2)" opacity=".7">${rays}</g><g filter="url(#${u}b)">${rays}</g></g>
        <path d="M0 330 C80 300 150 320 220 300 C300 280 350 310 400 295 V400 H0Z" fill="${mix(p.ink, "#000", 0.6)}"/>`;
    } },
  // ---------------- line ----------------
  { id: 7, fam: "line", he: "ציור קו", en: "Line art", fits: "עדינות, מינימליזם, הזמנות",
    draw(p) {
      const L = (x, y, a, len) => leaf(x, y, a, len) + `<path transform="translate(${x} ${y}) rotate(${a})" d="M2 0 L${len - 3} 0"/>`;
      return `${bgRect(p.bg)}<circle cx="232" cy="185" r="118" fill="${p.light}"/>
        <g fill="none" stroke="${p.ink}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M168 342 C146 300 148 252 180 226 C188 219 190 206 186 196 L214 196 C210 206 212 219 220 226 C252 252 254 300 232 342 Z"/>
        <path d="M178 228 H222"/><path d="M80 342 H320"/>
        <path d="M200 196 C206 150 232 110 272 80"/><path d="M206 162 C186 132 160 116 128 110"/><path d="M224 128 C242 120 256 104 262 88"/>
        ${L(242, 108, -40, 40)}${L(262, 90, -62, 34)}${L(272, 80, -18, 30)}${L(166, 118, 200, 38)}${L(142, 111, 172, 30)}${L(216, 150, -28, 36)}${L(190, 142, 212, 30)}</g>`;
    } },
  { id: 8, fam: "line", he: "קו רציף", en: "Continuous line", fits: "אישי, אמנותי, שער",
    draw(p) {
      const P = [];
      for (let t = 0; t <= 1; t += 0.02) P.push([200 + 18 * Math.sin(t * 3), 372 - t * 160]);
      for (let t = 0; t <= Math.PI * 2; t += 0.04) { const r = 62 + 22 * Math.sin(5 * t); P.push([205 + r * Math.sin(t), 168 + r * Math.cos(t) * 0.95]); }
      for (let t = 0; t <= Math.PI * 2; t += 0.05) { const r = 26 + 7 * Math.sin(5 * t + 1); P.push([205 + r * Math.sin(-t), 168 + r * Math.cos(t)]); }
      for (let t = 0; t <= 1; t += 0.03) P.push([205 - t * 4, 194 + t * 90]);
      for (let t = 0; t <= Math.PI; t += 0.06) P.push([201 + 70 * Math.sin(t) * (1 - t / 4), 284 - 34 * Math.sin(t * 2) - t * 6]);
      for (let t = 0; t <= 1; t += 0.05) P.push([201 - t * 2, 268 + t * 100]);
      return `${bgRect(p.bg)}<ellipse cx="230" cy="190" rx="120" ry="140" fill="${p.soft}" opacity=".65"/>
        <path d="${pathOf(P)}" fill="none" stroke="${p.ink}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>`;
    } },
  { id: 9, fam: "line", he: "קווי גובה", en: "Topographic contours", fits: "טבע, מסע, רקע שקט",
    draw(p, u) {
      let c = "";
      for (let i = 1; i < 30; i++) c += `<circle cx="240" cy="180" r="${i * 11}" stroke="${i % 5 === 0 ? p.ink : p.a1}" stroke-width="${i % 5 === 0 ? 2 : 1}"/>`;
      for (let i = 1; i < 9; i++) c += `<circle cx="70" cy="340" r="${i * 11}" stroke="${i % 5 === 0 ? p.ink : p.a1}" stroke-width="${i % 5 === 0 ? 2 : 1}"/>`;
      return `<defs><filter id="${u}d" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency="0.011" numOctaves="2" seed="7" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="80" xChannelSelector="R" yChannelSelector="G"/></filter></defs>
        ${bgRect(p.light)}<g filter="url(#${u}d)" fill="none" opacity=".9">${c}</g>`;
    } },
  { id: 10, fam: "line", he: "גיליוש", en: "Guilloche", fits: "תעודה, שובר, יוקרה",
    draw(p) {
      let g = "";
      const cols = [p.a1, p.ink, p.a2];
      for (let j = 0; j < 14; j++) {
        const P = [], R = 105, r = 15, d = 40 + j * 2.2, rot = (j * 360) / 7 / 14 * Math.PI / 180;
        for (let t = 0; t <= Math.PI * 2 + 0.01; t += 0.01) {
          const x = (R - r) * Math.cos(t) + d * Math.cos(((R - r) / r) * t), y = (R - r) * Math.sin(t) - d * Math.sin(((R - r) / r) * t);
          P.push([200 + x * Math.cos(rot) - y * Math.sin(rot), 200 + x * Math.sin(rot) + y * Math.cos(rot)]);
        }
        g += `<path d="${pathOf(P)}" stroke="${cols[j % 3]}" stroke-width=".7" fill="none" opacity=".85"/>`;
      }
      for (let j = 0; j < 6; j++) {
        const P = [];
        for (let t = 0; t <= Math.PI * 2 + 0.01; t += 0.005) { const rr = 172 + 9 * Math.sin(36 * t + j * 0.5); P.push([200 + rr * Math.cos(t), 200 + rr * Math.sin(t)]); }
        g += `<path d="${pathOf(P)}" stroke="${cols[j % 2]}" stroke-width=".6" fill="none"/>`;
      }
      return `${bgRect(p.bg)}${g}`;
    } },
  { id: 11, fam: "line", he: "אופ־ארט", en: "Op art", fits: "עוצמה, תנועה, כרזה",
    draw(p) {
      const lines = [];
      for (let y0 = -10; y0 <= 410; y0 += 11) {
        const L = [];
        for (let x = 0; x <= 400; x += 5) {
          const g = Math.exp(-((x - 200) ** 2) / (2 * 85 ** 2)) * Math.exp(-((y0 - 200) ** 2) / (2 * 140 ** 2));
          L.push([x, 200 + (y0 - 200) * (1 + 0.9 * g)]);
        }
        lines.push(L);
      }
      let s = "";
      for (let i = 0; i < lines.length - 1; i += 2) s += `<polygon points="${pts([...lines[i], ...lines[i + 1].slice().reverse()])}" fill="${p.ink}"/>`;
      return `${bgRect(p.bg)}${s}`;
    } },
  { id: 12, fam: "line", he: "שדה זרימה", en: "Flow field", fits: "אורגני, עשיר, רקע מותג",
    draw(p) {
      const n = noise2(5), r = rng(12), cols = [p.a1, p.a2, p.ink, p.soft];
      let s = "";
      for (let k = 0; k < 420; k++) {
        let x = r() * 420 - 10, y = r() * 420 - 10;
        const P = [[x, y]];
        for (let i = 0; i < 28; i++) { const a = n(x * 0.006, y * 0.006) * Math.PI * 4; x += Math.cos(a) * 3; y += Math.sin(a) * 3; P.push([x, y]); }
        s += `<path d="${pathOf(P)}" stroke="${cols[k % 4]}" stroke-width="1.3" fill="none" stroke-linecap="round" opacity=".75"/>`;
      }
      return `${bgRect(p.bg)}${s}`;
    } },
  // ---------------- dot ----------------
  { id: 13, fam: "dot", he: "רסטר", en: "Halftone", fits: "רטרו, דפוס, כרזה",
    draw(p) {
      const grid = (ang, step, tone, fill, max) => {
        let s = "";
        const c = Math.cos(ang), sn = Math.sin(ang);
        for (let a = -300; a <= 300; a += step) for (let b = -300; b <= 300; b += step) {
          const x = 200 + a * c - b * sn, y = 200 + a * sn + b * c;
          if (x < -6 || y < -6 || x > 406 || y > 406) continue;
          const t = tone(x, y);
          if (t > 0.03) s += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(max * Math.sqrt(Math.min(1, t)))}" fill="${fill}"/>`;
        }
        return s;
      };
      const t1 = (x, y) => 0.95 * Math.exp(-((x - 150) ** 2 + (y - 145) ** 2) / (2 * 90 ** 2)) + 0.12;
      const t2 = (x, y) => Math.max(0, (x + y - 380) / 420);
      return `${bgRect(p.light)}<g style="mix-blend-mode:multiply">${grid(Math.PI / 12, 12, t2, p.a1, 6.4)}</g><g style="mix-blend-mode:multiply">${grid(Math.PI / 4, 12, t1, p.ink, 6.2)}</g>`;
    } },
  { id: 14, fam: "dot", he: "ריסוגרף", en: "Risograph", fits: "אינדי, חוברת, כרזה צבעונית",
    draw(p, u) {
      return `<defs><filter id="${u}r" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".95" numOctaves="2" seed="3" result="n"/>
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.6 2.2" result="a"/><feComposite in="SourceGraphic" in2="a" operator="in"/></filter></defs>
        ${bgRect(mix(p.bg, "#FFFFFF", 0.4))}
        <g filter="url(#${u}r)" style="mix-blend-mode:multiply" opacity=".9"><circle cx="165" cy="170" r="105" fill="${p.a1}"/><rect x="40" y="300" width="230" height="22" fill="${p.a1}"/><rect x="40" y="335" width="160" height="22" fill="${p.a1}"/></g>
        <g filter="url(#${u}r)" style="mix-blend-mode:multiply" opacity=".85" transform="translate(7 5)"><path d="M170 120 C240 80 330 120 340 200 C350 280 270 330 220 300 C170 270 120 180 170 120Z" fill="${p.a2}"/><circle cx="330" cy="330" r="36" fill="${p.a2}"/></g>`;
    } },
  { id: 15, fam: "dot", he: "דיתרינג", en: "Dither / 1-bit", fits: "רטרו־דיגיטלי, חדשני",
    draw(p) {
      const B = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], cell = 5;
      let s = "";
      for (let gy = 0; gy < 80; gy++) {
        let run = -1;
        for (let gx = 0; gx <= 80; gx++) {
          const x = gx * cell + 2.5, y = gy * cell + 2.5;
          let tone;
          const dx = (x - 200) / 125, dy = (y - 190) / 125, d2 = dx * dx + dy * dy;
          if (d2 < 1) { const nz = Math.sqrt(1 - d2); tone = Math.max(0, -0.55 * dx - 0.6 * dy + 0.6 * nz) * 0.95 + 0.05; }
          else tone = 0.62 + 0.3 * (1 - y / 400);
          const on = gx < 80 && (1 - tone) * 16 > B[gy % 4][gx % 4] + 0.5;
          if (on && run < 0) run = gx;
          if (!on && run >= 0) { s += `<rect x="${run * cell}" y="${gy * cell}" width="${(gx - run) * cell}" height="${cell}"/>`; run = -1; }
        }
      }
      return `${bgRect(p.light)}<g fill="${p.ink}">${s}</g>`;
    } },
  { id: 16, fam: "dot", he: "פסיפס", en: "Mosaic", fits: "ים תיכוני, מסורתי, אריח",
    draw(p) {
      const r = rng(16), n = noise2(3);
      let s = "";
      for (let gy = 0; gy < 22; gy++) for (let gx = 0; gx < 22; gx++) {
        const cx = gx * 18.2 + 9, cy = gy * 18.2 + 9, d = Math.hypot(cx - 200, cy - 200);
        let c = d < 62 ? p.a1 : d < 74 ? p.light : d < 122 ? p.a2 : d < 134 ? p.light : n(cx * 0.03, cy * 0.03) > 0.5 ? p.soft : p.bg;
        if (d < 30) c = p.ink;
        c = mix(c, r() > 0.5 ? "#FFFFFF" : "#000000", r() * 0.1);
        s += `<rect x="${f1(cx - 7.6)}" y="${f1(cy - 7.6)}" width="15.2" height="15.2" rx="2" fill="${c}" transform="rotate(${f1((r() - 0.5) * 12)} ${f1(cx)} ${f1(cy)})"/>`;
      }
      return `${bgRect(mix(p.bg, p.ink, 0.28))}${s}`;
    } },
  { id: 17, fam: "dot", he: "טרצו", en: "Terrazzo", fits: "עכשווי, אדריכלי, אריזה",
    draw(p, u) {
      const r = rng(17), cols = [p.a1, p.a2, p.soft, p.ink, p.a3];
      const chip = (cx, cy, rad) => {
        const k = 5 + Math.floor(r() * 3), P = [];
        for (let i = 0; i < k; i++) { const a = (i / k) * Math.PI * 2 + r() * 0.6; P.push([cx + Math.cos(a) * rad * (0.6 + r() * 0.5), cy + Math.sin(a) * rad * (0.6 + r() * 0.5)]); }
        return `<polygon points="${pts(P)}" fill="${cols[Math.floor(r() * cols.length)]}"/>`;
      };
      let s = "";
      for (let i = 0; i < 150; i++) s += chip(r() * 400, r() * 400, 2 + r() * 8);
      for (let i = 0; i < 9; i++) s += chip(r() * 400, r() * 400, 13 + r() * 10);
      return `${bgRect(mix(p.bg, "#FFFFFF", 0.4))}${s}${grain(u, 0.25)}`;
    } },
  { id: 18, fam: "dot", he: "נקודות בקצב", en: "Polka / dot grid", fits: "משחקי, ילדות, אריזה",
    draw(p) {
      let s = "";
      for (let gy = 0; gy < 11; gy++) for (let gx = 0; gx < 11; gx++) {
        const x = gx * 40 + (gy % 2 ? 20 : 0), y = gy * 40 + 10, big = (gx + gy) % 3 === 0;
        s += `<circle cx="${x}" cy="${y}" r="${big ? 11 : 6}" fill="${big ? p.a1 : p.a2}"/>`;
      }
      return `${bgRect(p.light)}${s}<circle cx="270" cy="150" r="70" fill="none" stroke="${p.ink}" stroke-width="3"/>`;
    } },
  // ---------------- shape ----------------
  { id: 19, fam: "shape", he: "באוהאוס", en: "Bauhaus", fits: "אייקוני, מודרניסטי, כרזה",
    draw(p) {
      return `<rect x="200" y="0" width="200" height="200" fill="${p.a1}"/><circle cx="300" cy="100" r="78" fill="${p.light}"/>
        <rect x="0" y="0" width="200" height="200" fill="${p.light}"/><path d="M20 200 A80 80 0 0 1 180 200Z" fill="${p.ink}"/>
        <rect x="0" y="200" width="200" height="200" fill="${p.a2}"/><path d="M0 200 H120 A120 120 0 0 1 0 320Z" fill="${p.bg}"/>
        <rect x="200" y="200" width="200" height="200" fill="${p.ink}"/><rect x="250" y="250" width="100" height="100" fill="${p.a1}" transform="rotate(45 300 300)"/><circle cx="300" cy="300" r="22" fill="${p.light}"/>
        <path d="M200 0 V400 M0 200 H400" stroke="${p.ink}" stroke-width="3"/>`;
    } },
  { id: 20, fam: "shape", he: "סגנון שוויצרי", en: "Swiss / International", fits: "מקצועי, נקי, דוח וכרזה",
    draw(p, u, o) {
      let bars = "";
      for (let i = 0; i < 6; i++) bars += `<rect x="${380 - 120 + (i % 2) * 20}" y="${262 + i * 14}" width="${120 - (i % 2) * 20}" height="5" fill="${mix(p.ink, p.bg, 0.55)}"/>`;
      return `${bgRect(p.bg)}<g stroke="${mix(p.bg, p.ink, 0.16)}" stroke-width="1"><path d="M20 0 V400 M147 0 V400 M273 0 V400 M380 0 V400 M0 230 H400"/></g>
        <text x="380" y="190" font-family="${o.head}, Heebo, sans-serif" font-weight="900" font-size="150" fill="${p.ink}" text-anchor="end" letter-spacing="-4">גריד</text>
        <circle cx="105" cy="305" r="62" fill="${p.a1}"/>${bars}<text x="380" y="252" font-family="Heebo" font-weight="700" font-size="16" fill="${p.ink}" text-anchor="end">01</text>`;
    } },
  { id: 21, fam: "shape", he: "ממפיס", en: "Memphis", fits: "שמח, אנרגטי, ילדים",
    draw(p) {
      const r = rng(21), cols = [p.a1, p.a2, p.soft, p.ink];
      let conf = "";
      for (let i = 0; i < 26; i++) conf += `<rect x="${f1(r() * 380)}" y="${f1(r() * 380)}" width="12" height="4" fill="${cols[i % 4]}" transform="rotate(${f1(r() * 180)} ${f1(r() * 400)} ${f1(r() * 400)})"/>`;
      let dots = "";
      for (let y = 0; y < 5; y++) for (let x = 0; x < 6; x++) dots += `<circle cx="${250 + x * 12}" cy="${290 + y * 12}" r="2.2" fill="${p.ink}"/>`;
      return `${bgRect(p.light)}${conf}${dots}
        <path d="M40 90 Q70 50 100 90 T160 90 T220 90" stroke="${p.a1}" stroke-width="12" fill="none" stroke-linecap="round"/>
        <circle cx="300" cy="110" r="52" fill="${p.a2}" stroke="${p.ink}" stroke-width="3"/>
        <polygon points="80,330 150,200 220,330" fill="none" stroke="${p.ink}" stroke-width="4"/>
        <path d="M250 220 l20 -20 l20 20 l20 -20 l20 20 l20 -20" stroke="${p.ink}" stroke-width="5" fill="none"/>
        <rect x="120" y="150" width="60" height="60" fill="${p.soft}" transform="rotate(20 150 180)"/>`;
    } },
  { id: 22, fam: "shape", he: "אריחי טרושה", en: "Truchet tiles", fits: "דוגמה לאריזה, נייר עטיפה",
    draw(p) {
      const r = rng(3), c = 50, w = 10;
      let s = "";
      for (let gy = 0; gy < 8; gy++) for (let gx = 0; gx < 8; gx++) {
        const x = gx * c, y = gy * c, col = [p.soft, p.a1, p.a2][(gx + gy) % 3];
        const d = r() < 0.5
          ? `M${x + c / 2},${y} A${c / 2},${c / 2} 0 0 1 ${x},${y + c / 2} M${x + c},${y + c / 2} A${c / 2},${c / 2} 0 0 0 ${x + c / 2},${y + c}`
          : `M${x + c / 2},${y} A${c / 2},${c / 2} 0 0 0 ${x + c},${y + c / 2} M${x},${y + c / 2} A${c / 2},${c / 2} 0 0 1 ${x + c / 2},${y + c}`;
        s += `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`;
      }
      return `${bgRect(p.bg)}${s}`;
    } },
  { id: 23, fam: "shape", he: "איזומטרי", en: "Isometric", fits: "אינפוגרפיקה, מבנה, מוצר",
    draw(p) {
      const s = 46, cx = 200, cy = 250, c30 = Math.cos(Math.PI / 6);
      const P = (i, j, k) => [cx + (i - j) * s * c30, cy + (i + j) * s * 0.5 - k * s];
      const cube = (i, j, k) => {
        const a = P(i, j, k + 1), b = P(i + 1, j, k + 1), c = P(i + 1, j + 1, k + 1), d = P(i, j + 1, k + 1), e = P(i + 1, j + 1, k), g = P(i, j + 1, k), h = P(i + 1, j, k);
        return `<polygon points="${pts([a, b, c, d])}" fill="${p.light}"/><polygon points="${pts([d, c, e, g])}" fill="${p.a1}"/><polygon points="${pts([c, b, h, e])}" fill="${mix(p.a1, p.ink, 0.45)}"/>`;
      };
      const list = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0], [0, 2, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [0, 0, 2]];
      list.sort((A, B) => (A[0] + A[1]) - (B[0] + B[1]) || A[2] - B[2]);
      const fl = [P(-1, -1, 0), P(4, -1, 0), P(4, 4, 0), P(-1, 4, 0)];
      return `${bgRect(p.bg)}<polygon points="${pts(fl)}" fill="${p.soft}" opacity=".5"/>${list.map((q) => cube(...q)).join("")}`;
    } },
  { id: 24, fam: "shape", he: "לואו־פולי", en: "Low poly", fits: "טכנולוגי, נוף, רקע",
    draw(p) {
      const r = rng(24), n = noise2(9), N = 8, G = [];
      for (let j = 0; j <= N; j++) { G.push([]); for (let i = 0; i <= N; i++) { const edge = i === 0 || j === 0 || i === N || j === N; G[j].push([i * 50 + (edge ? 0 : (r() - 0.5) * 34), j * 50 + (edge ? 0 : (r() - 0.5) * 34)]); } }
      let s = "";
      const tri = (A, B, C) => { const y = (A[1] + B[1] + C[1]) / 3, x = (A[0] + B[0] + C[0]) / 3; const t = Math.min(1, Math.max(0, y / 420 + (n(x * 0.012, y * 0.012) - 0.5) * 0.5)); const c = t < 0.5 ? mix(p.light, p.a1, t * 2) : mix(p.a1, p.ink, (t - 0.5) * 1.6); return `<polygon points="${pts([A, B, C])}" fill="${c}" stroke="${c}" stroke-width=".6"/>`; };
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const a = G[j][i], b = G[j][i + 1], c = G[j + 1][i + 1], d = G[j + 1][i]; s += (i + j) % 2 ? tri(a, b, c) + tri(a, c, d) : tri(a, b, d) + tri(b, c, d); }
      return s;
    } },
  // ---------------- matter ----------------
  { id: 25, fam: "matter", he: "נייר וגרעין", en: "Paper grain", fits: "חמים, מודפס, הזמנה",
    draw(p, u) {
      return `<defs><filter id="${u}sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="3" dy="8" stdDeviation="8" flood-color="${p.ink}" flood-opacity=".3"/></filter>
        <filter id="${u}pg" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".75" numOctaves="3" seed="2"/><feColorMatrix type="matrix" values="0 0 0 0 .45  0 0 0 0 .42  0 0 0 0 .38  0 0 0 -1.2 .95"/></filter>
        <linearGradient id="${u}fold" x1="0" x2="1"><stop offset=".47" stop-color="#000" stop-opacity="0"/><stop offset=".5" stop-color="#000" stop-opacity=".09"/><stop offset=".53" stop-color="#fff" stop-opacity=".25"/><stop offset=".6" stop-color="#fff" stop-opacity="0"/></linearGradient>
        <clipPath id="${u}c"><rect x="60" y="40" width="280" height="320"/></clipPath></defs>
        ${bgRect(mix(p.bg, p.ink, 0.18))}
        <g transform="rotate(-3 200 200)"><rect x="60" y="40" width="280" height="320" fill="${mix(p.bg, "#FFFFFF", 0.5)}" filter="url(#${u}sh)"/>
        <g clip-path="url(#${u}c)"><rect x="60" y="40" width="280" height="320" filter="url(#${u}pg)" opacity=".5" style="mix-blend-mode:multiply"/><rect x="60" y="40" width="280" height="320" fill="url(#${u}fold)"/></g>
        <rect x="150" y="130" width="100" height="6" fill="${p.a1}"/><rect x="120" y="150" width="160" height="4" fill="${mix(p.ink, p.bg, 0.5)}"/><rect x="135" y="162" width="130" height="4" fill="${mix(p.ink, p.bg, 0.5)}"/></g>`;
    } },
  { id: 26, fam: "matter", he: "נייר בשכבות", en: "Layered papercut", fits: "עומק, ילדים, שער",
    draw(p, u) {
      const cols = [p.light, p.soft, p.a2, p.a1, mix(p.a1, p.ink, 0.5), p.ink];
      let s = "";
      cols.forEach((c, k) => {
        const y = 150 + k * 42, a = 18 + k * 3, ph = k * 1.3;
        const P = [[0, 400]];
        for (let x = 0; x <= 400; x += 10) P.push([x, y + a * Math.sin(x / 55 + ph) + 8 * Math.sin(x / 23 + ph * 2)]);
        P.push([400, 400]);
        s += `<polygon points="${pts(P)}" fill="${c}" filter="url(#${u}ds)"/>`;
      });
      return `<defs><filter id="${u}ds" x="-10%" y="-30%" width="120%" height="160%"><feDropShadow dx="0" dy="-5" stdDeviation="5" flood-color="#000" flood-opacity=".3"/></filter></defs>
        ${bgRect(mix(p.bg, p.light, 0.5))}<circle cx="290" cy="110" r="50" fill="${p.a2}"/>${s}`;
    } },
  { id: 27, fam: "matter", he: "הטבעה", en: "Letterpress / Emboss", fits: "הזמנות יוקרה, כרטיס ביקור",
    draw(p, u, o) {
      const inner = `<filter id="${u}in" x="-10%" y="-10%" width="120%" height="120%"><feFlood flood-color="#000" flood-opacity=".55"/><feComposite in2="SourceAlpha" operator="out"/>
        <feOffset dx="0" dy="2.2"/><feGaussianBlur stdDeviation="1.4"/><feComposite in2="SourceAlpha" operator="in" result="s"/><feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="s"/></feMerge></filter>`;
      let blind = "";
      for (let i = 0; i < 9; i++) blind += `<circle cx="${80 + i * 30}" cy="330" r="7" fill="${p.bg}" filter="url(#${u}in)"/>`;
      return `<defs>${inner}</defs>${bgRect(p.bg)}${grain(u, 0.3)}
        <text x="200" y="232" font-family="${o.serif}, serif" font-weight="700" font-size="112" fill="#FFFFFF" text-anchor="middle" opacity=".8">שמחה</text>
        <text x="200" y="230" font-family="${o.serif}, serif" font-weight="700" font-size="112" fill="${p.a1}" text-anchor="middle" filter="url(#${u}in)">שמחה</text>
        <rect x="70" y="270" width="260" height="1.4" fill="${p.a1}" filter="url(#${u}in)"/>${blind}`;
    } },
  { id: 28, fam: "matter", he: "ריקוע זהב", en: "Foil stamping", fits: "חגיגי, יוקרתי, מונוגרמה",
    draw(p, u, o) {
      return `<defs><linearGradient id="${u}gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7A5A24"/><stop offset=".25" stop-color="#E8CF86"/><stop offset=".5" stop-color="#A8822F"/><stop offset=".72" stop-color="#F6E7B2"/><stop offset="1" stop-color="#8D6A2B"/></linearGradient>
        <filter id="${u}foil" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="4" result="n"/>
        <feSpecularLighting in="n" surfaceScale="1.6" specularConstant=".9" specularExponent="16" lighting-color="#FFF6D6" result="s"><feDistantLight azimuth="225" elevation="48"/></feSpecularLighting>
        <feComposite in="s" in2="SourceAlpha" operator="in" result="s2"/><feComposite in="SourceGraphic" in2="s2" operator="arithmetic" k2="1" k3=".5"/></filter></defs>
        ${bgRect(mix(p.ink, "#000", 0.2))}${grain(u, 0.35)}
        <g filter="url(#${u}foil)"><circle cx="200" cy="200" r="132" fill="none" stroke="url(#${u}gold)" stroke-width="5"/><circle cx="200" cy="200" r="120" fill="none" stroke="url(#${u}gold)" stroke-width="1.5"/>
        <text x="200" y="258" font-family="${o.serif}, serif" font-weight="700" font-size="170" fill="url(#${u}gold)" text-anchor="middle">${o.initial}</text></g>`;
    } },
  { id: 29, fam: "matter", he: "שיש", en: "Marble", fits: "יוקרה, אסתטיקה, רקע",
    draw(p, u) {
      const r = rng(29);
      let v = "", soft = "";
      for (let i = 0; i < 7; i++) {
        const x = -80 + i * 75 + r() * 30;
        v += `<path d="M${f1(x)} -30 C${f1(x + 60)} 120 ${f1(x + 20)} 260 ${f1(x + 150)} 440" stroke="${i === 3 ? p.a1 : mix(p.ink, p.bg, 0.3)}" stroke-width="${f1(0.8 + r() * 2.2)}" opacity="${(0.45 + r() * 0.4).toFixed(2)}" fill="none"/>`;
        soft += `<path d="M${f1(x + 20)} -30 C${f1(x + 80)} 120 ${f1(x + 40)} 260 ${f1(x + 170)} 440" stroke="${mix(p.ink, p.bg, 0.5)}" stroke-width="14" opacity=".12" fill="none"/>`;
      }
      return `<defs><filter id="${u}m" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" baseFrequency=".012" numOctaves="5" seed="12" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="70" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation=".45"/></filter>
        <filter id="${u}m2" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" baseFrequency=".012" numOctaves="5" seed="12" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="70" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation="5"/></filter>
        <filter id="${u}cl" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".006" numOctaves="3" seed="2"/><feColorMatrix type="matrix" values="0 0 0 0 ${rgbOf(p.soft)[0] / 255}  0 0 0 0 ${rgbOf(p.soft)[1] / 255}  0 0 0 0 ${rgbOf(p.soft)[2] / 255}  0 0 0 1.6 -.7"/></filter></defs>
        ${bgRect(mix(p.bg, "#FFFFFF", 0.65))}<rect width="400" height="400" filter="url(#${u}cl)" opacity=".5"/><g filter="url(#${u}m2)">${soft}</g><g filter="url(#${u}m)">${v}</g>`;
    } },
  { id: 30, fam: "matter", he: "כתם צבעי מים", en: "Watercolor wash", fits: "רך, ידני, הזמנה",
    draw(p, u) {
      const blob = (cx, cy, r, c, seed) => `<filter id="${u}w${seed}" x="-40%" y="-40%" width="180%" height="180%"><feTurbulence type="fractalNoise" baseFrequency=".022" numOctaves="3" seed="${seed}" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="46" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation="1.1"/></filter>
        <g filter="url(#${u}w${seed})" style="mix-blend-mode:multiply"><circle cx="${cx}" cy="${cy}" r="${r}" fill="${c}" fill-opacity=".42"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${c}" stroke-opacity=".5" stroke-width="3"/><circle cx="${cx - 12}" cy="${cy + 8}" r="${r * 0.6}" fill="${c}" fill-opacity=".18"/></g>`;
      return `${bgRect(mix(p.bg, "#FFFFFF", 0.5))}${grain(u, 0.3)}${blob(150, 160, 100, p.a1, 3)}${blob(260, 230, 95, p.a2, 7)}${blob(170, 290, 70, p.soft, 11)}`;
    } },
  // ---------------- color ----------------
  { id: 31, fam: "color", he: "מעבר צבע רשת", en: "Mesh gradient", fits: "עכשווי, דיגיטלי, רקע",
    draw(p, u) {
      return `<defs><filter id="${u}b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="55"/></filter><clipPath id="${u}c"><rect width="400" height="400"/></clipPath></defs>
        <g clip-path="url(#${u}c)">${bgRect(p.a1)}<g filter="url(#${u}b)"><circle cx="70" cy="70" r="160" fill="${p.a2}"/><circle cx="340" cy="80" r="150" fill="${p.soft}"/><circle cx="320" cy="340" r="170" fill="${p.a3}"/><circle cx="70" cy="330" r="150" fill="${p.light}"/><circle cx="210" cy="210" r="90" fill="${p.a1}"/></g></g>`;
    } },
  { id: 32, fam: "color", he: "מעבר עם גרעין", en: "Grain gradient", fits: "עכשווי־חמים, שער, רקע",
    draw(p, u) {
      return `<defs><linearGradient id="${u}g" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="${p.a3}"/><stop offset=".45" stop-color="${p.a1}"/><stop offset=".8" stop-color="${p.soft}"/><stop offset="1" stop-color="${p.light}"/></linearGradient>
        <radialGradient id="${u}h" cx=".75" cy=".25" r=".6"><stop offset="0" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/><rect width="400" height="400" fill="url(#${u}h)"/>${grain(u, 0.55, 0.95)}`;
    } },
  { id: 33, fam: "color", he: "דואוטון", en: "Duotone", fits: "חזק, מותגי, כרזה",
    draw(p, u) {
      const [a, b] = [rgbOf(mix(p.ink, "#000", 0.15)), rgbOf(p.a2)].map((c) => c.map((v) => (v / 255).toFixed(3)));
      return `<defs><filter id="${u}d" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".005 .011" numOctaves="5" seed="9"/>
        <feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncR type="linear" slope="2.2" intercept="-.6"/><feFuncG type="linear" slope="2.2" intercept="-.6"/><feFuncB type="linear" slope="2.2" intercept="-.6"/><feFuncA type="linear" slope="0" intercept="1"/></feComponentTransfer>
        <feComponentTransfer><feFuncR type="table" tableValues="${a[0]} ${b[0]}"/><feFuncG type="table" tableValues="${a[1]} ${b[1]}"/><feFuncB type="table" tableValues="${a[2]} ${b[2]}"/></feComponentTransfer></filter></defs>
        <rect width="400" height="400" filter="url(#${u}d)"/><circle cx="280" cy="130" r="60" fill="${p.a2}"/><path d="M0 300 C100 260 160 330 260 290 C320 265 360 280 400 270 V400 H0Z" fill="${mix(p.ink, "#000", 0.15)}"/>`;
    } },
  { id: 34, fam: "color", he: "זכוכית חלבית", en: "Glassmorphism", fits: "מסך, ממשק, כרטיס דיגיטלי",
    draw(p, u) {
      const blobs = `<circle cx="125" cy="140" r="95" fill="${p.a1}"/><circle cx="295" cy="280" r="80" fill="${p.a2}"/><circle cx="305" cy="105" r="55" fill="${p.soft}"/>`;
      return `<defs><filter id="${u}b" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="16"/></filter><filter id="${u}s" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="12"/></filter>
        <clipPath id="${u}c"><rect x="70" y="125" width="260" height="165" rx="22"/></clipPath><linearGradient id="${u}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${p.bg}"/><stop offset="1" stop-color="${p.light}"/></linearGradient></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/>${blobs}
        <rect x="76" y="140" width="260" height="165" rx="22" fill="${p.ink}" opacity=".18" filter="url(#${u}s)"/>
        <g clip-path="url(#${u}c)"><g filter="url(#${u}b)">${blobs}</g><rect x="70" y="125" width="260" height="165" fill="#fff" opacity=".3"/></g>
        <rect x="70.5" y="125.5" width="259" height="164" rx="21.5" fill="none" stroke="#fff" stroke-opacity=".75" stroke-width="1.5"/>
        <rect x="200" y="160" width="100" height="10" rx="5" fill="#fff" opacity=".9"/><rect x="230" y="182" width="70" height="7" rx="3.5" fill="#fff" opacity=".7"/><circle cx="118" cy="245" r="20" fill="#fff" opacity=".8"/>`;
    } },
  { id: 35, fam: "color", he: "צל ארוך", en: "Long shadow", fits: "אייקון, שטוח, כרזה",
    draw(p, u, o) {
      const cx = 185, cy = 185, r = 85, k = Math.SQRT1_2;
      const P1 = [cx + r * k, cy - r * k], P2 = [cx - r * k, cy + r * k];
      return `<defs><linearGradient id="${u}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${p.ink}" stop-opacity=".45"/><stop offset=".7" stop-color="${p.ink}" stop-opacity="0"/></linearGradient></defs>
        ${bgRect(p.a1)}<polygon points="${pts([P1, [P1[0] + 400, P1[1] + 400], [P2[0] + 400, P2[1] + 400], P2])}" fill="url(#${u}g)"/>
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="${p.light}"/>${T(o, 100, 700, p.a1, cx, cy + 36, o.initial)}`;
    } },
  { id: 36, fam: "color", he: "חימר רך", en: "Claymorphism / soft 3D", fits: "ידידותי, ילדים, אייקונים",
    draw(p, u) {
      const g = (id, c) => `<radialGradient id="${u}${id}" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="${mix(c, "#fff", 0.55)}"/><stop offset=".45" stop-color="${c}"/><stop offset="1" stop-color="${mix(c, "#000", 0.22)}"/></radialGradient>`;
      return `<defs>${g("a", p.a1)}${g("b", p.a2)}${g("c", p.soft)}<filter id="${u}s" x="-40%" y="-40%" width="180%" height="190%"><feDropShadow dx="6" dy="14" stdDeviation="12" flood-color="${p.ink}" flood-opacity=".28"/></filter></defs>
        ${bgRect(mix(p.light, p.bg, 0.5))}
        <rect x="70" y="190" width="170" height="130" rx="48" fill="url(#${u}a)" filter="url(#${u}s)"/>
        <circle cx="285" cy="145" r="62" fill="url(#${u}b)" filter="url(#${u}s)"/>
        <rect x="200" y="290" width="150" height="56" rx="28" fill="url(#${u}c)" filter="url(#${u}s)"/>`;
    } },
  // ---------------- heritage ----------------
  { id: 37, fam: "heritage", he: "מיקרוגרפיה", en: "Micrography", fits: "מסורת, ספר, מתנה",
    draw(p, u, o) {
      const P = [];
      for (let th = 0; th < Math.PI * 2 * 13; th += 0.05) { const r = 8 + (th / (Math.PI * 2)) * 10; P.push([200 + r * Math.cos(th), 220 + r * Math.sin(th)]); }
      const txt = "בשמחה ובאהבה ברוכים הבאים ".repeat(70);
      const crown = "M168 92 L176 58 L188 84 L200 50 L212 84 L224 58 L232 92";
      return `<defs><path id="${u}sp" d="${pathOf(P)}"/><path id="${u}cr" d="${crown}"/></defs>${bgRect(p.bg)}
        <text font-family="${o.serif}, serif" font-size="7.4" fill="${p.ink}"><textPath href="#${u}sp">${txt}</textPath></text>
        <text font-family="${o.serif}, serif" font-size="7" fill="${p.a1}"><textPath href="#${u}cr">${"שמחה ".repeat(12)}</textPath></text>
        <path d="${crown}" fill="none" stroke="${p.a1}" stroke-width="1" transform="translate(0 6)"/>`;
    } },
  { id: 38, fam: "heritage", he: "נייר גזור יהודי", en: "Jewish papercut", fits: "שמחות, כתובה, מזרח",
    draw(p, u) {
      let half = "";
      for (let i = 0; i < 8; i++) half += `<circle cx="${60 + 3}" cy="${110 + i * 30}" r="7"/><path d="M${92} ${102 + i * 30} q8 8 0 16 q-8 -8 0 -16z"/>`;
      for (let x = 30; x < 200; x += 20) half += `<circle cx="${x}" cy="30" r="5"/><circle cx="${x}" cy="370" r="5"/>`;
      for (let y = 50; y < 360; y += 20) half += `<circle cx="30" cy="${y}" r="5"/>`;
      half += `<path d="M126 330 V190 A74 74 0 0 1 200 116 V330Z"/>`;
      half += `<path d="M110 82 l10 -22 l10 22z M150 70 l10 -22 l10 22z"/>`;
      half += `<path d="M60 345 q15 -18 30 0z M100 345 q15 -18 30 0z M140 345 q15 -18 30 0z"/>`;
      // A rosette of petals left standing inside the cut arch (no national or religious emblems).
      let rosette = "";
      for (let k = 0; k < 8; k++) rosette += `<ellipse cx="200" cy="200" rx="9" ry="30" transform="rotate(${k * 45} 200 230) translate(0 0)"/>`;
      return `<defs><mask id="${u}m"><rect width="400" height="400" fill="#fff"/><g fill="#000">${half}<g transform="translate(400 0) scale(-1 1)">${half}</g></g>
        <g fill="#fff">${rosette}<circle cx="200" cy="300" r="10"/><rect x="196" y="150" width="8" height="34"/><path d="M160 330 Q200 300 240 330Z"/></g><g fill="#000"><circle cx="200" cy="230" r="9"/></g></mask>
        <filter id="${u}s" x="-5%" y="-5%" width="110%" height="110%"><feDropShadow dx="2" dy="3" stdDeviation="2" flood-color="#000" flood-opacity=".45"/></filter></defs>
        ${bgRect(p.a1)}<rect width="400" height="400" fill="${mix(p.bg, "#FFF8E8", 0.4)}" mask="url(#${u}m)" filter="url(#${u}s)"/>`;
    } },
  { id: 39, fam: "heritage", he: "מסגרת עיטור", en: "Ornamental frame", fits: "תעודה, הזמנה, כתובה",
    draw(p, u, o) {
      const corner = `<g fill="none" stroke="${p.a1}" stroke-width="1.6"><path d="M0 0 C30 4 44 18 48 48"/><path d="M0 0 C4 30 18 44 48 48"/><circle cx="48" cy="48" r="5" fill="${p.a1}"/>
        ${leaf(14, 14, 45, 26, `fill="${p.soft}" stroke="${p.a1}"`)}<path d="M10 70 C20 60 20 40 10 30 M70 10 C60 20 40 20 30 10"/></g>`;
      const at = (x, y, a) => `<g transform="translate(${x} ${y}) rotate(${a})">${corner}</g>`;
      return `${bgRect(mix(p.bg, "#F3E9D2", 0.35))}<rect x="22" y="22" width="356" height="356" fill="none" stroke="${p.a1}" stroke-width="2.5"/><rect x="32" y="32" width="336" height="336" fill="none" stroke="${p.ink}" stroke-width=".8"/>
        ${at(40, 40, 0)}${at(360, 40, 90)}${at(360, 360, 180)}${at(40, 360, 270)}
        <path d="M170 32 Q200 0 230 32" fill="none" stroke="${p.a1}" stroke-width="1.6"/><circle cx="200" cy="18" r="4" fill="${p.a1}"/>
        <text x="200" y="210" font-family="${o.serif}, serif" font-weight="700" font-size="46" fill="${p.ink}" text-anchor="middle">מזל טוב</text>
        <path d="M130 235 C160 222 180 248 200 235 C220 222 240 248 270 235" fill="none" stroke="${p.a1}" stroke-width="1.8"/>`;
    } },
  { id: 40, fam: "heritage", he: "שזירה", en: "Interlace", fits: "סמל, מונוגרמה, מסורתי",
    draw(p, u) {
      // Two interlaced rings: A passes over B at the top crossing, under it at the bottom.
      const r = 82, ax = 162, bx = 238, cy = 205, dy = Math.sqrt(r * r - ((bx - ax) / 2) ** 2);
      const ring = (x, c) => `<circle cx="${x}" cy="${cy}" r="${r}" fill="none" stroke="${p.ink}" stroke-width="24"/><circle cx="${x}" cy="${cy}" r="${r}" fill="none" stroke="${c}" stroke-width="16"/>`;
      const A = ring(ax, p.a1), B = ring(bx, p.a2);
      return `<defs><clipPath id="${u}c"><circle cx="200" cy="${f1(cy - dy)}" r="20"/></clipPath></defs>${bgRect(p.bg)}<circle cx="200" cy="${cy}" r="165" fill="${p.light}"/>
        ${A}${B}<g clip-path="url(#${u}c)">${A}</g>`;
    } },
  { id: 41, fam: "heritage", he: "אותיות כמרקם", en: "Typographic texture", fits: "מותג, אריזה, רקע",
    draw(p, u, o) {
      const abc = "אבגדהוזחטיכלמנסעפצקרשת";
      let s = "";
      for (let row = 0; row < 13; row++) {
        const line = (abc + abc).slice(row % 22, (row % 22) + 16);
        s += `<text x="${row % 2 ? 412 : 400}" y="${28 + row * 31}" font-family="${o.head}, Heebo, sans-serif" font-weight="${row % 3 ? 300 : 700}" font-size="30" fill="${mix(p.ink, p.light, row % 2 ? 0.28 : 0.42)}" text-anchor="end" letter-spacing="4">${line}</text>`;
      }
      return `${bgRect(p.ink)}${s}${T(o, 230, 900, p.a2, 200, 285, o.initial)}`;
    } },
  { id: 42, fam: "heritage", he: "אות ענקית", en: "Type as image", fits: "כרזה, שער, מיתוג",
    draw(p, u, o) {
      return `<defs><clipPath id="${u}c"><rect width="400" height="400"/></clipPath></defs><g clip-path="url(#${u}c)">${bgRect(p.light)}
        <text x="430" y="420" font-family="${o.head}, Heebo, sans-serif" font-weight="900" font-size="560" fill="${p.a1}" text-anchor="end">${o.initial}</text>
        <circle cx="95" cy="95" r="34" fill="${p.a2}"/>
        <text x="40" y="350" font-family="${o.head}, Heebo, sans-serif" font-weight="700" font-size="26" fill="${p.ink}" text-anchor="start">סטודיו</text>
        <rect x="40" y="362" width="80" height="4" fill="${p.ink}"/></g>`;
    } },
  // ---------------- scene ----------------
  { id: 43, fam: "scene", he: "מוקאפ על משטח", en: "Flat lay mockup", fits: "הצגת עבודה, תיק עבודות",
    draw(p, u) {
      const r = rng(43);
      let sprig = "";
      for (let i = 0; i < 9; i++) sprig += leaf(300 + i * 9, 320 - i * 14 + (i % 2) * 6, (i % 2 ? -50 : 40) - i * 4, 20 + r() * 8, `fill="${mix(p.a1, "#8FA89F", 0.6)}"`);
      return `<defs><filter id="${u}lin" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9 .02" numOctaves="2" seed="4" result="h"/><feTurbulence type="fractalNoise" baseFrequency=".02 .9" numOctaves="2" seed="9" result="v"/><feBlend in="h" in2="v" mode="multiply"/>
        <feColorMatrix type="matrix" values="0 0 0 0 .5  0 0 0 0 .55  0 0 0 0 .6  0 0 0 -1.1 .9"/></filter>
        <filter id="${u}sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="4" dy="10" stdDeviation="9" flood-color="#1b2a38" flood-opacity=".3"/></filter>
        <filter id="${u}bl" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="12"/></filter></defs>
        ${bgRect(mix(p.bg, p.light, 0.4))}<rect width="400" height="400" filter="url(#${u}lin)" opacity=".5" style="mix-blend-mode:multiply"/>
        <g filter="url(#${u}bl)" opacity=".16" fill="#1b2a38">${leaf(-20, 60, -20, 160)}${leaf(20, 140, 10, 140)}</g>
        <rect x="70" y="110" width="200" height="140" rx="3" fill="${p.a1}" transform="rotate(8 170 180)" filter="url(#${u}sh)"/>
        <g transform="rotate(-6 210 200)" filter="url(#${u}sh)"><rect x="130" y="80" width="170" height="240" fill="#FCFDFD"/>
        <rect x="185" y="125" width="60" height="5" fill="${p.a1}"/><rect x="160" y="150" width="110" height="14" fill="${p.ink}"/><rect x="175" y="175" width="80" height="4" fill="${mix(p.ink, "#fff", 0.5)}"/>
        <path d="M130 290 C170 270 210 300 300 280 V320 H130Z" fill="${p.soft}"/></g>${sprig}`;
    } },
  { id: 44, fam: "scene", he: "צללי חלון", en: "Gobo shadows", fits: "צילום מוצר, אווירה, רקע",
    draw(p, u) {
      return `<defs><linearGradient id="${u}w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(p.bg, "#FFF1DE", 0.3)}"/><stop offset="1" stop-color="${mix(p.bg, p.light, 0.5)}"/></linearGradient>
        <linearGradient id="${u}v" x1="0" x2="1"><stop offset="0" stop-color="${mix(p.a1, "#000", 0.25)}"/><stop offset=".4" stop-color="${p.a1}"/><stop offset=".7" stop-color="${mix(p.a1, "#fff", 0.3)}"/><stop offset="1" stop-color="${mix(p.a1, "#000", 0.3)}"/></linearGradient>
        <filter id="${u}b" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="7"/></filter><filter id="${u}b2" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4"/></filter></defs>
        <rect width="400" height="300" fill="url(#${u}w)"/><rect y="300" width="400" height="100" fill="${mix(p.bg, p.ink, 0.1)}"/>
        <g opacity=".22" fill="#2a2a2a" filter="url(#${u}b)"><path d="M150 -10 L190 -10 L120 300 L80 300Z"/><path d="M-10 110 L400 70 L400 100 L-10 140Z"/>${leaf(230, 40, 40, 90)}${leaf(260, 30, 80, 70)}${leaf(300, 70, 20, 80)}${leaf(250, 110, 60, 60)}</g>
        <path d="M150 420 L240 300 L400 300 L400 420Z" fill="#fff" opacity=".18" filter="url(#${u}b)"/>
        <ellipse cx="205" cy="318" rx="62" ry="10" fill="#000" opacity=".22" filter="url(#${u}b2)"/>
        <path d="M170 318 C150 270 155 220 190 195 L190 170 L220 170 L220 195 C255 220 260 270 240 318Z" fill="url(#${u}v)"/>
        <path d="M240 318 C300 300 330 290 360 230" stroke="#000" stroke-opacity=".08" stroke-width="40" fill="none" filter="url(#${u}b)"/>`;
    } },
  { id: 45, fam: "scene", he: "נוף מינימלי", en: "Minimal landscape", fits: "רקע, שער, רוגע",
    draw(p, u) {
      const hill = (y, a, f, ph, c) => { const P = [[0, 400]]; for (let x = 0; x <= 400; x += 8) P.push([x, y + a * Math.sin(x * f + ph) + a * 0.4 * Math.sin(x * f * 2.3 + ph)]); P.push([400, 400]); return `<polygon points="${pts(P)}" fill="${c}"/>`; };
      return `<defs><linearGradient id="${u}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.light}"/><stop offset="1" stop-color="${mix(p.bg, "#FFF6E6", 0.4)}"/></linearGradient>
        <linearGradient id="${u}hz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>
        <rect width="400" height="400" fill="url(#${u}s)"/><circle cx="270" cy="150" r="46" fill="${p.a2}" opacity=".9"/>
        ${hill(215, 22, 0.012, 1, p.soft)}<rect y="200" width="400" height="60" fill="url(#${u}hz)"/>${hill(258, 26, 0.015, 3, mix(p.soft, p.a1, 0.5))}${hill(300, 24, 0.011, 5, p.a1)}${hill(345, 20, 0.018, 2, p.ink)}`;
    } },
  { id: 46, fam: "scene", he: "ים ושמיים", en: "Sea & sky", fits: "רוגע, מרחב, רקע לכותרת",
    draw(p, u) {
      return `<defs><linearGradient id="${u}sk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.soft}"/><stop offset=".8" stop-color="${mix(p.light, "#fff", 0.6)}"/><stop offset="1" stop-color="#FFFBF0"/></linearGradient>
        <linearGradient id="${u}se" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(p.a1, "#fff", 0.35)}"/><stop offset=".35" stop-color="${p.a1}"/><stop offset="1" stop-color="${mix(p.a1, p.ink, 0.7)}"/></linearGradient>
        <radialGradient id="${u}sun"><stop offset="0" stop-color="#FFFDF5"/><stop offset="1" stop-color="#FFFDF5" stop-opacity="0"/></radialGradient>
        <linearGradient id="${u}fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".1"/><stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>
        <mask id="${u}mk"><rect y="235" width="400" height="165" fill="url(#${u}fade)"/></mask>
        <filter id="${u}wa" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".010 .10" numOctaves="4" seed="5" result="n"/>
        <feSpecularLighting in="n" surfaceScale="5" specularConstant="1" specularExponent="22" lighting-color="#FFFBEF"><feDistantLight azimuth="90" elevation="35"/></feSpecularLighting><feComposite in2="SourceGraphic" operator="in"/></filter></defs>
        <rect width="400" height="240" fill="url(#${u}sk)"/><ellipse cx="270" cy="232" rx="150" ry="70" fill="url(#${u}sun)"/>
        <rect y="235" width="400" height="165" fill="url(#${u}se)"/><g mask="url(#${u}mk)"><rect y="235" width="400" height="165" fill="#fff" filter="url(#${u}wa)" opacity=".7"/></g>
        <rect y="228" width="400" height="12" fill="#fff" opacity=".35"/>`;
    } },
  { id: 47, fam: "scene", he: "שמי לילה", en: "Night sky", fits: "לילה, חג, קסם",
    draw(p, u) {
      const r = rng(47);
      let st = "";
      for (let i = 0; i < 170; i++) st += `<circle cx="${f1(r() * 400)}" cy="${f1(r() * 320)}" r="${f1(0.3 + r() ** 3 * 2)}" fill="#fff" opacity="${(0.35 + r() * 0.65).toFixed(2)}"/>`;
      return `<defs><linearGradient id="${u}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(p.ink, "#000", 0.5)}"/><stop offset="1" stop-color="${mix(p.ink, p.a1, 0.4)}"/></linearGradient>
        <mask id="${u}moon"><circle cx="300" cy="95" r="40" fill="#fff"/><circle cx="318" cy="84" r="36" fill="#000"/></mask>
        <filter id="${u}gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8"/></filter></defs>
        <rect width="400" height="400" fill="url(#${u}g)"/>${st}
        <circle cx="300" cy="95" r="40" fill="${p.light}" mask="url(#${u}moon)" filter="url(#${u}gl)" opacity=".8"/><circle cx="300" cy="95" r="40" fill="${mix(p.light, "#fff", 0.6)}" mask="url(#${u}moon)"/>
        <path d="M0 330 C90 300 140 335 220 315 C290 297 340 320 400 305 V400 H0Z" fill="${mix(p.ink, "#000", 0.65)}"/>`;
    } },
  { id: 48, fam: "scene", he: "במה תלת־ממדית", en: "3D stage / podium", fits: "מוצר, מוקאפ, השקה",
    draw(p, u) {
      const cyl = (cx, top, rx, ry, h, c) => `<path d="M${cx - rx} ${top} V${top + h} A${rx} ${ry} 0 0 0 ${cx + rx} ${top + h} V${top}Z" fill="url(#${u}${c})"/><ellipse cx="${cx}" cy="${top}" rx="${rx}" ry="${ry}" fill="${mix(c === "c1" ? p.light : p.soft, "#fff", 0.35)}"/>`;
      const side = (id, c) => `<linearGradient id="${u}${id}" x1="0" x2="1"><stop offset="0" stop-color="${mix(c, "#000", 0.25)}"/><stop offset=".45" stop-color="${mix(c, "#fff", 0.2)}"/><stop offset="1" stop-color="${mix(c, "#000", 0.3)}"/></linearGradient>`;
      return `<defs>${side("c1", p.a1)}${side("c2", p.a2)}<radialGradient id="${u}ball" cx=".35" cy=".3"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="${p.a2}"/><stop offset="1" stop-color="${mix(p.a2, "#000", 0.35)}"/></radialGradient>
        <radialGradient id="${u}spot" cx=".5" cy="0" r=".9"><stop offset="0" stop-color="#fff" stop-opacity=".5"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
        <filter id="${u}b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8"/></filter></defs>
        ${bgRect(mix(p.soft, p.bg, 0.4))}<path d="M110 300 V140 A90 90 0 0 1 290 140 V300Z" fill="${p.light}"/><rect y="290" width="400" height="110" fill="${mix(p.soft, p.bg, 0.15)}"/>
        <ellipse cx="200" cy="352" rx="150" ry="22" fill="#000" opacity=".18" filter="url(#${u}b)"/>${cyl(200, 285, 135, 26, 55, "c1")}${cyl(230, 250, 70, 14, 36, "c2")}
        <circle cx="228" cy="214" r="34" fill="url(#${u}ball)"/><rect width="400" height="400" fill="url(#${u}spot)"/>`;
    } },
];
