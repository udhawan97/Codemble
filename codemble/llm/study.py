"""Deep study module: source, grounding, provider narration, and disk cache."""

from __future__ import annotations

import hashlib
import json
import os
import tokenize
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from codemble.adapters.base import Edge, Graph, Node
from codemble.lens import lens_notes
from codemble.llm.providers import (
    AnthropicProvider,
    NarrationProvider,
    OpenAIProvider,
    ProviderError,
)
from codemble.llm.structural import structural_summary

PROMPT_VERSION = "study-v3"
_CACHE_SCHEMA = 1


class UnknownNodeError(LookupError):
    """The requested node is not present in the parser graph."""


class StudySourceError(RuntimeError):
    """The parser-proven source can no longer be read safely."""


class GroundingError(RuntimeError):
    """Provider output references evidence outside the supplied graph context."""


class StudyService:
    """Return a complete, evidence-bounded study payload through one interface."""

    def __init__(
        self,
        graph: Graph,
        *,
        provider: NarrationProvider | None = None,
        cache_root: Path | None = None,
        setup_message: str | None = None,
    ) -> None:
        self._graph = graph
        self._project_root = Path(graph.project_root).resolve()
        self._nodes = {node.id: node for node in graph.nodes}
        self._provider = provider
        self._cache_root = cache_root or Path.home() / ".codemble" / "cache" / "explanations"
        self._setup_message = setup_message or (
            "Set ANTHROPIC_API_KEY or OPENAI_API_KEY, then restart Codemble."
        )

    @classmethod
    def from_environment(
        cls,
        graph: Graph,
        *,
        environ: Mapping[str, str] | None = None,
        config_path: Path | None = None,
        cache_root: Path | None = None,
    ) -> StudyService:
        """Build the module from environment variables or ``~/.codemble/config``."""

        values = dict(os.environ if environ is None else environ)
        path = config_path or Path.home() / ".codemble" / "config"
        config, config_error = _read_config(path)
        provider_name = (values.get("CODEMBLE_PROVIDER") or config.get("provider") or "").lower()
        generic_key = config.get("api_key")
        anthropic_key = (
            values.get("ANTHROPIC_API_KEY")
            or config.get("anthropic_api_key")
            or (generic_key if provider_name == "anthropic" else None)
        )
        openai_key = (
            values.get("OPENAI_API_KEY")
            or config.get("openai_api_key")
            or (generic_key if provider_name == "openai" else None)
        )

        if not provider_name:
            if anthropic_key:
                provider_name = "anthropic"
            elif openai_key:
                provider_name = "openai"

        provider: NarrationProvider | None = None
        setup_message = config_error
        if provider_name == "anthropic" and anthropic_key:
            provider = AnthropicProvider(
                anthropic_key,
                values.get("CODEMBLE_ANTHROPIC_MODEL")
                or config.get("anthropic_model")
                or config.get("model")
                or "claude-sonnet-5",
            )
        elif provider_name == "openai" and openai_key:
            provider = OpenAIProvider(
                openai_key,
                values.get("CODEMBLE_OPENAI_MODEL")
                or config.get("openai_model")
                or config.get("model")
                or "gpt-5.4-mini",
            )
        elif provider_name and provider_name not in {"anthropic", "openai"}:
            setup_message = (
                "CODEMBLE_PROVIDER must be 'anthropic' or 'openai'; structure remains available."
            )
        elif provider_name:
            setup_message = (
                f"Add the {provider_name.upper()} API key to the environment or {path}, "
                "then restart Codemble."
            )

        return cls(
            graph,
            provider=provider,
            cache_root=cache_root,
            setup_message=setup_message,
        )

    def study(self, node_id: str) -> dict[str, object]:
        """Return real source, parser neighbors, and the local structural summary.

        Never calls the narration provider — this stays fast and fully local so
        opening a node in the study panel cannot block on a network round trip.
        """

        node = self._nodes.get(node_id)
        if node is None:
            raise UnknownNodeError(node_id)
        source, neighbors, lens = self._prepare(node)
        return {
            "node": asdict(node),
            "source": source,
            "neighbors": neighbors,
            "lens": lens,
            "structural": structural_summary(node, neighbors, lens),
        }

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
        source, neighbors, lens = self._prepare(node)
        return self._explain(node, source, neighbors, lens, mode)

    def _prepare(
        self, node: Node
    ) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
        """Return the source, neighbors, and citation-anchored lens notes.

        Shared by ``study`` and ``explain`` so the lens-citation loop and
        neighbor/annotation lookup exist in exactly one place.
        """

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
        return source, neighbors, lens

    def _read_source(self, node: Node) -> dict[str, object]:
        source_path = (self._project_root / node.file).resolve()
        if not source_path.is_relative_to(self._project_root) or not source_path.is_file():
            raise StudySourceError("The parser-proven source file is no longer available.")
        try:
            if node.language == "python":
                with tokenize.open(source_path) as source_file:
                    source_text = source_file.read()
            else:
                source_text = source_path.read_bytes().decode("utf-8", errors="replace")
            all_lines = source_text.splitlines()
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            raise StudySourceError("The parser-proven source could not be decoded safely.") from error
        start = max(1, node.lineno)
        end = min(max(start, node.end_lineno), len(all_lines))
        return {
            "file": node.file,
            "start_line": start,
            "end_line": end,
            "lines": [
                {"number": line_number, "text": all_lines[line_number - 1]}
                for line_number in range(start, end + 1)
            ],
        }

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

    def _explain(
        self,
        node: Node,
        source: dict[str, object],
        neighbors: list[dict[str, object]],
        lens: list[dict[str, object]],
        mode: str,
    ) -> dict[str, object]:
        if self._provider is None:
            return {
                "status": "no_key",
                "message": self._setup_message,
                "cached": False,
            }

        file_hash = self._graph.file_hashes.get(node.file, "")
        cache_key = _cache_key(self._provider, node, file_hash, mode)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return {**cached, "cached": True}

        prompt = _grounded_prompt(node, source, neighbors, lens, mode)
        try:
            raw = self._provider.complete(prompt)
            validated = _validate_explanation(raw, node, neighbors)
        except (ProviderError, GroundingError) as error:
            return {
                "status": "error",
                "message": str(error),
                "cached": False,
                "provider": self._provider.name,
                "model": self._provider.model,
            }

        result = {
            "status": "ready",
            "cached": False,
            "provider": self._provider.name,
            "model": self._provider.model,
            **validated,
        }
        self._write_cache(cache_key, result)
        return result

    def _read_cache(self, cache_key: str) -> dict[str, object] | None:
        path = self._cache_root / f"{cache_key}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("schema_version") != _CACHE_SCHEMA:
            return None
        result = payload.get("result")
        return result if isinstance(result, dict) and result.get("status") == "ready" else None

    def _write_cache(self, cache_key: str, result: dict[str, object]) -> None:
        try:
            self._cache_root.mkdir(parents=True, exist_ok=True)
            destination = self._cache_root / f"{cache_key}.json"
            temporary = destination.with_suffix(".tmp")
            payload = {"schema_version": _CACHE_SCHEMA, "result": result}
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
        except OSError:
            return


def _read_config(path: Path) -> tuple[dict[str, str], str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, None
    except OSError:
        return {}, f"Codemble could not read {path}; environment keys still work."
    try:
        decoded = json.loads(raw) if raw.lstrip().startswith("{") else tomllib.loads(raw)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError):
        return {}, f"{path} must contain a TOML table or JSON object."
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in decoded.items()
    ):
        return {}, f"{path} must map string settings to string values."
    return decoded, None


def _neighbor_id(edge: Edge, node_id: str) -> tuple[str, str] | None:
    if edge.src == node_id and not edge.external:
        return edge.dst, "outbound"
    if edge.dst == node_id:
        return edge.src, "inbound"
    return None


def _cache_key(
    provider: NarrationProvider, node: Node, file_hash: str, mode: str
) -> str:
    material = "\0".join(
        (PROMPT_VERSION, provider.name, provider.model, node.id, file_hash, mode)
    ).encode()
    return hashlib.sha256(material).hexdigest()


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


def _grounded_prompt(
    node: Node,
    source: dict[str, object],
    neighbors: list[dict[str, object]],
    lens: list[dict[str, object]],
    mode: str,
) -> str:
    source_lines = source.get("lines", [])
    numbered_source = "\n".join(
        f"{line['number']:04d}: {line['text']}"
        for line in source_lines
        if isinstance(line, dict) and isinstance(line.get("number"), int)
    )
    neighbor_evidence = "\n".join(
        f"- {neighbor['node_id']} ({neighbor['relationship']}, "
        f"{'certain' if neighbor['certain'] else 'possible'}) at {neighbor['citation']}"
        for neighbor in neighbors
    ) or "- none"
    lens_evidence = "\n".join(
        f"- {note['concept']} at {note['citation']}: {note['snippet']}"
        for note in lens
    ) or "- none"
    return f"""You are the narration layer in Codemble, a code-learning tool.

{_MODE_STYLE.get(mode, _MODE_STYLE["easy"])}
HARD CORRECTNESS CONTRACT:
- Explain only the source and parser evidence below.
- Never invent a structure, identifier, behavior, dependency, or intent.
- If purpose is unclear from the code, say exactly that it is unclear from the code.
- Do not introduce identifier names in prose; the UI renders validated node IDs separately.
- Use only line numbers inside {node.file}:{node.lineno}-{node.end_lineno}.
- A relationship may name only one of the supplied neighbor node IDs.
- Approximate relationships must be described as possible, never certain.
- Return JSON only, with no Markdown fence.

Return this exact shape:
{{
  "summary": "plain-language explanation",
  "walkthrough": [{{"line": {node.lineno}, "explanation": "what that line does"}}],
  "relationships": [{{"node_id": "allowed neighbor ID", "explanation": "relationship"}}]
}}

Selected node: {node.id} ({node.kind})
Citation: {node.file}:{node.lineno}

SOURCE:
{numbered_source}

PARSER-PROVEN NEIGHBORS:
{neighbor_evidence}

LANGUAGE-LENS ANNOTATIONS:
{lens_evidence}
"""


def _validate_explanation(
    raw: str,
    node: Node,
    neighbors: list[dict[str, object]],
) -> dict[str, object]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.removeprefix("```json").removeprefix("```")
        candidate = candidate.removesuffix("```").strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise GroundingError("The provider response was not valid grounded JSON.") from error
    if not isinstance(payload, dict):
        raise GroundingError("The provider response did not contain a grounded object.")

    summary = _bounded_text(payload.get("summary"), "summary")
    raw_walkthrough = payload.get("walkthrough")
    if not isinstance(raw_walkthrough, list) or not raw_walkthrough:
        raise GroundingError("The provider response omitted the source walkthrough.")
    walkthrough: list[dict[str, object]] = []
    for item in raw_walkthrough[:8]:
        if not isinstance(item, dict) or not isinstance(item.get("line"), int):
            raise GroundingError("A walkthrough item did not cite a real source line.")
        line = item["line"]
        if line < node.lineno or line > node.end_lineno:
            raise GroundingError("A walkthrough citation fell outside the selected source span.")
        walkthrough.append(
            {
                "line": line,
                "citation": f"{node.file}:{line}",
                "text": _bounded_text(item.get("explanation"), "walkthrough explanation"),
            }
        )

    neighbor_by_id = {str(item["node_id"]): item for item in neighbors}
    raw_relationships = payload.get("relationships", [])
    if not isinstance(raw_relationships, list):
        raise GroundingError("The provider relationships were not a list.")
    relationships: list[dict[str, object]] = []
    for item in raw_relationships[:8]:
        if not isinstance(item, dict) or not isinstance(item.get("node_id"), str):
            raise GroundingError("A relationship omitted its parser-proven node ID.")
        neighbor = neighbor_by_id.get(item["node_id"])
        if neighbor is None:
            raise GroundingError("The provider named a relationship outside the parser graph.")
        relationships.append(
            {
                "node_id": item["node_id"],
                "citation": neighbor["citation"],
                "certain": neighbor["certain"],
                "text": _bounded_text(item.get("explanation"), "relationship explanation"),
            }
        )

    return {
        "summary": {"text": summary, "citation": f"{node.file}:{node.lineno}"},
        "walkthrough": walkthrough,
        "relationships": relationships,
    }


def _bounded_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GroundingError(f"The provider {label} was empty.")
    text = value.strip()
    if len(text) > 2400:
        raise GroundingError(f"The provider {label} exceeded the grounded response limit.")
    return text


__all__ = ["StudyService", "StudySourceError", "UnknownNodeError"]
