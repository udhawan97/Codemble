#!/usr/bin/env node
/**
 * Generates the Edo star-atlas plate artwork into public/brand/plates/.
 *
 * The plates are geometric — tapered brush arcs, seeded star fields, lobed
 * kasumi mist — so they are generated rather than hand-drawn: a script gives
 * exact coordinates, a fixed seed, and a diff you can actually read when the
 * art changes. Output is committed; the site never runs this at build time.
 *
 *   node scripts/build-plates.mjs
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "../public/brand/plates");
mkdirSync(OUT, { recursive: true });

/* ---- palette (mirrors tokens.css; plates are art, not themed surfaces) --- */
const NIGHT = "#070b1c";
const KACHI = "#101a3e";
const RURI = "#3f6ac0";
const RURI_HI = "#82abec";
const RURI_DIM = "#2b4d96";
const KOHAKU = "#e89b2e";
const KOHAKU_HI = "#f4c46a";
const GOFUN = "#faf7f0";

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
<rect width="${PW}" height="${PH}" fill="${NIGHT}"/>
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
    .map(([x, y], i) =>
      i === 0
        ? `<circle cx="${n(x)}" cy="${n(y)}" r="7" fill="${KOHAKU_HI}"/><circle cx="${n(x)}" cy="${n(y)}" r="14" fill="none" stroke="${KOHAKU}" stroke-width="1" opacity="0.5"/>`
        : `<circle cx="${n(x)}" cy="${n(y)}" r="${n(3 + (i % 3) * 1.4)}" fill="${RURI_HI}" opacity="0.9"/>`,
    )
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
    body += `<circle cx="${n(cx + Math.cos(a) * rr)}" cy="${n(cy + Math.sin(a) * rr * 0.42)}" r="${n(4 - i * 0.6)}" fill="${RURI_HI}"/>`;
  }
  body += `<circle cx="${cx}" cy="${cy}" r="9" fill="${KOHAKU_HI}"/>`;
  write("plate-system.svg", plate(body));
}

/* Study — a source panel with the read line marked. */
{
  const rand = rng(0xc0de);
  let body = `<rect x="34" y="40" width="${PW - 68}" height="${PH - 80}" fill="${KACHI}" stroke="${RURI_DIM}" stroke-width="1"/>`;
  for (let i = 0; i < 9; i++) {
    const y = 62 + i * 20;
    const w = 60 + rand() * 200;
    const lit = i === 4;
    body += `<text x="48" y="${y + 4}" font-family="monospace" font-size="9" fill="${RURI_DIM}">${String(i + 1).padStart(2, "0")}</text>`;
    body += `<rect x="72" y="${y - 4}" width="${n(w)}" height="4" rx="2" fill="${lit ? KOHAKU : RURI_HI}" opacity="${lit ? 0.95 : 0.34}"/>`;
    if (lit)
      body += `<rect x="34" y="${y - 10}" width="${PW - 68}" height="16" fill="${KOHAKU}" opacity="0.09"/>`;
  }
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

console.log(`\nPlates written to ${OUT}`);
