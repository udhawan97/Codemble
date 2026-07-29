import assert from "node:assert/strict";

import { ESCAPE_OWNERS, escapeAction, escapeOwner } from "../src/escapeArbiter.js";

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
const standDown = ["editableFocus", "nativeDialogOpen", "railDisclosureOpen", "finderOpen", "entrypointOpen"];

// The checks panel and the module index never claimed the key from their own
// subtree, so Escape there did nothing at all while the coach marks teach
// "Escape to come back". The window handler closes them.
const dismissed = [
  ["showChecks", "checks"],
  ["sidebarOpen", "sidebar"],
  ["showChart", "chart"],
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
  ],
  "the order is the contract, so a reorder has to be deliberate",
);

assert.deepEqual(
  ESCAPE_OWNERS.filter((owner) => owner.dismissible).map((owner) => owner.id),
  ["checks", "sidebar", "chart"],
  "every dismissible surface needs an entry in App's DISMISS map",
);

// ── A fact the arbiter does not know about changes nothing ─────────────────

assert.deepEqual(
  escapeAction(open({ somethingNew: true })),
  { kind: "retreat" },
  "an unknown fact is not silently treated as an open surface",
);

console.log("escape-arbiter contracts passed");
