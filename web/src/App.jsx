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
  const {
    chart,
    checkData,
    checkError,
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

  if (error) {
    return (
      <main className="load-state" role="alert">
        <h1>The graph did not load.</h1>
        <p>{error} Restart Codemble and reload this page.</p>
      </main>
    );
  }

  if (status === "picking" && picker) {
    return (
      <PickerScreen
        picker={picker}
        onBrowse={(path) => session.dispatch({ type: "BROWSE_PICKER", path })}
        onSelect={(path) => session.dispatch({ type: "SELECT_PROJECT", path })}
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
    <main className="app-shell" data-level={showChart ? "chart" : level.toLowerCase()}>
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

      {showChart ? (
        <StarChart chart={chart} studiedCount={focusedStudiedCount} />
      ) : (
      <section className="map-stage" aria-label="Parser-proven project map">
        <GalaxyCanvas
          graph={focusedGraph}
          level={level}
          region={region}
          selectedNode={selectedNode}
          onAdvance={(node) => session.dispatch({ type: "ADVANCE", node })}
          onRetreat={() => session.dispatch({ type: "RETREAT" })}
        />
        <aside className="map-legend" aria-label="Galaxy legend">
          <span><i className="legend-dot legend-dot--dim" /> Not studied</span>
          <span><i className="legend-dot legend-dot--lit" /> Understood</span>
          <span><i className="legend-dot legend-dot--partial" /> Unchartable</span>
          <span><i className="legend-route" /> Parser edge</span>
        </aside>
        {level === LEVELS.GALAXY ? (
          <section className="orientation-copy">
            <h1>
              {focusedGraph.regions.length}{" "}
              {languageFocus === "all"
                ? focusedGraph.regions.length === 1
                  ? "system"
                  : "systems"
                : `${languageLabel(languageFocus)} ${focusedGraph.regions.length === 1 ? "system" : "systems"}`} from real source.
            </h1>
            <p>Choose a system. Size follows lines of code; brightness follows call centrality.</p>
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
                    last visit
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

function CheckPanel({ suite, error, onClose, onSubmit }) {
  const current = suite?.checks.find((check) => !check.passed) ?? null;
  const passed = suite?.checks.filter((check) => check.passed).length ?? 0;
  const [selected, setSelected] = useState(() => new Set());
  const [feedback, setFeedback] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    setSelected(new Set());
    setFeedback(null);
    setSubmitError("");
  }, [current?.id]);

  function choose(optionId, multiple) {
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
      setFeedback(result);
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
      {!suite && !error ? <p className="check-loading">Deriving answers from parser edges…</p> : null}
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
          <p>This region has no certain graph relationship Codemble can test without guessing.</p>
        </div>
      ) : null}
      {current && !suite.region_understood ? (
        <form className="active-check" onSubmit={submit}>
          <div className="check-progress">
            <span>Check {passed + 1} of {suite.checks.length}</span>
            <progress value={passed} max={suite.checks.length} />
          </div>
          <fieldset>
            <legend>{current.prompt}</legend>
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

function StarChart({ chart, studiedCount }) {
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
          <div><dt>Structures studied</dt><dd>{studiedCount}</dd></div>
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
              <div><dt>Studied</dt><dd>{item.studied_nodes}/{item.nodes}</dd></div>
              <div><dt>Understood</dt><dd>{item.understood_nodes}/{item.nodes}</dd></div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
