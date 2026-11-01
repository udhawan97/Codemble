"""Repeated declarations retain their own spans without inventing active bindings."""

from pathlib import Path

import pytest

from codemble.adapters.python_ast import PythonAstAdapter


@pytest.mark.parametrize("source, caller, lines", [
    (
        (
            "def work():\n    return 1\ndef work():\n    return 2\n"
            "def main():\n    return work()\n"
        ),
        "app.main", [1, 3],
    ),
    (
        (
            "def main():\n    def work():\n        return 1\n    work()\n"
            "    def work():\n        return 2\n    work()\n"
        ),
        "app.main", [2, 5],
    ),
    (
        (
            "if flag:\n    def work():\n        return 1\n"
            "else:\n    def work():\n        return 2\n"
            "def main():\n    return work()\n"
        ),
        "app.main", [2, 5],
    ),
    (
        (
            "from typing import overload\n@overload\ndef work(x: int): ...\n"
            "@overload\ndef work(x: str): ...\ndef work(x):\n    return x\n"
            "def main():\n    return work(1)\n"
        ),
        "app.main", [3, 5, 6],
    ),
    (
        (
            "class Worker:\n    def work(self):\n        return 1\n"
            "    def work(self):\n        return 2\n"
            "    def main(self):\n        return self.work()\n"
        ),
        "app.Worker.main", [2, 4],
    ),
])
def test_repeated_definitions_keep_spans_and_uncertain_ownership(
    tmp_path: Path, source: str, caller: str, lines: list[int],
) -> None:
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    graph = PythonAstAdapter().parse(tmp_path)
    declarations = [node for node in graph.nodes if node.name == "work"]
    assert sorted(node.lineno for node in declarations) == lines
    assert len({node.id for node in declarations}) == len(lines)
    calls = [edge for edge in graph.edges if edge.src == caller and edge.kind == "call"]
    assert calls
    assert not any(edge.certain and edge.dst in {node.id for node in declarations} for edge in calls)
    assert graph.to_json() == PythonAstAdapter().parse(tmp_path).to_json()


def test_duplicate_parent_definitions_keep_children_in_their_actual_owner(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "class Worker:\n    def work(self):\n        def local():\n            return 1\n"
        "        return local()\n"
        "class Worker:\n    def work(self):\n        def local():\n            return 2\n"
        "        return local()\n",
        encoding="utf-8",
    )
    graph = PythonAstAdapter().parse(tmp_path)
    workers = [node for node in graph.nodes if node.name == "Worker"]
    methods = [node for node in graph.nodes if node.name == "work"]
    locals_ = [node for node in graph.nodes if node.name == "local"]
    assert len(workers) == len(methods) == len(locals_) == 2
    for method in methods:
        target = next(node for node in locals_ if node.lineno == method.lineno + 1)
        calls = [edge for edge in graph.edges if edge.kind == "call" and edge.src == method.id]
        assert [(edge.dst, edge.certain) for edge in calls] == [(target.id, True)]


def test_single_declarations_keep_existing_ids_and_certain_binding(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def work():\n    return 1\ndef main():\n    return work()\n",
        encoding="utf-8",
    )
    graph = PythonAstAdapter().parse(tmp_path)
    assert {node.id for node in graph.nodes} == {"app", "app.work", "app.main"}
    assert any(edge.src == "app.main" and edge.dst == "app.work" and edge.certain for edge in graph.edges)


def test_duplicate_declarations_cannot_supply_journey_or_check_proof(tmp_path: Path) -> None:
    from codemble.checks import generate_checks
    from codemble.graph.learning import learning_journey

    (tmp_path / "app.py").write_text(
        "def work():\n    return 1\ndef work():\n    return 2\n"
        "def main():\n    return work()\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    graph = PythonAstAdapter().parse(tmp_path)
    targets = {node.id for node in graph.nodes if node.name == "work"}
    assert len(targets) == 2
    assert all(learning_journey(graph, target)["status"] != "complete" for target in targets)
    assert not any(
        targets.intersection(question.answer_ids)
        for question in generate_checks(graph, "app")
        if question.kind in {"first-call", "direct-call"}
    )
