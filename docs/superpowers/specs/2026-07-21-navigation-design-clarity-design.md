# Navigation & design clarity — galaxy legibility overhaul

**Date:** 2026-07-21
**Status:** approved by UD
**Supersedes nothing.** Extends `2026-07-19-galaxy-ux-overhaul-design.md`.

## Problem

A tester opened a 169-system TypeScript galaxy and could not use it. Their words:
*"How am I expected to navigate here? Even inside a view you cannot move around
or change anything to see things better. This looks overwhelming without any
guidance or differentiation."*

Four separate defects converge on that one feeling:

1. **The camera cannot move.** `GalaxyCanvas.jsx` sets
   `.enableNavigationControls(false)` and drives two hardcoded `cameraPosition`
   calls. There is no orbit, pan, or zoom at any level.
2. **169 nameless dots, no index.** No star carries a label; hovering one at a
   time is the only way to learn a name. There is no search and no list. The
   import communities computed in `layout.py` place related modules together but
   nothing on screen draws the grouping.
3. **Edges outshine stars.** `galaxyData` emits every `region_edge`
   unconditionally while stars are 5–24 size specks at camera z=310, so the
   route mesh wins the pixel fight.
4. **Chrome eats the stage.** `orientation-copy` renders a display-size `h1` over
   the left half of the canvas at galaxy *and* system level — at system level
   that is a full module path wrapping to three lines — and the legend is a
   twelve-row always-on wall that clips off-screen.

Defects 2–4 are renderer problems: the graph already knows every fact needed to
fix them. Defect 1 is a product invariant and required an owner decision.

## Decisions taken in this design

| # | Decision | Consequence |
| --- | --- | --- |
| 1 | Camera gains **bounded orbit**, not free flight | Amends the `❌ Free-flight 3D navigation` Non-Goal; needs a Decision Log entry |
| 2 | Galaxy uses **progressive reveal**, not a new constellation tier | Semantic zoom keeps exactly three levels |
| 3 | Reveal is **understanding-driven *and* interaction-driven, with a Show-all toggle** | Three reveal sources, one derived set |
| 4 | Labels are **ranked, decluttered, always on** | Names visible at rest without becoming a text hairball |
| 5 | Find is **command palette *and* index sidebar** | Two surfaces, one shared index |
| 6 | Headline and legend are **demoted to a compact bar** | Canvas regains its full stage |

## A. Camera — bounded orbit

Switch the renderer to `controlType('orbit')` and enable navigation controls,
then clamp every degree of freedom that could strand a learner:

- **Pan disabled** (`controls.enablePan = false`). Translation away from the
  subject is never possible, so the "you cannot get lost" guarantee survives.
- **Target locked** to the current level's anchor: galaxy origin at `GALAXY`,
  the region's centre at `SYSTEM`, the selected node at `STUDY`. Entering a
  level re-anchors the target and re-applies the clamps.
- **Distance clamped** per level via `minDistance`/`maxDistance`, so the camera
  can neither enter a star nor retreat into empty space.
- **Polar angle clamped** (`minPolarAngle`/`maxPolarAngle`) so the galaxy plane
  never flips or goes edge-on to nothing.
- Scripted fly-to transitions are unchanged. Orbit governs only what the learner
  does *after* the transition lands.

**Wheel conflict.** The wheel currently changes level (`handleWheel`). Orbit zoom
also claims the wheel. Resolution: the wheel becomes zoom; level changes move to
click, `Enter`, `Escape`, and the breadcrumb. The `GALAXY_STEPS` coach-mark copy
that teaches scroll-to-advance is rewritten to teach orbit and click.

**Verification assumption.** `3d-force-graph` 1.80 is expected to expose the
underlying controls object via `.controls()` and to accept `controlType('orbit')`
at construction. The first implementation step verifies both against the
installed package before anything else is built on them.

## B. Progressive reveal

### Backend — `hops_from_home`

`Region` gains one additive field, `hops_from_home: int | None`: breadth-first
distance from the Home region over `region_edges`, treated as undirected, `None`
where no import route reaches the region. Computed in `layout.py` beside the
existing community pass, from parser-proven routes only. Graph schema goes 5 → 6.

This is parser-derived truth about the project, so it belongs in the graph layer.
It is deterministic: BFS over a sorted adjacency built from already-sorted
`region_edges`.

`with_entrypoint` recomputes the field, because changing Home changes every
distance.

### Frontend — the revealed set

Owned by `learnerSession.js`, never by React. The revealed set is:

```
floor          = { region | hops_from_home <= 2 }        # always, so run one is never empty
earned         = { neighbours of every lit region }      # permanent, grows with understanding
transient      = { neighbours of the current selection } # while it is the subject
revealed       = floor ∪ earned ∪ transient              # unless showAll
```

`showAll` is a per-project persisted toggle that reveals everything.

A region outside the revealed set is **not deleted**. It renders as a faint
unexplored marker carrying no label and no edges, and it remains clickable. The
project's true size stays honest — hiding a module entirely would be the kind of
wrong a learner cannot detect. Dropping the edges of unrevealed regions is what
dissolves the hairball, so no separate edge-density control is needed.

The compact bar states the ratio: `42 of 169 charted`.

## C. Labels

Sprite labels are added inside `makeMarker`, showing the **basename only**
(`ReliabilityDiagram.tsx`), never the full module path.

- **Rank:** Home first, then lit regions, then centrality descending, then
  camera distance ascending. All four inputs are graph truth or camera state.
- **Budget** scales with camera distance — roughly 12 labels at the far clamp,
  roughly 40 at the near clamp.
- **Declutter:** project label anchors into screen-space grid cells and keep only
  the highest-ranked label per cell. Recomputed on a throttled tick (~10 Hz),
  never per frame.
- Hover always labels its target, ignoring the budget.

Unrevealed regions are never labelled.

## D. Find — palette and sidebar

Both surfaces consume one derived `moduleIndex`: `{ id, basename, path, language,
community, communityName, lit, hops, centrality }`. There is no second source of
truth, and both respect the active language focus.

- **Command palette** — `Cmd/Ctrl-K` opens a filter-as-you-type list. `Enter`
  reveals the target if hidden, flies the camera to it, and selects it. Available
  in both the Galaxy and the Map layer.
- **Index sidebar** — a collapsible left rail listing every module grouped by
  community. A community's name is the longest shared path prefix of its members,
  falling back to the member count when members share no prefix. Rows show lit
  state. Clicking a row performs the same action as palette `Enter`.

## E. Chrome demotion

- The `orientation-copy` `h1` becomes one line of body text in the header rail:
  `169 systems · 42 charted · 1 unchartable`.
- At `SYSTEM` level the full module path becomes a breadcrumb, not a display
  heading.
- The legend collapses behind a `Key` disclosure button whose open state persists.

## F. Scope

| Surface | Receives |
| --- | --- |
| Galaxy layer | A, B, C, D, E |
| Map layer | D and E only — it is 2D, so orbit does not apply, and its boxes already carry labels |
| Untouched | Study panel, checks, parser output, palette and theme values |

Explicitly **not** built: an edge-density slider, and any colour or contrast
customisation. Reveal already de-noises edges, and `design.md` locks the palette
under a WCAG 4.5:1 floor. Both can follow later if reveal alone does not land.

## Correctness Contract compliance

- `hops_from_home` derives from parser-proven `region_edges` only; unreachable is
  `None`, never a guessed large number.
- Unrevealed regions stay present and clickable, so reveal never hides the
  project's real size or shape.
- Labels print `Node`/`Region` identifiers verbatim; no name is synthesised.
- Community names are the members' own shared path prefix, and fall back to a
  count rather than inventing a theme name.
- Uncertainty encoding is untouched: possible routes keep their distinct colour
  in the galaxy and their dash in the map.
- No layout coordinate changes, so no region signature changes and nothing
  re-dims.

## Testing

- `layout.py`: unit tests for `hops_from_home` — Home at 0, direct importer at 1,
  unreachable at `None`, undirected traversal, determinism across repeated
  parses, and recomputation through `with_entrypoint`.
- Existing graph fixture tests updated for schema 6 and the new field.
- `learnerSession.js`: tests for the revealed set — floor present on first run,
  lighting a region adding its neighbours permanently, transient selection
  reveal clearing on deselect, `showAll` overriding all three.
- Renderer changes (orbit, labels, sidebar, palette, chrome) are verified by
  running the app, per the standing rule.
