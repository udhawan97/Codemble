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
