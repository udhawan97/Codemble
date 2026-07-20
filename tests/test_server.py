"""Local API contracts for the galaxy server."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter
from codemble.checks import CheckService, generate_checks
from codemble.llm.study import StudyService
from codemble.progress import ProgressStore
from codemble.server.app import PickerConfig, create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """A TestClient bound to the sampleproj fixture -- the shape every other
    test in this file builds locally; shared here for tests that don't care
    about a specific graph, just a bound project."""

    graph = PythonAstAdapter().parse(FIXTURE)
    return TestClient(create_app(graph, tmp_path / "missing"))


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


def _inline_runner(work):  # type: ignore[no-untyped-def]
    """Run the parse on the request thread so tests never sleep or poll."""

    work()


def test_picker_select_returns_202_and_binds_through_the_parse_job(
    tmp_path: Path,
) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=_inline_runner,
        )
    )

    idle = client.get("/api/picker/progress").json()
    accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
    progress = client.get("/api/picker/progress").json()

    assert idle == {
        "state": "idle",
        "stage": None,
        "detail": None,
        "files_done": 0,
        "files_total": 0,
        "error": None,
    }
    assert accepted.status_code == 202
    assert accepted.json() == {"state": "parsing"}
    assert progress["state"] == "ready"
    assert progress["files_done"] == progress["files_total"] > 0
    assert progress["error"] is None
    assert client.get("/api/picker/state").json() == {"state": "ready"}
    assert client.get("/api/graph").status_code == 200
    assert (
        client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code
        == 409
    )


def test_picker_progress_reports_ready_for_a_cli_bound_project(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    assert client.get("/api/picker/progress").json()["state"] == "ready"


def test_a_failed_parse_becomes_an_error_state_with_an_in_app_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from codemble.adapters.project import ProjectParser
    from codemble.server.app import PickerConfig

    def exploding_parse(self, source, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("tree-sitter exploded")

    monkeypatch.setattr(ProjectParser, "parse", exploding_parse)
    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=_inline_runner,
        )
    )

    accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
    progress = client.get("/api/picker/progress").json()

    assert accepted.status_code == 202
    assert progress["state"] == "error"
    assert progress["error"] == "tree-sitter exploded"
    assert client.get("/api/picker/state").json() == {"state": "unpicked"}


def test_reset_during_a_parse_re_arms_the_picker_and_leaves_nothing_bound(
    tmp_path: Path,
) -> None:
    """Cancellation itself is proven in tests/test_parse_job.py; this pins the
    HTTP contract: whether the worker stops mid-parse or finishes a moment
    before the reset lands, reset wins and nothing stays bound."""

    import threading

    from codemble.server.app import PickerConfig

    started = threading.Event()
    release = threading.Event()
    threads: list[threading.Thread] = []

    def gated_runner(work):  # type: ignore[no-untyped-def]
        def run() -> None:
            started.set()
            assert release.wait(timeout=5)
            work()

        thread = threading.Thread(target=run, daemon=True)
        threads.append(thread)
        thread.start()

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=gated_runner,
        )
    )

    accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
    assert started.wait(timeout=5)
    parsing = client.get("/api/picker/progress").json()
    release.set()
    reset = client.post("/api/picker/reset", json={"confirmed": True})
    for thread in threads:
        thread.join(timeout=5)

    assert accepted.status_code == 202
    assert parsing["state"] == "parsing"
    assert parsing["stage"] == "discovering"
    assert reset.status_code == 200
    assert reset.json() == {"state": "unpicked"}
    assert client.get("/api/picker/state").json() == {"state": "unpicked"}
    assert client.get("/api/picker/progress").json()["state"] == "idle"
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/picker/browse").status_code == 200
    assert (
        client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code
        == 202
    ), "a reset picker accepts the next project without a server restart"


def test_a_bind_that_outlasts_cancel_does_not_resurrect_a_reset_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F5: ``work()`` checks ``reporter.cancelled`` only *before* calling
    ``state.bind(...)``. If ``bind`` (building ``CheckService`` and friends)
    outlasts ``cancel()``'s 2s wait, the old code committed anyway -- *after*
    ``reset`` had already unbound the project, resurrecting it (or clobbering
    whatever the learner selects next).

    The reset-during-a-parse test above can't catch this: its tiny fixture
    binds in far under 2s, so ``cancel()``'s wait always outlasts the bind and
    ``unbind()`` naturally runs after it. Here ``CheckService.__init__`` is
    gated open with a ``threading.Event`` so ``bind`` deterministically
    outlasts the pre-bind cancellation check *and* the reset call -- no sleep,
    no timing luck."""

    import threading

    from codemble.checks import CheckService

    entered_bind = threading.Event()
    release_bind = threading.Event()
    real_init = CheckService.__init__

    def gated_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        entered_bind.set()
        assert release_bind.wait(timeout=5)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(CheckService, "__init__", gated_init)

    threads: list[threading.Thread] = []

    def capturing_runner(work):  # type: ignore[no-untyped-def]
        thread = threading.Thread(target=work, daemon=True)
        threads.append(thread)
        thread.start()

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=capturing_runner,
        )
    )

    accepted = client.post("/api/picker/select", json={"path": str(FIXTURE)})
    assert accepted.status_code == 202
    assert entered_bind.wait(timeout=5), "worker never reached CheckService construction"

    # The worker is stuck inside bind(), past work()'s pre-bind cancellation
    # check. cancel() waits its full 2s and gives up because bind() has not
    # finished.
    reset = client.post("/api/picker/reset", json={"confirmed": True})
    assert reset.status_code == 200
    assert reset.json() == {"state": "unpicked"}

    # Let the stale bind run to its commit -- it must still lose the race.
    release_bind.set()
    for thread in threads:
        thread.join(timeout=5)

    assert client.get("/api/picker/state").json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409


def test_a_scale_refusal_leaves_the_picker_idle_not_stuck_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from codemble.adapters.project import ProjectParser
    from codemble.server.app import PickerConfig

    monkeypatch.setattr(ProjectParser, "scale_cap", 3)
    big = tmp_path / "big"
    (big / "api").mkdir(parents=True)
    for index in range(4):
        (big / "api" / f"module_{index}.py").write_text("A = 1\n", encoding="utf-8")
    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=tmp_path),
            parse_runner=_inline_runner,
        )
    )

    response = client.post("/api/picker/select", json={"path": str(big)})

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "scale"
    assert client.get("/api/picker/progress").json()["state"] == "idle"
    assert client.get("/api/picker/browse").status_code == 200


def test_picker_select_reports_scale_with_suggestions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from codemble.adapters.project import ProjectParser
    from codemble.server.app import PickerConfig

    monkeypatch.setattr(ProjectParser, "scale_cap", 3)
    big = tmp_path / "big"
    (big / "api").mkdir(parents=True)
    for index in range(4):
        (big / "api" / f"module_{index}.py").write_text("A = 1\n", encoding="utf-8")
    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    response = client.post("/api/picker/select", json={"path": str(big)})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"] == "scale"
    assert detail["file_count"] == 4
    assert detail["scale_cap"] == 3
    assert detail["root"] == str(big.resolve())
    assert detail["suggestions"][0] == {"path": "api", "file_count": 4}


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


def test_picker_reset_unbinds_and_re_arms_the_picker(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=_inline_runner,
        )
    )
    assert client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code == 202

    first = client.post("/api/picker/reset", json={"confirmed": True})
    second = client.post("/api/picker/reset", json={"confirmed": True})

    assert first.status_code == 200
    assert first.json() == {"state": "unpicked"}
    assert second.status_code == 200
    assert second.json() == {"state": "unpicked"}
    assert client.get("/api/picker/state").json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/picker/browse").status_code == 200
    assert client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code == 202
    assert client.get("/api/graph").status_code == 200


def test_picker_reset_refuses_a_body_a_cross_site_form_could_send(tmp_path: Path) -> None:
    # Releasing the project is the only state change a no-body POST could reach,
    # so a page on another origin could once unbind a learner's project with a
    # plain <form>.  Requiring JSON puts it behind the same preflight as every
    # other write here.  Nuisance, not disclosure -- but a one-field fix.
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=_inline_runner,
        )
    )
    assert client.post("/api/picker/select", json={"path": str(FIXTURE)}).status_code == 202

    formish = client.post(
        "/api/picker/reset",
        content="confirmed=true",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    empty = client.post("/api/picker/reset")

    assert formish.status_code == 422
    assert empty.status_code == 422
    # The project it tried to release is untouched.
    assert client.get("/api/graph").status_code == 200
    assert client.post("/api/picker/reset", json={"confirmed": True}).status_code == 200
    assert client.get("/api/graph").status_code == 409


def test_picker_reset_works_for_a_path_opened_project_that_carries_a_picker(
    tmp_path: Path,
) -> None:
    from codemble.server.app import PickerConfig

    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(
        create_app(
            graph,
            tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
        )
    )

    assert client.get("/api/graph").status_code == 200
    assert client.post(
        "/api/picker/reset", json={"confirmed": True}
    ).json() == {"state": "unpicked"}
    assert client.get("/api/graph").status_code == 409
    assert client.get("/api/picker/browse").status_code == 200


def test_picker_reset_refuses_an_app_built_without_a_picker(tmp_path: Path) -> None:
    # Unbinding here would strand the process with no way to pick anything,
    # so refusing is the honest answer rather than a 200 that breaks the app.
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    response = client.post("/api/picker/reset", json={"confirmed": True})

    assert response.status_code == 409
    assert client.get("/api/graph").status_code == 200


def test_selected_home_is_restored_for_the_next_run_of_the_same_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    first = TestClient(
        create_app(PythonAstAdapter().parse(project), tmp_path / "missing")
    )
    assert first.get("/api/graph").json()["selected_entrypoint"] is None
    assert first.post("/api/entrypoint", json={"node_id": "beta"}).status_code == 200

    restarted = TestClient(
        create_app(PythonAstAdapter().parse(project), tmp_path / "missing")
    )

    assert restarted.get("/api/graph").json()["selected_entrypoint"] == "beta"


def test_map_endpoint_serves_both_deterministic_layouts(client) -> None:  # type: ignore[no-untyped-def]
    first = client.get("/api/map")
    second = client.get("/api/map")

    assert first.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["schema_version"] == 1
    assert payload["architecture"]["home"] == "app"
    assert payload["workflow"]["root"] == "app"
    assert {box["id"] for box in payload["architecture"]["boxes"]} == {
        region["id"] for region in client.get("/api/graph").json()["regions"]
    }


def test_map_endpoint_refuses_before_a_project_is_bound() -> None:
    app = create_app(picker=PickerConfig(browse_root=Path.home()))

    with TestClient(app) as unbound:
        response = unbound.get("/api/map")

    assert response.status_code == 409
    assert response.json()["detail"] == "No project selected yet."


def test_graph_responses_are_cached_and_invalidated_by_light_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, tmp_path / "progress"))
    hydrations = 0
    real_graph = checks.graph

    def counting_graph():  # type: ignore[no-untyped-def]
        nonlocal hydrations
        hydrations += 1
        return real_graph()

    monkeypatch.setattr(checks, "graph", counting_graph)
    client = TestClient(
        create_app(
            graph,
            tmp_path / "missing",
            StudyService(graph, cache_root=tmp_path / "cache"),
            checks,
        )
    )

    first = client.get("/api/graph").json()
    second = client.get("/api/graph").json()
    after_two_reads = hydrations

    for check in generate_checks(graph, "app"):
        client.post(
            f"/api/regions/app/checks/{check.id}",
            json={"selected_ids": list(check.answer_ids)},
        )
    lit = client.get("/api/graph").json()

    assert first == second
    assert after_two_reads == 1, "a second read must not re-hydrate or re-sort"
    assert (
        next(region for region in first["regions"] if region["id"] == "app")[
            "understood"
        ]
        is False
    )
    assert (
        next(region for region in lit["regions"] if region["id"] == "app")["understood"]
        is True
    ), "a cached payload must never survive a region lighting up"


def test_graph_cache_is_invalidated_by_entrypoint_selection(tmp_path: Path) -> None:
    for module in ("alpha", "beta"):
        (tmp_path / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n',
            encoding="utf-8",
        )
    graph = PythonAstAdapter().parse(tmp_path)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    before = client.get("/api/graph").json()
    client.post("/api/entrypoint", json={"node_id": "beta"})
    after = client.get("/api/graph").json()

    assert before["selected_entrypoint"] is None
    assert after["selected_entrypoint"] == "beta"
    assert next(region for region in after["regions"] if region["id"] == "beta")["home"]


def test_graph_cache_is_dropped_when_the_project_is_reset(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=_inline_runner,
        )
    )
    client.post("/api/picker/select", json={"path": str(FIXTURE)})
    assert client.get("/api/graph").status_code == 200

    # The shipped reset endpoint requires a confirmed JSON body (added for
    # CSRF safety after this plan was written); a bare bodyless POST 422s and
    # never reaches unbind, which would make this test pass for the wrong
    # reason. See phasec-adjustments.md.
    client.post("/api/picker/reset", json={"confirmed": True})

    assert client.get("/api/graph").status_code == 409


def test_a_mode_change_serves_the_same_cached_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    before = client.get("/api/graph").json()
    client.put("/api/mode", json={"mode": "expert"})

    assert client.get("/api/graph").json() == before


def test_map_responses_are_cached_and_invalidated_by_light_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors the /api/graph cache test above: Easy mode defaults to the Map
    layer, so it carries the same never-serve-stale-light-up requirement."""

    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, tmp_path / "progress"))
    hydrations = 0
    real_graph = checks.graph

    def counting_graph():  # type: ignore[no-untyped-def]
        nonlocal hydrations
        hydrations += 1
        return real_graph()

    monkeypatch.setattr(checks, "graph", counting_graph)
    client = TestClient(
        create_app(
            graph,
            tmp_path / "missing",
            StudyService(graph, cache_root=tmp_path / "cache"),
            checks,
        )
    )

    first = client.get("/api/map").json()
    second = client.get("/api/map").json()
    after_two_reads = hydrations

    for check in generate_checks(graph, "app"):
        client.post(
            f"/api/regions/app/checks/{check.id}",
            json={"selected_ids": list(check.answer_ids)},
        )
    lit = client.get("/api/map").json()

    assert first == second
    assert after_two_reads == 1, "a second map read must not re-hydrate or re-layout"
    assert (
        next(box for box in first["architecture"]["boxes"] if box["id"] == "app")[
            "understood"
        ]
        is False
    )
    assert (
        next(box for box in lit["architecture"]["boxes"] if box["id"] == "app")[
            "understood"
        ]
        is True
    ), "a cached map payload must never survive a region lighting up"


def test_map_cache_is_invalidated_by_entrypoint_selection(tmp_path: Path) -> None:
    for module in ("alpha", "beta"):
        (tmp_path / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n',
            encoding="utf-8",
        )
    graph = PythonAstAdapter().parse(tmp_path)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    before = client.get("/api/map").json()
    client.post("/api/entrypoint", json={"node_id": "beta"})
    after = client.get("/api/map").json()

    assert before["architecture"]["home"] is None
    assert after["architecture"]["home"] == "beta"


def test_map_cache_is_dropped_when_the_project_is_reset(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=FIXTURE.parent),
            parse_runner=_inline_runner,
        )
    )
    client.post("/api/picker/select", json={"path": str(FIXTURE)})
    assert client.get("/api/map").status_code == 200

    client.post("/api/picker/reset", json={"confirmed": True})

    assert client.get("/api/map").status_code == 409


def test_a_mode_change_serves_the_same_cached_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    before = client.get("/api/map").json()
    client.put("/api/mode", json={"mode": "expert"})

    assert client.get("/api/map").json() == before


def test_graph_and_map_share_one_hydration_after_an_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/api/graph and /api/map each cache their own serialized payload, but
    both read the same underlying hydrated Graph. Reading both after a cold
    start (or after any invalidation) must hydrate once total, not once per
    endpoint -- otherwise a learner who opens the Map (Easy mode's default)
    and then the galaxy pays hydration twice for one page load."""

    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, tmp_path / "progress"))
    hydrations = 0
    real_graph = checks.graph

    def counting_graph():  # type: ignore[no-untyped-def]
        nonlocal hydrations
        hydrations += 1
        return real_graph()

    monkeypatch.setattr(checks, "graph", counting_graph)
    client = TestClient(
        create_app(
            graph,
            tmp_path / "missing",
            StudyService(graph, cache_root=tmp_path / "cache"),
            checks,
        )
    )

    client.get("/api/graph")
    client.get("/api/map")
    client.get("/api/graph")
    client.get("/api/map")

    assert hydrations == 1, "graph and map must share one hydration, not one each"


def test_rebinding_a_different_project_after_reset_serves_its_own_graph_and_map(
    tmp_path: Path,
) -> None:
    """A stale cache surviving a reset is invisible to the learner: they
    would see the previous project's graph and map after switching, with no
    error. The plain reset -> 409 check above cannot catch this, because
    ``_services()`` already 409s on ``checks is None`` regardless of what the
    cache fields hold; only serving a *second*, different project proves the
    cache was actually dropped rather than merely gated while unbound."""

    from codemble.server.app import PickerConfig

    first_project = tmp_path / "first"
    first_project.mkdir()
    (first_project / "alpha.py").write_text(
        "def alpha() -> None:\n    pass\n", encoding="utf-8"
    )
    second_project = tmp_path / "second"
    second_project.mkdir()
    (second_project / "bravo.py").write_text(
        "def bravo() -> None:\n    pass\n", encoding="utf-8"
    )

    client = TestClient(
        create_app(
            web_dist=tmp_path / "missing",
            picker=PickerConfig(browse_root=tmp_path),
            parse_runner=_inline_runner,
        )
    )

    client.post("/api/picker/select", json={"path": str(first_project)})
    first_graph = client.get("/api/graph").json()
    first_map = client.get("/api/map").json()

    client.post("/api/picker/reset", json={"confirmed": True})
    client.post("/api/picker/select", json={"path": str(second_project)})
    second_graph = client.get("/api/graph").json()
    second_map = client.get("/api/map").json()

    assert {region["id"] for region in first_graph["regions"]} == {"alpha"}
    assert {region["id"] for region in second_graph["regions"]} == {"bravo"}
    assert {box["id"] for box in first_map["architecture"]["boxes"]} == {"alpha"}
    assert {box["id"] for box in second_map["architecture"]["boxes"]} == {"bravo"}


def test_progress_can_be_cleared_for_the_bound_project_only(
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
    for check in generate_checks(graph, "app"):
        client.post(
            f"/api/regions/app/checks/{check.id}",
            json={"selected_ids": list(check.answer_ids)},
        )
    lit = client.get("/api/graph").json()

    cleared = client.delete("/api/progress")
    after = client.get("/api/graph").json()

    assert next(region for region in lit["regions"] if region["id"] == "app")[
        "understood"
    ]
    assert cleared.status_code == 200
    assert cleared.json() == {"understood_regions": 0}
    assert (
        next(region for region in after["regions"] if region["id"] == "app")[
            "understood"
        ]
        is False
    ), "the cached graph must not survive a progress reset"


def test_clearing_progress_requires_a_bound_project(tmp_path: Path) -> None:
    from codemble.server.app import PickerConfig

    client = TestClient(
        create_app(web_dist=tmp_path / "missing", picker=PickerConfig(browse_root=tmp_path))
    )

    assert client.delete("/api/progress").status_code == 409
