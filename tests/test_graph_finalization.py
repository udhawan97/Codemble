"""Language-neutral graph finalization contracts."""

from __future__ import annotations

import pytest

from codemble.adapters.base import ConceptAnnotation, Edge, Graph, Node
from codemble.graph import GraphFinalizationError, finalize_graph


def _node(
    node_id: str,
    *,
    region: str,
    rank: int | None = None,
) -> Node:
    return Node(
        id=node_id,
        kind="module" if node_id == region else "function",
        name=node_id.rsplit(".", 1)[-1],
        language="python",
        file=f"{region}.py",
        lineno=1,
        end_lineno=3,
        loc=3,
        region=region,
        entrypoint_rank=rank,
    )


def test_finalization_owns_canonical_graph_truth_and_layout() -> None:
    home = _node("app", region="app", rank=0)
    caller = _node("app.run", region="app")
    library = _node("lib", region="lib")
    target = _node("lib.work", region="lib")
    call = Edge("app.run", "lib.work", "call", True, 2)
    route = Edge("app", "lib", "import", True, 1)
    annotation = ConceptAnnotation(
        node_id="app.run",
        language="python",
        concept="async-await",
        lineno=2,
        end_lineno=2,
        snippet="await work()",
    )
    draft = Graph(
        nodes=(target, library, caller, home),
        edges=(call, route, call),
        entrypoint_candidates=("stale",),
        project_root="/project",
        file_hashes={"lib.py": "b", "app.py": "a"},
        selected_entrypoint="stale",
        concept_annotations=(annotation, annotation),
        partial_files=("broken.py", "broken.py"),
    )

    graph = finalize_graph(draft)

    assert [node.id for node in graph.nodes] == ["app", "app.run", "lib", "lib.work"]
    assert graph.edges == (route, call)
    assert next(node for node in graph.nodes if node.id == "lib.work").centrality == 1
    assert graph.entrypoint_candidates == ("app",)
    assert graph.selected_entrypoint == "app"
    assert graph.concept_annotations == (annotation,)
    assert graph.partial_files == ("broken.py",)
    assert next(region for region in graph.regions if region.id == "app").home is True
    assert [(edge.src, edge.dst, edge.weight) for edge in graph.region_edges] == [
        ("app", "lib", 1)
    ]


def test_finalization_rejects_a_home_without_parser_evidence() -> None:
    draft = Graph(
        nodes=(_node("app", region="app", rank=0),),
        edges=(),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"app.py": "a"},
    )

    with pytest.raises(GraphFinalizationError, match="not parser-ranked"):
        finalize_graph(draft, entrypoint="missing")
