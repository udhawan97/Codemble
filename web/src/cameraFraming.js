/**
 * How far the camera has to sit to hold a whole level on screen.
 *
 * A `PerspectiveCamera`'s `fov` is *vertical*, so the horizontal field is
 * `fov x aspect`. A fixed distance therefore frames one shape of window and
 * clips another, and it fails in the direction nobody expects: giving the
 * stage more height lowers the aspect and *narrows* the view sideways. That is
 * how v0.8.0 shipped a clipped galaxy by making the canvas taller.
 *
 * The camera's tilt is an art direction choice and stays fixed; only the
 * distance along it is computed here. Pure and allocation-light so that "same
 * code -> same sky" survives: the result depends on nothing but its arguments.
 */

const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;

const cross = (a, b) => ({
  x: a.y * b.z - a.z * b.y,
  y: a.z * b.x - a.x * b.z,
  z: a.x * b.y - a.y * b.x,
});

function unit(vector) {
  if (!vector) return null;
  const { x, y, z } = vector;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;
  const length = Math.hypot(x, y, z);
  return length > 0 ? { x: x / length, y: y / length, z: z / length } : null;
}

/**
 * Smallest distance along `direction` that keeps every point inside the
 * frustum, or `null` when there is nothing to frame — callers keep their own
 * default rather than receive a made-up number.
 *
 * @param {object}   options
 * @param {Array<{x:number,y:number,z:number}>} options.points Node positions
 *   **relative to the camera's look-at target** (the origin everywhere today).
 * @param {{x:number,y:number,z:number}} options.direction Target-to-camera
 *   direction. Length is ignored; only the tilt is used.
 * @param {number}   options.fov     Vertical field of view, in degrees.
 * @param {number}   options.aspect  Canvas width / height.
 * @param {number}  [options.padding] Breathing room for star radii and the
 *   name plates, which are drawn beyond the point they belong to.
 * @returns {number|null}
 */
export function framingDistance({ points, direction, fov, aspect, padding = 1.12 }) {
  const axis = unit(direction);
  if (!axis || !Array.isArray(points) || points.length === 0) return null;
  if (!Number.isFinite(fov) || fov <= 0 || fov >= 180) return null;
  if (!Number.isFinite(aspect) || aspect <= 0) return null;

  const tanV = Math.tan((fov * Math.PI) / 360);
  const tanH = tanV * aspect;

  // Any two unit vectors perpendicular to the view axis will do: the frustum is
  // symmetric about it, so only the magnitude of an offset matters, never its
  // sign. The seed only has to not be parallel to the axis.
  const seed = Math.abs(axis.y) > 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const right = unit(cross(seed, axis));
  if (!right) return null;
  // Unit by construction: axis and right are unit and perpendicular.
  const up = cross(axis, right);

  let distance = 0;
  for (const point of points) {
    if (!point) continue;
    const { x, y, z } = point;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    // A camera at `distance * axis` sees this point at depth `distance - along`,
    // so a node on the near side of the target needs less room than a far one.
    const along = dot(point, axis);
    const lateral = Math.abs(dot(point, right)) / tanH;
    const vertical = Math.abs(dot(point, up)) / tanV;
    distance = Math.max(distance, along + lateral, along + vertical);
  }

  return distance > 0 ? distance * padding : null;
}

/** Scale a direction to an exact length, for handing to `cameraPosition`. */
export function cameraPositionAt(direction, distance) {
  const axis = unit(direction);
  if (!axis || !Number.isFinite(distance)) return null;
  return { x: axis.x * distance, y: axis.y * distance, z: axis.z * distance };
}
