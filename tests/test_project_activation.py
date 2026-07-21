"""Project activation owns parse lifetime, binding, release, and live caches."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_a_bound_project_refuses_a_second_activation() -> None:
    activation = ProjectActivation(
        PythonAstAdapter().parse(FIXTURE), parse_runner=_inline_runner
    )

    with pytest.raises(ProjectActivationBusy, match="already selected"):
        activation.activate(FIXTURE)
