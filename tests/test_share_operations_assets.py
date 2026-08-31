"""Deployment templates preserve the selected free least-authority topology."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1] / "ops" / "share"


def test_writer_and_operator_templates_keep_schedules_and_authority_separate() -> None:
    writer_service = (ROOT / "codemble-share-writer.service").read_text()
    writer_timer = (ROOT / "codemble-share-writer.timer").read_text()
    operator_service = (ROOT / "codemble-share-operator.service").read_text()
    operator_timer = (ROOT / "codemble-share-operator.timer").read_text()
    tmpfiles = (ROOT / "codemble-share-tmpfiles.conf").read_text()
    writer_config = (ROOT / "share-writer.toml.example").read_text()
    operator_config = (ROOT / "share-operator.toml.example").read_text()
    journal_operator_config = (ROOT / "share-journal-operator.toml.example").read_text()
    alert_service = (ROOT / "codemble-share-alert@.service").read_text()
    alert_tmpfiles = (ROOT / "codemble-share-alert-tmpfiles.conf").read_text()
    alert_config = (ROOT / "share-alert.toml.example").read_text()

    assert "writer-cycle" in writer_service
    assert "OnCalendar=hourly" in writer_timer
    assert "Persistent=true" in writer_timer
    assert "operator-maintain" in operator_service
    assert "OnFailure=codemble-share-alert@%n.service" in writer_service
    assert "OnFailure=codemble-share-alert@%n.service" in operator_service
    assert "relay-failure" in alert_service
    assert "Restart=on-failure" in alert_service
    assert "RestartSec=5m" in alert_service
    assert "User=root" in alert_service
    assert "ReadWritePaths=/var/lib/codemble/share-alerts" in alert_service
    assert "0700 root root" in alert_tmpfiles
    assert ".relay.lock 0600 root root" in alert_tmpfiles
    assert 'role = "alert-relay"' in alert_config
    assert 'notifier_executable = "/usr/local/libexec/codemble-share-alert"' in alert_config
    assert "User=root" in operator_service
    assert "Group=codemble-share" in operator_service
    assert "Group=codemble-share" in writer_service
    assert "ReadWritePaths=/var/lib/codemble/share " in operator_service
    assert "d /var/lib/codemble/share 0750 root codemble-share -" in tmpfiles
    assert (
        "d /var/lib/codemble/share/active 0700 "
        "codemble-share codemble-share -"
    ) in tmpfiles
    assert (
        "d /var/lib/codemble/share/retirement-journal 0700 "
        "codemble-share codemble-share -"
    ) in tmpfiles
    assert (
        "d /var/lib/codemble/share/backup-staging 0700 "
        "codemble-share codemble-share -"
    ) in tmpfiles
    assert (
        "f /var/lib/codemble/share/.active.share-operations.lock "
        "0660 root codemble-share -"
    ) in tmpfiles
    assert "OnCalendar=daily" in operator_timer
    assert "role = \"writer\"" in writer_config
    assert "operator" not in writer_config
    assert "[journal_anchors.backup-node]" in writer_config
    assert "[journal_anchors.recovery-node]" in writer_config
    assert "deployment_id" in writer_config
    assert writer_config.count("repository_id") == 3
    assert "role = \"operator\"" in operator_config
    assert "schema_version = 2" in operator_config
    assert "writer_uid = 0 # REPLACE_WITH_OUTPUT_OF" in operator_config
    assert "writer_gid = 0 # REPLACE_WITH_OUTPUT_OF" in operator_config
    assert "rest_password_file" not in operator_config
    assert "journal_root" in operator_config
    assert "[journal_replicas.backup-node]" in operator_config
    assert "path =" in operator_config
    assert "role = \"journal-operator\"" in journal_operator_config
    assert "[replica_ids]" in journal_operator_config
    assert "rest_password_file" not in journal_operator_config
    assert 'repository = "/srv/codemble-restic/' in journal_operator_config
    writer_document = tomllib.loads(writer_config)
    authority_paths = [
        writer_document["repository_password_file"],
        writer_document["rest_password_file"],
        *(
            credential
            for anchor in writer_document["journal_anchors"].values()
            for credential in (
                anchor["repository_password_file"],
                anchor["rest_password_file"],
            )
        ),
    ]
    assert len(set(authority_paths)) == len(authority_paths)


def test_backup_node_is_append_only_over_tls_and_operator_is_local() -> None:
    rest_server = (ROOT / "codemble-rest-server.service").read_text()
    caddy = (ROOT / "Caddyfile.example").read_text()
    operator_config = (ROOT / "share-operator.toml.example").read_text()
    runbook = (ROOT / "README.md").read_text()

    assert "--append-only" in rest_server
    assert "OnFailure=codemble-share-alert@%n.service" in rest_server
    assert "--private-repos" in rest_server
    assert "127.0.0.1:8040" in rest_server
    assert "reverse_proxy 127.0.0.1:8040" in caddy
    assert 'repository = "/mnt/codemble-restic/codemble-writer/codemble"' in operator_config
    assert "root-only operator runs on the application host" in runbook
    assert "backup machine never receives" in runbook
    assert "independently controlled backup machine" in runbook.replace("\n", " ")
    assert "Caddy" in runbook and "restic" in runbook and "rest-server" in runbook
    assert "actual independent-node restore drill" in runbook
    assert "operator-restore" in runbook
    assert "operator-materialize-journal" in runbook
    assert "operator-retire-backups" in runbook
    assert "operator-list-backups" in runbook
    assert "writer-attest" in runbook and "operator-attest" in runbook
    assert "operator-authorize-retirement" in runbook
    assert "validate-deployment" in runbook
