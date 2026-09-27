# Codemble audit repairs — Sol execution plan

Status: **planning complete; implementation not started or authorized by this planning request.**

This plan covers all eleven Fix candidates from audit run
`20260927T022919Z-85c822af`, evidence revision
`b97fcf7574123c361a9a7b18642c7b9d8318a3fe`. The source revision was rechecked while
planning. Findings remain Open and unselected in the private audit ledger.
Dates in the audit use UTC (2026-09-27); this plan uses the owner's local date.

## 1. Start here

Read `CLAUDE.md` in full. Its Correctness Contract, Non-Goals, product identity,
and existing operational gates remain authoritative. Then read this plan and
resume the named run using the installed `dev-review` skill's ledger helper.
Do not rerun a whole audit merely to rediscover these eleven defects.

The plan is self-contained enough to rebuild the fictional reproductions if
temporary audit captures disappear. Private receipts and the offline report
belong in the private ledger/evidence directory, never in committed docs.
The ledger helper must be resolved from the installed skill, not from a script
of the same name in the repository. The current clone stores the run beneath
its Git common directory in `dev-review/runs/`.

### Copyable instruction for the future execution task

> Execute `docs/plans/2026-09-26-dev-review-sol-execution.md` with Sol. I select
> **all Fix candidates from run `20260927T022919Z-85c822af`**, findings
> `DR-85c822af-001` through `DR-85c822af-011`, at evidence revision
> `b97fcf7574123c361a9a7b18642c7b9d8318a3fe`. Revalidate any changed evidence,
> record the selection receipts, and implement and verify those bounded fixes
> in an isolated checkout. Follow the plan's ordering, three-specialist review
> protocol, tests, runtime gates, and final council gate. Preserve unrelated
> work. Do not commit, merge, push, release, deploy, connect public sharing, or
> change installed-app/user state. Stop with the reviewed candidate and report
> any remaining blocker honestly.

That paragraph is a **proposed future instruction**, not authority granted by
the present planning request. A narrower selection must explicitly name its
stable IDs; execute its dependencies only to the extent authorized. Do not
silently treat research items as selected repairs.

## 2. Baseline and boundaries

The audit verdict is **6.4/10, Hold, Medium coverage confidence**. Four P1
findings cap the headline; the weighted sampled score is 7.1. These are audit
judgments, not production certification. Do not increase the score until the
reproductions pass on the actual candidate.

| Baseline | Recorded evidence | Execution requirement |
| --- | --- | --- |
| Python | 682 passed; one package-version assertion failed because the existing environment reports distribution 0.22.0 while source is 0.23.0 | Install current source in a new contained environment. All tests, including version/package identity, must pass. Never edit the assertion or distribution metadata by hand. |
| Lint | `ruff check .` passed | Repeat on final source. |
| Frontend | `npm run check` passed, including 26 Node contracts and Vite build; all 13 SPA files matched committed bytes | Preserve contracts, add meaningful regressions, regenerate the shipped bundle from final source and prove a second build is stable. |
| Docs | Structural release facts, Astro diagnostics, and 28-page build passed | Repeat after final documentation synchronization. |
| Runtime | Eight non-UI failures independently reproduced; three UI failures reproduced with focused Playwright WebKit | Replay each same-condition failure as a passing regression; save before/after receipts. |
| Broad browser matrix | Chromium GPU startup failed inside the contained runtime; focused WebKit worked | Use a compatible contained host. Full browser acceptance remains a blocker until exercised; do not call the old failure an application defect. |
| Other gates | Fresh install, live providers, hosted CI/current downloads, unaided learner tests, and independent M20 operations were not established by this audit | Clean local package/install is part of this repair gate. External/release/learner/M20 operations remain separate. |

Preserve the nine-language adapter interface, conservative possible calls,
graph-only answers, no-key local Study, source citations, file-scoped progress,
complete Map, bounded orbit, Formal Edo palette, check-only amber, reduced
motion, existing provider contracts, and disconnected sharing boundaries.
No dependency upgrade, parser rewrite, new quest type, schema-wide graph change,
background watcher, general job platform, telemetry, or visual redesign belongs
in this repair plan.

Keep `.git-backup-remote`, `.last-git-backup-ts`, the dirty historical graphics
worktree, and unrelated/unique refs intact. Do not run destructive cleanup.
This is repair planning, not a roadmap promotion or release amendment.

## 3. Execution ownership and ordering

Sol is the senior coordinator and sole integrator. Use the three real
specialists required by `dev-review`: **A** architecture/correctness,
**P** production/adversarial, **U** product/UX. Assign actual agent identities
and write sets before each slice; the labels below are roles, not fabricated
review receipts. A peer must not be the author. Capacity limits permit
sequential work, not simulated reviewers.

Default to **serial slices on the last accepted candidate**. This avoids
conflicts in `tests/test_server.py`, `StudyPanel.jsx`, `App.jsx`,
`learnerSession.js`, and the browser harness. Do not parallelize generated SPA,
Graphify, documentation, fixtures, or test harness writes. If parallelizing
disjoint work later, first declare exclusive paths and integrate through Sol.

| Order | Package / stable finding | Owner → peer | Dependency / reason |
| --- | --- | --- | --- |
| 0 | G0: environment, authority, baseline | Sol, reviewed by P | Required before any repair |
| 1 | S01 / `DR-85c822af-001`: proxy-free local narration | P → A | Close local transport boundary first |
| 2 | S02 / `DR-85c822af-002`: Python lexical ownership | A → P | Correct graph evidence before consuming it in checks |
| 3 | S03 / `DR-85c822af-003`: coherent Study source identity | A → U | Owns Study/backend/UI error boundary before narration work |
| 4 | S04 / `DR-85c822af-004`: graph-supported call quiz | A → U | After S02; explicit check-identity compatibility |
| 5 | S05 / `DR-85c822af-005`: progress transactions | P → A | Establish committed-state behavior before cache tests |
| 6 | S06 / `DR-85c822af-006`: cache generation ownership | A → P | After S05; test against committed mutations |
| 7 | S07 / `DR-85c822af-007`: worker-owned narration budget | P → A | After S01/S03; shared provider/Study/server seams |
| 8 | S08 / `DR-85c822af-008`: obsolete clear refusal | U → A | Before remaining session/mode changes |
| 9 | S09 / `DR-85c822af-009`: consistent launch retry | U → A | Own mode/session/browser files exclusively |
| 10 | S10 / `DR-85c822af-010`: returning save failure feedback | U → P | After S09; same caller and lifecycle seams |
| 11 | S11 / `DR-85c822af-011`: bounded impact language | U → A | After S03/S10; same Study surface |
| 12 | G1: combined acceptance, packaging, documentation | Sol with all three peers | All selected slices accepted |

For every slice: reproduce red → narrow fix and focused green → worker
self-review → senior review of actual diff → independent peer → final senior
acceptance. Bind worker/senior/peer/final receipts to the same candidate tree
digest; a changed tree requires affected re-verification. After two concrete
correction loops, stop that slice with evidence rather than force acceptance.
Keep subsequent dependent slices queued while a prerequisite is unresolved.

## 4. G0 — establish a trustworthy execution baseline

1. Inventory status, current revision, worktrees, applicable instructions, and
   the named ledger/report digest. If source changed, compare each finding's
   owned paths and callers and rerun its reproduction. Keep IDs stable; record
   stale/resolved evidence instead of forcing the old fix.
2. Record the user's actual selection, bound to full run ID, finding ID, and
   verified revision. A planning request alone does not provide this receipt.
3. Create a fresh isolated checkout/worktree from the chosen current base, using
   the `stay-calm-its-codex/` branch prefix if a branch is needed. Transfer this
   plan and its CLAUDE handoff deliberately if they are still uncommitted; never
   copy unrelated main-checkout dirt. Do not commit solely to transfer a plan.
4. Use a new virtual environment with editable `.[dev]` installation from that
   checkout. Follow the project's Node 22 CI contract and existing npm lockfiles;
   do not rewrite locks or silently upgrade dependencies. Validate imported
   source path, installed distribution version, executable paths and dependency
   versions. Explicitly set `CODEMBLE_PYTHON` to the absolute interpreter path
   in this candidate virtualenv for the Python-spawning browser harnesses.
   If regenerating docs captures with `capture:docs`, also bind its separate
   `CODEMBLE_CAPTURE_PYTHON` override to that same interpreter. Inspect each
   harness's actual override rather than assuming a common variable.
   Do not rely on PATH: `check_large_project.mjs` otherwise defaults
   to `python3.12`, while other harnesses default to `python`. Verify the child
   server's imported source and distribution identity too.
   Use pre-provisioned/cache dependencies inside containment; missing
   dependencies are an environment blocker, not permission to allow arbitrary
   repository egress.
5. Inspect scripts before executing them. Use fictional fixtures, a fresh data
   root and cache/temp roots, no provider keys, and an OS/container boundary
   denying external network and unrelated personal-state access while permitting
   necessary loopback. Never replace `HOME`. Prove the boundary before tests.
   Browser profiles and each writer's runtime must be disposable and separate.
6. Run full pytest, Ruff, web check/build and docs check/build. Record the exact
   results; the audit's 682 passing tests are a comparison point, not a waiver
   or a required final count. Additional tests must raise the count naturally.
   A fresh environment's unexpected failure must be diagnosed before attributing
   it to a repair.
7. Query the existing Graphify graph for scoped navigation, then corroborate
   source; the audit query was truncated and is not architectural proof.

## 5. Slice contracts

Each owned-path list permits focused tests in the named files. An additional
production path, dependency, schema, or cross-cutting helper requires Sol to
record why it is necessary and revise ownership before writing it.

### S01 — `DR-85c822af-001`: local requests bypass ambient proxies

**Files:** `codemble/llm/providers.py`, `tests/test_providers.py`.

**Before:** set `http_proxy` to a fictional loopback proxy and `no_proxy` empty
before importing the module. Point Ollama at a different unused loopback port.
The proxy receives the fictional prompt and its response is accepted. This
proves proxy routing, not an observed remote disclosure.

**Direction:** supply an explicit empty `urllib.request.ProxyHandler` to the
local opener alongside its redirect-refusal handler. URL validation alone
cannot constrain the actual transport. Leave cloud transports unchanged.

**Acceptance:** two independent loopback listeners prove real Ollama requests
arrive only at the configured local listener and the proxy receives zero.
Cover lower/uppercase proxy configuration, empty bypass variables, local status
and generation, absent Ollama, redirect refusal, non-loopback refusal and
supported IPv4/IPv6/localhost forms. Restore environment/module state after
tests; no request may leave loopback. Reuse existing cloud fake-transport tests.
Run `pytest tests/test_providers.py tests/test_narration_rescue.py`.

**Stop/rollback:** do not broaden accepted URLs or weaken redirects to fix a
test. A cloud behavior change or failed local confinement test rejects the slice.

### S02 — `DR-85c822af-002`: resolve lexical owners before imports

**Files:** `codemble/adapters/python_ast.py`, `tests/test_python_resolution.py`,
`tests/test_python_ast.py`, relevant oracle fixtures only when explicitly owned.

**Before:** `lib.py` defines `work`; `app.py` imports it and defines
`def main(work): return work()`. The parser falsely emits a certain call from
`app.main` to `lib.work`.

**Direction:** determine the call name's lexical binding owner before consulting
module imports. Parameters and local assignments revoke imported certainty in
that scope. Cover positional-only/keyword-only/variadic arguments, aliases,
nested scopes, rebinding before/after the call, and explicit global/nonlocal
semantics. Use the existing uncertainty representation for unresolved targets;
do not invent a certain callback edge or build speculative data-flow analysis.

**Acceptance:** the shadow fixture never contributes a certain imported edge,
a complete journey, or an answer based on that false target. Unshadowed imports
remain certain with correct lines. Unaffected deterministic graph fixtures stay
stable. Add sensitivity at the graph/consumer boundary, not assertions about
the name of an internal helper. Run Python resolution/AST/role tests,
`tests/test_learning_journey.py`, `tests/test_checks.py`, and
`tests/test_parser_evidence_oracle.py` (nine-language regression).

**Stop/rollback:** stop if correctness requires unsupported whole-program
analysis. Do not alter the four-method LanguageAdapter interface or suppress
legitimate known calls just to remove a failing edge.

### S03 — `DR-85c822af-003`: one source identity per Study response

**Files:** `codemble/llm/study.py`, `codemble/adapters/source_text.py` if a
byte-decoding helper is needed, `tests/test_study.py`, `tests/test_server.py`;
`web/src/StudyPanel.jsx` and the existing Study error path only if needed for
actionable recovery, with matching browser coverage in `check_userflow_repairs.mjs`.

**Before:** parse `main` returning 1; cache fake narration saying “Returns one.”
Replace its file with `def changed(): return 999`. Old node identity, new source
bytes and old narration are returned together.

**Direction:** read bytes once from the confined source path, hash those exact
bytes against `graph.file_hashes`, and decode those same bytes using the existing
language encoding rules. Do not hash one read then decode a second. Missing
hash, mismatch, unavailable file or unsafe decode refuses coherent Study and
narration before cache/provider use. Reuse `StudySourceError`/the existing 422
route where sufficient; show a clear “source changed; reopen/reparse this folder”
recovery instruction rather than an endless unchanged retry. Do not add a watcher.

**Acceptance:** cached/uncached and no-key paths; edit, truncate, replace/rename,
missing file, original-byte restoration, Python coding cookie/BOM and non-Python
UTF-8 rules; confinement and partial-file behavior. A mismatch exposes no mixed
source/relationships/narration and makes zero provider calls. Reparse restores
the new node/hash; reverted exact bytes work with their original identity.
Exercise both `/study` and `/explanation`, and browser refusal/reopen recovery.
Run Study/server/narration tests and existing source-encoding parser tests.

**Compatibility:** graphs manually built in tests may need valid hashes derived
from their fixtures; never add a production “missing hash means trust it” escape.
An edit after the single read does not invalidate the internally consistent
snapshot already read; the next request must detect the change.

**Stop/rollback:** no cache entry under an old hash may contain new bytes. Preserve
no-key Study and safe source confinement; reject the slice if either regresses.

### S04 — `DR-85c822af-004`: replace unsupported ordering with call membership

**Files:** `codemble/checks/service.py`, `tests/test_checks.py`, affected typed
check consumers/tests found by searching `first-call`, plus narrowly relevant
documentation. Coordinate any necessary consumer path before editing it.

**Before:** `main` returns `a_outer(z_inner())`. The generated correct answer to
“called first” is `a_outer`, although Python evaluates `z_inner()` first.

**Plan choice:** ask which offered structures the graph shows the subject calling
directly. Include **all** certain direct targets as correct answers and offer
at least one graph-supported non-answer; if no valid distractor exists, omit
the question. Existing multiple-selection scoring supports this. Do not merely
remove “first” while retaining a single answer among several true callees.
Use a semantically accurate check kind (for example `direct-call`) and deliberately
bump `_CHECK_SCHEMA_VERSION` from its current 6 when changing the contract.
Search all consumers and documentation for the old kind. No execution-order
claim is justified by line sorting, target spelling or textual AST traversal.

**Acceptance:** nested and same-line calls, semicolons, conditional calls,
earlier possible/external calls, duplicate calls, ordinary sequential calls,
no certain targets, all-options-correct rejection, exact multi-answer scoring,
deterministic IDs/citations, and stale old-ID rejection. Wrong submissions must
not disclose answers. Run checks, learning journey, server and parser oracle
tests; replay quiz → illumination → restart in the browser.

**Compatibility decision:** this slice corrects newly generated questions and
invalidates stale question IDs. Preserve the existing file-hash-based saved
understanding contract; do not silently erase users' illumination or claim that
old passes were re-evaluated. `_passed` is process-local, while saved understanding
does not store question IDs. A retrospective re-proof policy is a separate
product decision, not an implicit schema reset. Record this limitation in the
repair report and Decision Log. Never claim historical proof was repaired.

**Stop/rollback:** stop on an unhandled old-kind consumer or if an honest question
cannot be formed. Do not weaken distractor or graph-only-answer rules to keep
the old number of questions.

### S05 — `DR-85c822af-005`: serialize complete progress mutations

**Files:** `codemble/progress/store.py`, `tests/test_progress.py`,
`tests/test_explorer_trail.py`; one small local lock helper only if platform
separation warrants it. Do not import the disconnected sharing storage system.

**Before:** pause `mark_understood(a)` after reading; complete `mark_visited(b)`;
resume the first write. Both calls succeed but reloaded visits are empty.

**Direction:** own the complete read → modify → atomic replacement transaction,
not only `_write`. Cover every writer: understand, visit, clear, Home and mode,
including `learner.json`. Use both in-process ownership and a stable OS advisory
lock for supported multiple CLI processes; never unlink/recreate a held lock.
Use unique temporary files in the target directory. Define a consistent lock
order (a single data-root mutation lock is the simplest acceptable starting
point) and bounded acquisition/error handling; do not add a database.

**Acceptance:** deterministic barriers/events for understand+visit, understand+
mode, Home+visit, competing modes, clear+mutation and two distinct store/process
instances. Unrelated successfully completed updates survive reload. Clear has a
linearized order: mutations committed before it are cleared; mutations ordered
after it may create new progress. No delayed stale payload resurrects the prior
snapshot. Test independent projects, concurrent learner defaults, failed write,
replace/lock failure, temporary cleanup and process-exit lock release. Assert
final persisted behavior rather than timing-based sleeps.

**Compatibility:** preserve schema 1, signatures, visits and preferences. Mode
touches project and learner-default files: serialization does not make two
replacements crash-atomic. Explicitly test a failure between them and ensure an
error cannot make the UI claim an unpersisted state; report remaining crash
atomicity limits. Do not grow a journal/migration mechanism without a separate
design decision. Do not narrow the package's OS-independent claim silently;
exercise lock semantics on supported POSIX and Windows runtimes or mark the
missing platform gate blocked.

Run progress, explorer trail, checks, project-selection and server tests.
**Stop/rollback:** no destructive migration, busy spin, unbounded deadlock or
unlocked fallback on unsupported locking. A failed preservation or cross-writer
test rejects the slice.

### S06 — `DR-85c822af-006`: invalidated work cannot publish current caches

**Files:** `codemble/server/project_activation.py`,
`tests/test_project_activation.py`, targeted `tests/test_server.py` cases.

**Before:** pause `graph_json()` after old hydration, commit understanding and
invalidate views, then release serialization. Later reads reuse old data.

**Direction:** use one generation boundary for `_hydrated`, `graph_json` and
`map_json`. Capture generation with inputs; publish only if still current.
Retry/discard stale work explicitly. Guarding only serialization leaves stale
hydration able to poison the next generation. Keep unchanged cache reuse.

**Acceptance:** force invalidation during each of hydration, graph serialization
and Map build, then assert subsequent reads equal the committed progress/Home.
Cover competing invalidations, clear, Home changes, accepted check submissions,
project release/re-entry and local share preview's hydration consumer. An
already in-flight pre-mutation response may represent its coherent old snapshot;
it must not become the cache served to new post-mutation requests. No mixed
generation payload and no unbounded retry loop under continuous mutation.
Run project-activation/server/Map/share-preview tests and relevant benchmark
comparison for repeated reads; preserve hot-cache behavior and bounded latency.

**Stop/rollback:** global locks around slow parsing/provider work are outside
scope. Reject deadlocks, stale publication or material responsiveness regression.

### S07 — `DR-85c822af-007`: narration owns capacity until workers finish

**Files:** `codemble/server/app.py`, `tests/test_narration_rescue.py`, targeted
`tests/test_server.py`; an app-local narration helper if needed for a bounded
lifetime owner. Keep `StudyService` changes limited to S03's established contract.

**Before:** on one ASGI loop with a real StudyService and blocked fake provider,
use a short test deadline. Three batches of four requests time out while twelve
provider calls remain active against the intended four-slot limit.

**Direction:** separate HTTP waiting lifetime from provider-worker lifetime.
Acquire admission before launching work; retain it until the worker actually
exits, even if the request times out/disconnects. Keep a dedicated narration
budget independent of ordinary endpoints. Pending admission must expire without
later launching orphan work. A dedicated bounded executor or app-owned task
owner is acceptable only with bounded admission and explicit lifespan cleanup;
an unbounded executor queue or a semaphore inside already-unbounded threads is
not a fix. Do not block the event loop or simply remove the request deadline.

**Acceptance:** in one async loop, drive multiple deadline and cancellation
windows; peak active providers stays at four, every request returns within its
configured budget, pending cancelled work never starts, ordinary graph/Map/check
requests stay responsive. Release fake workers in `finally`; verify capacity
recovery, completion/cache reuse, provider exceptions, project release and app
shutdown without permit leaks or stale UI updates. Distinguish inability to kill
a blocking third-party thread from loss of admission control. Keep provider
transport timeouts finite. Test fresh app instances do not share leaked capacity.
Run narration/server/Study/provider suites; do not use live or paid providers.

**Stop/rollback:** any ordinary endpoint starvation, unbounded queue, lost slot,
late cancelled admission or deadlocked shutdown rejects the slice.

### S08 — `DR-85c822af-008`: guard obsolete clear before committing

**Files:** `web/src/learnerSession.js`,
`web/scripts/check_learner_session.mjs`.

**Before:** defer clear; reset/restart and hydrate a replacement trail containing
`b`; resolve old clear. The ready replacement session loses its visits.

**Direction:** check captured lifecycle before the first post-await commit,
using the existing guard. Do not invent another session abstraction.

**Acceptance:** old clear settling after replacement hydration or disposal
emits no commit, reload, focus or error into the new session. Same-session clear
still clears trail/understanding, invalidates graph and Map, and permits re-quiz.
Refused clear retains current state with its existing visible refusal.
Run `node scripts/check_learner_session.mjs` from `web/` and full web check.
**Stop/rollback:** any same-session clear or stale-response guard regression.

### S09 — `DR-85c822af-009`: retry shows exactly what it will submit

**Files:** `web/src/ModeControl.jsx`, narrowly necessary launch wiring in
`web/src/App.jsx`, session code only if demonstrated necessary;
`web/scripts/check_userflow_repairs.mjs`, relevant mode-gate contract checks.

**Before:** select First Flight + Expert; delay and fail mode PUT with 503.
Reopened radios show Explore + Easy, but retry opens First Flight + Expert.

**Direction:** one coherent selection owns radio state, action label and payload
through optimistic unmount/remount and refusal. Controlled inputs or durable
selection state are acceptable; merely changing `defaultChecked` is not proof.
Preserve immediate rapid-input handling and save-before-launch semantics.

**Acceptance:** all four voyage/register combinations, delayed refusal and
untouched retry, editing after refusal, rapid pointer and keyboard input, repeat
refusals, successful reload, focus retention and accessible checked state.
Visible choices, label, request body, stored mode and actual voyage agree at
every point. First Flight never starts before durable save. Exercise Chromium
and WebKit at 320 and 1440 CSS pixels; include actual narrow interaction, not
only a screenshot. Run mode-gate/focus/session contracts and `npm run check:userflows`.
**Stop/rollback:** refusal loses selection/focus or a save starts the wrong voyage.

### S10 — `DR-85c822af-010`: returning save refusal is visible and announced

**Files:** `web/src/learnerSession.js`, `web/src/App.jsx`,
`web/src/ModeControl.jsx`, `web/src/StudyPanel.jsx`; focused styles only if
needed for existing inline feedback. Own related session and browser tests.

**Before:** returning learner changes Expert to Easy; mode PUT fails with 503.
The control silently returns to Expert. Header path is runtime verified;
Study's equivalent caller was source-traced and must now be exercised too.

**Direction:** preserve rollback and expose a safe inline status/error with
announced retry guidance at both action surfaces. Central session error state
may be simpler than callers interpreting a Boolean: existing `false` also
means superseded/aborted/lifecycle-obsolete, which must not display a save error.
Keep stale identity guards before any error commit. No new modal or focus theft.

**Acceptance:** header and Study, first refusal/repeated refusal/successful retry,
reload consistency, unchanged-mode no-op, project switch/disposal, superseded
requests settling in either order, and mid-persistence backend failure from S05.
Success/new project clears obsolete error. Screen-visible and accessible status
agree; use role/live-region assertions plus real keyboard/focus behavior. Run
session/mode/focus contracts and maintained userflow checks in both engines.
**Stop/rollback:** stale error leaks across projects, aborts show false failure,
or optimistic UI disagrees with authoritative persisted state after recovery.

### S11 — `DR-85c822af-011`: absence of detected edges is not absence of behavior

**Files:** `web/src/StudyPanel.jsx`, focused browser coverage in
`web/scripts/check_userflow_repairs.mjs` and existing wording contract if any.

**Before:** `app.py` dynamically imports `leaf`; `leaf.py` imports `helper`.
Study for leaf says “Nothing else in your code would notice if you changed this”
because the parser has no resolved inbound edge. The known outbound edge makes
the one-sided impact widget visible.

**Direction:** bound both empty-column claims to evidence, for example “No callers
found in this parser map” and “No dependencies found in this parser map.” Use
plain product language without implying complete runtime knowledge. Preserve
Expert wording and current rows/citations; no parser expansion to justify prose.

**Acceptance:** dynamic inbound and outbound fixtures, both one-sided states,
empty/known certain/possible relationships, Easy/Expert switching, no-key Study,
320px reflow and 200% effective zoom. Correctness is visible bounded copy with
unchanged graph payload. Run impact/Study tests, full web check and real userflows.
**Stop/rollback:** do not lose certain/possible distinction, useful impact rows
or citations, or reintroduce a universal program-behavior claim.

## 6. G1 — combined acceptance and exact-candidate verification

All commands below assume G0's inspected, isolated environment, explicit
`CODEMBLE_PYTHON` binding and no-egress boundary. They are verification
instructions, not authorization for dependency
downloads or access to the developer's real progress.

### Required source gates

From the candidate root:

```sh
python -m pytest
ruff check .
```

From `web/`:

```sh
npm run check
npm run check:userflows
```

From `docs-site/`:

```sh
npm run check
npm run build
```

Run package construction using the repo's package-check workflow recipe in a
fresh task-owned output directory (`python -m pip wheel . --no-deps --wheel-dir
<owned-output>`). Pre-provision pinned build requirements; use offline/no-index
mode where available. Install the wheel into a separate clean environment with
prepared dependencies. Confirm `codemble --version`, import/package paths and
required package files match the candidate, then launch a fictional project and
exercise no-key Study, graph, checks and progress. Preserve the installed user
environment. No version bump/tag is part of this plan.

Web builds write `codemble/web_dist`; the integrator alone owns these generated
files. Retain final source-derived output, record hashes, rebuild into the same
candidate and assert identical hashes/no further delta. A diff from old HEAD is
expected for a UI repair; treating any such diff as failure would be incorrect.
Never copy the old audited bundle over changed source to make a check pass.

### Required runtime regression gate

- Run all eleven red/green reproductions against the combined candidate. Tests
  must fail for the audited before condition, not merely inspect implementation
  strings. Pin barriers, fake events and controllable responses for races.
- Complete first launch → chosen voyage → Map/Finder → Study → graph-supported
  quiz → illumination → restart → clear → re-quiz. Check Home and preferences
  survive appropriate boundaries and edited source is refused coherently.
- Run the maintained `check:space`, `check:escape` and `check:text` scripts against
  an owned loopback app via `CODEMBLE_URL`; follow their inspected launch/fixture
  contract. Capture console, failed requests and unexpected origins. Do not
  attach the scripts to a personal/live server.
- Run `check:userflows` in Chromium and WebKit, including the newly added failure
  branches, keyboard interaction, 320/375/414/768/1440 widths, reduced motion and
  effective 200% reflow where affected. Native Safari-specific claims require
  native Safari acceptance. Obscura-first remains the general manual browser
  workflow; its loopback refusal does not prove either target engine.
- Cache/progress changes reach the complete Map and local share preview. Run
  Map/projection/share-preview contracts and a disposable local-preview smoke;
  do not connect it to public delivery. Existing share backend suites run with
  pytest. Re-run the complete 5,000-module gate after S06 or any hot-path change;
  retain all modules, responsiveness and the existing resource constraints.
  `npm run check:large-project` is the maintained entry point; inspect its
  fixture and resource requirements before running it.
- Read `.github/workflows/ci.yml` and cover every applicable gate above. Its
  standalone `npm run check:share-delivery` uses disposable TLS fixtures and is
  a final regression check for shared server/packaging changes, not proof of
  M20 operational readiness. If required platform/browser checks cannot run
  safely, report Blocked/Hold; a smaller successful probe does not replace them.

### Documentation, graph, review and closure

1. Update `CLAUDE.md` Current State and append-only Decision Log with actual
   completed slices and compatibility choices. Add meaningful unreleased
   CHANGELOG entries and synchronize affected docs (source-change recovery,
   call-question wording, mode retry). Preserve verified v0.23 release claims;
   new candidate behavior must not be described as already shipped.
2. Refresh `graphify update .` after code changes in the isolated candidate and
   verify one scoped affected-flow query against current source. Review generated
   graph changes; do not overwrite unrelated notes or add watchers/hooks.
3. Inspect full diff, paths, test sensitivity, unexpected lock/generated files,
   credentials and private artifacts. Record the final candidate digest only
   after source, bundle, docs and graph settle.
4. Replay the real affected surface on that exact candidate. Collect independent
   peer closure for any corrections and bind all accepted receipts/checks to
   the exact tree. A subsequent material edit invalidates affected receipts.
5. Update private report/ledger: same stable IDs, before/after evidence,
   resolved/partial/blocked status, exact commands/results, remaining research,
   score/confidence/verdict. Do not mark all findings resolved because a package
   builds. Revalidate the offline report and its privacy/layout/keyboard checks.
6. Run a fresh council gate: exactly two rounds, four real independent reviewer
   roles per round (evidence, coverage, risk, outcome), sequential if needed,
   no recursive councils. Correct valid blockers and obtain targeted closure
   for material post-review changes. Persist approval for the exact report and
   candidate digest before delivering it.
7. Finish with the reviewed local candidate, changed files, verification,
   material limitations and next authorized action. No automatic commit, merge,
   push, release or deployment. Remove only owned disposable services/scratch
   that no longer support the ledger; preserve the report and evidence needed
   for continuation.

## 7. Global stop rules and completion record

Stop the affected slice for uncertain evidence, a required product/compatibility
decision beyond the defaults above, overlapping user work, unsafe fixtures,
missing containment, changed instructions, unexpected scope expansion, failed
required checks or two unsuccessful correction loops. Preserve the candidate
and receipts; do not rewrite a failing assertion, loosen truth/privacy rules,
delete state, or claim an untested platform passed. Roll back only the owned
unaccepted slice in the isolated candidate, never unrelated work.

Track actual execution here or in an explicitly linked continuation document;
the private ledger remains the authority for audit selection/review receipts:

- [x] G0 — authority, contained current-source environment, green baseline
- [x] S01 — proxy boundary
- [x] S02 — Python binding certainty
- [x] S03 — coherent Study bytes/hash
- [x] S04 — graph-supported call checks and compatibility note
- [x] S05 — progress transaction ownership
- [x] S06 — cache generation ownership
- [x] S07 — narration admission lifetime
- [x] S08 — obsolete clear refusal
- [x] S09 — launch retry consistency
- [x] S10 — returning save refusal feedback
- [x] S11 — evidence-bounded impact wording
- [ ] G1 — combined runtime/package/docs/graph gates, exact-tree reviews and council

Deferred research remains deferred: unaided learner acceptance, actual external
provider behavior, independent-node M20 timers/alerts/restore/deletion/key and
media-erasure proof, public connection, release and hosted publication. Do not
convert a local repair pass into claims about those gates.
