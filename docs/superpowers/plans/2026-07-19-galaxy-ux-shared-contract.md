# Galaxy UX overhaul — shared interface contract

Binding for all three phase plans (A, B, C). Names here are exact and must not
be renamed by any task. Spec:
`docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md`.

## Repo conventions (all phases)

- Python: `pytest` and `ruff check .` are CI gates. Tests live in `tests/`.
- Frontend state tests: `web/scripts/check_learner_session.mjs` (plain node
  asserts, run by `npm run check` in `web/`). Graph-data tests:
  `web/scripts/check_graph_data.mjs`.
- Frontend verification: `cd web && npm run check` (runs both node check
  scripts, then `vite build` into `codemble/web_dist`).
- `codemble/web_dist` is a committed build artifact. Any task changing
  `web/src` must run `cd web && npm run build` and commit the resulting
  `codemble/web_dist` changes in the same commit.
- Canvas colours must be plain `rgb()` values resolvable by `readPalette`
  (`web/src/GalaxyCanvas.jsx`), never `color-mix()`.
- `web/src/tokens.css` holds app-only tokens. Never edit
  `docs-site/src/styles/tokens.css` for app work.
- Conventional Commits, DCO sign-off (`git commit -s`).

## Correctness Contract (never violate, any phase)

Structure, layouts, hints, tree shapes, and check answers come from the parser
or graph only. Uncertain relationships stay labelled "possible". Every
explanation cites a real `file:line`. The LLM narrates, never decides.

## Backend HTTP surface

Already shipped, wired in Phase A (do not re-implement):

- `GET /api/node/{node_id}/study` → `{node, source, neighbors, lens, structural}`
- `GET /api/node/{node_id}/explanation?mode=easy|expert`
- `GET /api/mode` → `{"mode": "easy"|"expert"}`
- `PUT /api/mode` body `{"mode": ...}` → `{"mode": ...}`
- `GET /api/llm/status` → `{configured_provider, configured_model, ollama}`

New endpoints by phase:

| Phase | Endpoint | Request | Response |
| --- | --- | --- | --- |
| A | `POST /api/picker/reset` | no body | `200 {"state": "unpicked"}`; idempotent (already-unbound also returns 200) |
| B | `GET /api/map` | none | `{"schema_version": 1, "architecture": {...}, "workflow": {...}}` (shape in Phase B plan) |
| C | `GET /api/picker/progress` | none | `{"state": "idle"\|"parsing"\|"ready"\|"error", "stage": str\|null, "files_done": int, "files_total": int, "error": str\|null}` |

Phase C also changes `POST /api/picker/select` to return `202 {"state": "parsing"}`
immediately instead of parsing inline.

## Frontend session contract (`web/src/learnerSession.js`)

State fields added, by phase. Field names are exact.

| Phase | Fields |
| --- | --- |
| A | `mode` (`"easy"`\|`"expert"`, default `"expert"`), `llmStatus` (object\|null), `explanation` (object\|null), `explanationLoading` (bool), `explanationError` (string\|null), `hoverNodeId` (string\|null) |
| B | `layer` (`"galaxy"`\|`"map"`), `mapTab` (`"architecture"`\|`"workflow"`), `mapData` (object\|null), `mapError` (string\|null), `coachmarksSeen` (bool) |
| C | `parseProgress` (object\|null) |

Derived in `deriveSnapshot` (never stored): Phase B adds `hint` (object\|null)
— the nearest unlit region to Home by route hops, ties broken by region id,
`null` in expert mode or when nothing is unlit.

Dispatch events added, by phase. Event names are exact.

| Phase | Events |
| --- | --- |
| A | `SET_MODE` (`{mode}`), `RESET_PROJECT`, `CHANGE_HOME`, `HOVER_NODE` (`{nodeId}`) |
| B | `SET_LAYER` (`{layer}`), `SET_MAP_TAB` (`{tab}`), `DISMISS_COACHMARKS` |
| C | none (progress polling is internal to `selectProject`) |

Adapter methods. Both `createHttpLearnerSessionAdapter` and
`createInMemoryLearnerSessionAdapter` must implement every method of every
phase that has landed. Method names are exact. The final parameter is the
repo's existing `options = {}` object carrying `signal` — **not** a bare
`AbortSignal` — matching all five methods already in the adapters
(CLAUDE.md: follow established patterns; mixing two calling conventions in one
adapter object is a footgun).

| Phase | Methods |
| --- | --- |
| A | `fetchExplanation(nodeId, mode, options)`, `fetchMode(options)`, `putMode(mode, options)`, `fetchLlmStatus(options)`, `resetProject(options)` |
| B | `fetchMap(options)` |
| C | `fetchParseProgress(options)`, `clearProgress(options)` |

### Contract extension recorded during planning (Phase C)

`DELETE /api/progress` → clears the **bound project's** saved progress only
(never a global wipe), with the `CLEAR_PROGRESS` session event and the
`clearProgress(options)` adapter method. Added for spec §7 gap G23
("reset progress" control); recorded here so the contract stays the single
source of truth.

Existing session invariants to preserve: one `AbortController` per async
concern, the `lifecycle` counter guarding stale responses, `commit()` clearing
checks on navigation unless `preserveChecks`, and `deriveSnapshot` re-resolving
region/node/level against the language-focused graph.

## Mode semantics (Phase A onwards)

`mode` never affects graph truth, coordinates, progress, or check scoring. It
selects narration voice, check prompt voice (`prompt_voices` already returned by
`checks/service.py`), label wording, and — from Phase B — default layer, edge
density, and whether the hint chip renders.
