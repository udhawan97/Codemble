"""Per-file parse progress and cancellation, without widening the adapter seam.

``LanguageAdapter`` keeps its four public methods exactly as they are.  A
parse that wants progress binds a hook for its own thread with
``reporting_files``; each adapter's private per-file helper calls
``note_file_parsed`` once per source file it finishes reading.  That single
call site is also the only cancellation check point, so "between files" means
exactly one place in each adapter.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Protocol, runtime_checkable

_local = threading.local()


class ParseCancelled(Exception):
    """A running parse was cancelled; no graph will be produced."""


@runtime_checkable
class ParseProgress(Protocol):
    """The reporting surface ``ProjectParser`` writes one parse's state to."""

    def stage(self, stage: str) -> None:
        """Report the stage now running."""

    def files_total(self, total: int) -> None:
        """Report how many source files this parse will read."""

    def file_parsed(self) -> None:
        """Report one finished file; raise ``ParseCancelled`` to stop."""

    def detail(self, detail: str) -> None:
        """Report the sub-step now running within a stage.

        The ``resolving`` stage is one label over several seconds of cross-file
        work; a sub-step keeps the screen honestly changing instead of frozen.
        An implementation MAY treat a detail boundary as a cancellation
        checkpoint and raise ``ParseCancelled`` — the ``resolving`` stage calls
        no ``file_parsed`` and would otherwise run to completion after a cancel.
        The picker's ``ParseJob`` does; the CLI's ``TerminalProgress`` does not,
        because that parse is not cancellable.  A reporter that ignores it loses
        nothing but the finer copy.
        """


@contextmanager
def reporting_files(on_file: Callable[[], None] | None) -> Iterator[None]:
    """Bind ``on_file`` for this thread for the duration of one parse."""

    previous = getattr(_local, "on_file", None)
    _local.on_file = on_file
    try:
        yield
    finally:
        _local.on_file = previous


def note_file_parsed() -> None:
    """Report one finished source file; a no-op when nobody is listening."""

    on_file = getattr(_local, "on_file", None)
    if on_file is not None:
        on_file()


@contextmanager
def reporting_detail(on_detail: Callable[[str], None] | None) -> Iterator[None]:
    """Bind ``on_detail`` for this thread for the duration of one parse.

    Separate from ``reporting_files`` because resolving sub-steps outlive the
    file-reading loop: they run through cross-file resolution and composition.
    """

    previous = getattr(_local, "on_detail", None)
    _local.on_detail = on_detail
    try:
        yield
    finally:
        _local.on_detail = previous


def note_detail(detail: str) -> None:
    """Report the resolving sub-step now running; a no-op with no listener."""

    on_detail = getattr(_local, "on_detail", None)
    if on_detail is not None:
        on_detail(detail)


__all__ = [
    "ParseCancelled",
    "ParseProgress",
    "note_detail",
    "note_file_parsed",
    "reporting_detail",
    "reporting_files",
]
