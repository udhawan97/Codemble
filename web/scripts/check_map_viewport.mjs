import assert from "node:assert/strict";

import {
  centerMapPoint,
  createMapViewportStore,
  fitMapZoom,
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
