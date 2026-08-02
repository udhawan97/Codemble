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


def test_virtual_dispatch_is_never_certain(tmp_path: Path) -> None:
    """A member a derived class may replace is not settled by the call site."""

    (tmp_path / "Dispatch.cs").write_text(
        "namespace Probe;\n"
        "\n"
        "public interface IThing\n"
        "{\n"
        "    void Ping();\n"
        "\n"
        "    void PingTwice()\n"
        "    {\n"
        "        Ping();\n"
        "    }\n"
        "}\n"
        "\n"
        "public abstract class Base\n"
        "{\n"
        "    public void Run()\n"
        "    {\n"
        "        Step();\n"
        "        this.Tidy();\n"
        "        Settled();\n"
        "    }\n"
        "\n"
        "    public virtual void Step()\n"
        "    {\n"
        "    }\n"
        "\n"
        "    protected abstract void Tidy();\n"
        "\n"
        "    private void Settled()\n"
        "    {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    calls = {(edge.src, edge.dst): edge.certain for edge in graph.edges if edge.kind == "call"}
    module = "csharp:Dispatch.cs"

    # `virtual` and `abstract` reach whichever override the instance carries,
    # and that override may be declared outside this parse entirely.
    assert calls[(f"{module}::Probe.Base.Run", f"{module}::Probe.Base.Step")] is False
    assert calls[(f"{module}::Probe.Base.Run", f"{module}::Probe.Base.Tidy")] is False
    # An interface member writes no modifier and is virtual all the same.
    assert (
        calls[(f"{module}::Probe.IThing.PingTwice", f"{module}::Probe.IThing.Ping")]
        is False
    )
    # A private member no derived class may replace still binds here for good,
    # so the rule withholds certainty rather than abolishing it.
    assert calls[(f"{module}::Probe.Base.Run", f"{module}::Probe.Base.Settled")] is True


def test_base_call_targets_the_base_type_never_the_calling_override(
    tmp_path: Path,
) -> None:
    """`base.M()` is the one call guaranteed not to reach this type's member."""

    (tmp_path / "Inherit.cs").write_text(
        "namespace Probe;\n"
        "\n"
        "public class Parent\n"
        "{\n"
        "    public virtual void Save()\n"
        "    {\n"
        "    }\n"
        "}\n"
        "\n"
        "public class Child : Parent\n"
        "{\n"
        "    public override void Save()\n"
        "    {\n"
        "        base.Save();\n"
        "    }\n"
        "}\n"
        "\n"
        "public class Orphan : System.Exception\n"
        "{\n"
        "    public override string ToString() => base.ToString();\n"
        "}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    module = "csharp:Inherit.cs"
    calls = [edge for edge in graph.edges if edge.kind == "call"]

    child_save = f"{module}::Probe.Child.Save"
    assert (child_save, f"{module}::Probe.Parent.Save", False) in [
        (edge.src, edge.dst, edge.certain) for edge in calls
    ]
    # Resolving `base` against the enclosing type named the override as the
    # target of the call that exists to skip it -- a structure that calls
    # itself, which is not what the source says.
    assert not any(edge.src == edge.dst for edge in calls)
    # A base type outside this parse names no project structure to point at.
    assert (f"{module}::Probe.Orphan.ToString", "external:base.ToString", False, True) in [
        (edge.src, edge.dst, edge.certain, edge.external) for edge in calls
    ]


def test_unqualified_call_across_types_in_one_file_stays_possible(
    tmp_path: Path,
) -> None:
    """Sharing a file settles nothing about what an unqualified name reaches."""

    (tmp_path / "Neighbours.cs").write_text(
        "namespace Probe;\n"
        "\n"
        "public class Holder\n"
        "{\n"
        "    public void Go()\n"
        "    {\n"
        "        Helper();\n"
        "    }\n"
        "}\n"
        "\n"
        "public static class Other\n"
        "{\n"
        "    public static void Helper()\n"
        "    {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    module = "csharp:Neighbours.cs"

    edge = next(
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == f"{module}::Probe.Holder.Go"
    )
    assert edge.dst == f"{module}::Probe.Other.Helper"
    # `Holder` reaches `Other.Helper` unqualified only through inheritance or a
    # `using static` this parse has not followed, so the name match is a lead.
    assert edge.certain is False


def test_generic_invocation_resolves_the_member_it_names(tmp_path: Path) -> None:
    (tmp_path / "Generic.cs").write_text(
        "namespace Probe;\n"
        "\n"
        "public class Runner\n"
        "{\n"
        "    public void Go()\n"
        "    {\n"
        "        Wrap<int>();\n"
        "    }\n"
        "\n"
        "    private void Wrap<T>()\n"
        "    {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    module = "csharp:Generic.cs"

    edge = next(
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == f"{module}::Probe.Runner.Go"
    )
    # Type arguments change no name this parse resolves by, so calling the
    # member outside the project was a claim the tree contradicts.
    assert (edge.dst, edge.certain, edge.external) == (
        f"{module}::Probe.Runner.Wrap",
        True,
        False,
    )


def test_using_static_reaches_the_project_file_declaring_its_namespace(
    tmp_path: Path,
) -> None:
    (tmp_path / "Lib.cs").write_text(
        "namespace Acme.Lib;\n"
        "\n"
        "public static class Helpers\n"
        "{\n"
        "    public static void Ping()\n"
        "    {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "Caller.cs").write_text(
        "using static Acme.Lib.Helpers;\nusing static System.Math;\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)
    imports = {
        (edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "import" and edge.src == "csharp:Caller.cs"
    }

    # `using static` names a type, so the namespace is its qualifier. Looking
    # the whole thing up found no declaring file and published the route as a
    # certain exit from the project, with the type sitting in the parse.
    assert ("csharp:Lib.cs", True, False) in imports
    assert not any(dst.startswith("external:Acme.") for dst, _, _ in imports)
    # A namespace no project file declares is still honestly external.
    assert ("external:System.Math", True, True) in imports


def test_unresolvable_calls_do_not_share_one_destination(tmp_path: Path) -> None:
    for name in ("First", "Second"):
        (tmp_path / f"{name}.cs").write_text(
            "namespace Probe;\n"
            f"public class {name}\n"
            "{\n"
            "    public void Go(System.Func<int>[] fs)\n"
            "    {\n"
            "        fs[0]();\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )

    graph = CSharpAdapter().parse(tmp_path)
    dynamic = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.dst.startswith("external:dynamic-call")
    ]

    assert len(dynamic) == 2
    # Two unrelated calls that happened to sit on the same line shared one
    # destination, which reads as a place they both go.
    assert len({edge.dst for edge in dynamic}) == 2
    assert not any(edge.certain for edge in dynamic)


def test_line_numbers_index_the_line_they_name(tmp_path: Path) -> None:
    """Line numbers come from the tree, so the source must be split its way."""

    # A form feed is one of nine characters `str.splitlines` breaks on and the
    # grammar reads as ordinary text. One inside a string literal shifted every
    # later snippet onto its predecessor's line while still citing its own.
    source = (
        "namespace Probe;\n"
        "\n"
        "public class Doc\n"
        "{\n"
        '    public string Page() => "top\fbottom";\n'
        "\n"
        "    public async Task Later()\n"
        "    {\n"
        "        await Task.Delay(1);\n"
        "    }\n"
        "}\n"
    )
    (tmp_path / "Doc.cs").write_text(source, encoding="utf-8")

    graph = CSharpAdapter().parse(tmp_path)
    real_lines = source.split("\n")
    module = next(node for node in graph.nodes if node.kind == "module")

    assert (module.end_lineno, module.loc) == (11, 11)
    assert graph.concept_annotations
    for annotation in graph.concept_annotations:
        assert annotation.snippet == real_lines[annotation.lineno - 1].strip()
    for node in graph.nodes:
        assert node.end_lineno <= 11


def test_degenerate_files_degrade_to_partial_parses(tmp_path: Path) -> None:
    (tmp_path / "Empty.cs").write_bytes(b"")
    (tmp_path / "Comments.cs").write_bytes(b"// only a comment\n/* and a block */\n")
    (tmp_path / "Severe.cs").write_bytes(b"}}}} class ??? {{{ <<<>>> namespace ;;;\n")
    # Undecodable bytes inside a string literal: the grammar reads bytes, so
    # this parses, and the decoded source must not take spans with it.
    (tmp_path / "Bytes.cs").write_bytes(
        b'namespace Probe;\npublic class B { public string S() => "\xff\xfe"; }\n'
    )
    (tmp_path / "Binary.cs").write_bytes(b"\xff\xfe\x00\x01\x02binary\x00\x00")

    graph = CSharpAdapter().parse(tmp_path)
    nodes = {node.id: node for node in graph.nodes}

    assert graph.partial_files == ("Binary.cs", "Severe.cs")
    assert nodes["csharp:Empty.cs"].partial is False
    assert (nodes["csharp:Empty.cs"].lineno, nodes["csharp:Empty.cs"].loc) == (1, 1)
    assert nodes["csharp:Comments.cs"].partial is False
    # Nothing is claimed inside a file the parser could not read through.
    assert not any(
        node.id.startswith(("csharp:Binary.cs::", "csharp:Severe.cs::"))
        for node in graph.nodes
    )
    assert "csharp:Bytes.cs::Probe.B.S" in nodes
    for node in graph.nodes:
        assert node.file in graph.file_hashes
        assert 1 <= node.lineno <= node.end_lineno
    assert graph.to_json()


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
