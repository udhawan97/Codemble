"""Selected Dev Review regressions, using only synthetic projects and narration."""

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.checks import CheckService
from codemble.llm.study import StudyService
from codemble.progress import ModeReadUncertainError, ProgressStore
from codemble.server.app import create_app


def _project(root):
    root.mkdir()
    (root / "app.py").write_text("from lib import work\n\ndef main():\n    return work()\n")
    (root / "lib.py").write_text("def work():\n    return 1\n")
    return PythonAstAdapter().parse(root)


class _Provider:
    name = "fake"
    model = "review-contract"

    def __init__(self):
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        return json.dumps({
            "summary": "Uses a parser-observed helper.",
            "walkthrough": [],
            "relationships": [{
                "node_id": "lib.work", "explanation": "A possible helper relationship.",
            }],
        })


def test_reparsed_neighbor_citation_retires_cache_and_unchanged_context_hits(tmp_path):
    graph = _project(tmp_path / "project")
    provider = _Provider()
    cache = tmp_path / "cache"
    studies = StudyService(graph, provider=provider, cache_root=cache)
    assert studies.explain("app.main")["relationships"][0]["citation"] == "lib.py:1"
    (tmp_path / "project/lib.py").write_text("\n\n\ndef work():\n    return 1\n")
    current = PythonAstAdapter().parse(tmp_path / "project")
    assert current.file_hashes["app.py"] == graph.file_hashes["app.py"]
    studies.update_graph(current)

    result = studies.explain("app.main")
    assert result["relationships"][0]["citation"] == "lib.py:4"
    assert result["cached"] is False
    reopened = StudyService(current, provider=provider, cache_root=cache)
    assert reopened.explain("app.main")["cached"] is True
    assert provider.calls == 2


def test_changed_neighbor_certainty_cannot_reuse_certain_narration(tmp_path):
    graph = _project(tmp_path / "project")
    provider = _Provider()
    studies = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")
    assert studies.explain("app.main")["relationships"][0]["certain"] is True
    studies.update_graph(replace(graph, edges=tuple(
        replace(edge, certain=False) if edge.src == "app.main" else edge
        for edge in graph.edges
    )))

    result = studies.explain("app.main")
    assert result["relationships"][0]["certain"] is False
    assert result["cached"] is False
    assert provider.calls == 2


def test_removed_neighbor_cannot_reuse_narration_that_names_it(tmp_path):
    graph = _project(tmp_path / "project")
    provider = _Provider()
    studies = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")
    assert studies.explain("app.main")["status"] == "ready"
    studies.update_graph(replace(graph, edges=tuple(
        edge for edge in graph.edges if edge.src != "app.main"
    )))

    result = studies.explain("app.main")
    assert result["status"] == "error"
    assert result["reason"] == "grounding"
    assert provider.calls == 2


def test_identical_caller_in_another_project_has_separate_evidence_identity(tmp_path):
    first = _project(tmp_path / "first")
    second = _project(tmp_path / "second")
    assert first.file_hashes == second.file_hashes
    provider = _Provider()
    cache = tmp_path / "cache"
    assert StudyService(first, provider=provider, cache_root=cache).explain("app.main")["status"] == "ready"
    result = StudyService(second, provider=provider, cache_root=cache).explain("app.main")
    assert result["cached"] is False
    assert provider.calls == 2


@pytest.mark.parametrize("headers", [
    {"Origin": "https://foreign.example"},
    {"Origin": "null"},
    {"Origin": "http://testserver:81"},
    {"Origin": "http://testserver:0"},
    {"Origin": "https://testserver"},
    {"Origin": "http://testserver:invalid"},
    {"Origin": "http://[invalid"},
    {"Origin": "http://testserver https://foreign.example"},
    {"Origin": "http://testserver/path"},
    {"Origin": "http://@testserver"},
    [("Origin", "http://testserver"), ("Origin", "https://foreign.example")],
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
    {"Origin": "http://testserver", "Sec-Fetch-Site": "cross-site"},
])
def test_foreign_narration_refused_before_provider_or_cache(tmp_path, headers):
    graph = _project(tmp_path / "project")
    provider = _Provider()
    studies = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")
    with TestClient(create_app(graph, study_service=studies)) as client:
        response = client.get("/api/node/app.main/explanation", headers=headers)
        assert response.status_code == 403
        assert provider.calls == 0
        assert not (tmp_path / "cache").exists()
        assert client.get("/api/node/app.main/explanation").json()["status"] == "ready"
        assert client.get("/api/node/app.main/explanation", headers=headers).status_code == 403
        assert provider.calls == 1


@pytest.mark.parametrize("headers", [
    {},
    {"Sec-Fetch-Site": "none"},
    {"Sec-Fetch-Site": "same-origin"},
    {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
    {"Origin": "http://testserver:80"},
    {"Origin": "http://TESTSERVER"},
])
def test_intentional_local_narration_clients_and_cache_remain_available(tmp_path, headers):
    graph = _project(tmp_path / "project")
    provider = _Provider()
    studies = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")
    with TestClient(create_app(graph, study_service=studies)) as client:
        assert client.get("/api/node/app.main/explanation", headers=headers).json()["status"] == "ready"
        assert client.get("/api/node/app.main/explanation", headers=headers).json()["cached"] is True
        assert provider.calls == 1


def test_no_key_study_and_narration_stay_local(tmp_path):
    graph = _project(tmp_path / "project")
    cache = tmp_path / "cache"
    studies = StudyService(graph, cache_root=cache)
    with TestClient(create_app(graph, study_service=studies)) as client:
        assert client.get("/api/node/app.main/study").json()["source"]["file"] == "app.py"
        assert client.get("/api/node/app.main/explanation").json()["status"] == "no_key"
    assert not cache.exists()


@pytest.mark.parametrize("invalid", [[], {}, None, 42, True])
@pytest.mark.parametrize("document", ["project", "learner"])
def test_malformed_modes_tolerate_startup_but_keep_strict_recovery_uncertain(
    tmp_path, invalid, document,
):
    graph = _project(tmp_path / "project")
    progress = ProgressStore(graph, tmp_path / "progress")
    progress.mark_understood("app")
    if document == "project":
        payload = json.loads(progress.path.read_text())
        progress.path.write_text(json.dumps({**payload, "mode": invalid}))
    else:
        progress._learner_path.write_text(json.dumps({"mode": invalid}))
    before = progress.path.read_bytes()
    assert progress.mode() == "easy"
    assert progress.mode_chosen() is False
    with pytest.raises(ModeReadUncertainError):
        progress.confirmed_mode_state()
    studies = StudyService(graph, cache_root=tmp_path / "cache")
    checks = CheckService(graph, progress)
    with TestClient(create_app(graph, study_service=studies, check_service=checks)) as client:
        assert client.get("/api/mode").json() == {"mode": "easy", "chosen": False}
        strict = client.get("/api/mode?strict=true")
        assert strict.status_code == 503
        assert strict.json()["detail"]["reason"] == "mode_read_uncertain"
    assert progress.understood_regions() == frozenset({"app"})
    assert progress.path.read_bytes() == before


def test_valid_project_override_survives_malformed_learner_mode(tmp_path):
    graph = _project(tmp_path / "project")
    progress = ProgressStore(graph, tmp_path / "progress")
    progress.mark_understood("app")
    progress.set_mode("expert")
    progress._learner_path.write_text('{"mode":[]}')
    assert progress.mode() == "expert"
    assert progress.mode_chosen() is True
    assert progress.confirmed_mode_state() == {"mode": "expert", "chosen": True}
    assert progress.understood_regions() == frozenset({"app"})
