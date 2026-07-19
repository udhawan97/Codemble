"""File-hash-scoped local progress for parser regions."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

from codemble.adapters.base import Graph

_SCHEMA_VERSION = 1


class UnknownRegionError(KeyError):
    """Raised when progress is requested for a region outside the graph."""


class ProgressStore:
    """Persist understood regions without letting stale source stay lit."""

    def __init__(self, graph: Graph, root: Path | None = None) -> None:
        self._graph = graph
        self._root = root or Path.home() / ".codemble" / "progress"
        project_key = hashlib.sha256(graph.project_root.encode()).hexdigest()[:20]
        self.path = self._root / f"{project_key}.json"
        self._signatures = _region_signatures(graph)

    def understood_regions(self) -> frozenset[str]:
        """Return only persisted regions whose current file hashes still match."""

        saved = self._read().get("regions", {})
        if not isinstance(saved, dict):
            return frozenset()
        return frozenset(
            region_id
            for region_id, signature in self._signatures.items()
            if isinstance(saved.get(region_id), dict)
            and saved[region_id].get("signature") == signature
        )

    def mark_understood(self, region_id: str) -> None:
        """Persist the current signature for one proven region."""

        signature = self._signatures.get(region_id)
        if signature is None:
            raise UnknownRegionError(region_id)
        payload = self._read()
        saved = payload.get("regions")
        regions = saved if isinstance(saved, dict) else {}
        regions[region_id] = {"signature": signature}
        self._write(
            {
                "schema_version": _SCHEMA_VERSION,
                "project_root": self._graph.project_root,
                "regions": dict(sorted(regions.items())),
            }
        )

    def hydrated_graph(self) -> Graph:
        """Project valid progress onto immutable render data."""

        understood = self.understood_regions()
        nodes = tuple(
            replace(node, understood=node.region in understood) for node in self._graph.nodes
        )
        regions = tuple(
            replace(region, understood=region.id in understood)
            for region in self._graph.regions
        )
        return replace(self._graph, nodes=nodes, regions=regions)

    def _read(self) -> dict[str, object]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return self._empty_payload()
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _SCHEMA_VERSION
            or payload.get("project_root") != self._graph.project_root
        ):
            return self._empty_payload()
        return payload

    def _write(self, payload: dict[str, object]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{os.getpid()}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _empty_payload(self) -> dict[str, object]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "project_root": self._graph.project_root,
            "regions": {},
        }


def _region_signatures(graph: Graph) -> dict[str, str]:
    files_by_region: dict[str, set[str]] = {}
    for node in graph.nodes:
        files_by_region.setdefault(node.region, set()).add(node.file)
    signatures: dict[str, str] = {}
    for region_id, files in files_by_region.items():
        evidence = [
            (file, graph.file_hashes.get(file, "missing")) for file in sorted(files)
        ]
        signatures[region_id] = hashlib.sha256(
            json.dumps(evidence, separators=(",", ":")).encode()
        ).hexdigest()
    return signatures


__all__ = ["ProgressStore", "UnknownRegionError"]
