"""Codemble command-line entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence

from codemble import __version__
from codemble.adapters.project import (
    ProjectIntake,
    ProjectParseError,
    ProjectParser,
    ProjectScaleError,
)
from codemble.server.runtime import serve_project

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codemble",
        description="Turn parser-proven project structure into Codemble graph data.",
    )
    parser.add_argument("--version", action="version", version=f"codemble {__version__}")
    commands = parser.add_subparsers(dest="command")
    parse_command = commands.add_parser("parse", help="parse a project into graph JSON")
    parse_command.add_argument("path", type=Path, help="source file or project directory")
    parse_command.add_argument(
        "--out", required=True, type=Path, help="destination for deterministic graph JSON"
    )
    parse_command.add_argument(
        "--entrypoint", help="parser-ranked node ID to mark as Home"
    )
    serve_command = commands.add_parser("serve", help=argparse.SUPPRESS)
    serve_command.add_argument(
        "path", nargs="?", default=Path("."), type=Path, help="source file or project directory"
    )
    serve_command.add_argument(
        "--path",
        dest="scope_path",
        type=Path,
        help="explicit project or subdirectory scope; skips the large-project prompt",
    )
    serve_command.add_argument(
        "--entrypoint", help="parser-ranked node ID to mark as Home"
    )
    serve_command.add_argument("--host", default="127.0.0.1")
    serve_command.add_argument("--port", default=0, type=int)
    serve_command.add_argument("--no-open", action="store_true", help="do not open a browser")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, returning a process exit status for testability."""

    parser = _parser()
    raw_arguments = list(argv) if argv is not None else list(sys.argv[1:])
    if raw_arguments and raw_arguments[0] not in {"parse", "serve", "--version", "-h", "--help"}:
        raw_arguments.insert(0, "serve")
    arguments = parser.parse_args(raw_arguments)
    if arguments.command is None:
        parser.print_help()
        return 0

    if arguments.command == "parse":
        try:
            graph = ProjectParser().parse(
                arguments.path,
                entrypoint=arguments.entrypoint,
                explicit=True,
            )
            graph.write_json(arguments.out)
        except (OSError, ProjectParseError) as error:
            print(f"codemble: {error}", file=sys.stderr)
            return 2
        print(
            f"Wrote {len(graph.nodes)} nodes and {len(graph.edges)} edges to "
            f"{arguments.out}"
        )
    elif arguments.command == "serve":
        try:
            requested = arguments.scope_path or arguments.path
            selected_path = choose_project_scope(
                requested,
                explicit=arguments.scope_path is not None,
                interactive=sys.stdin.isatty(),
            )
            serve_project(
                selected_path,
                host=arguments.host,
                port=arguments.port,
                open_browser=not arguments.no_open,
                entrypoint=arguments.entrypoint,
            )
        except (OSError, ProjectParseError) as error:
            print(f"codemble: {error}", file=sys.stderr)
            return 2
    return 0


def choose_project_scope(
    requested: Path,
    *,
    explicit: bool,
    interactive: bool,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> ProjectIntake:
    """Require an intentional subdirectory for projects above the v1 scale cap."""

    parser = ProjectParser()
    try:
        return parser.intake(requested, explicit=explicit)
    except ProjectScaleError as error:
        if not interactive:
            raise
        intake = error.intake
        scale_cap = error.scale_cap

    counts: dict[str, int] = {}
    for file in intake.files:
        relative = file.relative_to(intake.root)
        directory = relative.parts[0] if len(relative.parts) > 1 else "."
        counts[directory] = counts.get(directory, 0) + 1
    suggestions = ", ".join(
        f"{directory} ({count})"
        for directory, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:6]
    )
    output_fn(
        f"Codemble found {len(intake.files)} supported source files; "
        f"the limit is {scale_cap}."
    )
    if suggestions:
        output_fn(f"Top scopes: {suggestions}")

    while True:
        answer = input_fn("Subdirectory to map (or q to quit): ").strip()
        if answer.lower() in {"q", "quit"}:
            raise ProjectParseError("project scope selection cancelled")
        candidate = (intake.root / answer).expanduser().resolve()
        if not candidate.is_relative_to(intake.root):
            output_fn("Choose a subdirectory inside the project root.")
            continue
        try:
            return parser.intake(candidate)
        except ProjectScaleError as error:
            output_fn(
                f"That scope still has {len(error.intake.files)} supported source files; "
                "choose a smaller one."
            )
        except ProjectParseError as error:
            output_fn(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
