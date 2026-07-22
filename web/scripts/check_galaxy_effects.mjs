// The nebula dawn animates every sprite in the lit system's group and then
// restores it. Name plates are the one NON-uniform sprite in that group
// (scale.x = aspect * scale.y, set by configureNamePlate), so a restore that
// writes one scalar to all three axes squashes the plate square and leaves it
// that way until a level change rebuilds the marker. This drives the real
// runNebulaDawn to completion under a fake clock and asserts every component
// of every sprite's scale survives the round trip.
import assert from "node:assert/strict";
import * as THREE from "three";

// Deterministic fake frame clock, installed before the module under test runs.
let now = 0;
const frameQueue = [];
globalThis.requestAnimationFrame = (callback) => {
  frameQueue.push(callback);
  return frameQueue.length;
};
globalThis.cancelAnimationFrame = () => {};
const realNow = performance.now.bind(performance);
performance.now = () => now;

const { runNebulaDawn } = await import("../src/galaxyEffects.js");

function pump(untilMs, stepMs = 100) {
  while (now <= untilMs) {
    const callbacks = frameQueue.splice(0);
    if (!callbacks.length) break;
    for (const callback of callbacks) callback(now);
    now += stepMs;
  }
}

const scene = new THREE.Scene();
const group = new THREE.Group();
group.name = "codemble-system-demo.region";
scene.add(group);

const material = () =>
  new THREE.SpriteMaterial({ color: new THREE.Color("rgb(125, 138, 168)"), opacity: 0.6 });

// A halo: uniform scale, the case that always worked.
const halo = new THREE.Sprite(material());
halo.scale.setScalar(9.75);
group.add(halo);

// A name plate: non-uniform scale, the case the dawn used to flatten.
const plate = new THREE.Sprite(material());
plate.scale.set(0.034 * 5.9, 0.034, 1);
group.add(plate);

const before = {
  halo: halo.scale.toArray(),
  plate: plate.scale.toArray(),
  plateOpacity: plate.material.opacity,
};

const stop = runNebulaDawn({
  scene,
  regionId: "demo.region",
  palette: { star: "rgb(244, 196, 106)" },
});

// Mid-animation the plate must scale as a shape, not collapse to a square:
// x/y ratio is the plate's aspect and the dawn has no license to change it.
pump(600);
const midRatio = plate.scale.x / plate.scale.y;
assert.ok(
  Math.abs(midRatio - 5.9) < 1e-6,
  `mid-dawn plate aspect drifted: x/y = ${midRatio}, expected 5.9`,
);

// Run past DAWN_DURATION (1200ms) so the restore branch executes.
pump(2000);
stop();

assert.deepEqual(
  halo.scale.toArray(),
  before.halo,
  "halo scale must be restored exactly",
);
assert.deepEqual(
  plate.scale.toArray(),
  before.plate,
  "plate scale must be restored per-component (x = aspect * y, z = 1)",
);
assert.equal(plate.material.opacity, before.plateOpacity, "opacity restored");

performance.now = realNow;
console.log("check_galaxy_effects: nebula dawn restores non-uniform sprite scales");
