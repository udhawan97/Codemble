"""Smoke tests for package and CLI wiring."""

from pathlib import Path

import pytest

import codemble
from codemble.adapters.project import ProjectParseError
from codemble.cli import choose_project_scope, main
from codemble.server.app import _default_web_dist


def test_version() -> None:
    assert codemble.__version__


def test_bare_codemble_serves_the_picker(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "codemble.cli.serve_picker", lambda **kwargs: calls.update(kwargs)
    )

    assert main([]) == 0

    assert calls == {
        "host": "127.0.0.1",
        "port": 0,
        "open_browser": True,
        "entrypoint": None,
    }


def test_flags_without_a_path_still_serve_the_picker(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "codemble.cli.serve_picker", lambda **kwargs: calls.update(kwargs)
    )

    assert main(["--no-open", "--port", "8123"]) == 0

    assert calls["open_browser"] is False
    assert calls["port"] == 8123


def test_production_web_app_is_part_of_the_python_package() -> None:
    distribution = _default_web_dist()

    assert (distribution / "index.html").is_file()
    assert any((distribution / "assets").iterdir())


def test_the_v1_scale_cap_is_one_thousand_supported_files() -> None:
    from codemble.adapters.project import ProjectParser

    assert ProjectParser.scale_cap == 1000


def test_large_project_requires_an_explicit_or_interactive_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from codemble.adapters.project import ProjectParser

    # Exercise the mechanism, not the constant: building scale_cap+1 real
    # files would add a second of I/O to every run.
    monkeypatch.setattr(ProjectParser, "scale_cap", 3)
    project = tmp_path / "large"
    project.mkdir()
    for index in range(4):
        (project / f"module_{index:03d}.py").touch()
    small = project / "small"
    small.mkdir()
    (small / "one.py").touch()
    (small / "two.py").touch()

    with pytest.raises(ProjectParseError, match="Re-run with `codemble --path PATH`"):
        choose_project_scope(project, explicit=False, interactive=False)
    assert (
        choose_project_scope(project, explicit=True, interactive=False).path
        == project.resolve()
    )

    output: list[str] = []
    selected = choose_project_scope(
        project,
        explicit=False,
        interactive=True,
        input_fn=lambda _prompt: "small",
        output_fn=output.append,
    )
    assert selected.path == small.resolve()
    assert any("6 supported source files" in message for message in output)


def test_the_non_tty_scale_error_names_the_busiest_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A piped run gets the same actionable suggestions the prompt shows."""

    from codemble.adapters.project import ProjectParser

    monkeypatch.setattr(ProjectParser, "scale_cap", 2)
    project = tmp_path / "large"
    (project / "api").mkdir(parents=True)
    for index in range(3):
        (project / "api" / f"module_{index}.py").touch()
    (project / "web").mkdir()
    (project / "web" / "one.py").touch()

    with pytest.raises(ProjectParseError) as raised:
        choose_project_scope(project, explicit=False, interactive=False)

    assert "api (3)" in str(raised.value)
    assert "web (1)" in str(raised.value)
    assert "Re-run with `codemble --path PATH`" in str(raised.value)


def test_terminal_progress_prints_every_stage_in_order() -> None:
    from codemble.server.parse_job import STAGES
    from codemble.server.runtime import TerminalProgress

    lines: list[str] = []
    reporter = TerminalProgress(write=lines.append, isatty=False)

    reporter.stage("discovering")
    reporter.files_total(2)
    reporter.stage("parsing")
    reporter.file_parsed()
    reporter.file_parsed()
    reporter.stage("resolving")
    reporter.stage("checks")
    reporter.stage("layout")

    printed = "".join(lines)
    for stage in STAGES:
        assert stage in printed
    assert printed.index("discovering") < printed.index("parsing")
    assert printed.index("parsing") < printed.index("resolving")
    assert printed.index("resolving") < printed.index("checks")
    assert printed.index("checks") < printed.index("layout")


def test_terminal_progress_only_redraws_the_counter_on_a_tty() -> None:
    from codemble.server.runtime import TerminalProgress

    quiet: list[str] = []
    TerminalProgress(write=quiet.append, isatty=False).file_parsed()
    loud: list[str] = []
    loud_reporter = TerminalProgress(write=loud.append, isatty=True)
    loud_reporter.files_total(4)
    loud_reporter.stage("parsing")
    loud_reporter.file_parsed()

    assert "".join(quiet) == ""
    assert "\r" in "".join(loud)
    assert "1/4" in "".join(loud)


def test_terminal_progress_swallows_a_repeated_stage() -> None:
    """serve_project announces discovering; a Path parse announces it again."""

    from codemble.server.runtime import TerminalProgress

    lines: list[str] = []
    reporter = TerminalProgress(write=lines.append, isatty=False)
    reporter.stage("discovering")
    reporter.stage("discovering")

    assert len(lines) == 1


def test_serve_project_reports_the_full_stage_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from codemble.server import runtime

    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    fixture = Path(__file__).parent / "fixtures" / "sampleproj"
    lines: list[str] = []
    monkeypatch.setattr(
        runtime, "TerminalProgress", lambda **_kwargs: _StageRecorder(lines)
    )
    monkeypatch.setattr(runtime.uvicorn, "run", lambda *_a, **_k: None)

    runtime.serve_project(fixture, open_browser=False)

    # serve_project announces discovering, and ProjectParser.parse announces it
    # again for a Path input; TerminalProgress collapses the repeat, so compare
    # the deduplicated sequence.
    deduped = [
        stage
        for index, stage in enumerate(lines)
        if index == 0 or stage != lines[index - 1]
    ]
    assert deduped == [
        "discovering",
        "parsing",
        "resolving",
        "checks",
        "layout",
    ]


class _StageRecorder:
    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def stage(self, stage: str) -> None:
        self._sink.append(stage)

    def files_total(self, total: int) -> None:
        pass

    def file_parsed(self) -> None:
        pass
