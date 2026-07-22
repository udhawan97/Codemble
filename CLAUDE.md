# Codemble — agent brief & operating guide

Python 3.11 + FastAPI backend, Vite + React + `3d-force-graph` galaxy frontend.
A **learning game**, not a visualization tool and not a repo-tour generator:
*Codemble turns the code AI wrote for you into a galaxy you light up by
understanding it.*

This file is both the product spec and the agent's operating rules. Sections
marked **[AGENT-MAINTAINED]** are updated by the agent as work completes;
everything else changes only when the human owner (UD) approves via the
Decision Log.

## Commands

```bash
pip install -e ".[dev]"        # setup (venv recommended)
pytest                          # tests — CI gate
ruff check .                    # lint  — CI gate
codemble ./some-project         # run the CLI against a target project
codemble --version

cd docs-site && npm install
npm run dev                     # docs site at localhost:4321
npm run check                   # astro check — CI gate
npm run build                   # what the Pages workflow runs
```

## Layout

| Path | What |
| --- | --- |
| `codemble/adapters/` | LanguageAdapter seam; `python_ast.py` is the first adapter (M1) |
| `codemble/graph/` | Language-tagged graph + render-ready metadata (the frontend is a pure consumer) |
| `codemble/lens/` | Language lens: parser-detected idiom annotations → teachable notes |
| `codemble/checks/` | Active checks generated FROM the graph; answers never come from the LLM |
| `codemble/llm/` | Anthropic + OpenAI providers, BYO key, disk cache; narration only |
| `codemble/server/` | FastAPI: serves SPA + graph/checks JSON API |
| `codemble/progress/` | Local persistence: illumination + star chart (`~/.codemble/`) |
| `web/` | Galaxy renderer source (Vite + React + 3d-force-graph) |
| `codemble/web_dist/` | Versioned production SPA bundled in the Python wheel |
| `tests/` | Pytest suite |
| `docs/` | Internal: `adr/`, `plans/`, `research/` |
| `docs-site/` | Public site (Astro + Starlight → GitHub Pages) |

## Session protocol — read first, every session

**"What should we work on today?"**
1. Read **Current State** below; find the current milestone and next unchecked task.
2. Spot-check the repo matches the checkboxes (verify the last checked item runs).
3. Propose the **smallest next task** with a brief plan (files, verification).
4. On completion: check the box, update Current State (date + one-line note),
   append decisions to the Decision Log.

**"Plan the future" / "what's next?"** — answer from **Roadmap** (NOW → NEXT →
LATER). Do not invent scope; proposed changes enter the plan only with human
approval, recorded in the Decision Log.

**Milestone transitions** — a milestone advances only when its acceptance
criteria actually pass. Phase promotions (NOW→ NEXT items moving up) are
human-approved only; never self-promote.

**Standing rules**
- Never build **Non-Goals**. If a request conflicts, say so and point there.
- Ambiguity → ask the human; don't silently assume or expand scope.
- Small diffs; the project runs end-to-end after every session.
- Parser/graph/checks/persistence logic lands **with unit tests**; UI is
  verified by running it. A task isn't done until this file reflects it.
- The **Correctness Contract** outranks every feature request, including from
  the human — flag conflicts rather than quietly violating it.
- Anti-drift test for every feature: *"does this help a learner understand
  their code, or just decorate?"* Decoration waits.

## Product spec (locked)

- **Target user:** early/intermediate coder who built a project with Claude
  Code/Codex, doesn't fully understand it, can install a CLI, has a Claude or
  OpenAI key.
- **Local-first:** `codemble ./my-project` parses a local folder (no GitHub
  push needed) and serves the galaxy at localhost.
- **Semantic zoom, three levels, no free flight:** 1) **Galaxy** — modules =
  star systems, imports = routes, entrypoint = Home; camera on rails. 2)
  **System** — functions/classes as planets in deterministic orbits, call
  edges. 3) **Study** — panel with real source, grounded explanation, language
  lens note, checks; scene dims behind it. Scripted fly-to transitions.
- **Illumination is the game:** nodes start dim; passing a region's checks
  lights them permanently. **A region = one star system = one module** — the
  unit of checks, lighting, and invalidation. Star chart tracks language
  concepts. No other meta-progression.
- **Persistence:** local JSON in `~/.codemble/`, keyed by project path + file
  hashes; a changed file re-dims only its region.
- **Polyglot (from Phase 1):** nodes are language-tagged; users filter/focus
  the galaxy by language, each language with its own idiom lens.

## Architecture rules

1. **LanguageAdapter seam:** every language implements `discover(path)`,
   `parse(path) -> Graph`, `parse_files(root, files) -> Graph`, and
   `concepts(node) -> [ConceptAnnotation]`. Python first via stdlib `ast`; all
   later languages via tree-sitter. Nothing above the seam hardcodes a language.
   The JS/TS adapter reuses one internal syntax-evidence index across entrypoint,
   call, binding, and concept passes without widening this public seam.
2. **The graph is render-ready:** graph layer computes language, LOC,
   centrality, entrypoint rank, region id, understood-state. `LearnerSession`
   owns session transitions and local HTTP sequencing behind one external-store
   interface. React is a pure renderer of those truths — **no layout or game
   logic in React/the renderer.** This keeps the Phase-3 share-link viewer and
   any future renderer cheap.
3. **LLM narrates, never decides:** providers Anthropic + OpenAI, BYO key (env
   or `~/.codemble/config`), calls go direct from the user's machine, disk
   cache keyed by node + file hash. Input: real source + neighbors + concept
   annotations.
4. **Pinned stack:** Python 3.11+, FastAPI, Vite + React, `3d-force-graph`.
   Changes require a human-approved Decision Log entry.

## Correctness Contract — HARD CONSTRAINT

The audience cannot detect when the tool is wrong. Therefore:
1. **Structure is never invented** — nodes, edges, entrypoints, idiom locations
   come only from the parser.
2. **Explanations are grounded** — real identifiers only; say *"unclear from
   the code"* rather than guess.
3. **Lens claims attach only to parser-detected constructs.**
4. **Every explanation links to a real `file:line`.**
5. **Check answers come from the graph, never the model.**
6. **Approximate call edges are labeled "possible call."**

## Repo, docs & website ops

- **Docs site:** Astro 7 + Starlight 0.41 in `docs-site/`, deployed by
  `.github/workflows/pages.yml` to `https://udhawan97.github.io/Codemble/`.
  `base: "/Codemble"` is case-sensitive and must equal the repo name.
- **Sidebar is hand-authored** in `astro.config.mjs` — every new docs page
  needs a manual `{label, slug}` entry or it won't appear.
- **Design system:** `docs-site/design.md` is locked; `src/styles/tokens.css`
  is the value source of truth and **must load before** `custom.css`. Genre is
  the Edo star atlas on the Formal Edo palette. Two accents, one job each:
  kohaku amber = understanding/progress, ruri lapis = interaction — kohaku may
  never mark a navigation state. WCAG 4.5:1 floor on both grounds.
- **Plate artwork is generated:** `node docs-site/scripts/build-plates.mjs`
  rewrites `public/brand/plates/` from a fixed seed. Edit the script, never the
  SVGs; commit the output (the site never runs it at build time).
- **Site search is Pagefind**, which only exists after `npm run build` — the
  field says so in `npm run dev` rather than failing silently.
- **Docs cadence:** a milestone that changes user-facing behavior updates the
  relevant docs page(s) + sidebar in the same PR. CHANGELOG.md gets an entry
  per meaningful change (Keep a Changelog format).
- **Build in public:** weekly progress note; WIP galaxy shots are the content.
  README badges stay static until CI/releases exist, then switch to live
  shields (`github/v/release`, workflow status — FolioOrb pattern).
- **Community files:** Apache-2.0, Contributor Covenant 2.1, SECURITY.md
  (private advisories + `CODEMBLE SECURITY` email tag), issue forms, PR
  template with parser/LLM conditional checklists, Conventional Commits + DCO.

## Roadmap — NOW / NEXT / LATER

**NOW — Phase 1 tester evidence.** Exercise the shipped v0.2.0
Python/JavaScript/TypeScript and mixed-project loop on real learner projects.
The v0.1.0 Python learner-acceptance issue stays open in parallel; technical
completion does not claim those external runs passed.

**NEXT — Phase 2 (months ~3–6).** Go/Rust/Java adapters, LOD culling +
clustering for larger repos.

**LATER — Phase 3 (months ~7–9).** Shareable read-only galaxy link (the only
cloud touch). Extra quest types: trace-a-request, fix-the-failing-test.
Polish, then the coordinated launch (Show HN / X; lit-galaxy GIF as hero).

## Current State **[AGENT-MAINTAINED]**

**Current milestone: Phase 1 tester evidence** · Last updated: 2026-07-22 ·
Session note: v0.7.0 implements all fourteen findings of a fresh evidence-based
user-flow audit of the served v0.6.4 build (run as a first-run Easy learner on
this repository at 1280/375/320, with before/after screenshots) plus the
approved D1 design direction: parser-proven import communities now wear eight
deterministic traditional Japanese colour families (galaxy stars, planets, and
Architecture-box tints), lightness-capped beneath the unlit ceiling with the
amber band excluded so understanding stays the brightest claim in the sky.
Routes on both layers moved from the 1.6:1 border hairline to a dedicated
4.0:1 route ink (possible relationships stay dashed and deliberately more
visible); the Architecture map folds modules with no route from Home into a
counted shelf behind a Show-them control; Fit fits width when whole-shape fit
would be unreadable; and Easy guidance charges test-scoped paths a bounded
+1.5-hop penalty so a learner's own code outranks its test suite at equal
distance. Mechanical fixes: the nebula dawn restores sprite scale as a vector
(it squashed the lit system's name plate square), the map's language stripe
paints via a style property (an SVG fill attribute cannot resolve var() and
silently rendered navy), Escape on the Map is a window-level handler that
works with focus on body, stale map viewports re-centre on the focus point on
restore and on live resizes, the open Key stacks below the zoom controls, the
region panel's actions no longer clip, study connection dots carry names, and
the Easy register replaces parser vocabulary end to end ("candidate 1",
"Quiz · answers come from your code, not AI", "What it is / Length /
Evidence", fixture errors attributed "all under tests/"). Parser, graph,
checks, progress, provider, and HTTP contracts are byte-unchanged; the suite
grew a nebula-dawn scale-restore check plus community-colour, viewport, and
guidance-penalty contract assertions (241 pytest, ruff clean, 12 frontend
checks, rebuilt web_dist). Full planet realism explicitly remains a Phase 3
decision under the game-art Non-Goal. The milestone does not advance: issue
#13 still requires human tester evidence. Previously: v0.6.4 closes all twenty findings of a fresh end-to-end user-flow
audit run against the served build on three real projects (Codemble, Golavo,
FolioOrb) at 1280/375/320 px with a keyboard pass. The headline fix is a
Correctness Contract one: a missed check printed the parser answer and its
evidence and then accepted that answer, so a region could light without
understanding; a miss now returns neither, and both appear only after the
learner proves it. The Easy default layer gained the reading path it never had
(**Read the source** on the Map, guidance that says read-before-prove, Escape
stepping back a level), the checks panel became keyboard-usable (focus handoff
on open, focus preserved across submits), Enter now opens the arrow-selected
structure at study level, and the guidance chip is docked into its own strip
and hidden until the first-run decisions finish. Home calibration is now a
viewport-sized modal that states its candidate count, groups candidates by
their real scope, and keeps its escape hatch on screen; the audience question
is asked once per learner instead of once per project; the star chart is
reachable from every level and closes with Escape; exits name the layer they
return to; galaxy plates and the module index use path tails; Find opens on
Home and the busiest modules; and compact Map controls no longer share touch
targets (zero overlapping interactive rectangles at 320 and 375). Parser,
graph, checks, progress, and provider contracts are unchanged except for the
deliberate withholding of answers on a failed submission. Previously, v0.6.3
closed the four follow-up findings from the earlier user-flow audit. Easy guidance is now level-aware and never offers an enabled
no-op; compact Maps open at readable 100% around Home and preserve zoom/pan
through data refreshes; Switch project confirms on the first compact-Menu click
without leaking disclosure state across project or breakpoint changes; and Home
calibration, the coach, Modules, Find, and the Star chart own explicit keyboard
focus handoffs. Parser, graph, checks, progress, and provider contracts remain
unchanged. The bundled app is verified across compact and desktop widths; the
milestone does not advance because issue #13 still requires human tester
evidence. v0.6.2 was the immediate installed-artifact fix that moved the
first-run audience modal to the document top layer, and v0.6.1 remains the
responsive learning-loop release. The v0.6.0
architecture-depth pass is complete in five
behavior-preserving waves: project selection owns the home-jailed filesystem
policy; project activation atomically owns parse-to-live binding and graph/map
caches; project mapping owns picker attempts, polling, retry, outage, stale
responses, and release; the Name Atlas owns deterministic plate placement; and
the indexed Learner Projection reuses every unaffected derived view. The
1,000-node hover benchmark moved from ~0.331 ms to ~0.001 ms per commit, while
the HTTP, graph, check, persistence, and UI contracts stayed fixed. The current
milestone does not advance: issue #13 still requires human tester evidence.
Earlier architecture-deepening maintenance completed after the verified v0.2.0
release; all four report recommendations merged in phases. The public site was
then redesigned to the Formal Edo palette and Edo star-atlas genre, with an
expanding Pagefind search shared by the landing and docs; no parser, graph,
checks, persistence, or app behaviour was touched. A tester-run rehearsal of
the shipped loop then
verified Home calibration, study source, checks, illumination, and restart
persistence end to end, and found one real defect: multi-answer checks with four
or more answers offered no wrong option, so select-all lit a region without
proving understanding. Fixed with a regression test; 17 of 107 questions on this
repository were affected and no region lost a check. The root README was then
restructured around the learning loop, fast tester setup, correctness, and the
local/AI boundary. Its top mark now uses self-contained, GitHub-safe motion with
a static reduced-motion state; no product or app behavior changed. Bare
`codemble` now serves an in-app project picker (home-jailed browse +
recents, Host-header allowlisted) instead of the current directory; README,
docs-site, the changelog, and a new PyPI release checklist now lead with
`uvx codemble` ahead of the pending first PyPI publish. A galaxy UX overhaul
design was then interviewed and approved (spec
`docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md`): three phases —
light up the shipped-but-inert narration/mode/connections surface plus project
switching, then the "living cosmos" visual overhaul with a 2D Map layer, then
~1,000-file scale with staged parse progress; four Decision Log entries record
the approved Non-Goal and binding relaxations. Phase A (the narration/mode/
connections surface and project switching) and Phase B (M12: call-depth
orbits, the 2D Map layer, and the living-cosmos visual overhaul) have both
since shipped, and were released together as **v0.4.0** (tag `v0.4.0`, published
to PyPI, verified end to end from a clean `uvx codemble==0.4.0` install: the
wheel's SPA bundle is byte-identical to the tag, all 27 regions draw unclipped,
and the galaxy renders deep space with no console errors). Phase C (M13:
~1,000-file scale with staged parse progress) has since shipped from that
plan: parsing now runs on a worker thread behind a `202`-accepted picker
select and a polled `GET /api/picker/progress` through five honest stages,
cancellation is checked between files and a crashed worker reports as an
in-app error rather than a hung server, the scale cap moved 300 → 1,000 with
the over-cap prompt offering clickable busiest scopes plus a home-jailed typed
path, a one-pass check index replaced the per-region edge scans
(byte-identical suites, pinned by a golden fixture before the refactor),
`/api/graph` and `/api/map` responses are now cached with invalidation on
light-up, Home change, and binding, and a Clear this project's progress
control was added to the star chart. A dedicated verification pass at a
realistic ~1,000-file project then found the `resolving` stage — the slowest
one — showed no moving signal for most of the wait; the fix narrates its real
sub-steps instead of leaving the screen static, and a parser hotspot found
alongside it (an O(definitions × modules) module-resolution scan in the Python
adapter) was fixed too, together taking real parse wall-clock on a 1,000-file
Python project from roughly 11.5s to roughly 7.5s with byte-identical output.
Suite hermeticity was also closed on the read side: `CODEMBLE_DATA_DIR` now
relocates the narration cache and the `config` file as well as saved progress
through one `codemble/paths.py` helper, and the test suite clears every
provider variable `from_environment` reads, so a server test can no longer make
a real billed API call against a developer's exported key. A pre-release
re-audit then closed a cluster of first-run gaps that converged on the
Easy-default learner (who lands on the 2D Map): the coach-marks and footer now
teach the layer the learner is actually on, the audience gate and coach-marks
no longer stack as two modals, the no-entrypoint Map tabs stop pointing at a
Change Home button that isn't shown, language focus now filters the Map as a
frontend projection, and a parse `bind` that outlasts a cancel can no longer
rebind a released project. Phase C plus that gap-fix wave shipped as **v0.5.0**;
the parse work collided with an independent implementation of the same three
foundational commits on `main`, reconciled by taking the branch's verified
superset while preserving main's unique `CODEMBLE_DATA_DIR`/config-isolation
fix, which lived in files the branch never touched. The Architecture map now
uses deterministic barycenter ordering and backend-routed, directional,
weight-scaled SVG paths; cycle and long-span routes use clear flank corridors,
while possible relationships remain dashed and React remains a pure renderer.
Galaxy regions now place in deterministic constellations derived only from
parser-proven import communities, with the community ID exposed in graph schema
5 and progress signatures remaining coordinate-independent. A tester then
reported the 169-system galaxy unnavigable and undifferentiated, which resolved
into four separate defects: the camera could not move at all, no star carried a
name and there was no search or index, every region route drew unconditionally
so the mesh outshone the stars, and a display-size heading plus a twelve-row
always-on legend covered the stage. All four are fixed — bounded orbit,
progressive reveal keyed to a new `hops_from_home` graph field (schema 6),
ranked and decluttered name plates, a command palette plus an index sidebar over
one shared module index, and chrome demoted to a single line with the legend
behind a disclosure. On this repository the default galaxy went from 90 systems
with their whole route mesh to 22 charted with the rest drawn faint, unnamed and
edgeless; nothing was removed from the graph and no region re-dimmed. Four
defects were caught by running it rather than by the suite: a sprite map cleared
by an effect that ran after the one that filled it, an undefined constant that
threw inside the declutter timer and silently erased every name, plates that
claimed one screen cell regardless of their real width, and an open sidebar
occluding the system panel's primary action. A fifth followed: labels offered
only one position each, directly above their star, so at galaxy zoom nearly
every plate lost its slot to a neighbour and a 90-system sky carried one name.
Names now try a short list of slots around the star and collision-test where the
plate actually draws rather than where its star sits — 1 name became roughly 24
with everything shown, 9 by default. The same navigation and clarity pass was
then applied to the Map layer, where two of the three galaxy problems turned out
to exist in a sharper form: a fixed-width box truncated the dotted region id, so
`codemble.server.app` and `codemble.server.runtime` both rendered as
`codemble.server…` — identical text for different modules — and a 960x2640
diagram sat in a plain scroll box showing four of its nine import layers. Boxes
are now named by the tail of their real path (map schema 3, zero visible-text
collisions across all 90 boxes on this repository) and the Map gained zoom, Fit,
and drag-to-pan. Progressive reveal was deliberately not extended to the Map.

### M0 — Repo, docs & website scaffold ✅ (2026-07-19)
- [x] Root: README, LICENSE (Apache-2.0), CoC, SECURITY, CONTRIBUTING,
      CHANGELOG, .gitignore, .env.example, pyproject
- [x] `.github/`: CI (pytest+ruff / astro check), Pages deploy, issue forms,
      PR template, dependabot
- [x] Package skeleton (`codemble/` with module docstrings), smoke tests
- [x] docs-site: Starlight scaffold, tokens + design.md, 12 seeded pages,
      hand-authored sidebar, brand marks

### M1 — Parser & graph ✅ (2026-07-19)
- [x] `adapters/base.py`: LanguageAdapter interface + Graph/Node/Edge/ConceptAnnotation models
- [x] `python_ast.py`: modules, functions, classes with file + line spans
- [x] Import edges (project-resolved where possible; external flagged)
- [x] Call edges by name resolution (unresolved flagged "possible call")
- [x] Entrypoint ranking (`__main__`, `main()`, app objects)
- [x] Render metadata (LOC, centrality, region id, language)
- [x] Graph JSON serialization + fixture-project unit tests

**Acceptance:** runs on a real ~50-file Python project in <5s; 20 hand-verified
edges correct; unresolved calls flagged, never dropped or invented.

### M2 — Galaxy renderer + semantic zoom (weeks 2–4)
- [x] FastAPI serves SPA + graph JSON
- [x] Galaxy level: systems/stars/routes, deterministic layout
- [x] Encoding: size=LOC, brightness=centrality, color=language, Home marked
- [x] Semantic zoom galaxy → system (tidy orbits + call edges), camera on rails
- [x] Dim/lit states rendered from graph JSON

**Acceptance:** same code → identical layout; interactive framerate at ~1k
nodes on a mid-range laptop; transitions scripted, no free flight anywhere.

### M3 — Study panel + grounded explanations (weeks 4–5)
- [x] Study panel: click planet → source with line numbers
- [x] Provider abstraction (Anthropic + OpenAI), BYO key config
- [x] Grounded prompt template (source + neighbors + annotations; contract embedded)
- [x] `file:line` links in every explanation
- [x] Disk cache by node + file hash
- [x] Graceful no-key state (galaxy + checks still work)

**Acceptance:** explanations cite only real identifiers; cache hit on re-open;
pulling the key degrades gracefully.

### M4 — Language lens + star chart (weeks 5–6)
- [x] `concepts()` for Python: decorators, comprehensions, generators, context
      managers, async/await, dunder methods, exceptions, type hints
- [x] Lens notes in study panel, anchored to detected construct lines
- [x] Star chart screen: concepts encountered vs. understood

**Acceptance:** every lens note points at a parser-detected construct at a real
location; chart updates as concepts are studied.

### M5 — Checks + illumination + persistence (weeks 6–7)
- [x] Check generator (four types), answers validated from graph only
- [x] Region "understood" flow → permanent lighting
- [x] Persistence in `~/.codemble/`; changed file re-dims only its region

**Acceptance:** no check answer ever comes from the LLM; progress survives
restart; editing one file re-dims only that region.

### M6 — Polish + first testers (weeks 7–8)
- [x] Entrypoint picker when ambiguous; scale-cap prompt (>~300 files → subdir)
- [x] Partial-parse handling (syntax errors flagged; galaxy never crashes)
- [x] README demo GIF; `pipx`/`uvx` install path
- [ ] 3–5 early testers onboarded from learner communities

**Acceptance:** a stranger runs it on their own AI-built project without help
and lights up at least one system.

### M7 — Language orchestration (Phase 1 wave 1)
- [x] Make `LanguageAdapter` discovery and file ownership explicit
- [x] Add one language-neutral `ProjectParser` interface for discovery, scale
      guarding, graph composition, Home selection, and collision rejection
- [x] Route CLI and local server through `ProjectParser` without changing the
      Python-only graph bytes

**Acceptance:** the existing Python fixture is byte-identical through the new
interface; injected second-adapter tests prove deterministic mixed graph merge,
global Home ambiguity, and fail-closed node-ID collision handling.

### M8 — JavaScript/TypeScript structure (Phase 1 wave 2)
- [x] Add official tree-sitter runtime + JS/TS/TSX grammar wheels
- [x] Parse JS/JSX/MJS/CJS/TS/TSX/MTS/CTS modules, functions, classes, methods,
      imports/exports, calls, source spans, file hashes, and partial syntax
- [x] Resolve same-project JS/TS imports and statically provable calls; label
      all approximate relationships as possible
- [x] Rank parser-proven JS/TS entrypoints and compose mixed Python+TS projects

**Acceptance:** fixture assertions hand-check exact structures/edges/spans;
syntax errors remain visible and partial; repeated mixed parses are byte-identical.

### M9 — JavaScript/TypeScript language lens (Phase 1 wave 3)
- [x] Detect JS/TS idioms only from tree-sitter nodes at exact source spans
- [x] Add learner-facing notes for async/await, arrow functions, destructuring,
      optional chaining, nullish coalescing, modules, types/interfaces, generics,
      and JSX where parser evidence exists
- [x] Keep star-chart concepts language-tagged and collision-free

**Acceptance:** every TS/JS Lens note maps to a parser annotation and real
`file:line`; malformed source yields no invented concepts.

### M10 — Polyglot focus + Phase 1 tester release (Phase 1 wave 4)
- [x] Add an accessible language focus control for mixed galaxies without
      changing graph truth, deterministic coordinates, or progress
- [x] Verify focus behavior at galaxy/system/study levels and at 320 px
- [x] Update README, public docs, packaged SPA, changelog, and release evidence
- [x] Publish and verify the Phase 1 tester release from the exact `main` tag

**Acceptance:** Python-only behavior remains intact; a mixed fixture can focus
Python, JavaScript, or TypeScript without hiding uncertainty; source install,
wheel install, web build, docs build, and downloaded release asset all pass.

### M11 — Architecture deepening maintenance ✅ (2026-07-19)
- [x] Centralize canonical graph finalization across language adapters and project composition
- [x] Deepen `ProjectParser` project intake and reuse discovered file evidence
- [x] Move learner-session transitions behind one testable frontend interface
- [x] Reuse one internal JS/TS syntax-evidence index across parser passes

**Acceptance:** existing Python and mixed graph bytes stay deterministic; project
intake avoids repeated discovery; learner transitions are tested above local HTTP;
JS/TS certainty and concept evidence remain parser-proven through the unchanged
`LanguageAdapter` interface.

### M12 — Living cosmos + 2D map (galaxy UX overhaul, Phase B) ✅ (2026-07-20)
- [x] System orbits by call depth from the region's entry node, hash-seeded and
      deterministic; layout coordinates changed once, saved progress did not
- [x] `GET /api/map`: deterministic Architecture and Workflow 2D layouts
      computed in `codemble/graph/`, reading the same graph as `GET /api/graph`
- [x] A 2D Map layer (Architecture + Workflow tabs) switchable from the header,
      plain SVG, no WebGL dependency
- [x] Canvas-generated halos, language-tinted nebulae, a hash-seeded starfield,
      composited bloom, and drifting particles on certain call edges only
- [x] The ~1.2s nebula-dawn light-up moment, with an instantly finished lit
      state under reduced motion
- [x] Easy mode defaults to the Map with reduced edge density and a
      graph-derived hint chip; Expert defaults to the galaxy; an explicit
      layer choice always beats the mode default
- [x] First-run coach-marks, a clickable breadcrumb, and a language-tint
      legend key

**Acceptance:** the map and the galaxy read one graph and cannot disagree;
uncertainty renders distinctly in both — colour-only in the 3D galaxy (no
line-dash support there), genuinely dashed in the 2D map; region signatures
hash file content, never coordinates, so the orbit relayout did not re-dim any
region; reduced motion always yields the finished lit state with zero
animation.

### M13 — Galaxy UX Phase C: scale ✅ (2026-07-20)
- [x] Threaded parse behind `202` select, `GET /api/picker/progress`, and a
      staged loading screen with real file counts
- [x] Cancellation checked between files; a crashed worker becomes an error
      state, never a hung server
- [x] Scale cap 300 → 1,000; clickable busiest scopes plus a jailed path field;
      suggestions in the non-TTY CLI refusal
- [x] One per-bind check index replacing the per-region edge scans, pinned by a
      golden suite fixture
- [x] Cached `/api/graph` and `/api/map` documents invalidated on light-up,
      Home, and binding
- [x] Terminal stage lines for `codemble <path>`; reset-progress control

**Acceptance:** a ~1,000-file project parses with live progress and reaches an
interactive galaxy; re-fetching the graph does not re-sort the world; the scale
prompt is actionable entirely in-app; generated check suites are byte-identical
to before the index change.

### M14 — Architecture depth and indexed learner views ✅ (2026-07-21)
- [x] Put canonical browse-root resolution, folder listing, and recent-project
      filtering behind `ProjectSelector`
- [x] Make parse-to-live binding, stale-worker refusal, release, and graph/map
      cache lifetime atomic behind `ProjectActivation`
- [x] Put picker attempts, parse polling/backoff, retry, outage, reset, and
      stale-response guards behind one Project Mapping Run
- [x] Put name ranking, camera budget, projection, slots, collision cells,
      sprite metadata, and cleanup behind one deterministic Name Atlas
- [x] Index learner projections by their real dependencies and prove hover-only
      commits reuse stable outputs; benchmark the 1,000-node case

**Acceptance:** public HTTP payloads and parser/check/persistence contracts are
unchanged; focused module suites and the existing end-to-end session/server
suites pass; the production SPA is rebuilt; the 1,000-node projection benchmark
shows lower repeated-commit work without changing derived values.

## Decision Log **[AGENT-MAINTAINED — append only]**

| Date | Decision | Why |
| --- | --- | --- |
| 2026-07-18 | Learning-game identity; galaxy serves it | Resolved 3-way identity fight |
| 2026-07-18 | Galaxy IS the map in v1 via semantic zoom; free flight banned | Wonder + readable study |
| 2026-07-18 | Light gamification only (illumination + star chart) | The light-up IS the reward |
| 2026-07-18 | Phase 0 ≈ 6–8 weeks, nothing slipped | Honest budget for 3D in v1 |
| 2026-07-18 | Python first via stdlib `ast` behind adapter seam; tree-sitter later | Precision now, plugin languages later |
| 2026-07-18 | BYO Claude/OpenAI key; no Ollama | Learners can't catch a weak model's errors |
| 2026-07-18 | Local-first; no GitHub ingestion in v1 | Beginners' code isn't pushed yet |
| 2026-07-18 | Stack: Py3.11+/FastAPI/Vite+React/3d-force-graph | Solo-friendly, proven |
| 2026-07-18 | v1 scale cap ~300 files; LOD in Phase 2 | Beginner projects are small |
| 2026-07-18 | Build in public day 1; loud launch at Phase 3 | Users first, launch when ready |
| 2026-07-19 | Name: **Codemble** | Chosen by UD |
| 2026-07-19 | Repo layout, docs-site (Astro+Starlight 0.41, Pages), community files mirror FolioOrb/Golavo | Family consistency across UD's projects |
| 2026-07-19 | Apache-2.0; Contributor Covenant 2.1; Conventional Commits + DCO | Match sibling repos |
| 2026-07-19 | Brand: star-gold=understanding, orbit-cyan=interaction; observatory-instrument genre | design.md locked |
| 2026-07-19 | M1 graph adds `Edge.external`, `Node.partial`, and `Graph.partial_files` | The playbook requires external and failed parses to stay explicit; these fields prevent consumers from inferring or inventing that state |
| 2026-07-19 | One source module is one region; layout coordinates and import routes are computed in the graph layer | Progress invalidation is module-scoped and the renderer must remain a deterministic pure consumer |
| 2026-07-19 | Semantic zoom is input-driven and scripted; 3D navigation controls remain disabled | Preserves the locked no-free-flight learning contract while keeping the map keyboard-accessible |
| 2026-07-19 | `StudyService.study(node_id)` is the study seam; provider adapters expose only `complete(prompt)` | Source loading, prompt construction, validation, and caching stay local while the two true external transports remain replaceable |
| 2026-07-19 | `~/.codemble/config` accepts TOML (or JSON) and validated explanations cache by prompt/provider/model/node/file hash | Keeps BYO configuration readable and prevents stale prose after source or model changes |
| 2026-07-19 | Graph schema 2 carries parser-owned concept annotations; star-chart studied state is session-local while understood state comes only from checks | The Lens can teach exact syntax without guessing, and viewing a structure cannot masquerade as mastery |
| 2026-07-19 | `CheckService` owns four deterministic graph-only check families; `ProgressStore` owns atomic region signatures separately from the graph parser | No model can decide correctness, and changed source invalidates only the region whose file evidence changed |
| 2026-07-19 | A region with zero safe graph checks stays dim and says why instead of auto-lighting on visit | Auto-light would claim understanding without evidence and violate the Correctness Contract, so this intentionally overrides the Phase 0 playbook fallback |
| 2026-07-19 | Graph schema 3 separates ranked entrypoint candidates from selected Home; ambiguous rank-zero candidates require the learner or `--entrypoint` | Parser rank is evidence, but choosing between equal candidates is a user decision and must not be guessed |
| 2026-07-19 | Commit the production SPA under `codemble/web_dist` and bundle it in the wheel | `pipx`/`uvx` Git installs must run without Node or a source checkout; the Vite build and isolated wheel smoke test keep the bundle honest |
| 2026-07-19 | v0.1.0 is a tester release; keep Phase 1 out of NOW until 3–5 unaided learner runs pass | Technical completion cannot substitute for the human first-run acceptance criterion |
| 2026-07-18 | Owner explicitly promoted Phase 1 implementation while v0.1.0 learner acceptance continues in issue #13 | Build authorization is explicit; keeping the issue open prevents the promotion from fabricating human evidence |
| 2026-07-18 | `ProjectParser` is the one project-level interface; language adapters own file syntax and node IDs, while composition owns global Home and collision checks | The second adapter makes the seam real without leaking registry or language rules into CLI, server, graph, checks, or UI |
| 2026-07-18 | One tree-sitter adapter owns JS and TS dialects; exact paths may be certain, but extension substitution and extensionless resolution remain possible | Cross-JS/TS resolution stays local to one implementation and never upgrades a configuration-dependent guess into fact |
| 2026-07-18 | Graph schema 4 adds an explicit language to every concept annotation; the star chart keys concepts by language plus concept ID | Python and JS/TS may share names such as async/await, but their evidence and learning progress must never collide silently |
| 2026-07-19 | Language focus is a frontend projection over the immutable mixed graph, not a parser mode or saved preference | Filtering must never mutate coordinates, progress, uncertainty, or parser truth; cross-language navigation remains available |
| 2026-07-19 | v0.2.0 is tagged from exact-main commit `b6b7776` with a wheel and SHA256SUMS release asset | A release is complete only after CI, live docs, fresh download, checksum, isolated install, and mixed parse all pass |
| 2026-07-19 | Canonical graph finalization is one graph interface shared by adapters and project composition | Home selection, edge deduplication, centrality, annotation ordering, and layout are language-neutral truth and must not drift per adapter |
| 2026-07-19 | `ProjectIntake` carries one normalized scope and its adapter-owned files from scale selection through parsing | `ProjectParser` owns the 300-file policy, and adapters must not rediscover file evidence that project intake already resolved |
| 2026-07-19 | `LearnerSession` owns frontend transitions and request sequencing behind snapshot, subscription, lifecycle, and event-dispatch operations | React remains a renderer of session truth, local HTTP is replaceable, and transition races are testable through an in-memory adapter |
| 2026-07-19 | One internal `_SyntaxEvidenceIndex` owns JS/TS parse, definition, ownership, binding, and symbol lookups across parser passes | Rebuilding overlapping maps made certainty-sensitive passes harder to reason about and imported-call resolution scanned every node; the public `LanguageAdapter` seam stays unchanged |
| 2026-07-19 | Public-site palette moves to **Formal Edo** (kachi/ruri/kohaku/gofun) from `codemble_design/assets`; accent *jobs* are unchanged | UD supplied the palette and approved the redesign. Star-gold→kohaku and orbit-cyan→ruri swap values only: illumination still means understanding, interaction still means ruri. `design.md` was locked, so this entry is the approval record |
| 2026-07-19 | Site genre becomes **Edo star atlas**; landing is numbered plates in 起承転結 order, signature is a tatebanko paper-diorama hero | A canvas of dots in space is what every code-graph tool ships. The atlas makes "space exploration" and the Japanese theme one object instead of two glued together, and the four-act form is true of the content — plate three is a real turn |
| 2026-07-19 | Landing lives at `src/pages/index.astro` (standalone), replacing `src/content/docs/index.mdx` | Three of four sibling sites use a standalone landing; it gives scoped CSS and its own `<head>`, and the two files would otherwise collide on `/Codemble/`. Content moved, not lost |
| 2026-07-19 | Plate artwork is generated by a committed script from a fixed seed, not hand-authored | Geometric art needs exact coordinates and a readable diff; "same seed → same sky" mirrors the app's determinism rule. Output is committed so the site never runs it at build time |
| 2026-07-19 | One expanding `Search.astro` serves both the Starlight header and the landing nav | Family convention (Golavo and FolioOrb each override this slot). Pagefind only exists post-build, so the field states that in dev rather than failing silently |
| 2026-07-19 | Every check must offer a wrong option; a question the graph cannot supply one for is dropped, not asked | A four-or-more-answer check offered only its own answers, so select-all lit a region while proving nothing. Correct answers still came from the graph, so the Correctness Contract held — but illumination stopped meaning understanding, which is the product's core claim |
| 2026-07-19 | The app self-hosts the Formal Edo faces; it never loads the site's Google Fonts CDN | `web/src/tokens.css` imports the site's tokens, so the redesign silently changed the app's requested faces. The app is local-first and says "Local only" in its own footer, so a CDN request would break offline use and contradict that promise |
| 2026-07-19 | Understanding owns the top of the canvas brightness range: the unlit centrality ramp caps at `--cm-ink-2` and lit stars use `--cm-star-high` | Lit at 8.5:1 sat below the unlit ceiling of 17.4:1, so a busy un-understood module looked more lit than an understood one. Approved by UD; uses existing tokens only, so `design.md` is unchanged |
| 2026-07-19 | Canvas palette values are resolved to `rgb()` before they reach WebGL | A custom property returns its authored text, so `color-mix()` tokens rendered black — silently hiding unchartable nodes and every "possible call" edge, which the Correctness Contract requires to stay visible |
| 2026-07-19 | The root README uses a self-contained animated ensō mark; app icons and favicons remain static | GitHub strips page-level scripting, so motion belongs inside the referenced SVG. The loop is restrained to illumination, transforms, and opacity, and reduced-motion users receive the finished lit state |
| 2026-07-19 | Bare `codemble` serves a one-shot in-app project picker (browse + recents) on a single two-phase server; binding is one-shot and the API is home-jailed with a Host-header allowlist | Approved by UD this session: easiest possible run flow for learners without a second server, without free filesystem enumeration, and without changing the one-graph app model |
| 2026-07-19 | Codemble publishes to PyPI from the next tagged release; install collapses to `uvx codemble` | Approved by UD this session: the git+tag install was the biggest onboarding hurdle for the target learner |
| 2026-07-19 | Local models (Ollama) are now allowed, reversing the 2026-07-18 Non-Goal; guardrails: loopback-and-`http`-only enforced at construction, explicit opt-in with no auto-detection, the same grounding validation applied to every provider, and the deterministic Tier 0 summary always available as a floor | Approved by UD this session. Residual risk stated honestly: grounding validation catches an invented identifier, not a wrong claim about a real one, and small local models make that second kind of error more often |
| 2026-07-19 | A 2D Map layer (architecture + workflow-tree tabs) joins the 3D galaxy behind one switcher, superseding the "no second 2D renderer in v1" Non-Goal; layouts are computed deterministically in the graph layer and React stays a pure SVG renderer | Approved by UD in the galaxy UX overhaul interview (spec `docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md`); beginners read flat maps more easily and the render-ready graph rule makes the second view cheap and truthful |
| 2026-07-19 | Scale target raised to ~1,000 supported files with a worker-thread parse, polled staged progress, and an honest loading screen; the subdirectory prompt moves to the new cap | Approved by UD: a deliberate partial pull-forward of Phase 2 scale work; full LOD/clustering stays in Phase 2 |
| 2026-07-19 | One-shot project binding relaxed to an explicit in-app reset (`POST /api/picker/reset`); home jail and Host allowlist unchanged | Approved by UD: learners must be able to switch projects without killing the server; per-project progress makes switching safe |
| 2026-07-19 | App art direction is "living cosmos" within the Formal Edo palette: halo sprites, bloom, hash-seeded starfield, language-tinted nebulae, call-depth system orbits (layout bytes change once, still deterministic), and an Easy/Expert UI toggle riding the shipped audience-mode backend | Approved by UD section-by-section; amber keeps its monopoly on understanding, uncertainty stays dashed in both layers, and Easy-mode guidance is graph-deterministic (nearest unlit region by route hops), never model-decided |
| 2026-07-20 | System orbits are call depth from the module's entry node, with the seed widened to include members no sibling calls | A module node makes no intra-project calls, so the spec's literal seed was always empty and stranded every member in the outermost ring. Both spec rules are preserved: the entry's callees are ring 1, and unreachable members take the outermost ring by node id |
| 2026-07-20 | The workflow tree's first hop is labelled `defines`, not `calls` | The selected entrypoint is usually a module, and the parser observed no call from a module to its own function. Containment is real parser truth (`Node.region`); relabelling it a call would have invented an edge |
| 2026-07-20 | Nebula tints ship lighter than the values in the design spec | The spec's starting values measured 3.19–4.46:1 against `--cm-ground-2` and failed the 4.5:1 legend floor. Hue is held; only lightness moved, and all three stay below `--cm-ink-2` so amber's monopoly is intact |
| 2026-07-20 | Bloom resolution is capped with `composer.setPixelRatio(1)`, not the `UnrealBloomPass` constructor | `EffectComposer.setSize` forwards the canvas size to every pass on resize, overwriting the constructor's `resolution`. The pixel ratio is the cap that survives |
| 2026-07-20 | **Corrects the row above**: bloom is capped by wrapping the bloom pass's own `setSize`, and the composer keeps the renderer's pixel ratio | The pixel ratio *did* cap bloom, but `EffectComposer.setSize` multiplies it into `renderTarget1/2` and every pass, so the whole scene rendered at 1x and upscaled — measured 1280x611 scene passes on a 2560x1221 buffer at dpr 2. Wrapping the one pass caps the one expensive thing: scene now 2560x1221, bloom mip 0 800x382 (1280x611 uncapped), `?benchmark` at 951 nodes unchanged at 928.8 → 961.5 fps median |
| 2026-07-20 | **Corrects "binding is one-shot"** (2026-07-19 picker row): binding is one-*at-a-time*. `serve_project` attaches `PickerConfig(browse_root=Path.home())` too, so a `codemble <path>` run also exposes the picker endpoints after a reset, and browse then enumerates non-hidden directories under `$HOME` | The Switch project control has to work without a process restart, which is what that config is for — but the earlier row still claimed a permanent 409 for the path-opened flow, and this file is the source of truth. The home jail and the Host-header allowlist are unchanged; only the "one-shot" claim was false. An app built with no `PickerConfig` at all remains genuinely one-shot and refuses reset |
| 2026-07-20 | `CODEMBLE_DATA_DIR` owns every home-directory path — progress, the narration cache, and the `config` file — through one `codemble/paths.py` helper; the test suite additionally clears every provider variable `StudyService.from_environment` reads | The variable redirected progress only, while `StudyService` hardcoded `Path.home()` for the other two, so `create_app`'s default study service read the developer's real config and `ANTHROPIC_API_KEY`. Two server tests GET `/explanation` and assert only that a `status` key came back — true of `no_key`, `ready`, and `error` alike — so on a machine with a key they made a real billed API call and cached the reply under the developer's home while still passing. Redirecting the directory does nothing about the process environment, which is why the suite must clear the keys as well. No new variable is introduced, the default stays `~/.codemble`, and explicit `environ`/`config_path`/`cache_root` arguments still win over both channels |
| 2026-07-20 | Progress reporting is a thread-scoped per-file hook (`note_file_parsed`) bound by `ProjectParser`, not a new `LanguageAdapter` parameter | The public adapter seam must stay unchanged for Phase 2 languages; one hook site per adapter also gives cancellation its exact "between files" meaning |
| 2026-07-20 | Phase C adds `DELETE /api/progress`, the `CLEAR_PROGRESS` session event, and a `clearProgress` adapter method beyond the shared contract's Phase C rows | The contract's Phase C rows covered parse progress only, while the no-reset-progress-control gap is mapped to Phase C by the spec; recorded here rather than silently widened |
| 2026-07-20 | Generated check suites are pinned by a committed golden fixture before any performance work touches `checks/service.py` | The Correctness Contract makes suite drift top-severity, and a refactor that changes an answer is invisible without a byte-level pin |
| 2026-07-20 | Architecture map edges get backend-computed ports, barycenter ordering, arrowheads, and weight-scaled strokes; `MAP_SCHEMA_VERSION` 2; directory groups stay payload metadata | Within-layer order was arbitrary and direction was invisible in 2D while being parser truth; ordering stays deterministic (fixed sweeps, sorted ties); group containers wait for hierarchical layout |
| 2026-07-20 | Galaxy regions place by deterministic import-community constellations (pure-Python label propagation in `layout.py`); `community` is an additive Region field; layout bytes change once | Hash-order placement scattered coupled modules; communities are parser-truth-derived and deterministic; progress signatures hash file content so nothing re-dims (M12 precedent) |
| 2026-07-21 | **Bounded orbit** replaces the fixed camera, amending the free-flight Non-Goal: `controlType('orbit')` with panning disabled, per-level distance clamps, and clamped polar angle. The wheel becomes zoom; level changes move to click/Enter/Escape/breadcrumb | Approved by UD after a tester reported the galaxy unnavigable. Panning is the one degree of freedom that can strand a learner in empty space with nothing to navigate back by, so it stays off — rotation and zoom are clamped instead, which keeps "you cannot get lost" true. One gesture cannot mean both zoom and change-level, so the wheel's old meaning had to move |
| 2026-07-21 | Galaxy uses **progressive reveal**: floor (within 2 import hops of Home) ∪ neighbours of every lit region ∪ the current selection's neighbours, with a persisted Show-all toggle. An unrevealed region is drawn faint, unnamed, edgeless — never removed | Approved by UD. 169 systems and their whole route mesh was the hairball; dropping the *edges* of what is not yet charted thins the sky without a separate density control. Regions stay drawn and clickable because hiding one would misreport the project's size, which is precisely the kind of wrong a learner cannot detect. Reveal is recomputed from proven progress, never stored, so it cannot drift out of step with it |
| 2026-07-21 | `Region.hops_from_home` is graph-layer truth (schema 6): undirected BFS from Home over proven import routes, `None` when unreachable; `with_entrypoint` recomputes it | Reveal is game logic and belongs in `LearnerSession`, but the *distance* is a fact about the project and belongs in the graph. The frontend was already re-walking this exact BFS for the Easy-mode hint, so the two could in principle have disagreed about one number; there is now one source. `None` is never softened to a large number, or "unreachable" would read as "very far" |
| 2026-07-21 | Canvas name plates are ranked (Home → lit → centrality), budgeted by camera distance, and decluttered by claiming the full screen-cell rectangle each plate covers | A name is the cheapest differentiation there is and the sky had none. Claiming one cell per plate let a wide name cover three neighbours, and claiming only a row let two plates straddling a boundary collide — the rectangle is the only version that actually holds. Plate geometry is published on the sprite by the module that sizes it, so the constant is not duplicated across files |
| 2026-07-21 | Finding a module is a command palette **and** an index sidebar over one shared `moduleIndex`; sidebar rows show each path minus its group's shared prefix | Approved by UD. Progressive reveal makes targeted retrieval mandatory — a thinned sky must never hide a module from someone who knows its name — and both surfaces reach every module whether charted or not. Basenames alone are useless in a Python project where every package carries an `__init__.py`, so rows keep enough real path to be told apart |
| 2026-07-21 | Progressive reveal stays **galaxy-only**; the Map always draws every module | Approved by UD when the navigation work was extended to the Map. The Map's job is "how it all fits together", and a layered import diagram with holes in it teaches less than a complete one; the galaxy already offers the thinned view for learners who want it |
| 2026-07-21 | Architecture boxes are named by the tail of their file path (`short_label`, map schema 3); `label` keeps the full identifier for title and aria | A box is a fixed width, so its text always truncates on a real project — and truncating a dotted region id rendered `codemble.server.app` and `codemble.server.runtime` as the same glyphs. Identical text for different modules is worse than no label, and it is exactly the kind of wrong a learner cannot detect. The path tail also survives the `__init__.py` collision a basename alone cannot |
| 2026-07-21 | The Map gains zoom, Fit, and drag-to-pan; panning rides the container's own scroll and zoom only scales the rendered size | The 2D counterpart of bounded orbit: a 960x2640 diagram in a plain scroll box showed four of nine layers and no way to see the whole shape. Scroll-based panning keeps native scrollbars, keyboard scrolling and screen-reader behaviour intact, and because every coordinate inside the SVG stays backend-computed, React remains a pure renderer of graph-owned geometry. It opens at true size rather than auto-fitting: fitting on mount measured the scroller before layout settled and landed on a scale that was neither fitted nor honest |
| 2026-07-21 | v0.6.0 deepens five private boundaries without changing the HTTP, graph, check, persistence, or learner-visible contracts: Project Selection, Project Activation, Project Mapping Run, Name Atlas, and Learner Projection | Approved by UD as five behavior-preserving waves in one release PR. The deletion test now holds at each seam, stale activation and mapping responses lose atomically, and dependency-scoped learner projections measured ~0.331 ms → ~0.001 ms per hover commit on a synthetic 1,000-node project while preserving derived outputs |
| 2026-07-21 | v0.6.1 treats Modules and Find as global surfaces, sequences first-run decisions as audience → required Home → coach, and makes the 3D parser-owned layout explicitly non-draggable | Approved by UD as implementation of every verified user-flow audit finding. Global commands must never accept hidden state, onboarding must expose one foreground decision at a time, and learners orbit the immutable graph rather than editing its coordinates. The compact shell is a structural breakpoint of the existing Formal Edo interface, not a new visual system |
| 2026-07-21 | First-run audience modal portals to `document.body`; the persistent Easy/Expert toggle remains in responsive header chrome | A native modal inside the closed compact Menu entered the top layer but inherited `display:none` from its ancestor, leaving an invisible backdrop that blocked fresh mobile runs. Modal ownership is a document boundary, not header layout. Caught only by the clean public v0.6.1 installed-artifact smoke; PyPI immutability requires v0.6.2 rather than replacing 0.6.1 |
| 2026-07-21 | Easy guidance actions are derived from level, region, and layer, then executed by `LearnerSession`; the chip renders no button when the next step is already on screen | React must not guess a structure or own navigation truth, and an enabled action that commits the same state is a false promise. The nearest unlit region remains graph-derived; only the honest route to it changes with the learner's current context |
| 2026-07-21 | Map zoom/pan is renderer-local state keyed by tab and Home, preserved through transient data remounts but cleared with the project lifecycle; compact Maps start at 100% centred on the parser-backed target | Auto-fitting made 56 px boxes as little as 8–18 px tall and re-ran after check-driven map refreshes. Fit is still a valid explicit overview, while session state stays reserved for graph and learning truth |
| 2026-07-21 | Responsive disclosures and global surfaces own explicit focus handoffs; compact Menu closes on project exit and when crossing to the desktop rail | DOM focus and disclosure visibility are view concerns, but leaving focus on removed or hidden controls makes a successful navigation indistinguishable from a dead action to a keyboard or screen-reader user |
| 2026-07-21 | A wrong check submission returns no answer, no answer labels and no evidence; all three are returned only once the learner answers correctly | The response printed the parser answer on every miss and the same question then accepted it, so a region could light on an answer the app itself had just displayed — illumination stopped meaning understanding, the same failure class as the 2026-07-19 "every check needs a wrong option" fix. Evidence is withheld with the answer because an importer check cites exactly the files that *are* its answer |
| 2026-07-21 | The 2D Map gets a reading path: region focus offers **Read the source** beside the checks, Easy guidance recommends reading before proving, and Escape steps back a level there as it does in the Galaxy | Easy mode lands on the Map, where the only action was a quiz about code the layer could not show. The study panel is layer-neutral (`/api/node/:id/study`), so the Map only needed to select the module node the parser already produced — no new truth, and the audience that most needs to read first stops being sent to another layer to do it |
| 2026-07-21 | The audience answer is stored per learner as well as per project (`learner.json` beside progress); a fresh bind seeds from it and skips the gate, while the header toggle still overrides one project | The gate asks who the *learner* is, but the answer lived only under the project key, so every new project re-asked an expert whether they were new to coding. The file carries no `schema_version`, which is what keeps recents from reading it as a project |
| 2026-07-21 | Home calibration is a native modal sized to the viewport, grouped by the candidates' real top-level scope, with the candidate count stated and "Explore without Home" outside the scrolling list | It is the second step of the same required sequence as the audience gate and deserves the same shape. As a card capped to a share of the stage it showed one candidate of eleven with the escape hatch thousands of pixels below the fold, and a flat list put `tests/fixtures/...` beside the learner's entrypoint with nothing to tell them apart. Scope and rank are parser facts already in the payload; the leading group always opens so a project whose best candidate is rank 1 is never met by an all-collapsed list |
| 2026-07-21 | Galaxy name plates use the same path-tail rule as map schema 3's `short_label`; the shared module index and the command palette use it too, and the palette's unfiltered order is Home → lit → centrality | Basenames collide hard in a Python project — every package carries an `__init__.py` — so identical plates named different modules, which is precisely the wrong a learner cannot detect, and the palette opened on a screen of indistinguishable rows |
| 2026-07-22 | **Hue means import community.** Each parser-proven community takes one of eight traditional Japanese colour tokens (`--cm-com-0..7`) by `community id mod 8`; stars, planets and Architecture boxes all read the same arithmetic in `graphData.communityShade`. This amends the M2 encoding row: colour was "language", which is now the nebula/stripe channel only | Approved by UD. The sky had one hue for 109 systems, so nothing could be tracked without reading every plate — and the graph had proven communities since schema 5 that nothing rendered. Guardrails that keep the Correctness Contract intact: every token is lightness-tuned to `--cm-ink-2`'s luminance (0.389) so a lit star at 0.598 always wins, the kohaku band (~40°) is excluded so no community can read as "understood", a missing community id falls back to the old neutral ramp rather than borrowing a hue, and the mapping is pure arithmetic on graph truth so the same code always yields the same sky |
| 2026-07-22 | Routes get their own ink (`--cm-route`, 4.0:1) on both layers, and it sits deliberately BELOW `--cm-route-possible` (6.4:1) | Edges borrowed `--cm-hairline`, the ink of box borders and panel rules, measuring 1.57:1 on the canvas ground — the relationships the product exists to teach were its least visible marks, which is the literal complaint that opened the audit. Ordering the two inks this way keeps the 2026-07-19 rule that an unproven claim must be the more visible one |
| 2026-07-22 | Architecture-map modules with no import route from Home fold into a counted shelf behind an explicit control (auto-folded above 8), and Fit fits WIDTH when a whole-shape fit would land below 35% | On this repository 80 of 109 boxes are test fixtures and scripts, making the drawing 1:3.2 tall so the connected core fit at an unreadable 7%. Folding is view state, never truth: the note carries the exact count, **Show them** draws every one, and both surfaces still reach every module. Distinct from progressive reveal, which stays galaxy-only |
| 2026-07-22 | Easy guidance charges test-scoped paths a bounded +1.5-hop penalty; the displayed hop count stays the real one | A CLI's nearest neighbour is usually its own test suite, so pure hop-distance sent a brand-new learner from Home straight into `tests/`. The penalty is bounded so a non-test module one hop farther wins while a distant one does not, and an all-tests project is still guided. Both inputs stay parser truth (the BFS count and the recorded file path); only the ranking key is biased, never the reported fact |

## Non-Goals — do NOT build (point here when asked)

- ❌ ~~Free-flight 3D navigation~~ — superseded 2026-07-21: **bounded orbit** is
  approved (see Decision Log). The camera may rotate and zoom around the current
  subject; panning, free translation, and any control that can leave the subject
  off screen remain out
- ❌ XP, streaks, levels, leaderboards
- ❌ ~~A second 2D renderer/toggle in v1~~ — superseded 2026-07-19: the 2D Map layer is approved (see Decision Log); free-form/client-computed 2D layouts remain out
- ❌ Accounts, cloud hosting, multi-user; share link waits for Phase 3
- ❌ Extra quest types before Phase 3
- ❌ GitHub-URL ingestion in v1
- ❌ Elaborate game art before the loop teaches well — **still holds**: the
  2026-07-22 visual pass shipped only encodings that carry parser facts
  (community hue, class rings). Procedural planet surfaces, atmospheres and
  rotation ("almost real planets, like a game") remain OUT until Phase 1
  tester evidence lands, and would need their own Decision Log entry

## Gotchas

- **`base: "/Codemble"` is load-bearing and case-sensitive** — wrong case
  breaks every asset/link on GitHub Pages.
- **Starlight is 0.41.x, not 1.x** — `social` is an array of
  `{icon,label,href}`; logo uses `light`/`dark` keys. Don't scaffold against
  1.x docs.
- **`tokens.css` before `custom.css`** — custom.css resolves variables tokens
  defines; reversing the order silently unstyles the site.
- **Sidebar has no autogenerate** — a new docs page without a sidebar entry is
  invisible.
- **Docs CI uses `npm install` (not ci/pnpm), node 22** — match
  `pages.yml`/`ci.yml`; don't introduce a second package manager.
- **Determinism in scripts/layout:** galaxy layout must be seeded by content
  hash, never wall-clock or Math.random at render time — "same code → same sky"
  is an acceptance criterion.
- **The learner is the invariant:** when accuracy and delight conflict,
  accuracy wins. A wrong explanation is a top-severity bug, not a nitpick.
- **`web/src/tokens.css` imports the docs-site tokens across directories** —
  editing `docs-site/src/styles/tokens.css` restyles the app with no signal and
  no rebuild. `codemble/web_dist` is a committed build artifact, so a token
  change only reaches users after `cd web && npm run build` is re-run and the
  result committed.
- **Canvas colours must be plain values, never `color-mix()`** — WebGL receives
  a custom property's authored text, so a computed token renders black. Add new
  canvas tokens through `readPalette`, which resolves them.
- **`var()` never works in an SVG presentation attribute** — `fill="var(--x)"`
  is invalid and falls back to the cascade *silently*, which is how the map's
  language stripe rendered box-navy for a release while the legend advertised
  three colours. Use `style={{ fill: … }}` (a CSS property) for any
  token-driven SVG paint.

## Edge cases & limits

- >~1,000 supported source files → prompt to scope to a subdirectory (LOD arrives Phase 2)
- No clear entrypoint → ranked candidates; user picks Home
- Syntax errors / partial parses → parse what you can, flag the rest, never crash
- Missing/invalid key → galaxy + structure + checks work; explanations show "add your key"
- Unsupported-language files → outside the graph and never guessed
- No WebGL → clear requirements message (no 2D fallback in v1)

## Definition of done — Phase 0

A learner runs `codemble ./their-python-project`, flies (on rails) through an
accurate galaxy of their own code, zooms into Home, reads correct grounded
explanations and Python-idiom lessons, passes checks, watches stars light up
and their star chart grow — and comes away actually understanding the project.
Zero invented facts. Screenshot-worthy at every zoom level.

## Definition of done — Phase 1

A learner runs one command on a Python, JavaScript, TypeScript, or mixed project
and gets one deterministic parser-proven galaxy. They can focus a language
without changing graph truth or progress, study exact source with that
language's parser-anchored Lens, and keep uncertain or partial evidence visibly
honest. The tagged wheel includes the production app and installs without Node.
