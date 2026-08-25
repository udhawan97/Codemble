"""Tree-sitter Ruby implementation of Codemble's language seam."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_ruby
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
from codemble.adapters.role_rules import roles_from_complete_files
from codemble.adapters.tree_sitter_core import _TreeSitterAdapterCore

_LANGUAGE = Language(tree_sitter_ruby.language())
_EXTENSIONS = frozenset({".rb"})
_IGNORED_DIRECTORIES = frozenset({".bundle", "coverage", "tmp", "vendor"})
_CONTAINERS = frozenset({"class", "module"})
_CALLABLES = frozenset({"method", "singleton_method"})
_BARE_SEND_PARENTS = frozenset(
    {"body_statement", "then", "else", "elsif", "when", "rescue", "ensure"}
)


class RubyParseError(AdapterParseError):
    """Ruby source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
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
    singleton: bool


class RubyAdapter(_TreeSitterAdapterCore):
    """Map Ruby declarations and conservative relationships into one graph."""

    language = "ruby"
    file_extensions = _EXTENSIONS
    ignored_directories = _IGNORED_DIRECTORIES
    _parse_error_type = RubyParseError
    _source_label = "Ruby"

    def _parse_owned_file(self, path: Path, project_root: Path) -> _ParsedFile:
        raw = path.read_bytes()
        relative = path.relative_to(project_root).as_posix()
        parsed = _ParsedFile(
            path=path,
            project_root=project_root,
            relative_path=relative,
            module_id=f"ruby:{relative}",
            raw=raw,
            source=raw.decode("utf-8", errors="replace"),
            digest=hashlib.sha256(raw).hexdigest(),
            tree=Parser(_LANGUAGE).parse(raw),
        )
        note_file_parsed()
        return parsed

    def _build_graph_draft(
        self,
        project_root: Path,
        parsed_files: tuple[_ParsedFile, ...],
    ) -> Graph:
        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            module = _module_node(parsed)
            if _program_name_guard(parsed):
                module = replace(module, entrypoint_rank=1)
            nodes.append(module)
            # Ruby's recovery is intentionally not used as evidence. A file
            # with one syntax error contributes its visible partial module and
            # nothing else, so an earlier recovered declaration cannot look
            # authoritative in a learner's galaxy.
            if parsed.tree.root_node.has_error:
                continue
            file_nodes, file_definitions = _definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        node_tuple = tuple(nodes)
        definition_tuple = tuple(definitions)
        partial_files = tuple(
            parsed.relative_path
            for parsed in parsed_files
            if parsed.tree.root_node.has_error
        )
        roles = [
            RoleEvidence(
                node_id=parsed.module_id,
                role="application-entry",
                rule_id="ruby.entrypoint.program-name",
                file=parsed.relative_path,
                lineno=_program_name_guard(parsed) or 1,
                end_lineno=_program_name_guard(parsed) or 1,
            )
            for parsed in parsed_files
            if not parsed.tree.root_node.has_error and _program_name_guard(parsed)
        ]
        return Graph(
            nodes=node_tuple,
            edges=tuple(
                sorted(
                    {
                        *_import_edges(parsed_files),
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
            role_evidence=roles_from_complete_files(roles, node_tuple, partial_files),
            partial_files=partial_files,
        )

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only Ruby constructs proven inside ``node``."""

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
            digest=hashlib.sha256(raw).hexdigest(),
            tree=Parser(_LANGUAGE).parse(raw),
        )
        if parsed.tree.root_node.has_error:
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
        language="ruby",
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
        path: tuple[str, ...],
        parent_id: str,
        singleton_context: bool = False,
    ) -> None:
        for child in syntax.named_children:
            if child.has_error:
                continue
            if child.type in _CONTAINERS:
                name_node = child.child_by_field_name("name")
                name_path = _constant_path(name_node, parsed.raw)
                if not name_path:
                    visit(child, path, parent_id, singleton_context)
                    continue
                declared_path = (*path, *name_path)
                label = "::".join(name_path)
                base_id = f"{parsed.module_id}::{'.'.join(declared_path)}"
                node_id = _unique_id(base_id, child, used_ids)
                used_ids.add(node_id)
                nodes.append(_node(parsed, child, node_id, "class", label))
                definitions.append(
                    _Definition(
                        node_id=node_id,
                        syntax=child,
                        module_id=parsed.module_id,
                        parent_id=parent_id,
                        path=declared_path,
                        callable=False,
                        singleton=False,
                    )
                )
                visit(child, declared_path, node_id)
                continue
            if child.type == "singleton_class":
                value = child.child_by_field_name("value")
                singleton_path = path
                if value is not None and value.type != "self":
                    constant_path = _constant_path(value, parsed.raw)
                    if constant_path:
                        singleton_path = constant_path
                    else:
                        visit(child, path, parent_id, singleton_context)
                        continue
                body = child.child_by_field_name("body")
                visit(body or child, singleton_path, parent_id, True)
                continue
            if child.type in _CALLABLES:
                name_node = child.child_by_field_name("name")
                # A top-level Ruby method is real structure. Its id stays
                # below the file module rather than pretending it belongs to a
                # class the parser never observed.
                method_path = path
                if name_node is None:
                    visit(child, path, parent_id, singleton_context)
                    continue
                name = _text(name_node, parsed.raw)
                singleton = child.type == "singleton_method" or singleton_context
                sigil = "." if singleton else "#"
                owner = ".".join(method_path)
                segment = f"{owner}{sigil}{name}" if owner else name
                base_id = f"{parsed.module_id}::{segment}"
                node_id = _unique_id(base_id, child, used_ids)
                used_ids.add(node_id)
                nodes.append(_node(parsed, child, node_id, "function", name))
                definitions.append(
                    _Definition(
                        node_id=node_id,
                        syntax=child,
                        module_id=parsed.module_id,
                        parent_id=parent_id,
                        path=(*method_path, name),
                        callable=True,
                        singleton=singleton,
                    )
                )
                # A nested definition inside a method is not made singleton by
                # the surrounding `class << self` body.
                visit(child, path, node_id)
                continue
            visit(child, path, parent_id, singleton_context)

    visit(parsed.tree.root_node, (), parsed.module_id)
    return nodes, definitions


def _node(parsed: _ParsedFile, syntax: SyntaxNode, node_id: str, kind: str, name: str) -> Node:
    start, end = _span(syntax)
    return Node(
        id=node_id,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        language="ruby",
        file=parsed.relative_path,
        lineno=start,
        end_lineno=end,
        loc=end - start + 1,
        region=parsed.module_id,
    )


def _program_name_guard(parsed: _ParsedFile) -> int | None:
    for syntax in parsed.tree.root_node.named_children:
        if syntax.type != "if" or syntax.has_error:
            continue
        condition = syntax.child_by_field_name("condition")
        if condition is None or condition.type != "binary":
            continue
        operator = condition.child_by_field_name("operator")
        left = condition.child_by_field_name("left")
        right = condition.child_by_field_name("right")
        if operator is None or _text(operator, parsed.raw) != "==":
            continue
        operands = {
            _text(operand, parsed.raw)
            for operand in (left, right)
            if operand is not None
        }
        if operands == {"$PROGRAM_NAME", "__FILE__"}:
            return syntax.start_point.row + 1
    return None


def _import_edges(parsed_files: tuple[_ParsedFile, ...]) -> set[Edge]:
    by_path = {parsed.path.resolve(): parsed.module_id for parsed in parsed_files}
    edges: set[Edge] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        for syntax in _walk(parsed.tree.root_node):
            if syntax.type != "call" or syntax.has_error:
                continue
            method = syntax.child_by_field_name("method")
            if method is None:
                continue
            name = _text(method, parsed.raw)
            if name not in {"require", "require_relative", "load"}:
                continue
            literal = _single_string_argument(syntax, parsed.raw)
            lineno = syntax.start_point.row + 1
            if literal is None:
                edges.add(
                    Edge(
                        src=parsed.module_id,
                        dst=f"external:ruby.{name}.dynamic",
                        kind="import",
                        certain=False,
                        lineno=lineno,
                        external=True,
                    )
                )
                continue
            target: Path | None = None
            if name == "require_relative":
                target = (parsed.path.parent / literal).resolve()
            elif literal.startswith(("./", "../")):
                target = (parsed.project_root / literal).resolve()
            if target is not None and target.suffix == "":
                target = target.with_suffix(".rb")
            module_id = by_path.get(target) if target is not None else None
            edges.add(
                Edge(
                    src=parsed.module_id,
                    dst=module_id or f"external:{literal}",
                    kind="import",
                    certain=module_id is not None or name in {"require", "require_relative"},
                    lineno=lineno,
                    external=module_id is None,
                )
            )
    return edges


def _call_edges(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: tuple[_Definition, ...],
) -> set[Edge]:
    containers: dict[tuple[str, ...], list[_Definition]] = {}
    singleton_methods: dict[tuple[tuple[str, ...], str], list[_Definition]] = {}
    instance_methods: dict[tuple[tuple[str, ...], str], list[_Definition]] = {}
    for definition in definitions:
        if definition.callable:
            owner, name = definition.path[:-1], definition.path[-1]
            table = singleton_methods if definition.singleton else instance_methods
            table.setdefault((owner, name), []).append(definition)
        else:
            containers.setdefault(definition.path, []).append(definition)

    edges: set[Edge] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        file_definitions = [item for item in definitions if item.module_id == parsed.module_id]
        local_bindings: dict[str, frozenset[str]] = {}
        for syntax in _walk(parsed.tree.root_node):
            is_call = syntax.type == "call"
            is_bare_send = syntax.type == "identifier" and _is_bare_send(syntax)
            if (not is_call and not is_bare_send) or syntax.has_error:
                continue
            method = syntax.child_by_field_name("method") if is_call else syntax
            if method is None:
                continue
            name = _text(method, parsed.raw)
            if name in {"require", "require_relative", "load"}:
                continue
            owner = _owner(syntax, file_definitions)
            if is_bare_send and owner is not None:
                bindings = local_bindings.get(owner.node_id)
                if bindings is None:
                    bindings = _local_bindings(owner)
                    local_bindings[owner.node_id] = bindings
                if name in bindings:
                    continue
            src = owner.node_id if owner is not None else parsed.module_id
            receiver = syntax.child_by_field_name("receiver") if is_call else None
            targets: list[_Definition] = []
            label = name
            if receiver is not None:
                receiver_path = _constant_path(receiver, parsed.raw)
                if receiver_path:
                    label = f"{'::'.join(receiver_path)}.{name}"
                    targets = singleton_methods.get((receiver_path, name), [])
                    if name == "new" and not targets:
                        targets = containers.get(receiver_path, [])
                elif _text(receiver, parsed.raw) == "self" and owner is not None:
                    scope = owner.path[:-1] if owner.callable else owner.path
                    table = singleton_methods if owner.singleton else instance_methods
                    targets = table.get((scope, name), [])
                    label = f"self.{name}"
            elif owner is not None:
                scope = owner.path[:-1] if owner.callable else owner.path
                # Bare calls can invoke private methods, but Ruby's open classes
                # and method_missing mean even a unique parser match is possible.
                primary = singleton_methods if owner.singleton else instance_methods
                secondary = instance_methods if owner.singleton else singleton_methods
                targets = primary.get((scope, name), [])
                if not targets:
                    targets = secondary.get((scope, name), [])

            if len(targets) == 1:
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


def _is_bare_send(syntax: SyntaxNode) -> bool:
    """Identify a no-argument Ruby send without mistaking syntax names for calls."""

    parent = syntax.parent
    return parent is not None and parent.type in _BARE_SEND_PARENTS


def _local_bindings(owner: _Definition) -> frozenset[str]:
    """Names Ruby's syntax proves local in one callable scope."""

    if not owner.callable:
        return frozenset()
    names: set[str] = set()
    parameters = owner.syntax.child_by_field_name("parameters")
    if parameters is not None:
        names.update(
            child.text.decode("utf-8", errors="replace")
            for child in _walk(parameters)
            if child.type == "identifier"
        )

    def visit(syntax: SyntaxNode) -> None:
        if syntax is not owner.syntax and syntax.type in _CALLABLES:
            return
        if syntax.type in {"assignment", "operator_assignment", "multiple_assignment"}:
            left = syntax.child_by_field_name("left")
            if left is not None:
                names.update(
                    child.text.decode("utf-8", errors="replace")
                    for child in _walk(left)
                    if child.type == "identifier"
                )
        for child in syntax.named_children:
            visit(child)

    visit(owner.syntax)
    return frozenset(names)


def _concept_annotations(
    parsed_files: tuple[_ParsedFile, ...],
    definitions: tuple[_Definition, ...],
) -> tuple[ConceptAnnotation, ...]:
    concepts = {
        "block": "block",
        "do_block": "block",
        "interpolation": "string-interpolation",
        "rescue": "exception-handling",
        "singleton_method": "singleton-method",
        "simple_symbol": "symbol",
        "symbol": "symbol",
    }
    annotations: set[ConceptAnnotation] = set()
    for parsed in parsed_files:
        if parsed.tree.root_node.has_error:
            continue
        file_definitions = [item for item in definitions if item.module_id == parsed.module_id]
        for syntax in _walk(parsed.tree.root_node):
            concept = concepts.get(syntax.type)
            if concept is None and syntax.type == "call" and "&." in _text(syntax, parsed.raw):
                concept = "safe-navigation"
            if concept is None:
                continue
            owner = _owner(syntax, file_definitions)
            node_id = owner.node_id if owner is not None else parsed.module_id
            start, end = _span(syntax)
            annotations.add(
                ConceptAnnotation(
                    node_id=node_id,
                    language="ruby",
                    concept=concept,
                    lineno=start,
                    end_lineno=end,
                    snippet=_line_snippet(parsed.source, start),
                )
            )
    return tuple(
        sorted(annotations, key=lambda item: (item.node_id, item.lineno, item.concept))
    )


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


def _single_string_argument(syntax: SyntaxNode, raw: bytes) -> str | None:
    arguments = syntax.child_by_field_name("arguments")
    if arguments is None or len(arguments.named_children) != 1:
        return None
    string = arguments.named_children[0]
    if string.type != "string" or any(child.type == "interpolation" for child in _walk(string)):
        return None
    content = next((child for child in string.named_children if child.type == "string_content"), None)
    return None if content is None else _text(content, raw)


def _constant_path(syntax: SyntaxNode | None, raw: bytes) -> tuple[str, ...] | None:
    if syntax is None:
        return None
    if syntax.type == "constant":
        return (_text(syntax, raw),)
    if syntax.type == "scope_resolution":
        scope = _constant_path(syntax.child_by_field_name("scope"), raw)
        name = syntax.child_by_field_name("name")
        if scope and name is not None:
            return (*scope, _text(name, raw))
    return None


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


__all__ = ["RubyAdapter", "RubyParseError"]
