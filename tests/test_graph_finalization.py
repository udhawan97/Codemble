"""Language-neutral graph finalization contracts."""

from __future__ import annotations

import math

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


def test_centrality_counts_distinct_callers_not_call_sites() -> None:
    """Brightness must mean "how much depends on this", not "how often it is called".

    A private helper hammered three times inside one function outranked a
    utility two modules share, so the busiest loop in a project read as its
    most important structure. Region centrality sums its members, so the same
    distortion reached the galaxy view.
    """

    draft = Graph(
        nodes=(
            _node("app", region="app", rank=0),
            _node("app.spam", region="app"),
            _node("app.alpha", region="app"),
            _node("app.beta", region="app"),
            _node("lib", region="lib"),
            _node("lib.hot", region="lib"),
            _node("lib.shared", region="lib"),
        ),
        edges=(
            Edge("app.spam", "lib.hot", "call", True, 2),
            Edge("app.spam", "lib.hot", "call", True, 3),
            Edge("app.spam", "lib.hot", "call", True, 4),
            Edge("app.alpha", "lib.shared", "call", True, 2),
            Edge("app.beta", "lib.shared", "call", True, 2),
        ),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"app.py": "a", "lib.py": "b"},
    )

    graph = finalize_graph(draft)
    centrality = {node.id: node.centrality for node in graph.nodes}

    assert centrality["lib.hot"] == 1, "three call sites from one function is one caller"
    assert centrality["lib.shared"] == 2, "two modules each calling once is two callers"
    assert next(region for region in graph.regions if region.id == "lib").centrality == 3


def test_import_communities_are_deterministic_and_match_two_joined_cliques() -> None:
    draft = _community_fixture()

    first = finalize_graph(draft)
    second = finalize_graph(draft)
    communities = {region.id: region.community for region in first.regions}

    assert first.to_json() == second.to_json()
    assert {communities[region_id] for region_id in ("a0", "a1", "a2")} == {0}
    assert {communities[region_id] for region_id in ("b0", "b1", "b2")} == {1}
    assert len(set(communities.values())) == 2


def test_constellations_keep_same_community_regions_closer() -> None:
    graph = finalize_graph(_community_fixture())
    regions = {region.id: region for region in graph.regions}
    points = {
        region_id: (region.x, region.y, region.z)
        for region_id, region in regions.items()
    }
    within: list[float] = []
    between: list[float] = []
    region_ids = sorted(regions)
    for index, first in enumerate(region_ids):
        for second in region_ids[index + 1 :]:
            bucket = (
                within
                if regions[first].community == regions[second].community
                else between
            )
            bucket.append(math.dist(points[first], points[second]))

    assert sum(within) / len(within) < sum(between) / len(between)


def test_isolated_region_gets_its_own_finite_constellation_position() -> None:
    draft = _community_fixture(include_isolated=True)

    graph = finalize_graph(draft)
    isolated = next(region for region in graph.regions if region.id == "isolated")

    assert isolated.community not in {
        region.community for region in graph.regions if region.id != "isolated"
    }
    assert all(math.isfinite(value) for value in (isolated.x, isolated.y, isolated.z))


def test_region_community_is_serialized_in_graph_schema_five() -> None:
    payload = finalize_graph(_community_fixture()).to_dict()

    assert payload["schema_version"] == 5
    assert all(isinstance(region["community"], int) for region in payload["regions"])


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


def _community_fixture(*, include_isolated: bool = False) -> Graph:
    first = ("a0", "a1", "a2")
    second = ("b0", "b1", "b2")
    region_ids = first + second + (("isolated",) if include_isolated else ())
    clique_routes = tuple(
        (members[index], members[target])
        for members in (first, second)
        for index in range(len(members))
        for target in range(index + 1, len(members))
    )
    routes = clique_routes + (("a2", "b0"),)
    return Graph(
        nodes=tuple(_node(region_id, region=region_id) for region_id in region_ids),
        edges=tuple(
            Edge(src=src, dst=dst, kind="import", certain=True, lineno=1)
            for src, dst in routes
        ),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={f"{region_id}.py": region_id for region_id in region_ids},
    )
