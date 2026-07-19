"""Study-module contracts: real source, bounded narration, and cache behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter
from codemble.llm.providers import AnthropicProvider, OpenAIProvider
from codemble.llm.study import StudyService

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CONCEPT_FIXTURE = Path(__file__).parent / "fixtures" / "concepts_sample.py"
POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


class FakeProvider:
    name = "fake"
    model = "grounded-test"

    def __init__(self, relationship: str = "pkg.service.Service") -> None:
        self.calls = 0
        self.relationship = relationship

    def complete(self, prompt: str) -> str:
        self.calls += 1
        assert "HARD CORRECTNESS CONTRACT" in prompt
        assert "app.py:8-13" in prompt
        assert "pkg.service.Service" in prompt
        return json.dumps(
            {
                "summary": "This function coordinates the parser-observed calls shown below.",
                "walkthrough": [
                    {"line": 9, "explanation": "This line creates the observed service object."},
                    {"line": 13, "explanation": "This line makes a possible method call."},
                ],
                "relationships": [
                    {
                        "node_id": self.relationship,
                        "explanation": "The selected function constructs this parser-proven class.",
                    }
                ],
            }
        )


def test_study_without_key_keeps_real_source_available(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )

    result = service.study("app.main")

    assert result["source"]["file"] == "app.py"  # type: ignore[index]
    assert result["source"]["lines"][0] == {  # type: ignore[index]
        "number": 8,
        "text": "def main() -> None:",
    }
    assert "explanation" not in result
    assert result["lens"][0]["concept"] == "type-hint"  # type: ignore[index]
    assert result["lens"][0]["citation"] == "app.py:8"  # type: ignore[index]
    assert service.explain("app.main")["status"] == "no_key"
    assert not (tmp_path / "cache").exists()


def test_lens_notes_are_anchored_to_parser_detected_constructs(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(CONCEPT_FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )

    result = service.study("concepts_sample.collect")
    annotations = {
        (annotation.concept, annotation.lineno, annotation.snippet)
        for annotation in graph.concept_annotations
        if annotation.node_id == "concepts_sample.collect"
    }
    notes = {
        (note["concept"], note["line"], note["snippet"])
        for note in result["lens"]  # type: ignore[union-attr]
    }

    assert notes == annotations
    assert all(
        note["citation"] == f"concepts_sample.py:{note['line']}"
        for note in result["lens"]  # type: ignore[union-attr]
    )


def test_typescript_lens_notes_equal_language_tagged_parser_annotations(
    tmp_path: Path,
) -> None:
    graph = JavaScriptTypeScriptAdapter().parse(POLYGLOT_FIXTURE)
    service = StudyService.from_environment(
        graph,
        environ={},
        config_path=tmp_path / "missing-config",
        cache_root=tmp_path / "cache",
    )
    node_id = "typescript:src/widget.tsx::Card"

    result = service.study(node_id)
    annotations = {
        (
            annotation.language,
            annotation.concept,
            annotation.lineno,
            annotation.snippet,
        )
        for annotation in graph.concept_annotations
        if annotation.node_id == node_id
    }
    notes = {
        (note["language"], note["concept"], note["line"], note["snippet"])
        for note in result["lens"]  # type: ignore[union-attr]
    }

    assert notes == annotations
    assert {note["concept"] for note in result["lens"]} >= {  # type: ignore[union-attr]
        "arrow-function",
        "destructuring",
        "jsx",
        "type-annotation",
    }
    assert all(
        note["citation"] == f"src/widget.tsx:{note['line']}"
        for note in result["lens"]  # type: ignore[union-attr]
    )
    for note in result["lens"]:  # type: ignore[union-attr]
        assert set(note["note_voices"]) == {"easy", "expert"}
        assert note["note_voices"]["easy"].strip()
        assert note["note_voices"]["expert"].strip()
        assert note["note"] == note["note_voices"]["easy"], (
            "the legacy string keeps the shipped SPA rendering until phase 4"
        )


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
        assert set(note["note_voices"]) == {"easy", "expert"}
        assert note["note_voices"]["easy"].strip()
        assert note["note_voices"]["expert"].strip()
        assert note["note"] == note["note_voices"]["easy"], (
            "the legacy string keeps the shipped SPA rendering until phase 4"
        )


def test_no_concept_is_missing_a_voice():
    from codemble.lens.javascript_typescript import _NOTES
    from codemble.lens.python import _PYTHON_NOTES

    for table in (_PYTHON_NOTES, _NOTES):
        for concept, (title, voices) in table.items():
            assert title.strip(), concept
            assert voices["easy"].strip(), concept
            assert voices["expert"].strip(), concept


def test_partial_source_stays_visible_without_model_narration(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path)

    result = service.study("broken")

    assert result["source"]["file"] == "broken.py"  # type: ignore[index]
    assert "explanation" not in result
    assert result["lens"] == []
    assert service.explain("broken")["status"] == "partial"
    assert provider.calls == 0


def test_validated_explanation_is_cached_by_node_and_file_hash(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path)

    first = service.explain("app.main")
    reopened_provider = FakeProvider()
    reopened = StudyService(graph, provider=reopened_provider, cache_root=tmp_path)
    second = reopened.explain("app.main")

    assert first["status"] == "ready"  # type: ignore[index]
    assert first["summary"]["citation"] == "app.py:8"  # type: ignore[index]
    assert first["walkthrough"][1]["citation"] == "app.py:13"  # type: ignore[index]
    assert first["relationships"][0]["citation"] == "pkg/service.py:6"  # type: ignore[index]
    assert first["cached"] is False  # type: ignore[index]
    assert second["cached"] is True  # type: ignore[index]
    assert provider.calls == 1
    assert reopened_provider.calls == 0

    changed_graph = replace(
        graph,
        file_hashes={**graph.file_hashes, "app.py": "changed-file-hash"},
    )
    changed_provider = FakeProvider()
    changed_service = StudyService(
        changed_graph,
        provider=changed_provider,
        cache_root=tmp_path,
    )
    assert changed_service.explain("app.main")["cached"] is False  # type: ignore[index]
    assert changed_provider.calls == 1


def test_provider_output_cannot_reference_an_unobserved_node(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider("invented.module")
    service = StudyService(graph, provider=provider, cache_root=tmp_path)

    explanation = service.explain("app.main")

    assert explanation["status"] == "error"  # type: ignore[index]
    assert "outside the parser graph" in explanation["message"]  # type: ignore[index]
    assert not list(tmp_path.glob("*.json"))


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
    assert any(neighbor["direction"] == "inbound" for neighbor in neighbors)


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
    assert "explanation" not in payload, (
        "the shipped SPA crashes on an unknown explanation status; omitting the "
        "key makes App.jsx:523 render nothing instead"
    )


def test_explain_reaches_the_provider(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path / "cache")

    result = service.explain("app.main", "easy")

    assert result["status"] == "ready"
    assert provider.calls == 1


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


def test_style_bridge_sits_between_audience_note_and_contract(tmp_path: Path) -> None:
    """The seam sentence must sit after the style block and before the contract.

    Asserting on index order (not just substring presence) means a future
    reordering that buries the bridge inside either section fails this test.
    """

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

    bridge = (
        "The audience note above changes only wording. It never permits dropping "
        "a hedge, an uncertainty label, or a citation that the contract below "
        "requires."
    )
    style_marker = {
        "easy": "Assume no knowledge of frameworks, patterns, or jargon.",
        "expert": "Use standard terminology without defining it.",
    }
    contract_heading = "HARD CORRECTNESS CONTRACT:"

    assert len(provider.prompts) == 2
    for mode, prompt in zip(("easy", "expert"), provider.prompts):
        style_index = prompt.index(style_marker[mode])
        bridge_index = prompt.index(bridge)
        contract_index = prompt.index(contract_heading)
        assert style_index < bridge_index < contract_index, mode


def test_anthropic_and_openai_adapters_keep_transport_behind_one_interface() -> None:
    anthropic_requests: list[tuple[str, dict[str, str], dict[str, object]]] = []
    openai_requests: list[tuple[str, dict[str, str], dict[str, object]]] = []

    anthropic = AnthropicProvider(
        "secret-a",
        post_json=lambda url, headers, body: (
            anthropic_requests.append((url, headers, body))
            or {"content": [{"type": "text", "text": "anthropic result"}]}
        ),
    )
    openai = OpenAIProvider(
        "secret-o",
        post_json=lambda url, headers, body: (
            openai_requests.append((url, headers, body))
            or {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "openai result"}],
                    }
                ]
            }
        ),
    )

    assert anthropic.complete("grounded") == "anthropic result"
    assert openai.complete("grounded") == "openai result"
    assert anthropic_requests[0][0].endswith("/v1/messages")
    assert anthropic_requests[0][1]["x-api-key"] == "secret-a"
    assert openai_requests[0][0].endswith("/v1/responses")
    assert openai_requests[0][1]["authorization"] == "Bearer secret-o"
    assert openai_requests[0][2]["store"] is False
