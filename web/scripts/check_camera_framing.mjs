import assert from "node:assert/strict";

import { frameNodes, projectToScreen } from "../src/cameraFraming.js";

const GALAXY_PITCH = 105 / 310;
const SYSTEM_PITCH = 52 / 150;
const GALAXY_BOUNDS = { min: 120, max: 640 };
const SYSTEM_BOUNDS = { min: 55, max: 320 };

// This repository's real galaxy layout, read from /api/graph. Deterministic
// output of the community placement, so it is a fixture rather than a sample:
// its bounding box is x[-209, 80.6] y[-25.7, 25.1] z[-45.6, 199.3], centred at
// roughly (-64, 0, +77) -- nowhere near the origin the old camera stared at.
const GALAXY_REGIONS = [
  { x: 21.020056, y: -6.414822, z: 18.542976 },
  { x: -73.662422, y: 25.090255, z: 143.77367 },
  { x: -136.3136, y: -20.051243, z: 99.384391 },
  { x: -178.676869, y: -16.791206, z: 71.355913 },
  { x: -152.521704, y: -17.614235, z: 199.262175 },
  { x: -182.899722, y: 11.408227, z: 124.13424 },
  { x: -203.567929, y: -21.532794, z: 171.889593 },
  { x: -104.385045, y: 9.627615, z: 114.293515 },
  { x: -151.064048, y: 17.304185, z: 69.514331 },
  { x: -121.426149, y: 20.297565, z: 160.898099 },
  { x: -189.13476, y: 4.126118, z: 96.327538 },
  { x: -165.606627, y: 3.480623, z: 148.84302 },
  { x: -192.654979, y: 16.351947, z: 148.769022 },
  { x: -120.582956, y: -16.044701, z: 61.683199 },
  { x: -127.1829, y: -4.209396, z: 184.873994 },
  { x: -209.043444, y: 4.915071, z: 129.718044 },
  { x: -157.837181, y: 22.629669, z: 174.642305 },
  { x: -84.454508, y: 3.798299, z: 127.625157 },
  { x: 57.990496, y: -10.402205, z: 0.551398 },
  { x: 27.79977, y: -14.61905, z: -45.588617 },
  { x: 3.1738, y: -25.681121, z: -9.619054 },
  { x: -97.713511, y: -5.289538, z: 176.164545 },
  { x: 58.933967, y: -21.736323, z: 32.654988 },
  { x: -161.594571, y: 15.364683, z: 87.316533 },
  { x: -95.1709, y: 0.955555, z: 85.361432 },
  { x: -127.619787, y: -16.12049, z: 132.491362 },
  { x: 22.948492, y: 10.66787, z: 41.202477 },
  { x: -118.667722, y: -24.409588, z: 83.696938 },
  { x: -180.311612, y: -21.787685, z: 180.125958 },
  { x: -97.32594, y: 4.930265, z: 150.346084 },
  { x: 49.864666, y: -24.315823, z: -32.018823 },
  { x: 80.587123, y: 18.774804, z: -18.59258 },
];

// Every canvas the app actually renders at 720px tall, plus the compact ones.
// Easy keeps a guidance strip and Expert does not, so the two registers hand
// the scene different heights -- and the fov is vertical, so that changes the
// horizontal view too. Each row records how many regions the OLD fixed camera
// pushed off-screen.
const CANVASES = [
  { label: "Expert 1440x720", width: 1440, height: 549, wasClipped: 2 },
  { label: "Easy 1440x720", width: 1440, height: 455, wasClipped: 2 },
  { label: "Expert 1280x720", width: 1280, height: 549, wasClipped: 3 },
  { label: "Easy 1280x720", width: 1280, height: 455, wasClipped: 2 },
  { label: "compact 375", width: 375, height: 300, wasClipped: 16 },
  { label: "compact 320", width: 320, height: 240, wasClipped: 13 },
];

const OLD_CAMERA = { position: { x: 0, y: 105, z: 310 }, target: { x: 0, y: 0, z: 0 } };

function screenPoints(camera, canvas) {
  return GALAXY_REGIONS.map((region) =>
    projectToScreen({
      point: region,
      position: camera.position,
      target: camera.target,
      width: canvas.width,
      height: canvas.height,
    }),
  );
}

function clippedCount(points, canvas) {
  return points.filter(
    (p) => !p || p.x < 0 || p.x > canvas.width || p.y < 0 || p.y > canvas.height,
  ).length;
}

for (const canvas of CANVASES) {
  const framed = frameNodes({
    nodes: GALAXY_REGIONS,
    width: canvas.width,
    height: canvas.height,
    pitch: GALAXY_PITCH,
    bounds: GALAXY_BOUNDS,
  });
  assert.ok(framed, `${canvas.label}: a measurable canvas is framed`);

  // First, the fixture is a real regression test: the old constants really did
  // push these regions off-screen. Without this the property below could pass
  // against a layout that never had the problem.
  assert.equal(
    clippedCount(screenPoints(OLD_CAMERA, canvas), canvas),
    canvas.wasClipped,
    `${canvas.label}: the fixed camera clipped ${canvas.wasClipped} regions`,
  );

  // The property: nothing the parser charted opens off-screen.
  const points = screenPoints(framed, canvas);
  assert.equal(
    clippedCount(points, canvas),
    0,
    `${canvas.label}: every charted region opens inside the canvas`,
  );

  // ...and it is not achieved by simply flying far away until everything is a
  // dot. The sky still has to fill the frame it was given.
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const fillX = (Math.max(...xs) - Math.min(...xs)) / canvas.width;
  const fillY = (Math.max(...ys) - Math.min(...ys)) / canvas.height;
  assert.ok(
    fillX >= 0.35 && fillY >= 0.25,
    `${canvas.label}: the sky fills the canvas (x ${(fillX * 100).toFixed(0)}%, y ${(fillY * 100).toFixed(0)}%)`,
  );
}

// The orbit clamps still own the range. A tiny system must not let the camera
// dive inside the level's minimum, and a sprawling one must not escape its
// maximum -- "you cannot get lost" is a clamp, not a distance.
const tight = frameNodes({
  nodes: [{ x: 0, y: 0, z: 0 }, { x: 1, y: 1, z: 1 }],
  width: 1440,
  height: 549,
  pitch: SYSTEM_PITCH,
  bounds: SYSTEM_BOUNDS,
});
assert.equal(tight.distance, SYSTEM_BOUNDS.min, "a tiny system is held at the orbit minimum");

const sprawling = frameNodes({
  nodes: [{ x: -5000, y: 0, z: -5000 }, { x: 5000, y: 0, z: 5000 }],
  width: 1440,
  height: 549,
  pitch: GALAXY_PITCH,
  bounds: GALAXY_BOUNDS,
});
assert.equal(sprawling.distance, GALAXY_BOUNDS.max, "a sprawling galaxy is held at the orbit maximum");

// Nothing measurable yet -> the caller keeps whatever the camera was doing
// rather than flying somewhere arbitrary because a measurement was not ready.
assert.equal(frameNodes({ nodes: [], width: 1440, height: 549, pitch: GALAXY_PITCH }), null);
assert.equal(frameNodes({ nodes: GALAXY_REGIONS, width: 0, height: 0, pitch: GALAXY_PITCH }), null);
assert.equal(
  frameNodes({ nodes: [{ x: NaN, y: 0, z: 0 }], width: 1440, height: 549, pitch: GALAXY_PITCH }),
  null,
  "unplaced nodes do not produce a NaN camera",
);

// Same layout, same canvas, same camera. "Same code -> same sky" is an
// acceptance criterion and deriving the camera must not weaken it.
const first = frameNodes({ nodes: GALAXY_REGIONS, width: 1440, height: 549, pitch: GALAXY_PITCH, bounds: GALAXY_BOUNDS });
const second = frameNodes({ nodes: [...GALAXY_REGIONS], width: 1440, height: 549, pitch: GALAXY_PITCH, bounds: GALAXY_BOUNDS });
assert.deepEqual(first, second, "framing is deterministic");

console.log("camera framing contracts passed");
