import assert from "node:assert/strict";

import { framingDistance } from "../src/cameraFraming.js";
import {
  cameraBoundsFor,
  frameLevel,
  frameStudy,
  viewportAspect,
} from "../src/galaxyView.js";
import { LEVELS } from "../src/graphData.js";

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
    sample.distance - Math.hypot(sample.position.x, sample.position.y, sample.position.z),
  ) < 1e-9,
  "the reported distance is the magnitude of the reported position",
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

console.log("galaxy-view contracts passed");
