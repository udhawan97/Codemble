"""Project selection resolves browsing, recents, and the filesystem jail."""

from __future__ import annotations

from pathlib import Path

import pytest

from codemble.server.project_selection import (
    ProjectFolderForbidden,
    ProjectFolderMissing,
    ProjectSelector,
)


def test_browse_lists_only_visible_directories_in_name_order(tmp_path: Path) -> None:
    (tmp_path / "beta").mkdir()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "loose.py").write_text("A = 1\n", encoding="utf-8")
    selector = ProjectSelector(tmp_path)

    root = selector.browse()
    child = selector.browse(tmp_path / "beta")

    assert root.to_dict() == {
        "path": str(tmp_path.resolve()),
        "parent": None,
        "entries": (
            {"name": "Alpha", "path": str(tmp_path / "Alpha")},
            {"name": "beta", "path": str(tmp_path / "beta")},
        ),
    }
    assert child.parent == tmp_path.resolve()


def test_resolve_refuses_missing_and_outside_paths(tmp_path: Path) -> None:
    selector = ProjectSelector(tmp_path / "jail")

    with pytest.raises(ProjectFolderMissing, match="does not exist"):
        selector.resolve(tmp_path / "missing")
    with pytest.raises(ProjectFolderForbidden, match="inside your home"):
        selector.resolve(tmp_path)


def test_browse_refuses_a_symlink_escape(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    outside = tmp_path / "outside"
    jail.mkdir()
    outside.mkdir()
    (jail / "escape").symlink_to(outside)

    with pytest.raises(ProjectFolderForbidden, match="inside your home"):
        ProjectSelector(jail).browse(jail / "escape")


def test_recents_are_filtered_by_the_same_canonical_jail(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    inside = jail / "project"
    outside = tmp_path / "outside"
    jail.mkdir()
    inside.mkdir()
    outside.mkdir()
    entries = (
        {"project_root": str(inside), "understood_count": 1},
        {"project_root": str(outside), "understood_count": 2},
    )

    selector = ProjectSelector(jail, recent_projects=lambda: entries)

    assert selector.recents() == (entries[0],)
