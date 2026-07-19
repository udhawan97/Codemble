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


def discover_source_files(
    requested: Path,
    extensions: frozenset[str],
    *,
    ignored_directories: frozenset[str] = frozenset(),
) -> SourceDiscovery:
    """Discover matching files while honoring the project's root ``.gitignore``."""

    normalized = requested.expanduser().resolve()
    if not normalized.exists():
        raise SourceDiscoveryError(f"path does not exist: {normalized}")
    if normalized.is_file():
        files = (normalized,) if normalized.suffix.lower() in extensions else ()
        return SourceDiscovery(normalized.parent, files)
    if not normalized.is_dir():
        raise SourceDiscoveryError(f"expected a source file or directory: {normalized}")

    ignore_rules = _load_gitignore(normalized)
    discovered: list[Path] = []
    for current, directory_names, file_names in os.walk(normalized):
        current_path = Path(current)
        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if not _ignore_directory(
                (current_path / directory_name).relative_to(normalized),
                ignore_rules,
                ignored_directories,
            )
        )
        for file_name in sorted(file_names):
            candidate = current_path / file_name
            relative = candidate.relative_to(normalized)
            if (
                candidate.suffix.lower() in extensions
                and not _matches_gitignore(relative, False, ignore_rules)
            ):
                discovered.append(candidate)
    return SourceDiscovery(normalized, tuple(sorted(discovered)))


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


def _ignore_directory(
    relative: Path,
    rules: tuple[tuple[str, bool], ...],
    ignored_directories: frozenset[str],
) -> bool:
    if any(part.startswith(".") for part in relative.parts):
        return True
    if any(
        part in _IGNORED_DIRECTORIES or part in ignored_directories
        for part in relative.parts
    ):
        return True
    return _matches_gitignore(relative, True, rules)


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


__all__ = ["SourceDiscovery", "SourceDiscoveryError", "discover_source_files"]
