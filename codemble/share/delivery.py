"""Issue least-authority capabilities for one immutable share artifact."""

from __future__ import annotations

import base64
import hmac
import json
import logging
import math
import re
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_bytes
from typing import Literal, Protocol

import rfc8785

from codemble.share.artifact import (
    _DECLARED_EXCLUSIONS,
    _EDGE_KINDS,
    _LANGUAGES,
    _NODE_KINDS,
    _ORBIT_KINDS,
    _SUPPORTED_GRAPH_SCHEMA_VERSION,
    MAX_LABEL_UTF8_BYTES,
    MAX_RENDER_COORDINATE,
    MAX_SAFE_INTEGER,
    MAX_SHARE_LIFETIME,
    MAX_SHARE_REGIONS,
    SHARE_SCHEMA_VERSION,
    ShareArtifact,
)

_CAPABILITY_BYTES = 32
_CAPABILITY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_NODE_ID_PATTERN = re.compile(r"^n[0-9a-f]{32}$")
_REGION_ID_PATTERN = re.compile(r"^r[0-9a-f]{32}$")
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


@dataclass(frozen=True, slots=True)
class _ArtifactMetadata:
    created_at: datetime
    expires_at: datetime
    payload_digest: str
    artifact_digest: str


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
        metadata = _validate_artifact(encoded)
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
) -> _ArtifactMetadata:
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
    metadata = _validate_artifact(record.artifact)
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


def _validate_artifact(encoded: bytes) -> _ArtifactMetadata:
    try:
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError
        document = json.loads(encoded, object_pairs_hook=_unique_object)
        if rfc8785.dumps(document) != encoded:
            raise ValueError
        _exact_object(document, {"manifest", "payload"})
        manifest = document["manifest"]
        payload = document["payload"]
        _validate_manifest(manifest)
        partial_regions = _validate_payload(payload)
        _validate_coverage(manifest, payload, partial_regions=partial_regions)
        payload_bytes = rfc8785.dumps(payload)
        expected_payload_digest = f"sha256:{sha256(payload_bytes).hexdigest()}"
        if manifest["payload_digest"] != expected_payload_digest:
            raise ValueError
        created_at = _parse_time(manifest["created_at"])
        expires_at = _parse_time(manifest["expires_at"])
        if expires_at <= created_at or expires_at - created_at > MAX_SHARE_LIFETIME:
            raise ValueError
        return _ArtifactMetadata(
            created_at=created_at,
            expires_at=expires_at,
            payload_digest=expected_payload_digest,
            artifact_digest=f"sha256:{sha256(encoded).hexdigest()}",
        )
    except ShareStorageIntegrityError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise ShareStorageIntegrityError(
            "stored share is outside the closed immutable schema"
        ) from error


def _validate_manifest(value: object) -> None:
    _exact_object(
        value,
        {
            "schema_version",
            "producer",
            "created_at",
            "expires_at",
            "payload_digest",
            "declared_exclusions",
            "coverage",
        },
    )
    assert isinstance(value, dict)
    if value["schema_version"] != SHARE_SCHEMA_VERSION:
        raise ValueError
    producer = value["producer"]
    _exact_object(producer, {"codemble_version", "graph_schema_version"})
    assert isinstance(producer, dict)
    if (
        not isinstance(producer["codemble_version"], str)
        or not producer["codemble_version"]
        or len(producer["codemble_version"].encode("utf-8")) > 128
        or producer["graph_schema_version"] != _SUPPORTED_GRAPH_SCHEMA_VERSION
    ):
        raise ValueError
    if value["declared_exclusions"] != list(_DECLARED_EXCLUSIONS):
        raise ValueError
    if _DIGEST_PATTERN.fullmatch(value["payload_digest"] or "") is None:
        raise ValueError
    coverage = value["coverage"]
    _exact_object(
        coverage,
        {
            "source_files",
            "nodes",
            "regions",
            "partial_sources",
            "unsupported_sources",
        },
    )
    assert isinstance(coverage, dict)
    if any(not _safe_int(item) for item in coverage.values()):
        raise ValueError


def _validate_payload(value: object) -> set[str]:
    _exact_object(
        value,
        {
            "schema_version",
            "labels_included",
            "understanding_included",
            "nodes",
            "edges",
            "regions",
            "region_edges",
        },
    )
    assert isinstance(value, dict)
    if value["schema_version"] != SHARE_SCHEMA_VERSION:
        raise ValueError
    labels_included = value["labels_included"]
    understanding_included = value["understanding_included"]
    if not isinstance(labels_included, bool) or not isinstance(understanding_included, bool):
        raise TypeError
    nodes = value["nodes"]
    edges = value["edges"]
    regions = value["regions"]
    region_edges = value["region_edges"]
    if not all(isinstance(items, list) for items in (nodes, edges, regions, region_edges)):
        raise ValueError
    if len(regions) > MAX_SHARE_REGIONS:
        raise ValueError

    node_ids: set[str] = set()
    node_regions: dict[str, str] = {}
    node_languages: dict[str, str] = {}
    node_kinds: dict[str, str] = {}
    node_locs: dict[str, int] = {}
    partial_regions: set[str] = set()
    members_by_region: dict[str, list[str]] = defaultdict(list)
    entrypoints: list[str] = []
    for node in nodes:
        fields = {
            "id",
            "region_id",
            "kind",
            "language",
            "loc",
            "centrality",
            "entrypoint",
            "partial",
            "system_position",
            "system_orbit",
        }
        if labels_included:
            fields.add("label")
        if understanding_included:
            fields.add("understood")
        _exact_object(node, fields)
        assert isinstance(node, dict)
        node_id = node["id"]
        region_id = node["region_id"]
        if (
            not isinstance(node_id, str)
            or _NODE_ID_PATTERN.fullmatch(node_id) is None
            or node_id in node_ids
            or not isinstance(region_id, str)
            or _REGION_ID_PATTERN.fullmatch(region_id) is None
            or node["kind"] not in _NODE_KINDS
            or node["language"] not in _LANGUAGES
            or not _safe_int(node["loc"])
            or not _safe_int(node["centrality"])
            or not isinstance(node["entrypoint"], bool)
            or not isinstance(node["partial"], bool)
        ):
            raise ValueError
        _validate_position(node["system_position"])
        _validate_orbit(node["system_orbit"])
        if labels_included and not _valid_label(node["label"]):
            raise ValueError
        if understanding_included and not isinstance(node["understood"], bool):
            raise ValueError
        node_ids.add(node_id)
        node_regions[node_id] = region_id
        node_languages[node_id] = node["language"]
        node_kinds[node_id] = node["kind"]
        node_locs[node_id] = node["loc"]
        members_by_region[region_id].append(node_id)
        if node["partial"]:
            partial_regions.add(region_id)
        if node["entrypoint"]:
            entrypoints.append(node_id)
    if [node["id"] for node in nodes] != sorted(node_ids) or len(entrypoints) > 1:
        raise ValueError

    edge_marks: list[tuple[str, str, str, bool]] = []
    callers: dict[str, set[str]] = defaultdict(set)
    route_certainties: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for edge in edges:
        _exact_object(edge, {"source_id", "target_id", "kind", "certain"})
        assert isinstance(edge, dict)
        mark = (edge["source_id"], edge["target_id"], edge["kind"], edge["certain"])
        if (
            not all(isinstance(item, str) for item in mark[:3])
            or not isinstance(mark[3], bool)
            or mark[0] not in node_ids
            or mark[1] not in node_ids
            or mark[2] not in _EDGE_KINDS
        ):
            raise ValueError
        edge_marks.append(mark)
        if mark[2] == "call":
            callers[mark[1]].add(mark[0])
        elif node_regions[mark[0]] != node_regions[mark[1]]:
            route_certainties[(node_regions[mark[0]], node_regions[mark[1]])].append(mark[3])
    if edge_marks != sorted(set(edge_marks)):
        raise ValueError
    if any(node["centrality"] != len(callers[node["id"]]) for node in nodes):
        raise ValueError
    _validate_orbit_truth(nodes, edge_marks)

    region_ids: set[str] = set()
    homes: list[str] = []
    regions_by_id: dict[str, dict[str, object]] = {}
    for region in regions:
        fields = {
            "id",
            "language",
            "loc",
            "centrality",
            "node_count",
            "home",
            "layout",
            "community",
            "hops_from_home",
            "community_family",
        }
        if labels_included:
            fields.add("label")
        if understanding_included:
            fields.add("understood")
        _exact_object(region, fields)
        assert isinstance(region, dict)
        region_id = region["id"]
        if (
            not isinstance(region_id, str)
            or _REGION_ID_PATTERN.fullmatch(region_id) is None
            or region_id in region_ids
            or region["language"] not in _LANGUAGES
            or any(
                not _safe_int(region[field])
                for field in ("loc", "centrality", "node_count", "community")
            )
            or not isinstance(region["home"], bool)
            or (region["hops_from_home"] is not None and not _safe_int(region["hops_from_home"]))
            or (
                region["community_family"] is not None
                and (not _safe_int(region["community_family"]) or region["community_family"] > 7)
            )
        ):
            raise ValueError
        _validate_position(region["layout"])
        if labels_included and not _valid_label(region["label"]):
            raise ValueError
        if understanding_included and not isinstance(region["understood"], bool):
            raise ValueError
        members = members_by_region[region_id]
        member_languages = {node_languages[node_id] for node_id in members}
        module_loc = sum(
            node_locs[node_id] for node_id in members if node_kinds[node_id] == "module"
        )
        expected_loc = module_loc or sum(node_locs[node_id] for node_id in members)
        expected_centrality = sum(len(callers[node_id]) for node_id in members)
        if (
            not members
            or member_languages != {region["language"]}
            or region["node_count"] != len(members)
            or region["loc"] != expected_loc
            or region["centrality"] != expected_centrality
        ):
            raise ValueError
        region_ids.add(region_id)
        regions_by_id[region_id] = region
        if region["home"]:
            homes.append(region_id)
    if [region["id"] for region in regions] != sorted(region_ids):
        raise ValueError
    if set(node_regions.values()) != region_ids:
        raise ValueError
    expected_homes = [node_regions[entrypoints[0]]] if entrypoints else []
    if homes != expected_homes:
        raise ValueError

    route_marks: list[tuple[str, str, int, bool]] = []
    for route in region_edges:
        _exact_object(route, {"source_id", "target_id", "weight", "certain"})
        assert isinstance(route, dict)
        mark = (route["source_id"], route["target_id"], route["weight"], route["certain"])
        if (
            not isinstance(mark[0], str)
            or not isinstance(mark[1], str)
            or mark[0] not in region_ids
            or mark[1] not in region_ids
            or not _safe_int(mark[2])
            or mark[2] <= 0
            or not isinstance(mark[3], bool)
        ):
            raise ValueError
        route_marks.append(mark)
    if route_marks != sorted(set(route_marks)):
        raise ValueError
    expected_routes = sorted(
        (source, target, len(certainties), all(certainties))
        for (source, target), certainties in route_certainties.items()
    )
    if route_marks != expected_routes:
        raise ValueError

    expected_hops = _hops(region_ids, route_marks, homes[0] if homes else None)
    if any(
        region["hops_from_home"] != expected_hops.get(region_id)
        for region_id, region in regions_by_id.items()
    ):
        raise ValueError

    return partial_regions


def _validate_coverage(
    manifest: dict[str, object],
    payload: dict[str, object],
    *,
    partial_regions: set[str],
) -> None:
    coverage = manifest["coverage"]
    assert isinstance(coverage, dict)
    nodes = payload["nodes"]
    regions = payload["regions"]
    assert isinstance(nodes, list)
    assert isinstance(regions, list)
    if (
        coverage["source_files"] != len(regions)
        or coverage["nodes"] != len(nodes)
        or coverage["regions"] != len(regions)
        or coverage["partial_sources"] != len(partial_regions)
    ):
        raise ValueError


def _hops(
    region_ids: set[str],
    routes: list[tuple[str, str, int, bool]],
    home: str | None,
) -> dict[str, int]:
    if home is None:
        return {}
    neighbors: dict[str, set[str]] = {region_id: set() for region_id in region_ids}
    for source, target, _weight, _certain in routes:
        neighbors[source].add(target)
        neighbors[target].add(source)
    hops = {home: 0}
    queue = [home]
    for current in queue:
        for neighbor in sorted(neighbors[current]):
            if neighbor in hops:
                continue
            hops[neighbor] = hops[current] + 1
            queue.append(neighbor)
    return hops


def _validate_orbit_truth(
    nodes: list[object],
    edges: list[tuple[str, str, str, bool]],
) -> None:
    """Recompute semantic call layers without trusting stored orbit claims."""

    nodes_by_id: dict[str, dict[str, object]] = {}
    members_by_region: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in nodes:
        assert isinstance(item, dict)
        node_id = item["id"]
        region_id = item["region_id"]
        assert isinstance(node_id, str)
        assert isinstance(region_id, str)
        nodes_by_id[node_id] = item
        members_by_region[region_id].append(item)

    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = defaultdict(int)
    for source, target, kind, certain in edges:
        if (
            kind != "call"
            or not certain
            or source == target
            or nodes_by_id[source]["region_id"] != nodes_by_id[target]["region_id"]
        ):
            continue
        if target not in outgoing[source]:
            indegree[target] += 1
        outgoing[source].add(target)

    for members in members_by_region.values():
        ordered = sorted(
            members,
            key=lambda node: (node["kind"] != "module", node["id"]),
        )
        entry = ordered[0]["id"]
        assert isinstance(entry, str)
        layers: dict[str, tuple[int, int | None, str]] = {entry: (0, 0, "origin")}
        certain_entry_calls = outgoing[entry]
        roots = certain_entry_calls | {
            node_id
            for node in ordered
            if (node_id := node["id"]) != entry
            and isinstance(node_id, str)
            and indegree[node_id] == 0
        }
        queue: deque[str] = deque()
        for node_id in sorted(roots):
            layers[node_id] = (
                1,
                1,
                "certain-call" if node_id in certain_entry_calls else "call-root",
            )
            queue.append(node_id)
        while queue:
            current = queue.popleft()
            current_depth = layers[current][1]
            assert current_depth is not None
            for target in sorted(outgoing[current]):
                if target not in layers:
                    layers[target] = (
                        current_depth + 1,
                        current_depth + 1,
                        "certain-call",
                    )
                    queue.append(target)

        outermost = max(layer[0] for layer in layers.values()) + 1
        for node in ordered:
            node_id = node["id"]
            orbit = node["system_orbit"]
            assert isinstance(node_id, str)
            assert isinstance(orbit, dict)
            expected = layers.get(node_id, (outermost, None, "unreached"))
            actual = (orbit["ring"], orbit["call_depth"], orbit["kind"])
            if actual != expected:
                raise ValueError


def _validate_position(value: object) -> None:
    _exact_object(value, {"x", "y", "z"})
    assert isinstance(value, dict)
    if any(not _bounded_number(value[axis]) for axis in ("x", "y", "z")):
        raise ValueError


def _validate_orbit(value: object) -> None:
    _exact_object(value, {"ring", "radius", "call_depth", "kind"})
    assert isinstance(value, dict)
    if (
        not _safe_int(value["ring"])
        or not _bounded_number(value["radius"])
        or value["radius"] < 0
        or (value["call_depth"] is not None and not _safe_int(value["call_depth"]))
        or value["kind"] not in _ORBIT_KINDS
    ):
        raise ValueError


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _exact_object(value: object, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError
    return parsed.astimezone(UTC)


def _safe_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SAFE_INTEGER


def _bounded_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) <= MAX_RENDER_COORDINATE
    )


def _valid_label(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return len(value.encode("utf-8")) <= MAX_LABEL_UTF8_BYTES
    except UnicodeEncodeError:
        return False


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
