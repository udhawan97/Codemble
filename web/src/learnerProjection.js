import {
  LEVELS,
  buildConceptChart,
  defaultRegion,
  languageFocusGraph,
  languageFocusMap,
  moduleIndex,
  projectLanguageOptions,
  revealedRegionIds,
} from "./graphData.js";

const EMPTY_LIST = Object.freeze([]);
const EMPTY_REVEAL = new Set();

export function createLearnerProjection() {
  const focusedGraphs = new WeakMap();
  const focusedMaps = new WeakMap();
  const graphIndexes = new WeakMap();
  const languageOptions = new WeakMap();
  const moduleIndexes = new WeakMap();
  const projectNames = new WeakMap();
  let chartCache = null;
  let studiedCountCache = null;
  let hintCache = null;
  let revealCache = null;

  function derive(state) {
    const graph = state.graph;
    const focusedGraph = graph
      ? focusGraph(graph, state.languageFocus)
      : null;
    const index = focusedGraph ? graphIndex(focusedGraph) : null;
    let level = state.level;
    let region = index?.regionById.get(state.region?.id) ?? null;
    let selectedNode = state.selectedNode;
    if (focusedGraph) {
      if (!region) {
        region = defaultRegion(focusedGraph);
        selectedNode = null;
        level = LEVELS.GALAXY;
      } else if (selectedNode) {
        selectedNode = index.nodeById.get(selectedNode.id) ?? null;
        if (!selectedNode && level === LEVELS.STUDY) level = LEVELS.SYSTEM;
      }
    }
    const studiedNodeIds = state.studiedNodeIds;
    return {
      ...state,
      focusedGraph,
      focusedMapData: focusMap(state.mapData, state.languageFocus),
      entrypointOpen: Boolean(graph) && !state.entrypointDismissed,
      level,
      region,
      selectedNode,
      languageOptions: graph ? optionsFor(graph) : EMPTY_LIST,
      projectName: graph ? nameFor(graph) : "Loading local project",
      chart: focusedGraph
        ? chartFor(focusedGraph, studiedNodeIds)
        : EMPTY_LIST,
      focusedStudiedCount: focusedGraph
        ? studiedCountFor(focusedGraph, studiedNodeIds)
        : 0,
      hint: focusedGraph
        ? hintFor(focusedGraph, state.mode, level, region?.id ?? null, state.layer)
        : null,
      revealedRegionIds: focusedGraph
        ? revealFor(focusedGraph, state.showAll, region?.id ?? null)
        : EMPTY_REVEAL,
      moduleIndex: focusedGraph ? modulesFor(focusedGraph) : EMPTY_LIST,
    };
  }

  function focusGraph(graph, language) {
    let byLanguage = focusedGraphs.get(graph);
    if (!byLanguage) {
      byLanguage = new Map();
      focusedGraphs.set(graph, byLanguage);
    }
    const key = language || "all";
    if (!byLanguage.has(key)) {
      byLanguage.set(key, languageFocusGraph(graph, language));
    }
    return byLanguage.get(key);
  }

  function focusMap(mapData, language) {
    if (!mapData) return mapData;
    let byLanguage = focusedMaps.get(mapData);
    if (!byLanguage) {
      byLanguage = new Map();
      focusedMaps.set(mapData, byLanguage);
    }
    const key = language || "all";
    if (!byLanguage.has(key)) {
      byLanguage.set(key, languageFocusMap(mapData, language));
    }
    return byLanguage.get(key);
  }

  function graphIndex(graph) {
    if (!graphIndexes.has(graph)) {
      graphIndexes.set(graph, {
        nodeById: new Map(graph.nodes.map((node) => [node.id, node])),
        regionById: new Map(graph.regions.map((region) => [region.id, region])),
      });
    }
    return graphIndexes.get(graph);
  }

  function optionsFor(graph) {
    if (!languageOptions.has(graph)) {
      languageOptions.set(graph, projectLanguageOptions(graph));
    }
    return languageOptions.get(graph);
  }

  function modulesFor(graph) {
    if (!moduleIndexes.has(graph)) moduleIndexes.set(graph, moduleIndex(graph));
    return moduleIndexes.get(graph);
  }

  function nameFor(graph) {
    if (!projectNames.has(graph)) {
      projectNames.set(
        graph,
        graph.project_root.split("/").filter(Boolean).at(-1) ?? graph.project_root,
      );
    }
    return projectNames.get(graph);
  }

  function chartFor(graph, studiedNodeIds) {
    if (
      !chartCache ||
      chartCache.graph !== graph ||
      chartCache.studiedNodeIds !== studiedNodeIds
    ) {
      chartCache = {
        graph,
        studiedNodeIds,
        value: buildConceptChart(graph, studiedNodeIds),
      };
    }
    return chartCache.value;
  }

  function studiedCountFor(graph, studiedNodeIds) {
    if (
      !studiedCountCache ||
      studiedCountCache.graph !== graph ||
      studiedCountCache.studiedNodeIds !== studiedNodeIds
    ) {
      studiedCountCache = {
        graph,
        studiedNodeIds,
        value: graph.nodes.filter((node) => studiedNodeIds.has(node.id)).length,
      };
    }
    return studiedCountCache.value;
  }

  function hintFor(graph, mode, level, regionId, layer) {
    if (
      !hintCache ||
      hintCache.graph !== graph ||
      hintCache.mode !== mode ||
      hintCache.level !== level ||
      hintCache.regionId !== regionId ||
      hintCache.layer !== layer
    ) {
      hintCache = {
        graph,
        mode,
        level,
        regionId,
        layer,
        value: nextStudyHint(graph, { mode, level, regionId, layer }),
      };
    }
    return hintCache.value;
  }

  function revealFor(graph, showAll, selectionId) {
    if (
      !revealCache ||
      revealCache.graph !== graph ||
      revealCache.showAll !== showAll ||
      revealCache.selectionId !== selectionId
    ) {
      revealCache = {
        graph,
        showAll,
        selectionId,
        value: revealedRegionIds(graph, { showAll, selectionId }),
      };
    }
    return revealCache.value;
  }

  return Object.freeze({ derive });
}

function nextStudyHint(graph, { mode, level, regionId, layer }) {
  if (mode !== "easy" || level === LEVELS.STUDY) return null;
  const unlit = graph.regions.filter((region) => !region.understood);
  if (!unlit.length) return null;
  const nearest = unlit
    .map((region) => ({
      regionId: region.id,
      hops:
        typeof region.hops_from_home === "number"
          ? region.hops_from_home
          : Infinity,
    }))
    .sort(
      (left, right) =>
        left.hops - right.hops || left.regionId.localeCompare(right.regionId),
    )[0];
  const hint = {
    ...nearest,
    message: `Study ${nearest.regionId} next`,
    reason:
      nearest.hops === 0
        ? "Home is not lit yet."
        : Number.isFinite(nearest.hops)
          ? `${nearest.hops} ${nearest.hops === 1 ? "route" : "routes"} from Home.`
          : "No import route reaches it from Home.",
  };
  if (level !== LEVELS.SYSTEM || regionId !== nearest.regionId) {
    return {
      ...hint,
      action: { type: "OPEN_REGION", regionId: nearest.regionId },
      actionLabel: `Open ${nearest.regionId}`,
    };
  }
  if (layer === "map") {
    return {
      ...hint,
      reason: "Its parser-proven structures are visible in Galaxy.",
      action: { type: "SET_LAYER", layer: "galaxy" },
      actionLabel: "View structures",
    };
  }
  return {
    ...hint,
    reason: "Choose one of its parser-proven structures.",
    action: null,
    actionLabel: null,
  };
}
