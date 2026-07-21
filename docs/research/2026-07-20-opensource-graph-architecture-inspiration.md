# Open-source graph & architecture-visualization inspiration survey

**Date:** 2026-07-20
**Status:** research only — no scope change implied; adoptions enter the plan only via the Decision Log.

**Purpose.** Codemble's owner named two repos — `Graphify-Labs/graphify` ("better graph connections and visuals") and `tt-a1i/archify` ("better 2D architecture SVGs") — and asked for a survey of the surrounding open-source landscape: what each project actually does (verified against the repos themselves, not blog posts), its license and maintenance state, which specific ideas/algorithms Codemble could adopt, and which parts must be rejected because they conflict with Codemble's constraints. Named repos were shallow-cloned and read at source level; survey items were verified from their GitHub READMEs/docs. Claims a fetch could not confirm are marked *unverified*.

## Constraints this evaluation was run against (short form)

- **Correctness Contract:** structure (nodes/edges/entrypoints) comes only from parsers, never from an LLM; approximate call edges stay visibly labeled "possible"; explanations link a real `file:line`. Tools that let an LLM draw architecture can contribute **UX ideas only**, never their structure pipeline.
- **Determinism:** same code → same layout bytes. No wall-clock or `Math.random` at render time. All layouts (3D galaxy and 2D map) are computed in the Python graph layer; React renders numbers it is handed. **Client-computed force layouts violate this.**
- **No free-flight 3D navigation** (semantic zoom on rails); no XP/streaks/leaderboards; no elaborate game art before the loop teaches.
- **License:** Codemble is Apache-2.0. Vendoring/porting requires MIT/BSD/Apache-compatible source with attribution; GPL/AGPL/EPL projects are **ideas-only**. Algorithms themselves (Sugiyama, Louvain/Leiden, PageRank) may be reimplemented from papers/docs.
- **Pinned stack:** Python 3.11 + FastAPI backend; Vite + React + `3d-force-graph` frontend. New runtime dependencies need strong justification; pure-Python stdlib implementations preferred.

---

## 1. Graphify-Labs/graphify — knowledge-graph pipeline with god nodes & community detection

**Repo:** <https://github.com/Graphify-Labs/graphify> · **License:** MIT (LICENSE, "Copyright (c) 2026 Safi Shamsi") · **Maintained:** yes — v0.9.22 in `pyproject.toml`, last commit 2026-07-20 on default branch `v8` (verified from a shallow clone at `abff1b1`). Pure Python, published to PyPI as `graphifyy`.

**What it is.** A CLI + AI-assistant skill that turns any folder (code, docs, SQL, PDFs, images, video) into a queryable knowledge graph with three outputs: interactive `graph.html`, `graph.json`, and a plain-language `GRAPH_REPORT.md` (<https://github.com/Graphify-Labs/graphify/blob/v8/README.md>). The pipeline is seven single-function stages: `detect() → extract() → build_graph() → cluster() → analyze() → report() → export()`, communicating through plain dicts and NetworkX graphs (<https://github.com/Graphify-Labs/graphify/blob/v8/ARCHITECTURE.md>).

**How it builds edges.** Hybrid, but split by input type: *code* is parsed locally and deterministically with tree-sitter (one extractor per language under `graphify/extractors/`, ~25 languages in the clone), while docs/PDFs/media go through the host assistant's model. Every edge carries a **confidence label**: `EXTRACTED` (explicitly stated in source, e.g. an import), `INFERRED` (deduction, e.g. the call-graph second pass), or `AMBIGUOUS` (uncertain, flagged for human review) — enforced by `validate.py` before graph build (<https://github.com/Graphify-Labs/graphify/blob/v8/ARCHITECTURE.md> "Confidence labels"; `EXTRACTED` literals throughout <https://github.com/Graphify-Labs/graphify/blob/v8/graphify/extract.py>). New-language recipe: "tree-sitter parse → walk nodes → collect nodes and edges → call-graph second pass for INFERRED `calls` edges" (ARCHITECTURE.md).

**God nodes.** Not a fancy algorithm: top-N nodes by **plain degree**, after filtering noise — file-level hub nodes (they "accumulate import/contains edges mechanically"), concept nodes (empty/extension-less `source_file`), and JSON-key noise labels (`god_nodes()` in <https://github.com/Graphify-Labs/graphify/blob/v8/graphify/analyze.py>). The insight is the *filtering*, not the ranking.

**Community detection.** `cluster.py` (<https://github.com/Graphify-Labs/graphify/blob/v8/graphify/cluster.py>) tries **Leiden** via `graspologic.partition.leiden` with `random_seed=42, trials=1`, and falls back to **Louvain** via `networkx.community.louvain_communities(seed=42, threshold=1e-4, max_level=10)`. Around the partitioner sits a lot of hard-won determinism and quality engineering:

- The graph is **rebuilt in sorted node/edge order** before partitioning so the partitioner sees a canonical input (`_partition`, lines 34–45).
- **Oversized communities** (>25 % of the graph, min 10 nodes) are split by a second Leiden pass on the subgraph; **low-cohesion** communities (cohesion < 0.05, ≥ 50 nodes — cohesion = intra-edges / possible edges) are re-split to break doc-hub bridges ("e.g. CLAUDE.md connected to everything").
- Optional **hub-exclusion percentile**: super-hub nodes above a degree percentile are excluded from partitioning and re-attached afterwards by majority vote over neighbours, "so they don't pull unrelated subsystems into the same community."
- **Total-order community re-indexing** (size desc, then `tuple(sorted(members))` tiebreak) so identical groupings always get identical IDs — without it, equal-sized communities' IDs "permute run-to-run."
- **Membership fingerprints** — `sha256(sorted member ids)` per community — persisted so a later re-cluster can tell which communities actually changed and avoid stale labels (`community_member_sigs`).
- `remap_communities_to_previous()` — greedy intersection matching so incremental updates keep stable community IDs.
- **LLM-free labels**: each community is named after its highest-degree member, ties broken by node id (`label_communities_by_hub`); an LLM naming pass may override but is never required.

**"Surprising connections."** A composite, fully deterministic surprise score over cross-file edges: confidence weight (AMBIGUOUS 3 > INFERRED 2 > EXTRACTED 1) + cross-file-type bonus + cross-directory bonus + cross-community bonus + "peripheral→hub" bonus (a degree ≤ 2 node reaching a degree ≥ 5 node), with suppression rules for known resolver pollution (`_surprise_score` in <https://github.com/Graphify-Labs/graphify/blob/v8/graphify/analyze.py>).

**Visualization.** `graph.html` embeds **vis-network 9.1.6** with the `forceAtlas2Based` solver — a *client-side force layout* — with a sidebar (search, node info, neighbour list, community legend with click-to-filter) and a 5,000-node viz cap (<https://github.com/Graphify-Labs/graphify/blob/v8/graphify/exporters/html.py>). A separate `callflow_html.py` renders Mermaid architecture/call-flow HTML (ARCHITECTURE.md module table).

**Adoptable for Codemble**
- **The determinism playbook around clustering** (sorted canonical input, seeded partitioner, total-order re-indexing, membership hashes, remap-to-previous). Codemble already hashes region signatures; if Phase-2 LOD clustering ever groups star systems into constellations, this is the exact checklist that keeps "same code → same sky" true. → `codemble/graph/`.
- **Louvain/Leiden as the Phase-2 clustering algorithm** — reimplement seeded Louvain in pure Python (algorithm-from-paper is explicitly allowed; graspologic/networkx as runtime deps are not justified).
- **Surprise scoring** as a deterministic, graph-only signal for Easy-mode hints or a future check family ("this quiet module unexpectedly reaches hub X — which edge proves it?"). All inputs (confidence, degree, region, community) already exist in Codemble's graph. → `codemble/checks/`, hint chip logic in `codemble/graph/`.
- **God-node noise filtering** — Codemble's centrality brightness could similarly discount module nodes that accumulate mechanical `contains` edges. → `codemble/graph/finalize.py`.
- **Community labeled after its structural hub** — a good deterministic naming rule if constellations ever need names.

**Rejected**
- The **vis-network client-side force layout** — direct determinism violation; Codemble's layouts stay in Python.
- **LLM/semantic edges** (`semantically_similar_to`, doc-extraction edges) — invented-structure risk; Codemble structure comes only from parsers. Graphify's own `INFERRED`/`AMBIGUOUS` honesty labels are the *compatible* part (they rhyme with Codemble's "possible call"), but its LLM-derived edge *sources* are not.
- **graspologic dependency** (heavy; pulls scientific stack) — reimplement instead.

---

## 2. tt-a1i/archify — agent-driven typed-IR diagram renderer (2D SVG)

**Repo:** <https://github.com/tt-a1i/archify> · **License:** MIT (LICENSE, "Copyright (c) 2026 tt-a1i (Archify)") · **Maintained:** yes — last commit 2026-07-16; README describes latest release v2.11.0 (release date *unverified beyond the README fetch*). Node.js CLI (`bin/archify.mjs`) + vanilla-JS renderers; no runtime deps required (degraded no-ajv mode exists).

**What it is — and the crucial caveat.** Archify is **not a static-analysis tool**. It is an agent skill: the LLM writes a **typed JSON intermediate representation** which a deterministic renderer turns into a themed, self-contained HTML/SVG diagram; the loop is "Generate JSON IR → Validate → Render → Check → Iterate," and the skill instructs the agent to fix the JSON, "never edit the renderer" (<https://github.com/tt-a1i/archify/blob/main/archify/SKILL.md> "Renderer Modes"). Five diagram types with one JSON Schema each: architecture, workflow, sequence, dataflow, lifecycle (<https://github.com/tt-a1i/archify/tree/main/archify/schemas>). So the *structure source* is agent judgment — but everything downstream of the IR is deterministic rendering craft, which is exactly the part Codemble can use (Codemble's IR-equivalent is its parser-built graph).

**How the architecture renderer works** (all from the clone):
- **Layout is "fixed cell math only," explicitly "Not auto-layout"** (<https://github.com/tt-a1i/archify/blob/main/archify/renderers/architecture/grid.mjs> line 1). The IR assigns each component a `row`/`col` in a grid (`origin`, `cols`, `gapX/gapY`, `cellW/cellH` — defaults 4 cols, 130×64 cells) or a free `pos [x,y]`; the renderer computes pixels as `origin + col*(cellW+gapX)`. Placement validation catches shared cells and out-of-range cols.
- **Edge routing:** per-connection `route` mode — `auto` (direct line unless anchors are orthogonal-friendly), `orthogonal-h`, `orthogonal-v`, or explicit via-points — from **side anchors** (`fromSide`/`toSide`, with defaults chosen from the two boxes' relative positions), rendered as a **rounded-corner polyline** (`roundedPath(points, 8)`) (<https://github.com/tt-a1i/archify/blob/main/archify/renderers/architecture/render-architecture.mjs> `routeVia`/`pathFor`). Connection `variant`s (e.g. `emphasis`) map to arrow classes and stroke widths.
- **Boundaries:** named regions (`region` / `security-group`) declared as `wraps: [component ids]`; the renderer computes their rect as the members' bounding box plus padding (`boundaryRect`), and validates that every wrapped id exists (<https://github.com/tt-a1i/archify/blob/main/archify/renderers/architecture/render-architecture.mjs>).
- **Semantic component types** (`frontend | backend | database | cloud | security | messagebus | external`) drive visual categorization (<https://github.com/tt-a1i/archify/blob/main/archify/schemas/common.schema.json> `componentType`).
- **Machine-checkable output:** a **layout report** serializes every computed box and routed polyline for dry-run inspection (<https://github.com/tt-a1i/archify/blob/main/archify/renderers/shared/layout-report.mjs>), and a post-render checker fails on non-finite SVG coordinates, "two-point diagonal arrows," and arrows crossing the legend (<https://github.com/tt-a1i/archify/blob/main/archify/scripts/check-render-output.mjs>; SKILL.md step 4). Pure geometry helpers (`rectsOverlap`, `segmentIntersectsRect`) back these checks (<https://github.com/tt-a1i/archify/blob/main/archify/renderers/shared/geometry.mjs>).
- **Presentation:** self-contained HTML with dark/light theme variables, `prefers-color-scheme`, clipboard/PNG/SVG export, optional trace animation honoring `prefers-reduced-motion` (<https://github.com/tt-a1i/archify/blob/main/archify/README.md>).

**Adoptable for Codemble** (renderer craft, applied to Codemble's parser-truth graph)
- **Orthogonal elbow routing with side anchors and rounded corners** for the 2D Map's edges — computed in Python (`codemble/graph/mapview.py`) as point lists, rendered as SVG paths in `web/src/MapView.jsx`. This is the single biggest visible-quality gap between Codemble's current map and archify's output.
- **Boundary rects around member groups** — draw a labeled region around each package/directory of modules in the Architecture tab (pure bounding-box + padding math; containment is parser truth, so no contract risk).
- **A layout-report + render-check pattern**: emit the computed map layout as JSON (Codemble already serves it) and add unit checks in Python for "no NaN coordinates, no node overlaps, no edge crossing a label" — cheap regression armor for layout changes. → tests beside `codemble/graph/mapview.py`.
- **Route variants mapped to meaning** — Codemble already dashes "possible" edges in the map; archify's variant→class mapping is a tidy precedent for keeping that mapping declarative.

**Rejected**
- **The structure pipeline** — the agent chooses components, rows, and routes ("layout judgment over generic auto-layout", README). For Codemble that is an LLM drawing structure: contract violation. Codemble's layout must be *computed* from the graph, so it needs a real layout algorithm (see §10) where archify deliberately has none.
- **The Node renderer as a dependency** — stack is pinned; port the geometry ideas (they're ~200 lines of pure math), don't embed a Node toolchain.

---

## 3. vasturiano/3d-force-graph — Codemble's own renderer, advanced surface

**Repo:** <https://github.com/vasturiano/3d-force-graph> · **License:** MIT · **Maintained:** actively (Codemble pins `^1.80.0` in `web/package.json`). Capabilities below are from the README API reference.

Verified advanced features: **DAG mode** (`td/bu/lr/rl/zout/zin/radialout/radialin`), **link curvature** (3D béziers, `linkCurveRotation`), **directional particles** (`linkDirectionalParticles`, with custom particle objects via `linkDirectionalParticleThreeObject`), **custom node objects** (`nodeThreeObject`, with `nodeThreeObjectExtend` to extend rather than replace — the standard route to text sprites), **post-processing composer access** (bloom etc. — Codemble already exploits this), **engine callbacks** (`onEngineStop`/`onEngineTick`), **cooldown controls** (`cooldownTicks`/`cooldownTime`), **`d3Force()` access**, and **fixed positions via `fx/fy/fz`** (<https://github.com/vasturiano/3d-force-graph> README).

**Adoptable without free flight** (Codemble already pins every node with precomputed coordinates, which `fx/fy/fz` supports first-class):
- **Link curvature for parallel edges** — when a module pair has both an import route and a call edge (or a certain and a "possible" edge), a small fixed curvature keeps both visible instead of overdrawing. Deterministic: curvature is data, not simulation. → `web/src/GalaxyCanvas.jsx`.
- **`nodeThreeObjectExtend` text sprites** for always-legible system names at galaxy level (replacing/complementing DOM overlays). → `GalaxyCanvas.jsx`.
- **Custom particle objects** (`linkDirectionalParticleThreeObject`) to make the existing call-edge particles read as Edo-palette motes rather than default spheres. → `web/src/galaxyEffects.js`.
- **Not needed:** DAG mode and `d3Force` — Codemble computes layout server-side; enabling engine forces would surrender determinism.

---

## 4. chanhx/crabviz — LSP call graphs as interactive SVG (ideas only: AGPL)

**Repo:** <https://github.com/chanhx/crabviz> (the `hars/crabviz` path in the brief 404s; this is the real project) · **License:** **AGPL-3.0 → ideas only, never port code** · **Maintained:** VS Code release v0.5.0 on 2025-08-24 per README fetch; core crate at 0.8.0 in the clone.

**How it works** (verified from a shallow clone): a Rust core (compiled to WASM, `crate-type = ["cdylib"]`, `core/Cargo.toml`) consumes LSP data (document symbols + call hierarchy; `core/src/types/lsp.rs`) and builds the graph; the webview renders it with **`@viz-js/viz` — Graphviz in WASM — via `renderSVGElement`** (`webview-ui/src/graph/render.ts`; deps in `webview-ui/package.json`), so the layout is classic Graphviz layered dot. Files are clusters containing function "cells"; interactivity is **pure SVG post-processing**: every edge `<g>` carries `data-from`/`data-to` cell ids, and `CallGraph.ts` builds incoming/outgoing indexes, adds `incoming`/`outgoing` classes on click, and moves unrelated nodes/clusters into a `faded-group` element (`webview-ui/src/graph/CallGraph.ts`). README documents "Highlight on click," collapsing files to see file-level relationships, and HTML/SVG export (<https://github.com/chanhx/crabviz/blob/main/README.md>).

**Adoptable (as ideas):** the **click-to-focus grammar** — select a node → incoming edges one class, outgoing another, everything unrelated faded as a group — is cheap in Codemble's Map because the SVG is React-rendered from known edge endpoints; no layout change, pure class toggling. → `web/src/MapView.jsx`. **Rejected:** any code reuse (AGPL), and Graphviz-in-WASM as a layout engine (client-side layout + a heavyweight dependency; Codemble's layout belongs in Python).

---

## 5. glato/emerge — multi-language analysis + force graph

**Repo:** <https://github.com/glato/emerge> · **License:** MIT · **Maintenance:** last release 2.0.7, 2024-07-12 per README fetch — quiet since (treat as semi-stale).

Browser-based dependency/codebase visualizer for ~12 languages. Per-file/per-entity metrics: **SLOC, number of methods, fan-in/fan-out, Louvain modularity, whitespace complexity, TF-IDF semantic keywords, and git metrics (code churn, contributors)**; rendering is a D3 force-directed simulation with Louvain-based coloring (<https://github.com/glato/emerge> README). **Adoptable:** the metric menu — **fan-in/fan-out split** (Codemble's centrality is currently one number; distinguishing "many callers" from "many callees" is honest, parser-derived, and teaches architecture roles) and **whitespace complexity** as a zero-dependency complexity proxy. → `codemble/graph/finalize.py`. **Rejected:** D3 client-side force layout (determinism); git-churn metrics are real evidence but out of current scope (graph truth is parser evidence keyed by file hashes, not history).

---

## 6. sverweij/dependency-cruiser — rules, cycles, and the "archi" condensed view

**Repo:** <https://github.com/sverweij/dependency-cruiser> · **License:** MIT · **Maintained:** very — v18.1.0, July 2026 per README fetch.

Static JS/TS dependency analyzer: validates dependencies against user rules (cycle detection among the stock rules), reports as text/dot/mermaid/etc. What makes its high-level graphs readable is the **`collapsePattern`** mechanism: the **archi reporter** collapses everything below folders "directly under `packages`, `src`, `lib`, and `node_modules`" into single nodes; collapsed modules get a `consolidated` attribute that themes can style differently (<https://github.com/sverweij/dependency-cruiser/blob/main/doc/options-reference.md>). So the readable architecture view is *the same graph, deterministically folded by a path rule*, with consolidated nodes visually distinct. **Adoptable:** exactly that fold, for Phase-2 scale — when a project exceeds what the Architecture tab can show, collapse modules to their top-level package deterministically and mark collapsed nodes as consolidated (a projection, like language focus — graph truth unchanged). → `codemble/graph/mapview.py` + `web/src/MapView.jsx`. **Rejected:** nothing structural — it's honest static analysis; only its Graphviz/dot rendering path is irrelevant to the pinned stack.

---

## 7. githubocto/repo-visualizer — packed-circle repo diagram

**Repo:** <https://github.com/githubocto/repo-visualizer> · **License:** MIT · **Maintenance:** effectively frozen — self-described "an experiment"; last release 0.9.1, 2023-04-18 (README fetch).

A GitHub Action emitting an SVG of the repo as nested circles: **color = file type, nesting = directory depth (configurable to 9 levels)**; the specific d3 layout call is *unverified* from the README (visually it is a d3-hierarchy circle-pack). **Adoptable:** the encoding lesson — directory containment as *enclosure* rather than edges. Codemble's Architecture tab could group a package's modules inside a soft container (pairs with archify's boundary rects) instead of drawing `contains` edges. → `codemble/graph/mapview.py`. **Rejected:** nothing dangerous; it's just static and unmaintained.

---

## 8. ahmedkhaleel2004/gitdiagram — LLM-drawn architecture (UX ideas only)

**Repo:** <https://github.com/ahmedkhaleel2004/gitdiagram> · **License:** MIT · **Maintained:** active per README fetch (Next.js 16 stack).

Generates a Mermaid system diagram for any GitHub repo from the **file tree + README via an LLM** (OpenAI by default), in two stages: streamed prose explanation, then a "strict, size-bounded graph AST: groups, nodes, edges, shapes, labels, descriptions, and repository paths." Two ideas stand out despite the disqualifying pipeline: (1) **every component is clickable and opens its real file/directory on GitHub**, and (2) **the server validates all linked paths against the actual repository before persisting, with retries on invalid output** (README fetch of <https://github.com/ahmedkhaleel2004/gitdiagram>). **Adoptable:** the *validation posture* mirrors Codemble's grounding validator and endorses extending it: any surface that names a path must be checked against parser truth before display. Click-through-to-source everywhere is already Codemble law (`file:line`), reaffirmed. **Rejected:** the entire structure pipeline — an LLM inventing the component graph is precisely what the Correctness Contract forbids; the audience cannot detect when it is wrong.

---

## 9. Aider's repo map — tree-sitter tags + personalized PageRank

**Repo:** <https://github.com/Aider-AI/aider>, implementation `aider/repomap.py` (<https://raw.githubusercontent.com/Aider-AI/aider/main/aider/repomap.py>) · **License:** Apache-2.0 · **Maintained:** yes.

Verified from source: symbols are extracted with **tree-sitter tag queries** (`queries/tree-sitter-language-pack/{lang}-tags.scm`), split into *definitions* (`name.definition.*`) and *references* (`name.reference.*`). `get_ranked_tags()` builds a **`networkx.MultiDiGraph` whose nodes are files and whose edges are identifier references between files**, weighted by reference counts (scaled by `math.sqrt(num_refs)` so chatty identifiers don't dominate; 50× multiplier for files currently in chat; 0.1 self-edges for referenced-nowhere definitions). Ranking is **`nx.pagerank(G, weight="weight", personalization=..., dangling=...)`** — *personalized* PageRank, where the personalization dict boosts chat-relevant/mentioned files — followed by **redistributing each node's rank across its outgoing edges** (`rank * weight / total_weight`) to rank individual definitions. Selection into a token budget is a **binary search** over how many top tags fit (±15 % tolerance), with SQLite-backed tag caching keyed by mtime.

**Adoptable:** **personalized PageRank as Codemble's importance measure**, personalized on the selected Home/entrypoint — "important relative to where the learner starts" is pedagogically better than raw degree, it is deterministic (power iteration, fixed damping, fixed iteration cap, sorted tie-breaks), and ~40 lines of stdlib Python. Uses: brightness/centrality in `codemble/graph/finalize.py`, and orbit/hint ordering ("which planet should the learner study next"). The rank-redistribution trick maps cleanly onto ranking members within a region. **Rejected:** networkx as a dependency (reimplement), and the chat-file personalization concept (Codemble's equivalent signal is Home + lit regions, not a chat).

---

## 10. Layered-DAG layout engines — the algorithm Codemble's Architecture tab actually needs

Codemble must compute 2D layouts **in Python, deterministically** (graph-layer rule), so what matters here is the **Sugiyama framework** and license status of reference implementations. The canonical phases, per the ELK Layered documentation (<https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html>): **(1) cycle breaking** (greedy default), **(2) layering** (network simplex default; Coffman-Graham, MinWidth alternatives), **(3) crossing minimization** (layer sweep with barycenter; greedy-switch variants), **(4) node placement** (**Brandes-Köpf** default; linear segments, network simplex alternatives), **(5) edge routing** (orthogonal default; straight, splines).

| Project | License | Status | Notes |
| --- | --- | --- | --- |
| **dagrejs/dagre** <https://github.com/dagrejs/dagre> | MIT | Revived: v2.0.0, 2025-11-23; only the `@dagrejs` npm org receives updates (README) | JS. Its wiki's recommended reading names the exact papers to implement from: Gansner et al. *A Technique for Drawing Directed Graphs* (network-simplex ranking), Jünger & Mutzel (2-layer crossing minimization), Barth et al. (bilayer cross counting), **Brandes & Köpf** (*Fast and Simple Horizontal Coordinate Assignment*), Sander and Forster for compound/constrained variants (<https://github.com/dagrejs/dagre/wiki>). MIT means **porting to Python with attribution is legal** if reimplementing from papers stalls. |
| **eclipse-elk/elk** <https://github.com/eclipse-elk/elk> | **EPL-2.0 → ideas/docs only** (LICENSE.md title "Eclipse Public License - v 2.0") | Active (v0.11.0, 2025-09-15) | Java. Best-documented phase reference; use its docs as the spec, never its code. |
| **erikbrinkman/d3-dag** <https://github.com/erikbrinkman/d3-dag> | MIT | Active, v1.1.0 | TypeScript. Cleanly separated `sugiyama` operators (simplex layering; two-layer/optimal decrossing; greedy/simplex coords) — a readable modern reference implementation, portable if needed. |
| **bdcht/grandalf** <https://github.com/bdcht/grandalf> | **Dual GPLv2 / EPL-1.0 → ideas only, cannot vendor** (LICENSE: "distributed under either one of the two licenses") | ~1,500 LOC pure Python, version 0.8, "Under Development"; last-commit date unverified | Proof that a pure-Python Sugiyama (with Brandes-Köpf, per its README) fits in ~1.5k lines — but its license disqualifies both options for an Apache-2.0 project. Do not port. |
| **networkx `multipartite_layout`** <https://networkx.org/documentation/stable/reference/generated/networkx.drawing.layout.multipartite_layout.html> | BSD-3 (networkx) | Active | Docs state it "does not try to minimize edge crossings" — layer display only, **insufficient** for a readable Architecture tab. networkx has no full Sugiyama. |

**Adoptable — the centerpiece recommendation.** Implement a minimal Sugiyama pipeline in `codemble/graph/mapview.py`: BFS/longest-path layering from Home (cycle-break by removing back-edges toward Home, keeping them as routed "back" edges), a fixed number of **barycenter (or median) sweeps** with sorted deterministic tie-breaks, and either simple center-alignment or Brandes-Köpf for coordinates. Every phase is deterministic by construction; no dependency needed; dagre (MIT) and d3-dag (MIT) are legal cribs, ELK's docs are the spec, grandalf is licence-poisoned. **Rejected:** running any JS layout client-side (determinism + graph-layer rule), EPL/GPL code reuse.

---

## 11. Brief mentions

- **CoatiSoftware/Sourcetrail** <https://github.com/CoatiSoftware/Sourcetrail> — GPL-3.0, **archived 2021-12-14**, discontinued by its creators. Ideas only: its enduring UX is the synchronized three-pane loop (search ⇄ graph ⇄ real source) — the same loop as Codemble's galaxy⇄study panel, worth studying for edge-hover → code-line linking (three-view detail beyond the archive banner: *unverified from the repo page itself*).
- **cosmograph-org/cosmos** <https://github.com/cosmograph-org/cosmos> — MIT, active (v3.3, 2026-07-12). GPU force layout: "all the computations and drawing occur on the GPU in fragment and vertex shaders"; claims real-time simulation of hundreds of thousands of points. **Client-side, simulation-based layout conflicts with Codemble determinism** — logged only as a Phase-2+ escape hatch if a precomputed-positions mode (no simulation) ever exists at 100k-node scale.
- **MaibornWolff/codecharta** <https://github.com/MaibornWolff/codecharta> — BSD-3-Clause, very active (v1.143.0, 2026-06-23). Code-city metaphor: files are buildings; **area, height, and color are freely assignable metrics**; strictly local analysis. The lesson for Codemble is the *assignable-encoding discipline* (Codemble already fixes size=LOC, brightness=centrality, color=language — keeping encodings few and fixed is the differentiator, not a gap).

## 12. Broader 2024–2026 sweep (one search pass; two genuinely relevant finds)

- **Lum1104/Understand-Anything** <https://github.com/Lum1104/Understand-Anything> — MIT per search-result summaries (*license unverified against the repo file*). An AI-assistant plugin that scans a codebase with a multi-agent pipeline into a JSON knowledge graph plus an interactive React dashboard with architectural-layer grouping (API/Service/Data/UI) and a business-"domain view." Its own agent definitions describe "a two-phase approach: structural extraction script followed by LLM semantic analysis" with structural nodes never invented by the LLM. Relevant as the closest philosophical neighbor (deterministic skeleton + model prose on top), but its layer/domain *classification* is model-decided — in Codemble terms that is narration, never graph truth. Idea worth keeping: **grouping the architecture view by inferred layer bands is what beginners actually parse** — Codemble can get the honest version by layering on parser facts (call depth from Home, directory structure) instead of a model's opinion.
- **vitali87/code-graph-rag** <https://github.com/vitali87/code-graph-rag> — tree-sitter AST parsing across ~12 languages into a unified graph schema stored in Memgraph, queried in natural language for RAG (search summaries; PyPI `code-graph-rag`; license *unverified*). Relevant as convergent evidence that tree-sitter → language-neutral graph schema is the settled industry pattern Codemble already follows; its graph-database layer is out of scope for a local-first tool.
- A third distinct, verifiable 2024–2026 OSS find matching the brief did not surface in this pass (commercial tools like Repowise/CodeLayers dominated results and could not be verified as open source) — recorded honestly rather than padded.

---

## Shortlist — ranked concrete adoptions

| # | Adoption | Source | Codemble surface | Cost |
| --- | --- | --- | --- | --- |
| 1 | **Minimal Sugiyama layered layout** (layering from Home → barycenter sweeps with sorted tie-breaks → Brandes-Köpf or center alignment), pure Python, deterministic | ELK Layered docs (spec), dagre wiki papers, d3-dag (MIT reference) | `codemble/graph/mapview.py` Architecture layout | **M** (L if full Brandes-Köpf + compound boundaries in one go) |
| 2 | **Orthogonal elbow edge routing with side anchors + rounded corners, and boundary rects around package groups** | archify renderer geometry (MIT; port the math, not the runtime) | `codemble/graph/mapview.py` (points) + `web/src/MapView.jsx` (paths) | **M** |
| 3 | **Personalized PageRank centrality, personalized on Home** (with per-member rank redistribution inside regions) | aider `repomap.py` (Apache-2.0) | `codemble/graph/finalize.py` metrics; Easy-mode ordering | **S** |
| 4 | **Click-to-focus grammar in the 2D Map**: selected node → incoming/outgoing edge classes + faded-group for unrelated nodes | crabviz interaction model (AGPL — idea only, trivially re-expressed) | `web/src/MapView.jsx` | **S** |
| 5 | **Deterministic path-rule collapse ("consolidated" nodes) for over-scale Architecture views** | dependency-cruiser `collapsePattern`/archi (MIT) | `codemble/graph/mapview.py` + `MapView.jsx` (Phase-2 scale) | **M** |
| 6 | **Surprise-scored, graph-only "surprising connection" hints / check family** (confidence × cross-region × peripheral→hub) | graphify `analyze.py` (MIT) | `codemble/checks/` + Easy-mode hint selection in `codemble/graph/` | **S** |
| 7 | **Layout self-audit tests**: machine-readable layout report + checks for NaN coords, node overlap, edge-through-label | archify layout-report + check scripts (MIT) | tests beside `codemble/graph/mapview.py` | **S** |
| 8 | **Seeded Louvain constellation clustering with graphify's determinism kit** (canonical input order, total-order community IDs, membership hashes, remap-to-previous) — Phase-2 LOD only | graphify `cluster.py` (MIT; reimplement, don't take graspologic) | `codemble/graph/` (Phase-2), galaxy super-structure in `codemble/graph/layout.py` | **L** |
| — | *(smaller, riding along)* fan-in/fan-out split as separate render metadata (emerge); curved parallel edges + custom particle sprites (3d-force-graph API already pinned) | emerge (MIT), 3d-force-graph (MIT) | `finalize.py`; `GalaxyCanvas.jsx` + `galaxyEffects.js` | **S** each |

**Reading order for implementation:** #1 and #2 together are "better 2D architecture SVGs" (the archify wish, done honestly); #3 and #6 are "better graph connections" (the graphify wish, done deterministically); #4, #5, #7 are cheap polish/armor; #8 waits for Phase 2 by roadmap.
