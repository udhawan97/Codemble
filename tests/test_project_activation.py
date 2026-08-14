"""Project activation owns parse lifetime, binding, release, and live caches."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from codemble.adapters.base import Graph
from codemble.adapters.project import ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.server.project_activation import (
    ProjectActivation,
    ProjectActivationBusy,
    ProjectUnavailable,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def _inline_runner(work):  # type: ignore[no-untyped-def]
    work()


def test_initial_graph_is_immediately_active_and_renderable() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    activation = ProjectActivation(graph)

    project = activation.project()

    assert activation.bound is True
    assert activation.accepting_selection is False
    assert activation.progress()["state"] == "ready"
    assert '"regions"' in project.graph_json()
    assert '"architecture"' in project.map_json()


def test_selected_folder_becomes_one_live_project_through_the_parse_job() -> None:
    activation = ProjectActivation(parse_runner=_inline_runner)

    assert activation.accepting_selection is True
    activation.activate(FIXTURE)

    assert activation.bound is True
    assert activation.progress()["state"] == "ready"
    assert activation.progress()["files_done"] > 0
    assert '"regions"' in activation.project().graph_json()


def test_release_rearms_activation_without_leaking_the_previous_project() -> None:
    activation = ProjectActivation(parse_runner=_inline_runner)
    activation.activate(FIXTURE)

    activation.release()

    assert activation.bound is False
    assert activation.progress()["state"] == "idle"
    with pytest.raises(ProjectUnavailable, match="No project selected"):
        activation.project()
    activation.activate(FIXTURE)
    assert activation.bound is True


def test_release_reuses_the_injected_project_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = ProjectParser((PythonAstAdapter(),))
    parse_candidate = parser.parse_candidate
    calls: list[ProjectParser] = []

    def recording_parse_candidate(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        calls.append(parser)
        return parse_candidate(*args, **kwargs)

    monkeypatch.setattr(parser, "parse_candidate", recording_parse_candidate)
    activation = ProjectActivation(parser=parser, parse_runner=_inline_runner)

    activation.activate(FIXTURE)
    activation.release()
    activation.activate(FIXTURE)

    assert calls == [parser, parser]


def test_release_timeout_cannot_bind_or_cache_the_cancelled_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a.py").write_text("A = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("B = 2\n", encoding="utf-8")
    entered_second_read = threading.Event()
    release_second_read = threading.Event()
    original_read_bytes = Path.read_bytes

    def blocking_read(path: Path) -> bytes:
        if path.parent == tmp_path and path.name == "b.py":
            entered_second_read.set()
            assert release_second_read.wait(timeout=5)
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", blocking_read)
    parser = ProjectParser((PythonAstAdapter(),))
    activation = ProjectActivation(parser=parser)
    activation.activate(tmp_path)
    cancelled_job = activation._job
    assert entered_second_read.wait(timeout=5)

    activation.release(timeout=0.0)
    release_second_read.set()
    assert cancelled_job.wait(timeout=5)

    assert activation.bound is False
    assert parser.cache_info()["entries"] == 0
    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)
    activation.activate(tmp_path)
    completed_job = activation._job
    assert completed_job.wait(timeout=5)
    assert activation.project().graph_json() == ProjectActivation(
        ProjectParser((PythonAstAdapter(),)).parse(tmp_path)
    ).project().graph_json()


def test_release_while_evidence_is_prepared_cannot_publish_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "app.py").write_text("def ready() -> None:\n    pass\n", encoding="utf-8")
    entered_serialization = threading.Event()
    release_serialization = threading.Event()
    original_to_json = Graph.to_json

    def blocking_to_json(graph: Graph) -> str:
        if (
            graph.project_root == str(tmp_path.resolve())
            and threading.current_thread().name == "codemble-parse"
        ):
            entered_serialization.set()
            assert release_serialization.wait(timeout=5)
        return original_to_json(graph)

    monkeypatch.setattr(Graph, "to_json", blocking_to_json)
    parser = ProjectParser((PythonAstAdapter(),))
    activation = ProjectActivation(parser=parser)
    activation.activate(tmp_path)
    cancelled_job = activation._job
    assert entered_serialization.wait(timeout=5)

    activation.release(timeout=0.0)
    release_serialization.set()
    assert cancelled_job.wait(timeout=5)

    assert activation.bound is False
    assert parser.cache_info()["entries"] == 0


def test_a_bound_project_refuses_a_second_activation() -> None:
    activation = ProjectActivation(
        PythonAstAdapter().parse(FIXTURE), parse_runner=_inline_runner
    )

    with pytest.raises(ProjectActivationBusy, match="already selected"):
        activation.activate(FIXTURE)
