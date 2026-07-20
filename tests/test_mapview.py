"""Deterministic 2D map payloads for the learner-facing Map layer."""

from __future__ import annotations

import json
from pathlib import Path

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph import build_map

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def test_map_payload_is_byte_stable_for_one_graph() -> None:
    first = build_map(PythonAstAdapter().parse(FIXTURE))
    second = build_map(PythonAstAdapter().parse(FIXTURE))

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["schema_version"] == 1


def test_architecture_layers_follow_the_longest_import_path_from_home() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    layers = {box["id"]: box["layer"] for box in architecture["boxes"]}

    assert architecture["home"] == "app"
    assert layers["app"] == 0
    assert layers["pkg.helpers"] == 1
    assert layers["pkg.service"] == 1
    # app imports pkg.util directly, but app -> pkg.service -> pkg.util is
    # longer, and the longest path is what puts a module below all its callers.
    assert layers["pkg.util"] == 2
    assert layers["shared"] == 2
    assert architecture["layer_count"] == 4
    assert architecture["unreachable"] == [
        "ambiguous",
        "api",
        "broken",
        "cli",
        "pkg",
        "runner.__main__",
    ]
    assert all(layers[region] == 3 for region in architecture["unreachable"])
    assert all(
        box["reachable"] is False for box in architecture["boxes"] if box["layer"] == 3
    )


def test_architecture_groups_regions_by_source_directory() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    groups = {group["id"]: group["regions"] for group in architecture["groups"]}

    assert list(groups) == [".", "pkg", "runner"]
    assert groups["pkg"] == ["pkg", "pkg.helpers", "pkg.service", "pkg.util"]
    assert groups["runner"] == ["runner.__main__"]


def test_architecture_edges_keep_parser_certainty_and_weight() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    edges = {(edge["src"], edge["dst"]): edge for edge in architecture["edges"]}

    assert edges[("app", "pkg.service")]["certain"] is True
    assert edges[("app", "pkg.service")]["weight"] == 1
    assert all(edge["cycle"] is False for edge in architecture["edges"])


def test_workflow_expands_the_entrypoint_and_names_every_relation() -> None:
    workflow = build_map(PythonAstAdapter().parse(FIXTURE))["workflow"]
    rows = [
        (row["id"], row["depth"], row["relation"], row["certain"], row["cut"])
        for row in workflow["nodes"]
    ]

    assert workflow["root"] == "app"
    assert rows[0] == ("app", 0, "root", True, None)
    # The parser never observed a call from the module to its own function, so
    # the first hop is containment and is labelled as such -- never as a call.
    assert rows[1] == ("app.main", 1, "defines", True, None)
    assert ("pkg.service.Service.run", 2, "calls", False, None) in rows
    assert ("pkg.util.normalize", 3, "calls", True, None) in rows
    assert ("pkg.util.normalize", 3, "calls", True, "repeat") in rows
    assert workflow["depth_count"] == 4
    assert "ambiguous.invoke" in workflow["unreachable"]
    assert "app.main" not in workflow["unreachable"]


def test_cycles_are_cut_deterministically_and_stay_visible(tmp_path: Path) -> None:
    (tmp_path / "alpha.py").write_text(
        "import beta\n\n\ndef ping() -> None:\n    beta.pong()\n\n\n"
        'if __name__ == "__main__":\n    ping()\n',
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text(
        "import alpha\n\n\ndef pong() -> None:\n    alpha.ping()\n",
        encoding="utf-8",
    )

    payload = build_map(PythonAstAdapter().parse(tmp_path))
    repeated = build_map(PythonAstAdapter().parse(tmp_path))
    architecture = payload["architecture"]

    assert json.dumps(payload, sort_keys=True) == json.dumps(repeated, sort_keys=True)
    assert [edge["cycle"] for edge in architecture["edges"]].count(True) == 1
    # A cut edge is still drawn and still carries its parser certainty.
    assert all(edge["certain"] for edge in architecture["edges"])
    assert "cycle" in [row["cut"] for row in payload["workflow"]["nodes"]]


def test_a_graph_without_home_marks_every_region_unreachable(tmp_path: Path) -> None:
    (tmp_path / "solo.py").write_text("def work() -> None:\n    pass\n", encoding="utf-8")

    payload = build_map(PythonAstAdapter().parse(tmp_path))

    assert payload["architecture"]["home"] is None
    assert payload["architecture"]["unreachable"] == ["solo"]
    assert payload["architecture"]["layer_count"] == 1
    assert payload["workflow"]["root"] is None
    assert payload["workflow"]["nodes"] == []
    assert payload["workflow"]["unreachable"] == ["solo", "solo.work"]
