import {
  buildConceptChart,
  languageFocusGraph,
  moduleIndex,
  projectLanguageOptions,
  revealedRegionIds,
} from "../src/graphData.js";
import { createLearnerProjection } from "../src/learnerProjection.js";

const count = 1000;
const graph = syntheticGraph(count);
const studiedNodeIds = new Set(
  graph.nodes.filter((_, index) => index % 5 === 0).map((node) => node.id),
);
const state = {
  graph,
  mapData: null,
  languageFocus: "python",
  level: "GALAXY",
  region: graph.regions[0],
  selectedNode: null,
  studiedNodeIds,
  entrypointDismissed: false,
  showAll: false,
  mode: "easy",
  hoverNodeId: null,
};
const iterations = 1000;

const legacy = measure(() => {
  const focused = languageFocusGraph(graph, "python");
  return (
    projectLanguageOptions(graph).length +
    buildConceptChart(focused, studiedNodeIds).length +
    revealedRegionIds(focused, { selectionId: "r0" }).size +
    moduleIndex(focused).length
  );
}, iterations);

const projection = createLearnerProjection();
projection.derive(state);
let hover = 0;
const indexed = measure(() => {
  hover += 1;
  const snapshot = projection.derive({ ...state, hoverNodeId: `n${hover % count}` });
  return (
    snapshot.languageOptions.length +
    snapshot.chart.length +
    snapshot.revealedRegionIds.size +
    snapshot.moduleIndex.length
  );
}, iterations);

console.log(
  JSON.stringify({
    nodes: count,
    iterations,
    legacy_total_ms: rounded(legacy.elapsed),
    legacy_per_commit_ms: rounded(legacy.elapsed / iterations),
    indexed_total_ms: rounded(indexed.elapsed),
    indexed_per_commit_ms: rounded(indexed.elapsed / iterations),
    speedup: rounded(legacy.elapsed / indexed.elapsed),
    checksum: legacy.checksum + indexed.checksum,
  }),
);

function measure(work, repeats) {
  let checksum = 0;
  const started = performance.now();
  for (let index = 0; index < repeats; index += 1) checksum += work();
  return { elapsed: performance.now() - started, checksum };
}

function rounded(value) {
  return Number(value.toFixed(3));
}

function syntheticGraph(size) {
  const nodes = Array.from({ length: size }, (_, index) => ({
    id: `n${index}`,
    region: `r${index}`,
    file: `src/r${index}.py`,
    language: index % 2 ? "typescript" : "python",
    understood: index % 7 === 0,
  }));
  return {
    project_root: "/tmp/benchmark",
    nodes,
    edges: [],
    entrypoint_candidates: [],
    selected_entrypoint: null,
    file_hashes: Object.fromEntries(nodes.map((node) => [node.file, "hash"])),
    concept_annotations: nodes.map((node, index) => ({
      node_id: node.id,
      language: node.language,
      concept: `concept-${index % 30}`,
    })),
    regions: nodes.map((node, index) => ({
      id: node.region,
      language: node.language,
      home: index === 0,
      understood: node.understood,
      hops_from_home: index,
      community: index % 20,
      centrality: index % 9,
      loc: 10,
    })),
    region_edges: Array.from({ length: size - 1 }, (_, index) => ({
      src: `r${index}`,
      dst: `r${index + 1}`,
    })),
    partial_files: [],
  };
}
