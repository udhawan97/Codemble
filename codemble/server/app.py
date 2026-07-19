"""FastAPI application for the local Codemble experience."""

from __future__ import annotations

import tokenize
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from codemble.adapters.base import Graph


def create_app(graph: Graph, web_dist: Path | None = None) -> FastAPI:
    """Create an API and optional SPA server for one parsed project."""

    app = FastAPI(title="Codemble", version="0.0.1", docs_url=None, redoc_url=None)
    node_by_id = {node.id: node for node in graph.nodes}
    project_root = Path(graph.project_root).resolve()

    @app.get("/api/graph")
    def get_graph() -> dict[str, object]:
        return graph.to_dict()

    @app.get("/api/node/{node_id:path}/source")
    def get_node_source(node_id: str) -> dict[str, object]:
        node = node_by_id.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="That source node is not in this graph.")
        source_path = (project_root / node.file).resolve()
        if not source_path.is_relative_to(project_root) or not source_path.is_file():
            raise HTTPException(status_code=404, detail="The source file is no longer available.")
        try:
            with tokenize.open(source_path) as source_file:
                source = source_file.read()
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            raise HTTPException(
                status_code=422,
                detail="The source file exists but could not be decoded safely.",
            ) from error
        return {
            "id": node.id,
            "file": node.file,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "source": source,
        }

    distribution = web_dist or _default_web_dist()
    if distribution.is_dir() and (distribution / "index.html").is_file():
        assets = distribution / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/", include_in_schema=False)
        def spa_index() -> FileResponse:
            return FileResponse(distribution / "index.html")

        @app.get("/{spa_path:path}", include_in_schema=False)
        def spa_fallback(spa_path: str) -> FileResponse:
            candidate = (distribution / spa_path).resolve()
            if candidate.is_relative_to(distribution.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(distribution / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        def missing_web_build() -> dict[str, str]:
            return {
                "status": "web-build-missing",
                "action": "Run `npm install && npm run build` in web/.",
            }

    return app


def _default_web_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "web" / "dist"


__all__ = ["create_app"]
