import { nebulaTintKey } from "./graphData.js";

// Every coordinate here comes from GET /api/map. This file draws numbers and
// decides nothing: no layout, no ordering, no layering happens client-side.

const TINT_VAR = {
  nebPython: "var(--cm-neb-python)",
  nebJs: "var(--cm-neb-js)",
  nebTs: "var(--cm-neb-ts)",
};

function tintFor(language) {
  const key = nebulaTintKey(language);
  return key ? TINT_VAR[key] : "var(--cm-hairline)";
}

// Box geometry (box.width) is backend-computed and fixed regardless of label
// length (codemble/graph/mapview.py: _BOX_WIDTH is a constant) -- this only
// decides how much of the label fits inside that width, the way CSS
// text-overflow would if SVG <text> supported it. 0.62em matches the
// monospace advance width WorkflowTree already assumes for row.label below.
const BOX_LABEL_FONT_PX = 13;
const BOX_LABEL_CHAR_EM = 0.62;
const BOX_LABEL_X = 14;
const BOX_LABEL_RIGHT_PAD = 10;

function fitBoxLabel(label, boxWidth) {
  const available = boxWidth - BOX_LABEL_X - BOX_LABEL_RIGHT_PAD;
  const maxChars = Math.max(1, Math.floor(available / (BOX_LABEL_FONT_PX * BOX_LABEL_CHAR_EM)));
  if (label.length <= maxChars) return label;
  // An honest truncation, never a silent clip: a shortened identifier with
  // an ellipsis tells the learner it is shortened; a bare clip (the bug this
  // fixes) looked like a real, different identifier.
  return `${label.slice(0, Math.max(1, maxChars - 1))}…`;
}

export function MapView({
  data,
  mapTab,
  mode,
  error,
  onSelectTab,
  onSelectRegion,
  onSelectNode,
  onRetry,
}) {
  return (
    <section className="map-view" aria-label="Two-dimensional project map">
      <nav className="map-tabs" aria-label="Map view">
        <button
          type="button"
          aria-pressed={mapTab === "architecture"}
          onClick={() => onSelectTab("architecture")}
        >
          {mode === "easy" ? "How it fits together" : "Architecture"}
        </button>
        <button
          type="button"
          aria-pressed={mapTab === "workflow"}
          onClick={() => onSelectTab("workflow")}
        >
          {mode === "easy" ? "What runs first" : "Workflow"}
        </button>
      </nav>
      {error ? (
        <div className="map-state" role="alert">
          <h2>The map did not load.</h2>
          <p>{error} The galaxy layer is unaffected.</p>
          <button className="check-primary" type="button" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : !data ? (
        <p className="map-loading" role="status">Laying out parser evidence…</p>
      ) : mapTab === "architecture" ? (
        <ArchitectureMap
          architecture={data.architecture}
          mode={mode}
          onSelectRegion={onSelectRegion}
        />
      ) : (
        <WorkflowTree workflow={data.workflow} mode={mode} onSelectNode={onSelectNode} />
      )}
    </section>
  );
}

function ArchitectureMap({ architecture, mode, onSelectRegion }) {
  const boxes = new Map(architecture.boxes.map((box) => [box.id, box]));
  const padding = 32;
  return (
    <div className="map-scroll">
      <svg
        className="architecture-map"
        viewBox={`${-padding} ${-padding} ${architecture.width + padding * 2} ${architecture.height + padding * 2}`}
        // group, not img: `img` is children-presentational in ARIA, so it
        // stripped the name and role off every box below -- a screen-reader
        // user tabbed into focusable elements announced as nothing at all.
        // (StudyPanel's mini-constellation is correctly `img`: it has no
        // interactive children to hide.)
        role="group"
        aria-label={
          architecture.home
            ? `${architecture.boxes.length} modules in ${architecture.layer_count} import layers from Home`
            : `${architecture.boxes.length} modules in ${architecture.layer_count} import layers, measured from the modules nothing imports`
        }
      >
        <g className="architecture-map__edges">
          {architecture.edges.map((edge) => {
            const from = boxes.get(edge.src);
            const to = boxes.get(edge.dst);
            if (!from || !to) return null;
            return (
              <line
                key={`${edge.src}->${edge.dst}`}
                x1={from.x + from.width / 2}
                y1={from.y + from.height}
                x2={to.x + to.width / 2}
                y2={to.y}
                // Uncertainty stays visible in 2D exactly as it does in 3D.
                strokeDasharray={edge.certain ? undefined : "5 4"}
                className={edge.cycle ? "is-cycle" : undefined}
              />
            );
          })}
        </g>
        {architecture.boxes.map((box) => (
          <g
            key={box.id}
            className="architecture-map__box"
            data-understood={box.understood}
            data-home={box.home}
            data-reachable={box.reachable}
            data-partial={box.partial}
            transform={`translate(${box.x} ${box.y})`}
            role="button"
            tabIndex={0}
            aria-label={`${box.label}, ${box.node_count} structures, ${box.loc} lines${box.understood ? ", understood" : ", not yet understood"}${box.home ? ", Home" : ""}${box.reachable ? "" : ", no import route from Home"}${box.partial ? ", unchartable, syntax error" : ""}`}
            onClick={() => onSelectRegion(box.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectRegion(box.id);
              }
            }}
          >
            {/* Native hover tooltip; the full label is also always in
                aria-label above regardless of what the glyphs below fit. */}
            <title>{box.label}{box.partial ? " — unchartable, syntax error" : ""}</title>
            <rect width={box.width} height={box.height} rx="3" />
            <rect className="box-tint" width="4" height={box.height} fill={tintFor(box.language)} />
            {/* A corner flag, not just a colour: the box outline already
                carries understood (colour), Home (width), and reachability
                (dash), so a fourth signal on the same property would collide
                -- and a syntax error must stay perceivable without colour
                vision. The words are in <title> and aria-label above; the
                meta line below is already full at this fixed box width. */}
            {box.partial ? (
              <path
                className="box-partial"
                d={`M ${box.width - 16} 2 L ${box.width - 2} 2 L ${box.width - 2} 16 Z`}
              />
            ) : null}
            <text x={BOX_LABEL_X} y="24">{fitBoxLabel(box.label, box.width)}</text>
            <text className="box-meta" x="14" y="42">
              {mode === "easy"
                ? `${box.node_count} ${box.node_count === 1 ? "piece" : "pieces"}`
                : `${box.node_count} nodes · ${box.loc} LOC`}
            </text>
          </g>
        ))}
      </svg>
      {architecture.home ? null : (
        <p className="map-note">
          No Home is selected, so these layers run from the modules nothing else
          imports rather than from your entrypoint. Both are read from your imports,
          not guessed. Pick your starting point with “Change Home” to see the same
          modules layered by what the project runs first.
        </p>
      )}
      {architecture.unreachable.length ? (
        <p className="map-note">
          {architecture.unreachable.length}{" "}
          {architecture.unreachable.length === 1 ? "module has" : "modules have"} no import
          route from Home, so {architecture.unreachable.length === 1 ? "it sits" : "they sit"}{" "}
          in the bottom row rather than being placed by guesswork.
        </p>
      ) : null}
    </div>
  );
}

function WorkflowTree({ workflow, mode, onSelectNode }) {
  if (!workflow.root) {
    return (
      <div className="map-state">
        <h2>No Home is selected.</h2>
        <p>
          The workflow tree starts at your entrypoint. Pick Home and this tab will
          show what runs first, then what that calls.
        </p>
      </div>
    );
  }
  const rows = new Map(workflow.nodes.map((row) => [row.order, row]));
  return (
    <div className="map-scroll">
      <svg
        className="workflow-tree"
        viewBox={`-16 -16 ${workflow.width + 32} ${workflow.height + 32}`}
        // group, not img -- see ArchitectureMap above: these rows are buttons.
        role="group"
        aria-label={`Call tree from ${workflow.root}, ${workflow.nodes.length} steps deep to ${workflow.depth_count} levels`}
      >
        <g className="workflow-tree__edges">
          {workflow.nodes.map((row) => {
            if (row.parent === null) return null;
            const parent = [...rows.values()]
              .filter((candidate) => candidate.id === row.parent && candidate.order < row.order)
              .at(-1);
            if (!parent) return null;
            return (
              <path
                key={`${row.order}`}
                d={`M ${parent.x + 8} ${parent.y + 20} V ${row.y + 12} H ${row.x + 8}`}
                strokeDasharray={row.certain ? undefined : "5 4"}
              />
            );
          })}
        </g>
        {workflow.nodes.map((row) => (
          <g
            key={row.order}
            className="workflow-tree__row"
            data-understood={row.understood}
            data-cut={row.cut ?? undefined}
            data-partial={row.partial}
            data-relation={row.relation}
            transform={`translate(${row.x} ${row.y})`}
            role="button"
            tabIndex={0}
            aria-label={`${row.label} at ${row.file}:${row.lineno}${row.certain ? "" : ", possible call"}${row.cut === "cycle" ? ", repeats an earlier step" : ""}${row.cut === "repeat" ? ", already shown above" : ""}${row.partial ? ", unchartable, syntax error" : ""}`}
            onClick={() => onSelectNode(row.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectNode(row.id);
              }
            }}
          >
            <circle cx="8" cy="16" r="4" />
            <text x="20" y="20">{row.label}</text>
            <text className="row-meta" x="20" y="20" dx={`${row.label.length * 0.62}em`}>
              {row.relation === "defines"
                ? mode === "easy" ? " — lives here" : " — defined in this module"
                : row.certain
                  ? ""
                  : " — possible call"}
              {row.cut === "cycle" ? " — loops back" : ""}
              {row.cut === "repeat" ? " — shown above" : ""}
              {/* Unlike the fixed-width architecture box, a tree row has room
                  for the word, so partial says so in the same slot that
                  already carries "possible call". */}
              {row.partial ? (mode === "easy" ? " — could not be read" : " — unchartable") : ""}
            </text>
          </g>
        ))}
      </svg>
      {workflow.unreachable.length ? (
        <p className="map-note">
          {workflow.unreachable.length}{" "}
          {workflow.unreachable.length === 1 ? "structure is" : "structures are"} never
          reached from Home by a parser-proven call. They are listed as unreached rather
          than attached to the tree by guesswork.
        </p>
      ) : null}
    </div>
  );
}
