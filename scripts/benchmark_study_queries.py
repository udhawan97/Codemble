"""Benchmark indexed Study queries against the previous whole-graph scans."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import tempfile
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codemble.adapters.base import ConceptAnnotation, Edge, Graph, Node
from codemble.graph.impact import blast_radius
from codemble.graph.learning import LearningJourneyIndex
from codemble.llm.study import StudyService

DEFAULT_NODES = 10_000
DEFAULT_QUERIES = 20
_APPLICATION_ROLES = frozenset({"application-entry", "route-handler", "ui-renderer"})
_MAX_POSSIBLE_FRONTIER = 12


class _ScanAnnotations:
    def __init__(self, graph: Graph) -> None:
        self._graph = graph

    def get(
        self,
        node_id: str,
        default: tuple[ConceptAnnotation, ...] = (),
    ) -> tuple[ConceptAnnotation, ...]:
        matches = tuple(
            sorted(
                (
                    annotation
                    for annotation in self._graph.concept_annotations
                    if annotation.node_id == node_id
                ),
                key=lambda item: (item.lineno, item.concept, item.end_lineno),
            )
        )
        return matches or default


class _ScanEdges:
    def __init__(self, graph: Graph) -> None:
        self._graph = graph

    def get(self, _node_id: str, default: tuple[Edge, ...] = ()) -> tuple[Edge, ...]:
        return self._graph.edges or default


class _ScanImpact:
    def __init__(self, graph: Graph) -> None:
        self._graph = graph

    def build(self, node_id: str) -> dict[str, object]:
        return blast_radius(self._graph, node_id)


class _ScanJourney(LearningJourneyIndex):
    """The pre-index query behavior, retained only as a benchmark control."""

    def _possible_frontier(self, target: Node) -> tuple[list[dict[str, object]], int]:
        call_ancestors = _scan_reverse_reachable(target.id, self.certain_calls)
        target_module = self._module_for(target)
        import_ancestors = _scan_reverse_reachable(
            target_module.id,
            self.certain_imports,
        )
        home = self.nodes.get(self.graph.selected_entrypoint or "")
        if home is None:
            return [], 0
        certain_import_sources = _reachable(
            self._module_for(home).id,
            self.certain_imports,
        )
        certain_runtime_sources: set[str] = set()
        for evidence in self.graph.role_evidence:
            if evidence.role not in _APPLICATION_ROLES:
                continue
            surface = self.nodes.get(evidence.node_id)
            if (
                surface is None
                or self._module_for(surface).id not in certain_import_sources
            ):
                continue
            certain_runtime_sources.update(
                _reachable(surface.id, self.certain_calls)
            )
        certain_pairs = {
            (edge.src, edge.dst, edge.kind)
            for edge in self.graph.edges
            if edge.certain and not edge.external
        }
        entries: list[dict[str, object]] = []
        for edge in self.graph.edges:
            if (
                edge.certain
                or edge.external
                or edge.src not in self.nodes
                or edge.dst not in self.nodes
                or (edge.src, edge.dst, edge.kind) in certain_pairs
            ):
                continue
            relevant = (
                edge.kind == "call"
                and edge.src in certain_runtime_sources
                and edge.dst in call_ancestors
            ) or (
                edge.kind == "import"
                and edge.src in certain_import_sources
                and edge.dst in import_ancestors
            )
            if not relevant:
                continue
            source = self.nodes[edge.src]
            destination = self.nodes[edge.dst]
            entries.append(
                {
                    "relation": edge.kind,
                    "source_node_id": source.id,
                    "target_node_id": destination.id,
                    "certain": False,
                    "observation": _citation(source.file, edge.lineno),
                    "declaration": _citation(destination.file, destination.lineno),
                }
            )
        entries.sort(
            key=lambda item: (
                item["relation"],
                item["observation"]["file"],
                item["observation"]["line"],
                item["source_node_id"],
                item["target_node_id"],
            )
        )
        omitted = max(0, len(entries) - _MAX_POSSIBLE_FRONTIER)
        return entries[:_MAX_POSSIBLE_FRONTIER], omitted

    def _external_boundaries(
        self,
        canonical: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        route_nodes = {str(step["node_id"]) for step in canonical}
        entries = []
        for edge in self.graph.edges:
            if (
                not edge.external
                or edge.src not in route_nodes
                or edge.src not in self.nodes
            ):
                continue
            source = self.nodes[edge.src]
            entries.append(
                {
                    "source_node_id": edge.src,
                    "external_target": edge.dst,
                    "relation": edge.kind,
                    "certain": edge.certain,
                    "observation": _citation(source.file, edge.lineno),
                    "declaration": None,
                }
            )
        return sorted(
            entries,
            key=lambda item: (
                item["observation"]["file"],
                item["observation"]["line"],
                item["external_target"],
            ),
        )

    def _verification_candidates(self, target_id: str) -> list[dict[str, object]]:
        affects = {
            str(item["node_id"]): item
            for item in blast_radius(self.graph, target_id)["affects"]
        }
        candidates = []
        for evidence in self.graph.role_evidence:
            if evidence.role != "test" or evidence.node_id not in affects:
                continue
            node = self.nodes[evidence.node_id]
            impact = affects[evidence.node_id]
            candidates.append(
                {
                    "node_id": node.id,
                    "name": node.name,
                    "depth": impact["depth"],
                    "certain": impact["certain"],
                    "role_observation": _citation(evidence.file, evidence.lineno),
                    "declaration": _citation(node.file, node.lineno),
                }
            )
        return sorted(
            candidates,
            key=lambda item: (item["depth"], not item["certain"], item["node_id"]),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare repeated indexed Study queries with the previous whole-graph "
            "scan behavior and emit one private source-free JSON receipt."
        )
    )
    parser.add_argument("--nodes", type=int, default=DEFAULT_NODES)
    parser.add_argument("--queries", type=int, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.nodes < 2 or arguments.queries < 1:
        raise SystemExit("nodes must be at least 2 and queries must be positive")

    with tempfile.TemporaryDirectory(prefix="codemble-study-benchmark-") as temporary:
        project = Path(temporary)
        source = project / "fixture.py"
        raw = b"pass\n"
        source.write_bytes(raw)
        graph = _graph(arguments.nodes, project, raw)
        indexed = StudyService(graph, cache_root=project / "indexed-cache")
        scan = StudyService(graph, cache_root=project / "scan-cache")
        scan._annotations_by_node = _ScanAnnotations(graph)
        scan._edges_by_node = _ScanEdges(graph)
        scan._impact = _ScanImpact(graph)
        scan._journeys = _ScanJourney(graph)
        query_ids = _query_ids(arguments.nodes, arguments.queries)
        indexed.study(query_ids[0])
        scan.study(query_ids[0])
        indexed_times: list[float] = []
        scan_times: list[float] = []
        digests: list[dict[str, object]] = []
        for ordinal, node_id in enumerate(query_ids):
            first, second = (scan, indexed) if ordinal % 2 == 0 else (indexed, scan)
            first_payload, first_ms = _timed(first, node_id)
            second_payload, second_ms = _timed(second, node_id)
            if first is scan:
                scan_payload, scan_ms = first_payload, first_ms
                indexed_payload, indexed_ms = second_payload, second_ms
            else:
                indexed_payload, indexed_ms = first_payload, first_ms
                scan_payload, scan_ms = second_payload, second_ms
            if scan_payload != indexed_payload:
                raise RuntimeError("indexed Study payload diverged from scan control")
            scan_times.append(scan_ms)
            indexed_times.append(indexed_ms)
            digests.append(
                {
                    "query_ordinal": ordinal,
                    "sha256": hashlib.sha256(indexed_payload).hexdigest(),
                }
            )

    receipt = {
        "schema_version": 1,
        "fixture_kind": "deterministic-module-star",
        "nodes": arguments.nodes,
        "edges": arguments.nodes - 1,
        "queries": len(query_ids),
        "scan_control": "pre-index-whole-graph-query-scans",
        "scan_median_ms": round(statistics.median(scan_times), 3),
        "scan_p95_ms": round(_percentile(scan_times, 0.95), 3),
        "indexed_median_ms": round(statistics.median(indexed_times), 3),
        "indexed_p95_ms": round(_percentile(indexed_times, 0.95), 3),
        "exact_payload_equivalence": True,
        "payload_digests": digests,
    }
    _write_private(
        arguments.output,
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "nodes": arguments.nodes,
                "queries": len(query_ids),
                "output_mode": "private-0600",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _graph(nodes: int, root: Path, raw: bytes) -> Graph:
    entries = tuple(
        Node(
            id=f"python:module_{index:05d}.py",
            kind="module",
            name=f"module_{index:05d}",
            language="python",
            file="fixture.py",
            lineno=1,
            end_lineno=1,
            loc=1,
            region=f"python:module_{index:05d}.py",
            entrypoint_rank=0 if index == 0 else None,
        )
        for index in range(nodes)
    )
    edges = tuple(
        Edge(
            src=entries[0].id,
            dst=entries[index].id,
            kind="import",
            certain=True,
            lineno=1,
        )
        for index in range(1, nodes)
    )
    annotations = tuple(
        ConceptAnnotation(
            node_id=node.id,
            language="python",
            concept="type-hint",
            lineno=1,
            end_lineno=1,
            snippet="pass",
        )
        for node in entries
    )
    return Graph(
        nodes=entries,
        edges=edges,
        entrypoint_candidates=(entries[0].id,),
        selected_entrypoint=entries[0].id,
        project_root=str(root.resolve()),
        file_hashes={"fixture.py": hashlib.sha256(raw).hexdigest()},
        concept_annotations=annotations,
    )


def _query_ids(nodes: int, queries: int) -> tuple[str, ...]:
    count = min(queries, nodes - 1)
    indexes = {
        max(1, round(position * (nodes - 1) / count))
        for position in range(1, count + 1)
    }
    return tuple(f"python:module_{index:05d}.py" for index in sorted(indexes))


def _timed(service: StudyService, node_id: str) -> tuple[bytes, float]:
    started = time.perf_counter()
    payload = service.study(node_id)
    elapsed_ms = (time.perf_counter() - started) * 1_000
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return encoded, elapsed_ms


def _scan_reverse_reachable(
    target: str,
    adjacency: dict[str, tuple[Edge, ...]],
) -> set[str]:
    reverse: dict[str, set[str]] = {}
    for edges in adjacency.values():
        for edge in edges:
            reverse.setdefault(edge.dst, set()).add(edge.src)
    reached = {target}
    queue = deque([target])
    while queue:
        current = queue.popleft()
        for source in sorted(reverse.get(current, ())):
            if source in reached:
                continue
            reached.add(source)
            queue.append(source)
    return reached


def _reachable(
    start: str,
    adjacency: dict[str, tuple[Edge, ...]],
) -> set[str]:
    reached = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in adjacency.get(current, ()):
            if edge.dst in reached:
                continue
            reached.add(edge.dst)
            queue.append(edge.dst)
    return reached


def _citation(file: str, line: int) -> dict[str, object]:
    return {"file": file, "line": line, "citation": f"{file}:{line}"}


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))
    return ordered[index]


def _write_private(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)
    destination.chmod(0o600)


if __name__ == "__main__":
    raise SystemExit(main())
