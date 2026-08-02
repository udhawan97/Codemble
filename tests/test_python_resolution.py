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


def test_a_projects_own_entrypoint_outranks_its_test_suite(tmp_path: Path) -> None:
    """Home is chosen for the learner when one candidate clearly wins.

    Measured on this repository before this rule: seven candidates, five of
    them test fixtures, and three tied at rank 0 -- so no Home could be
    selected and a first-run learner was handed a picker whose list was mostly
    `tests/`. The project's own entry was in there, indistinguishable.

    Test-scoped candidates are demoted rather than dropped: a project that IS
    a test suite still needs somewhere to start, and removing them outright
    would leave such a project with no Home at all. Same reasoning as the Easy
    guidance penalty (Decision Log, 2026-07-22).
    """

    root = tmp_path / "app"
    (root / "tests").mkdir(parents=True)
    (root / "cli.py").write_text(
        "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (root / "tests" / "harness.py").write_text(
        "def main():\n    return 2\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(root)

    ranks = {
        node.id: node.entrypoint_rank
        for node in graph.nodes
        if node.entrypoint_rank is not None
    }
    assert ranks["cli"] < ranks["tests.harness"], "the project's own entry must win"
    assert graph.selected_entrypoint == "cli", (
        "one unambiguous best candidate means the learner is never asked"
    )


def test_an_all_tests_project_still_gets_a_home(tmp_path: Path) -> None:
    """Demotion, not exclusion. A test-only project must still be explorable."""

    root = tmp_path / "suite"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "harness.py").write_text(
        "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(root)

    assert any(node.entrypoint_rank is not None for node in graph.nodes)


def _framework_project(tmp_path: Path, name: str, body: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / "service.py").write_text(body, encoding="utf-8")
    (root / "helper.py").write_text("def util():\n    return 1\n", encoding="utf-8")
    return root


def test_an_app_object_counts_whatever_the_variable_is_called(tmp_path: Path) -> None:
    """The factory is the evidence; the variable name is a naming convention.

    Detection required the variable to be literally named `app`, so
    `srv = Flask(__name__)` and `cli = typer.Typer()` ranked nowhere at all --
    a project's real entrypoint invisible because its author chose a different
    word.
    """

    flask = _framework_project(
        tmp_path,
        "flask_app",
        "from flask import Flask\nsrv = Flask(__name__)\n\n@srv.route('/')\ndef index():\n    return 'x'\n",
    )
    typer_cli = _framework_project(
        tmp_path,
        "typer_app",
        "import typer\ncli = typer.Typer()\n\n@cli.command()\ndef run():\n    return 1\n",
    )

    for root in (flask, typer_cli):
        graph = PythonAstAdapter().parse(root)
        ranked = {
            node.id for node in graph.nodes if node.entrypoint_rank is not None
        }
        assert "service" in ranked, f"{root.name}: the app module must be a candidate"


def test_a_decorated_command_makes_its_module_an_entrypoint(tmp_path: Path) -> None:
    """A click CLI has no app object at all -- the decorator is the evidence."""

    root = _framework_project(
        tmp_path,
        "click_app",
        "import click\n\n@click.command()\ndef start():\n    return 1\n",
    )

    graph = PythonAstAdapter().parse(root)

    assert any(
        node.id == "service" and node.entrypoint_rank is not None
        for node in graph.nodes
    )


def test_one_best_candidate_is_chosen_whatever_its_rank(tmp_path: Path) -> None:
    """Home used to require a rank-ZERO candidate to auto-select.

    A web service frequently has no `__main__` guard at all, so its only
    candidate sat at the app-object rank and Home resolved to nothing -- the
    learner met the picker holding a single option. If exactly one candidate is
    the best available, there is no question to ask.
    """

    root = _framework_project(
        tmp_path,
        "service_only",
        "from fastapi import FastAPI\napi = FastAPI()\n\n@api.get('/health')\ndef health():\n    return {}\n",
    )

    graph = PythonAstAdapter().parse(root)

    assert graph.selected_entrypoint == "service"


def test_a_genuine_tie_still_asks(tmp_path: Path) -> None:
    """Two equally good candidates is a learner decision, not a guess."""

    root = tmp_path / "two_entries"
    root.mkdir()
    for name in ("first", "second"):
        (root / f"{name}.py").write_text(
            "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )

    graph = PythonAstAdapter().parse(root)

    assert graph.selected_entrypoint is None
