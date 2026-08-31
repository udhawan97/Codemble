"""Durable, provider-neutral failure alerts for scheduled share operations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import tomllib
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path

_ALERT_SCHEMA_VERSION = 1
_ALERT_ID_PATTERN = re.compile(r"alert-[0-9a-f]{32}")
_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_MONITORED_UNITS = frozenset(
    {
        "codemble-rest-server.service",
        "codemble-share-operator.service",
        "codemble-share-writer.service",
    }
)


class ShareFailureAlertError(RuntimeError):
    """A failure alert could not be durably relayed."""


@dataclass(frozen=True, slots=True)
class ShareFailureAlert:
    """One closed, token-free service-failure event."""

    event_id: str
    occurred_at: datetime
    unit: str

    def to_bytes(self) -> bytes:
        return (
            json.dumps(
                {
                    "event_id": self.event_id,
                    "kind": "service-failure",
                    "occurred_at": _utc_text(self.occurred_at),
                    "schema_version": _ALERT_SCHEMA_VERSION,
                    "unit": self.unit,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()

    @classmethod
    def from_bytes(cls, encoded: bytes) -> ShareFailureAlert:
        try:
            document = json.loads(encoded)
            if not isinstance(document, dict) or set(document) != {
                "event_id",
                "kind",
                "occurred_at",
                "schema_version",
                "unit",
            }:
                raise ValueError
            alert = cls(
                event_id=document["event_id"],
                occurred_at=_parse_utc(document["occurred_at"]),
                unit=document["unit"],
            )
            if (
                document["schema_version"] != _ALERT_SCHEMA_VERSION
                or document["kind"] != "service-failure"
                or not isinstance(alert.event_id, str)
                or _ALERT_ID_PATTERN.fullmatch(alert.event_id) is None
                or alert.unit not in _MONITORED_UNITS
                or alert.to_bytes() != encoded
            ):
                raise ValueError
            return alert
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ShareFailureAlertError("share failure alert is invalid") from error


@dataclass(frozen=True, slots=True)
class ShareAlertConfig:
    """Pinned local notifier and pre-provisioned private alert spool."""

    spool_root: Path
    notifier_executable: Path
    notifier_sha256: str

    @classmethod
    def load(cls, path: Path) -> ShareAlertConfig:
        _require_private_file(path, exact_mode=0o600, label="share alert configuration")
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or set(document) != {
                "notifier_executable",
                "notifier_sha256",
                "role",
                "schema_version",
                "spool_root",
            }:
                raise ValueError
            if document["schema_version"] != 1 or document["role"] != "alert-relay":
                raise ValueError
            spool_root = Path(document["spool_root"])
            notifier = Path(document["notifier_executable"])
            digest = document["notifier_sha256"]
            if (
                not spool_root.is_absolute()
                or not notifier.is_absolute()
                or not isinstance(digest, str)
                or _DIGEST_PATTERN.fullmatch(digest) is None
            ):
                raise ValueError
            _validate_spool(spool_root)
            _validate_notifier(notifier, digest)
            return cls(spool_root, notifier, digest)
        except (
            KeyError,
            OSError,
            ShareFailureAlertError,
            TypeError,
            ValueError,
            tomllib.TOMLDecodeError,
        ) as error:
            raise ValueError("share alert configuration is invalid") from error


AlertRunner = Callable[[tuple[str, ...], bytes], int]


class ShareFailureAlertRelay:
    """Persist an alert before attempting at-least-once local notification."""

    def __init__(
        self,
        config: ShareAlertConfig,
        *,
        runner: AlertRunner | None = None,
        entropy: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self._config = config
        self._runner = runner or _run_notifier
        self._entropy = entropy

    def relay(self, unit: str, *, now: datetime) -> ShareFailureAlert:
        if unit not in _MONITORED_UNITS:
            raise ValueError("share alert unit is not monitored")
        normalized_now = _normalize_utc(now)
        _validate_spool(self._config.spool_root)
        _validate_notifier(
            self._config.notifier_executable,
            self._config.notifier_sha256,
        )
        with _alert_lock(self._config.spool_root):
            pending = self._config.spool_root / "pending" / f"{unit}.json"
            if pending.exists():
                _require_private_file(pending, exact_mode=0o600, label="pending alert")
                alert = ShareFailureAlert.from_bytes(pending.read_bytes())
                if alert.unit != unit:
                    raise ShareFailureAlertError("pending share alert changed unit")
            else:
                event_id = "alert-" + self._entropy(16).hex()
                if _ALERT_ID_PATTERN.fullmatch(event_id) is None:
                    raise ShareFailureAlertError("share alert entropy is invalid")
                alert = ShareFailureAlert(event_id, normalized_now, unit)
                delivered = (
                    self._config.spool_root
                    / "delivered"
                    / f"{alert.event_id}.json"
                )
                if delivered.exists():
                    raise ShareFailureAlertError("share alert delivery identity was reused")
                _create_private_file(pending, alert.to_bytes())

            delivered = (
                self._config.spool_root / "delivered" / f"{alert.event_id}.json"
            )
            if delivered.exists():
                raise ShareFailureAlertError("share alert delivery identity was reused")
            return_code = self._runner(
                (str(self._config.notifier_executable),),
                alert.to_bytes(),
            )
            if return_code != 0:
                raise ShareFailureAlertError(
                    "share failure notifier failed; the durable alert remains pending"
                )

            pending.rename(delivered)
            _sync_directory(delivered.parent)
            _sync_directory(pending.parent)
            return alert


@contextmanager
def _alert_lock(root: Path):
    lock_path = root / ".relay.lock"
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(lock_path, flags)
    try:
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_uid != os.geteuid()
            or details.st_gid != os.getegid()
            or details.st_nlink != 1
        ):
            raise ShareFailureAlertError("share alert lock is not private and stable")
        flock(descriptor, LOCK_EX)
        yield
    finally:
        flock(descriptor, LOCK_UN)
        os.close(descriptor)


def _validate_spool(root: Path) -> None:
    for directory in (root, root / "pending", root / "delivered"):
        _require_private_directory(directory)
    _require_private_file(root / ".relay.lock", exact_mode=0o600, label="share alert lock")


def _validate_notifier(path: Path, digest: str) -> None:
    try:
        details = path.lstat()
    except OSError as error:
        raise ValueError("share alert notifier is unavailable") from error
    if (
        path.is_symlink()
        or not stat.S_ISREG(details.st_mode)
        or details.st_uid != os.geteuid()
        or details.st_gid != os.getegid()
        or stat.S_IMODE(details.st_mode) & 0o022
        or not os.access(path, os.X_OK)
        or _file_digest(path) != digest
    ):
        raise ValueError("share alert notifier is not a pinned trusted executable")


def _require_private_directory(path: Path) -> None:
    try:
        details = path.lstat()
    except OSError as error:
        raise ShareFailureAlertError("share alert spool is not provisioned") from error
    if (
        path.is_symlink()
        or not stat.S_ISDIR(details.st_mode)
        or stat.S_IMODE(details.st_mode) != 0o700
        or details.st_uid != os.geteuid()
        or details.st_gid != os.getegid()
    ):
        raise ShareFailureAlertError("share alert spool is not private")


def _require_private_file(path: Path, *, exact_mode: int, label: str) -> None:
    try:
        details = path.lstat()
    except OSError as error:
        raise ValueError(f"{label} is unavailable") from error
    if (
        path.is_symlink()
        or not stat.S_ISREG(details.st_mode)
        or stat.S_IMODE(details.st_mode) != exact_mode
        or details.st_uid != os.geteuid()
        or details.st_gid != os.getegid()
        or details.st_nlink != 1
    ):
        raise ValueError(f"{label} must be a private owned regular file")


def _create_private_file(path: Path, encoded: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _sync_directory(path.parent)


def _run_notifier(command: tuple[str, ...], encoded: bytes) -> int:
    try:
        result = subprocess.run(
            command,
            input=encoded,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd="/",
            env={"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin"},
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ShareFailureAlertError("share failure notifier could not run") from error
    return result.returncode


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _normalize_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("share alert time must be timezone-aware")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _normalize_utc(value).isoformat().replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(value)
    if _utc_text(parsed) != value:
        raise ValueError
    return parsed


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "ShareAlertConfig",
    "ShareFailureAlert",
    "ShareFailureAlertError",
    "ShareFailureAlertRelay",
]
