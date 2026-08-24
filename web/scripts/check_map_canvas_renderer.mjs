import assert from "node:assert/strict";

import {
  architectureKeyboardTarget,
  fitBoxLabel,
  hitArchitectureCanvas,
  hitWorkflowCanvas,
  prepareArchitectureCanvas,
  prepareWorkflowCanvas,
  visibleArchitectureCanvas,
  visibleWorkflowCanvas,
  workflowKeyboardTarget,
  workflowRowMeta,
} from "../src/mapCanvasRenderer.js";

const architecture = {
  boxes: Array.from({ length: 5_000 }, (_, index) => ({
    id: `module_${String(index).padStart(5, "0")}`,
    label: `module_${String(index).padStart(5, "0")}`,
    short_label: `module_${String(index).padStart(5, "0")}.py`,
    language: "python",
    x: 24,
    y: index * 120,
    width: 160,
    height: 56,
    loc: 4,
    node_count: 2,
    understood: false,
    home: index === 0,
    reachable: index < 4_988,
    partial: false,
  })),
  edges: Array.from({ length: 4_999 }, (_, index) => ({
    src: `module_${String(index).padStart(5, "0")}`,
    dst: `module_${String(index + 1).padStart(5, "0")}`,
    certain: true,
    weight: 1,
    cycle: false,
    points: [
      [104, index * 120 + 56],
      [104, (index + 1) * 120],
    ],
  })),
};

const scene = prepareArchitectureCanvas(architecture);
assert.equal(scene.boxes.length, 5_000, "the canvas scene retains every module");
assert.equal(scene.edges.length, 4_999, "the canvas scene retains every import route");

const viewport = {
  width: 960,
  height: 640,
  scrollLeft: 0,
  scrollTop: 0,
  offsetX: 0,
  scale: 1,
};
const firstFrame = visibleArchitectureCanvas(scene, viewport);
assert.ok(
  firstFrame.boxes.length < 10,
  `viewport delivery draws a bounded slice, got ${firstFrame.boxes.length}`,
);
assert.equal(
  scene.boxes.length,
  5_000,
  "culling changes delivery only; it cannot remove parser-owned modules",
);

assert.equal(
  architectureKeyboardTarget(scene, scene.boxes[0].id, "End")?.id,
  "module_04999",
  "End reaches the final module without 4,999 Tab presses",
);
assert.equal(
  architectureKeyboardTarget(scene, "module_02499", "ArrowDown")?.id,
  "module_02500",
  "arrow navigation follows backend row order",
);
assert.equal(
  hitArchitectureCanvas(scene, { x: 56, y: 32 })?.id,
  "module_00000",
  "pointer hit-testing uses the backend box geometry plus the declared view padding",
);
assert.equal(
  hitArchitectureCanvas(scene, { x: 400, y: 32 }),
  null,
  "empty drawing space remains available to drag-to-pan",
);

assert.equal(
  scene.boxes.filter((box) => !box.reachable).length,
  12,
  "more than eight modules without a Home route remain in the complete scene",
);

assert.equal(
  fitBoxLabel("server/runtime.py", 160),
  "server/runtime.py",
  "a path tail that fits stays whole",
);
assert.match(
  fitBoxLabel("a-very-long-module-name-that-cannot-fit.py", 160),
  /…$/,
  "a shortened identifier remains visibly shortened",
);

const workflow = {
  nodes: [
    {
      id: "app",
      label: "app",
      parent: null,
      relation: "root",
      certain: true,
      cut: null,
      order: 0,
      x: 0,
      y: 0,
      region: "app",
      file: "app.py",
      lineno: 1,
      understood: false,
      partial: false,
    },
    {
      id: "app.main",
      label: "main",
      parent: "app",
      relation: "defines",
      certain: true,
      cut: null,
      order: 1,
      x: 28,
      y: 34,
      region: "app",
      file: "app.py",
      lineno: 3,
      understood: true,
      partial: false,
    },
    {
      id: "app.helper",
      label: "helper",
      parent: "app.main",
      relation: "calls",
      certain: false,
      cut: "repeat",
      order: 2,
      x: 56,
      y: 68,
      region: "app",
      file: "app.py",
      lineno: 8,
      understood: false,
      partial: true,
    },
  ],
};
const workflowScene = prepareWorkflowCanvas(workflow);
assert.equal(workflowScene.edges.length, 2, "the renderer indexes parents in one pass");
assert.equal(
  workflowKeyboardTarget(workflowScene, 1, "ArrowRight")?.order,
  2,
  "Right enters the first child",
);
assert.equal(
  workflowKeyboardTarget(workflowScene, 2, "ArrowLeft")?.order,
  1,
  "Left returns to the nearest earlier parent occurrence",
);
assert.equal(
  workflowKeyboardTarget(workflowScene, 0, "End")?.order,
  2,
  "End reaches the final workflow row",
);
assert.equal(
  hitWorkflowCanvas(workflowScene, { x: 80, y: 90 })?.order,
  2,
  "workflow pointer hit-testing uses backend row coordinates",
);
assert.equal(
  hitWorkflowCanvas(workflowScene, { x: 900, y: 90 }),
  null,
  "blank space to the right of a workflow label remains available to drag-to-pan",
);
assert.match(
  workflowRowMeta(workflow.nodes[2], "easy"),
  /possible call — shown above — could not be read/,
  "uncertainty, repeat cuts, and partial source remain explicit",
);
assert.equal(
  visibleWorkflowCanvas(workflowScene, viewport).rows.length,
  3,
  "small workflow views remain complete",
);

const sparseWorkflow = {
  nodes: [
    { ...workflow.nodes[0], order: 100, y: 3_400 },
    { ...workflow.nodes[1], order: 102, y: 3_468 },
  ],
};
const sparseScene = prepareWorkflowCanvas(sparseWorkflow);
const sparseViewport = {
  ...viewport,
  height: 120,
  scrollTop: 3_380,
};
assert.equal(
  visibleWorkflowCanvas(sparseScene, sparseViewport).rows.length,
  2,
  "focused workflow culling follows emitted y coordinates rather than sparse order values",
);
assert.equal(
  workflowKeyboardTarget(sparseScene, 100, "ArrowDown")?.order,
  102,
  "focused workflow keyboard navigation follows scene position across sparse orders",
);

console.log("canvas Map renderer contracts passed");
