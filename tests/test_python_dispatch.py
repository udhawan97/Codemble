"""Python dispatch proof must remain sound through journeys and check grading."""

import subprocess
import sys
from pathlib import Path

import pytest

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.checks import CheckService, generate_checks
from codemble.graph.learning import learning_journey
from codemble.llm.study import StudyService
from codemble.progress import ProgressStore


def _parse(root: Path, files: dict[str, str]):
    root.mkdir()
    for name, source in files.items():
        (root / name).write_text(source, encoding="utf-8")
    return PythonAstAdapter().parse(root)


def _runtime(root: Path) -> str:
    return subprocess.run(
        [sys.executable, "-c", "import app; print(app.main())"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _assert_no_false_proof(graph, root: Path, caller: str, wrong: str, actual: str) -> None:
    calls = [edge for edge in graph.edges if edge.kind == "call" and edge.src == caller]
    assert any(edge.dst == actual and not edge.certain for edge in calls)
    assert not any(edge.dst == wrong and edge.certain for edge in calls)
    assert learning_journey(graph, wrong)["status"] != "complete"
    assert learning_journey(graph, actual)["status"] != "complete"
    region = next(node.region for node in graph.nodes if node.id == caller)
    checks = CheckService(graph, ProgressStore(graph, root.parent / "progress"))
    for question in generate_checks(graph, region):
        if question.kind == "direct-call":
            assert wrong not in question.answer_ids
            if wrong in {option.id for option in question.options}:
                assert checks.submit(region, question.id, [wrong])["correct"] is False
    study = StudyService(graph, cache_root=root.parent / "cache")
    assert study.explain(caller)["status"] == "no_key"
    assert not any(
        neighbor["node_id"] == wrong and neighbor["certain"]
        for neighbor in study.study(caller)["neighbors"]
    )


@pytest.mark.parametrize("kind", ["instance", "class", "static", "nested", "later_parameter"])
def test_virtual_receivers_cannot_supply_certain_journey_or_check_proof(tmp_path, kind):
    if kind == "class":
        methods = (
            '    @classmethod\n    def run(cls):\n        return cls.work()\n'
            '    @classmethod\n    def work(cls):\n        return "BASE"\n'
        )
        child = 'class B(A):\n    @classmethod\n    def work(cls):\n        return "CHILD"\n'
        main = 'def main():\n    return B.run()\n'
        caller = "app.A.run"
    elif kind == "static":
        methods = (
            '    @staticmethod\n    def run(self):\n        return self.work()\n'
            '    def work(self):\n        return "BASE"\n'
        )
        child = 'class B:\n    def work(self):\n        return "CHILD"\n'
        main = 'def main():\n    return A.run(B())\n'
        caller = "app.A.run"
    elif kind == "nested":
        methods = (
            '    def run(self):\n        def nested(self):\n            return self.work()\n'
            '        return nested(B())\n    def work(self):\n        return "BASE"\n'
        )
        child = 'class B:\n    def work(self):\n        return "CHILD"\n'
        main = 'def main():\n    return A().run()\n'
        caller = "app.A.run.nested"
    elif kind == "later_parameter":
        methods = (
            '    def run(owner, self):\n        return self.work()\n'
            '    def work(self):\n        return "BASE"\n'
        )
        child = 'class B:\n    def work(self):\n        return "CHILD"\n'
        main = 'def main():\n    return A().run(B())\n'
        caller = "app.A.run"
    else:
        methods = (
            '    def run(self):\n        return self.work()\n'
            '    def work(self):\n        return "BASE"\n'
        )
        child = 'class B(A):\n    def work(self):\n        return "CHILD"\n'
        main = 'def main():\n    return B().run()\n'
        caller = "app.A.run"
    root = tmp_path / "project"
    graph = _parse(root, {"app.py": 'class A:\n' + methods + child + main})
    assert _runtime(root) == "CHILD"
    _assert_no_false_proof(graph, root, caller, "app.A.work", "app.B.work")


def test_imported_subclass_keeps_relevant_possible_targets_without_namesake_fanout(tmp_path):
    root = tmp_path / "project"
    graph = _parse(root, {
        "base.py": (
            'class A:\n    def run(self):\n        return self.work()\n'
            '    def work(self):\n        return "BASE"\n'
        ),
        "child.py": (
            'from base import A\nclass B(A):\n    def work(self):\n        return "CHILD"\n'
        ),
        "other.py": 'class Unrelated:\n    def work(self):\n        return "OTHER"\n',
        "app.py": 'from child import B\ndef main():\n    return B().run()\n',
    })
    assert _runtime(root) == "CHILD"
    assert {
        edge.dst for edge in graph.edges if edge.kind == "call" and edge.src == "base.A.run"
    } == {"base.A.work", "child.B.work"}
    _assert_no_false_proof(graph, root, "base.A.run", "base.A.work", "child.B.work")


@pytest.mark.parametrize("bases, y_base, actual, wrong", [
    ("X, Y", "", "app.Base.work", "app.Y.work"),
    ("Y, X", "", "app.Y.work", "app.Base.work"),
    ("X, Y", "(Base)", "app.Y.work", "app.Base.work"),
])
def test_multiple_inheritance_never_promotes_breadth_first_lookup_to_proof(
    tmp_path, bases, y_base, actual, wrong,
):
    root = tmp_path / "project"
    graph = _parse(root, {"app.py": (
        'class Base:\n    def work(self):\n        return "BASE"\n'
        'class X(Base):\n    pass\n'
        f'class Y{y_base}:\n    def work(self):\n        return "Y"\n'
        f'class C({bases}):\n    pass\ndef main():\n    return C().work()\n'
    )})
    assert _runtime(root) == ("BASE" if actual == "app.Base.work" else "Y")
    method_calls = [
        edge for edge in graph.edges if edge.src == "app.main" and edge.dst.endswith(".work")
    ]
    assert {edge.dst for edge in method_calls} == {"app.Base.work", "app.Y.work"}
    assert all(not edge.certain for edge in method_calls)
    _assert_no_false_proof(graph, root, "app.main", wrong, actual)


@pytest.mark.parametrize("hierarchy", [
    'from missing_package import External\nclass C(External, Base):\n    pass\n',
    'from missing_package import External\nclass C(Base, External):\n    pass\n',
    'class C(Base, unknown_factory()):\n    pass\n',
    'class C(Base):\n    pass\nclass Base(C):\n    pass\n',
])
def test_incomplete_or_repeated_base_identity_cannot_prove_a_constructor_member(
    tmp_path, hierarchy,
):
    graph = _parse(tmp_path / "project", {"app.py": (
        'class Base:\n    def work(self):\n        return "BASE"\n' + hierarchy
        + 'def main():\n    return C().work()\n'
    )})
    methods = [edge for edge in graph.edges if edge.src == "app.main" and ".work" in edge.dst]
    assert methods
    assert all(not edge.certain for edge in methods)


def test_a_cycle_with_unique_class_ids_stays_uncertain_and_terminates(tmp_path):
    graph = _parse(tmp_path / "project", {"app.py": (
        'class A(B):\n    def work(self):\n        return 1\n'
        'class B(A):\n    pass\ndef main():\n    return B().work()\n'
    )})
    methods = [edge for edge in graph.edges if edge.src == "app.main" and edge.dst == "app.A.work"]
    assert methods and all(not edge.certain for edge in methods)


def test_rebound_base_name_is_not_restored_to_its_earlier_class(tmp_path):
    root = tmp_path / "project"
    graph = _parse(root, {"app.py": (
        'class Base:\n    def work(self):\n        return "BASE"\n'
        'class Other:\n    def work(self):\n        return "OTHER"\n'
        'Base = Other\nclass C(Base):\n    pass\ndef main():\n    return C().work()\n'
    )})
    assert _runtime(root) == "OTHER"
    _assert_no_false_proof(graph, root, "app.main", "app.Base.work", "app.Other.work")


@pytest.mark.parametrize("base_expression", ["factory().Base", "holders[0].Base"])
def test_dynamic_attribute_base_does_not_borrow_a_local_class_name(tmp_path, base_expression):
    root = tmp_path / "project"
    graph = _parse(root, {"app.py": (
        'class Base:\n    def work(self):\n        return "BASE"\n'
        'class Other:\n    def work(self):\n        return "OTHER"\n'
        'class Holder:\n    Base = Other\ndef factory():\n    return Holder\n'
        'holders = [Holder]\n'
        f'class C({base_expression}):\n    pass\ndef main():\n    return C().work()\n'
    )})
    assert _runtime(root) == "OTHER"
    _assert_no_false_proof(graph, root, "app.main", "app.Base.work", "app.Other.work")


@pytest.mark.parametrize("dotted", [False, True])
def test_exact_functions_and_single_inheritance_constructor_calls_remain_certain(tmp_path, dotted):
    root = tmp_path / "project"
    import_line = "import base" if dotted else "from base import Base"
    base = "base.Base" if dotted else "Base"
    graph = _parse(root, {
        "base.py": 'class Base:\n    def work(self):\n        return "BASE"\n',
        "app.py": (
            f'{import_line}\nclass C({base}):\n    pass\n'
            'def helper():\n    return C().work()\ndef main():\n    return helper()\n'
        ),
    })
    assert _runtime(root) == "BASE"
    assert any(
        edge.src == "app.main" and edge.dst == "app.helper" and edge.certain
        for edge in graph.edges
    )
    assert any(
        edge.src == "app.helper" and edge.dst == "base.Base.work" and edge.certain
        for edge in graph.edges
    )
    assert learning_journey(graph, "base.Base.work")["status"] == "complete"
