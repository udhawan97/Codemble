"""Mode-neutral feature journeys from parser-owned evidence only."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from codemble.adapters.base import Edge, Graph, Node, RoleEvidence
from codemble.graph.learning import learning_journey


def _write(root: Path, relative: str, source: str) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _node(
    node_id: str,
    *,
    kind: str,
    file: str,
    line: int,
    region: str,
    rank: int | None = None,
) -> Node:
    return Node(
        id=node_id,
        kind=kind,  # type: ignore[arg-type]
        name=node_id.rsplit(".", 1)[-1],
        language="python",
        file=file,
        lineno=line,
        end_lineno=line,
        loc=1,
        region=region,
        entrypoint_rank=rank,
    )


def test_longer_certain_route_wins_and_possible_shortcut_stays_separate(
    tmp_path: Path,
) -> None:
    hashes = {
        "app.py": _write(tmp_path, "app.py", "from routes import start\nmain()\n"),
        "routes.py": _write(tmp_path, "routes.py", "def start():\n    load()\n"),
        "feature.py": _write(tmp_path, "feature.py", "def load():\n    render()\n\ndef render():\n    pass\n"),
    }
    nodes = (
        _node("app", kind="module", file="app.py", line=1, region="app", rank=0),
        _node("routes", kind="module", file="routes.py", line=1, region="routes"),
        _node("feature", kind="module", file="feature.py", line=1, region="feature"),
        _node("routes.start", kind="function", file="routes.py", line=1, region="routes"),
        _node("feature.load", kind="function", file="feature.py", line=1, region="feature"),
        _node("feature.render", kind="function", file="feature.py", line=4, region="feature"),
    )
    graph = Graph(
        nodes=nodes,
        edges=(
            Edge("app", "routes", "import", True, 1),
            Edge("routes.start", "feature.load", "call", True, 2),
            Edge("feature.load", "feature.render", "call", True, 2),
            # Tempting and shorter, but not proven.
            Edge("routes.start", "feature.render", "call", False, 1),
        ),
        entrypoint_candidates=("app",),
        selected_entrypoint="app",
        project_root=str(tmp_path),
        file_hashes=hashes,
        role_evidence=(
            RoleEvidence(
                "routes.start",
                "route-handler",
                "python.decorator.route",
                "routes.py",
                1,
                1,
            ),
        ),
    )

    journey = learning_journey(graph, "feature.render")

    assert journey["status"] == "complete"
    assert [step["relation"] for step in journey["steps"]] == [
        "home",
        "import",
        "role",
        "call",
        "call",
    ]
    assert [step["node_id"] for step in journey["runtime_steps"]] == [
        "feature.load",
        "feature.render",
    ]
    assert journey["steps"][-1]["is_target"] is True
    assert journey["possible_frontier"] == [
        {
            "relation": "call",
            "source_node_id": "routes.start",
            "target_node_id": "feature.render",
            "certain": False,
            "observation": {
                "file": "routes.py",
                "line": 1,
                "citation": "routes.py:1",
            },
            "declaration": {
                "file": "feature.py",
                "line": 4,
                "citation": "feature.py:4",
            },
        }
    ]
    assert len({step["id"] for step in journey["steps"]}) == len(journey["steps"])
    assert journey == learning_journey(graph, "feature.render")


def test_module_target_is_an_honest_file_only_journey(tmp_path: Path) -> None:
    hashes = {
        "app.py": _write(tmp_path, "app.py", "import feature\n"),
        "feature.py": _write(tmp_path, "feature.py", "def render():\n    pass\n"),
    }
    graph = Graph(
        nodes=(
            _node("app", kind="module", file="app.py", line=1, region="app", rank=0),
            _node("feature", kind="module", file="feature.py", line=1, region="feature"),
            _node("feature.render", kind="function", file="feature.py", line=1, region="feature"),
        ),
        edges=(Edge("app", "feature", "import", True, 1),),
        entrypoint_candidates=("app",),
        selected_entrypoint="app",
        project_root=str(tmp_path),
        file_hashes=hashes,
    )

    journey = learning_journey(graph, "feature")

    assert journey["status"] == "complete"
    assert journey["runtime_status"] == "not_applicable"
    assert [step["relation"] for step in journey["steps"]] == ["home", "import"]
    assert journey["steps"][-1]["node_id"] == "feature"


def test_missing_home_stops_at_an_explicit_break(tmp_path: Path) -> None:
    digest = _write(tmp_path, "feature.py", "def render():\n    pass\n")
    graph = Graph(
        nodes=(
            _node("feature", kind="module", file="feature.py", line=1, region="feature"),
            _node("feature.render", kind="function", file="feature.py", line=1, region="feature"),
        ),
        edges=(),
        entrypoint_candidates=(),
        selected_entrypoint=None,
        project_root=str(tmp_path),
        file_hashes={"feature.py": digest},
    )

    journey = learning_journey(graph, "feature.render")

    assert journey["status"] == "broken"
    assert journey["steps"] == []
    assert journey["break"]["reason"] == "home-not-selected"
    assert journey["possible_frontier"] == []


def test_partial_target_stops_before_any_route_claim(tmp_path: Path) -> None:
    digest = _write(tmp_path, "feature.py", "def broken(:\n")
    target = replace(
        _node("feature", kind="module", file="feature.py", line=1, region="feature", rank=0),
        partial=True,
    )
    graph = Graph(
        nodes=(target,),
        edges=(),
        entrypoint_candidates=("feature",),
        selected_entrypoint="feature",
        project_root=str(tmp_path),
        file_hashes={"feature.py": digest},
        partial_files=("feature.py",),
    )

    journey = learning_journey(graph, "feature")

    assert journey["status"] == "broken"
    assert journey["steps"] == []
    assert journey["break"]["reason"] == "target-source-partial"


def test_connected_test_roles_are_candidates_not_proof(tmp_path: Path) -> None:
    hashes = {
        "app.py": _write(tmp_path, "app.py", "def main():\n    load()\n"),
        "feature.py": _write(tmp_path, "feature.py", "def load():\n    pass\n"),
        "test_feature.py": _write(tmp_path, "test_feature.py", "def test_load():\n    load()\n"),
    }
    graph = Graph(
        nodes=(
            _node("app", kind="module", file="app.py", line=1, region="app", rank=0),
            _node("app.main", kind="function", file="app.py", line=1, region="app", rank=1),
            _node("feature", kind="module", file="feature.py", line=1, region="feature"),
            _node("feature.load", kind="function", file="feature.py", line=1, region="feature"),
            _node("test_feature", kind="module", file="test_feature.py", line=1, region="test_feature"),
            _node("test_feature.test_load", kind="function", file="test_feature.py", line=1, region="test_feature"),
        ),
        edges=(
            Edge("app.main", "feature.load", "call", True, 2),
            Edge("test_feature.test_load", "feature.load", "call", True, 2),
        ),
        entrypoint_candidates=("app", "app.main"),
        selected_entrypoint="app",
        project_root=str(tmp_path),
        file_hashes=hashes,
        role_evidence=(
            RoleEvidence("app.main", "application-entry", "python.entrypoint.main", "app.py", 1, 1),
            RoleEvidence("test_feature.test_load", "test", "python.test.function-name", "test_feature.py", 1, 1),
        ),
    )

    journey = learning_journey(graph, "feature.load")

    assert journey["status"] == "complete"
    assert journey["verification_candidates"] == [
        {
            "node_id": "test_feature.test_load",
            "name": "test_load",
            "depth": 1,
            "certain": True,
            "role_observation": {
                "file": "test_feature.py",
                "line": 1,
                "citation": "test_feature.py:1",
            },
            "declaration": {
                "file": "test_feature.py",
                "line": 1,
                "citation": "test_feature.py:1",
            },
        }
    ]


def test_a_test_role_cannot_complete_an_application_journey(tmp_path: Path) -> None:
    hashes = {
        "app.py": _write(tmp_path, "app.py", "# Home has no application surface\n"),
        "feature.py": _write(tmp_path, "feature.py", "def load():\n    pass\n"),
        "test_feature.py": _write(
            tmp_path,
            "test_feature.py",
            "def test_load():\n    load()\n",
        ),
    }
    graph = Graph(
        nodes=(
            _node("app", kind="module", file="app.py", line=1, region="app", rank=0),
            _node("feature", kind="module", file="feature.py", line=1, region="feature"),
            _node("feature.load", kind="function", file="feature.py", line=1, region="feature"),
            _node(
                "test_feature",
                kind="module",
                file="test_feature.py",
                line=1,
                region="test_feature",
            ),
            _node(
                "test_feature.test_load",
                kind="function",
                file="test_feature.py",
                line=1,
                region="test_feature",
            ),
        ),
        edges=(Edge("test_feature.test_load", "feature.load", "call", True, 2),),
        entrypoint_candidates=("app",),
        selected_entrypoint="app",
        project_root=str(tmp_path),
        file_hashes=hashes,
        role_evidence=(
            RoleEvidence(
                "test_feature.test_load",
                "test",
                "python.test.function-name",
                "test_feature.py",
                1,
                1,
            ),
        ),
    )

    journey = learning_journey(graph, "feature.load")

    assert journey["status"] == "broken"
    assert journey["application_surface"] is None
    assert journey["break"]["reason"] == "application-surface-not-proven"


def test_possible_import_with_a_certain_tail_is_target_relevant(tmp_path: Path) -> None:
    hashes = {
        "app.py": _write(tmp_path, "app.py", "import bridge\n"),
        "bridge.py": _write(tmp_path, "bridge.py", "import feature\n"),
        "feature.py": _write(tmp_path, "feature.py", "def load():\n    pass\n"),
    }
    graph = Graph(
        nodes=(
            _node("app", kind="module", file="app.py", line=1, region="app", rank=0),
            _node("bridge", kind="module", file="bridge.py", line=1, region="bridge"),
            _node("feature", kind="module", file="feature.py", line=1, region="feature"),
        ),
        edges=(
            Edge("app", "bridge", "import", False, 1),
            Edge("bridge", "feature", "import", True, 1),
        ),
        entrypoint_candidates=("app",),
        selected_entrypoint="app",
        project_root=str(tmp_path),
        file_hashes=hashes,
    )

    journey = learning_journey(graph, "feature")

    assert journey["status"] == "broken"
    assert [(item["source_node_id"], item["target_node_id"]) for item in journey["possible_frontier"]] == [
        ("app", "bridge")
    ]


def test_cycles_and_shuffled_input_do_not_change_the_journey(tmp_path: Path) -> None:
    hashes = {
        "app.py": _write(tmp_path, "app.py", "def main():\n    middle()\n"),
        "feature.py": _write(tmp_path, "feature.py", "def middle():\n    target()\n\ndef target():\n    pass\n"),
    }
    nodes = (
        _node("app", kind="module", file="app.py", line=1, region="app", rank=0),
        _node("app.main", kind="function", file="app.py", line=1, region="app", rank=1),
        _node("feature", kind="module", file="feature.py", line=1, region="feature"),
        _node("feature.middle", kind="function", file="feature.py", line=1, region="feature"),
        _node("feature.target", kind="function", file="feature.py", line=4, region="feature"),
    )
    edges = (
        Edge("app.main", "feature.middle", "call", True, 2),
        Edge("feature.middle", "app.main", "call", True, 2),
        Edge("feature.middle", "feature.target", "call", True, 2),
    )
    role = RoleEvidence("app.main", "application-entry", "python.entrypoint.main", "app.py", 1, 1)

    first = Graph(nodes=nodes, edges=edges, entrypoint_candidates=("app",), selected_entrypoint="app", project_root=str(tmp_path), file_hashes=hashes, role_evidence=(role,))
    second = Graph(nodes=tuple(reversed(nodes)), edges=tuple(reversed(edges)), entrypoint_candidates=("app",), selected_entrypoint="app", project_root=str(tmp_path), file_hashes=dict(reversed(tuple(hashes.items()))), role_evidence=(role,))

    assert learning_journey(first, "feature.target") == learning_journey(second, "feature.target")


def test_supported_scale_is_exhaustive_but_presentation_is_bounded(tmp_path: Path) -> None:
    count = 80
    source = "\n".join(f"def step_{index}(): pass" for index in range(count)) + "\n"
    digest = _write(tmp_path, "app.py", source)
    module = _node("app", kind="module", file="app.py", line=1, region="app", rank=0)
    functions = tuple(
        _node(
            f"app.step_{index}",
            kind="function",
            file="app.py",
            line=index + 1,
            region="app",
            rank=1 if index == 0 else None,
        )
        for index in range(count)
    )
    edges = tuple(
        Edge(f"app.step_{index}", f"app.step_{index + 1}", "call", True, index + 1)
        for index in range(count - 1)
    )
    graph = Graph(
        nodes=(module, *functions),
        edges=edges,
        entrypoint_candidates=("app",),
        selected_entrypoint="app",
        project_root=str(tmp_path),
        file_hashes={"app.py": digest},
        role_evidence=(
            RoleEvidence(
                "app.step_0",
                "application-entry",
                "python.entrypoint.main",
                "app.py",
                1,
                1,
            ),
        ),
    )

    journey = learning_journey(graph, f"app.step_{count - 1}")

    assert journey["status"] == "truncated"
    assert len(journey["steps"]) == 32
    assert journey["omitted_step_count"] == 49
    assert journey["break"]["reason"] == "presentation-limit"
