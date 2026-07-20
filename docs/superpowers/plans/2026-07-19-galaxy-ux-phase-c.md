# Galaxy UX overhaul — Phase C (scale) implementation plan

**For agentic workers:** REQUIRED SUB-SKILL — `superpowers:subagent-driven-development`.
Execute one `### Task N` per subagent, in order, with a review checkpoint between
tasks. Do not start a task before the previous task's final commit exists.

Spec: `docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md` (§5 scale
fixes, §8 Phase C).
Binding contract: `docs/superpowers/plans/2026-07-19-galaxy-ux-shared-contract.md`.
Phases A and B land before this plan. Assume they exist; do not re-plan them.

**Goal**

A learner points Codemble at a ~1,000-file project, watches five honest stages
tick past on a loading screen instead of staring at a frozen tab, and reaches an
interactive galaxy. Re-fetching the graph does not re-sort the world. The
over-cap prompt is actionable entirely in-app: clickable busiest-scope buttons
plus a typed path, both still jailed to `$HOME`. Progress for the bound project
can be cleared from inside the app. No parser output, check suite, or check
answer changes by a single byte.

**Architecture**

Parsing moves off the request thread into one `ParseJob` — a small state machine
that owns `idle | parsing | ready | error`, the five stages, the file counter,
the cancellation token, and the worker's failure-to-state translation. The job is
also the `ParseProgress` implementation handed to `ProjectParser`, so there is
one object to reason about and one lock.

The progress seam does **not** widen `LanguageAdapter`. `ProjectParser.parse`
gains an optional `progress` keyword; it binds a thread-scoped per-file hook for
the duration of the parse, and each adapter's private `_parse_file` helper calls
one module-level `note_file_parsed()`. That call site is also the cancellation
check point — one hook serves both needs, and it fires exactly between files.

Two measured cliffs are removed behind unchanged public signatures: a single
`_CheckIndex` pass replaces the per-region full-edge and full-node scans in
`checks/service.py`, and `_ProjectState` caches the serialized `/api/graph`
document, invalidated on light-up, entrypoint selection, and bind/unbind.

React stays a pure renderer. `LearnerSession` owns the poll loop; `App.jsx` gains
presentation only.

**Tech Stack**

Python 3.11+, FastAPI, `threading` (stdlib) — no multiprocessing, no new runtime
dependency. Vite + React 19, `3d-force-graph`. Tests: `pytest`, `ruff`, and the
plain-node scripts under `web/scripts/`.

---

## Global Constraints

Copied verbatim from the repo rules, the shared contract, and the spec. These
outrank every step below; if a step appears to require breaking one, stop and
report instead of proceeding.

- **Deterministic parse output is unchanged by progress reporting.** The same
  source must produce byte-identical graph JSON whether or not a `ParseProgress`
  is supplied. `note_file_parsed()` may only count and may only raise
  `ParseCancelled`; it may never influence what the parser emits.
- **Check suites are identical after the index change.** Every region's
  generated questions, options, option order, answer IDs, evidence, and check IDs
  must match today's output exactly, for every fixture. This is a pure
  performance change; the Correctness Contract makes any behaviour drift a
  top-severity bug.
- **The home jail and the Host-header allowlist stay.** Every picker path is
  resolved and checked against `picker.browse_root`; outside-jail paths keep
  returning 403. `TrustedHostMiddleware` stays wired with the same allowlist.
- **The `LanguageAdapter` public seam stays unchanged.** `discover`, `parse`,
  `parse_files`, and `concepts` keep their exact signatures. Nothing above the
  seam hardcodes a language.
- **`codemble/web_dist` is a committed build artifact.** Any task changing
  `web/src` must run `cd web && npm run build` and commit the resulting
  `codemble/web_dist` changes in the same commit.
- **`pytest` and `ruff check .` are CI gates.** Both must pass at every commit.
  Frontend: `cd web && npm run check`.
- **Correctness Contract.** Structure, layouts, hints, tree shapes, and check
  answers come from the parser or graph only. Uncertain relationships stay
  labelled "possible". The LLM narrates, never decides.
- **Conventional Commits with DCO sign-off** (`git commit -s`).
- Canvas colours must be plain `rgb()` values resolvable by `readPalette`, never
  `color-mix()`. (No canvas work in this phase; the rule still applies if a step
  touches `web/src/tokens.css`.)

### Contract extensions this phase requires (flag, do not silently widen)

The shared contract's Phase C rows cover the parse-progress work only. Gap G23
("no reset-progress control") is mapped to Phase C by spec §7 but has no contract
row. This plan therefore adds, and records in the Decision Log in Task 12:

| Addition | Where | Why |
| --- | --- | --- |
| `DELETE /api/progress` → `200 {"understood_regions": 0}` | Task 8 | G23 needs a backend; scoped to the bound project's own progress file |
| `CLEAR_PROGRESS` session event | Task 9 | the control must reach the session; confirm state stays local React state |
| `clearProgress(signal)` adapter method | Task 9 | both adapters implement it, matching the contract's adapter rule |

Everything else in this plan uses contract names exactly:
`POST /api/picker/reset`, `GET /api/picker/progress`, `parseProgress`,
`fetchParseProgress(signal)`, and the `202 {"state": "parsing"}` select response.

---

## File Structure

| File | Created / Modified | One responsibility |
| --- | --- | --- |
| `codemble/adapters/parse_progress.py` | **created** | The progress + cancellation seam: `ParseProgress` protocol, `ParseCancelled`, the thread-scoped `reporting_files` binder, and `note_file_parsed()` |
| `codemble/server/parse_job.py` | **created** | The parse state machine: `idle/parsing/ready/error`, five stages, file counter, cancellation token, worker crash → state |
| `codemble/adapters/project.py` | modified | `ProjectParser.parse(progress=...)` stage reporting; `scale_cap` 300 → 1000; `ProjectScaleError` message carries busiest scopes |
| `codemble/adapters/python_ast.py` | modified | one `note_file_parsed()` call at the end of `_parse_file` |
| `codemble/adapters/typescript_tree_sitter.py` | modified | one `note_file_parsed()` call at the end of `_parse_file` |
| `codemble/checks/service.py` | modified | `_CheckIndex` — one O(nodes + edges) pass; per-region generation reads only its own buckets |
| `codemble/progress/store.py` | modified | `ProgressStore.clear()` — forget this project's understood regions only |
| `codemble/server/app.py` | modified | 202 select + `GET /api/picker/progress` + reset cancellation + `DELETE /api/progress` + the `_ProjectState` graph-response cache |
| `codemble/server/runtime.py` | modified | `serve_project` prints the same five stages to the terminal |
| `codemble/cli.py` | modified | non-TTY scale error prints busiest-scope suggestions |
| `web/src/learnerSession.js` | modified | `parseProgress` state, the poll loop, `fetchParseProgress`/`clearProgress` on both adapters, 202 mapping, `CLEAR_PROGRESS` |
| `web/src/App.jsx` | modified | `LoadingScreen`, clickable scale suggestions + path field, reset-progress control |
| `web/src/styles.css` | modified | styles for the loading screen, scale actions, and the reset control |
| `web/scripts/check_learner_session.mjs` | modified | in-memory-adapter coverage for parse polling, parse failure + retry, cancellation, and progress clearing |
| `codemble/web_dist/**` | modified | committed production bundle rebuilt alongside `web/src` |
| `tests/test_parse_progress.py` | **created** | the seam: determinism with/without a reporter, per-file counting, cancellation raising |
| `tests/test_parse_job.py` | **created** | the state machine: thread completion, cancellation mid-parse, crash → error |
| `tests/fixtures/check_suites.json` | **created** | golden pin of today's check suites for both fixtures |
| `tests/test_checks.py` | modified | golden-pin comparison + single-edge-pass assertion |
| `tests/test_server.py` | modified | 202 select, progress endpoint, reset cancellation, graph cache invalidation, `DELETE /api/progress`, cap-independent scale test |
| `tests/test_smoke.py` | modified | cap-independent large-project test + `scale_cap == 1000` pin + suggestions in the non-TTY message |
| `tests/test_project_parser.py` | modified | `progress=` stage sequence assertions |
| `README.md`, `TESTING.md`, `CLAUDE.md`, `CHANGELOG.md` | modified | cap and behaviour documentation |
| `docs-site/src/content/docs/quickstart.md`, `installation.md`, `the-galaxy.md`, `checks-and-lighting.md` | modified | cap, loading screen, actionable scale prompt, reset-progress |
| `docs-site/src/content/docs/progress/m12-scale.md` | **created** | build log for this milestone |
| `docs-site/astro.config.mjs` | modified | hand-authored sidebar entry for the new build log |

---

## Tasks

### Task 1: The progress + cancellation seam

**Files:** `codemble/adapters/parse_progress.py` (new),
`codemble/adapters/project.py`, `codemble/adapters/python_ast.py`,
`codemble/adapters/typescript_tree_sitter.py`, `tests/test_parse_progress.py`
(new), `tests/test_project_parser.py`

**Interfaces:**

Produces:

```python
# codemble/adapters/parse_progress.py
class ParseCancelled(Exception): ...

class ParseProgress(Protocol):
    def stage(self, stage: str) -> None: ...
    def files_total(self, total: int) -> None: ...
    def file_parsed(self) -> None: ...          # may raise ParseCancelled

@contextmanager
def reporting_files(on_file: Callable[[], None] | None) -> Iterator[None]: ...
def note_file_parsed() -> None: ...
```

```python
# codemble/adapters/project.py
class ProjectParser:
    def parse(
        self,
        source: Path | ProjectIntake,
        *,
        entrypoint: str | None = None,
        explicit: bool = False,
        progress: ParseProgress | None = None,
    ) -> Graph: ...
```

Consumes: nothing new. `LanguageAdapter.parse_files` is called with its existing
signature; adapters learn about progress only through the module-level
`note_file_parsed()`.

Stage ownership, so nobody has to guess later:

| Stage | Covered work | Reported by |
| --- | --- | --- |
| `discovering` | `ProjectParser.intake` — filesystem walk, ownership, scale guard | `ProjectParser.parse` (path input) or the request handler (intake input) |
| `parsing` | per-file read + syntax parse in every adapter; `files_done`/`files_total` advance here and only here | `ProjectParser.parse` sets it; `note_file_parsed()` advances it |
| `resolving` | cross-file import/call/entrypoint/concept passes, `_compose_graphs`, `finalize_graph` | the counter flips it when `files_done == files_total`; `ProjectParser.parse` re-asserts it before composition |
| `checks` | `CheckService` suite generation + `StudyService` construction at bind | Task 3 (`_ProjectState.bind`) |
| `layout` | building and caching the `/api/graph` render document the galaxy draws from | Task 3 (`_ProjectState.bind`) |

- [ ] **Step 1:** Write the failing seam test.

  Create `tests/test_parse_progress.py`:

  ```python
  """The parse progress and cancellation seam."""

  from __future__ import annotations

  from pathlib import Path

  import pytest

  from codemble.adapters.parse_progress import (
      ParseCancelled,
      note_file_parsed,
      reporting_files,
  )
  from codemble.adapters.project import ProjectParser
  from codemble.adapters.python_ast import PythonAstAdapter

  FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
  POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


  class _Recorder:
      """A ParseProgress that records everything and never interferes."""

      def __init__(self) -> None:
          self.stages: list[str] = []
          self.total = 0
          self.files = 0

      def stage(self, stage: str) -> None:
          self.stages.append(stage)

      def files_total(self, total: int) -> None:
          self.total = total

      def file_parsed(self) -> None:
          self.files += 1


  def test_note_file_parsed_is_a_no_op_when_nobody_is_listening() -> None:
      note_file_parsed()


  def test_reporting_files_restores_the_previous_binding() -> None:
      outer: list[str] = []
      inner: list[str] = []
      with reporting_files(lambda: outer.append("outer")):
          with reporting_files(lambda: inner.append("inner")):
              note_file_parsed()
          note_file_parsed()

      assert inner == ["inner"]
      assert outer == ["outer"]


  def test_progress_reporting_never_changes_the_parsed_graph() -> None:
      parser = ProjectParser()
      recorder = _Recorder()

      quiet = parser.parse(FIXTURE)
      reported = parser.parse(FIXTURE, progress=recorder)

      assert reported.to_json() == quiet.to_json()
      assert reported.to_json() == PythonAstAdapter().parse(FIXTURE).to_json()


  def test_every_owned_file_is_counted_exactly_once() -> None:
      parser = ProjectParser()
      intake = parser.intake(POLYGLOT_FIXTURE)
      recorder = _Recorder()

      parser.parse(intake, progress=recorder)

      assert recorder.total == len(intake.files)
      assert recorder.files == recorder.total


  def test_stages_are_reported_in_the_contract_order() -> None:
      parser = ProjectParser()
      recorder = _Recorder()

      parser.parse(FIXTURE, progress=recorder)

      assert recorder.stages == ["discovering", "parsing", "resolving"]


  def test_a_cancelling_hook_stops_the_parse_between_files() -> None:
      class _Cancelling(_Recorder):
          def file_parsed(self) -> None:
              super().file_parsed()
              if self.files >= 2:
                  raise ParseCancelled("stop")

      recorder = _Cancelling()

      with pytest.raises(ParseCancelled):
          ProjectParser().parse(FIXTURE, progress=recorder)

      assert recorder.files == 2
  ```

- [ ] **Step 2:** Run it and see it fail.

  ```bash
  pytest tests/test_parse_progress.py -x -q
  ```

  Expected: collection error —
  `ModuleNotFoundError: No module named 'codemble.adapters.parse_progress'`.

- [ ] **Step 3:** Create the seam module.

  `codemble/adapters/parse_progress.py`:

  ```python
  """Per-file parse progress and cancellation, without widening the adapter seam.

  ``LanguageAdapter`` keeps its four public methods exactly as they are.  A
  parse that wants progress binds a hook for its own thread with
  ``reporting_files``; each adapter's private per-file helper calls
  ``note_file_parsed`` once per source file it finishes reading.  That single
  call site is also the only cancellation check point, so "between files" means
  exactly one place in each adapter.
  """

  from __future__ import annotations

  import threading
  from collections.abc import Callable, Iterator
  from contextlib import contextmanager
  from typing import Protocol, runtime_checkable

  _local = threading.local()


  class ParseCancelled(Exception):
      """A running parse was cancelled; no graph will be produced."""


  @runtime_checkable
  class ParseProgress(Protocol):
      """The reporting surface ``ProjectParser`` writes one parse's state to."""

      def stage(self, stage: str) -> None:
          """Report the stage now running."""

      def files_total(self, total: int) -> None:
          """Report how many source files this parse will read."""

      def file_parsed(self) -> None:
          """Report one finished file; raise ``ParseCancelled`` to stop."""


  @contextmanager
  def reporting_files(on_file: Callable[[], None] | None) -> Iterator[None]:
      """Bind ``on_file`` for this thread for the duration of one parse."""

      previous = getattr(_local, "on_file", None)
      _local.on_file = on_file
      try:
          yield
      finally:
          _local.on_file = previous


  def note_file_parsed() -> None:
      """Report one finished source file; a no-op when nobody is listening."""

      on_file = getattr(_local, "on_file", None)
      if on_file is not None:
          on_file()


  __all__ = [
      "ParseCancelled",
      "ParseProgress",
      "note_file_parsed",
      "reporting_files",
  ]
  ```

- [ ] **Step 4:** Call the hook from both adapters.

  In `codemble/adapters/python_ast.py`, add the import beside the existing
  adapter imports:

  ```python
  from codemble.adapters.parse_progress import note_file_parsed
  ```

  and replace the tail of `_parse_file` (currently `return _ParsedFile(...)`):

  ```python
      parsed = _ParsedFile(
          path=path,
          relative_path=relative.as_posix(),
          module=_module_name(relative, project_root),
          source=source,
          digest=digest,
          tree=tree,
      )
      note_file_parsed()
      return parsed
  ```

  In `codemble/adapters/typescript_tree_sitter.py`, add the same import and
  replace the tail of `_parse_file`:

  ```python
      parsed = _ParsedFile(
          path=path,
          project_root=project_root,
          relative_path=relative,
          module_id=f"{language}:{relative}",
          language=language,
          raw=raw,
          source=raw.decode("utf-8", errors="replace"),
          digest=hashlib.sha256(raw).hexdigest(),
          tree=parser.parse(raw),
      )
      note_file_parsed()
      return parsed
  ```

- [ ] **Step 5:** Report stages from `ProjectParser`.

  In `codemble/adapters/project.py`, extend the imports:

  ```python
  from codemble.adapters.parse_progress import ParseProgress, reporting_files
  ```

  and replace `ProjectParser.parse` in full:

  ```python
      def parse(
          self,
          source: Path | ProjectIntake,
          *,
          entrypoint: str | None = None,
          explicit: bool = False,
          progress: ParseProgress | None = None,
      ) -> Graph:
          """Parse every detected language and return one deterministic graph."""

          if isinstance(source, ProjectIntake):
              intake = source
          else:
              if progress is not None:
                  progress.stage("discovering")
              intake = self.intake(source, explicit=explicit)
          owned = {
              adapter.language: intake._files_for(adapter.language)
              for adapter in self._adapters
          }
          if progress is not None:
              # The counter totals the files adapters will actually read, which
              # is what ``note_file_parsed`` counts.  ``intake.files`` is the
              # deduplicated union and would drift if two adapters ever shared
              # an extension.
              progress.files_total(sum(len(files) for files in owned.values()))
              progress.stage("parsing")
          graphs: list[Graph] = []
          on_file = progress.file_parsed if progress is not None else None
          with reporting_files(on_file):
              for adapter in self._adapters:
                  files = owned[adapter.language]
                  if not files:
                      continue
                  try:
                      graphs.append(adapter.parse_files(intake.root, files))
                  except AdapterParseError as error:
                      raise ProjectParseError(str(error)) from error
          if progress is not None:
              progress.stage("resolving")
          return _compose_graphs(tuple(graphs), intake.root, entrypoint)
  ```

  `ParseCancelled` is deliberately not caught here: it is not an
  `AdapterParseError`, so it propagates to the caller that requested the
  cancellation.

- [ ] **Step 6:** Run and see it pass.

  ```bash
  pytest tests/test_parse_progress.py tests/test_project_parser.py tests/test_python_ast.py tests/test_typescript_tree_sitter.py -q
  ruff check .
  ```

  Expected: all pass. `test_stages_are_reported_in_the_contract_order` passes
  because a path-input parse reports `discovering`, then `parsing`, then
  `resolving`; the counter's own flip to `resolving` writes the stage without
  appending to `_Recorder.stages`.

- [ ] **Step 7:** Pin the seam in the parser's own suite.

  Append to `tests/test_project_parser.py`:

  ```python
  def test_progress_reporting_leaves_the_language_adapter_seam_unchanged() -> None:
      """Progress is bound around adapters, never threaded through their signatures."""

      import inspect

      from codemble.adapters.base import LanguageAdapter

      assert list(inspect.signature(LanguageAdapter.discover).parameters) == [
          "self",
          "path",
      ]
      assert list(inspect.signature(LanguageAdapter.parse).parameters) == [
          "self",
          "path",
          "entrypoint",
      ]
      assert list(inspect.signature(LanguageAdapter.parse_files).parameters) == [
          "self",
          "project_root",
          "files",
          "entrypoint",
      ]
      assert list(inspect.signature(LanguageAdapter.concepts).parameters) == [
          "self",
          "node",
          "source",
      ]
  ```

  ```bash
  pytest tests/test_project_parser.py -q
  ```

  Expected: pass. Parameter names, not the rendered signature string: the module
  uses `from __future__ import annotations`, so `inspect` renders annotations as
  quoted strings and the exact text varies by Python version.

- [ ] **Step 8:** Commit.

  ```bash
  git add codemble/adapters/parse_progress.py codemble/adapters/project.py \
    codemble/adapters/python_ast.py codemble/adapters/typescript_tree_sitter.py \
    tests/test_parse_progress.py tests/test_project_parser.py
  git commit -s -m "feat(parser): report per-file parse progress without widening the adapter seam"
  ```

---

### Task 2: The `ParseJob` state machine

**Files:** `codemble/server/parse_job.py` (new), `tests/test_parse_job.py` (new)

**Interfaces:**

Consumes: `codemble.adapters.parse_progress.ParseCancelled` (Task 1).

Produces:

```python
STAGES: tuple[str, ...]          # ("discovering","parsing","resolving","checks","layout")

class ParseJob:                  # implements ParseProgress
    def __init__(self, runner: Callable[[Callable[[], None]], None] = _thread_runner) -> None: ...
    @property
    def active(self) -> bool: ...
    @property
    def cancelled(self) -> bool: ...
    def snapshot(self) -> dict[str, object]: ...   # state, stage, files_done, files_total, error
    def begin(self) -> None: ...                   # idle -> parsing/discovering
    def start(self, work: Callable[[ParseJob], None]) -> None: ...
    def request_cancel(self) -> None: ...
    def cancel(self, timeout: float = 2.0) -> None: ...
    def wait(self, timeout: float | None = None) -> bool: ...
    def stage(self, stage: str) -> None: ...
    def files_total(self, total: int) -> None: ...
    def file_parsed(self) -> None: ...
```

A `ParseJob` instance runs **at most once**. Re-arming means constructing a new
one, which is why a cancelled worker can never bind a stale graph: it holds its
own cancellation token forever.

- [ ] **Step 1:** Write the failing state-machine test.

  Create `tests/test_parse_job.py`:

  ```python
  """The picker's background parse: guarded transitions, cancellation, failure."""

  from __future__ import annotations

  import threading

  import pytest

  from codemble.adapters.parse_progress import ParseCancelled
  from codemble.server.parse_job import STAGES, ParseJob


  def test_a_fresh_job_is_idle() -> None:
      assert ParseJob().snapshot() == {
          "state": "idle",
          "stage": None,
          "files_done": 0,
          "files_total": 0,
          "error": None,
      }


  def test_begin_enters_the_discovering_stage() -> None:
      job = ParseJob()

      job.begin()

      assert job.active is True
      assert job.snapshot()["state"] == "parsing"
      assert job.snapshot()["stage"] == "discovering"


  def test_a_job_runs_at_most_once() -> None:
      job = ParseJob()
      job.begin()

      with pytest.raises(RuntimeError):
          job.begin()


  def test_a_finished_thread_reports_ready_with_its_final_counts() -> None:
      job = ParseJob()

      def work(reporter: ParseJob) -> None:
          reporter.files_total(2)
          reporter.stage("parsing")
          reporter.file_parsed()
          reporter.file_parsed()
          reporter.stage("checks")

      job.begin()
      job.start(work)

      assert job.wait(timeout=5) is True
      assert job.snapshot() == {
          "state": "ready",
          "stage": None,
          "files_done": 2,
          "files_total": 2,
          "error": None,
      }


  def test_the_counter_flips_to_resolving_when_every_file_is_read() -> None:
      job = ParseJob()
      job.files_total(2)
      job.stage("parsing")

      job.file_parsed()
      assert job.snapshot()["stage"] == "parsing"

      job.file_parsed()
      assert job.snapshot()["stage"] == "resolving"


  def test_cancelling_mid_parse_stops_at_the_next_file_and_returns_to_idle() -> None:
      job = ParseJob()
      reached_second_file = threading.Event()
      release = threading.Event()
      files_seen: list[int] = []

      def work(reporter: ParseJob) -> None:
          reporter.files_total(3)
          reporter.stage("parsing")
          reporter.file_parsed()
          files_seen.append(1)
          reached_second_file.set()
          assert release.wait(timeout=5)
          reporter.file_parsed()      # raises ParseCancelled
          files_seen.append(2)        # never reached

      job.begin()
      job.start(work)
      assert reached_second_file.wait(timeout=5)
      job.request_cancel()            # flag set before the worker is released
      release.set()

      assert job.wait(timeout=5) is True
      assert files_seen == [1]
      assert job.cancelled is True
      assert job.snapshot()["state"] == "idle"
      assert job.snapshot()["error"] is None


  def test_a_crash_in_the_worker_becomes_an_error_state_not_a_hang() -> None:
      job = ParseJob()

      def work(_reporter: ParseJob) -> None:
          raise ValueError("tree-sitter exploded")

      job.begin()
      job.start(work)

      assert job.wait(timeout=5) is True
      assert job.snapshot()["state"] == "error"
      assert job.snapshot()["error"] == "tree-sitter exploded"
      assert job.active is False


  def test_cancel_waits_for_a_worker_that_has_already_finished() -> None:
      job = ParseJob(runner=lambda work: work())
      job.begin()
      job.start(lambda reporter: None)

      job.cancel(timeout=5)

      assert job.cancelled is True


  def test_an_unknown_stage_is_refused_rather_than_shown_to_a_learner() -> None:
      job = ParseJob()

      with pytest.raises(ValueError):
          job.stage("thinking")

      assert set(STAGES) == {
          "discovering",
          "parsing",
          "resolving",
          "checks",
          "layout",
      }


  def test_a_cancelled_hook_raises_parse_cancelled() -> None:
      job = ParseJob()
      job.request_cancel()

      with pytest.raises(ParseCancelled):
          job.file_parsed()
  ```

- [ ] **Step 2:** Run it and see it fail.

  ```bash
  pytest tests/test_parse_job.py -x -q
  ```

  Expected: collection error —
  `ModuleNotFoundError: No module named 'codemble.server.parse_job'`.

- [ ] **Step 3:** Implement the state machine.

  Create `codemble/server/parse_job.py`:

  ```python
  """One background project parse: staged progress, cancellation, honest failure.

  A ``ParseJob`` instance runs at most once.  Re-arming the picker constructs a
  new job, so a worker that was cancelled keeps its own cancellation token for
  ever and can never bind a stale graph over a newer selection.
  """

  from __future__ import annotations

  import threading
  from collections.abc import Callable
  from typing import Literal

  from codemble.adapters.parse_progress import ParseCancelled

  JobState = Literal["idle", "parsing", "ready", "error"]

  # The learner-visible stage order, exactly as the design spec fixes it.
  STAGES = ("discovering", "parsing", "resolving", "checks", "layout")


  def _thread_runner(work: Callable[[], None]) -> None:
      threading.Thread(target=work, name="codemble-parse", daemon=True).start()


  class ParseJob:
      """The picker's parse state machine and its ``ParseProgress`` reporter."""

      def __init__(
          self, runner: Callable[[Callable[[], None]], None] = _thread_runner
      ) -> None:
          self._runner = runner
          self._lock = threading.Lock()
          self._cancelled = threading.Event()
          self._done = threading.Event()
          self._started = False
          self._state: JobState = "idle"
          self._stage: str | None = None
          self._files_done = 0
          self._files_total = 0
          self._error: str | None = None

      @property
      def active(self) -> bool:
          """True while this job owns an unfinished parse."""

          with self._lock:
              return self._state == "parsing"

      @property
      def cancelled(self) -> bool:
          """True once cancellation was requested; never cleared."""

          return self._cancelled.is_set()

      def snapshot(self) -> dict[str, object]:
          """Return the exact payload ``GET /api/picker/progress`` serves."""

          with self._lock:
              return {
                  "state": self._state,
                  "stage": self._stage,
                  "files_done": self._files_done,
                  "files_total": self._files_total,
                  "error": self._error,
              }

      def begin(self) -> None:
          """Enter ``discovering`` while the request thread walks the project."""

          with self._lock:
              if self._state != "idle":
                  raise RuntimeError("this parse job already ran")
              self._state = "parsing"
              self._stage = "discovering"

      def start(self, work: Callable[[ParseJob], None]) -> None:
          """Run ``work`` on the configured runner and translate its outcome."""

          def run() -> None:
              try:
                  work(self)
              except ParseCancelled:
                  self._finish("idle", None)
              except Exception as error:
                  # A background thread with no catch-all leaves the picker
                  # stuck on "parsing" for ever.  Every failure becomes state.
                  self._finish("error", str(error) or error.__class__.__name__)
              else:
                  self._finish("ready", None)
              finally:
                  self._done.set()

          self._started = True
          self._runner(run)

      def request_cancel(self) -> None:
          """Ask an active parse to stop at its next file boundary."""

          self._cancelled.set()

      def cancel(self, timeout: float = 2.0) -> None:
          """Request cancellation and wait briefly for the worker to notice."""

          self.request_cancel()
          if self._started:
              self.wait(timeout)

      def wait(self, timeout: float | None = None) -> bool:
          """Block until the worker finishes; False on timeout."""

          return self._done.wait(timeout)

      # --- ParseProgress ---------------------------------------------------

      def stage(self, stage: str) -> None:
          if stage not in STAGES:
              raise ValueError(f"unknown parse stage: {stage}")
          with self._lock:
              self._stage = stage

      def files_total(self, total: int) -> None:
          with self._lock:
              self._files_total = total

      def file_parsed(self) -> None:
          if self._cancelled.is_set():
              raise ParseCancelled("the learner reset the picker during this parse")
          with self._lock:
              self._files_done += 1
              if self._files_total and self._files_done >= self._files_total:
                  self._stage = "resolving"

      def _finish(self, state: JobState, error: str | None) -> None:
          with self._lock:
              self._state = state
              self._stage = None
              self._error = error


  __all__ = ["STAGES", "JobState", "ParseJob"]
  ```

- [ ] **Step 4:** Run and see it pass.

  ```bash
  pytest tests/test_parse_job.py -q
  ruff check .
  ```

  Expected: 10 passed, no ruff findings. The cancellation test is deterministic:
  the flag is set before `release.set()`, so the worker's next `file_parsed()`
  always raises.

- [ ] **Step 5:** Commit.

  ```bash
  git add codemble/server/parse_job.py tests/test_parse_job.py
  git commit -s -m "feat(server): add the parse job state machine with cancellation and crash reporting"
  ```

---

### Task 3: Threaded select, progress endpoint, and reset cancellation

**Files:** `codemble/server/app.py`, `tests/test_server.py`

**Interfaces:**

Consumes: `ParseJob`, `STAGES` (Task 2); `ProjectParser.parse(progress=...)`,
`ParseCancelled` (Task 1).

Produces:

- `POST /api/picker/select` → `202 {"state": "parsing"}`. Synchronous failures
  are unchanged: `403` outside the jail, `404` missing folder, `409` scale with
  the existing structured detail, `422` unparseable, `409` when already bound or
  a parse is already running.
- `GET /api/picker/progress` →
  `{"state": "idle"|"parsing"|"ready"|"error", "stage": str|null, "files_done": int, "files_total": int, "error": str|null}`.
  Never 409s; usable before a project is bound.
- `POST /api/picker/reset` (Phase A) additionally cancels an active parse.
- `create_app(..., parse_runner: Callable[[Callable[[], None]], None] | None = None)`
  — a test seam that runs the parse inline; production leaves it `None`.
- `_ProjectState.bind(graph, progress=None)` reports `checks` then `layout`.

- [ ] **Step 1:** Write the failing endpoint tests.

  Append to `tests/test_server.py`:

  ```python
  def _inline_runner(work):  # type: ignore[no-untyped-def]
      """Run the parse on the request thread so tests never sleep or poll."""

      work()


  def test_picker_select_returns_202_and_binds_through_the_parse_job(
      tmp_path: Path,
  ) -> None:
      from codemble.server.app import PickerConfig

      client = TestClient(
          create_app(
              web_dist=tmp_path / "missing",
              picker=PickerConfig(browse_root=FIXTURE.parent),
              parse_runner=_inline_runner,
          )
      )

      idle = client.get("/api/picker/progress").json()
      accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
      progress = client.get("/api/picker/progress").json()

      assert idle == {
          "state": "idle",
          "stage": None,
          "files_done": 0,
          "files_total": 0,
          "error": None,
      }
      assert accepted.status_code == 202
      assert accepted.json() == {"state": "parsing"}
      assert progress["state"] == "ready"
      assert progress["files_done"] == progress["files_total"] > 0
      assert progress["error"] is None
      assert client.get("/api/picker/state").json() == {"state": "ready"}
      assert client.get("/api/graph").status_code == 200
      assert (
          client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code
          == 409
      )


  def test_picker_progress_reports_ready_for_a_cli_bound_project(tmp_path: Path) -> None:
      graph = PythonAstAdapter().parse(FIXTURE)
      client = TestClient(create_app(graph, tmp_path / "missing"))

      assert client.get("/api/picker/progress").json()["state"] == "ready"


  def test_a_failed_parse_becomes_an_error_state_with_an_in_app_message(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      from codemble.adapters.project import ProjectParser
      from codemble.server.app import PickerConfig

      def exploding_parse(self, source, **kwargs):  # type: ignore[no-untyped-def]
          raise RuntimeError("tree-sitter exploded")

      monkeypatch.setattr(ProjectParser, "parse", exploding_parse)
      client = TestClient(
          create_app(
              web_dist=tmp_path / "missing",
              picker=PickerConfig(browse_root=FIXTURE.parent),
              parse_runner=_inline_runner,
          )
      )

      accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
      progress = client.get("/api/picker/progress").json()

      assert accepted.status_code == 202
      assert progress["state"] == "error"
      assert progress["error"] == "tree-sitter exploded"
      assert client.get("/api/picker/state").json() == {"state": "unpicked"}


  def test_reset_during_a_parse_re_arms_the_picker_and_leaves_nothing_bound(
      tmp_path: Path,
  ) -> None:
      """Cancellation itself is proven in tests/test_parse_job.py; this pins the
      HTTP contract: whether the worker stops mid-parse or finishes a moment
      before the reset lands, reset wins and nothing stays bound."""

      import threading

      from codemble.server.app import PickerConfig

      started = threading.Event()
      release = threading.Event()
      threads: list[threading.Thread] = []

      def gated_runner(work):  # type: ignore[no-untyped-def]
          def run() -> None:
              started.set()
              assert release.wait(timeout=5)
              work()

          thread = threading.Thread(target=run, daemon=True)
          threads.append(thread)
          thread.start()

      client = TestClient(
          create_app(
              web_dist=tmp_path / "missing",
              picker=PickerConfig(browse_root=FIXTURE.parent),
              parse_runner=gated_runner,
          )
      )

      accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
      assert started.wait(timeout=5)
      parsing = client.get("/api/picker/progress").json()
      release.set()
      reset = client.post("/api/picker/reset")
      for thread in threads:
          thread.join(timeout=5)

      assert accepted.status_code == 202
      assert parsing["state"] == "parsing"
      assert parsing["stage"] == "discovering"
      assert reset.status_code == 200
      assert reset.json() == {"state": "unpicked"}
      assert client.get("/api/picker/state").json() == {"state": "unpicked"}
      assert client.get("/api/picker/progress").json()["state"] == "idle"
      assert client.get("/api/graph").status_code == 409
      assert client.get("/api/picker/browse").status_code == 200
      assert (
          client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code
          == 202
      ), "a reset picker accepts the next project without a server restart"


  def test_a_scale_refusal_leaves_the_picker_idle_not_stuck_parsing(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      from codemble.adapters.project import ProjectParser
      from codemble.server.app import PickerConfig

      monkeypatch.setattr(ProjectParser, "scale_cap", 3)
      big = tmp_path / "big"
      (big / "api").mkdir(parents=True)
      for index in range(4):
          (big / "api" / f"module_{index}.py").write_text("A = 1\n", encoding="utf-8")
      client = TestClient(
          create_app(
              web_dist=tmp_path / "missing",
              picker=PickerConfig(browse_root=tmp_path),
              parse_runner=_inline_runner,
          )
      )

      response = client.post("/api/picker/select", json={"path": str(big)})

      assert response.status_code == 409
      assert response.json()["detail"]["reason"] == "scale"
      assert client.get("/api/picker/progress").json()["state"] == "idle"
      assert client.get("/api/picker/browse").status_code == 200
  ```

  Replace the existing `test_picker_select_binds_a_project_exactly_once` — the
  new `test_picker_select_returns_202_and_binds_through_the_parse_job` covers
  the same ground against the 202 contract. Delete the old test body and its
  name; do not leave two tests asserting different select status codes.

- [ ] **Step 2:** Run and see it fail.

  ```bash
  pytest tests/test_server.py -x -q
  ```

  Expected: `TypeError: create_app() got an unexpected keyword argument
  'parse_runner'`.

- [ ] **Step 3:** Rework `_ProjectState` and the picker routes.

  In `codemble/server/app.py`, extend the imports:

  ```python
  import json
  import threading
  from collections.abc import Callable

  from fastapi import FastAPI, HTTPException, Response

  from codemble.adapters.parse_progress import ParseCancelled, ParseProgress
  from codemble.server.parse_job import ParseJob
  ```

  Replace `_ProjectState` in full:

  ```python
  class _ProjectState:
      """Binding from picker selection to live project services, plus its parse."""

      def __init__(self) -> None:
          self.checks: CheckService | None = None
          self.studies: StudyService | None = None
          self.job = ParseJob()
          self._lock = threading.Lock()
          self._graph_json: str | None = None

      @property
      def bound(self) -> bool:
          return self.checks is not None

      def bind(self, graph: Graph, progress: ParseProgress | None = None) -> None:
          if progress is not None:
              progress.stage("checks")
          studies = StudyService.from_environment(graph)
          checks = CheckService(graph)
          if progress is not None:
              progress.stage("layout")
          with self._lock:
              self.studies = studies
              self.checks = checks
              self._graph_json = None
          self.graph_json()

      def unbind(self) -> None:
          with self._lock:
              self.checks = None
              self.studies = None
              self._graph_json = None

      def graph_json(self) -> str:
          """Serialize the render document once per invalidating event."""

          with self._lock:
              cached = self._graph_json
              checks = self.checks
          if cached is not None:
              return cached
          if checks is None:
              raise HTTPException(status_code=409, detail="No project selected yet.")
          payload = json.dumps(
              checks.graph().to_dict(), separators=(",", ":"), ensure_ascii=False
          )
          with self._lock:
              self._graph_json = payload
          return payload

      def invalidate_graph_json(self) -> None:
          with self._lock:
              self._graph_json = None
  ```

  Task 5 adds the tests that pin the cache; the field is introduced here so
  `bind` can report the `layout` stage honestly.

  Add `parse_runner` to `create_app`'s signature, after `picker`:

  ```python
      picker: PickerConfig | None = None,
      parse_runner: Callable[[Callable[[], None]], None] | None = None,
      allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver"),
  ```

  and inside the body, right after `state = _ProjectState()`:

  ```python
      if parse_runner is not None:
          state.job = ParseJob(runner=parse_runner)

      def _new_job() -> ParseJob:
          return ParseJob(runner=parse_runner) if parse_runner else ParseJob()
  ```

  Replace `select_project` in full:

  ```python
      @app.post("/api/picker/select", status_code=202)
      def select_project(selection: ProjectSelection) -> dict[str, object]:
          if state.bound or picker is None or state.job.active:
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
          job = _new_job()
          state.job = job
          job.begin()
          try:
              intake = parser.intake(resolved)
          except ProjectScaleError as error:
              state.job = _new_job()
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
              state.job = _new_job()
              raise HTTPException(status_code=422, detail=str(error)) from error

          def work(reporter: ParseJob) -> None:
              bound_graph = parser.parse(
                  intake, entrypoint=picker.entrypoint, progress=reporter
              )
              if reporter.cancelled:
                  raise ParseCancelled("the learner reset the picker during this parse")
              state.bind(bound_graph, progress=reporter)

          job.start(work)
          return {"state": "parsing"}
  ```

  Add the progress route directly below it:

  ```python
      @app.get("/api/picker/progress")
      def picker_progress() -> dict[str, object]:
          # Never guarded by _services(): the loading screen polls this while
          # nothing is bound yet, and it must answer honestly before, during,
          # and after a parse.
          snapshot = state.job.snapshot()
          if snapshot["state"] == "idle" and state.bound:
              snapshot["state"] = "ready"
          return snapshot
  ```

  Extend Phase A's reset route so a running parse is cancelled first. Phase A
  ships the same handler minus the two `job` lines:

  ```python
      @app.post("/api/picker/reset")
      def reset_picker() -> dict[str, str]:
          if picker is None:
              raise HTTPException(
                  status_code=409, detail="This server was started for one project."
              )
          state.job.cancel()
          state.job = _new_job()
          state.unbind()
          return {"state": "unpicked"}
  ```

- [ ] **Step 4:** Run and see it pass.

  ```bash
  pytest tests/test_server.py -q
  ruff check .
  ```

  Expected: all pass, including the untouched picker browse/recents/jail tests.

- [ ] **Step 5:** Prove the jail and the Host allowlist still hold.

  ```bash
  pytest tests/test_server.py -q -k "jail or symlink or foreign_host or escaping"
  ```

  Expected: `test_picker_browse_lists_directories_inside_the_jail`,
  `test_picker_browse_refuses_symlink_escape`,
  `test_picker_select_rejects_unparseable_and_escaping_paths`, and
  `test_foreign_host_headers_are_rejected` all pass unchanged.

- [ ] **Step 6:** Commit.

  ```bash
  git add codemble/server/app.py tests/test_server.py
  git commit -s -m "feat(server): parse in a worker thread behind 202 select and a progress endpoint"
  ```

---

### Task 4: One-pass check index

**Files:** `codemble/checks/service.py`, `tests/test_checks.py`,
`tests/fixtures/check_suites.json` (new)

**Interfaces:**

Consumes: `Graph`, `Node`, `Edge`.

Produces: unchanged public API — `generate_checks(graph, region_id)` and
`CheckService(graph, progress=None)` keep their exact signatures and outputs.
Internally:

```python
class _CheckIndex:
    """One O(nodes + edges) pass every region's generation reads."""
    nodes: dict[str, Node]
    region_ids: frozenset[str]
    all_ids: tuple[str, ...]                              # sorted, unique
    ids_by_kind: dict[str, tuple[str, ...]]               # sorted, unique
    calls_out_by_region: dict[str, dict[str, list[Edge]]] # region of src -> src -> edges
    calls_in_by_region: dict[str, dict[str, list[Edge]]]  # region of dst -> dst -> edges
    imports_into: dict[str, list[Edge]]                   # edge.dst -> edges
    imports_out: dict[str, list[Edge]]                    # edge.src -> edges
    ranked_entrypoints: list[str]

def _region_checks(index: _CheckIndex, region_id: str) -> tuple[Check, ...]: ...
```

Today `CheckService.__init__` calls `generate_checks` once per region; each call
rebuilds the node dict (O(N)), re-scans `graph.edges` four times, rebuilds the
option pool from all nodes, and re-scans `graph.regions` to validate the region
id. That is O(R × (N + E)) — the bind freeze at ~1,000 files.

- [ ] **Step 1:** Pin today's suites in a golden fixture.

  Generate it from the **unchanged** implementation:

  ```bash
  python - <<'PY'
  import json
  from pathlib import Path

  from codemble.adapters.python_ast import PythonAstAdapter
  from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter
  from codemble.checks import generate_checks

  root = Path("tests/fixtures")
  graphs = {
      "sampleproj": PythonAstAdapter().parse(root / "sampleproj"),
      "polyglot": JavaScriptTypeScriptAdapter().parse(root / "polyglot"),
  }
  golden = {}
  for name, graph in graphs.items():
      golden[name] = {
          region.id: [
              {
                  "id": check.id,
                  "kind": check.kind,
                  "prompt": check.prompt,
                  "options": [
                      {"id": option.id, "label": option.label} for option in check.options
                  ],
                  "answer_ids": list(check.answer_ids),
                  "evidence": list(check.evidence),
              }
              for check in generate_checks(graph, region.id)
          ]
          for region in graph.regions
      }
  (root / "check_suites.json").write_text(
      json.dumps(golden, indent=2, sort_keys=True) + "\n", encoding="utf-8"
  )
  print(sum(len(suites) for suites in golden.values()), "regions pinned")
  PY
  ```

  Then add the comparison test to `tests/test_checks.py`:

  ```python
  import json

  from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter

  GOLDEN = Path(__file__).parent / "fixtures" / "check_suites.json"
  POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


  def _suites(graph) -> dict:  # type: ignore[no-untyped-def]
      return {
          region.id: [
              {
                  "id": check.id,
                  "kind": check.kind,
                  "prompt": check.prompt,
                  "options": [
                      {"id": option.id, "label": option.label} for option in check.options
                  ],
                  "answer_ids": list(check.answer_ids),
                  "evidence": list(check.evidence),
              }
              for check in generate_checks(graph, region.id)
          ]
          for region in graph.regions
      }


  def test_generated_check_suites_match_the_pinned_golden() -> None:
      """A performance change to generation must not move one byte of a suite."""

      golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

      assert _suites(PythonAstAdapter().parse(FIXTURE)) == golden["sampleproj"]
      assert (
          _suites(JavaScriptTypeScriptAdapter().parse(POLYGLOT_FIXTURE))
          == golden["polyglot"]
      )


  def test_the_service_generates_the_same_suites_as_the_public_function(
      tmp_path: Path,
  ) -> None:
      graph = PythonAstAdapter().parse(FIXTURE)
      service = CheckService(graph, ProgressStore(graph, tmp_path))

      for region in graph.regions:
          suite = service.for_region(region.id)["checks"]
          expected = generate_checks(graph, region.id)
          assert [question["id"] for question in suite] == [
              check.id for check in expected
          ]
          assert [question["options"] for question in suite] == [
              [{"id": option.id, "label": option.label} for option in check.options]
              for check in expected
          ]
  ```

  ```bash
  pytest tests/test_checks.py -q
  ```

  Expected: **pass**. This is a characterization pin, not a red test — if it
  fails now, the golden was generated wrong, not the code. Do not proceed until
  it is green on the unchanged implementation.

  ```bash
  git add tests/fixtures/check_suites.json tests/test_checks.py
  git commit -s -m "test(checks): pin today's generated suites before the index refactor"
  ```

- [ ] **Step 2:** Write the failing performance test.

  Append to `tests/test_checks.py`:

  ```python
  from dataclasses import replace as replace_dataclass


  def test_check_generation_walks_every_edge_once(tmp_path: Path) -> None:
      """Per-region full-edge scans are the bind freeze at ~1,000 files."""

      graph = PythonAstAdapter().parse(FIXTURE)
      passes = 0

      class _CountingEdges(tuple):
          """A real tuple that records how many times a consumer walked it."""

          def __iter__(self):  # type: ignore[no-untyped-def]
              nonlocal passes
              passes += 1
              return super().__iter__()

      counted = replace_dataclass(graph, edges=_CountingEdges(graph.edges))
      # ProgressStore reads graph.nodes and graph.file_hashes only, so every
      # recorded pass belongs to check generation.
      CheckService(counted, ProgressStore(graph, tmp_path))

      assert len(graph.regions) > 1
      assert passes == 1
  ```

  ```bash
  pytest tests/test_checks.py::test_check_generation_walks_every_edge_once -x -q
  ```

  Expected: **fail** — `assert 24 == 1` or similar (up to four scans per region;
  the exact number depends on how many regions reach each generator). Any number
  greater than 1 is the red state.

- [ ] **Step 3:** Build the index and route generation through it.

  In `codemble/checks/service.py`, replace `CheckService.__init__`,
  `CheckService.select_entrypoint`, `generate_checks`, the four generators,
  `_node_options`, and `_options`. Everything else in the file is unchanged.

  ```python
  class _CheckIndex:
      """One O(nodes + edges) pass over the graph that every region reads."""

      __slots__ = (
          "graph",
          "nodes",
          "region_ids",
          "all_ids",
          "ids_by_kind",
          "calls_out_by_region",
          "calls_in_by_region",
          "imports_into",
          "imports_out",
          "ranked_entrypoints",
      )

      def __init__(self, graph: Graph) -> None:
          self.graph = graph
          self.nodes = {node.id: node for node in graph.nodes}
          self.region_ids = frozenset(region.id for region in graph.regions)
          self.all_ids = tuple(sorted(self.nodes))
          by_kind: dict[str, list[str]] = {}
          for node in graph.nodes:
              by_kind.setdefault(node.kind, []).append(node.id)
          self.ids_by_kind = {kind: tuple(sorted(ids)) for kind, ids in by_kind.items()}
          self.calls_out_by_region: dict[str, dict[str, list[Edge]]] = {}
          self.calls_in_by_region: dict[str, dict[str, list[Edge]]] = {}
          self.imports_into: dict[str, list[Edge]] = {}
          self.imports_out: dict[str, list[Edge]] = {}
          # One walk, in graph.edges order, so every bucket preserves the order
          # the previous per-region scans saw.
          for edge in graph.edges:
              if not edge.certain or edge.external:
                  continue
              if edge.kind == "call":
                  source = self.nodes.get(edge.src)
                  target = self.nodes.get(edge.dst)
                  if source is None or target is None:
                      continue
                  self.calls_out_by_region.setdefault(source.region, {}).setdefault(
                      edge.src, []
                  ).append(edge)
                  self.calls_in_by_region.setdefault(target.region, {}).setdefault(
                      edge.dst, []
                  ).append(edge)
              elif edge.kind == "import":
                  if edge.src in self.nodes:
                      self.imports_into.setdefault(edge.dst, []).append(edge)
                  if edge.dst in self.nodes:
                      self.imports_out.setdefault(edge.src, []).append(edge)
          self.ranked_entrypoints = [
              candidate
              for candidate in graph.entrypoint_candidates
              if candidate in self.nodes
          ]
  ```

  `CheckService`:

  ```python
      def __init__(self, graph: Graph, progress: ProgressStore | None = None) -> None:
          self._graph = graph
          self._progress = progress or ProgressStore(graph)
          self._checks = _suites(graph)
          self._passed: dict[str, set[str]] = {}
  ```

  ```python
      def select_entrypoint(self, node_id: str) -> Graph:
          """Apply an explicit parser-ranked Home choice to graph and check suites."""

          self._graph = with_entrypoint(self._graph, node_id)
          self._checks = _suites(self._graph)
          return self.graph()
  ```

  Module-level helpers:

  ```python
  def _suites(graph: Graph) -> dict[str, tuple[Check, ...]]:
      index = _CheckIndex(graph)
      return {region.id: _region_checks(index, region.id) for region in graph.regions}


  def generate_checks(graph: Graph, region_id: str) -> tuple[Check, ...]:
      """Build up to four stable questions from parser-owned evidence."""

      return _region_checks(_CheckIndex(graph), region_id)


  def _region_checks(index: _CheckIndex, region_id: str) -> tuple[Check, ...]:
      if region_id not in index.region_ids:
          raise UnknownCheckError(region_id)
      checks: list[Check] = []
      for build in (
          _first_call_check,
          _importer_check,
          _impact_check,
          _entrypoint_check,
      ):
          check = build(index, region_id)
          if check:
              checks.append(check)
      return tuple(check for check in checks if _proves_understanding(check))
  ```

  The four generators, with identical filters and identical sort keys:

  ```python
  def _first_call_check(index: _CheckIndex, region_id: str) -> Check | None:
      calls_by_source = index.calls_out_by_region.get(region_id)
      if not calls_by_source:
          return None
      source_id = sorted(calls_by_source)[0]
      edge = min(calls_by_source[source_id], key=lambda item: (item.lineno, item.dst))
      answers = (edge.dst,)
      return _check(
          index,
          region_id,
          "first-call",
          source_id,
          {
              "easy": f"Which piece of code does {source_id} call first?",
              "expert": f"Which structure does {source_id} call first?",
          },
          answers,
          _node_options(index, answers, kind="function"),
          (f"{index.nodes[source_id].file}:{edge.lineno}",),
      )


  def _importer_check(index: _CheckIndex, region_id: str) -> Check | None:
      incoming = sorted(
          index.imports_into.get(region_id, ()),
          key=lambda edge: (edge.src, edge.lineno),
      )
      if incoming:
          answers = tuple(sorted({edge.src for edge in incoming}))
          return _check(
              index,
              region_id,
              "direct-importer",
              region_id,
              {
                  "easy": f"Which of your files brings in {region_id} directly?",
                  "expert": f"Which project module imports {region_id} directly?",
              },
              answers,
              _node_options(index, answers, kind="module"),
              tuple(f"{index.nodes[edge.src].file}:{edge.lineno}" for edge in incoming),
          )

      outgoing = sorted(
          index.imports_out.get(region_id, ()),
          key=lambda edge: (edge.lineno, edge.dst),
      )
      if not outgoing:
          return None
      first = outgoing[0]
      answers = (first.dst,)
      return _check(
          index,
          region_id,
          "direct-importer",
          region_id,
          {
              "easy": f"Which of your files does {region_id} bring in first?",
              "expert": f"Which project module does {region_id} import first?",
          },
          answers,
          _node_options(index, answers, kind="module"),
          (f"{index.nodes[region_id].file}:{first.lineno}",),
      )


  def _impact_check(index: _CheckIndex, region_id: str) -> Check | None:
      callers_by_target = index.calls_in_by_region.get(region_id)
      if not callers_by_target:
          return None
      target_id = sorted(
          callers_by_target,
          key=lambda candidate: (-len(callers_by_target[candidate]), candidate),
      )[0]
      callers = sorted(
          callers_by_target[target_id], key=lambda edge: (edge.src, edge.lineno)
      )
      answers = tuple(sorted({edge.src for edge in callers}))
      return _check(
          index,
          region_id,
          "removal-impact",
          target_id,
          {
              "easy": f"Which piece of code uses {target_id} directly and would break if it disappeared?",
              "expert": (
                  f"Which structure directly depends on {target_id} "
                  "and could break if it disappeared?"
              ),
          },
          answers,
          _node_options(index, answers, kind="function"),
          tuple(f"{index.nodes[edge.src].file}:{edge.lineno}" for edge in callers),
      )


  def _entrypoint_check(index: _CheckIndex, region_id: str) -> Check | None:
      ranked = index.ranked_entrypoints
      selected = index.graph.selected_entrypoint
      if not ranked or selected is None or index.nodes[selected].region != region_id:
          return None
      answers = (selected,)
      # The old pool was ranked candidates followed by every other node; _options
      # only ever consumed sorted(set(pool)), which is exactly every node id.
      return _check(
          index,
          region_id,
          "entrypoint",
          selected,
          {
              "easy": "Which part of your code does the program start from?",
              "expert": "Which parser-ranked structure is selected as Home for this run?",
          },
          answers,
          _options(index, answers, index.all_ids),
          (f"{index.nodes[selected].file}:{index.nodes[selected].lineno}",),
      )


  def _node_options(
      index: _CheckIndex, answers: tuple[str, ...], *, kind: str
  ) -> tuple[CheckOption, ...]:
      pool = index.ids_by_kind.get(kind, ())
      if len(set(pool) | set(answers)) < 2:
          pool = index.all_ids
      return _options(index, answers, pool)


  def _options(
      index: _CheckIndex, answers: tuple[str, ...], pool: tuple[str, ...]
  ) -> tuple[CheckOption, ...]:
      """Offer every answer plus wrong options, or nothing if none exist.

      ``pool`` is already sorted and unique, so this walks it directly; the
      previous ``sorted(set(pool))`` per call was O(N log N) per region.

      The ceiling must clear ``len(answers)``; capping at four alone offered a
      multi-answer check no wrong option, so selecting everything always passed.
      """

      candidates = list(answers)
      ceiling = max(4, len(answers) + _MINIMUM_DISTRACTORS)
      for candidate in pool:
          if candidate not in candidates and len(candidates) < ceiling:
              candidates.append(candidate)
      if len(candidates) == len(answers):
          return ()
      return tuple(
          CheckOption(candidate, index.nodes[candidate].id) for candidate in candidates
      )


  def _check(
      index: _CheckIndex,
      region_id: str,
      kind: CheckKind,
      subject: str,
      prompt: dict[str, str],
      answers: tuple[str, ...],
      options: tuple[CheckOption, ...],
      evidence: tuple[str, ...],
  ) -> Check:
      check_id = hashlib.sha256(
          f"{index.graph.schema_version}|{region_id}|{kind}|{subject}".encode()
      ).hexdigest()[:16]
      return Check(
          id=check_id,
          region_id=region_id,
          kind=kind,
          prompt=prompt,
          options=options,
          answer_ids=answers,
          evidence=evidence,
      )
  ```

- [ ] **Step 4:** Run and see everything pass.

  ```bash
  pytest tests/test_checks.py tests/test_server.py -q
  ruff check .
  ```

  Expected: `test_check_generation_walks_every_edge_once` now reports 1 pass, and
  `test_generated_check_suites_match_the_pinned_golden` still matches byte for
  byte. If the golden test fails, the refactor changed behaviour — revert and
  re-derive; do not regenerate the golden.

- [ ] **Step 5:** Run the whole suite.

  ```bash
  pytest -q
  ```

  Expected: green, including
  `test_every_check_offers_at_least_one_wrong_option`,
  `test_the_two_voices_ask_the_same_question_of_the_same_answer`, and the
  server's `/api/regions/.../checks` tests.

- [ ] **Step 6:** Commit.

  ```bash
  git add codemble/checks/service.py tests/test_checks.py
  git commit -s -m "perf(checks): index graph edges once per bind instead of once per region"
  ```

---

### Task 5: Graph response cache

**Files:** `codemble/server/app.py`, `tests/test_server.py`

**Interfaces:**

Consumes: `_ProjectState.graph_json()` / `invalidate_graph_json()` (introduced in
Task 3).

Produces: `GET /api/graph` serves a cached compact JSON document as a
`Response(media_type="application/json")`. Invalidated on region light-up
(check submission), entrypoint selection, and bind/unbind. **Verified: mode
changes do not affect the payload** — `Graph.to_dict()` has no mode field and
`ProgressStore.set_mode` writes a sibling key that `hydrated_graph()` never
reads. The existing `test_changing_mode_does_not_re_dim_a_region` already asserts
that equality; Step 1 adds the cache-specific version so a future
mode-dependent field cannot slip through.

Source hashes are frozen at bind (`ProgressStore._region_signatures` is computed
once from the in-memory graph), so editing a file on disk does not change the
live response today and the cache introduces no new staleness there.

- [ ] **Step 1:** Write the failing cache tests.

  Append to `tests/test_server.py`:

  ```python
  def test_graph_responses_are_cached_and_invalidated_by_light_up(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
      graph = PythonAstAdapter().parse(FIXTURE)
      checks = CheckService(graph, ProgressStore(graph, tmp_path / "progress"))
      hydrations = 0
      real_graph = checks.graph

      def counting_graph():  # type: ignore[no-untyped-def]
          nonlocal hydrations
          hydrations += 1
          return real_graph()

      monkeypatch.setattr(checks, "graph", counting_graph)
      client = TestClient(
          create_app(
              graph,
              tmp_path / "missing",
              StudyService(graph, cache_root=tmp_path / "cache"),
              checks,
          )
      )

      first = client.get("/api/graph").json()
      second = client.get("/api/graph").json()
      after_two_reads = hydrations

      for check in generate_checks(graph, "app"):
          client.post(
              f"/api/regions/app/checks/{check.id}",
              json={"selected_ids": list(check.answer_ids)},
          )
      lit = client.get("/api/graph").json()

      assert first == second
      assert after_two_reads == 1, "a second read must not re-hydrate or re-sort"
      assert (
          next(region for region in first["regions"] if region["id"] == "app")[
              "understood"
          ]
          is False
      )
      assert (
          next(region for region in lit["regions"] if region["id"] == "app")["understood"]
          is True
      ), "a cached payload must never survive a region lighting up"


  def test_graph_cache_is_invalidated_by_entrypoint_selection(tmp_path: Path) -> None:
      for module in ("alpha", "beta"):
          (tmp_path / f"{module}.py").write_text(
              'if __name__ == "__main__":\n    print("start")\n',
              encoding="utf-8",
          )
      graph = PythonAstAdapter().parse(tmp_path)
      client = TestClient(create_app(graph, tmp_path / "missing"))

      before = client.get("/api/graph").json()
      client.post("/api/entrypoint", json={"node_id": "beta"})
      after = client.get("/api/graph").json()

      assert before["selected_entrypoint"] is None
      assert after["selected_entrypoint"] == "beta"
      assert next(region for region in after["regions"] if region["id"] == "beta")["home"]


  def test_graph_cache_is_dropped_when_the_project_is_reset(tmp_path: Path) -> None:
      from codemble.server.app import PickerConfig

      client = TestClient(
          create_app(
              web_dist=tmp_path / "missing",
              picker=PickerConfig(browse_root=FIXTURE.parent),
              parse_runner=_inline_runner,
          )
      )
      client.post("/api/picker/select", json={"path": str(FIXTURE)})
      assert client.get("/api/graph").status_code == 200

      client.post("/api/picker/reset")

      assert client.get("/api/graph").status_code == 409


  def test_a_mode_change_serves_the_same_cached_graph(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
      graph = PythonAstAdapter().parse(FIXTURE)
      client = TestClient(create_app(graph, tmp_path / "missing"))

      before = client.get("/api/graph").json()
      client.put("/api/mode", json={"mode": "expert"})

      assert client.get("/api/graph").json() == before
  ```

- [ ] **Step 2:** Run and see it fail.

  ```bash
  pytest tests/test_server.py -x -q -k "graph_cache or graph_responses"
  ```

  Expected: `assert 2 == 1, "a second read must not re-hydrate or re-sort"` —
  today `/api/graph` re-hydrates on every request.

- [ ] **Step 3:** Serve and invalidate the cache.

  In `codemble/server/app.py`, replace `get_graph`:

  ```python
      @app.get("/api/graph")
      def get_graph() -> Response:
          _services()
          return Response(state.graph_json(), media_type="application/json")
  ```

  In `select_entrypoint`, invalidate before returning:

  ```python
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
          state.invalidate_graph_json()
          return selected.to_dict()
  ```

  In `submit_region_check`, invalidate on every accepted submission — a
  submission is rare and a light-up is the one thing that must never be stale:

  ```python
      @app.post("/api/regions/{region_id:path}/checks/{check_id}")
      def submit_region_check(
          region_id: str, check_id: str, submission: CheckSubmission
      ) -> dict[str, object]:
          checks, _ = _services()
          try:
              result = checks.submit(region_id, check_id, submission.selected_ids)
          except UnknownCheckError as error:
              raise HTTPException(
                  status_code=404, detail="That graph check does not exist."
              ) from error
          except InvalidCheckSubmission as error:
              raise HTTPException(status_code=422, detail=str(error)) from error
          state.invalidate_graph_json()
          return result
  ```

  `bind()` and `unbind()` already clear `_graph_json` (Task 3).

- [ ] **Step 4:** Run and see it pass.

  ```bash
  pytest tests/test_server.py -q
  ruff check .
  ```

  Expected: all pass, including the pre-existing
  `test_check_api_withholds_answers_then_persists_graph_lighting` and
  `test_changing_mode_does_not_re_dim_a_region`.

- [ ] **Step 5:** Commit.

  ```bash
  git add codemble/server/app.py tests/test_server.py
  git commit -s -m "perf(server): cache the serialized graph response until progress or binding changes"
  ```

---

### Task 6: Scale cap 300 → 1,000 with an actionable message

**Files:** `codemble/adapters/project.py`, `tests/test_server.py`,
`tests/test_smoke.py`, `web/scripts/check_learner_session.mjs`

**Interfaces:**

Consumes: `ProjectIntake.scope_counts()`.

Produces: `ProjectParser.scale_cap == 1000`; `ProjectScaleError.__str__` names
the busiest scopes so the non-TTY CLI path is actionable (spec G4). The
`ProjectScaleError.intake` / `.scale_cap` attributes and the picker's structured
409 detail are unchanged.

Every place that asserts or documents 300 (documentation lands in Task 12):

| Location | Kind | Action |
| --- | --- | --- |
| `codemble/adapters/project.py:88` | source of truth | 300 → 1000 |
| `tests/test_server.py` `test_picker_select_reports_scale_with_suggestions` | asserts `scale_cap == 300`, builds 301 files | monkeypatch the cap; keep the payload assertions |
| `tests/test_smoke.py` `test_large_project_requires_an_explicit_or_interactive_scope` | builds 301 files to trip the cap | monkeypatch the cap; message assertion unchanged |
| `web/scripts/check_learner_session.mjs:236,238` | HTTP picker fixture | 300 → 1000 |
| `web/scripts/check_learner_session.mjs:308,310` | in-memory picker fixture | 300 → 1000 |
| `README.md:150`, `TESTING.md:11`, `docs-site/.../quickstart.md:41`, `docs-site/.../installation.md:88`, `CLAUDE.md:414` | prose | Task 12 |
| `CHANGELOG.md:149`, `CLAUDE.md:256/330/354`, `docs-site/.../progress/m6-release.md:17`, `docs/releases/v0.1.0.md`, `docs/releases/v0.2.0.md`, `docs/plans/phase-1.md:45`, `docs/plans/2026-07-19-install-ux-folder-picker-plan.md` | historical record (append-only log, shipped release notes, superseded plans) | **leave unchanged** |
| `docs-site/scripts/build-plates.mjs:135/141/241`, `docs-site/src/pages/index.astro:227` | SVG geometry, unrelated | leave unchanged |

- [ ] **Step 1:** Write the failing cap tests.

  In `tests/test_smoke.py`, replace
  `test_large_project_requires_an_explicit_or_interactive_scope` and add a pin:

  ```python
  def test_the_v1_scale_cap_is_one_thousand_supported_files() -> None:
      from codemble.adapters.project import ProjectParser

      assert ProjectParser.scale_cap == 1000


  def test_large_project_requires_an_explicit_or_interactive_scope(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      from codemble.adapters.project import ProjectParser

      # Exercise the mechanism, not the constant: building scale_cap+1 real
      # files would add a second of I/O to every run.
      monkeypatch.setattr(ProjectParser, "scale_cap", 3)
      project = tmp_path / "large"
      project.mkdir()
      for index in range(4):
          (project / f"module_{index:03d}.py").touch()
      small = project / "small"
      small.mkdir()
      (small / "one.py").touch()
      (small / "two.py").touch()

      with pytest.raises(ProjectParseError, match="Re-run with `codemble --path PATH`"):
          choose_project_scope(project, explicit=False, interactive=False)
      assert (
          choose_project_scope(project, explicit=True, interactive=False).path
          == project.resolve()
      )

      output: list[str] = []
      selected = choose_project_scope(
          project,
          explicit=False,
          interactive=True,
          input_fn=lambda _prompt: "small",
          output_fn=output.append,
      )
      assert selected.path == small.resolve()
      assert any("6 supported source files" in message for message in output)


  def test_the_non_tty_scale_error_names_the_busiest_scopes(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      """A piped run gets the same actionable suggestions the prompt shows."""

      from codemble.adapters.project import ProjectParser

      monkeypatch.setattr(ProjectParser, "scale_cap", 2)
      project = tmp_path / "large"
      (project / "api").mkdir(parents=True)
      for index in range(3):
          (project / "api" / f"module_{index}.py").touch()
      (project / "web").mkdir()
      (project / "web" / "one.py").touch()

      with pytest.raises(ProjectParseError) as raised:
          choose_project_scope(project, explicit=False, interactive=False)

      assert "api (3)" in str(raised.value)
      assert "web (1)" in str(raised.value)
      assert "Re-run with `codemble --path PATH`" in str(raised.value)
  ```

  `pytest` is already imported in `tests/test_smoke.py`; add
  `monkeypatch: pytest.MonkeyPatch` parameters as shown.

  In `tests/test_server.py`, replace
  `test_picker_select_reports_scale_with_suggestions`:

  ```python
  def test_picker_select_reports_scale_with_suggestions(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      from codemble.adapters.project import ProjectParser
      from codemble.server.app import PickerConfig

      monkeypatch.setattr(ProjectParser, "scale_cap", 3)
      big = tmp_path / "big"
      (big / "api").mkdir(parents=True)
      for index in range(4):
          (big / "api" / f"module_{index}.py").write_text("A = 1\n", encoding="utf-8")
      client = TestClient(
          create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
      )

      response = client.post("/api/picker/select", json={"path": str(big)})

      assert response.status_code == 409
      detail = response.json()["detail"]
      assert detail["reason"] == "scale"
      assert detail["file_count"] == 4
      assert detail["scale_cap"] == 3
      assert detail["root"] == str(big.resolve())
      assert detail["suggestions"][0] == {"path": "api", "file_count": 4}
  ```

- [ ] **Step 2:** Run and see them fail.

  ```bash
  pytest tests/test_smoke.py tests/test_server.py -q -k "scale or large_project"
  ```

  Expected: `test_the_v1_scale_cap_is_one_thousand_supported_files` fails with
  `assert 300 == 1000`, and `test_the_non_tty_scale_error_names_the_busiest_scopes`
  fails with `assert 'api (3)' in "found 4 supported source files; Codemble is
  capped at 2. Re-run with ..."`.

- [ ] **Step 3:** Raise the cap and enrich the message.

  In `codemble/adapters/project.py`, replace `ProjectScaleError.__init__`:

  ```python
      def __init__(self, intake: ProjectIntake, scale_cap: int) -> None:
          self.intake = intake
          self.scale_cap = scale_cap
          scopes = ", ".join(
              f"{directory} ({count})" for directory, count in intake.scope_counts()[:6]
          )
          suggestion = f" Busiest scopes: {scopes}." if scopes else ""
          super().__init__(
              f"found {len(intake.files)} supported source files; Codemble is capped at "
              f"{scale_cap}. Re-run with `codemble --path PATH` to choose a project "
              f"subdirectory.{suggestion}"
          )
  ```

  and raise the cap:

  ```python
      # Raised from 300 with the Phase C threaded parse and staged loading
      # screen; LOD and clustering remain Phase 2.
      scale_cap = 1000
  ```

- [ ] **Step 4:** Refresh the frontend picker fixtures.

  In `web/scripts/check_learner_session.mjs`, update both scale fixtures so the
  numbers describe the shipped cap. Lines 232-241 (HTTP adapter):

  ```js
        json: async () => ({
          detail: {
            reason: "scale",
            file_count: 1420,
            scale_cap: 1000,
            root: "/home/u/big",
            suggestions: [{ path: "api", file_count: 900 }],
          },
        }),
  ```

  and the matching assertion below it:

  ```js
  assert.equal(scaleResult.file_count, 1420);
  ```

  Lines 305-313 (in-memory adapter):

  ```js
        "/home/u/big": {
          state: "scale",
          file_count: 1420,
          scale_cap: 1000,
          root: "/home/u/big",
          suggestions: [{ path: "api", file_count: 900 }],
        },
  ```

  and the matching assertion:

  ```js
  assert.equal(pickerSnapshot.picker.scale.file_count, 1420);
  ```

- [ ] **Step 5:** Run and see them pass.

  ```bash
  pytest -q
  ruff check .
  cd web && node scripts/check_learner_session.mjs && cd ..
  ```

  Expected: all green. `npm run build` is not required here — no `web/src` file
  changed.

- [ ] **Step 6:** Commit.

  ```bash
  git add codemble/adapters/project.py tests/test_smoke.py tests/test_server.py \
    web/scripts/check_learner_session.mjs
  git commit -s -m "feat(parser): raise the scale cap to 1,000 files and name the busiest scopes"
  ```

---

### Task 7: CLI staged progress

**Files:** `codemble/server/runtime.py`, `tests/test_smoke.py`

**Interfaces:**

Consumes: `ProjectParser.parse(progress=...)` (Task 1), `STAGES` (Task 2).

Produces:

```python
# codemble/server/runtime.py
class TerminalProgress:
    """A ParseProgress that prints the same five stages the web loader shows."""
    def __init__(self, write: Callable[[str], None] = ..., isatty: bool = ...) -> None: ...
    def stage(self, stage: str) -> None: ...
    def files_total(self, total: int) -> None: ...
    def file_parsed(self) -> None: ...
```

`serve_project` keeps its blocking parse and prints `discovering`, `parsing`,
`resolving` from the parser, then `checks` and `layout` around `create_app`,
which is exactly where `CheckService` is built and the render document is warmed.

- [ ] **Step 1:** Write the failing CLI-progress test.

  Append to `tests/test_smoke.py`:

  ```python
  def test_terminal_progress_prints_every_stage_in_order() -> None:
      from codemble.server.parse_job import STAGES
      from codemble.server.runtime import TerminalProgress

      lines: list[str] = []
      reporter = TerminalProgress(write=lines.append, isatty=False)

      reporter.stage("discovering")
      reporter.files_total(2)
      reporter.stage("parsing")
      reporter.file_parsed()
      reporter.file_parsed()
      reporter.stage("resolving")
      reporter.stage("checks")
      reporter.stage("layout")

      printed = "".join(lines)
      for stage in STAGES:
          assert stage in printed
      assert printed.index("discovering") < printed.index("parsing")
      assert printed.index("parsing") < printed.index("resolving")
      assert printed.index("resolving") < printed.index("checks")
      assert printed.index("checks") < printed.index("layout")


  def test_terminal_progress_only_redraws_the_counter_on_a_tty() -> None:
      from codemble.server.runtime import TerminalProgress

      quiet: list[str] = []
      TerminalProgress(write=quiet.append, isatty=False).file_parsed()
      loud: list[str] = []
      loud_reporter = TerminalProgress(write=loud.append, isatty=True)
      loud_reporter.files_total(4)
      loud_reporter.stage("parsing")
      loud_reporter.file_parsed()

      assert "".join(quiet) == ""
      assert "\r" in "".join(loud)
      assert "1/4" in "".join(loud)


  def test_terminal_progress_swallows_a_repeated_stage() -> None:
      """serve_project announces discovering; a Path parse announces it again."""

      from codemble.server.runtime import TerminalProgress

      lines: list[str] = []
      reporter = TerminalProgress(write=lines.append, isatty=False)
      reporter.stage("discovering")
      reporter.stage("discovering")

      assert len(lines) == 1


  def test_serve_project_reports_the_full_stage_sequence(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      from codemble.server import runtime

      monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
      fixture = Path(__file__).parent / "fixtures" / "sampleproj"
      lines: list[str] = []
      monkeypatch.setattr(
          runtime, "TerminalProgress", lambda **_kwargs: _StageRecorder(lines)
      )
      monkeypatch.setattr(runtime.uvicorn, "run", lambda *_a, **_k: None)

      runtime.serve_project(fixture, open_browser=False)

      # serve_project announces discovering, and ProjectParser.parse announces it
      # again for a Path input; TerminalProgress collapses the repeat, so compare
      # the deduplicated sequence.
      deduped = [
          stage
          for index, stage in enumerate(lines)
          if index == 0 or stage != lines[index - 1]
      ]
      assert deduped == [
          "discovering",
          "parsing",
          "resolving",
          "checks",
          "layout",
      ]


  class _StageRecorder:
      def __init__(self, sink: list[str]) -> None:
          self._sink = sink

      def stage(self, stage: str) -> None:
          self._sink.append(stage)

      def files_total(self, total: int) -> None:
          pass

      def file_parsed(self) -> None:
          pass
  ```

- [ ] **Step 2:** Run and see it fail.

  ```bash
  pytest tests/test_smoke.py -x -q -k "progress or serve_project"
  ```

  Expected: `ImportError: cannot import name 'TerminalProgress' from
  'codemble.server.runtime'`.

- [ ] **Step 3:** Implement the terminal reporter.

  In `codemble/server/runtime.py`, extend the imports:

  ```python
  import sys
  from collections.abc import Callable
  ```

  and add above `serve_project`:

  ```python
  _STAGE_COPY = {
      "discovering": "Finding your source files",
      "parsing": "Reading each file",
      "resolving": "Connecting imports and calls",
      "checks": "Building graph-only checks",
      "layout": "Placing your galaxy",
  }


  class TerminalProgress:
      """Print the same five stages the in-app loading screen shows."""

      def __init__(
          self,
          write: Callable[[str], None] | None = None,
          isatty: bool | None = None,
      ) -> None:
          self._write = write or (lambda text: sys.stdout.write(text))
          self._isatty = sys.stdout.isatty() if isatty is None else isatty
          self._stage: str | None = None
          self._total = 0
          self._done = 0

      def stage(self, stage: str) -> None:
          # serve_project announces discovering before handing off, and a
          # Path-input parse announces it again; one line is enough.
          if stage == self._stage:
              return
          if self._stage == "parsing" and self._isatty:
              self._write("\n")
          self._stage = stage
          self._write(f"{stage}: {_STAGE_COPY.get(stage, stage)}\n")

      def files_total(self, total: int) -> None:
          self._total = total

      def file_parsed(self) -> None:
          self._done += 1
          if self._isatty and self._total:
              self._write(f"\r  {self._done}/{self._total} files")
  ```

  and replace the parse and app construction inside `serve_project`:

  ```python
      reporter = TerminalProgress()
      # The CLI has usually discovered already (choose_project_scope hands over a
      # ProjectIntake), so announce the stage here; TerminalProgress collapses the
      # repeat when a bare Path makes ProjectParser announce it too.
      reporter.stage("discovering")
      graph = ProjectParser().parse(path, entrypoint=entrypoint, progress=reporter)
      selected_port = port or available_port(host)
      url = f"http://{host}:{selected_port}"
      reporter.stage("checks")
      app = create_app(graph, allowed_hosts=("127.0.0.1", "localhost", "testserver", host))
      reporter.stage("layout")
  ```

  `create_app` already builds `CheckService` for a graph-mode server; add the
  render-document warm next to it in `codemble/server/app.py` so the `layout`
  stage is real work rather than a label:

  ```python
      if graph is not None:
          state.studies = study_service or StudyService.from_environment(graph)
          state.checks = check_service or CheckService(graph)
          state.graph_json()
  ```

- [ ] **Step 4:** Run and see it pass.

  ```bash
  pytest tests/test_smoke.py -q
  ruff check .
  ```

  Expected: all pass. Note that the real CLI always hands `serve_project` a
  `ProjectIntake` (`choose_project_scope` resolves the scope first), so
  `ProjectParser.parse` never reports `discovering` in production — which is why
  `serve_project` announces it and `TerminalProgress.stage` collapses the repeat
  that a bare `Path` would produce.

- [ ] **Step 5:** Commit.

  ```bash
  git add codemble/server/runtime.py codemble/server/app.py tests/test_smoke.py
  git commit -s -m "feat(cli): print the five parse stages while codemble maps a project"
  ```

---

### Task 8: Reset this project's progress

**Files:** `codemble/progress/store.py`, `codemble/server/app.py`,
`tests/test_progress.py`, `tests/test_server.py`

**Interfaces:**

Produces:

```python
# codemble/progress/store.py
class ProgressStore:
    def clear(self) -> None:
        """Forget this project's understood regions; other projects untouched."""
```

`DELETE /api/progress` → `200 {"understood_regions": 0}`; `409` when unbound.
Contract extension — recorded in Task 12's Decision Log entry.

- [ ] **Step 1:** Write the failing store and endpoint tests.

  Append to `tests/test_progress.py`:

  ```python
  def test_clear_forgets_only_this_projects_regions(tmp_path: Path) -> None:
      from codemble.adapters.python_ast import PythonAstAdapter
      from codemble.progress import ProgressStore

      fixture = Path(__file__).parent / "fixtures" / "sampleproj"
      other = tmp_path / "other"
      other.mkdir()
      (other / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")

      graph = PythonAstAdapter().parse(fixture)
      other_graph = PythonAstAdapter().parse(other)
      store = ProgressStore(graph, tmp_path / "progress")
      other_store = ProgressStore(other_graph, tmp_path / "progress")
      store.set_mode("expert")
      store.mark_understood("app")
      other_store.mark_understood("solo")

      store.clear()

      assert store.understood_regions() == frozenset()
      assert other_store.understood_regions() == frozenset({"solo"})
      assert store.mode() == "expert", "clearing progress must not reset preferences"
      assert other_store.path.exists()
  ```

  Append to `tests/test_server.py`:

  ```python
  def test_progress_can_be_cleared_for_the_bound_project_only(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
      graph = PythonAstAdapter().parse(FIXTURE)
      checks = CheckService(graph, ProgressStore(graph, tmp_path / "progress"))
      client = TestClient(
          create_app(
              graph,
              tmp_path / "missing",
              StudyService(graph, cache_root=tmp_path / "cache"),
              checks,
          )
      )
      for check in generate_checks(graph, "app"):
          client.post(
              f"/api/regions/app/checks/{check.id}",
              json={"selected_ids": list(check.answer_ids)},
          )
      lit = client.get("/api/graph").json()

      cleared = client.delete("/api/progress")
      after = client.get("/api/graph").json()

      assert next(region for region in lit["regions"] if region["id"] == "app")[
          "understood"
      ]
      assert cleared.status_code == 200
      assert cleared.json() == {"understood_regions": 0}
      assert (
          next(region for region in after["regions"] if region["id"] == "app")[
              "understood"
          ]
          is False
      ), "the cached graph must not survive a progress reset"


  def test_clearing_progress_requires_a_bound_project(tmp_path: Path) -> None:
      from codemble.server.app import PickerConfig

      client = TestClient(
          create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
      )

      assert client.delete("/api/progress").status_code == 409
  ```

- [ ] **Step 2:** Run and see them fail.

  ```bash
  pytest tests/test_progress.py tests/test_server.py -x -q -k "clear or progress_can_be"
  ```

  Expected: `AttributeError: 'ProgressStore' object has no attribute 'clear'`,
  then a `405 Method Not Allowed` for the endpoint test.

- [ ] **Step 3:** Implement the store method and the route.

  In `codemble/progress/store.py`, add after `mark_understood`:

  ```python
      def clear(self) -> None:
          """Forget this project's understood regions, keeping its preferences.

          Scoped to ``self.path``, which is keyed by this project's root, so no
          other project's progress can be touched.
          """

          payload = self._read()
          payload["schema_version"] = _SCHEMA_VERSION
          payload["project_root"] = self._graph.project_root
          payload["regions"] = {}
          self._write(payload)
  ```

  In `codemble/server/app.py`, add beside the mode routes:

  ```python
      @app.delete("/api/progress")
      def clear_progress() -> dict[str, int]:
          checks, _ = _services()
          checks.progress.clear()
          state.invalidate_graph_json()
          return {"understood_regions": len(checks.progress.understood_regions())}
  ```

  In-memory pass state (`CheckService._passed`) is deliberately untouched: it is
  session-local by design, and the region will re-dim on the next graph read
  because `understood_regions()` is now empty.

- [ ] **Step 4:** Run and see them pass.

  ```bash
  pytest -q
  ruff check .
  ```

- [ ] **Step 5:** Commit.

  ```bash
  git add codemble/progress/store.py codemble/server/app.py tests/test_progress.py \
    tests/test_server.py
  git commit -s -m "feat(progress): let a learner clear the bound project's saved progress"
  ```

---

### Task 9: Learner session — parse polling and progress clearing

**Files:** `web/src/learnerSession.js`, `web/scripts/check_learner_session.mjs`

**Interfaces:**

Consumes: `POST /api/picker/select` (202), `GET /api/picker/progress`,
`POST /api/picker/reset` (Phase A), `DELETE /api/progress` (Task 8).

Produces:

- State field `parseProgress` (object | null), shape:

  ```js
  {
    state: "parsing" | "ready" | "error" | "idle",
    stage: string | null,
    files_done: number,
    files_total: number,
    error: string | null,
    pollError: string,   // "" when the last poll succeeded
    attempts: number,    // consecutive failed polls
    path: string,        // the folder being parsed, for the retry button
  }
  ```

- Adapter methods on **both** adapters:
  `fetchParseProgress(signal)`, `clearProgress(signal)`.
- Event `CLEAR_PROGRESS` (contract extension, Task 12 records it).
- `selectProject` maps a 202 to `{state: "parsing"}` and starts the internal
  poll loop; no new event, per the contract's Phase C row.
- `RESET_PROJECT` (Phase A) additionally aborts the poll, clears its timer, and
  clears `parseProgress`.

Session invariants preserved: one `AbortController` per concern
(`progressController` is new), the `lifecycle` counter guarding stale responses,
`commit()`'s check clearing, and `deriveSnapshot` re-resolving against the
language-focused graph.

- [ ] **Step 1:** Write the failing session checks.

  Append to `web/scripts/check_learner_session.mjs`, before the `makeGraph`
  declaration:

  ```js
  // The earlier illumination assertion fires its timer without deleting it, so
  // start the Phase C blocks from a clean timer map.
  pendingTimers.clear();

  // Phase C: a 202 select drives a polled loading screen, not a frozen tab.
  const parseFixture = () => ({
    graph,
    picker: {
      browse: {
        "": {
          path: "/home/u",
          parent: null,
          entries: [{ name: "demo", path: "/home/u/demo" }],
        },
      },
      recents: [],
      selections: { "/home/u/demo": { state: "parsing" } },
      // The session seeds stage "discovering" itself from the 202, so the first
      // served payload is the first real server observation.
      progress: [
        {
          state: "parsing",
          stage: "parsing",
          files_done: 640,
          files_total: 1000,
          error: null,
        },
        {
          state: "ready",
          stage: null,
          files_done: 1000,
          files_total: 1000,
          error: null,
        },
      ],
    },
  });

  const parseSession = createLearnerSession({
    adapter: createInMemoryLearnerSessionAdapter(parseFixture()),
    clock,
  });
  await parseSession.start();
  await parseSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  let parseSnapshot = parseSession.getSnapshot();
  assert.equal(parseSnapshot.status, "picking");
  assert.equal(parseSnapshot.picker.busy, true);
  assert.equal(parseSnapshot.parseProgress.stage, "discovering");
  assert.equal(parseSnapshot.parseProgress.path, "/home/u/demo");
  assert.equal(pendingTimers.size, 1, "a parsing poll is scheduled, not spun");

  await fireOnlyTimer();
  parseSnapshot = parseSession.getSnapshot();
  assert.equal(parseSnapshot.parseProgress.stage, "parsing");
  assert.equal(parseSnapshot.parseProgress.files_done, 640);
  assert.equal(parseSnapshot.parseProgress.files_total, 1000);

  await fireOnlyTimer();
  parseSnapshot = parseSession.getSnapshot();
  assert.equal(parseSnapshot.status, "ready");
  assert.equal(parseSnapshot.parseProgress, null);
  assert.equal(parseSnapshot.graph, graph);
  assert.equal(pendingTimers.size, 0, "polling stops once the parse is ready");
  parseSession.dispose();

  // A crashed parse thread surfaces in-app and the same path can be retried.
  const failing = parseFixture();
  failing.picker.progress = [
    { state: "error", stage: null, files_done: 3, files_total: 9, error: "boom" },
  ];
  const failSession = createLearnerSession({
    adapter: createInMemoryLearnerSessionAdapter(failing),
    clock,
  });
  await failSession.start();
  await failSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  await fireOnlyTimer();
  let failSnapshot = failSession.getSnapshot();
  assert.equal(failSnapshot.status, "picking");
  assert.equal(failSnapshot.parseProgress, null);
  assert.equal(failSnapshot.picker.busy, false, "a failed parse re-arms the picker");
  assert.equal(failSnapshot.picker.error, "boom");
  failSession.dispose();

  // A poll failure backs off and reports honestly instead of going silent.
  const flaky = parseFixture();
  const flakyBase = createInMemoryLearnerSessionAdapter(flaky);
  let progressCalls = 0;
  const flakySession = createLearnerSession({
    adapter: {
      ...flakyBase,
      async fetchParseProgress(options = {}) {
        progressCalls += 1;
        if (progressCalls === 1) throw new Error("network hiccup");
        return flakyBase.fetchParseProgress(options);
      },
    },
    clock,
  });
  await flakySession.start();
  await flakySession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  await fireOnlyTimer();
  let flakySnapshot = flakySession.getSnapshot();
  assert.equal(flakySnapshot.parseProgress.pollError, "network hiccup");
  assert.equal(flakySnapshot.parseProgress.attempts, 1);
  assert.equal(pendingTimers.size, 1, "a failed poll retries with backoff");
  await fireOnlyTimer();
  flakySnapshot = flakySession.getSnapshot();
  assert.equal(flakySnapshot.parseProgress.pollError, "");
  assert.equal(flakySnapshot.parseProgress.attempts, 0);
  flakySession.dispose();

  // Reset during a parse cancels the poll and returns to the picker.
  const cancelSession = createLearnerSession({
    adapter: createInMemoryLearnerSessionAdapter(parseFixture()),
    clock,
  });
  await cancelSession.start();
  await cancelSession.dispatch({ type: "SELECT_PROJECT", path: "/home/u/demo" });
  assert.equal(pendingTimers.size, 1);
  await cancelSession.dispatch({ type: "RESET_PROJECT" });
  const cancelSnapshot = cancelSession.getSnapshot();
  assert.equal(cancelSnapshot.parseProgress, null);
  assert.equal(pendingTimers.size, 0, "reset cancels the scheduled poll");
  cancelSession.dispose();

  // Clearing progress reloads the graph so lit systems dim again.
  const clearAdapter = createInMemoryLearnerSessionAdapter({ graph: understoodGraph });
  let cleared = 0;
  const clearSession = createLearnerSession({
    adapter: {
      ...clearAdapter,
      async clearProgress(options = {}) {
        cleared += 1;
        return { understood_regions: 0 };
      },
      async loadGraph(options = {}) {
        return cleared ? graph : understoodGraph;
      },
    },
    clock,
  });
  await clearSession.start();
  assert.equal(clearSession.getSnapshot().region.understood, true);
  await clearSession.dispatch({ type: "CLEAR_PROGRESS" });
  assert.equal(cleared, 1);
  assert.equal(clearSession.getSnapshot().graph, graph);
  assert.equal(clearSession.getSnapshot().region.understood, false);
  clearSession.dispose();

  // HTTP adapter: exact URLs and the 202 mapping.
  const phaseCCalls = [];
  const phaseCHttp = createHttpLearnerSessionAdapter(async (url, options = {}) => {
    phaseCCalls.push({ url, options });
    if (url === "/api/picker/select") {
      return { ok: true, status: 202, json: async () => ({ state: "parsing" }) };
    }
    return { ok: true, status: 200, json: async () => ({ state: "parsing" }) };
  });
  assert.deepEqual(await phaseCHttp.selectProject("/home/u/demo"), {
    state: "parsing",
  });
  await phaseCHttp.fetchParseProgress();
  await phaseCHttp.clearProgress();
  assert.deepEqual(
    phaseCCalls.map(({ url }) => url),
    ["/api/picker/select", "/api/picker/progress", "/api/progress"],
  );
  assert.equal(phaseCCalls.at(-1).options.method, "DELETE");

  async function fireOnlyTimer() {
    assert.equal(pendingTimers.size, 1, "exactly one timer must be pending");
    const [timerId, callback] = pendingTimers.entries().next().value;
    pendingTimers.delete(timerId);
    await callback();
  }
  ```

- [ ] **Step 2:** Run and see it fail.

  ```bash
  cd web && node scripts/check_learner_session.mjs
  ```

  Expected: `AssertionError [ERR_ASSERTION]: Expected values to be strictly
  equal: undefined !== 'discovering'` — `parseProgress` does not exist yet.

- [ ] **Step 3:** Extend the session.

  In `web/src/learnerSession.js`, add the poll constants above
  `createLearnerSession`:

  ```js
  const POLL_INTERVAL = 300;
  const POLL_BACKOFF_BASE = 400;
  const POLL_BACKOFF_CEILING = 4000;
  ```

  Add `parseProgress: null,` to the initial `deriveSnapshot({...})` object
  (beside `picker: null`), and declare the new handles beside the other
  controllers:

  ```js
    let progressController = null;
    let progressTimer = null;
  ```

  Replace `selectProject`'s success branch and add the poll loop:

  ```js
    async function selectProject(path) {
      if (snapshot.status !== "picking" || snapshot.picker?.busy) return undefined;
      abortController(pickerController);
      pickerController = new AbortController();
      const controller = pickerController;
      commit({ picker: { ...snapshot.picker, busy: true, error: "", scale: null } });
      try {
        const result = await adapter.selectProject(path, { signal: controller.signal });
        if (controller.signal.aborted || snapshot.status !== "picking") return result;
        if (result.state === "parsing") {
          commit({
            parseProgress: {
              state: "parsing",
              stage: "discovering",
              files_done: 0,
              files_total: 0,
              error: null,
              pollError: "",
              attempts: 0,
              path,
            },
          });
          schedulePoll(0);
          return result;
        }
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

    function schedulePoll(delay) {
      if (progressTimer !== null) clock.clearTimeout(progressTimer);
      progressTimer = clock.setTimeout(async () => {
        progressTimer = null;
        await pollParseProgress();
      }, delay);
    }

    function stopPolling() {
      abortController(progressController);
      progressController = null;
      if (progressTimer !== null) {
        clock.clearTimeout(progressTimer);
        progressTimer = null;
      }
    }

    async function pollParseProgress() {
      if (!snapshot.parseProgress) return;
      abortController(progressController);
      progressController = new AbortController();
      const controller = progressController;
      const previous = snapshot.parseProgress;
      let payload;
      try {
        payload = await adapter.fetchParseProgress({ signal: controller.signal });
      } catch (requestError) {
        if (
          progressController !== controller ||
          isAbortError(requestError) ||
          !snapshot.parseProgress
        ) {
          return;
        }
        const attempts = previous.attempts + 1;
        commit({
          parseProgress: {
            ...previous,
            pollError: errorMessage(requestError),
            attempts,
          },
        });
        schedulePoll(
          Math.min(POLL_BACKOFF_CEILING, POLL_BACKOFF_BASE * 2 ** (attempts - 1)),
        );
        return;
      }
      if (progressController !== controller || !snapshot.parseProgress) return;
      if (payload.state === "ready") {
        stopPolling();
        commit({ parseProgress: null, picker: null });
        lifecycle += 1;
        const requestLifecycle = lifecycle;
        abortController(graphController);
        graphController = new AbortController();
        await loadProjectGraph(graphController, requestLifecycle);
        return;
      }
      if (payload.state === "error" || payload.state === "idle") {
        stopPolling();
        commit({
          parseProgress: null,
          picker: {
            ...snapshot.picker,
            busy: false,
            error: payload.error ?? "",
          },
        });
        return;
      }
      commit({
        parseProgress: {
          ...previous,
          ...payload,
          pollError: "",
          attempts: 0,
        },
      });
      schedulePoll(POLL_INTERVAL);
    }

    async function clearProgress() {
      await adapter.clearProgress({});
      lifecycle += 1;
      const requestLifecycle = lifecycle;
      abortController(graphController);
      graphController = new AbortController();
      return loadProjectGraph(graphController, requestLifecycle);
    }
  ```

  Add the event to `dispatch`, beside Phase A's `RESET_PROJECT`:

  ```js
        case "CLEAR_PROGRESS":
          return clearProgress();
  ```

  In Phase A's `RESET_PROJECT` handler, call `stopPolling()` and include
  `parseProgress: null` in the commit that returns to the picker. In `dispose()`,
  add `progressController` to the abort list and call `stopPolling()`.

  In `createHttpLearnerSessionAdapter`, map the 202 and add the two methods:

  ```js
      async selectProject(path, options = {}) {
        const response = await fetchImplementation("/api/picker/select", {
          ...options,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path }),
        });
        const payload = await response.json().catch(() => null);
        if (response.ok) {
          return { state: response.status === 202 ? "parsing" : "ready" };
        }
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
      fetchParseProgress(options = {}) {
        return request("/api/picker/progress", "Parse progress", options);
      },
      clearProgress(options = {}) {
        return request("/api/progress", "Progress reset", {
          ...options,
          method: "DELETE",
        });
      },
  ```

  In `createInMemoryLearnerSessionAdapter`, accept the scripted payloads and
  implement both methods:

  ```js
    const progressPayloads = [...(picker?.progress ?? [])];
    // ...
      async fetchParseProgress(options = {}) {
        throwIfAborted(options.signal);
        if (!progressPayloads.length) {
          throw new Error("No in-memory parse progress left to serve.");
        }
        const payload = progressPayloads.shift();
        if (payload.state === "ready" && pickerPhase) pickerPhase.selected = true;
        return payload;
      },
      async clearProgress(options = {}) {
        throwIfAborted(options.signal);
        return { understood_regions: 0 };
      },
  ```

- [ ] **Step 4:** Run and see it pass.

  ```bash
  cd web && node scripts/check_learner_session.mjs
  ```

  Expected: `learner-session contracts passed` plus no assertion failure from the
  new blocks.

- [ ] **Step 5:** Commit.

  ```bash
  git add web/src/learnerSession.js web/scripts/check_learner_session.mjs
  git commit -s -m "feat(web): poll staged parse progress and clear project progress from the session"
  ```

---

### Task 10: Loading screen, actionable scale prompt, reset control

**Files:** `web/src/App.jsx`, `web/src/styles.css`, `codemble/web_dist/**`

**Interfaces:**

Consumes: `parseProgress` and the `CLEAR_PROGRESS` / `RESET_PROJECT` events
(Task 9); `picker.scale` (`{file_count, scale_cap, root, suggestions}`).

Produces: presentation only — `LoadingScreen`, `ScaleGuidance` inside
`PickerScreen`, and a reset-progress control on the star chart. No layout, no
game logic, no derived truth.

The reset control lives on the star chart rather than the header: the star chart
is the surface that shows progress, and Phases A and B are rewriting the header.

- [ ] **Step 1:** Add the loading screen.

  In `web/src/App.jsx`, destructure `parseProgress` from `state` and render it
  before the picker branch:

  ```jsx
    if (parseProgress) {
      return (
        <LoadingScreen
          progress={parseProgress}
          onCancel={() => session.dispatch({ type: "RESET_PROJECT" })}
          onRetry={() =>
            session.dispatch({ type: "SELECT_PROJECT", path: parseProgress.path })
          }
        />
      );
    }
  ```

  and add the component:

  ```jsx
  const STAGE_COPY = {
    discovering: "Finding your source files",
    parsing: "Reading each file",
    resolving: "Connecting imports and calls",
    checks: "Building graph-only checks",
    layout: "Placing your galaxy",
  };
  const STAGE_ORDER = ["discovering", "parsing", "resolving", "checks", "layout"];

  function LoadingScreen({ progress, onCancel, onRetry }) {
    const { stage, files_done: done, files_total: total, pollError, path } = progress;
    const reached = STAGE_ORDER.indexOf(stage);
    return (
      <main className="loading-screen" aria-busy="true">
        <header className="loading-header">
          <p className="picker-wordmark">Codemble</p>
          <h1>Mapping {path}</h1>
          <p className="loading-subtitle">
            Parsing runs on your machine. Nothing is sent anywhere.
          </p>
        </header>
        <ol className="loading-stages" aria-label="Parse stages">
          {STAGE_ORDER.map((name, index) => (
            <li
              key={name}
              data-state={
                index < reached ? "done" : index === reached ? "active" : "waiting"
              }
            >
              <span>{STAGE_COPY[name]}</span>
              {name === "parsing" && total ? (
                <small>
                  {done}/{total} files
                </small>
              ) : null}
            </li>
          ))}
        </ol>
        <progress
          className="loading-meter"
          value={total ? done : 0}
          max={total || 1}
          aria-label={`${done} of ${total} files read`}
        />
        <p className="loading-live" aria-live="polite">
          {STAGE_COPY[stage] ?? "Starting"}
          {total ? ` · ${done}/${total} files` : ""}
        </p>
        {pollError ? (
          <p className="loading-error" role="status">
            Lost contact with the local server ({pollError}). Retrying…
          </p>
        ) : null}
        <div className="loading-actions">
          <button type="button" onClick={onCancel}>
            Cancel and pick another project
          </button>
          <button type="button" onClick={onRetry}>
            Retry this project
          </button>
        </div>
      </main>
    );
  }
  ```

  The failure path renders the picker again with `picker.error` set (Task 9), so
  "no server restart" holds; `onRetry` re-selects the same path without one.

- [ ] **Step 2:** Make the scale prompt actionable.

  In `PickerScreen`, replace the dead `{scale ? <p className="picker-scale">…}`
  sentence with:

  ```jsx
        {scale ? (
          <ScaleGuidance scale={scale} busy={busy} onBrowse={onBrowse} />
        ) : null}
  ```

  and add both components below `PickerScreen`:

  ```jsx
  function ScaleGuidance({ scale, busy, onBrowse }) {
    // "." counts files sitting directly in the root, which is not a smaller
    // scope, so it never becomes a button.
    const scopes = scale.suggestions.filter((suggestion) => suggestion.path !== ".");
    return (
      <section className="picker-scale" role="alert" aria-labelledby="picker-scale-heading">
        <h2 id="picker-scale-heading">That folder is too big to map at once.</h2>
        <p>
          It has {scale.file_count} supported source files; Codemble maps up to{" "}
          {scale.scale_cap}. Choose a smaller scope — busiest first.
        </p>
        {scopes.length ? (
          <ul className="picker-scale-scopes">
            {scopes.map((suggestion) => (
              <li key={suggestion.path}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onBrowse(`${scale.root}/${suggestion.path}`)}
                >
                  <span>{suggestion.path}/</span>
                  <small>{suggestion.file_count} files</small>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <PathEntry busy={busy} onBrowse={onBrowse} />
      </section>
    );
  }

  function PathEntry({ busy, onBrowse }) {
    const [typed, setTyped] = useState("");
    return (
      <form
        className="picker-path-entry"
        onSubmit={(event) => {
          event.preventDefault();
          const target = typed.trim();
          if (target) onBrowse(target);
        }}
      >
        <label htmlFor="picker-path-input">Or type a folder path</label>
        <input
          id="picker-path-input"
          type="text"
          value={typed}
          disabled={busy}
          placeholder="/Users/you/project/src"
          onChange={(event) => setTyped(event.target.value)}
        />
        <button type="submit" disabled={busy || !typed.trim()}>
          Go
        </button>
      </form>
    );
  }
  ```

  The jail is enforced server-side: `/api/picker/browse` returns 403 for a path
  outside `$HOME`, and the session already renders that message in
  `picker.error`. Nothing about the jail moves to the client.

- [ ] **Step 3:** Add the reset-progress control.

  In `StarChart`, accept `onClearProgress` and render a confirming control after
  the ledger:

  ```jsx
  function StarChart({ chart, studiedCount, onClearProgress }) {
    const understood = chart.filter((item) => item.understood_nodes > 0).length;
    const [confirming, setConfirming] = useState(false);
    // ... unchanged header and ledger ...
      <section className="progress-reset">
        {confirming ? (
          <>
            <p role="alert">
              This dims every system you lit in this project. Other projects keep
              their progress.
            </p>
            <button
              type="button"
              className="progress-reset__confirm"
              onClick={() => {
                setConfirming(false);
                onClearProgress();
              }}
            >
              Yes, clear this project's progress
            </button>
            <button type="button" onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirming(true)}>
            Clear this project's progress
          </button>
        )}
      </section>
  ```

  and pass the handler at the call site:

  ```jsx
        <StarChart
          chart={chart}
          studiedCount={focusedStudiedCount}
          onClearProgress={() => session.dispatch({ type: "CLEAR_PROGRESS" })}
        />
  ```

- [ ] **Step 4:** Style the new surfaces.

  Append to `web/src/styles.css`, reusing existing tokens only (kohaku amber
  stays reserved for understanding; ruri stays interaction):

  ```css
  .loading-screen {
    display: grid;
    gap: 1.5rem;
    align-content: center;
    justify-items: start;
    max-width: 46rem;
    margin: 0 auto;
    padding: clamp(1.5rem, 5vw, 4rem);
    min-height: 100dvh;
  }
  .loading-stages {
    display: grid;
    gap: 0.5rem;
    width: 100%;
    padding: 0;
    margin: 0;
    list-style: none;
  }
  .loading-stages li {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.55rem 0.75rem;
    border-left: 2px solid var(--cm-ink-3);
    color: var(--cm-ink-2);
  }
  .loading-stages li[data-state="active"] {
    border-left-color: var(--cm-orbit);
    color: var(--cm-ink-0);
  }
  .loading-stages li[data-state="done"] {
    color: var(--cm-ink-1);
  }
  .loading-meter {
    width: 100%;
    height: 0.4rem;
  }
  .loading-error {
    color: var(--cm-ink-1);
  }
  .loading-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }
  .picker-scale-scopes {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0;
    margin: 0.75rem 0;
    list-style: none;
  }
  .picker-scale-scopes button {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15rem;
  }
  .picker-path-entry {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }
  .picker-path-entry input {
    flex: 1 1 16rem;
    min-width: 0;
  }
  .progress-reset {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
    margin-top: 2rem;
  }
  ```

  If any token name above is absent from `web/src/tokens.css` after Phase B,
  substitute the nearest shipped token rather than adding a new one; this task
  introduces no palette values.

- [ ] **Step 5:** Verify by running the app, then build.

  ```bash
  cd web && npm run check
  ```

  Expected: both node checks pass, then `vite build` writes `codemble/web_dist`.

  Then drive the real surfaces (UI is verified by running it, per the repo rule):

  ```bash
  python -m codemble --no-open --port 8123
  ```

  Confirm in the browser at `http://127.0.0.1:8123`:
  1. picking a normal folder shows the staged loading screen and lands in the
     galaxy;
  2. picking an over-cap folder shows clickable scope buttons that navigate the
     browser into that subdirectory;
  3. typing an outside-`$HOME` path shows the 403 message and does not navigate;
  4. "Cancel and pick another project" during a parse returns to the picker;
  5. the star chart's clear control asks for confirmation, then dims the systems.
  6. Re-check 1-5 at a 320 px viewport width and with keyboard only.

- [ ] **Step 6:** Commit including the rebuilt bundle.

  ```bash
  git add web/src/App.jsx web/src/styles.css codemble/web_dist
  git commit -s -m "feat(web): add the staged loading screen, clickable scope prompt, and progress reset"
  ```

---

### Task 11: Verify at ~1,000 files

**Files:** none committed. This task produces evidence, not code.

- [ ] **Step 1:** Build a ~1,000-file target outside the repo.

  ```bash
  SCRATCH="$(mktemp -d)/bigproj"
  python - "$SCRATCH" <<'PY'
  import sys
  from pathlib import Path

  root = Path(sys.argv[1])
  for package in range(20):
      directory = root / f"pkg_{package:02d}"
      directory.mkdir(parents=True, exist_ok=True)
      (directory / "__init__.py").write_text("", encoding="utf-8")
      for module in range(50):
          name = f"mod_{module:02d}"
          previous = f"mod_{module - 1:02d}" if module else None
          imports = f"from . import {previous}\n" if previous else ""
          body = (
              f"{imports}\n\n"
              f"def run_{package:02d}_{module:02d}() -> int:\n"
              + (f"    return {previous}.run_{package:02d}_{module - 1:02d}() + 1\n"
                 if previous else "    return 0\n")
          )
          (directory / f"{name}.py").write_text(body, encoding="utf-8")
  (root / "app.py").write_text(
      'from pkg_00 import mod_00\n\n\n'
      'def main() -> None:\n    print(mod_00.run_00_00())\n\n\n'
      'if __name__ == "__main__":\n    main()\n',
      encoding="utf-8",
  )
  print(sum(1 for _ in root.rglob("*.py")), "files at", root)
  PY
  echo "$SCRATCH"
  ```

  Expected: `1021 files`. Confirm it is under the new cap and over the old one.

- [ ] **Step 2:** Time the blocking CLI path and watch the stages.

  ```bash
  time python -m codemble "$SCRATCH" --no-open --port 8124
  ```

  Expected: `discovering`, `parsing` with a live `n/1021` counter, `resolving`,
  `checks`, `layout`, then the "Open http://…" line. Record the wall-clock time.
  Stop the server with Ctrl-C.

- [ ] **Step 3:** Watch the in-app loading screen for the same target.

  ```bash
  python -m codemble --no-open --port 8125
  ```

  In the browser, type the scratch path into the picker's path field, then "Map
  this folder". Expected: the loading screen advances through all five stages
  with a moving file counter, then the galaxy renders. Confirm the tab stayed
  responsive throughout (the request thread is free).

- [ ] **Step 4:** Confirm the graph cache and check index at this size.

  With the same server running:

  ```bash
  time curl -s http://127.0.0.1:8125/api/graph -o /dev/null
  time curl -s http://127.0.0.1:8125/api/graph -o /dev/null
  ```

  Expected: the second request is dominated by transfer, not by re-sorting; both
  return the same bytes (`curl -s … | shasum` twice to confirm).

- [ ] **Step 5:** Measure framerate through the existing benchmark path.

  Reload the galaxy at `http://127.0.0.1:8125/?benchmark`, wait ~2 seconds, then
  in the browser console:

  ```js
  document.documentElement.dataset.codembleFps;
  ```

  Expected: a value present (the probe only runs at ≥900 nodes) and above 30 on a
  mid-range laptop. Record it.

- [ ] **Step 6:** Cancel mid-parse for real.

  Restart the picker, start the scratch project, and click "Cancel and pick
  another project" while the counter is moving. Expected: the picker returns
  within a second, `GET /api/picker/progress` reports `idle`, and selecting a
  small project immediately afterwards works.

- [ ] **Step 7:** Record the evidence in the commit that follows.

  No files change here; carry the recorded numbers into Task 12's CHANGELOG entry
  and the build-log page.

---

### Task 12: Documentation, changelog, sidebar, and project state

**Files:** `CHANGELOG.md`, `README.md`, `TESTING.md`, `CLAUDE.md`,
`docs-site/src/content/docs/quickstart.md`,
`docs-site/src/content/docs/installation.md`,
`docs-site/src/content/docs/the-galaxy.md`,
`docs-site/src/content/docs/checks-and-lighting.md`,
`docs-site/src/content/docs/progress/m12-scale.md` (new),
`docs-site/astro.config.mjs`

- [ ] **Step 1:** Update every prose location that states the old cap.

  These are the only prose files that describe the **live** limit; the historical
  records listed in Task 6's table stay untouched.

  `README.md` (the "Boundaries that keep the map truthful" list):

  ```markdown
  - **Scale:** above roughly 1,000 supported source files, choose a subdirectory —
    the in-app picker offers the busiest scopes as buttons and accepts a typed
    path, or pass `codemble --path ./project/subdirectory`.
  ```

  `TESTING.md` (the "Protect your project" list):

  ```markdown
  - Use a local project with at most 1,000 supported source files, or choose a
    smaller subdirectory when Codemble prompts (`--path` from the CLI).
  ```

  `docs-site/src/content/docs/quickstart.md`:

  ```markdown
  For a project above 1,000 supported source files, the picker offers the
  busiest-first subdirectories as buttons and accepts a typed path, right in the
  UI. From the CLI, select the scope yourself:
  ```

  `docs-site/src/content/docs/installation.md` (the "Limits that fail honestly"
  list — this is the edge-cases page):

  ```markdown
  - More than 1,000 supported source files: run
    `codemble --path ./project/subdirectory`; the picker offers the same
    busiest-first scopes as clickable buttons, plus a typed path field. Both stay
    inside your home directory.
  ```

  `CLAUDE.md` (Edge cases & limits):

  ```markdown
  - >~1,000 supported source files → prompt to scope to a subdirectory (LOD
    arrives Phase 2)
  ```

- [ ] **Step 2:** Document the new behaviour on the pages that own it.

  In `docs-site/src/content/docs/the-galaxy.md`, add a short section after the
  page's opening explanation:

  ```markdown
  ## While a large project loads

  Parsing runs on a background thread, so the browser stays responsive. The
  loading screen names the stage it is in — finding files, reading each file,
  connecting imports and calls, building checks, placing the galaxy — and shows a
  real file count, not a guessed percentage. If the parse fails, the message is
  the parser's own and you can retry from the same screen; there is no need to
  restart Codemble. Cancelling returns you to the picker and stops the parse at
  the next file boundary.
  ```

  In `docs-site/src/content/docs/checks-and-lighting.md`, add at the end:

  ```markdown
  ## Starting a project over

  The star chart has a **Clear this project's progress** control behind a
  confirmation. It forgets the understood regions for the project you have open
  and nothing else: progress is stored per project in `~/.codemble/progress/`,
  and other projects keep theirs. Your Easy/Expert preference survives the reset.
  ```

- [ ] **Step 3:** Add the build log and its hand-authored sidebar entry.

  Create `docs-site/src/content/docs/progress/m12-scale.md`:

  ```markdown
  ---
  title: "Build log: M12 scale"
  description: Threaded parsing, staged progress, a 1,000-file cap, and two removed performance cliffs.
  ---

  Phase C of the galaxy UX overhaul made Codemble usable on projects roughly
  three times larger, without changing one byte of parser output.

  ## What changed

  - **Parsing moved off the request thread.** `POST /api/picker/select` now
    answers `202 {"state": "parsing"}` immediately and a worker thread parses.
    `GET /api/picker/progress` reports one of `idle`, `parsing`, `ready`, or
    `error`, with the current stage and a real file count.
  - **Five honest stages**, in order: discovering, parsing, resolving, checks,
    layout. The file counter moves during `parsing` only, because that is the
    only stage measured per file.
  - **Cancellation.** Resetting the picker during a parse sets a flag that is
    checked between files, so the parse stops at the next file boundary and the
    picker re-arms. A crashed parse thread becomes an error state with the
    parser's own message, never a hung server.
  - **The scale cap moved from 300 to 1,000** supported source files. Above it,
    the picker offers the busiest scopes as buttons and accepts a typed path,
    both still jailed to your home directory. A piped, non-interactive CLI run
    now prints those same scopes instead of a bare refusal.
  - **Two measured cliffs removed.** Check generation used to walk every graph
    edge up to four times per region; it now builds one index in a single pass.
    `GET /api/graph` used to re-hydrate and re-sort the whole graph on every
    request; the serialized document is cached and dropped when a region lights
    up, when Home changes, or when the project is rebound.
  - **Clear this project's progress** is available from the star chart, behind a
    confirmation, scoped to the open project.

  ## What did not change

  Check suites and answers are byte-identical to before the index change; a
  committed golden fixture proves it for both the Python and the mixed
  JavaScript/TypeScript fixtures. Progress reporting cannot influence parser
  output: the same source produces the same graph JSON with or without a
  reporter attached, and a test pins that. The `LanguageAdapter` seam is
  unchanged.
  ```

  In `docs-site/astro.config.mjs`, add to the "Build & contribute" items, after
  the M10 entry:

  ```js
              { label: "Build log: M12 scale", slug: "progress/m12-scale" },
  ```

- [ ] **Step 4:** Add the CHANGELOG entry.

  Under `## [Unreleased]` in `CHANGELOG.md`:

  ```markdown
  ### Added
  - Large projects now show a staged loading screen instead of a frozen tab.
    Parsing runs on a worker thread; the app polls `GET /api/picker/progress` and
    names the stage it is in — discovering, parsing, resolving, checks, layout —
    with a real file count. A failed parse reports the parser's own message and
    offers an in-app retry; cancelling stops the parse at the next file boundary.
  - The over-cap prompt is actionable in-app: the busiest subdirectories are
    buttons that navigate the picker, and a typed path field accepts any folder
    inside your home directory. Outside-home paths are still refused.
  - A **Clear this project's progress** control on the star chart, behind a
    confirmation, scoped to the open project only.
  - A non-interactive `codemble` run now prints the busiest-scope suggestions
    with the scale refusal instead of a bare message.

  ### Changed
  - The scale cap moved from 300 to 1,000 supported source files. LOD and
    clustering remain Phase 2 work.
  - `POST /api/picker/select` returns `202 {"state": "parsing"}` instead of
    blocking until the graph is ready.

  ### Fixed
  - Check generation walked every graph edge up to four times per region, and
    rebuilt the node lookup and the option pool per region — an O(regions × graph)
    freeze at bind. One index is now built per bind in a single pass. A committed
    golden fixture proves the generated suites and answers are byte-identical for
    the Python and mixed fixtures.
  - `GET /api/graph` re-hydrated progress and re-sorted every node and edge on
    every request. The serialized document is cached and invalidated on region
    light-up, Home selection, and project bind or reset.
  ```

  Add the measured numbers from Task 11 (parse wall-clock and the `?benchmark`
  framerate at ~1,000 files) to the first "Added" bullet before committing.

- [ ] **Step 5:** Update `CLAUDE.md` Current State, milestone, and Decision Log.

  Add a milestone section after M11:

  ```markdown
  ### M12 — Galaxy UX Phase C: scale ✅
  - [x] Threaded parse behind `202` select, `GET /api/picker/progress`, and a
        staged loading screen with real file counts
  - [x] Cancellation checked between files; a crashed worker becomes an error
        state, never a hung server
  - [x] Scale cap 300 → 1,000; clickable busiest scopes plus a jailed path field;
        suggestions in the non-TTY CLI refusal
  - [x] One per-bind check index replacing the per-region edge scans, pinned by a
        golden suite fixture
  - [x] Cached `/api/graph` document invalidated on light-up, Home, and binding
  - [x] Terminal stage lines for `codemble <path>`; reset-progress control

  **Acceptance:** a ~1,000-file project parses with live progress and reaches an
  interactive galaxy; re-fetching the graph does not re-sort the world; the scale
  prompt is actionable entirely in-app; generated check suites are byte-identical
  to before the index change.
  ```

  Append to the Decision Log (append-only — do not edit the 2026-07-18 "~300"
  row, which stays as the superseded record):

  ```markdown
  | 2026-07-19 | Scale cap raised 300 → 1,000 with a threaded parse and staged progress; LOD/clustering stay Phase 2 | Approved in the galaxy UX overhaul spec. The old cap existed because a blocking parse froze the tab, not because the graph could not hold more; moving the parse off the request thread removes the reason |
  | 2026-07-19 | Progress reporting is a thread-scoped per-file hook (`note_file_parsed`) bound by `ProjectParser`, not a new `LanguageAdapter` parameter | The public adapter seam must stay unchanged for Phase 2 languages; one hook site per adapter also gives cancellation its exact "between files" meaning |
  | 2026-07-19 | Phase C adds `DELETE /api/progress`, the `CLEAR_PROGRESS` session event, and a `clearProgress` adapter method beyond the shared contract's Phase C rows | The contract's Phase C rows covered parse progress only, while gap G23 (no reset-progress control) is mapped to Phase C by the spec; recorded here rather than silently widened |
  | 2026-07-19 | Generated check suites are pinned by a committed golden fixture before any performance work touches `checks/service.py` | The Correctness Contract makes suite drift top-severity, and a refactor that changes an answer is invisible without a byte-level pin |
  ```

  Update the Current State session note to record Phase C and keep the
  "Current milestone" line accurate.

- [ ] **Step 6:** Verify the docs build and the full suite.

  ```bash
  pytest -q
  ruff check .
  cd web && npm run check && cd ..
  cd docs-site && npm install && npm run check && npm run build && cd ..
  ```

  Expected: all green. `npm run build` also proves the new sidebar slug resolves;
  a missing page or a typo'd slug fails the Astro build.

- [ ] **Step 7:** Commit.

  ```bash
  git add CHANGELOG.md README.md TESTING.md CLAUDE.md \
    docs-site/src/content/docs/quickstart.md \
    docs-site/src/content/docs/installation.md \
    docs-site/src/content/docs/the-galaxy.md \
    docs-site/src/content/docs/checks-and-lighting.md \
    docs-site/src/content/docs/progress/m12-scale.md \
    docs-site/astro.config.mjs
  git commit -s -m "docs: document the 1,000-file cap, staged parse progress, and progress reset"
  ```

---

## Self-review

### 1. Spec coverage

| Phase C item | Task | Notes |
| --- | --- | --- |
| 1. Threaded parse, 202 select, `GET /api/picker/progress`, five stages, progress-callback seam, thread safety, crash → error | 1, 2, 3 | Seam in Task 1, state machine in Task 2, HTTP in Task 3 |
| 2. Cancellation on `POST /api/picker/reset`, flag checked between files, state `unpicked` | 2, 3 | Check point is `ParseJob.file_parsed()`, called from each adapter's `_parse_file` |
| 3. `LoadingScreen` polling with AbortController + `lifecycle`, in-app retry, poll backoff | 9, 10 | Session in 9, presentation in 10 |
| 4. Scale cap 300 → 1,000, CLI copy, picker 409 path, tests asserting 300 | 6 | Every 300 location enumerated in Task 6's table |
| 5. Clickable suggestions + jailed path field | 10 | Jail stays server-side; 403 surfaces through `picker.error` |
| 6. Check-generation cliff → one O(E) index, identical suites | 4 | Golden fixture pinned before the refactor |
| 7. Graph response cache with proven invalidation | 5 | Mode verified not to affect the payload; test added anyway |
| 8. CLI stage lines + non-TTY suggestions | 6, 7 | Message change in 6 (single root-cause site), printer in 7 |
| 9. Reset progress with confirm, project-scoped | 8, 10 | Contract extension flagged |
| 10. ~1,000-file verification incl. `?benchmark` | 11 | Concrete generator and commands |

### 2. Placeholder scan

No `TBD`, no "add appropriate error handling", no "similar to Task N". Every code
step carries a real body. Three deliberate cross-references, all bounded:
Task 3's reset handler states which two lines Phase A does not have; Task 10's
CSS says to substitute a shipped token if Phase B renamed one; Task 7's step 7
notes the signature string may render differently per Python version and gives
the exact command to obtain it.

### 3. Type consistency

- `GET /api/picker/progress` returns exactly the contract's five keys, with
  `state` in `idle|parsing|ready|error`, `stage: str|null`, `error: str|null`.
  `ParseJob.snapshot()` is the single producer, asserted key-for-key in
  `tests/test_parse_job.py` and `tests/test_server.py`.
- `POST /api/picker/select` returns `202 {"state": "parsing"}`, matching the
  contract line; the HTTP adapter maps status 202 to `{state: "parsing"}` and the
  in-memory adapter's fixture uses the same literal.
- Session field is `parseProgress` (contract's exact name); the adapter method is
  `fetchParseProgress(signal)` with the signal last, as the contract requires.
  Phase C adds no dispatch event for polling, per the contract; the one added
  event (`CLEAR_PROGRESS`) is flagged as an extension in two places.
- `ParseProgress` has one shape across Task 1 (protocol), Task 2 (`ParseJob`),
  Task 3 (`_ProjectState.bind`), and Task 7 (`TerminalProgress`): `stage(str)`,
  `files_total(int)`, `file_parsed()`. `TerminalProgress` and the test
  `_Recorder`s implement all three.
- `STAGES` is defined once in `codemble/server/parse_job.py`; `runtime.py` and
  the tests import it, and `ParseJob.stage()` rejects any value outside it, so an
  unknown stage can never reach a learner. `App.jsx` carries a hand-kept mirror
  (`STAGE_ORDER` plus `STAGE_COPY`); the loading screen renders an unknown stage
  as "Starting" rather than crashing, and Task 10's step 5 checks the five
  labels against a real run. Keep the two lists in the same order.
- `ProjectScaleError` keeps `.intake` and `.scale_cap`; only `__str__` changes,
  so `app.py`'s structured 409 detail is untouched and the picker's
  `{file_count, scale_cap, root, suggestions}` shape is stable across Tasks 6,
  9, and 10.
- `generate_checks(graph, region_id) -> tuple[Check, ...]` and
  `CheckService(graph, progress=None)` keep their published signatures; only
  private helpers change arity (`_CheckIndex` replaces the `graph, nodes` pair).
