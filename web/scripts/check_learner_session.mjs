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
assert.deepEqual(
  await adapter.loadMode(),
  { mode: "expert", chosen: true },
  "PUT reached the adapter, and writing a mode records it as chosen",
);
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
assert.equal(
  snapshot.pendingDawnRegionId,
  "app.py",
  "a light-up also queues a pending dawn, independent of the toast",
);
assert.equal(pendingTimers.size, 1);
pendingTimers.values().next().value();
assert.equal(session.getSnapshot().litRegionId, null);
assert.equal(
  session.getSnapshot().pendingDawnRegionId,
  "app.py",
  "the pending dawn outlives the toast's 520ms timer -- it is consumed when the dawn actually runs, never timed out",
);

// A stale CONSUME_DAWN for some other region id (e.g. a race with a newer
// light-up) must leave this pending dawn alone.
await session.dispatch({ type: "CONSUME_DAWN", regionId: "does-not-match" });
assert.equal(
  session.getSnapshot().pendingDawnRegionId,
  "app.py",
  "a mismatched CONSUME_DAWN leaves the real pending dawn untouched",
);
await session.dispatch({ type: "CONSUME_DAWN", regionId: "app.py" });
assert.equal(
  session.getSnapshot().pendingDawnRegionId,
  null,
  "CONSUME_DAWN clears the pending dawn once GalaxyCanvas has claimed it",
);

await session.dispatch({ type: "RETREAT" });
assert.equal(
  session.getSnapshot().entrypointOpen,
  true,
  "a graph with no selected Home opens the picker on load",
);
await session.dispatch({ type: "SELECT_ENTRYPOINT", nodeId: "python:app.py:run" });
assert.equal(session.getSnapshot().graph, understoodGraph);
assert.equal(
  session.getSnapshot().entrypointOpen,
  false,
  "choosing Home closes the picker",
);
await session.dispatch({ type: "DISMISS_ENTRYPOINT" });
assert.equal(session.getSnapshot().entrypointDismissed, true);
assert.equal(session.getSnapshot().entrypointOpen, false);

// Regression: CHANGE_HOME must clear a *genuine* STUDY state, not just find
// fields that were already empty. Drive all the way into STUDY with the
// chart open first, so each assertion below would fail if the handler
// stopped clearing that field.
await session.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await session.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
await session.dispatch({ type: "SHOW_CHART" });
let studySnapshot = session.getSnapshot();
assert.equal(studySnapshot.level, LEVELS.STUDY, "setup reached a genuine study state");
assert.equal(studySnapshot.selectedNode?.id, "python:app.py:run");
assert.equal(studySnapshot.studyData?.node.id, "python:app.py:run");
assert.equal(studySnapshot.explanation?.summary.text, "easy voice");
assert.equal(studySnapshot.showChart, true);

await session.dispatch({ type: "CHANGE_HOME" });
let homeSnapshot = session.getSnapshot();
assert.equal(homeSnapshot.entrypointOpen, true, "Change Home reopens the picker");
assert.equal(homeSnapshot.level, LEVELS.GALAXY, "Home is a galaxy-level decision");
assert.equal(homeSnapshot.selectedNode, null, "Change Home clears the selected node");
assert.equal(homeSnapshot.studyData, null, "Change Home clears study data");
assert.equal(homeSnapshot.studyError, "", "Change Home clears study error");
assert.equal(homeSnapshot.explanation, null, "Change Home clears the narration");
assert.equal(homeSnapshot.explanationError, "", "Change Home clears the narration error");
assert.equal(
  homeSnapshot.explanationLoading,
  false,
  "Change Home clears the narration loading flag",
);
assert.equal(homeSnapshot.showChart, false, "Change Home closes the star chart");
await session.dispatch({ type: "DISMISS_ENTRYPOINT" });
await session.dispatch({ type: "SHOW_CHART" });
assert.equal(session.getSnapshot().showChart, true);
await session.dispatch({ type: "HIDE_CHART" });
assert.equal(session.getSnapshot().showChart, false);
assert(notifications > 0);

unsubscribe();
session.dispose();

// Regression: a pending dawn must not survive a project reset -- it is
// discarded, not carried into whatever project the learner picks next.
const dawnResetSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({
    graph,
    checks: { "app.py": firstChecks },
    submissions: {
      "app.py:calls": {
        result: { correct: true, region_understood: true },
        graph: understoodGraph,
        checks: passedChecks,
      },
    },
  }),
  clock,
});
await dawnResetSession.start();
await dawnResetSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await dawnResetSession.dispatch({
  type: "SUBMIT_CHECK",
  checkId: "calls",
  selectedIds: ["python:app.py:run"],
});
assert.equal(dawnResetSession.getSnapshot().pendingDawnRegionId, "app.py");
await dawnResetSession.dispatch({ type: "RESET_PROJECT" });
assert.equal(
  dawnResetSession.getSnapshot().pendingDawnRegionId,
  null,
  "a project reset discards a pending dawn instead of carrying it into the next project",
);
dawnResetSession.dispose();

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
          file_count: 1420,
          scale_cap: 1000,
          root: "/home/u/big",
          suggestions: [{ path: "api", file_count: 900 }],
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
assert.equal(scaleResult.file_count, 1420);
assert.equal(
  JSON.parse(pickerHttpCalls.at(-1).options.body).path,
  "/home/u/big",
);

// A refusal carries the server's own sentence, not its status code: the picker
// path field is the first control that can reach a 403, and "Folder listing
// returned 403." tells a learner nothing about what to do next.
const detailedAdapter = createHttpLearnerSessionAdapter(async (url) => {
  if (url.startsWith("/api/picker/browse")) {
    return {
      ok: false,
      status: 403,
      json: async () => ({ detail: "Choose a folder inside your home directory." }),
    };
  }
  // A refusal with no JSON body at all still has to produce a message.
  return { ok: false, status: 500, json: async () => { throw new Error("not json"); } };
});
await assert.rejects(
  () => detailedAdapter.browsePicker("/etc"),
  /^Error: Choose a folder inside your home directory\.$/,
  "a browse refusal shows the server's sentence",
);
await assert.rejects(
  () => detailedAdapter.loadGraph(),
  /^Error: Graph request returned 500\.$/,
  "a refusal with no detail still falls back to the labelled status",
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
        file_count: 1420,
        scale_cap: 1000,
        root: "/home/u/big",
        suggestions: [{ path: "api", file_count: 900 }],
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
assert.equal(pickerSnapshot.picker.scale.file_count, 1420);
assert.equal(pickerSnapshot.picker.path, "/home/u/big");
assert.equal(pickerSnapshot.picker.busy, false);

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "ready");
assert.equal(pickerSnapshot.picker, null);
assert.equal(pickerSnapshot.graph, graph);

await pickerSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await pickerSession.dispatch({ type: "RESET_PROJECT" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "picking", "reset returns the learner to the picker");
assert.equal(pickerSnapshot.graph, null);
assert.equal(pickerSnapshot.region, null);
assert.equal(pickerSnapshot.selectedNode, null);
assert.equal(pickerSnapshot.level, LEVELS.GALAXY);
assert.equal(pickerSnapshot.studiedNodeIds.size, 0);
assert.equal(pickerSnapshot.explanation, null);
assert.equal(pickerSnapshot.llmStatus, null);
assert.equal(pickerSnapshot.picker.path, "/home/u");

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
assert.equal(pickerSession.getSnapshot().status, "ready", "a project can be re-picked");

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

// Phase B: layer, map tab, map data, coach-marks, and the derived hint.
const mapPayload = {
  schema_version: 1,
  architecture: { home: "app.py", boxes: [], edges: [], groups: [], unreachable: [] },
  workflow: { root: null, nodes: [], unreachable: [] },
};
// Home (app.py) is understood so it cannot shadow main.ts as the nearest
// unlit region -- the fixture default `mode: "easy"` on
// createInMemoryLearnerSessionAdapter would otherwise also flip this
// session's default layer to "map" before the first assertion below, so
// mode is pinned to "expert" explicitly.
const layerSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({
      graph: makeGraph({ understood: true }),
      mode: "expert",
    }),
    async fetchMap() {
      return mapPayload;
    },
  },
  clock,
});
await layerSession.start();
assert.equal(
  layerSession.getSnapshot().layer,
  "galaxy",
  "expert mode lands on the galaxy",
);
assert.equal(layerSession.getSnapshot().mapTab, "architecture");
assert.equal(layerSession.getSnapshot().coachmarksSeen, false);

await layerSession.dispatch({ type: "SET_LAYER", layer: "map" });
let layerSnapshot = layerSession.getSnapshot();
assert.equal(layerSnapshot.layer, "map");
assert.equal(layerSnapshot.mapData, mapPayload, "switching to map fetches it once");
assert.equal(layerSnapshot.mapError, "");

await layerSession.dispatch({ type: "SET_MAP_TAB", tab: "workflow" });
assert.equal(layerSession.getSnapshot().mapTab, "workflow");

await layerSession.dispatch({ type: "DISMISS_COACHMARKS" });
assert.equal(layerSession.getSnapshot().coachmarksSeen, true);
assert.equal(
  layerSession.getSnapshot().coachmarksSeen,
  true,
  "dismissing coach-marks is sticky within a session",
);
await layerSession.dispatch({ type: "SET_LAYER", layer: "galaxy" });
assert.equal(
  layerSession.getSnapshot().coachmarksSeen,
  true,
  "coach-marks never return after a layer change",
);

// The hint is expert-mode-silent and graph-derived.
assert.equal(layerSession.getSnapshot().hint, null, "expert mode shows no hint");
await layerSession.dispatch({ type: "SET_MODE", mode: "easy" });
layerSnapshot = layerSession.getSnapshot();
// The most recent explicit choice is now "galaxy" (dispatched above to prove
// coach-marks survive a layer change), so that -- not the earlier "map" --
// is what must survive this mode flip.
assert.equal(layerSnapshot.layer, "galaxy", "an explicit layer choice survives a mode flip");
assert.equal(
  layerSnapshot.hint.regionId,
  "main.ts",
  "the hint is the nearest unlit region to Home",
);
assert.equal(layerSnapshot.hint.hops, Infinity, "an unrouted region still reports its distance");
layerSession.dispose();

// Easy mode defaults to the map layer when the learner has not chosen one.
// makeGraph's `understood` flag only marks the Home region (app.py); mark
// main.ts understood too so this graph is genuinely fully understood.
const fullyUnderstoodGraph = makeGraph({ understood: true });
fullyUnderstoodGraph.regions[1].understood = true;
fullyUnderstoodGraph.nodes[1].understood = true;
let easyMapFetchCount = 0;
const easySession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph: fullyUnderstoodGraph }),
    async fetchMap() {
      easyMapFetchCount += 1;
      return mapPayload;
    },
    async loadMode() {
      return { mode: "easy", chosen: true };
    },
  },
  clock,
});
await easySession.start();
assert.equal(easySession.getSnapshot().layer, "map", "easy mode lands on the map");
// Regression (carried-over fix): applyMode() used to set layer:"map" for a
// persisted Easy mode without ever calling loadMap(), so a learner whose
// mode was already Easy on load landed on a Map stuck loading forever.
assert.equal(
  easySession.getSnapshot().mapData,
  mapPayload,
  "a persisted easy mode must load the map itself, not strand the learner on a permanent loading state",
);
assert.equal(
  easySession.getSnapshot().mapError,
  "",
  "the map that loaded from the mode default carries no error",
);
assert.equal(
  easyMapFetchCount,
  1,
  "landing on the map by mode default fetches it exactly once, never a duplicate",
);
assert.equal(
  easySession.getSnapshot().hint,
  null,
  "a fully understood project has nothing to hint at",
);
easySession.dispose();

// A map failure is scoped to the map layer and never breaks the galaxy.
const mapFailureSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph }),
    async fetchMap() {
      throw new Error("map unavailable");
    },
  },
  clock,
});
await mapFailureSession.start();
await mapFailureSession.dispatch({ type: "SET_LAYER", layer: "map" });
const failureSnapshot = mapFailureSession.getSnapshot();
assert.equal(failureSnapshot.mapError, "map unavailable");
assert.equal(failureSnapshot.mapData, null);
assert.equal(failureSnapshot.status, "ready", "a map failure never downs the session");
mapFailureSession.dispose();

// The HTTP adapter hits the documented URL.
const mapCalls = [];
const mapHttp = createHttpLearnerSessionAdapter(async (url) => {
  mapCalls.push(url);
  return { ok: true, async json() { return mapPayload; } };
});
assert.deepEqual(await mapHttp.fetchMap(), mapPayload);
assert.deepEqual(mapCalls, ["/api/map"]);

console.log("phase B layer + map contracts passed");

// --- progressive reveal through the session ---------------------------------

function revealGraph() {
  const ids = ["home", "near", "mid", "far"];
  return {
    project_root: "/tmp/reveal",
    nodes: ids.map((id) => ({
      id,
      name: id,
      language: "python",
      region: id,
      file: `src/${id}.py`,
      understood: false,
    })),
    edges: [],
    entrypoint_candidates: ["home"],
    selected_entrypoint: "home",
    file_hashes: Object.fromEntries(ids.map((id) => [`src/${id}.py`, id])),
    concept_annotations: [],
    regions: ids.map((id, index) => ({
      id,
      language: "python",
      home: index === 0,
      understood: false,
      community: 0,
      centrality: 0,
      loc: 1,
      hops_from_home: index,
    })),
    region_edges: [
      { src: "home", dst: "near", certain: true, weight: 1 },
      { src: "near", dst: "mid", certain: true, weight: 1 },
      { src: "mid", dst: "far", certain: true, weight: 1 },
    ],
    partial_files: [],
  };
}

const revealSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph: revealGraph() }),
  clock,
});
await revealSession.start();

assert.deepEqual(
  [...revealSession.getSnapshot().revealedRegionIds].sort(),
  ["home", "mid", "near"],
  "a first run opens on the floor, never an empty sky and never the whole hairball",
);
assert.deepEqual(
  revealSession.getSnapshot().moduleIndex.map((row) => row.label),
  ["far.py", "home.py", "mid.py", "near.py"],
  "the index lists every module the parser found, charted or not",
);

// Walking into a region reveals its neighbours while it is the subject.
await revealSession.dispatch({ type: "GO_TO_REGION", regionId: "far" });
assert.equal(revealSession.getSnapshot().region.id, "far");
assert.equal(
  revealSession.getSnapshot().finderOpen,
  false,
  "a jump closes the finder in the same commit, so it cannot land over the new scene",
);
assert.ok(
  revealSession.getSnapshot().revealedRegionIds.has("far"),
  "the region the learner is standing in is always charted",
);

// Show all is a view preference: it changes the drawing, never the graph.
const beforeToggle = revealSession.getSnapshot().focusedGraph.regions.length;
await revealSession.dispatch({ type: "TOGGLE_SHOW_ALL" });
assert.equal(revealSession.getSnapshot().showAll, true);
assert.deepEqual(
  [...revealSession.getSnapshot().revealedRegionIds].sort(),
  ["far", "home", "mid", "near"],
);
assert.equal(
  revealSession.getSnapshot().focusedGraph.regions.length,
  beforeToggle,
  "Show all reveals; it must not add or remove a single region",
);
await revealSession.dispatch({ type: "TOGGLE_SHOW_ALL" });
assert.equal(revealSession.getSnapshot().showAll, false);
revealSession.dispose();

// A lit region permanently earns its neighbours, with no Show all involved.
const litGraph = revealGraph();
litGraph.regions = litGraph.regions.map((region) =>
  region.id === "far" ? { ...region, understood: true } : region,
);
const litSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph: litGraph }),
  clock,
});
await litSession.start();
assert.deepEqual(
  [...litSession.getSnapshot().revealedRegionIds].sort(),
  ["far", "home", "mid", "near"],
  "proving a region charts it and its import neighbours for good",
);
litSession.dispose();

console.log("reveal contracts passed");

// A failing mode write reverts the optimistic value: mode is a preference,
// never truth, so the UI must not claim a setting the server refused.
const modeFailureAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "easy" });
const modeFailureSession = createLearnerSession({
  adapter: {
    ...modeFailureAdapter,
    saveMode() {
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
// must win over the stale loadMode value it raced with, and llmStatus from
// that same response must still apply.
let resolveRaceStatus;
const raceStatus = new Promise((resolve) => {
  resolveRaceStatus = resolve;
});
let notifyStatusRequested;
const statusRequested = new Promise((resolve) => {
  notifyStatusRequested = resolve;
});
const preferencesRaceAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "expert" });
const preferencesRaceSession = createLearnerSession({
  adapter: {
    ...preferencesRaceAdapter,
    fetchLlmStatus() {
      notifyStatusRequested();
      return raceStatus;
    },
  },
  clock,
});
const preferencesRaceStart = preferencesRaceSession.start();
await statusRequested;
await preferencesRaceSession.dispatch({ type: "SET_MODE", mode: "easy" });
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
await preferencesRaceStart;
assert.equal(
  preferencesRaceSession.getSnapshot().mode,
  "easy",
  "a mode change that races the preferences load wins over the stale loadMode value",
);
assert.equal(
  preferencesRaceSession.getSnapshot().llmStatus.ollama.recommended,
  "gemma4:12b",
  "llmStatus from the same preferences response still applies",
);
preferencesRaceSession.dispose();

// A failing narration request must leave the structural evidence untouched.
const narrationFailureAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  studies: { "python:app.py:run": study },
});
const narrationFailureSession = createLearnerSession({
  adapter: {
    ...narrationFailureAdapter,
    loadExplanation() {
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

// A refused reset must surface to the caller and leave the project bound.
// `status` is what makes this a *refusal* rather than an unreachable server:
// createHttpLearnerSessionAdapter stamps it on every error it raises from a
// real HTTP response, and resetProject() keys the two failure modes off it.
const refusedResetAdapter = createInMemoryLearnerSessionAdapter({ graph });
const refusedResetSession = createLearnerSession({
  adapter: {
    ...refusedResetAdapter,
    resetProject() {
      throw httpRefusal("Project reset returned 409.", 409);
    },
  },
  clock,
});
await refusedResetSession.start();
await assert.rejects(
  () => refusedResetSession.dispatch({ type: "RESET_PROJECT" }),
  /Project reset returned 409\./,
);
assert.equal(
  refusedResetSession.getSnapshot().graph,
  graph,
  "a refused reset leaves the bound project exactly as it was",
);
refusedResetSession.dispose();

// Regression: a stale SELECT_ENTRYPOINT response arriving after RESET_PROJECT
// must not resurrect the old project. resetProject() must abort
// entrypointController like cancelStudy() aborts study/explanation, and
// selectEntrypoint() must check lifecycle like loadProjectGraph/loadPreferences.
let resolveStaleEntrypoint;
const staleEntrypoint = new Promise((resolve) => {
  resolveStaleEntrypoint = resolve;
});
const entrypointRaceBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [{ name: "demo", path: "/home/u/demo" }],
      },
    },
    recents: [],
    selections: { "/home/u/demo": { state: "ready" } },
  },
});
const entrypointRaceSession = createLearnerSession({
  adapter: { ...entrypointRaceBaseAdapter, selectEntrypoint: () => staleEntrypoint },
  clock,
});
await entrypointRaceSession.start();
await entrypointRaceSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
assert.equal(entrypointRaceSession.getSnapshot().status, "ready");

const staleEntrypointRequest = entrypointRaceSession.dispatch({
  type: "SELECT_ENTRYPOINT",
  nodeId: "python:app.py:run",
});
await entrypointRaceSession.dispatch({ type: "RESET_PROJECT" });
assert.equal(
  entrypointRaceSession.getSnapshot().status,
  "picking",
  "reset returns to the picker while the entrypoint request is still in flight",
);

resolveStaleEntrypoint(understoodGraph);
await staleEntrypointRequest;
const entrypointRaceSnapshot = entrypointRaceSession.getSnapshot();
assert.equal(
  entrypointRaceSnapshot.status,
  "picking",
  "a stale entrypoint response must not move the session off the picker",
);
assert.equal(
  entrypointRaceSnapshot.graph,
  null,
  "a stale entrypoint response after reset must not resurrect the old project's graph",
);
entrypointRaceSession.dispose();

// Regression: RESET_PROJECT must clear map-layer state too, not just
// graph/study/entrypoint state -- otherwise project A's architecture and
// workflow trees stay in mapData after the learner switches to project B.
const mapClearBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  mode: "expert",
  map: mapPayload,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [{ name: "demo", path: "/home/u/demo" }],
      },
    },
    recents: [],
    selections: { "/home/u/demo": { state: "ready" } },
  },
});
const mapClearSession = createLearnerSession({ adapter: mapClearBaseAdapter, clock });
await mapClearSession.start();
await mapClearSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
await mapClearSession.dispatch({ type: "SET_LAYER", layer: "map" });
assert.equal(
  mapClearSession.getSnapshot().mapData,
  mapPayload,
  "setup: project A's map really loaded before reset",
);

await mapClearSession.dispatch({ type: "RESET_PROJECT" });
const mapClearSnapshot = mapClearSession.getSnapshot();
assert.equal(mapClearSnapshot.status, "picking", "reset returns to the picker");
assert.equal(mapClearSnapshot.mapData, null, "reset clears the previous project's map data");
assert.equal(mapClearSnapshot.mapError, "", "reset clears any previous map error too");
mapClearSession.dispose();

// Regression: a map fetch that was in flight for the old project at reset
// time must not be able to commit into the new session when it later
// resolves -- same class of bug as the SELECT_ENTRYPOINT race above.
// resetProject() must abort mapController like it aborts entrypointController,
// and loadMap() must check lifecycle like loadProjectGraph/selectEntrypoint,
// because an adapter that ignores the abort signal still resolves.
let resolveLateMap;
const lateMap = new Promise((resolve) => {
  resolveLateMap = resolve;
});
const mapRaceBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  mode: "expert",
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [{ name: "demo", path: "/home/u/demo" }],
      },
    },
    recents: [],
    selections: { "/home/u/demo": { state: "ready" } },
  },
});
const mapRaceSession = createLearnerSession({
  adapter: { ...mapRaceBaseAdapter, fetchMap: () => lateMap },
  clock,
});
await mapRaceSession.start();
await mapRaceSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
assert.equal(mapRaceSession.getSnapshot().status, "ready");

const staleMapRequest = mapRaceSession.dispatch({ type: "SET_LAYER", layer: "map" });
await mapRaceSession.dispatch({ type: "RESET_PROJECT" });
assert.equal(
  mapRaceSession.getSnapshot().status,
  "picking",
  "reset returns to the picker while the map request is still in flight",
);
assert.equal(mapRaceSession.getSnapshot().mapData, null);

resolveLateMap(mapPayload);
await staleMapRequest;
assert.equal(
  mapRaceSession.getSnapshot().mapData,
  null,
  "a stale map response after reset must not resurrect the old project's map",
);
mapRaceSession.dispose();

// Regression: both Map payloads are computed *from* Home -- Architecture
// layers the regions by import depth from it, Workflow is the call tree rooted
// at it -- so SELECT_ENTRYPOINT must invalidate the cached map exactly as
// RESET_PROJECT does. Left alone, the header named the Home the learner had
// just chosen while the Map still drew the diagram built from the old one, and
// nothing told them the structure on screen no longer matched the project.
const newHomeMapPayload = {
  schema_version: 1,
  architecture: { home: "main.ts", boxes: [], edges: [], groups: [], unreachable: [] },
  workflow: { root: "typescript:main.ts:main", nodes: [], unreachable: [] },
};
const homeMapFetches = [];
const homeMapSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({
      graph,
      mode: "expert",
      entrypoints: { "python:app.py:run": understoodGraph },
    }),
    async fetchMap() {
      homeMapFetches.push(true);
      return homeMapFetches.length === 1 ? mapPayload : newHomeMapPayload;
    },
  },
  clock,
});
await homeMapSession.start();
await homeMapSession.dispatch({ type: "SET_LAYER", layer: "map" });
assert.equal(
  homeMapSession.getSnapshot().mapData,
  mapPayload,
  "setup: the old Home's map really is on screen before Home changes",
);

await homeMapSession.dispatch({
  type: "SELECT_ENTRYPOINT",
  nodeId: "python:app.py:run",
});
const homeMapSnapshot = homeMapSession.getSnapshot();
assert.notEqual(
  homeMapSnapshot.mapData,
  mapPayload,
  "a new Home must not leave the previous Home's diagram on the Map",
);
assert.equal(
  homeMapSnapshot.mapData,
  newHomeMapPayload,
  "the Map the learner is looking at is refetched for the Home they just chose",
);
assert.equal(homeMapSnapshot.mapError, "");
assert.equal(
  homeMapFetches.length,
  2,
  "changing Home refetches the visible map exactly once, never a duplicate",
);
homeMapSession.dispose();

// The other half of the same fix: a map fetch still in flight for the *old*
// Home when the learner picks a new one must be aborted and must not commit
// when it later resolves -- the same class as the RESET_PROJECT races above,
// and the abort alone would miss an adapter that resolves instead of rejecting.
let resolveOldHomeMap;
const oldHomeMap = new Promise((resolve) => {
  resolveOldHomeMap = resolve;
});
const homeMapRaceFetches = [];
const homeMapRaceSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({
      graph,
      mode: "expert",
      entrypoints: { "python:app.py:run": understoodGraph },
    }),
    fetchMap() {
      homeMapRaceFetches.push(true);
      return homeMapRaceFetches.length === 1
        ? oldHomeMap
        : Promise.resolve(newHomeMapPayload);
    },
  },
  clock,
});
await homeMapRaceSession.start();
const oldHomeMapRequest = homeMapRaceSession.dispatch({
  type: "SET_LAYER",
  layer: "map",
});
await homeMapRaceSession.dispatch({
  type: "SELECT_ENTRYPOINT",
  nodeId: "python:app.py:run",
});
assert.equal(
  homeMapRaceSession.getSnapshot().mapData,
  newHomeMapPayload,
  "the new Home's map lands while the old Home's fetch is still outstanding",
);

resolveOldHomeMap(mapPayload);
await oldHomeMapRequest;
assert.equal(
  homeMapRaceSession.getSnapshot().mapData,
  newHomeMapPayload,
  "a late map response for the previous Home must not repaint the new Home's Map",
);
homeMapRaceSession.dispose();

// Regression: the Map's `understood` flags (mapview.py, per region and per
// node) come from the same graph a passed check reloads, so a region that
// just finished its checks invalidates the cached map exactly as a new Home
// does above. Left uncleared, the galaxy lit the region while the Map --
// Easy mode's default layer, the exact audience the light-up is the reward
// for -- kept drawing it dim, with no error to notice.
const understoodMapPayload = {
  schema_version: 1,
  architecture: { home: "app.py", boxes: [], edges: [], groups: [], unreachable: [] },
  workflow: { root: null, nodes: [], unreachable: [] },
};
const checkMapFetches = [];
const checkMapSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({
      graph,
      mode: "expert",
      checks: { "app.py": firstChecks },
      submissions: {
        // A wrong answer: neither correct nor region_understood, so this
        // must not spend a map refetch either.
        "app.py:wrong": { result: { correct: false, region_understood: false } },
        "app.py:calls": {
          result: { correct: true, region_understood: true },
          graph: understoodGraph,
          checks: passedChecks,
        },
      },
    }),
    async fetchMap() {
      checkMapFetches.push(true);
      return checkMapFetches.length === 1 ? mapPayload : understoodMapPayload;
    },
  },
  clock,
});
await checkMapSession.start();
await checkMapSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await checkMapSession.dispatch({ type: "SET_LAYER", layer: "map" });
assert.equal(
  checkMapSession.getSnapshot().mapData,
  mapPayload,
  "setup: the not-yet-understood map really is on screen before any check is submitted",
);

await checkMapSession.dispatch({ type: "OPEN_CHECKS" });
await checkMapSession.dispatch({ type: "SUBMIT_CHECK", checkId: "wrong", selectedIds: [] });
assert.equal(
  checkMapSession.getSnapshot().mapData,
  mapPayload,
  "a submission that does not finish the region must not refetch the map",
);
assert.equal(
  checkMapFetches.length,
  1,
  "an answer that leaves the region unfinished pays for no extra map fetch",
);

await checkMapSession.dispatch({
  type: "SUBMIT_CHECK",
  checkId: "calls",
  selectedIds: ["python:app.py:run"],
});
const checkMapSnapshot = checkMapSession.getSnapshot();
assert.equal(
  checkMapSnapshot.region.understood,
  true,
  "setup: the region really is understood now",
);
assert.notEqual(
  checkMapSnapshot.mapData,
  mapPayload,
  "a region passing its checks must not leave the previous map payload on screen",
);
assert.equal(
  checkMapSnapshot.mapData,
  understoodMapPayload,
  "the Map the learner is looking at is refetched once the region lights up",
);
assert.equal(checkMapSnapshot.mapError, "");
assert.equal(
  checkMapFetches.length,
  2,
  "a passed region refetches the visible map exactly once, never a duplicate",
);
checkMapSession.dispose();

// Regression: the mode toggle and Switch project sit in the same always-
// rendered header, so a learner can flip Easy/Expert and confirm the switch
// before PUT /api/mode answers. If that write then fails, setMode's rollback
// belongs to the project that is gone -- committing it would push the previous
// project's mode into the new session, and because Easy defaults to the Map
// layer it would also fire a second, spurious map fetch. resetProject() must
// abort modeController like it aborts entrypointController/mapController, and
// setMode() must re-check lifecycle across the await, because an adapter that
// ignores the abort signal still settles.
let rejectStaleMode;
const staleMode = new Promise((_resolve, reject) => {
  rejectStaleMode = reject;
});
const modeRaceFetchedMaps = [];
const modeRaceBaseAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  mode: "easy",
  map: mapPayload,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [{ name: "demo", path: "/home/u/demo" }],
      },
    },
    recents: [],
    selections: { "/home/u/demo": { state: "ready" } },
  },
});
const modeRaceSession = createLearnerSession({
  adapter: {
    ...modeRaceBaseAdapter,
    saveMode: () => staleMode,
    fetchMap(options) {
      modeRaceFetchedMaps.push(options);
      return modeRaceBaseAdapter.fetchMap(options);
    },
  },
  clock,
});
await modeRaceSession.start();
await modeRaceSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
assert.equal(
  modeRaceSession.getSnapshot().mode,
  "easy",
  "setup: project A hydrated Easy, which lands the learner on the Map layer",
);
assert.equal(modeRaceSession.getSnapshot().layer, "map");
assert.equal(modeRaceFetchedMaps.length, 1, "setup: Easy fetched project A's map once");

const staleModeRequest = modeRaceSession.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(
  modeRaceSession.getSnapshot().mode,
  "expert",
  "setup: the mode applies optimistically while the write is in flight",
);
await modeRaceSession.dispatch({ type: "RESET_PROJECT" });
assert.equal(
  modeRaceSession.getSnapshot().status,
  "picking",
  "reset returns to the picker while the mode write is still in flight",
);

rejectStaleMode(new Error("Mode write returned 500."));
await staleModeRequest;
const modeRaceSnapshot = modeRaceSession.getSnapshot();
assert.equal(
  modeRaceSnapshot.mode,
  "expert",
  "a failed mode write for the released project must not roll its mode into the next one",
);
assert.equal(
  modeRaceSnapshot.modeChosen,
  true,
  "nor may it resurrect the released project's never-chosen state",
);
assert.equal(
  modeRaceSnapshot.layer,
  "galaxy",
  "nor drag the new session onto the previous project's default layer",
);
assert.equal(
  modeRaceFetchedMaps.length,
  1,
  "and the rolled-back layer must not fire a second map fetch after reset",
);
modeRaceSession.dispose();

// A project that already carries a Home must not greet the learner with the
// picker; the affordance is opt-in from the header instead.
const homeGraph = { ...makeGraph(), selected_entrypoint: "python:app.py:run" };
const seededHomeSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph: homeGraph }),
  clock,
});
await seededHomeSession.start();
assert.equal(seededHomeSession.getSnapshot().entrypointDismissed, true);
assert.equal(seededHomeSession.getSnapshot().entrypointOpen, false);
await seededHomeSession.dispatch({ type: "CHANGE_HOME" });
assert.equal(seededHomeSession.getSnapshot().entrypointOpen, true);
seededHomeSession.dispose();

// Hover is view state: it must survive redundant events cheaply and must never
// outlive the view it described.
const hoverSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph }),
  clock,
});
await hoverSession.start();
assert.equal(hoverSession.getSnapshot().hoverNodeId, null);
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: "app.py" });
assert.equal(hoverSession.getSnapshot().hoverNodeId, "app.py");
const hoverBefore = hoverSession.getSnapshot();
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: "app.py" });
assert.equal(
  hoverSession.getSnapshot(),
  hoverBefore,
  "a repeated hover does not produce a new snapshot",
);
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: null });
assert.equal(hoverSession.getSnapshot().hoverNodeId, null);
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: "app.py" });
await hoverSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
assert.equal(
  hoverSession.getSnapshot().hoverNodeId,
  null,
  "moving between levels drops the stale hover target",
);
hoverSession.dispose();

// Regression: the 2D map draws every module the parser found, including ones
// the current language focus hides, so a box can name a region that is absent
// from the focused projection. Resolving that id in React handed `undefined` to
// ADVANCE, which dereferenced `node.id` straight into the error boundary --
// and Easy mode *defaults* to the map layer, so this was one click deep.
const focusedOutSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph }),
  clock,
});
await focusedOutSession.start();
await focusedOutSession.dispatch({ type: "SET_LANGUAGE_FOCUS", language: "python" });
assert.deepEqual(
  focusedOutSession.getSnapshot().focusedGraph.regions.map((region) => region.id),
  ["app.py"],
  "the focus really does hide the TypeScript region",
);
await focusedOutSession.dispatch({ type: "ADVANCE_REGION", regionId: "main.ts" });
let focusedOutSnapshot = focusedOutSession.getSnapshot();
assert.equal(focusedOutSnapshot.region.id, "main.ts", "the named region is entered");
assert.equal(focusedOutSnapshot.level, LEVELS.SYSTEM);
assert.equal(
  focusedOutSnapshot.languageFocus,
  "typescript",
  "the focus widens to the module the learner named, as SELECT_STUDY_NODE does",
);
assert.equal(focusedOutSnapshot.error, "", "no failure reaches the learner");
// An id no region carries is a caller bug, not a crash.
await focusedOutSession.dispatch({ type: "ADVANCE_REGION", regionId: "nope.py" });
assert.equal(focusedOutSession.getSnapshot().region.id, "main.ts");
// The same guard on the node-object path: ADVANCE must survive a missing node.
await focusedOutSession.dispatch({ type: "ADVANCE", node: undefined });
focusedOutSnapshot = focusedOutSession.getSnapshot();
assert.equal(focusedOutSnapshot.region.id, "main.ts");
assert.equal(focusedOutSnapshot.level, LEVELS.SYSTEM);
focusedOutSession.dispose();

// Regression: a merge left both a parallel (`void`) and a sequential (`await`)
// narration fetch in loadStudy. Two requests per study open meant call 2 aborted
// call 1, silently killing the parallel behaviour and double-hitting the
// provider. Exactly one request per open, and it must not wait for the study.
let explanationCalls = 0;
let studyResolved = false;
const narrationOnceSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({
      graph,
      studies: { "python:app.py:run": study },
      explanations: { "python:app.py:run:easy": { summary: { text: "easy voice" } } },
    }),
    async loadStudy(nodeId) {
      await Promise.resolve();
      studyResolved = true;
      return study;
    },
    async loadExplanation() {
      explanationCalls += 1;
      assert.equal(
        studyResolved,
        false,
        "narration starts beside the study fetch, not after it",
      );
      return { summary: { text: "easy voice" } };
    },
  },
  clock,
});
await narrationOnceSession.start();
await narrationOnceSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await narrationOnceSession.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
assert.equal(explanationCalls, 1, "one study open issues exactly one narration request");
narrationOnceSession.dispose();

// The earlier illumination assertion fires its timer without deleting it, so
// start the Phase C blocks from a clean timer map.
pendingTimers.clear();

// Phase C: a 202 select drives a polled loading screen, not a frozen tab.
const parseFixture = () => ({
  graph,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [{ name: "demo", path: "/home/u/demo" }],
      },
    },
    recents: [],
    selections: { "/home/u/demo": { state: "parsing" } },
    // The session seeds stage "discovering" itself from the 202, so the first
    // served payload is the first real server observation.
    progress: [
      {
        state: "parsing",
        stage: "parsing",
        files_done: 640,
        files_total: 1000,
        error: null,
      },
      {
        state: "ready",
        stage: null,
        files_done: 1000,
        files_total: 1000,
        error: null,
      },
    ],
  },
});

const parseSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter(parseFixture()),
  clock,
});
await parseSession.start();
await parseSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
let parseSnapshot = parseSession.getSnapshot();
assert.equal(parseSnapshot.status, "picking");
assert.equal(parseSnapshot.picker.busy, true);
assert.equal(parseSnapshot.parseProgress.stage, "discovering");
assert.equal(parseSnapshot.parseProgress.path, "/home/u/demo");
assert.equal(pendingTimers.size, 1, "a parsing poll is scheduled, not spun");

await fireOnlyTimer();
parseSnapshot = parseSession.getSnapshot();
assert.equal(parseSnapshot.parseProgress.stage, "parsing");
assert.equal(parseSnapshot.parseProgress.files_done, 640);
assert.equal(parseSnapshot.parseProgress.files_total, 1000);

await fireOnlyTimer();
parseSnapshot = parseSession.getSnapshot();
assert.equal(parseSnapshot.status, "ready");
assert.equal(parseSnapshot.parseProgress, null);
assert.equal(parseSnapshot.graph, graph);
assert.equal(pendingTimers.size, 0, "polling stops once the parse is ready");
parseSession.dispose();

// A crashed parse thread surfaces in-app and the same path can be retried.
const failing = parseFixture();
failing.picker.progress = [
  { state: "error", stage: null, files_done: 3, files_total: 9, error: "boom" },
];
const failSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter(failing),
  clock,
});
await failSession.start();
await failSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
await fireOnlyTimer();
let failSnapshot = failSession.getSnapshot();
assert.equal(failSnapshot.status, "picking");
assert.equal(failSnapshot.parseProgress, null);
assert.equal(failSnapshot.picker.busy, false, "a failed parse re-arms the picker");
assert.equal(failSnapshot.picker.error, "boom");
assert.equal(pendingTimers.size, 0, "a failed parse stops the loop, it does not retry it");
failSession.dispose();

// A poll failure backs off and reports honestly instead of going silent.
const flaky = parseFixture();
const flakyBase = createInMemoryLearnerSessionAdapter(flaky);
let progressCalls = 0;
const flakySession = createLearnerSession({
  adapter: {
    ...flakyBase,
    async fetchParseProgress(options = {}) {
      progressCalls += 1;
      if (progressCalls === 1) throw new Error("network hiccup");
      return flakyBase.fetchParseProgress(options);
    },
  },
  clock,
});
await flakySession.start();
await flakySession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
await fireOnlyTimer();
let flakySnapshot = flakySession.getSnapshot();
assert.equal(flakySnapshot.parseProgress.pollError, "network hiccup");
assert.equal(flakySnapshot.parseProgress.attempts, 1);
assert.equal(pendingTimers.size, 1, "a failed poll retries with backoff");
await fireOnlyTimer();
flakySnapshot = flakySession.getSnapshot();
assert.equal(flakySnapshot.parseProgress.pollError, "");
assert.equal(flakySnapshot.parseProgress.attempts, 0);
assert.equal(pendingTimers.size, 1, "setup: a poll really is still scheduled at dispose");
flakySession.dispose();
assert.equal(
  pendingTimers.size,
  0,
  "unmounting mid-parse clears the scheduled poll: a leaked loop would keep " +
    "hitting a server the learner has already walked away from",
);

// Reset during a parse cancels the poll and returns to the picker.
const cancelSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter(parseFixture()),
  clock,
});
await cancelSession.start();
await cancelSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
assert.equal(pendingTimers.size, 1);
await cancelSession.dispatch({ type: "RESET_PROJECT" });
const cancelSnapshot = cancelSession.getSnapshot();
assert.equal(cancelSnapshot.parseProgress, null);
assert.equal(pendingTimers.size, 0, "reset cancels the scheduled poll");
cancelSession.dispose();

// Regression: the escape hatch must not depend on the server it is escaping.
// A learner watching a parse whose server has died sees the poll fail forever;
// "Cancel and pick another project" is their only way out, and it used to run
// the local teardown *after* awaiting the reset request -- so when that request
// rejected, stopPolling() and the commit that returns to the picker were both
// skipped and the learner was trapped on the loading screen with no way back.
{
  const strandedAdapter = createInMemoryLearnerSessionAdapter(parseFixture());
  const strandedSession = createLearnerSession({
    adapter: {
      ...strandedAdapter,
      // Not a refusal: no HTTP response ever arrived, which is exactly what a
      // killed server looks like from the browser.
      resetProject() {
        return Promise.reject(networkFailure());
      },
    },
    clock,
  });
  await strandedSession.start();
  await strandedSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  assert.equal(
    strandedSession.getSnapshot().parseProgress.stage,
    "discovering",
    "setup: the learner really is on the loading screen",
  );
  assert.equal(pendingTimers.size, 1, "setup: the poll loop really is running");

  await strandedSession.dispatch({ type: "RESET_PROJECT" });
  const strandedSnapshot = strandedSession.getSnapshot();
  assert.equal(
    strandedSnapshot.parseProgress,
    null,
    "an unreachable server must not keep the learner on the loading screen",
  );
  assert.equal(
    pendingTimers.size,
    0,
    "the local teardown runs even when the reset request never reaches a server",
  );
  assert.equal(
    strandedSnapshot.status,
    "picking",
    "cancelling against a dead reset endpoint still returns the learner to the picker",
  );
  strandedSession.dispose();
}

// The whole-server-gone case: every endpoint is unreachable, so start() cannot
// rebuild the picker either. The learner must still leave the loading screen,
// and the screen they land on must say what is actually wrong -- "Failed to
// fetch" is the browser's words for it and names nothing they can act on.
{
  // Alive through the setup, then killed mid-parse -- the learner's exact
  // sequence, and the only way the loading screen is reachable at all.
  let serverDead = false;
  const deadServerBase = createInMemoryLearnerSessionAdapter(parseFixture());
  const whenAlive = (method) => (...args) =>
    serverDead ? Promise.reject(networkFailure()) : deadServerBase[method](...args);
  const deadServerSession = createLearnerSession({
    adapter: {
      ...deadServerBase,
      resetProject: whenAlive("resetProject"),
      loadPickerState: whenAlive("loadPickerState"),
      loadGraph: whenAlive("loadGraph"),
      browsePicker: whenAlive("browsePicker"),
      loadRecents: whenAlive("loadRecents"),
    },
    clock,
  });
  await deadServerSession.start();
  await deadServerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  assert.equal(deadServerSession.getSnapshot().parseProgress.stage, "discovering");
  serverDead = true;

  await deadServerSession.dispatch({ type: "RESET_PROJECT" });
  const deadSnapshot = deadServerSession.getSnapshot();
  assert.equal(
    deadSnapshot.parseProgress,
    null,
    "a completely unreachable server still lets the learner off the loading screen",
  );
  assert.equal(pendingTimers.size, 0, "and stops the poll loop on the way out");
  assert.equal(deadSnapshot.status, "error");
  assert.match(
    deadSnapshot.error,
    /local server/i,
    "the error names the local server rather than repeating the browser's 'Failed to fetch'",
  );
  assert.match(
    deadSnapshot.error,
    /codemble/i,
    "and tells the learner the one command that brings it back",
  );
  deadServerSession.dispose();
}

// The other half of the same distinction: a server that answered and refused
// still holds the project, so the app must stay exactly where it is. Blanking
// it here would desync the browser from a server that is still bound.
{
  const refusedDuringParseSession = createLearnerSession({
    adapter: {
      ...createInMemoryLearnerSessionAdapter(parseFixture()),
      resetProject() {
        return Promise.reject(httpRefusal("Project reset returned 409.", 409));
      },
    },
    clock,
  });
  await refusedDuringParseSession.start();
  await refusedDuringParseSession.dispatch({
    type: "SELECT_PROJECT",
    path: "/home/u/demo",
  });
  await assert.rejects(
    () => refusedDuringParseSession.dispatch({ type: "RESET_PROJECT" }),
    /Project reset returned 409\./,
    "a refusal from a live server still surfaces inline to the caller",
  );
  const refusedSnapshot = refusedDuringParseSession.getSnapshot();
  assert.equal(
    refusedSnapshot.parseProgress.stage,
    "discovering",
    "a refused reset leaves the loading screen up: the parse is still bound server-side",
  );
  assert.equal(refusedSnapshot.status, "picking");
  assert.equal(pendingTimers.size, 1, "and the poll loop keeps running");
  refusedDuringParseSession.dispose();
  pendingTimers.clear();
}

// A brief poll blip may really be nothing, so the first failures keep the
// reassuring copy. A sustained outage may not be reassured about at all: after
// POLL_OUTAGE_ATTEMPTS consecutive failures (~18s of widening backoff) the
// session says so, and the loading screen swaps in copy that stops implying the
// parse is fine and points at restarting `codemble`.
{
  const outageSession = createLearnerSession({
    adapter: {
      ...createInMemoryLearnerSessionAdapter(parseFixture()),
      fetchParseProgress: () => Promise.reject(networkFailure()),
    },
    clock,
  });
  await outageSession.start();
  await outageSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  await fireOnlyTimer();
  assert.equal(outageSession.getSnapshot().parseProgress.attempts, 1);
  assert.equal(
    outageSession.getSnapshot().parseProgress.pollOutage,
    false,
    "one failed poll is a blip, not an outage",
  );
  for (let attempt = 2; attempt < 8; attempt += 1) {
    await fireOnlyTimer();
    assert.equal(
      outageSession.getSnapshot().parseProgress.pollOutage,
      false,
      `${attempt} failures is still inside the blip window`,
    );
  }
  await fireOnlyTimer();
  const outageSnapshot = outageSession.getSnapshot();
  assert.equal(outageSnapshot.parseProgress.attempts, 8);
  assert.equal(
    outageSnapshot.parseProgress.pollOutage,
    true,
    "a sustained outage is reported as one, instead of reassuring forever",
  );
  assert.equal(
    outageSnapshot.parseProgress.pollError,
    "Failed to fetch",
    "the raw failure is still carried for the learner to report",
  );
  assert.equal(pendingTimers.size, 1, "an outage keeps retrying; it just stops over-promising");
  outageSession.dispose();
  pendingTimers.clear();
}

// The discriminator's foundation: the HTTP adapter must stamp the response
// status on the errors it raises, or resetProject cannot tell a live server's
// refusal from a server that is not there at all.
{
  const statusStampAdapter = createHttpLearnerSessionAdapter(async () => ({
    ok: false,
    status: 409,
    json: async () => ({ detail: "Already bound." }),
  }));
  const refusal = await statusStampAdapter.resetProject().catch((error) => error);
  assert.equal(refusal.message, "Already bound.");
  assert.equal(refusal.status, 409, "an HTTP refusal carries the status that produced it");

  const deadAdapter = createHttpLearnerSessionAdapter(async () => {
    throw networkFailure();
  });
  const unreachable = await deadAdapter.resetProject().catch((error) => error);
  assert.equal(
    unreachable.status,
    undefined,
    "a request that never reached a server carries no status to key off",
  );
}

// Regression class: a poll issued for a selection the learner has already
// abandoned must not commit when it later resolves. The abort alone would miss
// an adapter that ignores the signal and resolves anyway -- and this one lands
// `state: "ready"`, so committing it would bind a project that was released.
let resolveStalePoll;
const stalePoll = new Promise((resolve) => {
  resolveStalePoll = resolve;
});
const staleParseSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter(parseFixture()),
    fetchParseProgress: () => stalePoll,
  },
  clock,
});
await staleParseSession.start();
await staleParseSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
// Not awaited: the poll is now suspended on the deferred response above.
const stalePollRun = fireOnlyTimer();
await staleParseSession.dispatch({ type: "RESET_PROJECT" });
assert.equal(staleParseSession.getSnapshot().status, "picking");
assert.equal(staleParseSession.getSnapshot().parseProgress, null);

resolveStalePoll({
  state: "ready",
  stage: null,
  files_done: 9,
  files_total: 9,
  error: null,
});
await stalePollRun;
const staleParseSnapshot = staleParseSession.getSnapshot();
assert.equal(
  staleParseSnapshot.status,
  "picking",
  "a superseded poll must not bind the project the learner just released",
);
assert.equal(staleParseSnapshot.graph, null);
assert.equal(staleParseSnapshot.parseProgress, null);
assert.equal(pendingTimers.size, 0, "nor may it restart the loop it belonged to");
staleParseSession.dispose();

// Clearing progress reloads the graph so lit systems dim again.
const clearAdapter = createInMemoryLearnerSessionAdapter({ graph: understoodGraph });
let cleared = 0;
const clearSession = createLearnerSession({
  adapter: {
    ...clearAdapter,
    async clearProgress(options = {}) {
      cleared += 1;
      return { understood_regions: 0 };
    },
    async loadGraph(options = {}) {
      return cleared ? graph : understoodGraph;
    },
  },
  clock,
});
await clearSession.start();
assert.equal(clearSession.getSnapshot().region.understood, true);
await clearSession.dispatch({ type: "CLEAR_PROGRESS" });
assert.equal(cleared, 1);
assert.equal(clearSession.getSnapshot().graph, graph);
assert.equal(clearSession.getSnapshot().region.understood, false);
clearSession.dispose();

// The same stale-generation guard on the clear path: the reload that follows
// the DELETE belongs to the project that asked for it. Left unguarded it fires
// into whatever session replaced it -- and against an unbound one that is a
// 409 painted over the picker.
let resolveLateClear;
const lateClear = new Promise((resolve) => {
  resolveLateClear = resolve;
});
let clearGraphLoads = 0;
const clearRaceSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph }),
    clearProgress: () => lateClear,
    async loadGraph() {
      clearGraphLoads += 1;
      return graph;
    },
  },
  clock,
});
await clearRaceSession.start();
assert.equal(clearGraphLoads, 1, "setup: the session loaded its graph once");
const staleClear = clearRaceSession.dispatch({ type: "CLEAR_PROGRESS" });
clearRaceSession.dispose();
resolveLateClear({ understood_regions: 0 });
await staleClear;
assert.equal(
  clearGraphLoads,
  1,
  "a clear that outlives its session must not refetch into the next one",
);

// HTTP adapter: exact URLs and the 202 mapping.
const phaseCCalls = [];
const phaseCHttp = createHttpLearnerSessionAdapter(async (url, options = {}) => {
  phaseCCalls.push({ url, options });
  if (url === "/api/picker/select") {
    return { ok: true, status: 202, json: async () => ({ state: "parsing" }) };
  }
  return { ok: true, status: 200, json: async () => ({ state: "parsing" }) };
});
assert.deepEqual(await phaseCHttp.selectProject("/home/u/demo"), {
  state: "parsing",
});
await phaseCHttp.fetchParseProgress();
await phaseCHttp.clearProgress();
assert.deepEqual(
  phaseCCalls.map(({ url }) => url),
  ["/api/picker/select", "/api/picker/progress", "/api/progress"],
);
assert.equal(phaseCCalls.at(-1).options.method, "DELETE");

async function fireOnlyTimer() {
  assert.equal(pendingTimers.size, 1, "exactly one timer must be pending");
  const [timerId, callback] = pendingTimers.entries().next().value;
  pendingTimers.delete(timerId);
  await callback();
}

// The two shapes a failed request can take, mirroring what the real HTTP
// adapter produces: a refusal always arrives with the status of the response
// that carried it; an unreachable server never produces a response at all, so
// fetch itself rejects with a bare TypeError.
function httpRefusal(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function networkFailure(message = "Failed to fetch") {
  return new TypeError(message);
}

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
