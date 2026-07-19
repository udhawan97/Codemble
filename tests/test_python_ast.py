"""Contract tests for the Python AST adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codemble.adapters.base import Edge
from codemble.adapters.python_ast import PythonAstAdapter, PythonParseError
from codemble.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


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
    assert nodes["pkg.util.normalize"].centrality == 3
    assert nodes["shared.duplicate"].centrality == 3
    assert nodes["app.main"].centrality == 1
    assert nodes["pkg.util.normalize"].understood is False


def test_serialization_is_byte_deterministic(graph) -> None:  # type: ignore[no-untyped-def]
    second = PythonAstAdapter().parse(FIXTURE)

    assert graph.to_json().encode() == second.to_json().encode()
    payload = json.loads(graph.to_json())
    assert payload["schema_version"] == 1
    assert payload["nodes"] == sorted(payload["nodes"], key=lambda node: node["id"])
    assert list(payload["file_hashes"]) == sorted(payload["file_hashes"])


def test_layout_is_render_ready_and_deterministic(graph) -> None:  # type: ignore[no-untyped-def]
    second = PythonAstAdapter().parse(FIXTURE)
    regions = {region.id: region for region in graph.regions}
    second_regions = {region.id: region for region in second.regions}
    nodes = {node.id: node for node in graph.nodes}

    assert regions == second_regions
    assert len({(region.x, region.y, region.z) for region in graph.regions}) == len(
        graph.regions
    )
    assert regions["app"].home is True
    assert regions["app"].node_count == 2
    assert regions["pkg.service"].node_count == 4
    assert nodes["app"].system_x == 0.0
    assert (nodes["app.main"].system_x, nodes["app.main"].system_z) != (0.0, 0.0)
    assert any(route.src == "cli" and route.dst == "app" for route in graph.region_edges)


def test_invalid_target_fails_honestly(tmp_path: Path) -> None:
    with pytest.raises(PythonParseError, match="no Python files"):
        PythonAstAdapter().parse(tmp_path)


def test_parse_cli_writes_graph_json(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    destination = tmp_path / "nested" / "graph.json"

    assert main(["parse", str(FIXTURE), "--out", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "Wrote" in capsys.readouterr().out
