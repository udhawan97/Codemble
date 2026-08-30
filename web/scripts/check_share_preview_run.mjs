import assert from "node:assert/strict";

import { createSharePreviewRun } from "../src/sharePreviewRun.js";

const requestIds = ["create-1", "create-2", "confirm-1"];
const run = createSharePreviewRun({
  requestIdFactory: () => requestIds.shift(),
});

let snapshot = run.getSnapshot();
assert.equal(snapshot.phase, "closed");

snapshot = run.dispatch({ type: "OPEN" });
assert.equal(snapshot.phase, "choosing");
assert.deepEqual(snapshot.focusRequest, { id: 1, target: "close" });

snapshot = run.dispatch({ type: "BEGIN_CREATE" });
assert.equal(snapshot.phase, "compiling");
assert.equal(snapshot.activeRequestId, "create-1");

snapshot = run.dispatch({ type: "RESTART" });
assert.equal(snapshot.phase, "choosing");
assert.deepEqual(snapshot.focusRequest, { id: 2, target: "selected-lifetime" });
const restarted = snapshot;

snapshot = run.dispatch({
  type: "CREATE_SUCCEEDED",
  requestId: "create-1",
  preview: { preview_id: "stale" },
});
assert.equal(snapshot, restarted, "a restarted run refuses its stale create response");

snapshot = run.dispatch({ type: "BEGIN_CREATE" });
assert.equal(snapshot.activeRequestId, "create-2");
const preview = {
  preview_id: "preview-2",
  payload_digest: "sha256:preview-2",
  exposure: {
    labels_included: true,
    understanding_included: false,
  },
};
snapshot = run.dispatch({
  type: "CREATE_SUCCEEDED",
  requestId: "create-2",
  preview,
});
assert.equal(snapshot.phase, "inspecting");
assert.equal(snapshot.preview, preview);
assert.deepEqual(snapshot.focusRequest, { id: 3, target: "artifact" });
assert.equal(snapshot.readyToConfirm, false);

run.dispatch({ type: "SET_ACKNOWLEDGEMENT", name: "reviewed", value: true });
snapshot = run.dispatch({
  type: "SET_ACKNOWLEDGEMENT",
  name: "labelsConfirmed",
  value: true,
});
assert.equal(snapshot.readyToConfirm, true);
assert.deepEqual(snapshot.acknowledgements, {
  reviewed: true,
  labelsConfirmed: true,
  understandingConfirmed: false,
});

snapshot = run.dispatch({ type: "BEGIN_CONFIRM" });
assert.equal(snapshot.phase, "confirming");
assert.equal(snapshot.activeRequestId, "confirm-1");

const confirming = snapshot;
snapshot = run.dispatch({
  type: "CONFIRM_FAILED",
  requestId: "wrong-request",
  error: "stale",
});
assert.equal(snapshot, confirming, "a run refuses a response for another request");

const confirmation = { status: "confirmed", preview_id: "preview-2" };
snapshot = run.dispatch({
  type: "CONFIRM_SUCCEEDED",
  requestId: "confirm-1",
  confirmation,
});
assert.equal(snapshot.phase, "confirmed");
assert.equal(snapshot.confirmation, confirmation);
assert.deepEqual(snapshot.focusRequest, { id: 4, target: "confirmation" });

snapshot = run.dispatch({ type: "RELEASE_PROJECT" });
assert.equal(snapshot.phase, "closed");
assert.equal(snapshot.preview, null);
assert.equal(snapshot.confirmation, null);

console.log("share preview run contracts passed");
