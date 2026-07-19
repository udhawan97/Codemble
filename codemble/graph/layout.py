"""Deterministic layout metadata for pure render consumers."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import replace

from codemble.adapters.base import Graph, Node, Region, RegionEdge

_GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
_SYSTEM_RING_CAPACITY = 12


def layout_graph(graph: Graph) -> Graph:
    """Return ``graph`` with stable galaxy and system coordinates filled.

    Coordinates depend only on stable identifiers and sorted membership. No
    clock, process hash seed, or random source participates in the result.
    """

    grouped: dict[str, list[Node]] = defaultdict(list)
    for node in graph.nodes:
        grouped[node.region].append(node)

    region_order = sorted(grouped, key=lambda region_id: (_digest(region_id), region_id))
    regions: list[Region] = []
    positioned_nodes: list[Node] = []
    node_by_id = {node.id: node for node in graph.nodes}

    for region_index, region_id in enumerate(region_order):
        members = sorted(
            grouped[region_id],
            key=lambda node: (node.kind != "module", node.id),
        )
        region_angle = region_index * _GOLDEN_ANGLE + _fraction(region_id, "phase") * 0.18
        region_radius = 42.0 + 54.0 * math.sqrt(region_index)
        region_x = _rounded(math.cos(region_angle) * region_radius)
        region_y = _rounded(((_fraction(region_id, "height") * 2.0) - 1.0) * 28.0)
        region_z = _rounded(math.sin(region_angle) * region_radius)

        module_nodes = [node for node in members if node.kind == "module"]
        loc = sum(node.loc for node in module_nodes) or sum(node.loc for node in members)
        regions.append(
            Region(
                id=region_id,
                language=members[0].language,
                loc=loc,
                centrality=sum(node.centrality for node in members),
                node_count=len(members),
                understood=bool(members) and all(node.understood for node in members),
                home=any(node.entrypoint_rank == 0 for node in members),
                x=region_x,
                y=region_y,
                z=region_z,
            )
        )

        for member_index, node in enumerate(members):
            if member_index == 0:
                positioned_nodes.append(
                    replace(node, system_x=0.0, system_y=0.0, system_z=0.0)
                )
                continue
            orbit_index = member_index - 1
            ring = orbit_index // _SYSTEM_RING_CAPACITY
            slot = orbit_index % _SYSTEM_RING_CAPACITY
            ring_members = min(
                _SYSTEM_RING_CAPACITY,
                max(1, len(members) - 1 - ring * _SYSTEM_RING_CAPACITY),
            )
            angle = (2.0 * math.pi * slot / ring_members) + _fraction(node.id, "orbit") * 0.08
            radius = 34.0 + ring * 24.0
            positioned_nodes.append(
                replace(
                    node,
                    system_x=_rounded(math.cos(angle) * radius),
                    system_y=_rounded(((_fraction(node.id, "depth") * 2.0) - 1.0) * 8.0),
                    system_z=_rounded(math.sin(angle) * radius),
                )
            )

    routes: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for edge in graph.edges:
        if edge.kind != "import" or edge.external:
            continue
        src_node = node_by_id.get(edge.src)
        dst_node = node_by_id.get(edge.dst)
        if src_node is None or dst_node is None or src_node.region == dst_node.region:
            continue
        routes[(src_node.region, dst_node.region)].append(edge.certain)

    region_edges = tuple(
        RegionEdge(src=src, dst=dst, weight=len(certainties), certain=all(certainties))
        for (src, dst), certainties in sorted(routes.items())
    )
    return replace(
        graph,
        nodes=tuple(sorted(positioned_nodes, key=lambda node: node.id)),
        regions=tuple(sorted(regions, key=lambda region: region.id)),
        region_edges=region_edges,
    )


def _digest(value: str, salt: str = "") -> bytes:
    return hashlib.sha256(f"{salt}:{value}".encode()).digest()


def _fraction(value: str, salt: str) -> float:
    integer = int.from_bytes(_digest(value, salt)[:8], "big")
    return integer / float((1 << 64) - 1)


def _rounded(value: float) -> float:
    return round(value, 6)


__all__ = ["layout_graph"]
