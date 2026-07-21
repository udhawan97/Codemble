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

// The Map's frontend language projection, the flat-layer twin of
// languageFocusGraph above. A focus drops every box, row, and edge that
// belongs to another language and leaves the survivors at their
// backend-computed coordinates: a hole where a filtered box stood is honest,
// but nothing may move, resize, or re-layout -- those numbers stay
// backend-owned. Same node.language test the galaxy focus uses, so the two
// layers hide exactly the same modules.
export function languageFocusMap(mapData, language) {
  if (!mapData || !language || language === "all") return mapData;
  const architecture = mapData.architecture;
  const boxes = architecture.boxes.filter((box) => box.language === language);
  const keptBoxIds = new Set(boxes.map((box) => box.id));
  const workflow = mapData.workflow;
  const prefix = `${language}:`;
  return {
    ...mapData,
    architecture: {
      ...architecture,
      boxes,
      // An edge whose endpoint box was dropped is dropped too, never redrawn to
      // a new anchor: an orphaned edge is an honest hole, an invented one lies.
      edges: architecture.edges.filter(
        (edge) => keptBoxIds.has(edge.src) && keptBoxIds.has(edge.dst),
      ),
      // Every region is drawn as a box, so the same kept-set keeps the
      // "no import route from Home" note's count true under the focus.
      unreachable: architecture.unreachable.filter((id) => keptBoxIds.has(id)),
    },
    workflow: {
      ...workflow,
      // Rows carry their node's language; a focused row whose parent row was
      // dropped simply loses its connector (WorkflowTree derives edges from
      // row.parent and returns null when the parent is gone) and stays put.
      nodes: workflow.nodes.filter((row) => row.language === language),
      // Unreached rows are never emitted, so they carry no language field here.
      // Node ids are minted `<language>:<file>:<symbol>` -- the same invariant
      // the galaxy focus keys off -- so the prefix is their honest language test.
      unreachable: workflow.unreachable.filter((id) => id.startsWith(prefix)),
    },
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

// Language gets its own visual channel (nebula tint) so it never competes with
// brightness, which belongs to centrality and understanding. Unknown languages
// return null and render no fog rather than borrowing another language's hue.
export function nebulaTintKey(language) {
  if (language === "python") return "nebPython";
  if (language === "javascript") return "nebJs";
  if (language === "typescript") return "nebTs";
  return null;
}

// How far from Home a region may sit and still be visible on a first run. Two
// routes is the floor that guarantees run one is never an empty sky: Home, what
// Home imports, and what those import. Everything beyond it is earned.
const REVEAL_FLOOR_HOPS = 2;

/**
 * The regions currently drawn as charted sky.
 *
 * Three sources union together: the floor (within REVEAL_FLOOR_HOPS of Home,
 * so a first run is never empty), the earned set (every lit region and its
 * import neighbours, which is what makes understanding uncover the map), and
 * the transient set (the current selection and its neighbours).
 *
 * A region outside the result is NOT removed from the graph -- the renderer
 * draws it as an uncharted marker and it stays clickable. Hiding a module
 * outright would misreport the project's size, which is exactly the kind of
 * wrong a learner cannot detect.
 */
export function revealedRegionIds(
  graph,
  { showAll = false, selectionId = null } = {},
) {
  const everything = () => new Set(graph.regions.map((region) => region.id));
  if (showAll) return everything();
  // No Home means no origin to measure distance from. Revealing everything is
  // the honest fallback: hiding regions by a distance the graph could not
  // compute would be guessing, and reveal must never outrun the parser.
  if (!graph.regions.some((region) => region.home)) return everything();

  const revealed = new Set();
  const seeds = new Set();
  for (const region of graph.regions) {
    if (typeof region.hops_from_home === "number" && region.hops_from_home <= REVEAL_FLOOR_HOPS) {
      revealed.add(region.id);
    }
    // A region you proved you understand can never go dark again.
    if (region.understood) seeds.add(region.id);
  }
  if (selectionId) seeds.add(selectionId);
  for (const id of seeds) revealed.add(id);
  for (const edge of graph.region_edges) {
    // Undirected, matching hops_from_home: a route is a relationship, and the
    // module that imports your lit one is as much its neighbour as the reverse.
    if (seeds.has(edge.src) || seeds.has(edge.dst)) {
      revealed.add(edge.src);
      revealed.add(edge.dst);
    }
  }
  return revealed;
}

// The real filename the parser recorded for a region's members, never a name
// derived from the region id: Python regions are dotted module paths while
// JS/TS regions are file paths, and only `Node.file` is true for both.
export function regionFiles(graph) {
  const files = new Map();
  for (const node of graph.nodes) {
    if (!files.has(node.region)) files.set(node.region, node.file);
  }
  return files;
}

export function basename(file) {
  return file.split("/").filter(Boolean).at(-1) ?? file;
}

/**
 * One flat, searchable row per region, shared by the palette and the sidebar so
 * the two can never disagree about what exists or where it is.
 */
export function moduleIndex(graph) {
  const files = regionFiles(graph);
  return graph.regions
    .map((region) => ({
      id: region.id,
      file: files.get(region.id) ?? region.id,
      label: basename(files.get(region.id) ?? region.id),
      language: region.language,
      community: region.community,
      understood: region.understood,
      home: region.home,
      hops: typeof region.hops_from_home === "number" ? region.hops_from_home : null,
      centrality: region.centrality,
      loc: region.loc,
    }))
    .sort((left, right) => left.label.localeCompare(right.label) || left.id.localeCompare(right.id));
}

/**
 * Name a constellation by the directory its members actually share.
 *
 * The name is the members' own longest shared path prefix, so it is a fact
 * about the project rather than a theme invented for it. Members that share no
 * directory get a count instead of a borrowed label.
 */
export function communityName(rows) {
  if (!rows.length) return "";
  const segments = rows.map((row) => row.file.split("/").slice(0, -1));
  let shared = segments[0];
  for (const candidate of segments.slice(1)) {
    let index = 0;
    while (index < shared.length && index < candidate.length && shared[index] === candidate[index]) {
      index += 1;
    }
    shared = shared.slice(0, index);
    if (!shared.length) break;
  }
  if (shared.length) return `${shared.join("/")}/`;
  return `${rows.length} ${rows.length === 1 ? "module" : "modules"}`;
}

export function groupByCommunity(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.community)) groups.set(row.community, []);
    groups.get(row.community).push(row);
  }
  return [...groups]
    .map(([community, members]) => {
      const name = communityName(members);
      // Basenames collide hard in real projects -- a Python package puts an
      // __init__.py in every directory -- so a list of basenames alone is a
      // list of things the learner cannot tell apart. Each row shows its real
      // path with the group's own shared prefix removed: still parser truth,
      // just without repeating the part the heading already says.
      const prefix = name.endsWith("/") ? name : "";
      return {
        community,
        name,
        members: members
          .map((row) => ({
            ...row,
            display: prefix && row.file.startsWith(prefix)
              ? row.file.slice(prefix.length)
              : row.file,
          }))
          .sort((left, right) => left.display.localeCompare(right.display)),
      };
    })
    // Biggest constellation first, so the sidebar opens on the project's bulk;
    // community id breaks ties so the order never depends on Map insertion.
    .sort(
      (left, right) =>
        right.members.length - left.members.length || left.community - right.community,
    );
}

// Summed over a region's members, so the top step stays where it was.
const REGION_BRIGHT_AT = 5;
// Distinct callers of one structure. See brightness() below.
const NODE_BRIGHT_AT = 2;

export function galaxyData(graph, palette, revealed = null) {
  const isRevealed = (regionId) => revealed === null || revealed.has(regionId);
  const files = regionFiles(graph);
  return {
    nodes: graph.regions.map((region) => {
      const charted = isRevealed(region.id);
      return {
        ...region,
        kind: "region",
        name: region.id,
        // The label is the parser's own filename for the module, shortened to
        // its basename so a 60-character path cannot become a 60-character
        // sprite. Uncharted regions carry none -- a name is the reward for
        // reaching them, and labelling all 169 was the original hairball.
        label: charted ? basename(files.get(region.id) ?? region.id) : "",
        charted,
        fx: region.x,
        fy: region.y,
        fz: region.z,
        val: sizeFromLoc(region.loc, 5, 24),
        color: !charted
          ? palette.nodeDim
          : region.understood
            ? palette.star
            : graph.nodes.some((node) => node.region === region.id && node.partial)
              ? palette.routePossible
              : brightness(region.centrality, palette, REGION_BRIGHT_AT),
        focusDim: false,
      };
    }),
    // An uncharted region contributes no routes. This is what dissolves the
    // hairball: at 169 systems the route mesh outdrew the stars, and dropping
    // the edges of what is not yet charted removes the noise without ever
    // removing a module or misreporting how many there are.
    links: graph.region_edges
      .filter((edge) => isRevealed(edge.src) && isRevealed(edge.dst))
      .map((edge) => ({
        ...edge,
        source: edge.src,
        target: edge.dst,
        color: edge.certain ? palette.route : palette.routePossible,
        focusDim: false,
      })),
  };
}

export function systemData(graph, regionId, palette, { selectedId = null } = {}) {
  const members = graph.nodes.filter((node) => node.region === regionId);
  const memberIds = new Set(members.map((node) => node.id));
  const callEdges = graph.edges.filter(
    (edge) =>
      edge.kind === "call" &&
      !edge.external &&
      memberIds.has(edge.src) &&
      memberIds.has(edge.dst),
  );
  // Presentation of an already-computed edge list, not layout: which nodes the
  // selection touches. Study level fades the rest instead of dimming the whole
  // scene, so the selected node's connections stay readable.
  const connected = new Set(selectedId ? [selectedId] : []);
  if (selectedId) {
    for (const edge of callEdges) {
      if (edge.src === selectedId) connected.add(edge.dst);
      if (edge.dst === selectedId) connected.add(edge.src);
    }
  }
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
          : brightness(node.centrality, palette, NODE_BRIGHT_AT),
      selected: node.id === selectedId,
      focusDim: Boolean(selectedId) && !connected.has(node.id),
    })),
    links: callEdges.map((edge) => ({
      ...edge,
      source: edge.src,
      target: edge.dst,
      color: edge.certain ? palette.route : palette.routePossible,
      focusDim:
        Boolean(selectedId) && edge.src !== selectedId && edge.dst !== selectedId,
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

export function linkLabel(link) {
  const relation =
    link.kind === "import" ? "import" : link.kind === "call" ? "call" : "import route";
  const certainty = link.certain
    ? "certain"
    : relation === "call"
      ? "possible call"
      : "possible import";
  const weight =
    typeof link.weight === "number"
      ? ` · ${link.weight} ${link.weight === 1 ? "import" : "imports"}`
      : "";
  const where = typeof link.lineno === "number" ? ` · line ${link.lineno}` : "";
  return `${link.src} → ${link.dst} · ${relation} · ${certainty}${weight}${where}`;
}

function sizeFromLoc(loc, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, Math.sqrt(Math.max(1, loc)) * 1.15));
}

// Two very different domains share this ramp, so each names its own top step.
// A region's centrality is the SUM over its members (0..86 on this repo); a
// single structure's is its count of DISTINCT callers (0..26, and 96% of nodes
// sit at 0-2). One threshold cannot serve both: at >= 5 only 4% of nodes ever
// reached the bright step, so at system level the legend promised a ramp the
// scene did not draw. Per-node the steps now read exactly as the legend says --
// nothing calls it, one place calls it, several places call it.
function brightness(centrality, palette, brightAt) {
  if (centrality >= brightAt) return palette.nodeBright;
  if (centrality >= 1) return palette.node;
  return palette.nodeDim;
}
