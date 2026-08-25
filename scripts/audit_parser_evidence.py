"""Diff parser-owned facts against the bounded nine-language oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codemble.adapters.csharp_tree_sitter import CSharpAdapter
from codemble.adapters.go_tree_sitter import GoAdapter
from codemble.adapters.java_tree_sitter import JavaAdapter
from codemble.adapters.php_tree_sitter import PHPAdapter
from codemble.adapters.project import ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.adapters.ruby_tree_sitter import RubyAdapter
from codemble.adapters.rust_tree_sitter import RustAdapter
from codemble.adapters.typescript_tree_sitter import (
    JavaScriptTypeScriptAdapter,
)
from codemble.graph.learning import LearningJourneyIndex

FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_ORACLE = FIXTURES / "parser_evidence_oracle.json"
_PRIORITIES = {
    1: "invented-certain-facts",
    2: "false-role-home-or-journey",
    3: "missing-certain-journey-structure",
    4: "bounded-precision-or-coverage",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit parser evidence against hand-authored oracle scopes."
    )
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    arguments = parser.parse_args()
    oracle_bytes = arguments.oracle.read_bytes()
    oracle = json.loads(oracle_bytes)
    if oracle.get("schema_version") != 1:
        raise SystemExit("parser evidence oracle schema_version must be 1")

    regressions: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    candidates: list[dict[str, str]] = []
    for case in oracle["cases"]:
        case_regressions, summary = _evaluate_case(case)
        regressions.extend(case_regressions)
        summaries.append(summary)
        candidates.extend(
            {"case": case["id"], "candidate": candidate}
            for candidate in case.get("known_gaps", [])
        )

    plan = _evidence_gap_plan(regressions, candidates)
    result = {
        "status": "fail" if regressions else "pass",
        "schema_version": 1,
        "oracle_sha256": hashlib.sha256(oracle_bytes).hexdigest(),
        "cases": len(summaries),
        "case_summaries": summaries,
        "regressions": regressions,
        "evidence_gap_plan": plan,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 1 if regressions else 0


def _evaluate_case(
    case: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    with ExitStack() as stack:
        root = _case_root(case, stack)
        graph = _project_parser(case["adapter"]).parse(root, explicit=True)

    regressions: list[dict[str, object]] = []
    case_id = str(case["id"])
    _diff(
        regressions,
        case_id,
        "languages",
        case["languages"],
        sorted({node.language for node in graph.nodes}),
    )
    _diff(
        regressions,
        case_id,
        "partial_files",
        case["partial_files"],
        list(graph.partial_files),
    )
    actual_unsupported = [
        {
            "extension": source.extension,
            "language": source.language,
            "count": source.count,
        }
        for source in graph.unsupported_sources
    ]
    _diff(
        regressions,
        case_id,
        "unsupported_sources",
        case["unsupported_sources"],
        actual_unsupported,
    )

    entrypoints = {
        node.id: node.entrypoint_rank
        for node in graph.nodes
        if node.entrypoint_rank is not None
    }
    _scalar_diff(
        regressions,
        case_id,
        "entrypoint_count",
        int(case["entrypoints"]["count"]),
        len(entrypoints),
    )
    _scalar_diff(
        regressions,
        case_id,
        "home",
        case["entrypoints"]["selected"],
        graph.selected_entrypoint,
    )
    required_entrypoints = [tuple(item) for item in case["entrypoints"]["required"]]
    actual_entrypoints = [(node_id, rank) for node_id, rank in entrypoints.items()]
    _required(
        regressions,
        case_id,
        "entrypoints_required",
        required_entrypoints,
        actual_entrypoints,
    )

    actual_roles = [
        (
            evidence.node_id,
            evidence.role,
            evidence.rule_id,
            evidence.file,
            evidence.lineno,
            evidence.end_lineno,
        )
        for evidence in graph.role_evidence
    ]
    _scalar_diff(
        regressions,
        case_id,
        "role_count",
        int(case["roles"]["count"]),
        len(actual_roles),
    )
    _required(
        regressions,
        case_id,
        "roles_required",
        [tuple(item) for item in case["roles"]["required"]],
        actual_roles,
    )

    edge_sources = set(case["edge_sources"])
    actual_edges = [
        (edge.src, edge.dst, edge.kind, edge.certain, edge.lineno, edge.external)
        for edge in graph.edges
        if edge.src in edge_sources
    ]
    _diff(
        regressions,
        case_id,
        "edges",
        [tuple(item) for item in case["edges"]],
        actual_edges,
    )

    concept_nodes = set(case["concept_nodes"])
    actual_concepts = [
        (
            annotation.node_id,
            annotation.language,
            annotation.concept,
            annotation.lineno,
            annotation.end_lineno,
            annotation.snippet,
        )
        for annotation in graph.concept_annotations
        if annotation.node_id in concept_nodes
    ]
    _diff(
        regressions,
        case_id,
        "concepts",
        [tuple(item) for item in case["concepts"]],
        actual_concepts,
    )

    journey_node, expected_status, expected_runtime, expected_break = case["journey"]
    journey = LearningJourneyIndex(graph).build(journey_node)
    actual_journey = (
        journey_node,
        journey["status"],
        journey["runtime_status"],
        (journey.get("break") or {}).get("reason"),
    )
    _diff(
        regressions,
        case_id,
        "journey",
        [(journey_node, expected_status, expected_runtime, expected_break)],
        [actual_journey],
    )

    return regressions, {
        "id": case_id,
        "languages": len({node.language for node in graph.nodes}),
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "concepts": len(graph.concept_annotations),
        "roles": len(graph.role_evidence),
        "partial_files": len(graph.partial_files),
        "regressions": len(regressions),
    }


def _case_root(case: dict[str, Any], stack: ExitStack) -> Path:
    if "fixture" in case:
        return FIXTURES / case["fixture"]
    temporary = Path(stack.enter_context(tempfile.TemporaryDirectory())) / "mixed"
    temporary.mkdir()
    for fixture in case["fixtures"]:
        shutil.copytree(FIXTURES / fixture, temporary / fixture)
    for relative, content in case.get("extra_files", []):
        destination = temporary / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return temporary


def _project_parser(adapter: str) -> ProjectParser:
    adapters = {
        "python": PythonAstAdapter,
        "javascript": JavaScriptTypeScriptAdapter,
        "go": GoAdapter,
        "java": JavaAdapter,
        "rust": RustAdapter,
        "csharp": CSharpAdapter,
        "ruby": RubyAdapter,
        "php": PHPAdapter,
    }
    if adapter == "default":
        return ProjectParser()
    try:
        return ProjectParser((adapters[adapter](),))
    except KeyError as error:
        raise ValueError(f"unknown oracle adapter: {adapter}") from error


def _diff(
    regressions: list[dict[str, object]],
    case: str,
    category: str,
    expected: list[Any],
    actual: list[Any],
) -> None:
    expected_rows = {_canonical(row): row for row in expected}
    actual_rows = {_canonical(row): row for row in actual}
    missing = [expected_rows[key] for key in sorted(expected_rows.keys() - actual_rows)]
    extra = [actual_rows[key] for key in sorted(actual_rows.keys() - expected_rows)]
    if missing or extra:
        regressions.append(
            {
                "case": case,
                "category": category,
                "missing": _json_rows(missing),
                "extra": _json_rows(extra),
            }
        )


def _required(
    regressions: list[dict[str, object]],
    case: str,
    category: str,
    expected: list[tuple[Any, ...]],
    actual: list[tuple[Any, ...]],
) -> None:
    actual_keys = {_canonical(item) for item in actual}
    missing = [item for item in expected if _canonical(item) not in actual_keys]
    if missing:
        regressions.append(
            {
                "case": case,
                "category": category,
                "missing": _json_rows(missing),
                "extra": [],
            }
        )


def _scalar_diff(
    regressions: list[dict[str, object]],
    case: str,
    category: str,
    expected: object,
    actual: object,
) -> None:
    if expected != actual:
        regressions.append(
            {
                "case": case,
                "category": category,
                "missing": [expected],
                "extra": [actual],
            }
        )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _json_rows(rows: list[Any]) -> list[object]:
    return [list(row) if isinstance(row, tuple) else row for row in rows]


def _evidence_gap_plan(
    regressions: list[dict[str, object]],
    candidates: list[dict[str, str]],
) -> list[dict[str, object]]:
    buckets: dict[int, list[dict[str, object]]] = {priority: [] for priority in _PRIORITIES}
    for regression in regressions:
        for direction in ("extra", "missing"):
            rows = regression[direction]
            if not rows:
                continue
            priority = _priority(regression["category"], direction, rows)
            buckets[priority].append(
                {
                    "case": regression["case"],
                    "category": regression["category"],
                    "direction": direction,
                }
            )
    return [
        {
            "priority": priority,
            "kind": _PRIORITIES[priority],
            "regressions": buckets[priority],
            "candidates": candidates if priority == 4 else [],
            "eligibility": (
                "A new semantic rule needs a minimal regression fixture, no new "
                "false-positive oracle failures, and corroborating real-corpus evidence."
            ),
        }
        for priority in sorted(_PRIORITIES)
    ]


def _priority(category: object, direction: str, rows: object) -> int:
    if category == "edges":
        if direction == "extra" and any(_certain_edge(row) for row in rows):
            return 1
        if direction == "missing" and any(_certain_edge(row) for row in rows):
            return 3
        return 4
    if category in {
        "entrypoint_count",
        "entrypoints_required",
        "home",
        "journey",
        "role_count",
        "roles_required",
    }:
        return 2
    return 4


def _certain_edge(row: object) -> bool:
    return isinstance(row, (list, tuple)) and len(row) > 3 and row[3] is True


if __name__ == "__main__":
    raise SystemExit(main())
