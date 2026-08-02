"""Parser-grounded Java graph contracts."""

from pathlib import Path

import pytest

from codemble.adapters.java_tree_sitter import JavaAdapter, JavaParseError

FIXTURE = Path(__file__).parent / "fixtures" / "java_sample"

APP = "java:src/com/example/app/App.java"
BROKEN = "java:src/com/example/app/Broken.java"
CATALOG = "java:src/com/example/model/Catalog.java"
FORMATTER = "java:src/com/example/util/Formatter.java"
HELPER = "java:src/com/example/util/Helper.java"
SERVICE = "java:src/com/example/app/Service.java"
SHAPES = "java:src/com/example/model/Shapes.java"
TEST = "java:test/com/example/app/AppTest.java"


@pytest.fixture(scope="module")
def graph():  # type: ignore[no-untyped-def]
    return JavaAdapter().parse(FIXTURE)


def _edges(graph, kind: str) -> set[tuple[str, str, bool, bool]]:  # type: ignore[no-untyped-def]
    return {
        (edge.src, edge.dst, edge.certain, edge.external)
        for edge in graph.edges
        if edge.kind == kind
    }


def test_discovers_java_sources_and_skips_build_output() -> None:
    adapter = JavaAdapter()
    root, files = adapter.discover(FIXTURE)

    assert root == FIXTURE.resolve()
    assert adapter.file_extensions == {".java"}
    assert adapter.ignored_directories == {"build", "out", "target"}
    assert [file.relative_to(root).as_posix() for file in files] == [
        "src/com/example/app/App.java",
        "src/com/example/app/Broken.java",
        "src/com/example/app/Service.java",
        "src/com/example/model/Catalog.java",
        "src/com/example/model/Shapes.java",
        "src/com/example/util/Formatter.java",
        "src/com/example/util/Helper.java",
        "test/com/example/app/AppTest.java",
    ]


def test_nodes_are_parser_proven_language_tagged_and_spanned(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}

    assert nodes[APP].kind == "module"
    assert nodes[APP].language == "java"
    # The package declaration is what names a Java type, so the module carries
    # the qualified name rather than the bare filename.
    assert nodes[APP].name == "com.example.app.App"
    assert nodes[f"{APP}::App"].kind == "class"
    assert nodes[f"{APP}::App.start"].kind == "function"
    assert nodes[f"{APP}::App.start"].lineno == 24
    assert nodes[f"{APP}::App.start"].end_lineno == 31
    assert nodes[f"{APP}::App.start"].loc == 8
    assert nodes[f"{APP}::App.App"].kind == "function"
    assert nodes[f"{SHAPES}::Shape"].kind == "class"
    assert nodes[f"{SHAPES}::Circle"].kind == "class"
    assert nodes[f"{CATALOG}::Catalog$Status"].kind == "class"

    assert all(node.region.startswith("java:") for node in graph.nodes)
    assert all(node.file in graph.file_hashes for node in graph.nodes)
    assert all(node.lineno >= 1 and node.end_lineno >= node.lineno for node in graph.nodes)


def test_nested_types_are_identifiable_as_nested_in_their_node_id(graph) -> None:  # type: ignore[no-untyped-def]
    ids = {node.id for node in graph.nodes}

    # `$` separates a type from the type containing it and `.` separates a
    # member from its owner, so nesting is readable straight off the id.
    assert f"{APP}::App$Launcher" in ids
    assert f"{APP}::App$Launcher.launch" in ids
    assert f"{CATALOG}::Catalog$Index.size" in ids
    assert f"{APP}::App.start" in ids


def test_overloads_keep_separate_ids_without_colliding(graph) -> None:  # type: ignore[no-untyped-def]
    wraps = sorted(
        node.id for node in graph.nodes if node.name == "wrap" and node.kind == "function"
    )

    assert wraps == [f"{FORMATTER}::Formatter.wrap", f"{FORMATTER}::Formatter.wrap@17"]


def test_imports_resolve_by_package_and_never_upgrade_a_wildcard(graph) -> None:  # type: ignore[no-untyped-def]
    imports = _edges(graph, "import")

    # A single-type import names its target exactly.
    assert (APP, FORMATTER, True, False) in imports
    assert (APP, HELPER, True, False) in imports
    # `import com.example.model.*` proves the package but never one type.
    assert (APP, CATALOG, False, False) in imports
    assert (APP, SHAPES, False, False) in imports
    # A type outside the project stays an explicit external observation.
    assert (
        SERVICE,
        "external:org.springframework.boot.autoconfigure.SpringBootApplication",
        True,
        True,
    ) in imports
    assert (TEST, "external:org.junit.jupiter.api.Test", True, True) in imports


def test_a_wildcard_import_of_an_absent_package_stays_uncertain(tmp_path: Path) -> None:
    (tmp_path / "Solo.java").write_text(
        "package solo;\n\nimport com.absent.*;\n\nclass Solo {\n}\n",
        encoding="utf-8",
    )

    graph = JavaAdapter().parse(tmp_path)

    assert _edges(graph, "import") == {
        ("java:Solo.java", "external:com.absent.*", False, True)
    }


def test_calls_are_certain_only_where_the_tree_proves_the_receiver(graph) -> None:  # type: ignore[no-untyped-def]
    calls = _edges(graph, "call")

    # `this.` resolves inside the enclosing type.
    assert (f"{APP}::App.start", f"{APP}::App.tally", True, False) in calls
    # A static reference to an imported type resolves.
    assert (f"{APP}::App.start", f"{HELPER}::Helper.shout", True, False) in calls
    # A same-package type needs no import at all -- package, not directory.
    assert (f"{TEST}::AppTest.startsUp", f"{APP}::App.main", True, False) in calls
    # A field with a declared type resolves, but two overloads share the name,
    # so which one runs is not proven.
    assert (f"{APP}::App.start", f"{FORMATTER}::Formatter.wrap", False, False) in calls
    # An unknown receiver is kept and labelled, never dropped.
    assert (f"{APP}::App.start", "external:mystery.compute", False, True) in calls
    # `super.` targets a supertype the parser cannot identify.
    assert (
        f"{APP}::App.start",
        f"unresolved:{APP}:super.toString",
        False,
        False,
    ) in calls
    # A chained call's receiver is the result of an expression, not a type.
    assert (
        f"{CATALOG}::Catalog.names",
        "external:shapes.stream",
        False,
        True,
    ) in calls


def test_a_static_import_resolves_an_unqualified_call(graph) -> None:  # type: ignore[no-untyped-def]
    shout = [
        edge
        for edge in graph.edges
        if edge.kind == "call" and edge.src == f"{APP}::App.start" and edge.lineno == 28
    ]

    assert len(shout) == 1
    assert shout[0].dst == f"{HELPER}::Helper.shout"
    assert shout[0].certain is True


def test_a_local_binding_shadows_a_field_and_blocks_its_declared_type(
    tmp_path: Path,
) -> None:
    (tmp_path / "Formatter.java").write_text(
        "package demo;\n\npublic class Formatter {\n"
        "    public String wrap(String value) {\n        return value;\n    }\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "Shadow.java").write_text(
        "package demo;\n\npublic class Shadow {\n\n"
        "    private Formatter formatter;\n\n"
        "    void direct() {\n        formatter.wrap(\"a\");\n    }\n\n"
        "    void shadowed(Formatter formatter) {\n"
        "        formatter.wrap(\"b\");\n    }\n}\n",
        encoding="utf-8",
    )

    calls = _edges(JavaAdapter().parse(tmp_path), "call")

    # The field's declared type proves the target.
    assert (
        "java:Shadow.java::Shadow.direct",
        "java:Formatter.java::Formatter.wrap",
        True,
        False,
    ) in calls
    # The parameter shadows that field, so the same text proves nothing here.
    assert (
        "java:Shadow.java::Shadow.shadowed",
        "external:formatter.wrap",
        False,
        True,
    ) in calls


def test_a_call_in_a_field_initializer_is_kept_not_dropped(tmp_path: Path) -> None:
    (tmp_path / "Eager.java").write_text(
        "package demo;\n\nclass Eager {\n\n"
        "    private final String label = build();\n\n"
        "    static String build() {\n        return \"x\";\n    }\n}\n",
        encoding="utf-8",
    )

    calls = _edges(JavaAdapter().parse(tmp_path), "call")

    assert (
        "java:Eager.java::Eager",
        "java:Eager.java::Eager.build",
        True,
        False,
    ) in calls


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_a_static_wildcard_import_names_the_type_not_its_package(
    tmp_path: Path,
) -> None:
    # `import static a.b.C.*` has already stopped at the type -- the asterisk
    # only leaves which member open. Trimming a segment named the package `a.b`
    # instead, and here `a.b` is itself a project class, so the mistake landed
    # as a certain import edge to an unrelated module.
    root = _write(
        tmp_path,
        {
            "a/b.java": "package a;\npublic class b {\n}\n",
            "a/b2/C.java": "package a.b;\npublic class C {\n"
            "    public static void m() {}\n}\n",
            "z/User.java": "package z;\n\nimport static a.b.C.*;\n\nclass User {\n}\n",
        },
    )

    assert _edges(JavaAdapter().parse(root), "import") == {
        ("java:z/User.java", "java:a/b2/C.java", True, False)
    }


def test_an_abstract_declaration_is_never_the_proven_target(tmp_path: Path) -> None:
    # Deliberately no project type implements `Shape`: an implementer would
    # redeclare `area` and the override rule would carry this case on its own,
    # leaving the guard under test never exercised.
    root = _write(
        tmp_path,
        {
            "Shape.java": "public interface Shape {\n    double area();\n"
            "    default double scaled() { return 1.0; }\n}\n",
            "Board.java": "public class Board {\n    private Shape shape;\n"
            "    void draw() {\n        shape.area();\n        shape.scaled();\n"
            "    }\n}\n",
        },
    )

    calls = _edges(JavaAdapter().parse(root), "call")

    # The tree shows `area()` with no body at all, so that declaration is the
    # one target the call provably does not reach.
    assert ("java:Board.java::Board.draw", "java:Shape.java::Shape.area", False, False) in calls
    # `scaled()` has a body and nothing redeclares it, so it stays proven --
    # the downgrade above is evidence, not blanket caution.
    assert (
        "java:Board.java::Board.draw",
        "java:Shape.java::Shape.scaled",
        True,
        False,
    ) in calls


def test_an_overridden_method_is_not_a_proven_target(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "Animal.java": "public class Animal {\n"
            "    public String name() { return \"a\"; }\n"
            "    public void speak() {}\n"
            "    public static void register() {}\n}\n",
            "Dog.java": "public class Dog extends Animal {\n"
            "    public void speak() {}\n}\n",
            "Zoo.java": "public class Zoo {\n    private Animal animal;\n"
            "    void go() {\n        animal.name();\n        animal.speak();\n"
            "        Animal.register();\n    }\n}\n",
        },
    )

    calls = _edges(JavaAdapter().parse(root), "call")

    # Java dispatches on the runtime type, so a subtype redeclaring the name
    # means the tree cannot say which body runs.
    assert ("java:Zoo.java::Zoo.go", "java:Animal.java::Animal.speak", False, False) in calls
    # No subtype redeclares `name`, so the subclass proves nothing against it.
    assert ("java:Zoo.java::Zoo.go", "java:Animal.java::Animal.name", True, False) in calls
    # The receiver names the type itself: a static call is not dispatched, so
    # the presence of a subclass cannot intercept it.
    assert (
        "java:Zoo.java::Zoo.go",
        "java:Animal.java::Animal.register",
        True,
        False,
    ) in calls


def test_an_override_is_found_through_a_whole_supertype_chain(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "Base.java": "public interface Base {\n    default void run() {}\n}\n",
            "Mid.java": "public class Mid implements Base {\n}\n",
            "Leaf.java": "public class Leaf extends Mid {\n    public void run() {}\n}\n",
            "Site.java": "public class Site {\n    private Base b;\n"
            "    void go() { b.run(); }\n}\n",
        },
    )

    assert (
        "java:Site.java::Site.go",
        "java:Base.java::Base.run",
        False,
        False,
    ) in _edges(JavaAdapter().parse(root), "call")


def test_illegal_cyclic_inheritance_terminates(tmp_path: Path) -> None:
    # A compiler would reject this, but a half-written project reaches the
    # adapter and walking supertypes must not depend on the source compiling.
    root = _write(
        tmp_path,
        {
            "A.java": "public class A extends B {\n    void f() {}\n}\n",
            "B.java": "public class B extends A {\n    void f() {}\n}\n",
            "C.java": "public class C {\n    private A a;\n    void go() { a.f(); }\n}\n",
        },
    )

    assert ("java:C.java::C.go", "java:A.java::A.f", False, False) in _edges(
        JavaAdapter().parse(root), "call"
    )


def test_a_nested_type_is_invisible_to_a_sibling_top_level_type(
    tmp_path: Path,
) -> None:
    root = _write(
        tmp_path,
        {
            "other/Helper.java": "package other;\npublic class Helper {\n"
            "    public static void x() {}\n}\n",
            "Pair.java": "import other.Helper;\n\n"
            "class Outer {\n    static class Helper {\n        static void x() {}\n    }\n"
            "    void inside() { Helper.x(); }\n}\n\n"
            "class Sibling {\n    void f() { Helper.x(); }\n}\n",
        },
    )

    calls = _edges(JavaAdapter().parse(root), "call")

    # `Outer.Helper` is not in scope for `Sibling`, so Java reads the import.
    assert (
        "java:Pair.java::Sibling.f",
        "java:other/Helper.java::Helper.x",
        True,
        False,
    ) in calls
    # From inside its own owner the nested type still wins, as Java says.
    assert (
        "java:Pair.java::Outer.inside",
        "java:Pair.java::Outer$Helper.x",
        True,
        False,
    ) in calls


def test_an_anonymous_class_body_does_not_borrow_the_enclosing_type(
    tmp_path: Path,
) -> None:
    # `wrap` here is inherited into the anonymous subclass of `Formatter`, so
    # Java runs `Formatter.wrap`, not the enclosing `Host.wrap`. The parser
    # cannot see an external supertype's members either way, so the honest
    # answer is that the target is unproven.
    root = _write(
        tmp_path,
        {
            "Formatter.java": "public class Formatter {\n"
            "    public void wrap() {}\n}\n",
            "Host.java": "public class Host {\n    void wrap() {}\n"
            "    void go() {\n"
            "        Formatter f = new Formatter() {\n"
            "            public void inner() { wrap(); }\n        };\n    }\n}\n",
        },
    )

    calls = _edges(JavaAdapter().parse(root), "call")

    assert (
        "java:Host.java::Host.go.inner",
        "unresolved:java:Host.java:wrap",
        False,
        False,
    ) in calls
    assert not any(
        edge[0] == "java:Host.java::Host.go.inner" and edge[2] for edge in calls
    )


def test_a_type_parameter_is_not_a_project_type(tmp_path: Path) -> None:
    # `T` inside `class Box<T>` is a type variable. Reading it as the project
    # class that happens to share the name invents a call across the project.
    root = _write(
        tmp_path,
        {
            "T.java": "public class T {\n    public void render() {}\n}\n",
            "Box.java": "public class Box<T> {\n    private T item;\n"
            "    void go() { item.render(); }\n}\n",
        },
    )

    calls = _edges(JavaAdapter().parse(root), "call")

    assert ("java:Box.java::Box.go", "external:item.render", False, True) in calls
    assert not any(edge[1] == "java:T.java::T.render" for edge in calls)


def test_partial_files_stay_visible_without_claiming_broken_structures(graph) -> None:  # type: ignore[no-untyped-def]
    ids = {node.id for node in graph.nodes}
    broken = next(node for node in graph.nodes if node.id == BROKEN)

    assert graph.partial_files == ("src/com/example/app/Broken.java",)
    assert broken.partial is True
    assert broken.file in graph.file_hashes
    # The class header and its sound sibling parsed, so both are charted.
    assert f"{BROKEN}::Broken" in ids
    assert f"{BROKEN}::Broken.readable" in ids
    # The member whose own parameter list never parsed is never claimed.
    assert f"{BROKEN}::Broken.unreadable" not in ids


def test_unreadable_bytes_degrade_to_a_partial_parse_and_never_raise(
    tmp_path: Path,
) -> None:
    # A galaxy must still draw when one file is empty, unreadable, or not even
    # UTF-8. Byte offsets drive every span, so a lossy decode has to leave the
    # line numbering of the sound files alone rather than crash the run.
    (tmp_path / "Empty.java").write_bytes(b"")
    (tmp_path / "Comments.java").write_bytes(b"// only a comment\n")
    (tmp_path / "Severe.java").write_bytes(b"class {{{ ]]] <<<\n\x00\x01 void )( {\n")
    (tmp_path / "Latin.java").write_bytes(
        b"package demo;\n// caf\xe9 na\xefve \xff\xfe\nclass Latin {\n"
        b"    void go() { helper(); }\n    void helper() {}\n}\n"
    )

    graph = JavaAdapter().parse(tmp_path)
    ids = {node.id for node in graph.nodes}

    assert graph.partial_files == ("Severe.java",)
    assert "java:Empty.java" in ids
    assert "java:Comments.java" in ids
    # The undecodable bytes sit above `go`, so its span proves the line
    # numbering survived the replacement decode.
    latin = next(node for node in graph.nodes if node.id == "java:Latin.java::Latin.go")
    assert (latin.lineno, latin.end_lineno) == (4, 4)
    assert (
        "java:Latin.java::Latin.go",
        "java:Latin.java::Latin.helper",
        True,
        False,
    ) in _edges(graph, "call")


def test_entrypoint_ranking_puts_main_first_and_tests_last(graph) -> None:  # type: ignore[no-untyped-def]
    assert graph.entrypoint_candidates == (
        APP,
        f"{APP}::App.main",
        f"{SERVICE}::Service",
        SERVICE,
        f"{TEST}::AppTest",
    )
    assert graph.selected_entrypoint == APP


def test_an_explicit_entrypoint_must_still_be_parser_ranked() -> None:
    selected = JavaAdapter().parse(FIXTURE, entrypoint=f"{APP}::App.main")

    assert selected.selected_entrypoint == f"{APP}::App.main"
    with pytest.raises(JavaParseError, match="not parser-ranked"):
        JavaAdapter().parse(FIXTURE, entrypoint="made-up")


def test_main_ranking_requires_the_real_jvm_signature(tmp_path: Path) -> None:
    (tmp_path / "Varargs.java").write_text(
        "class Varargs {\n"
        "    public static void main(String... args) {\n    }\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "Decoy.java").write_text(
        "class Decoy {\n"
        "    public void main(String[] args) {\n    }\n\n"
        "    public static void main(int count) {\n    }\n}\n",
        encoding="utf-8",
    )

    graph = JavaAdapter().parse(tmp_path)

    # `String...` is the same entrypoint the JVM accepts; the decoys are not.
    assert graph.selected_entrypoint == "java:Varargs.java"
    assert not any("Decoy" in candidate for candidate in graph.entrypoint_candidates)


def test_a_parameter_annotation_never_makes_a_class_look_like_a_test(
    tmp_path: Path,
) -> None:
    # The method carries real modifiers of its own, so the annotation on its
    # parameter is genuinely reachable from the declaration -- reading the
    # whole subtree instead of just the method's `modifiers` would find it.
    (tmp_path / "NotATest.java").write_text(
        "class NotATest {\n"
        "    public void helper(@Test int value) {\n    }\n}\n",
        encoding="utf-8",
    )

    graph = JavaAdapter().parse(tmp_path)

    assert graph.entrypoint_candidates == ()


def test_repeated_parses_are_byte_identical() -> None:
    first = JavaAdapter().parse(FIXTURE).to_json()
    second = JavaAdapter().parse(FIXTURE).to_json()

    assert first == second


def test_concepts_are_tree_sitter_proven_owned_and_language_tagged(graph) -> None:  # type: ignore[no-untyped-def]
    nodes = {node.id: node for node in graph.nodes}
    by_node: dict[str, set[str]] = {}
    for annotation in graph.concept_annotations:
        by_node.setdefault(annotation.node_id, set()).add(annotation.concept)
        assert annotation.language == "java"
        assert annotation.language == nodes[annotation.node_id].language
        assert annotation.snippet
        assert annotation.lineno >= 1

    assert by_node[f"{SHAPES}::Shape"] == {"sealed-type"}
    assert by_node[f"{SHAPES}::Shape.describe"] == {"default-method"}
    assert by_node[f"{SHAPES}::Circle"] == {"record"}
    assert by_node[f"{CATALOG}::Catalog.firstLine"] == {"try-with-resources"}
    assert by_node[f"{CATALOG}::Catalog.names"] == {
        "annotation",
        "generic",
        "lambda",
        "stream",
    }
    assert by_node[f"{FORMATTER}::Formatter.labels"] == {"generic", "lambda", "stream"}
    assert by_node[f"{SERVICE}::Service"] == {"annotation"}
    # Nothing is claimed for the file the parser could not fully read.
    assert BROKEN not in by_node
    assert f"{BROKEN}::Broken.readable" not in by_node


def test_a_stream_concept_needs_a_proven_chain_not_a_method_name(
    tmp_path: Path,
) -> None:
    (tmp_path / "Streams.java").write_text(
        "import java.util.List;\n\nclass Streams {\n"
        "    void chained(List<String> xs) {\n"
        "        xs.stream().count();\n    }\n\n"
        "    void bare(List<String> xs) {\n"
        "        xs.stream();\n    }\n}\n",
        encoding="utf-8",
    )

    graph = JavaAdapter().parse(tmp_path)
    streams = {
        annotation.node_id
        for annotation in graph.concept_annotations
        if annotation.concept == "stream"
    }

    assert streams == {"java:Streams.java::Streams.chained"}


def test_concepts_method_matches_graph_annotations_for_one_owner(graph) -> None:  # type: ignore[no-untyped-def]
    node = next(node for node in graph.nodes if node.id == f"{CATALOG}::Catalog.names")
    source = (FIXTURE / node.file).read_text(encoding="utf-8")

    direct = JavaAdapter().concepts(node, source)
    serialized = [
        annotation
        for annotation in graph.concept_annotations
        if annotation.node_id == node.id
    ]

    assert direct == serialized
    assert direct


def test_a_missing_scope_is_refused_rather_than_silently_empty(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("no java here\n", encoding="utf-8")

    with pytest.raises(JavaParseError, match="no Java files found"):
        JavaAdapter().parse(tmp_path)
