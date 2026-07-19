"""Language-neutral project parsing and graph composition."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from codemble.adapters.base import AdapterParseError, Graph, LanguageAdapter, Node
from codemble.adapters.discovery import SourceDiscoveryError, discover_source_files
from codemble.graph.finalize import GraphFinalizationError, finalize_graph


class ProjectParseError(AdapterParseError):
    """A project cannot be composed into one honest graph."""


class ProjectParser:
    """Discover supported languages and compose their graphs behind one interface."""

    def __init__(self, adapters: Iterable[LanguageAdapter] | None = None) -> None:
        if adapters is None:
            from codemble.adapters.python_ast import PythonAstAdapter
            from codemble.adapters.typescript_tree_sitter import (
                JavaScriptTypeScriptAdapter,
            )

            adapters = (PythonAstAdapter(), JavaScriptTypeScriptAdapter())
        self._adapters = tuple(adapters)
        if not self._adapters:
            raise ValueError("ProjectParser requires at least one language adapter")
        languages = [adapter.language for adapter in self._adapters]
        if len(languages) != len(set(languages)):
            raise ValueError("ProjectParser adapter languages must be unique")

    @property
    def languages(self) -> tuple[str, ...]:
        """Return supported language identifiers in stable registry order."""

        return tuple(adapter.language for adapter in self._adapters)

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return all files accepted by the registered language adapters."""

        extensions = frozenset().union(*(adapter.file_extensions for adapter in self._adapters))
        try:
            discoveries = tuple(
                discover_source_files(
                    path,
                    adapter.file_extensions,
                    ignored_directories=adapter.ignored_directories,
                )
                for adapter in self._adapters
            )
        except SourceDiscoveryError as error:
            raise ProjectParseError(str(error)) from error
        files = tuple(sorted({file for discovery in discoveries for file in discovery.files}))
        if not files:
            expected = ", ".join(sorted(extensions))
            raise ProjectParseError(
                f"no supported source files found under: {path.expanduser().resolve()} "
                f"(expected {expected})"
            )
        return discoveries[0].root, files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse every detected language and return one deterministic graph."""

        project_root, files = self.discover(path)
        suffixes = {file.suffix.lower() for file in files}
        graphs: list[Graph] = []
        for adapter in self._adapters:
            if adapter.file_extensions.isdisjoint(suffixes):
                continue
            try:
                graphs.append(adapter.parse(path))
            except AdapterParseError as error:
                raise ProjectParseError(str(error)) from error
        return _compose_graphs(tuple(graphs), project_root, entrypoint)


def _compose_graphs(
    graphs: tuple[Graph, ...],
    project_root: Path,
    entrypoint: str | None,
) -> Graph:
    nodes: list[Node] = []
    edges = []
    annotations = []
    partial_files: set[str] = set()
    file_hashes: dict[str, str] = {}
    node_ids: set[str] = set()

    for graph in graphs:
        for node in graph.nodes:
            if node.id in node_ids:
                raise ProjectParseError(
                    f"language adapters produced the same node ID: {node.id}"
                )
            node_ids.add(node.id)
            nodes.append(node)
        edges.extend(graph.edges)
        annotations.extend(graph.concept_annotations)
        partial_files.update(graph.partial_files)
        for file, digest in graph.file_hashes.items():
            existing = file_hashes.get(file)
            if existing is not None and existing != digest:
                raise ProjectParseError(
                    f"language adapters disagreed on the source hash for: {file}"
                )
            file_hashes[file] = digest

    draft = Graph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        entrypoint_candidates=(),
        project_root=str(project_root),
        file_hashes=file_hashes,
        concept_annotations=tuple(annotations),
        partial_files=tuple(partial_files),
    )
    try:
        return finalize_graph(draft, entrypoint=entrypoint)
    except GraphFinalizationError as error:
        raise ProjectParseError(str(error)) from error


__all__ = ["ProjectParseError", "ProjectParser"]
