"""Recents derived from the local progress directory."""

import json
import os
from pathlib import Path

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
