"""Codemble command-line entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from codemble import __version__
from codemble.adapters.python_ast import PythonAstAdapter, PythonParseError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codemble",
        description="Turn parser-proven project structure into Codemble graph data.",
    )
    parser.add_argument("--version", action="version", version=f"codemble {__version__}")
    commands = parser.add_subparsers(dest="command")
    parse_command = commands.add_parser("parse", help="parse a Python project into graph JSON")
    parse_command.add_argument("path", type=Path, help="Python file or project directory")
    parse_command.add_argument(
        "--out", required=True, type=Path, help="destination for deterministic graph JSON"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, returning a process exit status for testability."""

    parser = _parser()
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    if arguments.command is None:
        parser.print_help()
        return 0

    if arguments.command == "parse":
        try:
            graph = PythonAstAdapter().parse(arguments.path)
            graph.write_json(arguments.out)
        except (OSError, PythonParseError) as error:
            print(f"codemble: {error}", file=sys.stderr)
            return 2
        print(
            f"Wrote {len(graph.nodes)} nodes and {len(graph.edges)} edges to "
            f"{arguments.out}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
