"""Local server runtime used by the bare ``codemble <path>`` command."""

from __future__ import annotations

import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.server.app import create_app


def available_port(host: str = "127.0.0.1") -> int:
    """Ask the operating system for an available local TCP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return int(listener.getsockname()[1])


def serve_project(
    path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
    entrypoint: str | None = None,
) -> None:
    """Parse ``path`` and block while serving its local Codemble app."""

    graph = PythonAstAdapter().parse(path, entrypoint=entrypoint)
    selected_port = port or available_port(host)
    url = f"http://{host}:{selected_port}"
    app = create_app(graph)
    print(
        f"Codemble mapped {len(graph.nodes)} nodes across {len(graph.regions)} systems.\n"
        f"Open {url}"
    )
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=selected_port, log_level="warning")


__all__ = ["available_port", "serve_project"]
