"""Language-neutral graph finalization contracts."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from codemble.adapters.base import ConceptAnnotation, Edge, Graph, Node, UnsupportedSource
from codemble.adapters.project import ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph import GraphFinalizationError, finalize_graph
from codemble.graph.layout import (
    _CONSTELLATION_SPACING,
    _REGION_SPACING,
    with_entrypoint,
)


def _node(
    node_id: str,
    *,
    region: str,
    rank: int | None = None,
    file: str | None = None,
    language: str = "python",
) -> Node:
    return Node(
        id=node_id,
        kind="module" if node_id == region else "function",
        name=node_id.rsplit(".", 1)[-1],
        language=language,
        file=file if file is not None else f"{region}.py",
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


def test_region_community_is_serialized_in_the_graph_schema() -> None:
    payload = finalize_graph(_community_fixture()).to_dict()

    assert all(isinstance(region["community"], int) for region in payload["regions"])


def _families_fixture() -> Graph:
    """A project with more communities than there are colour families.

    Two real clusters plus ten unrelated modules, which is the shape every
    real project has: a handful of genuine constellations and a long tail of
    files nothing imports.
    """

    nodes: list[Node] = [_node("a0", region="a0", rank=0)]
    edges: list[Edge] = []
    for index in range(1, 5):
        nodes.append(_node(f"a{index}", region=f"a{index}"))
        edges.append(Edge(f"a{index - 1}", f"a{index}", "import", True, 1))
    for index in range(3):
        nodes.append(_node(f"b{index}", region=f"b{index}"))
        if index:
            edges.append(Edge(f"b{index - 1}", f"b{index}", "import", True, 1))
    for index in range(10):
        nodes.append(_node(f"i{index:02d}", region=f"i{index:02d}"))
    return Graph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={f"{node.region}.py": node.region for node in nodes},
    )


def test_colour_families_are_never_shared_by_two_communities() -> None:
    """The defect this field exists for.

    ``community % 8`` gave community 12 and community 36 the same family, so
    two unrelated parts of a project rendered in one colour and the hue stopped
    meaning anything a learner could rely on.  A family may name at most one
    community.
    """

    graph = finalize_graph(_families_fixture())

    owners: dict[int, set[int]] = {}
    for region in graph.regions:
        if region.community_family is None:
            continue
        owners.setdefault(region.community_family, set()).add(region.community)
    assert owners, "some community must carry a family"
    for family, communities in owners.items():
        assert len(communities) == 1, f"family {family} is shared by {communities}"


def test_colour_families_go_to_the_largest_communities() -> None:
    graph = finalize_graph(_families_fixture())

    sizes: dict[int, int] = {}
    for region in graph.regions:
        sizes[region.community] = sizes.get(region.community, 0) + 1
    assert len(sizes) > 8, "the fixture must have more communities than families"

    families = {
        region.community: region.community_family
        for region in graph.regions
        if region.community_family is not None
    }
    assert len(families) == 8, "every available family is used"
    assert set(families.values()) == set(range(8)), "families are the dense range 0..7"

    # The two real clusters are the biggest communities, so they must be among
    # the eight that earn a hue.
    largest = sorted(sizes, key=lambda community: (-sizes[community], community))[:8]
    assert set(families) == set(largest)

    # A community that missed the cut carries no family rather than borrowing
    # one: "not one of this project's main groups" is a fact, and drawing it as
    # absence is honest where borrowing a hue was not.
    missed = [c for c in sizes if c not in families]
    assert missed, "the fixture must leave some community without a family"


def test_colour_families_are_deterministic_and_survive_a_home_change() -> None:
    first = finalize_graph(_families_fixture())
    second = finalize_graph(_families_fixture())
    assert {r.id: r.community_family for r in first.regions} == {
        r.id: r.community_family for r in second.regions
    }, "same code -> same sky"

    # Home is a learner choice; it must never repaint the project.
    moved = with_entrypoint(first, "a0")
    assert {r.id: r.community_family for r in moved.regions} == {
        r.id: r.community_family for r in first.regions
    }, "choosing Home must not recolour a single region"


def test_constellation_spacing_stays_tied_to_region_spacing() -> None:
    """Constellation and member spacing are one packing problem, not two.

    Written as unrelated literals they drifted to 4.5x, which left the galaxy
    98.7% empty -- constellation centres a median 728 units apart while the
    widest constellation measured 137 across -- so the camera had to stand back
    far enough to frame all that void and every system became a speck.

    The guard is the *relationship*, not a magic number: a ratio may be tuned,
    but it may not quietly become independent again.
    """

    ratio = _CONSTELLATION_SPACING / _REGION_SPACING
    assert 1.0 < ratio <= 3.0, (
        "constellations must sit further apart than the regions inside one, but "
        f"a ratio of {ratio} is the drift that emptied the sky"
    )


def test_constellations_stay_compact_enough_to_frame() -> None:
    """A regression guard on the emptiness itself.

    The camera fits whatever extent the layout produces, so a layout that
    sprawls silently costs legibility rather than raising an error: everything
    is still on screen, just too small to read. Pinning the extent of a known
    fixture is what makes that visible.
    """

    graph = finalize_graph(_families_fixture())
    regions = graph.regions
    centre = [sum(getattr(r, axis) for r in regions) / len(regions) for axis in "xyz"]
    extent = max(math.dist((r.x, r.y, r.z), centre) for r in regions)

    # 155 at today's ratio; 265 at the 4.5x that caused the defect.
    assert extent < 200, (
        f"this fixture's galaxy spans {extent:.0f} units; above 200 the packing "
        "constants have drifted apart again"
    )


def test_region_community_family_is_serialized_in_the_graph_schema() -> None:
    payload = finalize_graph(_families_fixture()).to_dict()

    assert all("community_family" in region for region in payload["regions"])
    assert all(
        region["community_family"] is None or isinstance(region["community_family"], int)
        for region in payload["regions"]
    )


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


def _hops_fixture() -> Graph:
    """Home -> mid -> far, plus a reverse importer and an unreachable island.

    ``side`` imports ``app`` rather than the other way round, so the fixture
    pins the undirected traversal: an import route is a relationship between two
    regions, and a learner reaches the importer from Home just as readily as the
    imported.  ``far`` is parser-ranked too so the Home-change test has a second
    legitimate candidate to move to.
    """

    region_ids = ("app", "mid", "far", "side", "island")
    ranks = {"app": 0, "far": 1}
    routes = (("app", "mid"), ("mid", "far"), ("side", "app"))
    return Graph(
        nodes=tuple(
            _node(region_id, region=region_id, rank=ranks.get(region_id))
            for region_id in region_ids
        ),
        edges=tuple(
            Edge(src=src, dst=dst, kind="import", certain=True, lineno=1)
            for src, dst in routes
        ),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={f"{region_id}.py": region_id for region_id in region_ids},
    )


def test_hops_from_home_measures_undirected_import_distance() -> None:
    graph = finalize_graph(_hops_fixture())
    hops = {region.id: region.hops_from_home for region in graph.regions}

    assert hops["app"] == 0, "Home is its own origin"
    assert hops["mid"] == 1, "a region Home imports is one route away"
    assert hops["far"] == 2, "distance accumulates along the route chain"
    assert hops["side"] == 1, "a region that imports Home is reachable from Home"


def test_hops_from_home_reports_no_route_as_none_never_a_guessed_distance() -> None:
    graph = finalize_graph(_hops_fixture())
    island = next(region for region in graph.regions if region.id == "island")

    assert island.hops_from_home is None


def test_hops_from_home_is_none_everywhere_without_a_selected_home() -> None:
    """No Home means no origin to measure from, and the graph must not pick one."""

    graph = finalize_graph(_community_fixture())

    assert graph.selected_entrypoint is None
    assert all(region.hops_from_home is None for region in graph.regions)


def test_choosing_a_different_home_recomputes_every_distance() -> None:
    graph = finalize_graph(_hops_fixture())
    moved = with_entrypoint(graph, "far")
    hops = {region.id: region.hops_from_home for region in moved.regions}

    assert hops == {"far": 0, "mid": 1, "app": 2, "side": 3, "island": None}


def test_hops_from_home_is_deterministic_and_serialized_in_the_render_schema() -> None:
    draft = _hops_fixture()
    payload = finalize_graph(draft).to_dict()

    assert finalize_graph(draft).to_json() == finalize_graph(draft).to_json()
    assert payload["schema_version"] == 9
    assert {region["id"]: region["hops_from_home"] for region in payload["regions"]} == {
        "app": 0,
        "mid": 1,
        "far": 2,
        "side": 1,
        "island": None,
    }


def test_unreached_call_cycle_is_labeled_instead_of_given_a_fake_depth() -> None:
    draft = Graph(
        nodes=(
            _node("cycle", region="cycle", rank=0),
            _node("cycle.alpha", region="cycle"),
            _node("cycle.beta", region="cycle"),
        ),
        edges=(
            Edge("cycle.alpha", "cycle.beta", "call", True, 2),
            Edge("cycle.beta", "cycle.alpha", "call", True, 3),
        ),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"cycle.py": "cycle"},
    )

    graph = finalize_graph(draft)
    nodes = {node.id: node for node in graph.nodes}

    assert nodes["cycle"].system_orbit is not None
    assert nodes["cycle"].system_orbit.kind == "origin"
    for node_id in ("cycle.alpha", "cycle.beta"):
        orbit = nodes[node_id].system_orbit
        assert orbit is not None
        assert orbit.kind == "unreached"
        assert orbit.call_depth is None
        assert orbit.ring == 1
        assert orbit.radius == 34.0


def test_overflow_subrings_never_overlap_the_next_call_layer() -> None:
    roots = tuple(_node(f"wide.root_{index:02d}", region="wide") for index in range(13))
    draft = Graph(
        nodes=(
            _node("wide", region="wide", rank=0),
            *roots,
            _node("wide.child", region="wide"),
        ),
        edges=(Edge("wide.root_00", "wide.child", "call", True, 2),),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"wide.py": "wide"},
    )

    graph = finalize_graph(draft)
    nodes = {node.id: node for node in graph.nodes}
    layer_one_radii = {
        nodes[node.id].system_orbit.radius
        for node in roots
        if nodes[node.id].system_orbit is not None
    }
    child_orbit = nodes["wide.child"].system_orbit

    assert layer_one_radii == {34.0, 46.0}
    assert child_orbit is not None
    assert child_orbit.call_depth == 2
    assert child_orbit.radius == 70.0
    assert child_orbit.radius not in layer_one_radii


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


def test_unsupported_sources_are_carried_and_serialized_in_canonical_order() -> None:
    """A language nobody parsed must survive into the payload the UI reads."""

    graph = Graph(
        nodes=(_node("only", region="only"),),
        edges=(),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"only.py": "hash"},
        unsupported_sources=(
            UnsupportedSource(".rs", "Rust", 1),
            UnsupportedSource(".go", "Go", 12),
            UnsupportedSource(".h", None, 3),
        ),
    )

    payload = graph.to_dict()

    assert payload["schema_version"] == 9
    assert payload["unsupported_sources"] == [
        {"extension": ".go", "language": "Go", "count": 12},
        {"extension": ".h", "language": None, "count": 3},
        {"extension": ".rs", "language": "Rust", "count": 1},
    ]


def test_a_graph_with_nothing_unsupported_reports_an_empty_list() -> None:
    """Absence is stated, not omitted: the field is always present."""

    graph = Graph(
        nodes=(_node("only", region="only"),),
        edges=(),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"only.py": "hash"},
    )

    assert graph.to_dict()["unsupported_sources"] == []


def test_choosing_a_new_home_preserves_the_unsupported_report() -> None:
    """Re-homing must not silently erase what the project could not chart."""

    draft = Graph(
        nodes=(_node("a", region="a", rank=0), _node("b", region="b", rank=1)),
        edges=(Edge(src="a", dst="b", kind="import", certain=True, lineno=1),),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"a.py": "one", "b.py": "two"},
        unsupported_sources=(UnsupportedSource(".go", "Go", 4),),
    )
    finalized = finalize_graph(draft)

    rehomed = with_entrypoint(finalized, "b")

    assert rehomed.unsupported_sources == (UnsupportedSource(".go", "Go", 4),)


def test_rehoming_a_graph_that_never_reached_layout_refuses_instead_of_emptying_it() -> None:
    """A missing precondition must fail loudly, not return a starless galaxy.

    ``with_entrypoint`` measures every distance against ``graph.regions``, which
    only ``layout_graph`` fills. Handed a graph that skipped it, the old code
    returned a valid-looking graph with zero regions -- a galaxy with no stars,
    reported as success.
    """

    draft = Graph(
        nodes=(_node("a", region="a", rank=0),),
        edges=(),
        entrypoint_candidates=("a",),
        project_root="/project",
        file_hashes={"a.py": "one"},
    )

    with pytest.raises(ValueError, match="never laid out"):
        with_entrypoint(draft, "a")


def test_reselecting_the_home_a_graph_already_has_is_a_no_op() -> None:
    """Every hydration re-selected the same Home and paid a whole BFS for it.

    ``CheckService.graph`` calls ``with_entrypoint`` with the Home the graph
    already carries, so the regions it rebuilds are the regions it was given.
    """

    draft = Graph(
        nodes=(
            _node("a", region="a", rank=0),
            _node("b", region="b", rank=1),
            _node("c", region="c", rank=2),
        ),
        edges=(
            Edge(src="a", dst="b", kind="import", certain=True, lineno=1),
            Edge(src="b", dst="c", kind="import", certain=True, lineno=1),
        ),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"a.py": "one", "b.py": "two", "c.py": "three"},
    )
    finalized = finalize_graph(draft)
    assert finalized.selected_entrypoint == "a"

    assert with_entrypoint(finalized, "a") is finalized


def test_reselecting_the_same_home_still_answers_what_a_recompute_would() -> None:
    """The shortcut is only safe while it agrees with the long way round."""

    draft = Graph(
        nodes=(
            _node("a", region="a", rank=0),
            _node("b", region="b", rank=1),
            _node("c", region="c", rank=2),
            _node("island", region="island"),
        ),
        edges=(
            Edge(src="a", dst="b", kind="import", certain=True, lineno=1),
            Edge(src="b", dst="c", kind="import", certain=True, lineno=1),
        ),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={f"{name}.py": name for name in ("a", "b", "c", "island")},
    )
    finalized = finalize_graph(draft)

    # Route the same request through a graph the shortcut cannot recognise, so
    # the full recompute runs, and compare the two answers field by field.
    forgetful = replace(finalized, selected_entrypoint=None)
    recomputed = with_entrypoint(forgetful, "a")

    assert {region.id: region.hops_from_home for region in recomputed.regions} == {
        "a": 0,
        "b": 1,
        "c": 2,
        "island": None,
    }
    assert {region.id: region.home for region in recomputed.regions} == {
        region.id: region.home for region in finalized.regions
    }
    assert {region.id: region.hops_from_home for region in recomputed.regions} == {
        region.id: region.hops_from_home for region in finalized.regions
    }


def test_layout_never_claims_a_region_is_understood() -> None:
    """Understanding is the progress store's fact, and it has exactly one rule.

    ``layout_graph`` once carried a second, unreachable definition -- "every
    node understood" -- which is not the rule the store applies ("this region
    id is in the learner's proven set"). Two formulas for one field is how a
    region lights without evidence.
    """

    draft = Graph(
        nodes=(_node("a", region="a", rank=0), _node("a.run", region="a")),
        edges=(),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"a.py": "one"},
    )

    finalized = finalize_graph(draft)

    assert [region.understood for region in finalized.regions] == [False]
    assert all(node.understood is False for node in finalized.nodes)


def test_a_test_fixture_never_ties_with_the_project_s_own_entrypoint() -> None:
    """Home resolves itself when only test fixtures tie with the real entry.

    Measured on this repository before this rule: rank 0 held SIX candidates --
    `codemble.cli` plus a C#, Go, Java, Rust and TypeScript fixture, each an
    ordinary unmarked `main()` under `tests/fixtures/`. No candidate was
    uniquely best, so `selected_entrypoint` was None and a first-run learner
    met a picker listing 26 candidates, 22 of them under `tests/`.

    Every adapter already had SOME notion of a test, but each asked a question
    only its own language could answer -- Rust `#[test]`, Java `@Test`, C#
    `[Fact]`, Go the `_test.go` suffix -- and none of those sees a plain
    `main()` in a file that is not named like a test. "Is this file inside the
    project's own test tree?" is path-based and language-neutral, so it is
    asked once, here, where every adapter already funnels.
    """

    draft = Graph(
        nodes=(
            _node("app", region="app", rank=0, file="src/app.py"),
            _node(
                "go:tests/fixtures/sample/main.go",
                region="go:tests/fixtures/sample/main.go",
                rank=0,
                file="tests/fixtures/sample/main.go",
                language="go",
            ),
            _node(
                "rust:tests/fixtures/sample/main.rs::main",
                region="rust:tests/fixtures/sample/main.rs",
                rank=0,
                file="tests/fixtures/sample/main.rs",
                language="rust",
            ),
        ),
        edges=(),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"src/app.py": "one"},
    )

    finalized = finalize_graph(draft)
    ranks = {node.id: node.entrypoint_rank for node in finalized.nodes}

    assert finalized.selected_entrypoint == "app", (
        "the project's own entry is the unique best candidate, so nothing is asked"
    )
    order = finalized.entrypoint_candidates
    assert order[0] == "app"
    for fixture in ("go:tests/fixtures/sample/main.go", "rust:tests/fixtures/sample/main.rs::main"):
        assert order.index("app") < order.index(fixture), (
            f"{fixture} must sort below the project's own entry"
        )
        assert fixture in order, (
            "demoted, never dropped -- a project that IS a test suite still needs a Home"
        )
        # The bias is in the ordering; the number the picker shows is untouched.
        assert ranks[fixture] == ranks["app"] == 0


def test_an_all_fixture_project_still_resolves_a_home() -> None:
    """Demotion is relative, so a project made only of tests still gets one."""

    draft = Graph(
        nodes=(
            _node(
                "go:tests/sample/main.go",
                region="go:tests/sample/main.go",
                rank=0,
                file="tests/sample/main.go",
                language="go",
            ),
        ),
        edges=(),
        entrypoint_candidates=(),
        project_root="/project",
        file_hashes={"tests/sample/main.go": "one"},
    )

    finalized = finalize_graph(draft)

    assert finalized.selected_entrypoint == "go:tests/sample/main.go"


def test_the_test_bias_survives_being_finalized_twice(tmp_path: Path) -> None:
    """The normal path finalizes twice, so the rule has to be idempotent.

    `parse_files` finalizes inside the adapter, and `ProjectParser` finalizes
    again when it composes. A first version of this rule *added* a penalty to
    `entrypoint_rank`, so the composed path applied it twice -- measured, rank
    4 became rank 8. It changed no outcome on the fixtures at hand, which is
    exactly why it needed a test at the real seam rather than at
    `finalize_graph` alone.

    Biasing the sort key instead of the field is idempotent by construction,
    and it keeps the promise the picker makes: the rank shown is the parser's
    own, not one Codemble has quietly moved.
    """

    root = tmp_path / "app"
    (root / "tests").mkdir(parents=True)
    entry = "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n"
    (root / "main.py").write_text(entry, encoding="utf-8")
    (root / "tests" / "test_thing.py").write_text(entry, encoding="utf-8")

    once = PythonAstAdapter().parse(root)
    twice = ProjectParser().parse(root)

    ranks_once = {n.id: n.entrypoint_rank for n in once.nodes if n.entrypoint_rank is not None}
    ranks_twice = {n.id: n.entrypoint_rank for n in twice.nodes if n.entrypoint_rank is not None}

    assert ranks_once == ranks_twice, "finalizing twice must not compound the bias"
    assert ranks_twice["tests.test_thing"] == ranks_twice["main"] == 0, (
        "the stored rank stays the parser's own; only the ordering is biased"
    )
    assert twice.entrypoint_candidates[0] == "main"
    assert twice.entrypoint_candidates.index("main") < twice.entrypoint_candidates.index(
        "tests.test_thing"
    ), "the project's own entry must sort above the fixture"
    assert twice.selected_entrypoint == "main"
