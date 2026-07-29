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
 * @param {number}  [options.margin] Fraction of each half-axis held in reserve
 *   for what is drawn *around* a node rather than at it — its radius and halo.
 *   Deliberately not sized for name plates: a plate keeps its pixel width
 *   whatever the camera does, so no fixed share of the frame can cover it on a
 *   narrow window. `nameAtlas` keeps plates on screen instead, which is where
 *   plate geometry already lives.
 * @returns {number|null}
 */
export function framingDistance({ points, direction, fov, aspect, margin = 0.1 }) {
  const axis = unit(direction);
  if (!axis || !Array.isArray(points) || points.length === 0) return null;
  if (!Number.isFinite(fov) || fov <= 0 || fov >= 180) return null;
  if (!Number.isFinite(aspect) || aspect <= 0) return null;

  const usable = 1 - Math.min(Math.max(margin, 0), 0.9);
  const tanV = Math.tan((fov * Math.PI) / 360) * usable;
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
    // `radius` is what is drawn AROUND this point rather than at it, in world
    // units -- a star's glow. Per point, because the sets handed here are mixed:
    // a system fits its planets AND the guide circles they sit on, and a guide
    // is a line with no glow to reserve for. The `margin` fraction cannot
    // express this at all: a share of the frame is a different number of world
    // units at every distance, so it over-reserves on a wide sky and
    // under-reserves on a tight one -- which is exactly how correcting the aim,
    // and so shortening the standoff, began cropping stars that had been safe
    // only because the camera stood too far back.
    const radius = Number.isFinite(point.radius) ? Math.max(0, point.radius) : 0;
    const lateral = (Math.abs(dot(point, right)) + radius) / tanH;
    const vertical = (Math.abs(dot(point, up)) + radius) / tanV;
    distance = Math.max(distance, along + lateral, along + vertical);
  }

  return distance > 0 ? distance : null;
}

/** Scale a direction to an exact length, for handing to `cameraPosition`. */
export function cameraPositionAt(direction, distance) {
  const axis = unit(direction);
  if (!axis || !Number.isFinite(distance)) return null;
  return { x: axis.x * distance, y: axis.y * distance, z: axis.z * distance };
}

// `framingDistance` answers "how far", but where the camera AIMS changes what
// fits, so the two are coupled and have to be solved together. Each pass aims
// exactly for the distance it has, then refits the distance for the aim it just
// chose. Fixed counts rather than loop-until-converged: "same code -> same sky"
// wants an answer that does not depend on a tolerance, and both loops here are
// cheap arithmetic over a few hundred points.
// 24 passes because the coupling converges linearly, not quadratically: aiming
// better shortens the distance, a shorter distance deepens the perspective, and
// a deeper perspective moves the ideal aim again. Traced on a system view the
// residual falls by roughly a fifth per pass -- 13.5pp, 10.6, 8.7, 5.1, 2.3,
// 0.1 -- so it is under a tenth of a point by the sixteenth and flat by the
// twenty-fourth. Damping was tried and is strictly worse: it converges to the
// same place more slowly. The whole loop is a few hundred thousand float
// operations, run once per level change or resize.
const CENTRING_PASSES = 24;
// Halvings per solve. 30 leaves the bracket smaller than a millionth of the
// layout, which is far below anything a pixel can show.
const SOLVE_STEPS = 30;

/**
 * The sideways shift that makes the projected extremes symmetric, solved rather
 * than stepped toward.
 *
 * Moving the aim by d along an axis perpendicular to the view leaves every
 * point's depth alone, so each point's screen offset is `(offset - d) / depth`
 * -- and the imbalance `max + min` is continuous and strictly decreasing in d.
 * The answer is therefore a root, bracketed by the smallest and largest offsets
 * in the set, and bisection finds it whatever the perspective.
 *
 * The first version stepped toward it instead, by the error measured at the
 * mean depth of the two extreme points. That converges when the subject is far
 * away relative to its own size, and stalls when it is not: a system view sits
 * 66 units from a ring of radius 58, where the near edge is three times closer
 * than the far one, and the step overshot and settled 15 points off centre.
 */
function centringShift(offsets, depths) {
  if (!offsets.length) return 0;
  const imbalance = (shift) => {
    let high = -Infinity;
    let low = Infinity;
    for (let i = 0; i < offsets.length; i += 1) {
      const screen = (offsets[i] - shift) / depths[i];
      if (screen > high) high = screen;
      if (screen < low) low = screen;
    }
    return high + low;
  };
  // At the smallest offset every point is at or right of the aim, so the
  // imbalance is positive; at the largest it is negative. The root is between.
  let low = Math.min(...offsets);
  let high = Math.max(...offsets);
  for (let step = 0; step < SOLVE_STEPS; step += 1) {
    const middle = (low + high) / 2;
    if (imbalance(middle) > 0) low = middle;
    else high = middle;
  }
  return (low + high) / 2;
}

/**
 * Where to aim, and how far back to stand, so the points fill the frame evenly.
 *
 * `framingDistance` alone guarantees only that nothing is off screen -- it says
 * nothing about *where* on screen. Aiming at a fixed point (the origin, until
 * now) works when the content is centred there, which parser-derived layouts
 * simply are not: this project's charted sky sits 15pp left of centre and 27pp
 * high, hugging one edge with a third of the canvas empty on the other side.
 *
 * The world-space centre of the points is not the answer either, and that is
 * the part worth stating: under perspective a near point at a given lateral
 * offset projects further from centre than a far one, so a set centred in world
 * units is still lopsided on screen. Aiming at the world centre measured *worse*
 * vertically than aiming at the origin (29.6pp against 27.1pp). What has to be
 * centred is the projected extent, which depends on the distance, which depends
 * on the aim -- hence the passes.
 *
 * A shorter distance falls out of it for free: a centred subject needs less
 * standoff than an off-centre one, so the sky also arrives bigger (this project
 * fills 63% of the canvas height at the origin, 90% aimed properly).
 *
 * @param {object} options Same shape as `framingDistance`.
 * @returns {{target: {x,y,z}, distance: number}|null} `target` is relative to
 *   the coordinates the points were given in; `null` when there is nothing to
 *   frame, so callers keep their own default rather than get a made-up number.
 */
export function frameAround({ points, direction, fov, aspect, margin = 0.1 }) {
  const axis = unit(direction);
  if (!axis || !Array.isArray(points) || points.length === 0) return null;
  const usable = points.filter(
    (p) => p && Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z),
  );
  if (!usable.length) return null;

  const seed = Math.abs(axis.y) > 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const right = unit(cross(seed, axis));
  if (!right) return null;
  const up = cross(axis, right);

  const midpoint = (basis) => {
    let low = Infinity;
    let high = -Infinity;
    for (const point of usable) {
      const along = dot(point, basis);
      if (along < low) low = along;
      if (along > high) high = along;
    }
    return (low + high) / 2;
  };
  // Start from the world-space midpoint. It is the wrong answer on its own, but
  // it is a much better first guess than the origin, so fewer passes are needed.
  let target = {
    x: right.x * midpoint(right) + up.x * midpoint(up) + axis.x * midpoint(axis),
    y: right.y * midpoint(right) + up.y * midpoint(up) + axis.y * midpoint(axis),
    z: right.z * midpoint(right) + up.z * midpoint(up) + axis.z * midpoint(axis),
  };

  const relative = () =>
    usable.map((p) => ({ x: p.x - target.x, y: p.y - target.y, z: p.z - target.z, radius: p.radius }));
  let distance = framingDistance({ points: relative(), direction, fov, aspect, margin });
  if (distance === null) return null;

  for (let pass = 0; pass < CENTRING_PASSES; pass += 1) {
    // Both axes are perpendicular to the view, so neither shift changes any
    // depth and the two solve independently for the distance we currently have.
    // The frustum's tan factors scale max and min alike, so they do not move
    // the root and are left out.
    const lateral = [];
    const vertical = [];
    const depths = [];
    for (const point of usable) {
      const v = { x: point.x - target.x, y: point.y - target.y, z: point.z - target.z };
      const depth = distance - dot(v, axis);
      if (depth <= 0) continue;
      // Both edges of what is drawn, not the centre between them. Padding is
      // applied at each point's own depth, so a near star's glow covers more of
      // the frame than a far one's -- centring the centres would leave the sky
      // as drawn slightly lopsided, which is the same mistake one level down.
      const radius = Number.isFinite(point.radius) ? Math.max(0, point.radius) : 0;
      const sideways = dot(v, right);
      const upward = dot(v, up);
      lateral.push(sideways - radius, sideways + radius);
      vertical.push(upward - radius, upward + radius);
      depths.push(depth, depth);
    }
    if (!depths.length) break;
    const shiftRight = centringShift(lateral, depths);
    const shiftUp = centringShift(vertical, depths);
    target = {
      x: target.x + right.x * shiftRight + up.x * shiftUp,
      y: target.y + right.y * shiftRight + up.y * shiftUp,
      z: target.z + right.z * shiftRight + up.z * shiftUp,
    };
    const next = framingDistance({ points: relative(), direction, fov, aspect, margin });
    if (next === null) break;
    distance = next;
  }

  return { target, distance };
}
