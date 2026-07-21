import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { clearStaleNonTouchPointers } from "../src/orbitPointerGuard.js";

const empty = { _pointers: [], _pointerPositions: {} };
assert.equal(clearStaleNonTouchPointers(empty, { pointerType: "mouse" }), false);

const touch = { _pointers: [4, 7], _pointerPositions: { 4: { x: 1 }, 7: { x: 2 } } };
assert.equal(clearStaleNonTouchPointers(touch, { pointerType: "touch" }), false);
assert.deepEqual(touch._pointers, [4, 7]);

const stalePointers = [3, 9];
const stalePositions = { 3: { x: 20, y: 30 } };
const mouse = { _pointers: stalePointers, _pointerPositions: stalePositions };
assert.equal(clearStaleNonTouchPointers(mouse, { pointerType: "mouse" }), true);
assert.equal(mouse._pointers, stalePointers, "mutate OrbitControls' collection in place");
assert.deepEqual(mouse._pointers, []);
assert.deepEqual(mouse._pointerPositions, {});

const pen = { _pointers: [11], _pointerPositions: {} };
assert.equal(clearStaleNonTouchPointers(pen, { pointerType: "pen" }), true);
assert.deepEqual(pen._pointers, []);

assert.equal(clearStaleNonTouchPointers({}, { pointerType: "mouse" }), false);

const galaxySource = readFileSync(new URL("../src/GalaxyCanvas.jsx", import.meta.url), "utf8");
assert.match(
  galaxySource,
  /\.enableNodeDrag\(false\)/,
  "the immutable graph must not install 3d-force-graph drag controls",
);

console.log("orbit pointer guard contract: ok");
