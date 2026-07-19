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


def test_unpicked_app_reports_state_and_guards_project_api(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.get("/api/picker/state").json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/regions/pkg/checks").status_code == 409
    assert client.get("/api/node/pkg.x/study").status_code == 409
    assert client.post("/api/entrypoint", json={"node_id": "x"}).status_code == 409


def test_bound_app_reports_ready_picker_state(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/picker/state").json() == {"state": "ready"}
    assert client.get("/api/graph").status_code == 200


def test_create_app_requires_a_graph_or_picker(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        create_app(web_dist=tmp_path / "missing")


def test_picker_browse_lists_directories_inside_the_jail(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    (tmp_path / "beta").mkdir()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "loose.py").write_text("A = 1\n", encoding="utf-8")
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    root_listing = client.get("/api/picker/browse")
    child_listing = client.get(
        "/api/picker/browse", params={"path": str(tmp_path / "beta")}
    )

    assert root_listing.status_code == 200
    assert root_listing.json()["parent"] is None
    assert [entry["name"] for entry in root_listing.json()["entries"]] == [
        "Alpha",
        "beta",
    ]
    assert child_listing.json()["parent"] == str(tmp_path.resolve())
    assert client.get(
        "/api/picker/browse", params={"path": str(tmp_path / "missing-dir")}
    ).status_code == 404
    assert client.get(
        "/api/picker/browse", params={"path": str(tmp_path.parent)}
    ).status_code == 403


def test_picker_browse_refuses_symlink_escape(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    jail = tmp_path / "jail"
    outside = tmp_path / "outside"
    jail.mkdir()
    outside.mkdir()
    (jail / "escape").symlink_to(outside)
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=jail))
    )

    assert client.get(
        "/api/picker/browse", params={"path": str(jail / "escape")}
    ).status_code == 403


def test_picker_recents_come_from_the_progress_store(
    tmp_path: Path, monkeypatch
) -> None:
    import json as json_module

    from codemble.server.app import PickerConfig

    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    project = tmp_path / "demo"
    project.mkdir()
    progress = tmp_path / "data" / "progress"
    progress.mkdir(parents=True)
    (progress / "abc.json").write_text(
        json_module.dumps(
            {
                "schema_version": 1,
                "project_root": str(project),
                "regions": {"pkg": {"signature": "s"}},
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.get("/api/picker/recents").json() == {
        "recents": [{"project_root": str(project), "understood_count": 1}]
    }


def test_picker_select_binds_a_project_exactly_once(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
        )
    )

    first = client.post("/api/picker/select", json={"path": str(FIXTURE)})
    second = client.post("/api/picker/select", json={"path": str(FIXTURE)})

    assert first.status_code == 200
    assert first.json() == {"state": "ready"}
    assert client.get("/api/picker/state").json() == {"state": "ready"}
    assert client.get("/api/graph").status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "A project is already selected."
    assert client.get("/api/picker/browse").status_code == 409


def test_picker_select_reports_scale_with_suggestions(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    big = tmp_path / "big"
    (big / "api").mkdir(parents=True)
    for index in range(301):
        (big / "api" / f"module_{index}.py").write_text("A = 1\n", encoding="utf-8")
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    response = client.post("/api/picker/select", json={"path": str(big)})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"] == "scale"
    assert detail["file_count"] == 301
    assert detail["scale_cap"] == 300
    assert detail["root"] == str(big.resolve())
    assert detail["suggestions"][0] == {"path": "api", "file_count": 301}


def test_picker_select_rejects_unparseable_and_escaping_paths(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    empty = tmp_path / "empty"
    empty.mkdir()
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.post(
        "/api/picker/select", json={"path": str(empty)}
    ).status_code == 422
    assert client.post(
        "/api/picker/select", json={"path": str(tmp_path.parent)}
    ).status_code == 403
    assert client.post(
        "/api/picker/select", json={"path": str(tmp_path / "nope")}
    ).status_code == 404


def test_foreign_host_headers_are_rejected(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    rebinding = client.get("/api/graph", headers={"Host": "evil.example"})

    assert rebinding.status_code == 400
    assert client.get("/api/graph").status_code == 200
