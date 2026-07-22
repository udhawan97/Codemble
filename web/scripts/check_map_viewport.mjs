import assert from "node:assert/strict";

import {
  centerMapPoint,
  createMapViewportStore,
  fitMapWidthZoom,
  fitMapZoom,
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

// Fit width keeps layers readable and scrolls the height; never inflates.
assert.equal(fitMapWidthZoom(640, 1088), 640 / 1088);
assert.equal(fitMapWidthZoom(2000, 1088), 1, "small drawings stay at crisp 100%");
assert.equal(fitMapWidthZoom(0, 1088), 1, "unmeasured viewports fall back to 100%");

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
