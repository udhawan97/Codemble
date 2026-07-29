// A "possible call" must stay visibly uncertain without relying on colour.
// These assertions pin the two things that make that true in 3D: the route is
// drawn with a dashed material, and its dash phase is actually measured --
// `computeLineDistances` is what turns a LineDashedMaterial into visible gaps,
// and skipping it draws a solid line that looks exactly like a proven one.
import assert from "node:assert/strict";

import * as THREE from "three";

import {
  DASH_SIZE,
  GAP_SIZE,
  ROUTE_CURVE_RESOLUTION,
  ROUTE_OPACITY,
  createPossibleRoute,
  refreshPossibleRoutes,
  updateRouteGeometry,
} from "../src/possibleRoutes.js";

const link = { src: "a", dst: "b", certain: false, weight: 1 };
const line = createPossibleRoute(link, "rgb(139, 152, 182)");

assert.ok(line.isLine, "a possible route is a Line, never a cylinder mesh");
assert.equal(
  line.material.type,
  "LineDashedMaterial",
  "uncertainty needs a shape channel, not only a colour",
);
assert.ok(DASH_SIZE > 0 && GAP_SIZE > 0, "a zero gap would render solid");
assert.equal(line.material.opacity, ROUTE_OPACITY);
assert.equal(line.userData.codembleRouteLink, link, "the route can find its own link again");

// Straight route: two points, and real dash distances along it.
const straight = updateRouteGeometry(line, null, { x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 });
assert.equal(straight, true, "the caller must be told it positioned the line itself");
assert.equal(line.geometry.getAttribute("position").count, 2);
const distances = line.geometry.getAttribute("lineDistance");
assert.ok(distances, "without lineDistance the dash never renders");
assert.equal(distances.array[0], 0);
assert.ok(
  Math.abs(distances.array[1] - 10) < 1e-6,
  "dash phase is measured in world units along the route",
);
assert.ok(
  distances.array[1] > DASH_SIZE + GAP_SIZE,
  "a route must be long enough to show at least one full gap",
);

// Curved route: follows the library's own curve at its own resolution, so a
// dashed route traces exactly the arc a solid one would.
const curve = new THREE.QuadraticBezierCurve3(
  new THREE.Vector3(0, 0, 0),
  new THREE.Vector3(5, 6, 0),
  new THREE.Vector3(10, 0, 0),
);
updateRouteGeometry(line, curve, { x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 });
assert.equal(
  line.geometry.getAttribute("position").count,
  ROUTE_CURVE_RESOLUTION + 1,
  "a curved route is sampled at the library's own resolution",
);
const curved = line.geometry.getAttribute("lineDistance");
assert.ok(
  curved.array[curved.count - 1] > 10,
  "an arc is longer than its chord, so its dash phase must be too",
);
for (let index = 1; index < curved.count; index += 1) {
  assert.ok(
    curved.array[index] > curved.array[index - 1],
    "dash distance increases monotonically along the route",
  );
}

// Repainting: a custom object owns its material, so highlight has to reach it
// explicitly or hovering a system would light only its proven routes.
const scene = new THREE.Scene();
scene.add(line);
refreshPossibleRoutes(scene, () => "rgb(130, 171, 236)");
// Compared through getStyle, not the raw channels: three.js colour management
// stores linear-light values, so the raw r/g/b of an sRGB input never match the
// number that was set.
assert.equal(
  line.material.color.getStyle(),
  "rgb(130,171,236)",
  "a dashed route follows the highlight state like any other link",
);

// A stray object without a link must be left alone rather than crash the pass.
const bystander = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
bystander.material.color.setStyle("rgb(255, 255, 255)");
scene.add(bystander);
refreshPossibleRoutes(scene, () => "rgb(1, 2, 3)");
assert.equal(
  bystander.material.color.getStyle(),
  "rgb(255,255,255)",
  "only routes are repainted",
);

console.log("possible-route contracts passed");
