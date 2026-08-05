#!/usr/bin/env node
/**
 * Generates Codemble's committed brand system: Edo plates, interface icons,
 * README download banner, and SVG/PNG social card.
 *
 * The plates are geometric — tapered brush arcs, seeded star fields, lobed
 * kasumi mist — so they are generated rather than hand-drawn: a script gives
 * exact coordinates, a fixed seed, and a diff you can actually read when the
 * art changes. Output is committed; the site never runs this at build time.
 *
 *   node scripts/build-plates.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const BRAND = join(dirname(fileURLToPath(import.meta.url)), "../public/brand");
const OUT = join(BRAND, "plates");
const ICONS = join(BRAND, "icons");
mkdirSync(OUT, { recursive: true });
mkdirSync(ICONS, { recursive: true });

/* ---- palette (mirrors tokens.css; plates are art, not themed surfaces) --- */
const NIGHT = "#070b1c";
const KACHI = "#101a3e";
const RURI = "#3f6ac0";
const RURI_HI = "#82abec";
const RURI_DIM = "#2b4d96";
const KOHAKU = "#e89b2e";
const KOHAKU_HI = "#f4c46a";
const GOFUN = "#faf7f0";
const APP_SKY = "#131f4b";
const APP_GLOW = "#2a4b91";
const APP_FAMILIES = [
  "#7ebd9e",
  "#b39ac9",
  "#80afc9",
  "#c79383",
  "#a9b77a",
  "#a69cce",
  "#72b6b7",
  "#c28eb0",
];

const tokenSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../src/styles/tokens.css"),
  "utf8",
);
for (const colour of [
  NIGHT,
  KACHI,
  RURI,
  RURI_HI,
  RURI_DIM,
  KOHAKU,
  KOHAKU_HI,
  GOFUN,
  APP_SKY,
  APP_GLOW,
]) {
  if (!tokenSource.includes(colour)) {
    throw new Error(`Generated-brand palette drift: ${colour} is absent from tokens.css.`);
  }
}

/** Deterministic PRNG — same seed, same plate, forever. */
const rng = (seed) => () => {
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const n = (v) => Math.round(v * 100) / 100;

/* ---- shared defs --------------------------------------------------------
   Washi grain and bokashi (the hand-wiped ink fade at the head of a woodblock
   print). Material, not glow: the atlas is paper, so depth comes from tooth
   and wash rather than blur.                                              */
const defs = (id, extra = "") => `
  <defs>
    <filter id="washi-${id}" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="7" result="n"/>
      <feColorMatrix in="n" type="saturate" values="0"/>
    </filter>
    <linearGradient id="bokashi-${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${KACHI}" stop-opacity="0.95"/>
      <stop offset="0.55" stop-color="${NIGHT}" stop-opacity="0.35"/>
      <stop offset="1" stop-color="${NIGHT}" stop-opacity="0"/>
    </linearGradient>${extra}
  </defs>`;

const washiWash = (id, w, h, o = 0.05) =>
  `<rect width="${w}" height="${h}" filter="url(#washi-${id})" opacity="${o}"/>`;

/* ---- the enso ribbon ----------------------------------------------------
   One brush pass: lands, swells through the belly, lifts to nothing. Built as
   a closed outline (offset along the normal) so the taper is a real shape and
   not a stroke that beads at the caps.                                     */
function ensoRibbon({ cx, cy, r, gap = 0.62, weight = 0.075, samples = 220 }) {
  const rand = rng(0x5eed1a);
  const w1 = rand() * Math.PI * 2;
  const w2 = rand() * Math.PI * 2;
  const wob = (a) => 1 + Math.sin(a * 2 + w1) * 0.035 + Math.sin(a * 3 + w2) * 0.022;
  const ang = (t) => gap + t * (Math.PI * 2 - gap * 2);

  const pts = [];
  for (let i = 0; i < samples; i++) {
    const a = ang(i / (samples - 1));
    pts.push([cx + Math.cos(a) * r * wob(a), cy + Math.sin(a) * r * wob(a) * 0.985]);
  }
  const outer = [];
  const inner = [];
  for (let i = 0; i < samples; i++) {
    const [ax, ay] = pts[Math.max(0, i - 1)];
    const [bx, by] = pts[Math.min(samples - 1, i + 1)];
    let tx = bx - ax;
    let ty = by - ay;
    const len = Math.hypot(tx, ty) || 1;
    tx /= len;
    ty /= len;
    const t = i / (samples - 1);
    const taper = Math.pow(Math.sin(Math.pow(t, 0.62) * Math.PI), 0.7);
    const hw = (r * weight * taper) / 2;
    outer.push([pts[i][0] - ty * hw, pts[i][1] + tx * hw]);
    inner.push([pts[i][0] + ty * hw, pts[i][1] - tx * hw]);
  }
  const d =
    `M${n(outer[0][0])} ${n(outer[0][1])}` +
    outer.slice(1).map(([x, y]) => `L${n(x)} ${n(y)}`).join("") +
    inner.reverse().map(([x, y]) => `L${n(x)} ${n(y)}`).join("") +
    "Z";
  return { d, pts };
}

/* ---- kasumi ------------------------------------------------------------
   Heraldic mist: the lobed band that separates scenes in a scroll painting.
   Used here as a section divider — Golavo owns seigaiha waves, so the family
   stays legible without repeating a motif.                                */
function kasumiBand(y, w, lobes, amp, seed) {
  const rand = rng(seed);
  const step = w / lobes;
  const thick = amp * 1.9;
  // Lobed on BOTH edges — a floating ribbon of mist. A flat bottom edge reads
  // as a rectangle the moment the artwork is narrower than its frame.
  let d = `M0 ${n(y)}`;
  for (let i = 0; i < lobes; i++) {
    const x = i * step;
    const h = amp * (0.55 + rand() * 0.75);
    d += `Q${n(x + step * 0.25)} ${n(y - h)} ${n(x + step * 0.5)} ${n(y)}`;
    d += `Q${n(x + step * 0.75)} ${n(y + h * 0.45)} ${n(x + step)} ${n(y)}`;
  }
  d += `L${n(w)} ${n(y + thick)}`;
  for (let i = lobes; i > 0; i--) {
    const x = i * step;
    const h = amp * (0.35 + rand() * 0.55);
    d += `Q${n(x - step * 0.25)} ${n(y + thick + h)} ${n(x - step * 0.5)} ${n(y + thick)}`;
    d += `Q${n(x - step * 0.75)} ${n(y + thick - h * 0.45)} ${n(x - step)} ${n(y + thick)}`;
  }
  return d + "Z";
}

const write = (name, svg) => {
  writeFileSync(join(OUT, name), svg.replace(/\n\s*\n/g, "\n").trim() + "\n");
  console.log("  ✓", name);
};

const writeBrand = (name, content) => {
  writeFileSync(join(BRAND, name), content.replace(/\n\s*\n/g, "\n").trim() + "\n");
  console.log("  ✓", name);
};

const writeIcon = (name, label, body, stroke = RURI) => {
  writeFileSync(
    join(ICONS, `${name}.svg`),
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="${stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="${label}">
${body}
</svg>\n`,
  );
  console.log("  ✓", `icons/${name}.svg`);
};

/* ===== HERO — a tatebanko (立版古) paper diorama in four sheets ========== */
const HW = 1000;
const HH = 820;
const CX = HW * 0.5;
const CY = HH * 0.47;
const R = 300;

/* Sheet 1 — the deepest field. */
{
  const rand = rng(0xa71a5);
  let stars = "";
  for (let i = 0; i < 300; i++) {
    const x = rand() * HW;
    const y = rand() * HH;
    const r = 0.4 + rand() * 1.1;
    const o = 0.18 + rand() * 0.4;
    stars += `<circle cx="${n(x)}" cy="${n(y)}" r="${n(r)}" fill="${GOFUN}" opacity="${n(o)}"/>`;
  }
  // Transparent ground on purpose: the sheet is oversized and offset, so any
  // filled rect would show its own edge as a hard rectangle across the hero.
  // The bokashi wash lives in CSS on the diorama box, full-bleed.
  write(
    "hero-field.svg",
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${HW} ${HH}" width="${HW}" height="${HH}">
${stars}
</svg>`,
  );
}

/* Sheet 2 — the chart itself: the enso arc and the star systems on it.
   (A kasumi mist sheet sat here during design. It read as haze behind an
   already-busy plate, and mist's real job — separating scenes — is done by the
   rule between sections, so the hero is three sheets and kasumi has one use.) */
{
  const rand = rng(0x5eed1a);
  const { d, pts } = ensoRibbon({ cx: CX, cy: CY, r: R });
  let systems = "";
  let ticks = "";
  const nodes = [];
  for (let i = 0; i < 13; i++) {
    const p = pts[Math.round((i / 12) * (pts.length - 1))];
    nodes.push(p);
    const rr = 3.2 + rand() * 3.4;
    systems += `<circle cx="${n(p[0])}" cy="${n(p[1])}" r="${n(rr)}" fill="${RURI_HI}"/>`;
    // Astronomer's tick: every plate on a real atlas is annotated.
    const a = Math.atan2(p[1] - CY, p[0] - CX);
    const t1 = [p[0] + Math.cos(a) * 14, p[1] + Math.sin(a) * 14];
    const t2 = [p[0] + Math.cos(a) * 22, p[1] + Math.sin(a) * 22];
    ticks += `<line x1="${n(t1[0])}" y1="${n(t1[1])}" x2="${n(t2[0])}" y2="${n(t2[1])}" stroke="${RURI_HI}" stroke-width="1" opacity="0.4"/>`;
    const moons = 2 + Math.floor(rand() * 3);
    for (let m = 0; m < moons; m++) {
      const ma = rand() * Math.PI * 2;
      const md = 13 + rand() * 17;
      systems += `<circle cx="${n(p[0] + Math.cos(ma) * md)}" cy="${n(p[1] + Math.sin(ma) * md)}" r="${n(0.9 + rand() * 1.1)}" fill="${RURI_HI}" opacity="0.65"/>`;
    }
  }
  write(
    "hero-chart.svg",
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${HW} ${HH}" width="${HW}" height="${HH}">
<path d="${d}" fill="${RURI}" opacity="0.92"/>
${ticks}
${systems}
</svg>`,
  );
}

/* Sheet 4 — the gold: the one region already understood. */
{
  const core = [
    [CX - 12, CY + 18, 11],
    [CX - 96, CY - 72, 5.5],
    [CX + 66, CY - 84, 5],
    [CX + 102, CY + 90, 4],
  ];
  const [c0] = core;
  let lines = core
    .slice(1)
    .map(
      (p) =>
        `<line x1="${n(c0[0])}" y1="${n(c0[1])}" x2="${n(p[0])}" y2="${n(p[1])}" stroke="${KOHAKU}" stroke-width="1.5" opacity="0.75"/>`,
    )
    .join("");
  let stars = core
    .map(
      ([x, y, r]) =>
        `<circle cx="${n(x)}" cy="${n(y)}" r="${n(r)}" fill="${KOHAKU_HI}"/>`,
    )
    .join("");
  write(
    "hero-gold.svg",
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${HW} ${HH}" width="${HW}" height="${HH}">
<defs><radialGradient id="lamp"><stop offset="0" stop-color="${KOHAKU}" stop-opacity="0.3"/><stop offset="0.55" stop-color="${KOHAKU}" stop-opacity="0.07"/><stop offset="1" stop-color="${KOHAKU}" stop-opacity="0"/></radialGradient></defs>
<circle cx="${n(c0[0])}" cy="${n(c0[1])}" r="105" fill="url(#lamp)"/>
${lines}
${stars}
</svg>`,
  );
}

/* ===== kasumi rule — the divider between plates ========================== */
write(
  "kasumi-rule.svg",
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 60" width="1200" height="60" preserveAspectRatio="none">
<path d="${kasumiBand(22, 1200, 9, 16, 0x33)}" fill="${RURI_DIM}" opacity="0.22"/>
<path d="${kasumiBand(22, 1200, 9, 16, 0x33)}" fill="none" stroke="${KOHAKU}" stroke-width="1" opacity="0.3"/>
</svg>`,
);

/* ===== the three instrument plates ======================================
   One diagram per zoom level, drawn like a figure in a technical atlas.   */
const PW = 420;
const PH = 300;
const plate = (body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${PW} ${PH}" width="${PW}" height="${PH}">
${defs("p")}
<rect width="${PW}" height="${PH}" fill="${APP_SKY}"/>
<path d="M-30 250 Q160 105 450 76" fill="none" stroke="${APP_GLOW}" stroke-width="80" opacity="0.12"/>
<rect x="8" y="8" width="${PW - 16}" height="${PH - 16}" fill="none" stroke="${RURI_DIM}" stroke-width="1" opacity="0.55"/>
${body}
${washiWash("p", PW, PH, 0.05)}
</svg>`;

/* Galaxy — systems and the routes between them. */
{
  const rand = rng(0xbeef1);
  const pts = [];
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2 + rand() * 0.4;
    const rr = 55 + rand() * 55;
    pts.push([PW / 2 + Math.cos(a) * rr * 1.35, PH / 2 + Math.sin(a) * rr]);
  }
  let edges = "";
  for (let i = 0; i < pts.length; i++) {
    const j = (i + 1) % pts.length;
    edges += `<line x1="${n(pts[i][0])}" y1="${n(pts[i][1])}" x2="${n(pts[j][0])}" y2="${n(pts[j][1])}" stroke="${RURI}" stroke-width="1" opacity="0.45"/>`;
  }
  edges += `<line x1="${n(pts[0][0])}" y1="${n(pts[0][1])}" x2="${n(pts[4][0])}" y2="${n(pts[4][1])}" stroke="${RURI}" stroke-width="1" opacity="0.28"/>`;
  const dots = pts
    .map(([x, y], i) => {
      const color = APP_FAMILIES[i % APP_FAMILIES.length];
      const label = i < 5
        ? `<rect x="${n(x + 7)}" y="${n(y - 10)}" width="${38 + i * 4}" height="10" fill="${NIGHT}" opacity="0.9"/><line x1="${n(x + 11)}" y1="${n(y - 5)}" x2="${n(x + 35 + i * 4)}" y2="${n(y - 5)}" stroke="${GOFUN}" stroke-width="1" opacity="0.72"/>`
        : "";
      return `<circle cx="${n(x)}" cy="${n(y)}" r="${n(4 + (i % 3) * 1.5)}" fill="${color}"/>${label}`;
    })
    .join("");
  write("plate-galaxy.svg", plate(edges + dots));
}

/* System — planets in tidy orbits around one star. */
{
  let body = "";
  const cx = PW / 2;
  const cy = PH / 2;
  for (const [i, rr] of [46, 74, 104].entries()) {
    body += `<ellipse cx="${cx}" cy="${cy}" rx="${rr}" ry="${n(rr * 0.42)}" fill="none" stroke="${RURI}" stroke-width="1" opacity="0.4"/>`;
    const a = 0.7 + i * 1.9;
    body += `<circle cx="${n(cx + Math.cos(a) * rr)}" cy="${n(cy + Math.sin(a) * rr * 0.42)}" r="${n(7 - i * 0.6)}" fill="${APP_FAMILIES[(i + 2) % APP_FAMILIES.length]}"/>`;
  }
  body += `<circle cx="${cx}" cy="${cy}" r="11" fill="${APP_FAMILIES[0]}"/><path d="M204 137 Q210 126 216 137 Q210 146 204 137Z" fill="${RURI_HI}" opacity="0.7"/>`;
  write("plate-system.svg", plate(body));
}

/* Study — current parser-owned Impact, not generated prose. */
{
  let body = `<rect x="28" y="34" width="${PW - 56}" height="${PH - 68}" fill="${KACHI}" stroke="${RURI_DIM}" stroke-width="1"/>`;
  body += `<text x="48" y="64" font-family="monospace" font-size="10" fill="${RURI_HI}" letter-spacing="1">IMPACT · NO MODEL NEEDED</text>`;
  body += `<line x1="48" y1="78" x2="372" y2="78" stroke="${RURI_DIM}"/>`;
  for (let i = 0; i < 5; i++) {
    const y = 104 + i * 28;
    body += `<circle cx="58" cy="${y}" r="3" fill="${APP_FAMILIES[i]}"/><path d="M68 ${y} H${154 + i * 8}" stroke="${RURI_HI}" stroke-width="3" opacity="0.55"/><text x="320" y="${y + 3}" font-family="monospace" font-size="8" fill="${RURI_HI}">${i + 1} STEP${i ? "S" : ""}</text>`;
  }
  body += `<path d="M210 96 V228" stroke="${RURI_DIM}"/><path d="M232 110 H354 M232 138 H330 M232 166 H366 M232 194 H344 M232 222 H318" stroke="${GOFUN}" stroke-width="3" opacity="0.32"/>`;
  write("plate-study.svg", plate(body));
}

/* ===== the seal — a kaō (花押), the brush cipher that signs a document === */
write(
  "seal.svg",
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">
<circle cx="60" cy="60" r="52" fill="none" stroke="${KOHAKU}" stroke-width="2" opacity="0.55"/>
<path d="M34 44 C52 30 74 34 84 46 C92 56 82 66 68 64 C54 62 44 68 46 78 C48 88 66 92 84 84"
      fill="none" stroke="${KOHAKU_HI}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="40" y1="88" x2="82" y2="88" stroke="${KOHAKU_HI}" stroke-width="3" stroke-linecap="round"/>
</svg>`,
);

/* ===== supporting icon family =========================================== */
writeIcon("install", "Install", `<path d="M12 3.5v9.5"/><path d="M8.25 9.5 12 13.25 15.75 9.5"/><path d="M4.5 15.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/>`);
writeIcon("asterism", "Chart", `<path d="M5 17.25 11 8.25l7.5 2.75"/><circle cx="5" cy="17.25" r="1.6"/><circle cx="11" cy="8.25" r="1.6"/><circle cx="18.5" cy="11" r="1.6"/>`);
writeIcon("download", "Download", `<path d="M12 3.5v11"/><path d="m7.5 10.5 4.5 4.5 4.5-4.5"/><path d="M4.5 19.5h15"/>`);
writeIcon("download-on-fill", "Download", `<path d="M12 3.5v11"/><path d="m7.5 10.5 4.5 4.5 4.5-4.5"/><path d="M4.5 19.5h15"/>`, GOFUN);
writeIcon("run", "Run", `<path d="m9 6 9 6-9 6Z"/><circle cx="12" cy="12" r="9"/>`);
writeIcon("package", "Package", `<path d="m4 7 8-4 8 4-8 4Z"/><path d="M4 7v10l8 4 8-4V7"/><path d="M12 11v10"/>`);
writeIcon("code", "Source", `<path d="m8 8-4 4 4 4"/><path d="m16 8 4 4-4 4"/><path d="m14 5-4 14"/>`);
writeIcon("release", "Release notes", `<path d="M7 3.5h7l4 4V20H7Z"/><path d="M14 3.5V8h4"/><path d="M10 12h5M10 15.5h5"/>`);
writeIcon("compass", "Explore", `<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5Z"/>`);
writeIcon("map", "Map", `<path d="m3.5 6 5-2 7 2 5-2v14l-5 2-7-2-5 2Z"/><path d="M8.5 4v14M15.5 6v14"/>`);
writeIcon("impact", "Impact", `<circle cx="5" cy="12" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 12h4M11 12l6-5M11 12l6 5"/>`);
writeIcon("check", "Checks", `<path d="m5 12 4 4 10-10"/><path d="M19 12a7 7 0 1 1-4-6.3"/>`);
writeIcon("shield", "Local and verified", `<path d="M12 3 19 6v5c0 4.5-2.8 8-7 10-4.2-2-7-5.5-7-10V6Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>`);
writeIcon("languages", "Languages", `<circle cx="12" cy="12" r="9"/><path d="M3.5 12h17M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>`);

/* ===== README download banner =========================================== */
writeBrand(
  "download-codemble.svg",
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 92" width="760" height="92" role="img" aria-label="Download Codemble — wheel, source archive, and SHA256 digests">
  <rect width="760" height="92" rx="6" fill="${NIGHT}"/>
  <rect x="1" y="1" width="758" height="90" rx="5" fill="none" stroke="${RURI_DIM}"/>
  <circle cx="48" cy="46" r="21" fill="none" stroke="${RURI_HI}" stroke-width="2"/>
  <path d="M48 31v23m-8-8 8 8 8-8M37 63h22" fill="none" stroke="${RURI_HI}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="86" y="39" fill="${GOFUN}" font-family="system-ui,sans-serif" font-size="21" font-weight="700">Download Codemble</text>
  <text x="86" y="64" fill="${RURI_HI}" font-family="ui-monospace,monospace" font-size="13">wheel · source archive · SHA256 digests · release notes</text>
  <path d="M680 46h36m-10-10 10 10-10 10" fill="none" stroke="${RURI_HI}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`,
);

/* ===== social card ======================================================= */
const socialRand = rng(0xc0de2026);
let socialStars = "";
for (let i = 0; i < 90; i++) {
  const x = 540 + socialRand() * 610;
  const y = 70 + socialRand() * 480;
  const color = APP_FAMILIES[i % APP_FAMILIES.length];
  const radius = 2 + socialRand() * 6;
  socialStars += `<circle cx="${n(x)}" cy="${n(y)}" r="${n(radius)}" fill="${color}" opacity="${n(0.55 + socialRand() * 0.4)}"/>`;
}
const socialSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <rect width="1200" height="630" fill="${NIGHT}"/>
  <path d="M420 610 Q760 40 1250 120" fill="none" stroke="${APP_GLOW}" stroke-width="190" opacity="0.22"/>
  ${socialStars}
  <rect x="58" y="54" width="1084" height="522" fill="none" stroke="${RURI_DIM}"/>
  <circle cx="110" cy="112" r="24" fill="none" stroke="${RURI_HI}" stroke-width="3" stroke-dasharray="135 20"/>
  <circle cx="118" cy="104" r="5" fill="${KOHAKU_HI}"/>
  <text x="154" y="121" fill="${GOFUN}" font-family="serif" font-size="34" font-weight="700">Codemble</text>
  <text x="90" y="282" fill="${GOFUN}" font-family="serif" font-size="62" font-weight="700">Explore the code</text>
  <text x="90" y="354" fill="${GOFUN}" font-family="serif" font-size="62" font-weight="700">AI left behind.</text>
  <text x="94" y="430" fill="${RURI_HI}" font-family="ui-monospace,monospace" font-size="22">local · parser-proven · seven languages</text>
  <text x="94" y="516" fill="${GOFUN}" font-family="system-ui,sans-serif" font-size="23">Your code, mapped. Understanding stays earned.</text>
</svg>`;
writeBrand("social-card.svg", socialSvg);
await sharp(Buffer.from(socialSvg)).png().toFile(join(BRAND, "social-card.png"));
console.log("  ✓", "social-card.png");

console.log(`\nBrand plates, icons, banner, and social card written to ${BRAND}`);
