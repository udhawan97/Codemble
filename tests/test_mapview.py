"""Deterministic 2D map payloads for the learner-facing Map layer."""

from __future__ import annotations

import json
from pathlib import Path

from codemble.adapters.base import Edge, Graph, Node
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph import build_map, finalize_graph
from codemble.graph.mapview import MAP_SCHEMA_VERSION, _MAX_COLUMNS

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def test_map_payload_is_byte_stable_for_one_graph() -> None:
    first = build_map(PythonAstAdapter().parse(FIXTURE))
    second = build_map(PythonAstAdapter().parse(FIXTURE))

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["schema_version"] == 3
    assert MAP_SCHEMA_VERSION == 3
    assert all(len(edge["points"]) >= 2 for edge in first["architecture"]["edges"])


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


def test_box_short_label_names_the_file_not_the_dotted_region_id() -> None:
    """A fixed-width box truncates, so what it truncates has to be the useful end.

    ``codemble.server.app`` and ``codemble.server.runtime`` both rendered as
    ``codemble.server…`` -- two different modules showing identical text, which
    is worse than no label. The last two path segments fit the box and tell
    them apart, while ``label`` keeps the full identifier for title and aria.
    """

    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    short = {box["id"]: box["short_label"] for box in architecture["boxes"]}
    full = {box["id"]: box["label"] for box in architecture["boxes"]}

    assert short["pkg.service"] == "pkg/service.py"
    assert short["pkg.util"] == "pkg/util.py"
    assert short["app"] == "app.py", "a top-level file has no parent to prefix"
    assert full["pkg.service"] == "pkg.service", "the full identity is still carried"
    assert len({short["pkg.service"], short["pkg.util"], short["pkg.helpers"]}) == 3


def test_short_labels_disambiguate_files_that_share_a_basename() -> None:
    """Two packages, two __init__.py: the case a basename alone cannot survive."""

    graph = finalize_graph(
        Graph(
            nodes=(
                Node(
                    id="pkg.alpha",
                    kind="module",
                    name="alpha",
                    language="python",
                    file="pkg/alpha/__init__.py",
                    lineno=1,
                    end_lineno=1,
                    loc=1,
                    region="pkg.alpha",
                ),
                Node(
                    id="pkg.beta",
                    kind="module",
                    name="beta",
                    language="python",
                    file="pkg/beta/__init__.py",
                    lineno=1,
                    end_lineno=1,
                    loc=1,
                    region="pkg.beta",
                ),
            ),
            edges=(),
            entrypoint_candidates=(),
            project_root="/project",
            file_hashes={"pkg/alpha/__init__.py": "a", "pkg/beta/__init__.py": "b"},
        )
    )
    boxes = {box["id"]: box["short_label"] for box in build_map(graph)["architecture"]["boxes"]}

    assert boxes == {"pkg.alpha": "alpha/__init__.py", "pkg.beta": "beta/__init__.py"}


def test_architecture_edges_keep_parser_certainty_and_weight() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    edges = {(edge["src"], edge["dst"]): edge for edge in architecture["edges"]}

    assert edges[("app", "pkg.service")]["certain"] is True
    assert edges[("app", "pkg.service")]["weight"] == 1
    assert all(edge["cycle"] is False for edge in architecture["edges"])
    assert all(len(edge["points"]) >= 2 for edge in architecture["edges"])


def test_barycenter_order_strictly_reduces_adjacent_layer_crossings() -> None:
    graph = _module_graph(
        ("a0", "a1", "a2", "b0", "b1", "b2"),
        (("a0", "b2"), ("a1", "b1"), ("a2", "b0")),
    )
    architecture = build_map(graph)["architecture"]
    boxes = {box["id"]: box for box in architecture["boxes"]}
    seeded = {region_id: index for index, region_id in enumerate(("a0", "a1", "a2"))}
    seeded.update({region_id: index for index, region_id in enumerate(("b0", "b1", "b2"))})
    final = {region_id: box["column"] for region_id, box in boxes.items()}
    edges = (("a0", "b2"), ("a1", "b1"), ("a2", "b0"))

    assert _crossings(edges, final) < _crossings(edges, seeded)
    assert _crossings(edges, final) == 0


def test_outgoing_edges_use_distinct_bottom_ports() -> None:
    graph = _module_graph(
        ("source", "target0", "target1", "target2"),
        (("source", "target0"), ("source", "target1"), ("source", "target2")),
    )
    architecture = build_map(graph)["architecture"]
    source = next(box for box in architecture["boxes"] if box["id"] == "source")
    starts = [
        tuple(edge["points"][0])
        for edge in architecture["edges"]
        if edge["src"] == "source"
    ]

    assert len(starts) == len(set(starts)) == 3
    assert all(y == source["y"] + source["height"] for _, y in starts)
    assert all(source["x"] < x < source["x"] + source["width"] for x, _ in starts)


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
    cycle = next(edge for edge in architecture["edges"] if edge["cycle"])
    assert min(point[0] for point in cycle["points"]) < 0 or max(
        point[0] for point in cycle["points"]
    ) > architecture["width"]
    assert "cycle" in [row["cut"] for row in payload["workflow"]["nodes"]]


def test_architecture_geometry_has_no_overlaps_or_edge_through_boxes() -> None:
    architecture = build_map(PythonAstAdapter().parse(FIXTURE))["architecture"]
    boxes = architecture["boxes"]

    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            assert not _boxes_overlap(first, second)

    box_by_id = {box["id"]: box for box in boxes}
    for edge in architecture["edges"]:
        assert edge["src"] in box_by_id and edge["dst"] in box_by_id
        for start, end in zip(edge["points"], edge["points"][1:]):
            assert start[0] == end[0] or start[1] == end[1]
            for box in boxes:
                if box["id"] in {edge["src"], edge["dst"]}:
                    continue
                assert not _segment_crosses_box_interior(start, end, box)


def test_a_graph_without_home_layers_from_the_modules_nothing_imports(
    tmp_path: Path,
) -> None:
    # Without a Home there is no root to measure import depth from.  Seeding
    # nothing put every region in one row, so a real project's modules became a
    # single line wider than the canvas -- unreadable, and mostly clipped away.
    # The import DAG's own sources are parser evidence too, so they layer it.
    (tmp_path / "leaf.py").write_text("def work() -> None:\n    pass\n", encoding="utf-8")
    (tmp_path / "middle.py").write_text(
        "import leaf\n\n\ndef go() -> None:\n    leaf.work()\n", encoding="utf-8"
    )
    (tmp_path / "top.py").write_text(
        "import middle\n\n\ndef run() -> None:\n    middle.go()\n", encoding="utf-8"
    )

    payload = build_map(PythonAstAdapter().parse(tmp_path))
    architecture = payload["architecture"]
    layers = {box["id"]: box["layer"] for box in architecture["boxes"]}

    assert architecture["home"] is None
    # "top" is the source: nothing in the project imports it.
    assert layers == {"top": 0, "middle": 1, "leaf": 2}
    assert architecture["layer_count"] == 3
    # Nothing is stranded, and no region is dropped to say so.
    assert architecture["unreachable"] == []
    assert len(architecture["boxes"]) == 3
    # The workflow tree still needs a real entrypoint and must not invent one.
    assert payload["workflow"]["root"] is None
    assert payload["workflow"]["nodes"] == []


def test_a_layer_wider_than_the_canvas_wraps_instead_of_overflowing(
    tmp_path: Path,
) -> None:
    # Regression: rows were centred on a fixed 960-wide canvas but never sized
    # to it, so a layer of more than _MAX_COLUMNS modules ran off both edges.
    # The SVG root clips outside the viewBox and the element is width:100%, so
    # the overflow was invisible AND unscrollable -- parser evidence silently
    # hidden.  These siblings share no imports, so they all land on layer 0.
    count = _MAX_COLUMNS * 2 + 1
    for index in range(count):
        (tmp_path / f"mod{index:02d}.py").write_text(
            "def work() -> None:\n    pass\n", encoding="utf-8"
        )

    architecture = build_map(PythonAstAdapter().parse(tmp_path))["architecture"]
    boxes = architecture["boxes"]

    assert len(boxes) == count
    assert {box["layer"] for box in boxes} == {0}
    # One layer, but drawn across three rows rather than one clipped line.
    assert len({box["y"] for box in boxes}) == 3
    # Every box sits inside the declared canvas, which is what the viewBox uses.
    assert all(0 <= box["x"] and box["x"] + box["width"] <= architecture["width"] for box in boxes)
    assert all(box["y"] + box["height"] <= architecture["height"] for box in boxes)
    # No row is overfilled, and the canvas grew to cover the wrapped rows.
    assert all(box["column"] < _MAX_COLUMNS for box in boxes)
    assert architecture["height"] == 3 * 120.0


def test_workflow_places_a_member_at_top_level_when_only_a_possible_call_claims_it(
    tmp_path: Path,
) -> None:
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

    workflow = build_map(PythonAstAdapter().parse(tmp_path))["workflow"]
    defines = {
        row["id"]: (row["parent"], row["depth"], row["certain"])
        for row in workflow["nodes"]
        if row["relation"] == "defines"
    }
    calls_hops = [
        (row["id"], row["parent"], row["certain"], row["cut"])
        for row in workflow["nodes"]
        if row["relation"] == "calls"
    ]

    # "helper()" is unqualified and resolved only by whole-project name lookup
    # (no import, no lexical match) -- a "possible" call, never proven.  A
    # possible call must not steal the module's certain containment claim on
    # its own member (mirrors layout.py's _call_depths, which excludes
    # certain=False edges from deciding orbit placement), so Box.helper still
    # gets a top-level "defines" row straight from the module.
    assert defines["workmod.Box.helper"] == ("workmod", 1, True)

    # The possible call itself must stay visible as a real relationship, not
    # be silently dropped now that it no longer decides placement.
    assert ("workmod.Box.helper", "workmod.caller", False, "repeat") in calls_hops
    assert workflow["unreachable"] == []


def test_workflow_prefers_a_certain_edge_when_a_pair_has_mixed_certainty(
    tmp_path: Path,
) -> None:
    (tmp_path / "greet.py").write_text("def hello() -> None:\n    pass\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import greet\n"
        "\n"
        "\n"
        "def run() -> None:\n"
        "    hello()\n"
        "    greet.hello()\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    run()\n",
        encoding="utf-8",
    )

    workflow = build_map(PythonAstAdapter().parse(tmp_path))["workflow"]
    hello_rows = [row for row in workflow["nodes"] if row["id"] == "greet.hello"]

    # Line 5's "hello()" is unqualified and only resolves by whole-project name
    # lookup -- possible, not proven.  Line 6's "greet.hello()" is the same
    # (src, dst) pair resolved as a certain, import-qualified call.  Dedup must
    # keep the pair's proven edge rather than whichever sorts first by line.
    assert len(hello_rows) == 1
    assert hello_rows[0]["certain"] is True


def test_workflow_survives_a_deep_unbranching_call_chain(tmp_path: Path) -> None:
    # Regression: the inner walk() in _workflow used to recurse once per call
    # hop, so a deep, unbranching chain blew CPython's default recursion limit
    # (empirically: 700-deep built fine, 1021-deep raised RecursionError).
    # 1500 sits comfortably past that failure point.
    depth = 1500
    body = [f"def f{i}() -> None:\n    f{i + 1}()\n\n\n" for i in range(depth - 1)]
    body.append(f"def f{depth - 1}() -> None:\n    pass\n\n\n")
    body.append('if __name__ == "__main__":\n    f0()\n')
    (tmp_path / "chain.py").write_text("".join(body), encoding="utf-8")

    workflow = build_map(PythonAstAdapter().parse(tmp_path))["workflow"]

    assert workflow["root"] == "chain"
    assert workflow["depth_count"] == depth + 1
    assert len(workflow["nodes"]) == depth + 1
    assert workflow["unreachable"] == []
    last = next(row for row in workflow["nodes"] if row["id"] == f"chain.f{depth - 1}")
    assert last["depth"] == depth
    assert last["cut"] is None


def _module_graph(
    region_ids: tuple[str, ...], routes: tuple[tuple[str, str], ...]
) -> Graph:
    nodes = tuple(
        Node(
            id=region_id,
            kind="module",
            name=region_id,
            language="python",
            file=f"src/{region_id}.py",
            lineno=1,
            end_lineno=1,
            loc=1,
            region=region_id,
        )
        for region_id in region_ids
    )
    edges = tuple(Edge(src, dst, "import", True, 1) for src, dst in routes)
    return finalize_graph(
        Graph(
            nodes=nodes,
            edges=edges,
            entrypoint_candidates=(),
            project_root="/project",
            file_hashes={f"src/{region_id}.py": region_id for region_id in region_ids},
        )
    )


def _crossings(
    edges: tuple[tuple[str, str], ...], positions: dict[str, int]
) -> int:
    return sum(
        (positions[src_a] - positions[src_b]) * (positions[dst_a] - positions[dst_b]) < 0
        for index, (src_a, dst_a) in enumerate(edges)
        for src_b, dst_b in edges[index + 1 :]
    )


def _boxes_overlap(first: dict[str, object], second: dict[str, object]) -> bool:
    return not (
        float(first["x"]) + float(first["width"]) <= float(second["x"])
        or float(second["x"]) + float(second["width"]) <= float(first["x"])
        or float(first["y"]) + float(first["height"]) <= float(second["y"])
        or float(second["y"]) + float(second["height"]) <= float(first["y"])
    )


def _segment_crosses_box_interior(
    start: list[float], end: list[float], box: dict[str, object]
) -> bool:
    left = float(box["x"])
    right = left + float(box["width"])
    top = float(box["y"])
    bottom = top + float(box["height"])
    if start[0] == end[0]:
        return left < start[0] < right and max(min(start[1], end[1]), top) < min(
            max(start[1], end[1]), bottom
        )
    if start[1] == end[1]:
        return top < start[1] < bottom and max(min(start[0], end[0]), left) < min(
            max(start[0], end[0]), right
        )
    raise AssertionError("backend routes must be orthogonal")
