"""Local API contracts for the galaxy server."""

from pathlib import Path

from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.checks import CheckService, generate_checks
from codemble.llm.study import StudyService
from codemble.progress import ProgressStore
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


def test_check_api_withholds_answers_then_persists_graph_lighting(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, tmp_path / "progress"))
    client = TestClient(
        create_app(
            graph,
            tmp_path / "missing",
            StudyService(graph, cache_root=tmp_path / "cache"),
            checks,
        )
    )

    suite = client.get("/api/regions/app/checks")
    assert suite.status_code == 200
    assert len(suite.json()["checks"]) == 4
    assert all("answer_ids" not in question for question in suite.json()["checks"])

    generated = generate_checks(graph, "app")
    for check in generated:
        response = client.post(
            f"/api/regions/app/checks/{check.id}",
            json={"selected_ids": list(check.answer_ids)},
        )
        assert response.status_code == 200
        assert response.json()["correct"] is True

    assert response.json()["region_understood"] is True
    graph_payload = client.get("/api/graph").json()
    app_region = next(region for region in graph_payload["regions"] if region["id"] == "app")
    assert app_region["understood"] is True
    assert client.get("/api/regions/not-real/checks").status_code == 404
