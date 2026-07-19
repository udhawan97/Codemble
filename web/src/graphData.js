export const LEVELS = Object.freeze({
  GALAXY: "GALAXY",
  SYSTEM: "SYSTEM",
  STUDY: "STUDY",
});

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
