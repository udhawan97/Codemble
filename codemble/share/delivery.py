"""Issue least-authority capabilities for one immutable share artifact."""

from __future__ import annotations

import base64
import hmac
import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_bytes
from typing import Literal, Protocol

import rfc8785

from codemble.share.artifact import MAX_SHARE_LIFETIME, ShareArtifact
from codemble.share.interpretation import (
    InvalidShareArtifactError,
    ShareArtifactFacts,
    interpret_share_artifact,
)

_CAPABILITY_BYTES = 32
_CAPABILITY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHARE_ID_PATTERN = re.compile(r"^s[0-9a-f]{32}$")
_LIFECYCLE_OPERATIONS = frozenset(("create", "view", "revoke"))
_LIFECYCLE_OUTCOMES = frozenset(
    (
        "created",
        "viewed",
        "revoked",
        "already_revoked",
        "not_found",
        "rejected",
        "integrity_error",
    )
)


class UnknownShareCapabilityError(LookupError):
    """A capability is invalid, expired, or no longer grants authority."""


class ShareRevocationConfirmationError(ValueError):
    """Revocation requires an explicit affirmative confirmation."""


class ShareStorageConflictError(RuntimeError):
    """Immutable storage already owns one of the candidate identities."""


class ShareStorageIntegrityError(RuntimeError):
    """Stored bytes or metadata no longer match the validated artifact."""


@dataclass(frozen=True, slots=True)
class ShareLifecycleEvent:
    """One token-free, closed-schema lifecycle record."""

    share_id: str | None
    occurred_at: datetime
    operation: Literal["create", "view", "revoke"]
    outcome: Literal[
        "created",
        "viewed",
        "revoked",
        "already_revoked",
        "not_found",
        "rejected",
        "integrity_error",
    ]


class ShareLifecycleLogPort(Protocol):
    """Append only allowlisted lifecycle facts without request targets or tokens."""

    def record(self, event: ShareLifecycleEvent) -> None:
        """Best-effort one event; never accept free-form fields or control lifecycle."""


class StructuredShareLifecycleLog:
    """Standard-library JSON logger whose records cannot accept bearer secrets."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("codemble.share.lifecycle")

    def record(self, event: ShareLifecycleEvent) -> None:
        occurred_at = _validate_lifecycle_event(event)
        self._logger.info(
            json.dumps(
                {
                    "operation": event.operation,
                    "outcome": event.outcome,
                    "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
                    "share_id": event.share_id,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )


class InMemoryShareLifecycleLog:
    """Thread-safe recording adapter for interface-level lifecycle tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[ShareLifecycleEvent] = []

    def record(self, event: ShareLifecycleEvent) -> None:
        _validate_lifecycle_event(event)
        with self._lock:
            self._events.append(event)

    @property
    def events(self) -> tuple[ShareLifecycleEvent, ...]:
        with self._lock:
            return tuple(self._events)


@dataclass(frozen=True, slots=True)
class ShareGrant:
    """The two independent capabilities shown once to the publisher."""

    view_capability: str = field(repr=False)
    delete_capability: str = field(repr=False)
    expires_at: datetime
    payload_digest: str


@dataclass(frozen=True, slots=True)
class ShareRevocation:
    """A retry-safe confirmation that view authority has been revoked."""

    status: Literal["revoked", "already_revoked"]
    expires_at: datetime
    payload_digest: str


@dataclass(frozen=True, slots=True)
class StoredShare:
    """Provider-neutral immutable record; capability plaintext never enters it."""

    share_id: str
    view_lookup: str = field(repr=False)
    delete_lookup: str = field(repr=False)
    view_fingerprint: str = field(repr=False)
    delete_fingerprint: str = field(repr=False)
    view_binding: str = field(repr=False)
    delete_binding: str = field(repr=False)
    artifact: bytes | None = field(repr=False)
    artifact_digest: str
    payload_digest: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    expired_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class StoredShareRevocation:
    """Atomic storage result for first and repeated revocation attempts."""

    share: StoredShare
    already_revoked: bool


class ShareStoragePort(Protocol):
    """Atomic create/read/revoke seam for a future authenticated adapter."""

    def create(self, record: StoredShare) -> None:
        """Refuse identity, lookup, or fingerprint reuse across roles and history."""

    def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
        """Return only active bytes; irreversibly tombstone observed expiry."""

    def revoke(
        self,
        delete_lookup: str,
        now: datetime,
    ) -> StoredShareRevocation | None:
        """Atomically revoke view authority and remove active artifact bytes."""


class InMemoryShareStorage:
    """Reference adapter with atomic process-local capability indexes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._shares: dict[str, StoredShare] = {}
        self._view_index: dict[str, str] = {}
        self._delete_index: dict[str, str] = {}
        self._capability_fingerprints: set[str] = set()

    def create(self, record: StoredShare) -> None:
        with self._lock:
            if (
                record.share_id in self._shares
                or record.view_lookup in self._view_index
                or record.delete_lookup in self._delete_index
                or record.view_fingerprint in self._capability_fingerprints
                or record.delete_fingerprint in self._capability_fingerprints
                or record.view_fingerprint == record.delete_fingerprint
            ):
                raise ShareStorageConflictError(
                    "share identities and capability lookups are create-only"
                )
            self._shares[record.share_id] = record
            self._view_index[record.view_lookup] = record.share_id
            self._delete_index[record.delete_lookup] = record.share_id
            self._capability_fingerprints.update(
                (record.view_fingerprint, record.delete_fingerprint)
            )

    def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
        with self._lock:
            share_id = self._view_index.get(view_lookup)
            record = self._shares.get(share_id) if share_id is not None else None
            if (
                record is None
                or record.revoked_at is not None
                or record.expired_at is not None
                or record.artifact is None
            ):
                return None
            if now >= record.expires_at:
                self._shares[record.share_id] = replace(
                    record,
                    artifact=None,
                    expired_at=record.expires_at,
                )
                return None
            return record

    def revoke(
        self,
        delete_lookup: str,
        now: datetime,
    ) -> StoredShareRevocation | None:
        with self._lock:
            share_id = self._delete_index.get(delete_lookup)
            record = self._shares.get(share_id) if share_id is not None else None
            if record is None or record.expired_at is not None:
                return None
            if record.revoked_at is not None:
                if now >= record.expires_at:
                    return None
                return StoredShareRevocation(record, already_revoked=True)
            if now < record.created_at:
                return None
            if now >= record.expires_at:
                self._shares[record.share_id] = replace(
                    record,
                    artifact=None,
                    expired_at=record.expires_at,
                )
                return None
            revoked = replace(record, artifact=None, revoked_at=now)
            self._shares[record.share_id] = revoked
            return StoredShareRevocation(revoked, already_revoked=False)


class ShareDelivery:
    """Own capability issuance, validation, expiry, viewing, and revocation."""

    def __init__(
        self,
        storage: ShareStoragePort,
        lifecycle_log: ShareLifecycleLogPort,
        *,
        clock: Callable[[], datetime] | None = None,
        entropy: Callable[[int], bytes] | None = None,
    ) -> None:
        self._storage = storage
        self._lifecycle_log = lifecycle_log
        self._clock = clock or (lambda: datetime.now(UTC))
        self._entropy = entropy or token_bytes

    def create(self, artifact: ShareArtifact) -> ShareGrant:
        """Validate and store one live artifact, returning independent capabilities."""

        if not isinstance(artifact, ShareArtifact):
            raise TypeError("artifact must be a ShareArtifact")
        encoded = artifact.to_bytes()
        metadata = _validated_artifact(encoded)
        now = self._now()
        if now < metadata.created_at:
            raise ValueError("share artifact creation time is in the future")
        if now >= metadata.expires_at:
            raise ValueError("share artifact is already expired")
        view_secret = self._secret()
        delete_secret = self._secret()
        if view_secret == delete_secret:
            raise RuntimeError("view and deletion capabilities must use independent entropy")
        view_capability = _encode_capability(view_secret)
        delete_capability = _encode_capability(delete_secret)
        view_lookup = _lookup("view", view_secret)
        delete_lookup = _lookup("delete", delete_secret)
        view_fingerprint = _fingerprint(view_secret)
        delete_fingerprint = _fingerprint(delete_secret)
        share_id = _share_id(view_lookup, delete_lookup)
        record = StoredShare(
            share_id=share_id,
            view_lookup=view_lookup,
            delete_lookup=delete_lookup,
            view_fingerprint=view_fingerprint,
            delete_fingerprint=delete_fingerprint,
            view_binding="",
            delete_binding="",
            artifact=encoded,
            artifact_digest=metadata.artifact_digest,
            payload_digest=metadata.payload_digest,
            created_at=metadata.created_at,
            expires_at=metadata.expires_at,
        )
        delete_binding = _record_binding("delete", delete_secret, record)
        record = replace(
            record,
            delete_binding=delete_binding,
            view_binding=_record_binding(
                "view",
                view_secret,
                replace(record, delete_binding=delete_binding),
            ),
        )
        self._storage.create(record)
        self._record("create", "created", share_id=share_id, occurred_at=now)
        return ShareGrant(
            view_capability=view_capability,
            delete_capability=delete_capability,
            expires_at=metadata.expires_at,
            payload_digest=metadata.payload_digest,
        )

    def view(self, view_capability: str) -> bytes:
        """Return one exact immutable artifact without changing its lifecycle."""

        now = self._now()
        try:
            secret = _decode_capability(view_capability)
        except UnknownShareCapabilityError:
            self._record("view", "not_found", share_id=None, occurred_at=now)
            raise
        lookup = _lookup("view", secret)
        record = self._storage.read(lookup, now)
        if record is None:
            self._record("view", "not_found", share_id=None, occurred_at=now)
            raise UnknownShareCapabilityError("Share not found.")
        try:
            metadata = _validate_stored_share(
                record,
                lookup=lookup,
                secret=secret,
                now=now,
            )
        except ShareStorageIntegrityError:
            self._record(
                "view",
                "integrity_error",
                share_id=None,
                occurred_at=now,
            )
            raise
        assert record.artifact is not None
        if metadata.payload_digest != record.payload_digest:
            self._record(
                "view",
                "integrity_error",
                share_id=record.share_id,
                occurred_at=now,
            )
            raise ShareStorageIntegrityError("stored share metadata does not match its bytes")
        self._record("view", "viewed", share_id=record.share_id, occurred_at=now)
        return record.artifact

    def revoke(
        self,
        delete_capability: str,
        *,
        confirmed: bool,
    ) -> ShareRevocation:
        """Atomically revoke view access; repeated confirmed calls are safe."""

        now = self._now()
        if confirmed is not True:
            self._record("revoke", "rejected", share_id=None, occurred_at=now)
            raise ShareRevocationConfirmationError("share deletion requires explicit confirmation")
        try:
            secret = _decode_capability(delete_capability)
        except UnknownShareCapabilityError:
            self._record("revoke", "not_found", share_id=None, occurred_at=now)
            raise
        lookup = _lookup("delete", secret)
        result = self._storage.revoke(lookup, now)
        if result is None:
            self._record("revoke", "not_found", share_id=None, occurred_at=now)
            raise UnknownShareCapabilityError("Share not found.")
        record = result.share
        try:
            _validate_revoked_share(
                record,
                lookup=lookup,
                secret=secret,
                now=now,
            )
        except ShareStorageIntegrityError:
            self._record(
                "revoke",
                "integrity_error",
                share_id=None,
                occurred_at=now,
            )
            raise
        outcome: Literal["already_revoked", "revoked"] = (
            "already_revoked" if result.already_revoked else "revoked"
        )
        self._record("revoke", outcome, share_id=record.share_id, occurred_at=now)
        return ShareRevocation(
            status=outcome,
            expires_at=record.expires_at,
            payload_digest=record.payload_digest,
        )

    def _record(
        self,
        operation: Literal["create", "view", "revoke"],
        outcome: Literal[
            "created",
            "viewed",
            "revoked",
            "already_revoked",
            "not_found",
            "rejected",
            "integrity_error",
        ],
        *,
        share_id: str | None,
        occurred_at: datetime,
    ) -> None:
        try:
            self._lifecycle_log.record(
                ShareLifecycleEvent(
                    share_id=share_id,
                    occurred_at=occurred_at,
                    operation=operation,
                    outcome=outcome,
                )
            )
        except Exception:  # noqa: BLE001 - adapters are an external failure boundary
            # Telemetry is deliberately non-authoritative: a failed sink must
            # never strand active bytes after create or alter view/revoke truth.
            try:
                logging.getLogger("codemble.share.lifecycle.failure").error(
                    "Share lifecycle event could not be recorded"
                )
            except Exception as fallback_error:  # noqa: BLE001
                _ = fallback_error

    def _secret(self) -> bytes:
        value = self._entropy(_CAPABILITY_BYTES)
        if not isinstance(value, bytes) or len(value) != _CAPABILITY_BYTES:
            raise RuntimeError("share capability entropy must contain exactly 32 bytes")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise TypeError("share delivery clock must return a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("share delivery clock must return a timezone-aware datetime")
        return value.astimezone(UTC)


def _validate_stored_share(
    record: StoredShare,
    *,
    lookup: str,
    secret: bytes,
    now: datetime,
) -> ShareArtifactFacts:
    if not isinstance(record, StoredShare):
        raise ShareStorageIntegrityError("storage returned an invalid share record")
    if (
        _SHARE_ID_PATTERN.fullmatch(record.share_id) is None
        or record.view_lookup != lookup
        or record.view_fingerprint != _fingerprint(secret)
        or not _valid_lookup(record.view_lookup)
        or not _valid_lookup(record.delete_lookup)
        or not _valid_lookup(record.view_fingerprint)
        or not _valid_lookup(record.delete_fingerprint)
        or not _valid_lookup(record.view_binding)
        or not _valid_lookup(record.delete_binding)
        or record.view_lookup == record.delete_lookup
        or record.view_fingerprint == record.delete_fingerprint
        or record.share_id != _share_id(record.view_lookup, record.delete_lookup)
        or record.revoked_at is not None
        or record.expired_at is not None
        or record.artifact is None
    ):
        raise ShareStorageIntegrityError("storage returned an unauthorized share record")
    metadata = _validated_artifact(record.artifact)
    if (
        metadata.artifact_digest != record.artifact_digest
        or metadata.payload_digest != record.payload_digest
        or metadata.created_at != record.created_at
        or metadata.expires_at != record.expires_at
        or now >= metadata.expires_at
        or not hmac.compare_digest(
            record.view_binding,
            _record_binding("view", secret, record),
        )
    ):
        raise ShareStorageIntegrityError("stored share metadata does not match its bytes")
    return metadata


def _validate_revoked_share(
    record: StoredShare,
    *,
    lookup: str,
    secret: bytes,
    now: datetime,
) -> None:
    if (
        not isinstance(record, StoredShare)
        or _SHARE_ID_PATTERN.fullmatch(record.share_id) is None
        or record.delete_lookup != lookup
        or record.delete_fingerprint != _fingerprint(secret)
        or not _valid_lookup(record.view_lookup)
        or not _valid_lookup(record.delete_lookup)
        or not _valid_lookup(record.view_fingerprint)
        or not _valid_lookup(record.delete_fingerprint)
        or not _valid_lookup(record.view_binding)
        or not _valid_lookup(record.delete_binding)
        or record.view_fingerprint == record.delete_fingerprint
        or record.share_id != _share_id(record.view_lookup, record.delete_lookup)
        or record.artifact is not None
        or not _aware_datetime(record.created_at)
        or not _aware_datetime(record.expires_at)
        or not _aware_datetime(record.revoked_at)
        or record.expired_at is not None
        or record.expires_at <= record.created_at
        or record.expires_at - record.created_at > MAX_SHARE_LIFETIME
        or record.revoked_at < record.created_at
        or record.revoked_at >= record.expires_at
        or now >= record.expires_at
        or _DIGEST_PATTERN.fullmatch(record.artifact_digest) is None
        or _DIGEST_PATTERN.fullmatch(record.payload_digest) is None
        or not hmac.compare_digest(
            record.delete_binding,
            _record_binding("delete", secret, record),
        )
    ):
        raise ShareStorageIntegrityError("storage returned an invalid revocation record")


def _validated_artifact(encoded: bytes) -> ShareArtifactFacts:
    try:
        return interpret_share_artifact(encoded).facts
    except InvalidShareArtifactError as error:
        raise ShareStorageIntegrityError(
            "stored share is outside the closed immutable schema"
        ) from error

def _validate_lifecycle_event(event: ShareLifecycleEvent) -> datetime:
    if not isinstance(event, ShareLifecycleEvent):
        raise TypeError("share lifecycle log accepts ShareLifecycleEvent only")
    if event.operation not in _LIFECYCLE_OPERATIONS or event.outcome not in _LIFECYCLE_OUTCOMES:
        raise ValueError("share lifecycle event has an invalid operation or outcome")
    if event.share_id is not None and _SHARE_ID_PATTERN.fullmatch(event.share_id) is None:
        raise ValueError("share lifecycle event has an invalid internal share ID")
    if (
        not isinstance(event.occurred_at, datetime)
        or event.occurred_at.tzinfo is None
        or event.occurred_at.utcoffset() is None
    ):
        raise ValueError("share lifecycle event time must be timezone-aware")
    return event.occurred_at.astimezone(UTC)


def _encode_capability(secret: bytes) -> str:
    return base64.urlsafe_b64encode(secret).rstrip(b"=").decode("ascii")


def _decode_capability(value: object) -> bytes:
    if not isinstance(value, str) or _CAPABILITY_PATTERN.fullmatch(value) is None:
        raise UnknownShareCapabilityError("Share not found.")
    try:
        decoded = base64.b64decode(value + "=", altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise UnknownShareCapabilityError("Share not found.") from error
    if len(decoded) != _CAPABILITY_BYTES or _encode_capability(decoded) != value:
        raise UnknownShareCapabilityError("Share not found.")
    return decoded


def _lookup(kind: str, secret: bytes) -> str:
    return sha256(f"codemble-share-{kind}-capability-v1\0".encode() + secret).hexdigest()


def _share_id(view_lookup: str, delete_lookup: str) -> str:
    return (
        "s"
        + sha256(
            b"codemble-share-id-v1\0" + bytes.fromhex(view_lookup) + bytes.fromhex(delete_lookup)
        ).hexdigest()[:32]
    )


def _record_binding(kind: Literal["view", "delete"], secret: bytes, record: StoredShare) -> str:
    document: dict[str, object] = {
        "share_id": record.share_id,
        "view_lookup": record.view_lookup,
        "delete_lookup": record.delete_lookup,
        "view_fingerprint": record.view_fingerprint,
        "delete_fingerprint": record.delete_fingerprint,
        "artifact_digest": record.artifact_digest,
        "payload_digest": record.payload_digest,
        "created_at": record.created_at.astimezone(UTC).isoformat(),
        "expires_at": record.expires_at.astimezone(UTC).isoformat(),
    }
    if kind == "view":
        document["delete_binding"] = record.delete_binding
    return hmac.new(
        secret,
        f"codemble-share-{kind}-record-binding-v1\0".encode() + rfc8785.dumps(document),
        sha256,
    ).hexdigest()


def _fingerprint(secret: bytes) -> str:
    return sha256(b"codemble-share-capability-fingerprint-v1\0" + secret).hexdigest()


def _valid_lookup(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


__all__ = [
    "InMemoryShareStorage",
    "ShareDelivery",
    "ShareGrant",
    "ShareRevocation",
    "ShareRevocationConfirmationError",
    "ShareStorageConflictError",
    "ShareStorageIntegrityError",
    "ShareStoragePort",
    "StoredShare",
    "StoredShareRevocation",
    "UnknownShareCapabilityError",
]
