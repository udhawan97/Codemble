"""Codemble command-line entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence

from codemble import __version__
from codemble.adapters.python_ast import PythonAstAdapter, PythonParseError
from codemble.server.runtime import serve_project

_SCALE_CAP = 300


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
    parse_command.add_argument(
        "--entrypoint", help="parser-ranked node ID to mark as Home"
    )
    serve_command = commands.add_parser("serve", help=argparse.SUPPRESS)
    serve_command.add_argument(
        "path", nargs="?", default=Path("."), type=Path, help="Python file or project directory"
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
            graph = PythonAstAdapter().parse(
                arguments.path, entrypoint=arguments.entrypoint
            )
            graph.write_json(arguments.out)
        except (OSError, PythonParseError) as error:
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
        except (OSError, PythonParseError) as error:
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
) -> Path:
    """Require an intentional subdirectory for projects above the v1 scale cap."""

    adapter = PythonAstAdapter()
    project_root, files = adapter.discover(requested)
    if explicit or len(files) <= _SCALE_CAP:
        return requested
    if not interactive:
        raise PythonParseError(
            f"found {len(files)} Python files; Phase 0 is capped at {_SCALE_CAP}. "
            "Re-run with `codemble --path PATH` to choose a project subdirectory."
        )

    counts: dict[str, int] = {}
    for file in files:
        relative = file.relative_to(project_root)
        directory = relative.parts[0] if len(relative.parts) > 1 else "."
        counts[directory] = counts.get(directory, 0) + 1
    suggestions = ", ".join(
        f"{directory} ({count})"
        for directory, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:6]
    )
    output_fn(
        f"Codemble found {len(files)} Python files; the Phase 0 limit is {_SCALE_CAP}."
    )
    if suggestions:
        output_fn(f"Top scopes: {suggestions}")

    while True:
        answer = input_fn("Subdirectory to map (or q to quit): ").strip()
        if answer.lower() in {"q", "quit"}:
            raise PythonParseError("project scope selection cancelled")
        candidate = (project_root / answer).expanduser().resolve()
        if not candidate.is_relative_to(project_root):
            output_fn("Choose a subdirectory inside the project root.")
            continue
        try:
            _, scoped_files = adapter.discover(candidate)
        except PythonParseError as error:
            output_fn(str(error))
            continue
        if len(scoped_files) > _SCALE_CAP:
            output_fn(
                f"That scope still has {len(scoped_files)} Python files; choose a smaller one."
            )
            continue
        return candidate


if __name__ == "__main__":
    raise SystemExit(main())
