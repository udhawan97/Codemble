"""Tree-sitter JavaScript/TypeScript implementation of the language seam."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser, Tree
from tree_sitter import Node as SyntaxNode

from codemble.adapters.base import (
    AdapterParseError,
    ConceptAnnotation,
    Edge,
    Graph,
    Node,
    RoleEvidence,
)
from codemble.adapters.parse_progress import note_file_parsed
from codemble.adapters.role_rules import native_entrypoint_roles, roles_from_complete_files
from codemble.adapters.tree_sitter_core import _TreeSitterAdapterCore

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

# Names the language or its host environment provides, which therefore leave
# the project exactly as `Math.max` already did. Python's adapter has said this
# about its own builtins from the start; JS/TS had no equivalent, so `new Set()`
# was reported as `unresolved:javascript:graphData.js:Set` -- which reads as
# "Codemble believes this is yours and could not find it". A coverage gap and a
# project boundary are different facts, and this is the channel graph schema 8
# exists to keep honest. Measured on `web/src`, 45% of unresolved call targets
# were these.
#
# Deliberately not exhaustive and deliberately not inferred: every entry is a
# global with no possible project definition. A name absent from this table
# falls through to the unresolved answer, which is the safe direction -- a
# missing entry costs precision, whereas a wrong one would silently reclassify
# a learner's own code as somebody else's.
_ECMASCRIPT_GLOBALS = frozenset(
    {
        # Values and collections
        "Array", "BigInt", "Boolean", "Map", "Number", "Object", "Proxy",
        "Reflect", "RegExp", "Set", "String", "Symbol", "WeakMap", "WeakRef",
        "WeakSet",
        # Errors
        "AggregateError", "Error", "EvalError", "RangeError", "ReferenceError",
        "SyntaxError", "TypeError", "URIError",
        # Async and time
        "AbortController", "AbortSignal", "Date", "Promise", "queueMicrotask",
        "setInterval", "setTimeout", "clearInterval", "clearTimeout",
        "requestAnimationFrame", "cancelAnimationFrame", "requestIdleCallback",
        # Typed arrays and binary
        "ArrayBuffer", "BigInt64Array", "DataView", "Float32Array",
        "Float64Array", "Int8Array", "Int16Array", "Int32Array", "SharedArrayBuffer",
        "Uint8Array", "Uint8ClampedArray", "Uint16Array", "Uint32Array",
        # Encoding and parsing
        "decodeURI", "decodeURIComponent", "encodeURI", "encodeURIComponent",
        "isFinite", "isNaN", "parseFloat", "parseInt", "structuredClone",
        "TextDecoder", "TextEncoder", "URL", "URLSearchParams",
        # Host objects a browser or Node supplies
        "Blob", "CustomEvent", "DOMException", "Event", "EventTarget", "File",
        "FileReader", "FormData", "Headers", "Image", "IntersectionObserver",
        "MutationObserver", "Request", "Response", "ResizeObserver", "Worker",
        "fetch",
    }
)

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


@dataclass(frozen=True, slots=True)
class _SyntaxEvidenceIndex:
    """Reusable ownership and lookup evidence derived from one syntax parse."""

    parsed_files: tuple[_ParsedFile, ...]
    definitions: tuple[_Definition, ...]
    nodes: tuple[Node, ...]
    parsed_by_relative: dict[str, _ParsedFile]
    parsed_by_module: dict[str, _ParsedFile]
    definitions_by_module: dict[str, tuple[_Definition, ...]]
    node_by_id: dict[str, Node]
    children_by_parent: dict[str, tuple[Node, ...]]
    nodes_by_module_name: dict[tuple[str, str], tuple[Node, ...]]
    nested_ranges_by_owner: dict[str, frozenset[tuple[int, int]]]
    local_bindings_by_owner: dict[str, frozenset[str]]

    @classmethod
    def build(
        cls,
        parsed_files: tuple[_ParsedFile, ...],
        definitions: tuple[_Definition, ...],
        nodes: tuple[Node, ...],
    ) -> _SyntaxEvidenceIndex:
        parsed_by_relative = {
            parsed.relative_path: parsed for parsed in parsed_files
        }
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
        return cls(
            parsed_files=parsed_files,
            definitions=definitions,
            nodes=nodes,
            parsed_by_relative=parsed_by_relative,
            parsed_by_module=parsed_by_module,
            definitions_by_module={
                module_id: tuple(module_definitions)
                for module_id, module_definitions in definitions_by_module_lists.items()
            },
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            nodes_by_module_name=nodes_by_module_name,
            nested_ranges_by_owner=frozen_ranges,
            local_bindings_by_owner=local_bindings_by_owner,
        )

    def with_nodes(self, nodes: tuple[Node, ...]) -> _SyntaxEvidenceIndex:
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


class JavaScriptTypeScriptAdapter(_TreeSitterAdapterCore):
    """Map JavaScript, JSX, TypeScript, and TSX into one deterministic graph."""

    language = "javascript-typescript"
    file_extensions = _ALL_EXTENSIONS
    ignored_directories = _GENERATED_DIRECTORIES
    _parse_error_type = JavaScriptTypeScriptParseError
    _source_label = "JavaScript/TypeScript"

    def _parse_owned_file(self, path: Path, project_root: Path) -> _ParsedFile:
        return _parse_file(path, project_root)

    def _build_graph_draft(
        self,
        project_root: Path,
        parsed_files: tuple[_ParsedFile, ...],
    ) -> Graph:
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
        ranked_nodes = tuple(
            replace(node, entrypoint_rank=entrypoint_ranks.get(node.id))
            for node in index.nodes
        )
        index = index.with_nodes(ranked_nodes)

        import_edges: set[Edge] = set()
        bindings_by_module: dict[str, list[_ImportBinding]] = defaultdict(list)
        for parsed in parsed_files:
            edges, bindings = _imports_for_file(parsed, index.parsed_by_relative)
            import_edges.update(edges)
            bindings_by_module[parsed.module_id].extend(bindings)

        call_edges = _call_edges(index, bindings_by_module)
        all_edges = [*import_edges, *call_edges]
        annotations = _concept_annotations(index)
        partial_files = tuple(
            parsed.relative_path
            for parsed in parsed_files
            if parsed.tree.root_node.has_error
        )
        return Graph(
            nodes=index.nodes,
            edges=tuple(all_edges),
            entrypoint_candidates=(),
            project_root=str(project_root),
            file_hashes={
                parsed.relative_path: parsed.digest for parsed in parsed_files
            },
            concept_annotations=annotations,
            role_evidence=roles_from_complete_files(
                _role_evidence(index, bindings_by_module),
                index.nodes,
                partial_files,
            ),
            partial_files=partial_files,
        )
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


_HTTP_REGISTRATION_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "all", "use"}
)
def _role_evidence(
    index: _SyntaxEvidenceIndex,
    bindings_by_module: dict[str, list[_ImportBinding]],
) -> tuple[RoleEvidence, ...]:
    """Persist JSX ownership, Express registration, and named test evidence."""

    roles = set(native_entrypoint_roles(index.nodes))
    for definition in index.definitions:
        node = index.node_by_id[definition.node_id]
        parsed = index.parsed_by_module[definition.module_id]
        if node.kind == "function" and node.name.startswith("test_"):
            roles.add(
                RoleEvidence(
                    node.id,
                    "test",
                    f"{node.language}.test.function-name",
                    node.file,
                    node.lineno,
                    node.lineno,
                )
            )
        jsx = next(
            (
                syntax
                for syntax in _walk_owned(
                    definition.syntax,
                    index.nested_ranges_by_owner.get(definition.node_id, frozenset()),
                )
                if syntax.type in {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}
                and not syntax.has_error
            ),
            None,
        )
        if node.kind == "function" and jsx is not None:
            lineno, end_lineno = _line_span(jsx)
            roles.add(
                RoleEvidence(
                    node.id,
                    "ui-renderer",
                    f"{node.language}.jsx.render",
                    parsed.relative_path,
                    lineno,
                    end_lineno,
                )
            )

    for parsed in index.parsed_files:
        binding_map = {
            binding.local_name: binding
            for binding in bindings_by_module.get(parsed.module_id, ())
        }
        express_route_sites = _express_route_sites(parsed, binding_map)
        for syntax in _walk(parsed.tree.root_node):
            if syntax.type != "call_expression" or syntax.has_error:
                continue
            function = syntax.child_by_field_name("function")
            arguments = syntax.child_by_field_name("arguments")
            if function is None or function.type != "member_expression" or arguments is None:
                continue
            object_node = function.child_by_field_name("object")
            property_node = function.child_by_field_name("property")
            if object_node is None or property_node is None:
                continue
            method = _node_text(property_node, parsed.raw)
            if (
                (syntax.start_byte, syntax.end_byte) not in express_route_sites
                or method not in _HTTP_REGISTRATION_METHODS
            ):
                continue
            arguments_list = list(arguments.named_children)
            if len(arguments_list) < 2:
                continue
            handler_syntax = arguments_list[-1]
            if handler_syntax.type != "identifier":
                continue
            handler_name = _node_text(handler_syntax, parsed.raw)
            candidates = list(
                index.nodes_by_module_name.get((parsed.module_id, handler_name), ())
            )
            binding = binding_map.get(handler_name)
            if binding is not None and binding.imported_name is not None:
                for target in binding.targets:
                    candidates.extend(
                        index.nodes_by_module_name.get(
                            (target.module_id, binding.imported_name),
                            (),
                        )
                    )
            unique = {candidate.id: candidate for candidate in candidates}
            if len(unique) != 1:
                continue
            handler = next(iter(unique.values()))
            lineno, end_lineno = _line_span(syntax)
            roles.add(
                RoleEvidence(
                    handler.id,
                    "route-handler",
                    f"{parsed.language}.express.{method}",
                    parsed.relative_path,
                    lineno,
                    end_lineno,
                )
            )
    return tuple(
        sorted(
            roles,
            key=lambda item: (
                item.file,
                item.lineno,
                item.role,
                item.rule_id,
                item.node_id,
            ),
        )
    )


_JAVASCRIPT_FUNCTION_SCOPES = frozenset(
    {
        "function_declaration",
        "function_expression",
        "generator_function_declaration",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)


def _express_route_sites(
    parsed: _ParsedFile,
    binding_map: dict[str, _ImportBinding],
) -> frozenset[tuple[int, int]]:
    """Return registration calls whose receiver is Express-bound at that site.

    A file-wide receiver-name set is unsound: a local ``app`` can shadow a
    proven outer app, and a later assignment can revoke the binding. This
    small lexical interpreter keeps only binding provenance needed for route
    observations; it never tries to evaluate general JavaScript.
    """

    express_bindings = {
        name: binding
        for name, binding in binding_map.items()
        if binding.external_specifier == "express"
    }
    route_sites: set[tuple[int, int]] = set()

    def is_factory_call(value: SyntaxNode | None, factories: set[str]) -> bool:
        if value is None or value.type != "call_expression":
            return False
        function = value.child_by_field_name("function")
        if function is None:
            return False
        if function.type == "identifier":
            name = _node_text(function, parsed.raw)
            binding = express_bindings.get(name)
            return (
                name in factories
                and binding is not None
                and binding.imported_name in {"default", "Router"}
            )
        if function.type == "member_expression":
            object_node = function.child_by_field_name("object")
            property_node = function.child_by_field_name("property")
            if object_node is not None and property_node is not None:
                name = _node_text(object_node, parsed.raw)
                binding = express_bindings.get(name)
                return (
                    name in factories
                    and binding is not None
                    and binding.imported_name in {"default", None}
                    and _node_text(property_node, parsed.raw) == "Router"
                )
        return False

    def declared_names(container: SyntaxNode) -> set[str]:
        names: set[str] = set()
        for statement in container.named_children:
            if statement.type in {"lexical_declaration", "variable_declaration"}:
                for declaration in statement.named_children:
                    if declaration.type != "variable_declarator":
                        continue
                    name = declaration.child_by_field_name("name")
                    if name is not None and name.type == "identifier":
                        names.add(_node_text(name, parsed.raw))
            elif statement.type in {
                "function_declaration",
                "generator_function_declaration",
                "class_declaration",
            }:
                name = statement.child_by_field_name("name")
                if name is not None and name.type == "identifier":
                    names.add(_node_text(name, parsed.raw))
        return names

    def hoisted_var_names(container: SyntaxNode) -> set[str]:
        names: set[str] = set()

        def visit(syntax: SyntaxNode) -> None:
            if syntax.type in _JAVASCRIPT_FUNCTION_SCOPES:
                return
            if syntax.type == "variable_declaration":
                for declaration in syntax.named_children:
                    if declaration.type != "variable_declarator":
                        continue
                    name = declaration.child_by_field_name("name")
                    if name is not None and name.type == "identifier":
                        names.add(_node_text(name, parsed.raw))
            for child in syntax.named_children:
                visit(child)

        for statement in container.named_children:
            visit(statement)
        return names

    def parameter_names(function: SyntaxNode) -> set[str]:
        parameters = function.child_by_field_name("parameters")
        if parameters is None:
            return set()
        return {
            _node_text(node, parsed.raw)
            for node in _walk(parameters)
            if node.type == "identifier"
        }

    def scan_container(
        container: SyntaxNode,
        inherited_receivers: set[str],
        inherited_factories: set[str],
        shadowed_parameters: set[str] | None = None,
    ) -> None:
        shadowed = (
            declared_names(container)
            | hoisted_var_names(container)
            | (shadowed_parameters or set())
        )
        receivers = set(inherited_receivers) - shadowed
        factories = set(inherited_factories) - shadowed

        def scan_inline(syntax: SyntaxNode) -> None:
            if syntax.type in _JAVASCRIPT_FUNCTION_SCOPES or syntax.type == "statement_block":
                return
            if syntax.type == "assignment_expression":
                right = syntax.child_by_field_name("right")
                if right is not None:
                    scan_inline(right)
                left = syntax.child_by_field_name("left")
                if left is not None and left.type == "identifier":
                    name = _node_text(left, parsed.raw)
                    receivers.discard(name)
                    factories.discard(name)
                    if is_factory_call(right, factories):
                        receivers.add(name)
                return
            if syntax.type == "call_expression" and not syntax.has_error:
                function = syntax.child_by_field_name("function")
                if function is not None and function.type == "member_expression":
                    object_node = function.child_by_field_name("object")
                    property_node = function.child_by_field_name("property")
                    if object_node is not None and property_node is not None:
                        receiver = _node_text(object_node, parsed.raw)
                        method = _node_text(property_node, parsed.raw)
                        if receiver in receivers and method in _HTTP_REGISTRATION_METHODS:
                            route_sites.add((syntax.start_byte, syntax.end_byte))
            for child in syntax.named_children:
                scan_inline(child)

        def scan_nested_scopes(syntax: SyntaxNode) -> None:
            for child in syntax.named_children:
                if child.type in _JAVASCRIPT_FUNCTION_SCOPES:
                    body = child.child_by_field_name("body")
                    if body is not None and body.type == "statement_block":
                        scan_container(
                            body,
                            receivers,
                            factories,
                            parameter_names(child),
                        )
                elif child.type == "statement_block":
                    scan_container(child, receivers, factories)
                else:
                    scan_nested_scopes(child)

        for statement in container.named_children:
            if statement.type in {"lexical_declaration", "variable_declaration"}:
                for declaration in statement.named_children:
                    if declaration.type != "variable_declarator":
                        continue
                    name_node = declaration.child_by_field_name("name")
                    value = declaration.child_by_field_name("value")
                    if name_node is not None and name_node.type == "identifier":
                        name = _node_text(name_node, parsed.raw)
                        receivers.discard(name)
                        factories.discard(name)
                        if is_factory_call(value, factories):
                            receivers.add(name)
                    if value is not None:
                        scan_nested_scopes(value)
                continue
            if statement.type in _JAVASCRIPT_FUNCTION_SCOPES:
                body = statement.child_by_field_name("body")
                if body is not None and body.type == "statement_block":
                    scan_container(
                        body,
                        receivers,
                        factories,
                        parameter_names(statement),
                    )
                continue
            scan_inline(statement)
            scan_nested_scopes(statement)

    scan_container(
        parsed.tree.root_node,
        set(),
        set(express_bindings),
    )
    return frozenset(route_sites)


def _parse_file(path: Path, project_root: Path) -> _ParsedFile:
    raw = path.read_bytes()
    relative = path.relative_to(project_root).as_posix()
    language = "javascript" if path.suffix.lower() in _JAVASCRIPT_EXTENSIONS else "typescript"
    parser = Parser(_language_for(path.suffix.lower()))
    parsed = _ParsedFile(
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
    note_file_parsed()
    return parsed


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
    nested_definition_ranges: AbstractSet[tuple[int, int]],
) -> Iterable[SyntaxNode]:
    for child in syntax.named_children:
        if (child.start_byte, child.end_byte) in nested_definition_ranges:
            continue
        yield child
        yield from _walk_owned(child, nested_definition_ranges)


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
    index: _SyntaxEvidenceIndex,
    bindings_by_module: dict[str, list[_ImportBinding]],
) -> list[Edge]:
    edges: list[Edge] = []
    for definition in index.definitions:
        parsed = index.parsed_by_module[definition.module_id]
        binding_map = {
            binding.local_name: binding
            for binding in bindings_by_module[definition.module_id]
        }
        for syntax in _walk_owned(
            definition.syntax,
            index.nested_ranges_by_owner.get(definition.node_id, frozenset()),
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
                    index,
                    index.local_bindings_by_owner[definition.node_id],
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
    index: _SyntaxEvidenceIndex,
    local_binding_names: frozenset[str],
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
            for node in index.children_by_parent.get(definition.node_id, ())
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
            definition,
            name,
            index,
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
                index,
            )
        # Reached only after every project-local answer has been tried, so a
        # name that gets here is either a language/host global or something
        # this parser genuinely cannot place. The first is a boundary and the
        # second is a coverage gap; they are different claims and only now can
        # they be told apart.
        if name in _ECMASCRIPT_GLOBALS:
            return [
                Edge(
                    definition.node_id,
                    f"external:{name}",
                    "call",
                    certain=False,
                    lineno=lineno,
                    external=True,
                )
            ]
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
                for node in index.children_by_parent.get(
                    definition.enclosing_class_id or "", ()
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
                    index,
                )
        possible = index.nodes_by_module_name.get((definition.module_id, name), ())
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
    index: _SyntaxEvidenceIndex,
) -> list[Node]:
    siblings = [
        node
        for node in index.children_by_parent.get(definition.parent_id, ())
        if node.name == name
    ]
    if siblings:
        return sorted(siblings, key=lambda node: node.id)
    return sorted(
        index.nodes_by_module_name.get((definition.module_id, name), ()),
        key=lambda node: node.id,
    )


def _local_binding_names(
    syntax: SyntaxNode,
    raw: bytes,
    nested_definition_ranges: AbstractSet[tuple[int, int]],
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
    index: _SyntaxEvidenceIndex,
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
            candidates.extend(
                (node, target.certain)
                for node in index.nodes_by_module_name.get(
                    (target.module_id, imported_name),
                    (),
                )
            )
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
    index: _SyntaxEvidenceIndex,
) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for parsed in index.parsed_files:
        for definition in index.definitions_by_module.get(parsed.module_id, ()):
            if index.node_by_id[definition.node_id].name == "main":
                ranks[definition.node_id] = 1
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
            index.nested_ranges_by_owner.get(parsed.module_id, frozenset()),
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
    nested_definition_ranges: AbstractSet[tuple[int, int]],
) -> bool:
    for syntax in _walk_owned(parsed.tree.root_node, nested_definition_ranges):
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
