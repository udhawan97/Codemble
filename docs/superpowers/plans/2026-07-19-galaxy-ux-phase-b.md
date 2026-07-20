# Galaxy UX Phase B — the look and the map · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Codemble a "living cosmos" 3D galaxy (bloom, halos, language-tinted
nebulae, a hash-seeded starfield, call-depth orbits, and a nebula-dawn light-up)
and a second, WebGL-free 2D **Map** layer whose Architecture and Workflow layouts
are computed deterministically in the Python graph layer.

**Architecture:** All layout — 3D and 2D — is computed in `codemble/graph/` and
shipped as data. A new `codemble/graph/mapview.py` builds both 2D payloads behind
one `GET /api/map` endpoint; `layout_graph` re-orbits system nodes by call depth.
On the frontend, `LearnerSession` gains layer/tab/map state and one derived `hint`,
React renders that truth, and the three.js material, sprite, fog, starfield, and
post-processing code moves out of `GalaxyCanvas.jsx` into two focused modules so
the component stays a renderer and nothing else.

**Tech Stack:** Python 3.11+ · FastAPI · pytest · ruff · Vite + React 19 ·
`3d-force-graph` 1.80.0 · `three` 0.185.1 (`three-forcegraph` 1.43.4,
`three-render-objects` 1.42.0) · plain-node assert scripts for frontend state.

## Global Constraints

Every task's requirements implicitly include this section.

- **Determinism — "same code → same sky".** Galaxy layout must be seeded by
  content hash, never wall-clock or `Math.random` at render time. Backend
  coordinates depend only on stable identifiers and sorted membership: no clock,
  no process hash seed, no random source, no set-iteration order in output.
- **Canvas colours must be plain values, never `color-mix()`.** WebGL receives a
  custom property's authored text, so a computed token renders black. Add new
  canvas tokens through `readPalette`, which resolves them.
- **Amber's monopoly on understanding.** `amber = understood and nothing unlit
  may outshine it`. The unlit centrality ramp caps at `--cm-ink-2`; lit stars use
  `--cm-star-high`. No new visual channel (halo, nebula, starfield, reticle) may
  render an un-understood object brighter than a lit star.
- **Uncertainty stays visible.** "Approximate call edges are labeled 'possible
  call.'" Possible calls stay **dashed and particle-free** in 3D and dashed in 2D.
  Structure is never invented: nodes, edges, entrypoints, layouts, tree shapes,
  hints, and check answers come from the parser or graph only.
- **No free flight.** Semantic zoom only; `enableNavigationControls(false)` stays.
- **Reduced motion.** `prefers-reduced-motion` gets the finished lit state
  instantly — the nebula dawn must not merely run faster, it must not run.
- **`codemble/web_dist` is a committed build artifact.** Any task changing
  `web/src` must run `cd web && npm run build` and commit the resulting
  `codemble/web_dist` changes **in the same commit**.
- **`web/src/tokens.css` holds app-only tokens.** Never edit
  `docs-site/src/styles/tokens.css` for app work.
- **CI gates:** `pytest` and `ruff check .` must pass. Frontend verification is
  `cd web && npm run check` (runs `check_graph_data.mjs`, then
  `check_learner_session.mjs`, then `vite build` into `codemble/web_dist`).
- **Conventional Commits with DCO sign-off** (`git commit -s`).

### Binding names (from `docs/superpowers/plans/2026-07-19-galaxy-ux-shared-contract.md`)

Never rename any of these.

| Kind | Phase B names |
| --- | --- |
| Endpoint | `GET /api/map` → `{"schema_version": 1, "architecture": {...}, "workflow": {...}}` |
| Session state | `layer` (`"galaxy"`\|`"map"`), `mapTab` (`"architecture"`\|`"workflow"`), `mapData` (object\|null), `mapError` (string\|null), `coachmarksSeen` (bool) |
| Derived (never stored) | `hint` (object\|null) — nearest unlit region to Home by route hops, ties by region id; `null` in expert mode or when nothing is unlit |
| Events | `SET_LAYER` (`{layer}`), `SET_MAP_TAB` (`{tab}`), `DISMISS_COACHMARKS` |
| Adapter method | `fetchMap(signal)` — implemented on **both** `createHttpLearnerSessionAdapter` and `createInMemoryLearnerSessionAdapter` |

### Phase A is already landed — do not re-plan it

Assume these exist: session fields `mode` / `llmStatus` / `explanation` /
`explanationLoading` / `explanationError` / `hoverNodeId`; events `SET_MODE`,
`RESET_PROJECT`, `CHANGE_HOME`, `HOVER_NODE`; adapter methods `fetchExplanation`,
`fetchMode`, `putMode`, `fetchLlmStatus`, `resetProject`; `POST /api/picker/reset`;
hover/select edge highlighting; link arrows; and the extracted study-panel module.

### Verified facts about the installed renderer stack

Confirmed against `web/node_modules` at plan time — do not re-derive:

- `postProcessingComposer(): EffectComposer` **is** available on
  `3d-force-graph@1.80.0` and returns the composer from
  `three/examples/jsm/postprocessing/EffectComposer.js`.
- The composer is constructed **already seeded with a `RenderPass`**, so bloom is
  a single `composer.addPass(...)`. The library always renders through the
  composer, and resizes it automatically on `width()`/`height()` changes.
- `three@0.185.1` maps `./addons/*` → `./examples/jsm/*` in its `exports`, and
  ships `UnrealBloomPass.js`. Constructor:
  `UnrealBloomPass(resolution, strength = 1, radius, threshold)`.
- **`UnrealBloomPass`'s constructor `resolution` is overwritten on the first
  composer resize** (`EffectComposer.setSize` forwards the canvas size to every
  pass). The cap that survives is `composer.setPixelRatio(1)`.
- **The existing `?benchmark` path bypasses the composer.** `GalaxyCanvas.jsx:111`
  calls `webglRenderer.render(scene, camera)` directly, so it would report a
  bloom-free framerate. Task 7 fixes it.
- Accessors used by this plan and present in the installed bundles:
  `linkCurvature`, `linkDirectionalParticles`, `linkDirectionalParticleSpeed`,
  `linkDirectionalParticleWidth`, `linkDirectionalParticleColor`,
  `nodeVisibility`, `linkVisibility`, `onEngineTick`, `scene()`, `renderer()`,
  `camera()`.

---

## File Structure

| File | Created / Modified | One responsibility |
| --- | --- | --- |
| `codemble/graph/mapview.py` | Create | Build both deterministic 2D map payloads from one graph |
| `codemble/graph/layout.py` | Modify | Add call-depth orbit rings to system layout |
| `codemble/graph/__init__.py` | Modify | Re-export `build_map` / `MAP_SCHEMA_VERSION` |
| `codemble/server/app.py` | Modify | Serve `GET /api/map` from the hydrated graph |
| `tests/test_mapview.py` | Create | Map determinism, layers, groups, cycles, unreachable |
| `tests/test_python_ast.py` | Modify | Re-pin layout test to call-depth orbit radii |
| `tests/test_server.py` | Modify | `/api/map` contract + 409 before binding |
| `web/src/tokens.css` | Modify | App-only nebula/halo tokens, plain `rgb()` |
| `web/src/galaxyMaterials.js` | Create | Canvas-generated textures + three.js object builders (halo, nebula, starfield, reticle) |
| `web/src/galaxyEffects.js` | Create | Bloom composer wiring + the nebula-dawn animation driver |
| `web/src/GalaxyCanvas.jsx` | Modify | React glue only: mount, feed data, drive camera and keyboard |
| `web/src/graphData.js` | Modify | Presentation flags (`focusDim`, nebula tint key) over graph truth |
| `web/src/MapView.jsx` | Create | 2D Map layer: tabs, `ArchitectureMap`, `WorkflowTree` (pure SVG) |
| `web/src/GuidanceLayer.jsx` | Create | Easy-mode guidance: `CoachMarks` + `HintChip` |
| `web/src/learnerSession.js` | Modify | Layer/tab/map state, `fetchMap`, derived `hint` |
| `web/src/App.jsx` | Modify | Header (`LayerSwitcher`, breadcrumb), legend, layer routing |
| `web/src/styles.css` | Modify | Styles for map, switcher, coach-marks, hint, legend tints |
| `web/scripts/check_learner_session.mjs` | Modify | Assert the new session contracts |
| `codemble/web_dist/**` | Modify | Committed SPA build artifact |
| `CHANGELOG.md`, `README.md`, `docs-site/**` | Modify | Docs the new look and layer invalidate |

**Why `GalaxyCanvas.jsx` splits:** it is the only WebGL surface and Phase B adds
halos, nebulae, a starfield, bloom, a reticle, focus dimming, particles, and the
dawn animation. Left inline that is ~600 lines of three.js inside a React
component. `galaxyMaterials.js` owns *what objects look like*, `galaxyEffects.js`
owns *post-processing and timed animation*, and neither imports React.

**No JavaScript test framework exists in this repo (no jest, no vitest, no RTL)
and this plan does not add one.** Backend logic gets pytest. Frontend *state*
gets `web/scripts/check_learner_session.mjs` through the in-memory adapter. Pure
visual/WebGL work has **no automated test**: it is verified by building, running
the app, and reading the `?benchmark` figure — each such task says so explicitly
and lists the exact commands and what to look for.

---

### Task 1: Call-depth system orbits

Re-orbit system nodes by call depth from the system's entry node. Galaxy-level
spiral coordinates are unchanged. Layout bytes change once.

**Resolved ambiguity (read before implementing).** The spec says "orbit 1 =
called directly by the system's entry node". The entry node is the module node at
the origin, and **module nodes have no outgoing intra-project call edges in the
fixture** (verified: every region of `tests/fixtures/sampleproj` has zero calls
out of its module node). Taken literally, orbit 1 would always be empty and every
member would fall to the outermost ring — a no-op. The seed is therefore widened
to *also* include members that **no sibling in the region calls** (in-degree 0 —
the region's call roots). Both spec rules are preserved exactly: the entry's
direct callees are still orbit 1, and members unreachable from those roots still
take the outermost orbit ordered by node id.

**Progress is safe:** `codemble/progress/store.py:124` derives region signatures
from **file hashes only**, so changing coordinates cannot dim a learner's lit
regions.

**Files:**
- Modify: `codemble/graph/layout.py`
- Test: `tests/test_python_ast.py:175` (`test_layout_is_render_ready_and_deterministic`)

**Interfaces:**
- Consumes: `Graph`, `Node`, `Edge` from `codemble.adapters.base`.
- Produces: `layout_graph(graph: Graph) -> Graph` — unchanged public signature.
  New private helper `_call_depths(members: list[Node], edges: tuple[Edge, ...]) -> dict[str, int]`
  mapping node id → orbit ring (0 = entry at origin).

**Existing determinism tests, named exactly.** These all compare *two parses of
the same input*, so none of them fails before or after this change — which is
precisely why the re-pin below adds real orbit assertions rather than editing an
expected constant:

- `tests/test_python_ast.py::test_layout_is_render_ready_and_deterministic` ← **re-pinned in Step 1**
- `tests/test_python_ast.py::test_serialization_is_byte_deterministic`
- `tests/test_project_parser.py::test_default_project_parser_preserves_the_python_graph`
- `tests/test_project_parser.py::test_project_intake_reuses_discovered_file_evidence`
- `tests/test_typescript_tree_sitter.py::test_repeated_mixed_parses_are_byte_identical`
- `tests/test_graph_finalization.py::test_finalization_owns_canonical_graph_truth_and_layout`

- [ ] **Step 1: Re-pin the layout test with call-depth orbit assertions**

In `tests/test_python_ast.py`, add `import math` to the existing imports at the
top of the file, then replace the whole body of
`test_layout_is_render_ready_and_deterministic` (lines 175–190) with:

```python
def test_layout_is_render_ready_and_deterministic(graph) -> None:  # type: ignore[no-untyped-def]
    second = PythonAstAdapter().parse(FIXTURE)
    regions = {region.id: region for region in graph.regions}
    second_regions = {region.id: region for region in second.regions}
    nodes = {node.id: node for node in graph.nodes}

    def orbit_radius(node_id: str) -> float:
        node = nodes[node_id]
        return round(math.hypot(node.system_x, node.system_z), 3)

    assert regions == second_regions
    assert len({(region.x, region.y, region.z) for region in graph.regions}) == len(
        graph.regions
    )
    assert regions["app"].home is True
    assert regions["app"].node_count == 2
    assert regions["pkg.service"].node_count == 4
    assert any(route.src == "cli" and route.dst == "app" for route in graph.region_edges)

    # Orbits are call depth from the system's entry node, not member index.
    # The module node holds the origin; ring 1 is 34.0 out, each ring +24.0.
    assert orbit_radius("app") == 0.0
    assert orbit_radius("pkg.service") == 0.0
    assert orbit_radius("app.main") == 34.0
    # Service.run calls Service.finish, so finish orbits one ring further out.
    assert orbit_radius("pkg.service.Service") == 34.0
    assert orbit_radius("pkg.service.Service.run") == 34.0
    assert orbit_radius("pkg.service.Service.finish") == 58.0
    # greet -> normalize, and duplicate is called by nobody in the region.
    assert orbit_radius("pkg.util.greet") == 34.0
    assert orbit_radius("pkg.util.duplicate") == 34.0
    assert orbit_radius("pkg.util.normalize") == 58.0
    assert orbit_radius("shared.choose") == 34.0
    assert orbit_radius("shared.duplicate") == 58.0
    assert {node.id: (node.system_x, node.system_y, node.system_z) for node in graph.nodes} == {
        node.id: (node.system_x, node.system_y, node.system_z) for node in second.nodes
    }
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python3 -m pytest tests/test_python_ast.py::test_layout_is_render_ready_and_deterministic -v`

Expected: FAIL — `assert 58.0 == 34.0` (or a similar radius mismatch) on the
first orbit assertion, because today's rings follow member index, not call depth.

- [ ] **Step 3: Implement call-depth orbits**

In `codemble/graph/layout.py`, widen the two imports at the top:

```python
from collections import defaultdict, deque
```

```python
from codemble.adapters.base import Edge, Graph, Node, Region, RegionEdge
```

Replace the member-positioning loop (lines 60–82, from `for member_index, node in
enumerate(members):` through the end of that block) with:

```python
        depths = _call_depths(members, graph.edges)
        orbits: dict[int, list[Node]] = defaultdict(list)
        for node in members:
            orbits[depths[node.id]].append(node)
        for node in orbits[0]:
            positioned_nodes.append(replace(node, system_x=0.0, system_y=0.0, system_z=0.0))
        for depth in sorted(orbit for orbit in orbits if orbit > 0):
            ring_nodes = orbits[depth]
            for slot_index, node in enumerate(ring_nodes):
                sub_ring = slot_index // _SYSTEM_RING_CAPACITY
                slot = slot_index % _SYSTEM_RING_CAPACITY
                ring_members = min(
                    _SYSTEM_RING_CAPACITY,
                    max(1, len(ring_nodes) - sub_ring * _SYSTEM_RING_CAPACITY),
                )
                angle = (
                    2.0 * math.pi * slot / ring_members
                ) + _fraction(node.id, "orbit") * 0.08
                radius = 34.0 + (depth - 1) * 24.0 + sub_ring * 12.0
                positioned_nodes.append(
                    replace(
                        node,
                        system_x=_rounded(math.cos(angle) * radius),
                        system_y=_rounded(((_fraction(node.id, "depth") * 2.0) - 1.0) * 8.0),
                        system_z=_rounded(math.sin(angle) * radius),
                    )
                )
```

Then add this helper immediately above `def with_entrypoint(`:

```python
def _call_depths(members: list[Node], edges: tuple[Edge, ...]) -> dict[str, int]:
    """Return each member's orbit ring: call depth from the system's entry node.

    The entry node is the module node at the origin (ring 0).  Ring 1 is what the
    entry calls directly *plus* every member no sibling calls, because a module
    that makes no module-level call would otherwise strand its whole region in
    the outermost ring.  Members unreachable from those roots take the outermost
    ring, ordered by node id, so unresolved evidence stays visible rather than
    being guessed into the structure.
    """

    member_ids = {node.id for node in members}
    entry = members[0].id
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.kind != "call" or edge.external or edge.src == edge.dst:
            continue
        if edge.src in member_ids and edge.dst in member_ids:
            if edge.dst not in outgoing[edge.src]:
                indegree[edge.dst] += 1
            outgoing[edge.src].add(edge.dst)

    depths = {entry: 0}
    queue: deque[str] = deque()
    roots = outgoing[entry] | {
        node.id for node in members if node.id != entry and indegree[node.id] == 0
    }
    for node_id in sorted(roots):
        depths[node_id] = 1
        queue.append(node_id)
    while queue:
        current = queue.popleft()
        for target in sorted(outgoing[current]):
            if target not in depths:
                depths[target] = depths[current] + 1
                queue.append(target)

    stranded = sorted(node.id for node in members if node.id not in depths)
    outermost = max(depths.values()) + 1 if depths else 1
    for node_id in stranded:
        depths[node_id] = outermost
    return depths
```

- [ ] **Step 4: Run the full suite and lint**

Run: `python3 -m pytest -q && python3 -m ruff check .`
Expected: `132 passed` (131 baseline, unchanged count — the re-pin edits an
existing test) and `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add codemble/graph/layout.py tests/test_python_ast.py
git commit -s -m "feat(graph): orbit system nodes by call depth from the entry node"
```

---

### Task 2: Deterministic 2D map payloads

Build both Map-layer layouts in the graph layer so React decides nothing.

**Files:**
- Create: `codemble/graph/mapview.py`
- Modify: `codemble/graph/__init__.py`
- Test: `tests/test_mapview.py`

**Interfaces:**
- Consumes: `Graph`, `Region`, `RegionEdge`, `Node`, `Edge` from `codemble.adapters.base`.
- Produces:
  - `MAP_SCHEMA_VERSION: int = 1`
  - `build_map(graph: Graph) -> dict[str, object]`

**The exact payload shape.** Byte-stable: every list is emitted in a documented
sorted order and every float is rounded to 6 places.

```jsonc
{
  "schema_version": 1,
  "architecture": {
    "home": "app",                 // region id of Home, or null
    "layer_count": 4,
    "width": 960.0,
    "height": 480.0,
    "groups": [                    // sorted by id
      {"id": "pkg", "label": "pkg", "regions": ["pkg", "pkg.helpers"]}
    ],
    "boxes": [                     // emitted in (layer, column) order
      {
        "id": "app", "group": ".", "label": "app", "language": "python",
        "layer": 0, "column": 0, "reachable": true,
        "x": 400.0, "y": 0.0, "width": 160.0, "height": 56.0,
        "loc": 12, "node_count": 2,
        "understood": false, "home": true, "partial": false
      }
    ],
    "edges": [                     // sorted by (src, dst)
      {"src": "app", "dst": "pkg.util", "certain": true, "weight": 1, "cycle": false}
    ],
    "unreachable": ["ambiguous"]   // sorted region ids with no import path from Home
  },
  "workflow": {
    "root": "app",                 // selected entrypoint node id, or null
    "depth_count": 4,
    "width": 432.0,
    "height": 306.0,
    "nodes": [                     // pre-order emission; `order` is the index
      {
        "id": "app.main", "label": "main", "parent": "app",
        "relation": "root" | "defines" | "calls",
        "certain": true,           // certainty of the edge from `parent`
        "cut": null | "cycle" | "repeat",
        "depth": 1, "order": 1,
        "x": 28.0, "y": 34.0,
        "region": "app", "language": "python", "file": "app.py", "lineno": 8,
        "understood": false, "partial": false
      }
    ],
    "unreachable": ["ambiguous.invoke"]  // sorted node ids the tree never reaches
  }
}
```

**Two shape decisions worth knowing:**

1. **`relation` exists because the entrypoint is usually a *module* node.**
   `graph.selected_entrypoint` on the fixture is `"app"` — a module — and modules
   make no intra-project calls, so a pure call tree is a single node. The first
   hop is therefore module→member **containment**, which is real parser truth
   (`Node.region`), and it is labelled `"defines"` — never relabelled a call.
   Everything below is `"calls"` and carries the parser's own `certain` flag.
2. **`cut` bounds the tree.** `"cycle"` marks a child already on the ancestor
   path; `"repeat"` marks a node already emitted elsewhere (diamond call graphs
   would otherwise blow up exponentially). Both are emitted as visible leaves —
   never silently dropped.

Groups carry no geometry: boxes within a layer are ordered by `(group, region id)`
so same-directory modules sit adjacent in each row, which gives "grouped by
directory" without bounding rectangles that could overlap across layers.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mapview.py`:

```python
"""Deterministic 2D map payloads for the learner-facing Map layer."""

from __future__ import annotations

import json
from pathlib import Path

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph import build_map

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def test_map_payload_is_byte_stable_for_one_graph() -> None:
    first = build_map(PythonAstAdapter().parse(FIXTURE))
    second = build_map(PythonAstAdapter().parse(FIXTURE))

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["schema_version"] == 1


def test_architecture_layers_follow_the_longest_import_path_from_home() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    layers = {box["id"]: box["layer"] for box in architecture["boxes"]}

    assert architecture["home"] == "app"
    assert layers["app"] == 0
    assert layers["pkg.helpers"] == 1
    assert layers["pkg.service"] == 1
    # app imports pkg.util directly, but app -> pkg.service -> pkg.util is
    # longer, and the longest path is what puts a module below all its callers.
    assert layers["pkg.util"] == 2
    assert layers["shared"] == 2
    assert architecture["layer_count"] == 4
    assert architecture["unreachable"] == [
        "ambiguous",
        "api",
        "broken",
        "cli",
        "pkg",
        "runner.__main__",
    ]
    assert all(layers[region] == 3 for region in architecture["unreachable"])
    assert all(
        box["reachable"] is False for box in architecture["boxes"] if box["layer"] == 3
    )


def test_architecture_groups_regions_by_source_directory() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    groups = {group["id"]: group["regions"] for group in architecture["groups"]}

    assert list(groups) == [".", "pkg", "runner"]
    assert groups["pkg"] == ["pkg", "pkg.helpers", "pkg.service", "pkg.util"]
    assert groups["runner"] == ["runner.__main__"]


def test_architecture_edges_keep_parser_certainty_and_weight() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    edges = {(edge["src"], edge["dst"]): edge for edge in architecture["edges"]}

    assert edges[("app", "pkg.service")]["certain"] is True
    assert edges[("app", "pkg.service")]["weight"] == 1
    assert all(edge["cycle"] is False for edge in architecture["edges"])


def test_workflow_expands_the_entrypoint_and_names_every_relation() -> None:
    workflow = build_map(PythonAstAdapter().parse(FIXTURE))["workflow"]
    rows = [
        (row["id"], row["depth"], row["relation"], row["certain"], row["cut"])
        for row in workflow["nodes"]
    ]

    assert workflow["root"] == "app"
    assert rows[0] == ("app", 0, "root", True, None)
    # The parser never observed a call from the module to its own function, so
    # the first hop is containment and is labelled as such -- never as a call.
    assert rows[1] == ("app.main", 1, "defines", True, None)
    assert ("pkg.service.Service.run", 2, "calls", False, None) in rows
    assert ("pkg.util.normalize", 3, "calls", True, None) in rows
    assert ("pkg.util.normalize", 3, "calls", True, "repeat") in rows
    assert workflow["depth_count"] == 4
    assert "ambiguous.invoke" in workflow["unreachable"]
    assert "app.main" not in workflow["unreachable"]


def test_cycles_are_cut_deterministically_and_stay_visible(tmp_path: Path) -> None:
    (tmp_path / "alpha.py").write_text(
        "import beta\n\n\ndef ping() -> None:\n    beta.pong()\n\n\n"
        'if __name__ == "__main__":\n    ping()\n',
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text(
        "import alpha\n\n\ndef pong() -> None:\n    alpha.ping()\n",
        encoding="utf-8",
    )

    payload = build_map(PythonAstAdapter().parse(tmp_path))
    repeated = build_map(PythonAstAdapter().parse(tmp_path))
    architecture = payload["architecture"]

    assert json.dumps(payload, sort_keys=True) == json.dumps(repeated, sort_keys=True)
    assert [edge["cycle"] for edge in architecture["edges"]].count(True) == 1
    # A cut edge is still drawn and still carries its parser certainty.
    assert all(edge["certain"] for edge in architecture["edges"])
    assert "cycle" in [row["cut"] for row in payload["workflow"]["nodes"]]


def test_a_graph_without_home_marks_every_region_unreachable(tmp_path: Path) -> None:
    (tmp_path / "solo.py").write_text("def work() -> None:\n    pass\n", encoding="utf-8")

    payload = build_map(PythonAstAdapter().parse(tmp_path))

    assert payload["architecture"]["home"] is None
    assert payload["architecture"]["unreachable"] == ["solo"]
    assert payload["architecture"]["layer_count"] == 1
    assert payload["workflow"]["root"] is None
    assert payload["workflow"]["nodes"] == []
    assert payload["workflow"]["unreachable"] == ["solo", "solo.work"]
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_mapview.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_map' from 'codemble.graph'`.

- [ ] **Step 3: Implement the map builder**

Create `codemble/graph/mapview.py`:

```python
"""Deterministic 2D map layouts for the learner-facing Map layer.

The galaxy layer owns 3D coordinates; this module owns the flat ones.  Both are
computed here so the renderer stays a pure consumer: React draws these numbers
and decides nothing.  No clock, no RNG, and no set iteration reaches the output.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from codemble.adapters.base import Graph

MAP_SCHEMA_VERSION = 1

_MAP_WIDTH = 960.0
_ROW_HEIGHT = 120.0
_BOX_WIDTH = 160.0
_BOX_HEIGHT = 56.0
_COLUMN_GAP = 24.0
_TREE_INDENT = 28.0
_TREE_ROW = 34.0
_TREE_LABEL_WIDTH = 320.0


def build_map(graph: Graph) -> dict[str, object]:
    """Return both 2D map payloads.  Same graph in, same bytes out."""

    return {
        "schema_version": MAP_SCHEMA_VERSION,
        "architecture": _architecture(graph),
        "workflow": _workflow(graph),
    }


def _architecture(graph: Graph) -> dict[str, object]:
    regions = {region.id: region for region in graph.regions}
    region_ids = sorted(regions)
    home = next((region.id for region in graph.regions if region.home), None)
    routes = sorted(graph.region_edges, key=lambda edge: (edge.src, edge.dst))

    successors: dict[str, list[str]] = defaultdict(list)
    for edge in routes:
        successors[edge.src].append(edge.dst)
    cut = _back_edges(([home] if home else []) + region_ids, successors)

    layers: dict[str, int] = {}
    if home is not None:
        layers[home] = 0
        for _ in range(len(region_ids)):
            changed = False
            for edge in routes:
                if (edge.src, edge.dst) in cut or edge.src not in layers:
                    continue
                if layers.get(edge.dst, -1) < layers[edge.src] + 1:
                    layers[edge.dst] = layers[edge.src] + 1
                    changed = True
            if not changed:
                break

    unreachable = [region_id for region_id in region_ids if region_id not in layers]
    outer_layer = (max(layers.values()) + 1) if layers else 0
    layer_of = {region_id: layers.get(region_id, outer_layer) for region_id in region_ids}
    layer_count = (max(layer_of.values()) + 1) if region_ids else 0

    module_file = {node.region: node.file for node in graph.nodes if node.kind == "module"}
    group_of = {
        region_id: _directory(module_file.get(region_id, region_id))
        for region_id in region_ids
    }
    grouped: dict[str, list[str]] = defaultdict(list)
    for region_id in region_ids:
        grouped[group_of[region_id]].append(region_id)

    rows: dict[int, list[str]] = defaultdict(list)
    for region_id in sorted(region_ids, key=lambda item: (group_of[item], item)):
        rows[layer_of[region_id]].append(region_id)

    partial_regions = {node.region for node in graph.nodes if node.partial}
    boxes: list[dict[str, object]] = []
    for layer_index in sorted(rows):
        members = rows[layer_index]
        span = len(members) * _BOX_WIDTH + (len(members) - 1) * _COLUMN_GAP
        start = (_MAP_WIDTH - span) / 2.0
        for column, region_id in enumerate(members):
            region = regions[region_id]
            boxes.append(
                {
                    "id": region_id,
                    "group": group_of[region_id],
                    "label": region_id,
                    "language": region.language,
                    "layer": layer_index,
                    "column": column,
                    "reachable": region_id in layers,
                    "x": _rounded(start + column * (_BOX_WIDTH + _COLUMN_GAP)),
                    "y": _rounded(layer_index * _ROW_HEIGHT),
                    "width": _BOX_WIDTH,
                    "height": _BOX_HEIGHT,
                    "loc": region.loc,
                    "node_count": region.node_count,
                    "understood": region.understood,
                    "home": region.home,
                    "partial": region_id in partial_regions,
                }
            )

    return {
        "home": home,
        "layer_count": layer_count,
        "width": _MAP_WIDTH,
        "height": _rounded(max(layer_count, 1) * _ROW_HEIGHT),
        "groups": [
            {"id": group_id, "label": group_id, "regions": sorted(grouped[group_id])}
            for group_id in sorted(grouped)
        ],
        "boxes": boxes,
        "edges": [
            {
                "src": edge.src,
                "dst": edge.dst,
                "certain": edge.certain,
                "weight": edge.weight,
                "cycle": (edge.src, edge.dst) in cut,
            }
            for edge in routes
        ],
        "unreachable": unreachable,
    }


def _workflow(graph: Graph) -> dict[str, object]:
    nodes = {node.id: node for node in graph.nodes}
    calls: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    called_by: dict[str, set[str]] = defaultdict(set)
    for edge in sorted(graph.edges, key=lambda item: (item.src, item.dst, item.lineno)):
        if edge.kind != "call" or edge.external:
            continue
        if edge.src not in nodes or edge.dst not in nodes or edge.src == edge.dst:
            continue
        if edge.dst not in {target for target, _ in calls[edge.src]}:
            calls[edge.src].append((edge.dst, edge.certain))
        called_by[edge.dst].add(edge.src)

    members: dict[str, list[str]] = defaultdict(list)
    for node in graph.nodes:
        if node.kind != "module":
            members[node.region].append(node.id)

    def children(node_id: str) -> list[tuple[str, bool, str]]:
        node = nodes[node_id]
        if node.kind == "module":
            # Containment is parser truth (Node.region); it is never relabelled
            # a call, because the parser observed no call from module to member.
            siblings = set(members[node.region])
            return [
                (member, True, "defines")
                for member in sorted(members[node.region])
                if not (called_by[member] & siblings)
            ]
        return [(target, certain, "calls") for target, certain in sorted(calls[node_id])]

    rows: list[dict[str, object]] = []
    emitted: set[str] = set()

    def emit(
        node_id: str,
        depth: int,
        parent: str | None,
        certain: bool,
        relation: str,
        cut: str | None,
    ) -> None:
        node = nodes[node_id]
        order = len(rows)
        rows.append(
            {
                "id": node_id,
                "label": node.name,
                "parent": parent,
                "relation": relation,
                "certain": certain,
                "cut": cut,
                "depth": depth,
                "order": order,
                "x": _rounded(depth * _TREE_INDENT),
                "y": _rounded(order * _TREE_ROW),
                "region": node.region,
                "language": node.language,
                "file": node.file,
                "lineno": node.lineno,
                "understood": node.understood,
                "partial": node.partial,
            }
        )
        emitted.add(node_id)

    # Recursion depth is bounded by the visit-once rule below: a node expands at
    # most once, so the stack can never exceed the number of graph nodes.
    def walk(
        node_id: str,
        depth: int,
        parent: str | None,
        certain: bool,
        relation: str,
        ancestors: frozenset[str],
    ) -> None:
        emit(node_id, depth, parent, certain, relation, None)
        for target, target_certain, target_relation in children(node_id):
            if target in ancestors:
                emit(target, depth + 1, node_id, target_certain, target_relation, "cycle")
            elif target in emitted:
                emit(target, depth + 1, node_id, target_certain, target_relation, "repeat")
            else:
                walk(
                    target,
                    depth + 1,
                    node_id,
                    target_certain,
                    target_relation,
                    ancestors | {target},
                )

    root = graph.selected_entrypoint if graph.selected_entrypoint in nodes else None
    if root is not None:
        walk(root, 0, None, True, "root", frozenset({root}))

    depth_count = max((int(row["depth"]) for row in rows), default=-1) + 1
    return {
        "root": root,
        "depth_count": depth_count,
        "width": _rounded(max(depth_count, 1) * _TREE_INDENT + _TREE_LABEL_WIDTH),
        "height": _rounded(max(len(rows), 1) * _TREE_ROW),
        "nodes": rows,
        "unreachable": sorted(node_id for node_id in nodes if node_id not in emitted),
    }


def _back_edges(roots: list[str], successors: dict[str, list[str]]) -> set[tuple[str, str]]:
    """Return the routes that close an import cycle, found in one sorted DFS.

    Iterative so a deep import chain cannot exhaust the interpreter stack.
    """

    cut: set[tuple[str, str]] = set()
    state: dict[str, int] = {}

    def visit(start: str) -> None:
        state[start] = 1
        stack = [(start, list(reversed(successors.get(start, []))))]
        while stack:
            node, pending = stack[-1]
            if not pending:
                state[node] = 2
                stack.pop()
                continue
            child = pending.pop()
            if state.get(child) == 1:
                cut.add((node, child))
            elif child not in state:
                state[child] = 1
                stack.append((child, list(reversed(successors.get(child, [])))))

    for root in roots:
        if root not in state:
            visit(root)
    return cut


def _directory(file: str) -> str:
    parent = str(PurePosixPath(file).parent)
    return "." if parent in {"", "."} else parent


def _rounded(value: float) -> float:
    return round(value, 6)


__all__ = ["MAP_SCHEMA_VERSION", "build_map"]
```

Then export it from `codemble/graph/__init__.py` — replace the file with:

```python
"""Language-tagged graph helpers and render-ready metadata."""

from codemble.adapters.base import ConceptAnnotation, Edge, Graph, Node, Region, RegionEdge
from codemble.graph.finalize import GraphFinalizationError, finalize_graph
from codemble.graph.layout import layout_graph
from codemble.graph.mapview import MAP_SCHEMA_VERSION, build_map

__all__ = [
    "MAP_SCHEMA_VERSION",
    "ConceptAnnotation",
    "Edge",
    "Graph",
    "GraphFinalizationError",
    "Node",
    "Region",
    "RegionEdge",
    "build_map",
    "finalize_graph",
    "layout_graph",
]
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `python3 -m pytest tests/test_mapview.py -v`
Expected: PASS — 7 passed.

- [ ] **Step 5: Run the full suite and lint**

Run: `python3 -m pytest -q && python3 -m ruff check .`
Expected: `139 passed` and `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add codemble/graph/mapview.py codemble/graph/__init__.py tests/test_mapview.py
git commit -s -m "feat(graph): deterministic architecture and workflow map layouts"
```

---

### Task 3: `GET /api/map`

**Files:**
- Modify: `codemble/server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `build_map` from `codemble.graph` (Task 2); `CheckService.graph()`.
- Produces: `GET /api/map` → the Task 2 payload; `409` with
  `{"detail": "No project selected yet."}` before a project is bound.

The endpoint reads `checks.graph()` — the **hydrated** graph — so `understood`
and the selected Home in the map always match what the galaxy shows.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py` (match the surrounding client-fixture style —
reuse whatever `TestClient` helper the file already defines for a bound project;
the two tests below assume the same `client` fixture the existing graph tests use):

```python
def test_map_endpoint_serves_both_deterministic_layouts(client) -> None:  # type: ignore[no-untyped-def]
    first = client.get("/api/map")
    second = client.get("/api/map")

    assert first.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["schema_version"] == 1
    assert payload["architecture"]["home"] == "app"
    assert payload["workflow"]["root"] == "app"
    assert {box["id"] for box in payload["architecture"]["boxes"]} == {
        region["id"] for region in client.get("/api/graph").json()["regions"]
    }


def test_map_endpoint_refuses_before_a_project_is_bound() -> None:
    app = create_app(picker=PickerConfig(browse_root=Path.home()))

    with TestClient(app) as unbound:
        response = unbound.get("/api/map")

    assert response.status_code == 409
    assert response.json()["detail"] == "No project selected yet."
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `python3 -m pytest tests/test_server.py -k map -v`
Expected: FAIL — the first returns `404` (route not registered) instead of `200`.

- [ ] **Step 3: Add the endpoint**

In `codemble/server/app.py`, extend the graph import (line 16):

```python
from codemble.adapters.base import Graph
from codemble.graph import build_map
```

Then add the route immediately after the existing `get_graph` handler (which
ends at line 208):

```python
    @app.get("/api/map")
    def get_map() -> dict[str, object]:
        # The hydrated graph, so lit regions and the selected Home in the 2D map
        # can never disagree with the galaxy the learner just came from.
        checks, _ = _services()
        return build_map(checks.graph())
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `python3 -m pytest tests/test_server.py -k map -v`
Expected: PASS — 2 passed.

- [ ] **Step 5: Run the full suite and lint**

Run: `python3 -m pytest -q && python3 -m ruff check .`
Expected: `141 passed` and `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add codemble/server/app.py tests/test_server.py
git commit -s -m "feat(server): serve GET /api/map with both 2D layouts"
```

---

### Task 4: App-side visual tokens

**Files:**
- Modify: `web/src/tokens.css`
- Modify: `web/src/GalaxyCanvas.jsx` (`readPalette` only)

**Interfaces:**
- Produces: CSS custom properties `--cm-neb-python`, `--cm-neb-js`,
  `--cm-neb-ts`, `--cm-star-halo`; `readPalette()` gains keys
  `nebPython`, `nebJs`, `nebTs`, `starHalo`.

**Resolved ambiguity — the spec's starting values fail the legend floor.** Spec
§4 offers starting values and says to tune them and WCAG-check anything used as
UI, and the repo rule is "Legend swatches for tints must pass the 4.5:1 floor
against the ground". Measured against `--cm-ground-2` (`#101a3e`, the legend
panel's own background) the spec's values score **3.19:1 (python), 4.46:1 (js),
3.86:1 (ts) — all three fail.** The values below hold each named hue (within
1°) and raise only lightness until both grounds clear 4.5:1:

| Token | Value | vs `--cm-ground` | vs `--cm-ground-2` | Relative luminance |
| --- | --- | --- | --- | --- |
| `--cm-neb-python` (rokushō) | `rgb(89 144 121)` | 5.30:1 | 4.59:1 | 0.2345 |
| `--cm-neb-js` (fuji) | `rgb(139 126 169)` | 5.27:1 | 4.56:1 | 0.2328 |
| `--cm-neb-ts` (asagi) | `rgb(86 139 170)` | 5.28:1 | 4.57:1 | 0.2335 |

All three sit **below `--cm-ink-2` (L 0.3886, the unlit ramp ceiling) and far
below `--cm-star-high` (L 0.5975)**, so amber's monopoly holds. The fog stays
faint because *alpha lives in the material*, not the token — Task 6 renders these
at low opacity while the legend renders them at full strength.

`--cm-star-halo` keeps the spec's `rgb(242 239 233)`. It is the **neutral base of
the halo sprite texture**, multiplied by each node's own colour by
`SpriteMaterial.color`; it is never a legend swatch and never rendered
untinted, so an unlit node's halo takes the unlit ramp colour and a lit node's
takes amber. The ordering is preserved structurally.

- [ ] **Step 1: Add the tokens**

In `web/src/tokens.css`, add these four declarations inside the existing
`:root { ... }` block, immediately after the `--cm-node-unlit` declaration:

```css
  /* Language nebula tints. Plain rgb() only -- readPalette hands the authored
     text to WebGL, and a color-mix() token renders black. Lightness is tuned so
     a legend swatch clears 4.5:1 on --cm-ground AND --cm-ground-2 while staying
     below --cm-ink-2, so no nebula can outshine a lit star. Fog alpha lives in
     the material, not here. */
  --cm-neb-python: rgb(89 144 121);
  --cm-neb-js: rgb(139 126 169);
  --cm-neb-ts: rgb(86 139 170);
  /* Neutral base for the halo sprite texture. Always multiplied by the node's
     own colour, so it can never brighten an unlit node past a lit one. */
  --cm-star-halo: rgb(242 239 233);
```

- [ ] **Step 2: Expose them through `readPalette`**

In `web/src/GalaxyCanvas.jsx`, extend the frozen object returned by
`readPalette()` (lines 222–234) — add these four entries after `star`:

```javascript
    star: value("--cm-star-high"),
    starHalo: value("--cm-star-halo"),
    nebPython: value("--cm-neb-python"),
    nebJs: value("--cm-neb-js"),
    nebTs: value("--cm-neb-ts"),
```

- [ ] **Step 3: Build and verify the tokens resolve**

Run: `cd web && npm run check`
Expected: both check scripts print their "contracts passed" lines and
`vite build` completes, writing `codemble/web_dist`.

Then start the app against the fixture and confirm the tokens resolve to real
`rgb()` triples rather than empty strings:

```bash
codemble ./tests/fixtures/sampleproj
```

In the browser console, run:

```javascript
["--cm-neb-python","--cm-neb-js","--cm-neb-ts","--cm-star-halo"]
  .map(t => [t, getComputedStyle(document.documentElement).getPropertyValue(t).trim()])
```

Expected: four non-empty `rgb(...)` strings. An empty string means the token did
not land in the built stylesheet.

- [ ] **Step 4: Commit**

```bash
git add web/src/tokens.css web/src/GalaxyCanvas.jsx codemble/web_dist
git commit -s -m "feat(web): add language nebula and star-halo canvas tokens"
```

---

### Task 5: Session layer, map, and hint state

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: `fetchMap(signal)` (added here to both adapters); `mode` from Phase A.
- Produces:
  - State: `layer`, `mapTab`, `mapData`, `mapError`, `coachmarksSeen`
  - Events: `SET_LAYER` (`{layer}`), `SET_MAP_TAB` (`{tab}`), `DISMISS_COACHMARKS`
  - Derived in `deriveSnapshot`: `hint` (object\|null) shaped
    `{regionId: string, hops: number, reason: string}`

**Hint semantics.** The nearest **unlit** region to Home counted in **route
hops**, ties broken by region id, `null` in expert mode or when nothing is unlit.
Hops are counted over `region_edges` treated as **undirected** — a route connects
two modules regardless of which one imports the other, and a learner should still
be pointed at a module that imports Home. Regions with no route path get
`Infinity` hops so they sort last but remain eligible when they are the only
unlit regions left. It is pure graph truth; no model participates.

- [ ] **Step 1: Write the failing assertions**

In `web/scripts/check_learner_session.mjs`, insert this block immediately before
the closing `function makeGraph(...)` declaration (i.e. after the picker race
regression block that ends with `raceSession.dispose();`):

```javascript
// Phase B: layer, map tab, map data, coach-marks, and the derived hint.
const mapPayload = {
  schema_version: 1,
  architecture: { home: "app.py", boxes: [], edges: [], groups: [], unreachable: [] },
  workflow: { root: null, nodes: [], unreachable: [] },
};
const layerSession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph }),
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

// The hint is expert-mode-silent and graph-derived.
assert.equal(layerSession.getSnapshot().hint, null, "expert mode shows no hint");
await layerSession.dispatch({ type: "SET_MODE", mode: "easy" });
layerSnapshot = layerSession.getSnapshot();
assert.equal(layerSnapshot.layer, "map", "an explicit layer choice survives a mode flip");
assert.equal(
  layerSnapshot.hint.regionId,
  "main.ts",
  "the hint is the nearest unlit region to Home",
);
assert.equal(layerSnapshot.hint.hops, Infinity, "an unrouted region still reports its distance");
layerSession.dispose();

// Easy mode defaults to the map layer when the learner has not chosen one.
const easySession = createLearnerSession({
  adapter: {
    ...createInMemoryLearnerSessionAdapter({ graph: makeGraph({ understood: true }) }),
    async fetchMap() {
      return mapPayload;
    },
    async fetchMode() {
      return { mode: "easy" };
    },
  },
  clock,
});
await easySession.start();
assert.equal(easySession.getSnapshot().layer, "map", "easy mode lands on the map");
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
```

- [ ] **Step 2: Run the check and watch it fail**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL — `AssertionError [ERR_ASSERTION]: expert mode lands on the
galaxy` (`undefined !== 'galaxy'`), because `layer` does not exist yet.

- [ ] **Step 3: Implement the session state**

In `web/src/learnerSession.js`:

**(a)** Add the five fields to the initial state object passed to
`deriveSnapshot` in `createLearnerSession` — insert after `picker: null,`:

```javascript
    picker: null,
    layer: "galaxy",
    layerChosen: false,
    mapTab: "architecture",
    mapData: null,
    mapError: "",
    coachmarksSeen: false,
```

**(b)** Add a controller alongside the existing ones (after `let pickerController = null;`):

```javascript
  let mapController = null;
```

**(c)** Add the three event cases to `dispatch`, immediately before `default:`:

```javascript
      case "SET_LAYER":
        return setLayer(event.layer);
      case "SET_MAP_TAB":
        commit({ mapTab: event.tab });
        return undefined;
      case "DISMISS_COACHMARKS":
        commit({ coachmarksSeen: true });
        return undefined;
```

**(d)** Add the layer/map functions immediately above `function illuminateRegion(`:

```javascript
  async function setLayer(layer) {
    commit({ layer, layerChosen: true });
    if (layer === "map" && !snapshot.mapData) return loadMap();
    return undefined;
  }

  async function loadMap() {
    abortController(mapController);
    mapController = new AbortController();
    const controller = mapController;
    commit({ mapError: "" });
    try {
      const mapData = await adapter.fetchMap(controller.signal);
      if (!controller.signal.aborted) commit({ mapData, mapError: "" });
      return mapData;
    } catch (requestError) {
      if (
        mapController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError)
      ) {
        // Scoped to the map layer on purpose: the galaxy must stay usable.
        commit({ mapError: errorMessage(requestError), mapData: null });
      }
      return undefined;
    }
  }
```

**(e)** Include `mapController` in the `dispose()` abort list and null it out
alongside the others.

**(f)** Phase A's mode load must set the default layer only while the learner has
not chosen one. Wherever Phase A commits the fetched mode during `start()`, also
pass the default layer — the mode handler becomes:

```javascript
  function applyMode(mode) {
    commit({
      mode,
      layer: snapshot.layerChosen ? snapshot.layer : mode === "easy" ? "map" : "galaxy",
    });
  }
```

and `SET_MODE` routes through the same `applyMode` so a mode flip never
overrides an explicit `SET_LAYER`.

**(g)** Derive the hint. In `deriveSnapshot`, add above the `return`:

```javascript
  const hint = focusedGraph ? nearestUnlitRegion(focusedGraph, state.mode) : null;
```

and include `hint,` in the returned object. Then add this module-level helper
beside the other private helpers at the bottom of the file:

```javascript
// Deterministic graph truth: the nearest unlit region to Home counted in route
// hops, ties broken by region id. Routes are walked undirected because a route
// connects two modules regardless of which one imports the other. No model,
// no heuristic, no stored state -- recomputed from the graph on every snapshot.
function nearestUnlitRegion(graph, mode) {
  if (mode !== "easy") return null;
  const unlit = graph.regions.filter((region) => !region.understood);
  if (!unlit.length) return null;
  const home = graph.regions.find((region) => region.home);
  const hops = new Map();
  if (home) {
    const neighbours = new Map();
    for (const edge of graph.region_edges) {
      if (!neighbours.has(edge.src)) neighbours.set(edge.src, []);
      if (!neighbours.has(edge.dst)) neighbours.set(edge.dst, []);
      neighbours.get(edge.src).push(edge.dst);
      neighbours.get(edge.dst).push(edge.src);
    }
    hops.set(home.id, 0);
    const queue = [home.id];
    while (queue.length) {
      const current = queue.shift();
      for (const next of (neighbours.get(current) ?? []).slice().sort()) {
        if (!hops.has(next)) {
          hops.set(next, hops.get(current) + 1);
          queue.push(next);
        }
      }
    }
  }
  const nearest = unlit
    .map((region) => ({
      regionId: region.id,
      hops: hops.has(region.id) ? hops.get(region.id) : Infinity,
    }))
    .sort(
      (left, right) => left.hops - right.hops || left.regionId.localeCompare(right.regionId),
    )[0];
  return {
    ...nearest,
    reason:
      nearest.hops === 0
        ? "Home is not lit yet."
        : Number.isFinite(nearest.hops)
          ? `${nearest.hops} ${nearest.hops === 1 ? "route" : "routes"} from Home.`
          : "No import route reaches it from Home.",
  };
}
```

**(h)** Add `fetchMap` to `createHttpLearnerSessionAdapter`'s returned object:

```javascript
    fetchMap(signal) {
      return request("/api/map", "Map request", { signal });
    },
```

**(i)** Add `fetchMap` to `createInMemoryLearnerSessionAdapter`'s returned object,
accepting an optional `map` fixture in its destructured options:

```javascript
    async fetchMap(signal) {
      throwIfAborted(signal);
      if (map === null) throw new Error("No in-memory map fixture.");
      return map;
    },
```

with `map = null` added to the destructured parameter list.

- [ ] **Step 4: Run the check and watch it pass**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: PASS — prints `learner-session contracts passed` then
`phase B layer + map contracts passed`.

- [ ] **Step 5: Build**

Run: `cd web && npm run check`
Expected: both scripts pass and `vite build` writes `codemble/web_dist`.

- [ ] **Step 6: Commit**

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): add layer, map, and derived-hint session state"
```

---

### Task 6: Canvas-generated halos, nebulae, and a seeded starfield

**No automated test.** This is pure WebGL rendering and the repo has no
JavaScript test framework (no jest, no vitest, no RTL) — this plan does not add
one. Verification is: build, run the app, and look, using the exact checks in
Step 4.

**Files:**
- Create: `web/src/galaxyMaterials.js`
- Modify: `web/src/GalaxyCanvas.jsx`
- Modify: `web/src/graphData.js`

**Interfaces:**
- Consumes: `readPalette()` keys from Task 4 (`starHalo`, `nebPython`, `nebJs`,
  `nebTs`); `graph.file_hashes` for the starfield seed.
- Produces, from `web/src/galaxyMaterials.js`:
  - `createDressing(palette) -> { halo(node), nebula(region), reticle(), dispose() }`
  - `createStarfield(seedText, palette) -> THREE.Points`
  - `seedFromHashes(fileHashes) -> string`
- Produces, from `web/src/graphData.js`:
  - `nebulaTintKey(language) -> "nebPython" | "nebJs" | "nebTs" | null`

- [ ] **Step 1: Write the builders module**

Create `web/src/galaxyMaterials.js`:

```javascript
import * as THREE from "three";

// Every texture here is drawn on a 2D canvas at runtime: no image assets ship,
// and the same code always produces the same bytes. Textures and materials are
// built once and shared, because these accessors run per node on every graph
// update and a texture per node would melt a mid-range laptop.

const HALO_TEXTURE_SIZE = 128;
const NEBULA_TEXTURE_SIZE = 256;

function radialTexture(size, stops) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const gradient = context.createRadialGradient(
    size / 2, size / 2, 0,
    size / 2, size / 2, size / 2,
  );
  for (const [offset, alpha] of stops) {
    gradient.addColorStop(offset, `rgba(255, 255, 255, ${alpha})`);
  }
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function ringTexture(size) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  context.strokeStyle = "rgba(255, 255, 255, 1)";
  context.lineWidth = size * 0.05;
  context.beginPath();
  context.arc(size / 2, size / 2, size * 0.4, 0, Math.PI * 2);
  context.stroke();
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function createDressing(palette) {
  const haloTexture = radialTexture(HALO_TEXTURE_SIZE, [
    [0, 0.85], [0.25, 0.42], [0.6, 0.1], [1, 0],
  ]);
  const nebulaTexture = radialTexture(NEBULA_TEXTURE_SIZE, [
    [0, 0.32], [0.45, 0.14], [0.8, 0.03], [1, 0],
  ]);
  const reticleTexture = ringTexture(HALO_TEXTURE_SIZE);
  const haloMaterials = new Map();
  const nebulaMaterials = new Map();

  function haloMaterial(color) {
    if (!haloMaterials.has(color)) {
      haloMaterials.set(
        color,
        new THREE.SpriteMaterial({
          map: haloTexture,
          // The white texture is multiplied by the node's own colour, so an
          // unlit node's halo can never be brighter than a lit one's.
          color: new THREE.Color(color).multiply(new THREE.Color(palette.starHalo)),
          blending: THREE.AdditiveBlending,
          transparent: true,
          depthWrite: false,
          opacity: 0.6,
        }),
      );
    }
    return haloMaterials.get(color);
  }

  return {
    // A billboard sprite: no geometry cost, always faces the camera.
    halo(node, radius) {
      const sprite = new THREE.Sprite(haloMaterial(node.color));
      sprite.scale.setScalar(radius * 6.5);
      sprite.renderOrder = -1;
      return sprite;
    },
    nebula(tint, radius) {
      if (!nebulaMaterials.has(tint)) {
        nebulaMaterials.set(
          tint,
          new THREE.SpriteMaterial({
            map: nebulaTexture,
            color: new THREE.Color(tint),
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false,
            // Alpha lives here, not in the token: the token has to survive a
            // 4.5:1 legend check, the fog has to stay a whisper.
            opacity: 0.16,
          }),
        );
      }
      const sprite = new THREE.Sprite(nebulaMaterials.get(tint));
      sprite.scale.setScalar(radius);
      sprite.renderOrder = -2;
      return sprite;
    },
    reticle(radius) {
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: reticleTexture,
          color: new THREE.Color(palette.orbit),
          transparent: true,
          depthWrite: false,
          depthTest: false,
        }),
      );
      sprite.scale.setScalar(radius * 5);
      sprite.renderOrder = 3;
      return sprite;
    },
    dispose() {
      haloTexture.dispose();
      nebulaTexture.dispose();
      reticleTexture.dispose();
      for (const material of haloMaterials.values()) material.dispose();
      for (const material of nebulaMaterials.values()) material.dispose();
      haloMaterials.clear();
      nebulaMaterials.clear();
    },
  };
}

// FNV-1a over the project's own file hashes. Same code -> same seed -> same sky.
export function seedFromHashes(fileHashes) {
  const entries = Object.entries(fileHashes ?? {}).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  return entries.map(([file, hash]) => `${file}:${hash}`).join("|");
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return function next() {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = Math.imul(state ^ (state >>> 15), 1 | state);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function fnv1a(text) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export function createStarfield(seedText, palette, count = 1400, radius = 1600) {
  const random = mulberry32(fnv1a(seedText));
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    // Uniform on a sphere shell, from the seeded stream only -- never Math.random.
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    const distance = radius * (0.65 + random() * 0.35);
    positions[index * 3] = distance * Math.sin(phi) * Math.cos(theta);
    positions[index * 3 + 1] = distance * Math.cos(phi);
    positions[index * 3 + 2] = distance * Math.sin(phi) * Math.sin(theta);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const points = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      // Dust, not stars: it must read as depth, never compete with a lit system.
      color: new THREE.Color(palette.nodeDim),
      size: 2.2,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
    }),
  );
  points.name = "codemble-starfield";
  return points;
}
```

- [ ] **Step 2: Add the tint lookup to `graphData.js`**

In `web/src/graphData.js`, add this exported helper after `shortLanguageLabel`:

```javascript
// Language gets its own visual channel (nebula tint) so it never competes with
// brightness, which belongs to centrality and understanding. Unknown languages
// return null and render no fog rather than borrowing another language's hue.
export function nebulaTintKey(language) {
  if (language === "python") return "nebPython";
  if (language === "javascript") return "nebJs";
  if (language === "typescript") return "nebTs";
  return null;
}
```

- [ ] **Step 3: Wire halos, nebulae, and the starfield into the canvas**

In `web/src/GalaxyCanvas.jsx`:

Add the imports:

```javascript
import { createDressing, createStarfield, seedFromHashes } from "./galaxyMaterials.js";
import { LEVELS, galaxyData, nebulaTintKey, nodeLabel, systemData } from "./graphData.js";
```

Add a ref beside the others:

```javascript
  const dressingRef = useRef(null);
```

Replace `makeMarker` (lines 183–204) with a dressing-aware version:

```javascript
function makeMarker(node, palette, dressing, focusedId) {
  const group = new THREE.Group();
  const radius = Math.cbrt(node.val ?? 1) * NODE_REL_SIZE;
  // Dimmed nodes keep their true colour and lose their glow. Dimming by
  // removing light rather than shifting hue keeps a lit star recognisably lit.
  if (!node.focusDim) group.add(dressing.halo(node, radius));
  if (node.kind === "region") {
    const tint = nebulaTintKey(node.language);
    if (tint) group.add(dressing.nebula(palette[tint], radius * 14));
  }
  if (node.home) {
    const homeRing = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 1.7, Math.max(0.18, radius * 0.07), 8, 36),
      new THREE.MeshBasicMaterial({ color: palette.home }),
    );
    homeRing.rotation.x = Math.PI / 2.8;
    group.add(homeRing);
  }
  if (node.selected) {
    const selectedRing = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 2.1, Math.max(0.16, radius * 0.05), 6, 24),
      new THREE.MeshBasicMaterial({ color: palette.orbit }),
    );
    selectedRing.rotation.x = Math.PI / 2.8;
    group.add(selectedRing);
  }
  if (node.id === focusedId) group.add(dressing.reticle(radius));
  return group;
}
```

In the mount effect, build the dressing before the renderer and pass it in:

```javascript
      const dressing = createDressing(palette);
      dressingRef.current = dressing;
      const renderer = ForceGraph3D()(host)
```

and change the `nodeThreeObject` accessor to:

```javascript
        .nodeThreeObject((node) => makeMarker(node, palette, dressing, focusedIdRef.current))
```

`focusedIdRef` is a plain ref mirroring the focused node's id so the accessor
never closes over stale state — declare it beside `dressingRef`:

```javascript
  const focusedIdRef = useRef(null);
```

and keep it current with an effect:

```javascript
  useEffect(() => {
    focusedIdRef.current = data.nodes[focusedIndex]?.id ?? null;
    rendererRef.current?.refresh();
  }, [data.nodes, focusedIndex]);
```

Extend the mount effect's cleanup to dispose the dressing:

```javascript
      return () => {
        resize.disconnect();
        cancelAnimationFrame(hideNavigationHint);
        renderer.pauseAnimation();
        dressing.dispose();
        dressingRef.current = null;
        host.replaceChildren();
        rendererRef.current = null;
      };
```

Finally, add the seeded starfield in its own effect, after the data effect:

```javascript
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return undefined;
    const scene = renderer.scene();
    const previous = scene.getObjectByName("codemble-starfield");
    if (previous) {
      scene.remove(previous);
      previous.geometry.dispose();
      previous.material.dispose();
    }
    // Seeded by the project's own file hashes: same code, same sky, every run.
    const starfield = createStarfield(seedFromHashes(graph.file_hashes), palette);
    scene.add(starfield);
    return () => {
      scene.remove(starfield);
      starfield.geometry.dispose();
      starfield.material.dispose();
    };
  }, [graph.file_hashes, palette]);
```

- [ ] **Step 4: Build, then verify by running the app**

```bash
cd web && npm run check
```
Expected: both check scripts pass; `vite build` writes `codemble/web_dist`.

```bash
codemble ./tests/fixtures/sampleproj
```

Confirm by eye, at galaxy level:
1. Every star system carries a soft glow, and a **lit (amber) system is visibly
   brighter than every unlit one** — this is the amber-monopoly check.
2. Star systems sit in faint coloured fog; run against a mixed project
   (`codemble ./tests/fixtures/polyglot`) and confirm Python/JS/TS fog differ.
3. A dust field is visible behind the systems.
4. **Same code → same sky:** reload the page twice and confirm the dust pattern
   is identical. Then run `codemble ./tests/fixtures/polyglot` and confirm it is
   a *different* pattern. Identical across reloads but different across projects
   is the pass condition.
5. Browser console shows no `THREE` warnings and no black nodes (a black node
   means a token reached WebGL as unresolved text).

- [ ] **Step 5: Commit**

```bash
git add web/src/galaxyMaterials.js web/src/GalaxyCanvas.jsx web/src/graphData.js codemble/web_dist
git commit -s -m "feat(web): add halo sprites, language nebulae, and a seeded starfield"
```

---

### Task 7: Bloom, focus dimming, reticle, and certain-call particles

**No automated test** — same reason as Task 6. Verified by running the app and
by the `?benchmark` reading in Step 5.

**Files:**
- Create: `web/src/galaxyEffects.js`
- Modify: `web/src/GalaxyCanvas.jsx`
- Modify: `web/src/graphData.js`

**Interfaces:**
- Consumes: `renderer.postProcessingComposer()`, `renderer.scene()`,
  `renderer.camera()`, `renderer.renderer()`.
- Produces, from `web/src/galaxyEffects.js`:
  - `attachBloom(renderer) -> { pass: UnrealBloomPass, composer: EffectComposer, dispose() }`
- Produces, from `web/src/graphData.js`: `systemData(...)` nodes gain
  `focusDim: boolean`; links gain `focusDim: boolean` and keep `certain`.

- [ ] **Step 1: Write the bloom module**

Create `web/src/galaxyEffects.js`:

```javascript
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import * as THREE from "three";

// 3d-force-graph builds the composer already seeded with a RenderPass and always
// renders through it, so bloom is one addPass. Verified against 3d-force-graph
// 1.80.0 / three 0.185.1.
const BLOOM_STRENGTH = 0.9;
const BLOOM_RADIUS = 0.45;
// Tuned so a lit amber star blooms hard and the unlit ramp barely does: the
// threshold sits above --cm-ink-2's luminance and below --cm-star-high's.
const BLOOM_THRESHOLD = 0.52;

export function attachBloom(renderer) {
  const composer = renderer.postProcessingComposer();
  // UnrealBloomPass's constructor resolution is overwritten on the first
  // composer resize, so the cap that actually survives is the pixel ratio:
  // at 1 the bloom mip chain stays in CSS pixels even on a retina display.
  composer.setPixelRatio(1);
  const pass = new UnrealBloomPass(
    new THREE.Vector2(composer._width ?? 1, composer._height ?? 1),
    BLOOM_STRENGTH,
    BLOOM_RADIUS,
    BLOOM_THRESHOLD,
  );
  composer.addPass(pass);
  return {
    pass,
    composer,
    dispose() {
      composer.removePass(pass);
      pass.dispose();
    },
  };
}
```

- [ ] **Step 2: Add focus flags to `systemData`**

In `web/src/graphData.js`, replace the whole `systemData` function with:

```javascript
export function systemData(graph, regionId, palette, { selectedId = null } = {}) {
  const members = graph.nodes.filter((node) => node.region === regionId);
  const memberIds = new Set(members.map((node) => node.id));
  const callEdges = graph.edges.filter(
    (edge) =>
      edge.kind === "call" &&
      !edge.external &&
      memberIds.has(edge.src) &&
      memberIds.has(edge.dst),
  );
  // Presentation of an already-computed edge list, not layout: which nodes the
  // selection touches. Study level fades the rest instead of dimming the whole
  // scene, so the selected node's connections stay readable.
  const connected = new Set(selectedId ? [selectedId] : []);
  if (selectedId) {
    for (const edge of callEdges) {
      if (edge.src === selectedId) connected.add(edge.dst);
      if (edge.dst === selectedId) connected.add(edge.src);
    }
  }
  return {
    nodes: members.map((node) => ({
      ...node,
      fx: node.system_x,
      fy: node.system_y,
      fz: node.system_z,
      val: sizeFromLoc(node.loc, 2.8, 11),
      color: node.understood
        ? palette.star
        : node.partial
          ? palette.routePossible
          : brightness(node.centrality, palette),
      selected: node.id === selectedId,
      focusDim: Boolean(selectedId) && !connected.has(node.id),
    })),
    links: callEdges.map((edge) => ({
      ...edge,
      source: edge.src,
      target: edge.dst,
      color: edge.certain ? palette.route : palette.routePossible,
      focusDim:
        Boolean(selectedId) && edge.src !== selectedId && edge.dst !== selectedId,
    })),
  };
}
```

`galaxyData`'s links get the same field so both levels share one accessor — add
`focusDim: false,` to the object spread inside `galaxyData`'s `links.map`, and
`focusDim: false,` to its `nodes.map`.

- [ ] **Step 3: Wire bloom, curvature, particles, and dimming into the canvas**

In `web/src/GalaxyCanvas.jsx`, add the import and a ref:

```javascript
import { attachBloom } from "./galaxyEffects.js";
```

```javascript
  const bloomRef = useRef(null);
```

In the mount effect, extend the renderer chain. Replace the existing
`.linkColor("color")`, `.linkOpacity(0.32)`, and `.linkWidth(...)` lines with:

```javascript
        .linkColor((link) => (link.focusDim ? palette.routePossible : link.color))
        .linkOpacity(0.32)
        .linkWidth((link) =>
          link.focusDim ? 0.4 : Math.min(2.2, 0.45 + (link.weight ?? 1) * 0.25),
        )
        .linkCurvature(0.12)
        // Particles drift only on CERTAIN call edges. A possible call stays
        // dashed and still, so motion can never imply proof.
        .linkDirectionalParticles((link) =>
          link.kind === "call" && link.certain && !link.focusDim ? 2 : 0,
        )
        .linkDirectionalParticleSpeed(0.006)
        .linkDirectionalParticleWidth(1.1)
        .linkDirectionalParticleColor(() => palette.orbit)
```

Immediately after the renderer chain and before `rendererRef.current = renderer;`:

```javascript
      bloomRef.current = attachBloom(renderer);
```

and in the cleanup, before `dressing.dispose();`:

```javascript
        bloomRef.current?.dispose();
        bloomRef.current = null;
```

Then stop the global study dim — in the data effect, replace

```javascript
      .nodeOpacity(level === LEVELS.STUDY ? 0.16 : 0.82)
```

with

```javascript
      // Study level no longer dims the whole scene to 0.16: focusDim removes the
      // glow from unconnected nodes instead, so the selection's connections stay
      // visible while everything else recedes.
      .nodeOpacity(0.82)
```

- [ ] **Step 4: Fix the benchmark so it measures the real frame**

In `web/src/GalaxyCanvas.jsx`, in the benchmark effect, replace the render loop
(lines 109–113) with:

```javascript
      const composer = graphRenderer.postProcessingComposer();
      const frameCount = 60;
      const startedAt = performance.now();
      for (let frame = 0; frame < frameCount; frame += 1) {
        // Must go through the composer: rendering the scene directly would skip
        // the bloom pass and report a framerate the learner never sees.
        composer.render();
      }
      webglRenderer.getContext().finish();
```

- [ ] **Step 5: Build, run, and read the benchmark**

```bash
cd web && npm run check
codemble ./tests/fixtures/polyglot
```

Confirm by eye:
1. Lit amber stars bloom noticeably; unlit stars barely glow. If unlit stars
   bloom, raise `BLOOM_THRESHOLD` — never lower it.
2. Edges curve slightly; **certain** call edges carry drifting particles and
   **possible** ones are still and dashed. Enter a system with a possible call
   (`pkg.service` in `tests/fixtures/sampleproj` has one) and confirm.
3. At study level the selected node and its call neighbours stay bright while the
   rest of the system recedes — the scene is not uniformly dark.
4. Arrow-key through nodes: the focused one shows a ruri ring.

**Benchmark.** The guard is `data.nodes.length >= 900` — the *scene* object
count, which at galaxy level is the number of **modules**. This repo has 70, and
the picker's scale cap is 300 files, so the benchmark cannot be reached through
the normal flow. Build a synthetic project and serve it directly:

```bash
python3 - <<'PY'
from pathlib import Path
import tempfile
root = Path(tempfile.mkdtemp(prefix="codemble-bench-"))
for index in range(1000):
    package = root / f"pkg{index // 50:02d}"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / f"mod{index:04d}.py").write_text(
        f"from pkg{(index + 1) % 20:02d}.mod{(index + 1) % 1000:04d} import work as nxt\n\n\n"
        f"def work() -> int:\n    return nxt() + {index}\n",
        encoding="utf-8",
    )
(root / "main.py").write_text(
    "from pkg00.mod0000 import work\n\n\ndef main() -> int:\n    return work()\n\n\n"
    'if __name__ == "__main__":\n    main()\n',
    encoding="utf-8",
)
print(root)
PY
```

Then serve that path and open it with `?benchmark`:

```bash
codemble --path <printed-path> --no-open
# then open http://127.0.0.1:<port>/?benchmark
```

After ~1s, read the figure:

```javascript
document.documentElement.dataset.codembleFps
```

Expected: a value comfortably above 30. Record it in the commit message. If it
is below 30, reduce `createStarfield`'s `count` and re-measure before committing
— do not lower the bloom threshold to buy frames.

- [ ] **Step 6: Commit**

```bash
git add web/src/galaxyEffects.js web/src/GalaxyCanvas.jsx web/src/graphData.js codemble/web_dist
git commit -s -m "feat(web): add bloom, edge particles, and study-level focus dimming"
```

---

### Task 8: The nebula dawn

**No automated test** — pure animation. Verified by running the app, including
with reduced motion forced on.

**Files:**
- Modify: `web/src/galaxyEffects.js`
- Modify: `web/src/GalaxyCanvas.jsx`

**Interfaces:**
- Consumes: `litRegionId` (already on the snapshot; Phase A passes it into the
  canvas — add the prop if it is not yet threaded through).
- Produces, from `web/src/galaxyEffects.js`:
  `runNebulaDawn({ scene, regionId, palette, onDone }) -> () => void` (returns a
  cancel function).

- [ ] **Step 1: Add the dawn driver**

Append to `web/src/galaxyEffects.js`:

```javascript
const DAWN_DURATION = 1200;

export function prefersReducedMotion() {
  return globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

// The one bold moment in the app: amber washes across the lit system's fog and
// its star flares. Reduced motion gets the finished lit state instantly -- not a
// faster animation, no animation at all.
export function runNebulaDawn({ scene, regionId, palette, onDone }) {
  const target = scene.getObjectByName(`codemble-system-${regionId}`);
  if (!target) {
    onDone?.();
    return () => {};
  }
  const sprites = [];
  target.traverse((child) => {
    if (child.isSprite) sprites.push([child, child.material.opacity, child.scale.x]);
  });
  const amber = new THREE.Color(palette.star);
  const originals = sprites.map(([sprite]) => sprite.material.color.clone());

  if (prefersReducedMotion()) {
    onDone?.();
    return () => {};
  }

  let frame = 0;
  const startedAt = performance.now();
  const step = () => {
    const progress = Math.min(1, (performance.now() - startedAt) / DAWN_DURATION);
    // Ease out: the flare arrives fast and settles, like a light coming up.
    const eased = 1 - (1 - progress) ** 3;
    const wash = Math.sin(progress * Math.PI);
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]).lerp(amber, wash * 0.85);
      sprite.material.opacity = baseOpacity + wash * 0.5;
      sprite.scale.setScalar(baseScale * (1 + wash * 0.45));
    });
    if (progress < 1) {
      frame = requestAnimationFrame(step);
      return;
    }
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]);
      sprite.material.opacity = baseOpacity;
      sprite.scale.setScalar(baseScale);
    });
    onDone?.();
  };
  frame = requestAnimationFrame(step);
  return () => {
    cancelAnimationFrame(frame);
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]);
      sprite.material.opacity = baseOpacity;
      sprite.scale.setScalar(baseScale);
    });
  };
}
```

Add `import * as THREE from "three";` at the top of the file if Step 1 of Task 7
did not already add it (it did — keep one import).

- [ ] **Step 2: Name each system group so the dawn can find it**

In `web/src/GalaxyCanvas.jsx`, inside `makeMarker`, immediately after
`const group = new THREE.Group();`:

```javascript
  group.name = node.kind === "region" ? `codemble-system-${node.id}` : `codemble-node-${node.id}`;
```

- [ ] **Step 3: Trigger the dawn on light-up**

Add `litRegionId` to the `GalaxyCanvas` props signature, then add this effect
after the starfield effect:

```javascript
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || !litRegionId) return undefined;
    return runNebulaDawn({
      scene: renderer.scene(),
      regionId: litRegionId,
      palette,
    });
  }, [litRegionId, palette]);
```

and extend the import:

```javascript
import { attachBloom, runNebulaDawn } from "./galaxyEffects.js";
```

In `web/src/App.jsx`, pass the prop through on the existing `<GalaxyCanvas .../>`:

```javascript
          litRegionId={litRegionId}
```

- [ ] **Step 4: Build and verify both motion modes**

```bash
cd web && npm run check
codemble ./tests/fixtures/sampleproj
```

1. At galaxy level, enter a system, pass all of its checks, and return to the
   galaxy. Expected: a ~1.2s amber wash across that system's fog with the star
   flaring, then a settle to the normal lit state.
2. Force reduced motion — in Chrome DevTools, **Rendering → Emulate CSS media
   feature `prefers-reduced-motion: reduce`** — reset progress and repeat.
   Expected: the system is simply lit, with **no wash and no flare at all**.
3. Confirm the system stays lit after the animation (the dawn restores the
   original sprite state; it must not leave the system stuck amber-bright or
   reset to unlit).

- [ ] **Step 5: Commit**

```bash
git add web/src/galaxyEffects.js web/src/GalaxyCanvas.jsx web/src/App.jsx codemble/web_dist
git commit -s -m "feat(web): add the nebula-dawn light-up moment"
```

---

### Task 9: The 2D Map layer

**No automated test for rendering.** The session state behind it is already
covered by Task 5's assertions; the SVG itself is verified by running the app.

**Files:**
- Create: `web/src/MapView.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `mapData` / `mapTab` / `mapError` from the session (Task 5); the
  `/api/map` payload shape (Task 2); `nebulaTintKey` (Task 6).
- Produces: `<MapView data mapTab mode onSelectTab onSelectRegion onSelectNode onRetry />`.

The Map layer must render **without WebGL**: `MapView` imports nothing from
`three` or `3d-force-graph`, and `App.jsx` must render it *instead of*
`GalaxyCanvas`, never alongside.

- [ ] **Step 1: Write the map components**

Create `web/src/MapView.jsx`:

```javascript
import { nebulaTintKey } from "./graphData.js";

// Every coordinate here comes from GET /api/map. This file draws numbers and
// decides nothing: no layout, no ordering, no layering happens client-side.

const TINT_VAR = {
  nebPython: "var(--cm-neb-python)",
  nebJs: "var(--cm-neb-js)",
  nebTs: "var(--cm-neb-ts)",
};

function tintFor(language) {
  const key = nebulaTintKey(language);
  return key ? TINT_VAR[key] : "var(--cm-hairline)";
}

export function MapView({
  data,
  mapTab,
  mode,
  error,
  onSelectTab,
  onSelectRegion,
  onSelectNode,
  onRetry,
}) {
  return (
    <section className="map-view" aria-label="Two-dimensional project map">
      <nav className="map-tabs" aria-label="Map view">
        <button
          type="button"
          aria-pressed={mapTab === "architecture"}
          onClick={() => onSelectTab("architecture")}
        >
          {mode === "easy" ? "How it fits together" : "Architecture"}
        </button>
        <button
          type="button"
          aria-pressed={mapTab === "workflow"}
          onClick={() => onSelectTab("workflow")}
        >
          {mode === "easy" ? "What runs first" : "Workflow"}
        </button>
      </nav>
      {error ? (
        <div className="map-state" role="alert">
          <h2>The map did not load.</h2>
          <p>{error} The galaxy layer is unaffected.</p>
          <button className="check-primary" type="button" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : !data ? (
        <p className="map-loading" aria-busy="true">Laying out parser evidence…</p>
      ) : mapTab === "architecture" ? (
        <ArchitectureMap
          architecture={data.architecture}
          mode={mode}
          onSelectRegion={onSelectRegion}
        />
      ) : (
        <WorkflowTree workflow={data.workflow} mode={mode} onSelectNode={onSelectNode} />
      )}
    </section>
  );
}

function ArchitectureMap({ architecture, mode, onSelectRegion }) {
  const boxes = new Map(architecture.boxes.map((box) => [box.id, box]));
  const padding = 32;
  return (
    <div className="map-scroll">
      <svg
        className="architecture-map"
        viewBox={`${-padding} ${-padding} ${architecture.width + padding * 2} ${architecture.height + padding * 2}`}
        role="img"
        aria-label={`${architecture.boxes.length} modules in ${architecture.layer_count} import layers from Home`}
      >
        <g className="architecture-map__edges">
          {architecture.edges.map((edge) => {
            const from = boxes.get(edge.src);
            const to = boxes.get(edge.dst);
            if (!from || !to) return null;
            return (
              <line
                key={`${edge.src}->${edge.dst}`}
                x1={from.x + from.width / 2}
                y1={from.y + from.height}
                x2={to.x + to.width / 2}
                y2={to.y}
                // Uncertainty stays visible in 2D exactly as it does in 3D.
                strokeDasharray={edge.certain ? undefined : "5 4"}
                className={edge.cycle ? "is-cycle" : undefined}
              />
            );
          })}
        </g>
        {architecture.boxes.map((box) => (
          <g
            key={box.id}
            className="architecture-map__box"
            data-understood={box.understood}
            data-home={box.home}
            data-reachable={box.reachable}
            data-partial={box.partial}
            transform={`translate(${box.x} ${box.y})`}
            role="button"
            tabIndex={0}
            aria-label={`${box.label}, ${box.node_count} structures, ${box.loc} lines${box.understood ? ", understood" : ", not yet understood"}${box.home ? ", Home" : ""}${box.reachable ? "" : ", no import route from Home"}`}
            onClick={() => onSelectRegion(box.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectRegion(box.id);
              }
            }}
          >
            <rect width={box.width} height={box.height} rx="3" />
            <rect className="box-tint" width="4" height={box.height} fill={tintFor(box.language)} />
            <text x="14" y="24">{box.label}</text>
            <text className="box-meta" x="14" y="42">
              {mode === "easy"
                ? `${box.node_count} ${box.node_count === 1 ? "piece" : "pieces"}`
                : `${box.node_count} nodes · ${box.loc} LOC`}
            </text>
          </g>
        ))}
      </svg>
      {architecture.unreachable.length ? (
        <p className="map-note">
          {architecture.unreachable.length}{" "}
          {architecture.unreachable.length === 1 ? "module has" : "modules have"} no import
          route from Home, so {architecture.unreachable.length === 1 ? "it sits" : "they sit"}{" "}
          in the bottom row rather than being placed by guesswork.
        </p>
      ) : null}
    </div>
  );
}

function WorkflowTree({ workflow, mode, onSelectNode }) {
  if (!workflow.root) {
    return (
      <div className="map-state">
        <h2>No Home is selected.</h2>
        <p>
          The workflow tree starts at your entrypoint. Pick Home and this tab will
          show what runs first, then what that calls.
        </p>
      </div>
    );
  }
  const rows = new Map(workflow.nodes.map((row) => [row.order, row]));
  return (
    <div className="map-scroll">
      <svg
        className="workflow-tree"
        viewBox={`-16 -16 ${workflow.width + 32} ${workflow.height + 32}`}
        role="img"
        aria-label={`Call tree from ${workflow.root}, ${workflow.nodes.length} steps deep to ${workflow.depth_count} levels`}
      >
        <g className="workflow-tree__edges">
          {workflow.nodes.map((row) => {
            if (row.parent === null) return null;
            const parent = [...rows.values()]
              .filter((candidate) => candidate.id === row.parent && candidate.order < row.order)
              .at(-1);
            if (!parent) return null;
            return (
              <path
                key={`${row.order}`}
                d={`M ${parent.x + 8} ${parent.y + 20} V ${row.y + 12} H ${row.x + 8}`}
                strokeDasharray={row.certain ? undefined : "5 4"}
              />
            );
          })}
        </g>
        {workflow.nodes.map((row) => (
          <g
            key={row.order}
            className="workflow-tree__row"
            data-understood={row.understood}
            data-cut={row.cut ?? undefined}
            data-relation={row.relation}
            transform={`translate(${row.x} ${row.y})`}
            role="button"
            tabIndex={0}
            aria-label={`${row.label} at ${row.file}:${row.lineno}${row.certain ? "" : ", possible call"}${row.cut === "cycle" ? ", repeats an earlier step" : ""}${row.cut === "repeat" ? ", already shown above" : ""}`}
            onClick={() => onSelectNode(row.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectNode(row.id);
              }
            }}
          >
            <circle cx="8" cy="16" r="4" />
            <text x="20" y="20">{row.label}</text>
            <text className="row-meta" x="20" y="20" dx={`${row.label.length * 0.62}em`}>
              {row.relation === "defines"
                ? mode === "easy" ? " — lives here" : " — defined in this module"
                : row.certain
                  ? ""
                  : " — possible call"}
              {row.cut === "cycle" ? " — loops back" : ""}
              {row.cut === "repeat" ? " — shown above" : ""}
            </text>
          </g>
        ))}
      </svg>
      {workflow.unreachable.length ? (
        <p className="map-note">
          {workflow.unreachable.length}{" "}
          {workflow.unreachable.length === 1 ? "structure is" : "structures are"} never
          reached from Home by a parser-proven call. They are listed as unreached rather
          than attached to the tree by guesswork.
        </p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Add the layer switcher and route the layer in `App.jsx`**

Add the import:

```javascript
import { MapView } from "./MapView.jsx";
```

Pull `layer`, `mapTab`, `mapData`, `mapError`, `mode`, and `hint` out of `state`
in the existing destructuring block.

Add this component beside the existing `LanguageFocus` function:

```javascript
function LayerSwitcher({ layer, mode, onChange }) {
  return (
    <nav className="layer-switcher" aria-label="View layer">
      {[
        { id: "galaxy", label: "Galaxy" },
        { id: "map", label: mode === "easy" ? "Diagram" : "Map" },
      ].map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={layer === option.id}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </nav>
  );
}
```

Render it in the header, immediately before `<LanguageFocus ... />`:

```javascript
        <LayerSwitcher
          layer={layer}
          mode={mode}
          onChange={(next) => session.dispatch({ type: "SET_LAYER", layer: next })}
        />
```

Then, inside `<section className="map-stage">`, replace the bare
`<GalaxyCanvas ... />` element with a layer switch:

```javascript
        {layer === "map" ? (
          <MapView
            data={mapData}
            mapTab={mapTab}
            mode={mode}
            error={mapError}
            onSelectTab={(tab) => session.dispatch({ type: "SET_MAP_TAB", tab })}
            onSelectRegion={(regionId) =>
              session.dispatch({
                type: "ADVANCE",
                node: focusedGraph.regions.find((region) => region.id === regionId),
              })
            }
            onSelectNode={(nodeId) =>
              session.dispatch({ type: "SELECT_STUDY_NODE", nodeId })
            }
            onRetry={() => session.dispatch({ type: "SET_LAYER", layer: "map" })}
          />
        ) : (
          <GalaxyCanvas
            graph={focusedGraph}
            level={level}
            region={region}
            selectedNode={selectedNode}
            litRegionId={litRegionId}
            onAdvance={(node) => session.dispatch({ type: "ADVANCE", node })}
            onRetreat={() => session.dispatch({ type: "RETREAT" })}
          />
        )}
```

- [ ] **Step 3: Style the map**

Append to `web/src/styles.css`:

```css
/* --- Layer switcher + 2D map ---------------------------------------------- */
.layer-switcher {
  display: inline-flex;
  border: 1px solid var(--cm-hairline);
  border-radius: var(--cm-radius);
  overflow: hidden;
}

.layer-switcher button {
  padding: var(--cm-space-2xs) var(--cm-space-sm);
  border: 0;
  background: transparent;
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
  cursor: pointer;
}

.layer-switcher button[aria-pressed="true"] {
  background: var(--cm-orbit-low);
  color: var(--cm-ink);
}

.map-view {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: var(--cm-space-sm);
  padding: var(--cm-space-md);
  background: var(--cm-ground);
  overflow: hidden;
}

.map-tabs {
  display: flex;
  gap: var(--cm-space-xs);
  flex: 0 0 auto;
}

.map-tabs button {
  padding: var(--cm-space-2xs) var(--cm-space-sm);
  border: 1px solid var(--cm-hairline);
  border-radius: var(--cm-radius);
  background: transparent;
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
  cursor: pointer;
}

.map-tabs button[aria-pressed="true"] {
  border-color: var(--cm-orbit);
  color: var(--cm-ink);
}

.map-scroll {
  flex: 1 1 auto;
  overflow: auto;
}

.architecture-map,
.workflow-tree {
  width: 100%;
  height: auto;
  min-height: 0;
}

.architecture-map__edges line,
.workflow-tree__edges path {
  stroke: var(--cm-hairline);
  stroke-width: 1.2;
  fill: none;
}

.architecture-map__edges line.is-cycle {
  stroke: var(--cm-route-possible);
}

.architecture-map__box rect {
  fill: var(--cm-ground-2);
  stroke: var(--cm-hairline);
}

.architecture-map__box .box-tint {
  stroke: none;
}

.architecture-map__box text {
  fill: var(--cm-ink);
  font-family: var(--cm-font-mono);
  font-size: 13px;
}

.architecture-map__box .box-meta {
  fill: var(--cm-ink-3);
  font-size: 11px;
}

.architecture-map__box[data-understood="true"] rect:first-child {
  stroke: var(--cm-star-high);
}

.architecture-map__box[data-home="true"] rect:first-child {
  stroke-width: 2;
}

.architecture-map__box[data-reachable="false"] rect:first-child {
  stroke-dasharray: 4 3;
}

.architecture-map__box:focus-visible rect:first-child,
.workflow-tree__row:focus-visible circle {
  outline: 2px solid var(--cm-orbit);
  outline-offset: 2px;
}

.architecture-map__box,
.workflow-tree__row {
  cursor: pointer;
}

.workflow-tree__row circle {
  fill: var(--cm-ink-3);
}

.workflow-tree__row[data-understood="true"] circle {
  fill: var(--cm-star-high);
}

.workflow-tree__row[data-cut] circle {
  fill: var(--cm-route-possible);
}

.workflow-tree__row text {
  fill: var(--cm-ink);
  font-family: var(--cm-font-mono);
  font-size: 13px;
}

.workflow-tree__row .row-meta {
  fill: var(--cm-ink-3);
  font-size: 11px;
}

.map-note,
.map-loading {
  flex: 0 0 auto;
  margin: 0;
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}

.map-state {
  margin: auto;
  max-width: 46ch;
  text-align: center;
  color: var(--cm-ink-2);
}
```

- [ ] **Step 4: Build and verify**

```bash
cd web && npm run check
codemble ./tests/fixtures/sampleproj
```

1. Switch to **Map**. The Architecture tab shows modules as boxes, `app` (Home)
   in the top row, `pkg.util` and `shared` two rows down, and the six unrouted
   modules in the bottom row with a dashed outline.
2. Click any box. The study panel opens on that module — the same panel the
   galaxy opens.
3. Switch to **Workflow**. The tree starts at `app`, with `main` one level in.
   `Service.run` renders with a dashed connector and reads "possible call".
4. **Illumination parity:** pass a region's checks, return to the Map, and
   confirm the box and the tree rows for that region are amber in exactly the
   same way the galaxy shows them.
5. **No WebGL:** in DevTools open the console and run
   `HTMLCanvasElement.prototype.getContext = () => null`, then reload and switch
   to Map. Expected: the map renders normally; only the galaxy layer shows its
   WebGL message.
6. Resize to 320 px wide and confirm the map scrolls rather than overflowing the
   viewport.

- [ ] **Step 5: Commit**

```bash
git add web/src/MapView.jsx web/src/App.jsx web/src/styles.css codemble/web_dist
git commit -s -m "feat(web): add the 2D map layer with architecture and workflow tabs"
```

---

### Task 10: Easy-mode density and the hint chip

**Files:**
- Create: `web/src/GuidanceLayer.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/GalaxyCanvas.jsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `mode`, `hint` (Task 5); `focusDim` (Task 7).
- Produces: `<HintChip hint mode onStudy />` from `web/src/GuidanceLayer.jsx`;
  `GalaxyCanvas` gains a `mode` prop.

Easy mode changes **presentation only** — never coordinates, progress, checks,
or graph truth.

- [ ] **Step 1: Add the hint chip**

Create `web/src/GuidanceLayer.jsx`:

```javascript
// Easy-mode guidance. Both components render deterministic graph truth handed
// down from the session: no model produces a hint, an order, or a next step.

export function HintChip({ hint, onStudy }) {
  if (!hint) return null;
  return (
    <output className="hint-chip" aria-live="polite">
      <span aria-hidden="true">→</span>
      <span>
        Study <strong>{hint.regionId}</strong> next
      </span>
      <small>{hint.reason}</small>
      <button type="button" onClick={() => onStudy(hint.regionId)}>
        Take me there
      </button>
    </output>
  );
}
```

- [ ] **Step 2: Reduce edge density in Easy mode**

In `web/src/GalaxyCanvas.jsx`, add `mode` to the props signature and use it to
hide edges that the selection does not touch:

```javascript
        .linkVisibility((link) => !(mode === "easy" && link.focusDim))
```

Insert that line into the renderer chain immediately after `.linkCurvature(0.12)`.
Because the chain is built once at mount, re-apply it whenever `mode` changes —
add to the data effect, alongside the existing `.nodeResolution(...)` call:

```javascript
      .linkVisibility((link) => !(mode === "easy" && link.focusDim))
```

and add `mode` to that effect's dependency array.

- [ ] **Step 3: Render the chip and pass `mode` down**

In `web/src/App.jsx`, add the import:

```javascript
import { HintChip } from "./GuidanceLayer.jsx";
```

Add `mode={mode}` to the `<GalaxyCanvas ... />` props, then render the chip
inside `<section className="map-stage">`, immediately before the closing
`</section>`:

```javascript
        <HintChip
          hint={hint}
          onStudy={(regionId) =>
            session.dispatch({
              type: "ADVANCE",
              node: focusedGraph.regions.find((region) => region.id === regionId),
            })
          }
        />
```

- [ ] **Step 4: Style the chip**

Append to `web/src/styles.css`:

```css
.hint-chip {
  position: absolute;
  z-index: var(--cm-z-raised);
  inset-inline-start: var(--cm-space-md);
  inset-block-end: var(--cm-space-md);
  display: flex;
  align-items: center;
  gap: var(--cm-space-sm);
  padding: var(--cm-space-sm) var(--cm-space-md);
  border: 1px solid var(--cm-orbit);
  border-radius: var(--cm-radius);
  background: var(--cm-ground-2);
  color: var(--cm-ink);
  font-size: var(--cm-text-sm);
}

.hint-chip small {
  color: var(--cm-ink-3);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}

.hint-chip button {
  padding: var(--cm-space-2xs) var(--cm-space-sm);
  border: 1px solid var(--cm-orbit);
  border-radius: var(--cm-radius);
  background: transparent;
  color: var(--cm-orbit);
  font-size: var(--cm-text-xs);
  cursor: pointer;
}
```

- [ ] **Step 5: Build and verify**

```bash
cd web && npm run check
codemble ./tests/fixtures/sampleproj
```

1. Switch to Easy mode. Expected: the app lands on the Map layer, and a hint chip
   names the nearest unlit region to Home.
2. Click "Take me there" — it enters that system.
3. Switch to the Galaxy layer in Easy mode, select a node, and confirm only that
   node's connections draw; peripheral nodes lose their halos.
4. Switch to Expert. Expected: no hint chip, all edges visible, and the layer
   stays wherever you last put it.
5. Pass every check in a project and confirm the chip disappears (nothing unlit).

- [ ] **Step 6: Commit**

```bash
git add web/src/GuidanceLayer.jsx web/src/App.jsx web/src/GalaxyCanvas.jsx web/src/styles.css codemble/web_dist
git commit -s -m "feat(web): add easy-mode edge density and the deterministic hint chip"
```

---

### Task 11: Coach-marks, clickable breadcrumb, and the legend tint key

**Files:**
- Modify: `web/src/GuidanceLayer.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/styles.css`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: `coachmarksSeen` and `DISMISS_COACHMARKS` (Task 5); `level`,
  `region`, `selectedNode` for the breadcrumb.
- Produces: `<CoachMarks onDismiss />` from `web/src/GuidanceLayer.jsx`.

The localStorage flag is a **UI preference, not progress** — it lives in
`localStorage`, never in `~/.codemble/`.

- [ ] **Step 1: Write the failing assertion**

In `web/scripts/check_learner_session.mjs`, add to the Phase B block (immediately
after the existing `DISMISS_COACHMARKS` assertion):

```javascript
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
```

- [ ] **Step 2: Run the check and watch it fail**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: PASS if Task 5 already holds the flag across commits, FAIL with
`coach-marks never return after a layer change` if `commit()` resets it. If it
passes, the assertion is a regression guard — proceed.

- [ ] **Step 3: Add the coach-marks component**

Append to `web/src/GuidanceLayer.jsx`:

```javascript
import { useState } from "react";

const COACHMARK_KEY = "codemble.coachmarks.seen";

const STEPS = [
  {
    title: "What you see",
    body: "Every star system is one file. Size is how much code it holds; brightness is how often the rest of your project calls it.",
  },
  {
    title: "How to move",
    body: "Scroll or press Enter to move closer, Escape to move back. Arrow keys step between systems. The camera stays on rails — you cannot get lost.",
  },
  {
    title: "What lights stars",
    body: "A system lights up only after you answer questions drawn from your own code. Nothing lights up just by looking at it.",
  },
];

// A UI preference, not progress: it belongs in localStorage, never in
// ~/.codemble/, which is reserved for what the learner has actually proven.
export function hasSeenCoachmarks() {
  try {
    return globalThis.localStorage?.getItem(COACHMARK_KEY) === "1";
  } catch {
    return false;
  }
}

export function CoachMarks({ onDismiss }) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  function finish() {
    try {
      globalThis.localStorage?.setItem(COACHMARK_KEY, "1");
    } catch {
      // A blocked storage API must never stop the learner from continuing.
    }
    onDismiss();
  }

  return (
    <aside className="coach-marks" role="dialog" aria-labelledby="coach-heading">
      <p className="coach-marks__progress">Step {step + 1} of {STEPS.length}</p>
      <h1 id="coach-heading">{current.title}</h1>
      <p>{current.body}</p>
      <div className="coach-marks__actions">
        <button type="button" className="coach-skip" onClick={finish}>Skip</button>
        <button
          type="button"
          className="check-primary"
          onClick={() => (step + 1 < STEPS.length ? setStep(step + 1) : finish())}
        >
          {step + 1 < STEPS.length ? "Next" : "Start exploring"}
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Render coach-marks and make the breadcrumb clickable**

In `web/src/App.jsx`, extend the import:

```javascript
import { CoachMarks, HintChip, hasSeenCoachmarks } from "./GuidanceLayer.jsx";
```

Replace the `<p className="location">` block (lines 91–99) with a clickable
breadcrumb:

```javascript
        <nav className="location" aria-label="Breadcrumb" aria-live="polite">
          {showChart ? (
            <span aria-current="page">Star chart</span>
          ) : (
            <>
              <button
                type="button"
                disabled={level === LEVELS.GALAXY}
                aria-current={level === LEVELS.GALAXY ? "page" : undefined}
                onClick={() => session.dispatch({ type: "SET_LEVEL_GALAXY" })}
              >
                Galaxy
              </button>
              {level !== LEVELS.GALAXY ? (
                <>
                  <span aria-hidden="true">/</span>
                  <button
                    type="button"
                    disabled={level === LEVELS.SYSTEM}
                    aria-current={level === LEVELS.SYSTEM ? "page" : undefined}
                    onClick={() => session.dispatch({ type: "RETREAT" })}
                  >
                    {region.id}
                  </button>
                </>
              ) : null}
              {level === LEVELS.STUDY && selectedNode ? (
                <>
                  <span aria-hidden="true">/</span>
                  <span aria-current="page">{selectedNode.name}</span>
                </>
              ) : null}
              {languageFocus !== "all" ? (
                <small>{languageLabel(languageFocus)} focus</small>
              ) : null}
            </>
          )}
        </nav>
```

Add the `SET_LEVEL_GALAXY` case to `dispatch` in `web/src/learnerSession.js`,
immediately before `default:`:

```javascript
      case "SET_LEVEL_GALAXY":
        commit({ level: LEVELS.GALAXY, selectedNode: null });
        return undefined;
```

Render the coach-marks inside `<section className="map-stage">`, immediately
before the `<HintChip ... />` added in Task 10:

```javascript
        {!coachmarksSeen && !hasSeenCoachmarks() ? (
          <CoachMarks onDismiss={() => session.dispatch({ type: "DISMISS_COACHMARKS" })} />
        ) : null}
```

pulling `coachmarksSeen` out of `state` in the destructuring block.

Finally, complete the legend — replace the `<aside className="map-legend">` block
(lines 146–151) with:

```javascript
        <aside className="map-legend" aria-label="Galaxy legend">
          <span><i className="legend-dot legend-dot--dim" /> Not studied</span>
          <span><i className="legend-dot legend-dot--lit" /> Understood</span>
          <span><i className="legend-dot legend-dot--partial" /> Unchartable</span>
          <span><i className="legend-route" /> Parser edge</span>
          <span><i className="legend-route legend-route--possible" /> Possible call</span>
          <span><i className="legend-size" /> Size = lines of code</span>
          <span><i className="legend-brightness" /> Brightness = how often it is called</span>
          {languageOptions
            .filter((option) => option.id !== "all")
            .map((option) => (
              <span key={option.id}>
                <i className={`legend-tint legend-tint--${option.id}`} /> {option.label}
              </span>
            ))}
        </aside>
```

- [ ] **Step 5: Style coach-marks, breadcrumb, and legend swatches**

Append to `web/src/styles.css`:

```css
.location button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--cm-orbit);
  font: inherit;
  cursor: pointer;
}

.location button[disabled] {
  color: var(--cm-ink-2);
  cursor: default;
}

.location button:not([disabled]):hover {
  text-decoration: underline;
}

.coach-marks {
  position: absolute;
  z-index: var(--cm-z-panel);
  inset-block-end: var(--cm-space-lg);
  inset-inline-start: 50%;
  translate: -50% 0;
  width: min(38ch, calc(100% - var(--cm-space-lg)));
  padding: var(--cm-space-md);
  border: 1px solid var(--cm-orbit);
  border-radius: var(--cm-radius);
  background: var(--cm-ground-2);
  color: var(--cm-ink);
}

.coach-marks__progress {
  margin: 0 0 var(--cm-space-2xs);
  color: var(--cm-ink-3);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}

.coach-marks h1 {
  margin: 0 0 var(--cm-space-xs);
  font-size: var(--cm-text-lg);
}

.coach-marks__actions {
  display: flex;
  justify-content: space-between;
  gap: var(--cm-space-sm);
  margin-block-start: var(--cm-space-md);
}

.coach-skip {
  border: 0;
  background: transparent;
  color: var(--cm-ink-3);
  cursor: pointer;
}

/* Legend swatches. The tint tokens are tuned to clear 4.5:1 on --cm-ground-2,
   which is this panel's own background. */
.legend-tint {
  display: inline-block;
  width: var(--cm-space-sm);
  height: var(--cm-space-sm);
  border-radius: 2px;
}

.legend-tint--python { background: var(--cm-neb-python); }
.legend-tint--javascript { background: var(--cm-neb-js); }
.legend-tint--typescript { background: var(--cm-neb-ts); }

.legend-route--possible {
  border-block-start-style: dashed;
}

.legend-size {
  display: inline-block;
  width: var(--cm-space-md);
  height: var(--cm-space-sm);
  border-radius: 50%;
  background: var(--cm-ink-3);
}

.legend-brightness {
  display: inline-block;
  width: var(--cm-space-md);
  height: var(--cm-space-sm);
  background: linear-gradient(90deg, var(--cm-node-unlit), var(--cm-ink-2));
}
```

- [ ] **Step 6: Build and verify**

```bash
cd web && npm run check
codemble ./tests/fixtures/polyglot
```

1. Clear the flag (`localStorage.removeItem("codemble.coachmarks.seen")`) and
   reload. Expected: three coach-mark steps, dismissible at any point.
2. Reload. Expected: no coach-marks.
3. At study level, click "Galaxy" in the breadcrumb — it returns to the galaxy.
   Click the system segment from study — it returns to the system.
4. The legend now shows size, brightness, amber, dashed uncertainty, and one
   swatch per language present in the project.
5. Keyboard-only pass: Tab reaches the layer switcher, map tabs, breadcrumb
   buttons, and coach-mark buttons, and every focused control shows a visible
   ring.

- [ ] **Step 7: Commit**

```bash
git add web/src/GuidanceLayer.jsx web/src/App.jsx web/src/learnerSession.js web/src/styles.css web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): add coach-marks, a clickable breadcrumb, and a complete legend"
```

---

### Task 12: Documentation, changelog, and invalidated claims

Phase B changes what the app *looks like* and adds a second layer, which
contradicts published copy in four places. The repo rule is that a milestone
changing user-facing behaviour updates the docs page(s) **and** the hand-authored
sidebar in the same PR.

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs-site/src/content/docs/the-galaxy.md`
- Modify: `docs-site/src/content/docs/quickstart.md`
- Modify: `docs-site/src/content/docs/architecture.md`
- Modify: `docs-site/src/content/docs/roadmap.md`
- Modify: `docs-site/src/pages/index.astro`
- Modify: `docs-site/astro.config.mjs`
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: everything Tasks 1–11 shipped.
- Produces: no code interface.

**The exact claims Phase B invalidates** (found by audit — fix all of them):

| File | Claim | Why it is now wrong |
| --- | --- | --- |
| `README.md:157-158` | "**Rendering:** WebGL is required. There is intentionally no misleading 2D fallback in this release." | The Map layer *is* a 2D view and works without WebGL |
| `README.md:93` | "Guides you from galaxy → system → study on scripted camera rails" | There are now two layers |
| `README.md:101-112` | "Read the galaxy" table — `Brightness \| Structural centrality` | Brightness is now halo + bloom; language has its own tint channel |
| `docs-site/.../the-galaxy.md:11-20` | Visual-encoding table (`Color \| Language`) | Language moved to nebula tint; the table needs the new channels |
| `docs-site/.../quickstart.md:56-66` | "## 4. Zoom in" three-level table | Needs the layer switcher and the two map tabs |
| `docs-site/.../architecture.md:70` | Stack line | Add the map layer's provenance (layouts computed in `codemble/graph/`) |
| `docs-site/.../roadmap.md:31-32` | "No free-flight camera. Ever." | Still true — but the "no second 2D renderer" Non-Goal in `CLAUDE.md` is now superseded and must say so |
| `docs-site/src/pages/index.astro:~213` | `<h2>Three levels of zoom. No free flight.</h2>` | Two layers, three levels within the galaxy layer |
| `assets/demo.gif` (via `README.md:36`) | The only real recording of the app | Predates bloom, nebulae, starfield, and the Map layer |

- [ ] **Step 1: Add the changelog entry**

In `CHANGELOG.md`, replace the empty `## [Unreleased]` line (line 6) with:

```markdown
## [Unreleased]

### Added
- A second **Map** layer sits beside the galaxy, switchable from the header. Its
  Architecture tab lays modules out by directory and by import distance from
  Home; its Workflow tab walks the call tree from your entrypoint. Both layouts
  are computed by the parser-backed graph layer and served by a new
  `GET /api/map`, so the map and the galaxy can never disagree.
- The Map layer renders without WebGL, so a machine that cannot draw the galaxy
  can still read the project.
- First-run coach-marks explain what you see, how to move, and what lights
  stars. Dismissing them is a local UI preference, not progress.
- Easy mode now lands on the Map, draws only the selected structure's
  connections, and shows a hint chip naming the nearest unlit region to Home.
  The hint is counted in import routes from the graph; no model chooses it.
- The breadcrumb is clickable, and the legend is complete: size, brightness,
  amber, dashed uncertainty, and one swatch per language.

### Changed
- The galaxy gained depth: every node carries a canvas-generated halo, lit stars
  bloom, each system sits in a faint language-tinted nebula, and a background
  starfield is seeded from the project's own file hashes — the same code always
  produces the same sky.
- Passing a region's checks now triggers a ~1.2s "nebula dawn": amber washes
  across that system's fog and its star flares. `prefers-reduced-motion` gets
  the finished lit state with no animation at all.
- System orbits are laid out by call depth from the module's entry node instead
  of by member index, so an inner ring means "this runs first". Structures no
  call reaches keep the outermost ring rather than being placed by guesswork.
  Layout coordinates changed once; saved progress is unaffected because region
  signatures are derived from file hashes, not coordinates.
- Studying a structure no longer dims the whole scene: the selection's
  connections stay lit while everything else recedes.
- Drifting particles mark **certain** call edges only. A possible call stays
  dashed and still, so motion can never imply proof.
```

- [ ] **Step 2: Update the invalidated docs pages**

**`docs-site/src/content/docs/the-galaxy.md`** — replace the visual-encoding
table (lines 11–20) with:

```markdown
| Visual | Meaning |
| --- | --- |
| Star system | One source module |
| Planet | A function or class |
| Route between systems | An import |
| Edge between planets | A call (uncertain calls are labeled "possible call") |
| Size | Lines of code |
| Brightness and glow | How often it's called (centrality) |
| Nebula tint | Language |
| Lit amber / dim | Understood / not yet |
| Drifting particles | A call the parser proved; possible calls stay still |
| Orbit ring | Call depth — the inner ring runs first |

Nothing that is merely busy can outshine something you understand: the unlit
brightness ramp stops below the amber a lit star uses.
```

and append to the "Semantic zoom, not free flight" section (after line 27):

```markdown
## Two layers, one truth

The header switches between the 3D **Galaxy** and a flat **Map**. The Map has
two tabs: *Architecture* lays your modules out by folder and by how far they sit
from Home along import routes, and *Workflow* walks the call tree from your
entrypoint. Both layouts are computed by the same parser-backed graph the galaxy
draws — the map cannot show you a relationship the galaxy does not have. Modules
with no import route from Home are placed in their own row and labelled, never
guessed into position. Clicking anything in either layer opens the same study
panel, and a lit system is amber in both.

The Map needs no WebGL, so it still works where the galaxy cannot draw.
```

**`docs-site/src/content/docs/quickstart.md`** — replace the "## 4. Zoom in"
section (lines 56–66) with:

```markdown
## 4. Choose a layer, then zoom in

The header switches between two layers. **Galaxy** is the 3D view; its camera
moves on rails through three levels. **Map** is a flat diagram with two tabs.
Easy mode starts on the Map, Expert starts on the Galaxy, and you can switch at
any time. In a mixed project, use the **Focus** control to show All, Python,
JavaScript, or TypeScript. Focus and layer are only views: neither alters
coordinates, progress, or graph evidence.

| Galaxy level | What you see | What it's for |
| --- | --- | --- |
| **Galaxy** | Source modules as star systems, imports as routes | Orientation |
| **System** | Functions and classes in call-depth orbits — the inner ring runs first | Structure |
| **Study** | Real source with line numbers and a validated, cached explanation | Learning |

| Map tab | What you see | What it's for |
| --- | --- | --- |
| **Architecture** | Modules as boxes, grouped by folder, layered by import distance from Home | Seeing how the project fits together |
| **Workflow** | The call tree from your entrypoint, depth by depth | Seeing what runs first |
```

**`docs-site/src/content/docs/architecture.md`** — replace the Stack line (line 70):

```markdown
Python 3.11+ · FastAPI · tree-sitter · Vite + React · `3d-force-graph` (three.js) ·
```

with:

```markdown
Python 3.11+ · FastAPI · tree-sitter · Vite + React · `3d-force-graph` (three.js) ·
plain SVG for the 2D map ·
```

and add this paragraph directly beneath it:

```markdown
Both the 3D galaxy coordinates and the 2D map layouts are computed in
`codemble/graph/` and served as data — `GET /api/graph` and `GET /api/map`. The
renderer places what the graph already decided. That is why "same code → same
sky" holds, and why adding a second renderer needed no second source of truth.
```

**`docs-site/src/content/docs/roadmap.md`** — replace the Non-goals sentence
(lines 31–32):

```markdown
No accounts. No telemetry. No hosted code. No XP or streaks — illumination and
the star chart are the whole game. No free-flight camera. Ever.
```

with:

```markdown
No accounts. No telemetry. No hosted code. No XP or streaks — illumination and
the star chart are the whole game. No free-flight camera. Ever. The 2D Map layer
is a second *view* of the same graph, not a second source of truth: it was
approved once the layouts moved into the graph layer.
```

**`docs-site/src/pages/index.astro`** — change the `<h2>` (around line 213) from
`Three levels of zoom. No free flight.` to
`Two layers. Three levels of zoom. No free flight.` The file header rule ("Every
claim is drawn from the shipped docs") still holds: this claim is now in
`quickstart.md`.

- [ ] **Step 3: Add the build log and its sidebar entry**

Create `docs-site/src/content/docs/progress/m12-galaxy-look.md` following the
existing build-log format (see `progress/m10-polyglot-release.md` for the house
style), with frontmatter:

```markdown
---
title: "Build log: the living cosmos"
description: Bloom, nebulae, a seeded starfield, call-depth orbits, and a second 2D map layer.
---
```

Then add its sidebar entry — the sidebar has no autogenerate, so a page without
an entry is invisible. In `docs-site/astro.config.mjs`, append to the
`"Build & contribute"` group's `items` array, after the M10 line:

```javascript
            { label: "Build log: M12 the living cosmos", slug: "progress/m12-galaxy-look" },
```

- [ ] **Step 4: Fix the invalidated README claims**

In `README.md`:

Replace lines 157–158:

```markdown
- **Rendering:** WebGL is required. There is intentionally no misleading 2D
  fallback in this release.
```

with:

```markdown
- **Rendering:** the 3D galaxy needs WebGL. If your machine cannot draw it, the
  Map layer still works — it is plain SVG over the same parser evidence, not a
  degraded guess.
```

Replace line 93:

```markdown
| **2. Navigate** | Guides you from galaxy → system → study on scripted camera rails | Orientation without getting lost in free flight |
```

with:

```markdown
| **2. Navigate** | Two layers over one graph: a 3D galaxy on scripted camera rails, and a flat map of architecture and workflow | Orientation without getting lost in free flight |
```

Replace the "Read the galaxy" table rows (lines 101–112) for Brightness, and add
the new channels:

```markdown
| Size | Lines of code |
| Brightness and glow | Structural centrality |
| Nebula tint | Language |
| Orbit ring | Call depth — the inner ring runs first |
| Dim → lit | Not yet proven → understood |
```

- [ ] **Step 5: Re-record the demo GIF**

`assets/demo.gif` (referenced at `README.md:36`) predates every visual in this
phase. Regenerate it with the existing script:

```bash
./scripts/record_demo.sh
```

The alt text at `README.md:36` also enumerates the old flow — update it to:

```html
  <img src="https://github.com/udhawan97/Codemble/raw/main/assets/demo.gif" alt="Codemble maps a project, switches between the galaxy and the map, runs graph-derived checks, and lights a system" width="960">
```

- [ ] **Step 6: Update `CLAUDE.md`**

Tick the M12 checkboxes, update **Current State** with the date and a one-line
note, and append these Decision Log rows:

```markdown
| 2026-07-19 | The 2D Map layer supersedes the "no second 2D renderer in v1" Non-Goal; both layouts are computed in `codemble/graph/` behind `GET /api/map` | The render-ready-graph rule always allowed a second renderer; moving the layouts server-side is what makes it free of a second source of truth |
| 2026-07-19 | System orbits are call depth from the module's entry node, with the seed widened to include members no sibling calls | A module node makes no intra-project calls, so the spec's literal seed was always empty and stranded every member in the outermost ring. Both spec rules are preserved: the entry's callees are ring 1, and unreachable members take the outermost ring by node id |
| 2026-07-19 | The workflow tree's first hop is labelled `defines`, not `calls` | The selected entrypoint is usually a module, and the parser observed no call from a module to its own function. Containment is real parser truth (`Node.region`); relabelling it a call would have invented an edge |
| 2026-07-19 | Nebula tints ship lighter than the values in the design spec | The spec's starting values measured 3.19–4.46:1 against `--cm-ground-2` and failed the 4.5:1 legend floor. Hue is held; only lightness moved, and all three stay below `--cm-ink-2` so amber's monopoly is intact |
| 2026-07-19 | Bloom resolution is capped with `composer.setPixelRatio(1)`, not the `UnrealBloomPass` constructor | `EffectComposer.setSize` forwards the canvas size to every pass on resize, overwriting the constructor's `resolution`. The pixel ratio is the cap that survives |
```

- [ ] **Step 7: Verify the docs build and the whole gate**

```bash
cd docs-site && npm install && npm run check && npm run build
```
Expected: `astro check` reports 0 errors and the build completes with Pagefind.

```bash
python3 -m pytest -q && python3 -m ruff check .
cd web && npm run check
```
Expected: all green.

Confirm the new build-log page appears in the sidebar of the built site (a page
without a hand-authored entry is invisible).

- [ ] **Step 8: Commit**

```bash
git add CHANGELOG.md README.md CLAUDE.md assets/demo.gif docs-site/
git commit -s -m "docs: document the map layer, the new galaxy look, and call-depth orbits"
```

---

## Self-Review

Run after the plan is written; findings fixed inline above.

### 1. Spec coverage

| Required item | Task |
| --- | --- |
| 1. `GET /api/map`, deterministic 2D layouts in `codemble/graph/`, `schema_version: 1`, both payloads, byte-stable, determinism tests | 2, 3 |
| 2. Call-depth orbits in `layout_graph`, hash-seeded, determinism tests re-pinned by exact name | 1 |
| 3. Halos, bloom via composer, nebula fog, seeded starfield, reticle, focus dimming, certain-only particles, curvature | 4, 6, 7 |
| 4. Nebula dawn ~1.2s + reduced-motion finished state | 8 |
| 5. Four new tokens, plain `rgb()`, added to `readPalette`, legend swatches ≥4.5:1 | 4 (values retuned), 11 (legend) |
| 6. `LayerSwitcher`, `MapView`/`ArchitectureMap`/`WorkflowTree`, pure SVG, same study panel, identical illumination, dashed uncertainty, no-WebGL | 9 |
| 7. Easy mode: default map, reduced edges, faded peripherals, `hint` in `deriveSnapshot`; Expert defaults galaxy + full density | 5, 10 |
| 8. Coach-marks (3 steps, localStorage), clickable breadcrumb, legend tint key | 11 |
| 9. 900-node resolution drop kept, billboards, capped bloom, `?benchmark` at 1k | 6, 7 |
| Docs: CHANGELOG, docs-site pages, sidebar, README/screenshots | 12 |

Gaps found and fixed: the `?benchmark` path bypassed the composer (fixed in Task
7 Step 4) and could not be reached through the picker at all given the 300-file
cap (Task 7 Step 5 now ships a synthetic-fixture recipe). The 900-node resolution
drop is untouched by every task, so it is retained by omission — verified against
`GalaxyCanvas.jsx:89`, which no step edits.

### 2. Placeholder scan

No "TBD", "TODO", "implement later", "add appropriate X", "handle edge cases",
"write tests for the above", or "similar to Task N" appears. Every code step
carries literal code; every command carries its expected output. Task 12's
build-log page is the one place a step says "following the existing format" — it
also names the exact model file (`progress/m10-polyglot-release.md`) and gives
the literal frontmatter, so nothing is left to invention.

### 3. Type consistency

- `build_map(graph) -> dict` and `MAP_SCHEMA_VERSION` are defined in Task 2 and
  consumed under those exact names in Task 3 and via the payload in Task 9.
- `nebulaTintKey` is defined in Task 6 (`graphData.js`) and imported in Task 9
  (`MapView.jsx`) — same name, same module.
- `focusDim` is introduced in Task 7 (`graphData.js`) and read in Task 7
  (`GalaxyCanvas.jsx` link accessors), Task 6 (`makeMarker`), and Task 10
  (`linkVisibility`). One spelling throughout.
- `createDressing` / `createStarfield` / `seedFromHashes` (Task 6) and
  `attachBloom` / `runNebulaDawn` / `prefersReducedMotion` (Tasks 7–8) are each
  used only under their defining names.
- Session fields and events match the shared contract exactly: `layer`,
  `mapTab`, `mapData`, `mapError`, `coachmarksSeen`, `hint`, `SET_LAYER`,
  `SET_MAP_TAB`, `DISMISS_COACHMARKS`, `fetchMap(signal)`.
- One addition beyond the contract: `layerChosen` (Task 5) and `SET_LEVEL_GALAXY`
  (Task 11). Neither is a contract name being renamed — `layerChosen` is private
  bookkeeping so a mode flip cannot override an explicit layer choice, and
  `SET_LEVEL_GALAXY` is a new event the breadcrumb needs. Both are additive.
- `Task 6` writes `makeMarker(node, palette, dressing, focusedId)`; Task 8 adds
  `group.name` inside the same function and Task 7 does not re-declare it.
