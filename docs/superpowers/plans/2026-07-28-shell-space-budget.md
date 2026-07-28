# Shell space budget — implementation plan

Spec: `docs/superpowers/specs/2026-07-28-shell-space-budget-design.md`

Each commit leaves the app running. Measure on the **built** bundle after each
wave, not the dev server.

## Wave 0 — baseline capture

- Serve the current committed bundle and record header / stage / guidance /
  footer / tabs / copy / canvas / notes at 1280x720, 375, 320 in Easy and
  Expert, module selected and not.
- Keep the numbers; every later wave is measured against them.

No code change.

## Wave 1 — header width and the rare-control disclosure

Files: `web/src/App.jsx`, `web/src/styles.css`

1. `App.jsx`: wrap `Change Home` and `<SwitchProject />` in
   `<div className="rail-more">`, inside `.rail-overflow__panel`, after
   `.rail-actions`. No state, no handler, no ref changes.
2. `App.jsx`: give `.mobile-menu-trigger` two labels —
   `<span className="rail-trigger__compact">Menu</span>` and
   `<span className="rail-trigger__wide">More</span>` — one hidden per
   breakpoint so the accessible name follows the layout.
3. `styles.css`, compact defaults: `.rail-more` is a plain grid inside the
   panel (today's behaviour, everything in one Menu); `.rail-trigger__wide` is
   `display: none`.
4. `styles.css`, `@media (min-width: 40rem)`:
   - `.instrument-rail` columns → `auto minmax(9rem, auto) minmax(0, 1fr)`
   - `.location` keeps `grid-column: 2; grid-row: 1`, drops `text-align: center`
   - `.rail-actions` → `grid-column: 3; grid-row: 1; justify-content: flex-end`
   - `.mobile-menu-trigger` becomes visible again, placed beside the actions
   - `.rail-more` becomes the absolute dropdown anchored to the rail, shown
     only under `.rail-overflow[data-open]`
   - `.rail-trigger__compact` hidden, `.rail-trigger__wide` shown

**Verify:** header 221 → ~170 at 1280; breadcrumb intact at 1280/1024/768;
compact widths byte-identical in behaviour; Escape and click-to-close still
work on both breakpoints; focus returns to the trigger.

## Wave 2 — Audience legend

Files: `web/src/styles.css`

- Float `.mode-toggle__label` so it shares the line with
  `.mode-toggle__options`; keep it a visible `<legend>`.

**Verify:** `.mode-toggle` 68 → 46px, header ~170 → ~148; the legend is still
announced and still visible; Expert mode matches.

## Wave 3 — orientation actions spacing

Files: `web/src/styles.css`

- Scope `.check-launch`'s `margin-block-start` so it applies to the floating
  orientation variant only, not inside `.orientation-copy__actions`.

**Verify:** 1280 copy 113 → ~97; 375 copy 240 → ~208; the galaxy's floating
variant is unchanged.

## Wave 4 — map notes on one row

Files: `web/src/MapView.jsx`, `web/src/styles.css`

- Wrap the unreachable note and the unsupported note in a `.map-notes` row.
- Each note collapses to its bare fact; the explanatory clause moves behind one
  disclosure button for the row.
- **Show them / Fold them away** stays on the collapsed line: it changes the
  drawing, it does not explain it.

**Verify:** both counts readable while collapsed on both tabs; notes 50 → ~22 at
1280 and 160 → ~44 at 375; the disclosure is keyboard reachable.

## Wave 5 — canvas floor

Files: `web/src/styles.css`

- Raise `.map-canvas`'s `min-block-size` to the largest value that still leaves
  an ordinary desktop column unscrolled after waves 1–4. Measure it; record the
  measurement in the comment.

**Verify:** no desktop column scrollbar at 1280x720 in Easy or Expert; the
column still scrolls rather than clips at 320; a 3x longer caption still never
clips.

## Wave 6 — guidance stops duplicating

Files: `web/src/learnerProjection.js`, plus a contract check

- In the `layer === "map"` branch, when the learner is already at SYSTEM level
  in the recommended region and the region panel renders its own
  **Read the source** button, return the hint with `action: null` and
  `actionLabel: null`, keeping message and reason.
- Add a frontend contract assertion covering it.

**Verify:** at 1280 and 375, the strip shows the message with no duplicate
button when the region panel offers the same action; the button returns when
the recommendation points elsewhere.

## Wave 7 — verification and bundle

- Full matrix from the spec's Verification section.
- `pytest`, `ruff check .`, frontend contract checks.
- `cd web && npm run build`; confirm CI's bundle gate accepts the result
  (a fresh rebuild must reproduce the committed bundle).

## Wave 8 — docs, changelog, release

- `/update-docs` across README, `docs-site/`, and the changelog.
- CLAUDE.md: Current State + Decision Log entries.
- Version bump, tag, release.
