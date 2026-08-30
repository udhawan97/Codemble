"""Authenticated encrypted SQLite storage for immutable read-only shares."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
import sqlite3
import stat
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_bytes
from typing import Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from codemble.share.delivery import (
    ShareStorageConflictError,
    ShareStorageIntegrityError,
    StoredShare,
    StoredShareRevocation,
)

DEFAULT_TERMINAL_RETENTION = timedelta(hours=24)

_DATABASE_NAME = "shares.sqlite3"
_SCHEMA_VERSION = 1
_NONCE_BYTES = 12
_IDENTITY_PLAINTEXT = b"codemble-share-storage-key-check:v1"
_IDENTITY_AAD = b"codemble-share-storage-identity:v1"
_HISTORY_KEY_CONTEXT = b"codemble-share-storage-history-key:v1"
_RECORD_KEYS = {
    "artifact",
    "artifact_digest",
    "created_at",
    "delete_binding",
    "delete_fingerprint",
    "delete_lookup",
    "expired_at",
    "expires_at",
    "payload_digest",
    "revoked_at",
    "share_id",
    "view_binding",
    "view_fingerprint",
    "view_lookup",
}
_SCHEMA_OBJECTS = (
    (
        "table",
        "shares",
        "shares",
        (
            "CREATE TABLE shares (\n"
            "    share_id TEXT PRIMARY KEY,\n"
            "    nonce BLOB NOT NULL,\n"
            "    ciphertext BLOB NOT NULL\n"
            ") STRICT"
        ),
    ),
    (
        "table",
        "capability_lookups",
        "capability_lookups",
        (
            "CREATE TABLE capability_lookups (\n"
            "    lookup TEXT PRIMARY KEY,\n"
            "    role TEXT NOT NULL CHECK (role IN ('view', 'delete')),\n"
            "    share_id TEXT REFERENCES shares(share_id) ON DELETE SET NULL\n"
            ") STRICT"
        ),
    ),
    (
        "index",
        "capability_lookup_share",
        "capability_lookups",
        (
            "CREATE INDEX capability_lookup_share\n"
            "    ON capability_lookups(share_id)"
        ),
    ),
    (
        "table",
        "capability_fingerprints",
        "capability_fingerprints",
        (
            "CREATE TABLE capability_fingerprints (\n"
            "    fingerprint TEXT PRIMARY KEY,\n"
            "    share_id TEXT REFERENCES shares(share_id) ON DELETE SET NULL\n"
            ") STRICT"
        ),
    ),
    (
        "index",
        "capability_fingerprint_share",
        "capability_fingerprints",
        (
            "CREATE INDEX capability_fingerprint_share\n"
            "    ON capability_fingerprints(share_id)"
        ),
    ),
    (
        "table",
        "encryption_nonces",
        "encryption_nonces",
        (
            "CREATE TABLE encryption_nonces (\n"
            "    nonce BLOB PRIMARY KEY\n"
            ") STRICT"
        ),
    ),
    (
        "table",
        "storage_identity",
        "storage_identity",
        (
            "CREATE TABLE storage_identity (\n"
            "    identity INTEGER PRIMARY KEY CHECK (identity = 1),\n"
            "    nonce BLOB NOT NULL,\n"
            "    ciphertext BLOB NOT NULL,\n"
            "    history_commitment BLOB NOT NULL\n"
            ") STRICT"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SharePurgeResult:
    """Observable result of one bounded active-store maintenance pass."""

    expired: int
    deleted: int


class EncryptedSQLiteShareStorage:
    """Persistent atomic storage with an externally supplied 256-bit key.

    The record body is AES-GCM ciphertext; share-derived sensitive plaintext is
    limited to the internal share ID, ciphertext size, nonces, and capability
    guards.
    The encryption key is accepted by the interface and never written beside the
    database. Revocation removes artifact bytes in the committing transaction;
    ``purge`` expires unobserved records and unlinks records once their configured
    retention threshold has elapsed after revocation or expiry. Actual removal
    time includes sweep latency and remains operationally gated. Detached
    capability and nonce guards remain until key-store retirement so committed
    authority and encryption nonces cannot be reassigned.
    """

    def __init__(
        self,
        root: Path,
        encryption_key: bytes,
        *,
        terminal_retention: timedelta = DEFAULT_TERMINAL_RETENTION,
        nonce_entropy: Callable[[int], bytes] | None = None,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError("share storage root must be a pathlib.Path")
        if os.name != "posix":
            raise OSError("encrypted share storage requires POSIX permission semantics")
        if not isinstance(encryption_key, bytes) or len(encryption_key) != 32:
            raise ValueError("share storage encryption key must contain exactly 32 bytes")
        if (
            not isinstance(terminal_retention, timedelta)
            or terminal_retention <= timedelta(0)
        ):
            raise ValueError("terminal retention must be a positive duration")
        self._root = root
        self._path = root / _DATABASE_NAME
        self._cipher = AESGCM(encryption_key)
        self._history_key = hmac.digest(
            encryption_key,
            _HISTORY_KEY_CONTEXT,
            "sha256",
        )
        self._terminal_retention = terminal_retention
        self._nonce_entropy = nonce_entropy or token_bytes
        self._prepare_root()
        self._initialize()

    @property
    def database_path(self) -> Path:
        """The active encrypted store path, for operator inspection."""

        return self._path

    @property
    def terminal_retention(self) -> timedelta:
        """Age at which terminal share linkage becomes eligible for unlinking."""

        return self._terminal_retention

    def create(self, record: StoredShare) -> None:
        """Atomically reserve all identities and write one encrypted record."""

        if not isinstance(record, StoredShare) or record.artifact is None:
            raise ShareStorageIntegrityError("persistent storage requires an active share")
        nonce = self._reserve_nonce()
        ciphertext = self._seal(record, nonce)
        try:
            with self._transaction() as connection:
                connection.execute(
                    "INSERT INTO shares (share_id, nonce, ciphertext) VALUES (?, ?, ?)",
                    (record.share_id, nonce, ciphertext),
                )
                connection.executemany(
                    "INSERT INTO capability_lookups (lookup, role, share_id) "
                    "VALUES (?, ?, ?)",
                    (
                        (record.view_lookup, "view", record.share_id),
                        (record.delete_lookup, "delete", record.share_id),
                    ),
                )
                connection.executemany(
                    "INSERT INTO capability_fingerprints (fingerprint, share_id) "
                    "VALUES (?, ?)",
                    (
                        (record.view_fingerprint, record.share_id),
                        (record.delete_fingerprint, record.share_id),
                    ),
                )
                self._write_history_commitment(connection)
        except sqlite3.IntegrityError as error:
            raise ShareStorageConflictError(
                "share identities and capability lookups are create-only"
            ) from error

    def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
        """Return active bytes or atomically persist observed expiry."""

        checked_now = _aware_utc(now)
        with self._read_transaction() as connection:
            record = self._load_by_lookup(connection, view_lookup, "view")
        if (
            record is None
            or record.revoked_at is not None
            or record.expired_at is not None
            or record.artifact is None
        ):
            return None
        if checked_now < record.expires_at:
            return record
        nonce = self._reserve_nonce()
        with self._transaction() as connection:
            record = self._load_by_lookup(connection, view_lookup, "view")
            if (
                record is None
                or record.revoked_at is not None
                or record.expired_at is not None
                or record.artifact is None
            ):
                return None
            if checked_now < record.expires_at:
                return record
            self._replace(
                connection,
                replace(record, artifact=None, expired_at=record.expires_at),
                nonce,
            )
            return None

    def revoke(
        self,
        delete_lookup: str,
        now: datetime,
    ) -> StoredShareRevocation | None:
        """Atomically revoke serving authority and replace active ciphertext."""

        checked_now = _aware_utc(now)
        with self._read_transaction() as connection:
            record = self._load_by_lookup(connection, delete_lookup, "delete")
        if record is None or record.expired_at is not None:
            return None
        if record.revoked_at is not None:
            if checked_now >= record.expires_at:
                return None
            return StoredShareRevocation(record, already_revoked=True)
        if checked_now < record.created_at:
            return None
        nonce = self._reserve_nonce()
        with self._transaction() as connection:
            record = self._load_by_lookup(connection, delete_lookup, "delete")
            if record is None or record.expired_at is not None:
                return None
            if record.revoked_at is not None:
                if checked_now >= record.expires_at:
                    return None
                return StoredShareRevocation(record, already_revoked=True)
            if checked_now < record.created_at:
                return None
            if checked_now >= record.expires_at:
                self._replace(
                    connection,
                    replace(record, artifact=None, expired_at=record.expires_at),
                    nonce,
                )
                return None
            revoked = replace(record, artifact=None, revoked_at=checked_now)
            self._replace(connection, revoked, nonce)
            return StoredShareRevocation(revoked, already_revoked=False)

    def purge(self, now: datetime) -> SharePurgeResult:
        """Expire unobserved shares and unlink records after the retention threshold."""

        checked_now = _aware_utc(now)
        expired = 0
        deleted = 0
        with self._read_transaction() as connection:
            rows = connection.execute(
                "SELECT share_id, nonce, ciphertext FROM shares ORDER BY share_id"
            ).fetchall()
            expiry_share_ids = {
                record.share_id
                for row in rows
                if (
                    (record := self._open(row["share_id"], row["nonce"], row["ciphertext"]))
                    .artifact
                    is not None
                    and checked_now >= record.expires_at
                )
            }
        expiry_nonces = {
            share_id: self._reserve_nonce() for share_id in expiry_share_ids
        }
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT share_id, nonce, ciphertext FROM shares ORDER BY share_id"
            ).fetchall()
            for row in rows:
                record = self._open(row["share_id"], row["nonce"], row["ciphertext"])
                self._authenticate_indexes(connection, record)
                if record.artifact is not None and checked_now >= record.expires_at:
                    record = replace(
                        record,
                        artifact=None,
                        expired_at=record.expires_at,
                    )
                    nonce = expiry_nonces.get(record.share_id)
                    if nonce is None:
                        continue
                    self._replace(connection, record, nonce)
                    expired += 1
                terminal_at = record.revoked_at or record.expired_at
                if (
                    terminal_at is not None
                    and checked_now >= terminal_at + self._terminal_retention
                ):
                    connection.execute(
                        "DELETE FROM shares WHERE share_id = ?",
                        (record.share_id,),
                    )
                    deleted += 1
            self._write_history_commitment(connection)
        return SharePurgeResult(expired=expired, deleted=deleted)

    def _prepare_root(self) -> None:
        if self._root.exists():
            if self._root.is_symlink() or not self._root.is_dir():
                raise ValueError("share storage root must be a private directory")
            _require_private_mode(self._root, directory=True)
        else:
            self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self._root.is_symlink() or not self._root.is_dir():
                raise ValueError("share storage root must be a private directory")
            os.chmod(self._root, 0o700)
        if self._path.exists():
            if self._path.is_symlink() or not self._path.is_file():
                raise ValueError("share storage database must be a regular file")
            _require_private_mode(self._path, directory=False)
        else:
            self._path.touch(mode=0o600)
            os.chmod(self._path, 0o600)

    def _initialize(self) -> None:
        with self._transaction(authenticate=False) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            objects = self._schema_objects(connection)
            pristine = version == 0 and not objects
            if pristine:
                for _kind, _name, _table, statement in _SCHEMA_OBJECTS:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                nonce = token_bytes(_NONCE_BYTES)
                connection.execute(
                    "INSERT INTO encryption_nonces (nonce) VALUES (?)",
                    (nonce,),
                )
                ciphertext = self._cipher.encrypt(
                    nonce,
                    _IDENTITY_PLAINTEXT,
                    _IDENTITY_AAD,
                )
                connection.execute(
                    "INSERT INTO storage_identity "
                    "(identity, nonce, ciphertext, history_commitment) "
                    "VALUES (1, ?, ?, ?)",
                    (nonce, ciphertext, self._history_commitment(connection)),
                )
            else:
                self._authenticate_storage(connection)
        os.chmod(self._path, 0o600)
        with self._read_transaction():
            pass

    def _connect(self, *, configure: bool = True) -> sqlite3.Connection:
        _require_private_mode(self._root, directory=True)
        _require_private_mode(self._path, directory=False)
        connection = sqlite3.connect(self._path, isolation_level=None, timeout=5)
        connection.row_factory = sqlite3.Row
        if not configure:
            return connection
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA secure_delete = ON")
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        secure_delete = connection.execute("PRAGMA secure_delete").fetchone()[0]
        if str(journal_mode).lower() != "delete" or secure_delete != 1:
            connection.close()
            raise ShareStorageIntegrityError("secure SQLite deletion is unavailable")
        return connection

    def _transaction(self, *, authenticate: bool = True):
        return _ImmediateTransaction(
            self._connect(configure=authenticate),
            self._authenticate_storage if authenticate else None,
        )

    def _read_transaction(self):
        return _ReadTransaction(self._connect(), self._authenticate_storage)

    def _schema_objects(
        self,
        connection: sqlite3.Connection,
    ) -> dict[tuple[str, str, str], str]:
        return {
            (row["type"], row["name"], row["tbl_name"]): row["sql"]
            for row in connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                "WHERE name NOT LIKE 'sqlite_%'"
            )
        }

    def _authenticate_storage(self, connection: sqlite3.Connection) -> None:
        expected = {
            (kind, name, table): statement
            for kind, name, table, statement in _SCHEMA_OBJECTS
        }
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != _SCHEMA_VERSION or self._schema_objects(connection) != expected:
            raise ShareStorageIntegrityError(
                "share storage schema does not match its authenticated contract"
            )
        identities = connection.execute(
            "SELECT nonce, ciphertext, history_commitment FROM storage_identity"
        ).fetchall()
        if len(identities) != 1:
            raise ShareStorageIntegrityError(
                "share storage is missing its authenticated identity"
            )
        identity = identities[0]
        self._authenticate_identity(identity)
        try:
            history_matches = hmac.compare_digest(
                identity["history_commitment"],
                self._history_commitment(connection),
            )
        except TypeError as error:
            raise ShareStorageIntegrityError(
                "share storage history failed authentication"
            ) from error
        if not history_matches:
            raise ShareStorageIntegrityError(
                "share storage history failed authentication"
            )

    def _authenticate_identity(self, identity: sqlite3.Row) -> None:
        try:
            plaintext = self._cipher.decrypt(
                identity["nonce"],
                identity["ciphertext"],
                _IDENTITY_AAD,
            )
        except (InvalidTag, KeyError, TypeError, ValueError) as error:
            raise ShareStorageIntegrityError(
                "share storage key does not authenticate this database"
            ) from error
        if plaintext != _IDENTITY_PLAINTEXT:
            raise ShareStorageIntegrityError("share storage identity failed authentication")

    def _history_commitment(self, connection: sqlite3.Connection) -> bytes:
        document = {
            "capability_fingerprints": [
                [row["fingerprint"], row["share_id"]]
                for row in connection.execute(
                    "SELECT fingerprint, share_id FROM capability_fingerprints "
                    "ORDER BY fingerprint"
                )
            ],
            "capability_lookups": [
                [row["lookup"], row["role"], row["share_id"]]
                for row in connection.execute(
                    "SELECT lookup, role, share_id FROM capability_lookups "
                    "ORDER BY lookup"
                )
            ],
            "encryption_nonces": [
                row["nonce"].hex()
                for row in connection.execute(
                    "SELECT nonce FROM encryption_nonces ORDER BY nonce"
                )
            ],
        }
        encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
        return hmac.digest(self._history_key, encoded, "sha256")

    def _write_history_commitment(self, connection: sqlite3.Connection) -> None:
        cursor = connection.execute(
            "UPDATE storage_identity SET history_commitment = ? WHERE identity = 1",
            (self._history_commitment(connection),),
        )
        if cursor.rowcount != 1:
            raise ShareStorageIntegrityError(
                "share storage identity disappeared during history update"
            )

    def _load_by_lookup(
        self,
        connection: sqlite3.Connection,
        lookup: str,
        role: Literal["view", "delete"],
    ) -> StoredShare | None:
        row = connection.execute(
            "SELECT shares.share_id, shares.nonce, shares.ciphertext "
            "FROM capability_lookups "
            "JOIN shares USING (share_id) "
            "WHERE capability_lookups.lookup = ? AND capability_lookups.role = ?",
            (lookup, role),
        ).fetchone()
        if row is None:
            return None
        record = self._open(row["share_id"], row["nonce"], row["ciphertext"])
        if getattr(record, f"{role}_lookup") != lookup:
            raise ShareStorageIntegrityError("share capability index failed authentication")
        self._authenticate_indexes(connection, record)
        return record

    def _authenticate_indexes(
        self,
        connection: sqlite3.Connection,
        record: StoredShare,
    ) -> None:
        lookups = {
            (row["role"], row["lookup"])
            for row in connection.execute(
                "SELECT role, lookup FROM capability_lookups WHERE share_id = ?",
                (record.share_id,),
            )
        }
        fingerprints = {
            row["fingerprint"]
            for row in connection.execute(
                "SELECT fingerprint FROM capability_fingerprints WHERE share_id = ?",
                (record.share_id,),
            )
        }
        if lookups != {
            ("view", record.view_lookup),
            ("delete", record.delete_lookup),
        } or fingerprints != {
            record.view_fingerprint,
            record.delete_fingerprint,
        }:
            raise ShareStorageIntegrityError("share capability indexes failed authentication")

    def _replace(
        self,
        connection: sqlite3.Connection,
        record: StoredShare,
        nonce: bytes,
    ) -> None:
        ciphertext = self._seal(record, nonce)
        cursor = connection.execute(
            "UPDATE shares SET nonce = ?, ciphertext = ? WHERE share_id = ?",
            (nonce, ciphertext, record.share_id),
        )
        if cursor.rowcount != 1:
            raise ShareStorageIntegrityError("share disappeared during atomic storage update")

    def _reserve_nonce(self) -> bytes:
        for _ in range(4):
            nonce = self._nonce_entropy(_NONCE_BYTES)
            if not isinstance(nonce, bytes) or len(nonce) != _NONCE_BYTES:
                raise RuntimeError("share storage nonce entropy must contain exactly 12 bytes")
            with self._transaction() as connection:
                reserved = connection.execute(
                    "INSERT OR IGNORE INTO encryption_nonces (nonce) VALUES (?)",
                    (nonce,),
                )
                if reserved.rowcount == 1:
                    self._write_history_commitment(connection)
            if reserved.rowcount == 1:
                return nonce
        raise ShareStorageIntegrityError("share storage refused repeated encryption nonces")

    def _seal(self, record: StoredShare, nonce: bytes) -> bytes:
        plaintext = _encode_record(record)
        return self._cipher.encrypt(nonce, plaintext, _aad(record.share_id))

    def _open(self, share_id: str, nonce: bytes, ciphertext: bytes) -> StoredShare:
        try:
            if not isinstance(nonce, bytes) or len(nonce) != _NONCE_BYTES:
                raise ValueError
            plaintext = self._cipher.decrypt(nonce, ciphertext, _aad(share_id))
            record = _decode_record(plaintext)
            if record.share_id != share_id:
                raise ValueError
            return record
        except (
            InvalidTag,
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            binascii.Error,
        ) as error:
            raise ShareStorageIntegrityError(
                "persistent share record failed authenticated decryption"
            ) from error


class _ImmediateTransaction:
    def __init__(
        self,
        connection: sqlite3.Connection,
        authenticator: Callable[[sqlite3.Connection], None] | None,
    ) -> None:
        self._connection = connection
        self._authenticator = authenticator

    def __enter__(self) -> sqlite3.Connection:
        try:
            self._connection.execute("BEGIN IMMEDIATE")
        except Exception:
            self._connection.close()
            raise
        if self._authenticator is not None:
            try:
                self._authenticator(self._connection)
            except sqlite3.DatabaseError as error:
                self._connection.rollback()
                self._connection.close()
                raise ShareStorageIntegrityError(
                    "share storage is missing its authenticated schema"
                ) from error
            except Exception:
                self._connection.rollback()
                self._connection.close()
                raise
        return self._connection

    def __exit__(self, error_type, error, traceback) -> bool:
        try:
            if error_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
        return False


class _ReadTransaction:
    def __init__(
        self,
        connection: sqlite3.Connection,
        authenticator: Callable[[sqlite3.Connection], None],
    ) -> None:
        self._connection = connection
        self._authenticator = authenticator

    def __enter__(self) -> sqlite3.Connection:
        try:
            self._connection.execute("BEGIN")
        except Exception:
            self._connection.close()
            raise
        try:
            self._authenticator(self._connection)
        except sqlite3.DatabaseError as error:
            self._connection.rollback()
            self._connection.close()
            raise ShareStorageIntegrityError(
                "share storage is missing its authenticated schema"
            ) from error
        except Exception:
            self._connection.rollback()
            self._connection.close()
            raise
        return self._connection

    def __exit__(self, error_type, error, traceback) -> bool:
        try:
            self._connection.rollback()
        finally:
            self._connection.close()
        return False


def _encode_record(record: StoredShare) -> bytes:
    document = asdict(record)
    document["artifact"] = (
        None if record.artifact is None else base64.b64encode(record.artifact).decode("ascii")
    )
    for field_name in ("created_at", "expires_at", "revoked_at", "expired_at"):
        value = getattr(record, field_name)
        document[field_name] = None if value is None else _format_time(value)
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode_record(encoded: bytes) -> StoredShare:
    document = json.loads(encoded)
    if not isinstance(document, dict) or set(document) != _RECORD_KEYS:
        raise ValueError
    artifact = document["artifact"]
    if artifact is not None:
        artifact = base64.b64decode(artifact, validate=True)
    return StoredShare(
        share_id=document["share_id"],
        view_lookup=document["view_lookup"],
        delete_lookup=document["delete_lookup"],
        view_fingerprint=document["view_fingerprint"],
        delete_fingerprint=document["delete_fingerprint"],
        view_binding=document["view_binding"],
        delete_binding=document["delete_binding"],
        artifact=artifact,
        artifact_digest=document["artifact_digest"],
        payload_digest=document["payload_digest"],
        created_at=_parse_time(document["created_at"]),
        expires_at=_parse_time(document["expires_at"]),
        revoked_at=_parse_optional_time(document["revoked_at"]),
        expired_at=_parse_optional_time(document["expired_at"]),
    )


def _aad(share_id: str) -> bytes:
    return f"codemble-share-storage:v{_SCHEMA_VERSION}:{share_id}".encode("ascii")


def _format_time(value: datetime) -> str:
    return _aware_utc(value).isoformat().replace("+00:00", "Z")


def _parse_optional_time(value: object) -> datetime | None:
    return None if value is None else _parse_time(value)


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError
    parsed = datetime.fromisoformat(value)
    return _aware_utc(parsed)


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("share storage clock must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("share storage clock must be timezone-aware")
    return value.astimezone(UTC)


def _require_private_mode(path: Path, *, directory: bool) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        kind = "directory" if directory else "database"
        raise PermissionError(f"share storage {kind} must not permit group or other access")
