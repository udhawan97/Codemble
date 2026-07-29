import assert from "node:assert/strict";

import {
  MIN_READABLE_FIT,
  centerMapPoint,
  createMapViewportStore,
  fitMapZoom,
  mapOverviewZoom,
  viewportShowsPoint,
} from "../src/mapViewport.js";

assert.equal(fitMapZoom(320, 480, 1024, 2640), 0.18181818181818182);
assert.equal(
  fitMapZoom(100, 100, 10000, 10000),
  0.05,
  "Fit reaches the documented overview floor",
);

assert.deepEqual(
  centerMapPoint({
    viewportWidth: 320,
    viewportHeight: 480,
    scale: 1,
    point: { x: 500, y: 700 },
  }),
  { scrollLeft: 340, scrollTop: 460 },
  "a compact readable map starts around Home instead of shrinking every target",
);

// A restored viewport is only honest while it shows the focus point; a desktop
// scroll replayed into a compact viewport must be rejected, not obeyed.
assert.equal(
  viewportShowsPoint({
    viewportWidth: 375,
    viewportHeight: 400,
    scale: 1,
    scrollLeft: 0,
    scrollTop: 0,
    point: { x: 488, y: 41 },
  }),
  false,
  "a stale scroll that hides Home is rejected",
);
assert.equal(
  viewportShowsPoint({
    viewportWidth: 375,
    viewportHeight: 400,
    scale: 1,
    scrollLeft: 340,
    scrollTop: 0,
    point: { x: 488, y: 41 },
  }),
  true,
  "a scroll that keeps Home visible is kept",
);
assert.equal(
  viewportShowsPoint({
    viewportWidth: 1236,
    viewportHeight: 280,
    scale: 0.07,
    scrollLeft: 0,
    scrollTop: 0,
    point: { x: 488, y: 3200 },
  }),
  true,
  "at overview scale the whole drawing counts as visible",
);

// Fit, case 1: the whole shape fits readably, so show the whole shape.
assert.equal(
  mapOverviewZoom(1200, 900, 1024, 1200),
  0.75,
  "a drawing that genuinely fits keeps whole-shape behaviour",
);

// Fit, case 2: only a thumbnail fits and the drawing is wider than the
// viewport, so fit the width and let the height scroll.
assert.equal(
  mapOverviewZoom(320, 480, 1024, 2640),
  0.3125,
  "a compact viewport still fits the drawing's width",
);

// Fit, case 3: only a thumbnail fits but the drawing is NARROWER than the
// viewport, so there is no width left to fit. This is the regression: the old
// width fit was capped at 1, which on this repository at 1440x720 resolved to
// exactly the scale the map already opens at.
const DESKTOP = [1396, 323, 1024, 1504];
assert.equal(
  mapOverviewZoom(...DESKTOP),
  MIN_READABLE_FIT,
  "Fit drops to the readable floor when the drawing is narrower than the viewport",
);
assert.ok(
  mapOverviewZoom(...DESKTOP) < 1,
  "Fit is no longer a no-op at the scale the map opens at",
);

// The property the regression broke: from any readable scale, Fit must never
// leave the learner seeing LESS of the drawing than they saw before it.
for (const current of [MIN_READABLE_FIT, 0.5, 0.64, 0.8, 1, 1.5, 2.5]) {
  const next = mapOverviewZoom(...DESKTOP);
  assert.ok(
    next <= current,
    `Fit from ${current} must not zoom in (got ${next})`,
  );
}

assert.equal(mapOverviewZoom(0, 323, 1024, 1504), 1, "unmeasured viewports fall back to 100%");
assert.equal(mapOverviewZoom(1396, 323, 0, 0), 1, "unmeasured content falls back to 100%");

const store = createMapViewportStore();
assert.equal(store.read("architecture"), null);
store.write("architecture", { scale: 1.25, scrollLeft: 140, scrollTop: 280 });
assert.deepEqual(
  store.read("architecture"),
  { scale: 1.25, scrollLeft: 140, scrollTop: 280 },
  "zoom and pan survive a transient MapCanvas remount",
);
store.clear();
assert.equal(store.read("architecture"), null, "a project lifecycle reset clears view state");

console.log("map viewport contracts passed");
