"""Operational share backup and anti-resurrection interfaces."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import shutil
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest

import codemble.share.operations as share_operations
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.cli import main as codemble_main
from codemble.share import (
    EncryptedSQLiteShareStorage,
    InMemoryShareLifecycleLog,
    ShareArtifact,
    ShareDelivery,
    SharePolicy,
    ShareStorageConflictError,
)
from codemble.share.operations import (
    BackupInventoryReceipt,
    ChainedRetirementJournal,
    JournalReplicaBinding,
    ResticSnapshot,
    ResticSnapshotReceipt,
    ResticWriterTargetConfig,
    RestoreGuard,
    RestoreGuardError,
    RetirementAnchorReceipt,
    RetirementJournalError,
    SecurityMetadataRetirementError,
    SecurityMetadataRetirementGuard,
    ShareOperationsRunner,
    ShareOperatorConfig,
    ShareWriterConfig,
    load_retirement_journal,
    materialize_journal_replica,
    retire_backup_snapshots,
)
from codemble.share.ops_cli import operator_restore, writer_cycle
from codemble.share.retirement import ShareRetirementEvent

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
KEY = bytes(range(32))
BACKUP_REPOSITORY_ID = "a" * 64
ANCHOR_IDS = {
    "backup-node": "b" * 64,
    "recovery-node": "c" * 64,
}
FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def _retirement(*, share_id: str = "s" + "1" * 32) -> ShareRetirementEvent:
    return ShareRetirementEvent(
        share_id=share_id,
        kind="revoked",
        terminal_at=NOW,
        expires_at=NOW + timedelta(days=7),
        payload_digest="sha256:" + "2" * 64,
    )


class _Anchor:
    def __init__(self, name: str, repository_id: str) -> None:
        self.name = name
        self.repository_id = repository_id
        self.fail = False
        self.calls = 0

    def repository_identity(self) -> str:
        return self.repository_id

    def anchor(
        self,
        _path: Path,
        *,
        tags: tuple[str, ...],
        replica_name: str,
        entry_digest: str,
    ) -> RetirementAnchorReceipt:
        assert "codemble-share-retirement" in tags
        assert replica_name == self.name
        self.calls += 1
        if self.fail:
            raise RuntimeError("anchor unavailable")
        return RetirementAnchorReceipt(
            replica_name=replica_name,
            repository_id=self.repository_id,
            snapshot_id=f"abc{self.calls:03x}",
            entry_digest=entry_digest,
        )


def _anchors() -> dict[str, _Anchor]:
    return {name: _Anchor(name, identity) for name, identity in ANCHOR_IDS.items()}


class _Writer:
    def __init__(self) -> None:
        self.paths: tuple[Path, ...] = ()
        self.copies: dict[str, bytes] = {}
        self.calls = 0

    def repository_identity(self) -> str:
        return BACKUP_REPOSITORY_ID

    def backup(
        self, paths: tuple[Path, ...], *, tags: tuple[str, ...]
    ) -> ResticSnapshotReceipt:
        assert tags == ("codemble-share-backup",)
        assert all(path.exists() for path in paths)
        self.paths = paths
        self.copies = {path.name: path.read_bytes() for path in paths}
        self.calls += 1
        return ResticSnapshotReceipt(BACKUP_REPOSITORY_ID, f"def{self.calls:03x}")


class _ProcessWriter(_Writer):
    def __init__(self, ready=None, release=None) -> None:
        super().__init__()
        self._ready = ready
        self._release = release

    def backup(
        self, paths: tuple[Path, ...], *, tags: tuple[str, ...]
    ) -> ResticSnapshotReceipt:
        if self._ready is not None:
            self._ready.set()
            if not self._release.wait(timeout=5):
                raise RuntimeError("process lock test timed out")
        return super().backup(paths, tags=tags)


def _run_writer_cycle_process(
    active_root: Path,
    journal_root: Path,
    staging_root: Path,
    ready,
    release,
    results,
) -> None:
    try:
        storage = EncryptedSQLiteShareStorage(
            active_root,
            KEY,
            retirement_recorder=ChainedRetirementJournal(journal_root, _anchors()),
        )
        ShareOperationsRunner(
            storage,
            ChainedRetirementJournal(journal_root, _anchors()),
            _ProcessWriter(ready, release),
            staging_root=staging_root,
        ).run(now=NOW)
        lock_path = active_root.parent / f".{active_root.name}.share-operations.lock"
        results.put(("ok", lock_path.stat().st_ino))
    except Exception as error:  # noqa: BLE001 - child must return the exact failure
        results.put(("error", type(error).__name__, str(error)))


def _hold_restore_promotion_process(
    active_root: Path,
    rollback: Path,
    ready,
    release,
    results,
) -> None:
    try:
        with share_operations._share_operation_lock(active_root):
            os.replace(active_root, rollback)
            ready.set()
            if not release.wait(timeout=5):
                raise RuntimeError("restore promotion test timed out")
            os.replace(rollback, active_root)
        results.put(("ok",))
    except Exception as error:  # noqa: BLE001 - child must return the exact failure
        results.put(("error", type(error).__name__, str(error)))


def _artifact() -> ShareArtifact:
    return ShareArtifact.from_graph(
        PythonAstAdapter().parse(FIXTURE),
        SharePolicy(expires_at=NOW + timedelta(days=7)),
        NOW,
    )


def _delivery(storage: EncryptedSQLiteShareStorage, *, entropy_byte: int = 1) -> ShareDelivery:
    values = iter((bytes([entropy_byte]) * 32, bytes([entropy_byte + 1]) * 32))
    return ShareDelivery(
        storage,
        InMemoryShareLifecycleLog(),
        clock=lambda: NOW,
        entropy=lambda _size: next(values),
    )


def _replicas(source: Path, root: Path) -> dict[str, JournalReplicaBinding]:
    result = {}
    for name, repository_id in ANCHOR_IDS.items():
        target = root / name
        shutil.copytree(source, target)
        result[name] = JournalReplicaBinding(target, repository_id)
    return result


def test_journal_binds_repository_identity_and_snapshot_receipt(tmp_path: Path) -> None:
    anchors = _anchors()
    anchors["backup-node"].fail = True
    journal = ChainedRetirementJournal(tmp_path / "journal", anchors)
    event = _retirement()
    with pytest.raises(RuntimeError, match="anchor unavailable"):
        journal.record(event)
    anchors["backup-node"].fail = False
    journal.record(event)
    journal.record(event)

    assert journal.anchored_head().sequence == 1
    receipts = tuple((tmp_path / "journal" / "receipts").glob("*.anchored"))
    assert len(receipts) == 2
    document = json.loads(receipts[0].read_bytes())
    assert document["repository_id"] in ANCHOR_IDS.values()
    assert document["snapshot_id"].startswith("abc")

    retargeted = _anchors()
    retargeted["recovery-node"].repository_id = "d" * 64
    with pytest.raises(RetirementJournalError, match="inventory changed"):
        ChainedRetirementJournal(tmp_path / "journal", retargeted)


def test_journal_serializes_concurrent_events(tmp_path: Path) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    events = (
        _retirement(share_id="s" + "1" * 32),
        _retirement(share_id="s" + "2" * 32),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        tuple(pool.map(journal.record, events))
    assert [entry.sequence for entry in load_retirement_journal(tmp_path / "journal")] == [1, 2]
    assert journal.anchored_head().sequence == 2


def test_backup_restore_replays_retirements_and_rehydrates_writer_journal(
    tmp_path: Path,
) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY, retirement_recorder=journal)
    delivery = _delivery(storage)
    grant = delivery.create(_artifact())
    writer = _Writer()
    cycle = ShareOperationsRunner(
        storage, journal, writer, staging_root=tmp_path / "staging"
    ).run(now=NOW)
    assert cycle.backup.repository_id == BACKUP_REPOSITORY_ID
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir(mode=0o700)
    for name, content in writer.copies.items():
        path = snapshot / name
        path.write_bytes(content)
        path.chmod(0o600)

    delivery.revoke(grant.delete_capability, confirmed=True)
    replicas = _replicas(tmp_path / "journal", tmp_path / "replicas")
    restored = tmp_path / "restored"
    receipt = RestoreGuard().verify_and_promote(
        snapshot,
        restored,
        encryption_key=KEY,
        journal_replicas=replicas,
        backup_repository_id=BACKUP_REPOSITORY_ID,
        writer_journal_root=tmp_path / "rehydrated-journal",
        writer_uid=os.getuid(),
        writer_gid=os.getgid(),
        now=NOW + timedelta(minutes=5),
    )
    assert receipt.replayed_retirements == 1
    assert load_retirement_journal(tmp_path / "rehydrated-journal") == load_retirement_journal(
        tmp_path / "journal"
    )
    reopened = ShareDelivery(
        EncryptedSQLiteShareStorage(restored, KEY),
        InMemoryShareLifecycleLog(),
        clock=lambda: NOW,
        entropy=lambda size: bytes([9]) * size,
    )
    assert reopened.revoke(grant.delete_capability, confirmed=True).status == "already_revoked"

    wrong_repository_snapshot = tmp_path / "wrong-repository-snapshot"
    wrong_repository_snapshot.mkdir(mode=0o700)
    for name, content in writer.copies.items():
        path = wrong_repository_snapshot / name
        path.write_bytes(content)
        path.chmod(0o600)
    with pytest.raises(RestoreGuardError, match="repository identity"):
        RestoreGuard().verify_and_promote(
            wrong_repository_snapshot,
            tmp_path / "not-restored",
            encryption_key=KEY,
            journal_replicas=replicas,
            backup_repository_id="f" * 64,
            writer_journal_root=tmp_path / "not-journal",
            writer_uid=os.getuid(),
            writer_gid=os.getgid(),
            now=NOW,
        )


def test_operator_restore_promotes_only_into_the_configured_application_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(
        tmp_path / "active",
        KEY,
        retirement_recorder=journal,
    )
    grant = _delivery(storage).create(_artifact())
    writer = _Writer()
    ShareOperationsRunner(
        storage,
        journal,
        writer,
        staging_root=tmp_path / "staging",
    ).run(now=NOW)
    _delivery(storage, entropy_byte=4).revoke(grant.delete_capability, confirmed=True)
    replicas = _replicas(tmp_path / "journal", tmp_path / "replicas")

    executable = tmp_path / "restic"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    executable_digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    repository_password = tmp_path / "operator-repository-key"
    repository_password.write_bytes(b"r" * 32)
    repository_password.chmod(0o600)
    recovery_key = tmp_path / "recovery-key"
    recovery_key.write_bytes(KEY)
    recovery_key.chmod(0o600)
    mounted_repository = tmp_path / "mounted-backup"
    mounted_repository.mkdir(mode=0o700)
    application_root = tmp_path / "application-host"
    backup_host_shadow = tmp_path / "backup-host-shadow"
    config = ShareOperatorConfig(
        deployment_id="codemble-production",
        active_root=application_root / "active",
        journal_root=application_root / "retirement-journal",
        recovery_key_file=recovery_key,
        restic_cache_root=tmp_path / "operator-cache",
        restic_executable=executable,
        restic_sha256=executable_digest,
        repository=str(mounted_repository),
        repository_id=BACKUP_REPOSITORY_ID,
        repository_password_file=repository_password,
        journal_replicas=replicas,
        writer_uid=os.getuid(),
        writer_gid=os.getgid(),
        backup_keep_days=7,
        deletion_deadline_days=8,
        security_margin_hours=48,
    )

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    def run(arguments, _environment):  # type: ignore[no-untyped-def]
        if arguments[1:3] == ("cat", "config"):
            return Result('{"id":"' + BACKUP_REPOSITORY_ID + '"}')
        if arguments[1] == "restore":
            destination = Path(arguments[arguments.index("--target") + 1])
            for name, content in writer.copies.items():
                restored = destination / name
                restored.write_bytes(content)
                restored.chmod(0o600)
        return Result()

    ownership_changes: list[tuple[int, int]] = []
    real_fchown = share_operations.os.fchown

    def record_fchown(descriptor: int, uid: int, gid: int) -> None:
        ownership_changes.append((uid, gid))
        real_fchown(descriptor, uid, gid)

    monkeypatch.setattr(share_operations.os, "fchown", record_fchown)
    receipt = operator_restore(
        config,
        snapshot_id="abc123",
        quarantine_root=application_root / "restore-quarantine",
        rollback=None,
        now=NOW + timedelta(minutes=5),
        runner=run,
    )

    assert receipt.destination == config.active_root
    assert config.active_root.is_dir()
    assert load_retirement_journal(config.journal_root) == load_retirement_journal(
        tmp_path / "journal"
    )
    assert ownership_changes
    assert set(ownership_changes) == {(config.writer_uid, config.writer_gid)}
    for root in (config.active_root, config.journal_root):
        for path in (root, *root.rglob("*")):
            facts = path.stat()
            assert (facts.st_uid, facts.st_gid) == (
                config.writer_uid,
                config.writer_gid,
            )
    assert not backup_host_shadow.exists()


def test_backup_high_water_precedes_concurrent_retirement(tmp_path: Path) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY, retirement_recorder=journal)
    delivery = _delivery(storage, entropy_byte=3)
    grant = delivery.create(_artifact())

    class InterleavingStorage:
        database_path = storage.database_path

        def validate_all(self) -> int:
            return storage.validate_all()

        def retirement_seal(self):  # type: ignore[no-untyped-def]
            return storage.retirement_seal()

        def purge(self, now):  # type: ignore[no-untyped-def]
            return storage.purge(now)

        def backup_to(self, destination: Path) -> None:
            storage.backup_to(destination)
            delivery.revoke(grant.delete_capability, confirmed=True)

    writer = _Writer()
    receipt = ShareOperationsRunner(
        InterleavingStorage(),  # type: ignore[arg-type]
        journal,
        writer,
        staging_root=tmp_path / "staging",
    ).run(now=NOW)
    manifest = json.loads(writer.copies[receipt.backup.manifest_path.name])
    assert manifest["journal_head"]["sequence"] == 0
    assert journal.anchored_head().sequence == 1


def test_concurrent_writer_cycle_cannot_delete_owned_staging(tmp_path: Path) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY, retirement_recorder=journal)
    entered = Event()
    release = Event()

    class BlockingWriter(_Writer):
        def backup(self, paths, *, tags):  # type: ignore[no-untyped-def]
            entered.set()
            assert release.wait(timeout=5)
            assert all(path.exists() for path in paths)
            return super().backup(paths, tags=tags)

    first = ShareOperationsRunner(
        storage, journal, BlockingWriter(), staging_root=tmp_path / "staging"
    )
    second = ShareOperationsRunner(storage, journal, _Writer(), staging_root=tmp_path / "staging")
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(first.run, now=NOW)
        assert entered.wait(timeout=5)
        with pytest.raises(RuntimeError, match="already owns"):
            second.run(now=NOW)
        assert (tmp_path / "staging" / "shares.sqlite3").exists()
        release.set()
        future.result(timeout=5)


def test_restore_promotion_excludes_a_concurrent_writer_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_root = tmp_path / "application-host" / "active"
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(active_root, KEY, retirement_recorder=journal)
    _delivery(storage).create(_artifact())
    writer = _Writer()
    ShareOperationsRunner(
        storage,
        journal,
        writer,
        staging_root=tmp_path / "initial-staging",
    ).run(now=NOW)
    shared_lock = active_root.parent / ".active.share-operations.lock"
    assert stat.S_IMODE(shared_lock.stat().st_mode) == 0o660
    assert shared_lock.stat().st_uid == active_root.parent.stat().st_uid
    assert shared_lock.stat().st_gid == active_root.parent.stat().st_gid
    quarantine = tmp_path / "application-host" / "restore-quarantine"
    quarantine.mkdir(mode=0o700)
    for name, content in writer.copies.items():
        path = quarantine / name
        path.write_bytes(content)
        path.chmod(0o600)
    replicas = _replicas(tmp_path / "journal", tmp_path / "replicas")
    rollback = tmp_path / "application-host" / "rollback"
    entered_promotion = Event()
    release_promotion = Event()
    replace = share_operations.os.replace

    def blocking_replace(source, destination):  # type: ignore[no-untyped-def]
        if Path(source) == quarantine and Path(destination) == active_root:
            entered_promotion.set()
            assert release_promotion.wait(timeout=5)
        return replace(source, destination)

    monkeypatch.setattr(share_operations.os, "replace", blocking_replace)
    guard = RestoreGuard()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(
            guard.verify_and_promote,
            quarantine,
            active_root,
            encryption_key=KEY,
            journal_replicas=replicas,
            backup_repository_id=BACKUP_REPOSITORY_ID,
            writer_journal_root=tmp_path / "rehydrated-journal",
            writer_uid=os.getuid(),
            writer_gid=os.getgid(),
            now=NOW,
            rollback=rollback,
        )
        assert entered_promotion.wait(timeout=5)
        try:
            with pytest.raises(RuntimeError, match="already owns"):
                ShareOperationsRunner(
                    storage,
                    journal,
                    _Writer(),
                    staging_root=tmp_path / "concurrent-staging",
                ).run(now=NOW)
        finally:
            release_promotion.set()
        future.result(timeout=5)

    ShareOperationsRunner(
        EncryptedSQLiteShareStorage(
            active_root,
            KEY,
            retirement_recorder=ChainedRetirementJournal(
                tmp_path / "rehydrated-journal",
                _anchors(),
            ),
        ),
        ChainedRetirementJournal(tmp_path / "rehydrated-journal", _anchors()),
        _Writer(),
        staging_root=tmp_path / "post-restore-staging",
    ).run(now=NOW)


def test_operation_lock_refuses_a_replaceable_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "application-host" / "active"
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(active_root, KEY, retirement_recorder=journal)
    active_root.parent.chmod(0o770)

    with pytest.raises(RuntimeError, match="parent"):
        ShareOperationsRunner(
            storage,
            journal,
            _Writer(),
            staging_root=tmp_path / "staging",
        ).run(now=NOW)

    active_root.parent.chmod(0o700)
    parent_owner = active_root.parent.stat().st_uid
    monkeypatch.setattr(share_operations.os, "geteuid", lambda: parent_owner + 1)
    with pytest.raises(RuntimeError, match="pre-created"):
        ShareOperationsRunner(
            storage,
            journal,
            _Writer(),
            staging_root=tmp_path / "staging",
        ).run(now=NOW)


def test_operation_lock_excludes_other_processes_without_replaceable_path(
    tmp_path: Path,
) -> None:
    active_root = tmp_path / "application-host" / "active"
    journal_root = tmp_path / "journal"
    journal = ChainedRetirementJournal(journal_root, _anchors())
    storage = EncryptedSQLiteShareStorage(active_root, KEY, retirement_recorder=journal)
    ShareOperationsRunner(
        storage,
        journal,
        _Writer(),
        staging_root=tmp_path / "initial-staging",
    ).run(now=NOW)
    lock_path = active_root.parent / ".active.share-operations.lock"
    initial_inode = lock_path.stat().st_ino
    active_root.parent.chmod(0o550)

    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder_results = context.Queue()
    holder = context.Process(
        target=_run_writer_cycle_process,
        args=(
            active_root,
            journal_root,
            tmp_path / "holder-staging",
            ready,
            release,
            holder_results,
        ),
    )
    holder.start()
    assert ready.wait(timeout=5)

    replacement = tmp_path / "replacement.lock"
    replacement.write_bytes(b"replacement")
    with pytest.raises(PermissionError):
        lock_path.unlink()
    with pytest.raises(PermissionError):
        lock_path.rename(active_root.parent / "renamed.lock")
    with pytest.raises(PermissionError):
        os.replace(replacement, lock_path)

    contender_results = context.Queue()
    contender = context.Process(
        target=_run_writer_cycle_process,
        args=(
            active_root,
            journal_root,
            tmp_path / "contender-staging",
            None,
            None,
            contender_results,
        ),
    )
    contender.start()
    contender_result = contender_results.get(timeout=5)
    contender.join(timeout=5)
    assert contender.exitcode == 0
    assert contender_result[:2] == ("error", "RuntimeError")
    assert "already owns" in contender_result[2]
    assert lock_path.stat().st_ino == initial_inode

    release.set()
    holder_result = holder_results.get(timeout=5)
    holder.join(timeout=5)
    assert holder.exitcode == 0
    assert holder_result == ("ok", initial_inode)

    reacquirer_results = context.Queue()
    reacquirer = context.Process(
        target=_run_writer_cycle_process,
        args=(
            active_root,
            journal_root,
            tmp_path / "reacquirer-staging",
            None,
            None,
            reacquirer_results,
        ),
    )
    reacquirer.start()
    reacquirer_result = reacquirer_results.get(timeout=5)
    reacquirer.join(timeout=5)
    assert reacquirer.exitcode == 0
    assert reacquirer_result == ("ok", initial_inode)


def test_writer_cycle_uses_preprovisioned_paths_under_stable_parent(
    tmp_path: Path,
) -> None:
    stable_parent = tmp_path / "application-host"
    active_root = stable_parent / "active"
    journal_root = stable_parent / "retirement-journal"
    staging_root = stable_parent / "backup-staging"
    active_root.mkdir(parents=True, mode=0o700)
    journal_root.mkdir(mode=0o700)
    staging_root.mkdir(mode=0o700)
    lock_path = stable_parent / ".active.share-operations.lock"
    lock_path.touch(mode=0o660)
    lock_path.chmod(0o660)
    journal = ChainedRetirementJournal(journal_root, _anchors())
    storage = EncryptedSQLiteShareStorage(active_root, KEY, retirement_recorder=journal)

    stable_parent.chmod(0o550)
    try:
        receipt = ShareOperationsRunner(
            storage,
            journal,
            _Writer(),
            staging_root=staging_root,
        ).run(now=NOW)
    finally:
        stable_parent.chmod(0o750)

    assert receipt.backup.repository_id == BACKUP_REPOSITORY_ID
    assert active_root.is_dir()
    assert journal_root.is_dir()
    assert staging_root.is_dir()


def test_public_writer_cycle_locks_before_restore_can_expose_a_missing_store(
    tmp_path: Path,
) -> None:
    stable_parent = tmp_path / "application-host"
    active_root = stable_parent / "active"
    journal_root = stable_parent / "retirement-journal"
    staging_root = stable_parent / "backup-staging"
    journal = ChainedRetirementJournal(journal_root, _anchors())
    storage = EncryptedSQLiteShareStorage(active_root, KEY, retirement_recorder=journal)
    ShareOperationsRunner(
        storage,
        journal,
        _Writer(),
        staging_root=staging_root,
    ).run(now=NOW)

    executable = tmp_path / "restic-writer"
    executable.write_text(
        "#!/bin/sh\n"
        'case "${RESTIC_REPOSITORY:-}" in\n'
        f"  *backup-node*) repository_id='{ANCHOR_IDS['backup-node']}' ;;\n"
        f"  *recovery-node*) repository_id='{ANCHOR_IDS['recovery-node']}' ;;\n"
        f"  *) repository_id='{BACKUP_REPOSITORY_ID}' ;;\n"
        "esac\n"
        'if [ "$1" = "cat" ] && [ "$2" = "config" ]; then\n'
        "  printf '{\"id\":\"%s\"}' \"$repository_id\"\n"
        "fi\n"
    )
    executable.chmod(0o700)
    executable_digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    secrets = {}
    for index, name in enumerate(
        (
            "storage-key",
            "writer-repository",
            "writer-rest",
            "backup-repository",
            "backup-rest",
            "recovery-repository",
            "recovery-rest",
        ),
        start=1,
    ):
        path = tmp_path / name
        path.write_bytes(KEY if name == "storage-key" else bytes([index]) * 32)
        path.chmod(0o600)
        secrets[name] = path
    targets = {
        name: ResticWriterTargetConfig(
            repository=f"rest:https://{name}.example.test/{name}/journal/",
            repository_id=repository_id,
            repository_password_file=secrets[f"{name.removesuffix('-node')}-repository"],
            rest_username=name,
            rest_password_file=secrets[f"{name.removesuffix('-node')}-rest"],
            restic_cache_root=tmp_path / f"{name}-cache",
        )
        for name, repository_id in ANCHOR_IDS.items()
    }
    config = ShareWriterConfig(
        deployment_id="codemble-production",
        active_root=active_root,
        journal_root=journal_root,
        staging_root=staging_root,
        storage_key_file=secrets["storage-key"],
        restic_cache_root=tmp_path / "writer-cache",
        restic_executable=executable,
        restic_sha256=executable_digest,
        repository="rest:https://backup.example.test/writer/codemble/",
        repository_id=BACKUP_REPOSITORY_ID,
        repository_password_file=secrets["writer-repository"],
        rest_username="writer",
        rest_password_file=secrets["writer-rest"],
        journal_anchors=targets,
        backup_interval_minutes=60,
        deletion_deadline_days=8,
    )

    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    results = context.Queue()
    rollback = stable_parent / "rollback"
    restore = context.Process(
        target=_hold_restore_promotion_process,
        args=(active_root, rollback, ready, release, results),
    )
    restore.start()
    assert ready.wait(timeout=5)
    try:
        with pytest.raises(RuntimeError, match="already owns"):
            writer_cycle(config, now=NOW)
        recreated_during_promotion = active_root.exists()
        if recreated_during_promotion:
            shutil.rmtree(active_root)
    finally:
        release.set()
    restore_result = results.get(timeout=5)
    restore.join(timeout=5)

    assert restore.exitcode == 0
    assert restore_result == ("ok",)
    assert not recreated_during_promotion
    assert active_root.is_dir()


def test_retirement_authorization_requires_preexisting_seal_and_empty_inventory(
    tmp_path: Path,
) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY, retirement_recorder=journal)
    delivery = _delivery(storage, entropy_byte=5)
    grant = delivery.create(_artifact())
    delivery.revoke(grant.delete_capability, confirmed=True)
    storage.purge(NOW + timedelta(days=2))
    replicas = _replicas(tmp_path / "journal", tmp_path / "replicas")

    class Inventory:
        identities: tuple[str, ...] = ("abc123",)

        def snapshot_inventory(self, *, tags: tuple[str, ...]) -> BackupInventoryReceipt:
            assert tags == ("codemble-share-backup",)
            return BackupInventoryReceipt(BACKUP_REPOSITORY_ID, self.identities)

    inventory = Inventory()
    guard = SecurityMetadataRetirementGuard(
        deletion_deadline=timedelta(days=8), safety_margin=timedelta(hours=48)
    )
    with pytest.raises(SecurityMetadataRetirementError, match="retirement seal"):
        guard.authorize(
            storage,
            journal_replicas=replicas,
            backup_inventory=inventory,
            expected_backup_repository_id=BACKUP_REPOSITORY_ID,
            now=NOW + timedelta(days=11),
        )
    seal = storage.seal_for_retirement(NOW + timedelta(days=11))
    with pytest.raises(SecurityMetadataRetirementError, match="backup snapshots remain"):
        guard.authorize(
            storage,
            journal_replicas=replicas,
            backup_inventory=inventory,
            expected_backup_repository_id=BACKUP_REPOSITORY_ID,
            now=NOW + timedelta(days=11),
        )
    assert storage.retirement_seal() == seal
    with pytest.raises(ShareStorageConflictError, match="sealed"):
        _delivery(storage, entropy_byte=7).create(_artifact())
    inventory.identities = ()
    receipt = guard.authorize(
        storage,
        journal_replicas=replicas,
        backup_inventory=inventory,
        expected_backup_repository_id=BACKUP_REPOSITORY_ID,
        now=NOW + timedelta(days=11),
    )
    assert receipt.seal_epoch == storage.retirement_seal().epoch
    assert receipt.backup_repository_id == BACKUP_REPOSITORY_ID
    assert receipt.inventory_digest.startswith("sha256:")


def test_retirement_inventory_callback_cannot_race_a_new_create(tmp_path: Path) -> None:
    journal = ChainedRetirementJournal(tmp_path / "journal", _anchors())
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY, retirement_recorder=journal)
    journal.record(_retirement())
    storage.seal_for_retirement(NOW + timedelta(days=11))
    replicas = _replicas(tmp_path / "journal", tmp_path / "replicas")

    class RacingInventory:
        def snapshot_inventory(self, *, tags: tuple[str, ...]) -> BackupInventoryReceipt:
            with pytest.raises(ShareStorageConflictError, match="sealed"):
                _delivery(storage, entropy_byte=10).create(_artifact())
            return BackupInventoryReceipt(BACKUP_REPOSITORY_ID, ())

    receipt = SecurityMetadataRetirementGuard(
        deletion_deadline=timedelta(days=8), safety_margin=timedelta(hours=48)
    ).authorize(
        storage,
        journal_replicas=replicas,
        backup_inventory=RacingInventory(),
        expected_backup_repository_id=BACKUP_REPOSITORY_ID,
        now=NOW + timedelta(days=11),
    )
    assert receipt.retirement_events == 1
    assert storage.validate_all() == 0


def test_explicit_backup_retirement_seals_and_removes_exact_inventory(tmp_path: Path) -> None:
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY)

    class Operator:
        identities = ("abc123", "def456")

        def snapshot_inventory(self, *, tags):  # type: ignore[no-untyped-def]
            return BackupInventoryReceipt(BACKUP_REPOSITORY_ID, self.identities)

        def remove_snapshots(self, identities):  # type: ignore[no-untyped-def]
            assert identities == self.identities
            self.identities = ()

        def full_check(self) -> None:
            pass

    operator = Operator()
    receipt = retire_backup_snapshots(
        storage,
        operator,  # type: ignore[arg-type]
        expected_snapshot_ids=("abc123", "def456"),
        expected_backup_repository_id=BACKUP_REPOSITORY_ID,
        now=NOW,
    )
    assert receipt.removed_snapshot_ids == ("abc123", "def456")
    assert storage.retirement_seal().epoch == receipt.seal_epoch
    runner = ShareOperationsRunner(
        storage,
        ChainedRetirementJournal(tmp_path / "journal", _anchors()),
        _Writer(),
        staging_root=tmp_path / "staging",
    )
    with pytest.raises(ShareStorageConflictError, match="sealed"):
        runner.run(now=NOW)


def test_explicit_empty_backup_retirement_installs_the_required_seal(tmp_path: Path) -> None:
    storage = EncryptedSQLiteShareStorage(tmp_path / "active", KEY)

    class Operator:
        def __init__(self) -> None:
            self.removed: list[tuple[str, ...]] = []

        def snapshot_inventory(self, *, tags):  # type: ignore[no-untyped-def]
            assert tags == ("codemble-share-backup",)
            return BackupInventoryReceipt(BACKUP_REPOSITORY_ID, ())

        def remove_snapshots(self, identities):  # type: ignore[no-untyped-def]
            self.removed.append(identities)

        def full_check(self) -> None:
            pass

    operator = Operator()
    receipt = retire_backup_snapshots(
        storage,
        operator,  # type: ignore[arg-type]
        expected_snapshot_ids=(),
        expected_backup_repository_id=BACKUP_REPOSITORY_ID,
        now=NOW,
    )

    assert receipt.removed_snapshot_ids == ()
    assert receipt.seal_epoch == storage.retirement_seal().epoch
    assert operator.removed == []


def test_remote_journal_materialization_reconstructs_receipts(tmp_path: Path) -> None:
    source = ChainedRetirementJournal(tmp_path / "source", _anchors())
    source.record(_retirement())
    entry_path = next((tmp_path / "source" / "events").glob("*.json"))
    entry = load_retirement_journal(tmp_path / "source")[0]

    class Operator:
        def repository_identity(self) -> str:
            return ANCHOR_IDS["backup-node"]

        def full_check(self) -> None:
            pass

        def snapshots(self, *, tags):  # type: ignore[no-untyped-def]
            return (
                ResticSnapshot(
                    "abc123",
                    tuple(
                        sorted(
                            (
                                *tags,
                                f"sequence-{entry.sequence}",
                                f"event-{entry.event.event_id}",
                            )
                        )
                    ),
                ),
            )

        def restore(self, snapshot_id: str, target: Path) -> None:
            assert snapshot_id == "abc123"
            target.mkdir(mode=0o700, parents=True)
            shutil.copy2(entry_path, target / entry_path.name)
            (target / entry_path.name).chmod(0o600)

    head = materialize_journal_replica(
        Operator(),  # type: ignore[arg-type]
        replica_name="backup-node",
        replica_ids=ANCHOR_IDS,
        destination=tmp_path / "materialized",
        quarantine_root=tmp_path / "quarantine",
    )
    assert head.sequence == 1
    receipt = json.loads(
        next((tmp_path / "materialized" / "receipts").glob("*.anchored")).read_bytes()
    )
    assert receipt["repository_id"] == ANCHOR_IDS["backup-node"]
    assert receipt["snapshot_id"] == "abc123"
    assert not (tmp_path / "quarantine").exists()


def test_share_operations_use_the_existing_codemble_entrypoint(capsys) -> None:  # type: ignore[no-untyped-def]
    assert codemble_main(["share-ops", "writer-cycle", "--config", "/missing"]) == 2
    assert "codemble share-ops: operation failed" in capsys.readouterr().err
    assert (
        codemble_main(
            [
                "share-ops",
                "validate-deployment",
                "--writer-attestation",
                "/missing-writer",
                "--operator-attestation",
                "/missing-operator",
            ]
        )
        == 2
    )
    assert (
        codemble_main(
            [
                "share-ops",
                "operator-retire-backups",
                "--config",
                "/missing",
                "--snapshot-id",
                "abc123",
            ]
        )
        == 2
    )
