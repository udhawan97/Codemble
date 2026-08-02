"""Python call resolution: fewer guesses, not more claims.

Measured on this repository before this work, 79% of Python call edges were
unproven -- and the shape mattered more than the number. A call to `.parse()`
emitted one edge to *every* class in the project defining a `parse` method:
nine of them here, 229 call sites each. At most one of those nine is the real
relationship, so the other eight are false edges that inflate centrality (which
drives a star's brightness), pad the impact widget's blast radius, and thicken
the route mesh.

They were labelled possible, so the Correctness Contract was satisfied in the
letter. This is the spirit: a hedge is honest about a relationship that might
exist, not a licence to list nine when the evidence names one.

Nothing here upgrades certainty on a dynamic dispatch. Python resolves methods
at runtime and a subclass may override, so a call through an annotated name
stays *possible* -- it simply names the one class the annotation points at
instead of every class that shares the method name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codemble.adapters.python_ast import PythonAstAdapter


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "base.py").write_text(
        "class Adapter:\n"
        "    def parse(self):\n"
        "        return 1\n"
        "\n"
        "    def shared(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    # A second, unrelated class with the same method names. This is the decoy:
    # name-only matching cannot tell it from the real target.
    (root / "other.py").write_text(
        "class Unrelated:\n"
        "    def parse(self):\n"
        "        return 3\n"
        "\n"
        "    def shared(self):\n"
        "        return 4\n",
        encoding="utf-8",
    )
    (root / "child.py").write_text(
        "from base import Adapter\n"
        "\n"
        "class Child(Adapter):\n"
        "    def run(self):\n"
        "        return self.shared()\n",
        encoding="utf-8",
    )
    (root / "caller.py").write_text(
        "from base import Adapter\n"
        "\n"
        "def annotated(adapter: Adapter):\n"
        "    return adapter.parse()\n"
        "\n"
        "def local():\n"
        "    thing: Adapter = Adapter()\n"
        "    return thing.parse()\n"
        "\n"
        "def unknown(mystery):\n"
        "    return mystery.parse()\n",
        encoding="utf-8",
    )
    return root


def _calls(graph, src: str) -> list:
    return [edge for edge in graph.edges if edge.kind == "call" and edge.src == src]


def test_an_inherited_method_resolves_through_the_base_class(project: Path) -> None:
    """`self.shared()` is defined on the base, not on Child.

    It used to fall past the self-call branch (which only looked at the class's
    own members) into the project-wide name match, so it emitted an edge to
    every `shared` in the project -- including the unrelated one.
    """

    graph = PythonAstAdapter().parse(project)

    edges = _calls(graph, "child.Child.run")

    assert [edge.dst for edge in edges] == ["base.Adapter.shared"]
    assert edges[0].certain is True, "the base class is in the project and declares it once"


def test_an_annotated_parameter_names_one_target_not_every_namesake(
    project: Path,
) -> None:
    graph = PythonAstAdapter().parse(project)

    edges = _calls(graph, "caller.annotated")

    assert [edge.dst for edge in edges] == ["base.Adapter.parse"]
    assert edges[0].certain is False, (
        "Python dispatches on the runtime type and a subclass may override, so "
        "the annotation narrows the target without proving it"
    )


def test_an_annotated_local_narrows_the_same_way(project: Path) -> None:
    graph = PythonAstAdapter().parse(project)

    edges = _calls(graph, "caller.local")

    assert "base.Adapter.parse" in [edge.dst for edge in edges]
    assert "other.Unrelated.parse" not in [edge.dst for edge in edges]


def test_an_unannotated_receiver_still_hedges_across_candidates(
    project: Path,
) -> None:
    """No evidence, no narrowing. This must NOT become quietly confident.

    A call on a name the parser knows nothing about is exactly the case the
    name fallback exists for, and its answer stays the honest one: every
    candidate, all of them possible.
    """

    graph = PythonAstAdapter().parse(project)

    edges = _calls(graph, "caller.unknown")

    assert {edge.dst for edge in edges} == {"base.Adapter.parse", "other.Unrelated.parse"}
    assert all(edge.certain is False for edge in edges)


def test_resolution_is_deterministic(project: Path) -> None:
    first = PythonAstAdapter().parse(project)
    second = PythonAstAdapter().parse(project)

    assert [
        (edge.src, edge.dst, edge.certain) for edge in first.edges
    ] == [(edge.src, edge.dst, edge.certain) for edge in second.edges]


def test_a_cycle_in_the_class_hierarchy_terminates(tmp_path: Path) -> None:
    """Impossible in a runnable program, reachable in a file being edited."""

    root = tmp_path / "cyclic"
    root.mkdir()
    (root / "a.py").write_text(
        "from b import Second\n\nclass First(Second):\n    def go(self):\n        return self.go()\n",
        encoding="utf-8",
    )
    (root / "b.py").write_text(
        "from a import First\n\nclass Second(First):\n    pass\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(root)

    assert graph.nodes, "a cyclic hierarchy must still produce a graph"


def test_the_lens_names_the_python_a_learner_actually_meets(tmp_path: Path) -> None:
    """Five idioms that dominate modern Python and had no note at all.

    They matter most for this product's audience specifically: someone reading
    code an AI wrote for them meets dataclasses, f-strings and Protocols
    constantly, and a lens that stayed silent on all three taught nothing about
    the file in front of them.
    """

    root = tmp_path / "modern"
    root.mkdir()
    (root / "app.py").write_text(
        "from dataclasses import dataclass\n"
        "from typing import Protocol\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Point:\n"
        "    x: int\n"
        "\n"
        "class Reader(Protocol):\n"
        "    def read(self) -> str: ...\n"
        "\n"
        "def describe(value):\n"
        "    match value:\n"
        "        case 1:\n"
        "            pass\n"
        "    if (found := len(str(value))) > 0:\n"
        "        return f'got {found}'\n"
        "    return ''\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(root)
    found = {annotation.concept for annotation in graph.concept_annotations}

    assert {"dataclass", "protocol", "pattern-matching", "f-string", "walrus"} <= found


def test_every_python_concept_the_parser_emits_can_be_taught(tmp_path: Path) -> None:
    """A detected idiom with no note is a fact the learner never receives.

    The adapter and the lens are separate files, so a new concept can ship
    detected and silent -- which is exactly how five of them stayed invisible.
    """

    from codemble.lens import lens_notes

    graph = PythonAstAdapter().parse(Path(__file__).parent.parent / "codemble")
    detected = {annotation.concept for annotation in graph.concept_annotations}
    voiced = {
        note["concept"] for note in lens_notes("python", list(graph.concept_annotations))
    }

    assert detected <= voiced, f"detected but never taught: {sorted(detected - voiced)}"
