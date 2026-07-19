"""Study-module contracts: real source, bounded narration, and cache behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.llm.providers import AnthropicProvider, OpenAIProvider
from codemble.llm.study import StudyService

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
CONCEPT_FIXTURE = Path(__file__).parent / "fixtures" / "concepts_sample.py"


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
    assert result["explanation"]["status"] == "no_key"  # type: ignore[index]
    assert result["lens"][0]["concept"] == "type-hint"  # type: ignore[index]
    assert result["lens"][0]["citation"] == "app.py:8"  # type: ignore[index]
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


def test_partial_source_stays_visible_without_model_narration(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path)

    result = service.study("broken")

    assert result["source"]["file"] == "broken.py"  # type: ignore[index]
    assert result["explanation"]["status"] == "partial"  # type: ignore[index]
    assert result["lens"] == []
    assert provider.calls == 0


def test_validated_explanation_is_cached_by_node_and_file_hash(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider()
    service = StudyService(graph, provider=provider, cache_root=tmp_path)

    first = service.study("app.main")["explanation"]
    reopened_provider = FakeProvider()
    reopened = StudyService(graph, provider=reopened_provider, cache_root=tmp_path)
    second = reopened.study("app.main")["explanation"]

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
    assert changed_service.study("app.main")["explanation"]["cached"] is False  # type: ignore[index]
    assert changed_provider.calls == 1


def test_provider_output_cannot_reference_an_unobserved_node(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    provider = FakeProvider("invented.module")
    service = StudyService(graph, provider=provider, cache_root=tmp_path)

    explanation = service.study("app.main")["explanation"]

    assert explanation["status"] == "error"  # type: ignore[index]
    assert "outside the parser graph" in explanation["message"]  # type: ignore[index]
    assert not list(tmp_path.glob("*.json"))


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
