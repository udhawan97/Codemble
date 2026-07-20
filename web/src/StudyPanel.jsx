import { conceptTitle } from "./graphData.js";

export function StudyPanel({
  node,
  study,
  error,
  mode,
  explanation,
  explanationLoading,
  explanationError,
  llmStatus,
  onSelectNode,
  onRetryNarration,
}) {
  return (
    <aside className="study-preview" aria-label="Selected source structure" aria-busy={!study && !error}>
      <header className="study-preview__header">
        <p className="study-preview__path">{node.file}:{node.lineno}</p>
        <h1>{node.name}</h1>
        <dl>
          <div><dt>Kind</dt><dd>{node.kind}</dd></div>
          <div><dt>Span</dt><dd>{node.loc} lines</dd></div>
          <div>
            {/* "Callers", not "Calls in": centrality counts the distinct
                structures that call this one, not the call sites they contain. */}
            <dt>{mode === "easy" ? "Used by" : "Callers"}</dt>
            <dd>{node.centrality}</dd>
          </div>
          <div><dt>Resolution</dt><dd>{node.partial ? "Partial parse" : "Parser-proven"}</dd></div>
        </dl>
      </header>

      {error ? (
        <section className="study-notice" role="alert">
          <h2>Study data did not load.</h2>
          <p>{error} The parser map is still available.</p>
          <button className="check-primary" type="button" onClick={() => onSelectNode(node.id)}>
            Try again
          </button>
        </section>
      ) : null}
      {!study && !error ? (
        <p className="study-loading" role="status">Reading parser evidence…</p>
      ) : null}
      {study ? (
        <div className="study-content">
          <StructuralSummary structural={study.structural} mode={mode} />
          <Explanation
            explanation={explanation}
            loading={explanationLoading}
            error={explanationError}
            llmStatus={llmStatus}
            mode={mode}
            node={node}
            onSelectNode={onSelectNode}
            onRetry={onRetryNarration}
          />
          <Connections
            neighbors={study.neighbors}
            node={node}
            mode={mode}
            onSelectNode={onSelectNode}
          />
          <SourceExcerpt source={study.source} />
          <LensNotes lens={study.lens} language={node.language} mode={mode} />
        </div>
      ) : null}
    </aside>
  );
}

function StructuralSummary({ structural, mode }) {
  if (!structural) return null;
  return (
    <section className="structural-summary" aria-labelledby="structural-heading">
      <div className="study-section-heading">
        <h2 id="structural-heading">
          {mode === "easy" ? "What this is" : "Structural summary"}
        </h2>
        <span>No model needed</span>
      </div>
      <p>{structural[mode] ?? structural.easy}</p>
    </section>
  );
}

const STRIP_LIMIT = 8;

function Connections({ neighbors, node, mode, onSelectNode }) {
  const items = neighbors ?? [];
  const inbound = items.filter((item) => item.direction === "inbound");
  const outbound = items.filter((item) => item.direction === "outbound");
  return (
    <section className="connections" aria-labelledby="connections-heading">
      <div className="study-section-heading">
        <h2 id="connections-heading">
          {mode === "easy" ? "What this connects to" : "Parser connections"}
        </h2>
        <span>
          {items.length} parser {items.length === 1 ? "relationship" : "relationships"}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="study-loading">
          {mode === "easy"
            ? "Nothing in your code reaches this yet, and it does not reach anything else."
            : "The parser observed no relationship into or out of this structure."}
        </p>
      ) : (
        <>
          <MiniConstellation inbound={inbound} outbound={outbound} node={node} />
          <ConnectionGroup
            title={mode === "easy" ? "Uses this" : "Inbound"}
            items={inbound}
            mode={mode}
            onSelectNode={onSelectNode}
          />
          <ConnectionGroup
            title={mode === "easy" ? "This uses" : "Outbound"}
            items={outbound}
            mode={mode}
            onSelectNode={onSelectNode}
          />
        </>
      )}
    </section>
  );
}

function ConnectionGroup({ title, items, mode, onSelectNode }) {
  if (!items.length) return null;
  return (
    <>
      <h3>{title}</h3>
      <ul className="connection-list">
        {items.map((item) => (
          <li key={`${item.direction}-${item.node_id}`}>
            <button type="button" onClick={() => onSelectNode(item.node_id)}>
              <span className="connection-name">{item.name}</span>
              <span className="connection-meta">
                {relationWords(item, mode)} · {certaintyWords(item, mode)}
              </span>
              <span className="source-citation">{item.citation}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function relationWords(item, mode) {
  if (item.relationship === "import") {
    if (item.direction === "inbound") return mode === "easy" ? "brings this in" : "import · inbound";
    return mode === "easy" ? "this brings it in" : "import · outbound";
  }
  if (item.direction === "inbound") return mode === "easy" ? "calls this" : "call · inbound";
  return mode === "easy" ? "this calls it" : "call · outbound";
}

function certaintyWords(item, mode) {
  if (item.certain) return mode === "easy" ? "certain" : "certain";
  if (item.relationship === "import") {
    return mode === "easy" ? "possible link, not certain" : "possible import";
  }
  return mode === "easy" ? "possible link, not certain" : "possible call";
}

function MiniConstellation({ inbound, outbound, node }) {
  // Seat coordinates ARE computed here, unlike the galaxy and the 2D map, whose
  // every coordinate is backend-owned. This is presentation of an already-
  // fetched list — evenly spacing N items down a strip, the way the star chart
  // sizes its bars from counts — and it asserts nothing about the project:
  // order comes from the payload, and no position here means anything.
  const left = inbound.slice(0, STRIP_LIMIT);
  const right = outbound.slice(0, STRIP_LIMIT);
  const height = Math.max(left.length, right.length, 1) * 22 + 16;
  const middle = height / 2;
  const seat = (index, count) => ((index + 1) * height) / (count + 1);
  return (
    <svg
      className="mini-constellation"
      viewBox={`0 0 280 ${height}`}
      role="img"
      aria-label={`${inbound.length} inbound and ${outbound.length} outbound parser relationships for ${node.name}`}
    >
      {left.map((item, index) => (
        <line
          key={`in-line-${item.node_id}`}
          x1="26"
          y1={seat(index, left.length)}
          x2="132"
          y2={middle}
          strokeDasharray={item.certain ? undefined : "3 3"}
        />
      ))}
      {right.map((item, index) => (
        <line
          key={`out-line-${item.node_id}`}
          x1="148"
          y1={middle}
          x2="254"
          y2={seat(index, right.length)}
          strokeDasharray={item.certain ? undefined : "3 3"}
        />
      ))}
      {left.map((item, index) => (
        <circle key={`in-dot-${item.node_id}`} cx="22" cy={seat(index, left.length)} r="4" />
      ))}
      {right.map((item, index) => (
        <circle key={`out-dot-${item.node_id}`} cx="258" cy={seat(index, right.length)} r="4" />
      ))}
      <circle className="mini-constellation__self" cx="140" cy={middle} r="6" />
    </svg>
  );
}

function LensNotes({ lens, language, mode }) {
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
              <p>{note.note_voices[mode]}</p>
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

function Explanation({
  explanation,
  loading,
  error,
  llmStatus,
  mode,
  node,
  onSelectNode,
  onRetry,
}) {
  if (loading) {
    return (
      <p className="study-loading" role="status">
        {mode === "easy"
          ? "Asking your model to explain this in plain language…"
          : "Requesting a grounded narration for this structure…"}
      </p>
    );
  }
  if (error) {
    return (
      <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">The explanation request failed.</h2>
        <p>{error}</p>
        <p>Every fact above and below this block came from the parser and is unaffected.</p>
        <button className="check-primary" type="button" onClick={onRetry}>
          Try again
        </button>
      </section>
    );
  }
  if (!explanation) return null;
  if (explanation.status === "no_key") {
    return <ProviderGuidance message={explanation.message} llmStatus={llmStatus} mode={mode} />;
  }
  if (explanation.status === "error") {
    return (
      <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">The explanation was withheld.</h2>
        <p>{explanation.message}</p>
        <p>Codemble will not display provider output that falls outside parser evidence.</p>
        <button className="check-primary" type="button" onClick={onRetry}>
          Try again
        </button>
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
      <div className="study-section-heading" role="status">
        <h2 id="explanation-heading">
          {mode === "easy" ? "In plain language" : "Grounded explanation"}
        </h2>
        <span>{explanation.cached ? "Local cache" : explanation.provider}</span>
      </div>
      <p>
        {explanation.summary.text}{" "}
        <Citation citation={explanation.summary.citation} fallbackLine={node.lineno} />
      </p>
      <h3>{mode === "easy" ? "Line by line" : "Walkthrough"}</h3>
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
          <h3>{mode === "easy" ? "How it fits in" : "Parser relationships"}</h3>
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

function ProviderGuidance({ message, llmStatus, mode }) {
  const ollama = llmStatus?.ollama ?? null;
  return (
    <section className="study-notice" aria-labelledby="explanation-heading">
      <h2 id="explanation-heading">
        {mode === "easy"
          ? "The plain-language write-up needs a model."
          : "No narration provider is configured."}
      </h2>
      <p>{message}</p>
      {ollama ? (
        <p>
          {ollama.running
            ? `Ollama is already running on this machine. Set CODEMBLE_PROVIDER=ollama and CODEMBLE_OLLAMA_MODEL=${ollama.recommended}, then restart Codemble to narrate without sending code anywhere.`
            : `Want to stay fully local? Install Ollama, run "ollama pull ${ollama.recommended}" (or ${ollama.fallback} on a smaller machine), set CODEMBLE_PROVIDER=ollama, then restart Codemble.`}
        </p>
      ) : null}
      <p>
        Everything else on this panel is parser evidence and works without any
        model at all.
      </p>
    </section>
  );
}

function Citation({ citation, fallbackLine }) {
  const parsedLine = Number(citation.split(":").at(-1)) || fallbackLine;
  return <a className="source-citation" href={`#source-L${parsedLine}`}>{citation}</a>;
}
