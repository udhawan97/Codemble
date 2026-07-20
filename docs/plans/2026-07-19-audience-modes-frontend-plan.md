# Audience Modes — Frontend (Phases 4–6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the audience modes visible: a learner picks Easy or Expert, every text surface follows, narration finally reaches the panel, and the local-model setup guide lets a beginner switch it on without a terminal.

**Architecture:** `LearnerSession` owns mode as session state hydrated from `/api/mode`; React stays a pure renderer. Lens notes, check prompts, and Tier 0 summaries already ship in both voices, so switching mode re-renders locally with no request. Only narration refetches, because only narration is generated per mode.

**Tech Stack:** Vite + React 19, `3d-force-graph`, plain CSS with the Formal Edo tokens. No new dependencies.

**Source spec:** `docs/plans/2026-07-19-audience-modes-and-local-narration-design.md`
**Backend it builds on:** `docs/plans/2026-07-19-audience-modes-backend-plan.md` (phases 1–3, merged)

## Global Constraints

- **The Correctness Contract outranks everything.** Nothing rendered may state more than the parser proved. Approximate relationships stay visibly labelled *possible*; a partial parse stays disclosed.
- **Mode is presentation only.** It must never change graph bytes, layout coordinates, check answers, edge certainty, or region progress.
- **React is a pure renderer.** All transitions, fetching, and sequencing live in `web/src/learnerSession.js`. No layout or game logic in components — this is an architecture rule in `CLAUDE.md`, and it keeps the future share-link viewer cheap.
- **Determinism:** layout is seeded by content hash. Never introduce `Math.random()` or wall-clock time into anything rendered.
- **Local-first:** no telemetry, no CDN. The app self-hosts its fonts; it must never request Google Fonts, because it runs offline and says "Local only" in its own footer.
- **Canvas colours must be plain values, never `color-mix()`.** WebGL receives a custom property's authored text, so a computed token renders black. New canvas tokens go through `readPalette`, which resolves them.
- **Accents have one job each:** kohaku amber = understanding/progress, ruri lapis = interaction. Kohaku may never mark a navigation state. WCAG 4.5:1 floor on both grounds.
- **`codemble/web_dist` is a committed build artifact.** A change under `web/` reaches nobody until `cd web && npm run build` is re-run and the result committed.
- Gates: `python -m pytest`, `ruff check .`, and `cd web && npm run check` must all pass.

---

## File Structure

| Path | Responsibility | Phase |
| --- | --- | --- |
| `web/src/learnerSession.js` | **Modify.** Mode state, `SET_MODE`, narration fetch, first-run flag. All sequencing. | 4 |
| `web/src/App.jsx` | **Modify.** Render mode from session; wire the toggle. Already 689 lines — extract rather than grow. | 4, 5 |
| `web/src/ModeControl.jsx` | **Create.** First-run question + header toggle. | 4 |
| `web/src/SetupGuide.jsx` | **Create.** Local-model and cloud-key setup panel. | 6 |
| `web/src/NeighbourDiagram.jsx` | **Create.** Graph-derived inbound/outbound figure. | 5 |
| `web/src/icons.jsx` | **Create.** Authored meaning-carrying glyphs. | 5 |
| `web/src/styles.css` | **Modify.** Density rules per mode; icon and diagram styling. | 4, 5 |
| `web/scripts/check_learner_session.mjs` | **Modify.** Extend the existing node check with mode transitions. | 4 |
| `codemble/lens/*.py`, `codemble/checks/service.py` | **Modify.** Drop the legacy `note` / `prompt` strings once the SPA reads `_voices`. | 4 |
| `codemble/web_dist/` | **Rebuild and commit.** | 6 |
| `README.md`, `docs-site/`, `CHANGELOG.md`, `CLAUDE.md` | **Modify.** User-facing docs and the Decision Log. | 6 |

**Ordering rule:** the legacy-key removal (Task 14) must land *after* the SPA reads `_voices` (Task 13) and *before* `web_dist` is rebuilt (Task 19). Removing them earlier white-screens the shipped bundle.

---

# PHASE 4 — Mode reaches the learner

### Task 12: Session mode state

**Files:**
- Modify: `web/src/learnerSession.js`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Produces: snapshot gains `mode: "easy" | "expert"` and `modeChosen: boolean`. Adapter gains `loadMode(options)` and `saveMode(mode, options)`. Dispatch accepts `{type: "SET_MODE", mode}`.
- The in-memory adapter (`createInMemoryLearnerSessionAdapter`) gains the same two methods so the node check can drive them without HTTP.

- [ ] **Step 1: Write the failing check**

`web/scripts/check_learner_session.mjs` is a plain node script using `assert`. Add:

```js
{
  const session = createLearnerSession({
    adapter: createInMemoryLearnerSessionAdapter({
      graph: GRAPH,
      mode: "expert",
    }),
  });
  await session.start();
  assert.equal(session.getSnapshot().mode, "expert", "mode hydrates from the adapter");

  await session.dispatch({ type: "SET_MODE", mode: "easy" });
  assert.equal(session.getSnapshot().mode, "easy", "SET_MODE updates the snapshot");
  assert.equal(session.getSnapshot().modeChosen, true, "choosing a mode records the choice");
  session.dispose();
}
```

Reuse whatever the file already names its fixture graph constant; read the file first and match its existing style and assertion phrasing.

- [ ] **Step 2: Run the check to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL — `mode` is `undefined`

- [ ] **Step 3: Implement**

In `createLearnerSession`'s initial `deriveSnapshot({...})` call, add:

```js
    mode: "easy",
    modeChosen: false,
```

In `start()`, hydrate mode alongside the existing graph load, tolerating failure so a mode error never blocks the galaxy:

```js
    try {
      const stored = await adapter.loadMode({ signal: controller.signal });
      if (requestLifecycle === lifecycle && stored?.mode) {
        commit({ mode: stored.mode, modeChosen: stored.chosen === true });
      }
    } catch {
      // Mode is a preference; a failure here must never block the galaxy.
    }
```

Add to `dispatch`'s switch, beside the other cases:

```js
      case "SET_MODE":
        return setMode(event.mode);
```

Add the transition. Persisting is fire-and-forget because the snapshot is the source of truth for rendering and a failed write must not block the toggle:

```js
  async function setMode(mode) {
    if (mode !== "easy" && mode !== "expert") return;
    if (snapshot.mode === mode && snapshot.modeChosen) return;
    commit({ mode, modeChosen: true });
    try {
      await adapter.saveMode(mode, {});
    } catch {
      // The snapshot already reflects the choice; a failed write is not fatal.
    }
  }
```

Add to `createHttpLearnerSessionAdapter`'s returned object:

```js
    async loadMode(options = {}) {
      return request("/api/mode", "Mode request", options);
    },
    async saveMode(mode, options = {}) {
      return request("/api/mode", "Mode update", {
        ...options,
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
    },
```

Add to `createInMemoryLearnerSessionAdapter`, accepting `mode` and `modeChosen` in its options object:

```js
    async loadMode(options = {}) {
      throwIfAborted(options.signal);
      return { mode: currentMode, chosen: modeChosen };
    },
    async saveMode(nextMode, options = {}) {
      throwIfAborted(options.signal);
      currentMode = nextMode;
      modeChosen = true;
      return { mode: nextMode };
    },
```

declaring `let currentMode = mode ?? "easy";` and `let modeChosen = false;` alongside the existing `let currentGraph = graph;`.

- [ ] **Step 4: Run the check to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs && npm run check`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/learnerSession.js web/scripts/check_learner_session.mjs
git commit -m "feat(web): give the learner session an audience mode"
```

---

### Task 13: Narration actually reaches the panel

The shipped bundle calls `/study` but never `/api/node/{id}/explanation`, so narration is currently dark for every user. This task connects it, per mode.

**Files:**
- Modify: `web/src/learnerSession.js`, `web/src/App.jsx`
- Test: `web/scripts/check_learner_session.mjs`

**Interfaces:**
- Consumes: `mode` (Task 12).
- Produces: snapshot gains `explanation` and `explanationError`; adapter gains `loadExplanation(nodeId, mode, options)`. `SET_MODE` refetches narration when the study level is open.

- [ ] **Step 1: Write the failing check**

```js
{
  const session = createLearnerSession({
    adapter: createInMemoryLearnerSessionAdapter({
      graph: GRAPH,
      studies: { "app.main": STUDY },
      explanations: { "app.main:easy": { status: "ready", summary: { text: "E" } } },
    }),
  });
  await session.start();
  await session.dispatch({ type: "SELECT_STUDY_NODE", nodeId: "app.main" });
  assert.equal(
    session.getSnapshot().explanation.status,
    "ready",
    "opening a node fetches its narration",
  );
  session.dispose();
}
```

Match the fixture names the file already uses.

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && node scripts/check_learner_session.mjs`
Expected: FAIL — `explanation` is `undefined`

- [ ] **Step 3: Implement**

Add `explanation: null` and `explanationError: ""` to the initial snapshot, and `let explanationController = null;` beside the other controllers.

After `loadStudy` resolves successfully, start the narration fetch. It is deliberately a *separate* request with its own controller, so slow narration never delays the source and lens:

```js
  async function loadExplanation(nodeId) {
    abortController(explanationController);
    explanationController = new AbortController();
    const controller = explanationController;
    commit({ explanation: null, explanationError: "" });
    try {
      const explanation = await adapter.loadExplanation(nodeId, snapshot.mode, {
        signal: controller.signal,
      });
      if (
        !controller.signal.aborted &&
        snapshot.level === LEVELS.STUDY &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({ explanation });
      }
    } catch (requestError) {
      if (
        explanationController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError) &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({ explanationError: errorMessage(requestError) });
      }
    }
  }
```

Call `loadExplanation(nodeId)` at the end of `loadStudy`'s success path. Add `explanationController` to `cancelStudy` and to `dispose`'s controller list, so navigating away cancels narration.

In `setMode`, refetch narration when a node is open — lens, checks, and Tier 0 switch locally and must NOT refetch:

```js
    if (snapshot.level === LEVELS.STUDY && snapshot.selectedNode) {
      await loadExplanation(snapshot.selectedNode.id);
    }
```

Add to the HTTP adapter:

```js
    loadExplanation(nodeId, mode, options = {}) {
      return request(
        `/api/node/${encodeURIComponent(nodeId)}/explanation?mode=${encodeURIComponent(mode)}`,
        "Explanation request",
        options,
      );
    },
```

Add to the in-memory adapter, keyed `"<nodeId>:<mode>"`:

```js
    async loadExplanation(nodeId, mode, options = {}) {
      throwIfAborted(options.signal);
      return requiredFixture(explanations, `${nodeId}:${mode}`, "explanation");
    },
```

accepting `explanations = {}` in its options.

In `App.jsx`, change `StudyPanel`'s `Explanation` usage to read `explanation` and `explanationError` from session state rather than `study.explanation`. Render a short pending line while `explanation` is null, and the error text when `explanationError` is set — never a blank region.

- [ ] **Step 4: Run to verify it passes**

Run: `cd web && node scripts/check_learner_session.mjs && npm run check`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/learnerSession.js web/src/App.jsx web/scripts/check_learner_session.mjs
git commit -m "feat(web): fetch narration per audience mode"
```

---

### Task 14: Read the voices, drop the legacy strings

**Files:**
- Modify: `web/src/App.jsx`, `codemble/lens/python.py`, `codemble/lens/javascript_typescript.py`, `codemble/checks/service.py`
- Test: `tests/test_study.py`, `tests/test_checks.py`, `tests/test_server.py`

**Interfaces:**
- Produces: lens notes emit only `note_voices`; `Check.public()` emits only `prompt_voices`. The legacy `note` and `prompt` strings are gone.

**Order matters:** do the JSX first, verify, then remove the backend keys. Reversing it breaks the running app mid-task.

- [ ] **Step 1: Read the voices in the renderer**

In `App.jsx`, `LensNotes` renders `<p>{note.note}</p>`; change it to render `note.note_voices[mode]`. `CheckPanel` renders `<legend>{current.prompt}</legend>`; change it to `current.prompt_voices[mode]`. Both components need `mode` — thread it from `App`'s destructured state through props rather than reaching for a context.

- [ ] **Step 2: Verify the app still renders both voices**

Run: `cd web && npm run check`
Expected: PASS. Then run the app and confirm a lens note and a check question both change wording when the mode toggle flips.

- [ ] **Step 3: Remove the legacy keys**

In both lens modules, drop `"note": explanation["easy"],` leaving `"note_voices": explanation,`.

In `codemble/checks/service.py`, drop `"prompt": self.prompt["easy"],` from `Check.public()`, leaving `"prompt_voices"`.

- [ ] **Step 4: Update the Python tests**

The backend tests assert the legacy keys exist and equal the easy voice. Those assertions were explicitly temporary — their messages say "until phase 4". Replace each with an assertion that the legacy key is **absent** and `_voices` carries both voices. Search for `note_voices` and `prompt_voices` across `tests/` to find every site.

- [ ] **Step 5: Run every gate**

Run: `python -m pytest && ruff check . && cd web && npm run check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/App.jsx codemble/lens/ codemble/checks/service.py tests/
git commit -m "feat(web): render audience voices and retire the legacy strings"
```

---

### Task 15: The mode control

**Files:**
- Create: `web/src/ModeControl.jsx`
- Modify: `web/src/App.jsx`, `web/src/styles.css`

**Interfaces:**
- Consumes: `mode`, `modeChosen`, and `SET_MODE` (Task 12).
- Produces: `<ModeControl mode modeChosen onChoose />`.

- [ ] **Step 1: Build the component**

Two states in one component:

- **First run** (`modeChosen === false`): a small centred card asking one friendly question — "New to coding?" / "I build software" — with a one-line explanation of what changes. It must be dismissible by choosing; there is no third "skip" option, because a default chosen silently is what this screen exists to avoid.
- **Thereafter:** a compact two-option toggle in the header rail.

Accessibility requirements, all non-negotiable:
- The toggle is a `radiogroup` (or a `<fieldset>` of two radios), not two buttons — it selects between mutually exclusive states.
- The current mode is announced, not conveyed by colour alone.
- Full keyboard operation, visible focus ring.
- The first-run card takes focus when it appears and returns focus sensibly after choosing.

Styling: ruri lapis marks the interactive control. **Kohaku is forbidden here** — it means understanding and progress, and a navigation control is neither.

- [ ] **Step 2: Wire it in `App.jsx`**

Render the first-run card before the galaxy when `modeChosen` is false and a graph is loaded; render the header toggle in `instrument-rail` otherwise. Dispatch `{type: "SET_MODE", mode}` from both.

- [ ] **Step 3: Density rules**

In `styles.css`, key density off a `data-mode` attribute on the app shell. Easy mode: larger base type, shorter measure, more space between blocks, plainer labels. Expert mode: today's density. Both must hold the WCAG 4.5:1 floor and must remain usable at 320 px.

- [ ] **Step 4: Verify by running it**

Run: `cd web && npm run check`, then run the app. Confirm at 320 px and at desktop width: the first-run card appears once, choosing dismisses it, the header toggle switches every text surface with no visible refetch of lens or checks, and narration refetches.

- [ ] **Step 5: Commit**

```bash
git add web/src/ModeControl.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat(web): let the learner choose an audience"
```

---

# PHASE 5 — Graphics that carry meaning

### Task 16: Meaning-carrying icons

**Files:**
- Create: `web/src/icons.jsx`
- Modify: `web/src/App.jsx`, `web/src/styles.css`

Authored inline SVG only — no icon library, no font, no network request. Each icon must earn its place by carrying information a learner needs:

- one per language (Python, JavaScript, TypeScript)
- one per lens concept group
- one per check type
- a mode badge

**The anti-drift test applies to every glyph:** does it help a learner understand their code, or does it decorate? If decoration, do not ship it. Icons are always paired with their text label, never replacing it — an icon-only control fails both accessibility and comprehension. Mark every decorative SVG `aria-hidden="true"` and keep the adjacent text as the accessible name.

- [ ] **Step 1: Build `icons.jsx`** exporting one small component per glyph, each taking a `title` prop it does not render when used decoratively.
- [ ] **Step 2: Use them** in `LensNotes`, `CheckPanel`, `LanguageFocus`, and the mode badge.
- [ ] **Step 3: Verify** `cd web && npm run check`, then run the app and confirm every icon has a visible text label beside it and none conveys meaning by colour alone.
- [ ] **Step 4: Commit**

```bash
git add web/src/icons.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat(web): add meaning-carrying icons"
```

---

### Task 17: Graph-derived neighbour diagram

**Files:**
- Create: `web/src/NeighbourDiagram.jsx`
- Modify: `web/src/App.jsx`, `web/src/styles.css`

A small inline SVG in the study panel: the selected structure in the centre, inbound neighbours on one side, outbound on the other, drawn from the same parser evidence the galaxy uses.

**Correctness rules, non-negotiable:**
- Draw only from `study.neighbors`. Never infer an edge.
- A `certain: false` relationship must be visually distinct **and** labelled "possible" in text. Uncertainty may never be conveyed by line style alone.
- Deterministic layout — same neighbours, same picture. No randomness, no time.
- Zero neighbours renders an explicit "nothing else in your code connects to this yet", not an empty box.
- Cap the drawn neighbours and state the overflow in text ("+3 more") rather than silently truncating.

- [ ] **Step 1: Build the component** taking `neighbors` and `mode`; easy mode labels the sides "used by" / "uses", expert labels them "inbound" / "outbound".
- [ ] **Step 2: Render it** in `StudyPanel` above the lens notes.
- [ ] **Step 3: Verify** by running the app on this repository: pick a node with both inbound and outbound edges and one with a possible edge; confirm the counts match the Tier 0 summary exactly and the possible edge is labelled in text.
- [ ] **Step 4: Commit**

```bash
git add web/src/NeighbourDiagram.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat(web): draw the parser-proven neighbour diagram"
```

---

# PHASE 6 — Setup guide, bundle, and docs

### Task 18: In-app setup guide

**Files:**
- Create: `web/src/SetupGuide.jsx`
- Modify: `web/src/App.jsx`, `web/src/learnerSession.js`, `web/src/styles.css`

Reached from the no-key explanation state and from the header. It renders `/api/llm/status`, which reports `configured_provider`, `configured_model`, and `ollama: {running, installed_models, recommended, fallback}`.

Two parallel paths, neither second-class:

**Local model** — three steps, each with live state:
1. Install Ollama — link to `https://ollama.com/download`.
2. Download the model — show the recommended tag from the API response with a copy button for `ollama pull <tag>`, its size, and the RAM note. Never hardcode the tag in JSX; render what the API returns, so the recommendation stays in one place.
3. Confirmed — poll `/api/llm/status` and mark the step done when the model appears, with no restart.

**Cloud key** — the parallel three steps: where to get a key, where to put it, confirmation.

**Two honesty requirements:**
- Local narration must carry a visible label that it may be less accurate than a cloud model. That label is a guardrail recorded in the Decision Log, not decoration — a beginner cannot evaluate a small model's errors.
- The Tier 0 structural summary stays visible above any narration, in every configuration.

Polling must stop when the panel closes, follow the existing `AbortController` pattern, and back off rather than hammering — this endpoint answers in ~2s when nothing is installed.

- [ ] **Step 1: Add `loadLlmStatus` to both adapters** and a session action to fetch it, following the established shape.
- [ ] **Step 2: Build the component.**
- [ ] **Step 3: Verify all three states by running it** — no provider configured, a cloud key configured, and Ollama running. If Ollama is not installed locally, verify the not-installed path and say so in the report rather than claiming the installed path was tested.
- [ ] **Step 4: Commit**

```bash
git add web/src/SetupGuide.jsx web/src/App.jsx web/src/learnerSession.js web/src/styles.css
git commit -m "feat(web): guide the learner through model setup"
```

---

### Task 19: Rebuild the bundle and tell the truth in the docs

**Files:**
- Modify: `codemble/web_dist/` (rebuilt), `README.md`, `docs-site/`, `CHANGELOG.md`, `CLAUDE.md`

- [ ] **Step 1: Rebuild the bundle**

```bash
cd web && npm run build
```

`codemble/web_dist` is committed, so this output must be committed too or none of phases 4–6 reaches a user.

- [ ] **Step 2: Verify the built app end to end**

Run `codemble ./` against this repository from the rebuilt bundle and walk the whole loop: pick Home, open a system, open a structure, read the Tier 0 summary in both modes, read a lens note in both modes, answer a check, light a region, restart, confirm it stays lit and the mode persisted. Confirm the app makes **no external network request** — check the browser network panel for any font or CDN call.

- [ ] **Step 3: Docs**

- `README.md`: document the two modes and local-model support, including the `CODEMBLE_PROVIDER=ollama` configuration and the recommended model.
- `docs-site/`: update the relevant pages. **Every new page needs a hand-authored sidebar entry in `astro.config.mjs`** or it is invisible.
- `CHANGELOG.md`: one entry per meaningful change, Keep a Changelog format.
- `CLAUDE.md`: append Decision Log rows for the audience-mode architecture and the endpoint split. Update **Current State** with the date and a one-line session note, and tick the milestone boxes this work completes.

- [ ] **Step 4: Run every gate**

```bash
python -m pytest && ruff check . && cd web && npm run check && cd ../docs-site && npm run check
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: ship audience modes to the learner"
```

---

## Verification before calling phases 4–6 done

- [ ] `python -m pytest`, `ruff check .`, `cd web && npm run check`, `cd docs-site && npm run check` — all green
- [ ] Mode persists across a restart
- [ ] Toggling mode changes lens, checks, and Tier 0 with no network request; narration refetches
- [ ] Toggling mode never re-dims a region
- [ ] Every icon has a visible text label; no meaning is carried by colour alone
- [ ] The neighbour diagram's counts match the Tier 0 summary exactly
- [ ] Possible relationships are labelled "possible" in text everywhere they appear
- [ ] The app makes no external network request
- [ ] Usable at 320 px in both modes
- [ ] `codemble/web_dist` is rebuilt and committed
