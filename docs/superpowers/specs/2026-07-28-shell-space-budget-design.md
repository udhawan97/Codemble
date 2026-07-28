# Shell space budget — design

**Date:** 2026-07-28
**Status:** approved by UD
**Scope:** `web/src/styles.css`, `web/src/App.jsx`, `web/src/MapView.jsx`,
`web/src/learnerProjection.js`, rebuilt `codemble/web_dist`

## Problem

The Easy-mode shell spends more vertical space on chrome than on the stage it
frames. Measured in the served bundle on this repository, Easy mode, Map layer,
module selected:

| | 1280x720 | 375x720 |
| --- | --- | --- |
| header | 221 | 124 |
| stage | 382 | 399 |
| guidance strip | 62 | 142 |
| footer | 55 | 55 |
| **chrome** | **338 (47%)** | **321 (45%)** |
| map tabs | 28 | 64 |
| region copy | 113 | 240 |
| **`.map-canvas`** | **82** | **80** (at its floor) |
| the two `.map-note` rows | 28 + 22 | 94 + 66 |
| column content vs visible | 382 / 382 | **653 / 399 — scrolls** |

`mapview.py` fixes box height at 56px, so 82px is roughly one row of boxes. At
375 the drawing is worse than small: the canvas spans y 482–562 while the stage
ends at y 523, so **41px of an 80px canvas** is on screen — half a box — and the
learner meets tabs, a 240px caption and two stacked buttons first.

This is separate from the truncation fixed in `55147ac`, which replaced a
percentage cap with a `min-block-size: 5rem` floor plus a scrolling column and
deliberately left the floor small. That fix stopped the clipping; the space
shortage behind it was left open, and is what this change addresses.

## Diagnosis

### The header is a horizontal problem billed as a vertical one

`.rail-actions` holds six buttons totalling **913px** including gaps
(Modules 111, Find 103, level-exit 145, Star chart 127, Change Home 157,
Switch project 160). The desktop grid is
`minmax(0, 1fr) auto minmax(0, 1fr)`, so that group is handed **522px** and
wraps to two 44px lines, while `.brand-lockup` is handed an equal 522px for
~147px of content. The header wastes ~390px of *width*, then pays for it in
*height* twice: once in the wrapped button row (104px), and once because
`.rail-controls` (370px wide) is exiled to a row of its own (68px).

Easy mode is barely implicated: Expert measures **201px** against Easy's 221px.
The density tokens cost 20px; the structure costs 180px.

### Repacking alone cannot fix it

Measured variants at 1280, Easy, module selected:

| variant | header | canvas | breadcrumb |
| --- | --- | --- | --- |
| baseline | 221 | 82 | intact |
| free the wasted width, keep all six buttons | 221 | 82 | intact — **no gain** |
| pack actions *and* controls into one row | 137 | 167 | **crushed to 0px** |
| move the two rare buttons to row 2 (hides nothing) | 199 | 105 | intact |
| demote the two rare buttons + float the legend | **148** | **156** | intact |

Minimum viewport width for a single-row header on this repository: 1688px with
all six buttons plus the controls, 1327px with four buttons plus the controls.
Neither fits 1280. Any true one-row header therefore either ellipsises or
erases the breadcrumb — the same class of wrong the 2026-07-21 `short_label`
entry rejects for region ids.

So the header shrinks only if something yields. Keeping all six buttons
permanently visible buys exactly **0px**.

### The column repeats the shell's mistake

Every row in `.map-view` is `flex: 0 0 auto` except `.map-canvas`, which is
`flex: 1 1 auto`. The drawing is the only thing that can absorb a shortfall, so
it absorbs all of it — structurally identical to the percentage cap `55147ac`
removed, one level out.

Two smaller faults sit inside it:

- `.check-launch` carries `margin-block-start: var(--cm-space-sm)` from the
  *floating* orientation variant, while `.orientation-copy__actions` also sets
  `gap: var(--cm-space-sm)`. Every wrapped row pays both, which is why two 44px
  buttons measure 136px rather than 104px.
- The two `.map-note` rows are always-on prose in the same column as the
  drawing: 50px at 1280 and **160px at 375**.

### Guidance duplicates a button already on screen

On the Map, when the learner is already in the recommended region,
`learnerProjection.js:280` returns an action labelled **Read the source** — the
identical button `.orientation-copy--inline` renders directly above it. The
2026-07-21 rule ("the chip renders no button when the next step is already on
screen") predates the Map gaining its own reading path in the same release, so
the two overlap. At 375 the duplicate costs ~50px of a 142px strip while the
diagram is half-visible.

## Design

**Principle: chrome yields to the stage.** Rigid chrome plus one flexible stage
means the stage pays for every shortfall. Each change below either frees width
the header was wasting, or lets a chrome row shrink before the drawing does.

### 1. Header — 221 → 148px at desktop, compact untouched

**1a. Stop the brand claiming an equal third.**
`grid-template-columns` at `min-width: 40rem` becomes
`auto minmax(9rem, auto) minmax(0, 1fr)`. The brand takes its content width;
the breadcrumb keeps a 9rem floor so it can never be crushed; `.rail-actions`
takes the remainder and right-aligns. This buys 0px alone and is what makes 1b
pay.

**1b. Demote `Change Home` and `Switch project` behind the existing
disclosure.** They move into a new `.rail-more` group inside
`.rail-overflow__panel`. At `min-width: 40rem` the panel stays
`display: contents`, so `.rail-actions` and `.rail-controls` still escape as
grid items, while `.rail-more` becomes the absolutely-positioned dropdown and
`.mobile-menu-trigger` becomes visible again labelled **More**.

No new state: `mobileMenuOpen`, the Escape handler, the click-to-close capture
and `mobileMenuRef` already wrap this subtree. The trigger's two labels are two
spans toggled by the media query, so the accessible name follows the breakpoint
without a resize listener.

`Modules`, `Find`, the level-exit and `Star chart` stay permanently visible,
preserving the 2026-07-21 "global surfaces" entry. `Change Home` is first-run
calibration and `Switch project` is once per project.

**1c. Float the Audience legend beside its radios.** `.mode-toggle` 68 → 46px.
It stays a real visible `<legend>` in a real `<fieldset>`, so the accessible
name is unchanged — this is layout, not an accessibility trade.

### 2. Map column

**2a. Drop `.check-launch`'s `margin-block-start` inside
`.orientation-copy__actions`.** The flex row already owns the spacing. −16px at
1280, −32px at 375. The floating variant keeps its margin.

**2b. The two `.map-note` rows share one wrapping row**, each stating its bare
fact, with the explanatory clause behind one disclosure. Both counts — the
unrouted-module count and the unread-language count and name — stay permanently
visible. The Correctness Contract and the 2026-07-27 unsupported-sources entry
require the fact *stated*; they do not require the sentence expanded. The
existing **Show them / Fold them away** control changes the drawing rather than
explaining it, so it stays on the collapsed line.

**2c. Raise `.map-canvas`'s floor** from `5rem` to the largest value that still
leaves an ordinary desktop column unscrolled once 1a–2b have landed. Set from
measurement on this repository, not chosen by taste, and recorded in the rule's
comment. The column keeps `overflow-y: auto` as its honest failure mode.

### 3. Guidance

**3a. The chip drops its action when that action is already on screen.** On the
Map, at SYSTEM level in the recommended region, the hint keeps its message and
reason and returns `action: null`, matching the branch that already does this
for the galaxy at line 290. The hop count and the recommendation are unchanged
graph truth; only a duplicated control is withdrawn.

## Correctness and contract impact

- No parser, graph, check, progress, provider or HTTP behaviour changes.
- No backend geometry changes: `codemble/graph/` and `mapview.py` are untouched,
  and React remains a pure renderer of backend-computed coordinates.
- No token changes: Easy mode's larger type and spacing are a deliberate
  accessibility choice and stay exactly as they are.
- Every fact currently stated on the Map is still stated. Nothing that was
  visible becomes unreachable; two rare controls become one click away through
  a disclosure that already exists at compact widths.
- The 2026-07-21 "global surfaces" entry is preserved: Modules, Find and Star
  chart remain permanent.

## Verification

1. Serve the **built** bundle, not the dev server (this worktree's `codemble`
   CLI is an editable install pointing elsewhere; use
   `PYTHONPATH=$PWD python3 -c "from codemble.cli import main; main()" serve …`).
2. Measure header, stage, guidance, footer, tabs, copy, canvas and notes at
   1280x720, 375 and 320, in Easy and Expert, with and without a module
   selected, on both Map tabs.
3. Confirm the breadcrumb is never truncated or crushed at any tested width.
4. Confirm the Galaxy layer is unchanged, including its floating orientation
   copy.
5. Keyboard path: the desktop **More** disclosure opens, traps nothing, closes
   on Escape and on activating a button, and returns focus to its trigger.
6. Confirm both map notes state their counts while collapsed.
7. Confirm no overlapping interactive rectangles at 320 and 375.
8. `pytest`, `ruff check .`, the frontend contract checks, and a rebuilt
   `codemble/web_dist` that CI's bundle gate accepts.

## Non-goals

- Type and spacing tokens (`tokens.css`, the Easy density block).
- Backend map or graph layout.
- The galaxy layer's floating orientation copy.
- Reordering the map column with CSS `order`: it would put the drawing above
  the caption visually while leaving DOM and focus order behind it, which is a
  known keyboard and screen-reader regression.
- Shrinking the 44px touch targets.
