"""Public semantic-oracle CLI contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ORACLE = ROOT / "tests" / "fixtures" / "parser_evidence_oracle.json"
AUDIT = ROOT / "scripts" / "audit_parser_evidence.py"


def _run(oracle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT), "--oracle", str(oracle)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_committed_oracle_matches_all_seven_languages_and_mixed_project() -> None:
    completed = _run(ORACLE)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["cases"] == 8
    assert payload["regressions"] == []
    assert [bucket["priority"] for bucket in payload["evidence_gap_plan"]] == [
        1,
        2,
        3,
        4,
    ]


def test_oracle_detects_both_false_positive_and_omitted_evidence(
    tmp_path: Path,
) -> None:
    payload = json.loads(ORACLE.read_text(encoding="utf-8"))
    python = payload["cases"][0]
    python["edges"].remove(
        ["app.main", "pkg.helpers.log", "call", True, 11, False]
    )
    python["edges"].append(
        ["app.main", "invented.missing", "call", True, 99, False]
    )
    changed = tmp_path / "oracle.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")

    completed = _run(changed)

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["status"] == "fail"
    edge_regressions = [
        regression
        for regression in result["regressions"]
        if regression["case"] == "python" and regression["category"] == "edges"
    ]
    assert any(regression["extra"] for regression in edge_regressions)
    assert any(regression["missing"] for regression in edge_regressions)
    assert result["evidence_gap_plan"][0]["regressions"]
    assert result["evidence_gap_plan"][2]["regressions"]
