"""Tree-sitter C# implementation of the language seam."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_c_sharp
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

_EXTENSIONS = frozenset({".cs"})
# `bin` and `obj` hold the compiler's own output -- including generated partial
# classes that duplicate structures the learner did write. Charting them would
# show the same type twice with one copy nobody typed.
_GENERATED_DIRECTORIES = frozenset({"bin", "obj"})

_NAMESPACE_DECLARATIONS = frozenset(
    {"namespace_declaration", "file_scoped_namespace_declaration"}
)
_TYPE_DECLARATIONS = frozenset(
    {
        "class_declaration",
        "enum_declaration",
        "interface_declaration",
        "record_declaration",
        "struct_declaration",
    }
)
_MEMBER_DECLARATIONS = frozenset(
    {"constructor_declaration", "method_declaration", "property_declaration"}
)
# Test attributes are recognised so a suite ranks *behind* real entrypoints.
# Deliberately only the two the product asked for: an unfamiliar attribute must
# leave a class unranked rather than guessed into last place.
_TEST_ATTRIBUTE_BYTES = frozenset({b"Fact", b"TestMethod"})

_CS_LANGUAGE = Language(tree_sitter_c_sharp.language())


class CSharpParseError(AdapterParseError):
    """C# source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
    raw: bytes
    source: str
    # The file split the way tree-sitter counts rows, so a line number taken
    # from the tree indexes the line it names. `str.splitlines` cannot be used
    # for this: it also breaks on VT, FF, NEL, U+2028 and six more characters
    # the grammar reads as ordinary text, so one form feed inside a string
    # literal shifted every later snippet onto its predecessor's line.
    lines: tuple[str, ...]
    digest: str
    tree: Tree


@dataclass(frozen=True, slots=True)
class _Definition:
    """One declared structure and the syntax that proves it."""

    node_id: str
    syntax: SyntaxNode
    parent_id: str
    module_id: str
    enclosing_type_id: str | None
    declaration: str


@dataclass(frozen=True, slots=True)
class _CSharpIndex:
    """Ownership and lookup evidence derived from one pass over the syntax."""

    parsed_files: tuple[_ParsedFile, ...]
    definitions: tuple[_Definition, ...]
    nodes: tuple[Node, ...]
    parsed_by_module: dict[str, _ParsedFile]
    definitions_by_module: dict[str, tuple[_Definition, ...]]
    node_by_id: dict[str, Node]
    children_by_parent: dict[str, tuple[Node, ...]]
    nodes_by_module_name: dict[tuple[str, str], tuple[Node, ...]]
    type_ids_by_name: dict[str, tuple[str, ...]]
    modules_by_namespace: dict[str, tuple[str, ...]]
    nested_ranges_by_owner: dict[str, frozenset[tuple[int, int]]]
    # Names a body binds itself: parameters and locals. A call through one of
    # these is a delegate invocation, and what a delegate points at is decided
    # while the program runs.
    local_names_by_owner: dict[str, frozenset[str]]
    # Only *explicitly* typed receivers appear here. `var` is deliberately
    # absent, so an inferred local can never borrow a declared type's certainty.
    receiver_types_by_owner: dict[str, dict[str, str]]
    member_types_by_type: dict[str, dict[str, str]]
    # Members whose dispatch C# settles at run time rather than at the call
    # site. Calling one by name reaches whichever override the instance
    # carries, and an override can live in a class this parse never sees.
    virtual_member_ids: frozenset[str]
    # The type names written after `:` on each type declaration, which is the
    # only evidence this parse has for what `base` refers to.
    base_type_names_by_type: dict[str, tuple[str, ...]]

    @classmethod
    def build(
        cls,
        parsed_files: tuple[_ParsedFile, ...],
        definitions: tuple[_Definition, ...],
        nodes: tuple[Node, ...],
    ) -> _CSharpIndex:
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
        children_by_parent, nodes_by_module_name = cls._node_lookups(
            definitions,
            node_by_id,
        )
        type_ids: dict[str, list[str]] = defaultdict(list)
        for definition in definitions:
            if definition.declaration in _TYPE_DECLARATIONS:
                type_ids[node_by_id[definition.node_id].name].append(definition.node_id)
        namespace_modules: dict[str, set[str]] = defaultdict(set)
        for definition in definitions:
            if definition.declaration in _NAMESPACE_DECLARATIONS:
                namespace_modules[node_by_id[definition.node_id].name].add(
                    definition.module_id
                )
        frozen_ranges = {
            owner: frozenset(ranges) for owner, ranges in nested_ranges.items()
        }

        virtual_members: set[str] = set()
        base_type_names: dict[str, tuple[str, ...]] = {}
        for definition in definitions:
            if definition.declaration in _TYPE_DECLARATIONS:
                base_type_names[definition.node_id] = _declared_base_type_names(
                    definition.syntax,
                    parsed_by_module[definition.module_id].raw,
                )
                continue
            if definition.declaration not in _MEMBER_DECLARATIONS:
                continue
            owner_definition = definitions_by_id.get(definition.parent_id)
            owner_declaration = (
                owner_definition.declaration if owner_definition is not None else ""
            )
            if owner_declaration == "interface_declaration" or any(
                _has_modifier(definition.syntax, keyword)
                for keyword in ("abstract", "override", "virtual")
            ):
                # An interface member carries no modifiers and is virtual all
                # the same, so the declaration that owns it is evidence too.
                virtual_members.add(definition.node_id)

        local_names: dict[str, frozenset[str]] = {}
        receiver_types: dict[str, dict[str, str]] = {}
        member_types: dict[str, dict[str, str]] = {}
        for parsed in parsed_files:
            # Top-level statements have no declaration to own them, so the file
            # itself is a call owner and needs the same local evidence.
            names, types = _body_bindings(
                parsed.tree.root_node,
                parsed.raw,
                frozen_ranges.get(parsed.module_id, frozenset()),
            )
            local_names[parsed.module_id] = names
            receiver_types[parsed.module_id] = types
        for definition in definitions:
            raw = parsed_by_module[definition.module_id].raw
            owned = frozen_ranges.get(definition.node_id, frozenset())
            names, types = _body_bindings(definition.syntax, raw, owned)
            local_names[definition.node_id] = names
            receiver_types[definition.node_id] = types
            if definition.declaration in _TYPE_DECLARATIONS:
                member_types[definition.node_id] = _declared_member_types(
                    definition.syntax,
                    raw,
                )

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
            nodes_by_module_name=nodes_by_module_name,
            type_ids_by_name={
                name: tuple(sorted(ids)) for name, ids in type_ids.items()
            },
            modules_by_namespace={
                namespace: tuple(sorted(modules))
                for namespace, modules in namespace_modules.items()
            },
            nested_ranges_by_owner=frozen_ranges,
            local_names_by_owner=local_names,
            receiver_types_by_owner=receiver_types,
            member_types_by_type=member_types,
            virtual_member_ids=frozenset(virtual_members),
            base_type_names_by_type=base_type_names,
        )

    def with_nodes(self, nodes: tuple[Node, ...]) -> _CSharpIndex:
        """Refresh node metadata without rebuilding syntax ownership evidence."""

        node_by_id = {node.id: node for node in nodes}
        children_by_parent, nodes_by_module_name = self._node_lookups(
            self.definitions,
            node_by_id,
        )
        return replace(
            self,
            nodes=nodes,
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            nodes_by_module_name=nodes_by_module_name,
        )

    @staticmethod
    def _node_lookups(
        definitions: tuple[_Definition, ...],
        node_by_id: dict[str, Node],
    ) -> tuple[
        dict[str, tuple[Node, ...]],
        dict[tuple[str, str], tuple[Node, ...]],
    ]:
        children: dict[str, list[Node]] = defaultdict(list)
        module_names: dict[tuple[str, str], list[Node]] = defaultdict(list)
        for definition in definitions:
            node = node_by_id[definition.node_id]
            children[definition.parent_id].append(node)
            module_names[(definition.module_id, node.name)].append(node)
        return (
            {parent: tuple(nodes) for parent, nodes in children.items()},
            {key: tuple(nodes) for key, nodes in module_names.items()},
        )


class CSharpAdapter:
    """Map C# source into one deterministic, parser-proven graph."""

    language = "csharp"
    file_extensions = _EXTENSIONS
    ignored_directories = _GENERATED_DIRECTORIES

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact C# source scope accepted by this adapter."""

        normalized = path.expanduser().resolve()
        try:
            discovery = discover_source_files(
                normalized,
                self.file_extensions,
                ignored_directories=self.ignored_directories,
            )
        except SourceDiscoveryError as error:
            raise CSharpParseError(str(error)) from error
        if not discovery.files:
            if normalized.is_file():
                raise CSharpParseError(f"expected a C# file or directory: {normalized}")
            raise CSharpParseError(f"no C# files found under: {normalized}")
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse ``path`` using the official tree-sitter C# grammar wheel."""

        project_root, files = self.discover(path)
        return self.parse_files(project_root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        """Parse C# files already discovered as owned by this adapter."""

        parsed_files = tuple(_parse_file(file, project_root) for file in files)

        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            nodes.append(_module_node(parsed))
            file_nodes, file_definitions = _collect_definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        index = _CSharpIndex.build(parsed_files, tuple(definitions), tuple(nodes))
        entrypoint_ranks = _entrypoint_ranks(index)
        index = index.with_nodes(
            tuple(
                replace(node, entrypoint_rank=entrypoint_ranks.get(node.id))
                for node in index.nodes
            )
        )

        edges: list[Edge] = []
        for parsed in parsed_files:
            edges.extend(_import_edges(parsed, index))
        edges.extend(_call_edges(index))

        draft = Graph(
            nodes=index.nodes,
            edges=tuple(edges),
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
            raise CSharpParseError(str(error)) from error

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only tree-sitter-proven concepts owned by ``node``."""

        if node.partial or node.language != self.language:
            return []
        raw = source.encode("utf-8")
        parsed = _ParsedFile(
            path=Path(node.file),
            project_root=Path("."),
            relative_path=node.file,
            module_id=node.region,
            raw=raw,
            source=source,
            lines=_source_lines(source),
            digest=hashlib.sha256(raw).hexdigest(),
            tree=Parser(_CS_LANGUAGE).parse(raw),
        )
        module_node = _module_node(parsed)
        file_nodes, definitions = _collect_definitions(parsed)
        index = _CSharpIndex.build(
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


def _source_lines(source: str) -> tuple[str, ...]:
    """Split ``source`` into the rows tree-sitter reports line numbers against."""

    lines = source.split("\n")
    if lines and lines[-1] == "":
        # A trailing newline ends the last line rather than starting an empty
        # one, which is the count a reader means by "how long is this file".
        lines.pop()
    return tuple(lines)


def _parse_file(path: Path, project_root: Path) -> _ParsedFile:
    raw = path.read_bytes()
    relative = path.relative_to(project_root).as_posix()
    source = raw.decode("utf-8", errors="replace")
    parsed = _ParsedFile(
        path=path,
        project_root=project_root,
        relative_path=relative,
        module_id=f"csharp:{relative}",
        raw=raw,
        source=source,
        lines=_source_lines(source),
        digest=hashlib.sha256(raw).hexdigest(),
        tree=Parser(_CS_LANGUAGE).parse(raw),
    )
    note_file_parsed()
    return parsed


def _module_node(parsed: _ParsedFile) -> Node:
    line_count = max(1, len(parsed.lines))
    return Node(
        id=parsed.module_id,
        kind="module",
        name=Path(parsed.relative_path).stem,
        language=CSharpAdapter.language,
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
        qualname: tuple[str, ...],
        parent_id: str,
        enclosing_type_id: str | None,
    ) -> tuple[str, tuple[str, ...]]:
        next_qualname = (*qualname, name)
        base_id = f"{parsed.module_id}::{'.'.join(next_qualname)}"
        node_id = _unique_node_id(base_id, syntax, used_ids)
        used_ids.add(node_id)
        lineno, end_lineno = _line_span(syntax)
        nodes.append(
            Node(
                id=node_id,
                kind=kind,  # type: ignore[arg-type]
                name=name,
                language=CSharpAdapter.language,
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
                declaration=syntax.type,
            )
        )
        return node_id, next_qualname

    def visit(
        container: SyntaxNode,
        qualname: tuple[str, ...],
        parent_id: str,
        enclosing_type_id: str | None,
    ) -> None:
        for child in container.named_children:
            if child.has_error:
                continue
            name = _declared_name(child, parsed.raw)
            if name is None:
                visit(child, qualname, parent_id, enclosing_type_id)
                continue
            if child.type == "file_scoped_namespace_declaration":
                # `namespace Foo;` has no body: everything after it in the file
                # belongs to it, so the remaining siblings are visited as its
                # children instead of recursing into the declaration itself.
                node_id, child_qualname = add_definition(
                    child,
                    name,
                    "class",
                    qualname,
                    parent_id,
                    enclosing_type_id,
                )
                qualname = child_qualname
                parent_id = node_id
                continue
            if child.type in _TYPE_DECLARATIONS:
                node_id, child_qualname = add_definition(
                    child, name, "class", qualname, parent_id, enclosing_type_id
                )
                visit(child, child_qualname, node_id, node_id)
                continue
            if child.type == "namespace_declaration":
                node_id, child_qualname = add_definition(
                    child, name, "class", qualname, parent_id, enclosing_type_id
                )
                visit(child, child_qualname, node_id, enclosing_type_id)
                continue
            if child.type in _MEMBER_DECLARATIONS and enclosing_type_id is not None:
                node_id, child_qualname = add_definition(
                    child,
                    name,
                    "function",
                    qualname,
                    parent_id,
                    enclosing_type_id,
                )
                visit(child, child_qualname, node_id, enclosing_type_id)
                continue
            visit(child, qualname, parent_id, enclosing_type_id)

    visit(parsed.tree.root_node, (), parsed.module_id, None)
    return nodes, definitions


def _declared_name(syntax: SyntaxNode, raw: bytes) -> str | None:
    """Return the declared name of a structure, or ``None`` when it is not one."""

    if (
        syntax.type not in _NAMESPACE_DECLARATIONS
        and syntax.type not in _TYPE_DECLARATIONS
        and syntax.type not in _MEMBER_DECLARATIONS
    ):
        return None
    name = syntax.child_by_field_name("name")
    if name is None or name.has_error:
        return None
    if name.type == "qualified_name":
        return _node_text(name, raw)
    if name.type != "identifier":
        return None
    return _node_text(name, raw)


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


def _has_modifier(syntax: SyntaxNode, keyword: str) -> bool:
    return any(
        child.type == "modifier" and child.text == keyword.encode("ascii")
        for child in syntax.children
    )


def _simple_type_name(syntax: SyntaxNode | None, raw: bytes) -> str | None:
    """Return the project-comparable simple name of a written type.

    ``None`` where the written type names nothing a project declaration could
    be: a built-in such as ``int``, or an array, whose members belong to the
    runtime rather than to the element type.
    """

    if syntax is None or syntax.has_error:
        return None
    if syntax.type == "nullable_type":
        return _simple_type_name(syntax.child_by_field_name("type"), raw)
    if syntax.type == "identifier":
        return _node_text(syntax, raw)
    if syntax.type in {"qualified_name", "alias_qualified_name"}:
        return _simple_type_name(syntax.child_by_field_name("name"), raw)
    if syntax.type == "generic_name":
        first = syntax.named_child(0)
        return _node_text(first, raw) if first is not None else None
    return None


def _body_bindings(
    syntax: SyntaxNode,
    raw: bytes,
    nested_definition_ranges: AbstractSet[tuple[int, int]],
) -> tuple[frozenset[str], dict[str, str]]:
    """Return the names a body binds, and the subset with a written type."""

    names: set[str] = set()
    types: dict[str, str] = {}
    for child in (syntax, *_walk_owned(syntax, nested_definition_ranges)):
        if child.type == "parameter":
            name = child.child_by_field_name("name")
            if name is None or name.type != "identifier":
                continue
            local = _node_text(name, raw)
            names.add(local)
            written = _simple_type_name(child.child_by_field_name("type"), raw)
            if written is not None:
                types[local] = written
        elif child.type == "variable_declaration":
            written = _simple_type_name(child.child_by_field_name("type"), raw)
            for declarator in child.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name = declarator.child_by_field_name("name")
                if name is None or name.type != "identifier":
                    continue
                local = _node_text(name, raw)
                names.add(local)
                if written is not None:
                    types[local] = written
    return frozenset(names), types


def _declared_base_type_names(type_syntax: SyntaxNode, raw: bytes) -> tuple[str, ...]:
    """Return the simple names written after ``:`` on a type declaration."""

    base_list = next(
        (child for child in type_syntax.children if child.type == "base_list"),
        None,
    )
    if base_list is None:
        return ()
    names = [
        name
        for child in base_list.named_children
        if (name := _simple_type_name(child, raw)) is not None
    ]
    return tuple(names)


def _declared_member_types(type_syntax: SyntaxNode, raw: bytes) -> dict[str, str]:
    """Return field and property names of one type mapped to their written type."""

    member_types: dict[str, str] = {}
    body = type_syntax.child_by_field_name("body")
    if body is None:
        return member_types
    for member in body.named_children:
        if member.has_error:
            continue
        if member.type == "field_declaration":
            declaration = next(
                (
                    child
                    for child in member.named_children
                    if child.type == "variable_declaration"
                ),
                None,
            )
            if declaration is None:
                continue
            written = _simple_type_name(declaration.child_by_field_name("type"), raw)
            if written is None:
                continue
            for declarator in declaration.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name = declarator.child_by_field_name("name")
                if name is not None and name.type == "identifier":
                    member_types[_node_text(name, raw)] = written
        elif member.type == "property_declaration":
            name = member.child_by_field_name("name")
            written = _simple_type_name(member.child_by_field_name("type"), raw)
            if name is not None and name.type == "identifier" and written is not None:
                member_types[_node_text(name, raw)] = written
    return member_types


def _concept_annotations(index: _CSharpIndex) -> tuple[ConceptAnnotation, ...]:
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
    candidates: Iterable[SyntaxNode] = (syntax, *walked) if include_owner else walked
    annotations: set[ConceptAnnotation] = set()
    source_lines = parsed.lines
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
                    language=owner.language,
                    concept=concept,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    snippet=snippet[:240],
                )
            )
    return annotations


def _concepts_for_syntax(syntax: SyntaxNode) -> tuple[str, ...]:
    concepts: list[str] = []
    if syntax.type == "query_expression":
        concepts.append("linq-query")
    if syntax.type == "await_expression":
        concepts.append("async-await")
    if syntax.type in {
        "constructor_declaration",
        "local_function_statement",
        "method_declaration",
    } and _has_modifier(syntax, "async"):
        concepts.append("async-await")
    if syntax.type == "property_declaration" and any(
        child.type == "accessor_list" for child in syntax.named_children
    ):
        concepts.append("property-accessors")
    if syntax.type == "record_declaration":
        concepts.append("record")
    if syntax.type == "nullable_type":
        # Named for what the tree shows -- a `?` written on a type. Whether the
        # underlying type is a reference type is a fact about the type's own
        # declaration, which may live in an assembly this parse never sees.
        concepts.append("nullable-type")
    if syntax.type == "switch_expression":
        concepts.append("pattern-matching")
    if syntax.type == "method_declaration" and _is_extension_method(syntax):
        concepts.append("extension-method")
    if syntax.type in {"type_parameter_list", "type_argument_list"}:
        concepts.append("generic")
    return tuple(concepts)


def _is_extension_method(syntax: SyntaxNode) -> bool:
    parameters = syntax.child_by_field_name("parameters")
    if parameters is None:
        return False
    first = next(
        (child for child in parameters.named_children if child.type == "parameter"),
        None,
    )
    return first is not None and _has_modifier(first, "this")


def _import_edges(parsed: _ParsedFile, index: _CSharpIndex) -> list[Edge]:
    """Turn every ``using`` directive into one honest namespace import."""

    edges: list[Edge] = []
    for syntax in _walk(parsed.tree.root_node):
        if syntax.type != "using_directive" or syntax.has_error:
            continue
        target = _using_target(syntax)
        if target is None:
            continue
        written = _node_text(target, parsed.raw)
        namespace = _using_namespace(syntax, written)
        # A `using` names a namespace, never a file, and a C# namespace is open
        # across files. Where several project files declare it, the parser
        # cannot say which one this file leans on, so each candidate stays a
        # possible route rather than one of them being picked.
        declaring = tuple(
            module_id
            for module_id in index.modules_by_namespace.get(namespace, ())
            if module_id != parsed.module_id
        )
        if declaring:
            edges.extend(
                Edge(
                    src=parsed.module_id,
                    dst=module_id,
                    kind="import",
                    certain=len(declaring) == 1,
                    lineno=syntax.start_point.row + 1,
                )
                for module_id in declaring
            )
            continue
        edges.append(
            Edge(
                src=parsed.module_id,
                dst=f"external:{written}",
                kind="import",
                certain=True,
                lineno=syntax.start_point.row + 1,
                external=True,
            )
        )
    return edges


def _using_target(syntax: SyntaxNode) -> SyntaxNode | None:
    """Return what a ``using`` names, past any alias keyword."""

    named = [child for child in syntax.named_children if not child.has_error]
    if not named:
        return None
    # `using Alias = Acme.Core;` puts the alias in the `name` field and the
    # target last; a plain or `static` using has only the target.
    return named[-1]


def _using_namespace(syntax: SyntaxNode, written: str) -> str:
    """Return the namespace a ``using`` reaches into.

    ``using static Acme.Lib.Helpers;`` names a *type*, so the namespace is its
    qualifier. Looking the whole thing up found no declaring file and the
    directive was published as a certain route out of the project -- while the
    type it names was sitting in the parse.
    """

    if not any(child.type == "static" for child in syntax.children):
        return written
    qualifier, separator, _ = written.rpartition(".")
    return qualifier if separator else written


def _call_edges(index: _CSharpIndex) -> list[Edge]:
    edges: list[Edge] = []
    owners = [
        # A file with top-level statements calls things with no declaration to
        # own the call, so the module node owns those.
        _Definition(
            node_id=parsed.module_id,
            syntax=parsed.tree.root_node,
            parent_id=parsed.module_id,
            module_id=parsed.module_id,
            enclosing_type_id=None,
            declaration="compilation_unit",
        )
        for parsed in index.parsed_files
    ]
    owners.extend(index.definitions)
    for owner in owners:
        parsed = index.parsed_by_module[owner.module_id]
        owned = index.nested_ranges_by_owner.get(owner.node_id, frozenset())
        for syntax in _walk_owned(owner.syntax, owned):
            if syntax.has_error:
                continue
            if syntax.type == "invocation_expression":
                edges.extend(_resolve_invocation(owner, syntax, parsed, index))
            elif syntax.type in {
                "implicit_object_creation_expression",
                "object_creation_expression",
            }:
                edges.extend(_resolve_creation(owner, syntax, parsed, index))
    return edges


def _resolve_invocation(
    owner: _Definition,
    syntax: SyntaxNode,
    parsed: _ParsedFile,
    index: _CSharpIndex,
) -> list[Edge]:
    target = syntax.child_by_field_name("function")
    lineno = syntax.start_point.row + 1
    if target is None:
        return [_dynamic_call_edge(owner.node_id, lineno)]

    # `Wrap<int>()` names its member as plainly as `Wrap()` does; only the type
    # arguments differ, and they change no name this parse resolves by.
    invoked = _invoked_name(target, parsed.raw)
    if invoked is not None:
        if invoked in index.local_names_by_owner.get(owner.node_id, frozenset()):
            # A parameter or local invoked by name is a delegate, and what it
            # points at is chosen while the program runs.
            return [
                Edge(
                    owner.node_id,
                    f"unresolved:{owner.node_id}:{invoked}",
                    "call",
                    certain=False,
                    lineno=lineno,
                )
            ]
        candidates = _members_named(index, owner.enclosing_type_id, invoked)
        if candidates:
            return _member_call_edges(owner.node_id, candidates, lineno, index)
        # Sharing a file settles nothing: an unqualified name reaches a member
        # of another type in it only through inheritance or a `using static`
        # this parse has not followed, so the match stays a possible call.
        siblings = sorted(
            index.nodes_by_module_name.get((owner.module_id, invoked), ()),
            key=lambda node: node.id,
        )
        if siblings:
            return [
                _call_edge(owner.node_id, node.id, lineno, certain=False)
                for node in siblings
            ]
        return [
            Edge(
                owner.node_id,
                f"unresolved:{owner.module_id}:{invoked}",
                "call",
                certain=False,
                lineno=lineno,
            )
        ]

    if target.type == "member_access_expression":
        return _resolve_member_call(owner, target, parsed, index, lineno)

    return [_dynamic_call_edge(owner.node_id, lineno)]


def _invoked_name(target: SyntaxNode, raw: bytes) -> str | None:
    """Return the bare member name an invocation target writes, if it writes one."""

    if target.type == "identifier":
        return _node_text(target, raw)
    if target.type == "generic_name":
        first = target.named_child(0)
        if first is not None and first.type == "identifier":
            return _node_text(first, raw)
    return None


def _member_call_edges(
    owner_id: str,
    candidates: list[Node],
    lineno: int,
    index: _CSharpIndex,
) -> list[Edge]:
    """Edge each candidate, certain only where C# settles dispatch at the call.

    A `virtual`, `abstract` or `override` member -- and every interface member,
    which is virtual without saying so -- reaches whichever override the
    instance carries, and that override can be declared in a class outside this
    parse. Only a member no derived class may replace binds here for good.
    """

    certain = len(candidates) == 1 and candidates[0].id not in index.virtual_member_ids
    return [
        _call_edge(owner_id, candidate.id, lineno, certain=certain)
        for candidate in candidates
    ]


def _resolve_member_call(
    owner: _Definition,
    target: SyntaxNode,
    parsed: _ParsedFile,
    index: _CSharpIndex,
    lineno: int,
) -> list[Edge]:
    receiver = target.child_by_field_name("expression")
    member = target.child_by_field_name("name")
    if member is None or member.type != "identifier":
        return [_dynamic_call_edge(owner.node_id, lineno)]
    name = _node_text(member, parsed.raw)

    if receiver is not None and receiver.type == "this":
        candidates = _members_named(index, owner.enclosing_type_id, name)
        if candidates:
            return _member_call_edges(owner.node_id, candidates, lineno, index)

    if receiver is not None and receiver.type == "base":
        # `base.M()` is the one call C# guarantees does NOT reach this type's
        # own member -- it reaches the one it overrides. Resolving it against
        # the enclosing type named the override as the target of the call that
        # exists precisely to skip it, so the base types written on the
        # declaration are the only honest place to look. They are simple names
        # this parse never checks a namespace against, and the member found
        # there may itself override something further up, so nothing is certain.
        inherited = sorted(
            (
                node
                for base_name in index.base_type_names_by_type.get(
                    owner.enclosing_type_id or "", ()
                )
                for type_id in index.type_ids_by_name.get(base_name, ())
                for node in index.children_by_parent.get(type_id, ())
                if node.name == name
            ),
            key=lambda node: node.id,
        )
        if inherited:
            return [
                _call_edge(owner.node_id, node.id, lineno, certain=False)
                for node in inherited
            ]
        return [
            Edge(
                owner.node_id,
                f"external:base.{name}",
                "call",
                certain=False,
                lineno=lineno,
                external=True,
            )
        ]

    if receiver is not None and receiver.type == "identifier":
        receiver_name = _node_text(receiver, parsed.raw)
        written = index.receiver_types_by_owner.get(owner.node_id, {}).get(
            receiver_name
        )
        if written is None and owner.enclosing_type_id is not None:
            written = index.member_types_by_type.get(
                owner.enclosing_type_id, {}
            ).get(receiver_name)
        if written is None and receiver_name not in index.local_names_by_owner.get(
            owner.node_id, frozenset()
        ):
            # Nothing bound this name in the body, so it may be the type itself
            # being called statically.
            written = receiver_name
        candidates = [
            node
            for type_id in index.type_ids_by_name.get(written or "", ())
            for node in index.children_by_parent.get(type_id, ())
            if node.name == name
        ]
        if candidates:
            # Never certain, and the reason is C# rather than this parse: a
            # written type is an upper bound, so the member that actually runs
            # can be an override the parser never sees, and an interface or
            # `var` receiver names no implementation at all.
            return [
                _call_edge(owner.node_id, node.id, lineno, certain=False)
                for node in sorted(candidates, key=lambda node: node.id)
            ]

    possible = index.nodes_by_module_name.get((owner.module_id, name), ())
    if possible:
        return [
            _call_edge(owner.node_id, node.id, lineno, certain=False)
            for node in sorted(possible, key=lambda node: node.id)
        ]
    return [
        Edge(
            owner.node_id,
            f"external:{_node_text(target, parsed.raw)}",
            "call",
            certain=False,
            lineno=lineno,
            external=True,
        )
    ]


def _resolve_creation(
    owner: _Definition,
    syntax: SyntaxNode,
    parsed: _ParsedFile,
    index: _CSharpIndex,
) -> list[Edge]:
    lineno = syntax.start_point.row + 1
    written = _simple_type_name(syntax.child_by_field_name("type"), parsed.raw)
    if written is None:
        # `new()` and the built-in types name nothing this project declares.
        return [_dynamic_call_edge(owner.node_id, lineno)]
    type_ids = index.type_ids_by_name.get(written, ())
    if not type_ids:
        return [
            Edge(
                owner.node_id,
                f"external:{written}",
                "call",
                certain=False,
                lineno=lineno,
                external=True,
            )
        ]
    # A constructor node carries its type's name, and only constructors are
    # children of the type under it.
    constructors = sorted(
        (
            node
            for type_id in type_ids
            for node in index.children_by_parent.get(type_id, ())
            if node.name == written
        ),
        key=lambda node: node.id,
    )
    # Object creation is not virtual, so a single declared type with a single
    # constructor is the exact structure that runs. Overloads are the ambiguity
    # this parse cannot settle -- it reads no argument types.
    if constructors:
        certain = len(constructors) == 1 and len(type_ids) == 1
        return [
            _call_edge(owner.node_id, node.id, lineno, certain=certain)
            for node in constructors
        ]
    return [
        _call_edge(owner.node_id, type_id, lineno, certain=len(type_ids) == 1)
        for type_id in type_ids
    ]


def _members_named(
    index: _CSharpIndex,
    type_id: str | None,
    name: str,
) -> list[Node]:
    if type_id is None:
        return []
    return sorted(
        (
            node
            for node in index.children_by_parent.get(type_id, ())
            if node.name == name
        ),
        key=lambda node: node.id,
    )


def _call_edge(src: str, dst: str, lineno: int, certain: bool) -> Edge:
    return Edge(src, dst, "call", certain=certain, lineno=lineno)


def _dynamic_call_edge(src: str, lineno: int) -> Edge:
    # Scoped by the calling structure, as the `unresolved:` targets are: a bare
    # line number made two unrelated calls in two unrelated files share one
    # destination, which reads as a place they both go.
    return Edge(
        src,
        f"external:dynamic-call:{src}@{lineno}",
        "call",
        certain=False,
        lineno=lineno,
        external=True,
    )


def _entrypoint_ranks(index: _CSharpIndex) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for parsed in index.parsed_files:
        if any(
            child.type == "global_statement" and not child.has_error
            for child in parsed.tree.root_node.named_children
        ):
            ranks[parsed.module_id] = 1
        for definition in index.definitions_by_module.get(parsed.module_id, ()):
            node = index.node_by_id[definition.node_id]
            if (
                definition.declaration == "method_declaration"
                and node.name == "Main"
                and _has_modifier(definition.syntax, "static")
            ):
                ranks[definition.node_id] = 0
            elif definition.declaration in _TYPE_DECLARATIONS and _declares_tests(
                definition.syntax
            ):
                # A suite is a real way into a project and a poor first stop, so
                # it stays a candidate and ranks behind everything else.
                ranks[definition.node_id] = 9
    return ranks


def _declares_tests(type_syntax: SyntaxNode) -> bool:
    for child in _walk(type_syntax):
        if child.type != "attribute":
            continue
        name = child.child_by_field_name("name")
        if name is not None and name.text in _TEST_ATTRIBUTE_BYTES:
            return True
    return False


__all__ = ["CSharpAdapter", "CSharpParseError"]
