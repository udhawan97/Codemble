"""Canonical graph finalization shared by every language adapter."""

from __future__ import annotations

import re
import tomllib
from dataclasses import replace
from pathlib import Path, PurePosixPath

from codemble.adapters.base import ConceptAnnotation, Edge, Graph, Node, RoleEvidence
from codemble.graph.layout import layout_graph


class GraphFinalizationError(ValueError):
    """Parser evidence cannot be finalized into one honest graph."""


# A test-scoped candidate sorts below every non-test one rather than being
# removed: a project that IS a test suite still needs somewhere to start, and
# dropping them would leave it with no Home at all. Same reasoning as the Easy
# guidance penalty (Decision Log, 2026-07-22) -- bias the ranking, never the
# reported fact. Here that is literal: the stored `entrypoint_rank` is never
# touched, so the number the picker shows is the parser's own.
_UNRANKED = 1 << 30

_TEST_DIRECTORIES = frozenset({"tests", "test", "testing", "__tests__", "spec", "__specs__"})
_ROLE_KINDS = frozenset({"application-entry", "route-handler", "ui-renderer", "test"})
_RULE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")


def _manifest_entry_ids(project_root: str) -> frozenset[str]:
    """Modules and functions the project's own packaging manifest declares
    as programs.

    `[project.scripts]` and `[project.gui-scripts]` entries have the form
    ``pkg.mod:func`` (function optional): the manifest literally states which
    code the installed command runs, which is stronger evidence than any
    ``__main__`` guard -- four maintenance scripts tied this repository's real
    entry at rank 0 while pyproject.toml already named it. Only ranking uses
    this; a declared module the parser never saw contributes nothing, so no
    structure is invented. A missing or broken manifest also contributes
    nothing rather than failing the parse.
    """

    manifest = Path(project_root) / "pyproject.toml"
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    project = data.get("project")
    if not isinstance(project, dict):
        return frozenset()
    ids: set[str] = set()
    for table in ("scripts", "gui-scripts"):
        entries = project.get(table)
        if not isinstance(entries, dict):
            continue
        for target in entries.values():
            if not isinstance(target, str):
                continue
            module, _, attribute = target.partition(":")
            module = module.strip()
            if not module:
                continue
            ids.add(module)
            first_attribute = attribute.strip().split(".", 1)[0]
            if first_attribute:
                ids.add(f"{module}.{first_attribute}")
    return frozenset(ids)


def _is_test_scoped(file: str) -> bool:
    """Whether a file lives in, or is, a test.

    Path-based on purpose, and language-neutral on purpose. Every adapter has
    some notion of a test, but each asks a question only its own language can
    answer: Rust reads `#[test]`, Java `@Test`, C# `[Fact]`/`[TestMethod]`, Go
    the `_test.go` suffix. None of those sees a fixture carrying an ordinary,
    unmarked `main()` in a file that is not named like a test -- which is
    exactly the shape of `tests/fixtures/<lang>_sample/...` and exactly what
    tied six candidates at rank 0 on this project, leaving Home unresolved.

    "Is this file inside the project's own test tree?" needs no parser
    evidence, so it belongs here, once, where every adapter already funnels --
    not copied into each of them, and not left to whichever language happens
    to have thought of it.
    """

    path = PurePosixPath(file)
    if any(part in _TEST_DIRECTORIES for part in path.parts[:-1]):
        return True
    stem = path.stem
    return stem.startswith("test_") or stem.endswith("_test") or stem == "conftest"


def finalize_graph(graph: Graph, *, entrypoint: str | None = None) -> Graph:
    """Canonicalize parser evidence and return one render-ready graph."""

    edges = tuple(sorted(set(graph.edges), key=_edge_key))
    node_ids = {node.id for node in graph.nodes}
    callers_by_target: dict[str, set[str]] = {}
    for edge in edges:
        if edge.kind == "call" and not edge.external and edge.dst in node_ids:
            callers_by_target.setdefault(edge.dst, set()).add(edge.src)
    nodes = tuple(
        sorted(
            (
                replace(node, centrality=len(callers_by_target.get(node.id, ())))
                for node in graph.nodes
            ),
            key=lambda node: node.id,
        )
    )
    node_by_id = {node.id: node for node in nodes}
    # Test-scoping biases the ORDER, and never the stored rank. Two reasons,
    # both of which a rank-mutating version got wrong: `finalize_graph` runs
    # twice on the normal path -- once inside an adapter's `parse_files`, again
    # inside `ProjectParser` composition -- so adding a penalty to the field
    # applied it twice (measured: rank 4 became rank 8); and the rank is shown
    # to the learner, who is promised it is the parser's real one.
    manifest_ids = _manifest_entry_ids(graph.project_root)

    def candidate_order(node: Node) -> tuple[int, int, int, str]:
        return _candidate_order(node, manifest_ids)

    candidates = tuple(
        node.id
        for node in sorted(
            (node for node in nodes if node.entrypoint_rank is not None),
            key=candidate_order,
        )
    )
    if entrypoint is not None and entrypoint not in candidates:
        choices = ", ".join(candidates) or "none"
        raise GraphFinalizationError(
            f"entrypoint is not parser-ranked: {entrypoint} (candidates: {choices})"
        )
    # The BEST available rank, not rank zero specifically. A web service
    # frequently has no `__main__` guard at all, so its only candidate sat at
    # the app-object rank and Home resolved to nothing -- the learner met the
    # picker holding a single option and was asked a question with one answer.
    # When exactly one candidate is the best available there is nothing to ask;
    # when several tie, that is a genuine decision and the picker still opens.
    # Compared on the same key the candidate list is ordered by, so "best"
    # means what the learner sees at the top: a test-scoped candidate only wins
    # when nothing outside the test tree is ranked at all, which keeps a project
    # that IS a test suite explorable.
    keys = [candidate_order(node_by_id[candidate]) for candidate in candidates]
    best = [
        candidate
        for candidate in candidates
        if keys and candidate_order(node_by_id[candidate])[:3] == min(keys)[:3]
    ]
    selected_entrypoint = entrypoint or (best[0] if len(best) == 1 else None)
    finalized = replace(
        graph,
        nodes=nodes,
        edges=edges,
        entrypoint_candidates=candidates,
        file_hashes=dict(sorted(graph.file_hashes.items())),
        selected_entrypoint=selected_entrypoint,
        concept_annotations=tuple(
            sorted(set(graph.concept_annotations), key=_annotation_key)
        ),
        role_evidence=_finalize_role_evidence(graph, node_by_id),
        regions=(),
        region_edges=(),
        import_cycles=(),
        partial_files=tuple(sorted(set(graph.partial_files))),
    )
    return layout_graph(finalized)


def _finalize_role_evidence(
    graph: Graph,
    node_by_id: dict[str, Node],
) -> tuple[RoleEvidence, ...]:
    """Validate the separate role channel before any journey can consume it."""

    root = Path(graph.project_root).resolve()
    validated: set[RoleEvidence] = set()
    line_counts: dict[str, int] = {}
    for evidence in graph.role_evidence:
        node = node_by_id.get(evidence.node_id)
        if node is None:
            raise GraphFinalizationError(
                f"role evidence references an unknown node: {evidence.node_id}"
            )
        if node.partial:
            raise GraphFinalizationError(
                f"role evidence references a partial node: {evidence.node_id}"
            )
        if evidence.role not in _ROLE_KINDS:
            raise GraphFinalizationError(f"unknown role evidence kind: {evidence.role}")
        if not _RULE_ID.fullmatch(evidence.rule_id):
            raise GraphFinalizationError(
                f"role evidence rule ID is not stable: {evidence.rule_id}"
            )
        if evidence.file not in graph.file_hashes:
            raise GraphFinalizationError(
                f"role evidence file was not hashed: {evidence.file}"
            )
        if evidence.file in graph.partial_files:
            raise GraphFinalizationError(
                f"role evidence file was only partially parsed: {evidence.file}"
            )
        if evidence.lineno < 1 or evidence.end_lineno < evidence.lineno:
            raise GraphFinalizationError(
                f"role evidence has an invalid span: {evidence.file}:{evidence.lineno}"
            )
        if evidence.file not in line_counts:
            observation = (root / evidence.file).resolve()
            if not observation.is_relative_to(root) or not observation.is_file():
                raise GraphFinalizationError(
                    f"role evidence file is unavailable: {evidence.file}"
                )
            try:
                line_counts[evidence.file] = max(1, len(observation.read_bytes().splitlines()))
            except OSError as error:
                raise GraphFinalizationError(
                    f"role evidence file could not be read: {evidence.file}"
                ) from error
        if evidence.end_lineno > line_counts[evidence.file]:
            raise GraphFinalizationError(
                f"role evidence span is outside its file: {evidence.file}:{evidence.lineno}"
            )
        validated.add(evidence)
    return tuple(sorted(validated, key=_role_key))


def _candidate_order(node: Node, manifest_ids: frozenset[str]) -> tuple[int, int, int, str]:
    """Order entrypoint candidates: manifest-declared first, then real code
    ahead of test-scoped, then rank, then id.

    Idempotent by construction — it reads the node and returns a sort key
    rather than editing a field, so running finalization twice (which the
    normal path does) cannot compound it.
    """

    return (
        0 if node.id in manifest_ids else 1,
        1 if _is_test_scoped(node.file) else 0,
        node.entrypoint_rank if node.entrypoint_rank is not None else _UNRANKED,
        node.id,
    )


def _edge_key(edge: Edge) -> tuple[str, str, str, int, bool, bool]:
    return (
        edge.src,
        edge.dst,
        edge.kind,
        edge.lineno,
        edge.certain,
        edge.external,
    )


def _annotation_key(
    annotation: ConceptAnnotation,
) -> tuple[str, str, int, str, int]:
    return (
        annotation.language,
        annotation.node_id,
        annotation.lineno,
        annotation.concept,
        annotation.end_lineno,
    )


def _role_key(evidence: RoleEvidence) -> tuple[str, str, str, str, int, int]:
    return (
        evidence.node_id,
        evidence.role,
        evidence.rule_id,
        evidence.file,
        evidence.lineno,
        evidence.end_lineno,
    )


__all__ = ["GraphFinalizationError", "finalize_graph"]
