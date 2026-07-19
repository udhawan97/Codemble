"""Provider transports are exercised through injection; no test touches a network."""

import pytest

from codemble.llm.local_status import ollama_status
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


@pytest.mark.parametrize(
    "host",
    [
        # Scheme bypass: the hostname allowlist matches "localhost"/"127.0.0.1"
        # regardless of scheme. `urlopen` on a `file://` URL ignores method="POST"
        # and data=, and instead returns the raw bytes of a local file — turning
        # this into arbitrary local file disclosure into the narration pipeline.
        "file://localhost",
        "file://127.0.0.1",
        # Not file://, but still not the plain HTTP loopback Ollama actually speaks.
        "https://127.0.0.1:11434",
        # Schemeless (e.g. the bare `OLLAMA_HOST` format Ollama itself documents):
        # urlsplit parses no netloc here, so hostname is None too, but the scheme
        # check is what must fail this closed, not an accidental hostname miss.
        "127.0.0.1:11434",
    ],
    ids=["file-scheme-localhost", "file-scheme-loopback-ip", "https-scheme", "schemeless"],
)
def test_ollama_refuses_a_non_http_scheme(host):
    with pytest.raises(ValueError):
        OllamaProvider(host=host)


def test_ollama_host_cannot_be_reassigned_after_construction():
    provider = OllamaProvider(post_json=_transport({"response": "text"}))
    with pytest.raises(AttributeError):
        provider.host = "http://evil.example"


def test_status_lists_installed_models_when_ollama_is_running():
    def get_json(url: str):
        assert url == "http://127.0.0.1:11434/api/tags"
        return {"models": [{"name": "gemma4:12b"}, {"name": "qwen3:8b"}]}

    status = ollama_status(get_json=get_json)
    assert status["running"] is True
    assert status["installed_models"] == ["gemma4:12b", "qwen3:8b"]
    assert status["recommended"] == "gemma4:12b"
    assert status["fallback"] == "qwen3:8b"


def test_status_reports_not_running_without_raising():
    def get_json(url: str):
        raise OSError("connection refused")

    status = ollama_status(get_json=get_json)
    assert status["running"] is False
    assert status["installed_models"] == []


def test_status_reports_not_running_for_a_non_dict_body():
    # A learner could point CODEMBLE at something on 11434 that isn't Ollama
    # at all; the body might parse as JSON but not be a JSON object.
    def get_json(url: str):
        return ["not", "a", "dict"]

    status = ollama_status(get_json=get_json)
    assert status["running"] is False
    assert status["installed_models"] == []


def test_status_skips_malformed_model_entries_without_raising():
    def get_json(url: str):
        return {
            "models": [
                {"name": "gemma4:12b"},
                {"no_name_field": "oops"},
                "not-a-dict-entry",
                {"name": 12345},
                None,
            ]
        }

    status = ollama_status(get_json=get_json)
    assert status["running"] is True
    assert status["installed_models"] == ["gemma4:12b"]
