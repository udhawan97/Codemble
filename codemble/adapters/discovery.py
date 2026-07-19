"""Shared, deterministic source discovery for language adapters."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

_IGNORED_DIRECTORIES = {"venv", ".venv", "node_modules", "__pycache__"}


class SourceDiscoveryError(ValueError):
    """The requested source scope does not exist or is not readable as a scope."""


@dataclass(frozen=True, slots=True)
class SourceDiscovery:
    """A normalized project root and its supported source files."""

    root: Path
    files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class SourceOwnership:
    """One adapter's source extensions and directory exclusions."""

    owner: str
    extensions: frozenset[str]
    ignored_directories: frozenset[str]


@dataclass(frozen=True, slots=True)
class OwnedSourceFiles:
    """Files assigned to one adapter during project discovery."""

    owner: str
    files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ProjectSourceDiscovery:
    """One normalized project root with all adapter ownership resolved."""

    root: Path
    ownership: tuple[OwnedSourceFiles, ...]

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(
            sorted({file for owned in self.ownership for file in owned.files})
        )


def discover_source_files(
    requested: Path,
    extensions: frozenset[str],
    *,
    ignored_directories: frozenset[str] = frozenset(),
) -> SourceDiscovery:
    """Discover matching files while honoring the project's root ``.gitignore``."""
    owner = "source"
    project = discover_project_sources(
        requested,
        (SourceOwnership(owner, extensions, ignored_directories),),
    )
    return SourceDiscovery(project.root, project.ownership[0].files)


def discover_project_sources(
    requested: Path,
    ownership: tuple[SourceOwnership, ...],
) -> ProjectSourceDiscovery:
    """Discover every adapter's files in one deterministic filesystem walk."""

    normalized = requested.expanduser().resolve()
    if not normalized.exists():
        raise SourceDiscoveryError(f"path does not exist: {normalized}")
    if not ownership:
        raise ValueError("project source discovery requires at least one owner")
    discovered: dict[str, list[Path]] = {rule.owner: [] for rule in ownership}
    if normalized.is_file():
        for rule in ownership:
            if normalized.suffix.lower() in rule.extensions:
                discovered[rule.owner].append(normalized)
        return ProjectSourceDiscovery(
            normalized.parent,
            tuple(
                OwnedSourceFiles(rule.owner, tuple(discovered[rule.owner]))
                for rule in ownership
            ),
        )
    if not normalized.is_dir():
        raise SourceDiscoveryError(f"expected a source file or directory: {normalized}")

    ignore_rules = _load_gitignore(normalized)
    for current, directory_names, file_names in os.walk(normalized):
        current_path = Path(current)
        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if not _ignore_project_directory(
                (current_path / directory_name).relative_to(normalized),
                ignore_rules,
                ownership,
            )
        )
        for file_name in sorted(file_names):
            candidate = current_path / file_name
            relative = candidate.relative_to(normalized)
            if _matches_gitignore(relative, False, ignore_rules):
                continue
            for rule in ownership:
                if candidate.suffix.lower() not in rule.extensions:
                    continue
                if any(part in rule.ignored_directories for part in relative.parts):
                    continue
                discovered[rule.owner].append(candidate)
    return ProjectSourceDiscovery(
        normalized,
        tuple(
            OwnedSourceFiles(rule.owner, tuple(sorted(discovered[rule.owner])))
            for rule in ownership
        ),
    )


def _load_gitignore(root: Path) -> tuple[tuple[str, bool], ...]:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return ()
    rules: list[tuple[str, bool]] = []
    for raw_line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line[1:] if negated else line
        rules.append((pattern, negated))
    return tuple(rules)


def _ignore_project_directory(
    relative: Path,
    rules: tuple[tuple[str, bool], ...],
    ownership: tuple[SourceOwnership, ...],
) -> bool:
    if any(part.startswith(".") for part in relative.parts):
        return True
    if any(part in _IGNORED_DIRECTORIES for part in relative.parts):
        return True
    if _matches_gitignore(relative, True, rules):
        return True
    return all(
        any(part in rule.ignored_directories for part in relative.parts)
        for rule in ownership
    )


def _matches_gitignore(
    relative: Path,
    is_directory: bool,
    rules: tuple[tuple[str, bool], ...],
) -> bool:
    path = relative.as_posix()
    ignored = False
    for raw_pattern, negated in rules:
        directory_only = raw_pattern.endswith("/")
        pattern = raw_pattern.rstrip("/").lstrip("/")
        if directory_only and not is_directory and not path.startswith(f"{pattern}/"):
            continue
        if "/" in pattern:
            matched = fnmatch.fnmatch(path, pattern) or path.startswith(f"{pattern}/")
        else:
            matched = any(fnmatch.fnmatch(part, pattern) for part in relative.parts)
        if matched:
            ignored = not negated
    return ignored


__all__ = [
    "OwnedSourceFiles",
    "ProjectSourceDiscovery",
    "SourceDiscovery",
    "SourceDiscoveryError",
    "SourceOwnership",
    "discover_project_sources",
    "discover_source_files",
]
