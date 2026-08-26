import assert from "node:assert/strict";

import * as canvasOcclusion from "../src/canvasOcclusion.js";

assert.deepEqual(
  Object.keys(canvasOcclusion),
  ["measureCanvasOcclusion"],
  "canvas occlusion exposes one measurement operation",
);

function element(box, pointerEvents = "auto") {
  return { box, pointerEvents, getBoundingClientRect: () => box };
}

const clickable = element({ left: 130, right: 190, top: 80, bottom: 110, width: 60, height: 30 });
const ignoredClick = element(
  { left: 200, right: 240, top: 80, bottom: 110, width: 40, height: 30 },
  "none",
);
const emptyClick = element({ left: 250, right: 250, top: 80, bottom: 110, width: 0, height: 30 });
const orientation = element({ left: 110, right: 310, top: 60, bottom: 90, width: 200, height: 30 }, "none");
const keyboard = element({ left: 120, right: 260, top: 500, bottom: 525, width: 140, height: 25 }, "none");
const stage = {
  querySelectorAll(selector) {
    if (selector === ".orientation-copy--system, .system-navigator, .legend-toggle") {
      return [clickable, ignoredClick, emptyClick];
    }
    if (
      selector ===
      ".orientation-bar, .orientation-copy--system, .system-navigator, .keyboard-focus"
    ) {
      return [orientation, keyboard];
    }
    throw new Error(`unexpected selector: ${selector}`);
  },
};
const parent = { querySelectorAll: () => { throw new Error("must query the stage, not the parent"); } };
const host = {
  parentElement: parent,
  closest(selector) {
    assert.equal(selector, ".map-stage");
    return stage;
  },
  getBoundingClientRect: () => ({ left: 100, right: 900, top: 50, bottom: 650, width: 800, height: 600 }),
};
const measured = canvasOcclusion.measureCanvasOcclusion({
  host,
  renderer: { width: () => 1, height: () => 1 },
  getStyle: (target) => ({ pointerEvents: target.pointerEvents }),
});
assert.deepEqual(measured.viewport, { width: 800, height: 600 });
assert.deepEqual(measured.clickObstructions, [
  { left: 30, right: 90, top: 30, bottom: 60 },
]);
assert.deepEqual(measured.nameObstructions, [
  { left: 10, right: 210, top: 10, bottom: 40 },
  { left: 20, right: 160, top: 450, bottom: 475 },
]);
assert.ok(Object.isFrozen(measured));
assert.ok(Object.isFrozen(measured.clickObstructions));

const fallback = canvasOcclusion.measureCanvasOcclusion({
  host: {
    closest: () => null,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0 }),
  },
  renderer: { width: () => 640, height: () => 360 },
});
assert.deepEqual(fallback, {
  viewport: { width: 640, height: 360 },
  clickObstructions: [],
  nameObstructions: [],
});

const unmeasured = canvasOcclusion.measureCanvasOcclusion({
  host: null,
  renderer: { width: () => 0, height: () => 0 },
});
assert.equal(unmeasured.viewport, null);
assert.deepEqual(unmeasured.clickObstructions, []);
assert.deepEqual(unmeasured.nameObstructions, []);

console.log("canvas occlusion contract: ok");
