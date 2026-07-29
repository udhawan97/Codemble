// The ink-to-light dawn animates every sprite in the lit system's group, runs
// amber motes along the region's PROVEN routes, and then restores everything.
//
// Two regressions this guards:
//
//   1. Name plates are the one NON-uniform sprite in that group (scale.x =
//      aspect * scale.y, set by configureNamePlate), so a restore that writes
//      one scalar to all three axes squashes the plate square and leaves it
//      that way until a level change rebuilds the marker.
//   2. A mote may only run along a route the parser PROVED. Animating light
//      down a "possible" route would dramatise a claim the graph never made,
//      which is exactly the kind of wrong a learner cannot detect.
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

const { runDawnSequence, dawnPhases, dawnRoutes } = await import("../src/dawnSequence.js");

function pump(untilMs, stepMs = 100) {
  while (now <= untilMs) {
    const callbacks = frameQueue.splice(0);
    if (!callbacks.length) break;
    for (const callback of callbacks) callback(now);
    now += stepMs;
  }
}

/* --- phases are ordered, and amber never leads the light ----------------- */
assert.equal(dawnPhases(0).ignite, 0, "ignite starts at zero");
assert.equal(dawnPhases(0).flare, 0, "no flare at the very start");
assert.equal(
  dawnPhases(0.3).flare,
  0,
  "amber must not flare while the light is still travelling",
);
assert.ok(dawnPhases(0.3).travel > 0, "travel is under way at 30%");
assert.equal(dawnPhases(1).settle, 1, "settle completes at the end");

/* --- only PROVEN routes carry light -------------------------------------- */
const routes = [
  { src: "far", dst: "demo.region", certain: true },
  { src: "demo.region", dst: "near", certain: true },
  { src: "guess", dst: "demo.region", certain: false },
  { src: "other", dst: "unrelated", certain: true },
];
const hops = new Map([["near", 1], ["far", 4], ["guess", 0]]);
const chosen = dawnRoutes("demo.region", routes, hops);
assert.ok(!chosen.includes("guess"), "an unproven route must never carry the dawn");
assert.ok(!chosen.includes("other"), "a route not touching the region is irrelevant");
assert.deepEqual(chosen, ["near", "far"], "closer to Home lights first, then by id");

/* --- the full sequence restores every value it touched -------------------- */
const scene = new THREE.Scene();
const group = new THREE.Group();
group.name = "codemble-system-demo.region";
scene.add(group);
const neighbour = new THREE.Group();
neighbour.name = "codemble-system-near";
neighbour.position.set(40, 0, 0);
scene.add(neighbour);

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
  children: scene.children.length,
};

const sparkMaterial = new THREE.SpriteMaterial({ opacity: 0 });
const stop = runDawnSequence({
  scene,
  regionId: "demo.region",
  palette: { star: "rgb(244, 196, 106)" },
  dressing: { spark: () => new THREE.Sprite(sparkMaterial) },
  routes,
  hopsById: hops,
});

// A mote was added for the one proven route whose neighbour is in the scene.
assert.equal(
  scene.children.length,
  before.children + 1,
  "one mote per proven route whose neighbour is actually in the scene",
);

// Mid-animation the plate must scale as a shape, not collapse to a square:
// x/y ratio is the plate's aspect and the dawn has no license to change it.
pump(1000);
const midRatio = plate.scale.x / plate.scale.y;
assert.ok(
  Math.abs(midRatio - 5.9) < 1e-6,
  `mid-dawn plate aspect drifted: x/y = ${midRatio}, expected 5.9`,
);

// Run past DAWN_DURATION (1600ms) so the restore branch executes.
pump(2600);
stop();

assert.deepEqual(halo.scale.toArray(), before.halo, "halo scale must be restored exactly");
assert.deepEqual(
  plate.scale.toArray(),
  before.plate,
  "plate scale must be restored per-component (x = aspect * y, z = 1)",
);
assert.equal(plate.material.opacity, before.plateOpacity, "opacity restored");
assert.equal(
  scene.children.length,
  before.children,
  "every mote is removed from the scene when the dawn ends",
);

/* --- bloom sizes its pass chain from the host, not from the composer ----- */

// The composer PRESENTS through the pass chain, so an unsized chain is a blank
// canvas: correctly sized element, no console error, nothing drawn. It reached
// that state whenever the renderer re-mounted into a host of the same size --
// the width/height props are diffed, an unchanged prop is skipped, and
// `composer.setSize` is the only thing that sizes the chain. Switching to the
// Diagram and back did exactly that.
const { attachBloom } = await import("../src/galaxyEffects.js");

function fakeRenderer(composerWidth, composerHeight) {
  const sized = [];
  const passes = [];
  const composer = {
    _width: composerWidth,
    _height: composerHeight,
    addPass: (pass) => {
      passes.push(pass);
      // EffectComposer sizes a pass on insert, from what IT currently holds --
      // which is the `undefined` the real fault flowed from.
      pass.setSize?.(composer._width ?? 0, composer._height ?? 0);
    },
    removePass: (pass) => passes.splice(passes.indexOf(pass), 1),
    setSize: (width, height) => {
      composer._width = width;
      composer._height = height;
      sized.push([width, height]);
      for (const pass of passes) pass.setSize?.(width, height);
    },
  };
  return { renderer: { postProcessingComposer: () => composer }, composer, sized };
}

// The fault: a fresh composer that is never resized afterwards.
const unsized = fakeRenderer(undefined, undefined);
const attached = attachBloom(unsized.renderer, { width: 1440, height: 555 });
assert.deepEqual(
  unsized.sized.at(-1),
  [1440, 555],
  "the pass chain is sized from the host even when the composer holds nothing",
);
assert.ok(
  attached.pass.resolution.x > 1 && attached.pass.resolution.y > 1,
  "and the bloom pass is not left at the 1x1 it would otherwise be built with",
);

// The retina cap still applies to the size that arrives here, so this cannot
// quietly undo it: a 2560-wide host clamps the blur, not the scene.
const capped = fakeRenderer(undefined, undefined);
const cappedBloom = attachBloom(capped.renderer, { width: 2560, height: 1440 });
assert.ok(
  Math.max(cappedBloom.pass.resolution.x, cappedBloom.pass.resolution.y) <= 1600,
  "bloom resolution stays capped when the host is larger than the cap",
);
assert.deepEqual(
  capped.sized.at(-1),
  [2560, 1440],
  "while the composer itself keeps the host's real size",
);

// No host measurement yet -> keep whatever the composer holds rather than
// forcing the chain to 1x1.
const measured = fakeRenderer(800, 600);
attachBloom(measured.renderer, null);
assert.deepEqual(
  measured.sized.at(-1),
  [800, 600],
  "an unmeasured host keeps the composer's own size",
);

performance.now = realNow;
console.log(
  "check_galaxy_effects: ink-to-light dawn phases, proven-route motes, exact restore, sized bloom chain",
);
