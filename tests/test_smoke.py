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


def test_large_project_requires_an_explicit_or_interactive_scope(tmp_path: Path) -> None:
    project = tmp_path / "large"
    project.mkdir()
    for index in range(299):
        (project / f"module_{index:03d}.py").touch()
    small = project / "small"
    small.mkdir()
    (small / "one.py").touch()
    (small / "two.py").touch()

    with pytest.raises(ProjectParseError, match="Re-run with `codemble --path PATH`"):
        choose_project_scope(project, explicit=False, interactive=False)
    assert choose_project_scope(project, explicit=True, interactive=False).path == project.resolve()

    output: list[str] = []
    selected = choose_project_scope(
        project,
        explicit=False,
        interactive=True,
        input_fn=lambda _prompt: "small",
        output_fn=output.append,
    )
    assert selected.path == small.resolve()
    assert any("301 supported source files" in message for message in output)
