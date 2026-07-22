"""Recents derived from the local progress directory."""

import json
import os
from pathlib import Path

import pytest

from codemble.progress import list_recent_projects


def _write_progress(root: Path, name: str, payload: object, mtime: float) -> None:
    path = root / "progress" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_recents_lists_existing_projects_newest_first(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    older = tmp_path / "older-project"
    newer = tmp_path / "newer-project"
    older.mkdir()
    newer.mkdir()
    _write_progress(
        tmp_path / "data",
        "aaa",
        {
            "schema_version": 1,
            "project_root": str(older),
            "regions": {"pkg": {"signature": "s1"}},
        },
        mtime=1_000.0,
    )
    _write_progress(
        tmp_path / "data",
        "bbb",
        {
            "schema_version": 1,
            "project_root": str(newer),
            "regions": {"a": {"signature": "s2"}, "b": {"signature": "s3"}},
        },
        mtime=2_000.0,
    )
    _write_progress(
        tmp_path / "data",
        "ccc",
        {
            "schema_version": 1,
            "project_root": str(tmp_path / "deleted-project"),
            "regions": {},
        },
        mtime=3_000.0,
    )
    (tmp_path / "data" / "progress" / "junk.json").write_text(
        "not json", encoding="utf-8"
    )

    recents = list_recent_projects()

    assert recents == [
        {"project_root": str(newer), "understood_count": 2},
        {"project_root": str(older), "understood_count": 1},
    ]


def test_recents_survive_a_missing_progress_directory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "never-written"))

    assert list_recent_projects() == []


def test_clear_forgets_only_this_projects_regions(tmp_path: Path) -> None:
    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore

    fixture = Path(__file__).parent / "fixtures" / "sampleproj"
    other = tmp_path / "other"
    other.mkdir()
    (other / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")

    graph = PythonAstAdapter().parse(fixture)
    other_graph = PythonAstAdapter().parse(other)
    store = ProgressStore(graph, tmp_path / "progress")
    other_store = ProgressStore(other_graph, tmp_path / "progress")
    store.set_mode("expert")
    store.mark_understood("app")
    other_store.mark_understood("solo")

    store.clear()

    assert store.understood_regions() == frozenset()
    assert other_store.understood_regions() == frozenset({"solo"})
    assert store.mode() == "expert", "clearing progress must not reset preferences"
    assert other_store.path.exists()


def test_a_new_project_inherits_the_audience_the_learner_already_chose(
    tmp_path: Path,
) -> None:
    """The gate asks about the learner, so it must not re-ask per project.

    Mode stays per project -- it drives the default layer and can be changed
    from the header on any one of them -- but a fresh bind seeds itself from
    the last answer instead of showing the first-run gate again.
    """

    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore

    first = tmp_path / "first"
    second = tmp_path / "second"
    for project in (first, second):
        project.mkdir()
        (project / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")
    root = tmp_path / "progress"

    answered = ProgressStore(PythonAstAdapter().parse(first), root)
    answered.set_mode("expert")

    fresh = ProgressStore(PythonAstAdapter().parse(second), root)
    assert fresh.mode() == "expert"
    assert fresh.mode_chosen() is True, "a seeded project must not re-open the gate"

    fresh.set_mode("easy")
    assert fresh.mode() == "easy"
    assert answered.mode() == "expert", "per-project override must not rewrite the other"


def test_the_learner_preference_file_is_never_offered_as_a_recent_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It shares the progress directory, so recents must not read it as a project."""

    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore, list_recent_projects

    project = tmp_path / "project"
    project.mkdir()
    (project / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))

    store = ProgressStore(PythonAstAdapter().parse(project))
    store.set_mode("expert")
    store.mark_understood("solo")

    recents = list_recent_projects()
    assert [entry["project_root"] for entry in recents] == [str(project.resolve())]
