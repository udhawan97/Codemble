import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  FIRST_FLIGHT_LIMIT,
  firstFlightPlan,
  flightCameraDuration,
} from "../src/firstFlight.js";

const regions = [
  { id: "home", language: "python", home: true, centrality: 1 },
  { id: "alpha", language: "python", home: false, centrality: 7 },
  { id: "beta", language: "typescript", home: false, centrality: 7 },
  { id: "gamma", language: "go", home: false, centrality: 2 },
  { id: "possible", language: "rust", home: false, centrality: 99 },
  { id: "indirect", language: "java", home: false, centrality: 40 },
  { id: "extra_a", language: "csharp", home: false, centrality: 1 },
  { id: "extra_b", language: "python", home: false, centrality: 0 },
];
const graph = {
  selected_entrypoint: "home",
  nodes: regions.map((region) => ({
    id: region.id,
    region: region.id,
    language: region.language,
  })),
  regions,
  edges: [
    { src: "home", dst: "beta", kind: "import", certain: true, external: false },
    { src: "home", dst: "alpha", kind: "import", certain: true, external: false },
    { src: "home", dst: "gamma", kind: "import", certain: true, external: false },
    { src: "home", dst: "possible", kind: "import", certain: false, external: false },
    { src: "alpha", dst: "home", kind: "import", certain: true, external: false },
    { src: "alpha", dst: "indirect", kind: "import", certain: true, external: false },
    { src: "home", dst: "extra_b", kind: "import", certain: true, external: false },
    { src: "home", dst: "extra_a", kind: "import", certain: true, external: false },
    // A second statement between the same modules is still one direct module
    // relationship for "used by N / uses M".
    { src: "home", dst: "alpha", kind: "import", certain: true, external: false },
  ],
  region_edges: [
    { src: "home", dst: "beta", certain: true },
    { src: "home", dst: "alpha", certain: true },
    { src: "home", dst: "gamma", certain: true },
    { src: "home", dst: "possible", certain: false },
    { src: "home", dst: "extra_b", certain: true },
    { src: "home", dst: "extra_a", certain: true },
    { src: "alpha", dst: "home", certain: true },
    { src: "alpha", dst: "indirect", certain: true },
  ],
};

const before = structuredClone(graph);
const plan = firstFlightPlan(graph);
assert.equal(plan.length, FIRST_FLIGHT_LIMIT, "Home is included in the six-stop cap");
assert.deepEqual(
  plan.map((stop) => stop.id),
  ["home", "alpha", "beta", "gamma", "extra_a", "extra_b"],
  "direct proven imports sort by centrality descending, then id",
);
assert.deepEqual(
  plan[0],
  { id: "home", language: "python", usedBy: 1, uses: 6, home: true },
);
assert.deepEqual(
  plan[1],
  { id: "alpha", language: "python", usedBy: 1, uses: 2, home: false },
);
assert.ok(!plan.some((stop) => stop.id === "possible"), "a possible edge earns no stop");
assert.ok(!plan.some((stop) => stop.id === "indirect"), "the flight is direct from Home only");
assert.deepEqual(firstFlightPlan(graph), plan, "the same graph produces the same flight");
assert.deepEqual(graph, before, "planning never mutates graph truth");

assert.deepEqual(firstFlightPlan({ ...graph, selected_entrypoint: null }), []);
assert.deepEqual(
  firstFlightPlan({ ...graph, regions: graph.regions.map((region) => ({ ...region, home: false })) }),
  [],
  "without an explicit Home there is no control and no guessed first stop",
);
assert.equal(flightCameraDuration(650, { active: true, reducedMotion: true }), 0);
assert.equal(flightCameraDuration(650, { active: true, reducedMotion: false }), 650);
assert.equal(flightCameraDuration(650, { active: false, reducedMotion: true }), 650);

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const canvasSource = readFileSync(new URL("../src/GalaxyCanvas.jsx", import.meta.url), "utf8");
const guidanceSource = readFileSync(new URL("../src/GuidanceLayer.jsx", import.meta.url), "utf8");
assert.match(
  appSource,
  /function visitFirstFlightStop[\s\S]*?GO_TO_REGION/,
  "every rendered stop travels through the session's existing recordVisit path",
);
assert.match(
  appSource,
  /function exitFirstFlight[\s\S]*?restoreRailFocus\(firstFlightTriggerRef\)/,
  "every exit returns focus through the existing deferred task helper",
);
assert.match(
  canvasSource,
  /event\.key === "Escape" && firstFlightActive/,
  "the canvas yields a tour Escape to the single arbiter instead of retreating first",
);
assert.match(
  canvasSource,
  /setFocusedIndex\(0\);\s*setKeyboardExploring\(false\);/,
  "a keyboard neighborhood persists across overlay focus and resets when its graph view changes",
);
const runtimeSource = readFileSync(new URL("../src/galaxyRuntime.js", import.meta.url), "utf8");
assert.match(
  runtimeSource,
  /flightCameraDuration\(CAMERA_DURATION,[\s\S]*?next\.firstFlightActive[\s\S]*?reducedMotion/,
  "the refactored runtime still owns First Flight's reduced-motion jump cut",
);
assert.doesNotMatch(
  guidanceSource,
  /Finish\s*<\/button>[\s\S]*?<button[^>]*onClick={firstFlight\.onExit}>\s*Exit/,
  "the final stop offers one clear completion action instead of duplicate Finish and Exit buttons",
);

console.log("first-flight contracts passed");
