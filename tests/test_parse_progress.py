"""The parse progress and cancellation seam."""

from __future__ import annotations

from pathlib import Path

import pytest

from codemble.adapters.parse_progress import (
    ParseCancelled,
    note_detail,
    note_file_parsed,
    reporting_detail,
    reporting_files,
)
from codemble.adapters.project import ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


class _Recorder:
    """A ParseProgress that records everything and never interferes."""

    def __init__(self) -> None:
        self.stages: list[str] = []
        self.total = 0
        self.files = 0
        self.details: list[str] = []

    def stage(self, stage: str) -> None:
        self.stages.append(stage)

    def files_total(self, total: int) -> None:
        self.total = total

    def file_parsed(self) -> None:
        self.files += 1

    def detail(self, detail: str) -> None:
        self.details.append(detail)


def test_note_file_parsed_is_a_no_op_when_nobody_is_listening() -> None:
    note_file_parsed()


def test_reporting_files_restores_the_previous_binding() -> None:
    outer: list[str] = []
    inner: list[str] = []
    with reporting_files(lambda: outer.append("outer")):
        with reporting_files(lambda: inner.append("inner")):
            note_file_parsed()
        note_file_parsed()

    assert inner == ["inner"]
    assert outer == ["outer"]


def test_progress_reporting_never_changes_the_parsed_graph() -> None:
    parser = ProjectParser()
    recorder = _Recorder()

    quiet = parser.parse(FIXTURE)
    reported = parser.parse(FIXTURE, progress=recorder)

    assert reported.to_json() == quiet.to_json()
    assert reported.to_json() == PythonAstAdapter().parse(FIXTURE).to_json()
    # Driving the resolving detail hook must not perturb the graph either.
    assert recorder.details


def test_note_detail_is_a_no_op_when_nobody_is_listening() -> None:
    note_detail("no listener bound")


def test_reporting_detail_restores_the_previous_binding() -> None:
    outer: list[str] = []
    inner: list[str] = []
    with reporting_detail(outer.append):
        with reporting_detail(inner.append):
            note_detail("inner")
        note_detail("outer")

    assert inner == ["inner"]
    assert outer == ["outer"]


def test_resolving_reports_real_named_substeps() -> None:
    parser = ProjectParser()
    recorder = _Recorder()

    parser.parse(FIXTURE, progress=recorder)

    # The resolving stage must not be a single frozen label: it reports the
    # real cross-file passes as they run, and every one is a non-empty string.
    assert len(recorder.details) >= 2
    assert all(isinstance(detail, str) and detail for detail in recorder.details)


def test_every_owned_file_is_counted_exactly_once() -> None:
    parser = ProjectParser()
    intake = parser.intake(POLYGLOT_FIXTURE)
    recorder = _Recorder()

    parser.parse(intake, progress=recorder)

    assert recorder.total == len(intake.files)
    assert recorder.files == recorder.total


def test_stages_are_reported_in_the_contract_order() -> None:
    parser = ProjectParser()
    recorder = _Recorder()

    parser.parse(FIXTURE, progress=recorder)

    assert recorder.stages == ["discovering", "parsing", "resolving"]


def test_a_cancelling_hook_stops_the_parse_between_files() -> None:
    class _Cancelling(_Recorder):
        def file_parsed(self) -> None:
            super().file_parsed()
            if self.files >= 2:
                raise ParseCancelled("stop")

    recorder = _Cancelling()

    with pytest.raises(ParseCancelled):
        ProjectParser().parse(FIXTURE, progress=recorder)

    assert recorder.files == 2
