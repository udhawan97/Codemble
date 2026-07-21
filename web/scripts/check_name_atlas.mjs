import assert from "node:assert/strict";
import * as THREE from "three";

import { configureNamePlate, createNameAtlas } from "../src/nameAtlas.js";

const nodes = Array.from({ length: 10 }, (_, index) => ({
  id: `node-${index}`,
  label: `module-${index}.py`,
  home: index === 0,
  understood: index === 1,
  centrality: 10 - index,
}));
const scene = new THREE.Scene();
const sprites = new Map();
for (const node of nodes) {
  const star = new THREE.Group();
  const plate = configureNamePlate(new THREE.Sprite(), {
    radius: 1,
    aspect: 4,
  });
  plate.userData.nodeId = node.id;
  star.add(plate);
  scene.add(star);
  sprites.set(node.id, plate);
}
scene.updateMatrixWorld(true);

assert.equal(sprites.get("node-0").scale.y, 0.034);
assert.equal(sprites.get("node-0").userData.codembleLabel, true);
assert.equal(sprites.get("node-0").visible, false);

const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
camera.position.set(0, 0, 100);
camera.lookAt(0, 0, 0);
camera.updateProjectionMatrix();
camera.updateMatrixWorld(true);
const atlas = createNameAtlas(nodes);
const view = {
  scene,
  camera,
  width: 1000,
  height: 1000,
  distance: 100,
  distanceBounds: { min: 10, max: 100 },
};

const first = atlas.place(view);
assert.equal(first.budget, 14, "the far camera clamp uses the conservative budget");
assert(first.shown <= 5, "ten coincident stars can occupy only the finite slot set");
assert.equal(
  sprites.get("node-0").visible,
  true,
  "Home wins the first available name slot",
);

const repeated = atlas.place(view);
assert.deepEqual(
  repeated.visibleIds,
  first.visibleIds,
  "the same graph and camera produce the same atlas",
);

const hovered = atlas.place({ ...view, hoverNodeId: "node-9" });
assert(
  hovered.visibleIds.includes("node-9"),
  "the pointer subject outranks every graph-derived name",
);

const near = atlas.place({ ...view, distance: 10 });
assert.equal(near.budget, 44, "the near camera clamp exposes the larger budget");

atlas.hide(scene);
assert([...sprites.values()].every((sprite) => sprite.visible === false));

console.log("name-atlas contracts passed");
