"""FastAPI application for the local Codemble experience."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from codemble import __version__
from codemble.adapters.base import Graph
from codemble.adapters.project import (
    ProjectParseError,
    ProjectScaleError,
)
from codemble.checks import CheckService, InvalidCheckSubmission, UnknownCheckError
from codemble.llm.local_status import ollama_status
from codemble.llm.study import StudyService, StudySourceError, UnknownNodeError
from codemble.server.project_activation import (
    LiveProject,
    ProjectActivation,
    ProjectActivationBusy,
    ProjectUnavailable,
)
from codemble.server.project_selection import (
    ProjectFolderForbidden,
    ProjectFolderMissing,
    ProjectFolderUnreadable,
    ProjectSelector,
)


class CheckSubmission(BaseModel):
    """Option IDs selected for one graph-owned active check."""

    selected_ids: list[str]


class EntrypointSelection(BaseModel):
    """One parser-ranked candidate chosen as Home."""

    node_id: str


class ProjectSelection(BaseModel):
    """One learner-chosen folder to parse into the session's project."""

    path: str


class ModeSelection(BaseModel):
    """The learner's chosen audience voice."""

    mode: Literal["easy", "expert"]


class ProjectRelease(BaseModel):
    """Confirmation that the bound project should be released.

    The field exists to make this endpoint JSON-only.  A cross-site HTML form
    can POST without any script, but only as form-encoded, multipart, or
    text/plain -- none of which parse as this body, so validation refuses them
    before the handler runs, and a cross-origin JSON POST needs a preflight the
    browser will not grant.  Every other state-changing endpoint already had
    that protection by virtue of taking a body; reset was the one that did not.
    """

    confirmed: Literal[True]


@dataclass(frozen=True)
class PickerConfig:
    """Filesystem scope and parse settings for the in-app project picker."""

    browse_root: Path
    entrypoint: str | None = None


def create_app(
    graph: Graph | None = None,
    web_dist: Path | None = None,
    study_service: StudyService | None = None,
    check_service: CheckService | None = None,
    *,
    picker: PickerConfig | None = None,
    parse_runner: Callable[[Callable[[], None]], None] | None = None,
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver"),
) -> FastAPI:
    """Create an API and optional SPA server for one local project."""

    if graph is None and picker is None:
        raise ValueError("create_app needs a parsed graph or a PickerConfig")
    app = FastAPI(title="Codemble", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))
    activation = ProjectActivation(
        graph,
        studies=study_service,
        checks=check_service,
        entrypoint=picker.entrypoint if picker is not None else None,
        parse_runner=parse_runner,
    )
    selector = ProjectSelector(picker.browse_root) if picker is not None else None

    def _project() -> LiveProject:
        try:
            return activation.project()
        except ProjectUnavailable as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    def _services() -> tuple[CheckService, StudyService]:
        project = _project()
        return project.checks, project.studies

    @app.get("/api/picker/state")
    def get_picker_state() -> dict[str, str]:
        return {"state": "ready" if activation.bound else "unpicked"}

    @app.post("/api/picker/reset")
    def reset_picker(release: ProjectRelease) -> dict[str, str]:
        # `release` is never read: validating it is the whole point (see
        # ProjectRelease). A request that reaches this line already proved it
        # carried a JSON body, which a cross-site form cannot send.
        del release
        if picker is None:
            raise HTTPException(
                status_code=409,
                detail="This project was opened without a picker; restart Codemble to switch.",
            )
        activation.release()
        return {"state": "unpicked"}

    @app.get("/api/llm/status")
    def get_llm_status() -> dict[str, object]:
        # Deliberately bypasses _services(): this reports LLM configuration,
        # not project data, and the setup guide it feeds is most useful
        # before a project is bound -- it must not 409 like /api/graph does.
        provider = activation.provider
        return {
            "configured_provider": getattr(provider, "name", None),
            "configured_model": getattr(provider, "model", None),
            "ollama": ollama_status(),
        }

    @app.get("/api/picker/browse")
    def browse_picker(path: str | None = None) -> dict[str, object]:
        if activation.bound or selector is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        try:
            return selector.browse(path).to_dict()
        except ProjectFolderMissing as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ProjectFolderForbidden as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ProjectFolderUnreadable as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    @app.get("/api/picker/recents")
    def picker_recents() -> dict[str, object]:
        if activation.bound or selector is None:
            raise HTTPException(status_code=409, detail="A project is already selected.")
        return {"recents": selector.recents()}

    @app.post("/api/picker/select", status_code=202)
    def select_project(selection: ProjectSelection) -> dict[str, object]:
        if (
            picker is None
            or selector is None
            or not activation.accepting_selection
        ):
            raise HTTPException(status_code=409, detail="A project is already selected.")
        try:
            resolved = selector.resolve(selection.path)
        except ProjectFolderMissing as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ProjectFolderForbidden as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        try:
            activation.activate(resolved)
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
        except ProjectActivationBusy as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"state": "parsing"}

    @app.get("/api/picker/progress")
    def picker_progress() -> dict[str, object]:
        # Never guarded by _services(): the loading screen polls this while
        # nothing is bound yet, and it must answer honestly before, during,
        # and after a parse.
        return activation.progress()

    @app.get("/api/graph")
    def get_graph() -> Response:
        return Response(_project().graph_json(), media_type="application/json")

    @app.get("/api/map")
    def get_map() -> Response:
        # The hydrated graph, so lit regions and the selected Home in the 2D map
        # can never disagree with the galaxy the learner just came from. Cached
        # like /api/graph -- Easy mode defaults to this layer, so it is the
        # beginner's first request and must not re-pay hydration + layout on
        # every read either.
        return Response(_project().map_json(), media_type="application/json")

    @app.post("/api/entrypoint")
    def select_entrypoint(selection: EntrypointSelection) -> dict[str, object]:
        project = _project()
        try:
            selected = project.checks.select_entrypoint(selection.node_id)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Choose one of the parser-ranked entrypoint candidates.",
            ) from error
        project.invalidate_views()
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
        project = _project()
        try:
            result = project.checks.submit(region_id, check_id, submission.selected_ids)
        except UnknownCheckError as error:
            raise HTTPException(
                status_code=404, detail="That graph check does not exist."
            ) from error
        except InvalidCheckSubmission as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        # Invalidated on every accepted submission, not only a completing one:
        # a submission is rare, and a light-up is the one thing that must
        # never be served stale.
        project.invalidate_views()
        return result

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

    @app.get("/api/node/{node_id:path}/explanation")
    def get_node_explanation(
        node_id: str, mode: Literal["easy", "expert"] = "easy"
    ) -> dict[str, object]:
        _, studies = _services()
        try:
            return studies.explain(node_id, mode)
        except UnknownNodeError as error:
            raise HTTPException(
                status_code=404, detail="That source node is not in this graph."
            ) from error
        except StudySourceError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/mode")
    def get_mode() -> dict[str, object]:
        checks, _ = _services()
        return {"mode": checks.progress.mode(), "chosen": checks.progress.mode_chosen()}

    @app.put("/api/mode")
    def set_mode(selection: ModeSelection) -> dict[str, object]:
        checks, _ = _services()
        checks.progress.set_mode(selection.mode)
        return {"mode": selection.mode, "chosen": True}

    @app.delete("/api/progress")
    def clear_progress() -> dict[str, int]:
        project = _project()
        project.checks.progress.clear()
        project.invalidate_views()
        return {
            "understood_regions": len(project.checks.progress.understood_regions())
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
    return Path(__file__).resolve().parents[1] / "web_dist"


__all__ = ["create_app", "PickerConfig"]
