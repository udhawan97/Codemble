"""Contract tests for the Python AST adapter."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from codemble.adapters.base import Edge
from codemble.adapters.python_ast import PythonAstAdapter, PythonParseError
from codemble.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CONCEPT_FIXTURE = Path(__file__).parent / "fixtures" / "concepts_sample.py"


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    return PythonAstAdapter().parse(FIXTURE)


def test_discovers_nodes_and_keeps_parse_failures_visible(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert len(graph.file_hashes) == 11
    assert graph.partial_files == ("broken.py",)
    assert nodes["broken"].partial is True
    assert "broken.this_will_not_parse" not in nodes
    assert not any("should_not_exist" in node.id for node in graph.nodes)
    assert not any("should_also_not_exist" in node.id for node in graph.nodes)
    assert nodes["pkg.service.Service.run"].file == "pkg/service.py"
    assert nodes["pkg.service.Service.run"].lineno == 7
    assert nodes["pkg.service.Service.run"].end_lineno == 10
    assert nodes["pkg.service.Service.run"].loc == 4
    assert nodes["pkg.service.Service.run"].region == "pkg.service"
    assert all(node.language == "python" for node in graph.nodes)


def test_resolves_project_and_external_imports(graph) -> None:  # type: ignore[no-untyped-def]
    imports = {edge for edge in graph.edges if edge.kind == "import"}
    expected = {
        Edge("app", "external:json", "import", True, 1, True),
        Edge("app", "pkg.helpers", "import", True, 3, False),
        Edge("app", "pkg.service", "import", True, 4, False),
        Edge("app", "pkg.util", "import", True, 5, False),
        Edge("api", "external:fastapi", "import", True, 1, True),
        Edge("cli", "app", "import", True, 1, False),
        Edge("pkg", "pkg.service", "import", True, 1, False),
        Edge("pkg.helpers", "pkg.util", "import", True, 1, False),
        Edge("pkg.service", "shared", "import", True, 1, False),
        Edge("pkg.service", "pkg.util", "import", True, 3, False),
    }

    assert expected <= imports
    assert len(imports) == len(expected)


def test_call_resolution_is_exact_or_explicitly_uncertain(graph) -> None:  # type: ignore[no-untyped-def]
    calls = {edge for edge in graph.edges if edge.kind == "call"}
    expected_certain = {
        Edge("app.main", "pkg.service.Service", "call", True, 9, False),
        Edge("app.main", "pkg.util.greet", "call", True, 10, False),
        Edge("app.main", "pkg.helpers.log", "call", True, 11, False),
        Edge("cli.launch", "app.main", "call", True, 5, False),
        Edge("pkg.helpers.log", "pkg.util.normalize", "call", True, 5, False),
        Edge("pkg.service.Service.run", "pkg.util.normalize", "call", True, 8, False),
        Edge("pkg.service.Service.run", "shared.duplicate", "call", True, 9, False),
        Edge(
            "pkg.service.Service.run",
            "pkg.service.Service.finish",
            "call",
            True,
            10,
            False,
        ),
        Edge("pkg.util.greet", "pkg.util.normalize", "call", True, 2, False),
        Edge("shared.choose", "shared.duplicate", "call", True, 6, False),
    }
    expected_possible = {
        Edge("app.main", "pkg.service.Service.run", "call", False, 13, False),
    }
    expected_external = {
        Edge("app.main", "external:builtins.print", "call", False, 12, True),
        Edge("app.main", "external:json.dumps", "call", False, 12, True),
        Edge("pkg.helpers.log", "external:builtins.print", "call", False, 6, True),
        Edge("pkg.service.Service.finish", "external:builtins.len", "call", False, 13, True),
        Edge("pkg.service.Service.finish", "external:builtins.str", "call", False, 13, True),
        Edge("pkg.util.normalize", "external:value.strip", "call", False, 6, True),
    }
    ambiguous = {
        edge
        for edge in calls
        if edge.src == "ambiguous.invoke" and edge.lineno == 2
    }

    assert expected_certain <= calls
    assert expected_external <= calls
    assert expected_possible <= calls
    assert ambiguous == {
        Edge("ambiguous.invoke", "pkg.util.duplicate", "call", False, 2, False),
        Edge("ambiguous.invoke", "shared.duplicate", "call", False, 2, False),
    }
    assert all(not edge.certain for edge in ambiguous)
    assert len(calls) == 19


def test_entrypoints_centrality_and_render_metadata(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert graph.entrypoint_candidates == ("app", "app.main", "api", "runner.__main__")
    assert nodes["app"].entrypoint_rank == 0
    assert nodes["app.main"].entrypoint_rank == 1
    assert nodes["api"].entrypoint_rank == 2
    assert nodes["runner.__main__"].entrypoint_rank == 3
    assert graph.selected_entrypoint == "app"
    assert nodes["pkg.util.normalize"].centrality == 3
    assert nodes["shared.duplicate"].centrality == 3
    assert nodes["app.main"].centrality == 1
    assert nodes["pkg.util.normalize"].understood is False


def test_serialization_is_byte_deterministic(graph) -> None:  # type: ignore[no-untyped-def]
    second = PythonAstAdapter().parse(FIXTURE)

    assert graph.to_json().encode() == second.to_json().encode()
    payload = json.loads(graph.to_json())
    assert payload["schema_version"] == 5
    assert payload["nodes"] == sorted(payload["nodes"], key=lambda node: node["id"])
    assert list(payload["file_hashes"]) == sorted(payload["file_hashes"])
    assert payload["concept_annotations"] == sorted(
        payload["concept_annotations"],
        key=lambda item: (
            item["language"],
            item["node_id"],
            item["lineno"],
            item["concept"],
            item["end_lineno"],
        ),
    )


def _longest_prefix_reference(node_id: str, modules: set[str]) -> str:
    """The original O(defs x modules) scan, kept as the byte-identical oracle."""

    return max(
        (m for m in modules if node_id == m or node_id.startswith(f"{m}.")),
        key=len,
    )


def test_module_from_node_id_matches_longest_prefix_oracle() -> None:
    from codemble.adapters.python_ast import _module_from_node_id

    cases: list[tuple[str, set[str]]] = [
        ("a.b.func", {"a.b"}),
        ("a.b.c.func", {"a", "a.b", "a.b.c"}),
        ("a.bc.func", {"a", "a.b"}),  # component boundary: not "a.b"
        ("a.b", {"a", "a.b"}),  # exact module match
        ("pkg.Outer.method", {"pkg", "pkg.Outer"}),  # nested-class ambiguity kept
        ("pkg.mod.Class.method.inner", {"pkg.mod", "pkg.mod.Class"}),
    ]
    for node_id, modules in cases:
        assert _module_from_node_id(node_id, modules) == _longest_prefix_reference(
            node_id, modules
        )


def test_module_from_node_id_is_byte_identical_to_the_old_scan() -> None:
    import random

    from codemble.adapters.python_ast import _module_from_node_id

    rng = random.Random(20260720)
    atoms = ["a", "ab", "abc", "pkg", "mod", "Class", "fn", "x"]
    for _ in range(4000):
        modules = {
            ".".join(rng.choices(atoms, k=rng.randint(1, 4)))
            for _ in range(rng.randint(1, 6))
        }
        base = rng.choice(sorted(modules))
        node_id = base + "." + ".".join(rng.choices(atoms, k=rng.randint(1, 3)))
        assert _module_from_node_id(node_id, modules) == _longest_prefix_reference(
            node_id, modules
        )


def test_python_lens_annotations_are_ast_proven_and_lexically_owned() -> None:
    graph = PythonAstAdapter().parse(CONCEPT_FIXTURE)
    concepts_by_node: dict[str, set[tuple[str, int]]] = {}
    for annotation in graph.concept_annotations:
        concepts_by_node.setdefault(annotation.node_id, set()).add(
            (annotation.concept, annotation.lineno)
        )

    assert concepts_by_node.get("concepts_sample", set()) == set()
    assert {
        ("decorator", 8),
        ("async-await", 9),
        ("type-hint", 9),
        ("comprehension", 10),
        ("comprehension", 11),
        ("async-await", 12),
        ("async-await", 13),
        ("context-manager", 14),
        ("exception-handling", 16),
        ("exception-handling", 19),
    } <= concepts_by_node["concepts_sample.collect"]
    assert ("generator", 23) in concepts_by_node["concepts_sample.stream"]
    assert ("generator", 27) in concepts_by_node["concepts_sample.expression"]
    assert ("type-hint", 31) in concepts_by_node["concepts_sample.Example"]
    assert {
        ("dunder-method", 33),
        ("type-hint", 33),
    } <= concepts_by_node["concepts_sample.Example.__len__"]
    assert all(annotation.snippet for annotation in graph.concept_annotations)
    assert {annotation.language for annotation in graph.concept_annotations} == {"python"}


def test_layout_is_render_ready_and_deterministic(graph) -> None:  # type: ignore[no-untyped-def]
    second = PythonAstAdapter().parse(FIXTURE)
    regions = {region.id: region for region in graph.regions}
    second_regions = {region.id: region for region in second.regions}
    nodes = {node.id: node for node in graph.nodes}

    def orbit_radius(node_id: str) -> float:
        node = nodes[node_id]
        return round(math.hypot(node.system_x, node.system_z), 3)

    assert regions == second_regions
    assert len({(region.x, region.y, region.z) for region in graph.regions}) == len(
        graph.regions
    )
    assert regions["app"].home is True
    assert regions["app"].node_count == 2
    assert regions["pkg.service"].node_count == 4
    assert any(route.src == "cli" and route.dst == "app" for route in graph.region_edges)

    # Orbits are call depth from the system's entry node, not member index.
    # The module node holds the origin; ring 1 is 34.0 out, each ring +24.0.
    assert orbit_radius("app") == 0.0
    assert orbit_radius("pkg.service") == 0.0
    assert orbit_radius("app.main") == 34.0
    # Service.run calls Service.finish, so finish orbits one ring further out.
    assert orbit_radius("pkg.service.Service") == 34.0
    assert orbit_radius("pkg.service.Service.run") == 34.0
    assert orbit_radius("pkg.service.Service.finish") == 58.0
    # greet -> normalize, and duplicate is called by nobody in the region.
    assert orbit_radius("pkg.util.greet") == 34.0
    assert orbit_radius("pkg.util.duplicate") == 34.0
    assert orbit_radius("pkg.util.normalize") == 58.0
    assert orbit_radius("shared.choose") == 34.0
    assert orbit_radius("shared.duplicate") == 58.0
    assert {node.id: (node.system_x, node.system_y, node.system_z) for node in graph.nodes} == {
        node.id: (node.system_x, node.system_y, node.system_z) for node in second.nodes
    }


def test_a_possible_call_never_decides_orbit_depth(tmp_path: Path) -> None:
    """An unproven call must not pull a node into a deeper ring.

    ``sampleproj`` has no intra-region uncertain call edge, so the
    ``not edge.certain`` filter in ``layout.py``'s ``_call_depths`` was live but
    untested: deleting it left the whole suite green while the galaxy silently
    asserted a call depth the parser never proved.  Its twin in ``mapview.py``
    is covered by ``test_mapview.py``; this is the layout half.
    """

    (tmp_path / "workmod.py").write_text(
        "class Box:\n"
        "    def helper(self) -> None:\n"
        "        pass\n"
        "\n"
        "\n"
        "def caller() -> None:\n"
        "    helper()\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    caller()\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(tmp_path)
    nodes = {node.id: node for node in graph.nodes}

    def orbit_radius(node_id: str) -> float:
        node = nodes[node_id]
        return round(math.hypot(node.system_x, node.system_z), 3)

    # The premise: `helper()` is unqualified and resolved only by whole-project
    # name lookup, so the parser records it as possible, and both ends sit in
    # the same region -- exactly the edge _call_depths must refuse to act on.
    calls_into_helper = [
        (edge.src, edge.certain)
        for edge in graph.edges
        if edge.kind == "call" and edge.dst == "workmod.Box.helper"
    ]
    assert calls_into_helper == [("workmod.caller", False)]
    assert nodes["workmod.caller"].region == nodes["workmod.Box.helper"].region == "workmod"

    # Ring 1 is 34.0 from the origin, each ring a further 24.0.  Box.helper is
    # a root because nothing PROVEN calls it; placing it at 58.0 would draw a
    # call depth that exists only in a guess.
    assert orbit_radius("workmod.caller") == 34.0
    assert orbit_radius("workmod.Box.helper") == 34.0

    # The uncertain edge itself must stay in the graph, just powerless.
    assert any(
        edge.src == "workmod.caller"
        and edge.dst == "workmod.Box.helper"
        and not edge.certain
        for edge in graph.edges
    )


def test_ambiguous_rank_zero_entrypoints_require_an_explicit_choice(
    tmp_path: Path,
) -> None:
    for module in ("alpha", "beta"):
        (tmp_path / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n',
            encoding="utf-8",
        )

    graph = PythonAstAdapter().parse(tmp_path)
    assert graph.entrypoint_candidates == ("alpha", "beta")
    assert graph.selected_entrypoint is None
    assert not any(region.home for region in graph.regions)

    selected = PythonAstAdapter().parse(tmp_path, entrypoint="beta")
    assert selected.selected_entrypoint == "beta"
    assert next(region for region in selected.regions if region.id == "beta").home
    with pytest.raises(PythonParseError, match="not parser-ranked"):
        PythonAstAdapter().parse(tmp_path, entrypoint="missing")


def test_invalid_target_fails_honestly(tmp_path: Path) -> None:
    with pytest.raises(PythonParseError, match="no Python files"):
        PythonAstAdapter().parse(tmp_path)


def test_parse_cli_writes_graph_json(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    destination = tmp_path / "nested" / "graph.json"

    assert main(["parse", str(FIXTURE), "--out", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 5
    assert "Wrote" in capsys.readouterr().out
