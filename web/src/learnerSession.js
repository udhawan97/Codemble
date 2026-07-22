import { LEVELS, defaultRegion } from "./graphData.js";
import { createLearnerProjection } from "./learnerProjection.js";
import { createProjectMapping } from "./projectMapping.js";

const DEFAULT_CLOCK = Object.freeze({
  setTimeout(callback, delay) {
    return globalThis.setTimeout(callback, delay);
  },
  clearTimeout(timerId) {
    globalThis.clearTimeout(timerId);
  },
});

export function createLearnerSession({
  adapter = createHttpLearnerSessionAdapter(),
  clock = DEFAULT_CLOCK,
} = {}) {
  const listeners = new Set();
  const learnerProjection = createLearnerProjection();
  let snapshot = learnerProjection.derive({
    status: "idle",
    error: "",
    graph: null,
    level: LEVELS.GALAXY,
    region: null,
    selectedNode: null,
    studyData: null,
    studyError: "",
    explanation: null,
    explanationLoading: false,
    explanationError: "",
    showChart: false,
    studiedNodeIds: new Set(),
    showChecks: false,
    checkData: null,
    checkError: "",
    entrypointDismissed: false,
    entrypointError: "",
    litRegionId: null,
    pendingDawnRegionId: null,
    languageFocus: "all",
    picker: null,
    parseProgress: null,
    projectFailure: null,
    layer: "galaxy",
    layerChosen: false,
    mapTab: "architecture",
    mapData: null,
    mapError: "",
    // Read once, here, and written only by DISMISS_COACHMARKS below. This is
    // the single owner: the component used to read localStorage during render
    // while this field held a second, non-authoritative copy, so whatever a
    // test asserted about this one said nothing about what the UI did.
    coachmarksSeen: readCoachmarksSeen(),
    llmStatus: null,
    hoverNodeId: null,
    // A view preference over the immutable graph, exactly like languageFocus:
    // it changes what is drawn, never what is true. Read once here and owned
    // only by TOGGLE_SHOW_ALL below.
    showAll: readShowAll(),
    finderOpen: false,
    sidebarOpen: false,
    legendOpen: false,
    mode: "easy",
    // Three states, not two: null means hydration hasn't resolved yet
    // (unknown), false means the backend confirmed nobody has ever chosen,
    // true means chosen (by the learner, or resolved after a mode-fetch
    // failure — see loadPreferences). Collapsing null into false was the
    // root cause of the first-run gate flashing over returning learners.
    modeChosen: null,
  });
  let lifecycle = 0;
  let modeLifecycle = 0;
  let graphController = null;
  let studyController = null;
  let explanationController = null;
  let checksController = null;
  let submissionController = null;
  let entrypointController = null;
  let mapController = null;
  let modeController = null;
  let illuminationTimer = null;

  function getSnapshot() {
    return snapshot;
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function commit(patch, { preserveChecks = false } = {}) {
    const previous = snapshot;
    let next = learnerProjection.derive({ ...previous, ...patch });
    const navigationChanged =
      next.level !== previous.level || next.region?.id !== previous.region?.id;
    if (navigationChanged) {
      const navigationPatch = { hoverNodeId: null };
      if (!preserveChecks) {
        abortController(checksController);
        abortController(submissionController);
        checksController = null;
        submissionController = null;
        navigationPatch.showChecks = false;
        navigationPatch.checkData = null;
        navigationPatch.checkError = "";
      }
      next = learnerProjection.derive({ ...next, ...navigationPatch });
    }
    snapshot = Object.freeze(next);
    for (const listener of listeners) listener();
  }

  const projectMapping = createProjectMapping({
    adapter,
    clock,
    async onReady() {
      lifecycle += 1;
      const requestLifecycle = lifecycle;
      abortController(graphController);
      graphController = new AbortController();
      return loadProjectGraph(graphController, requestLifecycle);
    },
  });
  const unsubscribeProjectMapping = projectMapping.subscribe(() => {
    const mapping = projectMapping.getSnapshot();
    const patch = {
      picker: mapping.picker,
      parseProgress: mapping.progress,
      projectFailure: mapping.failure,
    };
    if (mapping.phase === "picking") patch.status = "picking";
    if (mapping.phase === "error") {
      patch.status = "error";
      patch.error = mapping.error;
    }
    commit(patch);
  });

  async function start() {
    lifecycle += 1;
    const requestLifecycle = lifecycle;
    abortController(graphController);
    graphController = new AbortController();
    const controller = graphController;
    commit({ status: "loading", error: "" });
    let pickerState;
    try {
      pickerState = await adapter.loadPickerState({ signal: controller.signal });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: appDownMessage(requestError) });
      }
      return snapshot;
    }
    if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
    if (pickerState.state === "unpicked") {
      await projectMapping.start();
      return snapshot;
    }
    return loadProjectGraph(controller, requestLifecycle);
  }

  async function loadProjectGraph(controller, requestLifecycle) {
    commit({ status: "loading", error: "", picker: null });
    try {
      const graph = await adapter.loadGraph({ signal: controller.signal });
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      commit({
        status: "ready",
        graph,
        region: defaultRegion(graph),
        error: "",
        entrypointDismissed: Boolean(graph.selected_entrypoint),
      });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: appDownMessage(requestError) });
      }
    }
    // Outside the try on purpose, and never awaited into it: preferences are
    // a per-project concern the backend can only serve once a project is
    // bound, so they hydrate here rather than in start() — but a failure on
    // either side must never block or masquerade as the other.
    await loadPreferences(controller, requestLifecycle);
    return snapshot;
  }

  async function loadPreferences(controller, requestLifecycle) {
    // allSettled, not all: mode and provider status are preferences. A failing
    // one must never blank the other and must never surface as a graph error.
    // Each call is wrapped in an async thunk so an adapter that throws
    // synchronously (rather than rejecting a promise) still settles instead of
    // escaping allSettled and being mistaken for a graph load failure.
    const requestModeLifecycle = modeLifecycle;
    const [modeResult, statusResult] = await Promise.allSettled([
      (async () => adapter.loadMode({ signal: controller.signal }))(),
      (async () => adapter.fetchLlmStatus({ signal: controller.signal }))(),
    ]);
    if (requestLifecycle !== lifecycle || controller.signal.aborted) return;
    // A same-project setMode call (in flight or already committed) is a newer
    // truth than this fetch, which was issued before it: never let it clobber
    // the learner's choice. setMode bumps modeLifecycle synchronously, so a
    // mismatch here means the learner already made an explicit choice that
    // must win no matter which of the two requests resolves first. llmStatus
    // is unrelated to mode and always applies.
    if (requestModeLifecycle === modeLifecycle) {
      const stored = modeResult.status === "fulfilled" ? modeResult.value : null;
      const validMode = stored?.mode === "easy" || stored?.mode === "expert";
      if (validMode) {
        applyMode(stored.mode, stored.chosen === true);
      } else if (snapshot.modeChosen === null) {
        // Resolves the unknown (null) state when the response can't be
        // trusted — a thrown request, or a payload with a mode value the
        // renderer doesn't understand. Leaving it null forever would leave
        // ModeControl rendering nothing for the rest of the session, so it
        // resolves to known-and-chosen rather than known-and-never-chosen:
        // the worse failure is flashing the first-run gate over a *returning*
        // learner, who could then silently overwrite their real stored mode by
        // clicking through it — the exact bug this fix exists to prevent. A
        // genuine first-timer only loses the friendly first-run framing for
        // this one reload and still has the always-available header toggle.
        commit({ modeChosen: true });
      }
    }
    if (statusResult.status === "fulfilled") commit({ llmStatus: statusResult.value });
  }

  async function clearProgress() {
    // Deliberately uncaught, like resetProject and submitCheck: a refused clear
    // is a control failure the header shows inline, not a reason to blank the
    // galaxy the learner is still looking at.
    const requestLifecycle = lifecycle;
    await adapter.clearProgress({});
    // The reload below belongs to the project that asked for the clear. A
    // project released or switched across that await owns the session now, and
    // reloading into it would either resurrect the old graph or, against an
    // unbound server, paint a 409 over the picker.
    if (requestLifecycle !== lifecycle) return snapshot;
    lifecycle += 1;
    const nextLifecycle = lifecycle;
    abortController(graphController);
    graphController = new AbortController();
    return loadProjectGraph(graphController, nextLifecycle);
  }

  async function resetProject() {
    if (!(await projectMapping.reset())) return snapshot;
    cancelStudy();
    abortController(entrypointController);
    entrypointController = null;
    // Like entrypointController above: an in-flight map fetch belongs to the
    // released project. Abort it here and re-check lifecycle inside loadMap
    // -- abort alone would miss an adapter that resolves instead of rejecting.
    abortController(mapController);
    mapController = null;
    // The mode toggle and Switch project sit in the same always-rendered
    // header, so a mode write can still be in flight when the project is
    // released. Its rollback belongs to the project that is going away: left
    // alone, a later failure commits the previous project's mode -- and, when
    // that mode defaults to the Map layer, a spurious map fetch -- into the
    // next project's already-loading session.
    abortController(modeController);
    modeController = null;
    commit({
      graph: null,
      parseProgress: null,
      projectFailure: null,
      region: null,
      selectedNode: null,
      level: LEVELS.GALAXY,
      studyData: null,
      studyError: "",
      explanation: null,
      explanationError: "",
      explanationLoading: false,
      showChart: false,
      studiedNodeIds: new Set(),
      showChecks: false,
      checkData: null,
      checkError: "",
      entrypointDismissed: false,
      entrypointError: "",
      litRegionId: null,
      pendingDawnRegionId: null,
      languageFocus: "all",
      llmStatus: null,
      picker: null,
      mapData: null,
      mapError: "",
    });
    return start();
  }

  async function dispatch(event) {
    switch (event.type) {
      case "ADVANCE":
        return advance(event.node);
      case "ADVANCE_REGION":
        advanceRegion(event.regionId);
        return undefined;
      case "FOLLOW_HINT":
        return followHint();
      case "RETREAT":
        retreat();
        return undefined;
      case "SELECT_STUDY_NODE":
        return selectStudyNode(event.nodeId);
      case "SET_LANGUAGE_FOCUS":
        setLanguageFocus(event.language);
        return undefined;
      case "SET_MODE":
        return setMode(event.mode);
      case "HOVER_NODE":
        // Pointer motion fires this constantly; only a real change may notify.
        if (snapshot.hoverNodeId !== (event.nodeId ?? null)) {
          commit({ hoverNodeId: event.nodeId ?? null });
        }
        return undefined;
      case "SHOW_CHART":
        commit({ showChart: true });
        return undefined;
      case "HIDE_CHART":
        commit({ showChart: false });
        return undefined;
      case "OPEN_CHECKS":
        return openChecks();
      case "CLOSE_CHECKS":
        closeChecks();
        return undefined;
      case "SUBMIT_CHECK":
        return submitCheck(event.checkId, event.selectedIds);
      case "CONSUME_DAWN":
        consumeDawn(event.regionId);
        return undefined;
      case "SELECT_ENTRYPOINT":
        return selectEntrypoint(event.nodeId);
      case "DISMISS_ENTRYPOINT":
        commit({ entrypointDismissed: true });
        return undefined;
      case "CHANGE_HOME":
        cancelStudy();
        commit({
          entrypointDismissed: false,
          entrypointError: "",
          level: LEVELS.GALAXY,
          selectedNode: null,
          showChart: false,
          studyData: null,
          studyError: "",
          explanation: null,
          explanationError: "",
          explanationLoading: false,
        });
        return undefined;
      case "BROWSE_PICKER":
        return projectMapping.browse(event.path);
      case "SELECT_PROJECT":
        return projectMapping.select(event.path);
      case "RESET_PROJECT":
        return resetProject();
      case "CLEAR_PROGRESS":
        return clearProgress();
      case "SET_LAYER":
        return setLayer(event.layer);
      case "SET_MAP_TAB":
        commit({ mapTab: event.tab });
        return undefined;
      case "DISMISS_COACHMARKS":
        writeCoachmarksSeen();
        commit({ coachmarksSeen: true });
        return undefined;
      case "SET_LEVEL_GALAXY":
        cancelStudy();
        commit({ level: LEVELS.GALAXY, selectedNode: null });
        return undefined;
      case "TOGGLE_SHOW_ALL":
        writeShowAll(!snapshot.showAll);
        commit({ showAll: !snapshot.showAll });
        return undefined;
      case "SET_FINDER_OPEN":
        commit({ finderOpen: event.open });
        return undefined;
      case "TOGGLE_SIDEBAR":
        commit({ sidebarOpen: !snapshot.sidebarOpen });
        return undefined;
      case "TOGGLE_LEGEND":
        commit({ legendOpen: !snapshot.legendOpen });
        return undefined;
      // The palette and the sidebar both land here. Closing the finder in the
      // same commit as the jump keeps the two from racing: a separate close
      // dispatch could land after the region change and re-render the overlay
      // over the scene the learner just asked to see.
      case "GO_TO_REGION":
        commit({ finderOpen: false });
        return advanceRegion(event.regionId);
      default:
        throw new Error(`Unknown learner-session event: ${event.type}`);
    }
  }

  // The projection supplies only actions that move the current session. React
  // never interprets the learner's level or guesses a structure on their
  // behalf; when the learner is already looking at the target system in the
  // Galaxy, the hint becomes prose instead of an enabled no-op control.
  function followHint() {
    const action = snapshot.hint?.action;
    if (!action) return undefined;
    if (action.type === "OPEN_REGION") {
      advanceRegion(action.regionId);
      return undefined;
    }
    if (action.type === "SET_LAYER") return setLayer(action.layer);
    if (action.type === "OPEN_STUDY") return selectStudyNode(action.nodeId);
    return undefined;
  }

  // Region entry by id, for callers that hold a region *name* rather than a
  // node from the rendered scene: the 2D map (which draws every module the
  // parser found, focus or no focus) and the Easy-mode hint chip. Resolving the
  // id here rather than in React is what keeps a focused-out box from handing
  // `undefined` to advance() -- and it keeps the renderer free of graph lookups.
  function advanceRegion(regionId) {
    // Searched against the whole graph, never the focused projection: the
    // learner named a module that really exists, so the honest answer is to go
    // there. A focus that hides it widens to that module's language, exactly as
    // selectStudyNode already does for a cross-language node. The alternative --
    // an inert box that looks and announces like a button -- would be a control
    // that lies about being live.
    const region = snapshot.graph?.regions.find((candidate) => candidate.id === regionId);
    if (!region) return;
    cancelStudy();
    commit({
      languageFocus:
        snapshot.languageFocus !== "all" && region.language !== snapshot.languageFocus
          ? region.language
          : snapshot.languageFocus,
      region,
      selectedNode: null,
      level: LEVELS.SYSTEM,
      studyData: null,
      studyError: "",
      explanation: null,
      explanationError: "",
      explanationLoading: false,
    });
  }

  async function advance(node) {
    // A missing node is a caller bug, not a learner-visible failure: dropping it
    // keeps the galaxy on screen instead of tearing it down into the error
    // boundary. Every id-based caller goes through advanceRegion above.
    if (!snapshot.focusedGraph || !node) return;
    if (snapshot.level === LEVELS.GALAXY) {
      const nextRegion =
        snapshot.focusedGraph.regions.find((candidate) => candidate.id === node.id) ?? node;
      cancelStudy();
      commit({
        region: nextRegion,
        selectedNode: null,
        level: LEVELS.SYSTEM,
        studyData: null,
        studyError: "",
        explanation: null,
        explanationError: "",
      });
      return;
    }
    if (snapshot.level === LEVELS.SYSTEM) {
      const selectedNode =
        snapshot.focusedGraph.nodes.find((candidate) => candidate.id === node.id) ?? node;
      commit({ selectedNode, level: LEVELS.STUDY });
      return loadStudy(selectedNode.id);
    }
    // Already at study level: arrow keys move the announced selection between
    // siblings, so Enter has to re-target the panel. Without this it was a
    // no-op -- the canvas announced "choose_project_scope" while the panel
    // still showed the module, which is exactly what the canvas's own
    // aria-label promises would not happen.
    if (snapshot.level === LEVELS.STUDY) {
      const selectedNode = snapshot.focusedGraph.nodes.find(
        (candidate) => candidate.id === node.id,
      );
      if (!selectedNode || selectedNode.id === snapshot.selectedNode?.id) return;
      commit({ selectedNode });
      return loadStudy(selectedNode.id);
    }
  }

  function retreat() {
    if (snapshot.level === LEVELS.STUDY) {
      cancelStudy();
      commit({
        selectedNode: null,
        level: LEVELS.SYSTEM,
        studyData: null,
        studyError: "",
        explanation: null,
        explanationError: "",
        explanationLoading: false,
      });
    } else if (snapshot.level === LEVELS.SYSTEM) {
      commit({ level: LEVELS.GALAXY });
    }
  }

  async function selectStudyNode(nodeId) {
    const nextNode = snapshot.graph?.nodes.find((candidate) => candidate.id === nodeId);
    if (!nextNode) return;
    const nextRegion = snapshot.graph.regions.find(
      (candidate) => candidate.id === nextNode.region,
    );
    commit({
      languageFocus:
        snapshot.languageFocus !== "all" && nextNode.language !== snapshot.languageFocus
          ? nextNode.language
          : snapshot.languageFocus,
      region: nextRegion ?? snapshot.region,
      selectedNode: nextNode,
      level: LEVELS.STUDY,
    });
    return loadStudy(nextNode.id);
  }

  function setLanguageFocus(language) {
    const previousNodeId = snapshot.selectedNode?.id;
    commit({ languageFocus: language });
    if (previousNodeId && snapshot.selectedNode?.id !== previousNodeId) {
      cancelStudy();
      commit({
        studyData: null,
        studyError: "",
        explanation: null,
        explanationError: "",
        explanationLoading: false,
      });
    }
  }

  // Mode hydration (loadPreferences) and SET_MODE both funnel through here so
  // a mode value is never committed without also settling the layer -- an
  // explicit SET_LAYER (layerChosen) always wins, otherwise the mode picks the
  // learner's default layer -- and never without settling modeChosen, whose
  // three states the first-run gate reads directly.
  function applyMode(mode, chosen) {
    const layer = snapshot.layerChosen ? snapshot.layer : mode === "easy" ? "map" : "galaxy";
    commit({ mode, layer, modeChosen: chosen });
    // Landing on Map by mode default must fetch exactly like an explicit
    // SET_LAYER does -- otherwise a learner already in Easy mode lands on a
    // Map that stays in its loading state forever.
    if (layer === "map") ensureMapLoaded();
  }

  async function setMode(mode) {
    if (mode !== "easy" && mode !== "expert") return undefined;
    const previous = snapshot.mode;
    const previousChosen = snapshot.modeChosen;
    // Not a plain mode-equality check: confirming the current mode is exactly
    // how a first-run learner leaves the never-chosen state, so the choice
    // still has to be written when only modeChosen changes.
    if (mode === previous && snapshot.modeChosen) return undefined;
    // Bump first so a mode hydration already in flight (loadPreferences)
    // notices this explicit choice and skips its own commit on resolution.
    modeLifecycle += 1;
    abortController(modeController);
    modeController = new AbortController();
    const controller = modeController;
    // Captured like loadProjectGraph/selectEntrypoint/loadMap do: resetProject
    // aborts this controller, but an adapter that ignores the signal still
    // settles, so the project generation has to be re-checked across the await
    // as well. Both sides below belong to the project that issued the write.
    const requestLifecycle = lifecycle;
    applyMode(mode, true);
    try {
      await adapter.saveMode(mode, { signal: controller.signal });
    } catch (requestError) {
      // Rolled back rather than left optimistically committed: a snapshot that
      // silently disagrees with disk is the undetectable kind of wrong. Rolling
      // back into a *different* project would be worse still, hence the
      // lifecycle re-check beside the controller identity one.
      if (
        modeController === controller &&
        requestLifecycle === lifecycle &&
        !isAbortError(requestError)
      ) {
        applyMode(previous, previousChosen);
      }
      return undefined;
    }
    if (requestLifecycle !== lifecycle || controller.signal.aborted) return undefined;
    // Lens, checks, and the Tier 0 summary already carry both voices and
    // switch locally from the existing payload -- only narration is generated
    // per mode, so only narration is worth a refetch here. It runs after the
    // write so a rolled-back choice never leaves the other voice's narration
    // on screen.
    if (snapshot.level === LEVELS.STUDY && snapshot.selectedNode) {
      return loadExplanation(snapshot.selectedNode.id);
    }
    return undefined;
  }

  async function loadStudy(nodeId) {
    cancelStudy();
    studyController = new AbortController();
    const controller = studyController;
    commit({ studyData: null, studyError: "" });
    // Started here and deliberately not awaited: narration runs *beside* the
    // study fetch, so slow or absent narration never delays the source, lens,
    // and structural summary. It is also outside the try below -- awaiting it
    // there would let a narration failure commit `studyError`, mislabelling the
    // one part of the panel that is allowed to fail as the part that is not.
    void loadExplanation(nodeId);
    try {
      const studyData = await adapter.loadStudy(nodeId, { signal: controller.signal });
      if (
        controller.signal.aborted ||
        snapshot.level !== LEVELS.STUDY ||
        snapshot.selectedNode?.id !== nodeId
      ) {
        return;
      }
      commit({
        studyData,
        studiedNodeIds: new Set(snapshot.studiedNodeIds).add(studyData.node.id),
      });
    } catch (requestError) {
      if (
        studyController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError) &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({ studyError: errorMessage(requestError) });
      }
    }
  }

  function cancelStudy() {
    abortController(studyController);
    studyController = null;
    abortController(explanationController);
    explanationController = null;
  }

  async function loadExplanation(nodeId) {
    abortController(explanationController);
    explanationController = new AbortController();
    const controller = explanationController;
    commit({ explanation: null, explanationError: "", explanationLoading: true });
    try {
      const explanation = await adapter.loadExplanation(nodeId, snapshot.mode, {
        signal: controller.signal,
      });
      // Returns without clearing explanationLoading on purpose: a superseded
      // request must not touch state the newer request has already claimed.
      if (
        controller.signal.aborted ||
        snapshot.level !== LEVELS.STUDY ||
        snapshot.selectedNode?.id !== nodeId
      ) {
        return;
      }
      commit({ explanation, explanationLoading: false });
    } catch (requestError) {
      if (
        explanationController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError) &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({
          explanationError: errorMessage(requestError),
          explanationLoading: false,
        });
      }
    }
  }

  async function openChecks() {
    if (!snapshot.region) return;
    const regionId = snapshot.region.id;
    commit({ showChecks: true, checkData: null, checkError: "" });
    return loadChecks(regionId);
  }

  async function loadChecks(regionId) {
    abortController(checksController);
    checksController = new AbortController();
    const controller = checksController;
    try {
      const checkData = await adapter.loadChecks(regionId, { signal: controller.signal });
      if (
        !controller.signal.aborted &&
        snapshot.showChecks &&
        snapshot.region?.id === regionId
      ) {
        commit({ checkData, checkError: "" }, { preserveChecks: true });
      }
      return checkData;
    } catch (requestError) {
      if (
        checksController === controller &&
        !isAbortError(requestError) &&
        !controller.signal.aborted &&
        snapshot.showChecks &&
        snapshot.region?.id === regionId
      ) {
        commit(
          { checkError: errorMessage(requestError) },
          { preserveChecks: true },
        );
      }
      return undefined;
    }
  }

  function closeChecks() {
    abortController(checksController);
    checksController = null;
    commit({ showChecks: false, checkData: null, checkError: "" });
  }

  async function submitCheck(checkId, selectedIds) {
    if (!snapshot.region) return undefined;
    const regionId = snapshot.region.id;
    abortController(submissionController);
    submissionController = new AbortController();
    const controller = submissionController;
    const result = await adapter.submitCheck(regionId, checkId, selectedIds, {
      signal: controller.signal,
    });
    if (controller.signal.aborted || snapshot.region?.id !== regionId) return result;
    if (result.correct) await loadChecks(regionId);
    if (result.region_understood) {
      const graph = await adapter.loadGraph({ signal: controller.signal });
      if (!controller.signal.aborted && snapshot.region?.id === regionId) {
        // The Map's understood flags (mapview.py, per region and per node) are
        // computed from this same graph, so a region finishing its checks
        // invalidates the cached map exactly like a new Home does in
        // selectEntrypoint: abort any in-flight fetch for it, clear it
        // always, and refetch only when Map is the layer on screen.
        abortController(mapController);
        mapController = null;
        commit(
          {
            graph,
            region: graph.regions.find((candidate) => candidate.id === regionId),
            mapData: null,
            mapError: "",
          },
          { preserveChecks: true },
        );
        illuminateRegion(regionId);
        if (snapshot.layer === "map") await ensureMapLoaded();
      }
    }
    return result;
  }

  async function selectEntrypoint(nodeId) {
    const requestLifecycle = lifecycle;
    abortController(entrypointController);
    entrypointController = new AbortController();
    const controller = entrypointController;
    commit({ entrypointError: "" });
    try {
      const graph = await adapter.selectEntrypoint(nodeId, {
        signal: controller.signal,
      });
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      // Both Map payloads are computed *from* Home -- Architecture layers the
      // regions by import depth from it, Workflow is the call tree rooted at
      // it -- so a new Home invalidates the cached map exactly as a project
      // switch does. Left alone, the header named the new Home while the Map
      // still drew the diagram built from the old one, with no error to notice.
      // Aborted like resetProject does, and re-checked inside loadMap, because
      // an adapter that ignores the signal still resolves.
      abortController(mapController);
      mapController = null;
      commit({
        graph,
        region: defaultRegion(graph),
        entrypointError: "",
        entrypointDismissed: true,
        mapData: null,
        mapError: "",
      });
      // Cleared always, refetched only when the Map is the layer on screen:
      // ensureMapLoaded() is the same single "landing on Map fetches exactly
      // once" gate SET_LAYER and applyMode already share, so a learner on the
      // galaxy pays nothing and picks the new map up when they switch, while
      // one already looking at the Map is never stranded on a permanent
      // loading state by the clear above.
      if (snapshot.layer === "map") await ensureMapLoaded();
      return graph;
    } catch (requestError) {
      if (
        entrypointController === controller &&
        requestLifecycle === lifecycle &&
        !controller.signal.aborted &&
        !isAbortError(requestError)
      ) {
        commit({ entrypointError: errorMessage(requestError) });
      }
      return undefined;
    }
  }

  async function setLayer(layer) {
    commit({ layer, layerChosen: true });
    if (layer === "map") return ensureMapLoaded();
    return undefined;
  }

  // Shared by setLayer and applyMode so landing on Map always fetches
  // exactly once: skip when the data is already cached, skip when a fetch
  // for it is genuinely still in flight, otherwise (including a retry after
  // a failed attempt, where mapController is set but mapError is not empty)
  // start the one map-loading concern's single AbortController.
  function ensureMapLoaded() {
    if (snapshot.mapData) return undefined;
    const inFlight = mapController && !mapController.signal.aborted && !snapshot.mapError;
    return inFlight ? undefined : loadMap();
  }

  async function loadMap() {
    const requestLifecycle = lifecycle;
    abortController(mapController);
    mapController = new AbortController();
    const controller = mapController;
    commit({ mapError: "" });
    try {
      const mapData = await adapter.fetchMap({ signal: controller.signal });
      if (requestLifecycle === lifecycle && !controller.signal.aborted) {
        commit({ mapData, mapError: "" });
      }
      return mapData;
    } catch (requestError) {
      if (
        mapController === controller &&
        requestLifecycle === lifecycle &&
        !controller.signal.aborted &&
        !isAbortError(requestError)
      ) {
        // Scoped to the map layer on purpose: the galaxy must stay usable.
        commit({ mapError: errorMessage(requestError), mapData: null });
      }
      return undefined;
    }
  }

  function illuminateRegion(regionId) {
    if (illuminationTimer !== null) clock.clearTimeout(illuminationTimer);
    commit({ litRegionId: regionId, pendingDawnRegionId: regionId });
    illuminationTimer = clock.setTimeout(() => {
      illuminationTimer = null;
      if (snapshot.litRegionId === regionId) commit({ litRegionId: null });
    }, 520);
  }

  // The dawn's pending flag is deliberately not on the toast's timer above:
  // returning to the galaxy can take over a second (measured), well past the
  // toast's 520ms window. It is discarded by consumption, not by a clock --
  // GalaxyCanvas calls this the moment it actually attempts to play the dawn
  // (see CONSUME_DAWN), which happens at most once, because every route to a
  // *different* system passes back through Galaxy level first. A light-up
  // the learner abandons entirely (switches or resets the project) is
  // discarded by resetProject() below instead of lingering for the next one.
  function consumeDawn(regionId) {
    if (snapshot.pendingDawnRegionId === regionId) commit({ pendingDawnRegionId: null });
  }

  function dispose() {
    lifecycle += 1;
    for (const controller of [
      graphController,
      studyController,
      explanationController,
      checksController,
      submissionController,
      entrypointController,
      mapController,
      modeController,
    ]) {
      abortController(controller);
    }
    graphController = null;
    studyController = null;
    explanationController = null;
    checksController = null;
    submissionController = null;
    entrypointController = null;
    mapController = null;
    modeController = null;
    unsubscribeProjectMapping();
    projectMapping.dispose();
    if (illuminationTimer !== null) {
      clock.clearTimeout(illuminationTimer);
      illuminationTimer = null;
    }
  }

  return Object.freeze({ dispatch, dispose, getSnapshot, start, subscribe });
}

export function createHttpLearnerSessionAdapter(fetchImplementation = globalThis.fetch) {
  if (typeof fetchImplementation !== "function") {
    throw new TypeError("Learner-session HTTP adapter requires fetch.");
  }

  async function request(url, label, options = {}) {
    const response = await fetchImplementation(url, options);
    if (!response.ok) {
      // Every refusal on this server already carries a sentence written for a
      // learner -- "Choose a folder inside your home directory." -- and a bare
      // status code threw all of them away. selectProject read `detail`
      // already; doing it here means every caller does, rather than each one
      // growing its own copy.
      const payload = await response.json().catch(() => null);
      const detail = payload?.detail;
      const failure = new Error(
        typeof detail === "string" && detail
          ? detail
          : `${label} returned ${response.status}.`,
      );
      // The one fact that tells a refusal apart from a server that is not there
      // at all: this error exists *because* a response arrived. `fetch` rejects
      // with a bare TypeError when nothing answered, and that carries no status
      // to read. See isServerRefusal, which resetProject keys its two very
      // different recoveries off.
      failure.status = response.status;
      throw failure;
    }
    return response.json();
  }

  return Object.freeze({
    loadGraph(options = {}) {
      return request("/api/graph", "Graph request", options);
    },
    fetchMap(options = {}) {
      return request("/api/map", "Map request", options);
    },
    loadStudy(nodeId, options = {}) {
      return request(
        `/api/node/${encodeURIComponent(nodeId)}/study`,
        "Study request",
        options,
      );
    },
    loadExplanation(nodeId, mode, options = {}) {
      return request(
        `/api/node/${encodeURIComponent(nodeId)}/explanation?mode=${encodeURIComponent(mode)}`,
        "Explanation request",
        options,
      );
    },
    loadChecks(regionId, options = {}) {
      return request(
        `/api/regions/${encodeURIComponent(regionId)}/checks`,
        "Checks request",
        options,
      );
    },
    submitCheck(regionId, checkId, selectedIds, options = {}) {
      return request(
        `/api/regions/${encodeURIComponent(regionId)}/checks/${encodeURIComponent(checkId)}`,
        "Check submission",
        {
          ...options,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected_ids: selectedIds }),
        },
      );
    },
    selectEntrypoint(nodeId, options = {}) {
      return request("/api/entrypoint", "Home selection", {
        ...options,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: nodeId }),
      });
    },
    loadMode(options = {}) {
      return request("/api/mode", "Mode request", options);
    },
    saveMode(mode, options = {}) {
      return request("/api/mode", "Mode update", {
        ...options,
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
    },
    fetchLlmStatus(options = {}) {
      return request("/api/llm/status", "Model status", options);
    },
    resetProject(options = {}) {
      return request("/api/picker/reset", "Project reset", {
        ...options,
        method: "POST",
        // A body, so the one state-changing endpoint that a cross-site form
        // could once reach is now JSON-only like its siblings.
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true }),
      });
    },
    loadPickerState(options = {}) {
      return request("/api/picker/state", "Picker state", options);
    },
    browsePicker(path, options = {}) {
      const query = path ? `?path=${encodeURIComponent(path)}` : "";
      return request(`/api/picker/browse${query}`, "Folder listing", options);
    },
    loadRecents(options = {}) {
      return request("/api/picker/recents", "Recent projects", options);
    },
    fetchParseProgress(options = {}) {
      return request("/api/picker/progress", "Parse progress", options);
    },
    clearProgress(options = {}) {
      return request("/api/progress", "Progress reset", { ...options, method: "DELETE" });
    },
    async selectProject(path, options = {}) {
      const response = await fetchImplementation("/api/picker/select", {
        ...options,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const payload = await response.json().catch(() => null);
      // 202 means accepted-and-parsing, 200 means already usable. Collapsing
      // them into "ready" is what made the tab look frozen: the session would
      // fetch a graph the server had not built yet.
      if (response.ok) {
        return { state: response.status === 202 ? "parsing" : "ready" };
      }
      const detail = payload?.detail;
      if (detail && typeof detail === "object" && detail.reason === "scale") {
        return { state: "scale", ...detail };
      }
      return {
        state: "error",
        detail:
          typeof detail === "string"
            ? detail
            : `Project selection returned ${response.status}.`,
      };
    },
  });
}

export function createInMemoryLearnerSessionAdapter({
  graph,
  studies = {},
  explanations = {},
  checks = {},
  submissions = {},
  entrypoints = {},
  picker = null,
  llmStatus = null,
  map = null,
  mode,
  modeChosen: initialModeChosen = false,
}) {
  let currentGraph = graph;
  let currentMode = mode ?? "easy";
  let modeChosen = initialModeChosen;
  const currentChecks = new Map(Object.entries(checks));
  const pickerPhase = picker ? { ...picker, selected: false } : null;
  // A scripted queue rather than a fixture map: progress is a *sequence* the
  // poll loop walks, and each entry must be served exactly once so a test can
  // assert how many polls really happened.
  const progressPayloads = [...(picker?.progress ?? [])];
  return Object.freeze({
    async loadGraph(options = {}) {
      throwIfAborted(options.signal);
      return currentGraph;
    },
    async fetchMap(options = {}) {
      throwIfAborted(options.signal);
      if (map === null) throw new Error("No in-memory map fixture.");
      return map;
    },
    async loadStudy(nodeId, options = {}) {
      throwIfAborted(options.signal);
      return requiredFixture(studies, nodeId, "study");
    },
    async loadExplanation(nodeId, mode, options = {}) {
      throwIfAborted(options.signal);
      return requiredFixture(explanations, `${nodeId}:${mode}`, "explanation");
    },
    async loadChecks(regionId, options = {}) {
      throwIfAborted(options.signal);
      if (!currentChecks.has(regionId)) {
        throw new Error(`No in-memory checks for ${regionId}.`);
      }
      return currentChecks.get(regionId);
    },
    async submitCheck(regionId, checkId, _selectedIds, options = {}) {
      throwIfAborted(options.signal);
      const scenario = requiredFixture(
        submissions,
        `${regionId}:${checkId}`,
        "submission",
      );
      if (scenario.graph) currentGraph = scenario.graph;
      if (scenario.checks) currentChecks.set(regionId, scenario.checks);
      return scenario.result;
    },
    async selectEntrypoint(nodeId, options = {}) {
      throwIfAborted(options.signal);
      currentGraph = requiredFixture(entrypoints, nodeId, "entrypoint graph");
      return currentGraph;
    },
    async loadMode(options = {}) {
      throwIfAborted(options.signal);
      return { mode: currentMode, chosen: modeChosen };
    },
    async saveMode(nextMode, options = {}) {
      throwIfAborted(options.signal);
      currentMode = nextMode;
      modeChosen = true;
      return { mode: nextMode, chosen: true };
    },
    async fetchLlmStatus(options = {}) {
      throwIfAborted(options.signal);
      return (
        llmStatus ?? {
          configured_provider: null,
          configured_model: null,
          ollama: {
            running: false,
            installed_models: [],
            recommended: "gemma4:12b",
            fallback: "qwen3:8b",
          },
        }
      );
    },
    async loadPickerState(options = {}) {
      throwIfAborted(options.signal);
      return pickerPhase && !pickerPhase.selected
        ? { state: "unpicked" }
        : { state: "ready" };
    },
    async browsePicker(path, options = {}) {
      throwIfAborted(options.signal);
      return requiredFixture(pickerPhase.browse, path ?? "", "picker listing");
    },
    async loadRecents(options = {}) {
      throwIfAborted(options.signal);
      return { recents: pickerPhase.recents ?? [] };
    },
    async selectProject(path, options = {}) {
      throwIfAborted(options.signal);
      const result = requiredFixture(pickerPhase.selections, path, "picker selection");
      if (result.state === "ready") pickerPhase.selected = true;
      return result;
    },
    async resetProject(options = {}) {
      throwIfAborted(options.signal);
      if (pickerPhase) pickerPhase.selected = false;
      return { state: "unpicked" };
    },
    async fetchParseProgress(options = {}) {
      throwIfAborted(options.signal);
      if (!progressPayloads.length) {
        throw new Error("No in-memory parse progress left to serve.");
      }
      const payload = progressPayloads.shift();
      if (payload.state === "ready" && pickerPhase) pickerPhase.selected = true;
      return payload;
    },
    async clearProgress(options = {}) {
      throwIfAborted(options.signal);
      return { understood_regions: 0 };
    },
  });
}

// A UI preference, not progress: it belongs in localStorage, never in
// ~/.codemble/, which is reserved for what the learner has actually proven.
// A blocked or absent storage API must never stop the learner from continuing,
// so both directions fail soft -- the cost is re-seeing onboarding once.
const COACHMARK_KEY = "codemble.coachmarks.seen";

// Guarded on `document` rather than on localStorage itself: under Node the mere
// property access emits an experimental-feature warning, which would put noise
// in every harness run for a store that only exists in a browser anyway.
function browserStorage() {
  if (typeof document === "undefined") return null;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function readCoachmarksSeen() {
  try {
    return browserStorage()?.getItem(COACHMARK_KEY) === "1";
  } catch {
    return false;
  }
}

function writeCoachmarksSeen() {
  try {
    browserStorage()?.setItem(COACHMARK_KEY, "1");
  } catch {
    // Storage refused; the session field still hides it for this session.
  }
}

// Same class of fact as the coach-mark flag: a view preference, so localStorage
// rather than ~/.codemble/. Reveal state itself is never stored -- it is
// recomputed from what the learner has proven, so it can never drift out of
// step with progress or survive a project whose regions have changed.
const SHOW_ALL_KEY = "codemble.galaxy.showAll";

function readShowAll() {
  try {
    return browserStorage()?.getItem(SHOW_ALL_KEY) === "1";
  } catch {
    return false;
  }
}

function writeShowAll(showAll) {
  try {
    const storage = browserStorage();
    if (showAll) storage?.setItem(SHOW_ALL_KEY, "1");
    else storage?.removeItem(SHOW_ALL_KEY);
  } catch {
    // Storage refused; the session field still carries it for this session.
  }
}

function abortController(controller) {
  if (controller && !controller.signal.aborted) controller.abort();
}

function isAbortError(error) {
  return error instanceof Error && error.name === "AbortError";
}

// True only when an HTTP response actually arrived and said no: the adapter's
// request() stamps `status` on every error it raises from one. A fetch that
// never reached the server rejects with a bare TypeError ("Failed to fetch"),
// which carries no status -- and a deliberate cancel is an AbortError, which
// every caller checks first, so it can never be mistaken for either.
function isServerRefusal(error) {
  return Number.isInteger(error?.status);
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

// The message behind the app-level "did not load" screen. A refusal already
// carries the server's own learner-facing sentence, so it is passed through --
// but an unreachable server produces the browser's words for it ("Failed to
// fetch"), which name nothing the learner can do anything about. The one thing
// that is certainly true, and the one action that fixes it, is said instead.
function appDownMessage(error) {
  return isServerRefusal(error)
    ? errorMessage(error)
    : `Codemble's local server is not responding, so nothing can be loaded from it. It may have stopped — start it again by running codemble in your terminal. (${errorMessage(error)})`;
}

function requiredFixture(fixtures, key, description) {
  if (!Object.hasOwn(fixtures, key)) {
    throw new Error(`No in-memory ${description} for ${key}.`);
  }
  return fixtures[key];
}

function throwIfAborted(signal) {
  if (signal?.aborted) {
    const error = new Error("Request aborted.");
    error.name = "AbortError";
    throw error;
  }
}
