import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { ESCAPE_OWNERS, escapeAction, escapeOwner } from "../src/escapeArbiter.js";
import { LEVELS } from "../src/graphData.js";

// Escape precedence used to be an eleven-term disjunction inside App.jsx, plus
// a second shorter copy on the chart stage. `check_focus_handoffs.mjs` could
// only assert that a *substring* appeared in the file. This executes it.

const open = (extra = {}) => ({ ready: true, canRetreat: true, ...extra });

// ── Nothing open: Escape steps back a level ────────────────────────────────

assert.deepEqual(escapeAction(open()), { kind: "retreat" });
assert.equal(escapeOwner(open()), null);

// ── Not ready, or nowhere to retreat to: Escape does nothing ───────────────

assert.equal(escapeAction({ ready: false, canRetreat: true }), null, "a project still loading has no level to leave");
assert.equal(escapeAction(open({ canRetreat: false })), null, "the outermost level is already the way out");
assert.equal(escapeAction(), null, "no facts at all is not an invitation to act");
assert.equal(escapeAction({}), null);

// ── Every surface stands the window handler down ───────────────────────────

// This is the regression the arbiter exists for. Each of these was a term in
// the disjunction, and `railDisclosureOpen` is the one that was missing: it
// closed the Menu *and* retreated a level on one keypress.
const standDown = ["editableFocus", "nativeDialogOpen", "finderOpen", "entrypointOpen"];

// The checks panel and the module index never claimed the key from their own
// subtree, so Escape there did nothing at all while the coach marks teach
// "Escape to come back". The window handler closes them.
const dismissed = [
  ["railDisclosureOpen", "railDisclosure"],
  ["showChecks", "checks"],
  ["sidebarOpen", "sidebar"],
  ["showChart", "chart"],
  ["firstFlightOpen", "firstFlight"],
];
for (const [fact, surface] of dismissed) {
  assert.deepEqual(
    escapeAction(open({ [fact]: true })),
    { kind: "dismiss", surface },
    `${fact} is closed by the window handler, not merely deferred to`,
  );
}
for (const fact of standDown) {
  assert.equal(
    escapeAction(open({ [fact]: true })),
    null,
    `${fact} owns Escape, so the window handler must not also retreat`,
  );
}

// Adding a surface is one entry in one list -- the whole point. If a new fact
// is introduced without one, this catches the omission the disjunction hid.
assert.equal(
  ESCAPE_OWNERS.length,
  standDown.length + dismissed.length,
  "every fact is an owner and every owner is a fact -- a new one cannot be half-wired",
);
assert.equal(
  new Set(ESCAPE_OWNERS.map((owner) => owner.id)).size,
  ESCAPE_OWNERS.length,
  "owner ids are unique",
);

// ── The chart is the one surface the caller closes ─────────────────────────

// The chart yields to anything opened over it. It used to carry a second copy
// of the bail list that knew only about the finder and the sidebar, plus a
// `stopPropagation` to stop the window handler retreating on top of its own
// dismissal -- a race that cannot exist with one handler and one list.
for (const fact of standDown) {
  assert.equal(
    escapeAction(open({ showChart: true, [fact]: true })),
    null,
    `${fact} sits over the chart, so it owns the key -- not the chart`,
  );
}
assert.deepEqual(
  escapeAction(open({ showChart: true, showChecks: true })),
  { kind: "dismiss", surface: "checks" },
  "and to a panel opened over it that the window handler closes",
);
assert.deepEqual(
  escapeAction(open({ showChart: true, firstFlightOpen: true })),
  { kind: "dismiss", surface: "chart" },
  "the chart opened over a flight closes before the flight behind it",
);

// ── Precedence is the list order, innermost first ──────────────────────────

assert.equal(
  escapeOwner(open({ finderOpen: true, showChart: true })).id,
  "finder",
  "the innermost open surface wins, whatever else is open behind it",
);
assert.equal(
  escapeOwner(open({ showChecks: true, sidebarOpen: true })).id,
  "checks",
  "the quiz sits over the module index",
);
assert.equal(
  escapeOwner(open({ editableFocus: true, nativeDialogOpen: true, showChart: true })).id,
  "editableField",
  "typing in a field beats every panel: Escape there is the field's",
);
assert.deepEqual(
  ESCAPE_OWNERS.map((owner) => owner.id),
  [
    "editableField",
    "nativeDialog",
    "railDisclosure",
    "checks",
    "sidebar",
    "finder",
    "entrypoint",
    "chart",
    "firstFlight",
  ],
  "the order is the contract, so a reorder has to be deliberate",
);

assert.deepEqual(
  ESCAPE_OWNERS.filter((owner) => owner.dismissible).map((owner) => owner.id),
  ["railDisclosure", "checks", "sidebar", "chart", "firstFlight"],
  "every dismissible surface needs an entry in App's DISMISS map",
);

// ── A fact the arbiter does not know about changes nothing ─────────────────

assert.deepEqual(
  escapeAction(open({ somethingNew: true })),
  { kind: "retreat" },
  "an unknown fact is not silently treated as an open surface",
);

// Execute the real DOM fact shim and both event handlers: pure arbiter tests
// alone missed a Galaxy Study heading outside the canvas keyboard subtree.
const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const canvas = readFileSync(new URL("../src/GalaxyCanvas.jsx", import.meta.url), "utf8");
const factsSource = app.slice(app.indexOf("function escapeFacts("), app.indexOf("function isEditableTarget("));
const fieldSource = app.slice(app.indexOf("function isEditableTarget("), app.indexOf("function LoadingScreen("));
const windowSource = app.slice(app.indexOf("    function onEscape("), app.indexOf('    window.addEventListener("keydown", onEscape)'));
const canvasSource = canvas.slice(canvas.indexOf("  function handleKeyDown("), canvas.indexOf("  if (renderError)"));
for (const layer of ["galaxy", "map"]) {
  for (const focus of ["study", "frame"]) {
    let snapshot;
    const events = [];
    const doc = { activeElement: { tagName: "H1" }, querySelector: () => null };
    const escapeFacts = new Function("LEVELS", "document", `${factsSource}${fieldSource}; return escapeFacts;`)(LEVELS, doc);
    const session = {
      getSnapshot: () => snapshot,
      dispatch(event) {
        events.push(event.type);
        if (event.type === "RETREAT") snapshot = { ...snapshot, level: snapshot.level === LEVELS.STUDY ? LEVELS.SYSTEM : LEVELS.GALAXY };
      },
    };
    const dismiss = Object.fromEntries(dismissed.map(([, surface]) => [surface, () => events.push(surface)]));
    const onEscape = new Function("escapeAction", "escapeFacts", "session", "firstFlightActiveRef", "DISMISS", `${windowSource}; return onEscape;`)(escapeAction, escapeFacts, session, { current: false }, dismiss);
    const onCanvasKey = new Function("firstFlightActive", "retreatRef", `${canvasSource}; return handleKeyDown;`)(false, { current: () => session.dispatch({ type: "RETREAT" }) });
    const press = (key) => {
      const event = { key, preventDefault() {} };
      if (focus === "frame" && layer === "galaxy") onCanvasKey(event);
      onEscape(event);
    };
    snapshot = { status: "ready", layer, level: LEVELS.STUDY };
    press("Escape");
    assert.deepEqual(events.splice(0), ["RETREAT"], `${layer} ${focus}: Study Escape retreats exactly once`);
    assert.equal(snapshot.level, LEVELS.SYSTEM, `${layer} ${focus}: Study Escape retains its System`);
    press("Escape");
    assert.deepEqual(events.splice(0), ["RETREAT"], `${layer} ${focus}: System Escape retreats exactly once`);
    assert.equal(snapshot.level, LEVELS.GALAXY);
    press("Escape");
    assert.deepEqual(events.splice(0), [], `${layer} ${focus}: Galaxy has nowhere to retreat`);
    for (const [fact, surface] of dismissed) {
      snapshot = { status: "ready", layer, level: LEVELS.STUDY, [fact]: true };
      doc.querySelector = (selector) => fact === "railDisclosureOpen" && selector.startsWith(".rail-overflow") ? {} : null;
      // First Flight is view-local rather than a session field.
      const handler = new Function("escapeAction", "escapeFacts", "session", "firstFlightActiveRef", "DISMISS", `${windowSource}; return onEscape;`)(escapeAction, escapeFacts, session, { current: fact === "firstFlightOpen" }, dismiss);
      const event = { key: "Escape", preventDefault() {} };
      if (focus === "frame" && layer === "galaxy") onCanvasKey(event);
      handler(event);
      assert.deepEqual(events.splice(0), [surface], `${layer} ${focus}: ${surface} closes without retreat`);
      assert.equal(snapshot.level, LEVELS.STUDY);
    }
    for (const fact of standDown) {
      snapshot = { status: "ready", layer, level: LEVELS.STUDY, [fact]: true };
      doc.activeElement = { tagName: fact === "editableFocus" ? "INPUT" : "H1" };
      doc.querySelector = (selector) => fact === "nativeDialogOpen" && selector === "dialog[open]" ? {} : null;
      press("Escape");
      assert.deepEqual(events.splice(0), [], `${layer} ${focus}: ${fact} retains Escape`);
      assert.equal(snapshot.level, LEVELS.STUDY);
    }
    if (layer === "galaxy" && focus === "frame") {
      snapshot = { status: "ready", layer, level: LEVELS.STUDY };
      press("Backspace");
      assert.deepEqual(events, ["RETREAT"], "canvas Backspace retains its one-level retreat");
      assert.equal(snapshot.level, LEVELS.SYSTEM);
    }
  }
}

console.log("escape-arbiter contracts passed");
