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

1. **LanguageAdapter seam:** every language implements `parse(path) -> Graph`
   and `concepts(node) -> [ConceptAnnotation]`. Python first via stdlib `ast`;
   all later languages via tree-sitter. Nothing above the seam hardcodes a
   language.
2. **The graph is render-ready:** graph layer computes language, LOC,
   centrality, entrypoint rank, region id, understood-state. The renderer is a
   pure consumer — **no layout or game logic in the frontend.** This keeps the
   Phase-3 share-link viewer and any future renderer cheap.
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
  is the value source of truth and **must load before** `custom.css`. Two
  accents, one job each: star-gold = understanding/progress, orbit-cyan =
  interaction. WCAG 4.5:1 floor on both grounds.
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

**NOW — Phase 1 TS/JS delivery.** Build the tree-sitter JavaScript/TypeScript
adapter, parser-anchored language lens, and polyglot language focus in M7–M10.
The v0.1.0 Python learner-acceptance issue stays open in parallel; promotion
does not retroactively claim those external runs passed.

**NEXT — Phase 2 (months ~3–6).** Go/Rust/Java adapters, LOD culling +
clustering for larger repos.

**LATER — Phase 3 (months ~7–9).** Shareable read-only galaxy link (the only
cloud touch). Extra quest types: trace-a-request, fix-the-failing-test.
Polish, then the coordinated launch (Show HN / X; lit-galaxy GIF as hero).

## Current State **[AGENT-MAINTAINED]**

**Current milestone: M9 JavaScript/TypeScript Lens** · Last updated: 2026-07-18
· Session note: M8 merged after all parser/API/package gates. M9 adds explicit
annotation language tags, tree-sitter-owned JS/TS concepts, and deterministic
Lens notes while keeping broken-module claims off.

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
- [ ] Add an accessible language focus control for mixed galaxies without
      changing graph truth, deterministic coordinates, or progress
- [ ] Verify focus behavior at galaxy/system/study levels and at 320 px
- [ ] Update README, public docs, packaged SPA, changelog, and release evidence
- [ ] Publish and verify the Phase 1 tester release from the exact `main` tag

**Acceptance:** Python-only behavior remains intact; a mixed fixture can focus
Python, JavaScript, or TypeScript without hiding uncertainty; source install,
wheel install, web build, docs build, and downloaded release asset all pass.

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

## Non-Goals — do NOT build (point here when asked)

- ❌ Free-flight 3D navigation — semantic zoom only
- ❌ XP, streaks, levels, leaderboards
- ❌ A second 2D renderer/toggle in v1 (render-ready graph keeps one possible later)
- ❌ Accounts, cloud hosting, multi-user; share link waits for Phase 3
- ❌ Local models (Ollama)
- ❌ Extra quest types before Phase 3
- ❌ GitHub-URL ingestion in v1
- ❌ Elaborate game art before the loop teaches well

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

## Edge cases & limits

- >~300 files → prompt to scope to a subdirectory (LOD arrives Phase 2)
- No clear entrypoint → ranked candidates; user picks Home
- Syntax errors / partial parses → parse what you can, flag the rest, never crash
- Missing/invalid key → galaxy + structure + checks work; explanations show "add your key"
- Unsupported-language files → visible, tagged, no lens, no guessing
- No WebGL → clear requirements message (no 2D fallback in v1)

## Definition of done — Phase 0

A learner runs `codemble ./their-python-project`, flies (on rails) through an
accurate galaxy of their own code, zooms into Home, reads correct grounded
explanations and Python-idiom lessons, passes checks, watches stars light up
and their star chart grow — and comes away actually understanding the project.
Zero invented facts. Screenshot-worthy at every zoom level.
