"""Free, provider-neutral backup operations and anti-resurrection journal."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
from hashlib import sha256
from hmac import digest as hmac_digest
from pathlib import Path
from threading import Lock, RLock
from typing import Protocol
from urllib.parse import urlsplit

from codemble.share.delivery import ShareStorageConflictError
from codemble.share.persistent_storage import (
    EncryptedSQLiteShareStorage,
    SharePurgeResult,
)
from codemble.share.retirement import ShareRetirementEvent

_ZERO_DIGEST = "sha256:" + "0" * 64
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_REPOSITORY_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SNAPSHOT_ID_PATTERN = re.compile(r"^[0-9a-f]{6,64}$")
_BACKUP_MANIFEST_NAME = "share-backup-manifest.json"
_JOURNAL_LOCKS: dict[Path, RLock] = {}
_JOURNAL_LOCKS_GUARD = Lock()
_OPERATION_LOCKS: dict[Path, RLock] = {}
_OPERATION_LOCKS_GUARD = Lock()


class RetirementJournalError(RuntimeError):
    """Retirement history is missing, stale, malformed, gapped, or forked."""


@dataclass(frozen=True, slots=True)
class ResticSnapshotReceipt:
    repository_id: str
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class RetirementAnchorReceipt:
    replica_name: str
    repository_id: str
    snapshot_id: str
    entry_digest: str

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "entry_digest": self.entry_digest,
                "replica_name": self.replica_name,
                "repository_id": self.repository_id,
                "schema_version": 1,
                "snapshot_id": self.snapshot_id,
            }
        )


@dataclass(frozen=True, slots=True)
class BackupInventoryReceipt:
    repository_id: str
    snapshot_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResticSnapshot:
    snapshot_id: str
    tags: tuple[str, ...]


class RetirementAnchorPort(Protocol):
    """Write one immutable journal entry to independently controlled storage."""

    def repository_identity(self) -> str:
        """Return the authenticated immutable repository identity."""

    def anchor(
        self,
        path: Path,
        *,
        tags: tuple[str, ...],
        replica_name: str,
        entry_digest: str,
    ) -> RetirementAnchorReceipt:
        """Anchor one create-only entry and return its authenticated receipt."""


class BackupWriterPort(Protocol):
    """Append one encrypted backup snapshot without prune or restore authority."""

    def repository_identity(self) -> str:
        """Return the authenticated immutable repository identity."""

    def backup(
        self, paths: tuple[Path, ...], *, tags: tuple[str, ...]
    ) -> ResticSnapshotReceipt:
        """Write paths and return the bound repository/snapshot receipt."""


class BackupInventoryPort(Protocol):
    """Read the operator-owned inventory without accepting caller assertions."""

    def snapshot_inventory(self, *, tags: tuple[str, ...]) -> BackupInventoryReceipt:
        """Return the authenticated repository and exact closed-tag inventory."""


class ResticCommandError(RuntimeError):
    """A closed restic operation failed without exposing command output."""


class _CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class _ResticRole:
    def __init__(
        self,
        repository: str,
        password_file: Path,
        *,
        expected_repository_id: str,
        restic_executable: Path,
        expected_executable_digest: str,
        cache_root: Path,
        repository_validator,
        extra_environment: dict[str, str] | None = None,
        runner=None,
    ) -> None:
        repository_validator(repository)
        if _REPOSITORY_ID_PATTERN.fullmatch(expected_repository_id) is None:
            raise ValueError("restic repository identity must be 64 lowercase hex characters")
        _require_private_file(password_file, label="restic password")
        if (
            not restic_executable.is_absolute()
            or restic_executable.is_symlink()
            or not restic_executable.is_file()
            or not os.access(restic_executable, os.X_OK)
        ):
            raise ValueError("restic executable must be an absolute executable file")
        if (
            _DIGEST_PATTERN.fullmatch(expected_executable_digest) is None
            or _file_digest(restic_executable) != expected_executable_digest
        ):
            raise ValueError("restic executable does not match its pinned SHA-256 digest")
        cache_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require_private_directory(cache_root)
        self._executable = restic_executable
        self._expected_repository_id = expected_repository_id
        self._runner = runner or _run_command
        self._environment = {
            "LANG": "C.UTF-8",
            "RESTIC_CACHE_DIR": str(cache_root),
            "RESTIC_PASSWORD_FILE": str(password_file),
            "RESTIC_REPOSITORY": repository,
        }
        self._environment.update(extra_environment or {})

    def _execute(self, arguments: tuple[str, ...]) -> _CommandResult:
        result = self._runner(
            (str(self._executable), *arguments),
            dict(self._environment),
        )
        if result.returncode != 0:
            raise ResticCommandError("restic operation failed; inspect the closed operator log")
        return result

    def repository_identity(self) -> str:
        """Authenticate the repository config and return its stable restic ID."""

        try:
            document = json.loads(self._execute(("cat", "config")).stdout)
            repository_id = document["id"]
            if (
                not isinstance(repository_id, str)
                or _REPOSITORY_ID_PATTERN.fullmatch(repository_id) is None
                or repository_id != self._expected_repository_id
            ):
                raise ValueError
            return repository_id
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ResticCommandError(
                "restic repository identity does not match its attestation"
            ) from error


class ResticBackupWriter(_ResticRole):
    """Application-writer role: append snapshots, with no prune or restore method."""

    def __init__(
        self,
        repository: str,
        password_file: Path,
        *,
        expected_repository_id: str,
        restic_executable: Path,
        expected_executable_digest: str,
        cache_root: Path,
        rest_username: str,
        rest_password_file: Path,
        runner=None,
    ) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", rest_username) is None:
            raise ValueError("rest-server writer username must use the closed slug format")
        _validate_private_rest_repository(repository, rest_username)
        _require_private_file(rest_password_file, label="rest-server writer password")
        rest_password = rest_password_file.read_text(encoding="utf-8")
        if not rest_password or "\n" in rest_password or "\r" in rest_password:
            raise ValueError("rest-server writer password must be one non-empty line")
        super().__init__(
            repository,
            password_file,
            expected_repository_id=expected_repository_id,
            restic_executable=restic_executable,
            expected_executable_digest=expected_executable_digest,
            cache_root=cache_root,
            repository_validator=_validate_rest_repository,
            extra_environment={
                "RESTIC_REST_PASSWORD": rest_password,
                "RESTIC_REST_USERNAME": rest_username,
            },
            runner=runner,
        )

    def backup(
        self, paths: tuple[Path, ...], *, tags: tuple[str, ...]
    ) -> ResticSnapshotReceipt:
        if not paths or any(
            not isinstance(path, Path) or path.is_symlink() or not path.is_file()
            for path in paths
        ):
            raise ValueError("restic backup accepts regular files only")
        if not tags or any(
            re.fullmatch(r"[a-z0-9][a-z0-9-]{0,126}", tag) is None
            for tag in tags
        ):
            raise ValueError("restic backup tags must use the closed slug format")
        parents = {path.parent for path in paths}
        names = tuple(path.name for path in paths)
        if len(parents) != 1 or len(set(names)) != len(names):
            raise ValueError("restic backup files must share one staging directory")
        parent = next(iter(parents))
        _require_private_directory(parent)
        arguments: list[str] = ["backup", "--json", "--cwd", str(parent)]
        for tag in tags:
            arguments.extend(("--tag", tag))
        arguments.extend(names)
        repository_id = self.repository_identity()
        result = self._execute(tuple(arguments))
        snapshot_id = ""
        for line in result.stdout.splitlines():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("message_type") == "summary":
                candidate = message.get("snapshot_id")
                if isinstance(candidate, str):
                    snapshot_id = candidate
        if _SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id) is None:
            raise ResticCommandError("restic backup returned no valid snapshot identity")
        if self.repository_identity() != repository_id:
            raise ResticCommandError("restic repository identity changed during backup")
        return ResticSnapshotReceipt(repository_id, snapshot_id)

    def anchor(
        self,
        path: Path,
        *,
        tags: tuple[str, ...],
        replica_name: str,
        entry_digest: str,
    ) -> RetirementAnchorReceipt:
        snapshot = self.backup((path,), tags=tags)
        return RetirementAnchorReceipt(
            replica_name=replica_name,
            repository_id=snapshot.repository_id,
            snapshot_id=snapshot.snapshot_id,
            entry_digest=entry_digest,
        )


class ResticOperator(_ResticRole):
    """Separate operator role for full checks, bounded prune, and quarantine restore."""

    def __init__(
        self,
        repository: str,
        password_file: Path,
        *,
        expected_repository_id: str,
        restic_executable: Path,
        expected_executable_digest: str,
        cache_root: Path,
        rest_username: str | None = None,
        rest_password_file: Path | None = None,
        runner=None,
    ) -> None:
        extra_environment = None
        repository_validator = _validate_local_repository
        if repository.startswith("rest:"):
            repository_validator = _validate_rest_repository
            if (
                rest_username is None
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", rest_username) is None
                or rest_password_file is None
            ):
                raise ValueError("remote restic operator requires closed REST credentials")
            _validate_private_rest_repository(repository, rest_username)
            _require_private_file(rest_password_file, label="rest-server operator password")
            rest_password = rest_password_file.read_text(encoding="utf-8")
            if not rest_password or "\n" in rest_password or "\r" in rest_password:
                raise ValueError("rest-server operator password must be one non-empty line")
            extra_environment = {
                "RESTIC_REST_PASSWORD": rest_password,
                "RESTIC_REST_USERNAME": rest_username,
            }
        elif rest_username is not None or rest_password_file is not None:
            raise ValueError("local restic operator must not receive REST credentials")
        super().__init__(
            repository,
            password_file,
            expected_repository_id=expected_repository_id,
            restic_executable=restic_executable,
            expected_executable_digest=expected_executable_digest,
            cache_root=cache_root,
            repository_validator=repository_validator,
            extra_environment=extra_environment,
            runner=runner,
        )

    def full_check(self) -> None:
        self.repository_identity()
        self._execute(("check", "--read-data"))

    def forget_and_prune(self, *, keep_within: timedelta) -> None:
        if keep_within != timedelta(days=7):
            raise ValueError("Codemble backup retention is fixed at seven days")
        self._execute(("forget", "--keep-within", "7d", "--prune"))

    def snapshots(self, *, tags: tuple[str, ...]) -> tuple[ResticSnapshot, ...]:
        if not tags or any(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,126}", tag) is None for tag in tags):
            raise ValueError("restic snapshot tags must use the closed slug format")
        arguments: list[str] = ["snapshots", "--json"]
        for tag in tags:
            arguments.extend(("--tag", tag))
        result = self._execute(tuple(arguments))
        try:
            document = json.loads(result.stdout)
            if not isinstance(document, list):
                raise TypeError
            snapshots = tuple(
                sorted(
                    (
                        ResticSnapshot(
                            snapshot_id=item["id"],
                            tags=tuple(sorted(item.get("tags", ()))),
                        )
                        for item in document
                    ),
                    key=lambda item: item.snapshot_id,
                )
            )
            if any(
                _SNAPSHOT_ID_PATTERN.fullmatch(item.snapshot_id) is None
                or any(
                    not isinstance(tag, str)
                    or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,126}", tag) is None
                    for tag in item.tags
                )
                for item in snapshots
            ):
                raise ValueError
            return snapshots
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ResticCommandError("restic returned an invalid snapshot inventory") from error

    def snapshot_inventory(self, *, tags: tuple[str, ...]) -> BackupInventoryReceipt:
        repository_id = self.repository_identity()
        snapshots = self.snapshots(tags=tags)
        if self.repository_identity() != repository_id:
            raise ResticCommandError("restic repository identity changed during inventory")
        return BackupInventoryReceipt(
            repository_id=repository_id,
            snapshot_ids=tuple(item.snapshot_id for item in snapshots),
        )

    def snapshot_ids(self, *, tags: tuple[str, ...]) -> tuple[str, ...]:
        """Return exact snapshot identities from an authenticated inventory."""

        return self.snapshot_inventory(tags=tags).snapshot_ids

    def remove_snapshots(self, snapshot_ids: tuple[str, ...]) -> None:
        if not snapshot_ids or any(
            _SNAPSHOT_ID_PATTERN.fullmatch(identity) is None
            for identity in snapshot_ids
        ):
            raise ValueError("restic snapshot deletion requires explicit valid identities")
        self._execute(("forget", "--prune", *snapshot_ids))

    def restore(self, snapshot_id: str, target: Path) -> None:
        if _SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id) is None:
            raise ValueError("restic snapshot identity is invalid")
        if target.exists():
            if target.is_symlink() or not target.is_dir() or any(target.iterdir()):
                raise ValueError("restic restore target must be absent or empty")
            _require_private_directory(target)
        else:
            target.mkdir(mode=0o700, parents=True)
        self._execute(("restore", snapshot_id, "--target", str(target)))


@dataclass(frozen=True, slots=True)
class ResticWriterTargetConfig:
    repository: str
    repository_id: str
    repository_password_file: Path
    rest_username: str
    rest_password_file: Path
    restic_cache_root: Path

    @classmethod
    def from_document(cls, value: object) -> ResticWriterTargetConfig:
        if not isinstance(value, dict) or set(value) != {
            "repository",
            "repository_id",
            "repository_password_file",
            "rest_password_file",
            "rest_username",
            "restic_cache_root",
        }:
            raise ValueError
        repository = value["repository"]
        repository_id = value["repository_id"]
        if (
            not isinstance(repository_id, str)
            or _REPOSITORY_ID_PATTERN.fullmatch(repository_id) is None
        ):
            raise ValueError
        paths = {
            name: Path(value[name])
            for name in (
                "repository_password_file",
                "rest_password_file",
                "restic_cache_root",
            )
            if isinstance(value[name], str) and Path(value[name]).is_absolute()
        }
        if len(paths) != 3:
            raise ValueError
        _require_private_file(
            paths["repository_password_file"],
            label="journal repository password",
        )
        _require_private_file(
            paths["rest_password_file"],
            label="journal rest-server password",
        )
        username = value["rest_username"]
        if (
            not isinstance(username, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", username) is None
        ):
            raise ValueError
        _validate_private_rest_repository(repository, username)
        return cls(
            repository=repository,
            repository_id=repository_id,
            repository_password_file=paths["repository_password_file"],
            rest_username=username,
            rest_password_file=paths["rest_password_file"],
            restic_cache_root=paths["restic_cache_root"],
        )


@dataclass(frozen=True, slots=True)
class ShareWriterConfig:
    deployment_id: str
    active_root: Path
    journal_root: Path
    staging_root: Path
    storage_key_file: Path
    restic_cache_root: Path
    restic_executable: Path
    restic_sha256: str
    repository: str
    repository_id: str
    repository_password_file: Path
    rest_username: str
    rest_password_file: Path
    journal_anchors: dict[str, ResticWriterTargetConfig]
    backup_interval_minutes: int
    deletion_deadline_days: int

    @classmethod
    def load(cls, path: Path) -> ShareWriterConfig:
        _require_private_file(path, label="share writer configuration")
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            expected = {
                "active_root",
                "backup_interval_minutes",
                "deletion_deadline_days",
                "deployment_id",
                "journal_anchors",
                "journal_root",
                "repository",
                "repository_id",
                "repository_password_file",
                "rest_password_file",
                "rest_username",
                "restic_cache_root",
                "restic_executable",
                "restic_sha256",
                "role",
                "schema_version",
                "staging_root",
                "storage_key_file",
            }
            if not isinstance(document, dict) or set(document) != expected:
                raise ValueError
            if document["schema_version"] != 1 or document["role"] != "writer":
                raise ValueError
            path_fields = {
                name: Path(document[name])
                for name in (
                    "active_root",
                    "journal_root",
                    "staging_root",
                    "storage_key_file",
                    "restic_cache_root",
                    "restic_executable",
                    "repository_password_file",
                    "rest_password_file",
                )
                if isinstance(document[name], str)
            }
            if len(path_fields) != 8 or any(not value.is_absolute() for value in path_fields.values()):
                raise ValueError
            for name in (
                "storage_key_file",
                "repository_password_file",
                "rest_password_file",
            ):
                _require_private_file(path_fields[name], label=name.replace("_", " "))
            if len(set(path_fields.values())) != len(path_fields):
                raise ValueError
            anchors = document["journal_anchors"]
            if (
                not isinstance(anchors, dict)
                or len(anchors) < 2
                or any(
                    not isinstance(name, str)
                    or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name) is None
                    for name in anchors
                )
            ):
                raise ValueError
            anchor_targets = {
                name: ResticWriterTargetConfig.from_document(value)
                for name, value in anchors.items()
            }
            if len({target.repository for target in anchor_targets.values()}) != len(
                anchor_targets
            ):
                raise ValueError
            authority_paths = (
                path_fields["repository_password_file"],
                path_fields["rest_password_file"],
                *(
                    credential
                    for target in anchor_targets.values()
                    for credential in (
                        target.repository_password_file,
                        target.rest_password_file,
                    )
                ),
            )
            if len(set(authority_paths)) != len(authority_paths):
                raise ValueError
            fixed = {
                "backup_interval_minutes": 60,
                "deletion_deadline_days": 8,
            }
            if any(document[name] != value for name, value in fixed.items()):
                raise ValueError
            repository = document["repository"]
            deployment_id = document["deployment_id"]
            repository_id = document["repository_id"]
            restic_sha256 = document["restic_sha256"]
            rest_username = document["rest_username"]
            _validate_private_rest_repository(repository, rest_username)
            if (
                not isinstance(deployment_id, str)
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{7,126}", deployment_id) is None
                or not isinstance(repository_id, str)
                or _REPOSITORY_ID_PATTERN.fullmatch(repository_id) is None
                or not isinstance(restic_sha256, str)
                or _DIGEST_PATTERN.fullmatch(restic_sha256) is None
                or _file_digest(path_fields["restic_executable"]) != restic_sha256
                or not isinstance(rest_username, str)
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", rest_username)
                is None
                or repository
                in {target.repository for target in anchor_targets.values()}
                or repository_id
                in {target.repository_id for target in anchor_targets.values()}
                or len({target.repository_id for target in anchor_targets.values()})
                != len(anchor_targets)
            ):
                raise ValueError
            return cls(
                deployment_id=deployment_id,
                **path_fields,
                restic_sha256=restic_sha256,
                repository=repository,
                repository_id=repository_id,
                rest_username=rest_username,
                journal_anchors=dict(sorted(anchor_targets.items())),
                **fixed,
            )
        except (KeyError, OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
            raise ValueError("share writer configuration is invalid") from error


@dataclass(frozen=True, slots=True)
class JournalReplicaBinding:
    path: Path
    repository_id: str

    @classmethod
    def from_document(cls, value: object) -> JournalReplicaBinding:
        if not isinstance(value, dict) or set(value) != {"path", "repository_id"}:
            raise ValueError
        path = Path(value["path"]) if isinstance(value["path"], str) else Path()
        repository_id = value["repository_id"]
        if (
            not path.is_absolute()
            or not isinstance(repository_id, str)
            or _REPOSITORY_ID_PATTERN.fullmatch(repository_id) is None
        ):
            raise ValueError
        return cls(path=path, repository_id=repository_id)


@dataclass(frozen=True, slots=True)
class JournalReplicaOperatorConfig:
    deployment_id: str
    replica_name: str
    replica_ids: dict[str, str]
    repository: str
    repository_id: str
    repository_password_file: Path
    restic_cache_root: Path
    restic_executable: Path
    restic_sha256: str

    @classmethod
    def load(cls, path: Path) -> JournalReplicaOperatorConfig:
        _require_private_file(path, label="journal replica operator configuration")
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or set(document) != {
                "deployment_id",
                "replica_ids",
                "replica_name",
                "repository",
                "repository_id",
                "repository_password_file",
                "restic_cache_root",
                "restic_executable",
                "restic_sha256",
                "role",
                "schema_version",
            }:
                raise ValueError
            if document["schema_version"] != 1 or document["role"] != "journal-operator":
                raise ValueError
            deployment_id = document["deployment_id"]
            replica_name = document["replica_name"]
            replica_ids = document["replica_ids"]
            repository = document["repository"]
            repository_id = document["repository_id"]
            if (
                not isinstance(deployment_id, str)
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{7,126}", deployment_id) is None
                or not isinstance(replica_name, str)
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", replica_name) is None
                or not isinstance(replica_ids, dict)
                or len(replica_ids) < 2
                or dict(sorted(replica_ids.items())) != replica_ids
                or replica_ids.get(replica_name) != repository_id
                or len(set(replica_ids.values())) != len(replica_ids)
                or any(
                    not isinstance(identity, str)
                    or _REPOSITORY_ID_PATTERN.fullmatch(identity) is None
                    for identity in replica_ids.values()
                )
                or not isinstance(repository_id, str)
                or _REPOSITORY_ID_PATTERN.fullmatch(repository_id) is None
            ):
                raise ValueError
            _validate_local_repository(repository)
            paths = {
                name: Path(document[name])
                for name in (
                    "repository_password_file",
                    "restic_cache_root",
                    "restic_executable",
                )
                if isinstance(document[name], str) and Path(document[name]).is_absolute()
            }
            if len(paths) != 3:
                raise ValueError
            _require_private_file(
                paths["repository_password_file"],
                label="repository password file",
            )
            restic_sha256 = document["restic_sha256"]
            if (
                not isinstance(restic_sha256, str)
                or _DIGEST_PATTERN.fullmatch(restic_sha256) is None
                or _file_digest(paths["restic_executable"]) != restic_sha256
            ):
                raise ValueError
            return cls(
                deployment_id=deployment_id,
                replica_name=replica_name,
                replica_ids=replica_ids,
                repository=repository,
                repository_id=repository_id,
                repository_password_file=paths["repository_password_file"],
                restic_cache_root=paths["restic_cache_root"],
                restic_executable=paths["restic_executable"],
                restic_sha256=restic_sha256,
            )
        except (KeyError, OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
            raise ValueError("journal replica operator configuration is invalid") from error


@dataclass(frozen=True, slots=True)
class ShareOperatorConfig:
    deployment_id: str
    active_root: Path
    journal_root: Path
    recovery_key_file: Path
    restic_cache_root: Path
    restic_executable: Path
    restic_sha256: str
    repository: str
    repository_id: str
    repository_password_file: Path
    journal_replicas: dict[str, JournalReplicaBinding]
    writer_uid: int
    writer_gid: int
    backup_keep_days: int
    deletion_deadline_days: int
    security_margin_hours: int

    @classmethod
    def load(cls, path: Path) -> ShareOperatorConfig:
        _require_private_file(path, label="share operator configuration")
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            expected = {
                "active_root",
                "backup_keep_days",
                "deletion_deadline_days",
                "deployment_id",
                "journal_replicas",
                "journal_root",
                "recovery_key_file",
                "repository",
                "repository_id",
                "repository_password_file",
                "restic_cache_root",
                "restic_executable",
                "restic_sha256",
                "role",
                "schema_version",
                "security_margin_hours",
                "writer_gid",
                "writer_uid",
            }
            if (
                not isinstance(document, dict)
                or set(document) != expected
                or document["schema_version"] != 2
                or document["role"] != "operator"
            ):
                raise ValueError
            path_fields = {
                name: Path(document[name])
                for name in (
                    "active_root",
                    "journal_root",
                    "recovery_key_file",
                    "restic_cache_root",
                    "restic_executable",
                    "repository_password_file",
                )
                if isinstance(document[name], str)
            }
            if len(path_fields) != 6 or any(not value.is_absolute() for value in path_fields.values()):
                raise ValueError
            _require_private_file(
                path_fields["repository_password_file"],
                label="repository password file",
            )
            replicas = document["journal_replicas"]
            if not isinstance(replicas, dict) or len(replicas) < 2:
                raise ValueError
            replica_bindings = {
                name: JournalReplicaBinding.from_document(value)
                for name, value in replicas.items()
                if isinstance(name, str)
                and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name)
            }
            if (
                len(replica_bindings) != len(replicas)
                or len({binding.path for binding in replica_bindings.values()}) != len(replicas)
                or len({binding.repository_id for binding in replica_bindings.values()}) != len(replicas)
            ):
                raise ValueError
            fixed = {
                "backup_keep_days": 7,
                "deletion_deadline_days": 8,
                "security_margin_hours": 48,
            }
            if any(document[name] != value for name, value in fixed.items()):
                raise ValueError
            repository = document["repository"]
            _validate_local_repository(repository)
            deployment_id = document["deployment_id"]
            repository_id = document["repository_id"]
            restic_sha256 = document["restic_sha256"]
            writer_uid = document["writer_uid"]
            writer_gid = document["writer_gid"]
            if (
                not isinstance(deployment_id, str)
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{7,126}", deployment_id) is None
                or not isinstance(repository_id, str)
                or _REPOSITORY_ID_PATTERN.fullmatch(repository_id) is None
                or not isinstance(restic_sha256, str)
                or _DIGEST_PATTERN.fullmatch(restic_sha256) is None
                or type(writer_uid) is not int
                or type(writer_gid) is not int
                or not 0 < writer_uid < 2**31
                or not 0 < writer_gid < 2**31
                or _file_digest(path_fields["restic_executable"]) != restic_sha256
                or repository_id
                in {binding.repository_id for binding in replica_bindings.values()}
                or Path(repository)
                in {binding.path for binding in replica_bindings.values()}
            ):
                raise ValueError
            return cls(
                deployment_id=deployment_id,
                **path_fields,
                restic_sha256=restic_sha256,
                repository=repository,
                repository_id=repository_id,
                journal_replicas=replica_bindings,
                writer_uid=writer_uid,
                writer_gid=writer_gid,
                **fixed,
            )
        except (KeyError, OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
            raise ValueError("share operator configuration is invalid") from error


@dataclass(frozen=True, slots=True)
class ShareDeploymentAttestation:
    role: str
    deployment_id: str
    backup_repository_id: str
    journal_repository_ids: dict[str, str]
    storage_key_proof: str
    authority_proofs: tuple[str, ...]

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "authority_proofs": list(self.authority_proofs),
                "backup_repository_id": self.backup_repository_id,
                "deployment_id": self.deployment_id,
                "journal_repository_ids": self.journal_repository_ids,
                "role": self.role,
                "schema_version": 1,
                "storage_key_proof": self.storage_key_proof,
            }
        )

    @classmethod
    def from_bytes(cls, encoded: bytes) -> ShareDeploymentAttestation:
        try:
            document = json.loads(encoded, object_pairs_hook=_unique_object)
            if not isinstance(document, dict) or set(document) != {
                "authority_proofs",
                "backup_repository_id",
                "deployment_id",
                "journal_repository_ids",
                "role",
                "schema_version",
                "storage_key_proof",
            }:
                raise ValueError
            journal_ids = document["journal_repository_ids"]
            authority = document["authority_proofs"]
            attestation = cls(
                role=document["role"],
                deployment_id=document["deployment_id"],
                backup_repository_id=document["backup_repository_id"],
                journal_repository_ids=journal_ids,
                storage_key_proof=document["storage_key_proof"],
                authority_proofs=tuple(authority),
            )
            if (
                attestation.role not in ("writer", "operator")
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{7,126}", attestation.deployment_id)
                is None
                or _REPOSITORY_ID_PATTERN.fullmatch(attestation.backup_repository_id)
                is None
                or not isinstance(journal_ids, dict)
                or len(journal_ids) < 2
                or dict(sorted(journal_ids.items())) != journal_ids
                or len(set(journal_ids.values())) != len(journal_ids)
                or attestation.backup_repository_id in journal_ids.values()
                or any(
                    re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name) is None
                    or not isinstance(identity, str)
                    or _REPOSITORY_ID_PATTERN.fullmatch(identity) is None
                    for name, identity in journal_ids.items()
                )
                or not isinstance(authority, list)
                or sorted(set(authority)) != authority
                or not authority
                or any(_DIGEST_PATTERN.fullmatch(value) is None for value in authority)
                or _DIGEST_PATTERN.fullmatch(attestation.storage_key_proof) is None
                or attestation.to_bytes() != encoded
            ):
                raise ValueError
            return attestation
        except (KeyError, TypeError, ValueError, UnicodeError) as error:
            raise ValueError("share deployment attestation is invalid") from error


def create_writer_attestation(
    writer: ShareWriterConfig,
    *,
    backup_repository_id: str,
    journal_repository_ids: dict[str, str],
) -> ShareDeploymentAttestation:
    """Create the credential-derived writer half after repository authentication."""

    if (
        backup_repository_id != writer.repository_id
        or journal_repository_ids
        != {name: target.repository_id for name, target in writer.journal_anchors.items()}
        or backup_repository_id in journal_repository_ids.values()
        or len(set(journal_repository_ids.values())) != len(journal_repository_ids)
    ):
        raise ValueError("writer repository identities disagree with live evidence")
    secrets = (
        writer.repository_password_file,
        writer.rest_password_file,
        *(
            path
            for target in writer.journal_anchors.values()
            for path in (target.repository_password_file, target.rest_password_file)
        ),
    )
    storage_proof = _secret_equality_proof(
        writer.storage_key_file,
        deployment_id=writer.deployment_id,
    )
    authority_proofs = tuple(
        sorted(
            _secret_equality_proof(path, deployment_id=writer.deployment_id)
            for path in secrets
        )
    )
    if len(set(authority_proofs)) != len(authority_proofs) or storage_proof in authority_proofs:
        raise ValueError("writer storage and authority secret material must be distinct")
    return ShareDeploymentAttestation(
        role="writer",
        deployment_id=writer.deployment_id,
        backup_repository_id=backup_repository_id,
        journal_repository_ids=dict(sorted(journal_repository_ids.items())),
        storage_key_proof=storage_proof,
        authority_proofs=authority_proofs,
    )


def create_operator_attestation(
    operator: ShareOperatorConfig,
    *,
    backup_repository_id: str,
) -> ShareDeploymentAttestation:
    """Create the credential-derived operator half on the operator host only."""

    journal_repository_ids = {
        name: binding.repository_id
        for name, binding in sorted(operator.journal_replicas.items())
    }
    if (
        backup_repository_id != operator.repository_id
        or backup_repository_id in journal_repository_ids.values()
        or len(set(journal_repository_ids.values())) != len(journal_repository_ids)
    ):
        raise ValueError("operator repository identity disagrees with live evidence")
    storage_proof = _secret_equality_proof(
        operator.recovery_key_file,
        deployment_id=operator.deployment_id,
    )
    authority_proof = _secret_equality_proof(
        operator.repository_password_file,
        deployment_id=operator.deployment_id,
    )
    if storage_proof == authority_proof:
        raise ValueError("operator recovery and authority secret material must be distinct")
    return ShareDeploymentAttestation(
        role="operator",
        deployment_id=operator.deployment_id,
        backup_repository_id=backup_repository_id,
        journal_repository_ids=journal_repository_ids,
        storage_key_proof=storage_proof,
        authority_proofs=(authority_proof,),
    )


def validate_role_separation(
    writer: ShareDeploymentAttestation,
    operator: ShareDeploymentAttestation,
) -> None:
    """Compare credential-derived attestations without co-locating role secrets."""

    if writer.role != "writer" or operator.role != "operator":
        raise ValueError("deployment attestations have invalid roles")
    if writer.deployment_id != operator.deployment_id:
        raise ValueError("deployment attestations name different deployments")
    if writer.backup_repository_id != operator.backup_repository_id:
        raise ValueError("writer and operator backup repository identities disagree")
    if writer.journal_repository_ids != operator.journal_repository_ids:
        raise ValueError("writer and operator journal repository identities disagree")
    if (
        writer.backup_repository_id in writer.journal_repository_ids.values()
        or operator.backup_repository_id in operator.journal_repository_ids.values()
        or len(set(writer.journal_repository_ids.values()))
        != len(writer.journal_repository_ids)
        or len(set(operator.journal_repository_ids.values()))
        != len(operator.journal_repository_ids)
    ):
        raise ValueError("primary backup repository cannot be a journal repository")
    if writer.storage_key_proof != operator.storage_key_proof:
        raise ValueError("operator recovery key does not match the active storage key")
    if set(writer.authority_proofs) & set(operator.authority_proofs):
        raise ValueError("writer and operator authority secret material is shared")
    if writer.storage_key_proof in {
        *writer.authority_proofs,
        *operator.authority_proofs,
    }:
        raise ValueError("storage and authority secret material is shared")


@dataclass(frozen=True, slots=True)
class RetirementJournalEntry:
    sequence: int
    previous_digest: str
    entry_digest: str
    event: ShareRetirementEvent

    def to_bytes(self) -> bytes:
        document = self._document(include_digest=True)
        return _canonical_json(document)

    def _document(self, *, include_digest: bool) -> dict[str, object]:
        document: dict[str, object] = {
            "event": json.loads(self.event.to_bytes()),
            "previous_digest": self.previous_digest,
            "schema_version": 1,
            "sequence": self.sequence,
        }
        if include_digest:
            document["entry_digest"] = self.entry_digest
        return document


@dataclass(frozen=True, slots=True)
class RetirementJournalHead:
    sequence: int
    digest: str


@dataclass(frozen=True, slots=True)
class ShareBackupManifest:
    created_at: datetime
    backup_repository_id: str
    database_digest: str
    journal_head: RetirementJournalHead
    journal_replicas: dict[str, str]

    def to_bytes(self) -> bytes:
        return _canonical_json(
            {
                "created_at": _format_time(self.created_at),
                "backup_repository_id": self.backup_repository_id,
                "database_digest": self.database_digest,
                "journal_head": {
                    "digest": self.journal_head.digest,
                    "sequence": self.journal_head.sequence,
                },
                "journal_replicas": self.journal_replicas,
                "schema_version": 2,
            }
        )

    @classmethod
    def from_bytes(cls, encoded: bytes) -> ShareBackupManifest:
        try:
            document = json.loads(encoded, object_pairs_hook=_unique_object)
            if not isinstance(document, dict) or set(document) != {
                "created_at",
                "backup_repository_id",
                "database_digest",
                "journal_head",
                "journal_replicas",
                "schema_version",
            }:
                raise ValueError
            if document["schema_version"] != 2:
                raise ValueError
            head = document["journal_head"]
            replicas = document["journal_replicas"]
            if not isinstance(head, dict) or set(head) != {"digest", "sequence"}:
                raise ValueError
            if (
                not isinstance(replicas, dict)
                or len(replicas) < 2
                or dict(sorted(replicas.items())) != replicas
                or any(
                    not isinstance(name, str)
                    or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name) is None
                    or not isinstance(identity, str)
                    or _REPOSITORY_ID_PATTERN.fullmatch(identity) is None
                    for name, identity in replicas.items()
                )
                or len(set(replicas.values())) != len(replicas)
                or not isinstance(document["backup_repository_id"], str)
                or _REPOSITORY_ID_PATTERN.fullmatch(document["backup_repository_id"])
                is None
                or not isinstance(head["sequence"], int)
                or isinstance(head["sequence"], bool)
                or head["sequence"] < 0
                or _DIGEST_PATTERN.fullmatch(head["digest"]) is None
                or _DIGEST_PATTERN.fullmatch(document["database_digest"]) is None
            ):
                raise ValueError
            manifest = cls(
                created_at=_parse_time(document["created_at"]),
                backup_repository_id=document["backup_repository_id"],
                database_digest=document["database_digest"],
                journal_head=RetirementJournalHead(head["sequence"], head["digest"]),
                journal_replicas=replicas,
            )
            if manifest.to_bytes() != encoded:
                raise ValueError
            return manifest
        except (KeyError, TypeError, ValueError, UnicodeError) as error:
            raise RestoreGuardError("share backup manifest is invalid") from error


@dataclass(frozen=True, slots=True)
class ShareBackupReceipt:
    repository_id: str
    snapshot_id: str
    manifest_path: Path
    manifest_digest: str


@dataclass(frozen=True, slots=True)
class ShareOperationsCycleReceipt:
    purge: SharePurgeResult
    backup: ShareBackupReceipt
    validated_records: int


@dataclass(frozen=True, slots=True)
class RestoreReceipt:
    destination: Path
    replayed_retirements: int
    journal_head: RetirementJournalHead


class RestoreGuardError(RuntimeError):
    """A backup cannot be promoted without complete no-resurrection proof."""


class ShareOperationsRunner:
    """Own the ordered hourly sweep, validation, snapshot, and staging cleanup."""

    def __init__(
        self,
        storage: EncryptedSQLiteShareStorage,
        journal: ChainedRetirementJournal,
        writer: BackupWriterPort,
        *,
        staging_root: Path,
    ) -> None:
        if not isinstance(staging_root, Path):
            raise TypeError("share backup staging root must be a pathlib.Path")
        self._storage = storage
        self._journal = journal
        self._writer = writer
        self._staging_root = staging_root

    def run(self, *, now: datetime) -> ShareOperationsCycleReceipt:
        checked_now = _aware_utc(now)
        with _share_operation_lock(self._storage.database_path.parent):
            return self._run_locked(now=checked_now)

    @classmethod
    def run_configured(
        cls,
        *,
        active_root: Path,
        encryption_key: bytes,
        journal_root: Path,
        anchors: dict[str, RetirementAnchorPort],
        writer: BackupWriterPort,
        staging_root: Path,
        now: datetime,
    ) -> ShareOperationsCycleReceipt:
        """Lock the stable path before opening any replaceable writer state."""

        checked_now = _aware_utc(now)
        with _share_operation_lock(active_root):
            journal = ChainedRetirementJournal(journal_root, anchors)
            storage = EncryptedSQLiteShareStorage(
                active_root,
                encryption_key,
                retirement_recorder=journal,
            )
            return cls(
                storage,
                journal,
                writer,
                staging_root=staging_root,
            )._run_locked(now=checked_now)

    def _run_locked(self, *, now: datetime) -> ShareOperationsCycleReceipt:
        if self._storage.retirement_seal() is not None:
            raise ShareStorageConflictError(
                "share writer refuses a store durably sealed for retirement"
            )
        purge = self._storage.purge(now)
        validated = self._storage.validate_all()
        try:
            backup = self._create_backup(now=now)
            return ShareOperationsCycleReceipt(purge, backup, validated)
        finally:
            self._clean_staging()

    def _create_backup(self, *, now: datetime) -> ShareBackupReceipt:
        if self._staging_root.exists():
            if (
                self._staging_root.is_symlink()
                or not self._staging_root.is_dir()
                or any(self._staging_root.iterdir())
            ):
                raise ValueError("backup staging root must be absent or empty")
            _require_private_directory(self._staging_root)
        else:
            self._staging_root.mkdir(mode=0o700, parents=True)
        self._storage.validate_all()
        if self._storage.retirement_seal() is not None:
            raise ShareStorageConflictError(
                "share writer refuses a store durably sealed for retirement"
            )
        head = self._journal.anchored_head()
        repository_id = self._writer.repository_identity()
        database_path = self._staging_root / "shares.sqlite3"
        self._storage.backup_to(database_path)
        manifest = ShareBackupManifest(
            created_at=now,
            backup_repository_id=repository_id,
            database_digest=_file_digest(database_path),
            journal_head=head,
            journal_replicas=self._journal.replica_ids,
        )
        manifest_path = self._staging_root / _BACKUP_MANIFEST_NAME
        _create_only(manifest_path, manifest.to_bytes())
        snapshot = self._writer.backup(
            (database_path, manifest_path),
            tags=("codemble-share-backup",),
        )
        if (
            not isinstance(snapshot, ResticSnapshotReceipt)
            or snapshot.repository_id != repository_id
            or _SNAPSHOT_ID_PATTERN.fullmatch(snapshot.snapshot_id) is None
        ):
            raise RuntimeError("backup writer returned an invalid snapshot identity")
        return ShareBackupReceipt(
            repository_id=repository_id,
            snapshot_id=snapshot.snapshot_id,
            manifest_path=manifest_path,
            manifest_digest="sha256:" + sha256(manifest.to_bytes()).hexdigest(),
        )

    def _clean_staging(self) -> None:
        expected = {
            self._staging_root / "shares.sqlite3",
            self._staging_root / _BACKUP_MANIFEST_NAME,
        }
        if self._staging_root.exists():
            unexpected = set(self._staging_root.iterdir()) - expected
            if unexpected:
                raise RuntimeError("share backup staging contains unexpected files")
        for path in expected:
            if path.exists():
                if path.is_symlink() or not path.is_file():
                    raise RuntimeError("share backup staging changed before cleanup")
                path.unlink()


@contextmanager
def _share_operation_lock(active_root: Path):
    """Exclude concurrent writer/retirement transitions without unsafe cleanup."""

    resolved = active_root.resolve(strict=False)
    with _OPERATION_LOCKS_GUARD:
        thread_lock = _OPERATION_LOCKS.setdefault(resolved, RLock())
    if not thread_lock.acquire(blocking=False):
        raise RuntimeError("another share operation already owns the active store")
    parent_descriptor: int | None = None
    descriptor: int | None = None
    try:
        lock_name = f".{resolved.name}.share-operations.lock"
        try:
            parent_descriptor = os.open(
                resolved.parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            parent = os.fstat(parent_descriptor)
            if (
                not stat.S_ISDIR(parent.st_mode)
                or stat.S_IMODE(parent.st_mode) & 0o022
            ):
                raise RuntimeError(
                    "share operation lock parent must not be group- or other-writable"
                )
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
            created = False
            try:
                descriptor = os.open(lock_name, flags, dir_fd=parent_descriptor)
            except FileNotFoundError:
                if os.geteuid() != parent.st_uid or parent.st_uid == 0:
                    raise RuntimeError(
                        "share operation lock must be pre-created by the parent owner"
                    )
                try:
                    descriptor = os.open(
                        lock_name,
                        flags | os.O_CREAT | os.O_EXCL,
                        0o660,
                        dir_fd=parent_descriptor,
                    )
                    created = True
                except FileExistsError:
                    descriptor = os.open(lock_name, flags, dir_fd=parent_descriptor)
            lock = os.fstat(descriptor)
            if created:
                if lock.st_gid != parent.st_gid:
                    os.fchown(descriptor, -1, parent.st_gid)
                os.fchmod(descriptor, 0o660)
                lock = os.fstat(descriptor)
            if (
                not stat.S_ISREG(lock.st_mode)
                or lock.st_nlink != 1
                or lock.st_uid != parent.st_uid
                or lock.st_gid != parent.st_gid
                or stat.S_IMODE(lock.st_mode) != 0o660
            ):
                raise RuntimeError(
                    "share operation lock must be a parent-owned 0660 regular file"
                )
            named_lock = os.stat(
                lock_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(named_lock.st_mode)
                or named_lock.st_nlink != 1
                or named_lock.st_dev != lock.st_dev
                or named_lock.st_ino != lock.st_ino
            ):
                raise RuntimeError("share operation lock path changed during admission")
        except OSError as error:
            raise RuntimeError(
                "share operation lock ownership contract is unavailable"
            ) from error
        try:
            flock(descriptor, LOCK_EX | LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("another share operation already owns the active store") from error
        named_lock = os.stat(
            lock_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        locked = os.fstat(descriptor)
        if (
            named_lock.st_dev != locked.st_dev
            or named_lock.st_ino != locked.st_ino
            or named_lock.st_nlink != 1
        ):
            raise RuntimeError("share operation lock path changed before acquisition")
        yield
    finally:
        if descriptor is not None:
            try:
                flock(descriptor, LOCK_UN)
            finally:
                os.close(descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)
        thread_lock.release()


class RestoreGuard:
    """Validate a quarantined backup, replay retirements, and atomically promote."""

    def verify_and_promote(
        self,
        quarantine_root: Path,
        destination: Path,
        *,
        encryption_key: bytes,
        journal_replicas: dict[str, JournalReplicaBinding],
        backup_repository_id: str,
        writer_journal_root: Path,
        writer_uid: int,
        writer_gid: int,
        now: datetime,
        rollback: Path | None = None,
    ) -> RestoreReceipt:
        with _share_operation_lock(destination):
            return self._verify_and_promote_locked(
                quarantine_root,
                destination,
                encryption_key=encryption_key,
                journal_replicas=journal_replicas,
                backup_repository_id=backup_repository_id,
                writer_journal_root=writer_journal_root,
                writer_uid=writer_uid,
                writer_gid=writer_gid,
                now=now,
                rollback=rollback,
            )

    def _verify_and_promote_locked(
        self,
        quarantine_root: Path,
        destination: Path,
        *,
        encryption_key: bytes,
        journal_replicas: dict[str, JournalReplicaBinding],
        backup_repository_id: str,
        writer_journal_root: Path,
        writer_uid: int,
        writer_gid: int,
        now: datetime,
        rollback: Path | None,
    ) -> RestoreReceipt:
        _require_private_directory(quarantine_root)
        manifest_path = quarantine_root / _BACKUP_MANIFEST_NAME
        database_path = quarantine_root / "shares.sqlite3"
        try:
            manifest = ShareBackupManifest.from_bytes(manifest_path.read_bytes())
        except OSError as error:
            raise RestoreGuardError("share backup manifest is missing") from error
        if _file_digest(database_path) != manifest.database_digest:
            raise RestoreGuardError("restored database does not match its backup manifest")
        if manifest.backup_repository_id != backup_repository_id:
            raise RestoreGuardError("backup repository identity does not match the manifest")
        actual_names = tuple(sorted(journal_replicas))
        manifest_names = tuple(manifest.journal_replicas)
        if actual_names != manifest_names or {
            name: journal_replicas[name].repository_id for name in actual_names
        } != manifest.journal_replicas:
            missing = sorted(set(manifest_names) - set(actual_names))
            detail = ", ".join(missing) if missing else "inventory mismatch"
            raise RestoreGuardError(f"missing journal replica: {detail}")
        try:
            chains = {
                name: _load_anchored_replica(
                    journal_replicas[name].path,
                    name=name,
                    replica_ids=manifest.journal_replicas,
                )
                for name in manifest_names
            }
        except RetirementJournalError as error:
            raise RestoreGuardError("retirement replica anchor evidence is invalid") from error
        reference = chains[manifest_names[0]]
        if any(chain != reference for chain in chains.values()):
            raise RestoreGuardError("journal replicas disagree")
        if len(reference) < manifest.journal_head.sequence:
            raise RestoreGuardError("retirement journal is stale for this backup")
        if manifest.journal_head.sequence:
            bound_digest = reference[manifest.journal_head.sequence - 1].entry_digest
        else:
            bound_digest = _ZERO_DIGEST
        if bound_digest != manifest.journal_head.digest:
            raise RestoreGuardError("retirement journal does not match backup high-water")

        storage = EncryptedSQLiteShareStorage(quarantine_root, encryption_key)
        storage.validate_all()
        retirements = tuple(
            entry.event for entry in reference[manifest.journal_head.sequence :]
        )
        replayed = storage.apply_retirements(retirements)
        storage.purge(_aware_utc(now))
        storage.validate_all()
        final_head = _head(reference)
        _rehydrate_writer_journal(
            writer_journal_root,
            journal_replicas=journal_replicas,
            reference=reference,
        )
        _assign_private_tree_identity(
            writer_journal_root,
            uid=writer_uid,
            gid=writer_gid,
        )
        _assign_private_tree_identity(
            quarantine_root,
            uid=writer_uid,
            gid=writer_gid,
        )
        self._promote(quarantine_root, destination, rollback=rollback)
        return RestoreReceipt(destination, replayed, final_head)

    def _promote(
        self,
        quarantine_root: Path,
        destination: Path,
        *,
        rollback: Path | None,
    ) -> None:
        if destination.exists() and rollback is None:
            raise RestoreGuardError("existing destination requires an explicit rollback path")
        if rollback is not None and rollback.exists():
            raise RestoreGuardError("restore rollback path must not already exist")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if quarantine_root.stat().st_dev != destination.parent.stat().st_dev:
            raise RestoreGuardError("restore promotion must stay on one filesystem")
        moved_existing = False
        try:
            if destination.exists():
                assert rollback is not None
                os.replace(destination, rollback)
                moved_existing = True
            os.replace(quarantine_root, destination)
        except Exception as error:
            if moved_existing and rollback is not None and not destination.exists():
                os.replace(rollback, destination)
            raise RestoreGuardError("atomic restore promotion failed") from error


class SecurityMetadataRetirementError(RuntimeError):
    """Security metadata cannot yet be retired from every inventoried copy."""


@dataclass(frozen=True, slots=True)
class SecurityMetadataRetirementReceipt:
    authorized_at: datetime
    not_before: datetime
    retirement_events: int
    journal_head: RetirementJournalHead
    seal_epoch: str
    backup_repository_id: str
    inventory_digest: str


@dataclass(frozen=True, slots=True)
class BackupRetirementReceipt:
    repository_id: str
    removed_snapshot_ids: tuple[str, ...]
    seal_epoch: str


class SecurityMetadataRetirementGuard:
    """Authorize whole-key-store retirement only after every copy is safe."""

    def __init__(
        self,
        *,
        deletion_deadline: timedelta,
        safety_margin: timedelta,
    ) -> None:
        if deletion_deadline != timedelta(days=8):
            raise ValueError("share deletion deadline is fixed at eight days")
        if safety_margin != timedelta(hours=48):
            raise ValueError("security metadata safety margin is fixed at 48 hours")
        self._retirement_delay = deletion_deadline + safety_margin

    def authorize(
        self,
        storage: EncryptedSQLiteShareStorage,
        *,
        journal_replicas: dict[str, JournalReplicaBinding],
        backup_inventory: BackupInventoryPort,
        expected_backup_repository_id: str,
        now: datetime,
    ) -> SecurityMetadataRetirementReceipt:
        checked_now = _aware_utc(now)
        names = tuple(sorted(journal_replicas))
        if len(names) < 2 or any(
            re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name) is None for name in names
        ):
            raise SecurityMetadataRetirementError(
                "every independently controlled journal replica is required"
            )
        try:
            chains = tuple(
                _load_anchored_replica(
                    journal_replicas[name].path,
                    name=name,
                    replica_ids={
                        replica_name: binding.repository_id
                        for replica_name, binding in sorted(journal_replicas.items())
                    },
                )
                for name in names
            )
        except RetirementJournalError as error:
            raise SecurityMetadataRetirementError(
                "retirement replica anchor evidence is invalid"
            ) from error
        reference = chains[0]
        if not reference or any(chain != reference for chain in chains[1:]):
            raise SecurityMetadataRetirementError("journal replicas are empty or disagree")
        not_before = max(entry.event.terminal_at for entry in reference) + self._retirement_delay
        if checked_now < not_before:
            raise SecurityMetadataRetirementError("security metadata safety horizon has not elapsed")
        with _share_operation_lock(storage.database_path.parent):
            seal = storage.retirement_seal()
            if seal is None:
                raise SecurityMetadataRetirementError(
                    "active store lacks the required retirement seal"
                )
            if storage.validate_all() != 0:
                raise SecurityMetadataRetirementError("active or terminal share records remain")
            inventory = backup_inventory.snapshot_inventory(
                tags=("codemble-share-backup",)
            )
            if (
                not isinstance(inventory, BackupInventoryReceipt)
                or inventory.repository_id != expected_backup_repository_id
                or _REPOSITORY_ID_PATTERN.fullmatch(inventory.repository_id) is None
                or any(
                    _SNAPSHOT_ID_PATTERN.fullmatch(identity) is None
                    for identity in inventory.snapshot_ids
                )
            ):
                raise SecurityMetadataRetirementError("backup inventory is malformed")
            if inventory.snapshot_ids:
                raise SecurityMetadataRetirementError("backup snapshots remain")
        return SecurityMetadataRetirementReceipt(
            authorized_at=checked_now,
            not_before=not_before,
            retirement_events=len(reference),
            journal_head=_head(reference),
            seal_epoch=seal.epoch,
            backup_repository_id=inventory.repository_id,
            inventory_digest="sha256:"
            + sha256(
                _canonical_json(
                    {
                        "repository_id": inventory.repository_id,
                        "snapshot_ids": list(inventory.snapshot_ids),
                    }
                )
            ).hexdigest(),
        )


def retire_backup_snapshots(
    storage: EncryptedSQLiteShareStorage,
    operator: ResticOperator,
    *,
    expected_snapshot_ids: tuple[str, ...],
    expected_backup_repository_id: str,
    now: datetime,
) -> BackupRetirementReceipt:
    """Seal the store, remove the exact live inventory, and prove it empty."""

    if (
        tuple(sorted(set(expected_snapshot_ids))) != expected_snapshot_ids
        or any(_SNAPSHOT_ID_PATTERN.fullmatch(value) is None for value in expected_snapshot_ids)
    ):
        raise ValueError("backup retirement requires the exact sorted snapshot inventory")
    with _share_operation_lock(storage.database_path.parent):
        before = operator.snapshot_inventory(tags=("codemble-share-backup",))
        if (
            before.repository_id != expected_backup_repository_id
            or before.snapshot_ids != expected_snapshot_ids
        ):
            raise SecurityMetadataRetirementError(
                "live backup inventory does not match the explicit retirement set"
            )
        try:
            seal = storage.seal_for_retirement(_aware_utc(now))
        except ShareStorageConflictError as error:
            raise SecurityMetadataRetirementError(
                "active or terminal share records remain"
            ) from error
        sealed_inventory = operator.snapshot_inventory(tags=("codemble-share-backup",))
        if (
            sealed_inventory.repository_id != expected_backup_repository_id
            or sealed_inventory.snapshot_ids != expected_snapshot_ids
        ):
            raise SecurityMetadataRetirementError(
                "backup inventory changed while installing the retirement seal"
            )
        if expected_snapshot_ids:
            operator.remove_snapshots(expected_snapshot_ids)
        operator.full_check()
        after = operator.snapshot_inventory(tags=("codemble-share-backup",))
        if after.repository_id != expected_backup_repository_id or after.snapshot_ids:
            raise SecurityMetadataRetirementError("backup retirement did not reach an empty inventory")
        return BackupRetirementReceipt(
            repository_id=after.repository_id,
            removed_snapshot_ids=expected_snapshot_ids,
            seal_epoch=seal.epoch,
        )


class ChainedRetirementJournal:
    """Serialized create-only chain replicated to every configured anchor."""

    def __init__(
        self,
        root: Path,
        anchors: dict[str, RetirementAnchorPort],
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError("retirement journal root must be a pathlib.Path")
        names = tuple(sorted(anchors)) if isinstance(anchors, dict) else ()
        if len(names) < 2 or any(
            re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name) is None
            for name in names
        ):
            raise ValueError("retirement journal requires two named anchor adapters")
        if any(not hasattr(anchors[name], "anchor") for name in names):
            raise TypeError("retirement journal anchor is invalid")
        try:
            replica_ids = {
                name: anchors[name].repository_identity() for name in names
            }
        except (AttributeError, ResticCommandError, TypeError, ValueError) as error:
            raise RetirementJournalError(
                "retirement journal anchor identity is unavailable"
            ) from error
        if (
            len(set(replica_ids.values())) != len(names)
            or any(_REPOSITORY_ID_PATTERN.fullmatch(value) is None for value in replica_ids.values())
        ):
            raise RetirementJournalError(
                "retirement journal anchors must have distinct authenticated identities"
            )
        self._root = root
        self._events = root / "events"
        self._receipts = root / "receipts"
        self._anchors = {name: anchors[name] for name in names}
        self._replica_names = names
        self._replica_ids = replica_ids
        for directory in (self._root, self._events, self._receipts):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            _require_private_directory(directory)
        replica_manifest = self._root / "replicas.json"
        expected_manifest = _canonical_json(
            {"replicas": replica_ids, "schema_version": 2}
        )
        with _journal_lock(self._root):
            if replica_manifest.exists():
                _require_private_file(replica_manifest, label="retirement replica manifest")
                if replica_manifest.read_bytes() != expected_manifest:
                    raise RetirementJournalError("retirement replica inventory changed")
            else:
                _create_only(replica_manifest, expected_manifest)

    @property
    def replica_names(self) -> tuple[str, ...]:
        """Return the immutable names bound to every journal entry."""

        return self._replica_names

    @property
    def replica_ids(self) -> dict[str, str]:
        """Return the immutable name-to-repository identity inventory."""

        return dict(self._replica_ids)

    def record(self, event: ShareRetirementEvent) -> None:
        if not isinstance(event, ShareRetirementEvent):
            raise TypeError("retirement journal accepts ShareRetirementEvent only")
        with _journal_lock(self._root):
            entries = load_retirement_journal(self._root)
            existing = next(
                (item for item in entries if item.event.event_id == event.event_id),
                None,
            )
            anchored = self._anchored_prefix(entries)
            if existing is None:
                if anchored.sequence != len(entries):
                    raise RetirementJournalError(
                        "previous retirement entry is not fully anchored"
                    )
                entry = _new_entry(anchored.sequence + 1, anchored.digest, event)
                path = self._events / f"{entry.sequence:020d}-{event.event_id}.json"
                _create_only(path, entry.to_bytes())
            else:
                if existing.event != event:
                    raise RetirementJournalError("retirement event identity collision")
                entry = existing
                path = self._events / f"{entry.sequence:020d}-{event.event_id}.json"
                if not path.exists():
                    raise RetirementJournalError("retirement entry path is ambiguous")
            for name, anchor in self._anchors.items():
                receipt = self._receipt_path(entry, name)
                if receipt.exists():
                    self._validate_receipt(receipt, entry, name)
                    continue
                anchor_receipt = anchor.anchor(
                    path,
                    tags=(
                        "codemble-share-retirement",
                        f"replica-{name}",
                        f"sequence-{entry.sequence}",
                        f"event-{event.event_id}",
                    ),
                    replica_name=name,
                    entry_digest=entry.entry_digest,
                )
                self._validate_anchor_result(anchor_receipt, entry, name)
                _create_only(receipt, anchor_receipt.to_bytes())

    def anchored_head(self) -> RetirementJournalHead:
        """Return only the contiguous head acknowledged by every named replica."""

        with _journal_lock(self._root):
            return self._anchored_prefix(load_retirement_journal(self._root))

    def _anchored_prefix(
        self,
        entries: tuple[RetirementJournalEntry, ...],
    ) -> RetirementJournalHead:
        anchored: list[RetirementJournalEntry] = []
        for entry in entries:
            receipts = [
                (name, self._receipt_path(entry, name))
                for name in self._replica_names
            ]
            if not all(receipt.exists() for _name, receipt in receipts):
                break
            for name, receipt in receipts:
                self._validate_receipt(receipt, entry, name)
            anchored.append(entry)
        return _head(tuple(anchored))

    def _receipt_path(self, entry: RetirementJournalEntry, name: str) -> Path:
        return self._receipts / f"{entry.event.event_id}.{name}.anchored"

    def _validate_receipt(
        self, path: Path, entry: RetirementJournalEntry, name: str
    ) -> None:
        _require_private_file(path, label="retirement anchor receipt")
        try:
            receipt = _parse_anchor_receipt(path.read_bytes())
            self._validate_anchor_result(receipt, entry, name)
        except (TypeError, ValueError) as error:
            raise RetirementJournalError("retirement anchor receipt is invalid") from error

    def _validate_anchor_result(
        self,
        receipt: RetirementAnchorReceipt,
        entry: RetirementJournalEntry,
        name: str,
    ) -> None:
        if (
            not isinstance(receipt, RetirementAnchorReceipt)
            or receipt.replica_name != name
            or receipt.repository_id != self._replica_ids[name]
            or receipt.entry_digest != entry.entry_digest
            or _SNAPSHOT_ID_PATTERN.fullmatch(receipt.snapshot_id) is None
        ):
            raise RetirementJournalError("retirement anchor receipt is invalid")


@contextmanager
def _journal_lock(root: Path):
    resolved = root.resolve()
    with _JOURNAL_LOCKS_GUARD:
        thread_lock = _JOURNAL_LOCKS.setdefault(resolved, RLock())
    with thread_lock:
        lock_path = root / "journal.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.chmod(lock_path, 0o600)
            flock(descriptor, LOCK_EX)
            yield
        finally:
            flock(descriptor, LOCK_UN)
            os.close(descriptor)


def _load_anchored_replica(
    root: Path,
    *,
    name: str,
    replica_ids: dict[str, str],
) -> tuple[RetirementJournalEntry, ...]:
    try:
        manifest = root / "replicas.json"
        _require_private_file(manifest, label="retirement replica manifest")
        expected = _canonical_json(
            {"replicas": replica_ids, "schema_version": 2}
        )
        if manifest.read_bytes() != expected:
            raise ValueError
        entries = load_retirement_journal(root)
        for entry in entries:
            receipt = root / "receipts" / f"{entry.event.event_id}.{name}.anchored"
            _require_private_file(receipt, label="retirement anchor receipt")
            parsed = _parse_anchor_receipt(receipt.read_bytes())
            if (
                parsed.replica_name != name
                or parsed.repository_id != replica_ids[name]
                or parsed.entry_digest != entry.entry_digest
            ):
                raise ValueError
        return entries
    except (OSError, TypeError, UnicodeError, ValueError) as error:
        raise RetirementJournalError(
            f"retirement replica {name} lacks complete anchor evidence"
        ) from error


def _rehydrate_writer_journal(
    destination: Path,
    *,
    journal_replicas: dict[str, JournalReplicaBinding],
    reference: tuple[RetirementJournalEntry, ...],
) -> None:
    """Atomically rebuild the writer chain from agreeing independent replicas."""

    replica_ids = {
        name: binding.repository_id for name, binding in sorted(journal_replicas.items())
    }
    if destination.exists():
        if _load_complete_writer_journal(destination, replica_ids=replica_ids) != reference:
            raise RestoreGuardError("existing writer journal does not match recovery replicas")
        return
    staging = destination.with_name(destination.name + ".rehydrating")
    if staging.exists():
        raise RestoreGuardError("writer journal rehydration staging already exists")
    events = staging / "events"
    receipts = staging / "receipts"
    for directory in (staging, events, receipts):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require_private_directory(directory)
    _create_only(
        staging / "replicas.json",
        _canonical_json({"replicas": replica_ids, "schema_version": 2}),
    )
    for entry in reference:
        _create_only(
            events / f"{entry.sequence:020d}-{entry.event.event_id}.json",
            entry.to_bytes(),
        )
        for name, binding in sorted(journal_replicas.items()):
            source = binding.path / "receipts" / f"{entry.event.event_id}.{name}.anchored"
            parsed = _parse_anchor_receipt(source.read_bytes())
            if (
                parsed.replica_name != name
                or parsed.repository_id != binding.repository_id
                or parsed.entry_digest != entry.entry_digest
            ):
                raise RestoreGuardError("journal receipt changed during rehydration")
            _create_only(
                receipts / f"{entry.event.event_id}.{name}.anchored",
                parsed.to_bytes(),
            )
    if _load_complete_writer_journal(staging, replica_ids=replica_ids) != reference:
        raise RestoreGuardError("rehydrated writer journal failed validation")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.replace(staging, destination)


def _assign_private_tree_identity(root: Path, *, uid: int, gid: int) -> None:
    """Give one validated private tree to the configured non-root writer."""

    if (
        not isinstance(root, Path)
        or type(uid) is not int
        or type(gid) is not int
        or not 0 < uid < 2**31
        or not 0 < gid < 2**31
    ):
        raise RestoreGuardError("writer ownership identity is invalid")
    _require_private_directory(root)
    try:
        for _current, directories, files, descriptor in os.fwalk(
            root,
            topdown=False,
            follow_symlinks=False,
        ):
            for name in files:
                _assign_private_entry_identity(
                    descriptor,
                    name,
                    uid=uid,
                    gid=gid,
                    directory=False,
                )
            for name in directories:
                _assign_private_entry_identity(
                    descriptor,
                    name,
                    uid=uid,
                    gid=gid,
                    directory=True,
                )
            current = os.fstat(descriptor)
            if not stat.S_ISDIR(current.st_mode):
                raise RestoreGuardError("restore ownership tree contains a non-directory")
            os.fchown(descriptor, uid, gid)
            os.fchmod(descriptor, 0o700)
            assigned = os.fstat(descriptor)
            if (
                assigned.st_uid != uid
                or assigned.st_gid != gid
                or stat.S_IMODE(assigned.st_mode) != 0o700
            ):
                raise RestoreGuardError("restore ownership handoff did not persist")
    except OSError as error:
        raise RestoreGuardError("restore ownership handoff failed") from error


def _assign_private_entry_identity(
    parent_descriptor: int,
    name: str,
    *,
    uid: int,
    gid: int,
    directory: bool,
) -> None:
    facts = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(facts.st_mode) or (not directory and facts.st_nlink != 1):
        raise RestoreGuardError("restore ownership tree contains an unsafe entry")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    if directory:
        flags |= os.O_DIRECTORY
    else:
        flags |= os.O_NONBLOCK
    descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    try:
        opened = os.fstat(descriptor)
        if (
            not expected(opened.st_mode)
            or opened.st_dev != facts.st_dev
            or opened.st_ino != facts.st_ino
            or (not directory and opened.st_nlink != 1)
        ):
            raise RestoreGuardError("restore ownership entry changed during handoff")
        os.fchown(descriptor, uid, gid)
        mode = 0o700 if directory else 0o600
        os.fchmod(descriptor, mode)
        assigned = os.fstat(descriptor)
        if (
            assigned.st_uid != uid
            or assigned.st_gid != gid
            or stat.S_IMODE(assigned.st_mode) != mode
        ):
            raise RestoreGuardError("restore ownership handoff did not persist")
    finally:
        os.close(descriptor)


def materialize_journal_replica(
    operator: ResticOperator,
    *,
    replica_name: str,
    replica_ids: dict[str, str],
    destination: Path,
    quarantine_root: Path,
) -> RetirementJournalHead:
    """Restore one independent journal repository into the replica evidence layout."""

    if (
        replica_name not in replica_ids
        or len(replica_ids) < 2
        or dict(sorted(replica_ids.items())) != replica_ids
        or len(set(replica_ids.values())) != len(replica_ids)
    ):
        raise ValueError("journal materialization requires the complete replica inventory")
    if operator.repository_identity() != replica_ids[replica_name]:
        raise RetirementJournalError("journal repository identity does not match its replica")
    staging = destination.with_name(destination.name + ".materializing")
    if destination.exists() or staging.exists() or quarantine_root.exists():
        raise ValueError("journal materialization destinations must not already exist")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    quarantine_root.mkdir(mode=0o700, parents=True)
    operator.full_check()
    snapshots = operator.snapshots(
        tags=("codemble-share-retirement", f"replica-{replica_name}")
    )
    recovered: dict[int, tuple[RetirementJournalEntry, str]] = {}
    try:
        for snapshot in snapshots:
            target = quarantine_root / snapshot.snapshot_id
            operator.restore(snapshot.snapshot_id, target)
            candidates = tuple(target.rglob("*.json"))
            if len(candidates) != 1:
                raise RetirementJournalError(
                    "journal snapshot must restore exactly one event entry"
                )
            entry = _parse_entry(candidates[0])
            required_tags = {
                "codemble-share-retirement",
                f"replica-{replica_name}",
                f"sequence-{entry.sequence}",
                f"event-{entry.event.event_id}",
            }
            if not required_tags.issubset(snapshot.tags):
                raise RetirementJournalError("journal snapshot tags contradict its event")
            existing = recovered.get(entry.sequence)
            if existing is not None and existing[0] != entry:
                raise RetirementJournalError("journal repository contains a forked sequence")
            if existing is None or snapshot.snapshot_id < existing[1]:
                recovered[entry.sequence] = (entry, snapshot.snapshot_id)

        events = staging / "events"
        receipts = staging / "receipts"
        for directory in (staging, events, receipts):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            _require_private_directory(directory)
        _create_only(
            staging / "replicas.json",
            _canonical_json({"replicas": replica_ids, "schema_version": 2}),
        )
        for sequence in sorted(recovered):
            entry, snapshot_id = recovered[sequence]
            _create_only(
                events / f"{entry.sequence:020d}-{entry.event.event_id}.json",
                entry.to_bytes(),
            )
            receipt = RetirementAnchorReceipt(
                replica_name=replica_name,
                repository_id=replica_ids[replica_name],
                snapshot_id=snapshot_id,
                entry_digest=entry.entry_digest,
            )
            _create_only(
                receipts / f"{entry.event.event_id}.{replica_name}.anchored",
                receipt.to_bytes(),
            )
        chain = _load_anchored_replica(
            staging,
            name=replica_name,
            replica_ids=replica_ids,
        )
        os.replace(staging, destination)
        return _head(chain)
    finally:
        if quarantine_root.exists():
            _remove_private_tree(quarantine_root)


def _load_complete_writer_journal(
    root: Path,
    *,
    replica_ids: dict[str, str],
) -> tuple[RetirementJournalEntry, ...]:
    chains = tuple(
        _load_anchored_replica(
            root,
            name=name,
            replica_ids=replica_ids,
        )
        for name in replica_ids
    )
    reference = chains[0]
    if any(chain != reference for chain in chains[1:]):
        raise RetirementJournalError("writer journal receipts disagree")
    return reference


def _remove_private_tree(root: Path) -> None:
    """Remove only a verified private, non-symlink materialization root."""

    _require_private_directory(root)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            raise RetirementJournalError("materialization quarantine contains a symlink")
        if path.is_dir():
            path.rmdir()
        elif path.is_file():
            path.unlink()
        else:
            raise RetirementJournalError("materialization quarantine contains a special file")
    root.rmdir()


def _parse_anchor_receipt(encoded: bytes) -> RetirementAnchorReceipt:
    document = json.loads(encoded, object_pairs_hook=_unique_object)
    if not isinstance(document, dict) or set(document) != {
        "entry_digest",
        "replica_name",
        "repository_id",
        "schema_version",
        "snapshot_id",
    }:
        raise ValueError
    receipt = RetirementAnchorReceipt(
        replica_name=document["replica_name"],
        repository_id=document["repository_id"],
        snapshot_id=document["snapshot_id"],
        entry_digest=document["entry_digest"],
    )
    if (
        document["schema_version"] != 1
        or not isinstance(receipt.replica_name, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", receipt.replica_name) is None
        or not isinstance(receipt.repository_id, str)
        or _REPOSITORY_ID_PATTERN.fullmatch(receipt.repository_id) is None
        or not isinstance(receipt.snapshot_id, str)
        or _SNAPSHOT_ID_PATTERN.fullmatch(receipt.snapshot_id) is None
        or not isinstance(receipt.entry_digest, str)
        or _DIGEST_PATTERN.fullmatch(receipt.entry_digest) is None
        or receipt.to_bytes() != encoded
    ):
        raise ValueError
    return receipt


def load_retirement_journal(root: Path) -> tuple[RetirementJournalEntry, ...]:
    events = root / "events"
    if not events.exists():
        return ()
    _require_private_directory(events)
    entries = tuple(_parse_entry(path) for path in sorted(events.glob("*.json")))
    sequences = [entry.sequence for entry in entries]
    if len(sequences) != len(set(sequences)):
        raise RetirementJournalError("retirement journal has a forked sequence")
    ordered = tuple(sorted(entries, key=lambda entry: entry.sequence))
    previous = _ZERO_DIGEST
    for expected, entry in enumerate(ordered, start=1):
        if entry.sequence != expected:
            raise RetirementJournalError("retirement journal has a sequence gap")
        if entry.previous_digest != previous:
            raise RetirementJournalError("retirement journal chain does not join")
        previous = entry.entry_digest
    return ordered


def _new_entry(
    sequence: int,
    previous_digest: str,
    event: ShareRetirementEvent,
) -> RetirementJournalEntry:
    provisional = RetirementJournalEntry(
        sequence=sequence,
        previous_digest=previous_digest,
        entry_digest=_ZERO_DIGEST,
        event=event,
    )
    digest = "sha256:" + sha256(
        _canonical_json(provisional._document(include_digest=False))
    ).hexdigest()
    return RetirementJournalEntry(sequence, previous_digest, digest, event)


def _parse_entry(path: Path) -> RetirementJournalEntry:
    try:
        if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError
        encoded = path.read_bytes()
        document = json.loads(encoded, object_pairs_hook=_unique_object)
        if not isinstance(document, dict) or set(document) != {
            "entry_digest",
            "event",
            "previous_digest",
            "schema_version",
            "sequence",
        }:
            raise ValueError
        if document["schema_version"] != 1:
            raise ValueError
        event = ShareRetirementEvent.from_bytes(_canonical_json(document["event"]))
        entry = RetirementJournalEntry(
            sequence=document["sequence"],
            previous_digest=document["previous_digest"],
            entry_digest=document["entry_digest"],
            event=event,
        )
        if (
            not isinstance(entry.sequence, int)
            or isinstance(entry.sequence, bool)
            or entry.sequence < 1
            or _DIGEST_PATTERN.fullmatch(entry.previous_digest) is None
            or _DIGEST_PATTERN.fullmatch(entry.entry_digest) is None
            or _new_entry(entry.sequence, entry.previous_digest, entry.event).entry_digest
            != entry.entry_digest
            or entry.to_bytes() != encoded
        ):
            raise ValueError
        return entry
    except (OSError, TypeError, ValueError, UnicodeError) as error:
        raise RetirementJournalError("retirement journal entry is invalid") from error


def _head(entries: tuple[RetirementJournalEntry, ...]) -> RetirementJournalHead:
    if not entries:
        return RetirementJournalHead(sequence=0, digest=_ZERO_DIGEST)
    last = entries[-1]
    return RetirementJournalHead(sequence=last.sequence, digest=last.entry_digest)


def _create_only(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _require_private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError("retirement journal directories must be private")


def _require_private_file(path: Path, *, label: str) -> None:
    if (
        not isinstance(path, Path)
        or path.is_symlink()
        or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) & 0o077
    ):
        raise PermissionError(f"{label} must be a private regular file")


def _secret_equality_proof(path: Path, *, deployment_id: str) -> str:
    """Produce an offline equality proof only for high-entropy private material."""

    _require_private_file(path, label="deployment secret")
    secret = path.read_bytes()
    if len(secret) < 32:
        raise ValueError("deployment secrets must contain at least 32 bytes")
    context = f"codemble-share-attestation:v1:{deployment_id}:secret-equality".encode()
    return "sha256:" + hmac_digest(secret, context, "sha256").hex()


def _validate_rest_repository(repository: object) -> None:
    if not isinstance(repository, str) or not repository.startswith("rest:"):
        raise ValueError("restic repository must use the rest-server protocol")
    target = urlsplit(repository.removeprefix("rest:"))
    if (
        target.scheme not in ("http", "https")
        or not target.hostname
        or target.username is not None
        or target.password is not None
        or target.query
        or target.fragment
        or (
            target.scheme == "http"
            and target.hostname not in ("127.0.0.1", "localhost", "::1")
        )
    ):
        raise ValueError("restic rest-server repository must use credential-free HTTPS")


def _validate_private_rest_repository(repository: object, username: str) -> None:
    """Require the username-scoped path enforced by rest-server --private-repos."""

    _validate_rest_repository(repository)
    assert isinstance(repository, str)
    target = urlsplit(repository.removeprefix("rest:"))
    parts = tuple(part for part in target.path.split("/") if part)
    if (
        len(parts) < 2
        or parts[0] != username
        or any(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", part) is None for part in parts)
    ):
        raise ValueError(
            "restic repository path must be scoped to its private-repos username"
        )


def _validate_local_repository(repository: object) -> None:
    if not isinstance(repository, str):
        raise TypeError("operator restic repository must be an absolute local path")
    path = Path(repository)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("operator restic repository must be an absolute local directory")
    _require_private_directory(path)


def _run_command(
    arguments: tuple[str, ...],
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=3_600,
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _format_time(value: datetime) -> str:
    return _aware_utc(value).isoformat().replace("+00:00", "Z")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    return _aware_utc(datetime.fromisoformat(value))


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("share operation time must be timezone-aware")
    return value.astimezone(UTC)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate journal field")
        result[key] = value
    return result


__all__ = [
    "BackupInventoryPort",
    "BackupInventoryReceipt",
    "BackupRetirementReceipt",
    "ChainedRetirementJournal",
    "JournalReplicaBinding",
    "JournalReplicaOperatorConfig",
    "ResticBackupWriter",
    "ResticCommandError",
    "ResticOperator",
    "ResticSnapshot",
    "ResticSnapshotReceipt",
    "ResticWriterTargetConfig",
    "RestoreGuard",
    "RestoreGuardError",
    "RestoreReceipt",
    "RetirementAnchorReceipt",
    "RetirementJournalEntry",
    "RetirementJournalError",
    "RetirementJournalHead",
    "SecurityMetadataRetirementError",
    "SecurityMetadataRetirementGuard",
    "SecurityMetadataRetirementReceipt",
    "ShareBackupManifest",
    "ShareBackupReceipt",
    "ShareDeploymentAttestation",
    "ShareOperationsCycleReceipt",
    "ShareOperationsRunner",
    "ShareOperatorConfig",
    "ShareWriterConfig",
    "create_operator_attestation",
    "create_writer_attestation",
    "load_retirement_journal",
    "materialize_journal_replica",
    "retire_backup_snapshots",
    "validate_role_separation",
]
