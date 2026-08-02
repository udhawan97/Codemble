"""Parser-grounded Go graph contracts."""

from pathlib import Path

import pytest

from codemble.adapters.go_tree_sitter import GoAdapter, GoParseError

FIXTURE = Path(__file__).parent / "fixtures" / "go_sample"


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    return GoAdapter().parse(FIXTURE)


def _edges(graph, kind):  # type: ignore[no-untyped-def]
    return {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == kind
    }


def test_discovers_go_sources_and_skips_vendored_and_testdata_trees() -> None:
    adapter = GoAdapter()
    root, files = adapter.discover(FIXTURE)

    assert root == FIXTURE.resolve()
    assert adapter.file_extensions == {".go"}
    assert adapter.ignored_directories == {"testdata", "vendor"}
    assert [file.relative_to(root).as_posix() for file in files] == [
        "cmd/app/main.go",
        "internal/report/broken.go",
        "internal/report/report.go",
        "internal/store/store.go",
        "internal/store/store_test.go",
    ]


def test_nodes_are_parser_proven_language_tagged_and_spanned(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert nodes["go:cmd/app/main.go"].kind == "module"
    assert nodes["go:cmd/app/main.go"].language == "go"
    assert nodes["go:cmd/app/main.go::main"].lineno == 10
    assert nodes["go:cmd/app/main.go::main"].end_lineno == 16
    assert nodes["go:cmd/app/main.go::main"].loc == 7
    assert nodes["go:internal/store/store.go::Store"].kind == "class"
    assert nodes["go:internal/store/store.go::Writer"].kind == "class"
    assert nodes["go:internal/report/report.go::Map"].kind == "function"
    assert nodes["go:internal/store/store.go::New"].region == "go:internal/store/store.go"
    assert all(node.file and node.lineno >= 1 and node.loc >= 1 for node in graph.nodes)
    # An unexported struct is still a structure a learner can open, so being
    # lowercase is no reason to leave it out of the graph.
    assert "go:internal/store/store.go::base" in nodes


def test_a_method_id_names_the_receiver_type_it_belongs_to(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert nodes["go:internal/store/store.go::(*Store).Save"].name == "Save"
    assert nodes["go:internal/store/store.go::(Store).Count"].name == "Count"
    assert "go:internal/store/store.go::Save" not in nodes
    assert "go:internal/store/store.go::Count" not in nodes


def test_imports_reach_every_non_test_file_of_the_resolved_package(graph) -> None:  # type: ignore[no-untyped-def]
    imports = _edges(graph, "import")

    assert ("go:cmd/app/main.go", "go:internal/store/store.go", True, False) in imports
    assert ("go:cmd/app/main.go", "go:internal/report/report.go", True, False) in imports
    # A file the parser could only read in part is still a file of that package.
    assert ("go:cmd/app/main.go", "go:internal/report/broken.go", True, False) in imports
    assert ("go:cmd/app/main.go", "external:fmt", True, True) in imports
    # `go test` alone compiles a `_test.go` file, so importing its package does
    # not depend on it.
    assert not any(dst.endswith("store_test.go") for _, dst, _, _ in imports)


def test_calls_are_exact_only_when_the_parse_tree_proves_the_target(graph) -> None:  # type: ignore[no-untyped-def]
    calls = _edges(graph, "call")

    assert (
        "go:internal/report/report.go::Render",
        "go:internal/report/report.go::collect",
        True,
        False,
    ) in calls
    assert (
        "go:cmd/app/main.go::main",
        "go:internal/store/store.go::New",
        True,
        False,
    ) in calls
    assert (
        "go:cmd/app/main.go::main",
        "go:internal/report/report.go::Render",
        True,
        False,
    ) in calls
    assert (
        "go:internal/report/report.go::collect",
        "go:internal/report/report.go::emit",
        True,
        False,
    ) in calls


def test_calls_through_a_value_or_an_interface_are_never_certain(graph) -> None:  # type: ignore[no-untyped-def]
    calls = _edges(graph, "call")

    # `persist` holds a `Writer`; which implementation answers `Save` is decided
    # at run time, so the only proven method of that name is a possibility.
    assert (
        "go:internal/store/store.go::persist",
        "go:internal/store/store.go::(*Store).Save",
        False,
        False,
    ) in calls
    # `main` calls a method on a value whose type this adapter does not infer,
    # and package `main` declares no method of that name to point at.
    assert (
        "go:cmd/app/main.go::main",
        "unresolved:go:cmd/app/main.go:s.Save",
        False,
        False,
    ) in calls
    # `transform` is a parameter: a function value, not a named function.
    assert (
        "go:internal/report/report.go::Map",
        "unresolved:go:internal/report/report.go::Map:transform",
        False,
        False,
    ) in calls
    assert (
        "go:internal/store/store.go::(*Store).Save",
        "external:errors.New",
        False,
        True,
    ) in calls


def test_explicit_generic_instantiation_is_possible_only_when_ambiguous(graph) -> None:  # type: ignore[no-untyped-def]
    calls = _edges(graph, "call")

    # `Map[string, string](xs, f)` cannot be a conversion, so the grammar calls
    # it a call and the target is proven.
    assert (
        "go:internal/report/report.go::headings",
        "go:internal/report/report.go::Map",
        True,
        False,
    ) in calls
    # `first[string](xs)` is spelled exactly like a conversion to a generic
    # type. It is kept as a possible call, never dropped and never upgraded.
    assert (
        "go:internal/report/report.go::titles",
        "go:internal/report/report.go::first",
        False,
        False,
    ) in calls


def test_conversions_builtins_and_literals_never_become_calls(tmp_path: Path) -> None:
    (tmp_path / "main.go").write_text(
        "package main\n"
        "\n"
        "type Celsius float64\n"
        "\n"
        "type Reading struct{ v float64 }\n"
        "\n"
        "func main() {\n"
        "\t_ = Celsius(1.5)\n"
        "\t_ = Reading{}\n"
        "\t_ = len(\"ab\")\n"
        "\t_ = int64(3)\n"
        "\thelper()\n"
        "}\n"
        "\n"
        "func helper() {}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)
    calls = [edge for edge in graph.edges if edge.kind == "call"]

    assert [(edge.dst, edge.certain) for edge in calls] == [
        ("go:main.go::helper", True)
    ]


def test_an_invoked_function_literal_stays_a_possible_call(tmp_path: Path) -> None:
    (tmp_path / "main.go").write_text(
        "package main\n"
        "\n"
        "func main() {\n"
        "\tfunc() { helper() }()\n"
        "}\n"
        "\n"
        "func helper() {}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)
    calls = {(edge.dst, edge.certain) for edge in graph.edges if edge.kind == "call"}

    assert ("external:dynamic-call@4", False) in calls
    assert ("go:main.go::helper", True) in calls


def test_imports_without_a_module_manifest_are_possible_not_proven(
    tmp_path: Path,
) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.go").write_text(
        "package main\n"
        "\n"
        'import "example.com/proj/internal/db"\n'
        "\n"
        "func main() { db.Open() }\n",
        encoding="utf-8",
    )
    (tmp_path / "internal" / "db").mkdir(parents=True)
    (tmp_path / "internal" / "db" / "db.go").write_text(
        "package db\n\nfunc Open() {}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)

    assert (
        "go:app/main.go",
        "go:internal/db/db.go",
        False,
        False,
    ) in _edges(graph, "import")
    assert (
        "go:app/main.go::main",
        "go:internal/db/db.go::Open",
        False,
        False,
    ) in _edges(graph, "call")


def test_a_standard_library_path_never_matches_a_project_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / "fmt").mkdir()
    (tmp_path / "fmt" / "fmt.go").write_text(
        "package fmt\n\nfunc Println(text string) {}\n",
        encoding="utf-8",
    )
    (tmp_path / "app.go").write_text(
        'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("x") }\n',
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)

    assert ("go:app.go", "external:fmt", True, True) in _edges(graph, "import")
    assert ("go:app.go::main", "external:fmt.Println", False, True) in _edges(
        graph,
        "call",
    )


def test_a_local_name_shadowing_a_package_never_resolves_through_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "go.mod").write_text("module example.com/x\n", encoding="utf-8")
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "db.go").write_text(
        "package db\n\nfunc Open() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "app.go").write_text(
        "package main\n"
        "\n"
        'import "example.com/x/db"\n'
        "\n"
        "func main(db Handle) { db.Open() }\n"
        "\n"
        "type Handle struct{}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)
    calls = _edges(graph, "call")

    assert ("go:app.go::main", "go:db/db.go::Open", True, False) not in calls
    assert ("go:app.go::main", "unresolved:go:app.go:db.Open", False, False) in calls


def test_a_name_bound_at_any_depth_shadows_the_package_scope(tmp_path: Path) -> None:
    # Every one of these binds a name somewhere the enclosing declaration's own
    # `parameters` field cannot see. Reading only that field made each call
    # below a *certain* edge to the package function the local name hides.
    (tmp_path / "go.mod").write_text("module example.com/x\n", encoding="utf-8")
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "db.go").write_text(
        "package db\n\nfunc Open() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "main.go").write_text(
        "package main\n"
        "\n"
        'import "example.com/x/db"\n'
        "\n"
        "func run(apply func(func())) {\n"
        "\tapply(func(helper func()) {\n"
        "\t\thelper()\n"
        "\t})\n"
        "}\n"
        "\n"
        "func sel(ch chan func()) {\n"
        "\tselect {\n"
        "\tcase db := <-ch:\n"
        "\t\tdb.Open()\n"
        "\t}\n"
        "}\n"
        "\n"
        "func guard(v any) {\n"
        "\tswitch helper := v.(type) {\n"
        "\tcase func():\n"
        "\t\thelper()\n"
        "\t}\n"
        "}\n"
        "\n"
        "func helper() {}\n",
        encoding="utf-8",
    )

    calls = _edges(GoAdapter().parse(tmp_path), "call")
    proven = {(src, dst) for src, dst, certain, _ in calls if certain}

    # A closure parameter, a select receive, and a type-switch alias.
    assert ("go:main.go::run", "go:main.go::helper") not in proven
    assert ("go:main.go::sel", "go:db/db.go::Open") not in proven
    assert ("go:main.go::guard", "go:main.go::helper") not in proven
    # Shadowed, never dropped: each stays a possible call to an unnamed target.
    assert ("go:main.go::run", "unresolved:go:main.go::run:helper", False, False) in calls
    assert ("go:main.go::sel", "unresolved:go:main.go:db.Open", False, False) in calls
    assert (
        "go:main.go::guard",
        "unresolved:go:main.go::guard:helper",
        False,
        False,
    ) in calls
    # An unshadowed call in the same declaration is still proven.
    assert ("go:main.go::run", "unresolved:go:main.go::run:apply", False, False) in calls


def test_a_conversion_through_an_imported_package_is_not_a_call(
    tmp_path: Path,
) -> None:
    (tmp_path / "go.mod").write_text("module example.com/x\n", encoding="utf-8")
    (tmp_path / "units").mkdir()
    (tmp_path / "units" / "units.go").write_text(
        "package units\n"
        "\n"
        "type Celsius float64\n"
        "\n"
        "type Meters = float64\n"
        "\n"
        "func Make() Celsius { return 0 }\n",
        encoding="utf-8",
    )
    (tmp_path / "main.go").write_text(
        "package main\n"
        "\n"
        'import "example.com/x/units"\n'
        "\n"
        "type Local float64\n"
        "\n"
        "type Alias = float64\n"
        "\n"
        "func main() {\n"
        "\t_ = units.Celsius(1)\n"
        "\t_ = units.Meters(2)\n"
        "\t_ = Local(3)\n"
        "\t_ = Alias(4)\n"
        "\t_ = units.Make()\n"
        "}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)

    # A named type and an alias are both types; neither becomes a structure,
    # and converting through one is not a relationship to anything.
    assert not any(node.id.endswith("::Celsius") for node in graph.nodes)
    assert _edges(graph, "call") == {
        ("go:main.go::main", "go:units/units.go::Make", True, False)
    }


def test_partial_files_stay_visible_without_claiming_broken_structures(graph) -> None:  # type: ignore[no-untyped-def]
    broken = next(
        node for node in graph.nodes if node.id == "go:internal/report/broken.go"
    )

    assert graph.partial_files == ("internal/report/broken.go",)
    assert broken.partial is True
    assert broken.file in graph.file_hashes
    assert "go:internal/report/broken.go::Visible" in {node.id for node in graph.nodes}
    assert "go:internal/report/broken.go::broken" not in {node.id for node in graph.nodes}


def test_entrypoint_ranking_and_explicit_selection_are_parser_bounded(graph) -> None:  # type: ignore[no-untyped-def]
    assert graph.entrypoint_candidates == (
        "go:cmd/app/main.go",
        "go:cmd/app/main.go::main",
        "go:internal/store/store_test.go::TestMain",
        "go:cmd/app/main.go::Boot",
    )
    assert graph.selected_entrypoint == "go:cmd/app/main.go"

    selected = GoAdapter().parse(FIXTURE, entrypoint="go:cmd/app/main.go::main")
    assert selected.selected_entrypoint == "go:cmd/app/main.go::main"
    with pytest.raises(GoParseError, match="not parser-ranked"):
        GoAdapter().parse(FIXTURE, entrypoint="made-up")


def test_a_main_function_outside_package_main_is_not_an_entrypoint(
    tmp_path: Path,
) -> None:
    (tmp_path / "helper.go").write_text(
        "package helper\n\nfunc main() {}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)

    assert graph.entrypoint_candidates == ()
    assert graph.selected_entrypoint is None


def test_repeated_parses_are_byte_identical() -> None:
    assert GoAdapter().parse(FIXTURE).to_json() == GoAdapter().parse(FIXTURE).to_json()


def test_concepts_are_tree_sitter_proven_owned_and_language_tagged(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}
    by_node: dict[str, set[tuple[str, int]]] = {}
    for annotation in graph.concept_annotations:
        by_node.setdefault(annotation.node_id, set()).add(
            (annotation.concept, annotation.lineno)
        )
        assert annotation.language == "go"
        assert annotation.language == nodes[annotation.node_id].language
        assert annotation.snippet

    assert by_node["go:internal/report/report.go::collect"] == {
        ("channel", 16),
        ("goroutine", 17),
        ("channel", 18),
    }
    assert by_node["go:internal/report/report.go::Render"] == {("defer", 11)}
    assert ("generics", 22) in by_node["go:internal/report/report.go::Map"]
    assert by_node["go:internal/store/store.go"] == {("interface-assertion", 18)}
    assert by_node["go:internal/store/store.go::Store"] == {("struct-embedding", 14)}
    assert ("error-return", 24) in by_node["go:internal/store/store.go::(*Store).Save"]
    # `Count` returns an int, so the error-return idiom is not claimed for it.
    assert "go:internal/store/store.go::(Store).Count" not in by_node
    # Nothing is claimed about a file the parser could only read in part.
    assert "go:internal/report/broken.go" not in by_node


def test_concepts_method_matches_graph_annotations_for_one_owner(graph) -> None:  # type: ignore[no-untyped-def]
    node = next(
        node
        for node in graph.nodes
        if node.id == "go:internal/report/report.go::collect"
    )
    source = (FIXTURE / node.file).read_text(encoding="utf-8")

    direct = GoAdapter().concepts(node, source)
    serialized = [
        annotation
        for annotation in graph.concept_annotations
        if annotation.node_id == node.id
    ]

    assert direct == serialized
    assert direct


def test_an_empty_or_missing_scope_is_refused_rather_than_guessed(
    tmp_path: Path,
) -> None:
    with pytest.raises(GoParseError, match="no Go files found"):
        GoAdapter().parse(tmp_path)
    with pytest.raises(GoParseError, match="does not exist"):
        GoAdapter().parse(tmp_path / "absent")
