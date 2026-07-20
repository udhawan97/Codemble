# Galaxy UX Phase A — "light the dark" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the already-shipped-but-inert narration stack into the study panel, make parser connections readable at every level, and give the learner in-app control over project, Home, mode, and failure recovery — without touching graph truth.

**Architecture:** Backend gains exactly one new endpoint (`POST /api/picker/reset`) and one new persisted field (the selected entrypoint in `ProgressStore`). Everything else in Phase A consumes endpoints that already exist. `LearnerSession` grows six adapter methods, six state fields, and four events; React remains a pure renderer of session truth. The study-panel component family moves out of the ~700-line `App.jsx` into its own module so the new Connections and narration sections have somewhere to live.

**Tech Stack:** Python 3.11 + FastAPI + pytest + ruff · Vite + React 19 + `3d-force-graph` + three.js · plain-node assert scripts for frontend state (`web/scripts/*.mjs`).

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md` and `docs/superpowers/plans/2026-07-19-galaxy-ux-shared-contract.md`. Every task's requirements implicitly include this section.

**Correctness Contract (never violate):**
- "Structure, layouts, hints, tree shapes, and check answers come from the parser or graph only. Uncertain relationships stay labelled 'possible'. Every explanation cites a real `file:line`. The LLM narrates, never decides."
- Structure is never invented; explanations are grounded; lens claims attach only to parser-detected constructs; check answers come from the graph, never the model; approximate call edges are labeled "possible call".
- A legend or label may only describe an encoding the renderer actually draws.

**Repo gates:**
- Python: `pytest` and `ruff check .` are CI gates. Tests live in `tests/`.
- Frontend state tests: `web/scripts/check_learner_session.mjs` (plain node asserts). Graph-data tests: `web/scripts/check_graph_data.mjs`.
- Frontend verification: `cd web && npm run check` (runs both node check scripts, then `vite build` into `codemble/web_dist`).
- `codemble/web_dist` is a committed build artifact. **Any task changing `web/src` or `web/index.html` must run `cd web && npm run build` (or `npm run check`) and commit the resulting `codemble/web_dist` changes in the same commit.**
- Canvas colours must be plain `rgb()` values resolvable by `readPalette` (`web/src/GalaxyCanvas.jsx`), never `color-mix()`.
- `web/src/tokens.css` holds app-only tokens. Never edit `docs-site/src/styles/tokens.css` for app work.
- Conventional Commits, DCO sign-off (`git commit -s`).
- There is **no** jest/vitest/RTL in this repo. Do not add one. Pure-presentation React work is verified by running the app.

**Exact backend HTTP surface (do not rename, do not re-implement the shipped ones):**
- `GET /api/node/{node_id}/study` → `{node, source, neighbors, lens, structural}` — shipped
- `GET /api/node/{node_id}/explanation?mode=easy|expert` — shipped
- `GET /api/mode` → `{"mode": "easy"|"expert"}` — shipped
- `PUT /api/mode` body `{"mode": ...}` → `{"mode": ...}` — shipped
- `GET /api/llm/status` → `{configured_provider, configured_model, ollama}` — shipped
- `POST /api/picker/reset` — **new in Phase A.** no body → `200 {"state": "unpicked"}`; idempotent (already-unbound also returns 200)

**Exact session state fields added in Phase A** (`web/src/learnerSession.js`): `mode` (`"easy"`|`"expert"`, default `"expert"`), `llmStatus` (object|null), `explanation` (object|null), `explanationLoading` (bool), `explanationError` (string|null), `hoverNodeId` (string|null).

**Exact dispatch events added in Phase A:** `SET_MODE` (`{mode}`), `RESET_PROJECT`, `CHANGE_HOME`, `HOVER_NODE` (`{nodeId}`).

**Exact adapter methods added in Phase A** (both `createHttpLearnerSessionAdapter` and `createInMemoryLearnerSessionAdapter` must implement all of them): `fetchExplanation(nodeId, mode, options)`, `fetchMode(options)`, `putMode(mode, options)`, `fetchLlmStatus(options)`, `resetProject(options)`.

> **Resolved contract detail — cancellation argument shape.** The shared contract writes these as `fetchExplanation(nodeId, mode, signal)` ("all take an `AbortSignal` last"). Every one of the five existing adapter methods in this repo takes `options = {}` and reads `options.signal`. Mixing two calling conventions inside one adapter object is a footgun, and CLAUDE.md requires following established patterns. **Resolution: method names are exactly as the contract states; the final parameter is the repo's existing `options = {}` object carrying `signal`.** Phase B and Phase C plans must mirror this.

**Session invariants to preserve:** one `AbortController` per async concern, the `lifecycle` counter guarding stale responses, `commit()` clearing checks on navigation unless `preserveChecks`, and `deriveSnapshot` re-resolving region/node/level against the language-focused graph.

**Mode semantics:** `mode` never affects graph truth, coordinates, progress, or check scoring. In Phase A it selects narration voice, check prompt voice (`prompt_voices`, already returned by `checks/service.py`), and label wording **only**. Default layer / edge density / hint chip are **Phase B — do not build them.**

**Deliberately unchanged in Phase A:** zero-check regions stay dim (copy polish only); "studied" stays session-local (label polish only); no free flight; no XP/streaks/levels; no bloom, halos, nebulae, starfield, focus reticle, call-depth orbits, nebula dawn, 2D Map layer, layer switcher, coach-marks, or clickable breadcrumb (all Phase B); no threaded parse, progress endpoint, loading screen, scale-cap raise, check index, or graph cache (all Phase C).

---

## File Structure

| File | Create/Modify | One responsibility |
| --- | --- | --- |
| `codemble/server/app.py` | Modify | Add `_ProjectState.unbind()` and the `POST /api/picker/reset` route |
| `codemble/server/runtime.py` | Modify | Give the path-opened server a `PickerConfig` so reset can re-arm a picker |
| `codemble/progress/store.py` | Modify | Persist and read the learner's selected entrypoint beside progress |
| `codemble/checks/service.py` | Modify | Restore a still-ranked persisted Home at construction; persist on selection |
| `tests/test_server.py` | Modify | Reset lifecycle + entrypoint-persistence API contracts |
| `tests/test_checks.py` | Modify | Entrypoint persistence and the "no longer ranked" drop guard |
| `web/src/learnerSession.js` | Modify | Session state, events, and both adapters for mode/llmStatus/explanation/reset/hover |
| `web/scripts/check_learner_session.mjs` | Modify | Assertions for every new session field, event, and adapter method |
| `web/src/StudyPanel.jsx` | **Create** | The whole study-panel family: `StudyPanel`, `StructuralSummary`, `Explanation`, `ProviderGuidance`, `Connections`, `ConnectionGroup`, `MiniConstellation`, `SourceExcerpt`, `LensNotes`, `Citation` — state and rendering only |
| `web/src/App.jsx` | Modify | Shell, header, picker, checks, star chart, legend; delegates study to `StudyPanel.jsx` |
| `web/src/GalaxyCanvas.jsx` | Modify | Arrows, link tooltips, hover/select highlight, study-level connection visibility |
| `web/src/graphData.js` | Modify | Add the pure `linkLabel(link)` tooltip formatter |
| `web/scripts/check_graph_data.mjs` | Modify | Assertions for `linkLabel` |
| `web/src/styles.css` | Modify | Styles for the new rail actions, connections, mini constellation, affirmation, legend rows |
| `web/src/main.jsx` | Modify | React error boundary around `<App />` |
| `web/index.html` | Modify | `<noscript>` fallback |
| `codemble/web_dist/**` | Modify (generated) | Committed production bundle; rebuilt in every frontend commit |
| `CHANGELOG.md` | Modify | Keep a Changelog entry for Phase A |
| `docs-site/src/content/docs/study-panel.md` | **Create** | Public docs for the study panel, Easy/Expert, and the no-key path |
| `docs-site/src/content/docs/the-galaxy.md` | Modify | Legend meanings, arrows, highlight, switch project, change Home |
| `docs-site/src/content/docs/checks-and-lighting.md` | Modify | Correct-answer affirmation, why zero-check regions stay dim |
| `docs-site/src/content/docs/star-chart.md` | Modify | "this session" wording for studied counts |
| `docs-site/astro.config.mjs` | Modify | Hand-authored sidebar entry for the new page |

---

### Task 1: `POST /api/picker/reset`

**Files:**
- Modify: `codemble/server/app.py:60-74` (`_ProjectState`), `codemble/server/app.py:101-103` (routes area)
- Modify: `codemble/server/runtime.py:24-44` (`serve_project`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `POST /api/picker/reset` → `200 {"state": "unpicked"}` when a `PickerConfig` exists; `409` with `detail` string when the app was created without one. `_ProjectState.unbind() -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py`:

```python
def test_picker_reset_unbinds_and_re_arms_the_picker(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
        )
    )
    assert client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code == 200

    first = client.post("/api/picker/reset")
    second = client.post("/api/picker/reset")

    assert first.status_code == 200
    assert first.json() == {"state": "unpicked"}
    assert second.status_code == 200
    assert second.json() == {"state": "unpicked"}
    assert client.get("/api/picker/state").json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/picker/browse").status_code == 200
    assert client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code == 200
    assert client.get("/api/graph").status_code == 200


def test_picker_reset_works_for_a_path_opened_project_that_carries_a_picker(
    tmp_path: Path,
) -> None:
    from codemble.server.app import PickerConfig

    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(
        create_app(
            graph,
            tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
        )
    )

    assert client.get("/api/graph").status_code == 200
    assert client.post("/api/picker/reset").json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/picker/browse").status_code == 200


def test_picker_reset_refuses_an_app_built_without_a_picker(tmp_path: Path) -> None:
    # Unbinding here would strand the process with no way to pick anything,
    # so refusing is the honest answer rather than a 200 that breaks the app.
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    response = client.post("/api/picker/reset")

    assert response.status_code == 409
    assert client.get("/api/graph").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py -k picker_reset -v`
Expected: 3 FAILED with `assert 404 == 200` (no `/api/picker/reset` route exists, so FastAPI returns its default 404).

- [ ] **Step 3: Add `unbind()` to `_ProjectState`**

In `codemble/server/app.py`, replace the `_ProjectState` class body's `bind` method block with:

```python
    def bind(self, graph: Graph) -> None:
        self.studies = StudyService.from_environment(graph)
        self.checks = CheckService(graph)

    def unbind(self) -> None:
        """Drop the bound project so the picker can arm again.

        Progress is already on disk per project root, so releasing the live
        services loses nothing a re-select cannot restore.
        """

        self.checks = None
        self.studies = None
```

- [ ] **Step 4: Add the route**

In `codemble/server/app.py`, immediately after the `get_picker_state` route, insert:

```python
    @app.post("/api/picker/reset")
    def reset_picker() -> dict[str, str]:
        if picker is None:
            raise HTTPException(
                status_code=409,
                detail="This project was opened without a picker; restart Codemble to switch.",
            )
        state.unbind()
        return {"state": "unpicked"}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_server.py -k picker_reset -v`
Expected: 3 passed.

- [ ] **Step 6: Give the path-opened server a picker**

In `codemble/server/runtime.py`, replace the `app = create_app(...)` line inside `serve_project` with:

```python
    # A PickerConfig rides along even for `codemble <path>` so the header's
    # Switch project control can re-arm the picker without a process restart.
    # The CLI --entrypoint deliberately does not carry over: it was chosen for
    # the named project, not for whatever the learner picks next.
    app = create_app(
        graph,
        picker=PickerConfig(browse_root=Path.home()),
        allowed_hosts=("127.0.0.1", "localhost", "testserver", host),
    )
```

- [ ] **Step 7: Run the full backend gates**

Run: `pytest && ruff check .`
Expected: all tests pass, `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add codemble/server/app.py codemble/server/runtime.py tests/test_server.py
git commit -s -m "feat(server): add POST /api/picker/reset so a project can be released in-app"
```

---

### Task 2: Persist the selected entrypoint

**Files:**
- Modify: `codemble/progress/store.py:62-77` (beside `mode`/`set_mode`)
- Modify: `codemble/checks/service.py:62-95` (`CheckService.__init__`, `select_entrypoint`)
- Test: `tests/test_checks.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `ProgressStore.selected_entrypoint() -> str | None`, `ProgressStore.set_selected_entrypoint(node_id: str) -> None`. `CheckService(graph, progress)` restores a persisted Home when `graph.selected_entrypoint is None` **and** the saved id is still in `graph.entrypoint_candidates`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_checks.py`:

```python
def test_home_choice_survives_a_restart(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    progress_root = tmp_path / "progress"
    graph = PythonAstAdapter().parse(project)
    assert graph.selected_entrypoint is None

    CheckService(graph, ProgressStore(graph, progress_root)).select_entrypoint("beta")
    restarted = CheckService(graph, ProgressStore(graph, progress_root))
    hydrated = restarted.graph()

    assert hydrated.selected_entrypoint == "beta"
    assert next(region for region in hydrated.regions if region.id == "beta").home is True


def test_a_persisted_home_outside_the_parser_ranking_is_never_restored(
    tmp_path: Path,
) -> None:
    """A saved id the parser no longer ranks must be dropped, not invented back."""

    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    progress_root = tmp_path / "progress"
    graph = PythonAstAdapter().parse(project)
    ProgressStore(graph, progress_root).set_selected_entrypoint("deleted.module")

    restarted = CheckService(graph, ProgressStore(graph, progress_root))

    assert restarted.graph().selected_entrypoint is None


def test_an_explicit_home_outranks_a_persisted_one(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    progress_root = tmp_path / "progress"
    graph = PythonAstAdapter().parse(project)
    ProgressStore(graph, progress_root).set_selected_entrypoint("beta")
    explicit = PythonAstAdapter().parse(project, entrypoint="alpha")

    restarted = CheckService(explicit, ProgressStore(explicit, progress_root))

    assert restarted.graph().selected_entrypoint == "alpha"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_checks.py -k "home_choice or persisted_home or explicit_home" -v`
Expected: FAIL with `AttributeError: 'ProgressStore' object has no attribute 'set_selected_entrypoint'`.

- [ ] **Step 3: Add the store methods**

In `codemble/progress/store.py`, insert immediately after `set_mode`:

```python
    def selected_entrypoint(self) -> str | None:
        """Return the learner's persisted Home choice, if one was stored.

        Not signature-scoped like understood regions: Home is a navigation
        preference, not evidence of understanding. The caller re-validates the
        id against the current parser ranking before trusting it.
        """

        value = self._read().get("entrypoint")
        return value if isinstance(value, str) else None

    def set_selected_entrypoint(self, node_id: str) -> None:
        """Persist the learner's Home choice beside progress."""

        payload = self._read()
        payload["entrypoint"] = node_id
        self._write(payload)
```

- [ ] **Step 4: Restore and persist in `CheckService`**

In `codemble/checks/service.py`, replace the `__init__` and `select_entrypoint` methods with:

```python
    def __init__(self, graph: Graph, progress: ProgressStore | None = None) -> None:
        self._progress = progress or ProgressStore(graph)
        self._graph = _restored_entrypoint(graph, self._progress)
        self._checks = {
            region.id: generate_checks(self._graph, region.id)
            for region in self._graph.regions
        }
        self._passed: dict[str, set[str]] = {}
```

```python
    def select_entrypoint(self, node_id: str) -> Graph:
        """Apply an explicit parser-ranked Home choice to graph and check suites."""

        self._graph = with_entrypoint(self._graph, node_id)
        self._progress.set_selected_entrypoint(node_id)
        self._checks = {
            region.id: generate_checks(self._graph, region.id)
            for region in self._graph.regions
        }
        return self.graph()
```

Add this module-level helper directly above `def generate_checks(`:

```python
def _restored_entrypoint(graph: Graph, progress: ProgressStore) -> Graph:
    """Re-apply a persisted Home only when the parser still ranks it.

    An explicit CLI or picker choice wins outright, and a saved id the parser
    no longer ranks is dropped rather than invented back into the graph.
    """

    if graph.selected_entrypoint is not None:
        return graph
    saved = progress.selected_entrypoint()
    if saved is None or saved not in graph.entrypoint_candidates:
        return graph
    return with_entrypoint(graph, saved)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_checks.py -k "home_choice or persisted_home or explicit_home" -v`
Expected: 3 passed.

- [ ] **Step 6: Add the server-level restart test**

Append to `tests/test_server.py`:

```python
def test_selected_home_is_restored_for_the_next_run_of_the_same_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    first = TestClient(
        create_app(PythonAstAdapter().parse(project), tmp_path / "missing")
    )
    assert first.get("/api/graph").json()["selected_entrypoint"] is None
    assert first.post("/api/entrypoint", json={"node_id": "beta"}).status_code == 200

    restarted = TestClient(
        create_app(PythonAstAdapter().parse(project), tmp_path / "missing")
    )

    assert restarted.get("/api/graph").json()["selected_entrypoint"] == "beta"
```

- [ ] **Step 7: Run the full backend gates**

Run: `pytest && ruff check .`
Expected: all tests pass, `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add codemble/progress/store.py codemble/checks/service.py tests/test_checks.py tests/test_server.py
git commit -s -m "feat(progress): persist the selected Home so it survives a restart"
```

---

### Task 3: Session — mode sync and LLM status

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: `GET /api/mode`, `PUT /api/mode`, `GET /api/llm/status` (all shipped).
- Produces: state `mode` (`"easy"|"expert"`, initial `"expert"`), `llmStatus` (object|null); event `SET_MODE` (`{mode}`); adapter methods `fetchMode(options)`, `putMode(mode, options)`, `fetchLlmStatus(options)`. In-memory adapter gains `mode` and `llmStatus` fixture options.

- [ ] **Step 1: Write the failing test**

In `web/scripts/check_learner_session.mjs`, replace the `const adapter = createInMemoryLearnerSessionAdapter({` block's closing so it reads:

```js
const adapter = createInMemoryLearnerSessionAdapter({
  graph,
  studies: {
    "python:app.py:run": study,
    "typescript:main.ts:main": { ...study, node: graph.nodes[1] },
  },
  checks: { "app.py": firstChecks },
  submissions: {
    "app.py:calls": {
      result: { correct: true, region_understood: true },
      graph: understoodGraph,
      checks: passedChecks,
    },
  },
  entrypoints: { "python:app.py:run": understoodGraph },
  mode: "easy",
  llmStatus: {
    configured_provider: null,
    configured_model: null,
    ollama: {
      running: true,
      installed_models: ["gemma4:12b"],
      recommended: "gemma4:12b",
      fallback: "qwen3:8b",
    },
  },
});
```

Then insert these assertions immediately after the existing `assert.deepEqual(snapshot.languageOptions.map((option) => option.id), [...]);` block:

```js
assert.equal(snapshot.mode, "easy", "the session adopts the server's persisted mode");
assert.equal(snapshot.llmStatus.ollama.recommended, "gemma4:12b");

await session.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(session.getSnapshot().mode, "expert");
assert.deepEqual(await adapter.fetchMode(), { mode: "expert" }, "PUT reached the adapter");
await session.dispatch({ type: "SET_MODE", mode: "easy" });
assert.equal(session.getSnapshot().mode, "easy");
```

And add this standalone block just above the `function makeGraph(` declaration:

```js
// A failing mode write reverts the optimistic value: mode is a preference,
// never truth, so the UI must not claim a setting the server refused.
const modeFailureAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "easy" });
const modeFailureSession = createLearnerSession({
  adapter: {
    ...modeFailureAdapter,
    putMode() {
      throw new Error("mode write refused");
    },
  },
  clock,
});
await modeFailureSession.start();
assert.equal(modeFailureSession.getSnapshot().mode, "easy");
await modeFailureSession.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(
  modeFailureSession.getSnapshot().mode,
  "easy",
  "a refused mode write rolls back to the last server-confirmed value",
);
modeFailureSession.dispose();

// A failing status read must not blank the mode that loaded beside it.
const statusFailureAdapter = createInMemoryLearnerSessionAdapter({ graph, mode: "expert" });
const statusFailureSession = createLearnerSession({
  adapter: {
    ...statusFailureAdapter,
    fetchLlmStatus() {
      throw new Error("status unavailable");
    },
  },
  clock,
});
await statusFailureSession.start();
assert.equal(statusFailureSession.getSnapshot().mode, "expert");
assert.equal(statusFailureSession.getSnapshot().llmStatus, null);
assert.equal(statusFailureSession.getSnapshot().status, "ready");
statusFailureSession.dispose();
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL with `AssertionError [ERR_ASSERTION]: the session adopts the server's persisted mode` — `undefined !== 'easy'`.

- [ ] **Step 3: Add the state, the loader, and the event**

In `web/src/learnerSession.js`, add the two fields to the initial `deriveSnapshot({...})` call in `createLearnerSession` — insert after `languageFocus: "all",`:

```js
    mode: "expert",
    llmStatus: null,
```

Add a controller beside the existing ones (after `let pickerController = null;`):

```js
  let modeController = null;
```

Add the preferences loader immediately after `loadProjectGraph`:

```js
  async function loadPreferences(controller, requestLifecycle) {
    // allSettled, not all: mode and provider status are preferences. A failing
    // one must never blank the other and must never surface as a graph error.
    const [modeResult, statusResult] = await Promise.allSettled([
      adapter.fetchMode({ signal: controller.signal }),
      adapter.fetchLlmStatus({ signal: controller.signal }),
    ]);
    if (requestLifecycle !== lifecycle || controller.signal.aborted) return;
    const patch = {};
    if (modeResult.status === "fulfilled") patch.mode = modeResult.value.mode;
    if (statusResult.status === "fulfilled") patch.llmStatus = statusResult.value;
    if (Object.keys(patch).length > 0) commit(patch);
  }
```

In `loadProjectGraph`, replace the success commit line with:

```js
      commit({ status: "ready", graph, region: defaultRegion(graph), error: "" });
      await loadPreferences(controller, requestLifecycle);
```

Add the setter immediately after `setLanguageFocus`:

```js
  async function setMode(mode) {
    if (mode !== "easy" && mode !== "expert") return undefined;
    const previous = snapshot.mode;
    if (mode === previous) return undefined;
    abortController(modeController);
    modeController = new AbortController();
    const controller = modeController;
    commit({ mode });
    try {
      await adapter.putMode(mode, { signal: controller.signal });
    } catch (requestError) {
      if (modeController === controller && !isAbortError(requestError)) {
        commit({ mode: previous });
      }
    }
    return undefined;
  }
```

Add the case to `dispatch`, immediately after the `SET_LANGUAGE_FOCUS` case:

```js
      case "SET_MODE":
        return setMode(event.mode);
```

Add `modeController` to the `dispose()` loop array and null it out afterwards:

```js
    for (const controller of [
      graphController,
      studyController,
      checksController,
      submissionController,
      entrypointController,
      pickerController,
      modeController,
    ]) {
      abortController(controller);
    }
```

```js
    pickerController = null;
    modeController = null;
```

- [ ] **Step 4: Add the HTTP adapter methods**

In `createHttpLearnerSessionAdapter`, insert after the `selectEntrypoint` method:

```js
    fetchMode(options = {}) {
      return request("/api/mode", "Mode request", options);
    },
    putMode(mode, options = {}) {
      return request("/api/mode", "Mode update", {
        ...options,
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
    },
    fetchLlmStatus(options = {}) {
      return request("/api/llm/status", "Model status", options);
    },
```

- [ ] **Step 5: Add the in-memory adapter methods**

Replace the `createInMemoryLearnerSessionAdapter` signature and add the state line:

```js
export function createInMemoryLearnerSessionAdapter({
  graph,
  studies = {},
  checks = {},
  submissions = {},
  entrypoints = {},
  picker = null,
  mode = "easy",
  llmStatus = null,
}) {
  let currentGraph = graph;
  let currentMode = mode;
  const currentChecks = new Map(Object.entries(checks));
  const pickerPhase = picker ? { ...picker, selected: false } : null;
```

Insert these methods after `selectEntrypoint`:

```js
    async fetchMode(options = {}) {
      throwIfAborted(options.signal);
      return { mode: currentMode };
    },
    async putMode(nextMode, options = {}) {
      throwIfAborted(options.signal);
      currentMode = nextMode;
      return { mode: currentMode };
    },
    async fetchLlmStatus(options = {}) {
      throwIfAborted(options.signal);
      return (
        llmStatus ?? {
          configured_provider: null,
          configured_model: null,
          ollama: {
            running: false,
            installed_models: [],
            recommended: "gemma4:12b",
            fallback: "qwen3:8b",
          },
        }
      );
    },
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: `learner-session contracts passed`, exit 0.

- [ ] **Step 7: Build and commit**

Run: `cd web && npm run check`
Expected: both check scripts print their pass lines, then `✓ built in …`.

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): sync the audience mode and provider status into the learner session"
```

---

### Task 4: Session — grounded explanation loading

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: `GET /api/node/{node_id}/explanation?mode=` (shipped); `snapshot.mode` from Task 3.
- Produces: state `explanation` (object|null), `explanationLoading` (bool), `explanationError` (string, `""` when clear); adapter method `fetchExplanation(nodeId, mode, options)`. In-memory adapter gains an `explanations` fixture map keyed `` `${nodeId}:${mode}` ``. No new dispatch event: narration loads inside `loadStudy` and re-loads inside `setMode`; a retry is a re-`SELECT_STUDY_NODE` of the same id.

> **Resolved spec ambiguity.** Spec §6 lists a `LOAD_EXPLANATION` event, but the binding shared contract's Phase A event row does not include it (only `SET_MODE`, `RESET_PROJECT`, `CHANGE_HOME`, `HOVER_NODE`). Resolution: explanation loading stays internal to `loadStudy`/`setMode` exactly as check loading is internal to `openChecks`, and the panel's retry button re-dispatches the contract-listed `SELECT_STUDY_NODE` with the same node id.

- [ ] **Step 1: Write the failing test**

In `web/scripts/check_learner_session.mjs`, add `explanations` to the main `adapter` fixture — insert directly after the `entrypoints: { ... },` line:

```js
  explanations: {
    "python:app.py:run:easy": { status: "ready", summary: { text: "easy voice" } },
    "python:app.py:run:expert": { status: "ready", summary: { text: "expert voice" } },
    "typescript:main.ts:main:easy": { status: "no_key", message: "Add a key." },
    "typescript:main.ts:main:expert": { status: "no_key", message: "Add a key." },
  },
```

Insert these assertions immediately after the existing `assert(snapshot.studiedNodeIds.has("python:app.py:run"));` line:

```js
assert.equal(snapshot.explanationLoading, false);
assert.equal(snapshot.explanationError, "");
assert.equal(snapshot.explanation.summary.text, "easy voice");

await session.dispatch({ type: "SET_MODE", mode: "expert" });
assert.equal(
  session.getSnapshot().explanation.summary.text,
  "expert voice",
  "changing voice while studying re-narrates the same node",
);
await session.dispatch({ type: "SET_MODE", mode: "easy" });

await session.dispatch({ type: "RETREAT" });
assert.equal(session.getSnapshot().explanation, null, "leaving study drops its narration");
await session.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
```

Add this standalone block just above the `function makeGraph(` declaration:

```js
// A failing narration request must leave the structural evidence untouched.
const narrationFailureAdapter = createInMemoryLearnerSessionAdapter({
  graph,
  studies: { "python:app.py:run": study },
});
const narrationFailureSession = createLearnerSession({
  adapter: {
    ...narrationFailureAdapter,
    fetchExplanation() {
      return Promise.reject(new Error("Explanation request returned 502."));
    },
  },
  clock,
});
await narrationFailureSession.start();
await narrationFailureSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await narrationFailureSession.dispatch({ type: "ADVANCE", node: graph.nodes[0] });
const narrationSnapshot = narrationFailureSession.getSnapshot();
assert.equal(narrationSnapshot.explanation, null);
assert.equal(narrationSnapshot.explanationLoading, false);
assert.equal(narrationSnapshot.explanationError, "Explanation request returned 502.");
assert.equal(
  narrationSnapshot.studyData.node.id,
  "python:app.py:run",
  "narration failure never removes parser evidence",
);
narrationFailureSession.dispose();
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL with `TypeError: adapter.fetchExplanation is not a function`.

- [ ] **Step 3: Add the state and the loader**

In `web/src/learnerSession.js`, add three fields to the initial `deriveSnapshot({...})` call — insert after `llmStatus: null,`:

```js
    explanation: null,
    explanationLoading: false,
    explanationError: "",
```

Add a controller after `let modeController = null;`:

```js
  let explanationController = null;
```

Replace `cancelStudy` with:

```js
  function cancelStudy() {
    abortController(studyController);
    studyController = null;
    abortController(explanationController);
    explanationController = null;
  }
```

Replace `loadStudy`'s opening so narration starts in parallel with the source read:

```js
  async function loadStudy(nodeId) {
    cancelStudy();
    studyController = new AbortController();
    const controller = studyController;
    commit({ studyData: null, studyError: "" });
    void loadExplanation(nodeId);
    try {
```

Add `loadExplanation` immediately after `cancelStudy`:

```js
  async function loadExplanation(nodeId) {
    abortController(explanationController);
    explanationController = new AbortController();
    const controller = explanationController;
    commit({ explanation: null, explanationError: "", explanationLoading: true });
    try {
      const explanation = await adapter.fetchExplanation(nodeId, snapshot.mode, {
        signal: controller.signal,
      });
      if (
        controller.signal.aborted ||
        snapshot.level !== LEVELS.STUDY ||
        snapshot.selectedNode?.id !== nodeId
      ) {
        return;
      }
      commit({ explanation, explanationLoading: false });
    } catch (requestError) {
      if (
        explanationController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError) &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({
          explanationError: errorMessage(requestError),
          explanationLoading: false,
        });
      }
    }
  }
```

Replace the `retreat` STUDY branch commit so narration clears with the panel:

```js
  function retreat() {
    if (snapshot.level === LEVELS.STUDY) {
      cancelStudy();
      commit({
        selectedNode: null,
        level: LEVELS.SYSTEM,
        studyData: null,
        studyError: "",
        explanation: null,
        explanationError: "",
        explanationLoading: false,
      });
    } else if (snapshot.level === LEVELS.SYSTEM) {
      commit({ level: LEVELS.GALAXY });
    }
  }
```

Replace `setLanguageFocus`'s clearing branch:

```js
  function setLanguageFocus(language) {
    const previousNodeId = snapshot.selectedNode?.id;
    commit({ languageFocus: language });
    if (previousNodeId && snapshot.selectedNode?.id !== previousNodeId) {
      cancelStudy();
      commit({
        studyData: null,
        studyError: "",
        explanation: null,
        explanationError: "",
        explanationLoading: false,
      });
    }
  }
```

Replace `setMode`'s tail so a voice change re-narrates the open node — the whole method now reads:

```js
  async function setMode(mode) {
    if (mode !== "easy" && mode !== "expert") return undefined;
    const previous = snapshot.mode;
    if (mode === previous) return undefined;
    abortController(modeController);
    modeController = new AbortController();
    const controller = modeController;
    commit({ mode });
    try {
      await adapter.putMode(mode, { signal: controller.signal });
    } catch (requestError) {
      if (modeController === controller && !isAbortError(requestError)) {
        commit({ mode: previous });
      }
      return undefined;
    }
    if (snapshot.level === LEVELS.STUDY && snapshot.selectedNode) {
      return loadExplanation(snapshot.selectedNode.id);
    }
    return undefined;
  }
```

Add `explanationController` to the `dispose()` loop array and null it afterwards:

```js
      pickerController,
      modeController,
      explanationController,
    ]) {
```

```js
    modeController = null;
    explanationController = null;
```

- [ ] **Step 4: Add both adapter methods**

In `createHttpLearnerSessionAdapter`, insert after `fetchLlmStatus`:

```js
    fetchExplanation(nodeId, mode, options = {}) {
      return request(
        `/api/node/${encodeURIComponent(nodeId)}/explanation?mode=${encodeURIComponent(mode)}`,
        "Explanation request",
        options,
      );
    },
```

In `createInMemoryLearnerSessionAdapter`, add `explanations = {},` to the destructured options (after `llmStatus = null,`) and insert after `fetchLlmStatus`:

```js
    async fetchExplanation(nodeId, mode, options = {}) {
      throwIfAborted(options.signal);
      return requiredFixture(explanations, `${nodeId}:${mode}`, "explanation");
    },
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: `learner-session contracts passed`, exit 0.

- [ ] **Step 6: Build and commit**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): load the grounded explanation alongside every study open"
```

---

### Task 5: Session — reset project

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: `POST /api/picker/reset` from Task 1.
- Produces: event `RESET_PROJECT`; adapter method `resetProject(options)`. `resetProject()` rethrows on failure (mirroring `submitCheck`) so the header's confirm control can show the message inline instead of replacing the whole app with an error screen.

- [ ] **Step 1: Write the failing test**

In `web/scripts/check_learner_session.mjs`, append to the picker-phase block — insert immediately after `assert.equal(pickerSnapshot.graph, graph);` and before `pickerSession.dispose();`:

```js
await pickerSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await pickerSession.dispatch({ type: "RESET_PROJECT" });
pickerSnapshot = pickerSession.getSnapshot();
assert.equal(pickerSnapshot.status, "picking", "reset returns the learner to the picker");
assert.equal(pickerSnapshot.graph, null);
assert.equal(pickerSnapshot.region, null);
assert.equal(pickerSnapshot.selectedNode, null);
assert.equal(pickerSnapshot.level, LEVELS.GALAXY);
assert.equal(pickerSnapshot.studiedNodeIds.size, 0);
assert.equal(pickerSnapshot.explanation, null);
assert.equal(pickerSnapshot.llmStatus, null);
assert.equal(pickerSnapshot.picker.path, "/home/u");

await pickerSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
assert.equal(pickerSession.getSnapshot().status, "ready", "a project can be re-picked");
```

Add this standalone block just above the `function makeGraph(` declaration:

```js
// A refused reset must surface to the caller and leave the project bound.
const refusedResetAdapter = createInMemoryLearnerSessionAdapter({ graph });
const refusedResetSession = createLearnerSession({
  adapter: {
    ...refusedResetAdapter,
    resetProject() {
      throw new Error("Project reset returned 409.");
    },
  },
  clock,
});
await refusedResetSession.start();
await assert.rejects(
  () => refusedResetSession.dispatch({ type: "RESET_PROJECT" }),
  /Project reset returned 409\./,
);
assert.equal(
  refusedResetSession.getSnapshot().graph,
  graph,
  "a refused reset leaves the bound project exactly as it was",
);
refusedResetSession.dispose();
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL with `Error: Unknown learner-session event: RESET_PROJECT`.

- [ ] **Step 3: Implement the reset flow**

In `web/src/learnerSession.js`, add a controller after `let explanationController = null;`:

```js
  let resetController = null;
```

Add the function immediately after `selectProject`:

```js
  async function resetProject() {
    abortController(resetController);
    resetController = new AbortController();
    const controller = resetController;
    // Deliberately uncaught, like submitCheck: a refused reset is a control
    // failure the header shows inline, not a reason to blank the galaxy.
    await adapter.resetProject({ signal: controller.signal });
    if (controller.signal.aborted) return snapshot;
    cancelStudy();
    commit({
      graph: null,
      region: null,
      selectedNode: null,
      level: LEVELS.GALAXY,
      studyData: null,
      studyError: "",
      explanation: null,
      explanationError: "",
      explanationLoading: false,
      showChart: false,
      studiedNodeIds: new Set(),
      showChecks: false,
      checkData: null,
      checkError: "",
      entrypointDismissed: false,
      entrypointError: "",
      litRegionId: null,
      languageFocus: "all",
      llmStatus: null,
      picker: null,
    });
    return start();
  }
```

Add the case to `dispatch`, immediately after the `SELECT_PROJECT` case:

```js
      case "RESET_PROJECT":
        return resetProject();
```

Add `resetController` to the `dispose()` loop array and null it afterwards:

```js
      modeController,
      explanationController,
      resetController,
    ]) {
```

```js
    explanationController = null;
    resetController = null;
```

- [ ] **Step 4: Add both adapter methods**

In `createHttpLearnerSessionAdapter`, insert after `fetchExplanation`:

```js
    resetProject(options = {}) {
      return request("/api/picker/reset", "Project reset", {
        ...options,
        method: "POST",
      });
    },
```

In `createInMemoryLearnerSessionAdapter`, insert after `selectProject`:

```js
    async resetProject(options = {}) {
      throwIfAborted(options.signal);
      if (pickerPhase) pickerPhase.selected = false;
      return { state: "unpicked" };
    },
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: `learner-session contracts passed`, exit 0.

- [ ] **Step 6: Build and commit**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): release the bound project and return to the picker in-app"
```

---

### Task 6: Session — re-openable Home

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: nothing new from the backend.
- Produces: event `CHANGE_HOME`; derived snapshot field `entrypointOpen` (bool, computed in `deriveSnapshot`, never stored). `entrypointDismissed` is now seeded from the loaded graph (`true` when a Home is already selected) and set `true` on a successful `SELECT_ENTRYPOINT`.

> **Resolved spec ambiguity.** "Change Home" needs the picker to open even when a Home *is* selected, but the binding contract's Phase A state list adds no field for it. Resolution: no new stored field. `entrypointDismissed` becomes the single "Home is settled for now" flag — seeded from `graph.selected_entrypoint` on load, set `true` on selection, set `false` by `CHANGE_HOME` — and `deriveSnapshot` exposes the derived `entrypointOpen` the renderer reads. This reproduces today's behaviour exactly on first load.

- [ ] **Step 1: Write the failing test**

In `web/scripts/check_learner_session.mjs`, replace the two existing entrypoint assertions

```js
await session.dispatch({ type: "SELECT_ENTRYPOINT", nodeId: "python:app.py:run" });
assert.equal(session.getSnapshot().graph, understoodGraph);
await session.dispatch({ type: "DISMISS_ENTRYPOINT" });
assert.equal(session.getSnapshot().entrypointDismissed, true);
```

with:

```js
assert.equal(
  session.getSnapshot().entrypointOpen,
  true,
  "a graph with no selected Home opens the picker on load",
);
await session.dispatch({ type: "SELECT_ENTRYPOINT", nodeId: "python:app.py:run" });
assert.equal(session.getSnapshot().graph, understoodGraph);
assert.equal(
  session.getSnapshot().entrypointOpen,
  false,
  "choosing Home closes the picker",
);
await session.dispatch({ type: "DISMISS_ENTRYPOINT" });
assert.equal(session.getSnapshot().entrypointDismissed, true);
assert.equal(session.getSnapshot().entrypointOpen, false);

await session.dispatch({ type: "ADVANCE", node: graph.regions[0] });
await session.dispatch({ type: "CHANGE_HOME" });
let homeSnapshot = session.getSnapshot();
assert.equal(homeSnapshot.entrypointOpen, true, "Change Home reopens the picker");
assert.equal(homeSnapshot.level, LEVELS.GALAXY, "Home is a galaxy-level decision");
assert.equal(homeSnapshot.selectedNode, null);
assert.equal(homeSnapshot.showChart, false);
await session.dispatch({ type: "DISMISS_ENTRYPOINT" });
```

Add this standalone block just above the `function makeGraph(` declaration:

```js
// A project that already carries a Home must not greet the learner with the
// picker; the affordance is opt-in from the header instead.
const homeGraph = { ...makeGraph(), selected_entrypoint: "python:app.py:run" };
const seededHomeSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph: homeGraph }),
  clock,
});
await seededHomeSession.start();
assert.equal(seededHomeSession.getSnapshot().entrypointDismissed, true);
assert.equal(seededHomeSession.getSnapshot().entrypointOpen, false);
await seededHomeSession.dispatch({ type: "CHANGE_HOME" });
assert.equal(seededHomeSession.getSnapshot().entrypointOpen, true);
seededHomeSession.dispose();
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL with `AssertionError [ERR_ASSERTION]: a graph with no selected Home opens the picker on load` — `undefined !== true`.

- [ ] **Step 3: Seed, close, reopen, and derive**

In `web/src/learnerSession.js`, replace the success commit inside `loadProjectGraph`:

```js
      commit({
        status: "ready",
        graph,
        region: defaultRegion(graph),
        error: "",
        entrypointDismissed: Boolean(graph.selected_entrypoint),
      });
      await loadPreferences(controller, requestLifecycle);
```

In `selectEntrypoint`, replace the success commit:

```js
      if (!controller.signal.aborted) {
        commit({
          graph,
          region: defaultRegion(graph),
          entrypointError: "",
          entrypointDismissed: true,
        });
      }
```

Add the case to `dispatch`, immediately after the `DISMISS_ENTRYPOINT` case:

```js
      case "CHANGE_HOME":
        cancelStudy();
        commit({
          entrypointDismissed: false,
          entrypointError: "",
          level: LEVELS.GALAXY,
          selectedNode: null,
          showChart: false,
          studyData: null,
          studyError: "",
          explanation: null,
          explanationError: "",
          explanationLoading: false,
        });
        return undefined;
```

In `deriveSnapshot`, add the derived field to the returned object — insert after `focusedGraph,`:

```js
    entrypointOpen: Boolean(graph) && !state.entrypointDismissed,
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: `learner-session contracts passed`, exit 0.

- [ ] **Step 5: Build and commit**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): let the learner reopen the Home picker at any time"
```

---

### Task 7: Session — hover node

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: state `hoverNodeId` (string|null, initial `null`); event `HOVER_NODE` (`{nodeId}`). Hover clears automatically whenever level or region changes.

- [ ] **Step 1: Write the failing test**

In `web/scripts/check_learner_session.mjs`, add this standalone block just above the `function makeGraph(` declaration:

```js
// Hover is view state: it must survive redundant events cheaply and must never
// outlive the view it described.
const hoverSession = createLearnerSession({
  adapter: createInMemoryLearnerSessionAdapter({ graph }),
  clock,
});
await hoverSession.start();
assert.equal(hoverSession.getSnapshot().hoverNodeId, null);
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: "app.py" });
assert.equal(hoverSession.getSnapshot().hoverNodeId, "app.py");
const hoverBefore = hoverSession.getSnapshot();
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: "app.py" });
assert.equal(
  hoverSession.getSnapshot(),
  hoverBefore,
  "a repeated hover does not produce a new snapshot",
);
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: null });
assert.equal(hoverSession.getSnapshot().hoverNodeId, null);
await hoverSession.dispatch({ type: "HOVER_NODE", nodeId: "app.py" });
await hoverSession.dispatch({ type: "ADVANCE", node: graph.regions[0] });
assert.equal(
  hoverSession.getSnapshot().hoverNodeId,
  null,
  "moving between levels drops the stale hover target",
);
hoverSession.dispose();
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL with `Error: Unknown learner-session event: HOVER_NODE`.

- [ ] **Step 3: Add the field, the event, and the navigation clear**

In `web/src/learnerSession.js`, add the field to the initial `deriveSnapshot({...})` call — insert after `explanationError: "",`:

```js
    hoverNodeId: null,
```

Replace `commit` so navigation clears hover without adding a third `deriveSnapshot` pass:

```js
  function commit(patch, { preserveChecks = false } = {}) {
    const previous = snapshot;
    let next = deriveSnapshot({ ...previous, ...patch });
    const navigationChanged =
      next.level !== previous.level || next.region?.id !== previous.region?.id;
    if (navigationChanged) {
      const navigationPatch = { hoverNodeId: null };
      if (!preserveChecks) {
        abortController(checksController);
        abortController(submissionController);
        checksController = null;
        submissionController = null;
        navigationPatch.showChecks = false;
        navigationPatch.checkData = null;
        navigationPatch.checkError = "";
      }
      next = deriveSnapshot({ ...next, ...navigationPatch });
    }
    snapshot = Object.freeze(next);
    for (const listener of listeners) listener();
  }
```

Add the case to `dispatch`, immediately after the `SET_MODE` case:

```js
      case "HOVER_NODE":
        // Pointer motion fires this constantly; only a real change may notify.
        if (snapshot.hoverNodeId !== (event.nodeId ?? null)) {
          commit({ hoverNodeId: event.nodeId ?? null });
        }
        return undefined;
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: `learner-session contracts passed`, exit 0.

- [ ] **Step 5: Build and commit**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs codemble/web_dist
git commit -s -m "feat(web): track the hovered node in learner-session view state"
```

---

### Task 8: Extract the study-panel module (no behaviour change)

**Files:**
- Create: `web/src/StudyPanel.jsx`
- Modify: `web/src/App.jsx:495-689` (remove the moved components), `web/src/App.jsx:1-13` (imports)
- Test: none — this is a pure move; verified by `npm run check` building and by running the app.

**Interfaces:**
- Consumes: `conceptTitle` from `./graphData.js`.
- Produces: `export function StudyPanel({ node, study, error, onSelectNode })` — identical props and rendering to the current `App.jsx` implementation.

- [ ] **Step 1: Create the module with the moved components**

Create `web/src/StudyPanel.jsx`:

```jsx
import { conceptTitle } from "./graphData.js";

export function StudyPanel({ node, study, error, onSelectNode }) {
  const explanation = study?.explanation;
  return (
    <aside className="study-preview" aria-label="Selected source structure" aria-busy={!study && !error}>
      <header className="study-preview__header">
        <p className="study-preview__path">{node.file}:{node.lineno}</p>
        <h1>{node.name}</h1>
        <dl>
          <div><dt>Kind</dt><dd>{node.kind}</dd></div>
          <div><dt>Span</dt><dd>{node.loc} lines</dd></div>
          <div><dt>Calls in</dt><dd>{node.centrality}</dd></div>
          <div><dt>Resolution</dt><dd>{node.partial ? "Partial parse" : "Parser-proven"}</dd></div>
        </dl>
      </header>

      {error ? (
        <section className="study-notice" role="alert">
          <h2>Study data did not load.</h2>
          <p>{error} The parser map is still available.</p>
        </section>
      ) : null}
      {!study && !error ? <p className="study-loading">Reading parser evidence…</p> : null}
      {study ? (
        <div className="study-content">
          {node.partial ? (
            <section className="partial-study" role="status">
              <h2>Unchartable beyond this source.</h2>
              <p>The language parser reported a syntax error, so Codemble kept the file visible but did not invent structures or relationships inside it.</p>
            </section>
          ) : null}
          <SourceExcerpt source={study.source} />
          <LensNotes lens={study.lens} language={node.language} />
          <Explanation explanation={explanation} node={node} onSelectNode={onSelectNode} />
        </div>
      ) : null}
    </aside>
  );
}

function LensNotes({ lens, language }) {
  if (!lens?.length) return null;
  return (
    <section className="lens-study" aria-labelledby="lens-heading">
      <div className="study-section-heading">
        <h2 id="lens-heading">{conceptTitle(language)} lens</h2>
        <span>{lens.length} detected</span>
      </div>
      <div className="lens-notes">
        {lens.map((note) => (
          <article className="lens-note" key={`${note.concept}-${note.line}-${note.snippet}`}>
            <div>
              <h3>{note.title}</h3>
              <Citation citation={note.citation} fallbackLine={note.line} />
            </div>
            <div>
              <p>{note.note}</p>
              <code>{note.snippet}</code>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SourceExcerpt({ source }) {
  return (
    <section className="source-study" aria-labelledby="source-heading">
      <div className="study-section-heading">
        <h2 id="source-heading">Real source</h2>
        <span>{source.file}:{source.start_line}–{source.end_line}</span>
      </div>
      <ol className="source-code" start={source.start_line} aria-label={`Source excerpt from ${source.file}`}>
        {source.lines.map((line) => (
          <li key={line.number} id={`source-L${line.number}`} data-line={line.number}>
            <code>{line.text || " "}</code>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Explanation({ explanation, node, onSelectNode }) {
  if (!explanation) return null;
  if (explanation.status === "no_key") {
    return (
      <section className="study-notice" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">Structure works without a model.</h2>
        <p>{explanation.message}</p>
        <p>Only explanation prose is unavailable; the source and parser evidence above remain authoritative.</p>
      </section>
    );
  }
  if (explanation.status === "error") {
    return (
      <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">The explanation was withheld.</h2>
        <p>{explanation.message}</p>
        <p>Codemble will not display provider output that falls outside parser evidence.</p>
      </section>
    );
  }
  if (explanation.status === "partial") {
    return (
      <section className="study-notice" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">Narration stays off for partial source.</h2>
        <p>{explanation.message}</p>
      </section>
    );
  }
  return (
    <section className="grounded-explanation" aria-labelledby="explanation-heading">
      <div className="study-section-heading">
        <h2 id="explanation-heading">Grounded explanation</h2>
        <span>{explanation.cached ? "Local cache" : explanation.provider}</span>
      </div>
      <p>
        {explanation.summary.text}{" "}
        <Citation citation={explanation.summary.citation} fallbackLine={node.lineno} />
      </p>
      <h3>Walkthrough</h3>
      <ul className="evidence-list">
        {explanation.walkthrough.map((item) => (
          <li key={`${item.citation}-${item.text}`}>
            <p>{item.text}</p>
            <Citation citation={item.citation} fallbackLine={item.line} />
          </li>
        ))}
      </ul>
      {explanation.relationships.length ? (
        <>
          <h3>Parser relationships</h3>
          <ul className="evidence-list">
            {explanation.relationships.map((item) => (
              <li key={`${item.node_id}-${item.text}`}>
                <strong>{item.certain ? item.node_id : `Possible: ${item.node_id}`}</strong>
                <p>{item.text}</p>
                <button
                  className="source-citation source-citation--button"
                  type="button"
                  onClick={() => onSelectNode(item.node_id)}
                >
                  Study {item.citation}
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

function Citation({ citation, fallbackLine }) {
  const parsedLine = Number(citation.split(":").at(-1)) || fallbackLine;
  return <a className="source-citation" href={`#source-L${parsedLine}`}>{citation}</a>;
}
```

- [ ] **Step 2: Delete the moved components from `App.jsx`**

In `web/src/App.jsx`, delete the `StudyPanel`, `LensNotes`, `SourceExcerpt`, `Explanation`, and `Citation` function declarations entirely (currently lines 495-558 and 597-689). Keep `StarChart` — it stays in `App.jsx`.

- [ ] **Step 3: Import the module in `App.jsx`**

Replace the import block at the top of `web/src/App.jsx` with:

```jsx
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { GalaxyCanvas } from "./GalaxyCanvas.jsx";
import { StudyPanel } from "./StudyPanel.jsx";
import {
  LEVELS,
  conceptTitle,
  defaultRegion,
  languageLabel,
} from "./graphData.js";
import {
  createHttpLearnerSessionAdapter,
  createLearnerSession,
} from "./learnerSession.js";
```

- [ ] **Step 4: Verify the build and run the app**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …` with no unresolved-import error.

Run: `codemble ./tests/fixtures/sampleproj`, open the printed URL, click a system then a planet.
Expected: the study panel renders exactly as before the move — path, name, the four `dl` fields, source lines, lens notes.

- [ ] **Step 5: Commit**

```bash
git add web/src/App.jsx web/src/StudyPanel.jsx codemble/web_dist
git commit -s -m "refactor(web): move the study-panel family into its own module"
```

---

### Task 9: Study panel — structural summary, narration, and provider guidance

**Files:**
- Modify: `web/src/StudyPanel.jsx`, `web/src/App.jsx` (pass the new props), `web/src/styles.css`
- Test: none available (pure presentation) — verified by running the app, with and without a provider key.

**Interfaces:**
- Consumes: `study.structural` (`{easy, expert}`) from `GET /api/node/{id}/study`; session `mode`, `explanation`, `explanationLoading`, `explanationError`, `llmStatus` from Tasks 3-4.
- Produces: `export function StudyPanel({ node, study, error, mode, explanation, explanationLoading, explanationError, llmStatus, onSelectNode, onRetryNarration })`.

- [ ] **Step 1: Replace `StudyPanel`'s body with the spec's section order**

In `web/src/StudyPanel.jsx`, replace the whole `StudyPanel` function with:

```jsx
export function StudyPanel({
  node,
  study,
  error,
  mode,
  explanation,
  explanationLoading,
  explanationError,
  llmStatus,
  onSelectNode,
  onRetryNarration,
}) {
  return (
    <aside className="study-preview" aria-label="Selected source structure" aria-busy={!study && !error}>
      <header className="study-preview__header">
        <p className="study-preview__path">{node.file}:{node.lineno}</p>
        <h1>{node.name}</h1>
        <dl>
          <div><dt>Kind</dt><dd>{node.kind}</dd></div>
          <div><dt>Span</dt><dd>{node.loc} lines</dd></div>
          <div>
            <dt>{mode === "easy" ? "Used by" : "Calls in"}</dt>
            <dd>{node.centrality}</dd>
          </div>
          <div><dt>Resolution</dt><dd>{node.partial ? "Partial parse" : "Parser-proven"}</dd></div>
        </dl>
      </header>

      {error ? (
        <section className="study-notice" role="alert">
          <h2>Study data did not load.</h2>
          <p>{error} The parser map is still available.</p>
          <button className="check-primary" type="button" onClick={() => onSelectNode(node.id)}>
            Try again
          </button>
        </section>
      ) : null}
      {!study && !error ? <p className="study-loading">Reading parser evidence…</p> : null}
      {study ? (
        <div className="study-content">
          <StructuralSummary structural={study.structural} mode={mode} />
          <Explanation
            explanation={explanation}
            loading={explanationLoading}
            error={explanationError}
            llmStatus={llmStatus}
            mode={mode}
            node={node}
            onSelectNode={onSelectNode}
            onRetry={onRetryNarration}
          />
          <SourceExcerpt source={study.source} />
          <LensNotes lens={study.lens} language={node.language} />
        </div>
      ) : null}
    </aside>
  );
}

function StructuralSummary({ structural, mode }) {
  if (!structural) return null;
  return (
    <section className="structural-summary" aria-labelledby="structural-heading">
      <div className="study-section-heading">
        <h2 id="structural-heading">
          {mode === "easy" ? "What this is" : "Structural summary"}
        </h2>
        <span>No model needed</span>
      </div>
      <p>{structural[mode] ?? structural.easy}</p>
    </section>
  );
}
```

Note the static `partial-study` block is gone: the partial-parse notice now rides the explanation block (gap G19), and the structural summary above it already states the partial parse in both voices, so no moment exists without that signal.

- [ ] **Step 2: Replace `Explanation` with its loading, error, and guidance states**

In `web/src/StudyPanel.jsx`, replace the whole `Explanation` function with:

```jsx
function Explanation({
  explanation,
  loading,
  error,
  llmStatus,
  mode,
  node,
  onSelectNode,
  onRetry,
}) {
  if (loading) {
    return (
      <p className="study-loading">
        {mode === "easy"
          ? "Asking your model to explain this in plain language…"
          : "Requesting a grounded narration for this structure…"}
      </p>
    );
  }
  if (error) {
    return (
      <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">The explanation request failed.</h2>
        <p>{error}</p>
        <p>Every fact above and below this block came from the parser and is unaffected.</p>
        <button className="check-primary" type="button" onClick={onRetry}>
          Try again
        </button>
      </section>
    );
  }
  if (!explanation) return null;
  if (explanation.status === "no_key") {
    return <ProviderGuidance message={explanation.message} llmStatus={llmStatus} mode={mode} />;
  }
  if (explanation.status === "error") {
    return (
      <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">The explanation was withheld.</h2>
        <p>{explanation.message}</p>
        <p>Codemble will not display provider output that falls outside parser evidence.</p>
        <button className="check-primary" type="button" onClick={onRetry}>
          Try again
        </button>
      </section>
    );
  }
  if (explanation.status === "partial") {
    return (
      <section className="study-notice" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">Narration stays off for partial source.</h2>
        <p>{explanation.message}</p>
      </section>
    );
  }
  return (
    <section className="grounded-explanation" aria-labelledby="explanation-heading">
      <div className="study-section-heading">
        <h2 id="explanation-heading">
          {mode === "easy" ? "In plain language" : "Grounded explanation"}
        </h2>
        <span>{explanation.cached ? "Local cache" : explanation.provider}</span>
      </div>
      <p>
        {explanation.summary.text}{" "}
        <Citation citation={explanation.summary.citation} fallbackLine={node.lineno} />
      </p>
      <h3>{mode === "easy" ? "Line by line" : "Walkthrough"}</h3>
      <ul className="evidence-list">
        {explanation.walkthrough.map((item) => (
          <li key={`${item.citation}-${item.text}`}>
            <p>{item.text}</p>
            <Citation citation={item.citation} fallbackLine={item.line} />
          </li>
        ))}
      </ul>
      {explanation.relationships.length ? (
        <>
          <h3>{mode === "easy" ? "How it fits in" : "Parser relationships"}</h3>
          <ul className="evidence-list">
            {explanation.relationships.map((item) => (
              <li key={`${item.node_id}-${item.text}`}>
                <strong>{item.certain ? item.node_id : `Possible: ${item.node_id}`}</strong>
                <p>{item.text}</p>
                <button
                  className="source-citation source-citation--button"
                  type="button"
                  onClick={() => onSelectNode(item.node_id)}
                >
                  Study {item.citation}
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

function ProviderGuidance({ message, llmStatus, mode }) {
  const ollama = llmStatus?.ollama ?? null;
  return (
    <section className="study-notice" aria-labelledby="explanation-heading">
      <h2 id="explanation-heading">
        {mode === "easy"
          ? "The plain-language write-up needs a model."
          : "No narration provider is configured."}
      </h2>
      <p>{message}</p>
      {ollama ? (
        <p>
          {ollama.running
            ? `Ollama is already running on this machine. Set CODEMBLE_PROVIDER=ollama and CODEMBLE_OLLAMA_MODEL=${ollama.recommended}, then restart Codemble to narrate without sending code anywhere.`
            : `Want to stay fully local? Install Ollama, run "ollama pull ${ollama.recommended}" (or ${ollama.fallback} on a smaller machine), set CODEMBLE_PROVIDER=ollama, then restart Codemble.`}
        </p>
      ) : null}
      <p>
        Everything else on this panel is parser evidence and works without any
        model at all.
      </p>
    </section>
  );
}
```

- [ ] **Step 3: Pass the new props from `App.jsx`**

In `web/src/App.jsx`, replace the whole `const { … } = state;` destructuring block with this one — the seven new fields are `entrypointOpen`, `explanation`, `explanationError`, `explanationLoading`, `hoverNodeId`, `llmStatus`, and `mode`:

```jsx
  const {
    chart,
    checkData,
    checkError,
    entrypointDismissed,
    entrypointError,
    entrypointOpen,
    error,
    explanation,
    explanationError,
    explanationLoading,
    focusedGraph,
    focusedStudiedCount,
    graph,
    hoverNodeId,
    languageFocus,
    languageOptions,
    level,
    litRegionId,
    llmStatus,
    mode,
    picker,
    projectName,
    region,
    selectedNode,
    showChart,
    showChecks,
    status,
    studyData,
    studyError,
  } = state;
```

`entrypointDismissed` is still destructured here because the current render guard reads it. Task 11 swaps that guard to `entrypointOpen` and deletes this binding.

Then replace the `<StudyPanel …/>` element with:

```jsx
          <StudyPanel
            node={selectedNode}
            study={studyData}
            error={studyError}
            mode={mode}
            explanation={explanation}
            explanationLoading={explanationLoading}
            explanationError={explanationError}
            llmStatus={llmStatus}
            onSelectNode={(nodeId) =>
              session.dispatch({ type: "SELECT_STUDY_NODE", nodeId })
            }
            onRetryNarration={() =>
              session.dispatch({ type: "SELECT_STUDY_NODE", nodeId: selectedNode.id })
            }
          />
```

- [ ] **Step 4: Swap the dead partial-parse styles for the structural-summary styles**

In `web/src/styles.css`, delete this whole block (currently lines 526-545) — Step 1 removed the only markup that used it:

```css
.partial-study {
  padding: var(--cm-space-md);
  border-inline-start: 2px solid var(--cm-route-possible);
  background: var(--cm-ground);
}

.partial-study h2,
.partial-study p {
  margin: 0;
}

.partial-study h2 {
  font-family: var(--cm-font-display);
  font-size: var(--cm-text-lg);
}

.partial-study p {
  margin-block-start: var(--cm-space-sm);
  color: var(--cm-ink-2);
}
```

In its place, insert:

```css
.structural-summary p {
  max-width: 62ch;
  margin: var(--cm-space-sm) 0 0;
  color: var(--cm-ink);
}

.load-state .check-primary,
.study-notice .check-primary {
  justify-self: start;
  margin-block-start: var(--cm-space-md);
}
```

- [ ] **Step 5: Verify by running the app, both with and without a key**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

Run: `env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u CODEMBLE_PROVIDER codemble ./tests/fixtures/sampleproj`, open a planet.
Expected: the structural summary renders instantly at the top; below it the no-key guidance names the real recommended Ollama model from `/api/llm/status`; source and lens still render below.

Run: `ANTHROPIC_API_KEY=… codemble ./tests/fixtures/sampleproj`, open a planet.
Expected: "Requesting a grounded narration…" appears, then the grounded explanation with `file:line` citations. Toggle nothing; re-open the same node — the heading shows "Local cache".

- [ ] **Step 6: Commit**

```bash
git add web/src/StudyPanel.jsx web/src/App.jsx web/src/styles.css codemble/web_dist
git commit -s -m "feat(web): render the Tier 0 summary, narration, and provider guidance in study"
```

---

### Task 10: Study panel — the Connections section

**Files:**
- Modify: `web/src/StudyPanel.jsx`, `web/src/styles.css`
- Test: none available (pure presentation of the already-fetched `neighbors` list) — verified by running the app.

**Interfaces:**
- Consumes: `study.neighbors` — each item is `{node_id, name, kind, file, line, citation, relationship, certain, direction, observed_line}` from `StudyService._neighbors`.
- Produces: `Connections`, `ConnectionGroup`, `MiniConstellation` inside `web/src/StudyPanel.jsx`. Clicking a row calls `onSelectNode(item.node_id)`.

- [ ] **Step 1: Add the components**

In `web/src/StudyPanel.jsx`, insert these functions immediately after `StructuralSummary`:

```jsx
const STRIP_LIMIT = 8;

function Connections({ neighbors, node, mode, onSelectNode }) {
  const items = neighbors ?? [];
  const inbound = items.filter((item) => item.direction === "inbound");
  const outbound = items.filter((item) => item.direction === "outbound");
  return (
    <section className="connections" aria-labelledby="connections-heading">
      <div className="study-section-heading">
        <h2 id="connections-heading">
          {mode === "easy" ? "What this connects to" : "Parser connections"}
        </h2>
        <span>
          {items.length} parser {items.length === 1 ? "relationship" : "relationships"}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="study-loading">
          {mode === "easy"
            ? "Nothing in your code reaches this yet, and it does not reach anything else."
            : "The parser observed no relationship into or out of this structure."}
        </p>
      ) : (
        <>
          <MiniConstellation inbound={inbound} outbound={outbound} node={node} />
          <ConnectionGroup
            title={mode === "easy" ? "Uses this" : "Inbound"}
            items={inbound}
            mode={mode}
            onSelectNode={onSelectNode}
          />
          <ConnectionGroup
            title={mode === "easy" ? "This uses" : "Outbound"}
            items={outbound}
            mode={mode}
            onSelectNode={onSelectNode}
          />
        </>
      )}
    </section>
  );
}

function ConnectionGroup({ title, items, mode, onSelectNode }) {
  if (!items.length) return null;
  return (
    <>
      <h3>{title}</h3>
      <ul className="connection-list">
        {items.map((item) => (
          <li key={`${item.direction}-${item.node_id}`}>
            <button type="button" onClick={() => onSelectNode(item.node_id)}>
              <span className="connection-name">{item.name}</span>
              <span className="connection-meta">
                {relationWords(item, mode)} · {certaintyWords(item, mode)}
              </span>
              <span className="source-citation">{item.citation}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function relationWords(item, mode) {
  if (item.relationship === "import") {
    if (item.direction === "inbound") return mode === "easy" ? "brings this in" : "import · inbound";
    return mode === "easy" ? "this brings it in" : "import · outbound";
  }
  if (item.direction === "inbound") return mode === "easy" ? "calls this" : "call · inbound";
  return mode === "easy" ? "this calls it" : "call · outbound";
}

function certaintyWords(item, mode) {
  if (item.certain) return mode === "easy" ? "certain" : "certain";
  if (item.relationship === "import") {
    return mode === "easy" ? "possible link, not certain" : "possible import";
  }
  return mode === "easy" ? "possible link, not certain" : "possible call";
}

function MiniConstellation({ inbound, outbound, node }) {
  // Presentation of the already-fetched neighbour list, like the star chart's
  // bars — no layout is computed here that the backend does not already own.
  const left = inbound.slice(0, STRIP_LIMIT);
  const right = outbound.slice(0, STRIP_LIMIT);
  const height = Math.max(left.length, right.length, 1) * 22 + 16;
  const middle = height / 2;
  const seat = (index, count) => ((index + 1) * height) / (count + 1);
  return (
    <svg
      className="mini-constellation"
      viewBox={`0 0 280 ${height}`}
      role="img"
      aria-label={`${inbound.length} inbound and ${outbound.length} outbound parser relationships for ${node.name}`}
    >
      {left.map((item, index) => (
        <line
          key={`in-line-${item.node_id}`}
          x1="26"
          y1={seat(index, left.length)}
          x2="132"
          y2={middle}
          strokeDasharray={item.certain ? undefined : "3 3"}
        />
      ))}
      {right.map((item, index) => (
        <line
          key={`out-line-${item.node_id}`}
          x1="148"
          y1={middle}
          x2="254"
          y2={seat(index, right.length)}
          strokeDasharray={item.certain ? undefined : "3 3"}
        />
      ))}
      {left.map((item, index) => (
        <circle key={`in-dot-${item.node_id}`} cx="22" cy={seat(index, left.length)} r="4" />
      ))}
      {right.map((item, index) => (
        <circle key={`out-dot-${item.node_id}`} cx="258" cy={seat(index, right.length)} r="4" />
      ))}
      <circle className="mini-constellation__self" cx="140" cy={middle} r="6" />
    </svg>
  );
}
```

- [ ] **Step 2: Render it between narration and source**

In `web/src/StudyPanel.jsx`, inside the `study ? (…)` branch of `StudyPanel`, insert the element between `<Explanation … />` and `<SourceExcerpt … />`:

```jsx
          <Connections
            neighbors={study.neighbors}
            node={node}
            mode={mode}
            onSelectNode={onSelectNode}
          />
```

- [ ] **Step 3: Add the styles**

In `web/src/styles.css`, insert immediately after the `.structural-summary p { … }` rule:

```css
.mini-constellation {
  width: 100%;
  max-width: 22rem;
  height: auto;
  margin-block-start: var(--cm-space-md);
}

.mini-constellation line {
  stroke: var(--cm-hairline);
  stroke-width: 1;
}

.mini-constellation circle {
  fill: var(--cm-ink-3);
}

.mini-constellation__self {
  fill: var(--cm-orbit);
}

.connections h3 {
  margin: var(--cm-space-lg) 0 0;
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.connection-list {
  margin: var(--cm-space-xs) 0 0;
  padding: 0;
  list-style: none;
  border-block-start: 1px solid var(--cm-hairline);
}

.connection-list button {
  display: grid;
  width: 100%;
  min-height: 52px;
  gap: var(--cm-space-2xs);
  padding: var(--cm-space-sm) 0;
  border: 0;
  border-block-end: 1px solid var(--cm-hairline);
  background: transparent;
  color: var(--cm-ink);
  cursor: pointer;
  text-align: start;
}

.connection-name {
  overflow-wrap: anywhere;
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-sm);
}

.connection-meta {
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}

@media (hover: hover) and (pointer: fine) {
  .connection-list button:hover .connection-name {
    color: var(--cm-orbit);
  }
}
```

- [ ] **Step 4: Verify by running the app**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

Run: `codemble ./tests/fixtures/sampleproj`, open the `app` system, then `main`.
Expected: a Connections section between narration and source, showing inbound/outbound rows with `file:line` citations; clicking a row navigates to that node's study. Any uncertain relationship reads "possible call" (expert) or "possible link, not certain" (easy) and its strip line is dashed.

Run the same at a 320 px viewport width.
Expected: the strip scales down, rows remain 52 px tall, nothing overflows horizontally.

- [ ] **Step 5: Commit**

```bash
git add web/src/StudyPanel.jsx web/src/styles.css codemble/web_dist
git commit -s -m "feat(web): show parser connections with direction, certainty, and citations"
```

---

### Task 11: Header — mode toggle, switch project, change Home

**Files:**
- Modify: `web/src/App.jsx` (header, `EntrypointPicker`), `web/src/styles.css`
- Test: none available (pure presentation over Tasks 3/5/6 state) — verified by running the app.

**Interfaces:**
- Consumes: session `mode`, `entrypointOpen`, events `SET_MODE`, `RESET_PROJECT`, `CHANGE_HOME`.
- Produces: `ModeToggle({ mode, onChange })` and `SwitchProject({ onConfirm })` inside `App.jsx`; `EntrypointPicker` gains a `selectedEntrypoint` prop.

- [ ] **Step 1: Regroup the header and add the controls**

In `web/src/App.jsx`, replace the whole `<header className="instrument-rail"> … </header>` block with:

```jsx
      <header className="instrument-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <strong>Codemble</strong>
            <span>{projectName}</span>
          </div>
        </div>
        <p className="location" aria-live="polite">
          {showChart
            ? "Star chart"
            : level === LEVELS.GALAXY
              ? `Galaxy · Home ${graph.selected_entrypoint ? (defaultRegion(graph)?.id ?? "unresolved") : "unselected"}`
              : region.id}
          {!showChart && level === LEVELS.STUDY && selectedNode ? ` / ${selectedNode.name}` : ""}
          {languageFocus !== "all" ? ` · ${languageLabel(languageFocus)} focus` : ""}
        </p>
        <div className="rail-actions">
          {showChart ? (
            <button
              className="rail-action"
              type="button"
              onClick={() => session.dispatch({ type: "HIDE_CHART" })}
            >
              Return to galaxy
            </button>
          ) : level !== LEVELS.GALAXY ? (
            <button
              className="rail-action"
              type="button"
              onClick={() => session.dispatch({ type: "RETREAT" })}
            >
              {level === LEVELS.STUDY ? "Return to system" : "Return to galaxy"}
            </button>
          ) : (
            <button
              className="rail-action"
              type="button"
              onClick={() => session.dispatch({ type: "SHOW_CHART" })}
            >
              Star chart
            </button>
          )}
          {graph.entrypoint_candidates.length ? (
            <button
              className="rail-action"
              type="button"
              onClick={() => session.dispatch({ type: "CHANGE_HOME" })}
            >
              Change Home
            </button>
          ) : null}
          <SwitchProject onConfirm={() => session.dispatch({ type: "RESET_PROJECT" })} />
        </div>
        <div className="rail-controls">
          <LanguageFocus
            options={languageOptions}
            value={languageFocus}
            onChange={(language) =>
              session.dispatch({ type: "SET_LANGUAGE_FOCUS", language })
            }
          />
          <ModeToggle
            mode={mode}
            onChange={(next) => session.dispatch({ type: "SET_MODE", mode: next })}
          />
        </div>
      </header>
```

- [ ] **Step 2: Add the two new components**

In `web/src/App.jsx`, insert both functions immediately after the existing `LanguageFocus` declaration:

```jsx
function ModeToggle({ mode, onChange }) {
  const options = [
    { id: "easy", label: "Easy", hint: "Plain language" },
    { id: "expert", label: "Expert", hint: "Full terminology" },
  ];
  return (
    <nav className="language-focus mode-toggle" aria-label="Explanation mode">
      <span className="language-focus__label">Mode</span>
      <div>
        {options.map((option) => (
          <button
            type="button"
            key={option.id}
            aria-label={`${option.label} mode: ${option.hint}`}
            aria-pressed={mode === option.id}
            title={option.hint}
            onClick={() => onChange(option.id)}
          >
            <span>{option.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}

function SwitchProject({ onConfirm }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");

  async function confirm() {
    setBusy(true);
    setFailure("");
    try {
      await onConfirm();
    } catch (resetError) {
      setFailure(resetError.message);
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <button className="rail-action" type="button" onClick={() => setConfirming(true)}>
        Switch project
      </button>
    );
  }
  return (
    <div className="switch-project" role="group" aria-label="Switch project">
      <p>Progress is saved per project, so this galaxy comes back lit.</p>
      {failure ? (
        <p className="switch-project__error" role="alert">
          {failure}
        </p>
      ) : null}
      <div>
        <button className="rail-action" type="button" disabled={busy} onClick={confirm}>
          {busy ? "Releasing…" : "Switch"}
        </button>
        <button
          className="rail-action"
          type="button"
          disabled={busy}
          onClick={() => {
            setConfirming(false);
            setFailure("");
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Make the Home picker re-openable and fix the zero-candidate copy (G20)**

In `web/src/App.jsx`, delete the now-unused `entrypointDismissed,` line from the `const { … } = state;` destructuring block, then replace the `EntrypointPicker` render guard with the derived flag:

```jsx
        {entrypointOpen && level === LEVELS.GALAXY ? (
          <EntrypointPicker
            candidates={graph.entrypoint_candidates}
            nodes={graph.nodes}
            selectedEntrypoint={graph.selected_entrypoint}
            error={entrypointError}
            onSelect={(nodeId) =>
              session.dispatch({ type: "SELECT_ENTRYPOINT", nodeId })
            }
            onContinue={() => session.dispatch({ type: "DISMISS_ENTRYPOINT" })}
          />
        ) : null}
```

Then replace the `EntrypointPicker` function's signature, its second paragraph, and its continue button:

```jsx
function EntrypointPicker({ candidates, nodes, selectedEntrypoint, error, onSelect, onContinue }) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return (
    <aside className="entrypoint-picker" aria-labelledby="entrypoint-heading">
      <p>Home calibration</p>
      <h1 id="entrypoint-heading">
        {candidates.length ? "Where does your project start?" : "No clear entrypoint found."}
      </h1>
      <p>
        {candidates.length
          ? "The parser found ranked candidates but cannot choose one honestly. Select the structure you run."
          : "No file here declares a startup structure the parser recognises, and Codemble will not guess one. Explore the map without Home — every system, check, explanation, and lens note still works."}
      </p>
      {candidates.length ? (
        <div className="entrypoint-candidates">
          {candidates.map((candidate) => {
            const node = nodeById.get(candidate);
            return (
              <button type="button" key={candidate} onClick={() => onSelect(candidate)}>
                <span>{candidate}</span>
                <small>{node?.file}:{node?.lineno} · parser rank {node?.entrypoint_rank}</small>
              </button>
            );
          })}
        </div>
      ) : null}
      {error ? <p className="entrypoint-error" role="alert">{error}</p> : null}
      <button className="entrypoint-continue" type="button" onClick={onContinue}>
        {selectedEntrypoint ? "Keep current Home" : "Explore without Home"}
      </button>
    </aside>
  );
}
```

- [ ] **Step 4: Add the header layout styles**

In `web/src/styles.css`, insert immediately after the `.rail-action[data-state="success"] { … }` rule:

```css
.rail-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: end;
  gap: var(--cm-space-sm);
  grid-column: 2;
  grid-row: 1;
}

.rail-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--cm-space-md);
  grid-column: 1 / -1;
  grid-row: 3;
  min-width: 0;
}

.switch-project {
  display: grid;
  gap: var(--cm-space-xs);
  padding: var(--cm-space-sm);
  border: 1px solid var(--cm-hairline);
  border-radius: var(--cm-radius);
  background: var(--cm-ground-2);
}

.switch-project p {
  max-width: 26ch;
  margin: 0;
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}

.switch-project__error {
  color: var(--cm-error) !important;
}

.switch-project > div {
  display: flex;
  gap: var(--cm-space-xs);
}
```

- [ ] **Step 5: Verify by running the app**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

Run: `codemble` (bare, picker flow), pick `tests/fixtures/sampleproj`.
Expected: header shows Star chart / Change Home / Switch project, with Focus and Mode below. Toggling Mode changes the study panel's headings and the check prompt wording. "Change Home" reopens the calibration panel from any level and returns the camera to the galaxy. "Switch project" asks for confirmation, then lands back on the picker; re-selecting the same folder restores the lit systems.

Run: `codemble ./tests/fixtures/sampleproj` (path flow), click Switch project → Switch.
Expected: the picker appears (Task 1 gave this server a `PickerConfig`).

Run the same at a 320 px viewport width, keyboard only (Tab/Enter).
Expected: every control is reachable and has a visible focus ring; nothing overflows horizontally.

- [ ] **Step 6: Commit**

```bash
git add web/src/App.jsx web/src/styles.css codemble/web_dist
git commit -s -m "feat(web): add mode, switch project, and change Home to the instrument rail"
```

---

### Task 12: Checks — correct-answer affirmation, and the G17/G21 copy fixes

**Files:**
- Modify: `web/src/App.jsx` (`CheckPanel`, `StarChart`), `web/src/styles.css`
- Test: none available (pure presentation over the shipped submit payload) — verified by running the app.

**Interfaces:**
- Consumes: `submitCheck` result `{correct, message, answer_labels, evidence, region_understood}` (shipped) and `check.prompt_voices` (shipped); session `mode`.
- Produces: no new exports.

- [ ] **Step 1: Hold the affirmation outside the per-question reset**

In `web/src/App.jsx`, replace `CheckPanel`'s state block, `choose`, and `submit` with:

```jsx
  const [selected, setSelected] = useState(() => new Set());
  const [feedback, setFeedback] = useState(null);
  const [affirmation, setAffirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    setSelected(new Set());
    setFeedback(null);
    setSubmitError("");
  }, [current?.id]);

  function choose(optionId, multiple) {
    setAffirmation("");
    setSelected((existing) => {
      if (!multiple) return new Set([optionId]);
      const next = new Set(existing);
      if (next.has(optionId)) next.delete(optionId);
      else next.add(optionId);
      return next;
    });
  }

  async function submit(event) {
    event.preventDefault();
    if (!current || selected.size === 0) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const result = await onSubmit(current.id, [...selected]);
      // A correct answer advances `current`, which resets `feedback` — so the
      // affirmation lives in its own slot or it would vanish before it is read.
      if (result.correct) {
        setAffirmation(result.message);
        setFeedback(null);
      } else {
        setAffirmation("");
        setFeedback(result);
      }
    } catch (requestError) {
      setSubmitError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }
```

- [ ] **Step 2: Render the affirmation, the mode-voiced prompt, and the G17 copy**

In `web/src/App.jsx`, replace `CheckPanel`'s zero-check block with:

```jsx
      {suite && !suite.region_understood && suite.checks.length === 0 ? (
        <div className="check-state">
          <h2>No safe check yet.</h2>
          <p>
            Every question here is answered by the parser graph, and this region
            has no certain relationship Codemble can build one from. It stays dim
            rather than lighting on a question that would prove nothing. Import
            this module somewhere, or call something inside it, and its checks
            appear.
          </p>
        </div>
      ) : null}
```

Replace the `<form className="active-check" …>` contents' progress row, legend, and feedback block:

```jsx
        <form className="active-check" onSubmit={submit}>
          <div className="check-progress">
            <span>Check {passed + 1} of {suite.checks.length}</span>
            <progress value={passed} max={suite.checks.length} />
          </div>
          {affirmation ? (
            <p className="check-affirmation" role="status">
              <span aria-hidden="true">✦</span> {affirmation}
            </p>
          ) : null}
          <fieldset>
            <legend>{current.prompt_voices?.[mode] ?? current.prompt}</legend>
            {current.multiple ? <p>Select every answer supported by the graph.</p> : null}
            <div className="check-options">
              {current.options.map((option) => (
                <label key={option.id}>
                  <input
                    type={current.multiple ? "checkbox" : "radio"}
                    name={`answer-${current.id}`}
                    value={option.id}
                    checked={selected.has(option.id)}
                    onChange={() => choose(option.id, current.multiple)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {feedback && !feedback.correct ? (
            <div className="check-feedback" role="status">
              <strong>{feedback.message}</strong>
              <span>Parser answer: {feedback.answer_labels.join(", ")}</span>
              <span>Evidence: {feedback.evidence.join(", ")}</span>
            </div>
          ) : null}
          <button className="check-primary" type="submit" disabled={!selected.size || submitting}>
            {submitting ? "Checking parser evidence…" : "Check answer"}
          </button>
        </form>
```

Add `mode` to `CheckPanel`'s signature:

```jsx
function CheckPanel({ suite, error, mode, onClose, onSubmit }) {
```

and pass it where `CheckPanel` is rendered in `App`:

```jsx
          <CheckPanel
            suite={checkData}
            error={checkError}
            mode={mode}
            onClose={() => session.dispatch({ type: "CLOSE_CHECKS" })}
            onSubmit={(checkId, selectedIds) =>
              session.dispatch({ type: "SUBMIT_CHECK", checkId, selectedIds })
            }
          />
```

- [ ] **Step 3: Label studied counts "this session" (G21)**

In `web/src/App.jsx`, inside `StarChart`, replace the studied `dt` in the intro list:

```jsx
          <div><dt>Studied this session</dt><dd>{studiedCount}</dd></div>
```

and the concept-row studied `dt`:

```jsx
              <div><dt>Studied (session)</dt><dd>{item.studied_nodes}/{item.nodes}</dd></div>
```

- [ ] **Step 4: Style the affirmation**

In `web/src/styles.css`, insert immediately after the `.check-feedback span { … }` rule:

```css
.check-affirmation {
  display: flex;
  align-items: baseline;
  gap: var(--cm-space-xs);
  margin: 0 0 var(--cm-space-lg);
  padding-inline-start: var(--cm-space-sm);
  border-inline-start: 2px solid var(--cm-star);
  color: var(--cm-star-high);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}
```

- [ ] **Step 5: Verify by running the app**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

Run: `codemble ./tests/fixtures/sampleproj`, open the `app` system, click "Prove understanding", answer one check correctly.
Expected: an amber "Correct. That answer is fixed by the parser graph." line appears above the next question and disappears the moment a new option is chosen. Answering wrongly still shows the parser answer and evidence. Switching Mode to Easy rewords the question via `prompt_voices`.

Run the same on a region with no checks (create one: a module nothing imports and which calls nothing).
Expected: the "No safe check yet." panel explains why it stays dim instead of lighting.

- [ ] **Step 6: Commit**

```bash
git add web/src/App.jsx web/src/styles.css codemble/web_dist
git commit -s -m "feat(web): affirm correct check answers and explain why a region stays dim"
```

---

### Task 13: Canvas — arrows, link tooltips, and hover/select highlighting

**Files:**
- Modify: `web/src/graphData.js`, `web/src/GalaxyCanvas.jsx`, `web/src/App.jsx` (props)
- Test: `web/scripts/check_graph_data.mjs` (for `linkLabel`); the canvas itself is verified by running the app.

**Interfaces:**
- Consumes: session `hoverNodeId` and the `HOVER_NODE` event from Task 7.
- Produces: `export function linkLabel(link)` in `web/src/graphData.js`; `GalaxyCanvas` gains `hoverNodeId` and `onHoverNode` props; `readPalette` gains a `faded` entry.

> **Resolved spec ambiguity — "dashed uncertainty".** `3d-force-graph` exposes no `linkLineDash` (dashing is a 2D-only `force-graph` feature), so the 3D canvas cannot draw dashes without a `linkThreeObject` material rewrite that Phase B's bloom/halo work will replace anyway. **Resolution: in 3D, uncertainty keeps its existing real channel — the `--cm-route-possible` colour — and the legend (Task 12/14) describes exactly that, never a dash the canvas does not draw. The dashed encoding ships where SVG can honestly render it: the study panel's mini constellation (Task 10) and Phase B's 2D Map layer.**

- [ ] **Step 1: Write the failing `linkLabel` test**

In `web/scripts/check_graph_data.mjs`, add `linkLabel` to the import list:

```js
import {
  buildConceptChart,
  languageFocusGraph,
  linkLabel,
  projectLanguageOptions,
} from "../src/graphData.js";
```

and append these assertions just above the final `console.log` line:

```js
assert.equal(
  linkLabel({ src: "app.main", dst: "pkg.run", kind: "call", certain: true, lineno: 12 }),
  "app.main → pkg.run · call · certain · line 12",
);
assert.equal(
  linkLabel({ src: "app.main", dst: "pkg.run", kind: "call", certain: false, lineno: 12 }),
  "app.main → pkg.run · call · possible call · line 12",
  "an approximate call edge must say so in its tooltip",
);
assert.equal(
  linkLabel({ src: "app", dst: "pkg", kind: "import", certain: false, lineno: 3 }),
  "app → pkg · import · possible import · line 3",
);
assert.equal(
  linkLabel({ src: "app", dst: "pkg", weight: 2, certain: true }),
  "app → pkg · import route · certain · 2 imports",
  "galaxy-level region edges carry a weight instead of a line number",
);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web && node scripts/check_graph_data.mjs`
Expected: FAIL with `TypeError: linkLabel is not a function`.

- [ ] **Step 3: Add `linkLabel`**

In `web/src/graphData.js`, insert immediately after `nodeLabel`:

```js
export function linkLabel(link) {
  const relation =
    link.kind === "import" ? "import" : link.kind === "call" ? "call" : "import route";
  const certainty = link.certain
    ? "certain"
    : relation === "call"
      ? "possible call"
      : "possible import";
  const weight =
    typeof link.weight === "number"
      ? ` · ${link.weight} ${link.weight === 1 ? "import" : "imports"}`
      : "";
  const where = typeof link.lineno === "number" ? ` · line ${link.lineno}` : "";
  return `${link.src} → ${link.dst} · ${relation} · ${certainty}${weight}${where}`;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd web && node scripts/check_graph_data.mjs`
Expected: `graph-data contracts passed`, exit 0.

- [ ] **Step 5: Add the faded palette entry**

In `web/src/GalaxyCanvas.jsx`, inside `readPalette`'s returned object, insert after `routePossible`:

```js
    // Everything outside the current selection or hover recedes to this;
    // it stays a plain value so readPalette can hand WebGL real rgb().
    faded: value("--cm-hairline-soft"),
```

- [ ] **Step 6: Add the highlight machinery, arrows, and tooltips**

In `web/src/GalaxyCanvas.jsx`, replace the component signature and add the refs and accessors:

```jsx
export function GalaxyCanvas({
  graph,
  level,
  region,
  selectedNode,
  hoverNodeId,
  onHoverNode,
  onAdvance,
  onRetreat,
}) {
  const hostRef = useRef(null);
  const rendererRef = useRef(null);
  const advanceRef = useRef(onAdvance);
  const retreatRef = useRef(onRetreat);
  const hoverRef = useRef(onHoverNode);
  const highlightRef = useRef({ activeId: null, neighborIds: new Set() });
  const wheelLockRef = useRef(0);
```

Replace the ref-syncing effect with:

```jsx
  useEffect(() => {
    advanceRef.current = onAdvance;
    retreatRef.current = onRetreat;
    hoverRef.current = onHoverNode;
  }, [onAdvance, onRetreat, onHoverNode]);
```

Add these three accessor definitions immediately after that effect. They are captured once by the mount effect and read `highlightRef` at call time, so they never go stale:

```jsx
  function nodeColor(node) {
    const { activeId, neighborIds } = highlightRef.current;
    if (!activeId) return node.color;
    if (node.id === activeId) return palette.orbit;
    return neighborIds.has(node.id) ? node.color : palette.faded;
  }

  function linkColor(link) {
    const { activeId, neighborIds } = highlightRef.current;
    const base = link.certain ? palette.route : palette.routePossible;
    if (!activeId) return base;
    const source = linkEndId(link.source);
    const target = linkEndId(link.target);
    if (source === activeId || target === activeId) return palette.orbit;
    return neighborIds.has(source) && neighborIds.has(target) ? base : palette.faded;
  }

  function linkWidth(link) {
    const { activeId } = highlightRef.current;
    const base = Math.min(2.2, 0.45 + (link.weight ?? 1) * 0.25);
    if (!activeId) return base;
    const source = linkEndId(link.source);
    const target = linkEndId(link.target);
    return source === activeId || target === activeId ? base + 0.9 : base;
  }
```

Replace the renderer construction chain inside the mount effect with:

```jsx
      const renderer = ForceGraph3D()(host)
        .backgroundColor(palette.ground)
        .showNavInfo(false)
        .enableNavigationControls(false)
        .warmupTicks(0)
        .cooldownTicks(0)
        .nodeId("id")
        .nodeLabel(nodeLabel)
        .nodeVal("val")
        .nodeColor(nodeColor)
        .nodeRelSize(NODE_REL_SIZE)
        .nodeResolution(8)
        .nodeOpacity(0.82)
        .nodeThreeObject((node) => makeMarker(node, palette))
        .nodeThreeObjectExtend(true)
        .linkColor(linkColor)
        .linkLabel(linkLabel)
        .linkOpacity(0.32)
        .linkWidth(linkWidth)
        .linkHoverPrecision(4)
        .linkDirectionalArrowRelPos(1)
        .linkDirectionalArrowColor(linkColor)
        .onNodeHover((node) => {
          host.style.cursor = node ? "pointer" : "default";
          hoverRef.current(node?.id ?? null);
        })
        .onNodeClick((node) => advanceRef.current(node));
```

Replace the `data`/`level` effect so the study level no longer dims the whole scene and arrows appear below the galaxy:

```jsx
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer
      .nodeResolution(data.nodes.length >= 900 ? 4 : 8)
      // Arrows only where an edge means a direction the learner can act on.
      .linkDirectionalArrowLength(level === LEVELS.GALAXY ? 0 : 3.2)
      .graphData(data);
    if (level === LEVELS.GALAXY) {
      renderer.cameraPosition({ x: 0, y: 105, z: 310 }, { x: 0, y: 0, z: 0 }, CAMERA_DURATION);
    } else {
      renderer.cameraPosition({ x: 0, y: 52, z: 150 }, { x: 0, y: 0, z: 0 }, CAMERA_DURATION);
    }
    setFocusedIndex(0);
  }, [data, level]);
```

Add the highlight effect immediately after it:

```jsx
  useEffect(() => {
    // At study level the selection is the subject even without a pointer, so
    // its connections stay legible instead of the scene fading to 0.16.
    const activeId = hoverNodeId ?? (level === LEVELS.STUDY ? selectedNode?.id ?? null : null);
    const neighborIds = new Set();
    if (activeId) {
      for (const link of data.links) {
        const source = linkEndId(link.source);
        const target = linkEndId(link.target);
        if (source === activeId) neighborIds.add(target);
        if (target === activeId) neighborIds.add(source);
      }
    }
    highlightRef.current = { activeId, neighborIds };
    const renderer = rendererRef.current;
    if (!renderer) return;
    // Re-setting an accessor to itself is the library's own refresh idiom.
    renderer
      .nodeColor(renderer.nodeColor())
      .linkColor(renderer.linkColor())
      .linkWidth(renderer.linkWidth())
      .linkDirectionalArrowColor(renderer.linkDirectionalArrowColor());
  }, [data, hoverNodeId, level, selectedNode?.id]);
```

Add the helper at the bottom of the module, just above `toRenderableColor`:

```jsx
// The force layout swaps link endpoints from ids to node objects in place.
function linkEndId(end) {
  return typeof end === "object" && end !== null ? end.id : end;
}
```

Update the import line at the top of the file:

```jsx
import { LEVELS, galaxyData, linkLabel, nodeLabel, systemData } from "./graphData.js";
```

- [ ] **Step 7: Wire the props from `App.jsx`**

In `web/src/App.jsx`, replace the `<GalaxyCanvas … />` element with:

```jsx
        <GalaxyCanvas
          graph={focusedGraph}
          level={level}
          region={region}
          selectedNode={selectedNode}
          hoverNodeId={hoverNodeId}
          onHoverNode={(nodeId) => session.dispatch({ type: "HOVER_NODE", nodeId })}
          onAdvance={(node) => session.dispatch({ type: "ADVANCE", node })}
          onRetreat={() => session.dispatch({ type: "RETREAT" })}
        />
```

- [ ] **Step 8: Verify by running the app**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

Run: `codemble .` (this repository), enter the `codemble/checks/service.py` system.
Expected: call edges carry arrowheads; hovering an edge shows the `src → dst · call · certain|possible call · line N` tooltip; hovering a node turns its edges ruri, keeps its neighbours at full colour, and fades everything else. Open a planet (study level): the selected node and its connections stay legible while the rest of the system recedes — no all-over 0.16 dimming.

Run: `codemble . ` and append `?benchmark` to the URL on a ≥900-node scope.
Expected: `document.documentElement.dataset.codembleFps` still reports a value; no exception in the console.

- [ ] **Step 9: Commit**

```bash
git add web/src/graphData.js web/src/GalaxyCanvas.jsx web/src/App.jsx web/scripts/check_graph_data.mjs codemble/web_dist
git commit -s -m "feat(web): add edge arrows, link tooltips, and hover/select highlighting"
```

---

### Task 14: Complete legend, in-app retry, error boundary, and noscript

**Files:**
- Modify: `web/src/App.jsx` (legend, error branch), `web/src/main.jsx`, `web/index.html`, `web/src/styles.css`
- Test: none available (pure presentation) — verified by running the app.

**Interfaces:**
- Consumes: session `mode` from Task 3; `session.start()` (already exported).
- Produces: `AppErrorBoundary` class component in `web/src/main.jsx`.

- [ ] **Step 1: Complete the legend**

In `web/src/App.jsx`, replace the `<aside className="map-legend" …>` block with:

```jsx
        <aside className="map-legend" aria-label="Galaxy legend">
          <span>
            <i className="legend-dot legend-dot--dim legend-dot--small" />
            <i className="legend-dot legend-dot--dim" />
            Size · {mode === "easy" ? "how much code" : "lines of code"}
          </span>
          <span>
            <i className="legend-dot legend-dot--bright" />
            Brighter · {mode === "easy" ? "used more often" : "higher call centrality"}
          </span>
          <span>
            <i className="legend-dot legend-dot--dim" />
            Dim · {mode === "easy" ? "not proven yet" : "not understood"}
          </span>
          <span>
            <i className="legend-dot legend-dot--lit" />
            Amber · {mode === "easy" ? "you proved you understand it" : "understood"}
          </span>
          <span>
            <i className="legend-dot legend-dot--partial" />
            {mode === "easy" ? "Could not be read" : "Unchartable · syntax error"}
          </span>
          <span>
            <i className="legend-route" />
            {mode === "easy" ? "Certain connection" : "Parser edge · certain"}
          </span>
          <span>
            <i className="legend-route legend-route--possible" />
            {mode === "easy" ? "Possible connection" : "Possible relationship"}
          </span>
        </aside>
```

- [ ] **Step 2: Replace the "restart Codemble" dead end with in-app retry (G25)**

In `web/src/App.jsx`, replace the top-level error branch with:

```jsx
  if (error) {
    return (
      <main className="load-state" role="alert">
        <h1>The graph did not load.</h1>
        <p>{error}</p>
        <p>Your progress is stored on this machine and is not affected.</p>
        <button className="check-primary" type="button" onClick={() => session.start()}>
          Try again
        </button>
      </main>
    );
  }
```

- [ ] **Step 3: Add the legend styles**

In `web/src/styles.css`, replace the `.map-legend { … }` rule's `display: none;` line and `gap` line so the rule reads:

```css
.map-legend {
  position: absolute;
  z-index: var(--cm-z-raised);
  inset-inline-end: var(--cm-space-md);
  inset-block-start: var(--cm-space-md);
  display: none;
  grid-template-columns: repeat(2, auto);
  gap: var(--cm-space-2xs) var(--cm-space-md);
  padding: var(--cm-space-sm) var(--cm-space-md);
  border: 1px solid var(--cm-hairline);
  border-radius: var(--cm-radius);
  background: var(--cm-ground-2);
  color: var(--cm-ink-2);
  font-family: var(--cm-font-mono);
  font-size: var(--cm-text-xs);
}
```

Insert after the `.legend-dot--partial { … }` rule:

```css
.legend-dot--bright {
  background: var(--cm-ink-2);
}

.legend-dot--small {
  width: var(--cm-space-2xs);
  height: var(--cm-space-2xs);
}

.legend-route--possible {
  border-block-start-color: var(--cm-route-possible);
}
```

And change the reveal media query so the grid actually shows:

```css
@media (min-width: 60rem) {
  .map-legend {
    display: grid;
  }
}
```

- [ ] **Step 4: Add the error boundary**

In `web/src/main.jsx`, replace the React import and the render call:

```jsx
import { Component, StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.jsx";
import "./styles.css";

class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { message: "" };
  }

  static getDerivedStateFromError(error) {
    return { message: error instanceof Error ? error.message : String(error) };
  }

  componentDidCatch(error) {
    console.error("Codemble stopped rendering:", error);
  }

  render() {
    if (!this.state.message) return this.props.children;
    return (
      <main className="load-state" role="alert">
        <h1>The galaxy stopped rendering.</h1>
        <p>{this.state.message}</p>
        <p>Your progress is saved on this machine; reloading re-reads it.</p>
        <button
          className="check-primary"
          type="button"
          onClick={() => window.location.reload()}
        >
          Reload Codemble
        </button>
      </main>
    );
  }
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </StrictMode>,
);
```

- [ ] **Step 5: Add the `<noscript>` fallback**

In `web/index.html`, replace the `<body>` block with:

```html
  <body>
    <div id="root"></div>
    <noscript>
      <div style="max-width: 42rem; margin: 4rem auto; padding: 0 1.5rem; font-family: system-ui, sans-serif; color: #eef2fa; background: #070b1c;">
        <h1 style="font-size: 1.5rem;">Codemble needs JavaScript.</h1>
        <p>
          The galaxy, the study panel, and the checks are all drawn in the
          browser from your locally parsed project. Enable JavaScript for this
          localhost page and reload. Nothing is sent anywhere either way.
        </p>
      </div>
    </noscript>
    <script type="module" src="/src/main.jsx"></script>
  </body>
```

The inline styles are deliberate: with scripting off, `styles.css` never loads because `main.jsx` imports it.

- [ ] **Step 6: Verify by running the app**

Run: `cd web && npm run check`
Expected: both check scripts pass, then `✓ built in …`.

Run: `codemble ./tests/fixtures/sampleproj` at a ≥60rem viewport.
Expected: the legend shows all seven rows in two columns, and its wording changes with the Mode toggle.

Stop the server while the page is open, then reload.
Expected: "The graph did not load." with a working "Try again" button (which succeeds once the server is back) — no "Restart Codemble" instruction anywhere.

Disable JavaScript in the browser and reload.
Expected: the noscript block renders legibly.

- [ ] **Step 7: Commit**

```bash
git add web/src/App.jsx web/src/main.jsx web/src/styles.css web/index.html codemble/web_dist
git commit -s -m "feat(web): complete the legend and add in-app retry, an error boundary, and noscript"
```

---

### Task 15: Changelog and public documentation

**Files:**
- Modify: `CHANGELOG.md`
- Create: `docs-site/src/content/docs/study-panel.md`
- Modify: `docs-site/src/content/docs/the-galaxy.md`, `docs-site/src/content/docs/checks-and-lighting.md`, `docs-site/src/content/docs/star-chart.md`, `docs-site/astro.config.mjs`
- Test: `cd docs-site && npm run check`

**Interfaces:**
- Consumes: every behaviour shipped in Tasks 1-14.
- Produces: no code interfaces. Repo rule: a milestone that changes user-facing behaviour updates the relevant docs page(s) **and** the hand-authored sidebar in the same PR.

- [ ] **Step 1: Add the changelog entry**

In `CHANGELOG.md`, replace the `## [Unreleased]` line with:

```markdown
## [Unreleased]

### Added
- The study panel now shows what the parser knows before any model is asked: a
  plain-language or expert structural summary that needs no key, no network,
  and no provider.
- Grounded narration finally reaches the panel. The explanation endpoint had
  shipped but was never called, so the narration block always rendered empty.
- A Connections section lists every parser relationship into and out of the
  selected structure — direction, certainty, and a `file:line` citation per
  row — with a small diagram of callers, this structure, and callees. Clicking
  a row opens that structure's study.
- An Easy/Expert toggle in the header. Easy uses plain language for narration,
  check questions, panel labels, and the legend; Expert keeps full terminology.
  The choice persists and never touches graph truth, coordinates, progress, or
  how a check is scored.
- Switch project: a header control releases the current project and returns to
  the picker, so a second project no longer needs a terminal.
- Change Home: the entrypoint picker can be reopened at any time, and the Home
  you select is remembered for the next run of the same project.
- Guidance when no model is configured, including how to narrate entirely
  locally with Ollama, driven by what is actually installed and running.
- Correct check answers now get an affirmation, not just silence.
- A complete legend: size, brightness, amber-understood, unchartable files, and
  certain versus possible relationships.
- Edge arrowheads below the galaxy level, hover tooltips on every edge, and
  hover/selection highlighting that brightens the selected structure's
  connections and fades the rest.
- A `<noscript>` message and a React error boundary, so a render failure
  explains itself and offers a reload instead of showing a blank page.

### Changed
- The study panel leads with the structural summary and narration, then
  connections, then source and lens notes.
- The study level keeps the selected structure's connections visible instead of
  dimming the whole scene.
- A region with no safe check now explains that Codemble refuses to ask a
  question the graph cannot answer, rather than only stating that none exists.
- The zero-candidate Home screen no longer tells you to restart with a CLI
  flag; every option is in the app.
- The star chart labels studied counts "this session", which is what they have
  always measured.

### Fixed
- The partial-parse notice rode a code path that never executed; it now renders
  with the narration block, and the structural summary states it as well.
- A failed graph load offered only "Restart Codemble and reload this page"; it
  now retries in place.
```

- [ ] **Step 2: Create the study-panel docs page**

Create `docs-site/src/content/docs/study-panel.md`:

```markdown
---
title: The study panel
description: What the parser knows, what a model adds, and what happens when you have no key.
---

## Five sections, in order of certainty

Open a planet and the panel builds itself from the most certain evidence
outward:

1. **What this is** — a summary written from parser facts alone: kind, file and
   line, size, how many things use it, how many it uses, and how many of those
   links are possible rather than certain. No key, no network, no model.
2. **The explanation** — grounded narration from your configured provider, with
   a `file:line` citation on every claim. Codemble refuses to display provider
   output that names anything outside the parsed graph.
3. **Connections** — every relationship the parser observed into and out of this
   structure. Each row states direction, whether the relationship is certain or
   only possible, and where it was seen. Click any row to study that structure.
4. **Real source** — the exact lines, numbered, straight from your file.
5. **The language lens** — idiom notes anchored to constructs the parser
   actually detected.

Sections 1, 3, 4 and 5 never involve a model. If narration fails or is not
configured, they are all still there.

## Easy and Expert

The header's **Mode** toggle changes wording only:

| | Easy | Expert |
| --- | --- | --- |
| Narration | Short sentences, every term explained in place | Concise, assumes fluency |
| Check questions | "Which piece of code…" | "Which structure…" |
| Labels | "Used by", "Possible connection" | "Calls in", "possible call" |

Mode never changes the graph, the coordinates, your progress, or how a check is
scored. It is remembered per project.

## No key? Nothing important is missing

Codemble is bring-your-own-key. Without one, the panel says so and everything
except the narration prose keeps working.

To narrate without sending your code anywhere, use a local model:

```bash
ollama pull gemma4:12b
export CODEMBLE_PROVIDER=ollama
export CODEMBLE_OLLAMA_MODEL=gemma4:12b
```

The panel tells you whether Ollama is already running on this machine and which
model it recommends. Honest caveat: grounding validation catches an invented
identifier, not a wrong claim about a real one, and smaller local models make
that second kind of mistake more often.

## Partial parses

If a file has a syntax error, Codemble keeps it visible and refuses to invent
structure inside it. Narration stays off for that file, and both the structural
summary and the narration block say why.
```

- [ ] **Step 3: Update `the-galaxy.md`**

In `docs-site/src/content/docs/the-galaxy.md`, append these sections at the end of the file:

```markdown
## Reading the connections

Below the galaxy level, every edge carries an arrowhead pointing from caller to
callee. Hover an edge for its tooltip: the two structures, whether it is an
import or a call, whether the parser is certain, and the line it was seen on. A
relationship the parser could not prove reads "possible call" or "possible
import" and is drawn in the uncertainty colour — never as fact.

Hover or select a structure and its connections brighten to the interaction
blue while its neighbours hold their colour and everything else recedes. In the
study level the selected structure stays highlighted with its connections, so
the panel and the sky agree about what you are reading.

The legend in the corner names every encoding: size, brightness, amber for
understood, the unchartable colour for syntax-error files, and certain versus
possible relationships. In Easy mode it says the same things in plain language.

## Switching project and changing Home

**Switch project** in the header releases the current project and returns you to
the picker; progress is stored per project, so the galaxy comes back lit. This
works whether you started from the picker or passed a path.

**Change Home** reopens the entrypoint picker at any time. The Home you choose
is remembered for the next run of the same project, and a saved choice the
parser no longer ranks is dropped rather than restored.
```

- [ ] **Step 4: Update `checks-and-lighting.md`**

In `docs-site/src/content/docs/checks-and-lighting.md`, append at the end of the file:

```markdown
## Right answers say so

A correct answer is confirmed in place — "Correct. That answer is fixed by the
parser graph." — before the next question loads. A wrong answer still shows the
graph's answer and the evidence behind it.

## Why a region can stay dim forever

Every question Codemble asks is answered by the parser graph, and every question
must offer at least one wrong option. A region with no certain relationship
gives Codemble nothing to build a question from, so it stays dim and says so.
Lighting it anyway would mean the amber said something untrue about what you
understand. Import that module somewhere, or call something inside it, and its
checks appear.
```

- [ ] **Step 5: Update `star-chart.md`**

In `docs-site/src/content/docs/star-chart.md`, find the sentence describing the studied count and make the session scope explicit by appending this paragraph at the end of the file:

```markdown
"Studied" counts the structures you have opened **in this session** and resets
when you reload — that is deliberate. Opening a file is not evidence that you
understood it, so only "Understood", which comes from passing graph-derived
checks, is persisted.
```

- [ ] **Step 6: Add the sidebar entry**

In `docs-site/astro.config.mjs`, inside the `"Playing Codemble"` group, insert the new entry after "The galaxy":

```js
            { label: "The study panel", slug: "study-panel" },
```

so the group reads:

```js
        {
          label: "Playing Codemble",
          items: [
            { label: "The galaxy", slug: "the-galaxy" },
            { label: "The study panel", slug: "study-panel" },
            { label: "Checks & lighting", slug: "checks-and-lighting" },
            { label: "The star chart", slug: "star-chart" },
          ],
        },
```

- [ ] **Step 7: Verify the docs build**

Run: `cd docs-site && npm install && npm run check`
Expected: `Result (… files): - 0 errors, 0 warnings, 0 hints`.

Run: `cd docs-site && npm run build`
Expected: build completes; "The study panel" appears in the generated sidebar.

- [ ] **Step 8: Run every gate one final time**

Run: `pytest && ruff check .`
Expected: all tests pass, `All checks passed!`.

Run: `cd web && npm run check`
Expected: `graph-data contracts passed`, `learner-session contracts passed`, `✓ built in …`.

Run: `git status --short`
Expected: clean, or only `codemble/web_dist` changes — if so, `git add codemble/web_dist` and amend the previous frontend commit.

- [ ] **Step 9: Commit**

```bash
git add CHANGELOG.md docs-site/src/content/docs/study-panel.md docs-site/src/content/docs/the-galaxy.md docs-site/src/content/docs/checks-and-lighting.md docs-site/src/content/docs/star-chart.md docs-site/astro.config.mjs
git commit -s -m "docs: document the lit study panel, mode toggle, and in-app project controls"
```
