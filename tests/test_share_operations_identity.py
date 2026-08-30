"""Repository identity and split-authority deployment receipts."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from codemble.share.operations import (
    JournalReplicaBinding,
    JournalReplicaOperatorConfig,
    ResticBackupWriter,
    ResticCommandError,
    ResticOperator,
    ResticSnapshotReceipt,
    ResticWriterTargetConfig,
    ShareDeploymentAttestation,
    ShareOperatorConfig,
    ShareWriterConfig,
    create_operator_attestation,
    create_writer_attestation,
    validate_role_separation,
)

BACKUP_ID = "a" * 64
ANCHOR_IDS = {"backup-node": "b" * 64, "recovery-node": "c" * 64}


class _Result:
    def __init__(self, stdout: str = "") -> None:
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""


def _private(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _restic(tmp_path: Path) -> tuple[Path, str]:
    executable = tmp_path / "restic"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    return executable, "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()


def test_restic_receipts_bind_the_authenticated_repository(tmp_path: Path) -> None:
    executable, executable_digest = _restic(tmp_path)
    repository_password = _private(tmp_path / "repository-password", b"r" * 32)
    rest_password = _private(tmp_path / "rest-password", b"w" * 32)
    calls: list[tuple[str, ...]] = []

    def run(arguments, _environment):  # type: ignore[no-untyped-def]
        calls.append(arguments)
        if arguments[1:3] == ("cat", "config"):
            return _Result('{"id":"' + BACKUP_ID + '"}')
        if "backup" in arguments:
            return _Result('{"message_type":"summary","snapshot_id":"abc123"}\n')
        if "snapshots" in arguments:
            return _Result('[{"id":"abc123","tags":["codemble-share-backup"]}]')
        return _Result()

    writer = ResticBackupWriter(
        "rest:https://backup.example.test/writer/codemble/",
        repository_password,
        expected_repository_id=BACKUP_ID,
        restic_executable=executable,
        expected_executable_digest=executable_digest,
        cache_root=tmp_path / "writer-cache",
        rest_username="writer",
        rest_password_file=rest_password,
        runner=run,
    )
    payload = _private(tmp_path / "payload", b"ciphertext")
    assert writer.backup((payload,), tags=("codemble-share-backup",)) == ResticSnapshotReceipt(
        BACKUP_ID, "abc123"
    )

    local_repository = tmp_path / "repository"
    local_repository.mkdir(mode=0o700)
    operator = ResticOperator(
        str(local_repository),
        repository_password,
        expected_repository_id=BACKUP_ID,
        restic_executable=executable,
        expected_executable_digest=executable_digest,
        cache_root=tmp_path / "operator-cache",
        runner=run,
    )
    inventory = operator.snapshot_inventory(tags=("codemble-share-backup",))
    assert inventory.repository_id == BACKUP_ID
    assert inventory.snapshot_ids == ("abc123",)
    assert sum(command[1:3] == ("cat", "config") for command in calls) >= 4

    wrong = ResticOperator(
        str(local_repository),
        repository_password,
        expected_repository_id="f" * 64,
        restic_executable=executable,
        expected_executable_digest=executable_digest,
        cache_root=tmp_path / "wrong-cache",
        runner=run,
    )
    with pytest.raises(ResticCommandError, match="identity"):
        wrong.snapshot_inventory(tags=("codemble-share-backup",))


def test_credential_derived_attestations_validate_without_colocating_configs(
    tmp_path: Path,
) -> None:
    executable, executable_digest = _restic(tmp_path)
    active = tmp_path / "active"
    journal = tmp_path / "journal"
    staging = tmp_path / "staging"
    local_repository = tmp_path / "repository"
    local_repository.mkdir(mode=0o700)
    storage_key = _private(tmp_path / "storage-key", b"k" * 32)
    recovery_key = _private(tmp_path / "recovery-key", b"k" * 32)
    writer_repository = _private(tmp_path / "writer-repository", b"a" * 32)
    writer_rest = _private(tmp_path / "writer-rest", b"b" * 32)
    operator_repository = _private(tmp_path / "operator-repository", b"c" * 32)
    anchor_credentials = []
    anchor_targets = {}
    for index, (name, repository_id) in enumerate(ANCHOR_IDS.items(), start=1):
        repository_secret = _private(
            tmp_path / f"{name}-repository", bytes([10 + index]) * 32
        )
        rest_secret = _private(tmp_path / f"{name}-rest", bytes([20 + index]) * 32)
        anchor_credentials.extend((repository_secret, rest_secret))
        anchor_targets[name] = ResticWriterTargetConfig(
            repository=f"rest:https://{name}.example.test/{name}/codemble/",
            repository_id=repository_id,
            repository_password_file=repository_secret,
            rest_username=name,
            rest_password_file=rest_secret,
            restic_cache_root=tmp_path / f"{name}-cache",
        )
    writer = ShareWriterConfig(
        deployment_id="codemble-production",
        active_root=active,
        journal_root=journal,
        staging_root=staging,
        storage_key_file=storage_key,
        restic_cache_root=tmp_path / "writer-cache",
        restic_executable=executable,
        restic_sha256=executable_digest,
        repository="rest:https://backup.example.test/writer/codemble/",
        repository_id=BACKUP_ID,
        repository_password_file=writer_repository,
        rest_username="writer",
        rest_password_file=writer_rest,
        journal_anchors=anchor_targets,
        backup_interval_minutes=60,
        deletion_deadline_days=8,
    )
    operator = ShareOperatorConfig(
        deployment_id="codemble-production",
        active_root=active,
        journal_root=journal,
        recovery_key_file=recovery_key,
        restic_cache_root=tmp_path / "operator-cache",
        restic_executable=executable,
        restic_sha256=executable_digest,
        repository=str(local_repository),
        repository_id=BACKUP_ID,
        repository_password_file=operator_repository,
        journal_replicas={
            name: JournalReplicaBinding(tmp_path / name, repository_id)
            for name, repository_id in ANCHOR_IDS.items()
        },
        writer_uid=os.getuid(),
        writer_gid=os.getgid(),
        backup_keep_days=7,
        deletion_deadline_days=8,
        security_margin_hours=48,
    )

    writer_receipt = create_writer_attestation(
        writer,
        backup_repository_id=BACKUP_ID,
        journal_repository_ids=ANCHOR_IDS,
    )
    operator_receipt = create_operator_attestation(
        operator,
        backup_repository_id=BACKUP_ID,
    )
    validate_role_separation(writer_receipt, operator_receipt)
    assert ShareDeploymentAttestation.from_bytes(writer_receipt.to_bytes()) == writer_receipt
    assert ShareDeploymentAttestation.from_bytes(operator_receipt.to_bytes()) == operator_receipt
    assert b"/" not in writer_receipt.to_bytes()

    wrong_repository = ShareDeploymentAttestation(
        role="operator",
        deployment_id=operator_receipt.deployment_id,
        backup_repository_id="f" * 64,
        journal_repository_ids=operator_receipt.journal_repository_ids,
        storage_key_proof=operator_receipt.storage_key_proof,
        authority_proofs=operator_receipt.authority_proofs,
    )
    with pytest.raises(ValueError, match="backup repository identities"):
        validate_role_separation(writer_receipt, wrong_repository)

    collapsed_ids = dict(operator_receipt.journal_repository_ids)
    collapsed_ids["backup-node"] = BACKUP_ID
    collapsed_writer = ShareDeploymentAttestation(
        role="writer",
        deployment_id=writer_receipt.deployment_id,
        backup_repository_id=BACKUP_ID,
        journal_repository_ids=collapsed_ids,
        storage_key_proof=writer_receipt.storage_key_proof,
        authority_proofs=writer_receipt.authority_proofs,
    )
    collapsed_operator = ShareDeploymentAttestation(
        role="operator",
        deployment_id=operator_receipt.deployment_id,
        backup_repository_id=BACKUP_ID,
        journal_repository_ids=collapsed_ids,
        storage_key_proof=operator_receipt.storage_key_proof,
        authority_proofs=operator_receipt.authority_proofs,
    )
    with pytest.raises(ValueError, match="primary backup repository"):
        validate_role_separation(collapsed_writer, collapsed_operator)
    with pytest.raises(ValueError, match="attestation"):
        ShareDeploymentAttestation.from_bytes(collapsed_writer.to_bytes())

    recovery_key.write_bytes(b"z" * 32)
    mismatched_key = create_operator_attestation(operator, backup_repository_id=BACKUP_ID)
    with pytest.raises(ValueError, match="recovery key"):
        validate_role_separation(writer_receipt, mismatched_key)

    recovery_key.write_bytes(b"k" * 32)
    operator_repository.write_bytes(b"a" * 32)
    shared_authority = create_operator_attestation(operator, backup_repository_id=BACKUP_ID)
    with pytest.raises(ValueError, match="authority secret"):
        validate_role_separation(writer_receipt, shared_authority)


def test_closed_configs_require_repository_identity_and_replica_bindings(
    tmp_path: Path,
) -> None:
    executable, executable_digest = _restic(tmp_path)
    local_repository = tmp_path / "repository"
    local_repository.mkdir(mode=0o700)
    paths = {
        name: _private(tmp_path / name, bytes([index]) * 32)
        for index, name in enumerate(
            (
                "storage-key",
                "writer-repository",
                "writer-rest",
                "backup-repository",
                "backup-rest",
                "recovery-repository",
                "recovery-rest",
                "recovery-key",
                "operator-repository",
            ),
            start=1,
        )
    }
    writer_path = tmp_path / "writer.toml"
    writer_path.write_text(
        f'''schema_version = 1
role = "writer"
deployment_id = "codemble-production"
active_root = "{tmp_path / 'active'}"
journal_root = "{tmp_path / 'journal'}"
staging_root = "{tmp_path / 'staging'}"
storage_key_file = "{paths['storage-key']}"
restic_cache_root = "{tmp_path / 'writer-cache'}"
restic_executable = "{executable}"
restic_sha256 = "{executable_digest}"
repository = "rest:https://backup.example.test/writer/codemble/"
repository_id = "{BACKUP_ID}"
repository_password_file = "{paths['writer-repository']}"
rest_username = "writer"
rest_password_file = "{paths['writer-rest']}"
backup_interval_minutes = 60
deletion_deadline_days = 8

[journal_anchors.backup-node]
repository = "rest:https://backup.example.test/backup-node/journal/"
repository_id = "{ANCHOR_IDS['backup-node']}"
repository_password_file = "{paths['backup-repository']}"
rest_username = "backup-node"
rest_password_file = "{paths['backup-rest']}"
restic_cache_root = "{tmp_path / 'backup-cache'}"

[journal_anchors.recovery-node]
repository = "rest:https://recovery.example.test/recovery-node/journal/"
repository_id = "{ANCHOR_IDS['recovery-node']}"
repository_password_file = "{paths['recovery-repository']}"
rest_username = "recovery-node"
rest_password_file = "{paths['recovery-rest']}"
restic_cache_root = "{tmp_path / 'recovery-cache'}"
'''
    )
    writer_path.chmod(0o600)
    writer = ShareWriterConfig.load(writer_path)
    assert writer.repository_id == BACKUP_ID
    assert {name: target.repository_id for name, target in writer.journal_anchors.items()} == ANCHOR_IDS

    reused_backup_identity = tmp_path / "writer-reused-backup-identity.toml"
    reused_backup_identity.write_text(
        writer_path.read_text().replace(ANCHOR_IDS["backup-node"], BACKUP_ID)
    )
    reused_backup_identity.chmod(0o600)
    with pytest.raises(ValueError, match="writer configuration"):
        ShareWriterConfig.load(reused_backup_identity)

    reused_backup_target = tmp_path / "writer-reused-backup-target.toml"
    reused_backup_target.write_text(
        writer_path.read_text()
        .replace(
            'repository = "rest:https://backup.example.test/backup-node/journal/"',
            'repository = "rest:https://backup.example.test/writer/codemble/"',
        )
        .replace('rest_username = "backup-node"', 'rest_username = "writer"')
    )
    reused_backup_target.chmod(0o600)
    with pytest.raises(ValueError, match="writer configuration"):
        ShareWriterConfig.load(reused_backup_target)

    reused_authority_path = tmp_path / "writer-reused-authority.toml"
    reused_authority_path.write_text(
        writer_path.read_text().replace(
            str(paths["backup-repository"]),
            str(paths["writer-repository"]),
        )
    )
    reused_authority_path.chmod(0o600)
    with pytest.raises(ValueError, match="writer configuration"):
        ShareWriterConfig.load(reused_authority_path)

    wrong_private_path = tmp_path / "writer-wrong-private-path.toml"
    wrong_private_path.write_text(
        writer_path.read_text().replace(
            "/writer/codemble/",
            "/somebody-else/codemble/",
        )
    )
    wrong_private_path.chmod(0o600)
    with pytest.raises(ValueError, match="writer configuration"):
        ShareWriterConfig.load(wrong_private_path)

    operator_path = tmp_path / "operator.toml"
    operator_path.write_text(
        f'''schema_version = 2
role = "operator"
deployment_id = "codemble-production"
active_root = "{tmp_path / 'active'}"
journal_root = "{tmp_path / 'journal'}"
recovery_key_file = "{paths['recovery-key']}"
restic_cache_root = "{tmp_path / 'operator-cache'}"
restic_executable = "{executable}"
restic_sha256 = "{executable_digest}"
repository = "{local_repository}"
repository_id = "{BACKUP_ID}"
repository_password_file = "{paths['operator-repository']}"
writer_uid = {os.getuid()}
writer_gid = {os.getgid()}
backup_keep_days = 7
deletion_deadline_days = 8
security_margin_hours = 48

[journal_replicas.backup-node]
path = "{tmp_path / 'backup-replica'}"
repository_id = "{ANCHOR_IDS['backup-node']}"

[journal_replicas.recovery-node]
path = "{tmp_path / 'recovery-replica'}"
repository_id = "{ANCHOR_IDS['recovery-node']}"
'''
    )
    operator_path.chmod(0o600)
    operator = ShareOperatorConfig.load(operator_path)
    assert operator.repository_id == BACKUP_ID
    assert {name: binding.repository_id for name, binding in operator.journal_replicas.items()} == ANCHOR_IDS

    root_writer = tmp_path / "operator-root-writer.toml"
    root_writer.write_text(
        operator_path.read_text().replace(
            f"writer_uid = {os.getuid()}",
            "writer_uid = 0",
        )
    )
    root_writer.chmod(0o600)
    with pytest.raises(ValueError, match="operator configuration"):
        ShareOperatorConfig.load(root_writer)

    reused_operator_identity = tmp_path / "operator-reused-backup-identity.toml"
    reused_operator_identity.write_text(
        operator_path.read_text().replace(ANCHOR_IDS["backup-node"], BACKUP_ID)
    )
    reused_operator_identity.chmod(0o600)
    with pytest.raises(ValueError, match="operator configuration"):
        ShareOperatorConfig.load(reused_operator_identity)

    reused_operator_target = tmp_path / "operator-reused-backup-target.toml"
    reused_operator_target.write_text(
        operator_path.read_text().replace(
            str(tmp_path / "backup-replica"),
            str(local_repository),
        )
    )
    reused_operator_target.chmod(0o600)
    with pytest.raises(ValueError, match="operator configuration"):
        ShareOperatorConfig.load(reused_operator_target)

    journal_repository = tmp_path / "journal-repository"
    journal_repository.mkdir(mode=0o700)
    journal_operator_path = tmp_path / "journal-operator.toml"
    journal_operator_path.write_text(
        f'''schema_version = 1
role = "journal-operator"
deployment_id = "codemble-production"
replica_name = "backup-node"
repository = "{journal_repository}"
repository_id = "{ANCHOR_IDS['backup-node']}"
repository_password_file = "{paths['backup-repository']}"
restic_cache_root = "{tmp_path / 'journal-operator-cache'}"
restic_executable = "{executable}"
restic_sha256 = "{executable_digest}"

[replica_ids]
backup-node = "{ANCHOR_IDS['backup-node']}"
recovery-node = "{ANCHOR_IDS['recovery-node']}"
'''
    )
    journal_operator_path.chmod(0o600)
    journal_operator = JournalReplicaOperatorConfig.load(journal_operator_path)
    assert journal_operator.repository == str(journal_repository)
    assert journal_operator.replica_ids == ANCHOR_IDS
