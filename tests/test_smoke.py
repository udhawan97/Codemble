"""Smoke tests: package wiring. Real parser/graph tests arrive with M1."""

import codemble
from codemble.cli import main


def test_version() -> None:
    assert codemble.__version__


def test_cli_runs() -> None:
    assert main() == 0
