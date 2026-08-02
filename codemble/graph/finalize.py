"""Canonical graph finalization shared by every language adapter."""

from __future__ import annotations

from dataclasses import replace

from codemble.adapters.base import ConceptAnnotation, Edge, Graph
from codemble.graph.layout import layout_graph


class GraphFinalizationError(ValueError):
    """Parser evidence cannot be finalized into one honest graph."""


def finalize_graph(graph: Graph, *, entrypoint: str | None = None) -> Graph:
    """Canonicalize parser evidence and return one render-ready graph."""

    edges = tuple(sorted(set(graph.edges), key=_edge_key))
    node_ids = {node.id for node in graph.nodes}
    callers_by_target: dict[str, set[str]] = {}
    for edge in edges:
        if edge.kind == "call" and not edge.external and edge.dst in node_ids:
            callers_by_target.setdefault(edge.dst, set()).add(edge.src)
    nodes = tuple(
        sorted(
            (
                replace(node, centrality=len(callers_by_target.get(node.id, ())))
                for node in graph.nodes
            ),
            key=lambda node: node.id,
        )
    )
    node_by_id = {node.id: node for node in nodes}
    candidates = tuple(
        node.id
        for node in sorted(
            (node for node in nodes if node.entrypoint_rank is not None),
            key=lambda node: (node.entrypoint_rank, node.id),  # type: ignore[arg-type]
        )
    )
    if entrypoint is not None and entrypoint not in candidates:
        choices = ", ".join(candidates) or "none"
        raise GraphFinalizationError(
            f"entrypoint is not parser-ranked: {entrypoint} (candidates: {choices})"
        )
    # The BEST available rank, not rank zero specifically. A web service
    # frequently has no `__main__` guard at all, so its only candidate sat at
    # the app-object rank and Home resolved to nothing -- the learner met the
    # picker holding a single option and was asked a question with one answer.
    # When exactly one candidate is the best available there is nothing to ask;
    # when several tie, that is a genuine decision and the picker still opens.
    ranks = [
        node_by_id[candidate].entrypoint_rank
        for candidate in candidates
        if node_by_id[candidate].entrypoint_rank is not None
    ]
    best = [
        candidate
        for candidate in candidates
        if ranks and node_by_id[candidate].entrypoint_rank == min(ranks)
    ]
    selected_entrypoint = entrypoint or (best[0] if len(best) == 1 else None)
    finalized = replace(
        graph,
        nodes=nodes,
        edges=edges,
        entrypoint_candidates=candidates,
        file_hashes=dict(sorted(graph.file_hashes.items())),
        selected_entrypoint=selected_entrypoint,
        concept_annotations=tuple(
            sorted(set(graph.concept_annotations), key=_annotation_key)
        ),
        regions=(),
        region_edges=(),
        partial_files=tuple(sorted(set(graph.partial_files))),
    )
    return layout_graph(finalized)


def _edge_key(edge: Edge) -> tuple[str, str, str, int, bool, bool]:
    return (
        edge.src,
        edge.dst,
        edge.kind,
        edge.lineno,
        edge.certain,
        edge.external,
    )


def _annotation_key(
    annotation: ConceptAnnotation,
) -> tuple[str, str, int, str, int]:
    return (
        annotation.language,
        annotation.node_id,
        annotation.lineno,
        annotation.concept,
        annotation.end_lineno,
    )


__all__ = ["GraphFinalizationError", "finalize_graph"]
