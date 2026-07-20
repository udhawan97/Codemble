"""FastAPI application for the local Codemble experience."""

from __future__ import annotations

import json
import threading
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
from codemble.adapters.parse_progress import ParseCancelled, ParseProgress
from codemble.graph import build_map
from codemble.adapters.project import (
    ProjectParseError,
    ProjectParser,
    ProjectScaleError,
)
from codemble.checks import CheckService, InvalidCheckSubmission, UnknownCheckError
from codemble.llm.local_status import ollama_status
from codemble.llm.study import StudyService, StudySourceError, UnknownNodeError
from codemble.progress import list_recent_projects
from codemble.server.parse_job import ParseJob


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


class _ProjectState:
    """Binding from picker selection to live project services, plus its parse.

    Binding is one-*at-a-time*, not one-shot: ``POST /api/picker/reset`` unbinds
    so the header's Switch project control can re-arm the picker without a
    process restart, and ``serve_project`` attaches a ``PickerConfig`` for
    exactly that reason.  An app built with no ``PickerConfig`` at all is the
    only genuinely one-shot case -- there, reset refuses rather than stranding
    the process with nothing to pick.
    """

    def __init__(self) -> None:
        self.checks: CheckService | None = None
        self.studies: StudyService | None = None
        self.job = ParseJob()
        self._lock = threading.Lock()
        self._graph: Graph | None = None
        self._graph_json: str | None = None
        self._map_json: str | None = None

    @property
    def bound(self) -> bool:
        return self.checks is not None

    def bind(self, graph: Graph, progress: ParseProgress | None = None) -> None:
        if progress is not None:
            progress.stage("checks")
        studies = StudyService.from_environment(graph)
        checks = CheckService(graph)
        if progress is not None:
            progress.stage("layout")
        with self._lock:
            self.studies = studies
            self.checks = checks
            self._graph = None
            self._graph_json = None
            self._map_json = None
        self.graph_json()

    def unbind(self) -> None:
        """Drop the bound project so the picker can arm again.

        Progress is already on disk per project root, so releasing the live
        services loses nothing a re-select cannot restore.
        """

        with self._lock:
            self.checks = None
            self.studies = None
            self._graph = None
            self._graph_json = None
            self._map_json = None

    def _hydrated(self) -> Graph:
        """Hydrate from progress once per invalidating event.

        ``graph_json`` and ``map_json`` both need this same render-ready
        graph -- sharing it means a cold cache after a light-up or Home
        change pays hydration once, not once per endpoint a learner happens
        to open next.
        """

        with self._lock:
            cached = self._graph
            checks = self.checks
        if cached is not None:
            return cached
        if checks is None:
            raise HTTPException(status_code=409, detail="No project selected yet.")
        hydrated = checks.graph()
        with self._lock:
            self._graph = hydrated
        return hydrated

    def graph_json(self) -> str:
        """Serialize the render document once per invalidating event."""

        with self._lock:
            cached = self._graph_json
        if cached is not None:
            return cached
        payload = json.dumps(
            self._hydrated().to_dict(), separators=(",", ":"), ensure_ascii=False
        )
        with self._lock:
            self._graph_json = payload
        return payload

    def map_json(self) -> str:
        """Serialize the 2D map layouts once per invalidating event.

        Easy mode defaults to the Map layer, so it must not re-pay hydration
        plus layout on every request either -- the same disease this class
        was written to cure for the galaxy payload.
        """

        with self._lock:
            cached = self._map_json
        if cached is not None:
            return cached
        payload = json.dumps(
            build_map(self._hydrated()), separators=(",", ":"), ensure_ascii=False
        )
        with self._lock:
            self._map_json = payload
        return payload

    def invalidate_graph_json(self) -> None:
        """Drop every cached payload derived from the live graph.

        One trigger for all three: the hydrated ``Graph``, the galaxy JSON,
        and the map JSON all become stale from the same three events (a
        region lighting up, an entrypoint choice, or bind/unbind), so there
        is nothing to gain from invalidating them separately.
        """

        with self._lock:
            self._graph = None
            self._graph_json = None
            self._map_json = None


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
    state = _ProjectState()
    if parse_runner is not None:
        state.job = ParseJob(runner=parse_runner)

    def _new_job() -> ParseJob:
        return ParseJob(runner=parse_runner) if parse_runner else ParseJob()

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
        state.job.cancel()
        state.job = _new_job()
        state.unbind()
        return {"state": "unpicked"}

    @app.get("/api/llm/status")
    def get_llm_status() -> dict[str, object]:
        # Deliberately bypasses _services(): this reports LLM configuration,
        # not project data, and the setup guide it feeds is most useful
        # before a project is bound -- it must not 409 like /api/graph does.
        provider = state.studies.provider if state.studies is not None else None
        return {
            "configured_provider": getattr(provider, "name", None),
            "configured_model": getattr(provider, "model", None),
            "ollama": ollama_status(),
        }

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
        jail = picker.browse_root.expanduser().resolve()
        recents = [
            entry
            for entry in list_recent_projects()
            if Path(str(entry["project_root"])).resolve().is_relative_to(jail)
        ]
        return {"recents": recents}

    @app.post("/api/picker/select", status_code=202)
    def select_project(selection: ProjectSelection) -> dict[str, object]:
        if state.bound or picker is None or state.job.active:
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
        job = _new_job()
        state.job = job
        job.begin()
        try:
            intake = parser.intake(resolved)
        except ProjectScaleError as error:
            state.job = _new_job()
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
            state.job = _new_job()
            raise HTTPException(status_code=422, detail=str(error)) from error

        def work(reporter: ParseJob) -> None:
            bound_graph = parser.parse(
                intake, entrypoint=picker.entrypoint, progress=reporter
            )
            if reporter.cancelled:
                raise ParseCancelled("the learner reset the picker during this parse")
            state.bind(bound_graph, progress=reporter)

        job.start(work)
        return {"state": "parsing"}

    @app.get("/api/picker/progress")
    def picker_progress() -> dict[str, object]:
        # Never guarded by _services(): the loading screen polls this while
        # nothing is bound yet, and it must answer honestly before, during,
        # and after a parse.
        snapshot = state.job.snapshot()
        if snapshot["state"] == "idle" and state.bound:
            snapshot["state"] = "ready"
        return snapshot

    @app.get("/api/graph")
    def get_graph() -> Response:
        _services()
        return Response(state.graph_json(), media_type="application/json")

    @app.get("/api/map")
    def get_map() -> Response:
        # The hydrated graph, so lit regions and the selected Home in the 2D map
        # can never disagree with the galaxy the learner just came from. Cached
        # like /api/graph -- Easy mode defaults to this layer, so it is the
        # beginner's first request and must not re-pay hydration + layout on
        # every read either.
        _services()
        return Response(state.map_json(), media_type="application/json")

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
        state.invalidate_graph_json()
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
            result = checks.submit(region_id, check_id, submission.selected_ids)
        except UnknownCheckError as error:
            raise HTTPException(
                status_code=404, detail="That graph check does not exist."
            ) from error
        except InvalidCheckSubmission as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        # Invalidated on every accepted submission, not only a completing one:
        # a submission is rare, and a light-up is the one thing that must
        # never be served stale.
        state.invalidate_graph_json()
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
