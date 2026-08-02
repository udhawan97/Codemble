"""JS/TS call targets: "leaves your project" is not "we could not find it".

Measured on `web/src` before this work, 73% of JS/TS call edges were unproven --
but unlike Python's, that number was almost entirely honest. 80% of them were
already `external:` (React hooks, three.js, `Math.max`), which genuinely leave
the project, and only 1% was in-project fan-out. TypeScript simply does not
have Python's ambiguity problem, so the fix is not a copy of Python's.

What was wrong was the *category*. 45% of the remaining `unresolved:` edges
named ECMAScript builtins -- `Set`, `Map`, `Error`, `WeakMap`, `AbortController`
-- plus web globals like `requestAnimationFrame` and `setTimeout`. Those were
reported as `unresolved:javascript:graphData.js:Set`, which reads as "Codemble
believes this is yours and could not find it". It is not missing coverage; the
call leaves the project, exactly as `Math.max` does, and Python has said so
about its own builtins from the start.

The distinction is the one graph schema 8 exists for: a coverage gap and a
boundary are different facts, and a learner cannot tell the tool is wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    root.mkdir()
    (root / "index.js").write_text(
        "export function build() {\n"
        "  const seen = new Set();\n"
        "  const index = new Map();\n"
        "  const controller = new AbortController();\n"
        "  requestAnimationFrame(() => seen.clear());\n"
        "  if (!index) throw new Error('nope');\n"
        "  return seen;\n"
        "}\n"
        "\n"
        "export function local() {\n"
        "  const helper = () => 1;\n"
        "  return helper();\n"
        "}\n"
        "\n"
        "export function viaParameter(onSelect) {\n"
        "  return onSelect();\n"
        "}\n",
        encoding="utf-8",
    )
    return root


def _targets(graph, src: str) -> set[str]:
    return {edge.dst for edge in graph.edges if edge.kind == "call" and edge.src == src}


def test_a_language_builtin_leaves_the_project(project: Path) -> None:
    graph = JavaScriptTypeScriptAdapter().parse(project)

    targets = _targets(graph, "javascript:index.js::build")

    for builtin in ("Set", "Map", "AbortController", "Error", "requestAnimationFrame"):
        assert f"external:{builtin}" in targets, f"{builtin} must read as external"
        assert not any(
            target.endswith(f":{builtin}") and target.startswith("unresolved:")
            for target in targets
        ), f"{builtin} must not read as a module Codemble failed to resolve"


def test_builtin_edges_are_flagged_external(project: Path) -> None:
    """`external` is what stops these being counted as project structure."""

    graph = JavaScriptTypeScriptAdapter().parse(project)

    builtins = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.dst.startswith("external:") and "Set" in edge.dst
    ]

    assert builtins
    assert all(edge.external for edge in builtins)
    assert all(edge.certain is False for edge in builtins)


def test_a_genuine_local_still_reads_as_unresolved(project: Path) -> None:
    """The honest case must survive: this must not launder unknowns as external.

    `onSelect` is a parameter -- whatever it holds is decided by the caller, so
    no definition in this project can be named. That is a real coverage limit
    and must keep saying so. (A local arrow function like `helper` is a
    different matter: the adapter already resolves it *certainly*, which is
    why it is not the example here.)
    """

    graph = JavaScriptTypeScriptAdapter().parse(project)

    targets = _targets(graph, "javascript:index.js::viaParameter")

    assert any(target.startswith("unresolved:") for target in targets), targets
    assert not any(target.startswith("external:") for target in targets)


def test_a_local_arrow_function_is_still_resolved_certainly(project: Path) -> None:
    graph = JavaScriptTypeScriptAdapter().parse(project)

    edges = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == "javascript:index.js::local"
    ]

    assert [edge.dst for edge in edges] == ["javascript:index.js::local.helper"]
    assert edges[0].certain is True


def test_resolution_stays_deterministic(project: Path) -> None:
    first = JavaScriptTypeScriptAdapter().parse(project)
    second = JavaScriptTypeScriptAdapter().parse(project)

    assert first.to_json() == second.to_json()
