"""Language-neutral graph contracts for Codemble parsers.

Adapters are the only layer allowed to derive structure from source text.  The
rest of Codemble consumes this render-ready, deterministic representation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Protocol

NodeKind = Literal["module", "class", "function"]
EdgeKind = Literal["import", "call"]


class AdapterParseError(ValueError):
    """A supported language could not be mapped without guessing."""


@dataclass(frozen=True, slots=True)
class Node:
    """A parser-proven source structure.

    ``partial`` is true only for module nodes whose source could not be fully
    parsed.  Keeping that node makes parse failures visible without inventing
    any structure for the unreadable file.
    """

    id: str
    kind: NodeKind
    name: str
    language: str
    file: str
    lineno: int
    end_lineno: int
    loc: int
    region: str
    centrality: int = 0
    entrypoint_rank: int | None = None
    understood: bool = False
    partial: bool = False
    system_x: float = 0.0
    system_y: float = 0.0
    system_z: float = 0.0


@dataclass(frozen=True, slots=True)
class Edge:
    """A parser-observed relationship between source structures.

    A destination beginning with ``external:`` is intentionally not a graph
    node.  ``external`` lets consumers render or filter those observations
    without pretending third-party or dynamically-resolved structure exists.
    """

    src: str
    dst: str
    kind: EdgeKind
    certain: bool
    lineno: int
    external: bool = False


@dataclass(frozen=True, slots=True)
class ConceptAnnotation:
    """A language construct proven by an adapter at an exact source span."""

    node_id: str
    concept: str
    lineno: int
    end_lineno: int
    snippet: str


@dataclass(frozen=True, slots=True)
class Region:
    """A render-ready star system derived from parser-proven nodes."""

    id: str
    language: str
    loc: int
    centrality: int
    node_count: int
    understood: bool
    home: bool
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class RegionEdge:
    """An aggregated import route between two project regions."""

    src: str
    dst: str
    weight: int
    certain: bool


@dataclass(frozen=True, slots=True)
class Graph:
    """A deterministic, language-tagged project graph."""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    entrypoint_candidates: tuple[str, ...]
    project_root: str
    file_hashes: dict[str, str]
    selected_entrypoint: str | None = None
    concept_annotations: tuple[ConceptAnnotation, ...] = ()
    regions: tuple[Region, ...] = ()
    region_edges: tuple[RegionEdge, ...] = ()
    partial_files: tuple[str, ...] = ()
    schema_version: int = field(default=3, init=False)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation in canonical collection order."""

        nodes = sorted(self.nodes, key=lambda node: node.id)
        edges = sorted(
            self.edges,
            key=lambda edge: (
                edge.src,
                edge.dst,
                edge.kind,
                edge.lineno,
                edge.certain,
                edge.external,
            ),
        )
        return {
            "schema_version": self.schema_version,
            "nodes": [asdict(node) for node in nodes],
            "edges": [asdict(edge) for edge in edges],
            "entrypoint_candidates": list(self.entrypoint_candidates),
            "selected_entrypoint": self.selected_entrypoint,
            "project_root": self.project_root,
            "file_hashes": dict(sorted(self.file_hashes.items())),
            "concept_annotations": [
                asdict(annotation)
                for annotation in sorted(
                    self.concept_annotations,
                    key=lambda item: (item.node_id, item.lineno, item.concept, item.end_lineno),
                )
            ],
            "regions": [asdict(region) for region in sorted(self.regions, key=lambda item: item.id)],
            "region_edges": [
                asdict(edge)
                for edge in sorted(self.region_edges, key=lambda item: (item.src, item.dst))
            ],
            "partial_files": sorted(self.partial_files),
        }

    def to_json(self) -> str:
        """Serialize with stable formatting so identical input yields bytes."""

        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def write_json(self, destination: Path) -> None:
        """Write canonical graph JSON to ``destination``."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_json(), encoding="utf-8")


class LanguageAdapter(Protocol):
    """The seam every supported language implements."""

    language: str
    file_extensions: frozenset[str]
    ignored_directories: frozenset[str]

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact root and supported files this adapter will parse."""

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse ``path`` into a graph without inventing source structure."""

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only language constructs proven present in ``source``."""
