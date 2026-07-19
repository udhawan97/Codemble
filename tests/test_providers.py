"""Provider transports are exercised through injection; no test touches a network."""

import pytest

from codemble.llm.providers import OllamaProvider, ProviderError


def _transport(payload: dict[str, object]):
    def post_json(url: str, headers: dict[str, str], body: dict[str, object]):
        post_json.seen = {"url": url, "headers": headers, "body": body}
        return payload

    return post_json


def test_ollama_returns_the_response_text():
    provider = OllamaProvider(post_json=_transport({"response": "  grounded text  "}))
    assert provider.complete("prompt") == "grounded text"


def test_ollama_posts_to_the_generate_endpoint_without_streaming():
    transport = _transport({"response": "text"})
    provider = OllamaProvider(post_json=transport)
    provider.complete("prompt")
    assert transport.seen["url"] == "http://127.0.0.1:11434/api/generate"
    assert transport.seen["body"]["stream"] is False
    assert transport.seen["body"]["model"] == "gemma4:12b"


def test_ollama_sends_no_credential_header():
    transport = _transport({"response": "text"})
    provider = OllamaProvider(post_json=transport)
    provider.complete("prompt")
    headers = {key.lower(): value for key, value in transport.seen["headers"].items()}
    assert "authorization" not in headers
    assert "x-api-key" not in headers


def test_ollama_rejects_an_empty_response():
    provider = OllamaProvider(post_json=_transport({"response": "   "}))
    with pytest.raises(ProviderError):
        provider.complete("prompt")


def test_ollama_rejects_a_response_without_the_text_field():
    provider = OllamaProvider(post_json=_transport({"unexpected": 1}))
    with pytest.raises(ProviderError):
        provider.complete("prompt")


@pytest.mark.parametrize(
    "host",
    [
        "http://example.com:11434",
        # Substring bypass: naive `"127.0.0.1" in host` checks pass this,
        # since the loopback address is a literal substring of the hostname.
        # The real hostname here is "127.0.0.1.evil.com" — not loopback.
        "http://127.0.0.1.evil.com/",
        # Userinfo bypass: everything before "@" is credentials, not host.
        # The real hostname here is "evil.com".
        "http://127.0.0.1:11434@evil.com/",
    ],
    ids=["remote-host", "loopback-subdomain-suffix", "loopback-userinfo-prefix"],
)
def test_ollama_refuses_a_non_loopback_host(host):
    with pytest.raises(ValueError):
        OllamaProvider(host=host)


@pytest.mark.parametrize("host", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"])
def test_ollama_accepts_loopback_hosts(host):
    provider = OllamaProvider(host=host, post_json=_transport({"response": "text"}))
    assert provider.name == "ollama"
