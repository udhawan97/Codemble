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
      .then(setStudyData)
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

  const projectName = useMemo(() => {
    if (!graph) return "Loading local project";
    return graph.project_root.split("/").filter(Boolean).at(-1) ?? graph.project_root;
  }, [graph]);

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
    <main className="app-shell" data-level={level.toLowerCase()}>
      <header className="instrument-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <strong>Codemble</strong>
            <span>{projectName}</span>
          </div>
        </div>
        <p className="location" aria-live="polite">
          {level === LEVELS.GALAXY ? "Galaxy" : region.id}
          {level === LEVELS.STUDY && selectedNode ? ` / ${selectedNode.name}` : ""}
        </p>
        {level !== LEVELS.GALAXY ? (
          <button className="rail-action" type="button" onClick={retreat}>
            {level === LEVELS.STUDY ? "Return to system" : "Return to galaxy"}
          </button>
        ) : (
          <span className="home-readout">Home: {defaultRegion(graph)?.id ?? "unresolved"}</span>
        )}
      </header>

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
          </section>
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

      <footer className="status-line">
        <span>{graph.nodes.length} nodes · {graph.edges.length} edges</span>
        <span>Scroll or Enter to move closer · Escape to move back</span>
        <span>Local only</span>
      </footer>
    </main>
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
          <Explanation explanation={explanation} node={node} onSelectNode={onSelectNode} />
        </div>
      ) : null}
    </aside>
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
