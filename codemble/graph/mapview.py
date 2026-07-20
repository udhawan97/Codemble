"""Deterministic 2D map layouts for the learner-facing Map layer.

The galaxy layer owns 3D coordinates; this module owns the flat ones.  Both are
computed here so the renderer stays a pure consumer: React draws these numbers
and decides nothing.  No clock, no RNG, and no set iteration reaches the output.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from codemble.adapters.base import Graph

MAP_SCHEMA_VERSION = 1

_MAP_WIDTH = 960.0
_ROW_HEIGHT = 120.0
_BOX_WIDTH = 160.0
_BOX_HEIGHT = 56.0
_COLUMN_GAP = 24.0
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


def _architecture(graph: Graph) -> dict[str, object]:
    regions = {region.id: region for region in graph.regions}
    region_ids = sorted(regions)
    home = next((region.id for region in graph.regions if region.home), None)
    routes = sorted(graph.region_edges, key=lambda edge: (edge.src, edge.dst))

    successors: dict[str, list[str]] = defaultdict(list)
    for edge in routes:
        successors[edge.src].append(edge.dst)
    cut = _back_edges(([home] if home else []) + region_ids, successors)

    layers: dict[str, int] = {}
    if home is not None:
        layers[home] = 0
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

    partial_regions = {node.region for node in graph.nodes if node.partial}
    boxes: list[dict[str, object]] = []
    for layer_index in sorted(rows):
        members = rows[layer_index]
        span = len(members) * _BOX_WIDTH + (len(members) - 1) * _COLUMN_GAP
        start = (_MAP_WIDTH - span) / 2.0
        for column, region_id in enumerate(members):
            region = regions[region_id]
            boxes.append(
                {
                    "id": region_id,
                    "group": group_of[region_id],
                    "label": region_id,
                    "language": region.language,
                    "layer": layer_index,
                    "column": column,
                    "reachable": region_id in layers,
                    "x": _rounded(start + column * (_BOX_WIDTH + _COLUMN_GAP)),
                    "y": _rounded(layer_index * _ROW_HEIGHT),
                    "width": _BOX_WIDTH,
                    "height": _BOX_HEIGHT,
                    "loc": region.loc,
                    "node_count": region.node_count,
                    "understood": region.understood,
                    "home": region.home,
                    "partial": region_id in partial_regions,
                }
            )

    return {
        "home": home,
        "layer_count": layer_count,
        "width": _MAP_WIDTH,
        "height": _rounded(max(layer_count, 1) * _ROW_HEIGHT),
        "groups": [
            {"id": group_id, "label": group_id, "regions": sorted(grouped[group_id])}
            for group_id in sorted(grouped)
        ],
        "boxes": boxes,
        "edges": [
            {
                "src": edge.src,
                "dst": edge.dst,
                "certain": edge.certain,
                "weight": edge.weight,
                "cycle": (edge.src, edge.dst) in cut,
            }
            for edge in routes
        ],
        "unreachable": unreachable,
    }


def _workflow(graph: Graph) -> dict[str, object]:
    nodes = {node.id: node for node in graph.nodes}
    calls: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    called_by: dict[str, set[str]] = defaultdict(set)
    for edge in sorted(graph.edges, key=lambda item: (item.src, item.dst, item.lineno)):
        if edge.kind != "call" or edge.external:
            continue
        if edge.src not in nodes or edge.dst not in nodes or edge.src == edge.dst:
            continue
        if edge.dst not in {target for target, _ in calls[edge.src]}:
            calls[edge.src].append((edge.dst, edge.certain))
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
        return [(target, certain, "calls") for target, certain in sorted(calls[node_id])]

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
