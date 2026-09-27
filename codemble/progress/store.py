"""File-hash-scoped local progress for parser regions."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from weakref import WeakValueDictionary

from codemble.adapters.base import Graph
from codemble.paths import data_dir

_SCHEMA_VERSION = 1
_MODES = frozenset({"easy", "expert"})
# The audience answer is about the learner, not the project, so it is also kept
# once per data directory. Project payloads still win, which is what keeps the
# header toggle a genuine per-project override.
_LEARNER_FILE = "learner.json"
_MUTATION_TIMEOUT_SECONDS = 5.0
_LOCKS: WeakValueDictionary[str, threading.Lock] = WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()


def _root_lock(root: Path) -> threading.Lock:
    key = os.path.normcase(str(root.resolve()))
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _file_lock(file, *, unlock: bool = False) -> None:
    """Lock one stable file on supported POSIX/Windows hosts; never fall back."""
    if os.name == "posix":
        import fcntl

        fcntl.flock(file.fileno(), fcntl.LOCK_UN if unlock else fcntl.LOCK_EX | fcntl.LOCK_NB)
    elif os.name == "nt":
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK if unlock else msvcrt.LK_NBLCK, 1)
    else:
        raise OSError(errno.ENOSYS, "Progress locking is unavailable on this platform.")


class UnknownRegionError(KeyError):
    """Raised when progress is requested for a region outside the graph."""


class ModeSaveUncertainError(OSError):
    """A failed compensating write leaves the selected mode unconfirmed."""


class ModeReadUncertainError(OSError):
    """Existing preference storage cannot establish a confirmed mode."""


def _mode_document(path: Path) -> dict[str, object] | None:
    """Missing initial storage is distinct from malformed/inaccessible storage."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if path.is_symlink():
            raise  # A broken existing storage link is not initial absence.
        return None
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("Preference storage is not an object.")
    return payload


class ProgressStore:
    """Persist understood regions without letting stale source stay lit."""

    def __init__(self, graph: Graph, root: Path | None = None) -> None:
        self._graph = graph
        self._root = root or data_dir() / "progress"
        project_key = hashlib.sha256(graph.project_root.encode()).hexdigest()[:20]
        self.path = self._root / f"{project_key}.json"
        self._learner_path = self._root / _LEARNER_FILE
        self._mutation_lock = _root_lock(self._root)
        self._signatures = _region_signatures(graph)

    def understood_regions(self) -> frozenset[str]:
        """Return only persisted regions whose current file hashes still match."""

        saved = self._read().get("regions", {})
        if not isinstance(saved, dict):
            return frozenset()
        return frozenset(
            region_id
            for region_id, signature in self._signatures.items()
            if isinstance(saved.get(region_id), dict)
            and saved[region_id].get("signature") == signature
        )

    def mark_understood(self, region_id: str) -> None:
        """Persist the current signature for one proven region."""

        signature = self._signatures.get(region_id)
        if signature is None:
            raise UnknownRegionError(region_id)
        with self._mutation():
            payload = self._read()
            saved = payload.get("regions")
            regions = saved if isinstance(saved, dict) else {}
            regions[region_id] = {"signature": signature}
            payload["schema_version"] = _SCHEMA_VERSION
            payload["project_root"] = self._graph.project_root
            payload["regions"] = dict(sorted(regions.items()))
            self._write(payload)

    def visited_regions(self) -> frozenset[str]:
        """Return the regions this learner has actually travelled to.

        Deliberately NOT signature-scoped, unlike ``understood_regions``. A
        proof of understanding is a claim about code, so editing that code must
        retire it; having been somewhere is a fact about the learner's own
        history and no edit can undo it. Filtered against the current graph all
        the same, so a region that has since been deleted stops being reported
        as somewhere in this project.
        """

        saved = self._read().get("visited")
        if not isinstance(saved, list):
            return frozenset()
        return frozenset(
            region_id for region_id in saved if region_id in self._signatures
        )

    def mark_visited(self, region_id: str) -> None:
        """Record that the learner reached one region. Never marks it understood."""

        if region_id not in self._signatures:
            raise UnknownRegionError(region_id)
        with self._mutation():
            payload = self._read()
            saved = payload.get("visited")
            visited = set(saved) if isinstance(saved, list) else set()
            visited.add(region_id)
            payload["schema_version"] = _SCHEMA_VERSION
            payload["project_root"] = self._graph.project_root
            payload["visited"] = sorted(visited)
            self._write(payload)

    def clear(self) -> None:
        """Forget this project's understood regions and trail, keeping preferences.

        Scoped to ``self.path``, which is keyed by this project's root, so no
        other project's progress can be touched. The trail goes with the
        understood set rather than surviving it: this control is a reset, and a
        map still showing everywhere you had been would be a half reset -- the
        same two-owners-of-one-fact shape as the 2026-08-01 quiz defect.
        """

        with self._mutation():
            payload = self._read()
            payload["schema_version"] = _SCHEMA_VERSION
            payload["project_root"] = self._graph.project_root
            payload["regions"] = {}
            payload["visited"] = []
            self._write(payload)

    def mode(self) -> str:
        """Return the learner's audience mode; this never affects progress."""

        value = self._read().get("mode")
        if value in _MODES:
            return value
        return self._learner_mode() or "easy"

    def mode_chosen(self) -> bool:
        """Return whether this learner has answered the audience question.

        Per project first, then the learner-level answer. The gate asks who
        the *learner* is, so re-asking it on every project would be asking a
        question they have already answered; the header toggle still overrides
        any single project.
        """

        return self._read().get("mode") in _MODES or self._learner_mode() is not None

    def confirmed_mode_state(self) -> dict[str, object]:
        """Read a coherent recovery snapshot without tolerant startup defaults.

        A project override wins without consulting the learner file. Otherwise
        a missing learner file means first launch; an existing unreadable or
        invalid file cannot truthfully confirm a default. The same root lock as
        writers prevents a read between the project and learner replacements.
        """
        try:
            with self._mutation():
                project = _mode_document(self.path)
                if project is not None:
                    if (
                        project.get("schema_version") != _SCHEMA_VERSION
                        or project.get("project_root") != self._graph.project_root
                        or not isinstance(project.get("regions"), dict)
                    ):
                        raise ValueError("Invalid project preference storage.")
                    if "mode" in project:
                        mode = project["mode"]
                        if not isinstance(mode, str) or mode not in _MODES:
                            raise ValueError("Invalid project explanation mode.")
                        return {"mode": mode, "chosen": True}
                learner = _mode_document(self._learner_path)
                if learner is None:
                    return {"mode": "easy", "chosen": False}
                mode = learner.get("mode")
                if not isinstance(mode, str) or mode not in _MODES:
                    raise ValueError("Invalid learner explanation mode.")
                return {"mode": mode, "chosen": True}
        except (OSError, ValueError, TypeError) as error:
            raise ModeReadUncertainError("Saved explanation choice could not be read.") from error

    def set_mode(self, mode: str) -> None:
        """Persist the audience mode beside progress without touching signatures."""

        if mode not in _MODES:
            raise ValueError("Mode must be 'easy' or 'expert'.")
        with self._mutation():
            previous = self._read()
            payload = {**previous, "mode": mode}
            self._write(payload)
            try:
                self._write_learner_mode(mode)
            except OSError:
                # Ordinary second-write failure must not return refusal while
                # leaving the new project mode persisted. This is compensating
                # rollback, not crash-atomic storage across two JSON files.
                try:
                    self._write(previous)
                except OSError as rollback_error:
                    raise ModeSaveUncertainError(
                        "Mode save and rollback failed; reload this project."
                    ) from rollback_error
                raise

    def _learner_mode(self) -> str | None:
        """Read the last audience answered on any project in this data dir."""

        try:
            payload = json.loads(self._learner_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        value = payload.get("mode")
        return value if value in _MODES else None

    def _write_learner_mode(self, mode: str) -> None:
        self._write_json(self._learner_path, {"mode": mode})

    def selected_entrypoint(self) -> str | None:
        """Return the learner's persisted Home choice, if one was stored.

        Not signature-scoped like understood regions: Home is a navigation
        preference, not evidence of understanding. The caller re-validates the
        id against the current parser ranking before trusting it.
        """

        value = self._read().get("entrypoint")
        return value if isinstance(value, str) else None

    def set_selected_entrypoint(self, node_id: str) -> None:
        """Persist the learner's Home choice beside progress."""

        with self._mutation():
            payload = self._read()
            payload["entrypoint"] = node_id
            self._write(payload)

    def hydrated_graph(self) -> Graph:
        """Project valid progress onto immutable render data."""

        understood = self.understood_regions()
        nodes = tuple(
            replace(node, understood=node.region in understood) for node in self._graph.nodes
        )
        regions = tuple(
            replace(region, understood=region.id in understood)
            for region in self._graph.regions
        )
        return replace(self._graph, nodes=nodes, regions=regions)

    def _read(self) -> dict[str, object]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return self._empty_payload()
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _SCHEMA_VERSION
            or payload.get("project_root") != self._graph.project_root
        ):
            return self._empty_payload()
        return payload

    def _write(self, payload: dict[str, object]) -> None:
        self._write_json(self.path, payload)

    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self._root,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as file:
                temporary = Path(file.name)
                file.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def _mutation(self) -> Iterator[None]:
        """Own read/modify/replace across stores and CLI processes.

        One root lock includes learner defaults. Always acquire the thread lock
        before the stable OS lock. Never unlink the lock file: existing waiters
        must continue to name the same inode after the owner exits.
        """
        deadline = time.monotonic() + _MUTATION_TIMEOUT_SECONDS
        if not self._mutation_lock.acquire(timeout=_MUTATION_TIMEOUT_SECONDS):
            raise TimeoutError("Progress is busy; please retry.")
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            with (self._root / ".mutation.lock").open("a+b") as file:
                if os.fstat(file.fileno()).st_size == 0:
                    file.write(b"\0")  # Windows byte-range locks require one byte.
                    file.flush()
                while True:
                    try:
                        _file_lock(file)
                        break
                    except OSError as error:
                        if error.errno not in (errno.EACCES, errno.EAGAIN):
                            raise
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("Progress is busy; please retry.") from error
                        time.sleep(min(0.02, remaining))
                try:
                    yield
                finally:
                    _file_lock(file, unlock=True)
        finally:
            self._mutation_lock.release()

    def _empty_payload(self) -> dict[str, object]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "project_root": self._graph.project_root,
            "regions": {},
        }


def _region_signatures(graph: Graph) -> dict[str, str]:
    files_by_region: dict[str, set[str]] = {}
    for node in graph.nodes:
        files_by_region.setdefault(node.region, set()).add(node.file)
    signatures: dict[str, str] = {}
    for region_id, files in files_by_region.items():
        evidence = [
            (file, graph.file_hashes.get(file, "missing")) for file in sorted(files)
        ]
        signatures[region_id] = hashlib.sha256(
            json.dumps(evidence, separators=(",", ":")).encode()
        ).hexdigest()
    return signatures


def list_recent_projects(limit: int = 8) -> list[dict[str, object]]:
    """Return recently explored projects whose paths still exist, newest first."""

    progress_root = data_dir() / "progress"
    entries: list[tuple[float, dict[str, object]]] = []
    try:
        candidates = sorted(progress_root.glob("*.json"))
    except OSError:
        return []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            modified = path.stat().st_mtime
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            continue
        project_root = payload.get("project_root")
        regions = payload.get("regions")
        if not isinstance(project_root, str) or not isinstance(regions, dict):
            continue
        if not Path(project_root).is_dir():
            continue
        entries.append(
            (modified, {"project_root": project_root, "understood_count": len(regions)})
        )
    entries.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in entries[:limit]]


__all__ = [
    "ModeReadUncertainError", "ModeSaveUncertainError", "ProgressStore",
    "UnknownRegionError", "list_recent_projects",
]
