"""Tree-sitter JavaScript/TypeScript implementation of the language seam."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node as SyntaxNode, Parser, Tree

from codemble.adapters.base import (
    AdapterParseError,
    ConceptAnnotation,
    Edge,
    Graph,
    Node,
)
from codemble.adapters.discovery import SourceDiscoveryError, discover_source_files
from codemble.graph.finalize import GraphFinalizationError, finalize_graph

_JAVASCRIPT_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs"})
_TYPESCRIPT_EXTENSIONS = frozenset({".ts", ".tsx", ".mts", ".cts"})
_ALL_EXTENSIONS = _JAVASCRIPT_EXTENSIONS | _TYPESCRIPT_EXTENSIONS
_GENERATED_DIRECTORIES = frozenset(
    {
        ".next",
        ".nuxt",
        ".output",
        "build",
        "coverage",
        "dist",
        "out",
        "storybook-static",
        "web_dist",
    }
)
_DEFINITION_TYPES = frozenset(
    {
        "class",
        "class_declaration",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "method_definition",
        "arrow_function",
    }
)
_STARTUP_FILE_STEMS = frozenset({"app", "cli", "index", "main", "server"})

_JS_LANGUAGE = Language(tree_sitter_javascript.language())
_TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
_TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())


class JavaScriptTypeScriptParseError(AdapterParseError):
    """JavaScript/TypeScript source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
    language: str
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
    enclosing_class_id: str | None


@dataclass(frozen=True, slots=True)
class _ResolvedModule:
    module_id: str
    certain: bool


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    local_name: str
    imported_name: str | None
    targets: tuple[_ResolvedModule, ...]
    external_specifier: str | None


class JavaScriptTypeScriptAdapter:
    """Map JavaScript, JSX, TypeScript, and TSX into one deterministic graph."""

    language = "javascript-typescript"
    file_extensions = _ALL_EXTENSIONS
    ignored_directories = _GENERATED_DIRECTORIES

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact JS/TS source scope accepted by this adapter."""

        normalized = path.expanduser().resolve()
        try:
            discovery = discover_source_files(
                normalized,
                self.file_extensions,
                ignored_directories=self.ignored_directories,
            )
        except SourceDiscoveryError as error:
            raise JavaScriptTypeScriptParseError(str(error)) from error
        if not discovery.files:
            if normalized.is_file():
                raise JavaScriptTypeScriptParseError(
                    f"expected a JavaScript/TypeScript file or directory: {normalized}"
                )
            raise JavaScriptTypeScriptParseError(
                f"no JavaScript/TypeScript files found under: {normalized}"
            )
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse ``path`` using official tree-sitter grammar wheels."""

        project_root, files = self.discover(path)
        return self.parse_files(project_root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        """Parse JS/TS files already owned by this adapter."""

        parsed_files = tuple(_parse_file(file, project_root) for file in files)
        parsed_by_relative = {parsed.relative_path: parsed for parsed in parsed_files}

        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            nodes.append(_module_node(parsed))
            file_nodes, file_definitions = _collect_definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        node_by_id = {node.id: node for node in nodes}
        entrypoint_ranks = _entrypoint_ranks(parsed_files, definitions, node_by_id)
        nodes = [
            replace(node, entrypoint_rank=entrypoint_ranks.get(node.id))
            for node in nodes
        ]
        node_by_id = {node.id: node for node in nodes}

        import_edges: set[Edge] = set()
        bindings_by_module: dict[str, list[_ImportBinding]] = defaultdict(list)
        for parsed in parsed_files:
            edges, bindings = _imports_for_file(parsed, parsed_by_relative)
            import_edges.update(edges)
            bindings_by_module[parsed.module_id].extend(bindings)

        call_edges = _call_edges(
            parsed_files,
            definitions,
            node_by_id,
            bindings_by_module,
        )
        all_edges = [*import_edges, *call_edges]
        annotations = _concept_annotations(parsed_files, definitions, node_by_id)
        draft = Graph(
            nodes=tuple(nodes),
            edges=tuple(all_edges),
            entrypoint_candidates=(),
            project_root=str(project_root),
            file_hashes={
                parsed.relative_path: parsed.digest for parsed in parsed_files
            },
            concept_annotations=annotations,
            partial_files=tuple(
                parsed.relative_path
                for parsed in parsed_files
                if parsed.tree.root_node.has_error
            ),
        )
        try:
            return finalize_graph(draft, entrypoint=entrypoint)
        except GraphFinalizationError as error:
            raise JavaScriptTypeScriptParseError(str(error)) from error

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only tree-sitter-proven concepts owned by ``node``."""

        if node.partial or node.language not in {"javascript", "typescript"}:
            return []
        raw = source.encode("utf-8")
        path = Path(node.file)
        parsed = _ParsedFile(
            path=path,
            project_root=Path("."),
            relative_path=node.file,
            module_id=node.region,
            language=node.language,
            raw=raw,
            source=source,
            digest=hashlib.sha256(raw).hexdigest(),
            tree=Parser(_language_for(path.suffix.lower())).parse(raw),
        )
        module_node = _module_node(parsed)
        file_nodes, definitions = _collect_definitions(parsed)
        node_by_id = {candidate.id: candidate for candidate in (module_node, *file_nodes)}
        if node.id not in node_by_id:
            return []
        return [
            annotation
            for annotation in _concept_annotations((parsed,), definitions, node_by_id)
            if annotation.node_id == node.id
        ]


def _parse_file(path: Path, project_root: Path) -> _ParsedFile:
    raw = path.read_bytes()
    relative = path.relative_to(project_root).as_posix()
    language = "javascript" if path.suffix.lower() in _JAVASCRIPT_EXTENSIONS else "typescript"
    parser = Parser(_language_for(path.suffix.lower()))
    return _ParsedFile(
        path=path,
        project_root=project_root,
        relative_path=relative,
        module_id=f"{language}:{relative}",
        language=language,
        raw=raw,
        source=raw.decode("utf-8", errors="replace"),
        digest=hashlib.sha256(raw).hexdigest(),
        tree=parser.parse(raw),
    )


def _language_for(extension: str) -> Language:
    if extension == ".tsx":
        return _TSX_LANGUAGE
    if extension in _TYPESCRIPT_EXTENSIONS:
        return _TS_LANGUAGE
    return _JS_LANGUAGE


def _module_node(parsed: _ParsedFile) -> Node:
    line_count = max(1, len(parsed.source.splitlines()))
    return Node(
        id=parsed.module_id,
        kind="module",
        name=Path(parsed.relative_path).stem,
        language=parsed.language,
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
        enclosing_class_id: str | None,
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
                language=parsed.language,
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
                enclosing_class_id=enclosing_class_id,
            )
        )
        return node_id, next_qualname

    def visit(
        container: SyntaxNode,
        qualname: tuple[str, ...],
        parent_id: str,
        enclosing_class_id: str | None,
    ) -> None:
        for child in container.named_children:
            if child.has_error:
                continue
            if child.type in {
                "function_declaration",
                "generator_function_declaration",
            }:
                name = _field_text(child, "name", parsed.raw)
                if name:
                    node_id, child_qualname = add_definition(
                        child,
                        name,
                        "function",
                        qualname,
                        parent_id,
                        enclosing_class_id,
                    )
                    visit(child, child_qualname, node_id, enclosing_class_id)
                    continue
            if child.type == "class_declaration":
                name = _field_text(child, "name", parsed.raw)
                if name:
                    node_id, child_qualname = add_definition(
                        child,
                        name,
                        "class",
                        qualname,
                        parent_id,
                        enclosing_class_id,
                    )
                    visit(child, child_qualname, node_id, node_id)
                    continue
            if child.type == "method_definition" and enclosing_class_id:
                name = _field_text(child, "name", parsed.raw)
                if name:
                    node_id, child_qualname = add_definition(
                        child,
                        name,
                        "function",
                        qualname,
                        parent_id,
                        enclosing_class_id,
                    )
                    visit(child, child_qualname, node_id, enclosing_class_id)
                    continue
            if child.type == "variable_declarator":
                value = child.child_by_field_name("value")
                name = _field_text(child, "name", parsed.raw)
                if (
                    value is not None
                    and not value.has_error
                    and name
                    and value.type in _DEFINITION_TYPES
                ):
                    kind = "class" if value.type in {"class", "class_declaration"} else "function"
                    node_id, child_qualname = add_definition(
                        value,
                        name,
                        kind,
                        qualname,
                        parent_id,
                        enclosing_class_id,
                    )
                    visit(value, child_qualname, node_id, enclosing_class_id)
                    continue
            visit(child, qualname, parent_id, enclosing_class_id)

    visit(parsed.tree.root_node, (), parsed.module_id, None)
    return nodes, definitions


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
        "property_identifier",
        "private_property_identifier",
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
    nested_definition_ranges: set[tuple[int, int]],
) -> Iterable[SyntaxNode]:
    for child in syntax.named_children:
        if (child.start_byte, child.end_byte) in nested_definition_ranges:
            continue
        yield child
        yield from _walk_owned(child, nested_definition_ranges)


def _concept_annotations(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: list[_Definition],
    node_by_id: dict[str, Node],
) -> tuple[ConceptAnnotation, ...]:
    parsed_by_module = {parsed.module_id: parsed for parsed in parsed_files}
    definitions_by_id = {definition.node_id: definition for definition in definitions}
    definitions_by_module: dict[str, list[_Definition]] = defaultdict(list)
    nested_ranges_by_owner: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for definition in definitions:
        definitions_by_module[definition.module_id].append(definition)
        ancestor = definition.parent_id
        while ancestor in definitions_by_id:
            nested_ranges_by_owner[ancestor].add(
                (definition.syntax.start_byte, definition.syntax.end_byte)
            )
            ancestor = definitions_by_id[ancestor].parent_id

    annotations: set[ConceptAnnotation] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        module_ranges = {
            (definition.syntax.start_byte, definition.syntax.end_byte)
            for definition in definitions_by_module[parsed.module_id]
        }
        annotations.update(
            _concepts_for_owner(
                node_by_id[parsed.module_id],
                parsed.tree.root_node,
                parsed,
                module_ranges,
                include_owner=False,
            )
        )
    for definition in definitions:
        annotations.update(
            _concepts_for_owner(
                node_by_id[definition.node_id],
                definition.syntax,
                parsed_by_module[definition.module_id],
                nested_ranges_by_owner[definition.node_id],
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
    nested_definition_ranges: set[tuple[int, int]],
    *,
    include_owner: bool,
) -> set[ConceptAnnotation]:
    candidates: Iterable[SyntaxNode]
    walked = _walk_owned(syntax, nested_definition_ranges)
    candidates = (syntax, *walked) if include_owner else walked
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
    if syntax.type in {
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "method_definition",
        "arrow_function",
    } and any(child.type == "async" for child in syntax.children):
        concepts.append("async-await")
    if syntax.type == "await_expression":
        concepts.append("async-await")
    if syntax.type == "arrow_function":
        concepts.append("arrow-function")
    if syntax.type in {"object_pattern", "array_pattern"}:
        concepts.append("destructuring")
    if syntax.type == "optional_chain":
        concepts.append("optional-chaining")
    if syntax.type == "binary_expression" and any(
        child.type == "??" for child in syntax.children
    ):
        concepts.append("nullish-coalescing")
    if syntax.type in {"import_statement", "export_statement"}:
        concepts.append("module-syntax")
    if syntax.type == "type_annotation":
        concepts.append("type-annotation")
    if syntax.type == "interface_declaration":
        concepts.append("interface")
    if syntax.type in {"type_parameters", "type_arguments"}:
        concepts.append("generic")
    if syntax.type in {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}:
        concepts.append("jsx")
    return tuple(concepts)


def _imports_for_file(
    parsed: _ParsedFile,
    parsed_by_relative: dict[str, _ParsedFile],
) -> tuple[list[Edge], list[_ImportBinding]]:
    edges: list[Edge] = []
    bindings: list[_ImportBinding] = []
    root = parsed.tree.root_node
    for syntax in _walk(root):
        if syntax.has_error:
            continue
        if syntax.type in {"import_statement", "export_statement"}:
            source_node = syntax.child_by_field_name("source")
            specifier = _string_value(source_node, parsed.raw)
            if specifier is None:
                continue
            resolved = _resolve_modules(parsed, specifier, parsed_by_relative)
            edges.extend(_import_edges(parsed, syntax, specifier, resolved))
            if syntax.type == "import_statement":
                bindings.extend(
                    _bindings_from_import(syntax, parsed.raw, specifier, resolved)
                )
        if syntax.type in {"call_expression", "new_expression"}:
            function = syntax.child_by_field_name("function")
            if function is None and syntax.type == "new_expression":
                function = syntax.child_by_field_name("constructor")
            if function is None or function.type not in {"identifier", "import"}:
                continue
            function_name = _node_text(function, parsed.raw)
            if function_name not in {"require", "import"}:
                continue
            specifier = _first_string_argument(syntax, parsed.raw)
            if specifier is None:
                continue
            resolved = _resolve_modules(parsed, specifier, parsed_by_relative)
            edges.extend(_import_edges(parsed, syntax, specifier, resolved))
            if function_name == "require" and _is_module_binding(syntax):
                binding = _binding_from_require(
                    syntax, parsed.raw, specifier, resolved
                )
                if binding is not None:
                    bindings.extend(binding)
    return edges, bindings


def _is_module_binding(syntax: SyntaxNode) -> bool:
    parent = syntax.parent
    allowed = {"export_statement", "lexical_declaration", "variable_declaration", "variable_declarator"}
    while parent is not None and parent.type != "program":
        if parent.type not in allowed:
            return False
        parent = parent.parent
    return parent is not None


def _string_value(syntax: SyntaxNode | None, raw: bytes) -> str | None:
    if syntax is None or syntax.type != "string" or syntax.has_error:
        return None
    value = _node_text(syntax, raw)
    if len(value) < 2 or value[0] not in {'"', "'"} or value[-1] != value[0]:
        return None
    unquoted = value[1:-1]
    if "\\" in unquoted:
        return None
    return unquoted


def _first_string_argument(syntax: SyntaxNode, raw: bytes) -> str | None:
    arguments = syntax.child_by_field_name("arguments")
    if arguments is None:
        return None
    first = arguments.named_child(0)
    return _string_value(first, raw)


def _resolve_modules(
    parsed: _ParsedFile,
    specifier: str,
    parsed_by_relative: dict[str, _ParsedFile],
) -> tuple[_ResolvedModule, ...]:
    if not specifier.startswith("."):
        return ()
    requested = (parsed.path.parent / specifier).resolve()
    project_root = parsed.project_root
    if not requested.is_relative_to(project_root):
        return ()
    relative = requested.relative_to(project_root).as_posix()
    candidates: list[tuple[str, bool]] = []

    if relative in parsed_by_relative:
        candidates.append((relative, True))
    suffix = Path(relative).suffix.lower()
    if suffix:
        substitutions = _extension_substitutions(relative, suffix)
        candidates.extend((candidate, False) for candidate in substitutions)
    else:
        for extension in sorted(_ALL_EXTENSIONS):
            candidates.append((f"{relative}{extension}", False))
            candidates.append((f"{relative}/index{extension}", False))

    resolved: dict[str, bool] = {}
    for candidate, certain in candidates:
        target = parsed_by_relative.get(candidate)
        if target is None:
            continue
        resolved[target.module_id] = resolved.get(target.module_id, False) or certain
    return tuple(
        _ResolvedModule(module_id, certain)
        for module_id, certain in sorted(resolved.items())
    )


def _extension_substitutions(relative: str, suffix: str) -> tuple[str, ...]:
    stem = relative[: -len(suffix)]
    if suffix in {".js", ".jsx"}:
        return tuple(f"{stem}{extension}" for extension in (".ts", ".tsx"))
    if suffix == ".mjs":
        return (f"{stem}.mts",)
    if suffix == ".cjs":
        return (f"{stem}.cts",)
    return ()


def _import_edges(
    parsed: _ParsedFile,
    syntax: SyntaxNode,
    specifier: str,
    resolved: tuple[_ResolvedModule, ...],
) -> list[Edge]:
    lineno = syntax.start_point.row + 1
    if resolved:
        return [
            Edge(
                src=parsed.module_id,
                dst=target.module_id,
                kind="import",
                certain=target.certain,
                lineno=lineno,
            )
            for target in resolved
        ]
    return [
        Edge(
            src=parsed.module_id,
            dst=f"external:{specifier}",
            kind="import",
            certain=True,
            lineno=lineno,
            external=True,
        )
    ]


def _bindings_from_import(
    syntax: SyntaxNode,
    raw: bytes,
    specifier: str,
    resolved: tuple[_ResolvedModule, ...],
) -> list[_ImportBinding]:
    clause = next(
        (child for child in syntax.named_children if child.type == "import_clause"),
        None,
    )
    if clause is None:
        return []
    external = None if resolved else specifier
    bindings: list[_ImportBinding] = []
    for child in clause.named_children:
        if child.type == "identifier":
            bindings.append(
                _ImportBinding(_node_text(child, raw), "default", resolved, external)
            )
        elif child.type == "namespace_import":
            identifier = next(
                (item for item in child.named_children if item.type == "identifier"),
                None,
            )
            if identifier is not None:
                bindings.append(
                    _ImportBinding(_node_text(identifier, raw), None, resolved, external)
                )
        elif child.type == "named_imports":
            for item in child.named_children:
                if item.type != "import_specifier":
                    continue
                name = item.child_by_field_name("name")
                alias = item.child_by_field_name("alias")
                if name is None:
                    continue
                imported_name = _node_text(name, raw)
                local_name = _node_text(alias or name, raw)
                bindings.append(
                    _ImportBinding(local_name, imported_name, resolved, external)
                )
    return bindings


def _binding_from_require(
    syntax: SyntaxNode,
    raw: bytes,
    specifier: str,
    resolved: tuple[_ResolvedModule, ...],
) -> list[_ImportBinding] | None:
    parent = syntax.parent
    if parent is None or parent.type != "variable_declarator":
        return None
    value = parent.child_by_field_name("value")
    name = parent.child_by_field_name("name")
    if value != syntax or name is None:
        return None
    external = None if resolved else specifier
    if name.type == "identifier":
        return [_ImportBinding(_node_text(name, raw), None, resolved, external)]
    if name.type != "object_pattern":
        return None
    bindings: list[_ImportBinding] = []
    for child in name.named_children:
        if child.type == "shorthand_property_identifier_pattern":
            imported = _node_text(child, raw)
            bindings.append(_ImportBinding(imported, imported, resolved, external))
        elif child.type == "pair_pattern":
            key = child.child_by_field_name("key")
            value_node = child.child_by_field_name("value")
            if key is not None and value_node is not None and value_node.type == "identifier":
                bindings.append(
                    _ImportBinding(
                        _node_text(value_node, raw),
                        _node_text(key, raw),
                        resolved,
                        external,
                    )
                )
    return bindings


def _call_edges(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: list[_Definition],
    node_by_id: dict[str, Node],
    bindings_by_module: dict[str, list[_ImportBinding]],
) -> list[Edge]:
    parsed_by_module = {parsed.module_id: parsed for parsed in parsed_files}
    definitions_by_id = {definition.node_id: definition for definition in definitions}
    children_by_parent: dict[str, list[Node]] = defaultdict(list)
    nodes_by_module_name: dict[tuple[str, str], list[Node]] = defaultdict(list)
    for definition in definitions:
        node = node_by_id[definition.node_id]
        children_by_parent[definition.parent_id].append(node)
        nodes_by_module_name[(definition.module_id, node.name)].append(node)
    nested_ranges_by_owner: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for definition in definitions:
        ancestor = definition.parent_id
        while ancestor in definitions_by_id:
            nested_ranges_by_owner[ancestor].add(
                (definition.syntax.start_byte, definition.syntax.end_byte)
            )
            ancestor = definitions_by_id[ancestor].parent_id

    local_bindings_by_owner = {
        definition.node_id: _local_binding_names(
            definition.syntax,
            parsed_by_module[definition.module_id].raw,
            nested_ranges_by_owner[definition.node_id],
        )
        for definition in definitions
    }

    edges: list[Edge] = []
    for definition in definitions:
        parsed = parsed_by_module[definition.module_id]
        binding_map = {
            binding.local_name: binding
            for binding in bindings_by_module[definition.module_id]
        }
        for syntax in _walk_owned(
            definition.syntax,
            nested_ranges_by_owner[definition.node_id],
        ):
            if syntax.has_error or syntax.type not in {"call_expression", "new_expression"}:
                continue
            if _is_import_loader_call(syntax, parsed.raw):
                continue
            edges.extend(
                _resolve_call(
                    definition,
                    syntax,
                    parsed.raw,
                    binding_map,
                    node_by_id,
                    nodes_by_module_name,
                    children_by_parent,
                    local_bindings_by_owner[definition.node_id],
                )
            )
    return edges


def _is_import_loader_call(syntax: SyntaxNode, raw: bytes) -> bool:
    function = syntax.child_by_field_name("function")
    if function is None:
        return False
    return function.type == "import" or (
        function.type == "identifier" and _node_text(function, raw) == "require"
    )


def _resolve_call(
    definition: _Definition,
    syntax: SyntaxNode,
    raw: bytes,
    bindings: dict[str, _ImportBinding],
    node_by_id: dict[str, Node],
    nodes_by_module_name: dict[tuple[str, str], list[Node]],
    children_by_parent: dict[str, list[Node]],
    local_binding_names: set[str],
) -> list[Edge]:
    target = syntax.child_by_field_name("function")
    if target is None and syntax.type == "new_expression":
        target = syntax.child_by_field_name("constructor")
    lineno = syntax.start_point.row + 1
    if target is None:
        return [_dynamic_call_edge(definition.node_id, lineno)]

    if target.type == "identifier":
        name = _node_text(target, raw)
        nested = [
            node
            for node in children_by_parent[definition.node_id]
            if node.name == name
        ]
        if nested:
            return [
                _call_edge(
                    definition.node_id,
                    candidate.id,
                    lineno,
                    certain=len(nested) == 1,
                )
                for candidate in sorted(nested, key=lambda node: node.id)
            ]
        if name in local_binding_names:
            return [
                Edge(
                    definition.node_id,
                    f"unresolved:{definition.node_id}:{name}",
                    "call",
                    certain=False,
                    lineno=lineno,
                )
            ]
        local = _local_call_candidates(
            definition, name, nodes_by_module_name, children_by_parent
        )
        if local:
            return [
                _call_edge(
                    definition.node_id,
                    candidate.id,
                    lineno,
                    certain=len(local) == 1,
                )
                for candidate in local
            ]
        binding = bindings.get(name)
        if binding is not None:
            return _binding_call_edges(
                definition.node_id,
                binding,
                binding.imported_name,
                lineno,
                node_by_id,
            )
        return [
            Edge(
                definition.node_id,
                f"unresolved:{definition.module_id}:{name}",
                "call",
                certain=False,
                lineno=lineno,
            )
        ]

    if target.type == "member_expression":
        object_node = target.child_by_field_name("object")
        property_node = target.child_by_field_name("property")
        if property_node is None:
            return [_dynamic_call_edge(definition.node_id, lineno)]
        name = _node_text(property_node, raw)
        if object_node is not None and object_node.type in {"this", "super"}:
            candidates = [
                node
                for node in children_by_parent.get(
                    definition.enclosing_class_id or "", []
                )
                if node.name == name
            ]
            if candidates:
                return [
                    _call_edge(
                        definition.node_id,
                        candidate.id,
                        lineno,
                        certain=len(candidates) == 1,
                    )
                    for candidate in sorted(candidates, key=lambda node: node.id)
                ]
        if object_node is not None and object_node.type == "identifier":
            object_name = _node_text(object_node, raw)
            binding = None if object_name in local_binding_names else bindings.get(object_name)
            if binding is not None and binding.imported_name is None:
                return _binding_call_edges(
                    definition.node_id,
                    binding,
                    name,
                    lineno,
                    node_by_id,
                )
        possible = nodes_by_module_name.get((definition.module_id, name), [])
        if possible:
            return [
                _call_edge(definition.node_id, node.id, lineno, certain=False)
                for node in sorted(possible, key=lambda node: node.id)
            ]
        dotted = _node_text(target, raw)
        return [
            Edge(
                definition.node_id,
                f"external:{dotted}",
                "call",
                certain=False,
                lineno=lineno,
                external=True,
            )
        ]

    return [_dynamic_call_edge(definition.node_id, lineno)]


def _local_call_candidates(
    definition: _Definition,
    name: str,
    nodes_by_module_name: dict[tuple[str, str], list[Node]],
    children_by_parent: dict[str, list[Node]],
) -> list[Node]:
    siblings = [node for node in children_by_parent[definition.parent_id] if node.name == name]
    if siblings:
        return sorted(siblings, key=lambda node: node.id)
    return sorted(
        nodes_by_module_name.get((definition.module_id, name), []),
        key=lambda node: node.id,
    )


def _local_binding_names(
    syntax: SyntaxNode,
    raw: bytes,
    nested_definition_ranges: set[tuple[int, int]],
) -> set[str]:
    names: set[str] = set()
    for field in ("parameter", "parameters"):
        parameter_node = syntax.child_by_field_name(field)
        if parameter_node is not None:
            names.update(_identifier_texts(parameter_node, raw))
    for child in _walk_owned(syntax, nested_definition_ranges):
        if child.type == "variable_declarator":
            pattern = child.child_by_field_name("name")
            if pattern is not None:
                names.update(_identifier_texts(pattern, raw))
        elif child.type == "catch_clause":
            parameter = child.child_by_field_name("parameter")
            if parameter is not None:
                names.update(_identifier_texts(parameter, raw))
    return names


def _identifier_texts(syntax: SyntaxNode, raw: bytes) -> set[str]:
    nodes = (syntax, *_walk(syntax))
    return {
        _node_text(node, raw)
        for node in nodes
        if node.type in {"identifier", "shorthand_property_identifier_pattern"}
    }


def _binding_call_edges(
    src: str,
    binding: _ImportBinding,
    imported_name: str | None,
    lineno: int,
    node_by_id: dict[str, Node],
) -> list[Edge]:
    if binding.external_specifier is not None:
        suffix = f".{imported_name}" if imported_name else ""
        return [
            Edge(
                src,
                f"external:{binding.external_specifier}{suffix}",
                "call",
                certain=False,
                lineno=lineno,
                external=True,
            )
        ]
    candidates: list[tuple[Node, bool]] = []
    if imported_name and imported_name != "default":
        for target in binding.targets:
            for node in node_by_id.values():
                if node.region == target.module_id and node.name == imported_name:
                    candidates.append((node, target.certain))
    if candidates:
        unambiguous = len(candidates) == 1
        return [
            _call_edge(
                src,
                node.id,
                lineno,
                certain=unambiguous and path_certain,
            )
            for node, path_certain in sorted(candidates, key=lambda item: item[0].id)
        ]
    target_names = ",".join(target.module_id for target in binding.targets)
    suffix = imported_name or "namespace"
    return [
        Edge(
            src,
            f"unresolved:{target_names}:{suffix}",
            "call",
            certain=False,
            lineno=lineno,
        )
    ]


def _call_edge(src: str, dst: str, lineno: int, certain: bool) -> Edge:
    return Edge(src, dst, "call", certain=certain, lineno=lineno)


def _dynamic_call_edge(src: str, lineno: int) -> Edge:
    return Edge(
        src,
        f"external:dynamic-call@{lineno}",
        "call",
        certain=False,
        lineno=lineno,
        external=True,
    )


def _entrypoint_ranks(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: list[_Definition],
    node_by_id: dict[str, Node],
) -> dict[str, int]:
    ranks: dict[str, int] = {}
    definitions_by_module: dict[str, list[_Definition]] = defaultdict(list)
    for definition in definitions:
        definitions_by_module[definition.module_id].append(definition)
        if node_by_id[definition.node_id].name == "main":
            ranks[definition.node_id] = 1

    for parsed in parsed_files:
        module_rank: int | None = None
        direct_children = [
            child for child in parsed.tree.root_node.named_children if not child.has_error
        ]
        for child in direct_children:
            if child.type == "if_statement" and _is_entrypoint_guard(child, parsed.raw):
                module_rank = 0
                break
        if module_rank is None and _has_top_level_startup_call(
            parsed,
            definitions_by_module[parsed.module_id],
        ):
            module_rank = 2
        if module_rank is None and parsed.path.stem.lower() in _STARTUP_FILE_STEMS:
            module_rank = 3
        if module_rank is not None:
            ranks[parsed.module_id] = module_rank
    return ranks


def _is_entrypoint_guard(syntax: SyntaxNode, raw: bytes) -> bool:
    condition = syntax.child_by_field_name("condition")
    if condition is None:
        return False
    normalized = "".join(_node_text(condition, raw).split()).strip("()")
    return normalized in {
        "require.main===module",
        "module===require.main",
        "require.main==module",
        "module==require.main",
        "import.meta.main",
    }


def _has_top_level_startup_call(
    parsed: _ParsedFile,
    definitions: list[_Definition],
) -> bool:
    nested_ranges = {
        (definition.syntax.start_byte, definition.syntax.end_byte)
        for definition in definitions
    }
    for syntax in _walk_owned(parsed.tree.root_node, nested_ranges):
        if syntax.has_error or syntax.type != "call_expression":
            continue
        function = syntax.child_by_field_name("function")
        if function is None:
            continue
        if function.type == "identifier" and _node_text(function, parsed.raw) == "main":
            return True
        if function.type != "member_expression":
            continue
        object_node = function.child_by_field_name("object")
        property_node = function.child_by_field_name("property")
        if object_node is None or property_node is None:
            continue
        property_name = _node_text(property_node, parsed.raw)
        object_text = _node_text(object_node, parsed.raw)
        if property_name == "listen" or (
            property_name == "serve" and object_text in {"Bun", "Deno"}
        ) or (
            property_name == "render" and object_text.startswith("createRoot(")
        ):
            return True
    return False


__all__ = ["JavaScriptTypeScriptAdapter", "JavaScriptTypeScriptParseError"]
