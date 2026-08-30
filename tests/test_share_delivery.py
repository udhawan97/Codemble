"""Provider-neutral capability delivery for immutable read-only shares."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
import rfc8785

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.share import (
    InMemoryShareLifecycleLog,
    InMemoryShareStorage,
    ShareArtifact,
    ShareDelivery,
    SharePolicy,
    ShareRevocationConfirmationError,
    ShareStorageConflictError,
    ShareStorageIntegrityError,
    ShareStoragePort,
    StoredShare,
    StoredShareRevocation,
    UnknownShareCapabilityError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CREATED_AT = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _artifact(*, lifetime: timedelta = timedelta(days=7)) -> ShareArtifact:
    return ShareArtifact.from_graph(
        PythonAstAdapter().parse(FIXTURE),
        SharePolicy(expires_at=CREATED_AT + lifetime),
        CREATED_AT,
    )


def _delivery(
    *,
    storage: ShareStoragePort | None = None,
    clock=lambda: CREATED_AT,
    entropy: list[bytes] | None = None,
) -> ShareDelivery:
    values = iter(entropy or (bytes([1]) * 32, bytes([2]) * 32))
    return ShareDelivery(
        storage or InMemoryShareStorage(),
        InMemoryShareLifecycleLog(),
        clock=clock,
        entropy=lambda size: next(values),
    )


def test_create_issues_independent_256_bit_capabilities_and_exact_view_bytes() -> None:
    artifact = _artifact()
    delivery = _delivery()

    grant = delivery.create(artifact)

    assert grant.view_capability != grant.delete_capability
    assert len(grant.view_capability) == 43
    assert len(grant.delete_capability) == 43
    assert grant.expires_at == CREATED_AT + timedelta(days=7)
    assert grant.payload_digest.startswith("sha256:")
    assert delivery.view(grant.view_capability) == artifact.to_bytes()


def test_lifecycle_sink_failure_never_orphans_or_changes_capability_state(caplog) -> None:
    class FailingLifecycleLog:
        def record(self, event) -> None:
            raise RuntimeError("sink contains a secret that must not be echoed")

    values = iter((bytes([1]) * 32, bytes([2]) * 32))
    delivery = ShareDelivery(
        InMemoryShareStorage(),
        FailingLifecycleLog(),
        clock=lambda: CREATED_AT,
        entropy=lambda size: next(values),
    )
    artifact = _artifact()

    with caplog.at_level(logging.ERROR, logger="codemble.share.lifecycle.failure"):
        grant = delivery.create(artifact)
        assert delivery.view(grant.view_capability) == artifact.to_bytes()
        assert delivery.revoke(grant.delete_capability, confirmed=True).status == "revoked"

    assert "Share lifecycle event could not be recorded" in caplog.text
    assert "sink contains" not in caplog.text
    assert grant.view_capability not in caplog.text
    assert grant.delete_capability not in caplog.text


def test_storage_port_receives_only_derived_lookups_not_raw_capabilities() -> None:
    class RecordingStorage:
        def __init__(self) -> None:
            self.record: StoredShare | None = None
            self.read_calls = 0
            self.revoke_calls = 0

        def create(self, record: StoredShare) -> None:
            self.record = record

        def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
            self.read_calls += 1
            assert self.record is not None
            return (
                self.record
                if self.record.view_lookup == view_lookup
                and self.record.artifact is not None
                and self.record.revoked_at is None
                and now < self.record.expires_at
                else None
            )

        def revoke(self, delete_lookup: str, now: datetime) -> StoredShareRevocation | None:
            self.revoke_calls += 1
            assert self.record is not None
            if self.record.delete_lookup != delete_lookup or now >= self.record.expires_at:
                return None
            if self.record.revoked_at is not None:
                return StoredShareRevocation(self.record, already_revoked=True)
            self.record = replace(self.record, artifact=None, revoked_at=now)
            return StoredShareRevocation(self.record, already_revoked=False)

    storage = RecordingStorage()
    delivery = _delivery(storage=storage)
    artifact = _artifact()

    grant = delivery.create(artifact)

    assert storage.record is not None
    stored_text = repr(storage.record)
    assert grant.view_capability not in stored_text
    assert grant.delete_capability not in stored_text
    assert grant.view_capability not in repr(grant)
    assert grant.delete_capability not in repr(grant)
    assert len(storage.record.view_lookup) == 64
    assert len(storage.record.delete_lookup) == 64
    assert storage.record.view_lookup != storage.record.delete_lookup
    assert len(storage.record.view_fingerprint) == 64
    assert len(storage.record.delete_fingerprint) == 64
    assert len(storage.record.view_binding) == 64
    assert len(storage.record.delete_binding) == 64
    assert storage.record.view_lookup not in stored_text
    assert storage.record.delete_lookup not in stored_text
    assert storage.record.artifact is not None
    assert storage.record.artifact.decode() not in stored_text
    assert delivery.view(grant.view_capability) == artifact.to_bytes()
    assert delivery.revoke(grant.delete_capability, confirmed=True).status == "revoked"
    assert delivery.revoke(grant.delete_capability, confirmed=True).status == "already_revoked"
    assert storage.read_calls == 1
    assert storage.revoke_calls == 2


def test_capabilities_are_least_authority_and_cannot_cross_roles() -> None:
    delivery = _delivery()
    grant = delivery.create(_artifact())

    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.delete_capability)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.revoke(grant.view_capability, confirmed=True)

    assert delivery.view(grant.view_capability)


def test_view_is_inert_and_invalid_expired_or_revoked_capabilities_are_uniform() -> None:
    now = [CREATED_AT]
    delivery = _delivery(clock=lambda: now[0])
    first = delivery.create(_artifact(lifetime=timedelta(days=1)))

    assert delivery.view(first.view_capability) == delivery.view(first.view_capability)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view("not-a-capability")

    now[0] += timedelta(days=1)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(first.view_capability)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.revoke(first.delete_capability, confirmed=True)


def test_observed_expiry_cannot_resurrect_after_server_clock_rollback() -> None:
    now = [CREATED_AT]
    delivery = _delivery(clock=lambda: now[0])
    grant = delivery.create(_artifact(lifetime=timedelta(days=1)))

    now[0] += timedelta(days=1)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.view_capability)

    now[0] = CREATED_AT
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.view_capability)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.revoke(grant.delete_capability, confirmed=True)


def test_revoke_requires_confirmation_is_atomic_and_is_retry_safe() -> None:
    now = [CREATED_AT]
    delivery = _delivery(clock=lambda: now[0])
    grant = delivery.create(_artifact())

    with pytest.raises(ShareRevocationConfirmationError):
        delivery.revoke(grant.delete_capability, confirmed=False)
    assert delivery.view(grant.view_capability)

    revoked = delivery.revoke(grant.delete_capability, confirmed=True)
    now[0] -= timedelta(seconds=1)
    repeated = delivery.revoke(grant.delete_capability, confirmed=True)

    assert revoked.status == "revoked"
    assert repeated.status == "already_revoked"
    assert repeated.payload_digest == revoked.payload_digest == grant.payload_digest
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.view_capability)


def test_no_view_authorization_started_after_revocation_can_succeed() -> None:
    delivery = _delivery()
    grant = delivery.create(_artifact())
    failures: list[BaseException] = []
    revoked = threading.Event()

    def view_after_revocation() -> None:
        assert revoked.wait(timeout=5)
        try:
            delivery.view(grant.view_capability)
        except BaseException as error:  # noqa: BLE001 - captured across a test thread
            failures.append(error)

    reader = threading.Thread(target=view_after_revocation)
    reader.start()
    delivery.revoke(grant.delete_capability, confirmed=True)
    revoked.set()
    reader.join(timeout=5)

    assert not reader.is_alive()
    assert len(failures) == 1
    assert isinstance(failures[0], UnknownShareCapabilityError)


@pytest.mark.parametrize(
    "second_entropy",
    (
        [bytes([1]) * 32, bytes([3]) * 32],
        [bytes([4]) * 32, bytes([2]) * 32],
        [bytes([2]) * 32, bytes([3]) * 32],
    ),
    ids=("same-view", "same-delete", "cross-role"),
)
def test_storage_never_reassigns_capabilities_after_revocation(
    second_entropy: list[bytes],
) -> None:
    storage = InMemoryShareStorage()
    artifact = _artifact()
    first = _delivery(
        storage=storage,
        entropy=[bytes([1]) * 32, bytes([2]) * 32],
    )
    second = _delivery(
        storage=storage,
        entropy=second_entropy,
    )
    grant = first.create(artifact)
    first.revoke(grant.delete_capability, confirmed=True)

    with pytest.raises(ShareStorageConflictError):
        second.create(artifact)


def test_storage_never_reassigns_capabilities_after_observed_expiry() -> None:
    now = [CREATED_AT]
    storage = InMemoryShareStorage()
    artifact = _artifact(lifetime=timedelta(days=1))
    first = _delivery(storage=storage, clock=lambda: now[0])
    grant = first.create(artifact)
    now[0] += timedelta(days=1)
    with pytest.raises(UnknownShareCapabilityError):
        first.view(grant.view_capability)

    replacement = _delivery(
        storage=storage,
        clock=lambda: now[0],
        entropy=[bytes([1]) * 32, bytes([3]) * 32],
    )
    with pytest.raises(ShareStorageConflictError):
        replacement.create(_artifact(lifetime=timedelta(days=2)))


def test_equal_or_wrong_sized_entropy_fails_before_storage() -> None:
    with pytest.raises(RuntimeError, match="32 bytes"):
        _delivery(entropy=[b"short", bytes([2]) * 32]).create(_artifact())
    with pytest.raises(RuntimeError, match="independent"):
        _delivery(entropy=[bytes([1]) * 32, bytes([1]) * 32]).create(_artifact())


def test_server_clock_must_be_timezone_aware_and_artifact_must_still_be_live() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _delivery(clock=lambda: CREATED_AT.replace(tzinfo=None)).create(_artifact())
    with pytest.raises(ValueError, match="already expired"):
        _delivery(clock=lambda: CREATED_AT + timedelta(days=7)).create(_artifact())
    with pytest.raises(ValueError, match="creation time is in the future"):
        _delivery(clock=lambda: CREATED_AT - timedelta(seconds=1)).create(_artifact())


@pytest.mark.parametrize(
    "mutation",
    ("unknown-field", "future-schema", "payload", "orbit"),
)
def test_stored_artifact_is_strictly_revalidated_before_view(mutation: str) -> None:
    class TamperingStorage(InMemoryShareStorage):
        def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
            record = super().read(view_lookup, now)
            assert record is not None and record.artifact is not None
            document = json.loads(record.artifact)
            if mutation == "unknown-field":
                document["payload"]["unexpected"] = True
            elif mutation == "future-schema":
                document["payload"]["schema_version"] += 1
            else:
                if mutation == "orbit":
                    document["payload"]["nodes"][0]["system_orbit"]["ring"] += 1
                else:
                    document["payload"]["nodes"][0]["centrality"] += 1
                payload = rfc8785.dumps(document["payload"])
                document["manifest"]["payload_digest"] = f"sha256:{sha256(payload).hexdigest()}"
            artifact = rfc8785.dumps(document)
            return replace(
                record,
                artifact=artifact,
                artifact_digest=f"sha256:{sha256(artifact).hexdigest()}",
                payload_digest=document["manifest"]["payload_digest"],
            )

    delivery = _delivery(storage=TamperingStorage())
    grant = delivery.create(_artifact())

    with pytest.raises(ShareStorageIntegrityError):
        delivery.view(grant.view_capability)


@pytest.mark.parametrize(
    "mutation",
    ("payload-digest", "share-id", "delete-lookup"),
)
def test_storage_record_identity_and_manifest_metadata_are_bound_to_exact_bytes(
    mutation: str,
) -> None:
    class MetadataTamperingStorage(InMemoryShareStorage):
        def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
            record = super().read(view_lookup, now)
            assert record is not None
            if mutation == "share-id":
                return replace(record, share_id="s" + "0" * 32)
            if mutation == "delete-lookup":
                return replace(record, delete_lookup="0" * 64)
            return replace(record, payload_digest="sha256:" + "0" * 64)

    delivery = _delivery(storage=MetadataTamperingStorage())
    grant = delivery.create(_artifact())

    with pytest.raises(ShareStorageIntegrityError):
        delivery.view(grant.view_capability)


@pytest.mark.parametrize("mutation", ("share-id", "payload-digest"))
def test_revocation_record_metadata_is_bound_to_the_delete_capability(
    mutation: str,
) -> None:
    class RevocationTamperingStorage(InMemoryShareStorage):
        def revoke(self, delete_lookup: str, now: datetime) -> StoredShareRevocation | None:
            result = super().revoke(delete_lookup, now)
            assert result is not None
            share = (
                replace(result.share, share_id="s" + "0" * 32)
                if mutation == "share-id"
                else replace(result.share, payload_digest="sha256:" + "0" * 64)
            )
            return StoredShareRevocation(
                share,
                already_revoked=result.already_revoked,
            )

    delivery = _delivery(storage=RevocationTamperingStorage())
    grant = delivery.create(_artifact())

    with pytest.raises(ShareStorageIntegrityError):
        delivery.revoke(grant.delete_capability, confirmed=True)
