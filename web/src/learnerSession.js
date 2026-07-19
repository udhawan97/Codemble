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
    showChart: false,
    studiedNodeIds: new Set(),
    showChecks: false,
    checkData: null,
    checkError: "",
    entrypointDismissed: false,
    entrypointError: "",
    litRegionId: null,
    languageFocus: "all",
  });
  let lifecycle = 0;
  let graphController = null;
  let studyController = null;
  let checksController = null;
  let submissionController = null;
  let entrypointController = null;
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
    try {
      const graph = await adapter.loadGraph({ signal: controller.signal });
      if (requestLifecycle !== lifecycle || controller.signal.aborted) return snapshot;
      commit({
        status: "ready",
        graph,
        region: defaultRegion(graph),
        error: "",
      });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestLifecycle === lifecycle) {
        commit({ status: "error", error: errorMessage(requestError) });
      }
    }
    return snapshot;
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
      commit({ studyData: null, studyError: "" });
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
      checksController,
      submissionController,
      entrypointController,
    ]) {
      abortController(controller);
    }
    graphController = null;
    studyController = null;
    checksController = null;
    submissionController = null;
    entrypointController = null;
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
  checks = {},
  submissions = {},
  entrypoints = {},
  picker = null,
}) {
  let currentGraph = graph;
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
