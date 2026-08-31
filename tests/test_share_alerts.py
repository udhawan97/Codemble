"""Failure alerts remain durable, token-free, and provider-neutral."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codemble.share.alerts import (
    ShareAlertConfig,
    ShareFailureAlert,
    ShareFailureAlertError,
    ShareFailureAlertRelay,
)

NOW = datetime(2026, 8, 30, 12, tzinfo=UTC)


def _private_directory(path: Path) -> Path:
    path.mkdir(mode=0o700)
    return path


def _private_file(path: Path, content: bytes, *, mode: int = 0o600) -> Path:
    path.write_bytes(content)
    path.chmod(mode)
    return path


def _configured(tmp_path: Path) -> tuple[ShareAlertConfig, Path]:
    spool = _private_directory(tmp_path / "alerts")
    _private_directory(spool / "pending")
    _private_directory(spool / "delivered")
    _private_file(spool / ".relay.lock", b"")
    notifier = _private_file(
        tmp_path / "notifier",
        b"#!/bin/sh\ncat > \"$(dirname \"$0\")/notified.json\"\n",
        mode=0o700,
    )
    digest = "sha256:" + hashlib.sha256(notifier.read_bytes()).hexdigest()
    config_path = tmp_path / "share-alert.toml"
    config_path.write_text(
        f'''schema_version = 1
role = "alert-relay"
spool_root = "{spool}"
notifier_executable = "{notifier}"
notifier_sha256 = "{digest}"
'''
    )
    config_path.chmod(0o600)
    return ShareAlertConfig.load(config_path), config_path


def test_relay_persists_exact_token_free_event_before_notifying(tmp_path: Path) -> None:
    config, _ = _configured(tmp_path)
    observed: list[bytes] = []

    def runner(command: tuple[str, ...], encoded: bytes) -> int:
        assert command == (str(config.notifier_executable),)
        pending = config.spool_root / "pending" / "codemble-share-writer.service.json"
        assert pending.read_bytes() == encoded
        observed.append(encoded)
        return 0

    alert = ShareFailureAlertRelay(
        config,
        runner=runner,
        entropy=lambda size: b"a" * size,
    ).relay("codemble-share-writer.service", now=NOW)

    assert alert == ShareFailureAlert(
        event_id="alert-" + "61" * 16,
        occurred_at=NOW,
        unit="codemble-share-writer.service",
    )
    assert observed == [alert.to_bytes()]
    document = json.loads(alert.to_bytes())
    assert document == {
        "event_id": alert.event_id,
        "kind": "service-failure",
        "occurred_at": "2026-08-30T12:00:00Z",
        "schema_version": 1,
        "unit": "codemble-share-writer.service",
    }
    assert not (config.spool_root / "pending" / f"{alert.unit}.json").exists()
    assert (
        config.spool_root / "delivered" / f"{alert.event_id}.json"
    ).read_bytes() == alert.to_bytes()


def test_failed_notifier_keeps_one_pending_event_and_retry_reuses_it(
    tmp_path: Path,
) -> None:
    config, _ = _configured(tmp_path)
    attempts: list[bytes] = []
    return_codes = iter((9, 0))

    def runner(_command: tuple[str, ...], encoded: bytes) -> int:
        attempts.append(encoded)
        return next(return_codes)

    relay = ShareFailureAlertRelay(
        config,
        runner=runner,
        entropy=lambda size: b"b" * size,
    )
    with pytest.raises(ShareFailureAlertError, match="remains pending"):
        relay.relay("codemble-share-operator.service", now=NOW)

    pending = config.spool_root / "pending" / "codemble-share-operator.service.json"
    original = pending.read_bytes()
    alert = relay.relay(
        "codemble-share-operator.service",
        now=NOW + timedelta(hours=1),
    )

    assert attempts == [original, original]
    assert alert.occurred_at == NOW
    assert not pending.exists()
    assert len(tuple((config.spool_root / "delivered").iterdir())) == 1


def test_alert_configuration_and_closed_unit_fail_closed(tmp_path: Path) -> None:
    config, config_path = _configured(tmp_path)
    with pytest.raises(ValueError, match="not monitored"):
        ShareFailureAlertRelay(config).relay("ssh.service", now=NOW)

    config_path.chmod(0o644)
    with pytest.raises(ValueError, match="private owned regular file"):
        ShareAlertConfig.load(config_path)

    config_path.chmod(0o600)
    config.notifier_executable.write_text("#!/bin/sh\nexit 0\n")
    with pytest.raises(ValueError, match="pinned trusted executable"):
        ShareFailureAlertRelay(config).relay(
            "codemble-rest-server.service",
            now=NOW,
        )


def test_delivered_alert_identity_cannot_be_reused_or_renotified(tmp_path: Path) -> None:
    config, _ = _configured(tmp_path)
    notifications = 0

    def runner(_command: tuple[str, ...], _encoded: bytes) -> int:
        nonlocal notifications
        notifications += 1
        return 0

    relay = ShareFailureAlertRelay(
        config,
        runner=runner,
        entropy=lambda size: b"d" * size,
    )
    relay.relay("codemble-share-writer.service", now=NOW)
    with pytest.raises(ShareFailureAlertError, match="identity was reused"):
        relay.relay(
            "codemble-share-writer.service",
            now=NOW + timedelta(hours=1),
        )

    assert notifications == 1
    assert not tuple((config.spool_root / "pending").iterdir())


def test_spool_refuses_open_permissions_and_corrupt_pending_event(
    tmp_path: Path,
) -> None:
    config, _ = _configured(tmp_path)
    (config.spool_root / "pending").chmod(0o755)
    with pytest.raises(ShareFailureAlertError, match="not private"):
        ShareFailureAlertRelay(config).relay(
            "codemble-share-writer.service",
            now=NOW,
        )

    (config.spool_root / "pending").chmod(0o700)
    pending = config.spool_root / "pending" / "codemble-share-writer.service.json"
    _private_file(pending, b'{}\n')
    with pytest.raises(ShareFailureAlertError, match="alert is invalid"):
        ShareFailureAlertRelay(config).relay(
            "codemble-share-writer.service",
            now=NOW,
        )


@pytest.mark.skipif(os.name != "posix", reason="share operations require POSIX")
def test_default_notifier_receives_only_the_closed_event(tmp_path: Path) -> None:
    config, _ = _configured(tmp_path)
    alert = ShareFailureAlertRelay(
        config,
        entropy=lambda size: b"c" * size,
    ).relay("codemble-rest-server.service", now=NOW)

    notified = json.loads((tmp_path / "notified.json").read_bytes())
    assert notified["event_id"] == alert.event_id
    assert notified["unit"] == "codemble-rest-server.service"
    assert set(notified) == {
        "event_id",
        "kind",
        "occurred_at",
        "schema_version",
        "unit",
    }
