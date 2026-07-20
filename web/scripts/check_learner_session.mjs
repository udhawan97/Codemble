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

await session.dispatch({ type: "ADVANCE", node: graph.regions[0] });
assert.equal(session.getSnapshot().level, LEVELS.SYSTEM);
await session.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
snapshot = session.getSnapshot();
assert.equal(snapshot.level, LEVELS.STUDY);
assert.equal(snapshot.studyData.node.id, "python:app.py:run");
assert(snapshot.studiedNodeIds.has("python:app.py:run"));

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

// Audience mode: hydrates from the adapter, and SET_MODE persists the choice.
const modeSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({
    graph,
    mode: "expert",
  }),
});
await modeSession.start();
assert.equal(modeSession.getSnapshot().mode, "expert", "mode hydrates from the adapter");

await modeSession.dispatch({ type: "SET_MODE", mode: "easy" });
assert.equal(modeSession.getSnapshot().mode, "easy", "SET_MODE updates the snapshot");
assert.equal(modeSession.getSnapshot().modeChosen, true, "choosing a mode records the choice");
modeSession.dispose();

// A backend returning garbage must never poison the snapshot with a mode
// the renderer doesn't understand — design contract says silently keep easy.
const garbageModeSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph }),
    async loadMode() {
      return { mode: "not-a-real-mode" };
    },
  },
});
await garbageModeSession.start();
assert.equal(
  garbageModeSession.getSnapshot().mode,
  "easy",
  "garbage mode from the backend is ignored, not stored",
);
garbageModeSession.dispose();

// Fix 1: the in-memory adapter mirrors the real backend's {mode, chosen}
// contract directly — chosen flips true only once saveMode is called.
const modeAdapter = createInMemoryLearnerSessionAdapter({ graph });
assert.deepEqual(await modeAdapter.loadMode(), { mode: "easy", chosen: false });
assert.deepEqual(await modeAdapter.saveMode("expert"), { mode: "expert", chosen: true });
assert.deepEqual(await modeAdapter.loadMode(), { mode: "expert", chosen: true });

// Fix 1: chosen vs not-chosen is the entire point of the field, including
// when the earlier explicit choice was "easy" — same value as the silent
// default, so mode alone can't tell these two learners apart.
const returningLearnerSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph, mode: "easy", modeChosen: true }),
});
await returningLearnerSession.start();
assert.equal(
  returningLearnerSession.getSnapshot().modeChosen,
  true,
  "a returning learner who explicitly picked easy still hydrates modeChosen=true",
);
returningLearnerSession.dispose();

const neverChosenSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph, mode: "easy", modeChosen: false }),
});
await neverChosenSession.start();
assert.equal(
  neverChosenSession.getSnapshot().modeChosen,
  false,
  "a project nobody has chosen a mode for hydrates modeChosen=false",
);
neverChosenSession.dispose();

// Fix 2: SET_MODE dispatched while mode hydration is still in flight must
// win over that hydration's response, regardless of which resolves first.
// The in-flight request is held open by a manually-resolved promise (no
// timers, no wall clock), so the interleaving below is deterministic.
let resolveLateMode;
const lateMode = new Promise((resolve) => {
  resolveLateMode = resolve;
});
let signalModeRequested;
const modeRequested = new Promise((resolve) => {
  signalModeRequested = resolve;
});
const raceModeSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph }),
    loadMode() {
      signalModeRequested();
      return lateMode;
    },
  },
});
const raceModeStart = raceModeSession.start();
// Awaiting this signal (instead of guessing a tick count) guarantees
// loadProjectGraph already captured its pre-choice baseline and is now
// blocked on the hydration fetch before SET_MODE is dispatched below.
await modeRequested;
await raceModeSession.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(raceModeSession.getSnapshot().mode, "expert");
assert.equal(raceModeSession.getSnapshot().modeChosen, true);
resolveLateMode({ mode: "easy", chosen: false }); // stale: resolves after the choice
await raceModeStart;
assert.equal(
  raceModeSession.getSnapshot().mode,
  "expert",
  "an explicit SET_MODE mid-flight beats a hydration response that resolves later",
);
assert.equal(
  raceModeSession.getSnapshot().modeChosen,
  true,
  "modeChosen stays true after the race, not reverted by the stale response",
);
raceModeSession.dispose();

// Fix 3: modeChosen must report the unknown state (null), not false, for
// the entire window between start() beginning and mode hydration resolving
// — collapsing the two let ModeControl show the first-run gate over a
// returning learner's galaxy on every load. This adapter's fixture reports
// a project that HAS already had a mode chosen, so any read of `false`
// during the pending window can only be the conflated-state bug, not a
// legitimately unchosen project. The in-flight loadMode() request is held
// open by a manually-resolved promise (no timers, no wall clock), so the
// interleaving below is deterministic — same checkpoint pattern as
// modeRequested above.
{
  let resolvePendingMode;
  const pendingMode = new Promise((resolve) => {
    resolvePendingMode = resolve;
  });
  let signalModePending;
  const modePending = new Promise((resolve) => {
    signalModePending = resolve;
  });
  const unknownModeSession = createLearnerSession({
    adapter: {
      ...createInMemoryLearnerSessionAdapter({ graph, mode: "easy", modeChosen: true }),
      loadMode() {
        signalModePending();
        return pendingMode;
      },
    },
  });
  const unknownModeStart = unknownModeSession.start();
  // Awaiting this signal (instead of guessing a tick count) guarantees the
  // graph has already committed and loadMode() is genuinely in flight
  // before the snapshot is inspected below.
  await modePending;
  assert.equal(
    unknownModeSession.getSnapshot().graph,
    graph,
    "the graph is already visible while mode hydration is still pending — " +
      "a mode failure or delay must never block the galaxy",
  );
  assert.equal(
    unknownModeSession.getSnapshot().modeChosen,
    null,
    "modeChosen must report unknown (null), not false, while hydration is " +
      "still pending — false would make ModeControl show the first-run gate " +
      "over a returning learner",
  );
  resolvePendingMode({ mode: "easy", chosen: true });
  await unknownModeStart;
  assert.equal(
    unknownModeSession.getSnapshot().modeChosen,
    true,
    "hydration resolves modeChosen once the real response lands",
  );
  unknownModeSession.dispose();
}

// Fix 3 (failure resolution): a thrown /api/mode request must resolve the
// unknown state rather than leave it null forever — a permanently null
// modeChosen would leave ModeControl rendering nothing for the rest of the
// session. Resolves to known-and-chosen; see learnerSession.js's
// resolveUnknownModeAfterFailure for the full reasoning.
{
  let rejectMode;
  const failingMode = new Promise((_resolve, reject) => {
    rejectMode = reject;
  });
  const modeFailureSession = createLearnerSession({
    adapter: {
      ...createInMemoryLearnerSessionAdapter({ graph }),
      loadMode() {
        return failingMode;
      },
    },
  });
  const modeFailureStart = modeFailureSession.start();
  rejectMode(new Error("mode request failed"));
  await modeFailureStart;
  assert.equal(
    modeFailureSession.getSnapshot().status,
    "ready",
    "a mode request failure must never block the galaxy from loading",
  );
  assert.equal(
    modeFailureSession.getSnapshot().modeChosen,
    true,
    "a failed mode request resolves to known-and-chosen, never stuck at unknown",
  );
  modeFailureSession.dispose();
}

// Narration: opening a node fetches its explanation as its own request.
{
  const explanationSession = createLearnerSession({
    adapter: createInMemoryLearnerSessionAdapter({
      graph,
      studies: { "python:app.py:run": study },
      explanations: { "python:app.py:run:easy": { status: "ready", summary: { text: "E" } } },
    }),
  });
  await explanationSession.start();
  await explanationSession.dispatch({ type: "SELECT_STUDY_NODE", nodeId: "python:app.py:run" });
  assert.equal(
    explanationSession.getSnapshot().explanation.status,
    "ready",
    "opening a node fetches its narration",
  );
  explanationSession.dispose();
}

// Narration: SET_MODE refetches narration for the open node but must not
// re-request the study payload or checks, which already carry both voices.
{
  let studyCalls = 0;
  let checksCalls = 0;
  const explanationBaseAdapter = createInMemoryLearnerSessionAdapter({
    graph,
    studies: { "python:app.py:run": study },
    checks: { "app.py": firstChecks },
    explanations: {
      "python:app.py:run:easy": { status: "ready", summary: { text: "Easy voice" } },
      "python:app.py:run:expert": { status: "ready", summary: { text: "Expert voice" } },
    },
  });
  const modeRefetchSession = createLearnerSession({
    adapter: {
      ...explanationBaseAdapter,
      loadStudy(...args) {
        studyCalls += 1;
        return explanationBaseAdapter.loadStudy(...args);
      },
      loadChecks(...args) {
        checksCalls += 1;
        return explanationBaseAdapter.loadChecks(...args);
      },
    },
  });
  await modeRefetchSession.start();
  await modeRefetchSession.dispatch({ type: "SELECT_STUDY_NODE", nodeId: "python:app.py:run" });
  await modeRefetchSession.dispatch({ type: "OPEN_CHECKS" });
  assert.equal(
    modeRefetchSession.getSnapshot().explanation.summary.text,
    "Easy voice",
    "narration starts in the hydrated easy mode",
  );
  assert.equal(studyCalls, 1);
  assert.equal(checksCalls, 1);

  await modeRefetchSession.dispatch({ type: "SET_MODE", mode: "expert" });
  assert.equal(
    modeRefetchSession.getSnapshot().explanation.summary.text,
    "Expert voice",
    "SET_MODE refetches narration for the open node",
  );
  assert.equal(studyCalls, 1, "SET_MODE must not refetch the study payload");
  assert.equal(checksCalls, 1, "SET_MODE must not refetch checks");
  modeRefetchSession.dispose();
}

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

// Narration: navigating to a second node while the first node's narration is
// still in flight must cancel it, so a late response never lands in the
// wrong node's panel. A's study data must resolve and hand off into its own
// narration fetch before B is dispatched — dispatching B any earlier trips
// the *study*-level guard inside loadStudy first, so loadExplanation(A) is
// never even called and the narration guard this test is about goes
// unexercised.
let resolveLateExplanation;
const lateExplanation = new Promise((resolve) => {
  resolveLateExplanation = resolve;
});
let signalExplanationRequested;
const explanationRequested = new Promise((resolve) => {
  signalExplanationRequested = resolve;
});
const explanationRaceBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  studies: {
    "python:app.py:run": study,
    "typescript:main.ts:main": { ...study, node: graph.nodes[1] },
  },
  explanations: {
    "typescript:main.ts:main:easy": { status: "ready", summary: { text: "Second node" } },
  },
});
const explanationRaceSession = createLearnerSession({
  adapter: {
    ...explanationRaceBaseAdapter,
    loadExplanation(nodeId, mode, options = {}) {
      if (nodeId === "python:app.py:run") {
        signalExplanationRequested();
        return lateExplanation;
      }
      return explanationRaceBaseAdapter.loadExplanation(nodeId, mode, options);
    },
  },
});
await explanationRaceSession.start();
const staleExplanationRequest = explanationRaceSession.dispatch({
  type: "SELECT_STUDY_NODE",
  nodeId: "python:app.py:run",
});
// Awaiting this signal (instead of guessing a tick count) guarantees A's
// study data already committed and loadExplanation(A) is genuinely in
// flight — the same deterministic-checkpoint pattern as modeRequested above
// — before B is dispatched below.
await explanationRequested;
await explanationRaceSession.dispatch({
  type: "SELECT_STUDY_NODE",
  nodeId: "typescript:main.ts:main",
});
resolveLateExplanation({ status: "ready", summary: { text: "Stale first node" } });
await staleExplanationRequest;
assert.equal(
  explanationRaceSession.getSnapshot().explanation.summary.text,
  "Second node",
  "a late narration response cannot replace the learner's current node",
);
explanationRaceSession.dispose();

// Narration: leaving the study level must actually abort the in-flight
// request, not merely ignore its eventual result — an un-cancelled fetch
// still runs the provider call (and its cost) to completion for nothing.
// This is checked on the AbortSignal directly, isolated from the
// snapshot-guard behaviour already proven above.
{
  let capturedSignal;
  let signalReceived;
  const signalCaptured = new Promise((resolve) => {
    signalReceived = resolve;
  });
  const abortSession = createLearnerSession({
    adapter: {
      ...createInMemoryLearnerSessionAdapter({
        graph,
        studies: { "python:app.py:run": study },
      }),
      loadExplanation(nodeId, mode, options = {}) {
        capturedSignal = options.signal;
        signalReceived();
        return new Promise(() => {}); // never settles; only the signal matters
      },
    },
  });
  await abortSession.start();
  abortSession.dispatch({ type: "SELECT_STUDY_NODE", nodeId: "python:app.py:run" });
  await signalCaptured;
  assert.equal(capturedSignal.aborted, false, "narration starts uncancelled");
  abortSession.dispatch({ type: "RETREAT" });
  assert.equal(
    capturedSignal.aborted,
    true,
    "leaving the study level aborts in-flight narration, not just its stale result",
  );
  abortSession.dispose();
}

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
const responsePayloads = [
  { graph: true },
  { study: true },
  { checks: true },
  { score: true },
  { home: true },
  { mode: "easy" },
  { mode: "expert" },
];
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
assert.deepEqual(await http.loadMode(), { mode: "easy" });
assert.deepEqual(await http.saveMode("expert"), { mode: "expert" });
assert.deepEqual(
  httpCalls.map(([url]) => url),
  [
    "/api/graph",
    "/api/node/node%2Fid/study",
    "/api/regions/region%2Fid/checks",
    "/api/regions/region%2Fid/checks/check%2Fid",
    "/api/entrypoint",
    "/api/mode",
    "/api/mode",
  ],
);
assert.equal(httpCalls[3][1].method, "POST");
assert.equal(httpCalls[3][1].body, JSON.stringify({ selected_ids: ["answer"] }));
assert.equal(httpCalls[4][1].body, JSON.stringify({ node_id: "node/id" }));
assert.equal(httpCalls[6][1].method, "PUT");
assert.equal(httpCalls[6][1].headers["Content-Type"], "application/json");
assert.equal(httpCalls[6][1].body, JSON.stringify({ mode: "expert" }));

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
