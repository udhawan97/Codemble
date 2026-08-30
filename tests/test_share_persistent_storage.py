"""Authenticated encrypted persistence through the share-storage interface."""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.share import (
    EncryptedSQLiteShareStorage,
    InMemoryShareLifecycleLog,
    ShareArtifact,
    ShareDelivery,
    SharePolicy,
    ShareStorageConflictError,
    ShareStorageIntegrityError,
    UnknownShareCapabilityError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CREATED_AT = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
KEY = bytes(range(32))


def _artifact(*, lifetime: timedelta = timedelta(days=7)) -> ShareArtifact:
    return ShareArtifact.from_graph(
        PythonAstAdapter().parse(FIXTURE),
        SharePolicy(expires_at=CREATED_AT + lifetime),
        CREATED_AT,
    )


def _delivery(storage, now: list[datetime]) -> ShareDelivery:
    entropy = iter((bytes([1]) * 32, bytes([2]) * 32))
    return ShareDelivery(
        storage,
        InMemoryShareLifecycleLog(),
        clock=lambda: now[0],
        entropy=lambda size: next(entropy),
    )


def test_encrypted_store_reopens_without_plaintext_or_adjacent_key(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    artifact = _artifact()
    storage = EncryptedSQLiteShareStorage(root, KEY)
    grant = _delivery(storage, now).create(artifact)

    database_bytes = storage.database_path.read_bytes()

    assert artifact.to_bytes() not in database_bytes
    assert KEY not in database_bytes
    assert sorted(path.name for path in root.iterdir()) == ["shares.sqlite3"]
    reopened = EncryptedSQLiteShareStorage(root, KEY)
    assert _delivery(reopened, now).view(grant.view_capability) == artifact.to_bytes()
    with pytest.raises(ShareStorageIntegrityError, match="key does not authenticate"):
        EncryptedSQLiteShareStorage(root, bytes(reversed(KEY)))
    assert _delivery(reopened, now).view(grant.view_capability) == artifact.to_bytes()


def test_deleted_identity_cannot_reinitialize_an_existing_store(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    storage = EncryptedSQLiteShareStorage(root, KEY)
    _delivery(storage, [CREATED_AT]).create(_artifact())

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute("DELETE FROM storage_identity")
        connection.execute("PRAGMA user_version = 0")

    with pytest.raises(ShareStorageIntegrityError, match="schema does not match"):
        EncryptedSQLiteShareStorage(root, KEY)
    with pytest.raises(ShareStorageIntegrityError, match="schema does not match"):
        storage.purge(CREATED_AT)


def test_identity_tampering_is_reauthenticated_on_every_operation(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    storage = EncryptedSQLiteShareStorage(root, KEY)

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute(
            "UPDATE storage_identity SET ciphertext = zeroblob(length(ciphertext))"
        )

    with pytest.raises(ShareStorageIntegrityError, match="key does not authenticate"):
        storage.purge(CREATED_AT)
    with pytest.raises(ShareStorageIntegrityError, match="key does not authenticate"):
        EncryptedSQLiteShareStorage(root, KEY)


def test_database_replacement_with_another_key_fails_closed(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = EncryptedSQLiteShareStorage(first_root, KEY)
    second = EncryptedSQLiteShareStorage(second_root, bytes(reversed(KEY)))
    _delivery(first, [CREATED_AT]).create(_artifact())
    _delivery(second, [CREATED_AT]).create(_artifact())

    shutil.copyfile(second.database_path, first.database_path)

    with pytest.raises(ShareStorageIntegrityError, match="key does not authenticate"):
        first.purge(CREATED_AT)


def test_missing_nonce_schema_is_never_repaired_on_reopen(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    storage = EncryptedSQLiteShareStorage(root, KEY)

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute("DROP TABLE encryption_nonces")

    with pytest.raises(ShareStorageIntegrityError, match="schema does not match"):
        EncryptedSQLiteShareStorage(root, KEY)
    with sqlite3.connect(storage.database_path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert "encryption_nonces" not in names


def test_deleted_nonce_history_blocks_attempted_reuse(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    record_nonce = bytes([7]) * 12
    storage = EncryptedSQLiteShareStorage(
        root,
        KEY,
        nonce_entropy=lambda size: record_nonce,
    )
    delivery = _delivery(storage, [CREATED_AT])
    delivery.create(_artifact())

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute(
            "DELETE FROM encryption_nonces WHERE nonce = ?",
            (record_nonce,),
        )

    with pytest.raises(ShareStorageIntegrityError, match="history failed authentication"):
        _delivery(storage, [CREATED_AT]).create(
            _artifact(lifetime=timedelta(days=8))
        )


def test_posix_root_and_database_modes_are_revalidated_on_every_use(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share-store"
    storage = EncryptedSQLiteShareStorage(root, KEY)

    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(storage.database_path.stat().st_mode) == 0o600
    os.chmod(storage.database_path, 0o644)
    with pytest.raises(PermissionError, match="group or other"):
        storage.purge(CREATED_AT)


def test_non_posix_permission_semantics_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")

    with pytest.raises(OSError, match="requires POSIX"):
        EncryptedSQLiteShareStorage(tmp_path / "share-store", KEY)


def test_concurrent_initialization_binds_an_empty_store_to_exactly_one_key(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share-store"
    other_key = bytes(reversed(KEY))

    def open_store(key: bytes) -> str:
        try:
            EncryptedSQLiteShareStorage(root, key)
        except ShareStorageIntegrityError:
            return "refused"
        return "opened"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(open_store, (KEY, other_key)))

    assert sorted(outcomes) == ["opened", "refused"]


def test_revocation_is_retry_safe_persistent_and_survives_clock_rollback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    storage = EncryptedSQLiteShareStorage(root, KEY)
    delivery = _delivery(storage, now)
    grant = delivery.create(_artifact())

    assert delivery.revoke(grant.delete_capability, confirmed=True).status == "revoked"
    now[0] -= timedelta(minutes=5)
    reopened = _delivery(EncryptedSQLiteShareStorage(root, KEY), now)

    assert reopened.revoke(grant.delete_capability, confirmed=True).status == "already_revoked"
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        reopened.view(grant.view_capability)


def test_purge_expires_unobserved_bytes_then_unlinks_after_retention(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    retention = timedelta(hours=2)
    storage = EncryptedSQLiteShareStorage(root, KEY, terminal_retention=retention)
    delivery = _delivery(storage, now)
    grant = delivery.create(_artifact(lifetime=timedelta(days=1)))

    before_retention = storage.purge(CREATED_AT + timedelta(days=1, hours=1))
    assert before_retention.expired == 1
    assert before_retention.deleted == 0

    now[0] = CREATED_AT
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.view_capability)

    after_retention = storage.purge(CREATED_AT + timedelta(days=1, hours=2))
    assert after_retention.expired == 0
    assert after_retention.deleted == 1
    with sqlite3.connect(storage.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM shares").fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM capability_lookups WHERE share_id IS NOT NULL"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM capability_fingerprints WHERE share_id IS NOT NULL"
        ).fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM capability_lookups").fetchone()[0] == 2
        assert connection.execute(
            "SELECT count(*) FROM capability_fingerprints"
        ).fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM encryption_nonces").fetchone()[0] >= 2


def test_early_revocation_unlinks_from_its_own_retention_without_reassignment(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    retention = timedelta(hours=2)
    storage = EncryptedSQLiteShareStorage(root, KEY, terminal_retention=retention)
    delivery = _delivery(storage, now)
    artifact = _artifact(lifetime=timedelta(days=30))
    grant = delivery.create(artifact)
    assert delivery.revoke(grant.delete_capability, confirmed=True).status == "revoked"

    assert storage.purge(CREATED_AT + timedelta(hours=1)).deleted == 0
    assert delivery.revoke(grant.delete_capability, confirmed=True).status == "already_revoked"
    assert storage.purge(CREATED_AT + retention).deleted == 1
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.view_capability)
    with pytest.raises(ShareStorageConflictError, match="create-only"):
        _delivery(storage, now).create(artifact)


def test_deleted_detached_capability_history_blocks_reassignment(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    retention = timedelta(hours=1)
    storage = EncryptedSQLiteShareStorage(
        root,
        KEY,
        terminal_retention=retention,
    )
    delivery = _delivery(storage, now)
    artifact = _artifact()
    grant = delivery.create(artifact)
    delivery.revoke(grant.delete_capability, confirmed=True)
    storage.purge(CREATED_AT + retention)

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute(
            "DELETE FROM capability_lookups WHERE lookup = "
            "(SELECT lookup FROM capability_lookups WHERE share_id IS NULL LIMIT 1)"
        )

    with pytest.raises(ShareStorageIntegrityError, match="history failed authentication"):
        _delivery(storage, now).create(artifact)


def test_observed_expiry_survives_reopen_and_clock_rollback(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    storage = EncryptedSQLiteShareStorage(root, KEY)
    delivery = _delivery(storage, now)
    grant = delivery.create(_artifact(lifetime=timedelta(days=1)))

    now[0] += timedelta(days=1)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        delivery.view(grant.view_capability)
    now[0] = CREATED_AT
    reopened = _delivery(EncryptedSQLiteShareStorage(root, KEY), now)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        reopened.view(grant.view_capability)
    with pytest.raises(UnknownShareCapabilityError, match="Share not found"):
        reopened.revoke(grant.delete_capability, confirmed=True)


def test_two_adapter_instances_atomically_refuse_identity_reuse(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    first_storage = EncryptedSQLiteShareStorage(root, KEY)
    first_delivery = _delivery(first_storage, now)
    artifact = _artifact()
    first_delivery.create(artifact)

    second_storage = EncryptedSQLiteShareStorage(root, KEY)
    with pytest.raises(ShareStorageConflictError, match="create-only"):
        _delivery(second_storage, now).create(artifact)


def test_two_adapter_instances_serialize_concurrent_create(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    storages = (
        EncryptedSQLiteShareStorage(root, KEY),
        EncryptedSQLiteShareStorage(root, KEY),
    )
    artifact = _artifact()

    def create(storage):
        try:
            return "created", _delivery(storage, now).create(artifact)
        except ShareStorageConflictError:
            return "refused", None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(create, storages))

    assert sorted(status for status, _ in outcomes) == ["created", "refused"]
    grant = next(grant for status, grant in outcomes if status == "created")
    assert grant is not None
    assert _delivery(storages[0], now).view(grant.view_capability) == artifact.to_bytes()


def test_eight_adapters_complete_120_distinct_concurrent_creates(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    storages = [EncryptedSQLiteShareStorage(root, KEY) for _ in range(8)]
    artifact = _artifact()

    def create(index: int):
        entropy = iter(
            (
                (index + 1).to_bytes(32, "big"),
                (index + 1_001).to_bytes(32, "big"),
            )
        )
        delivery = ShareDelivery(
            storages[index % len(storages)],
            InMemoryShareLifecycleLog(),
            clock=lambda: CREATED_AT,
            entropy=lambda size: next(entropy),
        )
        return delivery.create(artifact)

    with ThreadPoolExecutor(max_workers=8) as executor:
        grants = list(executor.map(create, range(120)))

    assert len({grant.view_capability for grant in grants}) == 120
    with sqlite3.connect(storages[0].database_path) as connection:
        assert connection.execute("SELECT count(*) FROM shares").fetchone()[0] == 120
        assert connection.execute(
            "SELECT count(*) FROM capability_lookups"
        ).fetchone()[0] == 240


def test_ciphertext_tampering_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    storage = EncryptedSQLiteShareStorage(root, KEY)
    delivery = _delivery(storage, now)
    grant = delivery.create(_artifact())

    with sqlite3.connect(storage.database_path) as connection:
        ciphertext = connection.execute("SELECT ciphertext FROM shares").fetchone()[0]
        changed = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
        connection.execute("UPDATE shares SET ciphertext = ?", (changed,))

    with pytest.raises(ShareStorageIntegrityError, match="authenticated decryption"):
        delivery.view(grant.view_capability)


def test_derived_index_tampering_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    storage = EncryptedSQLiteShareStorage(root, KEY)
    delivery = _delivery(storage, now)
    grant = delivery.create(_artifact())

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute("DELETE FROM capability_fingerprints")

    with pytest.raises(ShareStorageIntegrityError, match="history failed authentication"):
        delivery.view(grant.view_capability)


def test_encryption_nonce_reuse_is_refused_before_replacing_ciphertext(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    repeated_nonce = bytes([9]) * 12
    storage = EncryptedSQLiteShareStorage(
        root,
        KEY,
        nonce_entropy=lambda size: repeated_nonce,
    )
    delivery = _delivery(storage, now)
    grant = delivery.create(_artifact())

    with pytest.raises(ShareStorageIntegrityError, match="repeated encryption nonces"):
        delivery.revoke(grant.delete_capability, confirmed=True)

    assert delivery.view(grant.view_capability)


def test_failed_create_cannot_release_a_reserved_nonce_for_later_reuse(tmp_path: Path) -> None:
    root = tmp_path / "share-store"
    now = [CREATED_AT]
    first_nonce = bytes([8]) * 12
    failed_nonce = bytes([9]) * 12
    calls = [first_nonce]

    def nonce_entropy(size: int) -> bytes:
        return calls.pop(0) if calls else failed_nonce

    storage = EncryptedSQLiteShareStorage(root, KEY, nonce_entropy=nonce_entropy)
    artifact = _artifact()
    _delivery(storage, now).create(artifact)

    with pytest.raises(ShareStorageConflictError, match="create-only"):
        _delivery(storage, now).create(artifact)
    with pytest.raises(ShareStorageIntegrityError, match="repeated encryption nonces"):
        storage.purge(CREATED_AT + timedelta(days=8))
