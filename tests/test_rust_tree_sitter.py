"""Parser-grounded Rust graph contracts."""

from pathlib import Path

import pytest

from codemble.adapters.rust_tree_sitter import RustAdapter, RustParseError

FIXTURE = Path(__file__).parent / "fixtures" / "rust_sample"


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    return RustAdapter().parse(FIXTURE)


def test_discovers_rust_sources_and_ignores_cargo_build_output() -> None:
    adapter = RustAdapter()
    root, files = adapter.discover(FIXTURE)

    assert root == FIXTURE.resolve()
    assert adapter.language == "rust"
    assert adapter.file_extensions == {".rs"}
    assert "target" in adapter.ignored_directories
    assert [file.relative_to(root).as_posix() for file in files] == [
        "src/broken.rs",
        "src/lib.rs",
        "src/main.rs",
        "src/render.rs",
        "src/util.rs",
    ]


def test_nodes_are_parser_proven_language_tagged_and_spanned(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert nodes["rust:src/util.rs"].kind == "module"
    assert {node.language for node in graph.nodes} == {"rust"}
    assert nodes["rust:src/util.rs::Mode"].kind == "class"
    assert nodes["rust:src/util.rs::Formatter"].kind == "class"
    assert nodes["rust:src/render.rs::Render"].kind == "class"
    assert nodes["rust:src/util.rs::text"].kind == "class"
    assert nodes["rust:src/util.rs::text.shout"].kind == "function"

    helper = nodes["rust:src/util.rs::helper"]
    assert (helper.kind, helper.lineno, helper.end_lineno, helper.loc) == ("function", 43, 49, 7)
    signature = nodes["rust:src/render.rs::Render.render"]
    assert (signature.kind, signature.lineno, signature.end_lineno) == ("function", 2, 2)


def test_impl_methods_belong_to_their_type_and_trait_impls_stay_distinct(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    inherent = nodes["rust:src/util.rs::Formatter#impl"]
    trait_impl = nodes["rust:src/util.rs::Formatter#Render"]

    assert inherent.name == "impl Formatter"
    assert trait_impl.name == "impl Render for Formatter"
    assert (inherent.lineno, inherent.end_lineno) == (13, 29)
    assert (trait_impl.lineno, trait_impl.end_lineno) == (31, 35)
    assert {
        node_id for node_id in nodes if node_id.startswith("rust:src/util.rs::Formatter#impl.")
    } == {
        "rust:src/util.rs::Formatter#impl.decorate",
        "rust:src/util.rs::Formatter#impl.new",
        "rust:src/util.rs::Formatter#impl.set_prefix",
    }
    assert "rust:src/util.rs::Formatter#Render.render" in nodes
    # The struct keeps its own node; the two impl blocks never collapse into it.
    assert nodes["rust:src/util.rs::Formatter"].lineno == 9


def test_mod_declarations_of_other_files_claim_no_second_structure(graph) -> None:  # type: ignore[no-untyped-def]
    node_ids = {node.id for node in graph.nodes}

    assert "rust:src/main.rs::util" not in node_ids
    assert "rust:src/lib.rs::render" not in node_ids
    assert "rust:src/util.rs::text" in node_ids


def test_import_resolution_preserves_exact_and_possible_evidence(graph) -> None:  # type: ignore[no-untyped-def]
    imports = {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "import"
    }

    assert imports == {
        # `use crate::util::{...}` and `use crate::render::Render` are rooted in
        # the crate, so the file they reach is proven.
        ("rust:src/main.rs", "rust:src/util.rs", True, False),
        ("rust:src/util.rs", "rust:src/render.rs", True, False),
        # A bare root could equally name a dependency, so it stays possible.
        ("rust:src/main.rs", "rust:src/render.rs", False, False),
        ("rust:src/lib.rs", "rust:src/util.rs", False, False),
        ("rust:src/util.rs", "external:std", True, True),
    }


def test_a_bare_root_never_matches_on_the_importing_module_itself(tmp_path: Path) -> None:
    (tmp_path / "src" / "util").mkdir(parents=True)
    (tmp_path / "src" / "lib.rs").write_text("pub mod util;\n", encoding="utf-8")
    (tmp_path / "src" / "util" / "mod.rs").write_text(
        "use std::collections::HashMap;\n\npub fn run() {}\n",
        encoding="utf-8",
    )

    graph = RustAdapter().parse(tmp_path)
    imports = {
        (edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "import" and edge.src == "rust:src/util/mod.rs"
    }

    # Read from inside `util`, `std::collections::HashMap` must consume at least
    # `std`; matching on the empty remainder would make the file import itself.
    assert imports == {("external:std", True, True)}


def test_two_files_on_one_module_path_are_both_possible(tmp_path: Path) -> None:
    (tmp_path / "src" / "util").mkdir(parents=True)
    (tmp_path / "src" / "lib.rs").write_text(
        "use crate::util::helper;\n\npub fn run() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "util.rs").write_text("pub fn helper() {}\n", encoding="utf-8")
    (tmp_path / "src" / "util" / "mod.rs").write_text("pub fn helper() {}\n", encoding="utf-8")

    graph = RustAdapter().parse(tmp_path)
    imports = {
        (edge.dst, edge.certain)
        for edge in graph.edges
        if edge.kind == "import" and edge.src == "rust:src/lib.rs"
    }

    assert imports == {("rust:src/util.rs", False), ("rust:src/util/mod.rs", False)}


def test_calls_are_exact_only_when_the_target_is_statically_provable(graph) -> None:  # type: ignore[no-untyped-def]
    calls = {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == "call"
    }

    # A free function named once in its own module.
    assert ("rust:src/util.rs::helper", "rust:src/util.rs::normalize", True, False) in calls
    # A path through an inline `mod`.
    assert ("rust:src/util.rs::helper", "rust:src/util.rs::text.shout", True, False) in calls
    # `self.decorate()` reaches the inherent block from inside the trait impl.
    assert (
        "rust:src/util.rs::Formatter#Render.render",
        "rust:src/util.rs::Formatter#impl.decorate",
        True,
        False,
    ) in calls
    # `Formatter::new` through a proven `use crate::util::{...}` binding.
    assert (
        "rust:src/main.rs::main",
        "rust:src/util.rs::Formatter#impl.new",
        True,
        False,
    ) in calls
    assert ("rust:src/main.rs::main", "rust:src/util.rs::helper", True, False) in calls


def test_generic_and_receiver_dispatch_is_never_upgraded_to_certain(graph) -> None:  # type: ignore[no-untyped-def]
    calls = [edge for edge in graph.edges if edge.kind == "call"]

    # `item.render()` on a `T: Render` parameter: which implementation runs is
    # decided at monomorphisation, not in the tree.
    generic = next(
        edge
        for edge in calls
        if edge.src == "rust:src/render.rs::render_all"
        and edge.dst == "rust:src/render.rs::Render.render"
    )
    assert generic.certain is False
    assert generic.lineno == 16

    # A method on a local value has no proven receiver type at all.
    receiver = next(
        edge
        for edge in calls
        if edge.src == "rust:src/main.rs::main" and edge.dst.startswith("unresolved:")
    )
    assert receiver.dst == "unresolved:rust:src/main.rs:render"
    assert receiver.certain is False

    # An associated function on a standard-library type stays external.
    external = next(
        edge
        for edge in calls
        if edge.src == "rust:src/render.rs::render_all" and edge.external
    )
    assert (external.dst, external.certain) == ("external:Vec::new", False)

    assert not any(edge.certain for edge in calls if edge.external)


def test_a_local_binding_never_inherits_a_module_function_certainty(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(
        "pub fn helper() -> u32 {\n"
        "    1\n"
        "}\n"
        "\n"
        "pub fn run(helper: fn() -> u32) -> u32 {\n"
        "    helper()\n"
        "}\n",
        encoding="utf-8",
    )

    graph = RustAdapter().parse(tmp_path)
    calls = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == "rust:src/lib.rs::run"
    ]

    assert len(calls) == 1
    assert calls[0].dst == "unresolved:rust:src/lib.rs::run:helper"
    assert calls[0].certain is False


def test_partial_files_stay_visible_without_claiming_broken_structures(graph) -> None:  # type: ignore[no-untyped-def]
    node_ids = {node.id for node in graph.nodes}
    broken = next(node for node in graph.nodes if node.id == "rust:src/broken.rs")

    assert graph.partial_files == ("src/broken.rs",)
    assert broken.partial is True
    assert broken.file in graph.file_hashes
    assert "rust:src/broken.rs::visible" in node_ids
    assert "rust:src/broken.rs::broken" not in node_ids


def test_entrypoint_ranking_and_explicit_selection_are_parser_bounded(graph) -> None:  # type: ignore[no-untyped-def]
    assert graph.entrypoint_candidates == (
        "rust:src/main.rs::main",
        "rust:src/lib.rs",
        "rust:src/lib.rs::describe",
        "rust:src/main.rs::main_reports_failures",
    )
    assert graph.selected_entrypoint == "rust:src/main.rs::main"

    selected = RustAdapter().parse(FIXTURE, entrypoint="rust:src/lib.rs")
    assert selected.selected_entrypoint == "rust:src/lib.rs"
    with pytest.raises(RustParseError, match="not parser-ranked"):
        RustAdapter().parse(FIXTURE, entrypoint="made-up")


def test_repeated_parses_are_byte_identical() -> None:
    assert RustAdapter().parse(FIXTURE).to_json() == RustAdapter().parse(FIXTURE).to_json()


def test_concepts_are_tree_sitter_proven_owned_and_language_tagged(graph) -> None:  # type: ignore[no-untyped-def]
    concepts_by_node: dict[str, set[tuple[str, int]]] = {}
    nodes = {node.id: node for node in graph.nodes}
    for annotation in graph.concept_annotations:
        concepts_by_node.setdefault(annotation.node_id, set()).add(
            (annotation.concept, annotation.lineno)
        )
        assert annotation.language == "rust"
        assert nodes[annotation.node_id].language == "rust"
        assert annotation.snippet

    assert concepts_by_node["rust:src/util.rs::helper"] == {
        ("borrowing", 43),
        ("borrowing", 47),
        ("pattern-matching", 45),
        ("question-mark-operator", 44),
        ("result-option", 43),
    }
    assert concepts_by_node["rust:src/render.rs::fetch"] == {
        ("async-await", 5),
        ("async-await", 6),
        ("borrowing", 5),
        ("lifetime", 5),
        ("result-option", 5),
        ("unsafe", 7),
    }
    assert concepts_by_node["rust:src/util.rs::Formatter#impl.set_prefix"] == {
        ("borrowing", 20),
        ("mutable-borrow", 20),
    }
    assert concepts_by_node["rust:src/render.rs::collect"] == {
        ("borrowing", 21),
        ("mutable-borrow", 21),
    }
    assert concepts_by_node["rust:src/render.rs::Render"] == {("trait", 1)}
    assert concepts_by_node["rust:src/util.rs::Formatter#Render"] == {("impl", 31)}
    assert concepts_by_node["rust:src/util.rs::Formatter#impl.decorate"] == {
        ("borrowing", 24),
        ("macro", 26),
    }
    assert concepts_by_node["rust:src/render.rs::touch"] == {("unsafe", 31)}
    # An unreadable file yields no concepts at all, for the module or its parts.
    assert "rust:src/broken.rs" not in concepts_by_node
    assert "rust:src/broken.rs::visible" not in concepts_by_node


def test_every_concept_points_at_a_real_line_of_its_owner(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    for annotation in graph.concept_annotations:
        owner = nodes[annotation.node_id]
        assert owner.lineno <= annotation.lineno <= annotation.end_lineno <= owner.end_lineno
        line = (FIXTURE / owner.file).read_text(encoding="utf-8").splitlines()[
            annotation.lineno - 1
        ]
        assert annotation.snippet == line.strip()


def test_concepts_method_matches_graph_annotations_for_one_owner(graph) -> None:  # type: ignore[no-untyped-def]
    node = next(node for node in graph.nodes if node.id == "rust:src/util.rs::helper")
    source = (FIXTURE / node.file).read_text(encoding="utf-8")

    direct = RustAdapter().concepts(node, source)
    serialized = [
        annotation
        for annotation in graph.concept_annotations
        if annotation.node_id == node.id
    ]

    assert direct == serialized


def test_a_single_rust_file_parses_without_a_project_around_it(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.rs"
    source_file.write_text("pub fn mapped() -> u32 {\n    3\n}\n", encoding="utf-8")

    graph = RustAdapter().parse(source_file)

    assert graph.partial_files == ()
    assert {node.id for node in graph.nodes} == {"rust:sample.rs", "rust:sample.rs::mapped"}


def test_an_unreadable_scope_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    with pytest.raises(RustParseError, match="no Rust files found"):
        RustAdapter().parse(tmp_path)
