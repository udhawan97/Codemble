export const LEVELS = Object.freeze({
  GALAXY: "GALAXY",
  SYSTEM: "SYSTEM",
  STUDY: "STUDY",
});

export function languageFocusGraph(graph, language) {
  if (!language || language === "all") return graph;
  const nodes = graph.nodes.filter((node) => node.language === language);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const allNodeIds = new Set(graph.nodes.map((node) => node.id));
  const regionIds = new Set(nodes.map((node) => node.region));
  const files = new Set(nodes.map((node) => node.file));
  return {
    ...graph,
    nodes,
    edges: graph.edges.filter(
      (edge) =>
        nodeIds.has(edge.src) &&
        (nodeIds.has(edge.dst) || edge.external || !allNodeIds.has(edge.dst)),
    ),
    entrypoint_candidates: graph.entrypoint_candidates.filter((candidate) => nodeIds.has(candidate)),
    selected_entrypoint: nodeIds.has(graph.selected_entrypoint) ? graph.selected_entrypoint : null,
    file_hashes: Object.fromEntries(
      Object.entries(graph.file_hashes).filter(([file]) => files.has(file)),
    ),
    concept_annotations: graph.concept_annotations.filter(
      (annotation) => annotation.language === language && nodeIds.has(annotation.node_id),
    ),
    regions: graph.regions.filter((region) => regionIds.has(region.id)),
    region_edges: graph.region_edges.filter(
      (edge) => regionIds.has(edge.src) && regionIds.has(edge.dst),
    ),
    partial_files: graph.partial_files.filter((file) => files.has(file)),
  };
}

export function projectLanguageOptions(graph) {
  const counts = new Map();
  for (const region of graph.regions) {
    counts.set(region.language, (counts.get(region.language) ?? 0) + 1);
  }
  const languages = [...counts]
    .map(([id, count]) => ({ id, label: languageLabel(id), shortLabel: shortLanguageLabel(id), count }))
    .sort((left, right) => left.label.localeCompare(right.label));
  return [
    { id: "all", label: "All languages", shortLabel: "All", count: graph.regions.length },
    ...languages,
  ];
}

export function buildConceptChart(graph, studiedNodeIds) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const concepts = new Map();
  for (const annotation of graph.concept_annotations ?? []) {
    const key = `${annotation.language}:${annotation.concept}`;
    const current = concepts.get(key) ?? {
      language: annotation.language,
      concept: annotation.concept,
      occurrences: 0,
      nodeIds: new Set(),
      studiedNodeIds: new Set(),
      understoodNodeIds: new Set(),
    };
    current.occurrences += 1;
    current.nodeIds.add(annotation.node_id);
    if (studiedNodeIds.has(annotation.node_id)) current.studiedNodeIds.add(annotation.node_id);
    if (nodeById.get(annotation.node_id)?.understood) current.understoodNodeIds.add(annotation.node_id);
    concepts.set(key, current);
  }
  return [...concepts.values()]
    .map((item) => ({
      language: item.language,
      concept: item.concept,
      occurrences: item.occurrences,
      nodes: item.nodeIds.size,
      studied_nodes: item.studiedNodeIds.size,
      understood_nodes: item.understoodNodeIds.size,
    }))
    .sort(
      (left, right) =>
        left.language.localeCompare(right.language) || left.concept.localeCompare(right.concept),
    );
}

export function conceptTitle(concept) {
  const exact = {
    javascript: "JavaScript",
    jsx: "JSX",
    typescript: "TypeScript",
  };
  if (exact[concept]) return exact[concept];
  return concept
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function languageLabel(language) {
  return conceptTitle(language);
}

function shortLanguageLabel(language) {
  if (language === "javascript") return "JS";
  if (language === "typescript") return "TS";
  return languageLabel(language);
}

export function galaxyData(graph, palette) {
  return {
    nodes: graph.regions.map((region) => ({
      ...region,
      kind: "region",
      name: region.id,
      fx: region.x,
      fy: region.y,
      fz: region.z,
      val: sizeFromLoc(region.loc, 5, 24),
      color: region.understood
        ? palette.star
        : graph.nodes.some((node) => node.region === region.id && node.partial)
          ? palette.routePossible
          : brightness(region.centrality, palette),
    })),
    links: graph.region_edges.map((edge) => ({
      ...edge,
      source: edge.src,
      target: edge.dst,
      color: edge.certain ? palette.route : palette.routePossible,
    })),
  };
}

export function systemData(graph, regionId, palette, { selectedId = null } = {}) {
  const members = graph.nodes.filter((node) => node.region === regionId);
  const memberIds = new Set(members.map((node) => node.id));
  return {
    nodes: members.map((node) => ({
      ...node,
      fx: node.system_x,
      fy: node.system_y,
      fz: node.system_z,
      val: sizeFromLoc(node.loc, 2.8, 11),
      color: node.understood
        ? palette.star
        : node.partial
          ? palette.routePossible
          : brightness(node.centrality, palette),
      selected: node.id === selectedId,
    })),
    links: graph.edges
      .filter(
        (edge) =>
          edge.kind === "call" &&
          !edge.external &&
          memberIds.has(edge.src) &&
          memberIds.has(edge.dst),
      )
      .map((edge) => ({
        ...edge,
        source: edge.src,
        target: edge.dst,
        color: edge.certain ? palette.route : palette.routePossible,
      })),
  };
}

export function defaultRegion(graph) {
  return graph.regions.find((region) => region.home) ?? graph.regions[0] ?? null;
}

export function nodeLabel(node) {
  const role = node.kind === "region" ? "star system" : node.kind;
  const uncertainty = node.partial ? " · unchartable · syntax error" : "";
  const home = node.home ? " · Home" : "";
  return `${node.name} · ${role} · ${node.loc} LOC${home}${uncertainty}`;
}

function sizeFromLoc(loc, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, Math.sqrt(Math.max(1, loc)) * 1.15));
}

function brightness(centrality, palette) {
  if (centrality >= 5) return palette.nodeBright;
  if (centrality >= 1) return palette.node;
  return palette.nodeDim;
}
