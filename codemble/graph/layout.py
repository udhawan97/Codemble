"""Deterministic layout metadata for pure render consumers."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict, deque
from dataclasses import dataclass, replace

from codemble.adapters.base import (
    Edge,
    Graph,
    Node,
    Region,
    RegionEdge,
    SystemOrbit,
    SystemOrbitKind,
)

_GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
_SYSTEM_RING_CAPACITY = 12
# The number of traditional-Japanese colour families in `web/src/tokens.css`
# (`--cm-com-0..7`). Only the largest communities earn one; see
# `_colour_families`.
_COLOUR_FAMILIES = 8


def layout_graph(graph: Graph) -> Graph:
    """Return ``graph`` with stable galaxy and system coordinates filled.

    Coordinates depend only on stable identifiers and sorted membership. No
    clock, process hash seed, or random source participates in the result.
    """

    grouped: dict[str, list[Node]] = defaultdict(list)
    for node in graph.nodes:
        grouped[node.region].append(node)

    node_by_id = {node.id: node for node in graph.nodes}

    routes: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for edge in graph.edges:
        if edge.kind != "import" or edge.external:
            continue
        src_node = node_by_id.get(edge.src)
        dst_node = node_by_id.get(edge.dst)
        if src_node is None or dst_node is None or src_node.region == dst_node.region:
            continue
        routes[(src_node.region, dst_node.region)].append(edge.certain)

    # ``all``, deliberately, where ``mapview.py``'s ``_workflow`` uses ``any``
    # for a call pair.  The two marks claim different things.  A workflow row
    # asserts only that a relationship exists, so one proven call site settles
    # it and the ambiguous ones beside it change nothing.  A route is a single
    # line standing in for ``weight`` imports, so calling it certain asserts
    # every one of them: one unproven import among them and the whole route
    # drops to possible.  Under-claiming is the only direction that is safe
    # when one mark speaks for many edges.
    region_edges = tuple(
        RegionEdge(src=src, dst=dst, weight=len(certainties), certain=all(certainties))
        for (src, dst), certainties in sorted(routes.items())
    )

    region_order = sorted(grouped, key=lambda region_id: (_digest(region_id), region_id))
    communities = _communities(tuple(grouped), region_edges)
    community_members: dict[int, list[str]] = defaultdict(list)
    for region_id in region_order:
        community_members[communities[region_id]].append(region_id)

    families = _colour_families(community_members)

    region_positions: dict[str, tuple[float, float, float]] = {}
    cumulative_members = 0
    for community in sorted(community_members):
        members = community_members[community]
        community_angle = community * _GOLDEN_ANGLE
        community_radius = 42.0 + 54.0 * math.sqrt(cumulative_members)
        community_x = math.cos(community_angle) * community_radius
        community_z = math.sin(community_angle) * community_radius
        for member_index, region_id in enumerate(members):
            local_angle = (
                member_index * _GOLDEN_ANGLE
                + _fraction(region_id, "phase") * 0.18
            )
            local_radius = 16.0 + 12.0 * math.sqrt(member_index)
            region_positions[region_id] = (
                _rounded(community_x + math.cos(local_angle) * local_radius),
                _rounded(((_fraction(region_id, "height") * 2.0) - 1.0) * 28.0),
                _rounded(community_z + math.sin(local_angle) * local_radius),
            )
        cumulative_members += len(members)

    home_region = next(
        (node.region for node in graph.nodes if node.id == graph.selected_entrypoint),
        None,
    )
    hops = _hops_from_home(tuple(grouped), region_edges, home_region)

    regions: list[Region] = []
    positioned_nodes: list[Node] = []
    for region_id in region_order:
        members = sorted(
            grouped[region_id],
            key=lambda node: (node.kind != "module", node.id),
        )
        region_x, region_y, region_z = region_positions[region_id]
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
                home=any(node.id == graph.selected_entrypoint for node in members),
                x=region_x,
                y=region_y,
                z=region_z,
                community=communities[region_id],
                hops_from_home=hops.get(region_id),
                community_family=families.get(communities[region_id]),
            )
        )

        layers = _call_layers(members, graph.edges)
        orbits: dict[int, list[tuple[Node, _CallLayer]]] = defaultdict(list)
        for node in members:
            layer = layers[node.id]
            orbits[layer.ring].append((node, layer))
        for node, layer in orbits[0]:
            positioned_nodes.append(
                replace(
                    node,
                    system_x=0.0,
                    system_y=0.0,
                    system_z=0.0,
                    system_orbit=SystemOrbit(
                        ring=layer.ring,
                        radius=0.0,
                        call_depth=layer.call_depth,
                        kind=layer.kind,
                    ),
                )
            )

        # A call layer may need several physical circles when it contains more
        # than twelve structures. Allocate each layer as its own radial band:
        # overflow circles stay 12 units apart, and the next semantic layer
        # starts 24 units beyond the last one. The previous fixed formula let a
        # layer-1 overflow circle and the layer-2 circle both land at radius 58,
        # so a visible guide could not truthfully label either one.
        next_radius = 34.0
        for ring in sorted(orbit for orbit in orbits if orbit > 0):
            ring_nodes = orbits[ring]
            for slot_index, (node, layer) in enumerate(ring_nodes):
                sub_ring = slot_index // _SYSTEM_RING_CAPACITY
                slot = slot_index % _SYSTEM_RING_CAPACITY
                ring_members = min(
                    _SYSTEM_RING_CAPACITY,
                    max(1, len(ring_nodes) - sub_ring * _SYSTEM_RING_CAPACITY),
                )
                angle = (
                    2.0 * math.pi * slot / ring_members
                ) + _fraction(node.id, "orbit") * 0.08
                radius = next_radius + sub_ring * 12.0
                positioned_nodes.append(
                    replace(
                        node,
                        system_x=_rounded(math.cos(angle) * radius),
                        system_y=_rounded(((_fraction(node.id, "depth") * 2.0) - 1.0) * 8.0),
                        system_z=_rounded(math.sin(angle) * radius),
                        system_orbit=SystemOrbit(
                            ring=layer.ring,
                            radius=radius,
                            call_depth=layer.call_depth,
                            kind=layer.kind,
                        ),
                    )
                )
            sub_ring_count = math.ceil(len(ring_nodes) / _SYSTEM_RING_CAPACITY)
            next_radius += sub_ring_count * 12.0 + 12.0

    return replace(
        graph,
        nodes=tuple(sorted(positioned_nodes, key=lambda node: node.id)),
        regions=tuple(sorted(regions, key=lambda region: region.id)),
        region_edges=region_edges,
    )


def _communities(
    region_ids: tuple[str, ...], routes: tuple[RegionEdge, ...]
) -> dict[str, int]:
    """Find deterministic import communities with label propagation.

    Label propagation after Raghavan, Albert & Kumara (2007), "Near linear
    time algorithm to detect community structures in large-scale networks";
    constellation idea inspired by graphify. Implemented independently; no
    code copied.
    """

    ordered = sorted(region_ids)
    neighbors: dict[str, set[str]] = {region_id: set() for region_id in ordered}
    for route in sorted(routes, key=lambda edge: (edge.src, edge.dst)):
        if route.src not in neighbors or route.dst not in neighbors or route.src == route.dst:
            continue
        neighbors[route.src].add(route.dst)
        neighbors[route.dst].add(route.src)

    labels = {region_id: index for index, region_id in enumerate(ordered)}
    for _ in range(10):
        next_labels = dict(labels)
        for region_id in ordered:
            if not neighbors[region_id]:
                continue
            frequencies: dict[int, int] = defaultdict(int)
            for neighbor in sorted(neighbors[region_id]):
                frequencies[labels[neighbor]] += 1
            highest = max(frequencies.values())
            next_labels[region_id] = min(
                label for label, count in frequencies.items() if count == highest
            )
        if next_labels == labels:
            break
        labels = next_labels

    dense_labels: dict[int, int] = {}
    communities: dict[str, int] = {}
    for region_id in ordered:
        label = labels[region_id]
        if label not in dense_labels:
            dense_labels[label] = len(dense_labels)
        communities[region_id] = dense_labels[label]
    return communities


def _colour_families(community_members: dict[int, list[str]]) -> dict[int, int]:
    """Give the project's largest communities one colour family each.

    The palette has eight families and a real project has more communities than
    that -- this repository has thirty-seven.  The renderer previously wrapped
    with ``community % 8``, which is deterministic but not truthful: five
    distinct communities landed on family 4, so unrelated parts of the codebase
    wore one hue while the legend promised hue meant "which part of the project
    is this".

    Ranking by size and stopping at eight guarantees a family names at most one
    community.  Communities past the cut get ``None`` and fall back to the
    neutral centrality ramp, which reads as "not one of this project's main
    groups" -- an honest absence rather than a borrowed claim.

    Ties break on community id so the assignment never depends on dict order.
    """

    ranked = sorted(
        community_members,
        key=lambda community: (-len(community_members[community]), community),
    )
    return {community: family for family, community in enumerate(ranked[:_COLOUR_FAMILIES])}


def _hops_from_home(
    region_ids: tuple[str, ...],
    routes: tuple[RegionEdge, ...],
    home: str | None,
) -> dict[str, int]:
    """Return each region's import-route distance from Home.

    Undirected on purpose: an import route is a relationship between two
    modules, and a learner following it from Home arrives just as surely at the
    importer as at the imported.  Direction is still parser truth and is still
    drawn as an arrow -- it just is not what "how far from Home" means.

    Regions absent from the result have no route to Home at all.  The caller
    stores that as ``None`` rather than a sentinel distance, so "unreachable"
    can never be mistaken for "very far".
    """

    if home is None or home not in set(region_ids):
        return {}

    neighbors: dict[str, set[str]] = {region_id: set() for region_id in region_ids}
    for route in routes:
        if route.src not in neighbors or route.dst not in neighbors:
            continue
        neighbors[route.src].add(route.dst)
        neighbors[route.dst].add(route.src)

    hops = {home: 0}
    queue: deque[str] = deque([home])
    while queue:
        current = queue.popleft()
        for neighbor in sorted(neighbors[current]):
            if neighbor not in hops:
                hops[neighbor] = hops[current] + 1
                queue.append(neighbor)
    return hops


@dataclass(frozen=True, slots=True)
class _CallLayer:
    ring: int
    call_depth: int | None
    kind: SystemOrbitKind


def _call_layers(members: list[Node], edges: tuple[Edge, ...]) -> dict[str, _CallLayer]:
    """Return each member's honest semantic layer and fallback placement.

    The entry node is the module node at the origin (ring 0).  Ring 1 is what the
    entry calls directly *plus* every member no sibling calls, because a module
    that makes no module-level call would otherwise strand its whole region in
    the outermost ring. Members unreachable from those roots still take a
    deterministic outer ring, but their ``call_depth`` is ``None`` and their
    kind is ``unreached``: placement keeps them visible without fabricating a
    call path. Only ``certain`` calls count; a possible call is the parser
    admitting it is unsure and must not decide either depth or placement.
    """

    member_ids = {node.id for node in members}
    entry = members[0].id
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.kind != "call" or edge.external or not edge.certain or edge.src == edge.dst:
            continue
        if edge.src in member_ids and edge.dst in member_ids:
            if edge.dst not in outgoing[edge.src]:
                indegree[edge.dst] += 1
            outgoing[edge.src].add(edge.dst)

    layers = {entry: _CallLayer(ring=0, call_depth=0, kind="origin")}
    queue: deque[str] = deque()
    certain_entry_calls = outgoing[entry]
    roots = certain_entry_calls | {
        node.id for node in members if node.id != entry and indegree[node.id] == 0
    }
    for node_id in sorted(roots):
        layers[node_id] = _CallLayer(
            ring=1,
            call_depth=1,
            kind="certain-call" if node_id in certain_entry_calls else "call-root",
        )
        queue.append(node_id)
    while queue:
        current = queue.popleft()
        for target in sorted(outgoing[current]):
            if target not in layers:
                current_depth = layers[current].call_depth
                if current_depth is None:  # pragma: no cover - unreachable layers are not queued
                    continue
                layers[target] = _CallLayer(
                    ring=current_depth + 1,
                    call_depth=current_depth + 1,
                    kind="certain-call",
                )
                queue.append(target)

    stranded = sorted(node.id for node in members if node.id not in layers)
    outermost = max(layer.ring for layer in layers.values()) + 1
    for node_id in stranded:
        layers[node_id] = _CallLayer(
            ring=outermost,
            call_depth=None,
            kind="unreached",
        )
    return layers


def with_entrypoint(graph: Graph, node_id: str) -> Graph:
    """Select one parser-ranked candidate as Home without changing layout."""

    if node_id not in graph.entrypoint_candidates:
        raise ValueError(f"entrypoint is not a parser-ranked candidate: {node_id}")
    node_by_id = {node.id: node for node in graph.nodes}
    selected = node_by_id[node_id]
    # Every distance is measured from Home, so moving Home invalidates all of
    # them. Coordinates and communities are untouched: they depend on the import
    # structure, not on which entrypoint the learner chose, so a Home change
    # must not re-sort the sky or re-dim a region.
    hops = _hops_from_home(
        tuple(region.id for region in graph.regions), graph.region_edges, selected.region
    )
    regions = tuple(
        replace(
            region,
            home=region.id == selected.region,
            hops_from_home=hops.get(region.id),
        )
        for region in graph.regions
    )
    return replace(graph, selected_entrypoint=node_id, regions=regions)


def _digest(value: str, salt: str = "") -> bytes:
    return hashlib.sha256(f"{salt}:{value}".encode()).digest()


def _fraction(value: str, salt: str) -> float:
    integer = int.from_bytes(_digest(value, salt)[:8], "big")
    return integer / float((1 << 64) - 1)


def _rounded(value: float) -> float:
    return round(value, 6)


__all__ = ["layout_graph", "with_entrypoint"]
