"""Language-neutral project parsing and graph composition."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from codemble.adapters.base import (
    AdapterParseError,
    Graph,
    LanguageAdapter,
    Node,
    UnsupportedSource,
)
from codemble.adapters.discovery import (
    OwnedSourceFiles,
    SourceDiscoveryError,
    SourceOwnership,
    discover_project_sources,
)
from codemble.adapters.evidence_cache import EvidenceCache, PreparedEvidence
from codemble.adapters.parse_progress import (
    ParseCancelled,
    ParseProgress,
    check_parse_cancelled,
    note_detail,
    note_file_parsed,
    reporting_cancellation,
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
    # Chartable-language files no registered adapter claimed. Discovery is the
    # only place that sees every adapter's ownership at once, so the tally is
    # carried from there rather than recomputed per adapter.
    unsupported_sources: tuple[UnsupportedSource, ...] = ()

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


@dataclass(frozen=True, slots=True)
class ProjectParseCandidate:
    """A complete graph whose cache evidence is not published until acceptance."""

    graph: Graph
    _cache: EvidenceCache
    _evidence: tuple[PreparedEvidence, ...]
    _cancelled: Callable[[], bool] | None = None

    def publish_evidence(self) -> None:
        """Publish only while the owning activation still accepts this candidate."""

        if self._cancelled is not None and self._cancelled():
            raise ParseCancelled("the learner reset the picker during this parse")
        for prepared in self._evidence:
            self._cache.commit(prepared)


class ProjectParser:
    """Discover supported languages and compose their graphs behind one interface."""

    def __init__(
        self,
        adapters: Iterable[LanguageAdapter] | None = None,
        *,
        evidence_cache: EvidenceCache | None = None,
    ) -> None:
        if adapters is None:
            # The one place the supported language set is written down. Nothing
            # else above the seam names a language, which is what keeps adding
            # one to this tuple the whole integration -- graph, checks, lens
            # routing, the unsupported-sources tally and the frontend all key
            # off `Node.language` rather than off a list of their own.
            from codemble.adapters.csharp_tree_sitter import CSharpAdapter
            from codemble.adapters.go_tree_sitter import GoAdapter
            from codemble.adapters.java_tree_sitter import JavaAdapter
            from codemble.adapters.python_ast import PythonAstAdapter
            from codemble.adapters.rust_tree_sitter import RustAdapter
            from codemble.adapters.typescript_tree_sitter import (
                JavaScriptTypeScriptAdapter,
            )

            adapters = (
                PythonAstAdapter(),
                JavaScriptTypeScriptAdapter(),
                GoAdapter(),
                JavaAdapter(),
                RustAdapter(),
                CSharpAdapter(),
            )
        self._adapters = tuple(adapters)
        if not self._adapters:
            raise ValueError("ProjectParser requires at least one language adapter")
        languages = [adapter.language for adapter in self._adapters]
        if len(languages) != len(set(languages)):
            raise ValueError("ProjectParser adapter languages must be unique")
        self._evidence_cache = evidence_cache or EvidenceCache()

    @property
    def languages(self) -> tuple[str, ...]:
        """Return supported language identifiers in stable registry order."""

        return tuple(adapter.language for adapter in self._adapters)

    def cache_info(self) -> dict[str, int]:
        """Return source-free in-process evidence-cache counters."""

        return self._evidence_cache.info()

    # Raised from 300 with the Phase C threaded parse and staged loading screen.
    # The 2026-08-14 complete 5k Map gate passed Chromium but failed WebKit's
    # interaction budget, so explicit --path scopes may go larger while the
    # ordinary picker stays here until a complete canvas Map passes both.
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
            unsupported_sources=discovery.unsupported,
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

        candidate = self.parse_candidate(
            source,
            entrypoint=entrypoint,
            explicit=explicit,
            progress=progress,
        )
        candidate.publish_evidence()
        return candidate.graph

    def parse_candidate(
        self,
        source: Path | ProjectIntake,
        *,
        entrypoint: str | None = None,
        explicit: bool = False,
        progress: ParseProgress | None = None,
    ) -> ProjectParseCandidate:
        """Build a graph and validated evidence without publishing the evidence."""

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
        evidence: list[PreparedEvidence] = []
        on_file = progress.file_parsed if progress is not None else None
        # ``detail`` outlives the file-read loop: the adapters narrate their
        # cross-file passes and composition narrates the merge, all under the
        # single ``resolving`` stage the design spec fixes.
        on_detail = getattr(progress, "detail", None) if progress is not None else None
        is_cancelled = (
            None
            if progress is None
            else lambda: bool(getattr(progress, "cancelled", False))
        )
        with (
            reporting_cancellation(is_cancelled),
            reporting_detail(on_detail),
            reporting_files(on_file),
        ):
            for adapter in self._adapters:
                files = owned[adapter.language]
                if not files:
                    continue
                try:
                    graph, prepared = self._parse_adapter(adapter, intake.root, files)
                    graphs.append(graph)
                    if prepared is not None:
                        evidence.append(prepared)
                except AdapterParseError as error:
                    raise ProjectParseError(str(error)) from error
            if progress is not None:
                progress.stage("resolving")
            graph = _compose_graphs(
                tuple(graphs),
                intake.root,
                entrypoint,
                intake.unsupported_sources,
            )
            check_parse_cancelled()
            return ProjectParseCandidate(
                graph=graph,
                _cache=self._evidence_cache,
                _evidence=tuple(evidence),
                _cancelled=is_cancelled,
            )

    def _parse_adapter(
        self,
        adapter: LanguageAdapter,
        project_root: Path,
        files: tuple[Path, ...],
    ) -> tuple[Graph, PreparedEvidence | None]:
        key = self._evidence_cache.key_for(adapter, project_root, files)
        cached = self._evidence_cache.get(key)
        if cached is not None:
            note_detail(f"Reusing {adapter.language} parser evidence")
            for _ in files:
                note_file_parsed()
            return cached, None
        graph = adapter.parse_files(project_root, files)
        # A file may change between discovery/fingerprinting and the adapter's
        # own single-byte capture. Such a candidate is still a coherent graph,
        # but it cannot be retained under a key for different bytes.
        return graph, self._evidence_cache.prepare(key, graph)

def _compose_graphs(
    graphs: tuple[Graph, ...],
    project_root: Path,
    entrypoint: str | None,
    unsupported_sources: tuple[UnsupportedSource, ...] = (),
) -> Graph:
    note_detail("Composing your project")
    nodes: list[Node] = []
    edges = []
    annotations = []
    role_evidence = []
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
        role_evidence.extend(graph.role_evidence)
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
        role_evidence=tuple(role_evidence),
        partial_files=tuple(partial_files),
        unsupported_sources=unsupported_sources,
    )
    try:
        return finalize_graph(draft, entrypoint=entrypoint)
    except GraphFinalizationError as error:
        raise ProjectParseError(str(error)) from error


__all__ = [
    "ProjectIntake",
    "ProjectParseCandidate",
    "ProjectParseError",
    "ProjectParser",
    "ProjectScaleError",
]
