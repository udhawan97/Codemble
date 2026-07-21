# OSS-inspired upgrades: Architecture map SVG + galaxy constellations

Date: 2026-07-20 · Status: implemented in two ordered branches; Task 1 merged
before Task 2 began, with both Decision Log rows landed alongside the code

Companion research file (per-project findings with citations):
`docs/research/2026-07-20-opensource-graph-architecture-inspiration.md`

## What was asked

UD asked whether open-source projects — Graphify-Labs/graphify ("better graph
connections and visuals"), tt-a1i/archify ("better 2D architecture SVGs"), and
anything comparable — offer ideas or components Codemble should adopt, and for
a plan plus a ready-to-run Codex prompt.

## What the audit of our own code found first

Grounding reads before looking outward (all paths relative to repo root):

- `codemble/graph/mapview.py` — the Architecture tab layers correctly by
  import depth and cuts cycles, but orders boxes within a layer by
  `(directory, id)` only: **no crossing minimization**. It computes directory
  `groups` that the renderer **never draws**, and emits per-edge `weight`
  that the renderer **never uses**.
- `web/src/MapView.jsx` — edges are straight `<line>`s from bottom-center to
  top-center of fixed boxes: every edge leaving a busy module departs from the
  same point, and **direction is invisible** (no arrowheads), even though the
  3D galaxy shows direction with arrows and particles. Import direction is
  parser truth the 2D layer currently hides.
- `codemble/graph/layout.py` — galaxy regions are placed on a golden-angle
  spiral in **hash order**, so two tightly-coupled modules can sit across the
  galaxy from each other; routes stretch arbitrarily. Connectivity plays no
  part in placement.
- `codemble/graph/finalize.py` — centrality = distinct internal callers.
  Honest and cheap; no change proposed.
- Dependencies (`pyproject.toml`) are lean: fastapi, tree-sitter, uvicorn.
  **No networkx.** Anything adopted must be a pure-Python deterministic
  algorithm, which matches how mapview.py/layout.py are already written.

So the two named OSS projects map cleanly onto two real, verifiable gaps.

## Constraints every adoption must respect

- **Correctness Contract:** structure only from parsers; no LLM-drawn
  architecture (rules out gitdiagram-style pipelines as anything but UX
  inspiration); uncertain edges stay visibly "possible" (dashed in 2D).
- **Determinism:** same code → same bytes. Fixed iteration counts, sorted
  tie-breaks, no clock/RNG. Layouts computed in `codemble/graph/`; React
  renders numbers (client-side force layouts are out).
- **Non-Goals:** no free flight, no client-computed 2D layouts, no elaborate
  game art before the loop teaches well.
- **License:** Apache-2.0 repo. Port/vendor only from MIT/BSD/Apache sources
  with attribution; GPL/EPL projects are ideas-only. Algorithms themselves
  (Sugiyama barycenter, label propagation) are reimplemented from the
  literature, which is always safe.
- **Progress safety:** region signatures hash file content, never coordinates
  (M12 precedent), so a one-time layout change re-dims nothing.

## Credit & cost policy (binding for both tasks)

- **Cost is $0, permanently.** Both tasks are pure-Python stdlib
  implementations: no new dependencies, no network calls, no services, no
  free-tier-that-becomes-paid. Codemble's only paid path stays the optional
  BYO LLM key, which this plan does not touch. The shipped stack is already
  all open source (FastAPI, tree-sitter, Vite, React, 3d-force-graph).
- **Credit for ideas, given deliberately.** Reimplementing a published
  algorithm carries no license obligation — but credit is part of this plan
  anyway:
  - `README.md` gains an **Acknowledgements** section (none exists today;
    Task 1 creates it, Task 2 extends it) crediting by name with links:
    dagre and Eclipse ELK (layered-diagram approach), tt-a1i/archify
    (2D architecture-diagram inspiration), Graphify-Labs/graphify
    (community-constellation idea), and the shipped OSS stack.
  - The implementing modules cite sources in docstrings: `mapview.py` →
    barycenter crossing minimization after Sugiyama, Tagawa & Toda (1981),
    approach popularized by dagre/ELK; `layout.py` → label propagation after
    Raghavan, Albert & Kumara (2007), constellation idea inspired by
    graphify. Each notes "implemented independently; no code copied."
- **Credit for code — the guard.** Neither prompt permits copying code. If a
  future change ever ports real source, the rule is: verify the upstream
  license is MIT/BSD/Apache, keep the upstream copyright header at the
  ported site, add a NOTICE entry beside LICENSE, and record it in the
  Decision Log — or do not port it. GPL/EPL projects stay ideas-only.
- **Verified licenses** (full cited table in the research file): graphify
  MIT · archify MIT · dagre MIT · d3-dag MIT · aider Apache-2.0 — all safe
  for ideas, and legally portable if ever needed. Eclipse ELK EPL-2.0 — use
  its excellent algorithm docs as spec only. crabviz AGPL-3.0 and grandalf
  GPLv2/EPL — ideas only, never port code. Everything named is free and
  open source; nothing here has a paid tier.

## The plan — two tasks, run as two separate Codex sessions

### Task 1 (do first): Architecture map becomes a real layered diagram

Inspired by archify's renderer — the research pass confirmed archify's
*structure* comes from an LLM-written IR (contract-banned as a pipeline),
but its *renderer* is exactly our kind of thing: "fixed cell math only",
grid placement, orthogonal elbow routing with side anchors, and post-render
geometry checks, all deterministic and MIT. That craft, plus the Sugiyama
pipeline ELK documents and dagre implements (MIT), reimplemented
deterministically in Python. Lands in
`codemble/graph/mapview.py`, `web/src/MapView.jsx`, `web/src/styles.css`,
`tests/test_mapview.py`.

1. **Crossing minimization:** order boxes within each import layer by
   barycenter sweeps (fixed 4 down-up passes, ties broken by region id)
   instead of `(directory, id)`. Wrapping onto visual rows happens after
   ordering, unchanged.
2. **Ports + routed edges:** each edge gets backend-computed waypoints —
   fan-out ports spaced along the source box bottom / target box top, then a
   smooth path. `MAP_SCHEMA_VERSION` 1 → 2.
3. **Direction:** SVG arrowhead markers. Import direction is parser truth;
   showing it is a correctness improvement, not decoration.
4. **Weight:** stroke width scales with the existing (unused) `weight` field,
   mirroring what `GalaxyCanvas.jsx` already does for routes.
5. **Cycle edges** route around the flank instead of crossing through the
   middle, keeping their existing `is-cycle` styling.

Not doing: drawing directory group containers (groups scatter across layers;
containers need hierarchical layout — Phase 2 material). Groups stay payload
metadata.

### Task 2 (after Task 1 merges): constellation placement in the galaxy

Inspired by graphify's community detection. (The research pass confirmed
graphify runs Leiden — graspologic, seed-pinned — with a Louvain fallback,
wrapped in serious determinism engineering: canonical input order,
total-order community IDs, membership fingerprints. Same spirit here, but we
implement the simpler label-propagation algorithm to stay stdlib-only.)
Lands in
`codemble/graph/layout.py`, `codemble/adapters/base.py` (one additive Region
field), `tests/test_graph_finalization.py`.

1. **Deterministic community detection** over region import routes: pure-
   Python label propagation, sorted node order, fixed max iterations,
   deterministic tie-break (smallest label). ~40 lines, stdlib only.
2. **Two-level placement:** communities take the golden-angle spiral;
   members place on a local golden-angle disc around their community center,
   radius scaled by member count. Connected systems become visible
   constellations with dark space between groups; routes shorten.
3. **Expose `community` on regions** (additive graph-schema field) so the Map
   and Phase-2 LOD clustering can reuse it later without recomputing.
4. Layout bytes change once — M12 precedent; progress unaffected.

### Explicitly rejected from the OSS survey

- LLM-generated architecture (gitdiagram and any LLM mode of archify):
  violates "structure is never invented". UX-only inspiration.
- Client-side force/GPU layouts (cosmograph/cosmos, d3-force in 2D, mermaid
  auto-layout): violate determinism + render-ready-graph rules.
- New runtime dependencies (networkx, graphviz bindings): both tasks are
  small pure-Python algorithms; the repo's style is hand-rolled and tested.
- Home-personalized PageRank centrality (aider's approach, Apache-2.0,
  research shortlist #3, ~40 stdlib lines): deliberately NOT in these
  prompts. It changes what brightness *means* — "distinct callers" →
  "importance relative to Home" — a learner-facing semantics change that
  needs UD's explicit approval. If approved, it becomes its own small task
  with its own Decision Log row.

### Drafted Decision Log rows (land with each implementation)

| Date | Decision | Why |
| --- | --- | --- |
| (Task 1) | Architecture map edges get backend-computed ports, barycenter ordering, arrowheads, and weight-scaled strokes; `MAP_SCHEMA_VERSION` 2; directory groups stay payload metadata | Within-layer order was arbitrary and direction was invisible in 2D while being parser truth; ordering stays deterministic (fixed sweeps, sorted ties); group containers wait for hierarchical layout |
| (Task 2) | Galaxy regions place by deterministic import-community constellations (pure-Python label propagation in layout.py); `community` is an additive Region field; layout bytes change once | Hash-order placement scattered coupled modules; communities are parser-truth-derived and deterministic; progress signatures hash file content so nothing re-dims (M12 precedent) |

## Codex prompt — Task 1

Run from a fresh branch at the repo root. Paste everything between the fences.

```text
You are working in Codemble (github.com/udhawan97/Codemble), a Python 3.11 +
FastAPI + Vite/React learning game that parses a user's codebase into a
deterministic 3D "galaxy" and a 2D SVG "Map". Read CLAUDE.md first — it is
the operating spec. The sections that bind this task: Correctness Contract,
Architecture rules (the graph is render-ready; React is a pure renderer),
and Gotchas (determinism; web_dist is a committed build artifact).

TASK: Upgrade the 2D Architecture map from a straight-line grid diagram to a
properly routed layered diagram. Backend layout lives in
codemble/graph/mapview.py (function _architecture); the SVG renderer is
web/src/MapView.jsx (ArchitectureMap); styles in web/src/styles.css; tests in
tests/test_mapview.py.

HARD RULES — violating any of these is a failed task:
- Determinism: same graph in → byte-identical map JSON out. No wall-clock, no
  random, no set-iteration order reaching output. Fixed iteration counts,
  ties broken by sorted ids. Round emitted floats with the existing _rounded.
- All layout numbers are computed in Python. React draws numbers it is
  handed; it must not compute ordering, ports, or waypoints.
- Uncertain edges (certain=false) stay dashed; cycle edges keep their
  is-cycle marking. Never drop or merge an edge: every entry in
  architecture.edges today must still be drawn.
- No new runtime dependencies. Pure Python stdlib, matching the existing
  hand-rolled style of mapview.py. Nothing in this task may call a network,
  a service, or anything paid — the feature must be $0 forever.
- Do NOT copy code from dagre, ELK, archify, or any external repo. Implement
  the barycenter heuristic from its published description (Sugiyama, Tagawa
  & Toda 1981 — the algorithm dagre/ELK popularized). If you catch yourself
  adapting external source, stop and say so in the PR body instead; license
  review is the owner's call.
- Accessibility: keep every existing aria-label/role; boxes stay keyboard-
  focusable buttons. Do not encode any new meaning in color alone.
- Palette: reuse existing CSS custom properties from web/src/tokens.css /
  styles.css. Amber (--cm-star*) means "understood" ONLY — never use it for
  edges, arrows, or ordering emphasis. Interaction stays --cm-orbit.

IMPLEMENT, in codemble/graph/mapview.py:
1. Barycenter ordering: after computing layers (unchanged), order each
   layer's boxes by the barycenter (mean) of their already-ordered neighbor
   positions in the adjacent layer — 4 fixed sweeps alternating downward
   (order layer k by predecessors in k-1) and upward (by successors in k+1),
   seeded from the current (group, id) order. A box with no neighbors in the
   reference layer keeps its relative position. Break barycenter ties by
   region id. After ordering, the existing wrap-into-rows logic runs
   unchanged on the new order.
2. Ports: for each box, sort its outgoing edges by (target layer, target
   final x, target id) and space their start points evenly along the box's
   bottom edge; sort incoming edges the same way and space their end points
   along the top edge. Emit per-edge waypoints:
   "points": [[x1,y1],[x2,y2],...] — start port, one or two intermediate
   bend points that keep the path clear of box interiors, end port. For a
   back/cycle edge (dst on an earlier or same visual row), route around the
   diagram flank: out to x = -24 or width+24 (pick the nearer side of the
   source port, ties toward the left), vertically, then back in to the target
   top port.
3. Bump MAP_SCHEMA_VERSION to 2. Keep every existing field; "points" and any
   port fields are additive per-edge fields.

IMPLEMENT, in web/src/MapView.jsx + styles.css:
4. Render each edge as one <path> through its backend points (straight
   segments with a small rounded corner radius, or a gentle curve — your
   choice, but the geometry must come only from the provided points).
   Preserve strokeDasharray for certain=false and the is-cycle class.
5. Add an SVG <marker> arrowhead on the target end of every edge, colored by
   the same stroke (currentColor). Direction = src imports dst, matching the
   existing 3D arrows.
6. Scale stroke-width by edge.weight, clamped: 1 + min(2.5, (weight-1)*0.5)
   px. Add/adjust a CSS hook if needed.
7. Update the map legend/notes only if they describe edge appearance.

TESTS (tests/test_mapview.py — extend, don't rewrite):
- Determinism: build_map twice on the same fixture graph → identical JSON
  (json.dumps byte equality).
- Crossing reduction: on a fixture where (group,id) order forces a crossing
  that barycenter resolves (build one: 2 layers, 3+3 boxes, crossed edges),
  assert the new order has strictly fewer straight-line crossings between
  adjacent layers than the seeded order.
- Ports: a box with 3 outgoing edges emits 3 distinct start points, all on
  its bottom edge (y == box.y + height; x strictly inside [box.x,
  box.x+width]).
- Cycle edges: a cycle edge's points route outside the box column band
  (min or max x beyond [0, width]).
- Geometry self-audit (archify-style): on the largest fixture graph, no two
  boxes overlap, and no edge's straight segments pass through the interior
  of any box other than its own endpoints' boxes.
- Schema: MAP_SCHEMA_VERSION == 2 and every edge has >= 2 points.
- Existing tests must keep passing; update any that assert the old (group,
  id) ordering, and say in the PR body which assertions changed and why.

VERIFY (all must pass; paste outputs in the PR body):
  pip install -e ".[dev]"
  pytest
  ruff check .
  cd web && npm install && npm run build   # then commit the regenerated
                                           # codemble/web_dist/ — it ships in
                                           # the wheel; the app is broken for
                                           # wheel users if you skip this.
Then run `codemble .` at the repo root, open the Map layer, and confirm:
arrowheads visible, no edge passes through a box interior, dashed edges still
dashed, cycle edges routed around the flank, keyboard focus still works.
Attach a before/after screenshot of the Architecture tab.

BOOKKEEPING (same PR):
- CHANGELOG.md: one entry under Unreleased (Keep a Changelog format).
- ATTRIBUTION: add an "Acknowledgements" section at the end of README.md (it
  does not exist yet) — a short linked list crediting: dagre
  (github.com/dagrejs/dagre) and Eclipse ELK (github.com/eclipse-elk/elk)
  for the layered-diagram approach; tt-a1i/archify
  (github.com/tt-a1i/archify) for 2D architecture-diagram inspiration; and
  the shipped stack Codemble builds on: vasturiano/3d-force-graph,
  tree-sitter, FastAPI, Vite, React. One line each, no logos. In the new
  ordering code's docstring, cite: "Barycenter crossing minimization after
  Sugiyama, Tagawa & Toda (1981); approach popularized by dagre and Eclipse
  ELK. Implemented independently; no code copied." In the port/routing
  code's docstring, cite: "Orthogonal elbow routing with side anchors after
  tt-a1i/archify's renderer (MIT). Implemented independently in Python; no
  code copied."
- CLAUDE.md: append the Task-1 Decision Log row already drafted in
  docs/plans/2026-07-20-oss-inspired-map-and-constellations.md, and add one
  line to Current State's session note.
- Do NOT bump the package version or tag a release; the owner releases.
- Conventional Commit messages with DCO sign-off (git commit -s).

OUT OF SCOPE — do not touch: codemble/checks/ (suites are golden-pinned),
codemble/progress/, parsers/adapters, the 3D galaxy, the Workflow tab
layout, /api/graph schema. Do not draw directory group containers. Do not
add XP/streaks or any Non-Goal from CLAUDE.md.
```

## Codex prompt — Task 2

Run only after Task 1 merges, on a fresh branch.

```text
You are working in Codemble (github.com/udhawan97/Codemble). Read CLAUDE.md
first — Correctness Contract, Architecture rules, Gotchas (determinism) bind
this task.

TASK: Galaxy regions currently place on a golden-angle spiral in hash order
(codemble/graph/layout.py, layout_graph), so import-coupled modules can land
far apart. Replace hash-order placement with deterministic import-community
constellations. No new dependencies; pure Python stdlib.

HARD RULES:
- Determinism: same graph → byte-identical layout. Fixed iteration counts,
  sorted iteration, ties by smallest value. Keep using _digest/_fraction and
  _rounded. No clock, no random module.
- Free and local only: no new dependencies (no networkx), no network calls,
  no services. Do NOT copy code from graphify or any external repo —
  implement label propagation from the published description (Raghavan,
  Albert & Kumara 2007). If you catch yourself adapting external source,
  stop and say so in the PR body instead.
- Structure truth is untouched: communities derive ONLY from existing
  region-level import routes (the same evidence layout_graph already
  aggregates into region_edges). No LLM, no heuristics beyond the graph.
- Progress must not re-dim: region signatures hash file content, never
  coordinates (this is established M12 precedent — coordinates may change
  once).
- The renderer is untouched except where it already consumes region x/y/z.
  React computes no layout.

IMPLEMENT, in codemble/graph/layout.py:
1. _communities(region_ids, routes) -> dict[str, int]: label propagation on
   the undirected region-route graph. Init each region's label to its own
   index in sorted(region_ids). Iterate regions in sorted order for at most
   10 fixed passes: each region adopts the smallest label that is most
   frequent among its neighbors (ties → smallest label); stop early when a
   full pass changes nothing. Isolated regions keep their own label.
   Renumber final labels densely by first appearance in sorted region order.
2. Two-level placement in layout_graph: communities take the existing
   golden-angle spiral (ordered by community id); each community's members
   place on a local golden-angle disc around the community center, member
   order = existing (digest, id) sort, local radius 16 + 12*sqrt(member
   index), plus the existing per-region hash jitter for phase/height. Scale
   community spacing so discs don't overlap: community ring radius uses
   sqrt(cumulative member count), not community index. Keep all outputs
   through _rounded.
3. Add community: int to Region (codemble/adapters/base.py) and serialize it
   wherever Region already serializes. Bump the graph schema version:
   codemble/adapters/base.py line ~118 has
   `schema_version: int = field(default=4, init=False)` — change 4 to 5, and
   update every test that asserts schema_version == 4 (list them in the PR
   body).

TESTS (tests/test_graph_finalization.py — extend):
- Determinism: finalize the same fixture twice → identical serialized bytes.
- Community correctness: a fixture with two 3-region cliques joined by one
  route yields exactly 2 communities matching the cliques.
- Constellation property: mean pairwise distance between regions sharing a
  community < mean distance between regions in different communities, on
  that fixture.
- Isolated region: a region with no routes gets its own community and still
  places (no crash, finite coordinates).
- Schema: every serialized region carries an integer community; schema
  version constant bumped; old-schema assertions updated deliberately (list
  them in the PR body).

VERIFY (paste outputs in the PR body):
  pip install -e ".[dev]" && pytest && ruff check .
Then run `codemble .` and confirm in the galaxy: related systems visibly
cluster, routes are shorter, no two systems overlap, Home still marked, and
lighting/progress state is unchanged from before the branch (parse the same
project before/after and confirm the star chart and lit regions match).
No web/ changes are expected; if you believe one is needed, stop and explain
in the PR body instead of making it.

BOOKKEEPING (same PR):
- CHANGELOG.md entry under Unreleased.
- ATTRIBUTION: README.md's "Acknowledgements" section (created by the map-
  upgrade PR; create it if missing) gains one line: Graphify-Labs/graphify
  (github.com/Graphify-Labs/graphify) for the community-constellation idea.
  The _communities docstring cites: "Label propagation after Raghavan,
  Albert & Kumara (2007), 'Near linear time algorithm to detect community
  structures in large-scale networks'; constellation idea inspired by
  graphify. Implemented independently; no code copied."
- CLAUDE.md: append the Task-2 Decision Log row drafted in
  docs/plans/2026-07-20-oss-inspired-map-and-constellations.md; one-line
  Current State session note.
- No version bump, no tag. Conventional Commits + DCO (git commit -s).

OUT OF SCOPE: checks/ (golden-pinned suites), progress/ logic, parsers,
mapview.py, anything in web/ — the Map's use of community metadata is a
later task. Do not rename or reorder existing serialized fields.
```

## Later, from the research shortlist (not in these prompts)

Parked with owners' approval required, in rough value order: crabviz-style
click-to-focus fade on the Map (idea only — crabviz is AGPL);
dependency-cruiser-style deterministic collapse patterns for Phase-2 scale;
graphify's cross-community "surprise" signal as a graph-only hint; the
PageRank centrality option above.

## Sequencing and risk

1. Task 1 is pure win, contained, and visually obvious to testers — it goes
   first and alone.
2. Task 2 changes layout bytes once; M12 set the precedent and progress is
   signature-safe, but review the before/after galaxy manually before merge.
3. Both need UD approval before implementation per the session protocol;
   the Decision Log rows above are drafted for that purpose.
4. NOW-phase reminder: neither task replaces Phase 1 tester evidence (#13) —
   they improve what testers will see.
5. Credit & cost policy above is binding on both prompts. The research file's
   license table is the gate for ever turning an idea-adoption into a
   code-adoption.
