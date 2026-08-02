/**
 * The sky's palette, measured rather than described.
 *
 * "Amber means understanding and nothing unlit may outshine it" is the app's
 * most important visual claim, and until now it was enforced by a comment.
 * check_graph_data.mjs proves the *selection* (understood always takes amber)
 * using symbolic swatches, which is the right test for that file and says
 * nothing at all about whether the amber swatch is actually the brightest --
 * a token edit could invert the whole meaning with every gate still green.
 *
 * This reads tokens.css and does the arithmetic. It is the same lesson as the
 * shell space budget: three of the last eight bugfixes were stylesheet bugs no
 * JS seam could reach, so the stylesheet gets assertions of its own.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const raw = readFileSync(
  fileURLToPath(new URL("../src/tokens.css", import.meta.url)),
  "utf8",
);
// Comments out before anything is matched. This file explains each value at
// length, and the prose names both `@import` and the rejected color-mix()
// syntax -- so a checker reading the raw text flags the documentation of a
// rule as a violation of it.
const source = raw.replace(/\/\*[\s\S]*?\*\//g, "");

// --- the fork itself -------------------------------------------------------

assert.ok(
  !/@import/.test(source),
  "tokens.css must not import the docs-site tokens: a website edit would " +
    "restyle the shipped app with no signal and no rebuild",
);

// --- parsing ---------------------------------------------------------------

function token(name) {
  const match = source.match(new RegExp(`--${name}:\\s*([^;]+);`));
  assert.ok(match, `token --${name} is missing from tokens.css`);
  return match[1].trim();
}

function rgb(name) {
  const raw = token(name);
  const match = raw.match(/^rgb\((\d+)\s+(\d+)\s+(\d+)\)$/);
  assert.ok(
    match,
    `--${name} must be a plain "rgb(r g b)" value, got "${raw}". readPalette ` +
      "hands a custom property's authored TEXT to WebGL, so a color-mix() " +
      "token renders black -- silently hiding whatever it paints.",
  );
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function hex(name) {
  const raw = token(name);
  const match = raw.match(/^#([0-9a-f]{6})$/i);
  assert.ok(match, `--${name} must be a 6-digit hex value, got "${raw}"`);
  const value = match[1];
  return [0, 2, 4].map((index) => parseInt(value.slice(index, index + 2), 16));
}

const channel = (value) => {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
const luminance = ([r, g, b]) =>
  0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const hue = ([r, g, b]) => {
  const [max, min] = [Math.max(r, g, b), Math.min(r, g, b)];
  if (max === min) return 0;
  const d = max - min;
  const raw =
    max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (raw * 60 + 360) % 360;
};

// --- the ordering that carries the meaning ---------------------------------

const lit = hex("cm-star-high");
const families = Array.from({ length: 8 }, (_, index) => rgb(`cm-com-${index}`));
const ramp = {
  floor: rgb("cm-node-unlit"),
  mid: rgb("cm-node-mid"),
  ceiling: rgb("cm-node-bright"),
};
const sky = rgb("cm-sky");
const ground = hex("cm-ground");
const ground2 = hex("cm-ground-2");

assert.ok(
  luminance(ramp.floor) < luminance(ramp.mid) &&
    luminance(ramp.mid) < luminance(ramp.ceiling),
  "the unlit centrality ramp must ascend: brightness encodes importance",
);

assert.ok(
  luminance(ramp.ceiling) < luminance(lit),
  `a lit star (${luminance(lit).toFixed(3)}) must outshine the brightest ` +
    `un-understood one (${luminance(ramp.ceiling).toFixed(3)})`,
);

for (const [index, family] of families.entries()) {
  assert.ok(
    luminance(family) < luminance(lit),
    `community family ${index} (${luminance(family).toFixed(3)}) must not ` +
      `reach a lit star (${luminance(lit).toFixed(3)}): amber means ` +
      "understanding, and only understanding",
  );
}

// --- no family may shout over another --------------------------------------

const familyLuminance = families.map(luminance);
const spread = Math.max(...familyLuminance) - Math.min(...familyLuminance);
assert.ok(
  spread < 0.02,
  `community families span ${spread.toFixed(3)} in luminance; hue says WHICH ` +
    "part of the project a module belongs to, so a brighter family would " +
    "read as a more important one",
);

// --- the amber band stays reserved -----------------------------------------

for (const [index, family] of families.entries()) {
  const h = hue(family);
  assert.ok(
    h < 20 || h > 60,
    `community family ${index} sits at hue ${h.toFixed(0)}deg, inside the ` +
      "kohaku amber band -- it would read as 'understood'",
  );
}
for (const name of ["cm-star-cool", "cm-star-pale"]) {
  const h = hue(rgb(name));
  assert.ok(
    h < 20 || h > 60,
    `--${name} sits at hue ${h.toFixed(0)}deg: star temperature is decoration ` +
      "and may never stray into the band that means understanding",
  );
}

// --- legibility where these appear as UI swatches --------------------------

for (const name of [
  "cm-com-0", "cm-com-1", "cm-com-2", "cm-com-3",
  "cm-com-4", "cm-com-5", "cm-com-6", "cm-com-7",
  "cm-neb-python", "cm-neb-js", "cm-neb-ts",
  "cm-neb-go", "cm-neb-java", "cm-neb-rust", "cm-neb-csharp",
  "cm-route-possible",
]) {
  const value = rgb(name);
  for (const [surface, label] of [[ground, "--cm-ground"], [ground2, "--cm-ground-2"]]) {
    const ratio = contrast(value, surface);
    assert.ok(
      ratio >= 4.5,
      `--${name} measures ${ratio.toFixed(1)}:1 on ${label}; the legend floor is 4.5:1`,
    );
  }
}

// --- uncertainty stays louder than certainty -------------------------------

assert.ok(
  luminance(rgb("cm-route-possible")) > luminance(rgb("cm-route")),
  "an unproven route must be the MORE visible of the two: the Correctness " +
    "Contract requires a possible call to announce itself",
);

// --- bloom is the mechanism, so it is measured too --------------------------

const effects = readFileSync(
  fileURLToPath(new URL("../src/galaxyEffects.js", import.meta.url)),
  "utf8",
);
const threshold = Number(effects.match(/BLOOM_THRESHOLD\s*=\s*([\d.]+)/)?.[1]);
assert.ok(Number.isFinite(threshold), "BLOOM_THRESHOLD must be readable");
assert.ok(
  threshold > luminance(ramp.ceiling) && threshold > Math.max(...familyLuminance),
  `bloom threshold ${threshold} is at or below something unlit: an ` +
    "un-understood star would glow like an understood one",
);
assert.ok(
  threshold < luminance(lit),
  `bloom threshold ${threshold} is above a lit star (${luminance(lit).toFixed(3)}), ` +
    "so the one moment the app is built around would not glow at all",
);

// --- nothing in the sky is invisible ---------------------------------------

const dimmestStar = contrast(ramp.floor, sky);
assert.ok(
  dimmestStar >= 3,
  `the dimmest unlit star measures ${dimmestStar.toFixed(1)}:1 against the ` +
    "sky; every module must be visible without being understood first, which " +
    "is the whole point of an explorable galaxy",
);
assert.ok(
  luminance(sky) < luminance(ramp.floor),
  "the sky must stay darker than the faintest star drawn on it",
);

console.log(
  `sky palette contracts passed ` +
    `(lit ${luminance(lit).toFixed(3)} > family ${familyLuminance[0].toFixed(3)} > ` +
    `ramp ${luminance(ramp.ceiling).toFixed(3)}/${luminance(ramp.floor).toFixed(3)} > ` +
    `sky ${luminance(sky).toFixed(4)})`,
);

// --- one tint per language Codemble reads ---------------------------------
// A language with no tint draws no fog and shows an empty legend swatch: a
// channel silently missing rather than honestly absent. This table has to grow
// with the adapter registry, so the gate says so when it has not.
{
  const tints = ["python", "js", "ts", "go", "java", "rust", "csharp"];
  const luminances = tints.map((name) => luminance(rgb(`cm-neb-${name}`)));
  const spread = Math.max(...luminances) - Math.min(...luminances);
  assert.ok(
    spread < 0.02,
    `nebula tints span ${spread.toFixed(3)} in luminance; one language must ` +
      "not read as more important than another",
  );
  for (const name of tints) {
    const h = hue(rgb(`cm-neb-${name}`));
    assert.ok(
      h < 20 || h > 60,
      `--cm-neb-${name} sits at hue ${h.toFixed(0)}deg, inside the kohaku band`,
    );
  }
}
