"""Tree-sitter Java implementation of the language seam."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_java
from tree_sitter import Language, Parser, Tree
from tree_sitter import Node as SyntaxNode

from codemble.adapters.base import (
    AdapterParseError,
    ConceptAnnotation,
    Edge,
    Graph,
    Node,
)
from codemble.adapters.discovery import SourceDiscoveryError, discover_source_files
from codemble.adapters.parse_progress import note_file_parsed
from codemble.graph.finalize import GraphFinalizationError, finalize_graph

_JAVA_EXTENSIONS = frozenset({".java"})
# Build outputs, not sources. Every mainstream Java toolchain writes compiled
# and generated `.java` here -- Maven into `target`, Gradle into `build`, plain
# `javac -d` into `out` -- and charting generated code teaches a learner about
# their build tool rather than about what they wrote.
_GENERATED_DIRECTORIES = frozenset({"build", "out", "target"})

# The declarations this adapter maps to graph nodes. Types become ``class``
# nodes and callables become ``function`` nodes, because those are the only two
# structural kinds the seam offers -- an interface and a record really are
# types, whatever keyword introduces them.
_TYPE_DECLARATIONS = frozenset(
    {
        "class_declaration",
        "enum_declaration",
        "interface_declaration",
        "record_declaration",
    }
)
_CALLABLE_DECLARATIONS = frozenset(
    {
        "constructor_declaration",
        "method_declaration",
    }
)

# A pipeline is proven when one of these opens a chain, so the annotation
# describes syntax the parser actually saw rather than a naming convention.
_STREAM_SOURCES = frozenset({"parallelStream", "stream"})

_JAVA_LANGUAGE = Language(tree_sitter_java.language())


class JavaParseError(AdapterParseError):
    """Java source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
    # The declared package, or "" for the default package. Java resolves an
    # import against this and nothing else, so it is parser evidence rather
    # than a naming convention read off the directory layout.
    package: str
    raw: bytes
    source: str
    digest: str
    tree: Tree


@dataclass(frozen=True, slots=True)
class _Definition:
    node_id: str
    syntax: SyntaxNode
    parent_id: str
    module_id: str
    # The type that lexically owns this definition. ``this`` and an unqualified
    # invocation both resolve against exactly this type and no other.
    enclosing_type_id: str | None
    is_type: bool


@dataclass(frozen=True, slots=True)
class _TypeReference:
    """One import statement's parser-proven target."""

    # The type's fully qualified name, or the package for a type wildcard where
    # no single type was named.
    qualified: str
    simple_name: str | None
    # The member a static import names, when it named one.
    member: str | None
    # False only where the statement cannot name one type: `import a.b.*`.
    certain: bool
    lineno: int


@dataclass(frozen=True, slots=True)
class _SyntaxEvidenceIndex:
    """Reusable ownership and lookup evidence derived from one syntax parse."""

    parsed_files: tuple[_ParsedFile, ...]
    definitions: tuple[_Definition, ...]
    nodes: tuple[Node, ...]
    parsed_by_module: dict[str, _ParsedFile]
    definitions_by_module: dict[str, tuple[_Definition, ...]]
    node_by_id: dict[str, Node]
    children_by_parent: dict[str, tuple[Node, ...]]
    nested_ranges_by_owner: dict[str, frozenset[tuple[int, int]]]
    local_bindings_by_owner: dict[str, frozenset[str]]
    # A type's node id keyed by its fully qualified name, and again by the file
    # that declares it -- a same-file nested type is reachable by simple name
    # with no import at all.
    type_by_qualified: dict[str, str]
    type_by_module_name: dict[tuple[str, str], str]
    modules_by_package: dict[str, tuple[str, ...]]
    # Declared field types per owning type, so a call on a field can be proven
    # without inferring anything from the assigned value.
    field_types_by_type: dict[str, dict[str, str]]

    @classmethod
    def build(
        cls,
        parsed_files: tuple[_ParsedFile, ...],
        definitions: tuple[_Definition, ...],
        nodes: tuple[Node, ...],
    ) -> _SyntaxEvidenceIndex:
        parsed_by_module = {parsed.module_id: parsed for parsed in parsed_files}
        definitions_by_id = {
            definition.node_id: definition for definition in definitions
        }
        definitions_by_module_lists: dict[str, list[_Definition]] = defaultdict(list)
        nested_ranges: dict[str, set[tuple[int, int]]] = defaultdict(set)
        for definition in definitions:
            definitions_by_module_lists[definition.module_id].append(definition)
            syntax_range = (definition.syntax.start_byte, definition.syntax.end_byte)
            nested_ranges[definition.module_id].add(syntax_range)
            ancestor = definition.parent_id
            while ancestor in definitions_by_id:
                nested_ranges[ancestor].add(syntax_range)
                ancestor = definitions_by_id[ancestor].parent_id

        node_by_id = {node.id: node for node in nodes}
        children_by_parent = cls._children_by_parent(definitions, node_by_id)
        frozen_ranges = {
            owner: frozenset(ranges) for owner, ranges in nested_ranges.items()
        }
        local_bindings_by_owner = {
            definition.node_id: frozenset(
                _local_binding_names(
                    definition.syntax,
                    parsed_by_module[definition.module_id].raw,
                    frozen_ranges.get(definition.node_id, frozenset()),
                )
            )
            for definition in definitions
        }

        type_by_qualified: dict[str, str] = {}
        type_by_module_name: dict[tuple[str, str], str] = {}
        modules_by_package: dict[str, list[str]] = defaultdict(list)
        for parsed in parsed_files:
            modules_by_package[parsed.package].append(parsed.module_id)
        for definition in definitions:
            if not definition.is_type:
                continue
            node = node_by_id[definition.node_id]
            parsed = parsed_by_module[definition.module_id]
            type_by_module_name.setdefault((definition.module_id, node.name), node.id)
            # Only a top-level type carries a plain qualified name; a nested one
            # is reached through its owner, and inventing `pkg.Inner` for it
            # would resolve imports that Java itself would reject.
            if definition.parent_id == definition.module_id:
                qualified = f"{parsed.package}.{node.name}" if parsed.package else node.name
                type_by_qualified.setdefault(qualified, node.id)

        return cls(
            parsed_files=parsed_files,
            definitions=definitions,
            nodes=nodes,
            parsed_by_module=parsed_by_module,
            definitions_by_module={
                module_id: tuple(module_definitions)
                for module_id, module_definitions in definitions_by_module_lists.items()
            },
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            nested_ranges_by_owner=frozen_ranges,
            local_bindings_by_owner=local_bindings_by_owner,
            type_by_qualified=type_by_qualified,
            type_by_module_name=type_by_module_name,
            modules_by_package={
                package: tuple(sorted(module_ids))
                for package, module_ids in modules_by_package.items()
            },
            field_types_by_type=_field_types(definitions, node_by_id, parsed_by_module),
        )

    def with_nodes(self, nodes: tuple[Node, ...]) -> _SyntaxEvidenceIndex:
        """Refresh node metadata without rebuilding syntax ownership evidence."""

        node_by_id = {node.id: node for node in nodes}
        return replace(
            self,
            nodes=nodes,
            node_by_id=node_by_id,
            children_by_parent=self._children_by_parent(self.definitions, node_by_id),
        )

    @staticmethod
    def _children_by_parent(
        definitions: tuple[_Definition, ...],
        node_by_id: dict[str, Node],
    ) -> dict[str, tuple[Node, ...]]:
        children: dict[str, list[Node]] = defaultdict(list)
        for definition in definitions:
            children[definition.parent_id].append(node_by_id[definition.node_id])
        return {parent: tuple(nodes) for parent, nodes in children.items()}

    def members_named(self, type_id: str | None, name: str) -> list[Node]:
        """Return the members of ``type_id`` the parser saw carrying ``name``."""

        if type_id is None:
            return []
        return sorted(
            (
                node
                for node in self.children_by_parent.get(type_id, ())
                if node.name == name and node.kind == "function"
            ),
            key=lambda node: node.id,
        )


class JavaAdapter:
    """Map Java sources into one deterministic, parser-proven graph."""

    language = "java"
    file_extensions = _JAVA_EXTENSIONS
    ignored_directories = _GENERATED_DIRECTORIES

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact Java source scope accepted by this adapter."""

        normalized = path.expanduser().resolve()
        try:
            discovery = discover_source_files(
                normalized,
                self.file_extensions,
                ignored_directories=self.ignored_directories,
            )
        except SourceDiscoveryError as error:
            raise JavaParseError(str(error)) from error
        if not discovery.files:
            if normalized.is_file():
                raise JavaParseError(f"expected a Java file or directory: {normalized}")
            raise JavaParseError(f"no Java files found under: {normalized}")
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse ``path`` using the official tree-sitter Java grammar wheel."""

        project_root, files = self.discover(path)
        return self.parse_files(project_root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        """Parse Java files already owned by this adapter."""

        parsed_files = tuple(_parse_file(file, project_root) for file in files)

        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            nodes.append(_module_node(parsed))
            file_nodes, file_definitions = _collect_definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        index = _SyntaxEvidenceIndex.build(
            parsed_files,
            tuple(definitions),
            tuple(nodes),
        )
        entrypoint_ranks = _entrypoint_ranks(index)
        index = index.with_nodes(
            tuple(
                replace(node, entrypoint_rank=entrypoint_ranks.get(node.id))
                for node in index.nodes
            )
        )

        import_edges: set[Edge] = set()
        references_by_module: dict[str, tuple[_TypeReference, ...]] = {}
        for parsed in parsed_files:
            references = _type_references(parsed)
            references_by_module[parsed.module_id] = references
            import_edges.update(_import_edges(parsed, references, index))

        call_edges = _call_edges(index, references_by_module)
        draft = Graph(
            nodes=index.nodes,
            edges=(*import_edges, *call_edges),
            entrypoint_candidates=(),
            project_root=str(project_root),
            file_hashes={
                parsed.relative_path: parsed.digest for parsed in parsed_files
            },
            concept_annotations=_concept_annotations(index),
            partial_files=tuple(
                parsed.relative_path
                for parsed in parsed_files
                if parsed.tree.root_node.has_error
            ),
        )
        try:
            return finalize_graph(draft, entrypoint=entrypoint)
        except GraphFinalizationError as error:
            raise JavaParseError(str(error)) from error

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only tree-sitter-proven concepts owned by ``node``."""

        if node.partial or node.language != self.language:
            return []
        raw = source.encode("utf-8")
        tree = Parser(_JAVA_LANGUAGE).parse(raw)
        parsed = _ParsedFile(
            path=Path(node.file),
            project_root=Path("."),
            relative_path=node.file,
            module_id=node.region,
            package=_package_name(tree.root_node, raw),
            raw=raw,
            source=source,
            digest=hashlib.sha256(raw).hexdigest(),
            tree=tree,
        )
        module_node = _module_node(parsed)
        file_nodes, definitions = _collect_definitions(parsed)
        index = _SyntaxEvidenceIndex.build(
            (parsed,),
            tuple(definitions),
            (module_node, *file_nodes),
        )
        if node.id not in index.node_by_id:
            return []
        return [
            annotation
            for annotation in _concept_annotations(index)
            if annotation.node_id == node.id
        ]


def _parse_file(path: Path, project_root: Path) -> _ParsedFile:
    raw = path.read_bytes()
    relative = path.relative_to(project_root).as_posix()
    tree = Parser(_JAVA_LANGUAGE).parse(raw)
    parsed = _ParsedFile(
        path=path,
        project_root=project_root,
        relative_path=relative,
        module_id=f"java:{relative}",
        package=_package_name(tree.root_node, raw),
        raw=raw,
        source=raw.decode("utf-8", errors="replace"),
        digest=hashlib.sha256(raw).hexdigest(),
        tree=tree,
    )
    note_file_parsed()
    return parsed


def _package_name(root: SyntaxNode, raw: bytes) -> str:
    for child in root.named_children:
        if child.type != "package_declaration" or child.has_error:
            continue
        for name in child.named_children:
            if name.type in {"identifier", "scoped_identifier"}:
                return _node_text(name, raw)
    return ""


def _module_node(parsed: _ParsedFile) -> Node:
    line_count = max(1, len(parsed.source.splitlines()))
    # Java identity is the package-qualified name, not the bare filename, and a
    # project that splits `Formatter` across two packages is ordinary rather
    # than exotic -- so the plate has to carry the package to stay unambiguous.
    stem = Path(parsed.relative_path).stem
    name = f"{parsed.package}.{stem}" if parsed.package else stem
    return Node(
        id=parsed.module_id,
        kind="module",
        name=name,
        language="java",
        file=parsed.relative_path,
        lineno=1,
        end_lineno=line_count,
        loc=line_count,
        region=parsed.module_id,
        partial=parsed.tree.root_node.has_error,
    )


def _collect_definitions(
    parsed: _ParsedFile,
) -> tuple[list[Node], list[_Definition]]:
    nodes: list[Node] = []
    definitions: list[_Definition] = []
    used_ids: set[str] = {parsed.module_id}

    def add_definition(
        syntax: SyntaxNode,
        name: str,
        kind: str,
        suffix: str,
        parent_id: str,
        enclosing_type_id: str | None,
        *,
        is_type: bool,
    ) -> str:
        base_id = f"{parsed.module_id}::{suffix}"
        node_id = _unique_node_id(base_id, syntax, used_ids)
        used_ids.add(node_id)
        lineno, end_lineno = _line_span(syntax)
        nodes.append(
            Node(
                id=node_id,
                kind=kind,  # type: ignore[arg-type]
                name=name,
                language="java",
                file=parsed.relative_path,
                lineno=lineno,
                end_lineno=end_lineno,
                loc=end_lineno - lineno + 1,
                region=parsed.module_id,
            )
        )
        definitions.append(
            _Definition(
                node_id=node_id,
                syntax=syntax,
                parent_id=parent_id,
                module_id=parsed.module_id,
                enclosing_type_id=enclosing_type_id,
                is_type=is_type,
            )
        )
        return node_id

    def visit(
        container: SyntaxNode,
        qualname: str,
        parent_id: str,
        enclosing_type_id: str | None,
    ) -> None:
        for child in container.named_children:
            if child.type == "ERROR" or child.is_missing:
                continue
            if child.type in _TYPE_DECLARATIONS or child.type in _CALLABLE_DECLARATIONS:
                name = _field_text(child, "name", parsed.raw)
                # A declaration is claimed only when its own header parsed --
                # its name, parameters and modifiers. An error confined to the
                # body is the ordinary case of one broken member among sound
                # ones, and dropping the whole type for it would hide far more
                # structure than the parser actually failed to read.
                if name is None or not _header_parsed(child):
                    continue
                is_type = child.type in _TYPE_DECLARATIONS
                # `$` for containment inside a type and `.` for a member is the
                # JVM's own binary-name spelling, so a nested type announces
                # itself in the id without a second field to carry the fact.
                separator = "$" if is_type else "."
                suffix = f"{qualname}{separator}{name}" if qualname else name
                node_id = add_definition(
                    child,
                    name,
                    "class" if is_type else "function",
                    suffix,
                    parent_id,
                    enclosing_type_id,
                    is_type=is_type,
                )
                visit(
                    child,
                    suffix,
                    node_id,
                    node_id if is_type else enclosing_type_id,
                )
                continue
            visit(child, qualname, parent_id, enclosing_type_id)

    visit(parsed.tree.root_node, "", parsed.module_id, None)
    return nodes, definitions


def _header_parsed(syntax: SyntaxNode) -> bool:
    """True when everything but this declaration's body parsed cleanly.

    A missing bracket in one method leaves its own ``formal_parameters``
    erroring while its enclosing class reads perfectly, so asking the question
    per declaration -- and only of the header -- keeps the sound members of a
    partly-broken file without ever claiming the broken one.
    """

    body = syntax.child_by_field_name("body")
    return not any(
        child.has_error or child.is_missing
        for child in syntax.children
        if body is None or child.id != body.id
    )


def _field_types(
    definitions: tuple[_Definition, ...],
    node_by_id: dict[str, Node],
    parsed_by_module: dict[str, _ParsedFile],
) -> dict[str, dict[str, str]]:
    """Map each type's fields to their *declared* type names.

    Only the declaration is read. Inferring a field's type from whatever it was
    assigned would be a guess the tree does not support, and a wrong call edge
    is exactly the error a learner cannot detect.
    """

    field_types: dict[str, dict[str, str]] = {}
    for definition in definitions:
        if not definition.is_type:
            continue
        raw = parsed_by_module[definition.module_id].raw
        body = definition.syntax.child_by_field_name("body")
        if body is None:
            continue
        declared: dict[str, str] = {}
        for member in body.named_children:
            if member.type != "field_declaration" or member.has_error:
                continue
            type_name = _declared_type_name(member.child_by_field_name("type"), raw)
            if type_name is None:
                continue
            for declarator in member.named_children:
                if declarator.type != "variable_declarator":
                    continue
                field_name = _field_text(declarator, "name", raw)
                if field_name is not None:
                    declared.setdefault(field_name, type_name)
        if declared:
            field_types[node_by_id[definition.node_id].id] = declared
    return field_types


def _declared_type_name(syntax: SyntaxNode | None, raw: bytes) -> str | None:
    """Return the simple type name a declaration names, or ``None``.

    An array or a primitive is deliberately unnamed: a call on one reaches
    ``Object`` or the language itself, never a project type.
    """

    if syntax is None or syntax.has_error:
        return None
    if syntax.type == "type_identifier":
        return _node_text(syntax, raw)
    if syntax.type == "generic_type":
        return _declared_type_name(syntax.named_child(0), raw)
    if syntax.type == "scoped_type_identifier":
        return _node_text(syntax, raw).rsplit(".", 1)[-1]
    return None


def _unique_node_id(base_id: str, syntax: SyntaxNode, used_ids: set[str]) -> str:
    if base_id not in used_ids:
        return base_id
    lineno, _ = _line_span(syntax)
    candidate = f"{base_id}@{lineno}"
    counter = 2
    while candidate in used_ids:
        candidate = f"{base_id}@{lineno}-{counter}"
        counter += 1
    return candidate


def _line_span(syntax: SyntaxNode) -> tuple[int, int]:
    lineno = syntax.start_point.row + 1
    end_lineno = syntax.end_point.row + (1 if syntax.end_point.column else 0)
    return lineno, max(lineno, end_lineno)


def _field_text(syntax: SyntaxNode, field: str, raw: bytes) -> str | None:
    child = syntax.child_by_field_name(field)
    if child is None or child.has_error or child.type not in {
        "identifier",
        "type_identifier",
    }:
        return None
    return _node_text(child, raw)


def _node_text(syntax: SyntaxNode, raw: bytes) -> str:
    return raw[syntax.start_byte : syntax.end_byte].decode("utf-8", errors="replace")


def _walk(syntax: SyntaxNode) -> Iterable[SyntaxNode]:
    for child in syntax.named_children:
        yield child
        yield from _walk(child)


def _walk_owned(
    syntax: SyntaxNode,
    nested_definition_ranges: AbstractSet[tuple[int, int]],
) -> Iterable[SyntaxNode]:
    for child in syntax.named_children:
        if (child.start_byte, child.end_byte) in nested_definition_ranges:
            continue
        yield child
        yield from _walk_owned(child, nested_definition_ranges)


def _modifier_keywords(syntax: SyntaxNode) -> frozenset[str]:
    """Return the bare keywords of a declaration's ``modifiers``.

    Tree-sitter spells each keyword as an anonymous node whose type is the
    keyword itself, so this reads the parse tree rather than the source text.
    """

    modifiers = next(
        (child for child in syntax.named_children if child.type == "modifiers"),
        None,
    )
    if modifiers is None:
        return frozenset()
    return frozenset(child.type for child in modifiers.children if not child.is_named)


def _annotation_names(syntax: SyntaxNode, raw: bytes) -> frozenset[str]:
    """Return the simple names of annotations written on this declaration.

    Only the declaration's own ``modifiers`` are read: an annotation on a
    parameter belongs to that parameter, and counting it would let `void
    f(@Test int a)` masquerade as a test method.
    """

    modifiers = next(
        (child for child in syntax.named_children if child.type == "modifiers"),
        None,
    )
    if modifiers is None:
        return frozenset()
    names: set[str] = set()
    for child in modifiers.named_children:
        if child.type not in {"annotation", "marker_annotation"}:
            continue
        name = child.child_by_field_name("name")
        if name is not None:
            names.add(_node_text(name, raw).rsplit(".", 1)[-1])
    return frozenset(names)


def _concept_annotations(
    index: _SyntaxEvidenceIndex,
) -> tuple[ConceptAnnotation, ...]:
    annotations: set[ConceptAnnotation] = set()
    for parsed in index.parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        annotations.update(
            _concepts_for_owner(
                index.node_by_id[parsed.module_id],
                parsed.tree.root_node,
                parsed,
                index.nested_ranges_by_owner.get(parsed.module_id, frozenset()),
                include_owner=False,
            )
        )
    for definition in index.definitions:
        annotations.update(
            _concepts_for_owner(
                index.node_by_id[definition.node_id],
                definition.syntax,
                index.parsed_by_module[definition.module_id],
                index.nested_ranges_by_owner.get(definition.node_id, frozenset()),
                include_owner=True,
            )
        )
    return tuple(
        sorted(
            annotations,
            key=lambda item: (
                item.language,
                item.node_id,
                item.lineno,
                item.concept,
                item.end_lineno,
            ),
        )
    )


def _concepts_for_owner(
    owner: Node,
    syntax: SyntaxNode,
    parsed: _ParsedFile,
    nested_definition_ranges: AbstractSet[tuple[int, int]],
    *,
    include_owner: bool,
) -> set[ConceptAnnotation]:
    walked = _walk_owned(syntax, nested_definition_ranges)
    candidates: Iterable[SyntaxNode] = (
        (syntax, *walked) if include_owner else walked
    )
    annotations: set[ConceptAnnotation] = set()
    source_lines = parsed.source.splitlines()
    for candidate in candidates:
        if candidate.has_error:
            continue
        for concept in _concepts_for_syntax(candidate):
            lineno, end_lineno = _line_span(candidate)
            snippet = (
                source_lines[lineno - 1].strip()
                if 0 < lineno <= len(source_lines)
                else ""
            )
            annotations.add(
                ConceptAnnotation(
                    node_id=owner.id,
                    language="java",
                    concept=concept,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    snippet=snippet[:240],
                )
            )
    return annotations


def _concepts_for_syntax(syntax: SyntaxNode) -> tuple[str, ...]:
    concepts: list[str] = []
    if syntax.type in {"generic_type", "type_arguments", "type_parameters"}:
        concepts.append("generic")
    if syntax.type == "lambda_expression":
        concepts.append("lambda")
    if syntax.type in {"annotation", "marker_annotation"}:
        concepts.append("annotation")
    if syntax.type == "method_declaration" and "default" in _modifier_keywords(syntax):
        # `default` is legal only on an interface method, so the keyword alone
        # proves the construct without walking back up to the interface body.
        concepts.append("default-method")
    if syntax.type == "try_with_resources_statement":
        concepts.append("try-with-resources")
    if syntax.type == "record_declaration":
        concepts.append("record")
    if syntax.type in {"class_declaration", "interface_declaration"} and (
        "sealed" in _modifier_keywords(syntax)
        or any(child.type == "permits" for child in syntax.named_children)
    ):
        concepts.append("sealed-type")
    if _opens_stream_chain(syntax):
        concepts.append("stream")
    return tuple(concepts)


def _opens_stream_chain(syntax: SyntaxNode) -> bool:
    """True where the tree shows a stream call being chained from.

    A bare `stream()` proves nothing on its own -- any type may define such a
    method. What proves a pipeline is the chain: an invocation whose receiver
    IS that call.
    """

    if syntax.type != "method_invocation":
        return False
    receiver = syntax.child_by_field_name("object")
    if receiver is None or receiver.type != "method_invocation":
        return False
    receiver_name = receiver.child_by_field_name("name")
    return (
        receiver_name is not None
        and receiver_name.type == "identifier"
        and receiver_name.text is not None
        and receiver_name.text.decode("utf-8", errors="replace") in _STREAM_SOURCES
    )


def _type_references(parsed: _ParsedFile) -> tuple[_TypeReference, ...]:
    """Read every import statement as parser-proven target evidence."""

    references: list[_TypeReference] = []
    for child in parsed.tree.root_node.named_children:
        if child.type != "import_declaration" or child.has_error:
            continue
        name = next(
            (
                item
                for item in child.named_children
                if item.type in {"identifier", "scoped_identifier"}
            ),
            None,
        )
        if name is None:
            continue
        dotted = _node_text(name, parsed.raw)
        lineno = child.start_point.row + 1
        wildcard = any(item.type == "asterisk" for item in child.named_children)
        static = any(
            token.type == "static" for token in child.children if not token.is_named
        )
        if static:
            # `import static a.b.C.m` names the type in the second-to-last
            # segment; the wildcard form still names the type exactly and only
            # leaves the member open, so the type stays proven.
            type_qualified, _, member = dotted.rpartition(".")
            if not type_qualified:
                continue
            references.append(
                _TypeReference(
                    qualified=type_qualified,
                    simple_name=type_qualified.rsplit(".", 1)[-1],
                    member=None if wildcard else member,
                    certain=True,
                    lineno=lineno,
                )
            )
            continue
        if wildcard:
            # `import a.b.*` names a package. Which of its types this file
            # actually uses is not in the tree, so no target may be called
            # proven.
            references.append(
                _TypeReference(
                    qualified=dotted,
                    simple_name=None,
                    member=None,
                    certain=False,
                    lineno=lineno,
                )
            )
            continue
        references.append(
            _TypeReference(
                qualified=dotted,
                simple_name=dotted.rsplit(".", 1)[-1],
                member=None,
                certain=True,
                lineno=lineno,
            )
        )
    return references


def _import_edges(
    parsed: _ParsedFile,
    references: tuple[_TypeReference, ...],
    index: _SyntaxEvidenceIndex,
) -> list[Edge]:
    edges: list[Edge] = []
    for reference in references:
        lineno = reference.lineno
        if reference.simple_name is None:
            targets = [
                module_id
                for module_id in index.modules_by_package.get(reference.qualified, ())
                if module_id != parsed.module_id
            ]
            if targets:
                edges.extend(
                    Edge(
                        src=parsed.module_id,
                        dst=module_id,
                        kind="import",
                        certain=False,
                        lineno=lineno,
                    )
                    for module_id in targets
                )
                continue
            edges.append(
                Edge(
                    src=parsed.module_id,
                    dst=f"external:{reference.qualified}.*",
                    kind="import",
                    certain=False,
                    lineno=lineno,
                    external=True,
                )
            )
            continue
        type_id = index.type_by_qualified.get(reference.qualified)
        if type_id is not None:
            edges.append(
                Edge(
                    src=parsed.module_id,
                    dst=index.node_by_id[type_id].region,
                    kind="import",
                    certain=True,
                    lineno=lineno,
                )
            )
            continue
        edges.append(
            Edge(
                src=parsed.module_id,
                dst=f"external:{reference.qualified}",
                kind="import",
                certain=True,
                lineno=lineno,
                external=True,
            )
        )
    return edges


def _resolve_type(
    module_id: str,
    simple_name: str,
    references: tuple[_TypeReference, ...],
    index: _SyntaxEvidenceIndex,
) -> str | None:
    """Return the project type ``simple_name`` names here, or ``None``.

    The order is Java's own: a type declared in this file wins, then an
    explicit single-type import, then the file's own package. A type-wildcard
    import is deliberately not consulted -- it proves no specific type.
    """

    declared = index.type_by_module_name.get((module_id, simple_name))
    if declared is not None:
        return declared
    for reference in references:
        if reference.simple_name == simple_name and reference.certain:
            imported = index.type_by_qualified.get(reference.qualified)
            if imported is not None:
                return imported
    package = index.parsed_by_module[module_id].package
    qualified = f"{package}.{simple_name}" if package else simple_name
    return index.type_by_qualified.get(qualified)


def _call_edges(
    index: _SyntaxEvidenceIndex,
    references_by_module: dict[str, tuple[_TypeReference, ...]],
) -> list[Edge]:
    edges: list[Edge] = []
    # Types are walked too, not only callables: `_walk_owned` stops at every
    # nested definition, so what remains of a type is its field initializers
    # and initializer blocks -- real call sites that would otherwise be dropped
    # rather than merely left uncertain.
    for definition in index.definitions:
        parsed = index.parsed_by_module[definition.module_id]
        references = references_by_module[definition.module_id]
        for syntax in _walk_owned(
            definition.syntax,
            index.nested_ranges_by_owner.get(definition.node_id, frozenset()),
        ):
            if syntax.has_error or syntax.type != "method_invocation":
                continue
            edges.append(
                _resolve_call(
                    definition,
                    syntax,
                    parsed.raw,
                    references,
                    index,
                    index.local_bindings_by_owner[definition.node_id],
                )
            )
    return edges


def _resolve_call(
    definition: _Definition,
    syntax: SyntaxNode,
    raw: bytes,
    references: tuple[_TypeReference, ...],
    index: _SyntaxEvidenceIndex,
    local_binding_names: frozenset[str],
) -> Edge:
    lineno = syntax.start_point.row + 1
    name_node = syntax.child_by_field_name("name")
    if name_node is None or name_node.type != "identifier":
        return _dynamic_call_edge(definition.node_id, lineno)
    name = _node_text(name_node, raw)
    receiver = syntax.child_by_field_name("object")
    # A type definition owns its own field initializers, so `this` there means
    # the type itself rather than whatever encloses it.
    owner_type = (
        definition.node_id if definition.is_type else definition.enclosing_type_id
    )

    if receiver is None or receiver.type == "this":
        candidates = index.members_named(owner_type, name)
        if candidates:
            return _first_or_ambiguous(definition.node_id, candidates, lineno)
        if receiver is None:
            static = _static_import_target(
                definition.node_id, name, references, index, lineno
            )
            if static is not None:
                return static
        # An unqualified or `this.` call the enclosing type does not declare is
        # inherited from a supertype this file may not even contain.
        return _unresolved_call_edge(definition.node_id, definition.module_id, name, lineno)

    if receiver.type == "super":
        # `super.` targets a supertype by definition, and the parser proves
        # neither which one nor whether the project declares it.
        return _unresolved_call_edge(
            definition.node_id, definition.module_id, f"super.{name}", lineno
        )

    if receiver.type == "identifier":
        receiver_name = _node_text(receiver, raw)
        # A parameter, local, resource or catch binding shadows any field of the
        # same name, so the field's declared type says nothing about it.
        if receiver_name not in local_binding_names:
            field_type = index.field_types_by_type.get(owner_type or "", {}).get(
                receiver_name
            )
            if field_type is not None:
                owner = _resolve_type(
                    definition.module_id, field_type, references, index
                )
                candidates = index.members_named(owner, name)
                if candidates:
                    return _first_or_ambiguous(definition.node_id, candidates, lineno)
            static_owner = _resolve_type(
                definition.module_id, receiver_name, references, index
            )
            candidates = index.members_named(static_owner, name)
            if candidates:
                return _first_or_ambiguous(definition.node_id, candidates, lineno)
        return Edge(
            definition.node_id,
            f"external:{receiver_name}.{name}",
            "call",
            certain=False,
            lineno=lineno,
            external=True,
        )

    # A chained call, a field access, an array element: the receiver's type is
    # the result of an expression, which the syntax tree alone cannot type.
    return Edge(
        definition.node_id,
        f"external:{_node_text(receiver, raw)[:80]}.{name}",
        "call",
        certain=False,
        lineno=lineno,
        external=True,
    )


def _static_import_target(
    src: str,
    name: str,
    references: tuple[_TypeReference, ...],
    index: _SyntaxEvidenceIndex,
    lineno: int,
) -> Edge | None:
    """Resolve an unqualified call brought into scope by a static import."""

    for reference in references:
        if reference.member != name:
            continue
        owner = index.type_by_qualified.get(reference.qualified)
        candidates = index.members_named(owner, name)
        if candidates:
            return _first_or_ambiguous(src, candidates, lineno)
    return None


def _first_or_ambiguous(src: str, candidates: list[Node], lineno: int) -> Edge:
    """One name, one target: certain. Overloads share a name, so they are not."""

    return Edge(
        src,
        candidates[0].id,
        "call",
        certain=len(candidates) == 1,
        lineno=lineno,
    )


def _unresolved_call_edge(src: str, scope: str, name: str, lineno: int) -> Edge:
    return Edge(
        src,
        f"unresolved:{scope}:{name}",
        "call",
        certain=False,
        lineno=lineno,
    )


def _dynamic_call_edge(src: str, lineno: int) -> Edge:
    return Edge(
        src,
        f"external:dynamic-call@{lineno}",
        "call",
        certain=False,
        lineno=lineno,
        external=True,
    )


def _local_binding_names(
    syntax: SyntaxNode,
    raw: bytes,
    nested_definition_ranges: AbstractSet[tuple[int, int]],
) -> set[str]:
    """Every name bound inside this callable that shadows a field."""

    names: set[str] = set()
    parameters = syntax.child_by_field_name("parameters")
    if parameters is not None:
        names.update(_declared_names(parameters, raw))
    for child in _walk_owned(syntax, nested_definition_ranges):
        if child.type in {
            "catch_formal_parameter",
            "formal_parameter",
            "inferred_parameters",
            "resource",
            "spread_parameter",
        }:
            names.update(_declared_names(child, raw))
        elif child.type == "local_variable_declaration":
            for declarator in child.named_children:
                if declarator.type == "variable_declarator":
                    names.update(_declared_names(declarator, raw))
        elif child.type == "enhanced_for_statement":
            bound = child.child_by_field_name("name")
            if bound is not None:
                names.add(_node_text(bound, raw))
        elif child.type == "lambda_expression":
            bound = child.child_by_field_name("parameters")
            if bound is not None:
                names.update(_declared_names(bound, raw))
    return names


def _declared_names(syntax: SyntaxNode, raw: bytes) -> set[str]:
    if syntax.type == "identifier":
        return {_node_text(syntax, raw)}
    named = syntax.child_by_field_name("name")
    if named is not None and named.type == "identifier":
        return {_node_text(named, raw)}
    names: set[str] = set()
    for child in _walk(syntax):
        if child.type == "identifier" and child.parent is not None and (
            child.parent.child_by_field_name("name") == child
            or child.parent.type in {"inferred_parameters", "formal_parameters"}
        ):
            names.add(_node_text(child, raw))
    return names


def _entrypoint_ranks(index: _SyntaxEvidenceIndex) -> dict[str, int]:
    """Rank the structures a Java project actually starts from.

    A JVM starts at `public static void main(String[])`, so its file is Home
    and the method itself follows. A Spring Boot class is the next best
    evidence, and a test class is real but is the last place a learner should
    be sent to understand what their project does.
    """

    ranks: dict[str, int] = {}
    for parsed in index.parsed_files:
        raw = parsed.raw
        for definition in index.definitions_by_module.get(parsed.module_id, ()):
            syntax = definition.syntax
            if definition.is_type:
                annotations = _annotation_names(syntax, raw)
                if "SpringBootApplication" in annotations:
                    ranks[definition.node_id] = 2
                    ranks.setdefault(parsed.module_id, 3)
                elif _declares_test(syntax, raw):
                    ranks[definition.node_id] = 4
                continue
            if _is_main_method(syntax, raw):
                ranks[definition.node_id] = 1
                ranks[parsed.module_id] = 0
    return ranks


def _declares_test(type_syntax: SyntaxNode, raw: bytes) -> bool:
    body = type_syntax.child_by_field_name("body")
    if body is None:
        return False
    return any(
        member.type == "method_declaration"
        and not member.has_error
        and "Test" in _annotation_names(member, raw)
        for member in body.named_children
    )


def _is_main_method(syntax: SyntaxNode, raw: bytes) -> bool:
    if syntax.type != "method_declaration":
        return False
    if _field_text(syntax, "name", raw) != "main":
        return False
    if not {"public", "static"} <= _modifier_keywords(syntax):
        return False
    returns = syntax.child_by_field_name("type")
    if returns is None or returns.type != "void_type":
        return False
    parameters = syntax.child_by_field_name("parameters")
    if parameters is None:
        return False
    declared = [
        child
        for child in parameters.named_children
        if child.type in {"formal_parameter", "spread_parameter"}
    ]
    return len(declared) == 1 and _is_string_sequence(declared[0], raw)


def _is_string_sequence(parameter: SyntaxNode, raw: bytes) -> bool:
    """True for `String[] args` and for the equivalent `String... args`."""

    if parameter.type == "spread_parameter":
        return _declared_type_name(parameter.named_child(0), raw) == "String"
    declared = parameter.child_by_field_name("type")
    if declared is None or declared.type != "array_type":
        return False
    return _declared_type_name(declared.child_by_field_name("element"), raw) == "String"


__all__ = ["JavaAdapter", "JavaParseError"]
