"""Smoke tests for package and CLI wiring."""

import codemble
from codemble.cli import main


def test_version() -> None:
    assert codemble.__version__


def test_cli_runs(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main([]) == 0
    assert "usage: codemble" in capsys.readouterr().out
