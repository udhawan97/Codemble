"""Blast radius: what a change here reaches, and what can break it.

Graph-layer truth, computed from parser-proven edges only. It lives here rather
than in the study module for the reason the render-ready rule exists: this is a
fact about the project, not a rendering of one, and the panel that draws it must
stay a pure consumer.

It also means the Expert panel's lead content needs **no API key**. A developer
onboarding onto a codebase asking "what does this control, and what can break
it" is asking a question the parser already answered; making them wait on a
narration provider for it was the wrong shape.

The Correctness Contract clause that shapes the whole module: an approximate
edge is labelled possible, and reach *through* one is possible for its whole
length. A node is reported certain only when some entirely parser-proven route
reaches it.
"""

from __future__ import annotations

from collections import deque

from codemble.adapters.base import Edge, Graph, Node

# How far a change is traced. Three hops is where a reader stops reasoning about
# consequences and starts scrolling: past it the answer is "most of the
# project", which is true and useless. The cap is reported rather than applied
# silently, so a learner is never told a radius is complete when it was cut.
DEFAULT_MAX_DEPTH = 3


def blast_radius(
    graph: Graph, node_id: str, max_depth: int = DEFAULT_MAX_DEPTH
) -> dict[str, object]:
    """Return what this node affects and what it depends on, with certainty.

    ``affects`` walks inbound edges: the structures that would feel a change
    here. ``depends_on`` walks outbound edges: what this needs, and therefore
    what breaking would break it.
    """

    nodes = {node.id: node for node in graph.nodes}
    if node_id not in nodes:
        raise KeyError(node_id)

    inbound: dict[str, list[Edge]] = {}
    outbound: dict[str, list[Edge]] = {}
    for edge in graph.edges:
        # An external edge leaves the project, so there is nothing beyond it to
        # walk and no source file to cite. It is real, and it is reported in the
        # study panel's own connections list -- just not here, where every entry
        # has to be somewhere the learner can actually go.
        if edge.external or edge.dst not in nodes or edge.src not in nodes:
            continue
        inbound.setdefault(edge.dst, []).append(edge)
        outbound.setdefault(edge.src, []).append(edge)

    affects, affects_cut = _walk(node_id, inbound, nodes, max_depth, follow=_source_of)
    depends, depends_cut = _walk(node_id, outbound, nodes, max_depth, follow=_target_of)
    return {
        "node_id": node_id,
        "max_depth": max_depth,
        "affects": affects,
        "depends_on": depends,
        "truncated": affects_cut or depends_cut,
    }


def _source_of(edge: Edge) -> str:
    return edge.src


def _target_of(edge: Edge) -> str:
    return edge.dst


def _walk(
    start: str,
    adjacency: dict[str, list[Edge]],
    nodes: dict[str, Node],
    max_depth: int,
    *,
    follow,
) -> tuple[list[dict[str, object]], bool]:
    """Breadth-first reach, recording the shallowest depth for each node.

    Certainty is computed by a *second*, independent walk restricted to proven
    edges. Tracking it inside one pass is where this goes subtly wrong: the
    shallowest route to a node and its only proven route are frequently not the
    same route, so a single pass has to choose between reporting the true
    distance and reporting the true certainty. Two passes report both.
    """

    depths, truncated = _reach(start, adjacency, max_depth, follow, certain_only=False)
    proven, _ = _reach(start, adjacency, max_depth, follow, certain_only=True)

    entries = [
        {
            "node_id": reached,
            "name": nodes[reached].name,
            "kind": nodes[reached].kind,
            "file": nodes[reached].file,
            "line": nodes[reached].lineno,
            "citation": f"{nodes[reached].file}:{nodes[reached].lineno}",
            "language": nodes[reached].language,
            "depth": depth,
            # True only when an entirely parser-proven route reaches this node.
            # Anything else is reachable *possibly*, and must say so.
            "certain": reached in proven,
        }
        for reached, depth in depths.items()
    ]
    # Sorted, never in traversal order: identical input must produce identical
    # bytes, and "same code -> same answer" is as much a contract here as it is
    # for the layout.
    entries.sort(key=lambda entry: (entry["depth"], not entry["certain"], entry["node_id"]))
    return entries, truncated


def _reach(
    start: str,
    adjacency: dict[str, list[Edge]],
    max_depth: int,
    follow,
    *,
    certain_only: bool,
) -> tuple[dict[str, int], bool]:
    seen = {start: 0}
    queue = deque([(start, 0)])
    truncated = False
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            # Only a real onward edge counts as a cut: a node with nothing
            # beyond it has not been truncated, it has simply ended.
            if adjacency.get(current):
                truncated = True
            continue
        for edge in adjacency.get(current, []):
            if certain_only and not edge.certain:
                continue
            neighbor = follow(edge)
            if neighbor in seen:
                continue
            seen[neighbor] = depth + 1
            queue.append((neighbor, depth + 1))
    seen.pop(start, None)
    return seen, truncated


__all__ = ["DEFAULT_MAX_DEPTH", "blast_radius"]
