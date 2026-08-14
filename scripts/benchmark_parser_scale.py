"""Run disposable cold, warm, and one-change parser scale scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codemble.adapters.project import ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph import build_map

DEFAULT_SIZES = (1_000, 5_000, 10_000)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate private sparse-Python projects in a temporary directory and "
            "emit source-free JSONL timing/equivalence receipts."
        )
    )
    parser.add_argument("--sizes", nargs="+", type=int, default=DEFAULT_SIZES)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    sizes = tuple(dict.fromkeys(arguments.sizes))
    if not sizes or any(size < 1 for size in sizes):
        raise SystemExit("benchmark sizes must be positive")

    rows: list[dict[str, object]] = []
    for size in sizes:
        with tempfile.TemporaryDirectory(prefix="codemble-scale-") as temporary:
            project = Path(temporary) / "project"
            _generate_project(project, size)
            rows.extend(_measure_size(project, size))

    encoded = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    if arguments.output is None:
        print(encoded, end="")
    else:
        _write_private(arguments.output, encoded)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "receipts": len(rows),
                    "sizes": list(sizes),
                    "output_mode": "private-0600",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return 0


def _measure_size(project: Path, size: int) -> list[dict[str, object]]:
    parser = ProjectParser((PythonAstAdapter(),))
    before = parser.cache_info()
    cold_graph, cold_graph_bytes, cold_map_bytes, cold_timing = _run(parser, project)
    after_cold = parser.cache_info()
    cold = _receipt(
        "cold",
        size,
        cold_graph,
        cold_graph_bytes,
        cold_map_bytes,
        cold_timing,
        before,
        after_cold,
        equivalent=None,
    )

    warm_graph, warm_graph_bytes, warm_map_bytes, warm_timing = _run(parser, project)
    after_warm = parser.cache_info()
    warm_equivalent = (
        warm_graph_bytes == cold_graph_bytes and warm_map_bytes == cold_map_bytes
    )
    warm = _receipt(
        "no-change",
        size,
        warm_graph,
        warm_graph_bytes,
        warm_map_bytes,
        warm_timing,
        after_cold,
        after_warm,
        equivalent=warm_equivalent,
    )

    changed = project / f"module_{size - 1:05d}.py"
    changed.write_text(
        changed.read_text(encoding="utf-8") + "# one-file benchmark change\n",
        encoding="utf-8",
    )
    changed_graph, changed_graph_bytes, changed_map_bytes, changed_timing = _run(
        parser, project
    )
    after_changed = parser.cache_info()
    fresh = ProjectParser((PythonAstAdapter(),))
    fresh_graph, fresh_graph_bytes, fresh_map_bytes, _ = _run(fresh, project)
    changed_equivalent = (
        changed_graph.to_json() == fresh_graph.to_json()
        and changed_graph_bytes == fresh_graph_bytes
        and changed_map_bytes == fresh_map_bytes
    )
    one_change = _receipt(
        "one-file-change",
        size,
        changed_graph,
        changed_graph_bytes,
        changed_map_bytes,
        changed_timing,
        after_warm,
        after_changed,
        equivalent=changed_equivalent,
    )

    if not warm_equivalent or not changed_equivalent:
        raise RuntimeError("warm parser output diverged from a fresh parser")
    return [cold, warm, one_change]


def _run(
    parser: ProjectParser,
    project: Path,
) -> tuple[object, bytes, bytes, dict[str, float]]:
    started = time.perf_counter()
    graph = parser.parse(project, explicit=True)
    parsed = time.perf_counter()
    graph_bytes = graph.to_json().encode("utf-8")
    serialized = time.perf_counter()
    map_bytes = json.dumps(
        build_map(graph), separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    finished = time.perf_counter()
    return graph, graph_bytes, map_bytes, {
        "parse_seconds": parsed - started,
        "graph_serialize_seconds": serialized - parsed,
        "map_seconds": finished - serialized,
        "total_seconds": finished - started,
    }


def _receipt(
    scenario: str,
    files: int,
    graph: object,
    graph_bytes: bytes,
    map_bytes: bytes,
    timing: dict[str, float],
    before: dict[str, int],
    after: dict[str, int],
    *,
    equivalent: bool | None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "fixture_kind": "deterministic-sparse-python-import-chain",
        "python": platform.python_version(),
        "files": files,
        "scenario": scenario,
        "parse_seconds": round(timing["parse_seconds"], 6),
        "graph_serialize_seconds": round(timing["graph_serialize_seconds"], 6),
        "map_seconds": round(timing["map_seconds"], 6),
        "total_seconds": round(timing["total_seconds"], 6),
        "max_rss_bytes": _max_rss_bytes(),
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "regions": len(graph.regions),
        "graph_bytes": len(graph_bytes),
        "map_bytes": len(map_bytes),
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
        "map_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "cache_hits_delta": after["hits"] - before["hits"],
        "cache_misses_delta": after["misses"] - before["misses"],
        "cache_evictions_delta": after["evictions"] - before["evictions"],
        "cache_entries": after["entries"],
        "cache_file_entries": after["file_entries"],
        "cache_bytes": after["bytes"],
        "cache_partial_file_matches_delta": (
            after["partial_file_matches"] - before["partial_file_matches"]
        ),
        "cache_file_invalidations_delta": (
            after["file_invalidations"] - before["file_invalidations"]
        ),
        "cache_resolution_refreshes_delta": (
            after["resolution_refreshes"] - before["resolution_refreshes"]
        ),
        "equivalent_to_fresh": equivalent,
    }


def _generate_project(project: Path, size: int) -> None:
    project.mkdir(parents=True)
    for index in range(size):
        previous = (
            f"import module_{index - 1:05d}\n\n" if index > 0 else ""
        )
        (project / f"module_{index:05d}.py").write_text(
            f"{previous}def function_{index:05d}() -> int:\n    return {index}\n",
            encoding="utf-8",
        )


def _max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


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
