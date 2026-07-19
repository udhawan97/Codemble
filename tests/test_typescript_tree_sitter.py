"""Parser-grounded JavaScript/TypeScript graph contracts."""

from pathlib import Path

import pytest

from codemble.adapters.project import ProjectParser
from codemble.adapters.typescript_tree_sitter import (
    JavaScriptTypeScriptAdapter,
    JavaScriptTypeScriptParseError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    return JavaScriptTypeScriptAdapter().parse(FIXTURE)


def test_discovers_all_supported_extensions_and_ignores_dependencies() -> None:
    adapter = JavaScriptTypeScriptAdapter()
    root, files = adapter.discover(FIXTURE)

    assert root == FIXTURE.resolve()
    assert adapter.file_extensions == {
        ".cjs",
        ".cts",
        ".js",
        ".jsx",
        ".mjs",
        ".mts",
        ".ts",
        ".tsx",
    }
    assert [file.relative_to(root).as_posix() for file in files] == [
        "src/broken.ts",
        "src/legacy.js",
        "src/local.js",
        "src/main.ts",
        "src/reexport.ts",
        "src/util.ts",
        "src/widget.tsx",
    ]


def test_nodes_are_parser_proven_language_tagged_and_spanned(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert nodes["typescript:src/main.ts"].kind == "module"
    assert nodes["typescript:src/main.ts"].language == "typescript"
    assert nodes["javascript:src/legacy.js"].language == "javascript"
    assert nodes["typescript:src/main.ts::main"].lineno == 4
    assert nodes["typescript:src/main.ts::main"].end_lineno == 7
    assert nodes["typescript:src/util.ts::Formatter"].kind == "class"
    assert nodes["typescript:src/util.ts::Formatter.wrap"].kind == "function"
    assert nodes["typescript:src/widget.tsx::Card"].kind == "function"
    assert "typescript:src/broken.ts::visible" in nodes
    assert "typescript:src/broken.ts::broken" not in nodes


def test_import_resolution_preserves_exact_and_possible_evidence(graph) -> None:  # type: ignore[no-untyped-def]
    imports = {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "import"
    }

    assert (
        "javascript:src/legacy.js",
        "javascript:src/local.js",
        True,
        False,
    ) in imports
    assert (
        "typescript:src/main.ts",
        "typescript:src/util.ts",
        False,
        False,
    ) in imports
    assert (
        "typescript:src/reexport.ts",
        "typescript:src/util.ts",
        False,
        False,
    ) in imports
    assert (
        "typescript:src/widget.tsx",
        "external:react",
        True,
        True,
    ) in imports
    assert (
        "typescript:src/main.ts",
        "typescript:src/widget.tsx",
        False,
        False,
    ) in imports


def test_calls_are_exact_only_when_symbol_and_path_are_unambiguous(graph) -> None:  # type: ignore[no-untyped-def]
    calls = {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "call"
    }

    assert (
        "typescript:src/util.ts::helper",
        "typescript:src/util.ts::normalize",
        True,
        False,
    ) in calls
    assert (
        "typescript:src/util.ts::Formatter.wrap",
        "typescript:src/util.ts::Formatter.format",
        True,
        False,
    ) in calls
    assert (
        "javascript:src/legacy.js::run",
        "javascript:src/local.js::legacyHelper",
        True,
        False,
    ) in calls
    assert (
        "typescript:src/main.ts::main",
        "typescript:src/util.ts::helper",
        False,
        False,
    ) in calls
    assert (
        "typescript:src/widget.tsx::Widget.run",
        "typescript:src/util.ts::helper",
        False,
        False,
    ) in calls


def test_partial_files_stay_visible_without_claiming_broken_structures(graph) -> None:  # type: ignore[no-untyped-def]
    broken = next(node for node in graph.nodes if node.id == "typescript:src/broken.ts")

    assert graph.partial_files == ("src/broken.ts",)
    assert broken.partial is True
    assert broken.file in graph.file_hashes


def test_entrypoint_ranking_and_explicit_selection_are_parser_bounded(graph) -> None:  # type: ignore[no-untyped-def]
    assert graph.entrypoint_candidates[:2] == (
        "typescript:src/main.ts",
        "typescript:src/main.ts::main",
    )
    assert graph.selected_entrypoint == "typescript:src/main.ts"

    selected = JavaScriptTypeScriptAdapter().parse(
        FIXTURE, entrypoint="typescript:src/main.ts::main"
    )
    assert selected.selected_entrypoint == "typescript:src/main.ts::main"
    with pytest.raises(JavaScriptTypeScriptParseError, match="not parser-ranked"):
        JavaScriptTypeScriptAdapter().parse(FIXTURE, entrypoint="made-up")


def test_mixed_project_home_is_resolved_across_adapters() -> None:
    graph = ProjectParser().parse(FIXTURE)

    assert {node.language for node in graph.nodes} == {
        "javascript",
        "python",
        "typescript",
    }
    assert graph.entrypoint_candidates[:2] == (
        "python_worker",
        "typescript:src/main.ts",
    )
    assert graph.selected_entrypoint is None


def test_repeated_mixed_parses_are_byte_identical() -> None:
    first = ProjectParser().parse(FIXTURE).to_json()
    second = ProjectParser().parse(FIXTURE).to_json()

    assert first == second


@pytest.mark.parametrize(
    ("extension", "source", "language"),
    [
        (".js", "export function mapped() {}\n", "javascript"),
        (".jsx", "export const Mapped = () => <main />;\n", "javascript"),
        (".mjs", "export function mapped() {}\n", "javascript"),
        (".cjs", "function mapped() {}\n", "javascript"),
        (".ts", "export function mapped(): void {}\n", "typescript"),
        (".tsx", "export const Mapped = (): JSX.Element => <main />;\n", "typescript"),
        (".mts", "export function mapped(): void {}\n", "typescript"),
        (".cts", "function mapped(): void {}\n", "typescript"),
    ],
)
def test_each_registered_extension_uses_the_matching_grammar(
    tmp_path: Path,
    extension: str,
    source: str,
    language: str,
) -> None:
    source_file = tmp_path / f"sample{extension}"
    source_file.write_text(source, encoding="utf-8")

    graph = JavaScriptTypeScriptAdapter().parse(source_file)

    assert graph.partial_files == ()
    assert {node.language for node in graph.nodes} == {language}
    assert any(node.kind == "function" for node in graph.nodes)


def test_local_bindings_never_inherit_import_or_module_certainty(tmp_path: Path) -> None:
    (tmp_path / "util.js").write_text(
        "export function helper() { return 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text(
        'import { helper } from "./util.js";\n'
        "export function run(helper) { return helper(); }\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)
    calls = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == "javascript:app.js::run"
    ]

    assert len(calls) == 1
    assert calls[0].dst == "unresolved:javascript:app.js::run:helper"
    assert calls[0].certain is False


def test_block_scoped_require_is_not_promoted_to_a_module_binding(tmp_path: Path) -> None:
    (tmp_path / "util.js").write_text(
        "export function helper() { return 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text(
        'if (enabled) { const { helper } = require("./util.js"); }\n'
        "export function run() { return helper(); }\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)
    call = next(
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == "javascript:app.js::run"
    )

    assert call.dst == "unresolved:javascript:app.js:helper"
    assert call.certain is False


def test_generated_js_output_is_skipped_without_changing_python_discovery(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text(
        "export function main(): void {}\n",
        encoding="utf-8",
    )
    generated = tmp_path / "build"
    generated.mkdir()
    (generated / "bundle.js").write_text(
        "export function generated() {}\n",
        encoding="utf-8",
    )
    (generated / "worker.py").write_text("def worker():\n    pass\n", encoding="utf-8")

    root, files = ProjectParser().discover(tmp_path)
    graph = ProjectParser().parse(tmp_path)

    assert root == tmp_path.resolve()
    assert [file.relative_to(root).as_posix() for file in files] == [
        "build/worker.py",
        "src/app.ts",
    ]
    assert "build.worker" in {node.id for node in graph.nodes}
    assert not any(node.file == "build/bundle.js" for node in graph.nodes)

    explicit_root, explicit_files = JavaScriptTypeScriptAdapter().discover(generated)
    assert explicit_root == generated.resolve()
    assert [file.name for file in explicit_files] == ["bundle.js"]
