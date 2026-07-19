"""Local API contracts for the galaxy server."""

from pathlib import Path

from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.server.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def test_graph_and_source_endpoints_are_grounded(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    web_dist = tmp_path / "dist"
    web_dist.mkdir()
    (web_dist / "index.html").write_text("<h1>Codemble</h1>", encoding="utf-8")
    client = TestClient(create_app(graph, web_dist))

    graph_response = client.get("/api/graph")
    source_response = client.get("/api/node/pkg.service.Service.run/source")

    assert graph_response.status_code == 200
    assert graph_response.json()["regions"]
    assert source_response.status_code == 200
    assert source_response.json()["file"] == "pkg/service.py"
    assert "def run(self)" in source_response.json()["source"]
    assert client.get("/api/node/not-real/source").status_code == 404
    assert "Codemble" in client.get("/").text
    assert "Codemble" in client.get("/galaxy/system/pkg").text


def test_missing_web_build_keeps_api_available(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/graph").status_code == 200
    assert client.get("/").json()["status"] == "web-build-missing"
