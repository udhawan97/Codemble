"""Language-neutral project parsing and graph composition."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from codemble.adapters.base import AdapterParseError, Graph, LanguageAdapter, Node
from codemble.adapters.discovery import (
    OwnedSourceFiles,
    SourceDiscoveryError,
    SourceOwnership,
    discover_project_sources,
)
from codemble.adapters.parse_progress import (
    ParseProgress,
    note_detail,
    reporting_detail,
    reporting_files,
)
from codemble.graph.finalize import GraphFinalizationError, finalize_graph


class ProjectParseError(AdapterParseError):
    """A project cannot be composed into one honest graph."""


class ProjectScaleError(ProjectParseError):
    """A discovered project needs a smaller learner-selected scope."""

    def __init__(self, intake: ProjectIntake, scale_cap: int) -> None:
        self.intake = intake
        self.scale_cap = scale_cap
        scopes = ", ".join(
            f"{directory} ({count})" for directory, count in intake.scope_counts()[:6]
        )
        suggestion = f" Busiest scopes: {scopes}." if scopes else ""
        super().__init__(
            f"found {len(intake.files)} supported source files; Codemble is capped at "
            f"{scale_cap}. Re-run with `codemble --path PATH` to choose a project "
            f"subdirectory.{suggestion}"
        )


@dataclass(frozen=True, slots=True)
class ProjectIntake:
    """One supported project scope with adapter ownership resolved once."""

    path: Path
    root: Path
    files: tuple[Path, ...]
    _ownership: tuple[OwnedSourceFiles, ...]

    def _files_for(self, language: str) -> tuple[Path, ...]:
        return next(
            (owned.files for owned in self._ownership if owned.owner == language),
            (),
        )

    def scope_counts(self) -> tuple[tuple[str, int], ...]:
        """Count supported files per top-level directory, busiest first."""

        counts: dict[str, int] = {}
        for file in self.files:
            relative = file.relative_to(self.root)
            directory = relative.parts[0] if len(relative.parts) > 1 else "."
            counts[directory] = counts.get(directory, 0) + 1
        return tuple(
            sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        )


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

    # Raised from 300 with the Phase C threaded parse and staged loading
    # screen; LOD and clustering remain Phase 2.
    scale_cap = 1000

    def intake(self, path: Path, *, explicit: bool = False) -> ProjectIntake:
        """Resolve one project scope and every adapter's owned files."""

        normalized = path.expanduser().resolve()
        extensions = frozenset().union(*(adapter.file_extensions for adapter in self._adapters))
        ownership = tuple(
            SourceOwnership(
                owner=adapter.language,
                extensions=adapter.file_extensions,
                ignored_directories=adapter.ignored_directories,
            )
            for adapter in self._adapters
        )
        try:
            discovery = discover_project_sources(normalized, ownership)
        except SourceDiscoveryError as error:
            raise ProjectParseError(str(error)) from error
        files = discovery.files
        if not files:
            expected = ", ".join(sorted(extensions))
            raise ProjectParseError(
                f"no supported source files found under: {normalized} "
                f"(expected {expected})"
            )
        intake = ProjectIntake(
            path=normalized,
            root=discovery.root,
            files=files,
            _ownership=discovery.ownership,
        )
        if not explicit and len(files) > self.scale_cap:
            raise ProjectScaleError(intake, self.scale_cap)
        return intake

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return all files accepted by the registered language adapters."""

        intake = self.intake(path)
        return intake.root, intake.files

    def parse(
        self,
        source: Path | ProjectIntake,
        *,
        entrypoint: str | None = None,
        explicit: bool = False,
        progress: ParseProgress | None = None,
    ) -> Graph:
        """Parse every detected language and return one deterministic graph."""

        if isinstance(source, ProjectIntake):
            intake = source
        else:
            if progress is not None:
                progress.stage("discovering")
            intake = self.intake(source, explicit=explicit)
        owned = {
            adapter.language: intake._files_for(adapter.language)
            for adapter in self._adapters
        }
        if progress is not None:
            # The counter totals the files adapters will actually read, which
            # is what ``note_file_parsed`` counts.  ``intake.files`` is the
            # deduplicated union and would drift if two adapters ever shared
            # an extension.
            progress.files_total(sum(len(files) for files in owned.values()))
            progress.stage("parsing")
        graphs: list[Graph] = []
        on_file = progress.file_parsed if progress is not None else None
        # ``detail`` outlives the file-read loop: the adapters narrate their
        # cross-file passes and composition narrates the merge, all under the
        # single ``resolving`` stage the design spec fixes.
        on_detail = getattr(progress, "detail", None) if progress is not None else None
        with reporting_detail(on_detail), reporting_files(on_file):
            for adapter in self._adapters:
                files = owned[adapter.language]
                if not files:
                    continue
                try:
                    graphs.append(adapter.parse_files(intake.root, files))
                except AdapterParseError as error:
                    raise ProjectParseError(str(error)) from error
            if progress is not None:
                progress.stage("resolving")
            return _compose_graphs(tuple(graphs), intake.root, entrypoint)

def _compose_graphs(
    graphs: tuple[Graph, ...],
    project_root: Path,
    entrypoint: str | None,
) -> Graph:
    note_detail("Composing your project")
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


__all__ = [
    "ProjectIntake",
    "ProjectParseError",
    "ProjectParser",
    "ProjectScaleError",
]
