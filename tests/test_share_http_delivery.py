"""HTTPS/browser delivery contracts for immutable private share artifacts."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.share import (
    InMemoryShareLifecycleLog,
    InMemoryShareStorage,
    ShareArtifact,
    ShareDelivery,
    ShareLifecycleEvent,
    SharePolicy,
    StoredShare,
    StructuredShareLifecycleLog,
    create_share_delivery_app,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CREATED_AT = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
VIEW_SECRET = bytes([1]) * 32
DELETE_SECRET = bytes([2]) * 32


def _artifact(
    *,
    lifetime: timedelta = timedelta(days=7),
    hostile_label: bool = False,
    include_understanding: bool = True,
) -> ShareArtifact:
    graph = PythonAstAdapter().parse(FIXTURE)
    if hostile_label:
        first, *rest = graph.nodes
        graph = replace(
            graph,
            nodes=(
                replace(first, name='</style><script>window.pwned="yes"</script>'),
                *rest,
            ),
        )
    return ShareArtifact.from_graph(
        graph,
        SharePolicy(
            expires_at=CREATED_AT + lifetime,
            include_labels=True,
            include_understanding=include_understanding,
        ),
        CREATED_AT,
    )


def _delivery(
    *,
    clock=lambda: CREATED_AT,
    lifecycle_log=None,
) -> tuple[ShareDelivery, InMemoryShareLifecycleLog | None]:
    memory_log = InMemoryShareLifecycleLog() if lifecycle_log is None else None
    values = iter((VIEW_SECRET, DELETE_SECRET))
    return (
        ShareDelivery(
            InMemoryShareStorage(),
            lifecycle_log or memory_log,
            clock=clock,
            entropy=lambda size: next(values),
        ),
        memory_log,
    )


def _client(delivery: ShareDelivery) -> TestClient:
    return TestClient(
        create_share_delivery_app(delivery, allowed_hosts=("share.example",)),
        base_url="https://share.example",
    )


def _assert_private_headers(response) -> None:
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "style-src 'sha256-" in csp
    assert "unsafe-inline" not in csp


def test_https_view_is_static_context_encoded_no_store_and_no_referrer() -> None:
    delivery, lifecycle_log = _delivery()
    grant = delivery.create(_artifact(hostile_label=True))

    response = _client(delivery).get(f"/v/{grant.view_capability}")

    assert response.status_code == 200
    _assert_private_headers(response)
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert grant.view_capability not in response.text
    assert grant.delete_capability not in response.text
    assert "<script" not in response.text.casefold()
    assert "<form" not in response.text.casefold()
    assert "<iframe" not in response.text.casefold()
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text
    assert "serviceWorker" not in response.text
    assert "http://" not in response.text
    assert "https://" not in response.text
    assert "&lt;/style&gt;&lt;script&gt;window.pwned=&quot;yes&quot;&lt;/script&gt;" in response.text
    assert "Anyone with this link can view and copy this snapshot" in response.text
    assert "Not understood" in response.text
    assert "Not shared" not in response.text
    assert lifecycle_log is not None
    assert [event.outcome for event in lifecycle_log.events] == ["created", "viewed"]


def test_omitted_understanding_never_renders_understanding_status() -> None:
    delivery, _ = _delivery()
    grant = delivery.create(_artifact(include_understanding=False))

    response = _client(delivery).get(f"/v/{grant.view_capability}")

    assert response.status_code == 200
    assert "Understanding</strong><span>Omitted" in response.text
    assert "Understood" not in response.text
    assert "Not understood" not in response.text


def test_invalid_expired_and_revoked_views_are_uniform() -> None:
    invalid_delivery, _ = _delivery()
    invalid = _client(invalid_delivery).get("/v/not-a-capability")

    now = [CREATED_AT]
    expired_delivery, _ = _delivery(clock=lambda: now[0])
    expired_grant = expired_delivery.create(_artifact(lifetime=timedelta(days=1)))
    now[0] += timedelta(days=1)
    expired = _client(expired_delivery).get(f"/v/{expired_grant.view_capability}")

    revoked_delivery, _ = _delivery()
    revoked_grant = revoked_delivery.create(_artifact())
    revoked_delivery.revoke(revoked_grant.delete_capability, confirmed=True)
    revoked = _client(revoked_delivery).get(f"/v/{revoked_grant.view_capability}")

    assert [(item.status_code, item.text) for item in (invalid, expired, revoked)] == [
        (404, invalid.text),
        (404, invalid.text),
        (404, invalid.text),
    ]
    for response in (invalid, expired, revoked):
        _assert_private_headers(response)


@pytest.mark.parametrize(
    "mutation",
    ("share-id", "payload-digest", "artifact", "orbit"),
)
def test_tampered_views_match_the_uniform_not_found_response(mutation: str) -> None:
    class TamperingStorage(InMemoryShareStorage):
        def read(self, view_lookup: str, now: datetime) -> StoredShare | None:
            record = super().read(view_lookup, now)
            assert record is not None and record.artifact is not None
            if mutation == "share-id":
                return replace(record, share_id="invalid")
            if mutation == "payload-digest":
                return replace(record, payload_digest="sha256:" + "0" * 64)
            document = json.loads(record.artifact)
            if mutation == "orbit":
                document["payload"]["nodes"][0]["system_orbit"]["ring"] += 1
            else:
                document["payload"]["unexpected"] = True
            return replace(record, artifact=json.dumps(document).encode())

    values = iter((VIEW_SECRET, DELETE_SECRET))
    lifecycle_log = InMemoryShareLifecycleLog()
    delivery = ShareDelivery(
        TamperingStorage(),
        lifecycle_log,
        clock=lambda: CREATED_AT,
        entropy=lambda size: next(values),
    )
    grant = delivery.create(_artifact())
    expected_delivery, _ = _delivery()
    expected = _client(expected_delivery).get("/v/not-a-capability")

    response = _client(delivery).get(f"/v/{grant.view_capability}")

    assert (response.status_code, response.text) == (expected.status_code, expected.text)
    _assert_private_headers(response)
    assert lifecycle_log.events[-1].share_id is None
    assert lifecycle_log.events[-1].outcome == "integrity_error"


def test_revocation_uses_header_authority_exact_json_and_never_get() -> None:
    delivery, _ = _delivery()
    grant = delivery.create(_artifact())
    client = _client(delivery)

    inert_get = client.get(
        "/revoke",
        headers={"Authorization": f"Bearer {grant.delete_capability}"},
    )
    assert inert_get.status_code == 405
    assert client.get(f"/v/{grant.view_capability}").status_code == 200

    for response in (
        client.post("/revoke", json={"confirmed": True}),
        client.post(
            "/revoke",
            headers={"Authorization": f"Bearer {grant.delete_capability}"},
            content='{"confirmed":true,"confirmed":true}',
        ),
        client.post(
            "/revoke",
            headers={"Authorization": f"Bearer {grant.delete_capability}"},
            json={"confirmed": True, "unexpected": True},
        ),
    ):
        assert response.status_code == 400
        _assert_private_headers(response)

    for invalid_confirmation in (1, 1.0, "true", None, False, [], {}):
        response = client.post(
            "/revoke",
            headers={"Authorization": f"Bearer {grant.delete_capability}"},
            json={"confirmed": invalid_confirmation},
        )
        assert response.status_code == 400
        _assert_private_headers(response)
        assert client.get(f"/v/{grant.view_capability}").status_code == 200

    first = client.post(
        "/revoke",
        headers={"Authorization": f"Bearer {grant.delete_capability}"},
        json={"confirmed": True},
    )
    repeated = client.post(
        "/revoke",
        headers={"Authorization": f"Bearer {grant.delete_capability}"},
        json={"confirmed": True},
    )

    assert first.json()["status"] == "revoked"
    assert repeated.json()["status"] == "already_revoked"
    assert first.json()["payload_digest"] == grant.payload_digest
    assert grant.delete_capability not in first.text + repeated.text
    assert client.get(f"/v/{grant.view_capability}").status_code == 404


def test_insecure_wrong_host_query_and_unknown_routes_refuse_without_redirects() -> None:
    delivery, _ = _delivery()
    grant = delivery.create(_artifact())
    app = create_share_delivery_app(delivery, allowed_hosts=("share.example",))
    insecure = TestClient(app, base_url="http://share.example").get(
        f"/v/{grant.view_capability}",
        follow_redirects=False,
    )
    wrong_host = TestClient(app, base_url="https://wrong.example").get(
        f"/v/{grant.view_capability}",
        follow_redirects=False,
    )
    query = _client(delivery).get(
        f"/v/{grant.view_capability}?secret=must-not-survive",
        follow_redirects=False,
    )
    unknown = _client(delivery).get("/anything", follow_redirects=False)

    assert [response.status_code for response in (insecure, wrong_host, query, unknown)] == [
        400,
        400,
        404,
        404,
    ]
    assert all("location" not in response.headers for response in (insecure, wrong_host, query))
    for response in (insecure, wrong_host, query, unknown):
        _assert_private_headers(response)


def test_asgi_scope_redacts_path_query_and_authorization_before_response() -> None:
    delivery, _ = _delivery()
    grant = delivery.create(_artifact())
    app = create_share_delivery_app(delivery, allowed_hosts=("share.example",))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/revoke",
        "raw_path": b"/revoke",
        "query_string": b"",
        "headers": [
            (b"host", b"share.example"),
            (b"content-type", b"application/json"),
            (b"authorization", f"Bearer {grant.delete_capability}".encode()),
        ],
    }
    messages = iter(({"type": "http.request", "body": b'{"confirmed":true}'},))
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))

    assert scope["query_string"] == b""
    assert all(name != b"authorization" for name, _ in scope["headers"])
    assert grant.delete_capability.encode() not in repr(scope).encode()
    assert sent[0]["status"] == 200

    view_scope = {
        **scope,
        "method": "GET",
        "path": f"/v/{grant.view_capability}",
        "raw_path": f"/v/{grant.view_capability}".encode(),
        "query_string": b"target=must-not-survive",
        "headers": [(b"host", b"share.example")],
    }
    view_sent = []

    async def view_receive():
        return {"type": "http.request", "body": b""}

    async def view_send(message):
        view_sent.append(message)

    asyncio.run(app(view_scope, view_receive, view_send))
    assert view_scope["path"] == "/v/[redacted]"
    assert view_scope["raw_path"] == b"/v/[redacted]"
    assert grant.view_capability not in repr(view_scope)
    assert view_sent[0]["status"] == 404

    for secret_path in (
        f"/anything/{grant.view_capability}",
        f"/revoke/{grant.delete_capability}",
    ):
        unknown_scope = {
            **scope,
            "method": "GET",
            "path": secret_path,
            "raw_path": secret_path.encode(),
            "headers": [(b"host", b"share.example")],
        }
        unknown_sent = []

        async def unknown_send(message, sink=unknown_sent):
            sink.append(message)

        asyncio.run(app(unknown_scope, view_receive, unknown_send))
        assert unknown_scope["path"] == "/[redacted]"
        assert unknown_scope["raw_path"] == b"/[redacted]"
        assert grant.view_capability not in repr(unknown_scope)
        assert grant.delete_capability not in repr(unknown_scope)
        assert unknown_sent[0]["status"] == 404


def test_structured_lifecycle_log_has_only_allowlisted_token_free_fields() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("test-share-lifecycle")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(logging.StreamHandler(stream))
    delivery, _ = _delivery(lifecycle_log=StructuredShareLifecycleLog(logger))
    artifact = _artifact()
    grant = delivery.create(artifact)
    delivery.view(grant.view_capability)
    delivery.revoke(grant.delete_capability, confirmed=True)

    documents = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [document["outcome"] for document in documents] == [
        "created",
        "viewed",
        "revoked",
    ]
    assert all(
        set(document) == {"operation", "outcome", "occurred_at", "share_id"}
        for document in documents
    )
    rendered = stream.getvalue()
    assert grant.view_capability not in rendered
    assert grant.delete_capability not in rendered
    assert artifact.to_bytes().decode() not in rendered
    assert "/v/" not in rendered

    with pytest.raises(ValueError, match="invalid operation or outcome"):
        StructuredShareLifecycleLog(logger).record(
            ShareLifecycleEvent(
                share_id=None,
                occurred_at=CREATED_AT,
                operation="raw-target",  # type: ignore[arg-type]
                outcome="created",
            )
        )


def test_unexpected_storage_failure_keeps_headers_and_logs_no_exception_text(caplog) -> None:
    class ExplodingStorage(InMemoryShareStorage):
        failure_message: str | None = None

        def read(self, view_lookup: str, now: datetime):
            if self.failure_message is not None:
                raise RuntimeError(self.failure_message)
            return super().read(view_lookup, now)

    storage = ExplodingStorage()
    values = iter((VIEW_SECRET, DELETE_SECRET))
    delivery = ShareDelivery(
        storage,
        InMemoryShareLifecycleLog(),
        clock=lambda: CREATED_AT,
        entropy=lambda size: next(values),
    )
    grant = delivery.create(_artifact())
    storage.failure_message = grant.view_capability

    with caplog.at_level(logging.ERROR, logger="codemble.share.http"):
        response = _client(delivery).get(f"/v/{grant.view_capability}")

    assert response.status_code == 500
    _assert_private_headers(response)
    assert grant.view_capability not in response.text
    assert grant.view_capability not in caplog.text
    assert "Share delivery failed after bearer-target redaction" in caplog.text


def test_delivery_app_requires_exact_host_configuration() -> None:
    delivery, _ = _delivery()
    for hosts in ((), ("*",), (" https://share.example",), ("share.example/path",)):
        try:
            create_share_delivery_app(delivery, allowed_hosts=hosts)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe host configuration accepted: {hosts!r}")
