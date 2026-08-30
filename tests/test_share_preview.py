"""Exact local share preview and acknowledgement contracts."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
import rfc8785
from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.server.app import create_app
from codemble.server.project_activation import ProjectActivation
from codemble.share import (
    ShareArtifact,
    SharePreviewConfirmationError,
    SharePreviewService,
    UnknownSharePreviewError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CREATED_AT = datetime(2026, 8, 26, 18, 0, tzinfo=UTC)


def _graph(*, understood: bool = False):
    graph = PythonAstAdapter().parse(FIXTURE)
    if not understood:
        return graph
    home_region = graph.regions[0].id
    return replace(
        graph,
        nodes=tuple(
            replace(node, understood=node.region == home_region) for node in graph.nodes
        ),
        regions=tuple(
            replace(region, understood=region.id == home_region)
            for region in graph.regions
        ),
    )


def _service() -> SharePreviewService:
    return SharePreviewService(
        clock=lambda: CREATED_AT,
        preview_id_factory=lambda: "local-preview-one",
    )


def test_preview_returns_the_exact_source_free_artifact_and_exposure_ledger() -> None:
    preview = _service().create(
        _graph(understood=True),
        lifetime_days=7,
        include_labels=False,
        include_understanding=False,
    )

    encoded = preview["artifact_json"].encode()
    document = json.loads(encoded)
    payload_bytes = rfc8785.dumps(document["payload"])

    assert preview["status"] == "preview"
    assert preview["expires_at"] == "2026-09-02T18:00:00Z"
    assert preview["upload_available"] is False
    assert preview["exposure"] == {
        "labels_included": False,
        "label_count": 0,
        "understanding_included": False,
        "understood_regions": 0,
    }
    assert preview["facts"] == {
        "bytes": len(encoded),
        "nodes": len(document["payload"]["nodes"]),
        "regions": len(document["payload"]["regions"]),
    }
    assert preview["payload_digest"] == f"sha256:{sha256(payload_bytes).hexdigest()}"
    assert encoded == rfc8785.dumps(document), "the browser previews the canonical bytes"
    assert str(FIXTURE.resolve()).encode() not in encoded
    assert b"sampleproj" not in encoded
    assert b'"label"' not in encoded
    assert b'"understood"' not in encoded


def test_sensitive_choices_appear_separately_and_require_matching_acknowledgements() -> None:
    service = _service()
    preview = service.create(
        _graph(understood=True),
        lifetime_days=30,
        include_labels=True,
        include_understanding=True,
    )
    exposure = preview["exposure"]

    assert exposure["labels_included"] is True
    assert exposure["label_count"] > 0
    assert exposure["understanding_included"] is True
    assert exposure["understood_regions"] == 1

    with pytest.raises(SharePreviewConfirmationError, match="label acknowledgement"):
        service.confirm(
            preview_id=preview["preview_id"],
            payload_digest=preview["payload_digest"],
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=True,
        )
    with pytest.raises(SharePreviewConfirmationError, match="understanding acknowledgement"):
        service.confirm(
            preview_id=preview["preview_id"],
            payload_digest=preview["payload_digest"],
            reviewed=True,
            labels_confirmed=True,
            understanding_confirmed=False,
        )

    confirmed = service.confirm(
        preview_id=preview["preview_id"],
        payload_digest=preview["payload_digest"],
        reviewed=True,
        labels_confirmed=True,
        understanding_confirmed=True,
    )
    repeated = service.confirm(
        preview_id=preview["preview_id"],
        payload_digest=preview["payload_digest"],
        reviewed=True,
        labels_confirmed=True,
        understanding_confirmed=True,
    )

    assert confirmed == repeated
    assert confirmed["status"] == "confirmed"
    assert confirmed["upload_available"] is False


def test_confirmation_is_bound_to_the_current_preview_id_digest_and_review() -> None:
    ids = iter(("first", "second"))
    service = SharePreviewService(
        clock=lambda: CREATED_AT,
        preview_id_factory=lambda: next(ids),
    )
    first = service.create(
        _graph(),
        lifetime_days=1,
        include_labels=False,
        include_understanding=False,
    )
    second = service.create(
        _graph(),
        lifetime_days=1,
        include_labels=False,
        include_understanding=False,
    )

    with pytest.raises(UnknownSharePreviewError):
        service.confirm(
            preview_id=first["preview_id"],
            payload_digest=first["payload_digest"],
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=False,
        )
    with pytest.raises(SharePreviewConfirmationError, match="Review the exact"):
        service.confirm(
            preview_id=second["preview_id"],
            payload_digest=second["payload_digest"],
            reviewed=False,
            labels_confirmed=False,
            understanding_confirmed=False,
        )
    with pytest.raises(SharePreviewConfirmationError, match="preview changed"):
        service.confirm(
            preview_id=second["preview_id"],
            payload_digest="sha256:not-the-preview",
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=False,
        )


def test_expired_preview_is_cleared_before_confirmation() -> None:
    now = [CREATED_AT]
    service = SharePreviewService(
        clock=lambda: now[0],
        preview_id_factory=lambda: "expiring-preview",
    )
    preview = service.create(
        _graph(),
        lifetime_days=1,
        include_labels=False,
        include_understanding=False,
    )
    now[0] += timedelta(days=1)

    with pytest.raises(UnknownSharePreviewError, match="expired"):
        service.confirm(
            preview_id=preview["preview_id"],
            payload_digest=preview["payload_digest"],
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=False,
        )
    with pytest.raises(UnknownSharePreviewError, match="no longer active"):
        service.confirm(
            preview_id=preview["preview_id"],
            payload_digest=preview["payload_digest"],
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=False,
        )


def test_preview_clock_must_be_timezone_aware() -> None:
    service = SharePreviewService(clock=lambda: CREATED_AT.replace(tzinfo=None))

    with pytest.raises(ValueError, match="timezone-aware"):
        service.create(
            _graph(),
            lifetime_days=1,
            include_labels=False,
            include_understanding=False,
        )


def test_concurrent_creation_publishes_previews_in_request_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_compiling = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    second_compiling = threading.Event()
    call_count = 0
    call_lock = threading.Lock()
    original_from_graph = ShareArtifact.from_graph

    def blocking_from_graph(graph, policy, created_at):  # type: ignore[no-untyped-def]
        nonlocal call_count
        with call_lock:
            call_count += 1
            position = call_count
        if position == 1:
            first_compiling.set()
            assert release_first.wait(timeout=5)
        else:
            second_compiling.set()
        return original_from_graph(graph, policy, created_at)

    monkeypatch.setattr(ShareArtifact, "from_graph", staticmethod(blocking_from_graph))
    ids = iter(("first-preview", "second-preview"))
    service = SharePreviewService(
        clock=lambda: CREATED_AT,
        preview_id_factory=lambda: next(ids),
    )
    graph = _graph()
    results: dict[str, dict[str, object]] = {}

    def create(name: str) -> None:
        if name == "second":
            second_started.set()
        results[name] = service.create(
            graph,
            lifetime_days=7,
            include_labels=False,
            include_understanding=False,
        )

    first = threading.Thread(target=create, args=("first",))
    second = threading.Thread(target=create, args=("second",))
    first.start()
    assert first_compiling.wait(timeout=5)
    second.start()
    assert second_started.wait(timeout=5)
    assert not second_compiling.wait(timeout=0.05), "the newer request must wait its turn"
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert second_compiling.is_set()
    latest = results["second"]
    assert latest["preview_id"] == "second-preview"
    assert service.confirm(
        preview_id=latest["preview_id"],
        payload_digest=latest["payload_digest"],
        reviewed=True,
        labels_confirmed=False,
        understanding_confirmed=False,
    )["status"] == "confirmed"


@pytest.mark.parametrize("lifetime", (0, 2, 31, True, "7"))
def test_preview_lifetime_is_one_of_the_three_declared_choices(lifetime: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _service().create(
            _graph(),
            lifetime_days=lifetime,  # type: ignore[arg-type]
            include_labels=False,
            include_understanding=False,
        )


def test_local_preview_http_flow_is_json_only_no_store_and_has_no_upload_route(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(_graph(understood=True), tmp_path / "missing"))

    response = client.post(
        "/api/share/preview",
        json={
            "lifetime_days": 7,
            "include_labels": True,
            "include_understanding": True,
        },
    )
    preview = response.json()

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert preview["upload_available"] is False
    assert json.loads(preview["artifact_json"])["manifest"]["expires_at"] == preview[
        "expires_at"
    ]
    unknown_field = client.post(
        "/api/share/preview",
        json={
            "lifetime_days": 7,
            "include_labels": False,
            "include_understanding": False,
            "unexpected": "must fail closed",
        },
    )
    assert unknown_field.status_code == 422
    assert unknown_field.headers["cache-control"] == "no-store"
    form_post = client.post(
        "/api/share/preview",
        content="lifetime_days=7",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert form_post.status_code == 422
    assert form_post.headers["cache-control"] == "no-store"
    for coerced_lifetime in (True, 1.0, "1"):
        coerced = client.post(
            "/api/share/preview",
            json={
                "lifetime_days": coerced_lifetime,
                "include_labels": False,
                "include_understanding": False,
            },
        )
        assert coerced.status_code == 422
        assert coerced.headers["cache-control"] == "no-store"

    mismatch = client.post(
        "/api/share/confirm",
        json={
            "preview_id": preview["preview_id"],
            "payload_digest": preview["payload_digest"],
            "reviewed": True,
            "labels_confirmed": False,
            "understanding_confirmed": True,
        },
    )
    assert mismatch.status_code == 409
    assert mismatch.headers["cache-control"] == "no-store"
    malformed_digest = client.post(
        "/api/share/confirm",
        json={
            "preview_id": preview["preview_id"],
            "payload_digest": "not-a-digest",
            "reviewed": True,
            "labels_confirmed": True,
            "understanding_confirmed": True,
        },
    )
    assert malformed_digest.status_code == 422
    assert malformed_digest.headers["cache-control"] == "no-store"
    coerced_review = client.post(
        "/api/share/confirm",
        json={
            "preview_id": preview["preview_id"],
            "payload_digest": preview["payload_digest"],
            "reviewed": 1,
            "labels_confirmed": True,
            "understanding_confirmed": True,
        },
    )
    assert coerced_review.status_code == 422
    assert coerced_review.headers["cache-control"] == "no-store"
    stale = client.post(
        "/api/share/confirm",
        json={
            "preview_id": "missing-preview",
            "payload_digest": preview["payload_digest"],
            "reviewed": True,
            "labels_confirmed": True,
            "understanding_confirmed": True,
        },
    )
    assert stale.status_code == 404
    assert stale.headers["cache-control"] == "no-store"
    confirmed = client.post(
        "/api/share/confirm",
        json={
            "preview_id": preview["preview_id"],
            "payload_digest": preview["payload_digest"],
            "reviewed": True,
            "labels_confirmed": True,
            "understanding_confirmed": True,
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.headers["cache-control"] == "no-store"
    assert confirmed.json()["upload_available"] is False
    missing_upload = client.post("/api/share/upload", json={})
    assert missing_upload.status_code == 404
    assert missing_upload.headers["cache-control"] == "no-store"
    method_error = client.get("/api/share/preview")
    assert method_error.status_code == 405
    assert method_error.headers["cache-control"] == "no-store"


def test_preview_requires_an_active_project(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=tmp_path),
        )
    )

    response = client.post(
        "/api/share/preview",
        json={
            "lifetime_days": 1,
            "include_labels": False,
            "include_understanding": False,
        },
    )
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["detail"] == "No project selected yet."


def test_project_rebind_cannot_reach_the_previous_preview() -> None:
    activation = ProjectActivation(parse_runner=lambda work: work())
    activation.activate(FIXTURE)
    old_project = activation.project()
    preview = old_project.create_share_preview(
        lifetime_days=7,
        include_labels=False,
        include_understanding=False,
    )

    activation.release()
    activation.activate(FIXTURE)
    new_project = activation.project()

    assert new_project is not old_project
    assert new_project.share_previews is not old_project.share_previews
    with pytest.raises(UnknownSharePreviewError):
        old_project.share_previews.confirm(
            preview_id=preview["preview_id"],
            payload_digest=preview["payload_digest"],
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=False,
        )
    with pytest.raises(UnknownSharePreviewError):
        new_project.share_previews.confirm(
            preview_id=preview["preview_id"],
            payload_digest=preview["payload_digest"],
            reviewed=True,
            labels_confirmed=False,
            understanding_confirmed=False,
        )


def test_project_release_invalidates_an_in_flight_preview_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiling = threading.Event()
    finish_compiling = threading.Event()
    original_from_graph = ShareArtifact.from_graph

    def blocking_from_graph(graph, policy, created_at):  # type: ignore[no-untyped-def]
        compiling.set()
        assert finish_compiling.wait(timeout=5)
        return original_from_graph(graph, policy, created_at)

    monkeypatch.setattr(ShareArtifact, "from_graph", staticmethod(blocking_from_graph))
    activation = ProjectActivation(_graph())
    project = activation.project()
    errors: list[BaseException] = []

    def create() -> None:
        try:
            project.create_share_preview(
                lifetime_days=7,
                include_labels=False,
                include_understanding=False,
            )
        except BaseException as error:  # noqa: BLE001 - captured across a test thread
            errors.append(error)

    creator = threading.Thread(target=create)
    creator.start()
    assert compiling.wait(timeout=5)
    released = threading.Event()
    releaser = threading.Thread(target=lambda: (activation.release(), released.set()))
    releaser.start()
    assert not released.wait(timeout=0.05), "release is a barrier for in-flight work"
    finish_compiling.set()
    creator.join(timeout=5)
    releaser.join(timeout=5)

    assert not creator.is_alive()
    assert not releaser.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], UnknownSharePreviewError)
    assert released.is_set()


def test_project_release_invalidates_an_in_flight_confirmation() -> None:
    confirming = threading.Event()
    finish_clock = threading.Event()
    clock_calls = 0

    def blocking_clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        if clock_calls == 2:
            confirming.set()
            assert finish_clock.wait(timeout=5)
        return CREATED_AT

    activation = ProjectActivation(_graph())
    project = activation.project()
    project.share_previews = SharePreviewService(
        clock=blocking_clock,
        preview_id_factory=lambda: "release-race-preview",
    )
    preview = project.create_share_preview(
        lifetime_days=7,
        include_labels=False,
        include_understanding=False,
    )
    errors: list[BaseException] = []

    def confirm() -> None:
        try:
            project.share_previews.confirm(
                preview_id=preview["preview_id"],
                payload_digest=preview["payload_digest"],
                reviewed=True,
                labels_confirmed=False,
                understanding_confirmed=False,
            )
        except BaseException as error:  # noqa: BLE001 - captured across a test thread
            errors.append(error)

    confirmer = threading.Thread(target=confirm)
    confirmer.start()
    assert confirming.wait(timeout=5)
    released = threading.Event()
    releaser = threading.Thread(target=lambda: (activation.release(), released.set()))
    releaser.start()
    assert not released.wait(timeout=0.05), "release is a barrier for confirmation"
    finish_clock.set()
    confirmer.join(timeout=5)
    releaser.join(timeout=5)

    assert not confirmer.is_alive()
    assert not releaser.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], UnknownSharePreviewError)
    assert released.is_set()
