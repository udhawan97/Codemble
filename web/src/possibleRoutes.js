import * as THREE from "three";

/**
 * Dashed 3D geometry for relationships the parser could not prove.
 *
 * The Correctness Contract requires an approximate edge to stay visibly
 * uncertain, and until now the 3D layers carried that claim in **colour
 * alone** -- `--cm-route-possible` instead of `--cm-route`. The 2026-07-20
 * acceptance note recorded the reason as "no line-dash support there", and for
 * the default link that is true: `three-forcegraph` builds a *cylinder mesh*
 * whenever `linkWidth` is non-zero (`useCylinder = !!widthAccessor(link)`), and
 * a mesh cannot be dashed by `LineDashedMaterial`.
 *
 * Colour alone is the weakest possible encoding for the one thing a learner
 * must not misread: it disappears under colour-blindness, on a dim panel, and
 * in any greyscale screenshot of the galaxy. The 2D map has always dashed, so
 * the two layers also disagreed about how loudly they admitted doubt.
 *
 * A possible route therefore supplies its own `THREE.Line` through
 * `linkThreeObject`, which the library accepts in place of its default object.
 * Dashes are measured in world units along the line, so `computeLineDistances`
 * has to run after every geometry write -- the library never calls it.
 */

// Matches `curveResolution` inside three-forcegraph's own link positioning, so
// a dashed route traces exactly the arc a solid one would.
export const ROUTE_CURVE_RESOLUTION = 30;
// Short enough to read as broken at galaxy zoom, long enough not to alias into
// a dotted blur at the far clamp.
export const DASH_SIZE = 2.4;
export const GAP_SIZE = 1.8;
// Slightly stronger than the solid link's 0.5: a dash cycle is 57% ink, so
// matching opacity would make the *unproven* claim the fainter mark -- the
// wrong way round, and the exact inversion the 2026-07-22 route-ink decision
// was written to prevent.
export const ROUTE_OPACITY = 0.62;

/**
 * A dashed line for one unproven relationship.
 *
 * The material is per-link rather than shared by colour because hover and
 * selection repaint individual routes; `link` rides on the object so that
 * repaint can find its own line again without a second index.
 */
export function createPossibleRoute(link, color) {
  const material = new THREE.LineDashedMaterial({
    color: new THREE.Color(color),
    dashSize: DASH_SIZE,
    gapSize: GAP_SIZE,
    transparent: true,
    opacity: ROUTE_OPACITY,
    depthWrite: false,
  });
  const line = new THREE.Line(new THREE.BufferGeometry(), material);
  // three-forcegraph owns this object once it is returned, and its deallocator
  // disposes geometry and material -- which is correct here precisely because
  // nothing else shares them (unlike the halo and nebula resources).
  line.userData.codembleRouteLink = link;
  line.renderOrder = -1;
  return line;
}

/**
 * Write a route's points and re-measure its dashes.
 *
 * Returns true so the caller can hand the value straight back to
 * `linkPositionUpdate`, whose contract is "truthy means I positioned this
 * myself, skip the default".
 */
export function updateRouteGeometry(line, curve, start, end) {
  const points = curve
    ? curve.getPoints(ROUTE_CURVE_RESOLUTION)
    : [
        new THREE.Vector3(start.x, start.y ?? 0, start.z ?? 0),
        new THREE.Vector3(end.x, end.y ?? 0, end.z ?? 0),
      ];
  // `setFromPoints` REUSES an existing position attribute and fills only as far
  // as its current count, so a line that was once straight keeps its 2-vertex
  // buffer and silently redraws a 31-point curve as a stub. Resize first --
  // three-forcegraph guards its own link geometry the same way.
  const position = line.geometry.getAttribute("position");
  if (!position || position.count !== points.length) {
    line.geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(points.length * 3), 3),
    );
  }
  line.geometry.setFromPoints(points);
  line.geometry.computeBoundingSphere();
  // The whole point: dash phase is arc length, and without this every vertex
  // reports distance 0, which draws a solid line and silently restores the
  // colour-only encoding this module exists to remove.
  line.computeLineDistances();
  return true;
}

/**
 * Repaint every dashed route from the current highlight state.
 *
 * A custom object owns its material, so `linkColor` no longer reaches it the
 * way it reaches a library-built link. Without this, hovering a system would
 * light its proven routes and leave its unproven ones behind.
 */
export function refreshPossibleRoutes(scene, colorFor) {
  scene.traverse((object) => {
    const link = object.userData?.codembleRouteLink;
    if (!link || !object.material) return;
    object.material.color.set(colorFor(link));
  });
}
