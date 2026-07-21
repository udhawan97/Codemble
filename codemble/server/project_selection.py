"""The local-folder policy behind Codemble's project picker."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from codemble.progress import list_recent_projects

RecentProjects = Callable[[], Iterable[dict[str, object]]]


class ProjectSelectionError(Exception):
    """A folder cannot participate in project selection."""


class ProjectFolderMissing(ProjectSelectionError):
    """The requested folder does not exist."""


class ProjectFolderForbidden(ProjectSelectionError):
    """The requested folder is outside the allowed browse root."""


class ProjectFolderUnreadable(ProjectSelectionError):
    """The requested folder cannot be listed by this process."""


@dataclass(frozen=True, slots=True)
class FolderListing:
    """One resolved folder and its learner-visible child directories."""

    path: Path
    parent: Path | None
    entries: tuple[Path, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "parent": str(self.parent) if self.parent is not None else None,
            "entries": tuple(
                {"name": entry.name, "path": str(entry)} for entry in self.entries
            ),
        }


class ProjectSelector:
    """Resolve every picker operation under one canonical filesystem jail."""

    def __init__(
        self,
        browse_root: Path,
        recent_projects: RecentProjects = list_recent_projects,
    ) -> None:
        self._root = browse_root.expanduser().resolve()
        self._recent_projects = recent_projects

    def resolve(self, path: str | Path) -> Path:
        """Resolve an existing selection and enforce the browse-root jail."""

        try:
            resolved = Path(path).expanduser().resolve(strict=True)
        except OSError as error:
            raise ProjectFolderMissing("That folder does not exist.") from error
        self._require_inside_root(resolved)
        return resolved

    def browse(self, path: str | Path | None = None) -> FolderListing:
        """List non-hidden child directories for one allowed folder."""

        resolved = self.resolve(path if path is not None else self._root)
        if not resolved.is_dir():
            raise ProjectFolderMissing("That folder does not exist.")
        try:
            children = tuple(
                sorted(
                    (
                        child
                        for child in resolved.iterdir()
                        if child.is_dir() and not child.name.startswith(".")
                    ),
                    key=lambda child: child.name.lower(),
                )
            )
        except OSError as error:
            raise ProjectFolderUnreadable("Codemble cannot read that folder.") from error
        parent = resolved.parent if resolved != self._root else None
        return FolderListing(path=resolved, parent=parent, entries=children)

    def recents(self) -> tuple[dict[str, object], ...]:
        """Return only remembered projects still inside the browse-root jail."""

        return tuple(
            entry
            for entry in self._recent_projects()
            if self._is_inside_root(Path(str(entry["project_root"])).resolve())
        )

    def _require_inside_root(self, path: Path) -> None:
        if not self._is_inside_root(path):
            raise ProjectFolderForbidden(
                "Choose a folder inside your home directory."
            )

    def _is_inside_root(self, path: Path) -> bool:
        return path.is_relative_to(self._root)


__all__ = [
    "FolderListing",
    "ProjectFolderForbidden",
    "ProjectFolderMissing",
    "ProjectFolderUnreadable",
    "ProjectSelectionError",
    "ProjectSelector",
]
