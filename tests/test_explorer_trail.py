"""The explorer's trail: travelling charts the map, understanding lights it.

Two claims about a region that must never collapse into one:

* **explored** -- the learner has flown here. Earned by travel, costs nothing,
  and says nothing whatever about comprehension.
* **understood** -- the learner passed this region's graph-derived checks.
  Earned only by evidence, and the only thing that may ever burn amber.

Every test here exists to keep those apart, and to keep the trail from
acquiring the properties of progress it must not have.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.checks import CheckService
from codemble.progress import ProgressStore
from codemble.server.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def _store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(PythonAstAdapter().parse(FIXTURE), root=tmp_path)


def test_visiting_is_remembered_across_restarts(tmp_path: Path) -> None:
    store = _store(tmp_path)

    store.mark_visited("app")

    assert "app" in _store(tmp_path).visited_regions()


def test_visiting_never_marks_a_region_understood(tmp_path: Path) -> None:
    """The whole point of the trail: travel may not fake comprehension."""

    store = _store(tmp_path)

    store.mark_visited("app")

    assert store.visited_regions() == frozenset({"app"})
    assert store.understood_regions() == frozenset()


def test_a_changed_file_keeps_the_trail_but_drops_the_understanding(
    tmp_path: Path,
) -> None:
    """Understanding is a claim about code; having been somewhere is not.

    ``understood`` is signature-scoped, so editing a file re-dims it -- the
    learner's proof no longer covers what is there now. A visit is a fact about
    the learner's own history and cannot be invalidated by an edit, so the two
    deliberately behave differently rather than sharing one rule.
    """

    graph = PythonAstAdapter().parse(FIXTURE)
    store = ProgressStore(graph, root=tmp_path)
    store.mark_visited("app")
    store.mark_understood("app")

    from dataclasses import replace

    edited = replace(graph, file_hashes={**graph.file_hashes, "app.py": "edited"})
    after = ProgressStore(edited, root=tmp_path)

    assert after.understood_regions() == frozenset()
    assert after.visited_regions() == frozenset({"app"})


def test_a_region_that_no_longer_exists_leaves_the_trail(tmp_path: Path) -> None:
    """A stale id must not be reported as somewhere in this project."""

    store = _store(tmp_path)
    store.mark_visited("app")
    payload = json.loads(store.path.read_text(encoding="utf-8"))
    payload["visited"] = ["app", "deleted.module"]
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    assert _store(tmp_path).visited_regions() == frozenset({"app"})


def test_clearing_progress_clears_the_trail_too(tmp_path: Path) -> None:
    """A reset that leaves a trail behind is a half reset.

    This mirrors the 2026-08-01 fix: one caller clears everything it owns, or
    the two halves drift into a state no surface is written for.
    """

    store = _store(tmp_path)
    store.mark_visited("app")
    store.mark_understood("app")

    store.clear()

    assert store.visited_regions() == frozenset()
    assert store.understood_regions() == frozenset()


def test_the_trail_survives_an_older_progress_file(tmp_path: Path) -> None:
    """Every learner already has a file on disk with no `visited` key.

    Adding one must not bump the schema version: ``_read`` rejects any payload
    whose version differs, so a bump would silently discard every existing
    learner's understood set.
    """

    store = _store(tmp_path)
    store.mark_understood("app")
    payload = json.loads(store.path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    payload.pop("visited", None)
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    reopened = _store(tmp_path)

    assert reopened.visited_regions() == frozenset()
    assert reopened.understood_regions() == frozenset({"app"})


def test_the_visit_endpoint_records_and_returns_the_trail(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, root=tmp_path))
    client = TestClient(create_app(graph, tmp_path / "missing", check_service=checks))

    empty = client.get("/api/progress/visited")
    recorded = client.post("/api/progress/visited", json={"region_id": "app"})

    assert empty.json()["visited"] == []
    assert recorded.status_code == 200
    assert recorded.json()["visited"] == ["app"]
    assert client.get("/api/progress/visited").json()["visited"] == ["app"]


def test_visiting_an_unknown_region_is_refused(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, root=tmp_path))
    client = TestClient(create_app(graph, tmp_path / "missing", check_service=checks))

    response = client.post("/api/progress/visited", json={"region_id": "invented"})

    assert response.status_code == 404


def test_clearing_progress_over_http_empties_the_trail(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = CheckService(graph, ProgressStore(graph, root=tmp_path))
    client = TestClient(create_app(graph, tmp_path / "missing", check_service=checks))
    client.post("/api/progress/visited", json={"region_id": "app"})

    client.delete("/api/progress")

    assert client.get("/api/progress/visited").json()["visited"] == []
