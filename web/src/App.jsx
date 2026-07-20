import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { GalaxyCanvas } from "./GalaxyCanvas.jsx";
import { CoachMarks, HintChip } from "./GuidanceLayer.jsx";
import { MapView } from "./MapView.jsx";
import { ModeControl } from "./ModeControl.jsx";
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

export function App() {
  const session = useMemo(
    () => createLearnerSession({ adapter: createHttpLearnerSessionAdapter() }),
    [],
  );
  const state = useSyncExternalStore(
    session.subscribe,
    session.getSnapshot,
    session.getSnapshot,
  );
  useEffect(() => {
    session.start();
    return () => session.dispose();
  }, [session]);
  // The path the learner last handed to SELECT_PROJECT. The session reports a
  // failed parse as `picker.error` and drops `parseProgress` -- which carried
  // the path -- in the same commit, so the only place the attempted path
  // survives the loading screen unmounting is here, in the component that
  // never unmounts. Cleared on browse so a folder error can never be labelled
  // with an unrelated earlier attempt.
  const [attempt, setAttempt] = useState("");
  const {
    chart,
    checkData,
    checkError,
    coachmarksSeen,
    entrypointError,
    entrypointOpen,
    error,
    explanation,
    explanationError,
    explanationLoading,
    focusedGraph,
    focusedStudiedCount,
    graph,
    hint,
    hoverNodeId,
    languageFocus,
    languageOptions,
    layer,
    level,
    litRegionId,
    llmStatus,
    mapData,
    mapError,
    mapTab,
    mode,
    modeChosen,
    parseProgress,
    pendingDawnRegionId,
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

  if (parseProgress) {
    return (
      <LoadingScreen
        progress={parseProgress}
        onCancel={() => session.dispatch({ type: "RESET_PROJECT" })}
      />
    );
  }

  if (status === "picking" && picker) {
    return (
      <PickerScreen
        picker={picker}
        // A select that came back with an error is the only failure a learner
        // can retry in place; a browse error clears `attempt`, so it keeps the
        // server's own plain wording instead of being dressed as a parse crash.
        failure={attempt && picker.error ? { path: attempt, detail: picker.error } : null}
        onBrowse={(path) => {
          setAttempt("");
          return session.dispatch({ type: "BROWSE_PICKER", path });
        }}
        onSelect={(path) => {
          setAttempt(path);
          return session.dispatch({ type: "SELECT_PROJECT", path });
        }}
      />
    );
  }

  if (!graph || !focusedGraph || !region) {
    return (
      <main className="load-state" aria-busy="true">
        <p>Mapping parser evidence…</p>
      </main>
    );
  }

  return (
    <main
      className="app-shell"
      data-level={showChart ? "chart" : level.toLowerCase()}
      data-mode={mode}
    >
      <header className="instrument-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <strong>Codemble</strong>
            <span>{projectName}</span>
          </div>
        </div>
        <nav className="location" aria-label="Breadcrumb" aria-live="polite">
          {showChart ? (
            <span aria-current="page">Star chart</span>
          ) : (
            <>
              <button
                type="button"
                disabled={level === LEVELS.GALAXY}
                aria-current={level === LEVELS.GALAXY ? "page" : undefined}
                onClick={() => session.dispatch({ type: "SET_LEVEL_GALAXY" })}
              >
                Galaxy
              </button>
              {level === LEVELS.GALAXY ? (
                <small>
                  {" · Home "}
                  {graph.selected_entrypoint
                    ? (defaultRegion(graph)?.id ?? "unresolved")
                    : "unselected"}
                </small>
              ) : (
                <>
                  <span aria-hidden="true">/</span>
                  <button
                    type="button"
                    disabled={level === LEVELS.SYSTEM}
                    aria-current={level === LEVELS.SYSTEM ? "page" : undefined}
                    onClick={() => session.dispatch({ type: "RETREAT" })}
                  >
                    {region.id}
                  </button>
                </>
              )}
              {level === LEVELS.STUDY && selectedNode ? (
                <>
                  <span aria-hidden="true">/</span>
                  <span aria-current="page">{selectedNode.name}</span>
                </>
              ) : null}
              {languageFocus !== "all" ? (
                <small>{" · "}{languageLabel(languageFocus)} focus</small>
              ) : null}
            </>
          )}
        </nav>
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
          <LayerSwitcher
            layer={layer}
            mode={mode}
            onChange={(next) => session.dispatch({ type: "SET_LAYER", layer: next })}
          />
          <LanguageFocus
            options={languageOptions}
            value={languageFocus}
            onChange={(language) =>
              session.dispatch({ type: "SET_LANGUAGE_FOCUS", language })
            }
          />
          <ModeControl
            mode={mode}
            modeChosen={modeChosen}
            onChoose={(nextMode) => session.dispatch({ type: "SET_MODE", mode: nextMode })}
          />
        </div>
      </header>

      {showChart ? (
        <StarChart
          chart={chart}
          studiedCount={focusedStudiedCount}
          projectName={projectName}
          onClearProgress={() => session.dispatch({ type: "CLEAR_PROGRESS" })}
        />
      ) : (
      <section className="map-stage" aria-label="Parser-proven project map">
        {layer === "map" ? (
          <MapView
            data={mapData}
            mapTab={mapTab}
            mode={mode}
            error={mapError}
            onSelectTab={(tab) => session.dispatch({ type: "SET_MAP_TAB", tab })}
            onSelectRegion={(regionId) =>
              session.dispatch({ type: "ADVANCE_REGION", regionId })
            }
            onSelectNode={(nodeId) =>
              session.dispatch({ type: "SELECT_STUDY_NODE", nodeId })
            }
            onRetry={() => session.dispatch({ type: "SET_LAYER", layer: "map" })}
          />
        ) : (
          <GalaxyCanvas
            graph={focusedGraph}
            level={level}
            region={region}
            selectedNode={selectedNode}
            hoverNodeId={hoverNodeId}
            pendingDawnRegionId={pendingDawnRegionId}
            mode={mode}
            onHoverNode={(nodeId) => session.dispatch({ type: "HOVER_NODE", nodeId })}
            onAdvance={(node) => session.dispatch({ type: "ADVANCE", node })}
            onRetreat={() => session.dispatch({ type: "RETREAT" })}
            onDawnConsumed={(regionId) => session.dispatch({ type: "CONSUME_DAWN", regionId })}
          />
        )}
        {/* The legend describes the layer that is actually on screen. Size and
            brightness are 3D-only encodings: mapview.py fixes _BOX_WIDTH and
            _BOX_HEIGHT as constants, draws workflow rows as fixed-radius
            circles, and never sends centrality at all -- so claiming them on
            the Map would describe an encoding the renderer does not draw,
            which is precisely the kind of wrong a learner cannot detect.
            Language tint is drawn on architecture boxes but not on workflow
            rows, so it follows the tab as well as the layer -- and in the
            galaxy it is a nebula, which makeMarker only adds for
            `node.kind === "region"`. Regions exist at GALAXY level only
            (NodeKind is module/class/function), so at system and study level
            the sky carries no tint at all and the rows must go. A learner in a
            mixed project reads "no fog here" as "no language evidence here". */}
        <aside
          className="map-legend"
          aria-label={layer === "map" ? "Map legend" : "Galaxy legend"}
        >
          {layer === "galaxy" ? (
            <>
              <span>
                <i className="legend-size" />
                Size · {mode === "easy" ? "how much code" : "lines of code"}
              </span>
              <span>
                <i className="legend-brightness" />
                Brighter · {mode === "easy" ? "used in more places" : "more distinct callers"}
              </span>
            </>
          ) : null}
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
            {/* Uncertainty renders as a distinct colour in the 3D galaxy (no
                dash support in 3d-force-graph) but as a dash in the 2D SVG
                map -- the swatch must match whichever layer is on screen. */}
            <i
              className={
                layer === "map"
                  ? "legend-route legend-route--possible legend-route--dashed"
                  : "legend-route legend-route--possible"
              }
            />
            {mode === "easy" ? "Possible connection" : "Possible relationship"}
          </span>
          {(layer === "galaxy" && level === LEVELS.GALAXY) ||
          (layer === "map" && mapTab === "architecture")
            ? languageOptions
                .filter((option) => option.id !== "all")
                .map((option) => (
                  <span key={option.id}>
                    <i className={`legend-tint legend-tint--${option.id}`} /> {option.label}
                  </span>
                ))
            : null}
        </aside>
        {layer === "galaxy" && level === LEVELS.GALAXY ? (
          <section className="orientation-copy">
            <h1>
              {focusedGraph.regions.length}{" "}
              {languageFocus === "all"
                ? focusedGraph.regions.length === 1
                  ? "system"
                  : "systems"
                : `${languageLabel(languageFocus)} ${focusedGraph.regions.length === 1 ? "system" : "systems"}`} from real source.
            </h1>
            <p>Choose a system. Size follows lines of code; brightness follows how many places call it.</p>
            {focusedGraph.partial_files.length ? (
              <p className="partial-summary">
                {focusedGraph.partial_files.length} {focusedGraph.partial_files.length === 1 ? "file is" : "files are"} unchartable because {focusedGraph.partial_files.length === 1 ? "its" : "their"} language parser reported a syntax error.
              </p>
            ) : null}
          </section>
        ) : null}
        {level === LEVELS.SYSTEM ? (
          <section className="orientation-copy orientation-copy--system">
            <h1>{region.id}</h1>
            <p>
              {focusedGraph.nodes.some((node) => node.region === region.id && node.partial)
                ? `${region.node_count} source ${region.node_count === 1 ? "file remains" : "files remain"} visible · ${region.loc} lines. The module is unchartable beyond raw source because it has a syntax error.`
                : `${region.node_count} parser-proven structures · ${region.loc} lines in this system.`}
            </p>
            <button
              className="check-launch"
              type="button"
              onClick={() => session.dispatch({ type: "OPEN_CHECKS" })}
            >
              {focusedGraph.nodes.some((node) => node.region === region.id && node.partial)
                ? "Check availability"
                : region.understood
                  ? "Review understanding"
                  : "Prove understanding"}
            </button>
          </section>
        ) : null}
        {level === LEVELS.SYSTEM && showChecks ? (
          <CheckPanel
            suite={checkData}
            error={checkError}
            mode={mode}
            onClose={() => session.dispatch({ type: "CLOSE_CHECKS" })}
            onSubmit={(checkId, selectedIds) =>
              session.dispatch({ type: "SUBMIT_CHECK", checkId, selectedIds })
            }
          />
        ) : null}
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
        {litRegionId ? (
          <output className="illumination-pulse" aria-live="polite">
            <span aria-hidden="true">✦</span>
            <strong>{litRegionId} understood</strong>
          </output>
        ) : null}
        {level === LEVELS.STUDY && selectedNode ? (
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
        ) : null}
        {!coachmarksSeen ? (
          <CoachMarks onDismiss={() => session.dispatch({ type: "DISMISS_COACHMARKS" })} />
        ) : null}
        <HintChip
          hint={hint}
          onStudy={(regionId) => session.dispatch({ type: "ADVANCE_REGION", regionId })}
        />
      </section>
      )}

      <footer className="status-line">
        <span>
          {showChart
            ? `${chart.length} concepts detected`
            : languageFocus === "all"
              ? `${graph.nodes.length} nodes · ${graph.edges.length} edges`
              : `${focusedGraph.nodes.length}/${graph.nodes.length} nodes · ${focusedGraph.edges.length} focused edges`}
        </span>
        <span>{showChart ? `${focusedStudiedCount} focused structures studied this session` : "Scroll or Enter to move closer · Escape to move back"}</span>
        <span>Local only</span>
      </footer>
    </main>
  );
}

// The five stages ParseJob reports, in the order it reports them. Copy matches
// runtime.py's _STAGE_COPY so the terminal and the browser say the same thing.
const STAGE_COPY = {
  discovering: "Finding your source files",
  parsing: "Reading each file",
  resolving: "Connecting imports and calls",
  checks: "Building graph-only checks",
  layout: "Placing your galaxy",
};
const STAGE_ORDER = ["discovering", "parsing", "resolving", "checks", "layout"];

function LoadingScreen({ progress, onCancel }) {
  const { stage, detail, files_done: done, files_total: total, pollError, path } = progress;
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");
  const headingRef = useRef(null);
  const reached = STAGE_ORDER.indexOf(stage);

  // A whole-screen replacement with no focus move leaves a keyboard user's
  // focus on a button that no longer exists and tells a screen reader nothing
  // about where it went. Same route-change pattern the picker → galaxy hop
  // relies on the galaxy canvas for.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  async function cancel() {
    setCancelling(true);
    setCancelError("");
    try {
      await onCancel();
    } catch (resetError) {
      setCancelError(resetError.message);
      setCancelling(false);
    }
  }

  return (
    <main className="loading-screen">
      <header className="loading-header">
        <p className="picker-wordmark">Codemble</p>
        <h1 ref={headingRef} tabIndex={-1}>
          Mapping <span className="loading-path">{path}</span>
        </h1>
        <p className="loading-subtitle">
          Parsing runs on your machine. Nothing is sent anywhere.
        </p>
      </header>
      <ol className="loading-stages" aria-label="Parse stages">
        {STAGE_ORDER.map((name, index) => {
          const state =
            index < reached ? "done" : index === reached ? "active" : "waiting";
          return (
            <li key={name} data-state={state}>
              <span>{STAGE_COPY[name]}</span>
              {/* The state as a word, not only as a colour: done and waiting sit
                  two steps apart on one ink ramp, and `data-state` reaches no
                  screen reader at all. */}
              <small>
                {name === "parsing" && total ? `${done}/${total} files · ` : ""}
                {state === "done"
                  ? "done"
                  : state === "active"
                    ? detail
                      ? `working · ${detail}`
                      : "working"
                    : "waiting"}
              </small>
            </li>
          );
        })}
      </ol>
      {/* No bar until the server has reported a denominator. An indeterminate
          meter animates, and motion the data cannot justify is exactly the
          reassurance this screen must not fake: a stalled parse has to look
          stalled. */}
      {total ? (
        <progress
          className="loading-meter"
          value={done}
          max={total}
          aria-label={`${done} of ${total} files read`}
        />
      ) : null}
      {/* Stage and its live sub-step, never the running count: files_done moves
          on every 300 ms poll, and announcing it would bury the events that
          matter under a counter no listener can follow. The resolving detail
          changes only a handful of times, at real pass boundaries, so it earns
          the live region -- it is what keeps this stage from reading as a hang.
          The count stays on screen and on the meter's accessible name. */}
      <p className="loading-live" role="status">
        {detail ?? STAGE_COPY[stage] ?? "Starting"}
      </p>
      {pollError ? (
        <p className="loading-error" role="status">
          Lost contact with the local server ({pollError}). Still retrying — the
          parse itself may be running fine.
        </p>
      ) : null}
      {cancelError ? (
        <p className="loading-error" role="alert">
          {cancelError}
        </p>
      ) : null}
      <div className="loading-actions">
        <button
          className="check-primary"
          type="button"
          disabled={cancelling}
          onClick={cancel}
        >
          {cancelling ? "Stopping…" : "Cancel and pick another project"}
        </button>
      </div>
    </main>
  );
}

function PickerScreen({ picker, failure, onBrowse, onSelect }) {
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
                    last visit
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {scale ? (
        <ScaleGuidance scale={scale} busy={busy} onBrowse={onBrowse} />
      ) : null}
      {failure ? (
        <ProjectFailure failure={failure} busy={busy} onSelect={onSelect} />
      ) : error ? (
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

function ScaleGuidance({ scale, busy, onBrowse }) {
  // scope_counts() files "." for sources sitting directly in the root. That is
  // the folder the learner already chose, not a smaller scope, so it can never
  // become a button that claims to narrow anything.
  const scopes = scale.suggestions.filter((suggestion) => suggestion.path !== ".");
  return (
    <section
      className="picker-scale"
      role="alert"
      aria-labelledby="picker-scale-heading"
    >
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
        // Deliberately unvalidated here. /api/picker/browse resolves the path
        // and answers 403 for anything outside the home jail; re-deciding that
        // in the browser would be a second, weaker copy of the only rule that
        // matters, and the one a learner could edit around.
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

function ProjectFailure({ failure, busy, onSelect }) {
  // ParseJob turns any worker exception into str(error), so `detail` can be raw
  // traceback text. It is shown, because a learner reporting this needs it and
  // hiding it would be its own kind of dishonest -- but it is labelled as the
  // machine's words and kept out of the sentence that explains what happened.
  return (
    <section className="picker-failure" role="alert">
      <h2>Codemble could not map that folder.</h2>
      <p>
        Nothing on disk changed, and no project's saved progress was touched. Try
        it again, or choose a different folder below.
      </p>
      <p className="picker-failure__detail">
        <span>What the parser reported</span>
        <code>{failure.detail}</code>
      </p>
      <button
        className="picker-select"
        type="button"
        disabled={busy}
        onClick={() => onSelect(failure.path)}
      >
        Try <span className="picker-recent-path">{failure.path}</span> again
      </button>
    </section>
  );
}

function LayerSwitcher({ layer, mode, onChange }) {
  return (
    <nav className="layer-switcher" aria-label="View layer">
      {[
        { id: "galaxy", label: "Galaxy" },
        { id: "map", label: mode === "easy" ? "Diagram" : "Map" },
      ].map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={layer === option.id}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </nav>
  );
}

function LanguageFocus({ options, value, onChange }) {
  if (options.length <= 2) return null;
  return (
    <nav className="language-focus" aria-label="Language focus">
      <span className="language-focus__label">Focus</span>
      <div>
        {options.map((option) => (
          <button
            type="button"
            key={option.id}
            aria-label={`Focus ${option.label}: ${option.count} ${option.count === 1 ? "system" : "systems"}`}
            aria-pressed={value === option.id}
            title={option.label}
            onClick={() => onChange(option.id)}
          >
            <span>{option.shortLabel}</span>
            <small>{option.count}</small>
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
  const triggerRef = useRef(null);
  const groupRef = useRef(null);
  const wasConfirmingRef = useRef(false);

  // The trigger button and the confirm group are mutually exclusive branches,
  // so the trigger unmounts (its ref goes null) before a cancel can focus it.
  // Defer the refocus to an effect, which runs after React remounts it.
  useEffect(() => {
    if (confirming) {
      groupRef.current?.focus();
    } else if (wasConfirmingRef.current) {
      triggerRef.current?.focus();
    }
    wasConfirmingRef.current = confirming;
  }, [confirming]);

  function cancel() {
    setConfirming(false);
    setFailure("");
  }

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
      <button
        className="rail-action"
        type="button"
        ref={triggerRef}
        onClick={() => setConfirming(true)}
      >
        Switch project
      </button>
    );
  }
  return (
    <div
      className="switch-project"
      role="group"
      aria-label="Switch project"
      tabIndex={-1}
      ref={groupRef}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !busy) cancel();
      }}
    >
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
        <button className="rail-action" type="button" disabled={busy} onClick={cancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

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

function CheckPanel({ suite, error, mode, onClose, onSubmit }) {
  const current = suite?.checks.find((check) => !check.passed) ?? null;
  const passed = suite?.checks.filter((check) => check.passed).length ?? 0;
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

  return (
    <aside className="check-panel" aria-label="Graph-derived understanding checks">
      <header className="check-panel__header">
        <div>
          <p>Active recall · graph only</p>
          <h1>{suite?.region_id ?? "Loading checks"}</h1>
        </div>
        <button className="check-close" type="button" onClick={onClose}>Close</button>
      </header>

      {error || submitError ? (
        <div className="check-state" role="alert">
          <h2>The checks did not load.</h2>
          <p>{error || submitError} The galaxy remains available.</p>
        </div>
      ) : null}
      {!suite && !error ? (
        <p className="check-loading" role="status">Deriving answers from parser edges…</p>
      ) : null}
      {suite?.region_understood ? (
        <div className="check-complete" aria-live="polite">
          <span className="check-complete__star" aria-hidden="true">✦</span>
          <h2>System lit.</h2>
          <p>This region's source hash matches the checks you passed. Edit its file and only this system will dim again.</p>
          <button className="check-primary" type="button" onClick={onClose}>Return to the system</button>
        </div>
      ) : null}
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
      {current && !suite.region_understood ? (
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
            <legend>{current.prompt_voices[mode]}</legend>
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
      ) : null}
    </aside>
  );
}

function StarChart({ chart, studiedCount, projectName, onClearProgress }) {
  const understood = chart.filter((item) => item.understood_nodes > 0).length;
  return (
    <section className="star-chart-screen" aria-labelledby="star-chart-heading">
      <header className="star-chart-intro">
        <p>Parser-detected concepts</p>
        <h1 id="star-chart-heading">Your language star chart.</h1>
        <p>
          Encountered comes from real syntax. Studied tracks this session. Understood lights only after graph-derived checks pass.
        </p>
        <dl>
          <div><dt>Concepts encountered</dt><dd>{chart.length}</dd></div>
          <div><dt>Studied this session</dt><dd>{studiedCount}</dd></div>
          <div><dt>Concepts understood</dt><dd>{understood}</dd></div>
        </dl>
      </header>
      <div className="concept-ledger" role="list" aria-label="Language concept progress">
        {chart.map((item) => (
          <article className="concept-row" role="listitem" key={`${item.language}:${item.concept}`}>
            <div>
              <h2>{conceptTitle(item.concept)}</h2>
              <span>{conceptTitle(item.language)} · {item.occurrences} parser {item.occurrences === 1 ? "occurrence" : "occurrences"}</span>
            </div>
            <div className="concept-meter" aria-label={`${item.understood_nodes} of ${item.nodes} structures understood`}>
              <span style={{ width: `${item.nodes ? (item.understood_nodes / item.nodes) * 100 : 0}%` }} />
            </div>
            <dl>
              <div><dt>Studied (session)</dt><dd>{item.studied_nodes}/{item.nodes}</dd></div>
              <div><dt>Understood</dt><dd>{item.understood_nodes}/{item.nodes}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <ClearProgress projectName={projectName} onConfirm={onClearProgress} />
    </section>
  );
}

function ClearProgress({ projectName, onConfirm }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const triggerRef = useRef(null);
  const groupRef = useRef(null);
  const wasConfirmingRef = useRef(false);

  // Same deferred refocus SwitchProject uses: the trigger and the confirm group
  // are mutually exclusive branches, so the trigger has already unmounted by the
  // time a cancel would try to focus it.
  useEffect(() => {
    if (confirming) {
      groupRef.current?.focus();
    } else if (wasConfirmingRef.current) {
      triggerRef.current?.focus();
    }
    wasConfirmingRef.current = confirming;
  }, [confirming]);

  function cancel() {
    setConfirming(false);
    setFailure("");
  }

  async function confirm() {
    setBusy(true);
    setFailure("");
    try {
      await onConfirm();
      setConfirming(false);
    } catch (clearError) {
      setFailure(clearError.message);
    } finally {
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <section className="progress-reset">
        <button
          className="check-primary"
          type="button"
          ref={triggerRef}
          onClick={() => setConfirming(true)}
        >
          Clear this project's progress
        </button>
        <p>Start {projectName} over with every system dim again.</p>
      </section>
    );
  }
  return (
    <section
      className="progress-reset progress-reset--confirming"
      role="group"
      aria-label="Clear this project's progress"
      tabIndex={-1}
      ref={groupRef}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !busy) cancel();
      }}
    >
      <p role="alert">
        This dims every system you lit in {projectName} and cannot be undone. Your
        other projects keep their progress, and no source file is touched.
      </p>
      {failure ? (
        <p className="progress-reset__error" role="alert">
          {failure}
        </p>
      ) : null}
      <div>
        {/* The destructive half must not look like its safe twin: identical
            buttons make "which one undoes my work" a guess, and this one
            cannot be undone. */}
        <button
          className="check-primary progress-reset__confirm"
          type="button"
          disabled={busy}
          onClick={confirm}
        >
          {busy ? "Clearing…" : `Yes, clear ${projectName}`}
        </button>
        <button className="check-primary" type="button" disabled={busy} onClick={cancel}>
          Keep it
        </button>
      </div>
    </section>
  );
}
