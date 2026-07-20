import assert from "node:assert/strict";

import {
  buildConceptChart,
  galaxyData,
  languageFocusGraph,
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
