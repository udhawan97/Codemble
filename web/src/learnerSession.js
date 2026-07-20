import {
  LEVELS,
  buildConceptChart,
  defaultRegion,
  languageFocusGraph,
  projectLanguageOptions,
} from "./graphData.js";

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
  let snapshot = deriveSnapshot({
    status: "idle",
    error: "",
    graph: null,
    level: LEVELS.GALAXY,
    region: null,
    selectedNode: null,
    studyData: null,
    studyError: "",
    explanation: null,
    explanationError: "",
    showChart: false,
    studiedNodeIds: new Set(),
    showChecks: false,
    checkData: null,
    checkError: "",
    entrypointDismissed: false,
    entrypointError: "",
    litRegionId: null,
    languageFocus: "all",
    picker: null,
    mode: "easy",
    // Three states, not two: null means hydration hasn't resolved yet
    // (unknown), false means the backend confirmed nobody has ever chosen,
    // true means chosen (by the learner, or resolved after a mode-fetch
    // failure — see loadProjectGraph). Collapsing null into false was the
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
  let pickerController = null;
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
    let next = deriveSnapshot({ ...previous, ...patch });
    const navigationChanged =
      next.level !== previous.level || next.region?.id !== previous.region?.id;
    if (navigationChanged && !preserveChecks) {
      abortController(checksController);
      abortController(submissionController);
      checksController = null;
      submissionController = null;
      next = deriveSnapshot({
        ...next,
        showChecks: false,
        checkData: null,
        checkError: "",
      });
    }
    snapshot = Object.freeze(next);
    for (const listener of listeners) listener();
  }

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
        commit({ status: "error", error: errorMessage(requestError) });
      }
      return snapshot;
    }
    if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
    if (pickerState.state === "unpicked") {
      return startPicker(controller, requestLifecycle);
    }
    return loadProjectGraph(controller, requestLifecycle);
  }

  async function loadProjectGraph(controller, requestLifecycle) {
    commit({ status: "loading", error: "", picker: null });
    try {
      const graph = await adapter.loadGraph({ signal: controller.signal });
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      commit({ status: "ready", graph, region: defaultRegion(graph), error: "" });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: errorMessage(requestError) });
      }
    }
    // Mode is a per-project preference the backend can only serve once a
    // project is bound, so it hydrates here rather than earlier in start() —
    // and a failure here must never block the galaxy that just loaded above.
    const requestModeLifecycle = modeLifecycle;
    // requestModeLifecycle catches a SET_MODE dispatched while this fetch
    // was in flight: setMode bumps modeLifecycle synchronously, so a
    // mismatch here means the learner already made an explicit choice that
    // must win no matter which of the two requests resolves first.
    const modeRequestIsCurrent = () =>
      requestLifecycle === lifecycle && requestModeLifecycle === modeLifecycle;
    // Resolves the unknown (null) state when the response can't be trusted —
    // a thrown request, or a payload with a mode value the renderer doesn't
    // understand. Leaving it null forever would leave ModeControl rendering
    // nothing for the rest of the session, so it resolves to known-and-
    // chosen rather than known-and-never-chosen: the worse failure is
    // flashing the first-run gate over a *returning* learner, who could then
    // silently overwrite their real stored mode by clicking through it — the
    // exact bug this fix exists to prevent. A genuine first-timer only
    // loses the friendly first-run framing for this one reload and still has
    // the always-available header toggle to pick a mode explicitly.
    function resolveUnknownModeAfterFailure() {
      if (modeRequestIsCurrent() && snapshot.modeChosen === null) {
        commit({ modeChosen: true });
      }
    }
    try {
      const stored = await adapter.loadMode({ signal: controller.signal });
      const validMode = stored?.mode === "easy" || stored?.mode === "expert";
      if (modeRequestIsCurrent()) {
        if (validMode) {
          commit({ mode: stored.mode, modeChosen: stored.chosen === true });
        } else {
          resolveUnknownModeAfterFailure();
        }
      }
    } catch {
      resolveUnknownModeAfterFailure();
    }
    return snapshot;
  }

  async function startPicker(controller, requestLifecycle) {
    try {
      const [recentsPayload, listing] = await Promise.all([
        adapter.loadRecents({ signal: controller.signal }),
        adapter.browsePicker(null, { signal: controller.signal }),
      ]);
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      commit({
        status: "picking",
        picker: {
          ...listing,
          recents: recentsPayload.recents,
          error: "",
          scale: null,
          busy: false,
        },
      });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: errorMessage(requestError) });
      }
    }
    return snapshot;
  }

  async function browsePickerFolder(path) {
    if (snapshot.status !== "picking" || snapshot.picker?.busy) return;
    abortController(pickerController);
    pickerController = new AbortController();
    const controller = pickerController;
    try {
      const listing = await adapter.browsePicker(path, { signal: controller.signal });
      if (!controller.signal.aborted && snapshot.status === "picking") {
        commit({ picker: { ...snapshot.picker, ...listing, error: "" } });
      }
    } catch (requestError) {
      if (
        pickerController === controller &&
        !isAbortError(requestError) &&
        snapshot.status === "picking"
      ) {
        commit({ picker: { ...snapshot.picker, error: errorMessage(requestError) } });
      }
    }
  }

  async function selectProject(path) {
    if (snapshot.status !== "picking" || snapshot.picker?.busy) return undefined;
    abortController(pickerController);
    pickerController = new AbortController();
    const controller = pickerController;
    commit({ picker: { ...snapshot.picker, busy: true, error: "", scale: null } });
    try {
      const result = await adapter.selectProject(path, { signal: controller.signal });
      if (controller.signal.aborted || snapshot.status !== "picking") return result;
      if (result.state === "ready") {
        lifecycle += 1;
        const requestLifecycle = lifecycle;
        abortController(graphController);
        graphController = new AbortController();
        return loadProjectGraph(graphController, requestLifecycle);
      }
      if (result.state === "scale") {
        const listing = await adapter.browsePicker(result.root, {
          signal: controller.signal,
        });
        if (!controller.signal.aborted && snapshot.status === "picking") {
          commit({
            picker: { ...snapshot.picker, ...listing, busy: false, scale: result },
          });
        }
        return result;
      }
      commit({ picker: { ...snapshot.picker, busy: false, error: result.detail } });
      return result;
    } catch (requestError) {
      if (!isAbortError(requestError) && snapshot.status === "picking") {
        commit({ picker: { ...snapshot.picker, busy: false, error: errorMessage(requestError) } });
      }
      return undefined;
    }
  }

  async function dispatch(event) {
    switch (event.type) {
      case "ADVANCE":
        return advance(event.node);
      case "RETREAT":
        retreat();
        return undefined;
      case "SELECT_STUDY_NODE":
        return selectStudyNode(event.nodeId);
      case "SET_LANGUAGE_FOCUS":
        setLanguageFocus(event.language);
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
      case "SELECT_ENTRYPOINT":
        return selectEntrypoint(event.nodeId);
      case "DISMISS_ENTRYPOINT":
        commit({ entrypointDismissed: true });
        return undefined;
      case "BROWSE_PICKER":
        return browsePickerFolder(event.path);
      case "SELECT_PROJECT":
        return selectProject(event.path);
      case "SET_MODE":
        return setMode(event.mode);
      default:
        throw new Error(`Unknown learner-session event: ${event.type}`);
    }
  }

  async function advance(node) {
    if (!snapshot.focusedGraph) return;
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
      commit({ studyData: null, studyError: "", explanation: null, explanationError: "" });
    }
  }

  async function setMode(mode) {
    if (mode !== "easy" && mode !== "expert") return;
    if (snapshot.mode === mode && snapshot.modeChosen) return;
    // Bump first so a mode hydration already in flight (loadProjectGraph)
    // notices this explicit choice and skips its own commit on resolution.
    modeLifecycle += 1;
    commit({ mode, modeChosen: true });
    // Lens, checks, and the Tier 0 summary already carry both voices and
    // switch locally from the existing payload — only narration is generated
    // per mode, so only narration is worth a refetch here.
    if (snapshot.level === LEVELS.STUDY && snapshot.selectedNode) {
      await loadExplanation(snapshot.selectedNode.id);
    }
    try {
      await adapter.saveMode(mode, {});
    } catch {
      // The snapshot already reflects the choice; a failed write is not fatal.
    }
  }

  async function loadStudy(nodeId) {
    cancelStudy();
    studyController = new AbortController();
    const controller = studyController;
    commit({ studyData: null, studyError: "" });
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
      // A separate, deliberately unguarded request: slow or absent narration
      // must never delay the source, lens, and structural summary above.
      await loadExplanation(nodeId);
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
    commit({ explanation: null, explanationError: "" });
    try {
      const explanation = await adapter.loadExplanation(nodeId, snapshot.mode, {
        signal: controller.signal,
      });
      if (
        !controller.signal.aborted &&
        snapshot.level === LEVELS.STUDY &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({ explanation });
      }
    } catch (requestError) {
      if (
        explanationController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError) &&
        snapshot.selectedNode?.id === nodeId
      ) {
        commit({ explanationError: errorMessage(requestError) });
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
        commit(
          { graph, region: graph.regions.find((candidate) => candidate.id === regionId) },
          { preserveChecks: true },
        );
        illuminateRegion(regionId);
      }
    }
    return result;
  }

  async function selectEntrypoint(nodeId) {
    abortController(entrypointController);
    entrypointController = new AbortController();
    const controller = entrypointController;
    commit({ entrypointError: "" });
    try {
      const graph = await adapter.selectEntrypoint(nodeId, {
        signal: controller.signal,
      });
      if (!controller.signal.aborted) {
        commit({ graph, region: defaultRegion(graph), entrypointError: "" });
      }
      return graph;
    } catch (requestError) {
      if (
        entrypointController === controller &&
        !controller.signal.aborted &&
        !isAbortError(requestError)
      ) {
        commit({ entrypointError: errorMessage(requestError) });
      }
      return undefined;
    }
  }

  function illuminateRegion(regionId) {
    if (illuminationTimer !== null) clock.clearTimeout(illuminationTimer);
    commit({ litRegionId: regionId });
    illuminationTimer = clock.setTimeout(() => {
      illuminationTimer = null;
      if (snapshot.litRegionId === regionId) commit({ litRegionId: null });
    }, 520);
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
      pickerController,
    ]) {
      abortController(controller);
    }
    graphController = null;
    studyController = null;
    explanationController = null;
    checksController = null;
    submissionController = null;
    entrypointController = null;
    pickerController = null;
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
    if (!response.ok) throw new Error(`${label} returned ${response.status}.`);
    return response.json();
  }

  return Object.freeze({
    loadGraph(options = {}) {
      return request("/api/graph", "Graph request", options);
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
    async selectProject(path, options = {}) {
      const response = await fetchImplementation("/api/picker/select", {
        ...options,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const payload = await response.json().catch(() => null);
      if (response.ok) return { state: "ready" };
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
  mode,
  modeChosen: initialModeChosen = false,
}) {
  let currentGraph = graph;
  let currentMode = mode ?? "easy";
  let modeChosen = initialModeChosen;
  const currentChecks = new Map(Object.entries(checks));
  const pickerPhase = picker ? { ...picker, selected: false } : null;
  return Object.freeze({
    async loadGraph(options = {}) {
      throwIfAborted(options.signal);
      return currentGraph;
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
  });
}

function deriveSnapshot(state) {
  const graph = state.graph;
  const focusedGraph = graph
    ? languageFocusGraph(graph, state.languageFocus)
    : null;
  let level = state.level;
  let region = state.region;
  let selectedNode = state.selectedNode;
  if (focusedGraph) {
    region = focusedGraph.regions.find((candidate) => candidate.id === region?.id) ?? null;
    if (!region) {
      region = defaultRegion(focusedGraph);
      selectedNode = null;
      level = LEVELS.GALAXY;
    } else if (selectedNode) {
      selectedNode =
        focusedGraph.nodes.find((candidate) => candidate.id === selectedNode.id) ?? null;
      if (!selectedNode && level === LEVELS.STUDY) level = LEVELS.SYSTEM;
    }
  }
  const studiedNodeIds = state.studiedNodeIds;
  return {
    ...state,
    focusedGraph,
    level,
    region,
    selectedNode,
    languageOptions: graph ? projectLanguageOptions(graph) : [],
    projectName: graph
      ? graph.project_root.split("/").filter(Boolean).at(-1) ?? graph.project_root
      : "Loading local project",
    chart: focusedGraph ? buildConceptChart(focusedGraph, studiedNodeIds) : [],
    focusedStudiedCount: focusedGraph
      ? focusedGraph.nodes.filter((node) => studiedNodeIds.has(node.id)).length
      : 0,
  };
}

function abortController(controller) {
  if (controller && !controller.signal.aborted) controller.abort();
}

function isAbortError(error) {
  return error instanceof Error && error.name === "AbortError";
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
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
