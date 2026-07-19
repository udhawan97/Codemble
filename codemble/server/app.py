"""FastAPI application for the local Codemble experience."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from codemble.adapters.base import Graph
from codemble.llm.study import StudyService, StudySourceError, UnknownNodeError


def create_app(
    graph: Graph,
    web_dist: Path | None = None,
    study_service: StudyService | None = None,
) -> FastAPI:
    """Create an API and optional SPA server for one parsed project."""

    app = FastAPI(title="Codemble", version="0.0.1", docs_url=None, redoc_url=None)
    studies = study_service or StudyService.from_environment(graph)

    @app.get("/api/graph")
    def get_graph() -> dict[str, object]:
        return graph.to_dict()

    @app.get("/api/node/{node_id:path}/study")
    def get_node_study(node_id: str) -> dict[str, object]:
        try:
            return studies.study(node_id)
        except UnknownNodeError as error:
            raise HTTPException(
                status_code=404, detail="That source node is not in this graph."
            ) from error
        except StudySourceError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

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
