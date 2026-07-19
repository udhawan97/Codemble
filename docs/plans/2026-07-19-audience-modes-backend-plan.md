# Audience Modes — Backend (Phases 1–3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Codemble a deterministic explanation floor that needs no model, two audience voices over one unchanged graph truth, and Ollama as an optional local narration provider.

**Architecture:** Three explanation tiers — Tier 0 renders parser facts through fixed templates and always appears; Tiers 1/2 (local Ollama, cloud BYO key) add narration through the existing `NarrationProvider` seam and the existing grounding validator. The study endpoint splits so structure never waits on a model. Mode is a presentation concern: lens notes, check prompts, and Tier 0 ship in both voices and the frontend selects; only narration sends `mode` to the server, because only narration is generated rather than selected.

**Tech Stack:** Python 3.11+, FastAPI, pytest, ruff. Standard library only — no new dependencies.

**Source spec:** `docs/plans/2026-07-19-audience-modes-and-local-narration-design.md`

## Global Constraints

- **Correctness Contract outranks every task.** Structure is never invented; explanations are grounded; check answers come from the graph, never a model; approximate call edges stay labelled possible.
- **Mode never changes truth.** Graph bytes, layout, determinism, check *answers*, and edge certainty must be byte-identical in both modes. Only wording changes.
- **Mode values are exactly `"easy"` and `"expert"`.** No other value is accepted anywhere.
- **Recommended local model is `gemma4:12b`; low-RAM fallback is `qwen3:8b`.** Maximum 12B parameters.
- **No new runtime dependencies.** `urllib` only, matching the existing providers.
- **Tests are the gate:** `pytest` and `ruff check .` must both pass before every commit.
- **Never echo provider response bodies or credentials in errors** — matches existing `ProviderError` behaviour.
- **Phases 1–3 touch no files under `web/`.** The frontend lands in phases 4–6, so `codemble/web_dist` is not rebuilt in this plan.

---

## File Structure

| Path | Responsibility | Phase |
| --- | --- | --- |
| `codemble/llm/structural.py` | **Create.** Tier 0: render graph facts as dual-voice sentences. No inference. | 1 |
| `codemble/llm/study.py` | **Modify.** Split `study()` from `explain()`; add direction to neighbours; mode in prompt and cache key. | 1, 2 |
| `codemble/server/app.py` | **Modify.** Add `/api/node/{id}/explanation`, `/api/llm/status`, mode endpoints. | 1, 2, 3 |
| `codemble/lens/python.py` | **Modify.** Note table gains an easy and an expert string per concept. | 2 |
| `codemble/lens/javascript_typescript.py` | **Modify.** Same dual-voice table change. | 2 |
| `codemble/checks/service.py` | **Modify.** `Check.prompt` becomes dual-voice; answers unchanged. | 2 |
| `codemble/progress/store.py` | **Modify.** Persist the learner's mode; must not touch region signatures. | 2 |
| `codemble/llm/providers.py` | **Modify.** Add `OllamaProvider` and a loopback-only transport. | 3 |
| `tests/test_structural.py` | **Create.** Tier 0 templates in both voices. | 1 |
| `tests/test_study.py` | **Modify.** Endpoint split, cache-key mode isolation, mode prompt. | 1, 2 |
| `tests/test_checks.py` | **Modify.** Dual-voice prompts, identical answers. | 2 |
| `tests/test_server.py` | **Modify.** New endpoints and their error shapes. | 1, 2, 3 |
| `tests/test_providers.py` | **Create.** `OllamaProvider` through an injected transport; no network. | 3 |

---

# PHASE 1 — Tier 0 structural summary + endpoint split

### Task 1: Neighbour direction

`structural_summary` must count inbound versus outbound relationships, but `_neighbors` currently collapses direction — `_neighbor_id` returns the other end without recording which end it was. This task makes direction explicit.

**Files:**
- Modify: `codemble/llm/study.py:191-210` (`_neighbors`), `codemble/llm/study.py:299-304` (`_neighbor_id`)
- Test: `tests/test_study.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: every neighbour dict from `StudyService._neighbors` gains `"direction": "inbound" | "outbound"`. Task 2 depends on this key.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_study.py`:

`tests/test_study.py` has no shared service helper — each test builds its own from `FIXTURE` (`tests/fixtures/sampleproj`). Follow that pattern exactly:

```python
def test_neighbors_record_edge_direction(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )

    neighbors = service.study("app.main")["neighbors"]  # type: ignore[index]

    directions = {neighbor["direction"] for neighbor in neighbors}
    assert directions <= {"inbound", "outbound"}
    assert any(neighbor["direction"] == "outbound" for neighbor in neighbors)
```

`app.main` constructs `pkg.service.Service`, so it always has at least one outbound edge in this fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study.py::test_neighbors_record_edge_direction -v`
Expected: FAIL with `KeyError: 'direction'`

- [ ] **Step 3: Write minimal implementation**

Replace `_neighbor_id` in `codemble/llm/study.py`:

```python
def _neighbor_id(edge: Edge, node_id: str) -> tuple[str, str] | None:
    if edge.src == node_id and not edge.external:
        return edge.dst, "outbound"
    if edge.dst == node_id:
        return edge.src, "inbound"
    return None
```

In `_neighbors`, replace the lookup and add the key:

```python
    def _neighbors(self, node: Node) -> list[dict[str, object]]:
        observations: dict[tuple[str, str, int], dict[str, object]] = {}
        for edge in self._graph.edges:
            resolved = _neighbor_id(edge, node.id)
            if resolved is None:
                continue
            neighbor_id, direction = resolved
            neighbor = self._nodes.get(neighbor_id)
            if neighbor is None:
                continue
            key = (neighbor.id, edge.kind, edge.lineno)
            observations[key] = {
                "node_id": neighbor.id,
                "name": neighbor.name,
                "kind": neighbor.kind,
                "file": neighbor.file,
                "line": neighbor.lineno,
                "citation": f"{neighbor.file}:{neighbor.lineno}",
                "relationship": edge.kind,
                "certain": edge.certain,
                "direction": direction,
                "observed_line": edge.lineno,
            }
        return [observations[key] for key in sorted(observations)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_study.py -v && ruff check .`
Expected: PASS, all existing study tests still green

- [ ] **Step 5: Commit**

```bash
git add codemble/llm/study.py tests/test_study.py
git commit -m "feat(study): record neighbour edge direction"
```

---

### Task 2: Tier 0 structural summary

**Files:**
- Create: `codemble/llm/structural.py`
- Test: `tests/test_structural.py`

**Interfaces:**
- Consumes: `"direction"` on neighbour dicts (Task 1).
- Produces: `structural_summary(node: Node, neighbors: list[dict[str, object]], lens: list[dict[str, object]]) -> dict[str, str]` returning exactly `{"easy": str, "expert": str}`. Task 3 calls this.

- [ ] **Step 1: Write the failing test**

Create `tests/test_structural.py`:

```python
"""Tier 0 renders graph facts only; it must never infer."""

from codemble.adapters.base import Node
from codemble.llm.structural import structural_summary


def _node(**overrides: object) -> Node:
    values: dict[str, object] = {
        "id": "pkg/app.py::run",
        "kind": "function",
        "name": "run",
        "language": "python",
        "file": "pkg/app.py",
        "lineno": 41,
        "end_lineno": 88,
        "loc": 48,
        "region": "pkg/app.py",
    }
    values.update(overrides)
    return Node(**values)  # type: ignore[arg-type]


def _neighbor(direction: str, certain: bool = True) -> dict[str, object]:
    return {
        "node_id": "pkg/other.py::helper",
        "name": "helper",
        "kind": "function",
        "file": "pkg/other.py",
        "line": 3,
        "citation": "pkg/other.py:3",
        "relationship": "call",
        "certain": certain,
        "direction": direction,
        "observed_line": 44,
    }


def test_both_voices_name_the_structure_and_its_location():
    summary = structural_summary(_node(), [], [])
    assert "run" in summary["easy"]
    assert "pkg/app.py" in summary["easy"]
    assert "pkg/app.py:41-88" in summary["expert"]


def test_easy_voice_spells_small_counts_and_expert_uses_digits():
    neighbors = [_neighbor("inbound"), _neighbor("inbound"), _neighbor("outbound")]
    summary = structural_summary(_node(), neighbors, [])
    assert "Two other parts" in summary["easy"]
    assert "Inbound 2" in summary["expert"]
    assert "Outbound 1" in summary["expert"]


def test_possible_relationships_stay_labelled_possible_in_both_voices():
    neighbors = [_neighbor("inbound", certain=False)]
    summary = structural_summary(_node(), neighbors, [])
    assert "possible" in summary["easy"].lower()
    assert "possible" in summary["expert"].lower()


def test_zero_neighbours_is_stated_not_omitted():
    summary = structural_summary(_node(), [], [])
    assert "Nothing else in your code uses it yet." in summary["easy"]
    assert "Inbound 0" in summary["expert"]


def test_partial_parse_is_disclosed_in_both_voices():
    summary = structural_summary(_node(partial=True), [], [])
    assert "could not be fully read" in summary["easy"]
    assert "partial parse" in summary["expert"]


def test_lens_concepts_are_listed_when_present_and_omitted_when_not():
    lens = [{"concept": "decorator", "title": "Decorator"}]
    with_concepts = structural_summary(_node(), [], lens)
    assert "Decorator" in with_concepts["easy"]
    assert "decorator" in with_concepts["expert"]
    without = structural_summary(_node(), [], [])
    assert "ideas" not in without["easy"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structural.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codemble.llm.structural'`

- [ ] **Step 3: Write minimal implementation**

Create `codemble/llm/structural.py`:

```python
"""Tier 0 narration: parser facts rendered through fixed templates.

This module performs no inference and calls no model.  Every clause traces to
a field the graph already owns, which is why it is safe to render with no key,
no network, and no provider configured at all.
"""

from __future__ import annotations

from codemble.adapters.base import Node

_COUNT_WORDS = (
    "No",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
)

_KIND_WORDS = {
    "module": "file",
    "function": "function",
    "class": "class",
    "method": "function inside a class",
}


def structural_summary(
    node: Node,
    neighbors: list[dict[str, object]],
    lens: list[dict[str, object]],
) -> dict[str, str]:
    """Return the same parser facts in a beginner and an expert voice."""

    inbound = [item for item in neighbors if item.get("direction") == "inbound"]
    outbound = [item for item in neighbors if item.get("direction") == "outbound"]
    possible = [item for item in neighbors if not item.get("certain", True)]
    titles = [str(item.get("title", "")) for item in lens if item.get("title")]
    concepts = [str(item.get("concept", "")) for item in lens if item.get("concept")]
    return {
        "easy": _easy_voice(node, inbound, outbound, possible, titles),
        "expert": _expert_voice(node, inbound, outbound, possible, concepts),
    }


def _easy_voice(
    node: Node,
    inbound: list[dict[str, object]],
    outbound: list[dict[str, object]],
    possible: list[dict[str, object]],
    titles: list[str],
) -> str:
    kind = _KIND_WORDS.get(node.kind, node.kind)
    sentences = [
        f"This is {node.name}, a {kind}.",
        f"It lives in {node.file}, starting on line {node.lineno}.",
    ]
    sentences.append(
        f"{_count_word(len(inbound))} other "
        f"{'part' if len(inbound) == 1 else 'parts'} of your code "
        f"{'uses' if len(inbound) == 1 else 'use'} it."
        if inbound
        else "Nothing else in your code uses it yet."
    )
    sentences.append(
        f"It uses {_count_word(len(outbound)).lower()} other "
        f"{'part' if len(outbound) == 1 else 'parts'} of your code."
        if outbound
        else "It does not use any other part of your code."
    )
    if possible:
        sentences.append(
            f"{_count_word(len(possible))} of those "
            f"{'link is' if len(possible) == 1 else 'links are'} a possible "
            "connection, not a certain one."
        )
    if titles:
        sentences.append(f"Ideas found here: {_join_words(titles)}.")
    if node.partial:
        sentences.append(
            "Your file could not be fully read, so some parts may be missing."
        )
    return " ".join(sentences)


def _expert_voice(
    node: Node,
    inbound: list[dict[str, object]],
    outbound: list[dict[str, object]],
    possible: list[dict[str, object]],
    concepts: list[str],
) -> str:
    fields = [
        f"{node.name} · {node.kind} · {node.file}:{node.lineno}-{node.end_lineno}"
        f" ({node.loc} lines)",
        f"Inbound {len(inbound)} · Outbound {len(outbound)}"
        + (f" · {len(possible)} possible" if possible else ""),
    ]
    if concepts:
        fields.append(f"Concepts: {', '.join(concepts)}")
    if node.partial:
        fields.append("partial parse — structure incomplete")
    return " · ".join(fields)


def _count_word(count: int) -> str:
    return _COUNT_WORDS[count] if count < len(_COUNT_WORDS) else str(count)


def _join_words(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} and {values[-1]}"


__all__ = ["structural_summary"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_structural.py -v && ruff check .`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add codemble/llm/structural.py tests/test_structural.py
git commit -m "feat(study): add deterministic Tier 0 structural summary"
```

---

### Task 3: Split study from narration

**Files:**
- Modify: `codemble/llm/study.py:127-164` (`study`), `codemble/llm/study.py:212-253` (`_explain`)
- Test: `tests/test_study.py`

**Interfaces:**
- Consumes: `structural_summary` (Task 2).
- Produces:
  - `StudyService.study(node_id: str) -> dict` — no provider call ever; payload gains `"structural": {"easy": str, "expert": str}` and keeps `"explanation"` as a deferred placeholder.
  - `StudyService.explain(node_id: str, mode: str = "easy") -> dict` — performs the provider call. Task 4 (server) and Task 7 (mode) both use it.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_study.py`:

```python
def test_study_never_calls_the_provider(tmp_path: Path) -> None:
    class RefusingProvider:
        name = "refusing"
        model = "test"

        def complete(self, prompt: str) -> str:
            raise AssertionError("study() must not reach the provider")

    graph = PythonAstAdapter().parse(FIXTURE)
    service = StudyService(
        graph, provider=RefusingProvider(), cache_root=tmp_path / "cache"
    )

    payload = service.study("app.main")

    assert payload["structural"]["easy"]  # type: ignore[index]
    assert payload["structural"]["expert"]  # type: ignore[index]
    assert payload["explanation"]["status"] == "deferred"  # type: ignore[index]


def test_explain_reaches_the_provider(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")

    result = service.explain("app.main", "easy")

    assert result["status"] == "ready"
    assert provider.calls == 1
```

`FakeProvider` already exists at the top of `tests/test_study.py` and returns a
response that satisfies `_validate_explanation` for `app.main`. Note that it
asserts `"app.py:8-13" in prompt`, so it only works for that node.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study.py::test_study_never_calls_the_provider -v`
Expected: FAIL with `KeyError: 'structural'`

- [ ] **Step 3: Write minimal implementation**

In `codemble/llm/study.py`, add the import:

```python
from codemble.llm.structural import structural_summary
```

Replace the body of `study` from the `explanation = (` assignment to the `return` with:

```python
        return {
            "node": asdict(node),
            "source": source,
            "neighbors": neighbors,
            "lens": lens,
            "structural": structural_summary(node, neighbors, lens),
            "explanation": {
                "status": "deferred",
                "message": "Narration loads separately.",
                "cached": False,
            },
        }
```

Add a new public method directly after `study`:

```python
    def explain(self, node_id: str, mode: str = "easy") -> dict[str, object]:
        """Return only the narration state for one node in one audience voice."""

        node = self._nodes.get(node_id)
        if node is None:
            raise UnknownNodeError(node_id)
        if node.partial:
            return {
                "status": "partial",
                "message": (
                    "Narration is unavailable because the language parser reported "
                    "syntax errors in this file. The raw source remains visible."
                ),
                "cached": False,
            }
        source = self._read_source(node)
        neighbors = self._neighbors(node)
        annotations = sorted(
            (
                annotation
                for annotation in self._graph.concept_annotations
                if annotation.node_id == node.id
            ),
            key=lambda item: (item.lineno, item.concept, item.end_lineno),
        )
        lens = lens_notes(node.language, annotations)
        for note in lens:
            note["citation"] = f"{node.file}:{note['line']}"
        return self._explain(node, source, neighbors, lens, mode)
```

Change `_explain`'s signature to take `mode: str` as its final parameter, and leave its body unchanged for now (Task 7 threads mode into the prompt and cache key):

```python
    def _explain(
        self,
        node: Node,
        source: dict[str, object],
        neighbors: list[dict[str, object]],
        lens: list[dict[str, object]],
        mode: str,
    ) -> dict[str, object]:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_study.py -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/llm/study.py tests/test_study.py
git commit -m "feat(study): split structure from narration"
```

---

### Task 4: Narration endpoint

**Files:**
- Modify: `codemble/server/app.py:79-91`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `StudyService.explain(node_id, mode)` (Task 3).
- Produces: `GET /api/node/{node_id}/explanation?mode=easy|expert`. Phase 4's frontend calls this.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py`:

`tests/test_server.py` builds its client inline as `TestClient(create_app(graph, tmp_path / "missing"))`. Follow that:

```python
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

    assert client.get("/api/node/nope/explanation?mode=easy").status_code == 404
```

With no key configured the first test returns `status: "no_key"`, which is a
valid narration state — the assertion deliberately does not require `ready`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -k explanation -v`
Expected: FAIL with 404 on all three (route does not exist)

- [ ] **Step 3: Write minimal implementation**

In `codemble/server/app.py`, add to the imports:

```python
from typing import Literal
```

Add this route immediately after `get_node_study`:

```python
    @app.get("/api/node/{node_id:path}/explanation")
    def get_node_explanation(
        node_id: str, mode: Literal["easy", "expert"] = "easy"
    ) -> dict[str, object]:
        try:
            return studies.explain(node_id, mode)
        except UnknownNodeError as error:
            raise HTTPException(
                status_code=404, detail="That source node is not in this graph."
            ) from error
        except StudySourceError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
```

Route order matters: `{node_id:path}` is greedy, so this must be declared before the SPA fallback route. It already is.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS (full suite)

- [ ] **Step 5: Commit and open the Phase 1 PR**

```bash
git add codemble/server/app.py tests/test_server.py
git commit -m "feat(server): add the narration endpoint"
git push -u origin HEAD
gh pr create --title "feat: Tier 0 structural summary and endpoint split" --body "Phase 1 of docs/plans/2026-07-19-audience-modes-and-local-narration-design.md

Adds a deterministic structural summary that renders with no model configured,
and splits narration out of the study endpoint so the panel never blocks on a
provider.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

# PHASE 2 — Mode plumbing

### Task 5: Dual-voice lens notes

**Files:**
- Modify: `codemble/lens/python.py:7-40`, `codemble/lens/javascript_typescript.py` (its note table)
- Test: `tests/test_study.py`

**Interfaces:**
- Produces: every lens note dict's `"note"` key becomes `{"easy": str, "expert": str}`. `"title"`, `"concept"`, `"line"`, `"end_line"`, `"snippet"`, `"citation"` are unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_study.py`:

```python
def test_every_lens_note_carries_both_voices(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(CONCEPT_FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )

    notes = service.study("concepts_sample.collect")["lens"]  # type: ignore[index]

    assert notes, "the concept fixture must produce at least one lens note"
    for note in notes:
        assert set(note["note"]) == {"easy", "expert"}
        assert note["note"]["easy"].strip()
        assert note["note"]["expert"].strip()


def test_no_concept_is_missing_a_voice():
    from codemble.lens.javascript_typescript import _NOTES
    from codemble.lens.python import _PYTHON_NOTES

    for table in (_PYTHON_NOTES, _NOTES):
        for concept, (title, voices) in table.items():
            assert title.strip(), concept
            assert voices["easy"].strip(), concept
            assert voices["expert"].strip(), concept
```

Both tables map `concept -> (title, voices)`, so the unpacking above is correct once Step 3 lands.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study.py -k lens -v`
Expected: FAIL — `note` is currently a string, so `set(note["note"])` is a set of characters

- [ ] **Step 3: Write minimal implementation**

In `codemble/lens/python.py`, change every table entry from `(title, explanation)` to `(title, {"easy": ..., "expert": ...})`. The expert string is the existing text verbatim; the easy string is new. Full replacement table:

```python
_PYTHON_NOTES = {
    "decorator": (
        "Decorator",
        {
            "easy": "The @ line above wraps this in extra behaviour before it runs. Think of it as a sticker that adds a rule.",
            "expert": "Python evaluates this decorator while defining the structure and binds the returned object to its name.",
        },
    ),
    "comprehension": (
        "Comprehension",
        {
            "easy": "This is a short way to build a list by looping in one line, instead of writing a longer loop.",
            "expert": "This expression builds a collection through inline iteration and optional filtering.",
        },
    ),
    "generator": (
        "Generator",
        {
            "easy": "This hands back one value at a time instead of building everything at once, which saves memory.",
            "expert": "This construct produces values lazily instead of building the complete sequence at once.",
        },
    ),
    "context-manager": (
        "Context manager",
        {
            "easy": "The `with` line opens something and promises to close it again, even if an error happens.",
            "expert": "The `with` protocol brackets this block with managed setup and cleanup behavior.",
        },
    ),
    "async-await": (
        "Async / await",
        {
            "easy": "This can pause while waiting for slow work, letting other things run instead of blocking.",
            "expert": "This construct participates in Python's asynchronous protocol and may yield control while work is pending.",
        },
    ),
    "dunder-method": (
        "Dunder method",
        {
            "easy": "The double underscores mean Python calls this for you, for things like len() or printing.",
            "expert": "Python calls this specially named method through a language protocol such as length, comparison, or display.",
        },
    ),
    "exception-handling": (
        "Exception handling",
        {
            "easy": "This plans for something going wrong, so the program can react instead of crashing.",
            "expert": "This construct makes failure part of explicit control flow by catching, grouping, or raising an exception.",
        },
    ),
    "type-hint": (
        "Type hint",
        {
            "easy": "This is a note about what kind of value belongs here. Python does not enforce it; it helps readers and tools.",
            "expert": "This annotation communicates an expected type to readers and tooling; Python does not enforce it by default.",
        },
    ),
}
```

The unpacking in `python_lens_notes` needs no change (`title, explanation = note`), because `explanation` is now the dict and is stored under `"note"` unchanged.

Now the JS/TS table. In `codemble/lens/javascript_typescript.py` the dict is named `_NOTES` (not `_JS_TS_NOTES` — correct the test import in Step 1 to `from codemble.lens.javascript_typescript import _NOTES`). Full replacement:

```python
_NOTES = {
    "async-await": (
        "Async / await",
        {
            "easy": "This waits for something slow, like loading data, without freezing the rest of the page.",
            "expert": "This syntax pauses the current async flow until the awaited value settles without blocking the JavaScript event loop.",
        },
    ),
    "arrow-function": (
        "Arrow function",
        {
            "easy": "A shorter way to write a function. The `=>` is the arrow it is named after.",
            "expert": "This compact function form captures `this` from its surrounding scope instead of creating its own `this` binding.",
        },
    ),
    "destructuring": (
        "Destructuring",
        {
            "easy": "This unpacks values out of an object or list and gives each one its own name, in one line.",
            "expert": "This pattern binds selected array positions or object properties directly to local names.",
        },
    ),
    "optional-chaining": (
        "Optional chaining",
        {
            "easy": "The `?.` checks whether something exists before reaching inside it, so a missing value cannot crash the code.",
            "expert": "This chain stops and yields `undefined` when the value before `?.` is `null` or `undefined`.",
        },
    ),
    "nullish-coalescing": (
        "Nullish coalescing",
        {
            "easy": "The `??` supplies a backup value, but only when the first one is missing. A zero or empty text still counts as a real value.",
            "expert": "This expression uses its right side only when the left side is `null` or `undefined`, preserving values such as `0` and an empty string.",
        },
    ),
    "module-syntax": (
        "Module syntax",
        {
            "easy": "This line either borrows code from another file or offers this file's code to others.",
            "expert": "This declaration makes a dependency or exported binding explicit in the source module graph.",
        },
    ),
    "type-annotation": (
        "Type annotation",
        {
            "easy": "This says what kind of value belongs here, so your editor can warn you before you run the code.",
            "expert": "TypeScript uses this annotation for static checking and editor tooling; the annotation itself does not become a runtime check.",
        },
    ),
    "interface": (
        "Interface",
        {
            "easy": "This describes the shape a value must have — which fields it needs — without creating anything that exists while the program runs.",
            "expert": "This TypeScript declaration names a structural type contract for checking and tooling without creating a runtime value.",
        },
    ),
    "generic": (
        "Generic",
        {
            "easy": "This lets one piece of code work with many kinds of value while remembering which kind it was given.",
            "expert": "This type parameter preserves a relationship between types while letting callers supply a concrete type.",
        },
    ),
    "jsx": (
        "JSX",
        {
            "easy": "This is HTML-looking code written inside JavaScript. A build step turns it into real JavaScript.",
            "expert": "This syntax describes an element or component tree that the configured toolchain transforms into JavaScript.",
        },
    ),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/lens/ tests/test_study.py
git commit -m "feat(lens): author both audience voices for every concept"
```

---

### Task 6: Dual-voice check prompts

**Files:**
- Modify: `codemble/checks/service.py:33-55` (`Check`), `:177-318` (the four generators), `:349-370` (`_check`)
- Test: `tests/test_checks.py`

**Interfaces:**
- Produces: `Check.prompt` becomes `dict[str, str]` with `easy` and `expert` keys; `Check.public()` emits it unchanged. `answer_ids`, `options`, and `id` are untouched.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_checks.py`:

`tests/test_checks.py` parses `FIXTURE` inline with `PythonAstAdapter().parse(FIXTURE)`. Follow that:

```python
def test_check_prompts_carry_both_voices() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)

    for region in graph.regions:
        for check in generate_checks(graph, region.id):
            assert set(check.prompt) == {"easy", "expert"}
            assert check.prompt["easy"].strip()
            assert check.prompt["expert"].strip()


def test_the_two_voices_ask_the_same_question_of_the_same_answer() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)

    for region in graph.regions:
        for check in generate_checks(graph, region.id):
            public = check.public(passed=False)
            assert public["prompt"] == check.prompt
            assert public["multiple"] == (len(check.answer_ids) > 1)
            offered = {option["id"] for option in public["options"]}
            assert set(check.answer_ids) <= offered
            assert offered - set(check.answer_ids), "every check keeps a wrong option"
```

The second test is the contract test: wording varies, but the answer set and the
wrong-option guarantee from commit `cb7f9af` are unchanged.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_checks.py -k voices -v`
Expected: FAIL — `prompt` is a string

- [ ] **Step 3: Write minimal implementation**

In `codemble/checks/service.py`, change the dataclass field:

```python
    prompt: dict[str, str]
```

Change `_check`'s parameter type to `prompt: dict[str, str]`. Then give each generator both voices — replace each `f"..."` prompt argument:

`_first_call_check`:

```python
        {
            "easy": f"Which piece of code does {source_id} run first?",
            "expert": f"Which structure does {source_id} call first?",
        },
```

`_importer_check` (incoming branch):

```python
        {
            "easy": f"Which of your files brings in {region_id} to use it?",
            "expert": f"Which project module imports {region_id} directly?",
        },
```

`_importer_check` (outgoing branch, `codemble/checks/service.py:258`):

```python
        {
            "easy": f"Which of your files does {region_id} bring in first?",
            "expert": f"Which project module does {region_id} import first?",
        },
```

`_impact_check` (`codemble/checks/service.py:293`):

```python
        {
            "easy": f"If {target_id} disappeared, which piece of code would break?",
            "expert": (
                f"Which structure directly depends on {target_id} "
                "and could break if it disappeared?"
            ),
        },
```

`_entrypoint_check`:

```python
        {
            "easy": "Which part of your code does the program start from?",
            "expert": "Which parser-ranked structure is selected as Home for this run?",
        },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS. If a server test asserts a string prompt, update it to assert the dict — the answers must not change.

- [ ] **Step 5: Commit**

```bash
git add codemble/checks/service.py tests/
git commit -m "feat(checks): phrase every question in both voices"
```

---

### Task 7: Mode in the prompt and the cache key

This closes the defect found during design: `_cache_key` omits mode, so easy and expert would serve each other's cached text.

**Files:**
- Modify: `codemble/llm/study.py:23` (`PROMPT_VERSION`), `:212-253` (`_explain`), `:307-311` (`_cache_key`), `:314-365` (`_grounded_prompt`)
- Test: `tests/test_study.py`

**Interfaces:**
- Consumes: `_explain(..., mode)` (Task 3).
- Produces: cache keys differ by mode; `_grounded_prompt(node, source, neighbors, lens, mode)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_study.py`:

`FakeProvider` already counts its calls via `self.calls` and returns a valid grounded response for `app.main`. Record the prompts by subclassing it:

```python
def test_easy_and_expert_do_not_share_a_cache_entry(tmp_path: Path) -> None:
    class RecordingProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.prompts: list[str] = []

        def complete(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return super().complete(prompt)

    graph = PythonAstAdapter().parse(FIXTURE)
    provider = RecordingProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")

    service.explain("app.main", "easy")
    service.explain("app.main", "expert")

    assert provider.calls == 2, "expert must not be served the easy cache entry"
    assert provider.prompts[0] != provider.prompts[1], "each mode sends its own style"

    service.explain("app.main", "easy")

    assert provider.calls == 2, "the repeated easy call must hit cache"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study.py -k cache_entry -v`
Expected: FAIL with `len(prompts) == 1` — expert wrongly hit the easy cache

- [ ] **Step 3: Write minimal implementation**

Bump the version constant in `codemble/llm/study.py`:

```python
PROMPT_VERSION = "study-v3"
```

Add the style table above `_grounded_prompt`:

```python
_MODE_STYLE = {
    "easy": (
        "AUDIENCE: someone new to programming.\n"
        "- Use short sentences and everyday words.\n"
        "- Explain any technical term in the same sentence you use it.\n"
        "- Assume no knowledge of frameworks, patterns, or jargon.\n"
    ),
    "expert": (
        "AUDIENCE: an experienced developer onboarding onto this codebase.\n"
        "- Be concise and precise; assume language fluency.\n"
        "- Lead with this structure's role in the wider project.\n"
        "- Use standard terminology without defining it.\n"
    ),
}
```

Change `_cache_key` to include mode:

```python
def _cache_key(
    provider: NarrationProvider, node: Node, file_hash: str, mode: str
) -> str:
    material = "\0".join(
        (PROMPT_VERSION, provider.name, provider.model, node.id, file_hash, mode)
    ).encode()
    return hashlib.sha256(material).hexdigest()
```

In `_explain`, thread mode through both calls:

```python
        cache_key = _cache_key(self._provider, node, file_hash, mode)
```
```python
        prompt = _grounded_prompt(node, source, neighbors, lens, mode)
```

Change `_grounded_prompt`'s signature to accept `mode: str` and insert the style block into the returned template, directly above `HARD CORRECTNESS CONTRACT:`:

```python
    return f"""You are the narration layer in Codemble, a code-learning tool.

{_MODE_STYLE.get(mode, _MODE_STYLE["easy"])}
HARD CORRECTNESS CONTRACT:
```

The rest of the template is unchanged. The contract stays below the audience
block so style can never be read as permission to loosen grounding.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/llm/study.py tests/test_study.py
git commit -m "fix(study): key the explanation cache by audience mode"
```

---

### Task 8: Mode persistence

**Files:**
- Modify: `codemble/progress/store.py`, `codemble/server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `ProgressStore.mode() -> str` and `ProgressStore.set_mode(mode: str) -> None`; `GET /api/mode` and `PUT /api/mode`. Phase 4's frontend calls both.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py`:

`ProgressStore` writes under `CODEMBLE_DATA_DIR`, so the test must point that at `tmp_path` via `monkeypatch` to avoid touching the real `~/.codemble/`:

```python
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
    client = TestClient(create_app(graph, tmp_path / "missing"))

    before = client.get("/api/graph").json()
    client.put("/api/mode", json={"mode": "expert"})

    assert client.get("/api/graph").json() == before
```

Add `import pytest` to `tests/test_server.py` if it is not already imported.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -k mode -v`
Expected: FAIL with 404 — the routes do not exist

- [ ] **Step 3: Write minimal implementation**

In `codemble/progress/store.py`, add two methods to `ProgressStore`. They read and write the same payload the store already persists, under a key that `_region_signatures` never inspects, so mode cannot influence invalidation:

```python
    def mode(self) -> str:
        """Return the learner's audience mode; this never affects progress."""

        payload = self._read()
        value = payload.get("mode")
        return value if value in {"easy", "expert"} else "easy"

    def set_mode(self, mode: str) -> None:
        """Persist the audience mode beside progress without touching signatures."""

        if mode not in {"easy", "expert"}:
            raise ValueError("Mode must be 'easy' or 'expert'.")
        payload = self._read()
        payload["mode"] = mode
        self._write(payload)
```

Confirm `_empty_payload` does not need a `mode` key — `mode()` already defaults safely when it is absent.

In `codemble/server/app.py`, add the request model beside the existing ones:

```python
class ModeSelection(BaseModel):
    """The learner's chosen audience voice."""

    mode: Literal["easy", "expert"]
```

And the routes, before the SPA mount:

```python
    @app.get("/api/mode")
    def get_mode() -> dict[str, str]:
        return {"mode": checks.progress.mode()}

    @app.put("/api/mode")
    def set_mode(selection: ModeSelection) -> dict[str, str]:
        checks.progress.set_mode(selection.mode)
        return {"mode": selection.mode}
```

`CheckService` stores its store privately as `self._progress`. Add a read-only accessor to `codemble/checks/service.py` rather than reaching through the underscore:

```python
    @property
    def progress(self) -> ProgressStore:
        """Expose the local progress store for preference reads and writes."""

        return self._progress
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit and open the Phase 2 PR**

```bash
git add codemble/progress/store.py codemble/checks/service.py codemble/server/app.py tests/
git commit -m "feat(progress): persist the learner's audience mode"
git push -u origin HEAD
gh pr create --title "feat: audience mode plumbing" --body "Phase 2 of docs/plans/2026-07-19-audience-modes-and-local-narration-design.md

Dual-voice lens notes and check prompts, mode-aware narration prompts, and the
cache-key fix that stops easy and expert sharing a cache entry.

Check answers are unchanged and asserted identical across modes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

# PHASE 3 — Local narration through Ollama

### Task 9: The Ollama provider

**Files:**
- Modify: `codemble/llm/providers.py`
- Test: `tests/test_providers.py` (create)

**Interfaces:**
- Produces: `OllamaProvider(model: str = "gemma4:12b", host: str = "http://127.0.0.1:11434")` implementing `NarrationProvider` with `name = "ollama"`. Task 10 constructs it; Task 11 reports on it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_providers.py`:

```python
"""Provider transports are exercised through injection; no test touches a network."""

import pytest

from codemble.llm.providers import OllamaProvider, ProviderError


def _transport(payload: dict[str, object]):
    def post_json(url: str, headers: dict[str, str], body: dict[str, object]):
        post_json.seen = {"url": url, "headers": headers, "body": body}
        return payload

    return post_json


def test_ollama_returns_the_response_text():
    provider = OllamaProvider(post_json=_transport({"response": "  grounded text  "}))
    assert provider.complete("prompt") == "grounded text"


def test_ollama_posts_to_the_generate_endpoint_without_streaming():
    transport = _transport({"response": "text"})
    provider = OllamaProvider(post_json=transport)
    provider.complete("prompt")
    assert transport.seen["url"] == "http://127.0.0.1:11434/api/generate"
    assert transport.seen["body"]["stream"] is False
    assert transport.seen["body"]["model"] == "gemma4:12b"


def test_ollama_rejects_an_empty_response():
    provider = OllamaProvider(post_json=_transport({"response": "   "}))
    with pytest.raises(ProviderError):
        provider.complete("prompt")


def test_ollama_rejects_a_response_without_the_text_field():
    provider = OllamaProvider(post_json=_transport({"unexpected": 1}))
    with pytest.raises(ProviderError):
        provider.complete("prompt")


def test_ollama_refuses_a_non_loopback_host():
    with pytest.raises(ValueError):
        OllamaProvider(host="http://example.com:11434")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers.py -v`
Expected: FAIL with `ImportError: cannot import name 'OllamaProvider'`

- [ ] **Step 3: Write minimal implementation**

Add to `codemble/llm/providers.py`:

```python
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(slots=True)
class OllamaProvider:
    """Local narration adapter; loopback only and never sends a credential."""

    model: str = "gemma4:12b"
    host: str = "http://127.0.0.1:11434"
    post_json: PostJson = field(default_factory=lambda: _post_local_json, repr=False)
    name: str = field(default="ollama", init=False)

    def __post_init__(self) -> None:
        hostname = parse.urlsplit(self.host).hostname
        if hostname not in _LOOPBACK_HOSTS:
            raise ValueError("Codemble only talks to a local Ollama on loopback.")

    def complete(self, prompt: str) -> str:
        payload = self.post_json(
            f"{self.host}/api/generate",
            {"content-type": "application/json"},
            {"model": self.model, "prompt": prompt, "stream": False},
        )
        response = payload.get("response")
        if not isinstance(response, str) or not response.strip():
            raise ProviderError("Ollama returned an empty text response.")
        return response.strip()


def _post_local_json(
    url: str, headers: dict[str, str], payload: JsonObject
) -> JsonObject:
    """POST to a loopback Ollama.

    Separate from ``_post_json`` because that helper is documented as
    HTTPS-only, and because local generation needs a longer ceiling than a
    cloud round trip.
    """

    encoded = json.dumps(payload).encode("utf-8")
    outbound = request.Request(
        url,
        data=encoded,
        headers={**headers, "user-agent": f"Codemble/{__version__}"},
        method="POST",
    )
    try:
        with request.urlopen(outbound, timeout=120) as response:  # noqa: S310 - loopback only
            decoded = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as provider_error:
        raise ProviderError(
            f"The local model rejected the request with HTTP {provider_error.code}."
        ) from provider_error
    except (error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(
            "Codemble could not reach a local Ollama server on loopback."
        ) from exc
    if not isinstance(decoded, dict):
        raise ProviderError("The local model returned an unexpected response shape.")
    return decoded
```

Update the imports at the top of the file:

```python
from urllib import error, parse, request
```

And extend `__all__` with `"OllamaProvider"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_providers.py -v && ruff check .`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add codemble/llm/providers.py tests/test_providers.py
git commit -m "feat(llm): add a loopback-only Ollama provider"
```

---

### Task 10: Select Ollama from configuration

**Files:**
- Modify: `codemble/llm/study.py:59-125` (`from_environment`)
- Test: `tests/test_study.py`

**Interfaces:**
- Consumes: `OllamaProvider` (Task 9).
- Produces: `CODEMBLE_PROVIDER=ollama` selects it; `CODEMBLE_OLLAMA_MODEL` and `CODEMBLE_OLLAMA_HOST` override defaults.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_study.py`:

```python
def test_ollama_is_selected_only_when_asked_for(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={"CODEMBLE_PROVIDER": "ollama"},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )

    result = service.explain("app.main", "easy")

    assert result["provider"] == "ollama"
    assert result["model"] == "gemma4:12b"


def test_no_configuration_never_silently_picks_a_local_model(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )

    assert service.explain("app.main", "easy")["status"] == "no_key"
```

The first test asserts through the public `explain` surface rather than reaching
into `service._provider`. With no Ollama running the call returns
`status: "error"` carrying `provider` and `model`, which is exactly what proves
selection happened without requiring a live local server.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study.py -k ollama -v`
Expected: FAIL — provider is `None` because `"ollama"` is rejected as an unknown provider name

- [ ] **Step 3: Write minimal implementation**

In `codemble/llm/study.py`, import the provider:

```python
from codemble.llm.providers import (
    AnthropicProvider,
    NarrationProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderError,
)
```

Add an `ollama` branch before the unknown-provider branch in `from_environment`:

```python
        elif provider_name == "ollama":
            provider = OllamaProvider(
                model=values.get("CODEMBLE_OLLAMA_MODEL")
                or config.get("ollama_model")
                or "gemma4:12b",
                host=values.get("CODEMBLE_OLLAMA_HOST")
                or config.get("ollama_host")
                or "http://127.0.0.1:11434",
            )
```

Update the unknown-provider message to name all three:

```python
        elif provider_name and provider_name not in {"anthropic", "openai", "ollama"}:
            setup_message = (
                "CODEMBLE_PROVIDER must be 'anthropic', 'openai', or 'ollama'; "
                "structure remains available."
            )
```

Auto-detection is deliberately **not** added: an unconfigured Codemble must never silently narrate with a local model. The setup panel offers it; the learner opts in.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codemble/llm/study.py tests/test_study.py
git commit -m "feat(llm): select Ollama through explicit configuration"
```

---

### Task 11: Local-model status endpoint

**Files:**
- Create: `codemble/llm/local_status.py`
- Modify: `codemble/server/app.py`
- Test: `tests/test_providers.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `ollama_status(host: str = "http://127.0.0.1:11434", get_json=...) -> dict[str, object]` returning `{"running": bool, "installed_models": list[str], "recommended": str, "fallback": str}`; `GET /api/llm/status`. Phase 6's setup guide renders this.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_providers.py`:

```python
from codemble.llm.local_status import ollama_status


def test_status_lists_installed_models_when_ollama_is_running():
    def get_json(url: str):
        assert url == "http://127.0.0.1:11434/api/tags"
        return {"models": [{"name": "gemma4:12b"}, {"name": "qwen3:8b"}]}

    status = ollama_status(get_json=get_json)
    assert status["running"] is True
    assert status["installed_models"] == ["gemma4:12b", "qwen3:8b"]
    assert status["recommended"] == "gemma4:12b"
    assert status["fallback"] == "qwen3:8b"


def test_status_reports_not_running_without_raising():
    def get_json(url: str):
        raise OSError("connection refused")

    status = ollama_status(get_json=get_json)
    assert status["running"] is False
    assert status["installed_models"] == []
```

Add to `tests/test_server.py`:

```python
def test_llm_status_endpoint_reports_provider_and_local_state(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    client = TestClient(create_app(graph, tmp_path / "missing"))

    payload = client.get("/api/llm/status").json()

    assert "configured_provider" in payload
    assert payload["ollama"]["recommended"] == "gemma4:12b"
    assert payload["ollama"]["fallback"] == "qwen3:8b"
    assert isinstance(payload["ollama"]["running"], bool)
```

This test must pass on a machine with no Ollama installed, which is why it
asserts the *shape* of `running` rather than a specific value.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers.py -k status tests/test_server.py -k llm_status -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codemble.llm.local_status'`

- [ ] **Step 3: Write minimal implementation**

Create `codemble/llm/local_status.py`:

```python
"""Report whether a local Ollama is reachable, for the in-app setup guide."""

from __future__ import annotations

import json
from typing import Callable
from urllib import error, request

from codemble import __version__

RECOMMENDED_MODEL = "gemma4:12b"
FALLBACK_MODEL = "qwen3:8b"

GetJson = Callable[[str], dict]


def ollama_status(
    host: str = "http://127.0.0.1:11434",
    get_json: GetJson | None = None,
) -> dict[str, object]:
    """Return local-model availability without ever raising."""

    fetch = get_json or _get_json
    installed: list[str] = []
    running = False
    try:
        payload = fetch(f"{host}/api/tags")
        models = payload.get("models", [])
        if isinstance(models, list):
            installed = [
                str(entry["name"])
                for entry in models
                if isinstance(entry, dict) and isinstance(entry.get("name"), str)
            ]
        running = True
    except (OSError, ValueError, json.JSONDecodeError):
        running = False
    return {
        "running": running,
        "installed_models": installed,
        "recommended": RECOMMENDED_MODEL,
        "fallback": FALLBACK_MODEL,
    }


def _get_json(url: str) -> dict:
    outbound = request.Request(
        url, headers={"user-agent": f"Codemble/{__version__}"}, method="GET"
    )
    with request.urlopen(outbound, timeout=2) as response:  # noqa: S310 - loopback only
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Ollama returned an unexpected shape.")
    return decoded


__all__ = ["FALLBACK_MODEL", "RECOMMENDED_MODEL", "ollama_status"]
```

The two-second timeout matters: this endpoint is polled by the setup guide, so a
missing server must fail fast rather than stall the panel.

In `codemble/server/app.py`, import and add the route:

```python
from codemble.llm.local_status import ollama_status
```

```python
    @app.get("/api/llm/status")
    def get_llm_status() -> dict[str, object]:
        provider = getattr(studies, "_provider", None)
        return {
            "configured_provider": getattr(provider, "name", None),
            "configured_model": getattr(provider, "model", None),
            "ollama": ollama_status(),
        }
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -v && ruff check .`
Expected: PASS

- [ ] **Step 5: Commit and open the Phase 3 PR**

```bash
git add codemble/llm/local_status.py codemble/server/app.py tests/
git commit -m "feat(llm): report local model availability"
git push -u origin HEAD
gh pr create --title "feat: local narration through Ollama" --body "Phase 3 of docs/plans/2026-07-19-audience-modes-and-local-narration-design.md

Adds a loopback-only Ollama provider behind the existing NarrationProvider
seam, explicit opt-in configuration, and a status endpoint for the setup guide.

Local output passes the same grounding validation as cloud output. Ollama is
never selected automatically.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## Verification before calling phases 1–3 done

- [ ] `python -m pytest` — full suite green
- [ ] `ruff check .` — clean
- [ ] `codemble ./` against this repository still serves a galaxy
- [ ] `curl localhost:8000/api/node/<id>/study` returns `structural` with both voices and no provider delay
- [ ] `curl 'localhost:8000/api/node/<id>/explanation?mode=easy'` returns a narration state
- [ ] `curl localhost:8000/api/llm/status` reports `running: false` promptly with no Ollama installed
- [ ] Region illumination and progress survive a mode change

## Deferred to phases 4–6 (not in this plan)

- Frontend mode state, first-run question, header toggle, UI density
- Icons, graph-derived mini-diagrams, typography
- The in-app setup guide UI (this plan ships only the status API it needs)
- `codemble/web_dist` rebuild, README, docs-site, CHANGELOG, Decision Log entry
  recording the Ollama reversal
