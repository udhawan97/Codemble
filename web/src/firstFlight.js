export const FIRST_FLIGHT_LIMIT = 6;

/**
 * Home followed by the modules it directly and provably imports.
 *
 * The graph carries raw certain import edges, so this does not use the
 * aggregate region mark: a mark shared by one certain and one possible import
 * is conservatively possible, but the certain edge still earns its stop. The
 * direct stops sort by centrality descending, then id, and the total including
 * Home is capped at six. Same graph, same short flight.
 */
export function firstFlightPlan(graph) {
  if (!graph?.selected_entrypoint) return [];
  const nodeById = new Map((graph.nodes ?? []).map((node) => [node.id, node]));
  const regionById = new Map((graph.regions ?? []).map((region) => [region.id, region]));
  const entrypoint = nodeById.get(graph.selected_entrypoint);
  const home = entrypoint ? regionById.get(entrypoint.region) : null;
  if (!home?.home) return [];

  const directProvenUses = new Map();
  for (const edge of graph.edges ?? []) {
    if (edge.kind !== "import" || edge.external || edge.certain !== true) continue;
    const src = nodeById.get(edge.src)?.region;
    const dst = nodeById.get(edge.dst)?.region;
    if (!src || !dst || src === dst || !regionById.has(src) || !regionById.has(dst)) {
      continue;
    }
    if (!directProvenUses.has(src)) directProvenUses.set(src, new Set());
    directProvenUses.get(src).add(dst);
  }

  // Use the same region-route degree the galaxy-tier hover/readout uses. The
  // order above stays restricted to proven imports; these two counts are
  // context about the system. After landing, the canvas readout may instead
  // describe a selected structure and its call edges -- a different question.
  const uses = new Map();
  const usedBy = new Map();
  for (const edge of graph.region_edges ?? []) {
    if (!regionById.has(edge.src) || !regionById.has(edge.dst) || edge.src === edge.dst) {
      continue;
    }
    if (!uses.has(edge.src)) uses.set(edge.src, new Set());
    if (!usedBy.has(edge.dst)) usedBy.set(edge.dst, new Set());
    uses.get(edge.src).add(edge.dst);
    usedBy.get(edge.dst).add(edge.src);
  }

  const direct = [...(directProvenUses.get(home.id) ?? [])]
    .map((regionId) => regionById.get(regionId))
    .filter(Boolean)
    .sort(
      (left, right) =>
        (right.centrality ?? 0) - (left.centrality ?? 0) ||
        String(left.id).localeCompare(String(right.id)),
    );

  return [home, ...direct].slice(0, FIRST_FLIGHT_LIMIT).map((region) => ({
    id: region.id,
    language: region.language,
    usedBy: usedBy.get(region.id)?.size ?? 0,
    uses: uses.get(region.id)?.size ?? 0,
    home: region.id === home.id,
  }));
}

export function flightCameraDuration(defaultDuration, { active, reducedMotion }) {
  return active && reducedMotion ? 0 : defaultDuration;
}
