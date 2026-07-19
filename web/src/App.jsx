import { useCallback, useEffect, useMemo, useState } from "react";

import { GalaxyCanvas } from "./GalaxyCanvas.jsx";
import { LEVELS, defaultRegion } from "./graphData.js";

export function App() {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState("");
  const [level, setLevel] = useState(LEVELS.GALAXY);
  const [region, setRegion] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [studyData, setStudyData] = useState(null);
  const [studyError, setStudyError] = useState("");
  const [showChart, setShowChart] = useState(false);
  const [studiedNodeIds, setStudiedNodeIds] = useState(() => new Set());
  const [showChecks, setShowChecks] = useState(false);
  const [checkData, setCheckData] = useState(null);
  const [checkError, setCheckError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/graph", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Graph request returned ${response.status}.`);
        return response.json();
      })
      .then((payload) => {
        setGraph(payload);
        setRegion(defaultRegion(payload));
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    setShowChecks(false);
    setCheckData(null);
    setCheckError("");
  }, [level, region?.id]);

  useEffect(() => {
    if (level !== LEVELS.STUDY || !selectedNode) {
      setStudyData(null);
      setStudyError("");
      return undefined;
    }
    const controller = new AbortController();
    setStudyData(null);
    setStudyError("");
    fetch(`/api/node/${encodeURIComponent(selectedNode.id)}/study`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Study request returned ${response.status}.`);
        return response.json();
      })
      .then((payload) => {
        setStudyData(payload);
        setStudiedNodeIds((current) => new Set(current).add(payload.node.id));
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setStudyError(requestError.message);
      });
    return () => controller.abort();
  }, [level, selectedNode]);

  const advance = useCallback(
    (node) => {
      if (!graph) return;
      if (level === LEVELS.GALAXY) {
        setRegion(graph.regions.find((candidate) => candidate.id === node.id) ?? node);
        setSelectedNode(null);
        setLevel(LEVELS.SYSTEM);
      } else if (level === LEVELS.SYSTEM) {
        setSelectedNode(node);
        setLevel(LEVELS.STUDY);
      }
    },
    [graph, level],
  );

  const retreat = useCallback(() => {
    if (level === LEVELS.STUDY) {
      setSelectedNode(null);
      setLevel(LEVELS.SYSTEM);
    } else if (level === LEVELS.SYSTEM) {
      setLevel(LEVELS.GALAXY);
    }
  }, [level]);

  const selectStudyNode = useCallback(
    (nodeId) => {
      const nextNode = graph?.nodes.find((candidate) => candidate.id === nodeId);
      if (nextNode) setSelectedNode(nextNode);
    },
    [graph],
  );

  const loadChecks = useCallback(async (regionId) => {
    setCheckError("");
    const response = await fetch(`/api/regions/${encodeURIComponent(regionId)}/checks`);
    if (!response.ok) throw new Error(`Checks request returned ${response.status}.`);
    const payload = await response.json();
    setCheckData(payload);
    return payload;
  }, []);

  const openChecks = useCallback(async () => {
    if (!region) return;
    setShowChecks(true);
    setCheckData(null);
    try {
      await loadChecks(region.id);
    } catch (requestError) {
      setCheckError(requestError.message);
    }
  }, [loadChecks, region]);

  const submitCheck = useCallback(
    async (checkId, selectedIds) => {
      const response = await fetch(
        `/api/regions/${encodeURIComponent(region.id)}/checks/${encodeURIComponent(checkId)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected_ids: selectedIds }),
        },
      );
      if (!response.ok) throw new Error(`Check submission returned ${response.status}.`);
      const result = await response.json();
      if (result.correct) await loadChecks(region.id);
      if (result.region_understood) {
        const graphResponse = await fetch("/api/graph");
        if (!graphResponse.ok) throw new Error(`Graph refresh returned ${graphResponse.status}.`);
        const payload = await graphResponse.json();
        setGraph(payload);
        setRegion((current) =>
          payload.regions.find((candidate) => candidate.id === current.id) ?? defaultRegion(payload),
        );
      }
      return result;
    },
    [loadChecks, region],
  );

  const projectName = useMemo(() => {
    if (!graph) return "Loading local project";
    return graph.project_root.split("/").filter(Boolean).at(-1) ?? graph.project_root;
  }, [graph]);

  const chart = useMemo(
    () => (graph ? buildConceptChart(graph, studiedNodeIds) : []),
    [graph, studiedNodeIds],
  );

  if (error) {
    return (
      <main className="load-state" role="alert">
        <h1>The graph did not load.</h1>
        <p>{error} Restart Codemble and reload this page.</p>
      </main>
    );
  }

  if (!graph || !region) {
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
          {showChart ? "Star chart" : level === LEVELS.GALAXY ? `Galaxy · Home ${defaultRegion(graph)?.id ?? "unresolved"}` : region.id}
          {!showChart && level === LEVELS.STUDY && selectedNode ? ` / ${selectedNode.name}` : ""}
        </p>
        {showChart ? (
          <button className="rail-action" type="button" onClick={() => setShowChart(false)}>
            Return to galaxy
          </button>
        ) : level !== LEVELS.GALAXY ? (
          <button className="rail-action" type="button" onClick={retreat}>
            {level === LEVELS.STUDY ? "Return to system" : "Return to galaxy"}
          </button>
        ) : (
          <button className="rail-action" type="button" onClick={() => setShowChart(true)}>
            Star chart
          </button>
        )}
      </header>

      {showChart ? (
        <StarChart chart={chart} studiedNodeIds={studiedNodeIds} />
      ) : (
      <section className="map-stage" aria-label="Parser-proven project map">
        <GalaxyCanvas
          graph={graph}
          level={level}
          region={region}
          selectedNode={selectedNode}
          onAdvance={advance}
          onRetreat={retreat}
        />
        <aside className="map-legend" aria-label="Galaxy legend">
          <span><i className="legend-dot legend-dot--dim" /> Not studied</span>
          <span><i className="legend-dot legend-dot--lit" /> Understood</span>
          <span><i className="legend-route" /> Parser edge</span>
        </aside>
        {level === LEVELS.GALAXY ? (
          <section className="orientation-copy">
            <h1>{graph.regions.length} systems from real source.</h1>
            <p>Choose a system. Size follows lines of code; brightness follows call centrality.</p>
          </section>
        ) : null}
        {level === LEVELS.SYSTEM ? (
          <section className="orientation-copy orientation-copy--system">
            <h1>{region.id}</h1>
            <p>{region.node_count} parser-proven structures · {region.loc} lines in this system.</p>
            <button className="check-launch" type="button" onClick={openChecks}>
              {region.understood ? "Review understanding" : "Prove understanding"}
            </button>
          </section>
        ) : null}
        {level === LEVELS.SYSTEM && showChecks ? (
          <CheckPanel
            suite={checkData}
            error={checkError}
            onClose={() => setShowChecks(false)}
            onSubmit={submitCheck}
          />
        ) : null}
        {level === LEVELS.STUDY && selectedNode ? (
          <StudyPanel
            node={selectedNode}
            study={studyData}
            error={studyError}
            onSelectNode={selectStudyNode}
          />
        ) : null}
      </section>
      )}

      <footer className="status-line">
        <span>{showChart ? `${chart.length} concepts detected` : `${graph.nodes.length} nodes · ${graph.edges.length} edges`}</span>
        <span>{showChart ? `${studiedNodeIds.size} structures studied this session` : "Scroll or Enter to move closer · Escape to move back"}</span>
        <span>Local only</span>
      </footer>
    </main>
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

function StudyPanel({ node, study, error, onSelectNode }) {
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

function StarChart({ chart, studiedNodeIds }) {
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
          <div><dt>Structures studied</dt><dd>{studiedNodeIds.size}</dd></div>
          <div><dt>Concepts understood</dt><dd>{understood}</dd></div>
        </dl>
      </header>
      <div className="concept-ledger" role="list" aria-label="Language concept progress">
        {chart.map((item) => (
          <article className="concept-row" role="listitem" key={item.concept}>
            <div>
              <h2>{conceptTitle(item.concept)}</h2>
              <span>{item.occurrences} parser {item.occurrences === 1 ? "occurrence" : "occurrences"}</span>
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

function buildConceptChart(graph, studiedNodeIds) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const concepts = new Map();
  for (const annotation of graph.concept_annotations ?? []) {
    const current = concepts.get(annotation.concept) ?? {
      concept: annotation.concept,
      occurrences: 0,
      nodeIds: new Set(),
      studiedNodeIds: new Set(),
      understoodNodeIds: new Set(),
    };
    current.occurrences += 1;
    current.nodeIds.add(annotation.node_id);
    if (studiedNodeIds.has(annotation.node_id)) current.studiedNodeIds.add(annotation.node_id);
    if (nodeById.get(annotation.node_id)?.understood) current.understoodNodeIds.add(annotation.node_id);
    concepts.set(annotation.concept, current);
  }
  return [...concepts.values()]
    .map((item) => ({
      concept: item.concept,
      occurrences: item.occurrences,
      nodes: item.nodeIds.size,
      studied_nodes: item.studiedNodeIds.size,
      understood_nodes: item.understoodNodeIds.size,
    }))
    .sort((left, right) => left.concept.localeCompare(right.concept));
}

function conceptTitle(concept) {
  return concept
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
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
