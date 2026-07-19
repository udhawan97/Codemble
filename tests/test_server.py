"""Local API contracts for the galaxy server."""

from pathlib import Path

from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter
from codemble.checks import CheckService, generate_checks
from codemble.llm.study import StudyService
from codemble.progress import ProgressStore
from codemble.server.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


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


def test_entrypoint_api_accepts_only_parser_ranked_candidates(tmp_path: Path) -> None:
    for module in ("alpha", "beta"):
        (tmp_path / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n',
            encoding="utf-8",
        )
    graph = PythonAstAdapter().parse(tmp_path)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/graph").json()["selected_entrypoint"] is None
    response = client.post("/api/entrypoint", json={"node_id": "beta"})
    assert response.status_code == 200
    assert response.json()["selected_entrypoint"] == "beta"
    assert next(
        region for region in response.json()["regions"] if region["id"] == "beta"
    )["home"]
    beta_checks = client.get("/api/regions/beta/checks").json()["checks"]
    assert len(beta_checks) == 1
    assert beta_checks[0]["kind"] == "entrypoint"
    assert "selected as Home" in beta_checks[0]["prompt"]
    assert client.get("/api/regions/alpha/checks").json()["checks"] == []
    assert client.post("/api/entrypoint", json={"node_id": "missing"}).status_code == 422


def test_js_ts_node_and_region_ids_with_paths_round_trip_through_the_api(
    tmp_path: Path,
) -> None:
    graph = JavaScriptTypeScriptAdapter().parse(POLYGLOT_FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))
    node_id = "typescript:src/util.ts::helper"
    region_id = "javascript:src/legacy.js"

    study = client.get(f"/api/node/{node_id}/study")
    suite = client.get(f"/api/regions/{region_id}/checks")

    assert study.status_code == 200
    assert study.json()["source"]["file"] == "src/util.ts"
    assert study.json()["source"]["lines"][0]["text"].startswith("export function")
    assert suite.status_code == 200
    check = suite.json()["checks"][0]
    generated = generate_checks(graph, region_id)[0]
    submission = client.post(
        f"/api/regions/{region_id}/checks/{check['id']}",
        json={"selected_ids": list(generated.answer_ids)},
    )
    assert submission.status_code == 200
    assert submission.json()["correct"] is True
