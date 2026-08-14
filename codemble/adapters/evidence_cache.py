"""Bounded process-memory cache for validated parser graph evidence.

The cache deliberately stores only immutable graph facts, partitioned by the
exact file bytes that produced them. Source bytes are read to derive
conservative identities and are discarded before this module returns a key.
Concept snippets are reconstructed transiently from hash-verified current
bytes on a hit; no captured source bytes, raw source-line snippet, syntax tree,
provider payload, or disk artifact is retained in the cache.
"""

from __future__ import annotations

import hashlib
import inspect
import io
import platform
import tokenize
from collections import OrderedDict
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from threading import Lock
from typing import Final, TypeAlias

from codemble.adapters.base import (
    ConceptAnnotation,
    Edge,
    Graph,
    LanguageAdapter,
    Node,
    RoleEvidence,
)
from codemble.adapters.parse_progress import check_parse_cancelled

_EVIDENCE_FORMAT_VERSION: Final = "2"
_DEFAULT_MAX_ENTRIES: Final = 24
_DEFAULT_MAX_BYTES: Final = 128 * 1024 * 1024
_GRAMMAR_DISTRIBUTIONS: Final[dict[str, tuple[str, ...]]] = {
    "csharp": ("tree-sitter", "tree-sitter-c-sharp"),
    "go": ("tree-sitter", "tree-sitter-go"),
    "java": ("tree-sitter", "tree-sitter-java"),
    "javascript-typescript": (
        "tree-sitter",
        "tree-sitter-javascript",
        "tree-sitter-typescript",
    ),
    "python": (),
    "rust": ("tree-sitter", "tree-sitter-rust"),
}


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """Exact source identity captured without retaining source bytes."""

    relative_path: str
    digest: str
    dialect: str


EvidenceOwner: TypeAlias = tuple[
    str,
    int,
    int,
    str,
    tuple[str, ...],
    tuple[tuple[str, ...], tuple[str, ...]],
]


@dataclass(frozen=True, slots=True)
class EvidenceKey:
    """Everything that can change graph facts for one adapter snapshot."""

    root: str
    root_device: int
    root_inode: int
    language: str
    adapter_version: tuple[str, ...]
    discovery_config: tuple[tuple[str, ...], tuple[str, ...]]
    sources: tuple[SourceFingerprint, ...]

    @property
    def owner(self) -> EvidenceOwner:
        """Identify one root, adapter, version, and discovery contract."""

        return (
            self.root,
            self.root_device,
            self.root_inode,
            self.language,
            self.adapter_version,
            self.discovery_config,
        )

    def matches(self, graph: Graph) -> bool:
        """Return whether an adapter graph came from the captured exact bytes."""

        expected = {
            fingerprint.relative_path: fingerprint.digest
            for fingerprint in self.sources
        }
        return graph.project_root == self.root and graph.file_hashes == expected


@dataclass(frozen=True, slots=True)
class _AnnotationEvidence:
    """Concept metadata retained without its presentation-only source line."""

    node_id: str
    language: str
    concept: str
    lineno: int
    end_lineno: int


@dataclass(frozen=True, slots=True)
class _FileEvidence:
    """Source-free parser facts whose provenance is one exact file."""

    fingerprint: SourceFingerprint
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    annotations: tuple[_AnnotationEvidence, ...]
    roles: tuple[RoleEvidence, ...]
    partial: bool


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    files: dict[str, _FileEvidence]
    size: int


@dataclass(frozen=True, slots=True)
class PreparedEvidence:
    """Validated evidence that is still invisible to cache readers."""

    owner: EvidenceOwner
    files: dict[str, _FileEvidence]
    size: int


class _EvidenceSnapshotChanged(Exception):
    """The current source no longer matches the fingerprint being rehydrated."""


class EvidenceCache:
    """Thread-safe, root-aware LRU of validated per-file graph evidence.

    ``max_entries`` bounds root/adapter/version buckets rather than individual
    source files. That keeps a 10,000-file project usable while ``max_bytes``
    bounds the canonical-JSON size of retained evidence conservatively. Python
    object overhead is intentionally not presented as an exact RSS limit.
    """

    def __init__(
        self,
        *,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        max_bytes: int = _DEFAULT_MAX_BYTES,
    ) -> None:
        if max_entries < 1:
            raise ValueError("evidence cache max_entries must be positive")
        if max_bytes < 1:
            raise ValueError("evidence cache max_bytes must be positive")
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._entries: OrderedDict[EvidenceOwner, _CacheEntry] = OrderedDict()
        self._bytes = 0
        self._hits = 0
        self._misses = 0
        self._puts = 0
        self._evictions = 0
        self._rejections = 0
        self._partial_file_matches = 0
        self._file_invalidations = 0
        self._resolution_refreshes = 0
        self._lock = Lock()

    def key_for(
        self,
        adapter: LanguageAdapter,
        project_root: Path,
        files: tuple[Path, ...],
    ) -> EvidenceKey:
        """Capture exact digests, then discard every captured source byte."""

        root = project_root.resolve()
        identity = root.stat()
        sources: list[SourceFingerprint] = []
        for path in files:
            check_parse_cancelled()
            raw = path.read_bytes()
            check_parse_cancelled()
            sources.append(
                SourceFingerprint(
                    relative_path=path.relative_to(root).as_posix(),
                    digest=hashlib.sha256(raw).hexdigest(),
                    dialect=path.suffix.lower(),
                )
            )
        return EvidenceKey(
            root=str(root),
            root_device=identity.st_dev,
            root_inode=identity.st_ino,
            language=adapter.language,
            adapter_version=_adapter_version(adapter),
            discovery_config=(
                tuple(sorted(adapter.file_extensions)),
                tuple(sorted(adapter.ignored_directories)),
            ),
            sources=tuple(sources),
        )

    def get(self, key: EvidenceKey) -> Graph | None:
        """Recompose a complete exact snapshot when every file identity matches."""

        with self._lock:
            entry = self._entries.get(key.owner)
            if entry is None:
                self._misses += 1
                return None
            matches = tuple(
                entry.files.get(source.relative_path)
                for source in key.sources
                if (
                    entry.files.get(source.relative_path) is not None
                    and entry.files[source.relative_path].fingerprint == source
                )
            )
            current_paths = {source.relative_path for source in key.sources}
            if len(matches) != len(key.sources) or set(entry.files) != current_paths:
                self._partial_file_matches += len(matches)
                self._misses += 1
                return None
            evidence = tuple(item for item in matches if item is not None)
        try:
            graph = _graph_from_evidence(key, evidence)
        except _EvidenceSnapshotChanged:
            with self._lock:
                self._misses += 1
            return None
        with self._lock:
            if key.owner in self._entries:
                self._entries.move_to_end(key.owner)
            self._hits += 1
        return graph

    def prepare(self, key: EvidenceKey, graph: Graph) -> PreparedEvidence | None:
        """Validate and size evidence without publishing it to cache readers."""

        if not key.matches(graph):
            with self._lock:
                self._rejections += 1
            return None
        try:
            files = _partition_graph(key, graph)
        except ValueError:
            with self._lock:
                self._rejections += 1
            return None
        # The canonical complete graph overestimates the serialized content of
        # the retained file partitions. This is a deterministic accounting
        # ceiling, not a claim about Python object overhead or process RSS.
        size = len(graph.to_json().encode("utf-8"))
        if size > self._max_bytes:
            with self._lock:
                self._rejections += 1
            return None
        return PreparedEvidence(owner=key.owner, files=files, size=size)

    def commit(self, prepared: PreparedEvidence) -> None:
        """Atomically publish evidence only after its parse candidate is accepted."""

        files = dict(prepared.files)
        with self._lock:
            previous = self._entries.pop(prepared.owner, None)
            if previous is not None:
                self._bytes -= previous.size
                for path, old in previous.files.items():
                    new = files.get(path)
                    if new is None or new.fingerprint != old.fingerprint:
                        self._file_invalidations += 1
                        self._evictions += 1
                    elif new != old:
                        # Same captured bytes, but another file changed the
                        # globally resolved edge/role facts owned here.
                        self._resolution_refreshes += 1
                    else:
                        files[path] = old
            self._entries[prepared.owner] = _CacheEntry(files, prepared.size)
            self._bytes += prepared.size
            self._puts += 1
            while (
                len(self._entries) > self._max_entries
                or self._bytes > self._max_bytes
            ):
                _, evicted = self._entries.popitem(last=False)
                self._bytes -= evicted.size
                self._evictions += len(evicted.files)

    def put(self, key: EvidenceKey, graph: Graph) -> bool:
        """Validate and immediately publish evidence for a synchronous parse."""

        prepared = self.prepare(key, graph)
        if prepared is None:
            return False
        self.commit(prepared)
        return True

    def info(self) -> dict[str, int]:
        """Return source-free counters suitable for private benchmark receipts."""

        with self._lock:
            return {
                "entries": len(self._entries),
                "file_entries": sum(
                    len(entry.files) for entry in self._entries.values()
                ),
                "bytes": self._bytes,
                "hits": self._hits,
                "misses": self._misses,
                "puts": self._puts,
                "evictions": self._evictions,
                "rejections": self._rejections,
                "partial_file_matches": self._partial_file_matches,
                "file_invalidations": self._file_invalidations,
                "resolution_refreshes": self._resolution_refreshes,
                "max_entries": self._max_entries,
                "max_bytes": self._max_bytes,
            }


def _partition_graph(key: EvidenceKey, graph: Graph) -> dict[str, _FileEvidence]:
    fingerprints = {source.relative_path: source for source in key.sources}
    nodes: dict[str, list[Node]] = {path: [] for path in fingerprints}
    edges: dict[str, list[Edge]] = {path: [] for path in fingerprints}
    annotations: dict[str, list[_AnnotationEvidence]] = {
        path: [] for path in fingerprints
    }
    roles: dict[str, list[RoleEvidence]] = {path: [] for path in fingerprints}
    node_files: dict[str, str] = {}
    for node in graph.nodes:
        if node.file not in fingerprints:
            raise ValueError("graph node has no captured source provenance")
        nodes[node.file].append(node)
        node_files[node.id] = node.file
    for edge in graph.edges:
        owner = node_files.get(edge.src)
        if owner is None:
            raise ValueError("graph edge source has no captured node provenance")
        edges[owner].append(edge)
    for annotation in graph.concept_annotations:
        owner = node_files.get(annotation.node_id)
        if owner is None:
            raise ValueError("concept annotation has no captured node provenance")
        annotations[owner].append(
            _AnnotationEvidence(
                node_id=annotation.node_id,
                language=annotation.language,
                concept=annotation.concept,
                lineno=annotation.lineno,
                end_lineno=annotation.end_lineno,
            )
        )
    for role in graph.role_evidence:
        if role.file not in fingerprints:
            raise ValueError("role evidence has no captured observation provenance")
        roles[role.file].append(role)
    partial = set(graph.partial_files)
    if not partial.issubset(fingerprints):
        raise ValueError("partial-file evidence has no captured source provenance")
    return {
        path: _FileEvidence(
            fingerprint=fingerprint,
            nodes=tuple(nodes[path]),
            edges=tuple(edges[path]),
            annotations=tuple(annotations[path]),
            roles=tuple(roles[path]),
            partial=path in partial,
        )
        for path, fingerprint in fingerprints.items()
    }


def _graph_from_evidence(
    key: EvidenceKey,
    files: tuple[_FileEvidence, ...],
) -> Graph:
    return Graph(
        nodes=tuple(node for file in files for node in file.nodes),
        edges=tuple(edge for file in files for edge in file.edges),
        entrypoint_candidates=(),
        project_root=key.root,
        file_hashes={
            file.fingerprint.relative_path: file.fingerprint.digest for file in files
        },
        concept_annotations=_rehydrate_annotations(key, files),
        role_evidence=tuple(role for file in files for role in file.roles),
        partial_files=tuple(
            file.fingerprint.relative_path for file in files if file.partial
        ),
    )


def _rehydrate_annotations(
    key: EvidenceKey,
    files: tuple[_FileEvidence, ...],
) -> tuple[ConceptAnnotation, ...]:
    """Rebuild bounded snippets from exact current bytes without retaining them."""

    annotations: list[ConceptAnnotation] = []
    root = Path(key.root)
    for file in files:
        if not file.annotations:
            continue
        path = root / file.fingerprint.relative_path
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise _EvidenceSnapshotChanged from error
        if hashlib.sha256(raw).hexdigest() != file.fingerprint.digest:
            raise _EvidenceSnapshotChanged
        lines = _source_lines(raw, file.fingerprint.dialect)
        for annotation in file.annotations:
            snippet = (
                lines[annotation.lineno - 1].strip()
                if 0 < annotation.lineno <= len(lines)
                else ""
            )
            annotations.append(
                ConceptAnnotation(
                    node_id=annotation.node_id,
                    language=annotation.language,
                    concept=annotation.concept,
                    lineno=annotation.lineno,
                    end_lineno=annotation.end_lineno,
                    snippet=snippet[:240],
                )
            )
    return tuple(annotations)


def _source_lines(raw: bytes, dialect: str) -> tuple[str, ...]:
    if dialect == ".py":
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
        except (SyntaxError, UnicodeDecodeError):
            source = raw.decode("utf-8", errors="replace")
    else:
        source = raw.decode("utf-8", errors="replace")
    if dialect == ".cs":
        lines = source.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        return tuple(lines)
    return tuple(source.splitlines())


def _adapter_version(adapter: LanguageAdapter) -> tuple[str, ...]:
    adapter_type = type(adapter)
    source_path = inspect.getsourcefile(adapter_type)
    source_digest = "unavailable"
    if source_path is not None:
        try:
            source_digest = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
        except OSError:
            pass
    declared = str(getattr(adapter, "evidence_version", "1"))
    distributions = _GRAMMAR_DISTRIBUTIONS.get(adapter.language, ())
    versions = tuple(
        f"{distribution}={_distribution_version(distribution)}"
        for distribution in distributions
    )
    return (
        _EVIDENCE_FORMAT_VERSION,
        platform.python_version(),
        f"{adapter_type.__module__}.{adapter_type.__qualname__}",
        declared,
        source_digest,
        *versions,
    )


def _distribution_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "missing"


__all__ = [
    "EvidenceCache",
    "EvidenceKey",
    "PreparedEvidence",
    "SourceFingerprint",
]
