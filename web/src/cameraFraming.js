/**
 * Where the camera starts, derived from the layout instead of hardcoded.
 *
 * The galaxy used to open from two constants -- `{x:0, y:105, z:310}` looking at
 * `{x:0, y:0, z:0}` -- independent of both the canvas and the content. Neither
 * assumption held. The parser-derived constellation is not centred on the
 * origin (on this repository its bounding box is x[-209, 80.6], z[-45.6, 199.3],
 * so its centre is at roughly (-64, 0, +77)), and a PerspectiveCamera's fov is
 * VERTICAL, so a short wide canvas sees less of the sky than a tall one at the
 * same distance. Measured at 1440x720 in Expert, the result was 42% of the
 * canvas empty above the content, 40% empty to its right, and two of thirty-two
 * systems projecting outside the canvas entirely.
 *
 * This module answers one question -- given the nodes, the canvas and the fov,
 * where does the camera go -- and answers it with the exact corner-fit rather
 * than a bounding sphere, because a sphere around a flat, wide galaxy pushes
 * the camera much further back than the shape needs.
 *
 * What it deliberately does NOT change: the viewing angle (each level keeps the
 * shallow look-down its constants encoded) and the orbit clamps (the distance is
 * clamped into the level's existing CAMERA_BOUNDS, so "you cannot get lost"
 * still means exactly what it meant).
 */

// A little air around the outermost node, so a sphere whose centre is exactly
// on the bounding box does not have its far side shaved by the frustum.
const FRAME_MARGIN = 1.12;

function boundingBox(nodes) {
  let minX = Infinity;
  let minY = Infinity;
  let minZ = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let maxZ = -Infinity;
  for (const node of nodes) {
    const { x, y, z } = node;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (z < minZ) minZ = z;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
    if (z > maxZ) maxZ = z;
  }
  if (!Number.isFinite(minX)) return null;
  return {
    center: { x: (minX + maxX) / 2, y: (minY + maxY) / 2, z: (minZ + maxZ) / 2 },
    half: { x: (maxX - minX) / 2, y: (maxY - minY) / 2, z: (maxZ - minZ) / 2 },
  };
}

function normalize(v) {
  const length = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / length, y: v.y / length, z: v.z / length };
}

function cross(a, b) {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  };
}

function dot(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/**
 * Frame `nodes` for a camera looking down the given pitch.
 *
 * `pitch` is rise over run along +z, taken straight from the constants this
 * replaces (galaxy 105/310, system 52/150) so the sky keeps the angle it has
 * always been drawn at. `fov` is the camera's VERTICAL field of view in
 * degrees; three's PerspectiveCamera defaults to 50.
 *
 * Returns `null` when there is nothing to frame, so the caller can keep
 * whatever the camera was already doing rather than fly somewhere arbitrary.
 */
export function frameNodes({ nodes, width, height, fov = 50, pitch, bounds }) {
  const box = nodes?.length ? boundingBox(nodes) : null;
  if (!box || !width || !height) return null;

  // Camera basis. `forward` points from the camera toward the content.
  const forward = normalize({ x: 0, y: -pitch, z: -1 });
  const right = normalize(cross(forward, { x: 0, y: 1, z: 0 }));
  const up = cross(right, forward);

  const tanVertical = Math.tan((fov * Math.PI) / 360);
  // The fov is vertical, so the horizontal half-angle grows with the aspect.
  // This is the term the fixed constants had no way to account for, and it is
  // why v0.8.0's taller canvas narrowed the horizontal view rather than
  // widening it.
  const tanHorizontal = tanVertical * (width / height);

  // For a camera at `center - forward * distance`, a corner at offset v needs
  //     |dot(v, right)| <= tanHorizontal * (dot(v, forward) + distance)
  // and the same vertically. Solve each for distance and take the worst corner.
  let distance = 0;
  for (const sx of [-1, 1]) {
    for (const sy of [-1, 1]) {
      for (const sz of [-1, 1]) {
        const v = { x: sx * box.half.x, y: sy * box.half.y, z: sz * box.half.z };
        const depth = dot(v, forward);
        distance = Math.max(
          distance,
          Math.abs(dot(v, right)) / tanHorizontal - depth,
          Math.abs(dot(v, up)) / tanVertical - depth,
        );
      }
    }
  }
  distance *= FRAME_MARGIN;
  if (bounds) distance = Math.min(bounds.max, Math.max(bounds.min, distance));

  return {
    target: box.center,
    position: {
      x: box.center.x - forward.x * distance,
      y: box.center.y - forward.y * distance,
      z: box.center.z - forward.z * distance,
    },
    distance,
  };
}

/**
 * Screen position of a world point for the same camera, in canvas pixels.
 *
 * Exported for the contract check: asserting that every region lands inside the
 * canvas is the only way to state this module's job as a property rather than
 * as a number somebody eyeballed once.
 */
export function projectToScreen({ point, position, target, width, height, fov = 50 }) {
  const forward = normalize({
    x: target.x - position.x,
    y: target.y - position.y,
    z: target.z - position.z,
  });
  const right = normalize(cross(forward, { x: 0, y: 1, z: 0 }));
  const up = cross(right, forward);
  const v = { x: point.x - position.x, y: point.y - position.y, z: point.z - position.z };
  const depth = dot(v, forward);
  if (depth <= 0) return null;
  const tanVertical = Math.tan((fov * Math.PI) / 360);
  const tanHorizontal = tanVertical * (width / height);
  return {
    x: ((dot(v, right) / depth / tanHorizontal + 1) / 2) * width,
    y: ((1 - dot(v, up) / depth / tanVertical) / 2) * height,
  };
}
