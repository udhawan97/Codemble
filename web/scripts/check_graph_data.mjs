import assert from "node:assert/strict";

import {
  buildConceptChart,
  galaxyData,
  languageFocusGraph,
  languageFocusMap,
  linkLabel,
  projectLanguageOptions,
  systemData,
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

// The Map's language projection (F4): the same drop-not-move rule as the galaxy
// focus, applied to the flat map payload. Boxes/rows/edges of other languages
// disappear; survivors keep their exact backend coordinates and objects.
const mapData = {
  schema_version: 1,
  architecture: {
    home: null,
    layer_count: 2,
    width: 960,
    height: 240,
    groups: [],
    boxes: [
      { id: "py", language: "python", x: 10, y: 0, width: 160, height: 56 },
      { id: "pylib", language: "python", x: 10, y: 120, width: 160, height: 56 },
      { id: "ts", language: "typescript", x: 200, y: 0, width: 160, height: 56 },
      { id: "js", language: "javascript", x: 390, y: 0, width: 160, height: 56 },
    ],
    edges: [
      { src: "py", dst: "pylib", certain: true }, // both python -> survives
      { src: "ts", dst: "js", certain: true }, // neither python -> dropped
      { src: "py", dst: "ts", certain: false }, // ts dropped -> orphaned -> dropped
    ],
    unreachable: ["js"],
  },
  workflow: {
    root: "python:py:run",
    depth_count: 2,
    width: 320,
    height: 68,
    nodes: [
      { id: "python:py:run", language: "python", x: 0, y: 0, parent: null },
      { id: "typescript:ts:main", language: "typescript", x: 28, y: 34, parent: "python:py:run" },
    ],
    unreachable: ["javascript:js:helper", "python:py:dead"],
  },
};

assert.equal(languageFocusMap(mapData, "all"), mapData, "no focus is the identity");
assert.equal(languageFocusMap(null, "python"), null, "a missing map projects to nothing");

const pyMap = languageFocusMap(mapData, "python");
assert.deepEqual(
  pyMap.architecture.boxes.map((box) => box.id),
  ["py", "pylib"],
  "only the focused language's boxes survive",
);
assert.equal(
  pyMap.architecture.boxes[0],
  mapData.architecture.boxes[0],
  "a surviving box keeps its object and its backend coordinates -- nothing moves",
);
assert.equal(pyMap.architecture.edges.length, 1, "an edge orphaned by a dropped box is dropped too");
assert.equal(
  pyMap.architecture.edges[0],
  mapData.architecture.edges[0],
  "a surviving edge keeps its object -- its certainty (dashed/solid) is never rewritten",
);
assert.deepEqual(pyMap.architecture.unreachable, [], "the unreachable note's count follows the focus");
assert.equal(pyMap.architecture.width, 960, "canvas dimensions are backend-owned and never recomputed");
assert.equal(pyMap.architecture.height, 240);
assert.deepEqual(
  pyMap.workflow.nodes.map((row) => row.id),
  ["python:py:run"],
  "only the focused language's workflow rows survive",
);
assert.equal(
  pyMap.workflow.nodes[0],
  mapData.workflow.nodes[0],
  "a surviving row keeps its object and coordinates",
);
assert.deepEqual(
  pyMap.workflow.unreachable,
  ["python:py:dead"],
  "unreached rows have no language field, so their language:file:symbol id prefix filters them",
);
assert.equal(pyMap.workflow.root, "python:py:run", "the backend root is untouched");
assert.equal(mapData.architecture.boxes.length, 4, "projection never mutates the map payload");
assert.equal(mapData.workflow.nodes.length, 2);

const tsMap = languageFocusMap(mapData, "typescript");
assert.deepEqual(tsMap.architecture.boxes.map((box) => box.id), ["ts"]);
assert.deepEqual(tsMap.architecture.edges, [], "ts's only edges point at dropped boxes, so none survive");
assert.deepEqual(tsMap.workflow.nodes.map((row) => row.id), ["typescript:ts:main"]);

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

assert.equal(
  linkLabel({ src: "app.main", dst: "pkg.run", kind: "call", certain: true, lineno: 12 }),
  "app.main → pkg.run · call · certain · line 12",
);
assert.equal(
  linkLabel({ src: "app.main", dst: "pkg.run", kind: "call", certain: false, lineno: 12 }),
  "app.main → pkg.run · call · possible call · line 12",
  "an approximate call edge must say so in its tooltip",
);
assert.equal(
  linkLabel({ src: "app", dst: "pkg", kind: "import", certain: false, lineno: 3 }),
  "app → pkg · import · possible import · line 3",
);
assert.equal(
  linkLabel({ src: "app", dst: "pkg", weight: 2, certain: true }),
  "app → pkg · import route · certain · 2 imports",
  "galaxy-level region edges carry a weight instead of a line number",
);

// Understanding owns the top of the brightness range, on both layers. The token
// values are ordered in tokens.css (--cm-star-high 12.06:1 on --cm-ground >
// --cm-ink-2 8.17 > --cm-route-possible 6.35), so what has to hold here is the
// *selection*: understood always takes amber, and nothing unlit may reach it.
// The two ramps have different top steps on purpose -- a region's centrality is
// the sum over its members, a node's is its count of distinct callers.
const swatches = {
  star: "AMBER",
  nodeBright: "BRIGHT",
  node: "MID",
  nodeDim: "DIM",
  routePossible: "UNCERTAIN",
  route: "ROUTE",
};
const ramp = {
  nodes: [
    { id: "cold", region: "r", centrality: 0, loc: 4, understood: false },
    { id: "warm", region: "r", centrality: 1, loc: 4, understood: false },
    { id: "hot", region: "r", centrality: 9, loc: 4, understood: false },
    { id: "lit", region: "r", centrality: 0, loc: 4, understood: true },
    { id: "broken", region: "r", centrality: 9, loc: 4, partial: true, understood: false },
  ],
  edges: [],
  regions: [
    { id: "r", centrality: 0, loc: 9, understood: false },
    { id: "busy", centrality: 6, loc: 9, understood: false },
    { id: "known", centrality: 0, loc: 9, understood: true },
  ],
  region_edges: [],
};
const byId = (data) => Object.fromEntries(data.nodes.map((n) => [n.id, n.color]));

const systemColors = byId(systemData(ramp, "r", swatches));
assert.deepEqual(systemColors, {
  cold: "DIM",
  warm: "MID",
  // 2 distinct callers is the top step per node, not 5: at 5 only 4% of nodes
  // on this repo could ever reach it and the ramp had no top in practice.
  hot: "BRIGHT",
  lit: "AMBER",
  broken: "UNCERTAIN",
});
const galaxyColors = byId(galaxyData(ramp, swatches));
assert.deepEqual(galaxyColors, { r: "UNCERTAIN", busy: "BRIGHT", known: "AMBER" });
assert.equal(
  galaxyData({ ...ramp, nodes: [] }, swatches).nodes[0].color,
  "DIM",
  "a region with no partial member falls back to its own centrality ramp",
);

console.log("graph-data contracts passed");
