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

// A plate is far wider than the star it names, so a star comfortably on screen
// can still put its name half off the canvas -- which reads as a rendering
// fault, not as a label. Stars sit at the origin here, so on a canvas narrower
// than one plate no slot can hold a name and the atlas must show none.
const plateWidth = 0.14 * view.height;
const tooNarrow = atlas.place({ ...view, width: Math.floor(plateWidth * 0.8) });
assert.equal(
  tooNarrow.shown,
  0,
  "a plate that cannot fit inside the canvas is not drawn overhanging it",
);
assert.equal(
  atlas.place(view).shown,
  first.shown,
  "restoring the canvas restores the names",
);

// The canvas is not all sky. The orientation line is drawn over its top-left
// corner and the keyboard readout over its bottom-left, both as
// `pointer-events: none` DOM the scene knows nothing about -- so a plate was
// printed straight through them. On this repository that put
// `tests/test_typescript_tree_sitter.py` across "24 charted · 2 could not be
// read · all under tests/", the line that states what Codemble could NOT parse.
// Covering that is worse than showing no name: the count exists so a learner is
// not misled about coverage.
const chromeless = atlas.place(view);
assert.ok(chromeless.shown > 0, "the fixture shows names with no chrome declared");

// A band across the whole canvas leaves no slot anywhere, the same outcome as a
// canvas too narrow to hold a plate: no name rather than a name over the text.
const buried = atlas.place({
  ...view,
  chrome: [{ left: 0, right: view.width, top: 0, bottom: view.height }],
});
assert.equal(buried.shown, 0, "no plate is drawn over chrome");

// ...and it is a rectangle test, not a top-band test: chrome in one corner must
// not cost the sky the rest of the row.
const corner = atlas.place({
  ...view,
  chrome: [{ left: 0, right: 120, top: 0, bottom: 24 }],
});
assert.equal(
  corner.shown,
  chromeless.shown,
  "chrome in a corner does not reserve the whole band",
);

// Absent or empty chrome is the same as none: a caller that draws nothing over
// its sky need not know this exists.
assert.equal(atlas.place({ ...view, chrome: [] }).shown, chromeless.shown);
assert.equal(atlas.place({ ...view, chrome: undefined }).shown, chromeless.shown);

atlas.hide(scene);
assert([...sprites.values()].every((sprite) => sprite.visible === false));

console.log("name-atlas contracts passed");
