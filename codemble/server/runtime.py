"""Local server runtime used by the bare ``codemble <path>`` command."""

from __future__ import annotations

import socket
import sys
import threading
import webbrowser
from collections.abc import Callable
from pathlib import Path

import uvicorn

from codemble.adapters.project import ProjectIntake, ProjectParser
from codemble.server.app import PickerConfig, create_app


def available_port(host: str = "127.0.0.1") -> int:
    """Ask the operating system for an available local TCP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return int(listener.getsockname()[1])


_STAGE_COPY = {
    "discovering": "Finding your source files",
    "parsing": "Reading each file",
    "resolving": "Connecting imports and calls",
    "checks": "Building graph-only checks",
    "layout": "Placing your galaxy",
}


class TerminalProgress:
    """Print the same five stages the in-app loading screen shows."""

    def __init__(
        self,
        write: Callable[[str], None] | None = None,
        isatty: bool | None = None,
    ) -> None:
        self._write = write or (lambda text: sys.stdout.write(text))
        self._isatty = sys.stdout.isatty() if isatty is None else isatty
        self._stage: str | None = None
        self._detail: str | None = None
        self._counter_open = False
        self._total = 0
        self._done = 0

    def stage(self, stage: str) -> None:
        # serve_project announces discovering before handing off, and a
        # Path-input parse announces it again; one line is enough.
        if stage == self._stage:
            return
        if self._stage == "parsing" and self._isatty:
            self._write("\n")
        self._stage = stage
        self._write(f"{stage}: {_STAGE_COPY.get(stage, stage)}\n")

    def files_total(self, total: int) -> None:
        self._total = total

    def file_parsed(self) -> None:
        self._done += 1
        if self._isatty and self._total:
            self._write(f"\r  {self._done}/{self._total} files")
            self._counter_open = True

    def detail(self, detail: str) -> None:
        # Resolving's real sub-steps, one per line, so the terminal shows the
        # same movement the browser loading screen does instead of one pause.
        if detail == self._detail:
            return
        self._detail = detail
        if self._counter_open:
            self._write("\n")
            self._counter_open = False
        self._write(f"  {detail}\n")


def serve_project(
    path: Path | ProjectIntake,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    entrypoint: str | None = None,
) -> None:
    """Parse ``path`` and block while serving its local Codemble app."""

    reporter = TerminalProgress()
    # The CLI has usually discovered already (choose_project_scope hands over a
    # ProjectIntake), so announce the stage here; TerminalProgress collapses the
    # repeat when a bare Path makes ProjectParser announce it too.
    reporter.stage("discovering")
    graph = ProjectParser().parse(path, entrypoint=entrypoint, progress=reporter)
    selected_port = port or available_port(host)
    url = f"http://{host}:{selected_port}"
    reporter.stage("checks")
    # A PickerConfig rides along even for `codemble <path>` so the header's
    # Switch project control can re-arm the picker without a process restart.
    # The CLI --entrypoint deliberately does not carry over: it was chosen for
    # the named project, not for whatever the learner picks next.
    app = create_app(
        graph,
        picker=PickerConfig(browse_root=Path.home()),
        allowed_hosts=("127.0.0.1", "localhost", "testserver", host),
    )
    reporter.stage("layout")
    print(
        f"Codemble mapped {len(graph.nodes)} nodes across {len(graph.regions)} systems.\n"
        f"Open {url}"
    )
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=selected_port, log_level="warning")


def serve_picker(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    entrypoint: str | None = None,
) -> None:
    """Serve the picker-first app so the learner selects a project in the UI."""

    selected_port = port or available_port(host)
    url = f"http://{host}:{selected_port}"
    app = create_app(
        picker=PickerConfig(browse_root=Path.home(), entrypoint=entrypoint),
        allowed_hosts=("127.0.0.1", "localhost", "testserver", host),
    )
    print(f"Codemble is ready — pick your project folder in the browser.\nOpen {url}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=selected_port, log_level="warning")


__all__ = ["available_port", "serve_picker", "serve_project"]
