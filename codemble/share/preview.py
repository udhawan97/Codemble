"""Hold one exact local share artifact through explicit exposure confirmation."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from codemble.adapters.base import Graph
from codemble.share.artifact import ShareArtifact, SharePolicy
from codemble.share.interpretation import ShareArtifactDocument, interpret_share_artifact

_ALLOWED_LIFETIME_DAYS = frozenset((1, 7, 30))
_PREVIEW_ID_BYTES = 24


class UnknownSharePreviewError(LookupError):
    """The local preview no longer belongs to the active project."""


class SharePreviewConfirmationError(ValueError):
    """The acknowledgement does not match the exact previewed artifact."""


@dataclass(frozen=True, slots=True)
class _PreviewRecord:
    preview_id: str
    artifact: ShareArtifact
    interpretation: ShareArtifactDocument
    expires_at: datetime
    confirmed: bool = False


class SharePreviewService:
    """Own one in-memory preview; replacement invalidates the older candidate."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        preview_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._preview_id_factory = preview_id_factory or (
            lambda: token_urlsafe(_PREVIEW_ID_BYTES)
        )
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._current: _PreviewRecord | None = None

    def close(self) -> None:
        """Invalidate this project's preview boundary, including in-flight work."""

        # Signal outside the compilation lock so a project reset can invalidate
        # a slow create/confirm immediately. Taking the lock afterwards makes
        # close() a barrier: when it returns, no earlier operation can publish
        # or confirm a candidate and no retained bytes remain reachable.
        self._closed.set()
        with self._lock:
            self._current = None

    def create(
        self,
        graph: Graph,
        *,
        lifetime_days: int,
        include_labels: bool,
        include_understanding: bool,
    ) -> dict[str, object]:
        """Compile and retain the exact bytes the learner is about to review."""

        if (
            isinstance(lifetime_days, bool)
            or not isinstance(lifetime_days, int)
            or lifetime_days not in _ALLOWED_LIFETIME_DAYS
        ):
            raise ValueError("share lifetime must be 1, 7, or 30 days")
        if not isinstance(include_labels, bool) or not isinstance(
            include_understanding, bool
        ):
            raise TypeError("share disclosure choices must be booleans")
        # Creation is intentionally serialized. Artifact compilation can be
        # slow for a large graph, and publishing outside this lock lets an
        # older request finish after a newer one and replace bytes the learner
        # is already reviewing. The lock makes completion order match request
        # admission order; the newest returned preview is always current.
        with self._lock:
            self._ensure_open()
            created_at = self._now()
            expires_at = created_at + timedelta(days=lifetime_days)
            artifact = ShareArtifact.from_graph(
                graph,
                SharePolicy(
                    expires_at=expires_at,
                    include_labels=include_labels,
                    include_understanding=include_understanding,
                ),
                created_at,
            )
            encoded = artifact.to_bytes()
            interpretation = interpret_share_artifact(encoded)
            # Compilation is the long-running part. A project release may have
            # invalidated this service while it was in progress.
            self._ensure_open()
            preview_id = self._preview_id_factory()
            if not isinstance(preview_id, str) or not preview_id or len(preview_id) > 256:
                raise RuntimeError("share preview identity must be a bounded string")
            record = _PreviewRecord(
                preview_id=preview_id,
                artifact=artifact,
                interpretation=interpretation,
                expires_at=expires_at,
            )
            self._current = record
        return _preview_response(record)

    def confirm(
        self,
        *,
        preview_id: str,
        payload_digest: str,
        reviewed: bool,
        labels_confirmed: bool,
        understanding_confirmed: bool,
    ) -> dict[str, object]:
        """Bind acknowledgement to the retained bytes; perform no upload."""

        with self._lock:
            self._ensure_open()
            record = self._current
            if record is None or record.preview_id != preview_id:
                raise UnknownSharePreviewError("That local share preview is no longer active.")
            now = self._now()
            # A test clock may block, and a project reset is allowed to close
            # the service while it does. Never complete confirmation afterward.
            self._ensure_open()
            if now >= record.expires_at:
                self._current = None
                raise UnknownSharePreviewError("That local share preview has expired.")
            manifest = record.interpretation.manifest
            facts = record.interpretation.facts
            expected_digest = facts.payload_digest
            if reviewed is not True:
                raise SharePreviewConfirmationError(
                    "Review the exact local artifact before confirming it."
                )
            if payload_digest != expected_digest:
                raise SharePreviewConfirmationError(
                    "The preview changed; build and review it again."
                )
            if labels_confirmed is not facts.labels_included:
                raise SharePreviewConfirmationError(
                    "The label acknowledgement does not match this preview."
                )
            if understanding_confirmed is not facts.understanding_included:
                raise SharePreviewConfirmationError(
                    "The understanding acknowledgement does not match this preview."
                )
            if not record.confirmed:
                record = replace(record, confirmed=True)
                self._current = record
        return {
            "status": "confirmed",
            "preview_id": record.preview_id,
            "payload_digest": expected_digest,
            "expires_at": manifest["expires_at"],
            "upload_available": False,
        }

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise TypeError("share preview clock must return a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("share preview clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    def _ensure_open(self) -> None:
        if self._closed.is_set():
            raise UnknownSharePreviewError(
                "That local share preview belongs to a released project."
            )


def _preview_response(record: _PreviewRecord) -> dict[str, object]:
    manifest = record.interpretation.manifest
    facts = record.interpretation.facts
    return {
        "status": "preview",
        "preview_id": record.preview_id,
        "payload_digest": manifest["payload_digest"],
        "created_at": manifest["created_at"],
        "expires_at": manifest["expires_at"],
        "artifact_json": record.artifact.to_bytes().decode("utf-8"),
        "facts": {
            "bytes": facts.byte_length,
            "nodes": facts.node_count,
            "regions": facts.region_count,
        },
        "exposure": {
            "labels_included": facts.labels_included,
            "label_count": facts.label_count,
            "understanding_included": facts.understanding_included,
            "understood_regions": facts.understood_region_count,
        },
        "confirmed": record.confirmed,
        "upload_available": False,
    }


__all__ = [
    "SharePreviewConfirmationError",
    "SharePreviewService",
    "UnknownSharePreviewError",
]
