/**
 * What the camera looks at, and how far back it stands to see it.
 *
 * `cameraFraming.js` answers "how far to hold these points on screen". This
 * module answers the questions around it -- *which* points, at *what* aspect,
 * and inside what clamps -- which is where all three shipped framing faults
 * actually landed:
 *
 *   0c6caf4  a fixed distance the layout outgrew
 *   c64a88a  a system fitted to its planets, cropping the rings they sit on
 *   5bdb110  the whole disc instead of the charted sky, and a stale aspect
 *
 * Those decisions lived inside GalaxyCanvas.jsx, a React component with a live
 * WebGL renderer, so nothing could reach them: `c64a88a` shipped with no test
 * change at all because there was nowhere to put one. None of this needs WebGL
 * or React. It is arithmetic over graph coordinates.
 *
 * Nothing here reads a renderer, a camera or the DOM. There is no state to go
 * stale, and "same code -> same sky" extends to "same window" because the
 * result depends on nothing but the arguments.
 */

import { cameraPositionAt, frameAround, framingDistance } from "./cameraFraming.js";
import { LEVELS, drawnRadius, isCharted } from "./graphData.js";

/** How long the camera takes to move between levels, in milliseconds. */
export const CAMERA_DURATION = 420;

// Bounded orbit, per the 2026-07-21 Decision Log entry. Free flight stays a
// Non-Goal: panning is off, so the camera can only ever swing around the
// current subject and never translate away from it. These are floors and
// ceilings, not the range itself -- a fitted distance may widen either, so the
// distance a level opens at always sits inside the range it is held to.
const CAMERA_BOUNDS = {
  GALAXY: { min: 120, max: 640 },
  SYSTEM: { min: 55, max: 320 },
  STUDY: { min: 22, max: 170 },
};

// The tilt each level is viewed from. Only the direction is art direction; the
// distance along it is measured from the nodes, because a layout that grows
// past a hardcoded distance puts its own far side behind the camera -- and a
// node behind the camera is not cropped, it is gone. Their lengths remain the
// fallback for a level with nothing to measure.
const CAMERA_VIEW = {
  GALAXY: { x: 0, y: 105, z: 310 },
  SYSTEM: { x: 0, y: 52, z: 150 },
};

// How much further than the whole project's fitted distance the learner may
// pull back. Enough for some space around it, not enough to lose it.
const ZOOM_OUT_HEADROOM = 1.15;

// Where the camera stands relative to one structure at study level: off to one
// side and slightly above, so the planet is the subject and its orbit
// neighbours stay in frame behind it.
const STUDY_OFFSET = { x: 20, y: 15, z: 42 };

/**
 * The aspect of the element actually being drawn into.
 *
 * The one place this number is computed. It used to come from two: an observer
 * entry on resize, and `renderer.width() / renderer.height()` everywhere else.
 * The library batches width/height and applies them on its next tick, so the
 * second source still carried the previous viewport at the moment a resize was
 * handled -- the camera re-framed for the window the learner had just left.
 *
 * An element that has not been measured yet has no aspect, and says so, rather
 * than returning `Infinity` or `NaN` for a caller to trip over.
 *
 * @returns {number|null}
 */
export function viewportAspect(size) {
  if (!size) return null;
  const { width, height } = size;
  if (!Number.isFinite(width) || !Number.isFinite(height)) return null;
  if (width <= 0 || height <= 0) return null;
  return width / height;
}

/**
 * Layout coordinates are fixed by the graph layer, so fx/fy/fz are the truth.
 *
 * Each carries the radius of what is DRAWN there. A coordinate is a star's
 * centre and a star reaches well past it, so fitting the coordinates alone fits
 * the centres and crops the stars -- harmless while the camera stood further
 * back than it needed to, and immediately visible once the aim was corrected
 * and the standoff shrank with it.
 */
const layoutPoints = (nodes) =>
  nodes.map((node) => ({
    x: node.fx ?? node.x ?? 0,
    y: node.fy ?? node.y ?? 0,
    z: node.fz ?? node.z ?? 0,
    radius: drawnRadius(node),
  }));

/**
 * The four cardinal points of each orbit guide.
 *
 * A guide is a circle through the planets on its layer, so its widest point on
 * screen usually falls *between* them -- fitting the planets alone crops the
 * ring they sit on.
 */
const orbitRingPoints = (plan) => {
  const points = [];
  for (const layer of plan ?? []) {
    for (const radius of layer.radii ?? []) {
      points.push(
        { x: radius, y: 0, z: 0 },
        { x: -radius, y: 0, z: 0 },
        { x: 0, y: 0, z: radius },
        { x: 0, y: 0, z: -radius },
      );
    }
  }
  return points;
};

/**
 * Where the camera sits for a level, and the clamps that then hold it there.
 *
 * @param {object} options
 * @param {string} options.level      One of `LEVELS`.
 * @param {Array}  options.nodes      The level's nodes, at their graph coordinates.
 * @param {Array}  [options.orbitPlan] Layers whose guide circles must also fit.
 * @param {number} [options.fov]      Vertical field of view, in degrees.
 * @param {number} [options.aspect]   From `viewportAspect`, never from a camera.
 * @returns {{position: {x,y,z}, target: {x,y,z}, distance: number, min: number, max: number, fitted: boolean}}
 *   `distance` is the magnitude of `position - target`, returned rather than
 *   left for the caller to re-derive with `Math.hypot` -- the same number twice
 *   is the habit this module exists to break, and the two disagree in the last
 *   bit. `target` is what the camera looks at and what the orbit then swings
 *   around; it is measured, not assumed to be the origin.
 *   `fitted` is false when nothing could be measured -- no aspect, no fov, or
 *   no nodes -- and the level opens at its art-directed default instead. The
 *   caller is told which it got rather than having to guess.
 */
export function frameLevel({ level, nodes, orbitPlan, fov, aspect, viewport, chrome }) {
  const view = CAMERA_VIEW[level] ?? CAMERA_VIEW.GALAXY;
  const bounds = CAMERA_BOUNDS[level] ?? CAMERA_BOUNDS.GALAXY;
  const rings = level === LEVELS.GALAXY ? [] : orbitRingPoints(orbitPlan);
  const subjects = Array.isArray(nodes) ? nodes : [];
  const pointsFor = (subset) => [...layoutPoints(subset), ...rings];
  const aim = (subset) =>
    frameAround({ points: pointsFor(subset), direction: view, fov, aspect });

  // Open on the sky the learner is meant to read. Fitting all 113 systems
  // instead framed the whole disc and left the charted core a thumbnail --
  // technically nothing off screen, nothing legible either. Progressive reveal
  // already decides what is worth reading, so the camera follows it. Show all
  // charts every region, so that case fits the lot with no special case.
  const charted = subjects.filter(isCharted);
  const measured = (charted.length ? aim(charted) : null) ?? aim(subjects);
  const solved = {
    target: measured?.target ?? { x: 0, y: 0, z: 0 },
    distance: measured?.distance ?? Math.hypot(view.x, view.y, view.z),
  };
  // Then move the sky out from under whatever is sitting on the canvas. A no-op
  // with no chrome, so a level that reserves nothing frames exactly as before.
  const { target, distance } = measured
    ? aimIntoClearRegion({
        ...solved,
        points: pointsFor(charted.length ? charted : subjects),
        direction: view,
        fov,
        viewport,
        chrome,
      })
    : solved;
  const offset = cameraPositionAt(view, distance) ?? view;
  // The ceiling is measured from the same point the camera is aimed at, or it
  // would be a reach computed from somewhere the camera never sits.
  const whole = framingDistance({
    points: pointsFor(subjects).map((p) => ({
      x: p.x - target.x,
      y: p.y - target.y,
      z: p.z - target.z,
      radius: p.radius,
    })),
    direction: view,
    fov,
    aspect,
  });
  return {
    position: { x: target.x + offset.x, y: target.y + offset.y, z: target.z + offset.z },
    target,
    distance,
    min: Math.min(bounds.min, distance),
    // Far enough back to reach the uncharted rim. Progressive reveal draws
    // those regions faint, never removes them, so the camera must be able to
    // get to them even though it does not open there.
    max: Math.max(bounds.max, (whole ?? distance) * ZOOM_OUT_HEADROOM),
    fitted: measured !== null,
  };
}

/**
 * The largest rectangle of the canvas that no interactive chrome covers.
 *
 * Greedy, and deliberately so: the chrome here is one or two small controls, and
 * cutting the band that costs the least area each time is exact for that. It
 * returns the whole canvas when nothing overlaps, which is what makes the whole
 * feature a no-op on a canvas with no controls over it.
 *
 * @param {{width: number, height: number}} viewport In canvas CSS pixels.
 * @param {Array<{left,right,top,bottom}>} chrome Rects in the same pixels.
 */
export function clearRegion(viewport, chrome) {
  const { width, height } = viewport ?? {};
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return null;
  }
  let rect = { left: 0, right: width, top: 0, bottom: height };
  const boxes = (chrome ?? []).filter(
    (box) =>
      box &&
      Number.isFinite(box.left) &&
      Number.isFinite(box.right) &&
      Number.isFinite(box.top) &&
      Number.isFinite(box.bottom),
  );
  for (let pass = 0; pass < boxes.length; pass += 1) {
    const hit = boxes.find(
      (box) =>
        box.left < rect.right &&
        box.right > rect.left &&
        box.top < rect.bottom &&
        box.bottom > rect.top,
    );
    if (!hit) break;
    const options = [
      { ...rect, right: Math.max(rect.left, hit.left) },
      { ...rect, left: Math.min(rect.right, hit.right) },
      { ...rect, bottom: Math.max(rect.top, hit.top) },
      { ...rect, top: Math.min(rect.bottom, hit.bottom) },
    ];
    rect = options.reduce((best, option) => {
      const area = (o) => Math.max(0, o.right - o.left) * Math.max(0, o.bottom - o.top);
      return area(option) > area(best) ? option : best;
    });
  }
  const clear = {
    left: rect.left,
    right: rect.right,
    top: rect.top,
    bottom: rect.bottom,
    width: Math.max(0, rect.right - rect.left),
    height: Math.max(0, rect.bottom - rect.top),
  };
  return clear.width > 0 && clear.height > 0 ? clear : null;
}

/**
 * Re-aim a solved frame so the sky lands where no control is sitting on it.
 *
 * The defect this exists for: at System level the orientation panel floats over
 * the canvas, and a planet the camera happened to project underneath its button
 * could not be clicked -- the click reached the button and opened the quiz
 * instead. `nameAtlas` already refuses to print a plate under that chrome; a
 * body cannot move, because the layout is parser-owned, so the camera moves.
 *
 * Bounded on purpose, and in this order:
 *   - offset only, when the sky already fits the clear region. The common case,
 *     and it costs no standoff at all.
 *   - push back only as far as needed to make it fit, when it does not.
 * With no chrome the clear region is the whole canvas, the scale is 1 and the
 * offset is 0, so the result is bit-identical to the frame it was handed. That
 * is what keeps every existing framing contract intact.
 *
 * @returns {{target: {x,y,z}, distance: number}} Never null; falls back to what
 *   it was given, because a camera that declines to move beats one sent nowhere.
 */
export function aimIntoClearRegion({
  target,
  distance,
  points,
  direction,
  fov,
  viewport,
  chrome,
  margin = 0.1,
}) {
  const fallback = { target, distance };
  const axis = unitVector(direction);
  const clear = clearRegion(viewport, chrome);
  if (!axis || !clear || !Number.isFinite(distance) || !Number.isFinite(fov)) return fallback;
  if (!Array.isArray(points) || !points.length) return fallback;
  const { width, height } = viewport;
  if (clear.width >= width && clear.height >= height) return fallback;

  const seed = Math.abs(axis.y) > 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const right = unitVector(crossProduct(seed, axis));
  if (!right) return fallback;
  const up = crossProduct(axis, right);
  const halfFov = (fov * Math.PI) / 360;

  // Where the sky actually lands, in canvas pixels, at the distance we have.
  // Measured per point at its own depth and padded by what is drawn there, the
  // same way the fit itself reserves space -- a near star's glow covers more of
  // the frame than a far one's.
  const extent = (dist) => {
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const point of points) {
      const v = { x: point.x - target.x, y: point.y - target.y, z: point.z - target.z };
      const depth = dist - dotProduct(v, axis);
      if (depth <= 0) continue;
      const perPixel = (2 * depth * Math.tan(halfFov)) / height;
      if (!(perPixel > 0)) continue;
      const radius = Number.isFinite(point.radius) ? Math.max(0, point.radius) : 0;
      const x = dotProduct(v, right) / perPixel;
      const y = dotProduct(v, up) / perPixel;
      const pad = radius / perPixel;
      minX = Math.min(minX, x - pad);
      maxX = Math.max(maxX, x + pad);
      minY = Math.min(minY, y - pad);
      maxY = Math.max(maxY, y + pad);
    }
    if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;
    return { width: maxX - minX, height: maxY - minY, x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
  };

  const drawn = extent(distance);
  if (!drawn) return fallback;
  const room = 1 - Math.min(0.9, Math.max(0, margin));
  const needed = Math.max(
    1,
    drawn.width / Math.max(1, clear.width * room),
    drawn.height / Math.max(1, clear.height * room),
  );
  const scaled = distance * needed;
  const placed = needed === 1 ? drawn : extent(scaled);
  if (!placed) return fallback;

  // The target is whatever shows at the canvas centre, so to put the sky's
  // centre at the clear region's centre the target moves the other way.
  const perPixel = (2 * scaled * Math.tan(halfFov)) / height;
  const wantX = clear.left + clear.width / 2 - width / 2;
  const wantY = clear.top + clear.height / 2 - height / 2;
  const shiftRight = (placed.x - wantX) * perPixel;
  const shiftUp = (placed.y + wantY) * perPixel;
  return {
    distance: scaled,
    target: {
      x: target.x + right.x * shiftRight + up.x * shiftUp,
      y: target.y + right.y * shiftRight + up.y * shiftUp,
      z: target.z + right.z * shiftRight + up.z * shiftUp,
    },
  };
}

function unitVector(vector) {
  if (!vector) return null;
  const { x, y, z } = vector;
  if (![x, y, z].every(Number.isFinite)) return null;
  const length = Math.hypot(x, y, z);
  return length > 0 ? { x: x / length, y: y / length, z: z / length } : null;
}

function crossProduct(a, b) {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  };
}

function dotProduct(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/**
 * A level's art-directed distance floor and ceiling, before any fit widens them.
 *
 * Only for callers that have no live controls to read. Anything that can reach
 * `controls.minDistance`/`maxDistance` should: those carry the *fitted* range,
 * and this carries the defaults the fit is allowed to widen. Reading these when
 * the fitted ones exist is how the name atlas came to budget labels against a
 * range the camera was not actually held to.
 */
export function cameraBoundsFor(level) {
  return CAMERA_BOUNDS[level] ?? CAMERA_BOUNDS.GALAXY;
}

/**
 * Where the camera stands to study one structure, and what it looks at.
 *
 * Returns `null` for a structure the layout never placed: a camera sent to
 * `undefined + 20` is a worse answer than not moving.
 *
 * @returns {{position: {x,y,z}, target: {x,y,z}}|null}
 */
export function frameStudy(node) {
  if (!node) return null;
  const { system_x: x, system_y: y, system_z: z } = node;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;
  return {
    position: { x: x + STUDY_OFFSET.x, y: y + STUDY_OFFSET.y, z: z + STUDY_OFFSET.z },
    target: { x, y, z },
  };
}
