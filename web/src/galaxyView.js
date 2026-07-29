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
export function frameLevel({ level, nodes, orbitPlan, fov, aspect }) {
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
  const target = measured?.target ?? { x: 0, y: 0, z: 0 };
  const distance = measured?.distance ?? Math.hypot(view.x, view.y, view.z);
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
