# Galaxy UX overhaul — design spec

Date: 2026-07-19 · Approved by: UD (section-by-section, this session)
Status: approved design, pre-implementation

## 1. Problem

UD's complaints, restated: the galaxy has no textures or 3D depth; connections
are hard to see at every zoom level; the system view's layout does not explain
how things relate; there is no way back to the project picker; larger repos
need to load at all (a loading screen is acceptable); the app should offer two
easily switchable layers; understanding aids (architecture SVGs, a workflow
tree) are missing; and an Easy/Expert toggle should be built in.

Exploration confirmed two structural findings that reframe the work:

1. **The narration stack is shipped but inert.** `/api/node/{id}/explanation`,
   `/api/mode`, `/api/llm/status`, and the Tier 0 `structural` summary all
   exist server-side; the SPA never calls them. `<Explanation>` always renders
   `null` (`web/src/App.jsx:615`), and the fetched `neighbors` list is dropped.
2. **Project binding is one-shot by design.** After bind, every picker endpoint
   returns 409 (`codemble/server/app.py:60-73`); switching projects requires
   killing the process.

## 2. Decisions made in the interview (all UD-approved)

| # | Question | Decision |
| --- | --- | --- |
| 1 | "Two layers" meaning | 3D galaxy + 2D map, one switcher |
| 2 | Scale target | ~1,000 supported files end-to-end |
| 3 | Art direction | "Living cosmos" inside the Formal Edo palette |
| 4 | Easy mode scope | Plain language + less visual noise + guided next steps + lands on 2D map |
| 5 | 2D map content | Two tabs: Architecture map + Workflow tree |
| 6 | Ship order | Phase A dark features → Phase B look/map → Phase C scale |

Approach calls (also approved): stay inside the pinned `3d-force-graph` stack;
2D layouts computed in the graph layer (React draws SVG, decides nothing);
fix the system view with both a call-depth orbit layout and selection
highlighting; scale via a worker-thread parse with polled progress, no
multiprocessing yet.

## 3. Navigation & UX architecture

### Header (single control surface)

Brand · clickable breadcrumb (Galaxy → system → structure) · layer switcher
`Galaxy | Map` · language focus (existing) · Easy/Expert toggle · star chart ·
Switch project.

### Two layers, one game

- **Galaxy layer (3D):** existing rails, galaxy → system → study. Free flight
  stays banned.
- **Map layer (2D):** two tabs.
  - *Architecture:* modules as boxes grouped by directory, import flows
    layered top-down from Home. Certain imports solid; possible edges dashed —
    uncertainty stays visible in 2D exactly as in 3D.
  - *Workflow:* expandable call tree rooted at Home (who calls whom, depth by
    depth; possible calls flagged; cycles cut deterministically).
- Clicking a node in either layer opens the same study panel; illumination
  (amber) renders identically in both. Layer choice is UI state, never truth.
- Easy mode lands on Map; Expert lands on Galaxy (active once Map ships in
  Phase B). Both can switch anytime.
- The Map layer works without WebGL (bonus fallback, not a v1 promise).

### Project switching

Header button → confirm ("Progress is saved per project") →
`POST /api/picker/reset` → picker screen. Jail (`$HOME`) and Host-header
allowlist unchanged. Reset during parse cancels the parse.

### Home (entrypoint)

- "Change Home" affordance reopens the entrypoint picker at any time
  (today it can never be reopened after first dismissal).
- Selected Home persists in the progress store and is restored on rebind
  (today it silently resets on restart).
- The zero-candidate branch stops telling users to restart with a CLI flag;
  ranked candidates and "explore without Home" remain available in-app.

### Easy / Expert (persisted via shipped `GET/PUT /api/mode`)

| Aspect | Easy | Expert |
| --- | --- | --- |
| Labels/tooltips | Plain language ("files this talks to") | Full terms (import/call edges, centrality, LOC) |
| Edges shown (3D) | Selection's connections only; peripheral nodes fade | All edges |
| Guidance | Hint chip: "Study `X` next" + celebration on light-up | None |
| Default layer | Map | Galaxy |
| Narration voice | `easy` | `expert` |

The hint is deterministic graph truth only: the nearest unlit region to Home by
route hops (ties broken by region id). Mode never affects graph truth,
progress, checks scoring, or coordinates.

### Study panel (finally lit)

Order within the panel:

1. **Structural summary** — Tier 0 dual-voice text (shipped, currently
   dropped); renders instantly, no key needed, voice follows mode.
2. **Narration** — `GET /api/node/{id}/explanation?mode=` when a provider is
   configured; loading/error states per existing panel patterns.
3. **Connections** — new section: callers / callees / imports as clickable
   rows (jump to that node's study), each with direction, certainty, and
   `file:line` citation, plus a mini SVG strip (callers → this → callees).
   The strip is presentation of the already-computed neighbor list (like the
   star chart's bars), not layout logic.
4. **Source excerpt + lens notes** — unchanged.
5. **No-key state** — panel explains BYO key and offers Ollama, driven by
   `GET /api/llm/status`. Partial-parse notice renders with the explanation
   block (it previously rode on the never-fetched response).

### Checks

Correct answers get a brief affirmative acknowledgment (today only wrong
answers produce feedback). Region-complete celebration unchanged.

## 4. Visual design — the living cosmos

Locked meaning rules kept: size = code volume, brightness = importance
(centrality), **amber = understood and nothing unlit may outshine it**, ruri =
interaction, dashed = possible/uncertain.

### Materials

- **Halo sprites:** every node keeps its pickable sphere and gains a soft
  radial glow sprite. Textures are canvas-generated at runtime — no image
  assets, deterministic.
- **Bloom:** UnrealBloom via `postProcessingComposer()`; threshold tuned so
  lit-amber stars bloom hard and the unlit ramp barely does.
- **Nebulae (language = tint):** each star system gets a faint billboard-fog
  tinted by language. This restores the promised color=language channel on a
  separate visual channel from node brightness.
- **Starfield:** background `THREE.Points` dust seeded by the project content
  hash — same code → same sky, literally.
- **Keyboard reticle:** the arrow-key-focused node shows a visible ring
  (reuses the ruri orbit token; interaction job unchanged).

### Edges

Slight curvature; arrows at system level; drifting directional particles on
**certain** call edges only. Possible calls stay dashed, particle-free.
Hover/select → that node's edges brighten ruri, neighbors hold full opacity,
rest fades. Study level keeps the selected node's connections visible instead
of dimming the entire scene to 0.16.

### New app-side tokens (`web/src/tokens.css`, plain `rgb()` for `readPalette`)

| Token | Meaning | Starting value (tune in impl., WCAG-checked where used as UI) |
| --- | --- | --- |
| `--cm-neb-python` | Python nebula tint | rokushō verdigris ≈ `rgb(72 116 98)` |
| `--cm-neb-js` | JavaScript nebula tint | fuji wisteria ≈ `rgb(138 124 168)` |
| `--cm-neb-ts` | TypeScript nebula tint | asagi indigo-teal ≈ `rgb(78 126 155)` |
| `--cm-star-halo` | halo sprite base | warm gofun white ≈ `rgb(242 239 233)` |

Fog alpha lives in material parameters, not tokens. docs-site tokens untouched.
Legend swatches for tints must pass the 4.5:1 floor against the ground.

### Signature moment

Passing a region's checks triggers the **nebula dawn**: amber light washes
across that system's fog and the star flares and blooms (~1.2 s).
`prefers-reduced-motion` gets the finished lit state instantly. This is the one
bold moment; everything else stays quiet.

### Legend & onboarding

- Legend becomes complete: size, brightness, amber, language tint, dashed
  uncertainty — plain-worded in Easy mode.
- First-run coach-marks (3 short steps: what you see → how to move → what
  lights stars), dismissible, never shown again (localStorage flag; UI
  preference, not progress).

### Performance guardrails

Halos/fog are billboards; bloom at capped resolution; existing
node-resolution drop above 900 nodes retained; target interactive framerate at
1k nodes on a mid-range laptop, verified via the existing `?benchmark` path.

## 5. Backend changes

### Endpoints

| Endpoint | Change |
| --- | --- |
| `POST /api/picker/reset` | **New.** Unbinds project, cancels active parse, re-arms picker. Idempotent; 200 `{"state":"unpicked"}`. |
| `POST /api/picker/select` | Returns `{"state":"parsing"}` immediately; parse runs in a worker thread. (Ships in Phase C together with the frontend change.) |
| `GET /api/picker/progress` | **New.** `{state: idle|parsing|ready|error, stage, files_done, files_total, error?}`. Stages: discovering → parsing → resolving → checks → layout. |
| `GET /api/map` | **New.** Deterministic 2D layouts, own `schema_version: 1`: `architecture` (directory groups, layer index per region via longest-path from Home over the import DAG, edges with `certain`) and `workflow` (call tree from selected entrypoint, `certain` flags, deterministic cycle cuts). |
| `POST /api/entrypoint` | Also persists the selection to the progress store; restored on rebind. |

`codemble <path>` CLI keeps its blocking parse but prints the same staged
progress to the terminal.

### Scale fixes (measured cliffs)

- **Check generation:** build one per-region edge index (O(E)) at bind;
  replaces the per-region full-edge scans (O(regions × edges)). Same answers,
  proven by existing check tests.
- **Graph response cache:** `GET /api/graph` result cached until progress,
  entrypoint, or binding changes (today it re-hydrates and re-sorts per
  request).
- **Scale cap:** subdirectory prompt moves 300 → 1,000. Above cap, picker
  suggestions become clickable and a type-a-path field is added (still
  home-jailed).

### Layout change

`layout_graph` re-orbits system nodes by call depth from the system's entry
node: orbit 1 = called directly, orbit 2 = called by those, etc.; nodes
unreachable from the entry take the outermost orbit, ordered by node id. Still
hash-seeded; no RNG, no clock. Layout bytes change once; determinism tests
re-pin. Galaxy-level spiral unchanged.

## 6. Frontend architecture

`LearnerSession` gains state: `layer` (galaxy|map), `mapTab`
(architecture|workflow), `mode` (easy|expert, synced with `/api/mode`),
`llmStatus`, `explanation` (+ loading/error), `mapData`, `parseProgress`,
`hint`, `coachmarksSeen`. New events: `SET_LAYER`, `SET_MAP_TAB`, `SET_MODE`,
`LOAD_EXPLANATION`, `RESET_PROJECT`, `CHANGE_HOME`. New HTTP-adapter methods:
`fetchExplanation`, `fetchMode`/`putMode`, `fetchLlmStatus`, `fetchMap`,
`resetProject`, `fetchParseProgress`. Async paths follow the existing
AbortController-per-concern pattern.

New components: `LayerSwitcher`, `ModeToggle` (both modeled on
`LanguageFocus`), `MapView` (`ArchitectureMap`, `WorkflowTree` — pure SVG from
`/api/map`), `ConnectionsList` + `MiniConstellation`, `HintChip`,
`LoadingScreen` (staged progress), `CoachMarks`, error boundary in `main.jsx`,
`<noscript>` in `index.html`. `GalaxyCanvas` gains: bloom composer, halo
sprites, nebula groups, starfield, focus reticle, hover/select highlight via
link/node accessor functions.

React renders session truth; no layout or game logic client-side. The Map
SVGs draw backend-computed coordinates/layers only.

## 7. UX gap register (from the code audit) and phase mapping

| Gap | Severity | Resolution | Phase |
| --- | --- | --- | --- |
| G1 No parse progress; server blocks during picker parse | major | Worker thread + progress endpoint + loading screen | C |
| G2 Web scale prompt is a dead-end sentence | major | Clickable suggestions | C |
| G3 Picker jailed to `$HOME`, no path entry | major | Path field (jail stays; deliberate security posture) | C |
| G4 Non-TTY CLI scale error is bare | minor | Print suggestions in message | C |
| G5 Legend omits size/brightness/color | major | Complete legend | A |
| G6 No onboarding/controls discovery | major | Coach-marks | B |
| G7 Keyboard focus invisible in scene | major | Focus reticle | B |
| G8 Breadcrumb not clickable | minor | Clickable breadcrumb | B |
| G9 Cannot switch project without restart | blocker | `/api/picker/reset` + header button | A |
| G10 Home not re-pickable | major | "Change Home" affordance | A |
| G11 No history/deep links | minor | Deliberate (rails); reload lands at galaxy | keep |
| G12 Explanation endpoint never called; panel dead | blocker | Wire explanation + structural | A |
| G13 Neighbors fetched, never shown | major | Connections section | A |
| G14 No arrows/hover/highlight on edges | major | Arrows + tooltips + highlight (A); particles (B) | A/B |
| G15 Cross-system edges invisible in system view | minor | Connections list covers; ghost edges considered in B | A |
| G16 No key/Ollama guidance | major | `/api/llm/status`-driven panel state | A |
| G17 Zero-check regions can never light | by design | Locked decision (no evidence → no light); copy polish | A (copy) |
| G18 No noscript/error boundary | minor | Add both | A |
| G19 Partial-parse notice rides dead code path | minor | Renders with explanation block | A |
| G20 Zero-candidate entrypoint says "restart with flag" | minor | In-app Change Home + copy | A |
| G21 "Studied" resets on reload | by design | Locked (session-local); label "this session" | A (copy) |
| G22 Entrypoint selection not persisted | major | Persist in progress store | A |
| G23 No reset-progress control | minor | Add control | C |
| G24 No in-app quit; server runs until Ctrl-C | minor | Out of scope (normal for local tools) | keep |
| G25 Errors say "restart Codemble" | minor | In-app retry | A |
| G26 Easy/Expert unreachable | minor | Mode toggle | A |
| G27 Correct answers give no feedback | minor | Affirmation | A |

## 8. Phases

**Phase A — light the dark.** Explanation + structural + Connections +
mode toggle + llm-status guidance; switch project (reset endpoint); Change
Home + persisted entrypoint; edge arrows, link tooltips, hover/select
highlighting; complete legend; check affirmation; retry states; error
boundary + noscript; copy fixes (G17/G20/G21). *Acceptance:* a learner can
read a grounded explanation and the connections of any structure, flip
Easy/Expert, switch projects, and re-pick Home — all without touching the
terminal; every wired endpoint degrades gracefully with no key.

**Phase B — the look and the map.** Bloom, halos, nebulae, starfield, focus
dimming + reticle, call-depth orbits, nebula dawn, 2D Map layer (both tabs),
layer switcher, Easy default-to-Map + hint chip, coach-marks, clickable
breadcrumb. *Acceptance:* same code → identical sky (hash-seeded visuals);
interactive framerate at 1k nodes via `?benchmark`; possible-call visibility
preserved in both layers; reduced-motion honored; screenshot-worthy at every
zoom level.

**Phase C — scale.** Threaded parse + progress endpoint + staged loading
screen; clickable scale suggestions + path field; cap → 1,000; check index;
graph cache; CLI progress lines; reset-progress control. *Acceptance:* a
~1,000-file project parses with live progress and reaches an interactive
galaxy; re-fetching the graph does not re-sort the world; scale prompt is
actionable entirely in-app.

Each phase is a shippable release: docs page updates + sidebar + CHANGELOG in
the same PR (repo rule), README/screenshots refreshed when the look changes.

## 9. Deliberately unchanged

- Zero-check regions stay dim with an explanation (locked correctness
  decision; lighting them would fake understanding).
- "Studied" remains session-local (locked decision); the star chart labels it
  "this session".
- No free flight, no XP/streaks/levels (hint chip + celebration are guidance,
  not meta-progression).
- LLM never decides: hints, layouts, SVG structure, and check answers are
  parser/graph truth only. Correctness Contract untouched.

## 10. Error handling

- Parse thread crash → picker error state with in-app retry (no restart).
- Progress polling failure → retry with backoff; loading screen shows the
  error honestly.
- Reset during parse → cancellation flag checked between files; state returns
  to `unpicked`.
- Explanation/provider errors → panel-scoped error with retry; structural
  summary always remains.
- Map fetch failure → Map layer shows retry; Galaxy layer unaffected.
- WebGL absent → existing message; Map layer still works.

## 11. Testing

- **Backend units:** reset/rebind lifecycle; progress state machine; per-region
  check index equivalence (same suites/answers as today); map layout
  determinism (same input → same bytes) incl. cycle cuts and possible-call
  flags; orbit layout re-pin; entrypoint persistence; graph-cache
  invalidation on light-up/entrypoint/reset.
- **Frontend state tests:** extend `scripts/check_learner_session.mjs` (reset
  flow, mode sync, layer/tab switching, explanation loading, progress
  polling) through the in-memory adapter.
- **Visual/manual:** run the app on this repo + a mixed fixture; verify
  encodings, dawn moment, reduced motion, 320 px width, keyboard-only pass;
  `?benchmark` at 1k nodes.
- Parser/graph/checks/persistence logic never lands without unit tests
  (repo rule); UI is verified by running it.

## 12. Decision Log entries (appended to CLAUDE.md with this spec)

1. 2D Map layer (architecture + workflow tabs) approved — supersedes the
   "no second 2D renderer in v1" Non-Goal; layouts computed in the graph
   layer, React stays a pure renderer.
2. Scale target raised to ~1,000 files with staged parse progress — a
   deliberate partial pull-forward of Phase 2 scale work; full LOD/clustering
   remains Phase 2.
3. One-shot binding relaxed to explicit in-app reset (`/api/picker/reset`);
   jail and Host allowlist unchanged.
4. "Living cosmos" art direction inside the Formal Edo palette; language
   gains a nebula-tint channel; amber's monopoly on understanding preserved.
5. System-view orbits re-layout by call depth (deterministic); layout bytes
   change once.
6. Easy/Expert UI toggle ships riding the existing audience-mode backend;
   Easy adds deterministic guidance only.
