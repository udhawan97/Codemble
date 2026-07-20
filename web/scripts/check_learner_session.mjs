import assert from "node:assert/strict";

import {
  createHttpLearnerSessionAdapter,
  createInMemoryLearnerSessionAdapter,
  createLearnerSession,
} from "../src/learnerSession.js";
import { LEVELS } from "../src/graphData.js";

const graph = makeGraph();
const understoodGraph = makeGraph({ understood: true });
const study = {
  node: graph.nodes[0],
  source: { file: "app.py", start_line: 1, end_line: 1, lines: [] },
};
const firstChecks = {
  region_id: "app.py",
  region_understood: false,
  checks: [{ id: "calls", passed: false }],
};
const passedChecks = {
  region_id: "app.py",
  region_understood: true,
  checks: [{ id: "calls", passed: true }],
};
const pendingTimers = new Map();
let nextTimerId = 1;
const clock = {
  setTimeout(callback) {
    const timerId = nextTimerId;
    nextTimerId += 1;
    pendingTimers.set(timerId, callback);
    return timerId;
  },
  clearTimeout(timerId) {
    pendingTimers.delete(timerId);
  },
};
const adapter = createInMemoryLearnerSessionAdapter({
  graph,
  studies: {
    "python:app.py:run": study,
    "typescript:main.ts:main": { ...study, node: graph.nodes[1] },
  },
  checks: { "app.py": firstChecks },
  submissions: {
    "app.py:calls": {
      result: { correct: true, region_understood: true },
      graph: understoodGraph,
      checks: passedChecks,
    },
  },
  entrypoints: { "python:app.py:run": understoodGraph },
  explanations: {
    "python:app.py:run:easy": { status: "ready", summary: { text: "easy voice" } },
    "python:app.py:run:expert": { status: "ready", summary: { text: "expert voice" } },
    "typescript:main.ts:main:easy": { status: "no_key", message: "Add a key." },
    "typescript:main.ts:main:expert": { status: "no_key", message: "Add a key." },
  },
  mode: "easy",
  llmStatus: {
    configured_provider: null,
    configured_model: null,
    ollama: {
      running: true,
      installed_models: ["gemma4:12b"],
      recommended: "gemma4:12b",
      fallback: "qwen3:8b",
    },
  },
});
const session = createLearnerSession({ adapter, clock });
let notifications = 0;
const unsubscribe = session.subscribe(() => {
  notifications += 1;
});

await session.start();
let snapshot = session.getSnapshot();
assert.equal(snapshot.status, "ready");
assert.equal(snapshot.graph, graph);
assert.equal(snapshot.focusedGraph, graph);
assert.equal(snapshot.region.id, "app.py");
assert.equal(snapshot.projectName, "demo");
assert.deepEqual(snapshot.languageOptions.map((option) => option.id), [
  "all",
  "python",
  "typescript",
]);
assert.equal(snapshot.mode, "easy", "the session adopts the server's persisted mode");
assert.equal(snapshot.llmStatus.ollama.recommended, "gemma4:12b");

await session.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(session.getSnapshot().mode, "expert");
assert.deepEqual(await adapter.fetchMode(), { mode: "expert" }, "PUT reached the adapter");
await session.dispatch({ type: "SET_MODE", mode: "easy" });
assert.equal(session.getSnapshot().mode, "easy");

await session.dispatch({ type: "ADVANCE", node: graph.regions[0] });
assert.equal(session.getSnapshot().level, LEVELS.SYSTEM);
await session.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
snapshot = session.getSnapshot();
assert.equal(snapshot.level, LEVELS.STUDY);
assert.equal(snapshot.studyData.node.id, "python:app.py:run");
assert(snapshot.studiedNodeIds.has("python:app.py:run"));
assert.equal(snapshot.explanationLoading, false);
assert.equal(snapshot.explanationError, "");
assert.equal(snapshot.explanation.summary.text, "easy voice");

await session.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(
  session.getSnapshot().explanation.summary.text,
  "expert voice",
  "changing voice while studying re-narrates the same node",
);
await session.dispatch({ type: "SET_MODE", mode: "easy" });

await session.dispatch({ type: "RETREAT" });
assert.equal(session.getSnapshot().explanation, null, "leaving study drops its narration");
await session.dispatch({ type: "ADVANCE", node: graph.nodes[0] });

await session.dispatch({ type: "SET_LANGUAGE_FOCUS", language: "python" });
await session.dispatch({ type: "SELECT_STUDY_NODE", nodeId: "typescript:main.ts:main" });
snapshot = session.getSnapshot();
assert.equal(snapshot.languageFocus, "typescript");
assert.equal(snapshot.region.id, "main.ts");
assert.equal(snapshot.selectedNode.id, "typescript:main.ts:main");
assert.equal(snapshot.studyData.node.id, "typescript:main.ts:main");

await session.dispatch({ type: "SET_LANGUAGE_FOCUS", language: "python" });
snapshot = session.getSnapshot();
assert.equal(snapshot.level, LEVELS.GALAXY);
assert.equal(snapshot.region.id, "app.py");
assert.equal(snapshot.selectedNode, null);
await session.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await session.dispatch({ type: "OPEN_CHECKS" });
assert.equal(session.getSnapshot().checkData, firstChecks);
const result = await session.dispatch({
  type: "SUBMIT_CHECK",
  checkId: "calls",
  selectedIds: ["python:app.py:run"],
});
snapshot = session.getSnapshot();
assert.deepEqual(result, { correct: true, region_understood: true });
assert.equal(snapshot.checkData, passedChecks);
assert.equal(snapshot.graph, understoodGraph);
assert.equal(snapshot.region.understood, true);
assert.equal(snapshot.litRegionId, "app.py");
assert.equal(pendingTimers.size, 1);
pendingTimers.values().next().value();
assert.equal(session.getSnapshot().litRegionId, null);

await session.dispatch({ type: "RETREAT" });
await session.dispatch({ type: "SELECT_ENTRYPOINT", nodeId: "python:app.py:run" });
assert.equal(session.getSnapshot().graph, understoodGraph);
await session.dispatch({ type: "DISMISS_ENTRYPOINT" });
assert.equal(session.getSnapshot().entrypointDismissed, true);
await session.dispatch({ type: "SHOW_CHART" });
assert.equal(session.getSnapshot().showChart, true);
await session.dispatch({ type: "HIDE_CHART" });
assert.equal(session.getSnapshot().showChart, false);
assert(notifications > 0);

unsubscribe();
session.dispose();

let resolveLateStudy;
const lateStudy = new Promise((resolve) => {
  resolveLateStudy = resolve;
});
const sequencingSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({
    graph,
    studies: {
      "python:app.py:run": lateStudy,
      "typescript:main.ts:main": { ...study, node: graph.nodes[1] },
    },
  }),
});
await sequencingSession.start();
await sequencingSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
const staleRequest = sequencingSession.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
await sequencingSession.dispatch({
  type: "SELECT_STUDY_NODE",
  nodeId: "typescript:main.ts:main",
});
resolveLateStudy(study);
await staleRequest;
assert.equal(
  sequencingSession.getSnapshot().studyData.node.id,
  "typescript:main.ts:main",
  "a late response cannot replace the learner's current study selection",
);
sequencingSession.dispose();

let rejectStaleChecks;
const staleChecks = new Promise((_resolve, reject) => {
  rejectStaleChecks = reject;
});
const checksBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  checks: { "app.py": passedChecks },
});
let checksRequestCount = 0;
const staleErrorSession = createLearnerSession({
  adapter: {
    ...checksBaseAdapter,
    loadChecks(...args) {
      checksRequestCount += 1;
      if (checksRequestCount === 1) return staleChecks;
      return checksBaseAdapter.loadChecks(...args);
    },
  },
});
await staleErrorSession.start();
await staleErrorSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
const staleChecksRequest = staleErrorSession.dispatch({ type: "OPEN_CHECKS" });
await staleErrorSession.dispatch({ type: "OPEN_CHECKS" });
rejectStaleChecks(new Error("late checks failure"));
await staleChecksRequest;
assert.equal(staleErrorSession.getSnapshot().checkData, passedChecks);
assert.equal(
  staleErrorSession.getSnapshot().checkError,
  "",
  "a superseded failure cannot replace newer check state",
);
staleErrorSession.dispose();

const httpCalls = [];
const responsePayloads = [{ graph: true }, { study: true }, { checks: true }, { score: true }, { home: true }];
const http = createHttpLearnerSessionAdapter(async (url, options = {}) => {
  httpCalls.push([url, options]);
  return {
    ok: true,
    async json() {
      return responsePayloads.shift();
    },
  };
});
assert.deepEqual(await http.loadGraph(), { graph: true });
assert.deepEqual(await http.loadStudy("node/id"), { study: true });
assert.deepEqual(await http.loadChecks("region/id"), { checks: true });
assert.deepEqual(await http.submitCheck("region/id", "check/id", ["answer"]), { score: true });
assert.deepEqual(await http.selectEntrypoint("node/id"), { home: true });
assert.deepEqual(
  httpCalls.map(([url]) => url),
  [
    "/api/graph",
    "/api/node/node%2Fid/study",
    "/api/regions/region%2Fid/checks",
    "/api/regions/region%2Fid/checks/check%2Fid",
    "/api/entrypoint",
  ],
);
assert.equal(httpCalls[3][1].method, "POST");
assert.equal(httpCalls[3][1].body, JSON.stringify({ selected_ids: ["answer"] }));
assert.equal(httpCalls[4][1].body, JSON.stringify({ node_id: "node/id" }));

console.log("learner-session contracts passed");

// HTTP picker adapter: URLs, payloads, and non-throwing select results.
const pickerHttpCalls = [];
const pickerFetch = async (url, options = {}) => {
  pickerHttpCalls.push({ url, options });
  if (url === "/api/picker/state") {
    return { ok: true, status: 200, json: async () => ({ state: "unpicked" }) };
  }
  if (url === "/api/picker/select") {
    return {
      ok: false,
      status: 409,
      json: async () => ({
        detail: {
          reason: "scale",
          file_count: 420,
          scale_cap: 300,
          root: "/home/u/big",
          suggestions: [{ path: "api", file_count: 300 }],
        },
      }),
    };
  }
  throw new Error(`Unexpected picker URL: ${url}`);
};
const httpPicker = createHttpLearnerSessionAdapter(pickerFetch);
assert.deepEqual(await httpPicker.loadPickerState(), { state: "unpicked" });
const scaleResult = await httpPicker.selectProject("/home/u/big");
assert.equal(scaleResult.state, "scale");
assert.equal(scaleResult.file_count, 420);
assert.equal(
  JSON.parse(pickerHttpCalls.at(-1).options.body).path,
  "/home/u/big",
);

// In-memory picker adapter: fixture-driven browse/recents/select and state flip.
const rootListing = {
  path: "/home/u",
  parent: null,
  entries: [{ name: "big", path: "/home/u/big", is_dir: true }],
};
const bigListing = { path: "/home/u/big", parent: "/home/u", entries: [] };
const memoryPicker = createInMemoryLearnerSessionAdapter({
  graph,
  picker: {
    browse: { "": rootListing, "/home/u/big": bigListing },
    recents: [{ project_root: "/home/u/big", understood_count: 2 }],
    selections: { "/home/u/big": { state: "ready" } },
  },
});
assert.deepEqual(await memoryPicker.loadPickerState(), { state: "unpicked" });
assert.equal(await memoryPicker.browsePicker(null), rootListing);
assert.equal(await memoryPicker.browsePicker("/home/u/big"), bigListing);
assert.deepEqual(await memoryPicker.loadRecents(), {
  recents: [{ project_root: "/home/u/big", understood_count: 2 }],
});
assert.deepEqual(await memoryPicker.selectProject("/home/u/big"), { state: "ready" });
assert.deepEqual(await memoryPicker.loadPickerState(), { state: "ready" });
assert.deepEqual(
  await createInMemoryLearnerSessionAdapter({ graph }).loadPickerState(),
  { state: "ready" },
  "adapters without a picker fixture stay ready for existing callers",
);

// Picker phase: unpicked server → recents → scale rescope → select → ready.
const pickerAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [
          { name: "big", path: "/home/u/big" },
          { name: "demo", path: "/home/u/demo" },
        ],
      },
      "/home/u/big": {
        path: "/home/u/big",
        parent: "/home/u",
        entries: [{ name: "api", path: "/home/u/big/api" }],
      },
    },
    recents: [{ project_root: "/home/u/demo", understood_count: 2 }],
    selections: {
      "/home/u/big": {
        state: "scale",
        file_count: 420,
        scale_cap: 300,
        root: "/home/u/big",
        suggestions: [{ path: "api", file_count: 300 }],
      },
      "/home/u/demo": { state: "ready" },
    },
  },
});
const pickerSession = createLearnerSession({ adapter: pickerAdapter, clock });
await pickerSession.start();
let pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "picking");
assert.equal(pickerSnapshot.picker.path, "/home/u");
assert.equal(pickerSnapshot.picker.recents[0].understood_count, 2);

await pickerSession.dispatch({ type: "BROWSE_PICKER", path: "/home/u/big" });
assert.equal(pickerSession.getSnapshot().picker.path, "/home/u/big");

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/big" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "picking");
assert.equal(pickerSnapshot.picker.scale.file_count, 420);
assert.equal(pickerSnapshot.picker.path, "/home/u/big");
assert.equal(pickerSnapshot.picker.busy, false);

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "ready");
assert.equal(pickerSnapshot.picker, null);
assert.equal(pickerSnapshot.graph, graph);
pickerSession.dispose();

// Regression: a browse during an in-flight selection must not wedge picker.busy.
let resolveRaceSelect;
const raceSelect = new Promise((resolve) => {
  resolveRaceSelect = resolve;
});
const raceBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [{ name: "demo", path: "/home/u/demo" }],
      },
      "/home/u/demo": { path: "/home/u/demo", parent: "/home/u", entries: [] },
    },
    recents: [],
    selections: {},
  },
});
const raceSession = createLearnerSession({
  adapter: { ...raceBaseAdapter, selectProject: () => raceSelect },
  clock,
});
await raceSession.start();
const raceSelectRequest = raceSession.dispatch({
  type: "SELECT_PROJECT",
  path: "/home/u/demo",
});
await raceSession.dispatch({ type: "BROWSE_PICKER", path: "/home/u/demo" });
let raceSnapshot = raceSession.getSnapshot();
assert.equal(
  raceSnapshot.picker.path,
  "/home/u",
  "a browse is refused while a selection is in flight",
);
assert.equal(raceSnapshot.picker.busy, true);
resolveRaceSelect({ state: "ready" });
await raceSelectRequest;
raceSnapshot = raceSession.getSnapshot();
assert.equal(raceSnapshot.status, "ready");
assert.equal(raceSnapshot.picker, null);
raceSession.dispose();

// A failing mode write reverts the optimistic value: mode is a preference,
// never truth, so the UI must not claim a setting the server refused.
const modeFailureAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "easy" });
const modeFailureSession = createLearnerSession({
  adapter: {
    ...modeFailureAdapter,
    putMode() {
      throw new Error("mode write refused");
    },
  },
  clock,
});
await modeFailureSession.start();
assert.equal(modeFailureSession.getSnapshot().mode, "easy");
await modeFailureSession.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(
  modeFailureSession.getSnapshot().mode,
  "easy",
  "a refused mode write rolls back to the last server-confirmed value",
);
modeFailureSession.dispose();

// A failing status read must not blank the mode that loaded beside it.
const statusFailureAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "expert" });
const statusFailureSession = createLearnerSession({
  adapter: {
    ...statusFailureAdapter,
    fetchLlmStatus() {
      throw new Error("status unavailable");
    },
  },
  clock,
});
await statusFailureSession.start();
assert.equal(statusFailureSession.getSnapshot().mode, "expert");
assert.equal(statusFailureSession.getSnapshot().llmStatus, null);
assert.equal(statusFailureSession.getSnapshot().status, "ready");
statusFailureSession.dispose();

// Regression: a same-project mode change that races the preferences load
// must win over the stale fetchMode value it raced with, and llmStatus from
// that same response must still apply.
let resolveRaceStatus;
const raceStatus = new Promise((resolve) => {
  resolveRaceStatus = resolve;
});
let notifyStatusRequested;
const statusRequested = new Promise((resolve) => {
  notifyStatusRequested = resolve;
});
const raceModeBaseAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "expert" });
const raceModeSession = createLearnerSession({
  adapter: {
    ...raceModeBaseAdapter,
    fetchLlmStatus() {
      notifyStatusRequested();
      return raceStatus;
    },
  },
  clock,
});
const raceModeStart = raceModeSession.start();
await statusRequested;
await raceModeSession.dispatch({ type: "SET_MODE", mode: "easy" });
resolveRaceStatus({
  configured_provider: null,
  configured_model: null,
  ollama: {
    running: true,
    installed_models: ["gemma4:12b"],
    recommended: "gemma4:12b",
    fallback: "qwen3:8b",
  },
});
await raceModeStart;
assert.equal(
  raceModeSession.getSnapshot().mode,
  "easy",
  "a mode change that races the preferences load wins over the stale fetchMode value",
);
assert.equal(
  raceModeSession.getSnapshot().llmStatus.ollama.recommended,
  "gemma4:12b",
  "llmStatus from the same preferences response still applies",
);
raceModeSession.dispose();

// A failing narration request must leave the structural evidence untouched.
const narrationFailureAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  studies: { "python:app.py:run": study },
});
const narrationFailureSession = createLearnerSession({
  adapter: {
    ...narrationFailureAdapter,
    fetchExplanation() {
      return Promise.reject(new Error("Explanation request returned 502."));
    },
  },
  clock,
});
await narrationFailureSession.start();
await narrationFailureSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await narrationFailureSession.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
const narrationSnapshot = narrationFailureSession.getSnapshot();
assert.equal(narrationSnapshot.explanation, null);
assert.equal(narrationSnapshot.explanationLoading, false);
assert.equal(narrationSnapshot.explanationError, "Explanation request returned 502.");
assert.equal(
  narrationSnapshot.studyData.node.id,
  "python:app.py:run",
  "narration failure never removes parser evidence",
);
narrationFailureSession.dispose();

function makeGraph({ understood = false } = {}) {
  return {
    project_root: "/tmp/demo",
    nodes: [
      {
        id: "python:app.py:run",
        name: "run",
        language: "python",
        region: "app.py",
        file: "app.py",
        understood,
      },
      {
        id: "typescript:main.ts:main",
        name: "main",
        language: "typescript",
        region: "main.ts",
        file: "main.ts",
        understood: false,
      },
    ],
    edges: [],
    entrypoint_candidates: ["python:app.py:run"],
    selected_entrypoint: null,
    file_hashes: { "app.py": "a", "main.ts": "b" },
    concept_annotations: [],
    regions: [
      { id: "app.py", language: "python", home: true, understood },
      { id: "main.ts", language: "typescript", home: false, understood: false },
    ],
    region_edges: [],
    partial_files: [],
  };
}
