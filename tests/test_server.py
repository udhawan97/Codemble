"""Local API contracts for the galaxy server."""

from pathlib import Path

import pytest
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
    explanation_response = client.get("/api/node/app.main/explanation?mode=easy")

    assert graph_response.status_code == 200
    assert graph_response.json()["regions"]
    assert study_response.status_code == 200
    assert study_response.json()["source"]["file"] == "pkg/service.py"
    assert study_response.json()["source"]["lines"][0]["text"].startswith("    def run")
    assert "structural" in study_response.json()
    assert "explanation" not in study_response.json()
    assert explanation_response.status_code == 200
    assert explanation_response.headers["content-type"] == "application/json"
    assert "status" in explanation_response.json()
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
    assert "selected as Home" in beta_checks[0]["prompt_voices"]["expert"]
    assert "prompt" not in beta_checks[0]
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
    explanation = client.get(f"/api/node/{node_id}/explanation?mode=easy")
    suite = client.get(f"/api/regions/{region_id}/checks")

    assert study.status_code == 200
    assert study.json()["source"]["file"] == "src/util.ts"
    assert study.json()["source"]["lines"][0]["text"].startswith("export function")
    assert explanation.status_code == 200
    assert "status" in explanation.json()
    assert suite.status_code == 200
    check = suite.json()["checks"][0]
    generated = generate_checks(graph, region_id)[0]
    submission = client.post(
        f"/api/regions/{region_id}/checks/{check['id']}",
        json={"selected_ids": list(generated.answer_ids)},
    )
    assert submission.status_code == 200
    assert submission.json()["correct"] is True


def test_explanation_endpoint_returns_narration_state(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    response = client.get("/api/node/app.main/explanation?mode=easy")

    assert response.status_code == 200
    assert "status" in response.json()


def test_explanation_endpoint_rejects_an_unknown_mode(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/node/app.main/explanation?mode=casual").status_code == 422


def test_explanation_endpoint_404s_for_an_unknown_node(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    response = client.get("/api/node/nope/explanation?mode=easy")

    assert response.status_code == 404
    # status_code alone passes even with no route at all (FastAPI's default
    # "Not Found" is also a 404), so it can't prove this hit the handler.
    # Pin the detail body too, so this genuinely exercises the route's
    # UnknownNodeError branch rather than an unmatched-path fallback.
    assert response.json()["detail"] == "That source node is not in this graph."


def test_mode_defaults_to_easy_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/mode").json()["mode"] == "easy"
    assert client.put("/api/mode", json={"mode": "expert"}).status_code == 200
    assert client.get("/api/mode").json()["mode"] == "expert"


def test_mode_rejects_an_unknown_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.put("/api/mode", json={"mode": "casual"}).status_code == 422


def test_changing_mode_does_not_re_dim_a_region(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
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

    generated = generate_checks(graph, "app")
    for check in generated:
        response = client.post(
            f"/api/regions/app/checks/{check.id}",
            json={"selected_ids": list(check.answer_ids)},
        )
        assert response.status_code == 200
    assert response.json()["region_understood"] is True

    before = client.get("/api/graph").json()
    client.put("/api/mode", json={"mode": "expert"})
    after = client.get("/api/graph").json()

    assert after == before
    app_region = next(region for region in after["regions"] if region["id"] == "app")
    assert app_region["understood"] is True


def test_mode_reports_unchosen_until_a_choice_is_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/mode").json() == {"mode": "easy", "chosen": False}

    put_response = client.put("/api/mode", json={"mode": "expert"})

    assert put_response.json() == {"mode": "expert", "chosen": True}
    assert client.get("/api/mode").json() == {"mode": "expert", "chosen": True}


def test_choosing_the_default_mode_still_counts_as_a_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A learner who explicitly picks 'easy' (the default) must not look like

    nobody has chosen yet — that's the whole reason `chosen` exists.
    """

    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    put_response = client.put("/api/mode", json={"mode": "easy"})

    assert put_response.json() == {"mode": "easy", "chosen": True}
    assert client.get("/api/mode").json() == {"mode": "easy", "chosen": True}


def test_a_malformed_progress_file_reports_unchosen_mode_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    progress = ProgressStore(graph)
    progress.path.parent.mkdir(parents=True, exist_ok=True)
    progress.path.write_text("not json", encoding="utf-8")
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/mode").json() == {"mode": "easy", "chosen": False}


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
    assert client.get("/api/mode").status_code == 409
    assert client.put("/api/mode", json={"mode": "easy"}).status_code == 409


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
    jail = tmp_path / "jail"
    jail.mkdir()
    project = jail / "demo"
    project.mkdir()
    outside_project = tmp_path / "outside-project"
    outside_project.mkdir()
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
    (progress / "outside.json").write_text(
        json_module.dumps(
            {
                "schema_version": 1,
                "project_root": str(outside_project),
                "regions": {"pkg": {"signature": "s"}, "other": {"signature": "s"}},
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=jail))
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


def test_llm_status_endpoint_reports_provider_and_local_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fake the transport, not just the value: a real ollama_status() call
    # would otherwise reach out to 127.0.0.1:11434 for real, making this test
    # depend on whether Ollama happens to be running on the machine that
    # executes it.
    monkeypatch.setattr(
        "codemble.llm.local_status._get_json",
        lambda url: {"models": [{"name": "gemma4:12b"}]},
    )
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    payload = client.get("/api/llm/status").json()

    assert "configured_provider" in payload
    assert payload["ollama"]["recommended"] == "gemma4:12b"
    assert payload["ollama"]["fallback"] == "qwen3:8b"
    assert payload["ollama"]["running"] is True
    assert payload["ollama"]["installed_models"] == ["gemma4:12b"]


def test_llm_status_endpoint_reports_a_configured_providers_name_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pins the provider.name / provider.model lookups in the route to real
    # values from a bound project. Without this, the getattr(..., None)
    # defaults used to survive an unbound project would also silently mask a
    # typo'd attribute name as None, and no other test here would notice.
    monkeypatch.setattr(
        "codemble.llm.local_status._get_json",
        lambda url: {"models": []},
    )

    class FakeProvider:
        name = "fake"
        model = "grounded-test"

        def complete(self, prompt: str) -> str:
            raise NotImplementedError

    graph = PythonAstAdapter().parse(FIXTURE)
    studies = StudyService(graph, provider=FakeProvider(), cache_root=tmp_path / "cache")
    client = TestClient(create_app(graph, tmp_path / "missing", studies))

    payload = client.get("/api/llm/status").json()

    assert payload["configured_provider"] == "fake"
    assert payload["configured_model"] == "grounded-test"


def test_llm_status_endpoint_works_before_a_project_is_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The in-app setup guide this endpoint feeds is most useful *before* a
    # learner has picked a project, so this must not 409 like /api/graph does.
    from codemble.server.app import PickerConfig

    def refused(url: str):
        raise OSError("connection refused")

    monkeypatch.setattr("codemble.llm.local_status._get_json", refused)
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    response = client.get("/api/llm/status")

    assert response.status_code == 200
    assert response.json()["configured_provider"] is None
    assert response.json()["configured_model"] is None
    assert response.json()["ollama"]["running"] is False


def test_foreign_host_headers_are_rejected(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    rebinding = client.get("/api/graph", headers={"Host": "evil.example"})

    assert rebinding.status_code == 400
    assert client.get("/api/graph").status_code == 200
