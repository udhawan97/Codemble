import assert from "node:assert/strict";

import {
  buildConceptChart,
  languageFocusGraph,
  projectLanguageOptions,
} from "../src/graphData.js";

const graph = {
  nodes: [
    { id: "py", region: "py", file: "py.py", language: "python", understood: false },
    { id: "ts", region: "ts", file: "ts.ts", language: "typescript", understood: true },
    { id: "js", region: "js", file: "js.js", language: "javascript", understood: false },
  ],
  edges: [
    { src: "ts", dst: "js", external: false },
    { src: "ts", dst: "external:react", external: true },
    { src: "ts", dst: "unresolved:local", external: false },
    { src: "py", dst: "ts", external: false },
  ],
  entrypoint_candidates: ["py", "ts"],
  selected_entrypoint: "py",
  file_hashes: { "js.js": "j", "py.py": "p", "ts.ts": "t" },
  concept_annotations: [
    { node_id: "py", language: "python", concept: "async-await" },
    { node_id: "ts", language: "typescript", concept: "async-await" },
  ],
  regions: [
    { id: "py", language: "python", x: 1 },
    { id: "ts", language: "typescript", x: 2 },
    { id: "js", language: "javascript", x: 3 },
  ],
  region_edges: [
    { src: "ts", dst: "js" },
    { src: "py", dst: "ts" },
  ],
  partial_files: ["js.js"],
};

assert.equal(languageFocusGraph(graph, "all"), graph);
const typescript = languageFocusGraph(graph, "typescript");
assert.deepEqual(typescript.nodes.map((node) => node.id), ["ts"]);
assert.equal(typescript.nodes[0], graph.nodes[1], "focus preserves parser coordinates and metadata");
assert.deepEqual(typescript.edges.map((edge) => edge.dst), ["external:react", "unresolved:local"]);
assert.deepEqual(typescript.entrypoint_candidates, ["ts"]);
assert.equal(typescript.selected_entrypoint, null);
assert.deepEqual(typescript.file_hashes, { "ts.ts": "t" });
assert.deepEqual(typescript.regions.map((region) => region.id), ["ts"]);
assert.deepEqual(typescript.region_edges, []);
assert.deepEqual(typescript.partial_files, []);
assert.equal(graph.nodes.length, 3, "focus never mutates graph truth");

assert.deepEqual(
  projectLanguageOptions(graph).map(({ id, count }) => [id, count]),
  [
    ["all", 3],
    ["javascript", 1],
    ["python", 1],
    ["typescript", 1],
  ],
);

const chart = buildConceptChart(graph, new Set(["ts"]));
assert.deepEqual(
  chart.map(({ language, concept, studied_nodes, understood_nodes }) => [
    language,
    concept,
    studied_nodes,
    understood_nodes,
  ]),
  [
    ["python", "async-await", 0, 0],
    ["typescript", "async-await", 1, 1],
  ],
);

console.log("graph-data contracts passed");
