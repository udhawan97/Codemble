"""Tree-sitter PHP implementation of Codemble's language seam."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_php
from tree_sitter import Language, Parser, Tree
from tree_sitter import Node as SyntaxNode

from codemble.adapters.base import AdapterParseError, ConceptAnnotation, Edge, Graph, Node
from codemble.adapters.parse_progress import note_file_parsed
from codemble.adapters.tree_sitter_core import _TreeSitterAdapterCore

_LANGUAGE = Language(tree_sitter_php.language_php())
_EXTENSIONS = frozenset({".php"})
_IGNORED_DIRECTORIES = frozenset({"cache", "coverage", "storage", "vendor"})
_TYPE_DECLARATIONS = frozenset(
    {
        "class_declaration",
        "enum_declaration",
        "interface_declaration",
        "trait_declaration",
    }
)
_CALLABLE_DECLARATIONS = frozenset({"function_definition", "method_declaration"})
_NAME_EXPRESSIONS = frozenset({"name", "qualified_name", "relative_name"})
_INCLUDE_EXPRESSIONS = frozenset(
    {
        "include_expression",
        "include_once_expression",
        "require_expression",
        "require_once_expression",
    }
)


class PHPParseError(AdapterParseError):
    """PHP source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
    namespace: tuple[str, ...]
    raw: bytes
    source: str
    digest: str
    tree: Tree


@dataclass(frozen=True, slots=True)
class _Definition:
    node_id: str
    syntax: SyntaxNode
    module_id: str
    parent_id: str
    path: tuple[str, ...]
    callable: bool
    method: bool


class PHPAdapter(_TreeSitterAdapterCore):
    """Map PHP declarations and conservative relationships into one graph."""

    language = "php"
    file_extensions = _EXTENSIONS
    ignored_directories = _IGNORED_DIRECTORIES
    _parse_error_type = PHPParseError
    _source_label = "PHP"

    def _parse_owned_file(self, path: Path, project_root: Path) -> _ParsedFile:
        raw = path.read_bytes()
        tree = Parser(_LANGUAGE).parse(raw)
        relative = path.relative_to(project_root).as_posix()
        parsed = _ParsedFile(
            path=path,
            project_root=project_root,
            relative_path=relative,
            module_id=f"php:{relative}",
            namespace=_namespace(tree.root_node, raw),
            raw=raw,
            source=raw.decode("utf-8", errors="replace"),
            digest=hashlib.sha256(raw).hexdigest(),
            tree=tree,
        )
        note_file_parsed()
        return parsed

    def _build_graph_draft(
        self,
        project_root: Path,
        parsed_files: tuple[_ParsedFile, ...],
    ) -> Graph:
        declared_bins = _composer_bins(project_root)
        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            module = _module_node(parsed)
            if parsed.relative_path in declared_bins:
                # composer.json's `bin` table is explicit packaging evidence.
                # It ranks the parsed file but creates no source node or edge.
                module = replace(module, entrypoint_rank=0)
            nodes.append(module)
            if parsed.tree.root_node.has_error:
                continue
            file_nodes, file_definitions = _definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        definition_tuple = tuple(definitions)
        partial_files = tuple(
            parsed.relative_path
            for parsed in parsed_files
            if parsed.tree.root_node.has_error
        )
        return Graph(
            nodes=tuple(nodes),
            edges=tuple(
                sorted(
                    {
                        *_import_edges(parsed_files, definition_tuple),
                        *_call_edges(parsed_files, definition_tuple),
                    },
                    key=lambda edge: (
                        edge.src,
                        edge.dst,
                        edge.kind,
                        edge.lineno,
                        edge.certain,
                        edge.external,
                    ),
                )
            ),
            entrypoint_candidates=(),
            project_root=str(project_root),
            file_hashes={parsed.relative_path: parsed.digest for parsed in parsed_files},
            concept_annotations=_concept_annotations(parsed_files, definition_tuple),
            partial_files=partial_files,
        )

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only PHP constructs proven inside ``node``."""

        if node.partial or node.language != self.language:
            return []
        raw = source.encode("utf-8")
        tree = Parser(_LANGUAGE).parse(raw)
        parsed = _ParsedFile(
            path=Path(node.file),
            project_root=Path("."),
            relative_path=node.file,
            module_id=node.region,
            namespace=_namespace(tree.root_node, raw),
            raw=raw,
            source=source,
            digest=hashlib.sha256(raw).hexdigest(),
            tree=tree,
        )
        if tree.root_node.has_error:
            return []
        _, definitions = _definitions(parsed)
        return [
            annotation
            for annotation in _concept_annotations((parsed,), tuple(definitions))
            if annotation.node_id == node.id
        ]


def _module_node(parsed: _ParsedFile) -> Node:
    lines = max(1, len(parsed.source.splitlines()))
    return Node(
        id=parsed.module_id,
        kind="module",
        name=Path(parsed.relative_path).stem,
        language="php",
        file=parsed.relative_path,
        lineno=1,
        end_lineno=lines,
        loc=lines,
        region=parsed.module_id,
        partial=parsed.tree.root_node.has_error,
    )


def _definitions(parsed: _ParsedFile) -> tuple[list[Node], list[_Definition]]:
    nodes: list[Node] = []
    definitions: list[_Definition] = []
    used_ids = {parsed.module_id}

    def visit(
        syntax: SyntaxNode,
        namespace: tuple[str, ...],
        owner_path: tuple[str, ...],
        parent_id: str,
    ) -> None:
        active_namespace = namespace
        for child in syntax.named_children:
            if child.has_error:
                continue
            if child.type == "namespace_definition":
                name_node = child.child_by_field_name("name")
                declared_namespace = (
                    _qualified_name(name_node, parsed.raw) if name_node is not None else ()
                )
                body = child.child_by_field_name("body")
                if body is not None:
                    # Braced namespaces own only their body. A declaration after
                    # the closing brace returns to the surrounding namespace.
                    visit(body, declared_namespace, (), parsed.module_id)
                else:
                    # Semicolon namespaces own following siblings until the next
                    # namespace declaration in this same statement list.
                    active_namespace = declared_namespace
                continue
            if child.type in _TYPE_DECLARATIONS:
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    visit(child, active_namespace, owner_path, parent_id)
                    continue
                name = _text(name_node, parsed.raw)
                path = (*active_namespace, *owner_path, name)
                base_id = f"{parsed.module_id}::{'.'.join(path)}"
                node_id = _unique_id(base_id, child, used_ids)
                used_ids.add(node_id)
                nodes.append(_node(parsed, child, node_id, "class", name))
                definitions.append(
                    _Definition(
                        node_id=node_id,
                        syntax=child,
                        module_id=parsed.module_id,
                        parent_id=parent_id,
                        path=path,
                        callable=False,
                        method=False,
                    )
                )
                visit(child, active_namespace, (*owner_path, name), node_id)
                continue
            if child.type in _CALLABLE_DECLARATIONS:
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    visit(child, active_namespace, owner_path, parent_id)
                    continue
                name = _text(name_node, parsed.raw)
                path = (*active_namespace, *owner_path, name)
                base_id = f"{parsed.module_id}::{'.'.join(path)}"
                node_id = _unique_id(base_id, child, used_ids)
                used_ids.add(node_id)
                nodes.append(_node(parsed, child, node_id, "function", name))
                definitions.append(
                    _Definition(
                        node_id=node_id,
                        syntax=child,
                        module_id=parsed.module_id,
                        parent_id=parent_id,
                        path=path,
                        callable=True,
                        method=child.type == "method_declaration",
                    )
                )
                visit(child, active_namespace, owner_path, node_id)
                continue
            visit(child, active_namespace, owner_path, parent_id)

    visit(parsed.tree.root_node, (), (), parsed.module_id)
    return nodes, definitions


def _node(parsed: _ParsedFile, syntax: SyntaxNode, node_id: str, kind: str, name: str) -> Node:
    start, end = _span(syntax)
    return Node(
        id=node_id,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        language="php",
        file=parsed.relative_path,
        lineno=start,
        end_lineno=end,
        loc=end - start + 1,
        region=parsed.module_id,
    )


def _namespace(root: SyntaxNode, raw: bytes) -> tuple[str, ...]:
    for syntax in root.named_children:
        if syntax.type != "namespace_definition" or syntax.has_error:
            continue
        name = syntax.child_by_field_name("name")
        if name is not None:
            return _qualified_name(name, raw)
    return ()


def _composer_bins(project_root: Path) -> frozenset[str]:
    manifest = project_root / "composer.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    bins = data.get("bin")
    if isinstance(bins, str):
        bins = [bins]
    if not isinstance(bins, list):
        return frozenset()
    return frozenset(
        Path(value).as_posix().removeprefix("./")
        for value in bins
        if isinstance(value, str) and value.strip()
    )


def _import_edges(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: tuple[_Definition, ...],
) -> set[Edge]:
    by_file = {parsed.path.resolve(): parsed.module_id for parsed in parsed_files}
    types: dict[tuple[str, ...], list[_Definition]] = {}
    for definition in definitions:
        if not definition.callable:
            types.setdefault(definition.path, []).append(definition)

    edges: set[Edge] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        use_paths = {syntax.id: path for syntax, path, _ in _namespace_use_clauses(parsed)}
        for syntax in _walk(parsed.tree.root_node):
            if syntax.type == "namespace_use_clause" and not syntax.has_error:
                path = use_paths.get(syntax.id)
                if not path:
                    continue
                matches = types.get(path, [])
                edges.add(
                    Edge(
                        src=parsed.module_id,
                        dst=(
                            matches[0].node_id
                            if len(matches) == 1
                            else f"external:{_display_path(path)}"
                        ),
                        kind="import",
                        certain=True,
                        lineno=syntax.start_point.row + 1,
                        external=len(matches) != 1,
                    )
                )
            elif syntax.type in _INCLUDE_EXPRESSIONS and not syntax.has_error:
                literal = _include_literal(syntax, parsed.raw)
                lineno = syntax.start_point.row + 1
                if literal is None:
                    edges.add(
                        Edge(
                            src=parsed.module_id,
                            dst=f"external:php.{syntax.type}.dynamic",
                            kind="import",
                            certain=False,
                            lineno=lineno,
                            external=True,
                        )
                    )
                    continue
                target = (parsed.path.parent / literal).resolve()
                module_id = by_file.get(target)
                edges.add(
                    Edge(
                        src=parsed.module_id,
                        dst=module_id or f"external:{literal}",
                        kind="import",
                        certain=True,
                        lineno=lineno,
                        external=module_id is None,
                    )
                )
    return edges


def _call_edges(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: tuple[_Definition, ...],
) -> set[Edge]:
    types: dict[tuple[str, ...], list[_Definition]] = {}
    functions: dict[tuple[str, ...], list[_Definition]] = {}
    methods: dict[tuple[tuple[str, ...], str], list[_Definition]] = {}
    for definition in definitions:
        if not definition.callable:
            types.setdefault(definition.path, []).append(definition)
        elif definition.method:
            methods.setdefault((definition.path[:-1], definition.path[-1]), []).append(definition)
        else:
            functions.setdefault(definition.path, []).append(definition)

    edges: set[Edge] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        aliases_by_namespace = _use_aliases(parsed)
        file_definitions = [item for item in definitions if item.module_id == parsed.module_id]
        for syntax in _walk(parsed.tree.root_node):
            if syntax.has_error:
                continue
            targets: list[_Definition] = []
            label: str | None = None
            namespace = _namespace_at(syntax, parsed.raw)
            aliases = aliases_by_namespace.get(namespace, {})
            if syntax.type == "object_creation_expression":
                name_node = next(
                    (
                        child
                        for child in syntax.named_children
                        if child.type in _NAME_EXPRESSIONS
                    ),
                    None,
                )
                if name_node is not None:
                    path = _resolve_syntax_name(name_node, parsed.raw, namespace, aliases)
                    targets = types.get(path, [])
                    label = f"new {_display_path(path)}"
            elif syntax.type == "scoped_call_expression":
                scope = syntax.child_by_field_name("scope")
                name = syntax.child_by_field_name("name")
                if scope is not None and name is not None:
                    path = _resolve_syntax_name(scope, parsed.raw, namespace, aliases)
                    method_name = _text(name, parsed.raw)
                    targets = methods.get((path, method_name), [])
                    label = f"{_display_path(path)}::{method_name}"
            elif syntax.type == "function_call_expression":
                function = syntax.child_by_field_name("function")
                if function is not None and function.type in _NAME_EXPRESSIONS:
                    path = _resolve_syntax_name(function, parsed.raw, namespace, aliases)
                    targets = functions.get(path, [])
                    label = "\\".join(path)
            elif syntax.type in {"member_call_expression", "nullsafe_member_call_expression"}:
                object_node = syntax.child_by_field_name("object")
                name = syntax.child_by_field_name("name")
                owner = _owner(syntax, file_definitions)
                if (
                    object_node is not None
                    and name is not None
                    and _text(object_node, parsed.raw) == "$this"
                    and owner is not None
                    and owner.method
                ):
                    method_name = _text(name, parsed.raw)
                    targets = methods.get((owner.path[:-1], method_name), [])
                    label = f"$this->{method_name}"
                elif object_node is not None and name is not None:
                    receiver = (
                        _text(object_node, parsed.raw)
                        if object_node.type in {"name", "variable_name"}
                        else "result"
                    )
                    operator = "?->" if syntax.type.startswith("nullsafe_") else "->"
                    label = f"{receiver}{operator}{_text(name, parsed.raw)}"
            else:
                continue

            if label is None:
                continue
            owner = _owner(syntax, file_definitions)
            src = owner.node_id if owner is not None else parsed.module_id
            if len(targets) == 1:
                # PHP supports late static binding, inheritance, aliases and
                # runtime autoloaders. A parser match is useful, but possible.
                edges.add(
                    Edge(
                        src=src,
                        dst=targets[0].node_id,
                        kind="call",
                        certain=False,
                        lineno=syntax.start_point.row + 1,
                    )
                )
            else:
                edges.add(
                    Edge(
                        src=src,
                        dst=f"external:{label}",
                        kind="call",
                        certain=False,
                        lineno=syntax.start_point.row + 1,
                        external=True,
                    )
                )
    return edges


def _use_aliases(
    parsed: _ParsedFile,
) -> dict[tuple[str, ...], dict[str, tuple[str, ...]]]:
    aliases: dict[tuple[str, ...], dict[str, tuple[str, ...]]] = {}
    for syntax, path, local in _namespace_use_clauses(parsed):
        aliases.setdefault(_namespace_at(syntax, parsed.raw), {})[local] = path
    return aliases


def _resolve_syntax_name(
    syntax: SyntaxNode,
    raw: bytes,
    namespace: tuple[str, ...],
    aliases: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    path = _qualified_name(syntax, raw)
    if not path:
        return path
    prefix = syntax.child_by_field_name("prefix")
    prefix_text = _text(prefix, raw) if prefix is not None else ""
    source = _text(syntax, raw)
    # A leading backslash is fully qualified and must never inherit the active
    # namespace. `namespace\\Name` is explicitly relative and bypasses imports.
    if source.startswith("\\") or prefix_text == "\\":
        return path
    if syntax.type == "relative_name" or prefix_text == "namespace":
        return (*namespace, *path)
    if path[0] in aliases:
        return (*aliases[path[0]], *path[1:])
    return (*namespace, *path)


def _namespace_use_clauses(
    parsed: _ParsedFile,
) -> tuple[tuple[SyntaxNode, tuple[str, ...], str], ...]:
    """Return absolute import paths and their local aliases, including groups."""

    clauses: list[tuple[SyntaxNode, tuple[str, ...], str]] = []
    for syntax in _walk(parsed.tree.root_node):
        if syntax.type != "namespace_use_clause" or syntax.has_error:
            continue
        alias = syntax.child_by_field_name("alias")
        target = next(
            (
                child
                for child in syntax.named_children
                if child is not alias and child.type in _NAME_EXPRESSIONS
            ),
            None,
        )
        if target is None:
            continue
        path = _qualified_name(target, parsed.raw)
        parent = syntax.parent
        if parent is not None and parent.type == "namespace_use_group":
            declaration = parent.parent
            prefix = (
                next(
                    (
                        child
                        for child in declaration.named_children
                        if child.type in {"namespace_name", "qualified_name"}
                    ),
                    None,
                )
                if declaration is not None
                else None
            )
            if prefix is not None:
                path = (*_qualified_name(prefix, parsed.raw), *path)
        if not path:
            continue
        local = _text(alias, parsed.raw) if alias is not None else path[-1]
        clauses.append((syntax, path, local))
    return tuple(clauses)


def _namespace_at(syntax: SyntaxNode, raw: bytes) -> tuple[str, ...]:
    """Return the PHP namespace that owns one syntax node.

    Braced namespaces are ancestors. Semicolon namespaces are stateful across
    following root siblings, so the last preceding unbraced declaration owns
    the node. Keeping this syntax-local prevents a legal multi-namespace file
    from assigning every declaration to the first namespace it contains.
    """

    current: SyntaxNode | None = syntax
    root = syntax
    while current is not None:
        root = current
        if current.type == "namespace_definition":
            name = current.child_by_field_name("name")
            return _qualified_name(name, raw) if name is not None else ()
        current = current.parent

    namespace: tuple[str, ...] = ()
    for child in root.named_children:
        if child.start_byte > syntax.start_byte:
            break
        if child.type != "namespace_definition" or child.has_error:
            continue
        if child.child_by_field_name("body") is not None:
            continue
        name = child.child_by_field_name("name")
        namespace = _qualified_name(name, raw) if name is not None else ()
    return namespace


def _concept_annotations(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: tuple[_Definition, ...],
) -> tuple[ConceptAnnotation, ...]:
    concepts = {
        "attribute_list": "attribute",
        "arrow_function": "arrow-function",
        "enum_declaration": "enum",
        "match_expression": "match-expression",
        "nullsafe_member_access_expression": "nullsafe-access",
        "nullsafe_member_call_expression": "nullsafe-access",
        "union_type": "union-type",
    }
    annotations: set[ConceptAnnotation] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        file_definitions = [item for item in definitions if item.module_id == parsed.module_id]
        for syntax in _walk(parsed.tree.root_node):
            concept = concepts.get(syntax.type)
            if (
                concept is None
                and syntax.type == "argument"
                and syntax.child_by_field_name("name") is not None
            ):
                concept = "named-argument"
            if concept is None:
                continue
            owner = _owner(syntax, file_definitions)
            node_id = owner.node_id if owner is not None else parsed.module_id
            start, end = _span(syntax)
            annotations.add(
                ConceptAnnotation(
                    node_id=node_id,
                    language="php",
                    concept=concept,
                    lineno=start,
                    end_lineno=end,
                    snippet=_line_snippet(parsed.source, start),
                )
            )
    return tuple(
        sorted(annotations, key=lambda item: (item.node_id, item.lineno, item.concept))
    )


def _include_literal(syntax: SyntaxNode, raw: bytes) -> str | None:
    named = list(syntax.named_children)
    if len(named) != 1:
        return None
    expression = named[0]
    if expression.type == "string":
        return _string_content(expression, raw)
    if expression.type != "binary_expression" or "." not in _text(expression, raw):
        return None
    strings = [child for child in _walk(expression) if child.type == "string"]
    names = {_text(child, raw) for child in _walk(expression) if child.type == "name"}
    if len(strings) == 1 and "__DIR__" in names:
        content = _string_content(strings[0], raw)
        return None if content is None else content.lstrip("/")
    return None


def _string_content(syntax: SyntaxNode, raw: bytes) -> str | None:
    if any(child.type in {"encapsed_string", "variable_name"} for child in _walk(syntax)):
        return None
    content = next((child for child in syntax.named_children if child.type == "string_content"), None)
    return None if content is None else _text(content, raw)


def _qualified_name(syntax: SyntaxNode, raw: bytes) -> tuple[str, ...]:
    names = [
        _text(child, raw)
        for child in _walk(syntax)
        if child.type == "name" and child is not syntax
    ]
    if syntax.type == "name":
        return (_text(syntax, raw),)
    return tuple(names)


def _display_path(path: tuple[str, ...]) -> str:
    return "\\".join(path)


def _owner(syntax: SyntaxNode, definitions: list[_Definition]) -> _Definition | None:
    containing = [
        item
        for item in definitions
        if item.syntax.start_byte <= syntax.start_byte
        and syntax.end_byte <= item.syntax.end_byte
    ]
    return min(
        containing,
        key=lambda item: item.syntax.end_byte - item.syntax.start_byte,
        default=None,
    )


def _walk(root: SyntaxNode):
    yield root
    for child in root.named_children:
        yield from _walk(child)


def _unique_id(base: str, syntax: SyntaxNode, used: set[str]) -> str:
    if base not in used:
        return base
    candidate = f"{base}@{syntax.start_point.row + 1}"
    suffix = 2
    while candidate in used:
        candidate = f"{base}@{syntax.start_point.row + 1}.{suffix}"
        suffix += 1
    return candidate


def _span(syntax: SyntaxNode) -> tuple[int, int]:
    return syntax.start_point.row + 1, syntax.end_point.row + 1


def _text(syntax: SyntaxNode, raw: bytes) -> str:
    return raw[syntax.start_byte : syntax.end_byte].decode("utf-8", errors="replace")


def _line_snippet(source: str, line: int) -> str:
    lines = source.splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


__all__ = ["PHPAdapter", "PHPParseError"]
