import { useCallback, useEffect, useMemo, useState } from "react";

import { GalaxyCanvas } from "./GalaxyCanvas.jsx";
import { LEVELS, defaultRegion } from "./graphData.js";

export function App() {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState("");
  const [level, setLevel] = useState(LEVELS.GALAXY);
  const [region, setRegion] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

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
          <aside className="study-preview" aria-label="Selected source structure">
            <p className="study-preview__path">{selectedNode.file}:{selectedNode.lineno}</p>
            <h1>{selectedNode.name}</h1>
            <dl>
              <div><dt>Kind</dt><dd>{selectedNode.kind}</dd></div>
              <div><dt>Span</dt><dd>{selectedNode.loc} lines</dd></div>
              <div><dt>Calls in</dt><dd>{selectedNode.centrality}</dd></div>
              <div><dt>Resolution</dt><dd>{selectedNode.partial ? "Partial parse" : "Parser-proven"}</dd></div>
            </dl>
            <p>Source and grounded explanations arrive in the next study wave.</p>
          </aside>
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
