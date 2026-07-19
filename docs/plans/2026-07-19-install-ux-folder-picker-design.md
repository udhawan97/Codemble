# Design: One-command install + in-app project picker

Date: 2026-07-19 · Status: approved by UD (this session) · Owner: UD

## Problem

Installing and starting Codemble asks a learner for three things at once: a
pipx/uvx install from a long git URL with a version tag, a terminal, and a
correctly typed project path. The target user (early/intermediate coder) trips
on all three. Goal: `uvx codemble` (or `pipx install codemble`, then bare
`codemble`) opens the browser and lets them **pick the project folder in the
UI**.

## Decisions (all approved)

1. **Publish to PyPI** — install becomes `uvx codemble` / `pipx install
   codemble`. No bootstrap script.
2. **In-app picker page** — the local server lists directories through a small
   API; no native OS dialog, no tkinter dependency.
3. **One project per run** — the picker appears once; after binding, the server
   behaves exactly as today. Re-run the CLI to inspect another project.
4. **Recents shown** — the picker lists previously explored projects read from
   the existing `~/.codemble/progress/*.json` files.
5. **One server, two phases** — a single process/port whose app starts
   "unpicked" and binds a graph exactly once. No throwaway pre-server, no
   restart the browser must survive.

## CLI

- Bare `codemble` (zero args) → serve in picker mode: start server with no
  project, open browser to the Welcome/picker screen.
- Unchanged: `codemble ./path`, `codemble --path ./scope`, `codemble parse`,
  `--entrypoint`, `--version`, `--host/--port/--no-open` (the flags also apply
  to picker mode). The terminal scale-cap prompt remains for the explicit-path
  flow.

## Server / API

`codemble/server/app.py`: `create_app` supports an unpicked state (no graph
yet). New endpoints, namespaced under `/api/picker/`:

| Endpoint | Behaviour |
| --- | --- |
| `GET /api/picker/state` | `{"state": "unpicked"}` or `{"state": "ready"}` — SPA decides which screen to render on load |
| `GET /api/picker/browse?path=…` | Child **directories** of `path` (default: user home), names only — no per-entry file counts (the scale-cap 409 already carries the counts that matter, and recursive counting per child is slow on `node_modules`-sized trees). Never lists files' contents; rejects paths outside the user's home directory. |
| `GET /api/picker/recents` | Scan the progress dir; return `{project_root, understood_count}` for stored projects whose paths still exist. |
| `POST /api/picker/select {path}` | Run `ProjectParser.intake` + parse. Success: bind graph + `CheckService` + `StudyService` once, return ready state. `ProjectScaleError`: structured **409** with file count, cap, and top-scope suggestions. Parse error: structured **422** with the message. After binding: **409 already-bound**. |

- Existing `/api/*` endpoints return a clear 409 "no project selected yet"
  while unpicked (never crash).
- Binding is one-shot; the bound path reuses the exact `serve_project` parse
  semantics (entrypoint handling included).

### Safety

- Server keeps binding `127.0.0.1`.
- Add a Host-header allowlist (`127.0.0.1`, `localhost`) so DNS-rebinding pages
  cannot drive the picker API.
- `browse` refuses paths outside the user's home directory and normalises
  `..`/symlink escapes before listing. Projects outside home (external drives
  etc.) use the existing escape hatch: pass the path on the CLI
  (`codemble /Volumes/...`).

## Frontend

- `web/src/learnerSession.js` gains a **pre-graph phase**: on load it queries
  `/api/picker/state`; `unpicked` → picker screen, `ready` → today's flow
  untouched. All picker logic (fetches, selection, error states, scale-cap
  re-scoping) lives in the session layer; React stays a pure renderer.
- Picker screen (Formal Edo styling; ruri = interaction, kohaku only for the
  recents' lit counts): recents list on top ("Continue — *path*, N systems
  lit"), folder browser below (breadcrumb, directory list, "Map this folder"
  action).
- Scale-cap 409 re-renders the same folder browser scoped inside the chosen
  root, showing the top-scope counts from the payload.
- Successful select transitions into the normal graph-loading path with no
  page reload.

## Release (PyPI)

- One-time: verify/claim the `codemble` name on PyPI.
- Add a manual `uv publish` (or twine) step to the release checklist, run from
  the tagged commit with the same evidence bar as v0.2.0. No auto-publish CI
  in this change.

## Docs

- README quick start collapses to: `uvx codemble` → browser opens → pick your
  folder. Keep the git+tag command as a fallback until the first PyPI release
  exists.
- Update docs-site install + getting-started pages (plus sidebar if any new
  page), CHANGELOG entry.
- Rebuild and commit `codemble/web_dist` (committed build artifact — known
  gotcha).
- Decision Log entries: picker architecture + PyPI publish.

## Testing

- **Server unit tests:** browse containment (home-dir jail, `..`/symlink
  escape), recents scanning under a fake `CODEMBLE_DATA_DIR`, select happy
  path, scale-cap 409 payload, one-shot 409, unpicked-state 409s on existing
  endpoints, Host-header rejection.
- **CLI unit tests:** zero-arg routing into picker mode; explicit-path flows
  unchanged.
- **Frontend:** `learnerSession` picker-phase transitions through the existing
  in-memory adapter.
- **Manual:** run bare `codemble` end-to-end on a fixture; verify picker →
  galaxy → checks → illumination.

## Out of scope

No in-session project switching; no new persistence (recents derive from
existing progress files); no changes to parsing, graph bytes, checks,
determinism, or the Correctness Contract. Non-Goals remain non-goals.
