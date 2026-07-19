"""Report whether a local Ollama is reachable, for the in-app setup guide."""

from __future__ import annotations

import http.client
import json
from typing import Callable
from urllib import request

from codemble import __version__

RECOMMENDED_MODEL = "gemma4:12b"
FALLBACK_MODEL = "qwen3:8b"

GetJson = Callable[[str], dict]


def ollama_status(
    host: str = "http://127.0.0.1:11434",
    get_json: GetJson | None = None,
) -> dict[str, object]:
    """Return local-model availability without ever raising.

    A missing Ollama is the normal case for most learners, so every failure
    mode here -- connection refused, a timeout, a non-dict body, garbage
    model entries, or a listener that speaks broken/non-HTTP -- resolves to
    ``running: False`` rather than propagating. The setup guide this feeds
    polls it, so it must fail fast, never hang or crash the panel it is meant
    to help populate.
    """

    fetch = get_json or _get_json
    installed: list[str] = []
    running = False
    try:
        payload = fetch(f"{host}/api/tags")
        if not isinstance(payload, dict):
            raise ValueError("Ollama returned an unexpected response shape.")
        models = payload.get("models", [])
        if isinstance(models, list):
            installed = [
                str(entry["name"])
                for entry in models
                if isinstance(entry, dict) and isinstance(entry.get("name"), str)
            ]
        running = True
    except (OSError, ValueError, http.client.HTTPException):
        running = False
    return {
        "running": running,
        "installed_models": installed,
        "recommended": RECOMMENDED_MODEL,
        "fallback": FALLBACK_MODEL,
    }


def _get_json(url: str) -> dict:
    outbound = request.Request(
        url, headers={"user-agent": f"Codemble/{__version__}"}, method="GET"
    )
    with request.urlopen(outbound, timeout=2) as response:  # noqa: S310 - loopback only
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Ollama returned an unexpected shape.")
    return decoded


__all__ = ["FALLBACK_MODEL", "RECOMMENDED_MODEL", "ollama_status"]
