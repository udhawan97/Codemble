"""The picker's background parse: guarded transitions, cancellation, failure."""

from __future__ import annotations

import threading

import pytest

from codemble.adapters.parse_progress import ParseCancelled
from codemble.server.parse_job import STAGES, ParseJob


def test_a_fresh_job_is_idle() -> None:
    assert ParseJob().snapshot() == {
        "state": "idle",
        "stage": None,
        "detail": None,
        "files_done": 0,
        "files_total": 0,
        "error": None,
    }


def test_begin_enters_the_discovering_stage() -> None:
    job = ParseJob()

    job.begin()

    assert job.active is True
    assert job.snapshot()["state"] == "parsing"
    assert job.snapshot()["stage"] == "discovering"


def test_a_job_runs_at_most_once() -> None:
    job = ParseJob()
    job.begin()

    with pytest.raises(RuntimeError):
        job.begin()


def test_a_finished_thread_reports_ready_with_its_final_counts() -> None:
    job = ParseJob()

    def work(reporter: ParseJob) -> None:
        reporter.files_total(2)
        reporter.stage("parsing")
        reporter.file_parsed()
        reporter.file_parsed()
        reporter.stage("checks")

    job.begin()
    job.start(work)

    assert job.wait(timeout=5) is True
    assert job.snapshot() == {
        "state": "ready",
        "stage": None,
        "detail": None,
        "files_done": 2,
        "files_total": 2,
        "error": None,
    }


def test_the_counter_flips_to_resolving_when_every_file_is_read() -> None:
    job = ParseJob()
    job.files_total(2)
    job.stage("parsing")

    job.file_parsed()
    assert job.snapshot()["stage"] == "parsing"

    job.file_parsed()
    assert job.snapshot()["stage"] == "resolving"


def test_cancelling_mid_parse_stops_at_the_next_file_and_returns_to_idle() -> None:
    job = ParseJob()
    reached_second_file = threading.Event()
    release = threading.Event()
    files_seen: list[int] = []

    def work(reporter: ParseJob) -> None:
        reporter.files_total(3)
        reporter.stage("parsing")
        reporter.file_parsed()
        files_seen.append(1)
        reached_second_file.set()
        assert release.wait(timeout=5)
        reporter.file_parsed()      # raises ParseCancelled
        files_seen.append(2)        # never reached

    job.begin()
    job.start(work)
    assert reached_second_file.wait(timeout=5)
    job.request_cancel()            # flag set before the worker is released
    release.set()

    assert job.wait(timeout=5) is True
    assert files_seen == [1]
    assert job.cancelled is True
    assert job.snapshot()["state"] == "idle"
    assert job.snapshot()["error"] is None


def test_a_crash_in_the_worker_becomes_an_error_state_not_a_hang() -> None:
    job = ParseJob()

    def work(_reporter: ParseJob) -> None:
        raise ValueError("tree-sitter exploded")

    job.begin()
    job.start(work)

    assert job.wait(timeout=5) is True
    assert job.snapshot()["state"] == "error"
    assert job.snapshot()["error"] == "tree-sitter exploded"
    assert job.active is False


def test_cancel_waits_for_a_worker_that_has_already_finished() -> None:
    job = ParseJob(runner=lambda work: work())
    job.begin()
    job.start(lambda reporter: None)

    job.cancel(timeout=5)

    assert job.cancelled is True


def test_an_unknown_stage_is_refused_rather_than_shown_to_a_learner() -> None:
    job = ParseJob()

    with pytest.raises(ValueError):
        job.stage("thinking")

    assert set(STAGES) == {
        "discovering",
        "parsing",
        "resolving",
        "checks",
        "layout",
    }


def test_a_cancelled_hook_raises_parse_cancelled() -> None:
    job = ParseJob()
    job.request_cancel()

    with pytest.raises(ParseCancelled):
        job.file_parsed()


def test_detail_is_reported_then_cleared_by_the_next_stage() -> None:
    job = ParseJob()
    job.stage("resolving")
    job.detail("Resolving imports and calls")
    assert job.snapshot()["detail"] == "Resolving imports and calls"

    # Re-announcing the same stage keeps a live sub-step visible.
    job.stage("resolving")
    assert job.snapshot()["detail"] == "Resolving imports and calls"

    # A real stage change retires the stale sub-step rather than stranding it.
    job.stage("checks")
    assert job.snapshot()["detail"] is None
