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
          {/* Easy reads its own register end to end: "Kind/Span/Resolution"
              are parser vocabulary the coach-marks never taught. The facts
              are identical; only the labels change. */}
          <div><dt>{mode === "easy" ? "What it is" : "Kind"}</dt><dd>{node.kind}</dd></div>
          <div><dt>{mode === "easy" ? "Length" : "Span"}</dt><dd>{node.loc} {node.loc === 1 ? "line" : "lines"}</dd></div>
          <div>
            {/* "Callers", not "Calls in": centrality counts the distinct
                structures that call this one, not the call sites they contain.
                The easy label says "Called by" and not "Used by" because the
                summary right below counts *imports* when it says five other
                parts use this file -- one panel showing "Used by 0" above
                "five other parts use it" is a contradiction a learner cannot
                resolve, and "use"/"brings this in" is import vocabulary. */}
            <dt>{mode === "easy" ? "Called by" : "Callers"}</dt>
            <dd>{node.centrality}</dd>
          </div>
          <div>
            <dt>{mode === "easy" ? "Evidence" : "Resolution"}</dt>
            <dd>
              {node.partial
                ? mode === "easy" ? "Could not be fully read" : "Partial parse"
                : mode === "easy" ? "Proven from your code" : "Parser-proven"}
            </dd>
          </div>
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
      {/* Narration sits outside the `study` gate on purpose. The two arrive on
          separate requests, so gating the whole panel on the parser payload
          also erased a narration that had already succeeded -- and gating
          narration on the parser payload made one failure look like five. */}
      <div className="study-content">
        {study ? <StructuralSummary structural={study.structural} mode={mode} /> : null}
        {/* Expert leads with impact. Someone onboarding onto a codebase is
            asking "what does this control, and what can break it" before they
            are asking for prose -- and this answer is parser truth, so it is
            the one part of the panel that is always there, key or no key. */}
        {study && mode !== "easy" ? (
          <ImpactWidget impact={study.impact} mode={mode} onSelectNode={onSelectNode} />
        ) : null}
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
        {study && mode === "easy" ? (
          <ImpactWidget impact={study.impact} mode={mode} onSelectNode={onSelectNode} />
        ) : null}
        {study ? (
          <>
            <Connections
              neighbors={study.neighbors}
              node={node}
              mode={mode}
              onSelectNode={onSelectNode}
            />
            <SourceExcerpt source={study.source} />
            <LensNotes lens={study.lens} language={node.language} mode={mode} />
          </>
        ) : null}
      </div>
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

/**
 * "Change this and these places feel it" / "this breaks if these change".
 *
 * Every row is graph truth with a real citation, so this section renders
 * identically with no provider configured -- which is the point. The depth
 * badge and the possible-route wording are both load-bearing: a chain that
 * passes through one unproven edge is unproven for its whole length, and the
 * backend labels it that way rather than rounding it up to a fact.
 */
function ImpactWidget({ impact, mode, onSelectNode }) {
  if (!impact) return null;
  const affects = impact.affects ?? [];
  const depends = impact.depends_on ?? [];
  if (!affects.length && !depends.length) return null;
  const easy = mode === "easy";
  return (
    <section className="impact-widget" aria-labelledby="impact-heading">
      <div className="study-section-heading">
        <h2 id="impact-heading">{easy ? "What this touches" : "Impact"}</h2>
        <span>No model needed</span>
      </div>
      <div className="impact-columns">
        <ImpactColumn
          title={easy ? "Change this and these change too" : "Change this → affected"}
          empty={
            easy
              ? "Nothing else in your code would notice if you changed this."
              : "No parser-proven dependents."
          }
          items={affects}
          mode={mode}
          onSelectNode={onSelectNode}
        />
        <ImpactColumn
          title={easy ? "This needs these to work" : "Depends on → breaks if changed"}
          empty={
            easy
              ? "This does not rely on anything else in your code."
              : "No parser-proven dependencies."
          }
          items={depends}
          mode={mode}
          onSelectNode={onSelectNode}
        />
      </div>
      {impact.truncated ? (
        <p className="study-loading">
          {easy
            ? `Traced ${impact.max_depth} steps out; the chain continues past that.`
            : `Traced to depth ${impact.max_depth}; deeper reach is not shown.`}
        </p>
      ) : null}
    </section>
  );
}

function ImpactColumn({ title, empty, items, mode, onSelectNode }) {
  return (
    <div className="impact-column">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="study-loading">{empty}</p>
      ) : (
        <ul className="impact-list">
          {items.map((item) => (
            <li key={item.node_id}>
              <button type="button" onClick={() => onSelectNode(item.node_id)}>
                <span className="impact-name">{item.name}</span>
                <span className="impact-meta">
                  {/* Depth 1 is "directly"; anything further is reach, and a
                      learner deciding what to read next needs the difference. */}
                  {item.depth === 1
                    ? mode === "easy" ? "directly" : "direct"
                    : mode === "easy"
                      ? `${item.depth} steps away`
                      : `depth ${item.depth}`}
                  {item.certain ? "" : mode === "easy" ? " · possible link" : " · possible"}
                </span>
                <span className="impact-citation">{item.citation}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
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

// Room above a dot fits about eighteen monospace glyphs at 9px; the TAIL of a
// long name survives truncation because that is the distinguishing part
// (basenames repeat, suffixes differ).
function shortConnectionName(name) {
  const text = String(name ?? "");
  return text.length <= 18 ? text : `…${text.slice(-17)}`;
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
      {/* Each dot names its structure (audit gap 13): six anonymous dots
          decorated the labelled list below without informing. The name is the
          item's own, shortened the way every other surface shortens. */}
      {left.map((item, index) => (
        <text
          key={`in-name-${item.node_id}`}
          className="mini-constellation__name"
          x="8"
          y={seat(index, left.length) - 7}
          textAnchor="start"
        >
          {shortConnectionName(item.name)}
        </text>
      ))}
      {right.map((item, index) => (
        <text
          key={`out-name-${item.node_id}`}
          className="mini-constellation__name"
          x="272"
          y={seat(index, right.length) - 7}
          textAnchor="end"
        >
          {shortConnectionName(item.name)}
        </text>
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

const NARRATION_FAILURE_HEADINGS = {
  grounding: "The explanation was withheld.",
  unavailable: "Codemble could not reach the model.",
  rejected: "The model refused the request.",
  timeout: "The model is taking longer than expected.",
  provider: "The model's reply could not be read.",
};

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
  if (explanation.status === "error" || explanation.status === "timeout") {
    // One heading per failure kind. These all shared the "withheld" wording,
    // so a dropped Wi-Fi connection told the learner Codemble had refused
    // ungrounded output -- a correctness lecture for a connectivity fault.
    const grounding = explanation.reason === "grounding";
    return (
      <section className="study-notice" role="alert" aria-labelledby="explanation-heading">
        <h2 id="explanation-heading">{NARRATION_FAILURE_HEADINGS[explanation.reason] ?? NARRATION_FAILURE_HEADINGS.provider}</h2>
        <p>{explanation.message}</p>
        {grounding ? (
          <p>Codemble will not display provider output that falls outside parser evidence.</p>
        ) : null}
        <p>Every fact from the parser on this panel is unaffected.</p>
        {explanation.retryable === false ? null : (
          <button className="check-primary" type="button" onClick={onRetry}>
            Try again
          </button>
        )}
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
      {explanation.excerpt?.truncated ? (
        <p className="study-loading">
          {mode === "easy"
            ? `This file is long, so the model was shown lines ${explanation.excerpt.first}–${explanation.excerpt.last} of ${explanation.excerpt.total}.`
            : `Narrated from an excerpt: lines ${explanation.excerpt.first}–${explanation.excerpt.last} of ${explanation.excerpt.total}.`}
        </p>
      ) : null}
      {explanation.withheld > 0 ? (
        <p className="study-loading">
          {explanation.withheld} {explanation.withheld === 1 ? "part" : "parts"} of the
          reply {explanation.withheld === 1 ? "was" : "were"} malformed and left out.
        </p>
      ) : null}
      {/* Behind a disclosure, closed. The line-by-line walkthrough used to be
          the bulk of what greeted every single click, which is most of what
          "the explanations are too complex for a casual user" meant: a reader
          who wanted to know what a file is FOR was handed eight numbered
          claims about individual lines. It is genuinely useful and it stays --
          one click away, for the reader who has decided they want it.
          An empty walkthrough is ordinary rather than a failure, so the
          disclosure follows the content instead of standing over nothing. */}
      {explanation.walkthrough.length ? (
        <details className="walkthrough-disclosure">
          <summary>
            {mode === "easy"
              ? `Walk me through it line by line (${explanation.walkthrough.length})`
              : `Line walkthrough (${explanation.walkthrough.length})`}
          </summary>
          <ul className="evidence-list">
            {explanation.walkthrough.map((item) => (
              <li key={`${item.citation}-${item.text}`}>
                <p>{item.text}</p>
                <Citation citation={item.citation} fallbackLine={item.line} />
              </li>
            ))}
          </ul>
        </details>
      ) : null}
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
