import assert from "node:assert/strict";

import {
  buildConceptChart,
  communityName,
  communityPaletteIndex,
  communityShade,
  galaxyData,
  groupByCommunity,
  isTestScopedPath,
  languageFocusGraph,
  languageFocusMap,
  linkLabel,
  moduleIndex,
  projectLanguageOptions,
  revealedRegionIds,
  sharedTopSegment,
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

// --- progressive reveal -----------------------------------------------------

// home -> near -> mid -> far, plus `lit` (understood, off the Home chain) with
// its own neighbour `beside`, plus `island`, which nothing imports at all.
const sky = {
  nodes: [
    "home",
    "near",
    "mid",
    "far",
    "lit",
    "beside",
    "island",
  ].map((id) => ({ id, region: id, file: `src/${id}.py`, language: "python" })),
  edges: [],
  regions: [
    { id: "home", home: true, hops_from_home: 0, understood: false, community: 0, centrality: 0, loc: 1, language: "python" },
    { id: "near", home: false, hops_from_home: 1, understood: false, community: 0, centrality: 0, loc: 1, language: "python" },
    { id: "mid", home: false, hops_from_home: 2, understood: false, community: 0, centrality: 0, loc: 1, language: "python" },
    { id: "far", home: false, hops_from_home: 3, understood: false, community: 0, centrality: 0, loc: 1, language: "python" },
    { id: "lit", home: false, hops_from_home: null, understood: true, community: 1, centrality: 0, loc: 1, language: "python" },
    { id: "beside", home: false, hops_from_home: null, understood: false, community: 1, centrality: 0, loc: 1, language: "python" },
    { id: "island", home: false, hops_from_home: null, understood: false, community: 2, centrality: 0, loc: 1, language: "python" },
  ],
  region_edges: [
    { src: "home", dst: "near", certain: true, weight: 1 },
    { src: "near", dst: "mid", certain: true, weight: 1 },
    { src: "mid", dst: "far", certain: true, weight: 1 },
    { src: "beside", dst: "lit", certain: true, weight: 1 },
  ],
};

assert.deepEqual(
  [...revealedRegionIds(sky)].sort(),
  ["beside", "home", "lit", "mid", "near"],
  "floor reaches two routes from Home; a lit region and its neighbour are earned; far and island stay uncharted",
);
assert.ok(
  !revealedRegionIds(sky).has("far"),
  "three routes out is beyond the first-run floor",
);
assert.deepEqual(
  [...revealedRegionIds(sky, { showAll: true })].sort(),
  ["beside", "far", "home", "island", "lit", "mid", "near"],
  "Show all reveals every region including the unreachable island",
);
assert.ok(
  revealedRegionIds(sky, { selectionId: "far" }).has("far"),
  "selecting an uncharted region reveals it while it is the subject",
);
assert.ok(
  !revealedRegionIds(sky).has("far"),
  "and that transient reveal leaves no trace once the selection moves on",
);
assert.deepEqual(
  [...revealedRegionIds({ ...sky, regions: sky.regions.map((r) => ({ ...r, home: false })) })].sort(),
  ["beside", "far", "home", "island", "lit", "mid", "near"],
  "with no Home there is no distance to measure, so nothing may be hidden",
);

const skyData = galaxyData(sky, swatches, revealedRegionIds(sky));
assert.deepEqual(
  skyData.links.map((link) => `${link.src}->${link.dst}`),
  ["home->near", "near->mid", "beside->lit"],
  "routes touching an uncharted region are dropped, which is what thins the mesh",
);
assert.equal(
  skyData.nodes.length,
  sky.regions.length,
  "every region is still drawn: reveal must never misreport the project's size",
);
assert.equal(
  skyData.nodes.find((node) => node.id === "far").label,
  "",
  "an uncharted region carries no label",
);
assert.equal(
  skyData.nodes.find((node) => node.id === "near").label,
  "src/near.py",
  "a charted region is labelled with the tail of the parser's own path",
);

// Basenames collide hard -- every Python package carries an __init__.py -- and
// identical plates over different modules are worse than none. This is the
// same rule map schema 3 gave the Architecture boxes.
{
  const collides = {
    ...sky,
    regions: sky.regions.map((region) => ({ ...region })),
    nodes: sky.regions.map((region) => ({
      id: `${region.id}.mod`,
      region: region.id,
      file: `${region.id}/__init__.py`,
      kind: "module",
      language: "python",
      loc: 1,
      centrality: 0,
      partial: false,
      understood: false,
      name: "__init__",
    })),
  };
  const labels = galaxyData(collides, swatches, null)
    .nodes.map((node) => node.label)
    .filter(Boolean);
  assert.equal(
    new Set(labels).size,
    labels.length,
    `every charted plate stays distinguishable: ${labels.join(", ")}`,
  );
}

// --- module index and constellation names ------------------------------------

const index = moduleIndex(sky);
assert.deepEqual(
  index.map((row) => row.id),
  ["beside", "far", "home", "island", "lit", "mid", "near"],
  "the index is sorted by label so both the palette and the sidebar are stable",
);
assert.equal(index.find((row) => row.id === "home").hops, 0);
assert.equal(index.find((row) => row.id === "island").hops, null);

assert.equal(
  communityName([{ file: "web/src/a.js" }, { file: "web/src/b.js" }]),
  "web/src/",
  "a constellation is named by the directory its members actually share",
);
assert.equal(
  communityName([{ file: "web/a.js" }, { file: "api/b.py" }]),
  "2 modules",
  "members sharing no directory get a count, never a borrowed name",
);
assert.deepEqual(
  groupByCommunity(index).map((group) => group.community),
  [0, 1, 2],
  "constellations are ordered by size, ties broken by community id",
);
assert.deepEqual(
  groupByCommunity(index)[0].members.map((row) => row.display),
  ["far.py", "home.py", "mid.py", "near.py"],
  "a row drops the prefix its group heading already states",
);
// Two packages, each with its own __init__.py: the case where basenames alone
// are useless, because every row would read identically.
const collide = groupByCommunity([
  { id: "a", file: "pkg/a/__init__.py", label: "__init__.py", community: 0 },
  { id: "b", file: "pkg/b/__init__.py", label: "__init__.py", community: 0 },
]);
assert.equal(collide[0].name, "pkg/");
assert.deepEqual(
  collide[0].members.map((row) => row.display),
  ["a/__init__.py", "b/__init__.py"],
  "colliding basenames keep enough real path to tell them apart",
);

// --- Community colour families (D1) -----------------------------------------
const communityPalette = {
  ground: "rgb(7, 11, 28)",
  star: "rgb(244, 196, 106)",
  node: "rgb(125, 138, 168)",
  nodeBright: "rgb(154, 168, 196)",
  nodeDim: "rgb(101, 111, 135)",
  routePossible: "rgb(137, 148, 175)",
  route: "rgb(96, 113, 152)",
  communities: [
    "rgb(109, 181, 153)",
    "rgb(187, 155, 211)",
    "rgb(155, 175, 113)",
    "rgb(110, 177, 190)",
    "rgb(215, 149, 167)",
    "rgb(191, 158, 175)",
    "rgb(94, 185, 133)",
    "rgb(170, 160, 218)",
  ],
};

// Deterministic slot arithmetic, wrap included; a missing fact maps to null.
assert.equal(communityPaletteIndex(0), 0);
assert.equal(communityPaletteIndex(9), 1);
assert.equal(communityPaletteIndex(-1), 7, "negative ids stay in range");
assert.equal(communityPaletteIndex(null), null);
assert.equal(communityPaletteIndex(2.5), null, "non-integer ids claim nothing");

// Same community, same colour, every time.
assert.equal(
  communityShade(communityPalette, 3, 9, 5),
  communityShade(communityPalette, 3, 9, 5),
);
// Bright tier IS the token; lower centrality recedes toward the ground but
// keeps the hue's channel ordering (green stays the dominant channel).
assert.equal(communityShade(communityPalette, 0, 9, 5), "rgb(109, 181, 153)");
const midShade = communityShade(communityPalette, 0, 1, 5);
const dimShade = communityShade(communityPalette, 0, 0, 5);
const channel = (rgb, index) => Number(/(\d+),\s*(\d+),\s*(\d+)/.exec(rgb)[index + 1]);
assert.ok(
  channel(midShade, 1) > channel(dimShade, 1),
  "mid tier is brighter than dim tier",
);
assert.ok(
  channel(midShade, 1) > channel(midShade, 0) &&
    channel(midShade, 1) > channel(midShade, 2),
  "the hue survives the tier mix",
);
// No community id -> the old neutral ramp, never a borrowed hue.
assert.equal(communityShade(communityPalette, undefined, 9, 5), communityPalette.nodeBright);
assert.equal(communityShade(communityPalette, undefined, 1, 5), communityPalette.node);
assert.equal(communityShade(communityPalette, undefined, 0, 5), communityPalette.nodeDim);

// Amber's monopoly survives D1: an understood region ignores its community.
const hueGraph = {
  ...graph,
  regions: graph.regions.map((region, index) => ({
    ...region,
    community: index,
    understood: region.id === "ts",
    centrality: 9,
    loc: 10,
  })),
  region_edges: [],
};
const huedGalaxy = galaxyData(hueGraph, communityPalette, null);
const understoodNode = huedGalaxy.nodes.find((node) => node.id === "ts");
assert.equal(understoodNode.color, communityPalette.star, "lit stays amber");
const unlitNode = huedGalaxy.nodes.find((node) => node.id === "py");
assert.equal(
  unlitNode.color,
  communityShade(communityPalette, 0, 9, 5),
  "unlit charted regions wear their community family",
);

// Test-scope detection is directory-based parser truth.
assert.equal(isTestScopedPath("tests/test_server.py"), true);
assert.equal(isTestScopedPath("tests/fixtures/impact/alpha.py"), true);
assert.equal(isTestScopedPath("web/src/App.jsx"), false);
assert.equal(isTestScopedPath("attestation/report.py"), false, "substring never matches");
assert.equal(isTestScopedPath("test_top.py"), false, "a basename alone is not a directory");

// Fixture-error attribution names the files' own shared directory, or nothing.
assert.equal(
  sharedTopSegment(["tests/fixtures/a.py", "tests/b.ts"]),
  "tests",
);
assert.equal(sharedTopSegment(["tests/a.py", "web/b.js"]), null);
assert.equal(sharedTopSegment([]), null);

console.log("graph-data contracts passed");
