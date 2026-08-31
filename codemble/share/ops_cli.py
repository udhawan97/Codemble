"""Closed operator entrypoint for scheduled share maintenance."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from codemble.share.alerts import ShareAlertConfig, ShareFailureAlertRelay
from codemble.share.operations import (
    JournalReplicaOperatorConfig,
    ResticBackupWriter,
    ResticOperator,
    RestoreGuard,
    RestoreReceipt,
    SecurityMetadataRetirementGuard,
    SecurityMetadataRetirementReceipt,
    ShareDeploymentAttestation,
    ShareOperationsCycleReceipt,
    ShareOperationsRunner,
    ShareOperatorConfig,
    ShareWriterConfig,
    create_operator_attestation,
    create_writer_attestation,
    materialize_journal_replica,
    retire_backup_snapshots,
    validate_role_separation,
)
from codemble.share.persistent_storage import EncryptedSQLiteShareStorage


def writer_cycle(
    config: ShareWriterConfig,
    *,
    now: datetime,
    runner=None,
) -> ShareOperationsCycleReceipt:
    """Run one hourly writer cycle from the least-authority configuration."""

    writer = ResticBackupWriter(
        config.repository,
        config.repository_password_file,
        expected_repository_id=config.repository_id,
        restic_executable=config.restic_executable,
        expected_executable_digest=config.restic_sha256,
        cache_root=config.restic_cache_root,
        rest_username=config.rest_username,
        rest_password_file=config.rest_password_file,
        runner=runner,
    )
    anchors = {
        name: ResticBackupWriter(
            target.repository,
            target.repository_password_file,
            expected_repository_id=target.repository_id,
            restic_executable=config.restic_executable,
            expected_executable_digest=config.restic_sha256,
            cache_root=target.restic_cache_root,
            rest_username=target.rest_username,
            rest_password_file=target.rest_password_file,
            runner=runner,
        )
        for name, target in config.journal_anchors.items()
    }
    return ShareOperationsRunner.run_configured(
        active_root=config.active_root,
        encryption_key=_read_key(config.storage_key_file),
        journal_root=config.journal_root,
        anchors=anchors,
        writer=writer,
        staging_root=config.staging_root,
        now=now,
    )


def operator_maintain(
    config: ShareOperatorConfig,
    *,
    runner=None,
) -> tuple[str, ...]:
    """Run the daily full-data check, seven-day prune, and final inventory."""

    operator = _operator(config, runner=runner)
    operator.full_check()
    operator.forget_and_prune(keep_within=timedelta(days=config.backup_keep_days))
    operator.full_check()
    return operator.snapshot_ids(tags=("codemble-share-backup",))


def operator_list_backups(
    config: ShareOperatorConfig,
    *,
    runner=None,
):
    """Return the authenticated live backup inventory for explicit retirement."""

    return _operator(config, runner=runner).snapshot_inventory(
        tags=("codemble-share-backup",)
    )


def operator_restore(
    config: ShareOperatorConfig,
    *,
    snapshot_id: str,
    quarantine_root: Path,
    rollback: Path | None,
    now: datetime,
    runner=None,
) -> RestoreReceipt:
    """Restore one verified snapshot and replay every later retirement."""

    operator = _operator(config, runner=runner)
    operator.full_check()
    repository_id = operator.repository_identity()
    operator.restore(snapshot_id, quarantine_root)
    return RestoreGuard().verify_and_promote(
        quarantine_root,
        config.active_root,
        encryption_key=_read_key(config.recovery_key_file),
        journal_replicas=config.journal_replicas,
        backup_repository_id=repository_id,
        writer_journal_root=config.journal_root,
        writer_uid=config.writer_uid,
        writer_gid=config.writer_gid,
        now=now,
        rollback=rollback,
    )


def operator_authorize_retirement(
    config: ShareOperatorConfig,
    *,
    now: datetime,
    runner=None,
) -> SecurityMetadataRetirementReceipt:
    """Authorize final key-store retirement from operator-owned live evidence."""

    operator = _operator(config, runner=runner)
    operator.full_check()
    storage = EncryptedSQLiteShareStorage.open_existing(
        config.active_root,
        _read_key(config.recovery_key_file),
    )
    return SecurityMetadataRetirementGuard(
        deletion_deadline=timedelta(days=config.deletion_deadline_days),
        safety_margin=timedelta(hours=config.security_margin_hours),
    ).authorize(
        storage,
        journal_replicas=config.journal_replicas,
        backup_inventory=operator,
        expected_backup_repository_id=config.repository_id,
        now=now,
    )


def operator_retire_backups(
    config: ShareOperatorConfig,
    *,
    snapshot_ids: tuple[str, ...],
    now: datetime,
    runner=None,
):
    """Seal the active store and delete one explicit, authenticated inventory."""

    operator = _operator(config, runner=runner)
    storage = EncryptedSQLiteShareStorage.open_existing(
        config.active_root,
        _read_key(config.recovery_key_file),
    )
    return retire_backup_snapshots(
        storage,
        operator,
        expected_snapshot_ids=tuple(sorted(snapshot_ids)),
        expected_backup_repository_id=config.repository_id,
        now=now,
    )


def materialize_replica(
    config: JournalReplicaOperatorConfig,
    *,
    destination: Path,
    quarantine_root: Path,
    runner=None,
):
    """Restore one independently controlled anchor into local evidence."""

    operator = ResticOperator(
        config.repository,
        config.repository_password_file,
        expected_repository_id=config.repository_id,
        restic_executable=config.restic_executable,
        expected_executable_digest=config.restic_sha256,
        cache_root=config.restic_cache_root,
        runner=runner,
    )
    return materialize_journal_replica(
        operator,
        replica_name=config.replica_name,
        replica_ids=config.replica_ids,
        destination=destination,
        quarantine_root=quarantine_root,
    )


def writer_attestation(
    config: ShareWriterConfig,
    *,
    runner=None,
) -> ShareDeploymentAttestation:
    """Authenticate writer repositories and emit a credential-derived receipt."""

    backup = ResticBackupWriter(
        config.repository,
        config.repository_password_file,
        expected_repository_id=config.repository_id,
        restic_executable=config.restic_executable,
        expected_executable_digest=config.restic_sha256,
        cache_root=config.restic_cache_root,
        rest_username=config.rest_username,
        rest_password_file=config.rest_password_file,
        runner=runner,
    )
    anchor_ids = {}
    for name, target in config.journal_anchors.items():
        anchor = ResticBackupWriter(
            target.repository,
            target.repository_password_file,
            expected_repository_id=target.repository_id,
            restic_executable=config.restic_executable,
            expected_executable_digest=config.restic_sha256,
            cache_root=target.restic_cache_root,
            rest_username=target.rest_username,
            rest_password_file=target.rest_password_file,
            runner=runner,
        )
        anchor_ids[name] = anchor.repository_identity()
    return create_writer_attestation(
        config,
        backup_repository_id=backup.repository_identity(),
        journal_repository_ids=anchor_ids,
    )


def operator_attestation(
    config: ShareOperatorConfig,
    *,
    runner=None,
) -> ShareDeploymentAttestation:
    """Authenticate the operator repository and emit its credential-derived receipt."""

    return create_operator_attestation(
        config,
        backup_repository_id=_operator(config, runner=runner).repository_identity(),
    )


def _operator(config: ShareOperatorConfig, *, runner=None) -> ResticOperator:
    return ResticOperator(
        config.repository,
        config.repository_password_file,
        expected_repository_id=config.repository_id,
        restic_executable=config.restic_executable,
        expected_executable_digest=config.restic_sha256,
        cache_root=config.restic_cache_root,
        runner=runner,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codemble share-ops",
        description="Run bounded Codemble share backup maintenance.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "writer-cycle",
        "writer-attest",
        "operator-maintain",
        "operator-list-backups",
        "operator-attest",
        "operator-authorize-retirement",
    ):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
    restore = commands.add_parser("operator-restore")
    restore.add_argument("--config", type=Path, required=True)
    restore.add_argument("--snapshot-id", required=True)
    restore.add_argument("--quarantine", type=Path, required=True)
    restore.add_argument("--rollback", type=Path)
    retirement = commands.add_parser("operator-retire-backups")
    retirement.add_argument("--config", type=Path, required=True)
    retirement.add_argument("--snapshot-id", action="append", default=[])
    retirement.add_argument("--confirm-empty-inventory", action="store_true")
    materialize = commands.add_parser("operator-materialize-journal")
    materialize.add_argument("--config", type=Path, required=True)
    materialize.add_argument("--destination", type=Path, required=True)
    materialize.add_argument("--quarantine", type=Path, required=True)
    validation = commands.add_parser("validate-deployment")
    validation.add_argument("--writer-attestation", type=Path, required=True)
    validation.add_argument("--operator-attestation", type=Path, required=True)
    alert = commands.add_parser("relay-failure")
    alert.add_argument("--config", type=Path, required=True)
    alert.add_argument("--unit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "writer-cycle":
            receipt = writer_cycle(
                ShareWriterConfig.load(arguments.config),
                now=datetime.now(UTC),
            )
            output = {
                "expired": receipt.purge.expired,
                "deleted": receipt.purge.deleted,
                "manifest_digest": receipt.backup.manifest_digest,
                "snapshot_id": receipt.backup.snapshot_id,
                "validated_records": receipt.validated_records,
            }
        elif arguments.command == "writer-attest":
            output = json.loads(
                writer_attestation(ShareWriterConfig.load(arguments.config)).to_bytes()
            )
        elif arguments.command == "operator-maintain":
            inventory = operator_maintain(ShareOperatorConfig.load(arguments.config))
            output = {"share_backup_snapshots": len(inventory)}
        elif arguments.command == "operator-list-backups":
            inventory = operator_list_backups(
                ShareOperatorConfig.load(arguments.config)
            )
            output = {
                "backup_repository_id": inventory.repository_id,
                "snapshot_ids": list(inventory.snapshot_ids),
            }
        elif arguments.command == "operator-attest":
            output = json.loads(
                operator_attestation(ShareOperatorConfig.load(arguments.config)).to_bytes()
            )
        elif arguments.command == "operator-restore":
            receipt = operator_restore(
                ShareOperatorConfig.load(arguments.config),
                snapshot_id=arguments.snapshot_id,
                quarantine_root=arguments.quarantine,
                rollback=arguments.rollback,
                now=datetime.now(UTC),
            )
            output = {
                "journal_sequence": receipt.journal_head.sequence,
                "replayed_retirements": receipt.replayed_retirements,
                "restored": True,
            }
        elif arguments.command == "operator-authorize-retirement":
            receipt = operator_authorize_retirement(
                ShareOperatorConfig.load(arguments.config),
                now=datetime.now(UTC),
            )
            output = {
                "authorized": True,
                "journal_sequence": receipt.journal_head.sequence,
                "retirement_events": receipt.retirement_events,
                "seal_epoch": receipt.seal_epoch,
                "backup_repository_id": receipt.backup_repository_id,
                "inventory_digest": receipt.inventory_digest,
            }
        elif arguments.command == "operator-retire-backups":
            if bool(arguments.snapshot_id) == arguments.confirm_empty_inventory:
                raise ValueError(
                    "choose snapshot IDs or explicitly confirm an empty inventory"
                )
            receipt = operator_retire_backups(
                ShareOperatorConfig.load(arguments.config),
                snapshot_ids=tuple(sorted(arguments.snapshot_id)),
                now=datetime.now(UTC),
            )
            output = {
                "backup_repository_id": receipt.repository_id,
                "removed_snapshots": len(receipt.removed_snapshot_ids),
                "seal_epoch": receipt.seal_epoch,
            }
        elif arguments.command == "operator-materialize-journal":
            head = materialize_replica(
                JournalReplicaOperatorConfig.load(arguments.config),
                destination=arguments.destination,
                quarantine_root=arguments.quarantine,
            )
            output = {
                "journal_digest": head.digest,
                "journal_sequence": head.sequence,
                "materialized": True,
            }
        elif arguments.command == "relay-failure":
            alert = ShareFailureAlertRelay(
                ShareAlertConfig.load(arguments.config)
            ).relay(arguments.unit, now=datetime.now(UTC))
            output = {
                "alert_event_id": alert.event_id,
                "alerted": True,
                "unit": alert.unit,
            }
        else:
            validate_role_separation(
                ShareDeploymentAttestation.from_bytes(
                    arguments.writer_attestation.read_bytes()
                ),
                ShareDeploymentAttestation.from_bytes(
                    arguments.operator_attestation.read_bytes()
                ),
            )
            output = {"valid": True}
    except (OSError, RuntimeError, ValueError):
        print("codemble share-ops: operation failed; inspect the private operator log", file=sys.stderr)
        return 2
    print(json.dumps(output, separators=(",", ":"), sort_keys=True))
    return 0


def _read_key(path: Path) -> bytes:
    encoded = path.read_bytes()
    if len(encoded) != 32:
        raise ValueError("share storage key file must contain exactly 32 raw bytes")
    return encoded


__all__ = [
    "main",
    "materialize_replica",
    "operator_attestation",
    "operator_authorize_retirement",
    "operator_list_backups",
    "operator_maintain",
    "operator_restore",
    "operator_retire_backups",
    "writer_attestation",
    "writer_cycle",
]


if __name__ == "__main__":
    raise SystemExit(main())
