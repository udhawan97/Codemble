"""Disposable, source-free parser scale benchmark contracts."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCHMARK = ROOT / "scripts" / "benchmark_parser_scale.py"
STUDY_BENCHMARK = ROOT / "scripts" / "benchmark_study_queries.py"


def test_scale_benchmark_emits_private_source_free_equivalence_receipts(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "scale.jsonl"

    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--sizes",
            "8",
            "--output",
            str(receipt),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    rows = [json.loads(line) for line in receipt.read_text(encoding="utf-8").splitlines()]
    assert [row["scenario"] for row in rows] == [
        "cold",
        "no-change",
        "one-file-change",
    ]
    assert all(row["files"] == 8 for row in rows)
    assert rows[1]["equivalent_to_fresh"] is True
    assert rows[2]["equivalent_to_fresh"] is True
    assert rows[1]["cache_hits_delta"] >= 1
    assert rows[1]["cache_file_entries"] == 8
    assert rows[2]["cache_partial_file_matches_delta"] == 7
    assert rows[2]["cache_file_invalidations_delta"] == 1
    forbidden = {"source", "root", "path", "file_hashes", "corpus"}
    assert all(not forbidden.intersection(row) for row in rows)
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600


def test_study_benchmark_emits_private_exact_scan_control_receipt(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "study.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(STUDY_BENCHMARK),
            "--nodes",
            "64",
            "--queries",
            "5",
            "--output",
            str(receipt),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    row = json.loads(receipt.read_text(encoding="utf-8"))
    assert row["nodes"] == 64
    assert row["queries"] == 5
    assert row["exact_payload_equivalence"] is True
    assert len(row["payload_digests"]) == 5
    forbidden = {"source", "root", "path", "file_hashes", "corpus"}
    assert not forbidden.intersection(row)
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
