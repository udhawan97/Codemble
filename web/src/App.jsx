import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { GalaxyCanvas } from "./GalaxyCanvas.jsx";
import { CoachMarks, HintChip } from "./GuidanceLayer.jsx";
import { MapView } from "./MapView.jsx";
import { ModeControl } from "./ModeControl.jsx";
import { StudyPanel } from "./StudyPanel.jsx";
import {
  LEVELS,
  conceptTitle,
  defaultRegion,
  groupByCommunity,
  languageLabel,
} from "./graphData.js";
import {
  createHttpLearnerSessionAdapter,
  createLearnerSession,
} from "./learnerSession.js";
import { PARSE_STAGES } from "./projectMapping.js";
import { createMapViewportStore } from "./mapViewport.js";

export function App() {
  const mobileMenuRef = useRef(null);
  const modulesTriggerRef = useRef(null);
  const finderTriggerRef = useRef(null);
  const finderReturnRef = useRef(null);
  const chartTriggerRef = useRef(null);
  const stageRef = useRef(null);
  const systemCopyRef = useRef(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mapViewportStore = useMemo(() => createMapViewportStore(), []);
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
  useEffect(() => {
    if (state.status !== "ready") {
      setMobileMenuOpen(false);
      mapViewportStore.clear();
    }
  }, [mapViewportStore, state.status]);
  useEffect(() => {
    const wideRail = window.matchMedia("(min-width: 40rem)");
    const closeDisclosure = (event) => {
      if (event.matches) setMobileMenuOpen(false);
    };
    wideRail.addEventListener("change", closeDisclosure);
    return () => wideRail.removeEventListener("change", closeDisclosure);
  }, []);
  // Cmd/Ctrl-K opens the finder from anywhere, including with the galaxy
  // focused. Bound on the window rather than the canvas so it works no matter
  // which layer or panel currently holds focus.
  useEffect(() => {
    function onKeyDown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        finderReturnRef.current =
          document.activeElement === document.body ? null : document.activeElement;
        session.dispatch({ type: "SET_FINDER_OPEN", open: true });
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [session]);
  const {
    chart,
    checkData,
    checkError,
    coachmarksSeen,
    entrypointError,
    entrypointOpen,
    error,
    explanation,
    explanationError,
    explanationLoading,
    finderOpen,
    focusedGraph,
    focusedMapData,
    focusedStudiedCount,
    graph,
    hint,
    hoverNodeId,
    languageFocus,
    languageOptions,
    layer,
    legendOpen,
    level,
    litRegionId,
    llmStatus,
    mapError,
    mapTab,
    mode,
    modeChosen,
    moduleIndex,
    parseProgress,
    pendingDawnRegionId,
    picker,
    projectName,
    projectFailure,
    region,
    revealedRegionIds,
    selectedNode,
    showAll,
    showChart,
    showChecks,
    sidebarOpen,
    status,
    studyData,
    studyError,
  } = state;

  function restoreRailFocus(primary, secondary) {
    requestAnimationFrame(() => {
      const values = [primary, secondary, mobileMenuRef];
      for (const value of values) {
        const candidate = value && "current" in value ? value.current : value;
        if (candidate?.isConnected && candidate.getClientRects().length) {
          candidate.focus();
          return;
        }
      }
    });
  }

  function toggleModules(event) {
    session.dispatch({ type: "TOGGLE_SIDEBAR" });
    if (sidebarOpen) restoreRailFocus(event.currentTarget, modulesTriggerRef);
  }

  function closeModules() {
    session.dispatch({ type: "TOGGLE_SIDEBAR" });
    restoreRailFocus(modulesTriggerRef);
  }

  function openFinder(event) {
    finderReturnRef.current = event.currentTarget;
    session.dispatch({ type: "SET_FINDER_OPEN", open: true });
  }

  function closeFinder() {
    session.dispatch({ type: "SET_FINDER_OPEN", open: false });
    restoreRailFocus(finderReturnRef.current, finderTriggerRef);
    finderReturnRef.current = null;
  }

  function goFromFinder(regionId) {
    session.dispatch({ type: "GO_TO_REGION", regionId });
    requestAnimationFrame(() => systemCopyRef.current?.focus());
  }

  function followHint() {
    session.dispatch({ type: "FOLLOW_HINT" });
    requestAnimationFrame(() => systemCopyRef.current?.focus());
  }

  function dismissCoachmarks() {
    session.dispatch({ type: "DISMISS_COACHMARKS" });
    requestAnimationFrame(() => stageRef.current?.focus());
  }

  if (error) {
    return (
      <main className="load-state" role="alert">
        <h1>The graph did not load.</h1>
        <p>{error}</p>
        <p>Your progress is stored on this machine and is not affected.</p>
        <button className="check-primary" type="button" onClick={() => session.start()}>
          Try again
        </button>
      </main>
    );
  }

  if (parseProgress) {
    return (
      <LoadingScreen
        progress={parseProgress}
        onCancel={() => session.dispatch({ type: "RESET_PROJECT" })}
      />
    );
  }

  if (status === "picking" && picker) {
    return (
      <PickerScreen
        picker={picker}
        failure={projectFailure}
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

  // One element, two placements. Over the galaxy it floats: the 3D canvas is
  // deep space at this corner, so nothing is behind it. The Map draws its SVG
  // in normal flow from that same corner, so there it is handed to MapView and
  // takes its own row above the drawing instead of sitting on the first rows
  // of the tree.
  const systemCopy =
    level === LEVELS.SYSTEM ? (
      <section
        ref={systemCopyRef}
        className={`orientation-copy orientation-copy--system${
          layer === "map" ? " orientation-copy--inline" : ""
        }`}
        tabIndex={-1}
      >
        {/* No heading here any more: the breadcrumb in the header already names
            this module, and rendering the full path at display size wrapped it
            across three lines over the very system it described. Dropping it
            also means the Map variant's height cap below rarely binds. */}
        <p>
          {focusedGraph.nodes.some((node) => node.region === region.id && node.partial)
            ? `${region.node_count} source ${region.node_count === 1 ? "file remains" : "files remain"} visible · ${region.loc} lines. The module is unchartable beyond raw source because it has a syntax error.`
            : layer === "map"
              ? // On the Map, a module is one box: its internal structures
                // aren't drawn here, only in the Galaxy. Say so plainly
                // rather than let the click look like it revealed nothing.
                // Only claim what is true for every module — an unreachable
                // one has no rows in the Workflow tab, so never promise it.
                `The ${region.node_count} parser-proven ${region.node_count === 1 ? "structure" : "structures"} inside this module ${region.node_count === 1 ? "is" : "are"} drawn as planets in the Galaxy layer. This map shows how modules connect, not what is inside them.`
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
    ) : null;

  return (
    <main
      className="app-shell"
      data-level={showChart ? "chart" : level.toLowerCase()}
      data-mode={mode}
    >
      <header className="instrument-rail">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <strong>Codemble</strong>
            <span>{projectName}</span>
          </div>
        </div>
        <nav className="location" aria-label="Breadcrumb" aria-live="polite">
          {showChart ? (
            <span aria-current="page">Star chart</span>
          ) : (
            <>
              <button
                type="button"
                disabled={level === LEVELS.GALAXY}
                aria-current={level === LEVELS.GALAXY ? "page" : undefined}
                onClick={() => session.dispatch({ type: "SET_LEVEL_GALAXY" })}
              >
                Galaxy
              </button>
              {level === LEVELS.GALAXY ? (
                <small>
                  {" · Home "}
                  {graph.selected_entrypoint
                    ? (defaultRegion(graph)?.id ?? "unresolved")
                    : "unselected"}
                </small>
              ) : (
                <>
                  <span aria-hidden="true">/</span>
                  <button
                    type="button"
                    disabled={level === LEVELS.SYSTEM}
                    aria-current={level === LEVELS.SYSTEM ? "page" : undefined}
                    onClick={() => session.dispatch({ type: "RETREAT" })}
                  >
                    {region.id}
                  </button>
                </>
              )}
              {level === LEVELS.STUDY && selectedNode ? (
                <>
                  <span aria-hidden="true">/</span>
                  <span aria-current="page">{selectedNode.name}</span>
                </>
              ) : null}
              {languageFocus !== "all" ? (
                <small>{" · "}{languageLabel(languageFocus)} focus</small>
              ) : null}
            </>
          )}
        </nav>
        <div
          className="rail-overflow"
          data-open={mobileMenuOpen || undefined}
          onKeyDown={(event) => {
            if (event.key === "Escape" && mobileMenuOpen) {
              event.preventDefault();
              setMobileMenuOpen(false);
              mobileMenuRef.current?.focus();
            }
          }}
        >
          <button
            ref={mobileMenuRef}
            className="mobile-menu-trigger"
            type="button"
            aria-expanded={mobileMenuOpen}
            aria-controls="rail-overflow-panel"
            onClick={() => setMobileMenuOpen((open) => !open)}
          >
            Menu
          </button>
          <div
            className="rail-overflow__panel"
            id="rail-overflow-panel"
            onClickCapture={(event) => {
              if (
                event.target.closest("button") &&
                !event.target.closest(".switch-project")
              ) {
                setMobileMenuOpen(false);
              }
            }}
          >
            <div className="rail-actions">
              <button
                ref={modulesTriggerRef}
                className="rail-action"
                type="button"
                aria-pressed={sidebarOpen}
                onClick={toggleModules}
              >
                Modules
              </button>
              <button
                ref={finderTriggerRef}
                className="rail-action"
                type="button"
                onClick={openFinder}
              >
                Find <kbd>⌘K</kbd>
              </button>
              {showChart ? (
                <button
                  ref={chartTriggerRef}
                  className="rail-action"
                  type="button"
                  onClick={() => {
                    session.dispatch({ type: "HIDE_CHART" });
                    restoreRailFocus(chartTriggerRef);
                  }}
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
                  ref={chartTriggerRef}
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
              {/* A view preference over the immutable graph, exactly like language
                  focus: it changes how much sky is drawn, never what the parser
                  found. Galaxy-only, because reveal is a galaxy affordance. */}
              {layer === "galaxy" ? (
                <button
                  className="rail-action rail-action--toggle"
                  type="button"
                  aria-pressed={showAll}
                  title="Draw every module at once, including the ones no route from Home reaches"
                  onClick={() => session.dispatch({ type: "TOGGLE_SHOW_ALL" })}
                >
                  Show all
                </button>
              ) : null}
              <LayerSwitcher
                layer={layer}
                mode={mode}
                onChange={(next) => session.dispatch({ type: "SET_LAYER", layer: next })}
              />
              <LanguageFocus
                options={languageOptions}
                value={languageFocus}
                onChange={(language) =>
                  session.dispatch({ type: "SET_LANGUAGE_FOCUS", language })
                }
              />
              <ModeControl
                mode={mode}
                modeChosen={modeChosen}
                onChoose={(nextMode) => session.dispatch({ type: "SET_MODE", mode: nextMode })}
              />
            </div>
          </div>
        </div>
      </header>

      {showChart ? (
        <section className="chart-stage" aria-label="Language concept progress">
          {sidebarOpen ? (
            <IndexSidebar
              index={moduleIndex}
              currentRegionId={null}
              onGo={(regionId) => session.dispatch({ type: "GO_TO_REGION", regionId })}
              onClose={closeModules}
            />
          ) : null}
          <StarChart
            chart={chart}
            studiedCount={focusedStudiedCount}
            projectName={projectName}
            onClearProgress={() => session.dispatch({ type: "CLEAR_PROGRESS" })}
          />
        </section>
      ) : (
        <section
          ref={stageRef}
          className="map-stage"
          aria-label="Parser-proven project map"
          tabIndex={-1}
        >
        {sidebarOpen ? (
          <IndexSidebar
            index={moduleIndex}
            currentRegionId={level === LEVELS.GALAXY ? null : region?.id}
            onGo={(regionId) => session.dispatch({ type: "GO_TO_REGION", regionId })}
            onClose={closeModules}
          />
        ) : null}
        {layer === "map" ? (
          <MapView
            data={focusedMapData}
            mapTab={mapTab}
            mode={mode}
            // Only once a region is actually the drill-down (SYSTEM/STUDY): at
            // GALAXY level `region` is just the default Home, which the learner
            // has not chosen, so highlighting it would fake a selection.
            selectedRegionId={level === LEVELS.GALAXY ? undefined : region?.id}
            hasEntrypointCandidates={graph.entrypoint_candidates.length > 0}
            error={mapError}
            onSelectTab={(tab) => session.dispatch({ type: "SET_MAP_TAB", tab })}
            onSelectRegion={(regionId) =>
              session.dispatch({ type: "ADVANCE_REGION", regionId })
            }
            onSelectNode={(nodeId) =>
              session.dispatch({ type: "SELECT_STUDY_NODE", nodeId })
            }
            onRetry={() => session.dispatch({ type: "SET_LAYER", layer: "map" })}
            viewportStore={mapViewportStore}
          >
            {systemCopy}
          </MapView>
        ) : (
          <GalaxyCanvas
            graph={focusedGraph}
            level={level}
            region={region}
            selectedNode={selectedNode}
            hoverNodeId={hoverNodeId}
            pendingDawnRegionId={pendingDawnRegionId}
            revealedRegionIds={revealedRegionIds}
            mode={mode}
            onHoverNode={(nodeId) => session.dispatch({ type: "HOVER_NODE", nodeId })}
            onAdvance={(node) => session.dispatch({ type: "ADVANCE", node })}
            onRetreat={() => session.dispatch({ type: "RETREAT" })}
            onDawnConsumed={(regionId) => session.dispatch({ type: "CONSUME_DAWN", regionId })}
          />
        )}
        {/* The legend describes the layer that is actually on screen. Size and
            brightness are 3D-only encodings: mapview.py fixes _BOX_WIDTH and
            _BOX_HEIGHT as constants, draws workflow rows as fixed-radius
            circles, and never sends centrality at all -- so claiming them on
            the Map would describe an encoding the renderer does not draw,
            which is precisely the kind of wrong a learner cannot detect.
            Language tint is drawn on architecture boxes but not on workflow
            rows, so it follows the tab as well as the layer -- and in the
            galaxy it is a nebula, which makeMarker only adds for
            `node.kind === "region"`. Regions exist at GALAXY level only
            (NodeKind is module/class/function), so at system and study level
            the sky carries no tint at all and the rows must go. A learner in a
            mixed project reads "no fog here" as "no language evidence here". */}
        {/* The legend was twelve always-on rows that owned the top-right corner
            and clipped off-screen at system level. It is the same content, now
            behind a disclosure: a key you consult, not a wall you read past. */}
        <button
          className="legend-toggle"
          type="button"
          aria-expanded={legendOpen}
          onClick={() => session.dispatch({ type: "TOGGLE_LEGEND" })}
        >
          Key
        </button>
        <aside
          className="map-legend"
          hidden={!legendOpen}
          aria-label={layer === "map" ? "Map legend" : "Galaxy legend"}
        >
          {layer === "galaxy" ? (
            <>
              <span>
                <i className="legend-size" />
                Size · {mode === "easy" ? "how much code" : "lines of code"}
              </span>
              <span>
                <i className="legend-brightness" />
                Brighter · {mode === "easy" ? "used in more places" : "more distinct callers"}
              </span>
            </>
          ) : null}
          <span>
            <i className="legend-dot legend-dot--dim" />
            Dim · {mode === "easy" ? "not proven yet" : "not understood"}
          </span>
          <span>
            <i className="legend-dot legend-dot--lit" />
            Amber · {mode === "easy" ? "you proved you understand it" : "understood"}
          </span>
          <span>
            <i className="legend-dot legend-dot--partial" />
            {mode === "easy" ? "Could not be read" : "Unchartable · syntax error"}
          </span>
          <span>
            <i className="legend-route" />
            {mode === "easy" ? "Certain connection" : "Parser edge · certain"}
          </span>
          <span>
            {/* Uncertainty renders as a distinct colour in the 3D galaxy (no
                dash support in 3d-force-graph) but as a dash in the 2D SVG
                map -- the swatch must match whichever layer is on screen. */}
            <i
              className={
                layer === "map"
                  ? "legend-route legend-route--possible legend-route--dashed"
                  : "legend-route legend-route--possible"
              }
            />
            {mode === "easy" ? "Possible connection" : "Possible relationship"}
          </span>
          {(layer === "galaxy" && level === LEVELS.GALAXY) ||
          (layer === "map" && mapTab === "architecture")
            ? languageOptions
                .filter((option) => option.id !== "all")
                .map((option) => (
                  <span key={option.id}>
                    <i className={`legend-tint legend-tint--${option.id}`} /> {option.label}
                  </span>
                ))
            : null}
        </aside>
        {/* One line of body text where a display-size heading used to own the
            left half of the canvas. The counts are the same facts; the stage
            they were covering is the point. */}
        {layer === "galaxy" && level === LEVELS.GALAXY ? (
          <p className="orientation-bar">
            <span>
              {focusedGraph.regions.length}{" "}
              {languageFocus === "all"
                ? focusedGraph.regions.length === 1
                  ? "system"
                  : "systems"
                : `${languageLabel(languageFocus)} ${focusedGraph.regions.length === 1 ? "system" : "systems"}`}
            </span>
            <span className="orientation-bar__charted">
              {showAll
                ? "all charted"
                : `${revealedRegionIds.size} charted`}
            </span>
            {focusedGraph.partial_files.length ? (
              <span className="partial-summary">
                {focusedGraph.partial_files.length} unchartable · syntax error
              </span>
            ) : null}
          </p>
        ) : null}
        {layer === "galaxy" ? systemCopy : null}
        {level === LEVELS.SYSTEM && showChecks ? (
          <CheckPanel
            suite={checkData}
            error={checkError}
            mode={mode}
            onClose={() => session.dispatch({ type: "CLOSE_CHECKS" })}
            onSubmit={(checkId, selectedIds) =>
              session.dispatch({ type: "SUBMIT_CHECK", checkId, selectedIds })
            }
          />
        ) : null}
        {modeChosen === true && entrypointOpen && level === LEVELS.GALAXY ? (
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
        {/* First-run work is one ordered sequence: audience, then the
            parser-required Home choice (when ambiguous), then coaching over
            the final layer. Two native dialogs may never compete for focus. */}
        {modeChosen === true && !entrypointOpen && !coachmarksSeen ? (
          <CoachMarks
            layer={layer}
            onDismiss={dismissCoachmarks}
          />
        ) : null}
      </section>
      )}

      {/* Find is a global command promised by the header and Cmd/Ctrl-K. Keep
          its modal outside the Map/Star-chart branch so the command is never
          accepted into state without a surface to render it. */}
      {finderOpen ? (
        <ModuleFinder
          index={moduleIndex}
          onGo={goFromFinder}
          onClose={closeFinder}
        />
      ) : null}
      {!showChart ? (
        <HintChip
          hint={hint}
          onFollow={followHint}
        />
      ) : null}

      <footer className="status-line">
        <span>
          {showChart
            ? `${chart.length} concepts detected`
            : languageFocus === "all"
              ? `${graph.nodes.length} nodes · ${graph.edges.length} edges`
              : `${focusedGraph.nodes.length}/${graph.nodes.length} nodes · ${focusedGraph.edges.length} focused edges`}
        </span>
        <span>
          {showChart
            ? `${focusedStudiedCount} focused structures studied this session`
            : layer === "map"
              ? "Click a box or row to study · Switch tabs to change view"
              : "Drag to orbit · Scroll to zoom · Click to move closer · Escape to move back"}
        </span>
        <span>Local only</span>
      </footer>
    </main>
  );
}

const STAGE_COPY = Object.fromEntries(
  PARSE_STAGES.map(({ id, copy }) => [id, copy]),
);
const STAGE_ORDER = PARSE_STAGES.map(({ id }) => id);

function LoadingScreen({ progress, onCancel }) {
  const {
    stage,
    detail,
    files_done: done,
    files_total: total,
    pollError,
    pollOutage,
    attempts,
    path,
  } = progress;
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");
  const headingRef = useRef(null);
  const reached = STAGE_ORDER.indexOf(stage);

  // A whole-screen replacement with no focus move leaves a keyboard user's
  // focus on a button that no longer exists and tells a screen reader nothing
  // about where it went. Same route-change pattern the picker → galaxy hop
  // relies on the galaxy canvas for.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  async function cancel() {
    setCancelling(true);
    setCancelError("");
    try {
      await onCancel();
    } catch (resetError) {
      setCancelError(resetError.message);
      setCancelling(false);
    }
  }

  return (
    <main className="loading-screen">
      <header className="loading-header">
        <p className="picker-wordmark">Codemble</p>
        <h1 ref={headingRef} tabIndex={-1}>
          Mapping <span className="loading-path">{path}</span>
        </h1>
        <p className="loading-subtitle">
          Parsing runs on your machine. Nothing is sent anywhere.
        </p>
      </header>
      <ol className="loading-stages" aria-label="Parse stages">
        {STAGE_ORDER.map((name, index) => {
          const state =
            index < reached ? "done" : index === reached ? "active" : "waiting";
          return (
            <li key={name} data-state={state}>
              <span>{STAGE_COPY[name]}</span>
              {/* The state as a word, not only as a colour: done and waiting sit
                  two steps apart on one ink ramp, and `data-state` reaches no
                  screen reader at all. */}
              <small>
                {name === "parsing" && total ? `${done}/${total} files · ` : ""}
                {state === "done"
                  ? "done"
                  : state === "active"
                    ? detail
                      ? `working · ${detail}`
                      : "working"
                    : "waiting"}
              </small>
            </li>
          );
        })}
      </ol>
      {/* No bar until the server has reported a denominator. An indeterminate
          meter animates, and motion the data cannot justify is exactly the
          reassurance this screen must not fake: a stalled parse has to look
          stalled. */}
      {total ? (
        <progress
          className="loading-meter"
          value={done}
          max={total}
          aria-label={`${done} of ${total} files read`}
        />
      ) : null}
      {/* Stage and its live sub-step, never the running count: files_done moves
          on every 300 ms poll, and announcing it would bury the events that
          matter under a counter no listener can follow. The resolving detail
          changes only a handful of times, at real pass boundaries, so it earns
          the live region -- it is what keeps this stage from reading as a hang.
          The count stays on screen and on the meter's accessible name. */}
      <p className="loading-live" role="status">
        {detail ?? STAGE_COPY[stage] ?? "Starting"}
      </p>
      {/* Two different truths, and the session decides which one it can back
          up. A first failed poll really may be nothing, so it keeps the
          reassuring wording. Once nothing has answered for POLL_OUTAGE_ATTEMPTS
          tries (~18s) that reassurance is a claim this screen cannot support --
          it has no evidence the parse is alive, only that it cannot ask. The
          keys keep these as two elements, so the live region is announced with
          the role it escalates to rather than the one it started with. */}
      {pollError ? (
        pollOutage ? (
          <p className="loading-error" key="outage" role="alert">
            The local server has not answered for the last {attempts} tries (
            {pollError}). It may have stopped. Codemble keeps retrying, but it
            cannot tell you whether the parse is still running. Cancel below,
            then run codemble again in your terminal — nothing you have already
            lit is lost.
          </p>
        ) : (
          <p className="loading-error" key="blip" role="status">
            Lost contact with the local server ({pollError}). Still retrying —
            the parse itself may be running fine.
          </p>
        )
      ) : null}
      {cancelError ? (
        <p className="loading-error" role="alert">
          {cancelError}
        </p>
      ) : null}
      <div className="loading-actions">
        <button
          className="check-primary"
          type="button"
          disabled={cancelling}
          onClick={cancel}
        >
          {cancelling ? "Stopping…" : "Cancel and pick another project"}
        </button>
      </div>
    </main>
  );
}

function PickerScreen({ picker, failure, onBrowse, onSelect }) {
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
        <ScaleGuidance scale={scale} busy={busy} onBrowse={onBrowse} />
      ) : null}
      {failure ? (
        <ProjectFailure failure={failure} busy={busy} onSelect={onSelect} />
      ) : error ? (
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

function ScaleGuidance({ scale, busy, onBrowse }) {
  // scope_counts() files "." for sources sitting directly in the root. That is
  // the folder the learner already chose, not a smaller scope, so it can never
  // become a button that claims to narrow anything.
  const scopes = scale.suggestions.filter((suggestion) => suggestion.path !== ".");
  return (
    <section
      className="picker-scale"
      role="alert"
      aria-labelledby="picker-scale-heading"
    >
      <h2 id="picker-scale-heading">That folder is too big to map at once.</h2>
      <p>
        It has {scale.file_count} supported source files; Codemble maps up to{" "}
        {scale.scale_cap}. Choose a smaller scope — busiest first.
      </p>
      {scopes.length ? (
        <ul className="picker-scale-scopes">
          {scopes.map((suggestion) => (
            <li key={suggestion.path}>
              <button
                type="button"
                disabled={busy}
                onClick={() => onBrowse(`${scale.root}/${suggestion.path}`)}
              >
                <span>{suggestion.path}/</span>
                <small>{suggestion.file_count} files</small>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <PathEntry busy={busy} onBrowse={onBrowse} />
    </section>
  );
}

function PathEntry({ busy, onBrowse }) {
  const [typed, setTyped] = useState("");
  return (
    <form
      className="picker-path-entry"
      onSubmit={(event) => {
        event.preventDefault();
        const target = typed.trim();
        // Deliberately unvalidated here. /api/picker/browse resolves the path
        // and answers 403 for anything outside the home jail; re-deciding that
        // in the browser would be a second, weaker copy of the only rule that
        // matters, and the one a learner could edit around.
        if (target) onBrowse(target);
      }}
    >
      <label htmlFor="picker-path-input">Or type a folder path</label>
      <input
        id="picker-path-input"
        type="text"
        value={typed}
        disabled={busy}
        placeholder="/Users/you/project/src"
        onChange={(event) => setTyped(event.target.value)}
      />
      <button type="submit" disabled={busy || !typed.trim()}>
        Go
      </button>
    </form>
  );
}

function ProjectFailure({ failure, busy, onSelect }) {
  // ParseJob turns any worker exception into str(error), so `detail` can be raw
  // traceback text. It is shown, because a learner reporting this needs it and
  // hiding it would be its own kind of dishonest -- but it is labelled as the
  // machine's words and kept out of the sentence that explains what happened.
  return (
    <section className="picker-failure" role="alert">
      <h2>Codemble could not map that folder.</h2>
      <p>
        Nothing on disk changed, and no project's saved progress was touched. Try
        it again, or choose a different folder below.
      </p>
      <p className="picker-failure__detail">
        <span>What the parser reported</span>
        <code>{failure.detail}</code>
      </p>
      <button
        className="picker-select"
        type="button"
        disabled={busy}
        onClick={() => onSelect(failure.path)}
      >
        Try <span className="picker-recent-path">{failure.path}</span> again
      </button>
    </section>
  );
}

/**
 * Filter-as-you-type jump to any module in the project.
 *
 * Both this and the sidebar consume `moduleIndex` from the session, so neither
 * can disagree with the other about what exists. Every module is reachable
 * here whether or not it is currently charted -- progressive reveal thins the
 * sky, and this is the guarantee that thinning it never hides anything from
 * someone who knows what they are looking for.
 */
function ModuleFinder({ index, onGo, onClose }) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const dialogRef = useRef(null);
  const inputRef = useRef(null);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = needle
      ? index.filter(
          (row) =>
            row.label.toLowerCase().includes(needle) || row.file.toLowerCase().includes(needle),
        )
      : index;
    return rows.slice(0, 60);
  }, [index, query]);

  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    inputRef.current?.focus();
  }, []);

  useEffect(() => setCursor(0), [query]);

  const active = matches[Math.min(cursor, matches.length - 1)] ?? null;

  function handleKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((value) => Math.min(value + 1, matches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter" && active) {
      event.preventDefault();
      onGo(active.id);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="module-finder"
      aria-label="Find a module"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
    >
      <input
        ref={inputRef}
        type="search"
        value={query}
        placeholder="Find a module…"
        aria-label="Find a module by name or path"
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <ul role="listbox" aria-label="Matching modules">
        {matches.map((row, position) => (
          <li key={row.id}>
            <button
              type="button"
              role="option"
              aria-selected={position === cursor}
              data-active={position === cursor || undefined}
              onMouseEnter={() => setCursor(position)}
              onClick={() => onGo(row.id)}
            >
              <strong>{row.label}</strong>
              <small>{row.file}</small>
              {row.home ? <em>Home</em> : row.understood ? <em>lit</em> : null}
            </button>
          </li>
        ))}
      </ul>
      {matches.length ? null : <p className="module-finder__empty">No module matches that.</p>}
    </dialog>
  );
}

/**
 * A browsable index of every module, grouped by the import communities the
 * graph layer already computed. Those communities placed related modules near
 * each other in the sky but were otherwise invisible; naming them here is what
 * turns a constellation into something a learner can read.
 */
function IndexSidebar({ index, currentRegionId, onGo, onClose }) {
  const groups = useMemo(() => groupByCommunity(index), [index]);
  const closeButtonRef = useRef(null);
  useLayoutEffect(() => {
    closeButtonRef.current?.focus();
  }, []);
  return (
    <aside className="index-sidebar" aria-label="Project index">
      <header>
        <h2>Modules</h2>
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label="Close the project index"
        >
          ×
        </button>
      </header>
      <div className="index-sidebar__scroll">
        {groups.map((group) => (
          <section key={group.community}>
            <h3 title={group.name}>{group.name}</h3>
            <ul>
              {group.members.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    aria-current={row.id === currentRegionId ? "true" : undefined}
                    data-lit={row.understood || undefined}
                    title={row.file}
                    onClick={() => onGo(row.id)}
                  >
                    <span>{row.display ?? row.label}</span>
                    {row.home ? <em>Home</em> : null}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </aside>
  );
}

function LayerSwitcher({ layer, mode, onChange }) {
  return (
    <nav className="layer-switcher" aria-label="View layer">
      {[
        { id: "galaxy", label: "Galaxy" },
        { id: "map", label: mode === "easy" ? "Diagram" : "Map" },
      ].map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={layer === option.id}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </nav>
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

function SwitchProject({ onConfirm }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const triggerRef = useRef(null);
  const groupRef = useRef(null);
  const wasConfirmingRef = useRef(false);

  // The trigger button and the confirm group are mutually exclusive branches,
  // so the trigger unmounts (its ref goes null) before a cancel can focus it.
  // Defer the refocus to an effect, which runs after React remounts it.
  useEffect(() => {
    if (confirming) {
      groupRef.current?.focus();
    } else if (wasConfirmingRef.current) {
      triggerRef.current?.focus();
    }
    wasConfirmingRef.current = confirming;
  }, [confirming]);

  function cancel() {
    setConfirming(false);
    setFailure("");
  }

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

  return (
    <div
      className="switch-project"
      data-confirming={confirming || undefined}
      role={confirming ? "group" : undefined}
      aria-label={confirming ? "Switch project" : undefined}
      tabIndex={confirming ? -1 : undefined}
      ref={confirming ? groupRef : undefined}
      onKeyDown={(event) => {
        if (event.key === "Escape" && confirming && !busy) cancel();
      }}
    >
      {!confirming ? (
      <button
        className="rail-action"
        type="button"
        ref={triggerRef}
        onClick={() => setConfirming(true)}
      >
        Switch project
      </button>
      ) : (
        <>
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
            <button className="rail-action" type="button" disabled={busy} onClick={cancel}>
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function EntrypointPicker({ candidates, nodes, selectedEntrypoint, error, onSelect, onContinue }) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const firstActionRef = useRef(null);
  useLayoutEffect(() => {
    firstActionRef.current?.focus();
  }, []);
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
              <button
                ref={candidate === candidates[0] ? firstActionRef : undefined}
                type="button"
                key={candidate}
                onClick={() => onSelect(candidate)}
              >
                <span>{candidate}</span>
                <small>{node?.file}:{node?.lineno} · parser rank {node?.entrypoint_rank}</small>
              </button>
            );
          })}
        </div>
      ) : null}
      {error ? <p className="entrypoint-error" role="alert">{error}</p> : null}
      <button
        ref={candidates.length ? undefined : firstActionRef}
        className="entrypoint-continue"
        type="button"
        onClick={onContinue}
      >
        {selectedEntrypoint ? "Keep current Home" : "Explore without Home"}
      </button>
    </aside>
  );
}

function CheckPanel({ suite, error, mode, onClose, onSubmit }) {
  const current = suite?.checks.find((check) => !check.passed) ?? null;
  const passed = suite?.checks.filter((check) => check.passed).length ?? 0;
  const [selected, setSelected] = useState(() => new Set());
  const [feedback, setFeedback] = useState(null);
  const [affirmation, setAffirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    setSelected(new Set());
    setFeedback(null);
    setSubmitError("");
  }, [current?.id]);

  function choose(optionId, multiple) {
    setAffirmation("");
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
      // A correct answer advances `current`, which resets `feedback` — so the
      // affirmation lives in its own slot or it would vanish before it is read.
      if (result.correct) {
        setAffirmation(result.message);
        setFeedback(null);
      } else {
        setAffirmation("");
        setFeedback(result);
      }
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
      {!suite && !error ? (
        <p className="check-loading" role="status">Deriving answers from parser edges…</p>
      ) : null}
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
          <p>
            Every question here is answered by the parser graph, and this region
            has no certain relationship Codemble can build one from. It stays dim
            rather than lighting on a question that would prove nothing. Import
            this module somewhere, or call something inside it, and its checks
            appear.
          </p>
        </div>
      ) : null}
      {current && !suite.region_understood ? (
        <form className="active-check" onSubmit={submit}>
          <div className="check-progress">
            <span>Check {passed + 1} of {suite.checks.length}</span>
            <progress value={passed} max={suite.checks.length} />
          </div>
          {affirmation ? (
            <p className="check-affirmation" role="status">
              <span aria-hidden="true">✦</span> {affirmation}
            </p>
          ) : null}
          <fieldset>
            <legend>{current.prompt_voices[mode]}</legend>
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

function StarChart({ chart, studiedCount, projectName, onClearProgress }) {
  const understood = chart.filter((item) => item.understood_nodes > 0).length;
  const headingRef = useRef(null);
  useLayoutEffect(() => {
    headingRef.current?.focus();
  }, []);
  return (
    <section className="star-chart-screen" aria-labelledby="star-chart-heading">
      <header className="star-chart-intro">
        <p>Parser-detected concepts</p>
        <h1 ref={headingRef} id="star-chart-heading" tabIndex={-1}>
          Your language star chart.
        </h1>
        <p>
          Encountered comes from real syntax. Studied tracks this session. Understood lights only after graph-derived checks pass.
        </p>
        <dl>
          <div><dt>Concepts encountered</dt><dd>{chart.length}</dd></div>
          <div><dt>Studied this session</dt><dd>{studiedCount}</dd></div>
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
              <div><dt>Studied (session)</dt><dd>{item.studied_nodes}/{item.nodes}</dd></div>
              <div><dt>Understood</dt><dd>{item.understood_nodes}/{item.nodes}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <ClearProgress projectName={projectName} onConfirm={onClearProgress} />
    </section>
  );
}

function ClearProgress({ projectName, onConfirm }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const triggerRef = useRef(null);
  const groupRef = useRef(null);
  const wasConfirmingRef = useRef(false);

  // Same deferred refocus SwitchProject uses: the trigger and the confirm group
  // are mutually exclusive branches, so the trigger has already unmounted by the
  // time a cancel would try to focus it.
  useEffect(() => {
    if (confirming) {
      groupRef.current?.focus();
    } else if (wasConfirmingRef.current) {
      triggerRef.current?.focus();
    }
    wasConfirmingRef.current = confirming;
  }, [confirming]);

  function cancel() {
    setConfirming(false);
    setFailure("");
  }

  async function confirm() {
    setBusy(true);
    setFailure("");
    try {
      await onConfirm();
      setConfirming(false);
    } catch (clearError) {
      setFailure(clearError.message);
    } finally {
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <section className="progress-reset">
        <button
          className="check-primary"
          type="button"
          ref={triggerRef}
          onClick={() => setConfirming(true)}
        >
          Clear this project's progress
        </button>
        <p>Start {projectName} over with every system dim again.</p>
      </section>
    );
  }
  return (
    <section
      className="progress-reset progress-reset--confirming"
      role="group"
      aria-label="Clear this project's progress"
      tabIndex={-1}
      ref={groupRef}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !busy) cancel();
      }}
    >
      <p role="alert">
        This dims every system you lit in {projectName} and cannot be undone. Your
        other projects keep their progress, and no source file is touched.
      </p>
      {failure ? (
        <p className="progress-reset__error" role="alert">
          {failure}
        </p>
      ) : null}
      <div>
        {/* The destructive half must not look like its safe twin: identical
            buttons make "which one undoes my work" a guess, and this one
            cannot be undone. */}
        <button
          className="check-primary progress-reset__confirm"
          type="button"
          disabled={busy}
          onClick={confirm}
        >
          {busy ? "Clearing…" : `Yes, clear ${projectName}`}
        </button>
        <button className="check-primary" type="button" disabled={busy} onClick={cancel}>
          Keep it
        </button>
      </div>
    </section>
  );
}
