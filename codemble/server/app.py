"""FastAPI application for the local Codemble experience."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codemble import __version__
from codemble.adapters.base import Graph
from codemble.adapters.project import (
    ProjectParseError,
    ProjectParser,
    ProjectScaleError,
)
from codemble.checks import CheckService, InvalidCheckSubmission, UnknownCheckError
from codemble.llm.study import StudyService, StudySourceError, UnknownNodeError
from codemble.progress import list_recent_projects


class CheckSubmission(BaseModel):
    """Option IDs selected for one graph-owned active check."""

    selected_ids: list[str]


class EntrypointSelection(BaseModel):
    """One parser-ranked candidate chosen as Home."""

    node_id: str


class ProjectSelection(BaseModel):
    """One learner-chosen folder to parse into the session's project."""

    path: str


@dataclass(frozen=True)
class PickerConfig:
    """Filesystem scope and parse settings for the in-app project picker."""

    browse_root: Path
    entrypoint: str | None = None


class _ProjectState:
    """One-shot binding from picker selection to live project services."""

    def __init__(self) -> None:
        self.checks: CheckService | None = None
        self.studies: StudyService | None = None

    @property
    def bound(self) -> bool:
        return self.checks is not None

    def bind(self, graph: Graph) -> None:
        self.studies = StudyService.from_environment(graph)
        self.checks = CheckService(graph)


def create_app(
    graph: Graph | None = None,
    web_dist: Path | None = None,
    study_service: StudyService | None = None,
    check_service: CheckService | None = None,
    *,
    picker: PickerConfig | None = None,
) -> FastAPI:
    """Create an API and optional SPA server for one local project."""

    if graph is None and picker is None:
        raise ValueError("create_app needs a parsed graph or a PickerConfig")
    app = FastAPI(title="Codemble", version=__version__, docs_url=None, redoc_url=None)
    state = _ProjectState()
    if graph is not None:
        state.studies = study_service or StudyService.from_environment(graph)
        state.checks = check_service or CheckService(graph)

    def _services() -> tuple[CheckService, StudyService]:
        if state.checks is None or state.studies is None:
            raise HTTPException(status_code=409, detail="No project selected yet.")
        return state.checks, state.studies

    @app.get("/api/picker/state")
    def get_picker_state() -> dict[str, str]:
        return {"state": "ready" if state.bound else "unpicked"}

    @app.get("/api/picker/browse")
    def browse_picker(path: str | None = None) -> dict[str, object]:
        if state.bound or picker is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        jail = picker.browse_root.expanduser().resolve()
        target = Path(path).expanduser() if path else jail
        try:
            resolved = target.resolve(strict=True)
        except OSError as error:
            raise HTTPException(
                status_code=404, detail="That folder does not exist."
            ) from error
        if not resolved.is_dir():
            raise HTTPException(status_code=404, detail="That folder does not exist.")
        if not resolved.is_relative_to(jail):
            raise HTTPException(
                status_code=403, detail="Choose a folder inside your home directory."
            )
        try:
            children = [
                child
                for child in resolved.iterdir()
                if child.is_dir() and not child.name.startswith(".")
            ]
        except OSError as error:
            raise HTTPException(
                status_code=403, detail="Codemble cannot read that folder."
            ) from error
        entries = sorted(
            ({"name": child.name, "path": str(child)} for child in children),
            key=lambda entry: str(entry["name"]).lower(),
        )
        parent = str(resolved.parent) if resolved != jail else None
        return {"path": str(resolved), "parent": parent, "entries": entries}

    @app.get("/api/picker/recents")
    def picker_recents() -> dict[str, object]:
        if state.bound or picker is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        return {"recents": list_recent_projects()}

    @app.post("/api/picker/select")
    def select_project(selection: ProjectSelection) -> dict[str, object]:
        if state.bound or picker is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        jail = picker.browse_root.expanduser().resolve()
        try:
            resolved = Path(selection.path).expanduser().resolve(strict=True)
        except OSError as error:
            raise HTTPException(
                status_code=404, detail="That folder does not exist."
            ) from error
        if not resolved.is_relative_to(jail):
            raise HTTPException(
                status_code=403, detail="Choose a folder inside your home directory."
            )
        parser = ProjectParser()
        try:
            intake = parser.intake(resolved)
        except ProjectScaleError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": "scale",
                    "file_count": len(error.intake.files),
                    "scale_cap": error.scale_cap,
                    "root": str(error.intake.root),
                    "suggestions": [
                        {"path": directory, "file_count": count}
                        for directory, count in error.intake.scope_counts()[:6]
                    ],
                },
            ) from error
        except ProjectParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        try:
            bound_graph = parser.parse(intake, entrypoint=picker.entrypoint)
        except ProjectParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        state.bind(bound_graph)
        return {"state": "ready"}

    @app.get("/api/graph")
    def get_graph() -> dict[str, object]:
        checks, _ = _services()
        return checks.graph().to_dict()

    @app.post("/api/entrypoint")
    def select_entrypoint(selection: EntrypointSelection) -> dict[str, object]:
        checks, _ = _services()
        try:
            selected = checks.select_entrypoint(selection.node_id)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Choose one of the parser-ranked entrypoint candidates.",
            ) from error
        return selected.to_dict()

    @app.get("/api/regions/{region_id:path}/checks")
    def get_region_checks(region_id: str) -> dict[str, object]:
        checks, _ = _services()
        try:
            return checks.for_region(region_id)
        except UnknownCheckError as error:
            raise HTTPException(
                status_code=404, detail="That region is not in this graph."
            ) from error

    @app.post("/api/regions/{region_id:path}/checks/{check_id}")
    def submit_region_check(
        region_id: str, check_id: str, submission: CheckSubmission
    ) -> dict[str, object]:
        checks, _ = _services()
        try:
            return checks.submit(region_id, check_id, submission.selected_ids)
        except UnknownCheckError as error:
            raise HTTPException(
                status_code=404, detail="That graph check does not exist."
            ) from error
        except InvalidCheckSubmission as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/node/{node_id:path}/study")
    def get_node_study(node_id: str) -> dict[str, object]:
        _, studies = _services()
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
    return Path(__file__).resolve().parents[1] / "web_dist"


__all__ = ["create_app", "PickerConfig"]
