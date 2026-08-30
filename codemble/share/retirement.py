"""Finite security-metadata events that prevent retired shares from returning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ShareRetirementEvent:
    """One token-free terminal fact suitable for an independent append-only anchor."""

    share_id: str
    kind: Literal["revoked", "expired"]
    terminal_at: datetime
    expires_at: datetime
    payload_digest: str

    def __post_init__(self) -> None:
        terminal_at = _aware_utc(self.terminal_at)
        expires_at = _aware_utc(self.expires_at)
        if re.fullmatch(r"s[0-9a-f]{32}", self.share_id) is None:
            raise ValueError("share retirement identity is invalid")
        if self.kind not in ("revoked", "expired"):
            raise ValueError("share retirement kind is invalid")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", self.payload_digest) is None:
            raise ValueError("share retirement payload digest is invalid")
        if (
            (self.kind == "revoked" and terminal_at >= expires_at)
            or (self.kind == "expired" and terminal_at != expires_at)
        ):
            raise ValueError("share retirement time contradicts its kind")

    @property
    def event_id(self) -> str:
        """Stable identity makes recorder retries idempotent."""

        return sha256(self.to_bytes()).hexdigest()

    def to_bytes(self) -> bytes:
        document = {
            "expires_at": _format_time(self.expires_at),
            "kind": self.kind,
            "payload_digest": self.payload_digest,
            "share_id": self.share_id,
            "terminal_at": _format_time(self.terminal_at),
        }
        return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()

    @classmethod
    def from_bytes(cls, encoded: bytes) -> ShareRetirementEvent:
        try:
            document = json.loads(encoded, object_pairs_hook=_unique_object)
            if not isinstance(document, dict) or set(document) != {
                "expires_at",
                "kind",
                "payload_digest",
                "share_id",
                "terminal_at",
            }:
                raise ValueError
            event = cls(
                share_id=document["share_id"],
                kind=document["kind"],
                terminal_at=_parse_time(document["terminal_at"]),
                expires_at=_parse_time(document["expires_at"]),
                payload_digest=document["payload_digest"],
            )
            if event.to_bytes() != encoded:
                raise ValueError
            return event
        except (KeyError, TypeError, ValueError, UnicodeError) as error:
            raise ValueError("share retirement event is outside its closed schema") from error


class ShareRetirementRecorder(Protocol):
    """Append terminal facts idempotently before an operator may unlink records."""

    def record(self, event: ShareRetirementEvent) -> None:
        """Durably anchor one event or raise without acknowledging retirement."""


def _format_time(value: datetime) -> str:
    return _aware_utc(value).isoformat().replace("+00:00", "Z")


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("share retirement times must be timezone-aware")
    return value.astimezone(UTC)


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    return _aware_utc(datetime.fromisoformat(value))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate retirement field")
        result[key] = value
    return result


__all__ = ["ShareRetirementEvent", "ShareRetirementRecorder"]
