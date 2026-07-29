import assert from "node:assert/strict";

import { framingDistance } from "../src/cameraFraming.js";
import {
  cameraBoundsFor,
  frameLevel,
  frameStudy,
  viewportAspect,
} from "../src/galaxyView.js";
import { LEVELS, drawnRadius } from "../src/graphData.js";

// `framingDistance` is the most thoroughly tested function in this frontend and
// has never been the bug. All three shipped framing faults were about *what it
// was handed*: the whole sky instead of the charted one, a system's planets
// without the rings they sit on, and an aspect the library had not applied yet.
// Those decisions used to live inside GalaxyCanvas.jsx where nothing could
// reach them. This file is the test surface they were missing.

const node = (x, y, z, extra = {}) => ({ fx: x, fy: y, fz: z, ...extra });

// ── viewportAspect: one source for a number that used to have two ──────────

assert.equal(viewportAspect({ width: 1280, height: 720 }), 1280 / 720);
assert.equal(viewportAspect({ width: 1280, height: 0 }), null, "a zero height is not an aspect");
assert.equal(viewportAspect({ width: 0, height: 720 }), null, "nor is a zero width");
assert.equal(viewportAspect({ width: 1280 }), null, "a missing height is not inferred");
assert.equal(viewportAspect(null), null);
assert.equal(
  viewportAspect({ width: Number.NaN, height: 720 }),
  null,
  "an unmeasured element yields no aspect rather than NaN",
);

// ── The charted-sky fit (5bdb110, first fault) ─────────────────────────────

// A tight charted core inside a wide uncharted rim: exactly the shape that
// made fitting everything leave the readable part a thumbnail.
const core = [node(0, 0, 0, { charted: true }), node(40, 0, 40, { charted: true })];
const rim = [node(600, 0, 600), node(-600, 0, -600)];
const sky = [...core, ...rim];

const chartedFit = frameLevel({
  level: LEVELS.GALAXY,
  nodes: sky,
  orbitPlan: [],
  fov: 50,
  aspect: 1280 / 720,
});
const everythingFit = frameLevel({
  level: LEVELS.GALAXY,
  nodes: sky.map((entry) => ({ ...entry, charted: true })),
  orbitPlan: [],
  fov: 50,
  aspect: 1280 / 720,
});

// The module reports its own distance. Re-deriving it with `Math.hypot` is the
// duplicate-derivation habit this file exists to guard against -- and the two
// answers differ in the last bit, which is enough to fail a range check whose
// bound is that very number.
const opened = (framed) => framed.distance;

const sample = frameLevel({
  level: LEVELS.GALAXY,
  nodes: [node(0, 0, 0), node(80, 0, 80)],
  orbitPlan: [],
  fov: 50,
  aspect: 1.6,
});
assert.ok(
  Math.abs(
    sample.distance -
      Math.hypot(
        sample.position.x - sample.target.x,
        sample.position.y - sample.target.y,
        sample.position.z - sample.target.z,
      ),
  ) < 1e-9,
  "the reported distance is the standoff from the reported target",
);

assert.ok(
  opened(chartedFit) < opened(everythingFit),
  "the galaxy opens on the charted sky, not on the whole disc",
);
assert.ok(chartedFit.fitted, "a fit that measured real nodes says so");
assert.ok(
  chartedFit.max >= opened(everythingFit),
  "but the clamp still reaches the uncharted rim -- reveal draws it faint, never removes it",
);

// Show all charts every region, so that case fits the lot with no special case.
assert.equal(
  opened(everythingFit),
  opened(
    frameLevel({
      level: LEVELS.GALAXY,
      nodes: sky.map((entry) => ({ ...entry, charted: true })),
      orbitPlan: [],
      fov: 50,
      aspect: 1280 / 720,
    }),
  ),
);

// Nothing charted yet (a first run before Home is picked) still frames something.
const unchartedOnly = frameLevel({
  level: LEVELS.GALAXY,
  nodes: rim,
  orbitPlan: [],
  fov: 50,
  aspect: 1280 / 720,
});
assert.ok(unchartedOnly.fitted, "with nothing charted the whole set is the subject");
assert.ok(opened(unchartedOnly) > 0);

// ── The orbit-guide fit (c64a88a) ──────────────────────────────────────────

// A guide is a circle through the planets on its layer, so its widest point on
// screen falls *between* them. Two planets on one axis plus the ring they sit
// on: fitting the planets alone crops the ring.
const planets = [node(0, 0, 0), node(90, 0, 0), node(-90, 0, 0)];
const orbitPlan = [{ radii: [90] }];

const withRings = frameLevel({
  level: LEVELS.SYSTEM,
  nodes: planets,
  orbitPlan,
  fov: 50,
  aspect: 3,
});
const withoutRings = frameLevel({
  level: LEVELS.SYSTEM,
  nodes: planets,
  orbitPlan: [],
  fov: 50,
  aspect: 3,
});

assert.ok(
  opened(withRings) > opened(withoutRings),
  "a system fits its orbit guides as well as its planets",
);

// The galaxy has no orbit guides, so a plan there changes nothing.
assert.deepEqual(
  frameLevel({ level: LEVELS.GALAXY, nodes: planets, orbitPlan, fov: 50, aspect: 3 }).position,
  frameLevel({ level: LEVELS.GALAXY, nodes: planets, orbitPlan: [], fov: 50, aspect: 3 }).position,
);

// ── The aspect (5bdb110, second fault) ─────────────────────────────────────

// The library batches width/height and applies them on its next tick, so
// `camera.aspect` still carried the previous viewport when a resize was
// handled. The module cannot read a renderer at all -- there is nothing here to
// go stale, and a caller that has no honest aspect gets an unfitted answer
// rather than a confidently wrong one.
const unfitted = frameLevel({
  level: LEVELS.GALAXY,
  nodes: sky,
  orbitPlan: [],
  fov: 50,
  aspect: null,
});
assert.equal(unfitted.fitted, false, "no aspect means no measurement was possible");
assert.ok(opened(unfitted) > 0, "and the level still opens at its art-directed default");

assert.equal(
  frameLevel({ level: LEVELS.GALAXY, nodes: sky, orbitPlan: [], fov: undefined, aspect: 1.7 })
    .fitted,
  false,
  "a missing fov is the same kind of absence",
);
assert.equal(
  frameLevel({ level: LEVELS.GALAXY, nodes: [], orbitPlan: [], fov: 50, aspect: 1.7 }).fitted,
  false,
  "and so is an empty sky",
);

// A wider window needs *no more* distance than a narrower one at the same
// height: the horizontal field is fov x aspect, which is the relationship the
// original fixed distance got backwards.
const narrow = opened(
  frameLevel({ level: LEVELS.GALAXY, nodes: sky, orbitPlan: [], fov: 50, aspect: 1 }),
);
const wide = opened(
  frameLevel({ level: LEVELS.GALAXY, nodes: sky, orbitPlan: [], fov: 50, aspect: 2.4 }),
);
assert.ok(wide <= narrow, "widening the window never pushes the camera further out");

// ── The clamps always contain what the level opens at ──────────────────────

for (const level of [LEVELS.GALAXY, LEVELS.SYSTEM]) {
  for (const aspect of [0.42, 1, 16 / 9, 3.2]) {
    const framed = frameLevel({ level, nodes: sky, orbitPlan, fov: 50, aspect });
    const distance = opened(framed);
    assert.ok(
      framed.min <= distance && distance <= framed.max,
      `${level} at aspect ${aspect} opens inside the range it is then held to`,
    );
    assert.ok(framed.min > 0 && framed.max > framed.min);
  }
}

// ── Same code, same window, same sky ───────────────────────────────────────

const first = frameLevel({ level: LEVELS.GALAXY, nodes: sky, orbitPlan, fov: 50, aspect: 1.6 });
const second = frameLevel({ level: LEVELS.GALAXY, nodes: sky, orbitPlan, fov: 50, aspect: 1.6 });
assert.deepEqual(first, second, "framing is a pure function of what it is handed");

// A node with no fixed coordinates falls back to 0 rather than poisoning the fit.
assert.ok(
  Number.isFinite(
    opened(
      frameLevel({
        level: LEVELS.GALAXY,
        nodes: [{ charted: true }, node(50, 0, 50, { charted: true })],
        orbitPlan: [],
        fov: 50,
        aspect: 1.6,
      }),
    ),
  ),
);

// ── Study framing joins the same module ────────────────────────────────────

const study = frameStudy({ system_x: 10, system_y: -4, system_z: 2 });
assert.deepEqual(study.target, { x: 10, y: -4, z: 2 }, "study looks at the structure itself");
assert.ok(
  study.position.x > study.target.x && study.position.z > study.target.z,
  "and stands off it rather than sitting inside it",
);
assert.equal(frameStudy(null), null, "with nothing selected there is nothing to frame");
assert.equal(
  frameStudy({ system_x: 0, system_y: 0 }),
  null,
  "a structure the layout never placed is not framed at a guess",
);

// ── The arithmetic underneath is unchanged ─────────────────────────────────

assert.ok(
  framingDistance({
    points: [{ x: 0, y: 0, z: 0 }],
    direction: { x: 0, y: 1, z: 1 },
    fov: 50,
    aspect: 1.6,
  }) === null,
  "a single point at the target still needs no distance -- cameraFraming is untouched",
);

// ── The bounds a caller without live controls falls back to ─────────────

assert.deepEqual(cameraBoundsFor("nonsense"), cameraBoundsFor(LEVELS.GALAXY));
for (const level of [LEVELS.GALAXY, LEVELS.SYSTEM, LEVELS.STUDY]) {
  const bounds = cameraBoundsFor(level);
  assert.ok(bounds.min > 0 && bounds.max > bounds.min, `${level} has a usable range`);
}
// These are floors, not the range: a fit is allowed to widen either, which is
// why anything holding live controls must read those instead.
const outgrown = frameLevel({
  level: LEVELS.GALAXY,
  nodes: [node(0, 0, 0, { charted: true }), node(4000, 0, 4000, { charted: true })],
  orbitPlan: [],
  fov: 50,
  aspect: 1.6,
});
assert.ok(
  outgrown.max > cameraBoundsFor(LEVELS.GALAXY).max,
  "a layout that outgrows the default widens the ceiling rather than clipping",
);

// ── Where the camera AIMS, not just how far back it stands ────────────────

// This repository's charted sky, read from `codemble parse codemble`: the
// sixteen regions within two import hops of Home. Its own centre is nowhere
// near the origin the camera used to stare at, which is the whole point.
const CHARTED_SKY = [
  [21.5, -6.6, 19.0], [-45.2, 25.1, 88.2], [-83.6, -20.6, 61.0],
  [-109.6, -17.3, 43.8], [-93.6, -18.1, 122.3], [-112.2, 11.7, 76.2],
  [-124.9, -22.1, 105.5], [-64.0, 9.9, 70.1], [-92.7, 17.8, 42.6],
  [-74.5, 20.9, 98.7], [-116.0, 4.2, 59.1], [-101.6, 3.6, 91.3],
  [-118.2, 16.8, 91.3], [-74.0, -16.5, 37.8], [-78.0, -4.3, 113.4],
  [-128.3, 5.1, 79.6],
].map(([x, y, z]) => node(x, y, z, { charted: true, val: 14 }));

/**
 * Where each star lands on a normalised canvas: -1..1 on both axes.
 *
 * Measured at the edge of what is DRAWN, not at the layout coordinate. A star's
 * glow reaches well past its centre, and framing the centres is how a corrected
 * aim -- which shortens the standoff -- started cropping stars that had only
 * been safe because the camera stood too far back.
 */
function screenSpread(framed, points, aspect, fov = 50) {
  const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
  const cross = (a, b) => ({
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  });
  const unit = (v) => {
    const l = Math.hypot(v.x, v.y, v.z);
    return { x: v.x / l, y: v.y / l, z: v.z / l };
  };
  const fwd = unit({
    x: framed.target.x - framed.position.x,
    y: framed.target.y - framed.position.y,
    z: framed.target.z - framed.position.z,
  });
  const right = unit(cross(fwd, { x: 0, y: 1, z: 0 }));
  const up = cross(right, fwd);
  const tanV = Math.tan((fov * Math.PI) / 360);
  const tanH = tanV * aspect;
  const xs = [];
  const ys = [];
  for (const p of points) {
    const v = { x: p.fx - framed.position.x, y: p.fy - framed.position.y, z: p.fz - framed.position.z };
    const depth = dot(v, fwd);
    if (depth <= 0) continue;
    const glow = drawnRadius(p);
    xs.push((dot(v, right) + glow) / depth / tanH, (dot(v, right) - glow) / depth / tanH);
    ys.push((dot(v, up) + glow) / depth / tanV, (dot(v, up) - glow) / depth / tanV);
  }
  return {
    // How lopsided the framing is: 0 means the two margins match.
    skewX: (Math.min(...xs) + Math.max(...xs)) / 2,
    skewY: (Math.min(...ys) + Math.max(...ys)) / 2,
    fillX: (Math.max(...xs) - Math.min(...xs)) / 2,
    fillY: (Math.max(...ys) - Math.min(...ys)) / 2,
    offscreen: xs.filter((x, i) => Math.abs(x) > 1 || Math.abs(ys[i]) > 1).length,
  };
}

for (const [label, aspect] of [
  ["Expert 1440x720", 1440 / 549],
  ["Easy 1440x720", 1440 / 455],
  ["Expert 1280x720", 1280 / 549],
  ["compact 375", 375 / 300],
  ["compact 320", 320 / 240],
]) {
  const framed = frameLevel({
    level: LEVELS.GALAXY,
    nodes: CHARTED_SKY,
    orbitPlan: [],
    fov: 50,
    aspect,
  });
  const seen = screenSpread(framed, CHARTED_SKY, aspect);

  assert.equal(seen.offscreen, 0, `${label}: nothing charted opens off screen`);

  // The property this aiming exists for. Aiming at the origin measured 15
  // points left and 27 points high on this fixture; aiming at the points'
  // world-space centre made the vertical WORSE (29.6), because under
  // perspective a near point at a given offset projects further out than a far
  // one. Only centring the projected extent fixes both.
  assert.ok(
    Math.abs(seen.skewX) < 0.03,
    `${label}: the sky is horizontally centred (skew ${(seen.skewX * 100).toFixed(1)}%)`,
  );
  assert.ok(
    Math.abs(seen.skewY) < 0.03,
    `${label}: the sky is vertically centred (skew ${(seen.skewY * 100).toFixed(1)}%)`,
  );

  // ...and centring is not bought by flying further out. A centred subject
  // needs LESS standoff, so the sky arrives bigger: this fixture went from
  // filling 63% of the canvas height to 90%.
  //
  // Asserted on whichever axis binds, not on height: this sky is wide and flat,
  // so a wide canvas runs out of height first and a near-square one runs out of
  // width first. Requiring both would be requiring the layout to match the
  // window's shape, which is not something a camera can or should do.
  assert.ok(
    Math.max(seen.fillX, seen.fillY) > 0.8,
    `${label}: the sky fills the frame it was given (${(seen.fillX * 100).toFixed(0)}% x ${(seen.fillY * 100).toFixed(0)}%)`,
  );
}

// A system: the module at the origin with its structures on three call rings.
// Worth stating carefully, because the obvious expectation is wrong. A ring
// symmetric in WORLD space is not symmetric on screen: seen from above at a
// tilt its near side is closer to the camera and so projects further from
// centre than its far side, and aiming at the module leaves the ring sitting
// low in the frame -- measured at 31.6 points off on this fixture, which is
// worse than the galaxy's own 27. Aiming at the module is the intuitive answer
// and it is not the centred one.
const systemNodes = [node(0, 0, 0, { val: 8 })];
for (const [index, radius] of [34, 58, 78].entries()) {
  for (let step = 0; step < 5; step += 1) {
    const angle = 2 * Math.PI * (step / 5 + index * 0.13);
    systemNodes.push(
      node(radius * Math.cos(angle), (step % 3) - 1, radius * Math.sin(angle), { val: 8 }),
    );
  }
}
const systemPlan = [{ radii: [34] }, { radii: [58] }, { radii: [78] }];
for (const [label, aspect] of [
  ["Expert 1440x720", 1440 / 549],
  ["Easy 1440x720", 1440 / 455],
  ["compact 320", 320 / 240],
]) {
  const framed = frameLevel({
    level: LEVELS.SYSTEM,
    nodes: systemNodes,
    orbitPlan: systemPlan,
    fov: 50,
    aspect,
  });
  const seen = screenSpread(framed, systemNodes, aspect);
  assert.ok(
    Math.abs(seen.skewX) < 0.03,
    `${label}: a system is horizontally centred (skew ${(seen.skewX * 100).toFixed(1)}%)`,
  );
  assert.ok(
    Math.abs(seen.skewY) < 0.03,
    `${label}: a system is centred on screen rather than in world units (skew ${(seen.skewY * 100).toFixed(1)}%)`,
  );
  // ...and the correction stays proportional to what it is correcting, so a
  // small system cannot be flung somewhere unrelated to itself.
  assert.ok(
    Math.hypot(framed.target.y, framed.target.z) < 78,
    `${label}: the aim stays inside the system it is framing`,
  );
}

// Same layout, same canvas, same aim. The passes are a fixed count over fixed
// input, so "same code -> same sky" survives the iteration.
const twice = [0, 1].map(() =>
  frameLevel({ level: LEVELS.GALAXY, nodes: CHARTED_SKY, orbitPlan: [], fov: 50, aspect: 1.6 }),
);
assert.deepEqual(twice[0], twice[1], "aiming is deterministic");

// Nothing measurable -> the art-directed default, aimed at the origin, and the
// caller is told it was not fitted rather than having to guess.
const unmeasurable = frameLevel({ level: LEVELS.GALAXY, nodes: [], orbitPlan: [], fov: 50, aspect: 1.6 });
assert.equal(unmeasurable.fitted, false);
assert.deepEqual(unmeasurable.target, { x: 0, y: 0, z: 0 }, "an unfitted level aims at the origin");

console.log("galaxy-view contracts passed");
