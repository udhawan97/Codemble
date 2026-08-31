"""Production share-operations CLI compositions stay executable."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from codemble.share.ops_cli import main
from codemble.share.persistent_storage import EncryptedSQLiteShareStorage

BACKUP_ID = "a" * 64
ANCHOR_IDS = {"backup-node": "b" * 64, "recovery-node": "c" * 64}


def _private(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _restic(
    path: Path,
    repository_id: str,
    *,
    reject_rest_credentials: bool,
) -> tuple[Path, str]:
    credential_check = (
        '[ -z "${RESTIC_REST_USERNAME:-}" ] && [ -z "${RESTIC_REST_PASSWORD:-}" ]'
        if reject_rest_credentials
        else '[ -n "${RESTIC_REST_USERNAME:-}" ] && [ -n "${RESTIC_REST_PASSWORD:-}" ]'
    )
    path.write_text(
        "#!/bin/sh\n"
        f"{credential_check} || exit 9\n"
        'case "${RESTIC_REPOSITORY:-}" in\n'
        f"  *backup-node*) repository_id='{ANCHOR_IDS['backup-node']}' ;;\n"
        f"  *recovery-node*) repository_id='{ANCHOR_IDS['recovery-node']}' ;;\n"
        f"  *) repository_id='{repository_id}' ;;\n"
        "esac\n"
        'if [ "$1" = "cat" ] && [ "$2" = "config" ]; then\n'
        "  printf '{\"id\":\"%s\"}' \"$repository_id\"\n"
        'elif [ "$1" = "backup" ]; then\n'
        "  printf '%s\\n' '{\"message_type\":\"summary\",\"snapshot_id\":\"abc123\"}'\n"
        'elif [ "$1" = "snapshots" ]; then\n'
        "  printf '%s' '[]'\n"
        "fi\n"
    )
    path.chmod(0o700)
    return path, "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _operator_config(tmp_path: Path, active_root: Path) -> tuple[Path, Path]:
    executable, executable_digest = _restic(
        tmp_path / "restic-operator",
        BACKUP_ID,
        reject_rest_credentials=True,
    )
    repository = tmp_path / "backup-repository"
    repository.mkdir(mode=0o700)
    recovery_key = _private(tmp_path / "recovery-key", b"k" * 32)
    repository_key = _private(tmp_path / "operator-repository-key", b"o" * 32)
    config = tmp_path / "operator.toml"
    config.write_text(
        f'''schema_version = 2
role = "operator"
deployment_id = "codemble-production"
active_root = "{active_root}"
journal_root = "{tmp_path / 'journal'}"
recovery_key_file = "{recovery_key}"
restic_cache_root = "{tmp_path / 'operator-cache'}"
restic_executable = "{executable}"
restic_sha256 = "{executable_digest}"
repository = "{repository}"
repository_id = "{BACKUP_ID}"
repository_password_file = "{repository_key}"
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
    config.chmod(0o600)
    return config, recovery_key


def test_writer_cycle_public_command_passes_primary_rest_credentials(
    tmp_path: Path,
    capsys,
) -> None:
    executable, executable_digest = _restic(
        tmp_path / "restic-writer",
        BACKUP_ID,
        reject_rest_credentials=False,
    )
    paths = {
        name: _private(tmp_path / name, bytes([index]) * 32)
        for index, name in enumerate(
            (
                "storage-key",
                "writer-repository-key",
                "writer-rest-password",
                "backup-repository-key",
                "backup-rest-password",
                "recovery-repository-key",
                "recovery-rest-password",
            ),
            start=1,
        )
    }
    config = tmp_path / "writer.toml"
    config.write_text(
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
repository_password_file = "{paths['writer-repository-key']}"
rest_username = "writer"
rest_password_file = "{paths['writer-rest-password']}"
backup_interval_minutes = 60
deletion_deadline_days = 8

[journal_anchors.backup-node]
repository = "rest:https://backup.example.test/backup-node/journal/"
repository_id = "{ANCHOR_IDS['backup-node']}"
repository_password_file = "{paths['backup-repository-key']}"
rest_username = "backup-node"
rest_password_file = "{paths['backup-rest-password']}"
restic_cache_root = "{tmp_path / 'backup-cache'}"

[journal_anchors.recovery-node]
repository = "rest:https://recovery.example.test/recovery-node/journal/"
repository_id = "{ANCHOR_IDS['recovery-node']}"
repository_password_file = "{paths['recovery-repository-key']}"
rest_username = "recovery-node"
rest_password_file = "{paths['recovery-rest-password']}"
restic_cache_root = "{tmp_path / 'recovery-cache'}"
'''
    )
    config.chmod(0o600)

    assert main(("writer-cycle", "--config", str(config))) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["snapshot_id"] == "abc123"
    assert output["validated_records"] == 0


def test_journal_materialization_public_command_uses_only_local_authority(
    tmp_path: Path,
    capsys,
) -> None:
    executable, executable_digest = _restic(
        tmp_path / "restic-journal-operator",
        ANCHOR_IDS["backup-node"],
        reject_rest_credentials=True,
    )
    repository = tmp_path / "journal-repository"
    repository.mkdir(mode=0o700)
    repository_key = _private(tmp_path / "journal-repository-key", b"j" * 32)
    config = tmp_path / "journal-operator.toml"
    config.write_text(
        f'''schema_version = 1
role = "journal-operator"
deployment_id = "codemble-production"
replica_name = "backup-node"
repository = "{repository}"
repository_id = "{ANCHOR_IDS['backup-node']}"
repository_password_file = "{repository_key}"
restic_cache_root = "{tmp_path / 'journal-cache'}"
restic_executable = "{executable}"
restic_sha256 = "{executable_digest}"

[replica_ids]
backup-node = "{ANCHOR_IDS['backup-node']}"
recovery-node = "{ANCHOR_IDS['recovery-node']}"
'''
    )
    config.chmod(0o600)
    destination = tmp_path / "materialized"
    quarantine = tmp_path / "quarantine"

    assert (
        main(
            (
                "operator-materialize-journal",
                "--config",
                str(config),
                "--destination",
                str(destination),
                "--quarantine",
                str(quarantine),
            )
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "journal_digest": "sha256:" + "0" * 64,
        "journal_sequence": 0,
        "materialized": True,
    }
    assert destination.is_dir()
    assert not quarantine.exists()


def test_empty_inventory_retirement_is_an_explicit_public_command(
    tmp_path: Path,
    capsys,
) -> None:
    active_root = tmp_path / "active"
    config, recovery_key = _operator_config(tmp_path, active_root)
    EncryptedSQLiteShareStorage(active_root, recovery_key.read_bytes())

    assert (
        main(
            (
                "operator-retire-backups",
                "--config",
                str(config),
                "--confirm-empty-inventory",
            )
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["removed_snapshots"] == 0
    assert EncryptedSQLiteShareStorage(
        active_root,
        recovery_key.read_bytes(),
    ).retirement_seal() is not None


def test_retirement_refuses_to_create_and_seal_a_shadow_store(
    tmp_path: Path,
) -> None:
    active_root = tmp_path / "missing-application-store"
    config, _recovery_key = _operator_config(tmp_path, active_root)

    assert (
        main(
            (
                "operator-retire-backups",
                "--config",
                str(config),
                "--confirm-empty-inventory",
            )
        )
        == 2
    )
    assert not active_root.exists()


def test_failure_alert_public_command_uses_pinned_local_notifier(
    tmp_path: Path,
    capsys,
) -> None:
    spool = tmp_path / "alerts"
    spool.mkdir(mode=0o700)
    (spool / "pending").mkdir(mode=0o700)
    (spool / "delivered").mkdir(mode=0o700)
    _private(spool / ".relay.lock", b"")
    notifier = tmp_path / "alert-notifier"
    notifier.write_text(
        "#!/bin/sh\n"
        f"cat > '{tmp_path / 'relayed-alert.json'}'\n"
    )
    notifier.chmod(0o700)
    notifier_digest = "sha256:" + hashlib.sha256(notifier.read_bytes()).hexdigest()
    config = tmp_path / "share-alert.toml"
    config.write_text(
        f'''schema_version = 1
role = "alert-relay"
spool_root = "{spool}"
notifier_executable = "{notifier}"
notifier_sha256 = "{notifier_digest}"
'''
    )
    config.chmod(0o600)

    assert (
        main(
            (
                "relay-failure",
                "--config",
                str(config),
                "--unit",
                "codemble-share-writer.service",
            )
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["alerted"] is True
    assert output["unit"] == "codemble-share-writer.service"
    assert output["alert_event_id"].startswith("alert-")
    relayed = json.loads((tmp_path / "relayed-alert.json").read_bytes())
    assert relayed["event_id"] == output["alert_event_id"]
    assert set(relayed) == {
        "event_id",
        "kind",
        "occurred_at",
        "schema_version",
        "unit",
    }
