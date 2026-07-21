"""Atomic project parsing, activation, release, and live payload caches."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path

from codemble.adapters.base import Graph
from codemble.adapters.parse_progress import ParseCancelled
from codemble.adapters.project import ProjectParser
from codemble.checks import CheckService
from codemble.graph import build_map
from codemble.llm.study import StudyService
from codemble.server.parse_job import ParseJob

ParseRunner = Callable[[Callable[[], None]], None]


class ProjectUnavailable(Exception):
    """No project is currently active."""


class ProjectActivationBusy(Exception):
    """A project is active or an activation is already running."""


class LiveProject:
    """The bound learner services and cached views for one parsed graph."""

    def __init__(
        self,
        graph: Graph,
        *,
        studies: StudyService | None = None,
        checks: CheckService | None = None,
    ) -> None:
        self.studies = studies or StudyService.from_environment(graph)
        self.checks = checks or CheckService(graph)
        self._lock = threading.Lock()
        self._graph: Graph | None = None
        self._graph_json: str | None = None
        self._map_json: str | None = None

    def graph_json(self) -> str:
        """Return one serialized render graph per invalidating event."""

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
        """Return one serialized 2D map per invalidating event."""

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

    def invalidate_views(self) -> None:
        """Drop all views derived from progress-sensitive graph state."""

        with self._lock:
            self._graph = None
            self._graph_json = None
            self._map_json = None

    def _hydrated(self) -> Graph:
        with self._lock:
            cached = self._graph
        if cached is not None:
            return cached
        hydrated = self.checks.graph()
        with self._lock:
            self._graph = hydrated
        return hydrated


class ProjectActivation:
    """Own the one-at-a-time transition from local folder to live project."""

    def __init__(
        self,
        graph: Graph | None = None,
        *,
        studies: StudyService | None = None,
        checks: CheckService | None = None,
        entrypoint: str | None = None,
        parse_runner: ParseRunner | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._entrypoint = entrypoint
        self._parse_runner = parse_runner
        self._job = self._new_job()
        self._project = (
            LiveProject(graph, studies=studies, checks=checks)
            if graph is not None
            else None
        )
        if self._project is not None:
            self._project.graph_json()

    @property
    def bound(self) -> bool:
        with self._lock:
            return self._project is not None

    @property
    def provider(self) -> object | None:
        with self._lock:
            project = self._project
        return project.studies.provider if project is not None else None

    def project(self) -> LiveProject:
        """Return one atomic snapshot of the active project."""

        with self._lock:
            project = self._project
        if project is None:
            raise ProjectUnavailable("No project selected yet.")
        return project

    def activate(self, path: Path) -> None:
        """Start parsing one selected folder and bind it only if still current."""

        parser = ProjectParser()
        job = self._new_job()
        with self._lock:
            if self._project is not None or self._job.active:
                raise ProjectActivationBusy("A project is already selected.")
            self._job = job
            job.begin()
        try:
            intake = parser.intake(path)
        except Exception:
            with self._lock:
                if self._job is job:
                    self._job = self._new_job()
            raise

        def work(reporter: ParseJob) -> None:
            graph = parser.parse(
                intake, entrypoint=self._entrypoint, progress=reporter
            )
            reporter.stage("checks")
            candidate = LiveProject(graph)
            reporter.stage("layout")
            with self._lock:
                if self._job is not job or reporter.cancelled:
                    raise ParseCancelled(
                        "the learner reset the picker during this parse"
                    )
                self._project = candidate
            candidate.graph_json()

        job.start(work)

    def release(self, timeout: float = 2.0) -> None:
        """Cancel the current activation and atomically leave no project bound."""

        with self._lock:
            previous = self._job
            self._job = self._new_job()
            self._project = None
        previous.cancel(timeout)

    def progress(self) -> dict[str, object]:
        """Return the picker progress payload for the current activation."""

        with self._lock:
            job = self._job
            bound = self._project is not None
        snapshot = job.snapshot()
        if snapshot["state"] == "idle" and bound:
            snapshot["state"] = "ready"
        return snapshot

    def _new_job(self) -> ParseJob:
        return (
            ParseJob(runner=self._parse_runner)
            if self._parse_runner is not None
            else ParseJob()
        )


__all__ = [
    "LiveProject",
    "ProjectActivation",
    "ProjectActivationBusy",
    "ProjectUnavailable",
]
