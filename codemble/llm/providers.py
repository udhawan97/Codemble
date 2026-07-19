"""Direct BYO-key narration adapters for the supported external providers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Protocol
from urllib import error, request

JsonObject = dict[str, object]
PostJson = Callable[[str, dict[str, str], JsonObject], JsonObject]


class ProviderError(RuntimeError):
    """A provider request failed without exposing credentials or response bodies."""


class NarrationProvider(Protocol):
    """The transport seam used by the study module."""

    name: str
    model: str

    def complete(self, prompt: str) -> str:
        """Return the provider's text response for one grounded prompt."""


@dataclass(slots=True)
class AnthropicProvider:
    """Anthropic Messages adapter using the user's key directly."""

    api_key: str
    model: str = "claude-sonnet-5"
    post_json: PostJson = field(default_factory=lambda: _post_json, repr=False)
    name: str = field(default="anthropic", init=False)

    def complete(self, prompt: str) -> str:
        payload = self.post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "x-api-key": self.api_key,
            },
            {
                "model": self.model,
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        content = payload.get("content")
        if not isinstance(content, list):
            raise ProviderError("Anthropic returned no text content.")
        text = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        if not text:
            raise ProviderError("Anthropic returned an empty text response.")
        return text


@dataclass(slots=True)
class OpenAIProvider:
    """OpenAI Responses adapter using the user's key directly."""

    api_key: str
    model: str = "gpt-5.4-mini"
    post_json: PostJson = field(default_factory=lambda: _post_json, repr=False)
    name: str = field(default="openai", init=False)

    def complete(self, prompt: str) -> str:
        payload = self.post_json(
            "https://api.openai.com/v1/responses",
            {
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            {
                "model": self.model,
                "input": prompt,
                "max_output_tokens": 1200,
                "store": False,
            },
        )
        output = payload.get("output")
        if not isinstance(output, list):
            raise ProviderError("OpenAI returned no output items.")
        text_parts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            text_parts.extend(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "output_text"
            )
        text = "".join(text_parts).strip()
        if not text:
            raise ProviderError("OpenAI returned an empty text response.")
        return text


def _post_json(url: str, headers: dict[str, str], payload: JsonObject) -> JsonObject:
    encoded = json.dumps(payload).encode("utf-8")
    outbound = request.Request(
        url,
        data=encoded,
        headers={**headers, "user-agent": "Codemble/0.0.1"},
        method="POST",
    )
    try:
        with request.urlopen(outbound, timeout=60) as response:  # noqa: S310 - fixed HTTPS URLs
            decoded = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as provider_error:
        raise ProviderError(
            f"The provider rejected the request with HTTP {provider_error.code}."
        ) from provider_error
    except (error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("The provider request could not be completed safely.") from exc
    if not isinstance(decoded, dict):
        raise ProviderError("The provider returned an unexpected response shape.")
    return decoded


__all__ = [
    "AnthropicProvider",
    "NarrationProvider",
    "OpenAIProvider",
    "ProviderError",
]
