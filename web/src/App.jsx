import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { GalaxyCanvas } from "./GalaxyCanvas.jsx";
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
    entrypointDismissed,
    entrypointError,
    error,
    explanation,
    explanationError,
    focusedGraph,
    focusedStudiedCount,
    graph,
    languageFocus,
    languageOptions,
    level,
    litRegionId,
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
        <LanguageFocus
          options={languageOptions}
          value={languageFocus}
          onChange={(language) =>
            session.dispatch({ type: "SET_LANGUAGE_FOCUS", language })
          }
        />
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
        {!graph.selected_entrypoint && !entrypointDismissed && level === LEVELS.GALAXY ? (
          <EntrypointPicker
            candidates={graph.entrypoint_candidates}
            nodes={graph.nodes}
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
            explanation={explanation}
            explanationError={explanationError}
            mode={mode}
            onSelectNode={(nodeId) =>
              session.dispatch({ type: "SELECT_STUDY_NODE", nodeId })
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

function EntrypointPicker({ candidates, nodes, error, onSelect, onContinue }) {
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
          : "Explore the parsed map without Home, or restart with an explicit --entrypoint after adding a recognized startup structure."}
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
        Explore without Home
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

function StudyPanel({ node, study, error, explanation, explanationError, mode, onSelectNode }) {
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
          <StructuralSummary structural={study.structural} mode={mode} />
          <Explanation
            explanation={explanation}
            explanationError={explanationError}
            node={node}
            onSelectNode={onSelectNode}
          />
        </div>
      ) : null}
    </aside>
  );
}

function StructuralSummary({ structural, mode }) {
  // The Tier 0 floor: graph facts through fixed templates, no model involved.
  // It ships in the same /study response as the source and lens above, so it
  // is never subject to narration's own loading/error/no-key states below it.
  if (!structural) return null;
  return (
    <section className="structural-summary" aria-labelledby="structural-heading">
      <div className="study-section-heading">
        <h2 id="structural-heading">Structural summary</h2>
        <span>No model required</span>
      </div>
      <p>{structural[mode]}</p>
    </section>
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

function Explanation({ explanation, explanationError, node, onSelectNode }) {
  if (!explanation) {
    if (explanationError) {
      return (
        <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
          <h2 id="explanation-heading">Narration did not load.</h2>
          <p>{explanationError} The source and parser evidence above remain available.</p>
        </section>
      );
    }
    return <p className="study-loading">Fetching narration…</p>;
  }
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
