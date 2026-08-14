"""Run a disposable picker server with an explicitly raised verification cap."""

from __future__ import annotations

import argparse
import resource
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codemble.adapters.project import ProjectParser
from codemble.server.app import PickerConfig, create_app


def main() -> int:
    arguments = _arguments()
    parser = ProjectParser()
    # This process exists only for the disposable cross-engine gate. The
    # product default remains 1,000 unless that gate passes every budget.
    parser.scale_cap = arguments.max_files
    codemble_app = create_app(
        picker=PickerConfig(browse_root=arguments.browse_root.resolve()),
        parser=parser,
        allowed_hosts=("127.0.0.1", "localhost"),
    )
    app = FastAPI(docs_url=None, redoc_url=None)

    @app.get("/__scale_gate__/metrics")
    def scale_gate_metrics() -> dict[str, int]:
        """Return this disposable process's OS-maintained RSS high-water mark."""

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return {
            "max_rss_bytes": value if sys.platform == "darwin" else value * 1024
        }

    app.mount("/", codemble_app)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=arguments.port,
        log_level="warning",
    )
    return 0


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browse-root", type=Path, required=True)
    parser.add_argument("--max-files", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    if arguments.max_files < 1:
        parser.error("--max-files must be positive")
    return arguments


if __name__ == "__main__":
    raise SystemExit(main())
