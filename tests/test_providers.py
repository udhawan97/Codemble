"""Provider transports use injected responses and disposable loopback listeners."""

import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from codemble.llm.local_status import ollama_status
from codemble.llm.providers import OllamaProvider, ProviderError


@pytest.mark.parametrize("proxy_variable", ["http_proxy", "HTTP_PROXY"])
def test_local_transport_ignores_ambient_proxy_before_import(proxy_variable):
    """Both local endpoints bypass an ambient proxy, including on failure."""
    requests = {"local": [], "unavailable": [], "proxy": []}

    def handler(destination):
        class Listener(BaseHTTPRequestHandler):
            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def respond(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                requests[destination].append((self.path, body))
                payload = json.dumps({"response": "fictional text", "models": []}).encode()
                self.send_response(503 if destination == "unavailable" else 200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        return Listener

    servers = [
        ThreadingHTTPServer(("127.0.0.1", 0), handler(destination))
        for destination in requests
    ]
    threads = [
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        for server in servers
    ]
    for thread in threads:
        thread.start()
    local, unavailable, proxy = [
        f"http://127.0.0.1:{server.server_port}" for server in servers
    ]
    # A controlled HTTP failure completes immediately on every platform.
    # A bound-but-not-listening socket can instead wait for network timeouts.
    env = {key: value for key, value in os.environ.items() if "proxy" not in key.lower()}
    env.update({proxy_variable: proxy, "no_proxy": "", "NO_PROXY": ""})
    env.pop("REQUEST_METHOD", None)
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from codemble.llm.providers import OllamaProvider, ProviderRejectedError
from codemble.llm.local_status import ollama_status
assert OllamaProvider(host=sys.argv[1]).complete('fictional prompt') == 'fictional text'
assert ollama_status(host=sys.argv[1])['running'] is True
assert ollama_status(host=sys.argv[2])['running'] is False
try:
    OllamaProvider(host=sys.argv[2]).complete('fictional prompt')
except ProviderRejectedError as error:
    assert error.status == 503
else:
    raise AssertionError('unavailable local model must fail locally')
""", local, unavailable],
            env=env, capture_output=True, timeout=10, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)
    assert [path for path, _ in requests["local"]] == ["/api/generate", "/api/tags"]
    assert json.loads(requests["local"][0][1])["prompt"] == "fictional prompt"
    assert [path for path, _ in requests["unavailable"]] == ["/api/tags", "/api/generate"]
    assert json.loads(requests["unavailable"][1][1])["prompt"] == "fictional prompt"
    assert requests["proxy"] == []


def _transport(payload: dict[str, object]):
    def post_json(url: str, headers: dict[str, str], body: dict[str, object]):
        post_json.seen = {"url": url, "headers": headers, "body": body}
        return payload

    return post_json


def _raw_server(response: bytes, *, contacted: threading.Event | None = None) -> str:
    """Start a one-shot raw TCP listener bound to an OS-assigned loopback port.

    Sends ``response`` verbatim to the first connection, then closes. Used to
    drive ``ollama_status``'s and the Ollama provider's *real* transports (not
    an injected fetcher) against byte sequences a real HTTP client chokes on,
    without ever touching port 11434 or a real Ollama.

    ``contacted``, when given, is set the moment a connection arrives -- used
    to prove a redirect target was (or was never) actually reached.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    def serve() -> None:
        conn, _ = sock.accept()
        if contacted is not None:
            contacted.set()
        with conn:
            conn.recv(65536)
            conn.sendall(response)

    threading.Thread(target=serve, daemon=True).start()
    return f"http://127.0.0.1:{port}"


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


def test_ollama_provider_refuses_to_follow_a_redirect_off_loopback():
    """A loopback listener answering 302 must not be followed off loopback.

    urlopen() follows redirects by default, so a listener on the configured
    port could send the request (and have its response trusted as narration)
    to another host entirely. This drives the *real* ``_post_local_json``
    transport -- no injected ``post_json`` -- against a real redirecting
    listener, and proves the redirect target is never even contacted.
    """
    contacted = threading.Event()
    redirect_target = _raw_server(
        b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n", contacted=contacted
    )
    host = _raw_server(
        f"HTTP/1.1 302 Found\r\nLocation: {redirect_target}/api/generate\r\n"
        "Content-Length: 0\r\n\r\n".encode()
    )

    provider = OllamaProvider(host=host)
    with pytest.raises(ProviderError):
        provider.complete("prompt")

    assert not contacted.wait(timeout=0.5), "the redirect target must never be reached"


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


def test_status_survives_a_truncated_response_body():
    # No injected get_json here: this drives the real _get_json transport.
    # A Content-Length that promises more bytes than arrive before the
    # socket closes makes http.client raise IncompleteRead, which is
    # neither an OSError nor a ValueError.
    host = _raw_server(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 100\r\n"
        b"\r\n"
        b'{"trunc'
    )

    status = ollama_status(host=host)

    assert status["running"] is False
    assert status["installed_models"] == []


def test_status_survives_a_non_http_listener():
    # A learner could have some other, non-Ollama process listening on the
    # configured port. A raw byte string that isn't a valid HTTP status line
    # makes http.client raise BadStatusLine, also neither an OSError nor a
    # ValueError.
    host = _raw_server(b"not an http response at all\r\n\r\n")

    status = ollama_status(host=host)

    assert status["running"] is False
    assert status["installed_models"] == []


def test_status_refuses_to_follow_a_redirect_off_loopback():
    # Same threat as the provider redirect test: a listener on the
    # configured port could 302 the status probe off loopback. This drives
    # the real _get_json transport against a real redirecting listener.
    contacted = threading.Event()
    redirect_target = _raw_server(
        b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n", contacted=contacted
    )
    host = _raw_server(
        f"HTTP/1.1 302 Found\r\nLocation: {redirect_target}/api/tags\r\n"
        "Content-Length: 0\r\n\r\n".encode()
    )

    status = ollama_status(host=host)

    assert status["running"] is False
    assert status["installed_models"] == []
    assert not contacted.wait(timeout=0.5), "the redirect target must never be reached"
