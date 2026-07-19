"""Local API contracts for the galaxy server."""

from pathlib import Path

from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.llm.study import StudyService
from codemble.server.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def test_graph_and_source_endpoints_are_grounded(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    web_dist = tmp_path / "dist"
    web_dist.mkdir()
    (web_dist / "index.html").write_text("<h1>Codemble</h1>", encoding="utf-8")
    studies = StudyService(graph, cache_root=tmp_path / "cache")
    client = TestClient(create_app(graph, web_dist, studies))

    graph_response = client.get("/api/graph")
    study_response = client.get("/api/node/pkg.service.Service.run/study")

    assert graph_response.status_code == 200
    assert graph_response.json()["regions"]
    assert study_response.status_code == 200
    assert study_response.json()["source"]["file"] == "pkg/service.py"
    assert study_response.json()["source"]["lines"][0]["text"].startswith("    def run")
    assert study_response.json()["explanation"]["status"] == "no_key"
    assert client.get("/api/node/not-real/study").status_code == 404
    assert "Codemble" in client.get("/").text
    assert "Codemble" in client.get("/galaxy/system/pkg").text


def test_missing_web_build_keeps_api_available(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/graph").status_code == 200
    assert client.get("/").json()["status"] == "web-build-missing"
