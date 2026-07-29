/**
 * Who owns the Escape key right now.
 *
 * There is one key and eight things that can be open over the stage, so
 * precedence has to be decided somewhere. It used to be decided by an
 * eleven-term disjunction inside App.jsx -- plus a second, shorter copy of the
 * same list on the chart stage -- which meant adding a global surface required
 * remembering to extend both. Forgetting has already shipped: the rail
 * disclosure closed *and* the level retreated on one keypress, and the comment
 * added with the eventual fix says so in the code ("This always double-fired").
 *
 * Here it is an ordered list. A new surface is one entry, in one file, and the
 * order says outright which one wins.
 *
 * Nothing in this module touches the DOM or the session. The caller gathers the
 * facts -- some from the session snapshot, some necessarily from the document,
 * because a native dialog's open state and a disclosure's open state are view
 * facts with no session field -- and this decides what they mean.
 */

/**
 * Ordered innermost-first: the first open surface owns the key.
 *
 * `dismissible` says whether the *caller* closes it. The rest own Escape
 * themselves -- a native `<dialog>` closes itself, a field's Escape belongs to
 * the field, and the finder, rail disclosure and entrypoint picker each carry
 * their own handler -- so the only thing the window handler does for them is
 * stand down.
 *
 * The checks panel and the module index are dismissible because neither ever
 * claimed the key from its own subtree: Escape there did nothing at all, while
 * the coach marks teach "Escape to come back". The chart is dismissible for a
 * sharper reason -- it *did* claim the key, in a second handler that then had
 * to call `stopPropagation` so the window handler would not re-read a session
 * it had already changed and retreat a level on top of the dismissal. One
 * handler asking one ordered list cannot race itself.
 */
export const ESCAPE_OWNERS = Object.freeze([
  { id: "editableField", open: (facts) => facts.editableFocus === true, dismissible: false },
  { id: "nativeDialog", open: (facts) => facts.nativeDialogOpen === true, dismissible: false },
  { id: "railDisclosure", open: (facts) => facts.railDisclosureOpen === true, dismissible: false },
  { id: "checks", open: (facts) => facts.showChecks === true, dismissible: true },
  { id: "sidebar", open: (facts) => facts.sidebarOpen === true, dismissible: true },
  { id: "finder", open: (facts) => facts.finderOpen === true, dismissible: false },
  { id: "entrypoint", open: (facts) => facts.entrypointOpen === true, dismissible: false },
  { id: "chart", open: (facts) => facts.showChart === true, dismissible: true },
]);

/**
 * The surface that owns Escape, or `null` when nothing does.
 *
 * @param {object} facts
 * @returns {{id: string, dismissible: boolean}|null}
 */
export function escapeOwner(facts) {
  const owner = ESCAPE_OWNERS.find((candidate) => candidate.open(facts ?? {}));
  return owner ? { id: owner.id, dismissible: owner.dismissible } : null;
}

/**
 * What Escape should do, given everything currently on screen.
 *
 * - `{kind: "dismiss", surface}` -- close that surface and return focus to the
 *   control that opened it. Only ever a surface marked `dismissible`.
 * - `{kind: "retreat"}` -- nothing is open, so step back a level.
 * - `null` -- do nothing: either a surface is handling the key itself, or
 *   retreating is not meaningful here.
 *
 * Retreat is deliberately narrow. It is the Map's documented way back; the
 * Galaxy has its own canvas-level handler, and the galaxy level is already the
 * outermost place there is.
 */
export function escapeAction(facts = {}) {
  if (facts.ready !== true) return null;
  const owner = escapeOwner(facts);
  if (owner) return owner.dismissible ? { kind: "dismiss", surface: owner.id } : null;
  if (!facts.canRetreat) return null;
  return { kind: "retreat" };
}
