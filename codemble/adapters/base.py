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
class Graph:
    """A deterministic, language-tagged project graph."""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    entrypoint_candidates: tuple[str, ...]
    project_root: str
    file_hashes: dict[str, str]
    partial_files: tuple[str, ...] = ()
    schema_version: int = field(default=1, init=False)

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
            "project_root": self.project_root,
            "file_hashes": dict(sorted(self.file_hashes.items())),
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

    def parse(self, path: Path) -> Graph:
        """Parse ``path`` into a graph without inventing source structure."""

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only language constructs proven present in ``source``."""
