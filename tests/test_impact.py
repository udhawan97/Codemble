"""Blast radius: "change this and these places feel it", from the graph alone.

This is the Expert lead surface, and the reason it is graph-layer truth rather
than narration is not tidiness -- it is that the panel's most useful content
must work with **no API key at all**. An onboarding developer asking "what does
this control, and what can break it" should never be blocked on a provider.

The one rule that carries the Correctness Contract into transitive reach: a
chain that passes through a single unproven edge is unproven for its whole
length, and says so.
"""

from __future__ import annotations

from pathlib import Path

from codemble.adapters.base import Edge, Graph, Node
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph.impact import blast_radius

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def _node(node_id: str) -> Node:
    return Node(
        id=node_id,
        kind="function",
        name=node_id.rsplit(".", 1)[-1],
        language="python",
        file=f"{node_id.split('.')[0]}.py",
        lineno=1,
        end_lineno=2,
        loc=2,
        region=node_id.split(".")[0],
    )


def _chain(*, certain_middle: bool) -> Graph:
    """a -> b -> c, so `c` is reached from `a` through `b`."""

    return Graph(
        project_root="/tmp/chain",
        entrypoint_candidates=(),
        file_hashes={},
        nodes=[_node("a.one"), _node("b.two"), _node("c.three")],
        edges=[
            Edge(src="a.one", dst="b.two", kind="call", certain=True, lineno=1),
            Edge(src="b.two", dst="c.three", kind="call", certain=certain_middle, lineno=1),
        ],
    )


def test_direct_callers_are_what_feels_a_change() -> None:
    graph = _chain(certain_middle=True)

    impact = blast_radius(graph, "b.two")

    affects = {item["node_id"]: item for item in impact["affects"]}
    depends = {item["node_id"]: item for item in impact["depends_on"]}
    assert affects["a.one"]["depth"] == 1
    assert depends["c.three"]["depth"] == 1


def test_reach_is_transitive_and_carries_its_depth() -> None:
    graph = _chain(certain_middle=True)

    impact = blast_radius(graph, "c.three")

    affects = {item["node_id"]: item["depth"] for item in impact["affects"]}
    assert affects == {"b.two": 1, "a.one": 2}


def test_a_chain_through_one_possible_edge_is_possible_throughout() -> None:
    """The clause this whole module exists to honour.

    ``a`` reaches ``c`` only by way of an edge the parser could not prove, so
    reporting it as a certain consequence would be inventing a relationship --
    exactly the wrong a learner cannot detect.
    """

    graph = _chain(certain_middle=False)

    impact = blast_radius(graph, "c.three")

    affects = {item["node_id"]: item["certain"] for item in impact["affects"]}
    assert affects["b.two"] is False, "the unproven edge itself is unproven"
    assert affects["a.one"] is False, "and everything reached only through it"


def test_a_certain_route_wins_over_a_possible_one_to_the_same_node() -> None:
    """Two routes, one proven: the proven one is the honest answer."""

    graph = Graph(
        project_root="/tmp/two",
        entrypoint_candidates=(),
        file_hashes={},
        nodes=[_node("a.one"), _node("b.two"), _node("c.three")],
        edges=[
            Edge(src="a.one", dst="c.three", kind="call", certain=False, lineno=1),
            Edge(src="a.one", dst="b.two", kind="call", certain=True, lineno=2),
            Edge(src="b.two", dst="c.three", kind="call", certain=True, lineno=3),
        ],
    )

    impact = blast_radius(graph, "c.three")

    reached = {item["node_id"]: item for item in impact["affects"]}
    assert reached["a.one"]["certain"] is True


def test_depth_is_capped_and_says_when_it_stopped() -> None:
    nodes = [_node(f"m{index}.f") for index in range(6)]
    edges = [
        Edge(src=f"m{index}.f", dst=f"m{index + 1}.f", kind="call", certain=True, lineno=1)
        for index in range(5)
    ]
    graph = Graph(
        project_root="/tmp/deep",
        nodes=nodes,
        edges=edges,
        entrypoint_candidates=(),
        file_hashes={},
    )

    impact = blast_radius(graph, "m5.f", max_depth=2)

    assert {item["depth"] for item in impact["affects"]} == {1, 2}
    assert impact["truncated"] is True


def test_an_external_dependency_is_never_reported_as_a_dependency() -> None:
    """External edges leave the project, so nothing downstream can be walked."""

    graph = Graph(
        project_root="/tmp/ext",
        entrypoint_candidates=(),
        file_hashes={},
        nodes=[_node("a.one")],
        edges=[Edge(src="a.one", dst="requests", kind="import", certain=True, lineno=1, external=True)],
    )

    impact = blast_radius(graph, "a.one")

    assert impact["depends_on"] == []


def test_a_cycle_terminates() -> None:
    graph = Graph(
        project_root="/tmp/cycle",
        entrypoint_candidates=(),
        file_hashes={},
        nodes=[_node("a.one"), _node("b.two")],
        edges=[
            Edge(src="a.one", dst="b.two", kind="call", certain=True, lineno=1),
            Edge(src="b.two", dst="a.one", kind="call", certain=True, lineno=1),
        ],
    )

    impact = blast_radius(graph, "a.one")

    assert {item["node_id"] for item in impact["affects"]} == {"b.two"}
    assert {item["node_id"] for item in impact["depends_on"]} == {"b.two"}


def test_every_entry_cites_a_real_location() -> None:
    """Correctness Contract: every claim links to a real file:line."""

    graph = PythonAstAdapter().parse(FIXTURE)

    impact = blast_radius(graph, "pkg.service.Service.run")

    entries = impact["affects"] + impact["depends_on"]
    assert entries, "the fixture's Service.run has parser-proven relationships"
    for entry in entries:
        assert entry["citation"].count(":") == 1
        file_part, line_part = entry["citation"].split(":")
        assert file_part.endswith(".py")
        assert int(line_part) >= 1


def test_the_result_is_deterministic() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)

    assert blast_radius(graph, "app.main") == blast_radius(graph, "app.main")


def test_an_unknown_node_is_refused() -> None:
    graph = _chain(certain_middle=True)

    try:
        blast_radius(graph, "not.a.node")
    except KeyError:
        return
    raise AssertionError("an unknown node must not return an empty-looking answer")
