"""One background project parse: staged progress, cancellation, honest failure.

A ``ParseJob`` instance runs at most once.  Re-arming the picker constructs a
new job, so a worker that was cancelled keeps its own cancellation token for
ever and can never bind a stale graph over a newer selection.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Literal

from codemble.adapters.parse_progress import ParseCancelled

JobState = Literal["idle", "parsing", "ready", "error"]

# The learner-visible stage order, exactly as the design spec fixes it.
STAGES = ("discovering", "parsing", "resolving", "checks", "layout")


def _thread_runner(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="codemble-parse", daemon=True).start()


class ParseJob:
    """The picker's parse state machine and its ``ParseProgress`` reporter."""

    def __init__(
        self, runner: Callable[[Callable[[], None]], None] = _thread_runner
    ) -> None:
        self._runner = runner
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._done = threading.Event()
        self._started = False
        self._state: JobState = "idle"
        self._stage: str | None = None
        self._files_done = 0
        self._files_total = 0
        self._error: str | None = None

    @property
    def active(self) -> bool:
        """True while this job owns an unfinished parse."""

        with self._lock:
            return self._state == "parsing"

    @property
    def cancelled(self) -> bool:
        """True once cancellation was requested; never cleared."""

        return self._cancelled.is_set()

    def snapshot(self) -> dict[str, object]:
        """Return the exact payload ``GET /api/picker/progress`` serves."""

        with self._lock:
            return {
                "state": self._state,
                "stage": self._stage,
                "files_done": self._files_done,
                "files_total": self._files_total,
                "error": self._error,
            }

    def begin(self) -> None:
        """Enter ``discovering`` while the request thread walks the project."""

        with self._lock:
            if self._state != "idle":
                raise RuntimeError("this parse job already ran")
            self._state = "parsing"
            self._stage = "discovering"

    def start(self, work: Callable[[ParseJob], None]) -> None:
        """Run ``work`` on the configured runner and translate its outcome."""

        def run() -> None:
            try:
                work(self)
            except ParseCancelled:
                self._finish("idle", None)
            except Exception as error:
                # A background thread with no catch-all leaves the picker
                # stuck on "parsing" for ever.  Every failure becomes state.
                self._finish("error", str(error) or error.__class__.__name__)
            else:
                self._finish("ready", None)
            finally:
                self._done.set()

        self._started = True
        self._runner(run)

    def request_cancel(self) -> None:
        """Ask an active parse to stop at its next file boundary."""

        self._cancelled.set()

    def cancel(self, timeout: float = 2.0) -> None:
        """Request cancellation and wait briefly for the worker to notice."""

        self.request_cancel()
        if self._started:
            self.wait(timeout)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the worker finishes; False on timeout."""

        return self._done.wait(timeout)

    # --- ParseProgress ---------------------------------------------------

    def stage(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown parse stage: {stage}")
        with self._lock:
            self._stage = stage

    def files_total(self, total: int) -> None:
        with self._lock:
            self._files_total = total

    def file_parsed(self) -> None:
        if self._cancelled.is_set():
            raise ParseCancelled("the learner reset the picker during this parse")
        with self._lock:
            self._files_done += 1
            if self._files_total and self._files_done >= self._files_total:
                self._stage = "resolving"

    def _finish(self, state: JobState, error: str | None) -> None:
        with self._lock:
            self._state = state
            self._stage = None
            self._error = error


__all__ = ["STAGES", "JobState", "ParseJob"]
