import assert from "node:assert/strict";

import {
  LEVELS,
  buildConceptChart,
  languageFocusGraph,
  languageFocusMap,
  moduleIndex,
  projectLanguageOptions,
  revealedRegionIds,
} from "../src/graphData.js";
import { createLearnerProjection } from "../src/learnerProjection.js";

const graph = makeGraph();
const mapData = makeMap();
const studiedNodeIds = new Set(["python:app.py:run"]);
const state = {
  graph,
  mapData,
  languageFocus: "python",
  level: LEVELS.GALAXY,
  region: graph.regions[0],
  selectedNode: null,
  studiedNodeIds,
  entrypointDismissed: false,
  showAll: false,
  mode: "easy",
  layer: "map",
  hoverNodeId: null,
};
const projection = createLearnerProjection();
const first = projection.derive(state);
const expectedGraph = languageFocusGraph(graph, "python");

assert.deepEqual(first.focusedGraph, expectedGraph);
assert.deepEqual(first.focusedMapData, languageFocusMap(mapData, "python"));
assert.deepEqual(first.languageOptions, projectLanguageOptions(graph));
assert.deepEqual(first.chart, buildConceptChart(expectedGraph, studiedNodeIds));
assert.deepEqual(
  first.revealedRegionIds,
  revealedRegionIds(expectedGraph, { selectionId: "app.py" }),
);
assert.deepEqual(first.moduleIndex, moduleIndex(expectedGraph));
const hovered = projection.derive({ ...state, hoverNodeId: "python:app.py:run" });
assert.notEqual(hovered, first);
for (const field of [
  "focusedGraph",
  "focusedMapData",
  "languageOptions",
  "chart",
  "hint",
  "revealedRegionIds",
  "moduleIndex",
]) {
  assert.equal(
    hovered[field],
    first[field],
    `hover-only commits reuse the ${field} projection`,
  );
}

assert.deepEqual(
  first.hint,
  {
    regionId: "app.py",
    hops: 0,
    message: "Study app.py next",
    reason: "Home is not lit yet.",
    action: { type: "OPEN_REGION", regionId: "app.py" },
    actionLabel: "Open app.py",
  },
  "galaxy-level guidance opens the nearest unlit region",
);

const sameRegionOnMap = projection.derive({
  ...state,
  level: LEVELS.SYSTEM,
  layer: "map",
});
assert.deepEqual(
  sameRegionOnMap.hint.action,
  { type: "SET_LAYER", layer: "galaxy" },
  "inside the target module, map guidance leads to the structures it cannot draw",
);
assert.equal(sameRegionOnMap.hint.actionLabel, "View structures");

const sameRegionInGalaxy = projection.derive({
  ...state,
  level: LEVELS.SYSTEM,
  layer: "galaxy",
});
assert.equal(
  sameRegionInGalaxy.hint.action,
  null,
  "guidance never renders an enabled action that would leave the learner in place",
);
assert.equal(
  sameRegionInGalaxy.hint.reason,
  "Choose one of its parser-proven structures.",
);

const differentRegion = projection.derive({
  ...state,
  level: LEVELS.SYSTEM,
  region: graph.regions[1],
  layer: "galaxy",
});
assert.deepEqual(
  differentRegion.hint.action,
  { type: "OPEN_REGION", regionId: "app.py" },
  "guidance can move from a different system to the target system",
);

assert.equal(
  projection.derive({ ...state, level: LEVELS.STUDY }).hint,
  null,
  "the Study panel already owns the learner's next action",
);

const studied = projection.derive({
  ...state,
  studiedNodeIds: new Set([...studiedNodeIds, "python:lib.py:helper"]),
});
assert.notEqual(studied.chart, first.chart);
assert.equal(studied.moduleIndex, first.moduleIndex);
assert.equal(studied.focusedGraph, first.focusedGraph);

const allLanguages = projection.derive({ ...state, languageFocus: "all" });
assert.equal(allLanguages.focusedGraph, graph);
assert.notEqual(allLanguages.moduleIndex, first.moduleIndex);

console.log("learner-projection contracts passed");

function makeGraph() {
  return {
    project_root: "/tmp/demo",
    nodes: [
      {
        id: "python:app.py:run",
        region: "app.py",
        file: "app.py",
        language: "python",
        understood: false,
      },
      {
        id: "python:lib.py:helper",
        region: "lib.py",
        file: "lib.py",
        language: "python",
        understood: true,
      },
      {
        id: "typescript:main.ts:main",
        region: "main.ts",
        file: "main.ts",
        language: "typescript",
        understood: false,
      },
    ],
    edges: [],
    entrypoint_candidates: ["python:app.py:run"],
    selected_entrypoint: null,
    file_hashes: { "app.py": "a", "lib.py": "b", "main.ts": "c" },
    concept_annotations: [
      { node_id: "python:app.py:run", language: "python", concept: "entrypoint" },
      { node_id: "python:lib.py:helper", language: "python", concept: "function" },
    ],
    regions: [
      {
        id: "app.py",
        language: "python",
        home: true,
        understood: false,
        hops_from_home: 0,
        community: 0,
        centrality: 2,
        loc: 10,
      },
      {
        id: "lib.py",
        language: "python",
        home: false,
        understood: true,
        hops_from_home: 1,
        community: 0,
        centrality: 1,
        loc: 8,
      },
      {
        id: "main.ts",
        language: "typescript",
        home: false,
        understood: false,
        hops_from_home: null,
        community: 1,
        centrality: 0,
        loc: 6,
      },
    ],
    region_edges: [{ src: "app.py", dst: "lib.py" }],
    partial_files: [],
  };
}

function makeMap() {
  return {
    architecture: {
      boxes: [
        { id: "app.py", language: "python" },
        { id: "main.ts", language: "typescript" },
      ],
      edges: [],
      unreachable: ["main.ts"],
    },
    workflow: {
      nodes: [
        { id: "python:app.py:run", language: "python" },
        { id: "typescript:main.ts:main", language: "typescript" },
      ],
      unreachable: ["typescript:main.ts:main"],
    },
  };
}
