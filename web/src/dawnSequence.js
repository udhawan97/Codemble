import * as THREE from "three";

import { prefersReducedMotion } from "./galaxyEffects.js";

/**
 * The ink-to-light dawn: the one self-celebrating moment in the app.
 *
 * A learner has just proved they understand a module, and this is the only
 * place the interface is allowed to be loud about it. It runs in four phases
 * rather than one wash, because the point is not "something flashed" but a
 * readable sentence: light travels along a route the parser proved, arrives,
 * and the world it reaches stays lit.
 *
 *   ignite  0.00-0.22  a mote appears on each proven route into the region
 *   travel  0.22-0.52  the motes run along their routes toward it
 *   flare   0.52-0.74  they arrive; the system's own sprites flare amber
 *   settle  0.74-1.00  the flare decays into the permanent lit state
 *
 * Two rules from the design are load-bearing rather than decorative:
 *
 * ONLY CERTAIN ROUTES CARRY LIGHT. A "possible" route is the parser admitting
 * it could not prove the relationship, and a mote running along one would
 * animate a claim the graph never made -- exactly the kind of wrong a learner
 * cannot detect. Unproven routes stay dark and still through the whole moment.
 *
 * THE FLARE COMES AFTER THE TRAVEL. Amber means understood, so it may never
 * appear in anticipation of a result. By the time this runs the region is
 * already lit in the graph, and the choreography only reveals in order what is
 * already true.
 *
 * Reduced motion gets the finished state instantly -- not a faster dawn, no
 * dawn at all. That is safe because the lit colour is already committed to the
 * graph, so the settled frame is what is on screen either way.
 */

const DAWN_DURATION = 1600;
const IGNITE_END = 0.22;
const TRAVEL_END = 0.52;
const FLARE_END = 0.74;
// A dawn on a hub module could otherwise fire a mote down thirty routes at
// once, which reads as an explosion rather than an arrival.
const MAX_SPARKS = 3;
const SPARK_SIZE = 7;

/** Phase weights for one progress value, each 0..1 inside its own phase. */
export function dawnPhases(progress) {
  const clamped = Math.min(1, Math.max(0, progress));
  const span = (from, to) =>
    Math.min(1, Math.max(0, (clamped - from) / (to - from)));
  return Object.freeze({
    ignite: span(0, IGNITE_END),
    travel: span(IGNITE_END, TRAVEL_END),
    flare: span(TRAVEL_END, FLARE_END),
    settle: span(FLARE_END, 1),
  });
}

/**
 * The routes a dawn may run light along, nearest-to-Home first.
 *
 * Only proven routes incident on the region qualify. Ordering by the
 * neighbour's own hop distance from Home means the light tends to arrive from
 * the direction the learner came from, which is the reading the choreography
 * is trying to give: understanding spreading outward from what they already
 * know.
 */
export function dawnRoutes(regionId, routes, hopsById = new Map()) {
  const incident = [];
  for (const route of routes ?? []) {
    if (!route?.certain) continue;
    const from =
      route.dst === regionId ? route.src : route.src === regionId ? route.dst : null;
    if (from === null || from === regionId) continue;
    incident.push(from);
  }
  const unique = [...new Set(incident)];
  unique.sort((left, right) => {
    const leftHops = hopsById.get(left);
    const rightHops = hopsById.get(right);
    const leftKey = typeof leftHops === "number" ? leftHops : Number.MAX_SAFE_INTEGER;
    const rightKey = typeof rightHops === "number" ? rightHops : Number.MAX_SAFE_INTEGER;
    return leftKey - rightKey || left.localeCompare(right);
  });
  return unique.slice(0, MAX_SPARKS);
}

/**
 * Play the dawn for one region. Returns a cancel function that restores every
 * value it touched, so an interrupted dawn can never strand the sky mid-flare.
 */
export function runDawnSequence({
  scene,
  regionId,
  palette,
  dressing,
  routes = [],
  hopsById = new Map(),
}) {
  if (prefersReducedMotion()) return () => {};
  const target = scene.getObjectByName(`codemble-system-${regionId}`);
  if (!target) return () => {};

  const sprites = [];
  target.traverse((child) => {
    // The full scale VECTOR, never scale.x alone: a name plate is non-uniform
    // (x = aspect * y), and a scalar snapshot restored through setScalar
    // squashed the lit system's plate square and left it that way until the
    // next level change rebuilt the marker.
    if (child.isSprite) sprites.push([child, child.material.opacity, child.scale.clone()]);
  });
  const originals = sprites.map(([sprite]) => sprite.material.color.clone());
  const amber = new THREE.Color(palette.star);

  // Motes, one per proven route, each with its own start point in world space.
  const destination = new THREE.Vector3();
  target.getWorldPosition(destination);
  const motes = [];
  if (dressing?.spark) {
    for (const neighbourId of dawnRoutes(regionId, routes, hopsById)) {
      const neighbour = scene.getObjectByName(`codemble-system-${neighbourId}`);
      if (!neighbour) continue;
      const origin = new THREE.Vector3();
      neighbour.getWorldPosition(origin);
      const sprite = dressing.spark();
      sprite.scale.setScalar(SPARK_SIZE);
      sprite.position.copy(origin);
      scene.add(sprite);
      motes.push({ sprite, origin });
    }
  }

  const restore = () => {
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]);
      sprite.material.opacity = baseOpacity;
      sprite.scale.copy(baseScale);
    });
    for (const { sprite } of motes) {
      scene.remove(sprite);
      // The material is dressing-owned and shared; removing the sprite is the
      // whole cleanup, and disposing here would blank every future dawn.
      sprite.material.opacity = 0;
    }
    motes.length = 0;
  };

  let frame = 0;
  const startedAt = performance.now();
  const step = () => {
    const progress = Math.min(1, (performance.now() - startedAt) / DAWN_DURATION);
    const phase = dawnPhases(progress);

    // Motes: fade in where they start, ease along the route, vanish on arrival.
    const travelEase = 1 - (1 - phase.travel) ** 3;
    for (const { sprite, origin } of motes) {
      sprite.position.lerpVectors(origin, destination, travelEase);
      sprite.material.opacity =
        phase.flare > 0 ? 0 : Math.min(1, phase.ignite) * 0.9;
    }

    // The system flares only once the light has arrived, then settles.
    const wash = Math.sin(Math.min(1, phase.flare) * Math.PI * 0.5) * (1 - phase.settle);
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]).lerp(amber, wash * 0.85);
      sprite.material.opacity = baseOpacity + wash * 0.5;
      sprite.scale.copy(baseScale).multiplyScalar(1 + wash * 0.45);
    });

    if (progress < 1) {
      frame = requestAnimationFrame(step);
      return;
    }
    restore();
  };
  frame = requestAnimationFrame(step);
  return () => {
    cancelAnimationFrame(frame);
    restore();
  };
}
