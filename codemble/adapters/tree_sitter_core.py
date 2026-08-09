"""Shared lifecycle for in-process tree-sitter language adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from codemble.adapters.base import AdapterParseError, Graph
from codemble.adapters.discovery import SourceDiscoveryError, discover_source_files
from codemble.graph.finalize import GraphFinalizationError, finalize_graph


class _TreeSitterAdapterCore:
    """Own discovery, parse orchestration, and canonical finalization once."""

    file_extensions: ClassVar[frozenset[str]]
    ignored_directories: ClassVar[frozenset[str]]
    _parse_error_type: ClassVar[type[AdapterParseError]]
    _source_label: ClassVar[str]

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact source scope accepted by this adapter."""

        normalized = path.expanduser().resolve()
        try:
            discovery = discover_source_files(
                normalized,
                self.file_extensions,
                ignored_directories=self.ignored_directories,
            )
        except SourceDiscoveryError as error:
            raise self._parse_error_type(str(error)) from error
        if not discovery.files:
            if normalized.is_file():
                raise self._parse_error_type(
                    f"expected a {self._source_label} file or directory: {normalized}"
                )
            raise self._parse_error_type(
                f"no {self._source_label} files found under: {normalized}"
            )
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Discover and parse one source scope."""

        project_root, files = self.discover(path)
        return self.parse_files(project_root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        """Parse files already discovered as owned by this adapter."""

        parsed_files = tuple(
            self._parse_owned_file(file, project_root) for file in files
        )
        draft = self._build_graph_draft(project_root, parsed_files)
        try:
            return finalize_graph(draft, entrypoint=entrypoint)
        except GraphFinalizationError as error:
            raise self._parse_error_type(str(error)) from error

    def _parse_owned_file(self, path: Path, project_root: Path) -> Any:
        """Parse one file already assigned to this language."""

        raise NotImplementedError

    def _build_graph_draft(
        self,
        project_root: Path,
        parsed_files: tuple[Any, ...],
    ) -> Graph:
        """Build language-specific graph evidence before canonicalization."""

        raise NotImplementedError
