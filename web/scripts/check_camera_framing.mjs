/**
 * Contract: the galaxy camera frames what is actually there.
 *
 * A PerspectiveCamera's `fov` is vertical, so the horizontal field is
 * `fov x aspect`. A fixed camera distance therefore frames one shape of window
 * and clips another -- which is how v0.8.0 shipped a regression by *giving the
 * stage more height*: the canvas grew, the aspect fell, and the sky narrowed.
 */
import assert from "node:assert/strict";

import { framingDistance } from "../src/cameraFraming.js";

const FOV = 50;

/** Every point must sit inside the frustum of a camera `distance` along `axis`. */
function everyPointVisible(points, direction, fov, aspect, distance) {
  const length = Math.hypot(direction.x, direction.y, direction.z);
  const axis = { x: direction.x / length, y: direction.y / length, z: direction.z / length };
  const tanV = Math.tan((fov * Math.PI) / 360);
  const tanH = tanV * aspect;
  const seed = Math.abs(axis.y) > 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const right = (() => {
    const c = {
      x: seed.y * axis.z - seed.z * axis.y,
      y: seed.z * axis.x - seed.x * axis.z,
      z: seed.x * axis.y - seed.y * axis.x,
    };
    const l = Math.hypot(c.x, c.y, c.z);
    return { x: c.x / l, y: c.y / l, z: c.z / l };
  })();
  const up = {
    x: axis.y * right.z - axis.z * right.y,
    y: axis.z * right.x - axis.x * right.z,
    z: axis.x * right.y - axis.y * right.x,
  };
  const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;

  return points.every((point) => {
    const depth = distance - dot(point, axis);
    if (depth <= 0) return false;
    return (
      Math.abs(dot(point, right)) <= depth * tanH + 1e-9 &&
      Math.abs(dot(point, up)) <= depth * tanV + 1e-9
    );
  });
}

// A flat disc in the XZ plane at the scale `graph/layout.py` actually produces
// on this repository: radius ~628, but only +/-27 of thickness. The scale is
// the point of the fixture -- the disc reaches further from the origin than the
// old fixed camera sat from it, which is what put a quarter of the sky behind
// the camera.
const disc = [];
for (let i = 0; i < 96; i += 1) {
  const angle = (i / 96) * Math.PI * 2;
  disc.push({ x: Math.cos(angle) * 628, y: ((i % 7) - 3) * 9, z: Math.sin(angle) * 590 });
}
const VIEW = { x: 0, y: 105, z: 310 };

// 1. A narrower horizontal field may never need LESS distance. The tilt
//    foreshortens the disc, so for a galaxy-shaped cloud the near edge binds
//    and aspect makes no difference at all -- but it must never invert.
let previous = 0;
for (const aspect of [6, 3.8, 3.16, 2.4, 1.78, 1, 0.6]) {
  const distance = framingDistance({ points: disc, direction: VIEW, fov: FOV, aspect });
  assert.ok(distance > 0, `aspect ${aspect} must produce a distance`);
  assert.ok(
    distance >= previous - 1e-9,
    `narrowing the field must not pull the camera in: ${aspect} gave ${distance} after ${previous}`,
  );
  previous = distance;
}

// 2. The property that actually matters, across a spread of real viewports.
for (const aspect of [0.6, 1, 1.78, 2.4, 3.16, 3.8, 6]) {
  const distance = framingDistance({ points: disc, direction: VIEW, fov: FOV, aspect });
  assert.ok(
    everyPointVisible(disc, VIEW, FOV, aspect, distance),
    `every node must be inside the frustum at aspect ${aspect}`,
  );
}

// 3. The bug this exists to prevent. At the old fixed distance the camera sat
//    *inside* the disc's own radius, so the near edge fell behind it -- and a
//    node behind the camera is not merely cropped, it is gone.
const fixed = Math.hypot(VIEW.x, VIEW.y, VIEW.z);
assert.ok(
  !everyPointVisible(disc, VIEW, FOV, 3.16, fixed),
  "the old fixed distance must fail this disc -- otherwise the fixture proves nothing",
);
assert.ok(
  framingDistance({ points: disc, direction: VIEW, fov: FOV, aspect: 3.16 }) > fixed,
  "a galaxy larger than the fixed camera distance must push the camera back",
);

// 4. Same code, same sky: framing is a pure function of its inputs.
const once = framingDistance({ points: disc, direction: VIEW, fov: FOV, aspect: 3.16 });
const twice = framingDistance({ points: [...disc], direction: { ...VIEW }, fov: FOV, aspect: 3.16 });
assert.equal(once, twice, "framing must be deterministic");

// 5. Nothing to frame, or a nonsense camera, leaves the caller's default alone.
for (const bad of [
  { points: [], direction: VIEW, fov: FOV, aspect: 2 },
  { points: disc, direction: { x: 0, y: 0, z: 0 }, fov: FOV, aspect: 2 },
  { points: disc, direction: VIEW, fov: 0, aspect: 2 },
  { points: disc, direction: VIEW, fov: FOV, aspect: 0 },
  { points: [{ x: 0, y: 0, z: 0 }], direction: VIEW, fov: FOV, aspect: 2 },
]) {
  assert.equal(framingDistance(bad), null, `expected null for ${JSON.stringify(bad.points?.length)}`);
}

// 6. A single off-centre node still frames, and non-finite coordinates are
//    skipped rather than poisoning the result with NaN.
const withJunk = [...disc, { x: Number.NaN, y: 0, z: 0 }, { x: 0, y: Infinity, z: 0 }];
assert.equal(
  framingDistance({ points: withJunk, direction: VIEW, fov: FOV, aspect: 3.16 }),
  once,
  "unusable coordinates must not change the framing",
);

console.log("camera framing contract: ok");
