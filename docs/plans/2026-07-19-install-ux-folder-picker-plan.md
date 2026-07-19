# One-command install + in-app project picker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bare `codemble` starts the local server with no project, opens the browser, and lets the learner pick the project folder (recents + folder browser) in the UI; install collapses to `uvx codemble` once published to PyPI.

**Architecture:** One server, two phases — `create_app` gains an "unpicked" state whose picker endpoints (`/api/picker/*`) bind a parsed project exactly once; after binding, the app behaves exactly as today. The frontend `learnerSession` gains a pre-graph "picking" phase; React stays a pure renderer. Spec: `docs/plans/2026-07-19-install-ux-folder-picker-design.md`.

**Tech Stack:** Python 3.11 + FastAPI (Starlette `TrustedHostMiddleware`), Vite + React, no new dependencies.

## Global Constraints

- Python 3.11+, FastAPI, Vite + React, `3d-force-graph` — pinned stack; add **no** new dependencies.
- Correctness Contract untouched: no parser, graph-bytes, checks, or determinism changes.
- One project per server run: binding is one-shot; after binding, picker mutation endpoints return 409.
- Browse/select are jailed to the user's home directory; projects elsewhere use `codemble /path` (documented escape hatch).
- Accent jobs: kohaku amber (`--cm-star`) = understanding only, ruri lapis (`--cm-orbit`) = interaction; kohaku never marks navigation.
- `codemble/web_dist` is a committed build artifact — Vite builds into it directly (`web/vite.config.js` `outDir`); rebuild + commit in the same PR as any `web/src` change.
- CI gates: `pytest`, `ruff check .`, `cd web && npm run check`.
- Commits: Conventional Commits + DCO style used by this repo.

---

### Task 1: `ProjectIntake.scope_counts()` — shared top-scope computation

The CLI's scale-cap prompt and the new picker 409 payload both need "supported files per top-level directory, busiest first". Move it onto `ProjectIntake` and make the CLI reuse it.

**Files:**
- Modify: `codemble/adapters/project.py` (add method to `ProjectIntake`, ~line 45)
- Modify: `codemble/cli.py:120-130` (reuse it in `choose_project_scope`)
- Test: `tests/test_project_parser.py`

**Interfaces:**
- Produces: `ProjectIntake.scope_counts() -> tuple[tuple[str, int], ...]` — `(directory_name, file_count)` pairs, busiest first, name-ascending tiebreak; files directly in the root count under `"."`. Task 6 consumes it for the scale 409 payload.

- [ ] **Step 1: Write the failing test** (append to `tests/test_project_parser.py`)

```python
def test_intake_scope_counts_orders_busiest_directories_first(tmp_path: Path) -> None:
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "one.py").write_text("A = 1\n", encoding="utf-8")
    (tmp_path / "api" / "two.py").write_text("B = 2\n", encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "app.py").write_text("C = 3\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("D = 4\n", encoding="utf-8")

    intake = ProjectParser().intake(tmp_path)

    assert intake.scope_counts() == (("api", 2), (".", 1), ("web", 1))
```

(If `tests/test_project_parser.py` does not already import `ProjectParser` and `Path`, add those imports to match the file's existing import block.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_parser.py::test_intake_scope_counts_orders_busiest_directories_first -v`
Expected: FAIL with `AttributeError: 'ProjectIntake' object has no attribute 'scope_counts'`

- [ ] **Step 3: Implement** — add to `ProjectIntake` in `codemble/adapters/project.py` (after `_files_for`):

```python
    def scope_counts(self) -> tuple[tuple[str, int], ...]:
        """Count supported files per top-level directory, busiest first."""

        counts: dict[str, int] = {}
        for file in self.files:
            relative = file.relative_to(self.root)
            directory = relative.parts[0] if len(relative.parts) > 1 else "."
            counts[directory] = counts.get(directory, 0) + 1
        return tuple(
            sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        )
```

- [ ] **Step 4: Reuse in the CLI** — in `codemble/cli.py`, replace the counting block inside `choose_project_scope` (the `counts: dict[str, int] = {}` loop and `suggestions = ...` expression) with:

```python
    suggestions = ", ".join(
        f"{directory} ({count})" for directory, count in intake.scope_counts()[:6]
    )
```

- [ ] **Step 5: Run the full suite and lint**

Run: `pytest && ruff check .`
Expected: all PASS (the existing `test_large_project_requires_an_explicit_or_interactive_scope` proves the CLI prompt still shows the same suggestions).

- [ ] **Step 6: Commit**

```bash
git add codemble/adapters/project.py codemble/cli.py tests/test_project_parser.py
git commit -m "refactor: share top-scope counts on ProjectIntake"
```

---

### Task 2: `list_recent_projects()` in the progress store

**Files:**
- Modify: `codemble/progress/store.py` (module function at the end, before `__all__`)
- Modify: `codemble/progress/__init__.py` (export it)
- Test: `tests/test_progress.py` (create)

**Interfaces:**
- Consumes: the existing progress file format written by `ProgressStore._write` — `{"schema_version": 1, "project_root": str, "regions": {region_id: {"signature": str}}}` in `$CODEMBLE_DATA_DIR/progress/*.json` (default `~/.codemble/progress/`).
- Produces: `list_recent_projects(limit: int = 8) -> list[dict[str, object]]` — dicts `{"project_root": str, "understood_count": int}`, newest file first, entries whose `project_root` no longer exists (or whose JSON is invalid) skipped. Task 5 consumes it.

- [ ] **Step 1: Write the failing test** (create `tests/test_progress.py`)

```python
"""Recents derived from the local progress directory."""

import json
import os
from pathlib import Path

from codemble.progress import list_recent_projects


def _write_progress(root: Path, name: str, payload: object, mtime: float) -> None:
    path = root / "progress" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_recents_lists_existing_projects_newest_first(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    older = tmp_path / "older-project"
    newer = tmp_path / "newer-project"
    older.mkdir()
    newer.mkdir()
    _write_progress(
        tmp_path / "data",
        "aaa",
        {
            "schema_version": 1,
            "project_root": str(older),
            "regions": {"pkg": {"signature": "s1"}},
        },
        mtime=1_000.0,
    )
    _write_progress(
        tmp_path / "data",
        "bbb",
        {
            "schema_version": 1,
            "project_root": str(newer),
            "regions": {"a": {"signature": "s2"}, "b": {"signature": "s3"}},
        },
        mtime=2_000.0,
    )
    _write_progress(
        tmp_path / "data",
        "ccc",
        {
            "schema_version": 1,
            "project_root": str(tmp_path / "deleted-project"),
            "regions": {},
        },
        mtime=3_000.0,
    )
    (tmp_path / "data" / "progress" / "junk.json").write_text(
        "not json", encoding="utf-8"
    )

    recents = list_recent_projects()

    assert recents == [
        {"project_root": str(newer), "understood_count": 2},
        {"project_root": str(older), "understood_count": 1},
    ]


def test_recents_survive_a_missing_progress_directory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "never-written"))

    assert list_recent_projects() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_progress.py -v`
Expected: FAIL with `ImportError: cannot import name 'list_recent_projects'`

- [ ] **Step 3: Implement** — append to `codemble/progress/store.py` (before `__all__`):

```python
def list_recent_projects(limit: int = 8) -> list[dict[str, object]]:
    """Return recently explored projects whose paths still exist, newest first."""

    data_root = os.environ.get("CODEMBLE_DATA_DIR")
    progress_root = (
        (Path(data_root).expanduser() if data_root else Path.home() / ".codemble")
        / "progress"
    )
    entries: list[tuple[float, dict[str, object]]] = []
    try:
        candidates = sorted(progress_root.glob("*.json"))
    except OSError:
        return []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            modified = path.stat().st_mtime
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            continue
        project_root = payload.get("project_root")
        regions = payload.get("regions")
        if not isinstance(project_root, str) or not isinstance(regions, dict):
            continue
        if not Path(project_root).is_dir():
            continue
        entries.append(
            (modified, {"project_root": project_root, "understood_count": len(regions)})
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries[:limit]]
```

Update `__all__` in `store.py` to `["ProgressStore", "UnknownRegionError", "list_recent_projects"]`, and `codemble/progress/__init__.py` to:

```python
"""Local persistence: illumination state + concept star chart (~/.codemble/)."""

from codemble.progress.store import (
    ProgressStore,
    UnknownRegionError,
    list_recent_projects,
)

__all__ = ["ProgressStore", "UnknownRegionError", "list_recent_projects"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_progress.py -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/progress/store.py codemble/progress/__init__.py tests/test_progress.py
git commit -m "feat: list recently explored projects from local progress"
```

---

### Task 3: Server unpicked state — optional graph, `/api/picker/state`, 409 guards

**Files:**
- Modify: `codemble/server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces (used by tasks 4–8):
  - `PickerConfig(browse_root: Path, entrypoint: str | None = None)` — frozen dataclass exported from `codemble.server.app`.
  - `create_app(graph: Graph | None = None, web_dist=None, study_service=None, check_service=None, *, picker: PickerConfig | None = None) -> FastAPI`. Raises `ValueError` if both `graph` and `picker` are `None`. Existing positional calls (`create_app(graph, web_dist, studies)`) keep working.
  - `GET /api/picker/state` → `{"state": "unpicked"}` or `{"state": "ready"}` (always registered).
  - Internal `_ProjectState` with `.bound`, `.checks`, `.studies`, `.bind(graph)`; every project endpoint guards through `_services()` → HTTP 409 `"No project selected yet."` while unbound.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_server.py`)

```python
def test_unpicked_app_reports_state_and_guards_project_api(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.get("/api/picker/state").json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/regions/pkg/checks").status_code == 409
    assert client.get("/api/node/pkg.x/study").status_code == 409
    assert client.post("/api/entrypoint", json={"node_id": "x"}).status_code == 409


def test_bound_app_reports_ready_picker_state(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/picker/state").json() == {"state": "ready"}
    assert client.get("/api/graph").status_code == 200


def test_create_app_requires_a_graph_or_picker(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        create_app(web_dist=tmp_path / "missing")
```

(Match the file's existing import style — `pytest` is imported at top of file if already there.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py -k "picker or requires_a_graph" -v`
Expected: FAIL with `ImportError` / `TypeError` (no `PickerConfig`, `graph` not optional)

- [ ] **Step 3: Restructure `create_app`** — in `codemble/server/app.py`:

Add imports and the two new types near the top (after the existing imports):

```python
from dataclasses import dataclass
```

```python
@dataclass(frozen=True)
class PickerConfig:
    """Filesystem scope and parse settings for the in-app project picker."""

    browse_root: Path
    entrypoint: str | None = None


class _ProjectState:
    """One-shot binding from picker selection to live project services."""

    def __init__(self) -> None:
        self.checks: CheckService | None = None
        self.studies: StudyService | None = None

    @property
    def bound(self) -> bool:
        return self.checks is not None

    def bind(self, graph: Graph) -> None:
        self.studies = StudyService.from_environment(graph)
        self.checks = CheckService(graph)
```

Change the `create_app` signature and body head to:

```python
def create_app(
    graph: Graph | None = None,
    web_dist: Path | None = None,
    study_service: StudyService | None = None,
    check_service: CheckService | None = None,
    *,
    picker: PickerConfig | None = None,
) -> FastAPI:
    """Create an API and optional SPA server for one local project."""

    if graph is None and picker is None:
        raise ValueError("create_app needs a parsed graph or a PickerConfig")
    app = FastAPI(title="Codemble", version=__version__, docs_url=None, redoc_url=None)
    state = _ProjectState()
    if graph is not None:
        state.studies = study_service or StudyService.from_environment(graph)
        state.checks = check_service or CheckService(graph)

    def _services() -> tuple[CheckService, StudyService]:
        if state.checks is None or state.studies is None:
            raise HTTPException(status_code=409, detail="No project selected yet.")
        return state.checks, state.studies

    @app.get("/api/picker/state")
    def get_picker_state() -> dict[str, str]:
        return {"state": "ready" if state.bound else "unpicked"}
```

Then rewrite each existing project endpoint to fetch services through the guard — first line of each body:

```python
    @app.get("/api/graph")
    def get_graph() -> dict[str, object]:
        checks, _ = _services()
        return checks.graph().to_dict()

    @app.post("/api/entrypoint")
    def select_entrypoint(selection: EntrypointSelection) -> dict[str, object]:
        checks, _ = _services()
        try:
            selected = checks.select_entrypoint(selection.node_id)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Choose one of the parser-ranked entrypoint candidates.",
            ) from error
        return selected.to_dict()

    @app.get("/api/regions/{region_id:path}/checks")
    def get_region_checks(region_id: str) -> dict[str, object]:
        checks, _ = _services()
        try:
            return checks.for_region(region_id)
        except UnknownCheckError as error:
            raise HTTPException(
                status_code=404, detail="That region is not in this graph."
            ) from error

    @app.post("/api/regions/{region_id:path}/checks/{check_id}")
    def submit_region_check(
        region_id: str, check_id: str, submission: CheckSubmission
    ) -> dict[str, object]:
        checks, _ = _services()
        try:
            return checks.submit(region_id, check_id, submission.selected_ids)
        except UnknownCheckError as error:
            raise HTTPException(
                status_code=404, detail="That graph check does not exist."
            ) from error
        except InvalidCheckSubmission as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/node/{node_id:path}/study")
    def get_node_study(node_id: str) -> dict[str, object]:
        _, studies = _services()
        try:
            return studies.study(node_id)
        except UnknownNodeError as error:
            raise HTTPException(
                status_code=404, detail="That source node is not in this graph."
            ) from error
        except StudySourceError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
```

Delete the old top-level `studies = ...` / `checks = ...` assignments. The `distribution = web_dist or _default_web_dist()` block stays last, unchanged — every `/api/picker/*` route added in tasks 4–6 must be registered **before** it (inside `create_app`, above the SPA block), or the SPA catch-all swallows them.

- [ ] **Step 4: Run the whole server suite**

Run: `pytest tests/test_server.py tests/test_smoke.py -v && ruff check .`
Expected: PASS (all pre-existing tests plus the three new ones)

- [ ] **Step 5: Commit**

```bash
git add codemble/server/app.py tests/test_server.py
git commit -m "feat: serve an unpicked project state behind /api/picker/state"
```

---

### Task 4: `GET /api/picker/browse` — jailed directory listing

**Files:**
- Modify: `codemble/server/app.py` (inside `create_app`, after `get_picker_state`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `PickerConfig.browse_root`, `_ProjectState.bound` (task 3).
- Produces: `GET /api/picker/browse?path=…` → `{"path": str, "parent": str | None, "entries": [{"name": str, "path": str}]}`; directories only, dot-dirs hidden, sorted case-insensitively; `parent` is `None` at the jail root. 404 unknown path, 403 outside `browse_root` or unreadable, 409 once bound. Task 9's HTTP adapter consumes this shape.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_server.py`)

```python
def test_picker_browse_lists_directories_inside_the_jail(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    (tmp_path / "beta").mkdir()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "loose.py").write_text("A = 1\n", encoding="utf-8")
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    root_listing = client.get("/api/picker/browse")
    child_listing = client.get(
        "/api/picker/browse", params={"path": str(tmp_path / "beta")}
    )

    assert root_listing.status_code == 200
    assert root_listing.json()["parent"] is None
    assert [entry["name"] for entry in root_listing.json()["entries"]] == [
        "Alpha",
        "beta",
    ]
    assert child_listing.json()["parent"] == str(tmp_path.resolve())
    assert client.get(
        "/api/picker/browse", params={"path": str(tmp_path / "missing-dir")}
    ).status_code == 404
    assert client.get(
        "/api/picker/browse", params={"path": str(tmp_path.parent)}
    ).status_code == 403


def test_picker_browse_refuses_symlink_escape(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    jail = tmp_path / "jail"
    outside = tmp_path / "outside"
    jail.mkdir()
    outside.mkdir()
    (jail / "escape").symlink_to(outside)
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=jail))
    )

    assert client.get(
        "/api/picker/browse", params={"path": str(jail / "escape")}
    ).status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py -k picker_browse -v`
Expected: FAIL — the SPA fallback (or missing-build handler) answers instead of a picker route.

- [ ] **Step 3: Implement** — add inside `create_app`, directly after `get_picker_state`:

```python
    @app.get("/api/picker/browse")
    def browse_picker(path: str | None = None) -> dict[str, object]:
        if state.bound or picker is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        jail = picker.browse_root.expanduser().resolve()
        target = Path(path).expanduser() if path else jail
        try:
            resolved = target.resolve(strict=True)
        except OSError as error:
            raise HTTPException(
                status_code=404, detail="That folder does not exist."
            ) from error
        if not resolved.is_dir():
            raise HTTPException(status_code=404, detail="That folder does not exist.")
        if not resolved.is_relative_to(jail):
            raise HTTPException(
                status_code=403, detail="Choose a folder inside your home directory."
            )
        try:
            children = [
                child
                for child in resolved.iterdir()
                if child.is_dir() and not child.name.startswith(".")
            ]
        except OSError as error:
            raise HTTPException(
                status_code=403, detail="Codemble cannot read that folder."
            ) from error
        entries = sorted(
            ({"name": child.name, "path": str(child)} for child in children),
            key=lambda entry: str(entry["name"]).lower(),
        )
        parent = str(resolved.parent) if resolved != jail else None
        return {"path": str(resolved), "parent": parent, "entries": entries}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -k picker -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/server/app.py tests/test_server.py
git commit -m "feat: browse home-jailed folders from the project picker"
```

---

### Task 5: `GET /api/picker/recents`

**Files:**
- Modify: `codemble/server/app.py` (import + endpoint after `browse_picker`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `list_recent_projects()` (task 2), `_ProjectState.bound` (task 3).
- Produces: `GET /api/picker/recents` → `{"recents": [{"project_root": str, "understood_count": int}]}`; 409 once bound. Task 9's HTTP adapter consumes this shape.

- [ ] **Step 1: Write the failing test** (append to `tests/test_server.py`)

```python
def test_picker_recents_come_from_the_progress_store(
    tmp_path: Path, monkeypatch
) -> None:
    import json as json_module

    from codemble.server.app import PickerConfig

    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    project = tmp_path / "demo"
    project.mkdir()
    progress = tmp_path / "data" / "progress"
    progress.mkdir(parents=True)
    (progress / "abc.json").write_text(
        json_module.dumps(
            {
                "schema_version": 1,
                "project_root": str(project),
                "regions": {"pkg": {"signature": "s"}},
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.get("/api/picker/recents").json() == {
        "recents": [{"project_root": str(project), "understood_count": 1}]
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -k picker_recents -v`
Expected: FAIL (route missing)

- [ ] **Step 3: Implement** — add `from codemble.progress import list_recent_projects` to the imports in `codemble/server/app.py`, then inside `create_app` after `browse_picker`:

```python
    @app.get("/api/picker/recents")
    def picker_recents() -> dict[str, object]:
        if state.bound or picker is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        return {"recents": list_recent_projects()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -k picker -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/server/app.py tests/test_server.py
git commit -m "feat: offer recently explored projects in the picker"
```

---

### Task 6: `POST /api/picker/select` — parse and bind exactly once

**Files:**
- Modify: `codemble/server/app.py` (model + endpoint after `picker_recents`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `ProjectParser.intake/parse`, `ProjectScaleError(intake, scale_cap)`, `ProjectParseError`, `intake.scope_counts()` (task 1), `_ProjectState.bind` (task 3), `PickerConfig.entrypoint`.
- Produces: `POST /api/picker/select {"path": str}` →
  - 200 `{"state": "ready"}` and the app is bound (existing `/api/*` endpoints go live);
  - 409 `{"detail": {"reason": "scale", "file_count": int, "scale_cap": int, "root": str, "suggestions": [{"path": str, "file_count": int}]}}` over the cap;
  - 422 `{"detail": str}` on parse errors; 404/403 mirror `browse`; 409 `{"detail": "A project is already selected."}` once bound.
  - Task 9's HTTP adapter distinguishes the two 409s by `detail.reason == "scale"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_server.py`)

```python
def test_picker_select_binds_a_project_exactly_once(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
        )
    )

    first = client.post("/api/picker/select", json={"path": str(FIXTURE)})
    second = client.post("/api/picker/select", json={"path": str(FIXTURE)})

    assert first.status_code == 200
    assert first.json() == {"state": "ready"}
    assert client.get("/api/picker/state").json() == {"state": "ready"}
    assert client.get("/api/graph").status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "A project is already selected."
    assert client.get("/api/picker/browse").status_code == 409


def test_picker_select_reports_scale_with_suggestions(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    big = tmp_path / "big"
    (big / "api").mkdir(parents=True)
    for index in range(301):
        (big / "api" / f"module_{index}.py").write_text("A = 1\n", encoding="utf-8")
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    response = client.post("/api/picker/select", json={"path": str(big)})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"] == "scale"
    assert detail["file_count"] == 301
    assert detail["scale_cap"] == 300
    assert detail["root"] == str(big.resolve())
    assert detail["suggestions"][0] == {"path": "api", "file_count": 301}


def test_picker_select_rejects_unparseable_and_escaping_paths(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    empty = tmp_path / "empty"
    empty.mkdir()
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.post(
        "/api/picker/select", json={"path": str(empty)}
    ).status_code == 422
    assert client.post(
        "/api/picker/select", json={"path": str(tmp_path.parent)}
    ).status_code == 403
    assert client.post(
        "/api/picker/select", json={"path": str(tmp_path / "nope")}
    ).status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py -k picker_select -v`
Expected: FAIL (route missing)

- [ ] **Step 3: Implement** — in `codemble/server/app.py` add to the imports:

```python
from codemble.adapters.project import (
    ProjectParseError,
    ProjectParser,
    ProjectScaleError,
)
```

Add the request model next to the existing models:

```python
class ProjectSelection(BaseModel):
    """One learner-chosen folder to parse into the session's project."""

    path: str
```

Add inside `create_app` after `picker_recents`:

```python
    @app.post("/api/picker/select")
    def select_project(selection: ProjectSelection) -> dict[str, object]:
        if state.bound or picker is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        jail = picker.browse_root.expanduser().resolve()
        try:
            resolved = Path(selection.path).expanduser().resolve(strict=True)
        except OSError as error:
            raise HTTPException(
                status_code=404, detail="That folder does not exist."
            ) from error
        if not resolved.is_relative_to(jail):
            raise HTTPException(
                status_code=403, detail="Choose a folder inside your home directory."
            )
        parser = ProjectParser()
        try:
            intake = parser.intake(resolved)
        except ProjectScaleError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": "scale",
                    "file_count": len(error.intake.files),
                    "scale_cap": error.scale_cap,
                    "root": str(error.intake.root),
                    "suggestions": [
                        {"path": directory, "file_count": count}
                        for directory, count in error.intake.scope_counts()[:6]
                    ],
                },
            ) from error
        except ProjectParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        try:
            bound_graph = parser.parse(intake, entrypoint=picker.entrypoint)
        except ProjectParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        state.bind(bound_graph)
        return {"state": "ready"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/server/app.py tests/test_server.py
git commit -m "feat: bind the picked project exactly once through the picker API"
```

---

### Task 7: Host-header allowlist

**Files:**
- Modify: `codemble/server/app.py` (signature + middleware)
- Modify: `codemble/server/runtime.py` (pass the serving host through)
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `create_app(..., allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver"))` keyword; `serve_project`/`serve_picker` (task 8) pass `allowed_hosts=("127.0.0.1", "localhost", "testserver", host)`. Requests with any other `Host` header get 400 before reaching a route.

- [ ] **Step 1: Write the failing test** (append to `tests/test_server.py`)

```python
def test_foreign_host_headers_are_rejected(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    rebinding = client.get("/api/graph", headers={"Host": "evil.example"})

    assert rebinding.status_code == 400
    assert client.get("/api/graph").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py::test_foreign_host_headers_are_rejected -v`
Expected: FAIL — the foreign-host request returns 200.

- [ ] **Step 3: Implement** — in `codemble/server/app.py` add the import:

```python
from starlette.middleware.trustedhost import TrustedHostMiddleware
```

Extend the `create_app` signature with a final keyword parameter:

```python
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver"),
```

and register the middleware right after `app = FastAPI(...)`:

```python
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))
```

In `codemble/server/runtime.py`, pass the runtime host through in `serve_project`:

```python
    app = create_app(graph, allowed_hosts=("127.0.0.1", "localhost", "testserver", host))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -v && ruff check .`
Expected: PASS (TestClient's default `Host: testserver` stays allowed everywhere)

- [ ] **Step 5: Commit**

```bash
git add codemble/server/app.py codemble/server/runtime.py tests/test_server.py
git commit -m "feat: reject foreign Host headers on the local server"
```

---

### Task 8: CLI — bare `codemble` serves the picker

**Files:**
- Modify: `codemble/server/runtime.py` (add `serve_picker`)
- Modify: `codemble/cli.py` (zero-arg routing, no-path routing)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `create_app(picker=PickerConfig(...), allowed_hosts=...)` (tasks 3, 7), `available_port`.
- Produces: `serve_picker(*, host: str = "127.0.0.1", port: int = 0, open_browser: bool = True, entrypoint: str | None = None) -> None` in `codemble.server.runtime`, imported by `codemble.cli`. Behavior change: `codemble` with no path at all (bare, flags-only, or hidden `codemble serve`) serves the picker instead of printing help / serving the CWD. `codemble ./path`, `codemble --path ./scope`, and `codemble parse` are unchanged.

- [ ] **Step 1: Update the zero-arg test** — in `tests/test_smoke.py`, replace `test_cli_runs` with:

```python
def test_bare_codemble_serves_the_picker(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "codemble.cli.serve_picker", lambda **kwargs: calls.update(kwargs)
    )

    assert main([]) == 0

    assert calls == {
        "host": "127.0.0.1",
        "port": 0,
        "open_browser": True,
        "entrypoint": None,
    }


def test_flags_without_a_path_still_serve_the_picker(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "codemble.cli.serve_picker", lambda **kwargs: calls.update(kwargs)
    )

    assert main(["--no-open", "--port", "8123"]) == 0

    assert calls["open_browser"] is False
    assert calls["port"] == 8123
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_smoke.py -k picker -v`
Expected: FAIL with `AttributeError: ... has no attribute 'serve_picker'`

- [ ] **Step 3: Implement `serve_picker`** — append to `codemble/server/runtime.py` (and add `PickerConfig` to its `codemble.server.app` import):

```python
def serve_picker(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    entrypoint: str | None = None,
) -> None:
    """Serve the picker-first app so the learner selects a project in the UI."""

    selected_port = port or available_port(host)
    url = f"http://{host}:{selected_port}"
    app = create_app(
        picker=PickerConfig(browse_root=Path.home(), entrypoint=entrypoint),
        allowed_hosts=("127.0.0.1", "localhost", "testserver", host),
    )
    print(f"Codemble is ready — pick your project folder in the browser.\nOpen {url}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=selected_port, log_level="warning")
```

Update `__all__` to `["available_port", "serve_picker", "serve_project"]`.

- [ ] **Step 4: Route the CLI** — in `codemble/cli.py`:

Import: `from codemble.server.runtime import serve_picker, serve_project`.

Make the serve path optional-with-no-default:

```python
    serve_command.add_argument(
        "path", nargs="?", default=None, type=Path, help="source file or project directory"
    )
```

Change the dispatch guard so zero args also route to serve:

```python
    if not raw_arguments or raw_arguments[0] not in {
        "parse",
        "serve",
        "--version",
        "-h",
        "--help",
    }:
        raw_arguments.insert(0, "serve")
```

Remove the now-unreachable `if arguments.command is None:` help block, and at the top of the `serve` branch:

```python
    elif arguments.command == "serve":
        try:
            if arguments.path is None and arguments.scope_path is None:
                serve_picker(
                    host=arguments.host,
                    port=arguments.port,
                    open_browser=not arguments.no_open,
                    entrypoint=arguments.entrypoint,
                )
                return 0
            requested = arguments.scope_path or arguments.path
            ...  # existing choose_project_scope / serve_project body unchanged
```

- [ ] **Step 5: Run the suite and lint**

Run: `pytest && ruff check .`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add codemble/cli.py codemble/server/runtime.py tests/test_smoke.py
git commit -m "feat: bare codemble serves the in-app project picker"
```

---

### Task 9: Frontend adapters — picker methods on HTTP and in-memory adapters

**Files:**
- Modify: `web/src/learnerSession.js` (both adapter factories)
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: the API shapes from tasks 3–6.
- Produces (consumed by task 10's session logic) — every adapter exposes:
  - `loadPickerState(options) -> {state: "unpicked" | "ready"}`
  - `browsePicker(path | null, options) -> {path, parent, entries}`
  - `loadRecents(options) -> {recents: [{project_root, understood_count}]}`
  - `selectProject(path, options) -> {state: "ready"} | {state: "scale", file_count, scale_cap, root, suggestions} | {state: "error", detail}` — **never throws on HTTP error statuses**; the in-memory adapter's `createInMemoryLearnerSessionAdapter` gains an optional `picker` fixture `{browse: {"" | path: listing}, recents: [...], selections: {path: result}}` and reports `ready` state when the fixture is absent or a `ready` selection has landed.

- [ ] **Step 1: Write the failing checks** — append to `web/scripts/check_learner_session.mjs`:

```js
// HTTP picker adapter: URLs, payloads, and non-throwing select results.
const httpCalls = [];
const pickerFetch = async (url, options = {}) => {
  httpCalls.push({ url, options });
  if (url === "/api/picker/state") {
    return { ok: true, status: 200, json: async () => ({ state: "unpicked" }) };
  }
  if (url === "/api/picker/select") {
    return {
      ok: false,
      status: 409,
      json: async () => ({
        detail: {
          reason: "scale",
          file_count: 420,
          scale_cap: 300,
          root: "/home/u/big",
          suggestions: [{ path: "api", file_count: 300 }],
        },
      }),
    };
  }
  throw new Error(`Unexpected picker URL: ${url}`);
};
const httpPicker = createHttpLearnerSessionAdapter(pickerFetch);
assert.deepEqual(await httpPicker.loadPickerState(), { state: "unpicked" });
const scaleResult = await httpPicker.selectProject("/home/u/big");
assert.equal(scaleResult.state, "scale");
assert.equal(scaleResult.file_count, 420);
assert.equal(
  JSON.parse(httpCalls.at(-1).options.body).path,
  "/home/u/big",
);
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL with `TypeError: httpPicker.loadPickerState is not a function`

- [ ] **Step 3: Implement the HTTP adapter methods** — inside the `return Object.freeze({...})` of `createHttpLearnerSessionAdapter`, add:

```js
    loadPickerState(options = {}) {
      return request("/api/picker/state", "Picker state", options);
    },
    browsePicker(path, options = {}) {
      const query = path ? `?path=${encodeURIComponent(path)}` : "";
      return request(`/api/picker/browse${query}`, "Folder listing", options);
    },
    loadRecents(options = {}) {
      return request("/api/picker/recents", "Recent projects", options);
    },
    async selectProject(path, options = {}) {
      const response = await fetchImplementation("/api/picker/select", {
        ...options,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const payload = await response.json().catch(() => null);
      if (response.ok) return { state: "ready" };
      const detail = payload?.detail;
      if (detail && typeof detail === "object" && detail.reason === "scale") {
        return { state: "scale", ...detail };
      }
      return {
        state: "error",
        detail:
          typeof detail === "string"
            ? detail
            : `Project selection returned ${response.status}.`,
      };
    },
```

- [ ] **Step 4: Implement the in-memory adapter methods** — change the factory signature to accept `picker = null` and add inside its frozen object:

```js
export function createInMemoryLearnerSessionAdapter({
  graph,
  studies = {},
  checks = {},
  submissions = {},
  entrypoints = {},
  picker = null,
}) {
  let currentGraph = graph;
  const currentChecks = new Map(Object.entries(checks));
  const pickerPhase = picker ? { ...picker, selected: false } : null;
  return Object.freeze({
    async loadPickerState(options = {}) {
      throwIfAborted(options.signal);
      return pickerPhase && !pickerPhase.selected
        ? { state: "unpicked" }
        : { state: "ready" };
    },
    async browsePicker(path, options = {}) {
      throwIfAborted(options.signal);
      return requiredFixture(pickerPhase.browse, path ?? "", "picker listing");
    },
    async loadRecents(options = {}) {
      throwIfAborted(options.signal);
      return { recents: pickerPhase.recents ?? [] };
    },
    async selectProject(path, options = {}) {
      throwIfAborted(options.signal);
      const result = requiredFixture(pickerPhase.selections, path, "picker selection");
      if (result.state === "ready") pickerPhase.selected = true;
      return result;
    },
    // ...existing loadGraph/loadStudy/loadChecks/submitCheck/selectEntrypoint stay unchanged
  });
}
```

- [ ] **Step 5: Run the check script**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: exits 0 (existing scenarios still pass — the in-memory adapter without a `picker` fixture reports `ready`, so current callers are untouched)

- [ ] **Step 6: Commit**

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs
git commit -m "feat: teach both session adapters the picker API"
```

---

### Task 10: Frontend session — the "picking" phase

**Files:**
- Modify: `web/src/learnerSession.js` (`createLearnerSession`)
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: adapter picker methods (task 9).
- Produces (consumed by task 11's React): snapshot `status` gains `"picking"`; snapshot gains `picker: null | {path, parent, entries, recents, error, scale, busy}`; new dispatch events `{type: "BROWSE_PICKER", path}` and `{type: "SELECT_PROJECT", path}`. A `ready` selection flows straight into the normal graph-loading path with no reload.

- [ ] **Step 1: Write the failing scenario** — append to `web/scripts/check_learner_session.mjs`:

```js
// Picker phase: unpicked server → recents → scale rescope → select → ready.
const pickerAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  picker: {
    browse: {
      "": {
        path: "/home/u",
        parent: null,
        entries: [
          { name: "big", path: "/home/u/big" },
          { name: "demo", path: "/home/u/demo" },
        ],
      },
      "/home/u/big": {
        path: "/home/u/big",
        parent: "/home/u",
        entries: [{ name: "api", path: "/home/u/big/api" }],
      },
    },
    recents: [{ project_root: "/home/u/demo", understood_count: 2 }],
    selections: {
      "/home/u/big": {
        state: "scale",
        file_count: 420,
        scale_cap: 300,
        root: "/home/u/big",
        suggestions: [{ path: "api", file_count: 300 }],
      },
      "/home/u/demo": { state: "ready" },
    },
  },
});
const pickerSession = createLearnerSession({ adapter: pickerAdapter, clock });
await pickerSession.start();
let pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "picking");
assert.equal(pickerSnapshot.picker.path, "/home/u");
assert.equal(pickerSnapshot.picker.recents[0].understood_count, 2);

await pickerSession.dispatch({ type: "BROWSE_PICKER", path: "/home/u/big" });
assert.equal(pickerSession.getSnapshot().picker.path, "/home/u/big");

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/big" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "picking");
assert.equal(pickerSnapshot.picker.scale.file_count, 420);
assert.equal(pickerSnapshot.picker.path, "/home/u/big");
assert.equal(pickerSnapshot.picker.busy, false);

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "ready");
assert.equal(pickerSnapshot.picker, null);
assert.equal(pickerSnapshot.graph, graph);
pickerSession.dispose();
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL — `status` is `"ready"`, not `"picking"` (session never queries picker state), or unknown event error.

- [ ] **Step 3: Implement the session phase** — in `createLearnerSession`:

Add `picker: null` to the initial `deriveSnapshot({...})` state and a `let pickerController = null;` beside the other controllers (abort + null it in `dispose`).

Replace `start` and add the helpers:

```js
  async function start() {
    lifecycle += 1;
    const requestLifecycle = lifecycle;
    abortController(graphController);
    graphController = new AbortController();
    const controller = graphController;
    commit({ status: "loading", error: "" });
    let pickerState;
    try {
      pickerState = await adapter.loadPickerState({ signal: controller.signal });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: errorMessage(requestError) });
      }
      return snapshot;
    }
    if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
    if (pickerState.state === "unpicked") {
      return startPicker(controller, requestLifecycle);
    }
    return loadProjectGraph(controller, requestLifecycle);
  }

  async function loadProjectGraph(controller, requestLifecycle) {
    commit({ status: "loading", error: "", picker: null });
    try {
      const graph = await adapter.loadGraph({ signal: controller.signal });
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      commit({ status: "ready", graph, region: defaultRegion(graph), error: "" });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: errorMessage(requestError) });
      }
    }
    return snapshot;
  }

  async function startPicker(controller, requestLifecycle) {
    try {
      const [recentsPayload, listing] = await Promise.all([
        adapter.loadRecents({ signal: controller.signal }),
        adapter.browsePicker(null, { signal: controller.signal }),
      ]);
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      commit({
        status: "picking",
        picker: {
          ...listing,
          recents: recentsPayload.recents,
          error: "",
          scale: null,
          busy: false,
        },
      });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: errorMessage(requestError) });
      }
    }
    return snapshot;
  }

  async function browsePickerFolder(path) {
    if (snapshot.status !== "picking") return;
    abortController(pickerController);
    pickerController = new AbortController();
    const controller = pickerController;
    try {
      const listing = await adapter.browsePicker(path, { signal: controller.signal });
      if (!controller.signal.aborted && snapshot.status === "picking") {
        commit({ picker: { ...snapshot.picker, ...listing, error: "" } });
      }
    } catch (requestError) {
      if (
        pickerController === controller &&
        !isAbortError(requestError) &&
        snapshot.status === "picking"
      ) {
        commit({ picker: { ...snapshot.picker, error: errorMessage(requestError) } });
      }
    }
  }

  async function selectProject(path) {
    if (snapshot.status !== "picking" || snapshot.picker?.busy) return undefined;
    abortController(pickerController);
    pickerController = new AbortController();
    const controller = pickerController;
    commit({ picker: { ...snapshot.picker, busy: true, error: "", scale: null } });
    try {
      const result = await adapter.selectProject(path, { signal: controller.signal });
      if (controller.signal.aborted || snapshot.status !== "picking") return result;
      if (result.state === "ready") {
        lifecycle += 1;
        const requestLifecycle = lifecycle;
        abortController(graphController);
        graphController = new AbortController();
        return loadProjectGraph(graphController, requestLifecycle);
      }
      if (result.state === "scale") {
        const listing = await adapter.browsePicker(result.root, {
          signal: controller.signal,
        });
        if (!controller.signal.aborted && snapshot.status === "picking") {
          commit({
            picker: { ...snapshot.picker, ...listing, busy: false, scale: result },
          });
        }
        return result;
      }
      commit({ picker: { ...snapshot.picker, busy: false, error: result.detail } });
      return result;
    } catch (requestError) {
      if (!isAbortError(requestError) && snapshot.status === "picking") {
        commit({ picker: { ...snapshot.picker, busy: false, error: errorMessage(requestError) } });
      }
      return undefined;
    }
  }
```

Add the dispatch cases:

```js
      case "BROWSE_PICKER":
        return browsePickerFolder(event.path);
      case "SELECT_PROJECT":
        return selectProject(event.path);
```

- [ ] **Step 4: Run the check script**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: exits 0 (all scenarios, old and new)

- [ ] **Step 5: Commit**

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs
git commit -m "feat: give the learner session a project-picking phase"
```

---

### Task 11: Picker screen UI + rebuilt `web_dist` + end-to-end run

**Files:**
- Modify: `web/src/App.jsx` (render the picking phase, add `PickerScreen`)
- Modify: `web/src/styles.css` (picker styles)
- Modify: `codemble/web_dist/` (rebuilt artifact — committed)

**Interfaces:**
- Consumes: snapshot `status === "picking"`, `snapshot.picker`, events `BROWSE_PICKER` / `SELECT_PROJECT` (task 10). No game or layout logic in React.

- [ ] **Step 1: Render the phase** — in `App()` in `web/src/App.jsx`, destructure `picker` from the state and add this branch between the error branch and the loading branch:

```jsx
  if (status === "picking" && picker) {
    return (
      <PickerScreen
        picker={picker}
        onBrowse={(path) => session.dispatch({ type: "BROWSE_PICKER", path })}
        onSelect={(path) => session.dispatch({ type: "SELECT_PROJECT", path })}
      />
    );
  }
```

- [ ] **Step 2: Add the component** — append near the other screen-level components in `App.jsx`:

```jsx
function PickerScreen({ picker, onBrowse, onSelect }) {
  const { path, parent, entries, recents, error, scale, busy } = picker;
  return (
    <main className="picker-screen" aria-busy={busy}>
      <header className="picker-header">
        <p className="picker-wordmark">Codemble</p>
        <h1>Choose the project to chart</h1>
        <p className="picker-subtitle">
          Codemble reads the folder locally and turns it into a galaxy. Nothing
          leaves this machine.
        </p>
      </header>
      {recents.length ? (
        <section className="picker-recents" aria-labelledby="picker-recents-heading">
          <h2 id="picker-recents-heading">Continue where you left off</h2>
          <ul>
            {recents.map((recent) => (
              <li key={recent.project_root}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onSelect(recent.project_root)}
                >
                  <span className="picker-recent-path">{recent.project_root}</span>
                  <span className="picker-recent-lit">
                    {recent.understood_count} {recent.understood_count === 1 ? "system" : "systems"} lit
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {scale ? (
        <p className="picker-scale" role="alert">
          That folder has {scale.file_count} supported source files; Codemble is
          capped at {scale.scale_cap}. Pick a subdirectory — busiest first:{" "}
          {scale.suggestions
            .map((suggestion) => `${suggestion.path} (${suggestion.file_count})`)
            .join(", ")}
          .
        </p>
      ) : null}
      {error ? (
        <p className="picker-error" role="alert">
          {error}
        </p>
      ) : null}
      <section className="picker-browser" aria-labelledby="picker-browser-heading">
        <h2 id="picker-browser-heading">Browse folders</h2>
        <p className="picker-path">{path}</p>
        <ul>
          {parent ? (
            <li>
              <button type="button" disabled={busy} onClick={() => onBrowse(parent)}>
                ↑ Up
              </button>
            </li>
          ) : null}
          {entries.map((entry) => (
            <li key={entry.path}>
              <button type="button" disabled={busy} onClick={() => onBrowse(entry.path)}>
                {entry.name}/
              </button>
            </li>
          ))}
        </ul>
        <button
          className="picker-select"
          type="button"
          disabled={busy}
          onClick={() => onSelect(path)}
        >
          {busy ? "Mapping…" : "Map this folder"}
        </button>
      </section>
    </main>
  );
}
```

- [ ] **Step 3: Style it** — append to `web/src/styles.css`, matching the existing token vocabulary (ruri `--cm-orbit` for interactive borders/focus, kohaku `--cm-star` **only** on the lit counts):

```css
.picker-screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: var(--cm-space-lg);
  padding: var(--cm-space-2xl) var(--cm-space-xl);
  max-width: 44rem;
  margin: 0 auto;
}

.picker-wordmark {
  font-family: var(--cm-font-display);
  font-size: var(--cm-text-sm);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--cm-ink-3);
}

.picker-subtitle {
  color: var(--cm-ink-2);
  font-size: var(--cm-text-sm);
}

.picker-recents ul,
.picker-browser ul {
  list-style: none;
  margin: var(--cm-space-sm) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--cm-space-2xs);
}

.picker-recents button,
.picker-browser ul button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: var(--cm-space-sm);
  padding: var(--cm-space-xs) var(--cm-space-sm);
  background: var(--cm-ground-2);
  border: 1px solid var(--cm-hairline);
  border-radius: var(--cm-radius);
  color: var(--cm-ink);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-sm);
  text-align: left;
  cursor: pointer;
}

.picker-recents button:hover,
.picker-recents button:focus-visible,
.picker-browser ul button:hover,
.picker-browser ul button:focus-visible {
  border-color: var(--cm-orbit);
}

.picker-recent-lit {
  color: var(--cm-star);
  white-space: nowrap;
}

.picker-path {
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-sm);
  color: var(--cm-ink-2);
  overflow-wrap: anywhere;
}

.picker-scale,
.picker-error {
  border: 1px solid var(--cm-hairline);
  border-radius: var(--cm-radius);
  padding: var(--cm-space-sm);
  font-size: var(--cm-text-sm);
}

.picker-error {
  color: var(--cm-error);
}

.picker-select {
  align-self: flex-start;
  padding: var(--cm-space-xs) var(--cm-space-lg);
  background: var(--cm-orbit-low);
  border: 1px solid var(--cm-orbit);
  border-radius: var(--cm-radius);
  color: var(--cm-ink);
  font-size: var(--cm-text-base);
  cursor: pointer;
}

.picker-select:disabled {
  opacity: 0.6;
  cursor: progress;
}
```

- [ ] **Step 4: Build and check**

Run: `cd web && npm run check`
Expected: both check scripts pass and `vite build` succeeds (writing into `codemble/web_dist/`).

- [ ] **Step 5: Verify end-to-end, by hand**

Run: `codemble --port 8321` (in the repo venv; the repo itself is a fine test project — pick a small subdirectory like `codemble/progress`).
Verify in the browser: picker screen appears → navigating folders works → "Map this folder" on a small project loads the galaxy with no reload → a huge folder shows the scale message and re-scopes → keyboard-only navigation works (all controls are buttons) → at 320 px width nothing overflows. Then re-run and confirm the just-explored project appears under recents. Ctrl-C the server.

- [ ] **Step 6: Commit (including the rebuilt artifact)**

```bash
git add web/src/App.jsx web/src/styles.css codemble/web_dist
git commit -m "feat: project picker screen in the packaged galaxy app"
```

---

### Task 12: Docs, changelog, release checklist, project bookkeeping

**Files:**
- Modify: `README.md` (install/quick-start section, ~lines 80–110)
- Modify: docs-site install/getting-started pages — find them with `grep -rl "pipx install" docs-site/src/content/docs`
- Modify: `CHANGELOG.md`
- Create: `docs/releases/checklist.md`
- Modify: `CLAUDE.md` (Current State note + Decision Log rows)

**Interfaces:** none — prose only. PyPI publishing itself is a human (UD) release-time action; this task only documents it.

- [ ] **Step 1: README quick start** — replace the primary install block with:

````markdown
### Run it

```bash
uvx codemble            # or: pipx install codemble && codemble
```

Codemble opens your browser — pick your project folder there. To skip the
picker, pass a path: `codemble ./your-ai-built-project`.

> Until the first PyPI release (v0.3.0) lands, install from the tag instead:
> `pipx install git+https://github.com/udhawan97/Codemble.git@v0.2.0`
````

Keep the "from source" block unchanged. Update the `--path` sentence to mention the picker handles over-cap projects in the UI too.

- [ ] **Step 2: Docs site** — apply the same install + picker copy to every page `grep` found; check each page's sidebar entry already exists in `docs-site/astro.config.mjs` (they do for existing pages; only a *new* page would need one). Run `cd docs-site && npm run check`.

- [ ] **Step 3: CHANGELOG** — add under a new `## [Unreleased]` heading (Keep a Changelog format):

```markdown
### Added
- Bare `codemble` now opens the browser to an in-app project picker: browse
  home folders, reopen recent projects, and re-scope over-cap projects without
  touching the terminal.
- The local server rejects foreign `Host` headers, keeping the picker API
  reachable only from the learner's own machine.

### Changed
- `codemble` with flags but no path serves the picker instead of the current
  directory; pass a path (or `--path`) for the previous behaviour.
```

- [ ] **Step 4: Release checklist** — create `docs/releases/checklist.md`:

```markdown
# Release checklist

Follow the evidence bar set by v0.2.0 (docs/releases/v0.2.0.md): tag from
exact `main`, CI green, live docs verified, wheel + SHA256SUMS attached,
fresh-download checksum and isolated install verified.

New since v0.2.0 — PyPI:

1. One-time: claim the `codemble` name on PyPI (UD account) before the first
   publish.
2. After the tag is verified: `python -m build` (or reuse the release wheel)
   and `uv publish` / `twine upload` from the tagged commit.
3. Verify `uvx codemble==<version>` cold-starts the picker on a clean machine
   before announcing the PyPI install path.
```

- [ ] **Step 5: CLAUDE.md bookkeeping** — update the Current State session note (one line: picker + PyPI-prep landed, date) and append the two pre-approved Decision Log rows:

```markdown
| 2026-07-19 | Bare `codemble` serves a one-shot in-app project picker (browse + recents) on a single two-phase server; binding is one-shot and the API is home-jailed with a Host-header allowlist | Approved by UD this session: easiest possible run flow for learners without a second server, without free filesystem enumeration, and without changing the one-graph app model |
| 2026-07-19 | Codemble publishes to PyPI from the next tagged release; install collapses to `uvx codemble` | Approved by UD this session: the git+tag install was the biggest onboarding hurdle for the target learner |
```

- [ ] **Step 6: Full verification sweep**

Run: `pytest && ruff check . && (cd web && npm run check) && (cd docs-site && npm run check)`
Expected: all four gates pass.

- [ ] **Step 7: Commit**

```bash
git add README.md CHANGELOG.md CLAUDE.md docs/releases/checklist.md docs-site
git commit -m "docs: picker-first quick start, PyPI release checklist"
```
