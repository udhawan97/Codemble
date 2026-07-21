"""Deterministic 2D map layouts for the learner-facing Map layer.

The galaxy layer owns 3D coordinates; this module owns the flat ones.  Both are
computed here so the renderer stays a pure consumer: React draws these numbers
and decides nothing.  No clock, no RNG, and no set iteration reaches the output.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from codemble.adapters.base import Graph, RegionEdge

MAP_SCHEMA_VERSION = 3

_MAP_WIDTH = 960.0
_ROW_HEIGHT = 120.0
_BOX_WIDTH = 160.0
_BOX_HEIGHT = 56.0
_COLUMN_GAP = 24.0
# How many fixed-width boxes fit the canvas.  A layer wider than this wraps
# rather than overflowing: the SVG root clips everything outside the viewBox,
# and the viewBox is built from _MAP_WIDTH.
_MAX_COLUMNS = int((_MAP_WIDTH + _COLUMN_GAP) // (_BOX_WIDTH + _COLUMN_GAP))
_TREE_INDENT = 28.0
_TREE_ROW = 34.0
_TREE_LABEL_WIDTH = 320.0


def build_map(graph: Graph) -> dict[str, object]:
    """Return both 2D map payloads.  Same graph in, same bytes out."""

    return {
        "schema_version": MAP_SCHEMA_VERSION,
        "architecture": _architecture(graph),
        "workflow": _workflow(graph),
    }


def _short_label(file: str) -> str:
    """Name a box by the tail of its real path, not by its dotted region id.

    A box is a fixed width, so its text is always truncated on a real project;
    what matters is that the surviving end is the part that distinguishes it.
    ``codemble.server.app`` and ``codemble.server.runtime`` both truncated to
    ``codemble.server…`` -- identical glyphs for different modules, which is
    worse than no label at all.  The last two path segments fit the box and
    stay distinct, including for the packages that all carry an ``__init__.py``.
    The full identifier is still carried in ``label`` for title and aria.
    """

    parts = PurePosixPath(file).parts
    return "/".join(parts[-2:]) if len(parts) > 1 else (parts[-1] if parts else file)


def _region_files(graph: Graph) -> dict[str, str]:
    """The first file each region's members came from, in node id order."""

    files: dict[str, str] = {}
    for node in sorted(graph.nodes, key=lambda item: item.id):
        files.setdefault(node.region, node.file)
    return files


def _architecture(graph: Graph) -> dict[str, object]:
    regions = {region.id: region for region in graph.regions}
    region_files = _region_files(graph)
    region_ids = sorted(regions)
    home = next((region.id for region in graph.regions if region.home), None)
    routes = sorted(graph.region_edges, key=lambda edge: (edge.src, edge.dst))

    successors: dict[str, list[str]] = defaultdict(list)
    for edge in routes:
        successors[edge.src].append(edge.dst)
    cut = _back_edges(([home] if home else []) + region_ids, successors)

    # With a Home, layers are import depth from Home, and whatever Home cannot
    # reach is reported as unreachable rather than placed by guesswork.
    #
    # Without a Home there is no root to measure from.  Seeding nothing put
    # every region in one row, which is not a diagram: this project's 80
    # modules became a single unreadable line.  So layer from the import DAG's
    # own sources instead -- the modules nothing else in the project imports.
    # That root set is parser evidence exactly like Home is, invents no
    # relationship, and always exists for a non-empty project, because cutting
    # the back edges above leaves a DAG and every DAG has a source.
    if home is not None:
        roots = [home]
    else:
        imported = {edge.dst for edge in routes if (edge.src, edge.dst) not in cut}
        roots = [region_id for region_id in region_ids if region_id not in imported]

    layers: dict[str, int] = dict.fromkeys(roots, 0)
    for _ in range(len(region_ids)):
        changed = False
        for edge in routes:
            if (edge.src, edge.dst) in cut or edge.src not in layers:
                continue
            if layers.get(edge.dst, -1) < layers[edge.src] + 1:
                layers[edge.dst] = layers[edge.src] + 1
                changed = True
        if not changed:
            break

    unreachable = [region_id for region_id in region_ids if region_id not in layers]
    outer_layer = (max(layers.values()) + 1) if layers else 0
    layer_of = {region_id: layers.get(region_id, outer_layer) for region_id in region_ids}
    layer_count = (max(layer_of.values()) + 1) if region_ids else 0

    module_file = {node.region: node.file for node in graph.nodes if node.kind == "module"}
    group_of = {
        region_id: _directory(module_file.get(region_id, region_id))
        for region_id in region_ids
    }
    grouped: dict[str, list[str]] = defaultdict(list)
    for region_id in region_ids:
        grouped[group_of[region_id]].append(region_id)

    rows: dict[int, list[str]] = defaultdict(list)
    for region_id in sorted(region_ids, key=lambda item: (group_of[item], item)):
        rows[layer_of[region_id]].append(region_id)
    rows = _barycenter_order(rows, routes, layer_of, cut)

    partial_regions = {node.region for node in graph.nodes if node.partial}
    boxes: list[dict[str, object]] = []
    visual_row = 0
    for layer_index in sorted(rows):
        members = rows[layer_index]
        # A layer wider than the canvas wraps onto further rows.  Boxes are a
        # fixed width and the SVG clips outside the viewBox, so an unwrapped
        # layer did not merely look cramped -- its overflow was invisible and
        # unscrollable, which is the one thing the map must never do to parser
        # evidence.  "layer" below stays the true import depth; only the row
        # the box is drawn on wraps.
        for offset in range(0, len(members), _MAX_COLUMNS):
            chunk = members[offset : offset + _MAX_COLUMNS]
            span = len(chunk) * _BOX_WIDTH + (len(chunk) - 1) * _COLUMN_GAP
            start = (_MAP_WIDTH - span) / 2.0
            for column, region_id in enumerate(chunk):
                region = regions[region_id]
                boxes.append(
                    {
                        "id": region_id,
                        "group": group_of[region_id],
                        "label": region_id,
                        "short_label": _short_label(region_files.get(region_id, region_id)),
                        "language": region.language,
                        "layer": layer_index,
                        "column": column,
                        "reachable": region_id in layers,
                        "x": _rounded(start + column * (_BOX_WIDTH + _COLUMN_GAP)),
                        "y": _rounded(visual_row * _ROW_HEIGHT),
                        "width": _BOX_WIDTH,
                        "height": _BOX_HEIGHT,
                        "loc": region.loc,
                        "node_count": region.node_count,
                        "understood": region.understood,
                        "home": region.home,
                        "partial": region_id in partial_regions,
                    }
                )
            visual_row += 1

    edge_payloads = _routed_edges(routes, boxes, layer_of, cut, _MAP_WIDTH)

    return {
        "home": home,
        "layer_count": layer_count,
        "width": _MAP_WIDTH,
        # Wrapped rows, not layers: the canvas has to be tall enough for every
        # row actually drawn, or the wrap would clip exactly what it fixed.
        "height": _rounded(max(visual_row, 1) * _ROW_HEIGHT),
        "groups": [
            {"id": group_id, "label": group_id, "regions": sorted(grouped[group_id])}
            for group_id in sorted(grouped)
        ],
        "boxes": boxes,
        "edges": edge_payloads,
        "unreachable": unreachable,
    }


def _barycenter_order(
    rows: dict[int, list[str]],
    routes: list[RegionEdge],
    layer_of: dict[str, int],
    cut: set[tuple[str, str]],
) -> dict[int, list[str]]:
    """Minimize crossings with four deterministic adjacent-layer sweeps.

    Barycenter crossing minimization after Sugiyama, Tagawa & Toda (1981);
    approach popularized by dagre and Eclipse ELK. Implemented independently;
    no code copied.
    """

    ordered = {layer: list(members) for layer, members in rows.items()}
    predecessors: dict[str, list[str]] = defaultdict(list)
    successors: dict[str, list[str]] = defaultdict(list)
    for edge in routes:
        if (edge.src, edge.dst) in cut:
            continue
        if layer_of.get(edge.dst) != layer_of.get(edge.src, -1) + 1:
            continue
        predecessors[edge.dst].append(edge.src)
        successors[edge.src].append(edge.dst)

    layer_ids = sorted(ordered)
    for sweep in range(4):
        downward = sweep % 2 == 0
        visited_layers = layer_ids[1:] if downward else list(reversed(layer_ids[:-1]))
        for layer in visited_layers:
            reference_layer = layer - 1 if downward else layer + 1
            reference = {
                region_id: index
                for index, region_id in enumerate(ordered.get(reference_layer, []))
            }
            neighbors = predecessors if downward else successors
            current = {region_id: index for index, region_id in enumerate(ordered[layer])}

            def position(region_id: str) -> tuple[float, str]:
                adjacent = [
                    reference[neighbor]
                    for neighbor in sorted(neighbors.get(region_id, []))
                    if neighbor in reference
                ]
                # An unconnected box keeps its seeded relative position instead
                # of being pulled to an arbitrary edge of the layer.
                barycenter = (
                    sum(adjacent) / len(adjacent) if adjacent else float(current[region_id])
                )
                return (barycenter, region_id)

            ordered[layer] = sorted(ordered[layer], key=position)
    return ordered


def _routed_edges(
    routes: list[RegionEdge],
    boxes: list[dict[str, object]],
    layer_of: dict[str, int],
    cut: set[tuple[str, str]],
    width: float,
) -> list[dict[str, object]]:
    """Assign deterministic side ports and orthogonal waypoints to every route.

    Orthogonal elbow routing with side anchors after tt-a1i/archify's renderer
    (MIT). Implemented independently in Python; no code copied.
    """

    box_by_id = {str(box["id"]): box for box in boxes}
    outgoing: dict[str, list[tuple[int, RegionEdge]]] = defaultdict(list)
    incoming: dict[str, list[tuple[int, RegionEdge]]] = defaultdict(list)
    for index, edge in enumerate(routes):
        if edge.src not in box_by_id or edge.dst not in box_by_id:
            continue
        outgoing[edge.src].append((index, edge))
        incoming[edge.dst].append((index, edge))

    start_ports: dict[int, tuple[float, float]] = {}
    end_ports: dict[int, tuple[float, float]] = {}
    for region_id in sorted(outgoing):
        ordered = sorted(
            outgoing[region_id],
            key=lambda item: (
                layer_of[item[1].dst],
                float(box_by_id[item[1].dst]["x"]),
                item[1].dst,
                item[0],
            ),
        )
        box = box_by_id[region_id]
        for port_index, (edge_index, _) in enumerate(ordered):
            start_ports[edge_index] = (
                _port_x(box, port_index, len(ordered)),
                _rounded(float(box["y"]) + float(box["height"])),
            )

    for region_id in sorted(incoming):
        ordered = sorted(
            incoming[region_id],
            key=lambda item: (
                layer_of[item[1].src],
                float(box_by_id[item[1].src]["x"]),
                item[1].src,
                item[0],
            ),
        )
        box = box_by_id[region_id]
        for port_index, (edge_index, _) in enumerate(ordered):
            end_ports[edge_index] = (
                _port_x(box, port_index, len(ordered)),
                _rounded(float(box["y"])),
            )

    payloads: list[dict[str, object]] = []
    for index, edge in enumerate(routes):
        src_box = box_by_id.get(edge.src)
        dst_box = box_by_id.get(edge.dst)
        if src_box is None or dst_box is None:
            continue
        cycle = (edge.src, edge.dst) in cut
        points = _route_points(
            start_ports[index],
            end_ports[index],
            src_box,
            dst_box,
            width,
            cycle=cycle,
        )
        payloads.append(
            {
                "src": edge.src,
                "dst": edge.dst,
                "certain": edge.certain,
                "weight": edge.weight,
                "cycle": cycle,
                "points": [[_rounded(x), _rounded(y)] for x, y in points],
            }
        )
    return payloads


def _port_x(box: dict[str, object], index: int, count: int) -> float:
    return _rounded(
        float(box["x"]) + float(box["width"]) * (index + 1) / (count + 1)
    )


def _route_points(
    start: tuple[float, float],
    end: tuple[float, float],
    src_box: dict[str, object],
    dst_box: dict[str, object],
    width: float,
    *,
    cycle: bool,
) -> list[tuple[float, float]]:
    src_row = int(round(float(src_box["y"]) / _ROW_HEIGHT))
    dst_row = int(round(float(dst_box["y"]) / _ROW_HEIGHT))
    if cycle or dst_row <= src_row or dst_row > src_row + 1:
        left_distance = start[0]
        right_distance = width - start[0]
        flank = -24.0 if left_distance <= right_distance else width + 24.0
        return [start, (flank, start[1]), (flank, end[1]), end]

    midpoint = _rounded((start[1] + end[1]) / 2.0)
    return [start, (start[0], midpoint), (end[0], midpoint), end]


def _workflow(graph: Graph) -> dict[str, object]:
    nodes = {node.id: node for node in graph.nodes}
    calls: dict[str, dict[str, bool]] = defaultdict(dict)
    called_by: dict[str, set[str]] = defaultdict(set)
    for edge in sorted(graph.edges, key=lambda item: (item.src, item.dst, item.lineno)):
        if edge.kind != "call" or edge.external:
            continue
        if edge.src not in nodes or edge.dst not in nodes or edge.src == edge.dst:
            continue
        # A pair can carry several call edges of differing certainty (e.g. one
        # proven call site plus one ambiguous one); the proven edge must win so
        # dedup never under-reports a pair's certainty.
        calls[edge.src][edge.dst] = calls[edge.src].get(edge.dst, False) or edge.certain
        # Only a certain call claims a same-region member for nested "calls"
        # placement -- a "possible" call must never suppress a member's
        # top-level "defines" row, mirroring layout.py's _call_depths, which
        # excludes certain=False edges from deciding orbit placement.
        if edge.certain:
            called_by[edge.dst].add(edge.src)

    members: dict[str, list[str]] = defaultdict(list)
    for node in graph.nodes:
        if node.kind != "module":
            members[node.region].append(node.id)

    def children(node_id: str) -> list[tuple[str, bool, str]]:
        node = nodes[node_id]
        if node.kind == "module":
            # Containment is parser truth (Node.region); it is never relabelled
            # a call, because the parser observed no call from module to member.
            siblings = set(members[node.region])
            return [
                (member, True, "defines")
                for member in sorted(members[node.region])
                if not (called_by[member] & siblings)
            ]
        return [(target, certain, "calls") for target, certain in sorted(calls[node_id].items())]

    rows: list[dict[str, object]] = []
    emitted: set[str] = set()

    def emit(
        node_id: str,
        depth: int,
        parent: str | None,
        certain: bool,
        relation: str,
        cut: str | None,
    ) -> None:
        node = nodes[node_id]
        order = len(rows)
        rows.append(
            {
                "id": node_id,
                "label": node.name,
                "parent": parent,
                "relation": relation,
                "certain": certain,
                "cut": cut,
                "depth": depth,
                "order": order,
                "x": _rounded(depth * _TREE_INDENT),
                "y": _rounded(order * _TREE_ROW),
                "region": node.region,
                "language": node.language,
                "file": node.file,
                "lineno": node.lineno,
                "understood": node.understood,
                "partial": node.partial,
            }
        )
        emitted.add(node_id)

    # Iterative (explicit stack), mirroring _back_edges below, so a deep,
    # unbranching call/defines chain cannot exhaust the interpreter stack.
    def walk(root: str) -> None:
        emit(root, 0, None, True, "root", None)
        # Each frame is (node_id, depth, ancestors, pending children left to
        # visit, reversed so pop() yields them in original order) -- the same
        # per-frame "resume list" _back_edges uses.
        stack = [(root, 0, frozenset({root}), list(reversed(children(root))))]
        while stack:
            node_id, depth, ancestors, pending = stack[-1]
            if not pending:
                stack.pop()
                continue
            target, target_certain, target_relation = pending.pop()
            if target in ancestors:
                emit(target, depth + 1, node_id, target_certain, target_relation, "cycle")
            elif target in emitted:
                emit(target, depth + 1, node_id, target_certain, target_relation, "repeat")
            else:
                emit(target, depth + 1, node_id, target_certain, target_relation, None)
                stack.append(
                    (target, depth + 1, ancestors | {target}, list(reversed(children(target))))
                )

    root = graph.selected_entrypoint if graph.selected_entrypoint in nodes else None
    if root is not None:
        walk(root)

    depth_count = max((int(row["depth"]) for row in rows), default=-1) + 1
    return {
        "root": root,
        "depth_count": depth_count,
        "width": _rounded(max(depth_count, 1) * _TREE_INDENT + _TREE_LABEL_WIDTH),
        "height": _rounded(max(len(rows), 1) * _TREE_ROW),
        "nodes": rows,
        "unreachable": sorted(node_id for node_id in nodes if node_id not in emitted),
    }


def _back_edges(roots: list[str], successors: dict[str, list[str]]) -> set[tuple[str, str]]:
    """Return the routes that close an import cycle, found in one sorted DFS.

    Iterative so a deep import chain cannot exhaust the interpreter stack.
    """

    cut: set[tuple[str, str]] = set()
    state: dict[str, int] = {}

    def visit(start: str) -> None:
        state[start] = 1
        stack = [(start, list(reversed(successors.get(start, []))))]
        while stack:
            node, pending = stack[-1]
            if not pending:
                state[node] = 2
                stack.pop()
                continue
            child = pending.pop()
            if state.get(child) == 1:
                cut.add((node, child))
            elif child not in state:
                state[child] = 1
                stack.append((child, list(reversed(successors.get(child, [])))))

    for root in roots:
        if root not in state:
            visit(root)
    return cut


def _directory(file: str) -> str:
    parent = str(PurePosixPath(file).parent)
    return "." if parent in {"", "."} else parent


def _rounded(value: float) -> float:
    return round(value, 6)


__all__ = ["MAP_SCHEMA_VERSION", "build_map"]
