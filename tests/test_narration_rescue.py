"""Narration must fail small, fail honestly, and never stall the rest of the app.

Every test here traces to a defect found by tracing why a learner reported that
"most of the stuff in the study view doesn't load":

* one slow provider call could exhaust the request threadpool and stall
  ``/api/graph``, ``/api/map``, ``/study`` and ``/checks`` alongside it;
* a single formatting fault discarded a perfectly good summary;
* a network timeout was displayed as a correctness refusal;
* a module node numbered its whole file into the prompt;
* the expert structural summary was a metadata line that read as a stub.

The contract these tests must NOT relax: invented structure stays fatal. See
``test_fabrication_is_never_salvaged``.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codemble.adapters.base import Node
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.llm.providers import (
    ProviderError,
    ProviderRejectedError,
    ProviderUnavailableError,
)
from codemble.llm.structural import structural_summary
from codemble.llm.study import StudyService
from codemble.server.app import _NARRATION_SLOTS, create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def _graph():
    return PythonAstAdapter().parse(FIXTURE)


class _Provider:
    """A provider whose single response body each test dictates outright."""

    name = "fake"
    model = "grounded-test"

    def __init__(self, body: object) -> None:
        self._body = body
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        if isinstance(self._body, Exception):
            raise self._body
        return self._body if isinstance(self._body, str) else json.dumps(self._body)


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "summary": "This function coordinates the parser-observed calls shown below.",
        "walkthrough": [
            {"line": 9, "explanation": "This line creates the observed service object."}
        ],
        "relationships": [],
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------
# Salvage: formatting faults degrade; fabrication does not.
# --------------------------------------------------------------------------


def test_missing_walkthrough_keeps_the_summary(tmp_path: Path) -> None:
    """An absent walkthrough is not a grounding failure.

    It used to raise, which threw away a summary the learner could have read --
    and once the walkthrough is on demand, a response without one is ordinary.
    """

    provider = _Provider(_payload(walkthrough=[]))
    service = StudyService(_graph(), provider=provider, cache_root=tmp_path)

    result = service.explain("app.main")

    assert result["status"] == "ready"
    assert result["summary"]["text"]  # type: ignore[index]
    assert result["walkthrough"] == []


def test_one_overlong_item_is_dropped_not_the_whole_payload(tmp_path: Path) -> None:
    """Length is a formatting fault, so it costs one item, never the summary."""

    provider = _Provider(
        _payload(
            walkthrough=[
                {"line": 9, "explanation": "This line creates the observed service object."},
                {"line": 13, "explanation": "x" * 2500},
            ]
        )
    )
    service = StudyService(_graph(), provider=provider, cache_root=tmp_path)

    result = service.explain("app.main")

    assert result["status"] == "ready"
    assert len(result["walkthrough"]) == 1  # type: ignore[arg-type]
    assert result["withheld"] == 1, "the learner must be told something was dropped"


def test_fabrication_is_never_salvaged(tmp_path: Path) -> None:
    """The Correctness Contract outranks the reliability goal.

    A relationship naming a node the parser never observed is invented
    structure. Salvaging the rest would display prose produced by a model that
    demonstrably just made something up -- and the audience cannot detect it.
    """

    provider = _Provider(
        _payload(
            relationships=[
                {"node_id": "invented.module", "explanation": "not in the graph"}
            ]
        )
    )
    service = StudyService(_graph(), provider=provider, cache_root=tmp_path)

    result = service.explain("app.main")

    assert result["status"] == "error"
    assert result["reason"] == "grounding"
    assert not list(tmp_path.glob("*.json")), "a refused payload must never cache"


def test_citation_outside_the_studied_span_stays_fatal(tmp_path: Path) -> None:
    provider = _Provider(
        _payload(walkthrough=[{"line": 9999, "explanation": "outside the span"}])
    )
    service = StudyService(_graph(), provider=provider, cache_root=tmp_path)

    result = service.explain("app.main")

    assert result["status"] == "error"
    assert result["reason"] == "grounding"


# --------------------------------------------------------------------------
# Honest error copy: a broken network is not a correctness refusal.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ProviderUnavailableError("unreachable"), "unavailable"),
        (ProviderRejectedError("rejected with HTTP 400"), "rejected"),
        (ProviderError("odd shape"), "provider"),
    ],
)
def test_each_failure_kind_reports_its_own_reason(
    tmp_path: Path, error: Exception, reason: str
) -> None:
    """The panel prints a correctness lecture for a grounding refusal only.

    All three used to collapse into the same branch, so a flaky connection told
    the learner Codemble had withheld output that fell outside parser evidence.
    """

    service = StudyService(_graph(), provider=_Provider(error), cache_root=tmp_path)

    result = service.explain("app.main")

    assert result["status"] == "error"
    assert result["reason"] == reason


# --------------------------------------------------------------------------
# Prompt: bounded source, and no instruction the contract forbids obeying.
# --------------------------------------------------------------------------


def test_a_long_span_is_sent_as_a_bounded_excerpt(tmp_path: Path) -> None:
    """A module node spans its whole file, which overflowed provider context."""

    long_file = tmp_path / "proj" / "wide.py"
    long_file.parent.mkdir(parents=True)
    long_file.write_text("\n".join(f"value_{n} = {n}" for n in range(600)), encoding="utf-8")
    graph = PythonAstAdapter().parse(long_file.parent)
    provider = _Provider(_payload(walkthrough=[{"line": 1, "explanation": "assigns a value."}]))
    service = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")

    module_id = next(node.id for node in graph.nodes if node.kind == "module")
    result = service.explain(module_id)

    prompt = provider.prompts[0]
    assert result["status"] == "ready"
    assert "0599:" not in prompt, "the whole file must not reach the provider"
    assert "excerpt" in prompt.lower(), "the excerpt must announce itself as one"


def test_a_walkthrough_may_not_cite_a_line_the_excerpt_withheld(tmp_path: Path) -> None:
    """Explaining an unseen line is a guess, even when the line is real."""

    long_file = tmp_path / "proj" / "wide.py"
    long_file.parent.mkdir(parents=True)
    long_file.write_text("\n".join(f"value_{n} = {n}" for n in range(600)), encoding="utf-8")
    graph = PythonAstAdapter().parse(long_file.parent)
    provider = _Provider(
        _payload(walkthrough=[{"line": 590, "explanation": "a line never supplied."}])
    )
    service = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")

    module_id = next(node.id for node in graph.nodes if node.kind == "module")
    result = service.explain(module_id)

    assert result["status"] == "error"
    assert result["reason"] == "grounding"


def test_expert_is_not_told_to_exceed_its_own_evidence(tmp_path: Path) -> None:
    """The expert block asked for the wider project; the contract forbids it.

    That pairing is what drove expert-only fabrication, and therefore the
    expert-only refusal rate the learner reported as "it doesn't load".
    """

    provider = _Provider(_payload())
    service = StudyService(_graph(), provider=provider, cache_root=tmp_path)

    service.explain("app.main", "expert")

    prompt = provider.prompts[0]
    assert "wider project" not in prompt
    assert "A relationship may name only one of the supplied neighbor node IDs." in prompt


# --------------------------------------------------------------------------
# Tier 0: the expert voice must read as prose, not as a stub.
# --------------------------------------------------------------------------


def test_expert_structural_summary_is_prose(tmp_path: Path) -> None:
    node = Node(
        id="pkg/app.py::run",
        kind="function",
        name="run",
        language="python",
        file="pkg/app.py",
        lineno=41,
        end_lineno=88,
        loc=48,
        region="pkg/app.py",
    )

    expert = structural_summary(node, [], [])["expert"]

    assert expert.endswith("."), "a metadata line reads as a section that failed to load"
    assert expert.count(" · ") == 0
    assert "run" in expert and "pkg/app.py:41" in expert


# --------------------------------------------------------------------------
# Isolation: narration may never delay a parser-only endpoint.
# --------------------------------------------------------------------------


def test_in_flight_narration_is_bounded_by_its_own_budget(tmp_path: Path) -> None:
    """Narration concurrency is capped, which is what protects every other route.

    The reported defect: every route was a plain ``def``, so all of them shared
    anyio's default request threadpool, and an uncancellable ``urlopen`` held
    its thread for the provider's whole timeout. Enough in-flight explanations
    therefore starved ``/api/graph``, ``/api/map``, ``/study`` and ``/checks``.

    **What this test can and cannot prove, stated rather than implied.** The
    starvation cascade itself is *not* reproducible in-process: ``TestClient``
    gives each threaded request its own event loop, so there is no shared
    default limiter to exhaust. Measured directly, 45 concurrent requests
    against the old sync route ran 45 provider calls at once and ``/api/graph``
    still answered in 0.01s. A test asserting the parser endpoints stay
    responsive therefore passes with the fix reverted -- it looks like a gate
    and is worth nothing.

    What is real, and what fails the moment the dedicated limiter is dropped,
    is the bound: no matter how many explanations are in flight, at most
    ``_NARRATION_SLOTS`` provider calls run together. Under a real uvicorn --
    one event loop, one shared 40-slot pool -- that bound is exactly what keeps
    the parser endpoints' budget intact. Pre-fix this measures 45; post-fix, 4.
    """

    release = threading.Event()
    lock = threading.Lock()
    live = 0
    peak = 0

    class HangingProvider:
        name = "hanging"
        model = "test"

        def complete(self, prompt: str) -> str:
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            release.wait(timeout=60)
            with lock:
                live -= 1
            return json.dumps(_payload())

    graph = _graph()
    studies = StudyService(graph, provider=HangingProvider(), cache_root=tmp_path / "c")
    app = create_app(graph, tmp_path / "missing", studies)
    client = TestClient(app)

    stuck = [
        threading.Thread(
            target=lambda: client.get("/api/node/app.main/explanation"), daemon=True
        )
        for _ in range(45)
    ]
    try:
        for thread in stuck:
            thread.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            with lock:
                if peak >= _NARRATION_SLOTS:
                    break
            time.sleep(0.05)

        with lock:
            observed = peak
        assert observed == _NARRATION_SLOTS, (
            f"narration ran {observed} provider calls at once; the dedicated "
            f"limiter must hold it to {_NARRATION_SLOTS} however many arrive"
        )
    finally:
        release.set()
        for thread in stuck:
            thread.join(timeout=60)


def test_a_slow_provider_returns_a_timeout_instead_of_hanging_the_request(
    tmp_path: Path,
) -> None:
    """The learner gets a bounded, retryable answer rather than a dead spinner."""

    release = threading.Event()

    class SlowProvider:
        name = "slow"
        model = "test"

        def complete(self, prompt: str) -> str:
            release.wait(timeout=30)
            return json.dumps(_payload())

    graph = _graph()
    studies = StudyService(graph, provider=SlowProvider(), cache_root=tmp_path / "c")
    app = create_app(graph, tmp_path / "missing", studies)
    app.state.narration_deadline_seconds = 0.25
    client = TestClient(app)

    try:
        response = client.get("/api/node/app.main/explanation")

        assert response.status_code == 200
        assert response.json()["status"] == "timeout"
        assert response.json()["retryable"] is True
    finally:
        release.set()
