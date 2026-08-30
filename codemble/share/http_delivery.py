"""Token-redacted HTTPS delivery for immutable read-only share artifacts."""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from html import escape
from typing import Any, Literal

from codemble.share.delivery import (
    ShareDelivery,
    ShareRevocationConfirmationError,
    ShareStorageIntegrityError,
    UnknownShareCapabilityError,
)

_MAX_REQUEST_BODY_BYTES = 128
_VIEW_PREFIX = "/v/"
_REDACTED_VIEW_PATH = "/v/[redacted]"
_REVOKE_PATH = "/revoke"
_REDACTED_UNKNOWN_PATH = "/[redacted]"
_VIEWER_STYLE = """
:root{color-scheme:dark;background:#07131f;color:#f4efe4;font-family:system-ui,sans-serif}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#17384d 0,#07131f 42rem);min-height:100vh}
main{width:min(72rem,calc(100% - 2rem));margin:auto;padding:3rem 0 5rem}header{border-block:1px solid #3c6f82;padding:1.5rem 0;margin-bottom:2rem}
h1,h2{font-family:ui-serif,Georgia,serif;letter-spacing:.02em}h1{font-size:clamp(2rem,6vw,4rem);margin:.35rem 0}.eyebrow{color:#7fd4ee;text-transform:uppercase;letter-spacing:.16em;font-size:.78rem}
.warning{max-width:52rem;color:#f0c873}.ledger,.coverage,.regions{display:grid;gap:1rem}.ledger,.coverage{grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));margin:1.5rem 0}
.card,.region{border:1px solid #31596b;background:#0b1e2c;padding:1rem}.card strong,.meta{display:block;color:#9db6c1;font-size:.8rem;text-transform:uppercase;letter-spacing:.08em}.card span{font-size:1.2rem}
.regions{grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),1fr))}.region h2{margin:.2rem 0}.region ul{padding-left:1.2rem}.region li{margin:.65rem 0}.tag{display:inline-block;border:1px solid #3c6f82;padding:.12rem .45rem;margin:.2rem .3rem .2rem 0;color:#b7d7e2;font-size:.75rem}
footer{margin-top:2rem;border-top:1px solid #31596b;padding-top:1rem;color:#9db6c1;font-size:.85rem;overflow-wrap:anywhere}@media(max-width:32rem){main{width:min(100% - 1rem,72rem);padding-top:1rem}.region{padding:.8rem}}
""".strip()
_STYLE_HASH = base64.b64encode(sha256(_VIEWER_STYLE.encode()).digest()).decode("ascii")
_CSP = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "connect-src 'none'; "
    "font-src 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "img-src 'none'; "
    "object-src 'none'; "
    "script-src 'none'; "
    f"style-src 'sha256-{_STYLE_HASH}'"
)
_SECURITY_HEADERS = (
    (b"cache-control", b"no-store, max-age=0"),
    (b"content-security-policy", _CSP.encode("ascii")),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"expires", b"0"),
    (b"permissions-policy", b"camera=(), geolocation=(), microphone=(), payment=()"),
    (b"pragma", b"no-cache"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"x-robots-tag", b"noindex, nofollow, noarchive"),
)

AsgiMessage = dict[str, Any]
AsgiReceive = Callable[[], Awaitable[AsgiMessage]]
AsgiSend = Callable[[AsgiMessage], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class _Request:
    route: Literal["view", "revoke", "unknown"]
    method: str
    scheme: str
    host: str | None
    query_present: bool
    view_capability: str | None
    delete_capability: str | None
    content_type: str | None


class _DuplicateField(ValueError):
    pass


class _ShareDeliveryApplication:
    """One ASGI owner for redaction, authorization, rendering, and headers."""

    def __init__(self, delivery: ShareDelivery, allowed_hosts: tuple[str, ...]) -> None:
        self._delivery = delivery
        self._allowed_hosts = frozenset(host.casefold() for host in allowed_hosts)
        self._logger = logging.getLogger("codemble.share.http")

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: AsgiReceive,
        send: AsgiSend,
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._lifespan(receive, send)
            return
        if scope_type != "http":
            await send({"type": "websocket.close", "code": 1008})
            return

        request = _redact_request(scope)
        response_started = False

        async def tracked_send(message: AsgiMessage) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._dispatch(request, receive, tracked_send)
        except Exception:
            self._logger.error("Share delivery failed after bearer-target redaction")
            if response_started:
                raise
            await _respond(tracked_send, 500, _error_page("Share unavailable."))

    async def _dispatch(
        self,
        request: _Request,
        receive: AsgiReceive,
        send: AsgiSend,
    ) -> None:
        if request.scheme != "https" or request.host not in self._allowed_hosts:
            await _respond(send, 400, _error_page("Request refused."))
            return
        if request.query_present:
            await _respond(send, 404, _error_page("Share not found."))
            return
        if request.route == "view":
            await self._view(request, send)
            return
        if request.route == "revoke":
            await self._revoke(request, receive, send)
            return
        await _respond(send, 404, _error_page("Not found."))

    async def _view(self, request: _Request, send: AsgiSend) -> None:
        if request.method != "GET":
            await _respond(
                send,
                405,
                _error_page("Method not allowed."),
                extra_headers=((b"allow", b"GET"),),
            )
            return
        assert request.view_capability is not None
        try:
            artifact = self._delivery.view(request.view_capability)
        except (UnknownShareCapabilityError, ShareStorageIntegrityError):
            await _respond(send, 404, _error_page("Share not found."))
            return
        await _respond(send, 200, _render_artifact(artifact))

    async def _revoke(
        self,
        request: _Request,
        receive: AsgiReceive,
        send: AsgiSend,
    ) -> None:
        if request.method != "POST":
            await _respond(
                send,
                405,
                _json_bytes({"detail": "Method not allowed."}),
                content_type=b"application/json; charset=utf-8",
                extra_headers=((b"allow", b"POST"),),
            )
            return
        if request.content_type != "application/json" or request.delete_capability is None:
            await _respond(
                send,
                400,
                _json_bytes({"detail": "Request refused."}),
                content_type=b"application/json; charset=utf-8",
            )
            return
        body = await _read_body(receive)
        if body is None:
            await _respond(
                send,
                413,
                _json_bytes({"detail": "Request refused."}),
                content_type=b"application/json; charset=utf-8",
            )
            return
        try:
            document = json.loads(body, object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateField):
            document = None
        if (
            not isinstance(document, dict)
            or set(document) != {"confirmed"}
            or document["confirmed"] is not True
        ):
            await _respond(
                send,
                400,
                _json_bytes({"detail": "Explicit confirmation is required."}),
                content_type=b"application/json; charset=utf-8",
            )
            return
        try:
            revocation = self._delivery.revoke(
                request.delete_capability,
                confirmed=True,
            )
        except (
            ShareRevocationConfirmationError,
            ShareStorageIntegrityError,
            UnknownShareCapabilityError,
        ):
            await _respond(
                send,
                404,
                _json_bytes({"detail": "Share not found."}),
                content_type=b"application/json; charset=utf-8",
            )
            return
        await _respond(
            send,
            200,
            _json_bytes(
                {
                    "expires_at": _timestamp(revocation.expires_at),
                    "payload_digest": revocation.payload_digest,
                    "status": revocation.status,
                }
            ),
            content_type=b"application/json; charset=utf-8",
        )

    @staticmethod
    async def _lifespan(receive: AsgiReceive, send: AsgiSend) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


def create_share_delivery_app(
    delivery: ShareDelivery,
    *,
    allowed_hosts: tuple[str, ...],
) -> _ShareDeliveryApplication:
    """Build a standalone viewer with no upload route, provider, or shared state."""

    if not isinstance(delivery, ShareDelivery):
        raise TypeError("delivery must be a ShareDelivery")
    if not allowed_hosts:
        raise ValueError("share delivery requires at least one exact allowed Host")
    for host in allowed_hosts:
        if (
            not isinstance(host, str)
            or not host
            or host != host.strip()
            or any(character in host for character in ("*", "/", "\\", "@"))
            or any(ord(character) > 127 for character in host)
        ):
            raise ValueError("share delivery hosts must be exact ASCII Host values")
    return _ShareDeliveryApplication(delivery, allowed_hosts)


def _redact_request(scope: dict[str, Any]) -> _Request:
    path = scope.get("path") if isinstance(scope.get("path"), str) else ""
    method = scope.get("method") if isinstance(scope.get("method"), str) else ""
    scheme = scope.get("scheme") if isinstance(scope.get("scheme"), str) else ""
    query_present = bool(scope.get("query_string"))
    raw_headers = scope.get("headers") if isinstance(scope.get("headers"), list) else []
    headers = [(bytes(name).lower(), bytes(value)) for name, value in raw_headers]

    host_values = [value for name, value in headers if name == b"host"]
    host_value = _ascii(host_values[0]) if len(host_values) == 1 else None
    host = host_value.casefold() if host_value is not None else None
    content_types = [value for name, value in headers if name == b"content-type"]
    content_type = None
    if len(content_types) == 1:
        raw_content_type = _ascii(content_types[0])
        if raw_content_type is not None:
            content_type = raw_content_type.partition(";")[0].strip().casefold()

    view_capability = None
    delete_capability = None
    route: Literal["view", "revoke", "unknown"] = "unknown"
    if path.startswith(_VIEW_PREFIX):
        candidate = path.removeprefix(_VIEW_PREFIX)
        if candidate and "/" not in candidate:
            route = "view"
            view_capability = candidate
        scope["path"] = _REDACTED_VIEW_PATH
        scope["raw_path"] = _REDACTED_VIEW_PATH.encode("ascii")
    elif path == _REVOKE_PATH:
        route = "revoke"
        scope["path"] = _REVOKE_PATH
        scope["raw_path"] = _REVOKE_PATH.encode("ascii")
    else:
        scope["path"] = _REDACTED_UNKNOWN_PATH
        scope["raw_path"] = _REDACTED_UNKNOWN_PATH.encode("ascii")

    authorizations = [value for name, value in headers if name == b"authorization"]
    if route == "revoke" and len(authorizations) == 1:
        authorization = _ascii(authorizations[0])
        if authorization is not None and authorization.startswith("Bearer "):
            candidate = authorization.removeprefix("Bearer ")
            if candidate and candidate == candidate.strip():
                delete_capability = candidate
    scope["headers"] = [(name, value) for name, value in headers if name != b"authorization"]
    scope["query_string"] = b""
    return _Request(
        route=route,
        method=method,
        scheme=scheme,
        host=host,
        query_present=query_present,
        view_capability=view_capability,
        delete_capability=delete_capability,
        content_type=content_type,
    )


async def _read_body(receive: AsgiReceive) -> bytes | None:
    chunks = bytearray()
    while True:
        message = await receive()
        if message.get("type") == "http.disconnect":
            return None
        if message.get("type") != "http.request":
            continue
        chunk = message.get("body", b"")
        if not isinstance(chunk, bytes):
            return None
        chunks.extend(chunk)
        if len(chunks) > _MAX_REQUEST_BODY_BYTES:
            return None
        if not message.get("more_body", False):
            return bytes(chunks)


async def _respond(
    send: AsgiSend,
    status: int,
    body: bytes,
    *,
    content_type: bytes = b"text/html; charset=utf-8",
    extra_headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    headers = (
        _SECURITY_HEADERS
        + ((b"content-type", content_type), (b"content-length", str(len(body)).encode("ascii")))
        + extra_headers
    )
    await send({"type": "http.response.start", "status": status, "headers": list(headers)})
    await send({"type": "http.response.body", "body": body})


def _render_artifact(artifact: bytes) -> bytes:
    document = json.loads(artifact)
    manifest = document["manifest"]
    payload = document["payload"]
    coverage = manifest["coverage"]
    labels_included = payload["labels_included"]
    understanding_included = payload["understanding_included"]
    nodes_by_region: dict[str, list[Mapping[str, object]]] = {}
    for node in payload["nodes"]:
        nodes_by_region.setdefault(node["region_id"], []).append(node)

    region_cards: list[str] = []
    for region_index, region in enumerate(payload["regions"], start=1):
        region_id = region["id"]
        region_label = region.get("label") if labels_included else None
        title = region_label if isinstance(region_label, str) else f"Region {region_index}"
        status = "Understood" if region.get("understood") is True else "Not understood"
        node_rows: list[str] = []
        for node_index, node in enumerate(nodes_by_region.get(region_id, ()), start=1):
            node_label = node.get("label") if labels_included else None
            node_title = (
                node_label if isinstance(node_label, str) else f"Structure {node_index}"
            )
            facts = [
                _tag(node["kind"]),
                _tag(node["language"]),
                _tag(f"{node['loc']} lines"),
            ]
            if node.get("entrypoint") is True:
                facts.append(_tag("Home"))
            if node.get("partial") is True:
                facts.append(_tag("Partial source"))
            if understanding_included and node.get("understood") is True:
                facts.append(_tag("Understood"))
            node_rows.append(f"<li><strong>{_text(node_title)}</strong><br>{''.join(facts)}</li>")
        understanding = (
            f'<span class="tag">{status}</span>' if understanding_included else ""
        )
        structure_tag = _tag(f"{region['node_count']} structures")
        region_cards.append(
            "<article class=\"region\">"
            f'<span class="meta">{_text(region["language"])} · {_text(region["loc"])} lines</span>'
            f"<h2>{_text(title)}</h2>"
            f"{structure_tag}{understanding}"
            f"<ul>{''.join(node_rows)}</ul>"
            "</article>"
        )

    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta name=\"referrer\" content=\"no-referrer\">"
        "<meta name=\"robots\" content=\"noindex,nofollow,noarchive\">"
        "<title>Private Codemble snapshot</title>"
        f"<style>{_VIEWER_STYLE}</style></head><body><main>"
        "<header><span class=\"eyebrow\">Read-only private snapshot</span>"
        "<h1>Codemble share</h1>"
        "<p class=\"warning\">Anyone with this link can view and copy this snapshot. "
        f"It expires at {_text(manifest['expires_at'])}.</p></header>"
        "<section aria-labelledby=\"exposure-title\"><h2 id=\"exposure-title\">Exposure ledger</h2>"
        "<div class=\"ledger\">"
        f"{_metric('Labels', 'Included' if labels_included else 'Omitted')}"
        f"{_metric('Understanding', 'Included' if understanding_included else 'Omitted')}"
        f"{_metric('Routes', str(len(payload['region_edges'])))}"
        "</div></section>"
        "<section aria-labelledby=\"coverage-title\"><h2 id=\"coverage-title\">Parser coverage</h2>"
        "<div class=\"coverage\">"
        f"{_metric('Source files', coverage['source_files'])}"
        f"{_metric('Structures', coverage['nodes'])}"
        f"{_metric('Regions', coverage['regions'])}"
        f"{_metric('Partial sources', coverage['partial_sources'])}"
        "</div></section>"
        "<section aria-labelledby=\"regions-title\"><h2 id=\"regions-title\">Structural snapshot</h2>"
        f"<div class=\"regions\">{''.join(region_cards)}</div></section>"
        "<footer>Raw source, paths, hashes, checks, narration, provider state, visits, "
        f"recents, and logs are excluded. Artifact seal: {_text(manifest['payload_digest'])}</footer>"
        "</main></body></html>"
    )
    return html.encode("utf-8")


def _error_page(message: str) -> bytes:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta name=\"referrer\" content=\"no-referrer\">"
        f"<title>{_text(message)}</title><style>{_VIEWER_STYLE}</style></head>"
        f"<body><main><header><span class=\"eyebrow\">Codemble share</span><h1>{_text(message)}</h1>"
        "<p>This private snapshot is unavailable.</p></header></main></body></html>"
    ).encode()


def _metric(label: object, value: object) -> str:
    return f'<div class="card"><strong>{_text(label)}</strong><span>{_text(value)}</span></div>'


def _tag(value: object) -> str:
    return f'<span class="tag">{_text(value)}</span>'


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _json_bytes(document: Mapping[str, object]) -> bytes:
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _ascii(value: bytes) -> str | None:
    try:
        return value.decode("ascii")
    except UnicodeDecodeError:
        return None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateField(key)
        result[key] = value
    return result
