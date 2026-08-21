import { useEffect, useRef, useState } from "react";

import { conceptTitle } from "./graphData.js";
import {
  moveJourneyStep,
  projectJourneyStep,
  reconcileJourneyStep,
} from "./learningJourney.js";

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
  onRetryStudy,
  onRetryNarration,
  onClose,
  revealSource = false,
}) {
  const panelRef = useRef(null);
  const headingRef = useRef(null);
  const errorHeadingRef = useRef(null);
  const sourceRef = useRef(null);
  const sourceHeadingRef = useRef(null);
  const revealedFor = useRef(null);
  const journey = study?.learning_journey ?? null;
  const [activeJourneyStepId, setActiveJourneyStepId] = useState(null);
  const sourceReady = Boolean(study?.source);
  // Study replaces the control that opens it. Without an explicit arrival
  // target the browser drops keyboard focus onto <body>, so the learner has to
  // rediscover the panel from the top of the document. Ordinary arrivals own
  // the module heading and reset the panel; the Read-the-source route below
  // owns the exact section it promised once that evidence exists. Every route
  // begins at the stable module heading; the source/error effects below may
  // refine that destination. Data readiness is intentionally not a dependency:
  // an ordinary response finishing must not steal focus after the learner has
  // already moved it to Close or another control.
  useEffect(() => {
    panelRef.current?.scrollTo({ top: 0, behavior: "auto" });
    headingRef.current?.focus({ preventScroll: true });
  }, [node.id, revealSource]);
  // A failed request has a more precise destination than the loading fallback.
  // Announce the visible failure once it mounts; Retry remains the next control
  // in reading order and the module heading remains the fallback before this.
  useEffect(() => {
    if (!error) return;
    panelRef.current?.scrollTo({ top: 0, behavior: "auto" });
    errorHeadingRef.current?.focus({ preventScroll: true });
  }, [error, node.id]);
  // A control named "Read the source" has to land on the source. The panel
  // opens at the top, and above the source sit the summary, the impact widget
  // and the connections list -- measured at 4144px on this project's own Home
  // module, which is 6.6 viewports down. Every other route to a node still
  // opens at the top; only this one control made that promise.
  useEffect(() => {
    if (!revealSource || !sourceReady) return;
    if (revealedFor.current === node.id) return;
    revealedFor.current = node.id;
    sourceRef.current?.scrollIntoView({ block: "start", behavior: "auto" });
    sourceHeadingRef.current?.focus({ preventScroll: true });
  }, [revealSource, sourceReady, node.id]);
  // Step identity is content-derived by the graph layer. Mode is deliberately
  // absent from this effect, so Easy/Expert changes detail without moving the
  // learner. A refreshed payload preserves the exact ID when it still exists;
  // if parser evidence removed it, reconciliation returns to the first claim
  // instead of clamping a numeric position onto a different statement.
  useEffect(() => {
    setActiveJourneyStepId((active) => reconcileJourneyStep(journey, active));
  }, [journey]);

  function retryStudy() {
    panelRef.current?.scrollTo({ top: 0, behavior: "auto" });
    headingRef.current?.focus({ preventScroll: true });
    onRetryStudy();
  }

  function retryNarration() {
    headingRef.current?.focus({ preventScroll: true });
    onRetryNarration();
  }

  return (
    <aside
      ref={panelRef}
      className="study-preview"
      aria-label="Selected source structure"
      aria-busy={!study && !error}
    >
      <header className="study-preview__header">
        {/* The panel's own dismissal. It had none: its only exit was "Back to
            the module" in the header rail, a different region of the screen
            that reads as navigation rather than as closing what is in front of
            you -- while the checks panel, which opens in the same slot, has
            carried a Close since it shipped. Escape already worked and still
            does; this is the affordance that says so. */}
        {onClose ? (
          <button className="check-close study-preview__close" type="button" onClick={onClose}>
            Close
          </button>
        ) : null}
        <p className="study-preview__path">{node.file}:{node.lineno}</p>
        <h1 ref={headingRef} tabIndex={-1}>{node.name}</h1>
      </header>

      {error ? (
        <section className="study-notice" role="alert">
          <h2 ref={errorHeadingRef} tabIndex={-1}>Study data did not load.</h2>
          <p>{error} The parser map is still available.</p>
          <button className="check-primary" type="button" onClick={retryStudy}>
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
        {study ? (
          <LearningJourney
            journey={journey}
            activeStepId={activeJourneyStepId}
            onActiveStepChange={setActiveJourneyStepId}
            impact={study.impact}
            neighbors={study.neighbors}
            node={node}
            mode={mode}
            onSelectNode={onSelectNode}
          />
        ) : null}
        {study ? <StudyFacts node={node} mode={mode} /> : null}
        {study ? <StructuralSummary structural={study.structural} mode={mode} /> : null}
        <Explanation
          explanation={explanation}
          loading={explanationLoading}
          error={explanationError}
          llmStatus={llmStatus}
          mode={mode}
          node={node}
          onSelectNode={onSelectNode}
          onRetry={retryNarration}
        />
        {study ? (
          <>
            <SourceExcerpt
              source={study.source}
              anchorRef={sourceRef}
              headingRef={sourceHeadingRef}
            />
            <LensNotes lens={study.lens} language={node.language} mode={mode} />
          </>
        ) : null}
      </div>
    </aside>
  );
}

function StudyFacts({ node, mode }) {
  return (
    <section className="study-facts" aria-label="Selected structure facts">
      <dl>
        <div><dt>{mode === "easy" ? "What it is" : "Kind"}</dt><dd>{node.kind}</dd></div>
        <div><dt>{mode === "easy" ? "Length" : "Span"}</dt><dd>{node.loc} {node.loc === 1 ? "line" : "lines"}</dd></div>
        <div>
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
    </section>
  );
}

function LearningJourney({
  journey,
  activeStepId,
  onActiveStepChange,
  impact,
  neighbors,
  node,
  mode,
  onSelectNode,
}) {
  const [announcement, setAnnouncement] = useState("");
  const active = projectJourneyStep(journey, activeStepId, mode);
  const steps = journey?.steps ?? [];
  const possible = journey?.possible_frontier ?? [];
  const verification = journey?.verification_candidates ?? [];

  useEffect(() => setAnnouncement(""), [journey?.fingerprint]);

  function choose(stepId) {
    onActiveStepChange(stepId);
    const projected = projectJourneyStep(journey, stepId, mode);
    if (projected) setAnnouncement(`Journey step ${projected.position}: ${projected.heading}`);
  }

  function move(direction) {
    const next = moveJourneyStep(journey, activeStepId, direction);
    if (next) choose(next);
  }

  return (
    <section className="learning-journey" aria-labelledby="learning-journey-heading">
      <div className="study-section-heading">
        <h2 id="learning-journey-heading">Feature journey</h2>
        <span>Parser evidence</span>
      </div>
      {steps.length ? (
        <>
          <ol className="journey-overview" aria-label="Feature journey steps">
            {steps.map((step, index) => (
              <li key={step.id}>
                <button
                  type="button"
                  aria-current={step.id === active?.id ? "step" : undefined}
                  aria-label={`Step ${index + 1}: ${projectJourneyStep(journey, step.id, mode)?.heading}`}
                  onClick={() => choose(step.id)}
                >
                  <span>{index + 1}</span>
                  <small>{step.layer.replaceAll("-", " ")}</small>
                </button>
              </li>
            ))}
          </ol>
          {active ? (
            <article className="journey-current" data-step-id={active.id}>
              <p className="journey-position">Step {active.position}</p>
              <h3>{active.heading}</h3>
              <p>{active.summary}</p>
              <div className="journey-citations">
                {active.observationCitation ? (
                  <span>Observed at <code>{active.observationCitation}</code></span>
                ) : null}
                <span>Declaration <code>{active.citation}</code></span>
              </div>
              <div className="journey-controls" aria-label="Journey controls">
                <button type="button" onClick={() => move(-1)} disabled={active.isFirst}>
                  Back
                </button>
                <button type="button" onClick={() => move(1)} disabled={active.isLast}>
                  Next
                </button>
                <button type="button" onClick={() => choose(steps[0].id)} disabled={active.isFirst}>
                  Replay
                </button>
              </div>
              {active.expertDetails ? (
                <dl className="journey-expert-facts">
                  <div><dt>Layer</dt><dd>{active.expertDetails.layer}</dd></div>
                  <div><dt>Relation</dt><dd>{active.expertDetails.relation}</dd></div>
                  <div><dt>Node ID</dt><dd>{active.expertDetails.nodeId}</dd></div>
                  {active.expertDetails.ruleId ? (
                    <div><dt>Parser rule</dt><dd>{active.expertDetails.ruleId}</dd></div>
                  ) : null}
                </dl>
              ) : null}
            </article>
          ) : null}
        </>
      ) : null}
      <span className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement}
      </span>

      {/* The proof break precedes every possible continuation in DOM and visual
          order. A possible edge can suggest where to inspect; it can never
          quietly complete the canonical route. */}
      {journey?.break ? (
        <div className="journey-break" role="note">
          <strong>Proof stops here</strong>
          <p>{journey.break.message}</p>
          {journey.break.citation ? <code>{journey.break.citation}</code> : null}
        </div>
      ) : null}
      {possible.length ? (
        <div className="journey-possible">
          <h3>Possible next evidence</h3>
          <p>These parser observations are not part of the proven route.</p>
          <ul>
            {possible.map((item) => (
              <li key={`${item.relation}-${item.source_node_id}-${item.target_node_id}-${item.observation.citation}`}>
                <strong>Possible {item.relation}</strong>
                <span>{item.observation.citation} → {item.declaration.citation}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <details className="journey-support" open={mode === "expert"}>
        <summary>
          {mode === "easy"
            ? "Explore selected feature impact and connections"
            : "Selected feature impact, connections, and verification"}
        </summary>
        <p className="journey-support-scope">
          These facts belong to {node.name}, the selected feature. They stay fixed while you
          move between journey steps.
        </p>
        <ImpactWidget impact={impact} mode={mode} onSelectNode={onSelectNode} />
        <Connections
          neighbors={neighbors}
          node={node}
          mode={mode}
          onSelectNode={onSelectNode}
        />
        {mode === "expert" ? (
          <VerificationCandidates items={verification} onSelectNode={onSelectNode} />
        ) : null}
      </details>
    </section>
  );
}

function VerificationCandidates({ items, onSelectNode }) {
  return (
    <section className="journey-verification" aria-labelledby="journey-verification-heading">
      <div className="study-section-heading">
        <h2 id="journey-verification-heading">Selected feature verification candidates</h2>
        <span>Parser-linked</span>
      </div>
      {items.length ? (
        <ul className="impact-list">
          {items.map((item) => (
            <li key={item.node_id}>
              <button
                type="button"
                aria-label={`Open verification candidate ${item.name}; ${
                  item.certain ? "certain route" : "possible route"
                }; depth ${item.depth}; ${item.declaration.citation}`}
                onClick={() => onSelectNode(item.node_id)}
              >
                <span className="impact-name">{item.name}</span>
                <span className="impact-meta">
                  depth {item.depth}{item.certain ? " · certain route" : " · possible route"}
                </span>
                <span className="impact-citation">{item.declaration.citation}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="study-loading">No connected test evidence was found.</p>
      )}
      <p className="journey-candidate-note">
        These are parser-linked candidate verification points, not proof that a test passes.
      </p>
    </section>
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
        <h2 id="impact-heading">
          {easy ? "What the selected feature touches" : "Selected feature impact"}
        </h2>
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
              {/* The three spans stack visually, but their text nodes are
                  adjacent, so the button's accessible name ran them together as
                  `test_python_astdirectlytests/test_python_ast.py:1` -- which is
                  what a screen reader announces and what copying the row yields.
                  An explicit label puts the separators back without adding
                  stray grid items between the spans. */}
              <button
                type="button"
                aria-label={`${item.name} — ${
                  item.depth === 1 ? "direct" : `${item.depth} steps away`
                }${item.certain ? "" : ", possible"} — ${item.citation}`}
                onClick={() => onSelectNode(item.node_id)}
              >
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
          {mode === "easy"
            ? "What the selected feature connects to"
            : "Selected feature connections"}
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
            {/* Same run-on as the impact rows: the name, the relation and the
                citation are adjacent text nodes, so the accessible name read
                `test_python_astbrings this in · certaintests/...`. */}
            <button
              type="button"
              aria-label={`${item.name} — ${relationWords(item, mode)}, ${certaintyWords(item, mode)} — ${item.citation}`}
              onClick={() => onSelectNode(item.node_id)}
            >
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

function SourceExcerpt({ source, anchorRef, headingRef }) {
  return (
    <section className="source-study" aria-labelledby="source-heading" ref={anchorRef}>
      <div className="study-section-heading">
        <h2 ref={headingRef} id="source-heading" tabIndex={-1}>Real source</h2>
        <span title={`${source.file}:${source.start_line}–${source.end_line}`}>
          {source.file}:{source.start_line}–{source.end_line}
        </span>
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
