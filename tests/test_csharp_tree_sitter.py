"""Parser-grounded C# graph contracts."""

from pathlib import Path

import pytest

from codemble.adapters.csharp_tree_sitter import CSharpAdapter, CSharpParseError

FIXTURE = Path(__file__).parent / "fixtures" / "csharp_sample"


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    return CSharpAdapter().parse(FIXTURE)


def test_discovery_owns_cs_and_skips_compiler_output() -> None:
    adapter = CSharpAdapter()
    root, files = adapter.discover(FIXTURE)

    assert adapter.language == "csharp"
    assert adapter.file_extensions == {".cs"}
    assert adapter.ignored_directories == {"bin", "obj"}
    assert root == FIXTURE.resolve()
    assert [file.relative_to(root).as_posix() for file in files] == [
        "src/Broken.cs",
        "src/Core/Shapes.cs",
        "src/Core/Store.cs",
        "src/Program.cs",
        "src/Query/Reports.cs",
        "src/Tests/StoreTests.cs",
    ]

    generated = FIXTURE / "obj"
    explicit_root, explicit_files = adapter.discover(generated)
    assert explicit_root == generated.resolve()
    assert [file.name for file in explicit_files] == ["AssemblyInfo.cs"]


def test_structures_are_parser_proven_and_exactly_spanned(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    module = nodes["csharp:src/Program.cs"]
    assert module.kind == "module"
    assert module.language == "csharp"
    assert (module.lineno, module.end_lineno, module.loc) == (1, 38, 38)

    # `namespace Acme.App;` carries no body, so its span is the declaration and
    # the types after it hang off it by qualified name.
    file_scoped = nodes["csharp:src/Program.cs::Acme.App"]
    assert (file_scoped.kind, file_scoped.lineno, file_scoped.end_lineno) == (
        "class",
        6,
        6,
    )
    blocked = nodes["csharp:src/Core/Store.cs::Acme.Core"]
    assert (blocked.kind, blocked.lineno, blocked.end_lineno) == ("class", 3, 34)

    main = nodes["csharp:src/Program.cs::Acme.App.Program.Main"]
    assert (main.kind, main.lineno, main.end_lineno, main.loc) == ("function", 19, 24, 6)
    assert main.file == "src/Program.cs"
    assert main.region == "csharp:src/Program.cs"

    constructor = nodes["csharp:src/Program.cs::Acme.App.Program.Program"]
    assert (constructor.kind, constructor.lineno, constructor.end_lineno) == (
        "function",
        14,
        17,
    )
    assert nodes["csharp:src/Program.cs::Acme.App.Program.Label"].kind == "function"
    assert nodes["csharp:src/Core/Store.cs::Acme.Core.IStore"].kind == "class"
    assert nodes["csharp:src/Core/Store.cs::Acme.Core.Person"].kind == "class"
    assert nodes["csharp:src/Core/Store.cs::Acme.Core.Color"].kind == "class"
    assert nodes["csharp:src/Core/Shapes.cs::Acme.Core.Point"].kind == "class"

    for node in graph.nodes:
        assert node.file in graph.file_hashes
        assert 1 <= node.lineno <= node.end_lineno
        assert node.loc >= 1


def test_using_directives_import_namespaces_not_types(graph) -> None:  # type: ignore[no-untyped-def]
    imports = {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "import"
    }

    # One project file declares `Acme.Query`, so the route is unambiguous.
    assert (
        "csharp:src/Program.cs",
        "csharp:src/Query/Reports.cs",
        True,
        False,
    ) in imports
    # `Acme.Core` is declared by two files. A `using` names the namespace, not
    # one of them, so both stay possible and neither is picked.
    assert (
        "csharp:src/Program.cs",
        "csharp:src/Core/Store.cs",
        False,
        False,
    ) in imports
    assert (
        "csharp:src/Program.cs",
        "csharp:src/Core/Shapes.cs",
        False,
        False,
    ) in imports
    # A namespace no project file declares stays outside the graph.
    assert ("csharp:src/Program.cs", "external:System", True, True) in imports
    assert (
        "csharp:src/Program.cs",
        "external:System.Text.Json",
        True,
        True,
    ) in imports
    assert not any(dst.startswith("external:Acme.") for _, dst, _, _ in imports)


def test_calls_are_certain_only_where_dispatch_is_settled(graph) -> None:  # type: ignore[no-untyped-def]
    calls = {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "call"
    }

    # A bare call to a uniquely named member of the same type.
    assert (
        "csharp:src/Core/Store.cs::Acme.Core.MemoryStore.Save",
        "csharp:src/Core/Store.cs::Acme.Core.MemoryStore.Track",
        True,
        False,
    ) in calls
    assert (
        "csharp:src/Program.cs::Acme.App.Program.Run",
        "csharp:src/Program.cs::Acme.App.Program.Describe",
        True,
        False,
    ) in calls
    # `new` is not virtual: one declared type with one constructor is exact.
    assert (
        "csharp:src/Program.cs::Acme.App.Program.Main",
        "csharp:src/Program.cs::Acme.App.Program.Program",
        True,
        False,
    ) in calls
    # An interface-typed field names no implementation.
    assert (
        "csharp:src/Program.cs::Acme.App.Program.Run",
        "csharp:src/Core/Store.cs::Acme.Core.IStore.Save",
        False,
        False,
    ) in calls
    # A `var` local has no written type, so its member call is never claimed.
    assert (
        "csharp:src/Program.cs::Acme.App.Program.Main",
        "csharp:src/Program.cs::Acme.App.Program.Run",
        False,
        False,
    ) in calls
    assert (
        "csharp:src/Program.cs::Acme.App.Program.Run",
        "external:store.Save",
        False,
        True,
    ) in calls
    assert (
        "csharp:src/Query/Reports.cs::Acme.Query.Reports.Recent",
        "external:picked.ToList",
        False,
        True,
    ) in calls
    # No call to a structure outside this project is ever marked certain.
    assert not any(certain for _, _, certain, external in calls if external)


def test_delegate_invocation_is_never_resolved_to_a_structure(tmp_path: Path) -> None:
    (tmp_path / "Runner.cs").write_text(
        "using System;\n"
        "\n"
        "public class Runner\n"
        "{\n"
        "    public void Go(Action step)\n"
        "    {\n"
        "        step();\n"
        "    }\n"
        "\n"
        "    private void Step()\n"
        "    {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    calls = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == "csharp:Runner.cs::Runner.Go"
    ]

    assert len(calls) == 1
    assert calls[0].dst == "unresolved:csharp:Runner.cs::Runner.Go:step"
    assert calls[0].certain is False


def test_constructor_overloads_stay_possible(tmp_path: Path) -> None:
    (tmp_path / "Box.cs").write_text(
        "public class Box\n"
        "{\n"
        "    public Box() { }\n"
        "\n"
        "    public Box(int size) { }\n"
        "\n"
        "    public static Box Make() => new Box(1);\n"
        "}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    calls = sorted(
        (edge for edge in graph.edges if edge.kind == "call"),
        key=lambda edge: edge.dst,
    )

    assert [(edge.dst, edge.certain) for edge in calls] == [
        ("csharp:Box.cs::Box.Box", False),
        ("csharp:Box.cs::Box.Box@5", False),
    ]


def test_partial_files_stay_visible_without_claiming_broken_structures(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert graph.partial_files == ("src/Broken.cs",)
    assert nodes["csharp:src/Broken.cs"].partial is True
    assert nodes["csharp:src/Broken.cs"].file in graph.file_hashes
    assert "csharp:src/Broken.cs::Acme.App.Intact.Visible" in nodes
    assert "csharp:src/Broken.cs::Acme.App.Damaged" not in nodes
    assert "csharp:src/Broken.cs::Acme.App.Damaged.Snapped" not in nodes


def test_entrypoint_ranking_and_explicit_selection_are_parser_bounded(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert graph.entrypoint_candidates == (
        "csharp:src/Program.cs::Acme.App.Program.Main",
        "csharp:src/Tests/StoreTests.cs::Acme.Tests.StoreTests",
    )
    assert nodes["csharp:src/Program.cs::Acme.App.Program.Main"].entrypoint_rank == 0
    assert (
        nodes["csharp:src/Tests/StoreTests.cs::Acme.Tests.StoreTests"].entrypoint_rank
        == 9
    )
    assert graph.selected_entrypoint == "csharp:src/Program.cs::Acme.App.Program.Main"

    selected = CSharpAdapter().parse(
        FIXTURE, entrypoint="csharp:src/Tests/StoreTests.cs::Acme.Tests.StoreTests"
    )
    assert (
        selected.selected_entrypoint
        == "csharp:src/Tests/StoreTests.cs::Acme.Tests.StoreTests"
    )
    with pytest.raises(CSharpParseError, match="not parser-ranked"):
        CSharpAdapter().parse(FIXTURE, entrypoint="made-up")


def test_top_level_statements_rank_the_file_itself(tmp_path: Path) -> None:
    (tmp_path / "Program.cs").write_text(
        'using System;\n\nConsole.WriteLine("ready");\n',
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    module = next(node for node in graph.nodes if node.id == "csharp:Program.cs")

    assert module.entrypoint_rank == 1
    assert graph.entrypoint_candidates == ("csharp:Program.cs",)
    assert any(
        edge.src == "csharp:Program.cs" and edge.dst == "external:Console.WriteLine"
        for edge in graph.edges
    )


def test_repeated_parses_are_byte_identical() -> None:
    first = CSharpAdapter().parse(FIXTURE).to_json()
    second = CSharpAdapter().parse(FIXTURE).to_json()

    assert first == second


def test_concepts_are_tree_sitter_proven_owned_and_language_tagged(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}
    concepts_by_node: dict[str, set[str]] = {}
    for annotation in graph.concept_annotations:
        concepts_by_node.setdefault(annotation.node_id, set()).add(annotation.concept)
        owner = nodes[annotation.node_id]
        assert annotation.language == "csharp"
        assert annotation.snippet
        assert owner.lineno <= annotation.lineno <= owner.end_lineno

    assert concepts_by_node["csharp:src/Program.cs::Acme.App.Program.Main"] == {
        "async-await"
    }
    assert concepts_by_node["csharp:src/Query/Reports.cs::Acme.Query.Reports.Recent"] == {
        "generic",
        "linq-query",
    }
    assert concepts_by_node[
        "csharp:src/Query/Reports.cs::Acme.Query.Reports.Describe"
    ] == {"pattern-matching"}
    assert concepts_by_node["csharp:src/Query/Reports.cs::Acme.Query.Reports.Twice"] == {
        "extension-method"
    }
    assert concepts_by_node["csharp:src/Core/Store.cs::Acme.Core.Person"] == {
        "nullable-type",
        "record",
    }
    assert concepts_by_node["csharp:src/Core/Store.cs::Acme.Core.MemoryStore.Count"] == {
        "property-accessors"
    }
    # Nothing is claimed about a file the parser could not read through.
    assert not any(
        annotation.node_id.startswith("csharp:src/Broken.cs")
        for annotation in graph.concept_annotations
    )


def test_concepts_method_matches_graph_annotations_for_one_owner(graph) -> None:  # type: ignore[no-untyped-def]
    node = next(
        node
        for node in graph.nodes
        if node.id == "csharp:src/Core/Store.cs::Acme.Core.Person"
    )
    source = (FIXTURE / node.file).read_text(encoding="utf-8")

    direct = CSharpAdapter().concepts(node, source)
    serialized = [
        annotation
        for annotation in graph.concept_annotations
        if annotation.node_id == node.id
    ]

    assert direct == serialized
    assert {annotation.concept for annotation in direct} == {"nullable-type", "record"}


def test_a_single_file_scope_still_parses(tmp_path: Path) -> None:
    source_file = tmp_path / "Solo.cs"
    source_file.write_text(
        "namespace Solo.App;\n\npublic sealed class Solo\n{\n    public void Go() { }\n}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(source_file)

    assert graph.partial_files == ()
    assert {node.id for node in graph.nodes} == {
        "csharp:Solo.cs",
        "csharp:Solo.cs::Solo.App",
        "csharp:Solo.cs::Solo.App.Solo",
        "csharp:Solo.cs::Solo.App.Solo.Go",
    }
