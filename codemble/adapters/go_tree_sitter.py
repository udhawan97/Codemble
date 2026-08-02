"""Tree-sitter Go implementation of the language seam."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_go
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

_EXTENSIONS = frozenset({".go"})
# `vendor` holds copies of other people's modules and `testdata` is, by the
# toolchain's own rule, never compiled -- neither is structure the learner wrote.
_IGNORED_DIRECTORIES = frozenset({"testdata", "vendor"})

# Predeclared identifiers. A call to one of these is either a language builtin
# or a type conversion, so neither names a structure this project defines: an
# edge to `len` or `int64` would be an invented relationship, not a missing one.
_PREDECLARED = frozenset(
    {
        "any",
        "append",
        "bool",
        "byte",
        "cap",
        "clear",
        "close",
        "comparable",
        "complex",
        "complex64",
        "complex128",
        "copy",
        "delete",
        "error",
        "float32",
        "float64",
        "imag",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "len",
        "make",
        "max",
        "min",
        "new",
        "panic",
        "print",
        "println",
        "real",
        "recover",
        "rune",
        "string",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "uintptr",
    }
)
_DEFINITION_TYPES = frozenset(
    {"function_declaration", "method_declaration", "type_declaration"}
)
_CLASS_TYPES = frozenset({"interface_type", "struct_type"})

# Every parameter list binds its names, wherever it sits: a receiver, a generic
# parameter, a named result, or the parameters of a closure written inline.
_BINDING_LISTS = frozenset({"parameter_list", "type_parameter_list"})
# Statements that introduce a name, and the field holding the names they bind.
_BINDING_STATEMENTS = {
    "short_var_declaration": "left",
    "range_clause": "left",
    "receive_statement": "left",
    "type_switch_statement": "alias",
}

_GO_LANGUAGE = Language(tree_sitter_go.language())


class GoParseError(AdapterParseError):
    """Go source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
    package_dir: str
    package_name: str | None
    raw: bytes
    source: str
    digest: str
    tree: Tree

    @property
    def is_test_file(self) -> bool:
        """Whether the toolchain excludes this file from a normal import.

        A ``_test.go`` file is compiled only by ``go test``, so importing the
        package it sits in does not depend on it. The suffix is the toolchain's
        own rule, not a guess about the file's contents.
        """

        return self.path.name.endswith("_test.go")


@dataclass(frozen=True, slots=True)
class _Definition:
    node_id: str
    syntax: SyntaxNode
    module_id: str
    package_dir: str


@dataclass(frozen=True, slots=True)
class _ResolvedPackage:
    package_dir: str
    certain: bool


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    local_name: str
    target: _ResolvedPackage | None
    external_path: str | None


@dataclass(frozen=True, slots=True)
class _GoIndex:
    """Package-scoped lookup evidence derived from one Go syntax parse."""

    parsed_files: tuple[_ParsedFile, ...]
    definitions: tuple[_Definition, ...]
    nodes: tuple[Node, ...]
    node_by_id: dict[str, Node]
    parsed_by_module: dict[str, _ParsedFile]
    files_by_package: dict[str, tuple[_ParsedFile, ...]]
    # Go resolves an unqualified name against the whole package, not the file,
    # so every symbol lookup below is keyed by directory rather than by module.
    functions_by_package: dict[tuple[str, str], tuple[Node, ...]]
    methods_by_package: dict[tuple[str, str], tuple[Node, ...]]
    # Every type the package declares, including the ones that become no node.
    # `type Celsius float64` is not a structure worth a planet, but `Celsius(x)`
    # is still a conversion, and without this it would read as a call.
    type_names_by_package: dict[str, frozenset[str]]
    nested_ranges_by_owner: dict[str, frozenset[tuple[int, int]]]
    local_bindings_by_owner: dict[str, frozenset[str]]

    @classmethod
    def build(
        cls,
        parsed_files: tuple[_ParsedFile, ...],
        definitions: tuple[_Definition, ...],
        nodes: tuple[Node, ...],
    ) -> _GoIndex:
        node_by_id = {node.id: node for node in nodes}
        parsed_by_module = {parsed.module_id: parsed for parsed in parsed_files}
        files_by_package: dict[str, list[_ParsedFile]] = defaultdict(list)
        for parsed in parsed_files:
            files_by_package[parsed.package_dir].append(parsed)

        nested_ranges: dict[str, set[tuple[int, int]]] = defaultdict(set)
        for definition in definitions:
            nested_ranges[definition.module_id].add(
                (definition.syntax.start_byte, definition.syntax.end_byte)
            )

        type_names: dict[str, set[str]] = defaultdict(set)
        for parsed in parsed_files:
            type_names[parsed.package_dir].update(_declared_type_names(parsed))

        functions, methods = cls._package_symbols(definitions, node_by_id)
        return cls(
            parsed_files=parsed_files,
            definitions=definitions,
            nodes=nodes,
            node_by_id=node_by_id,
            parsed_by_module=parsed_by_module,
            files_by_package={
                package_dir: tuple(package_files)
                for package_dir, package_files in files_by_package.items()
            },
            functions_by_package=functions,
            methods_by_package=methods,
            type_names_by_package={
                package_dir: frozenset(names)
                for package_dir, names in type_names.items()
            },
            nested_ranges_by_owner={
                owner: frozenset(ranges) for owner, ranges in nested_ranges.items()
            },
            local_bindings_by_owner={
                definition.node_id: frozenset(
                    _local_binding_names(
                        definition.syntax,
                        parsed_by_module[definition.module_id].raw,
                    )
                )
                for definition in definitions
            },
        )

    def with_nodes(self, nodes: tuple[Node, ...]) -> _GoIndex:
        """Refresh node metadata without rebuilding syntax ownership evidence."""

        node_by_id = {node.id: node for node in nodes}
        functions, methods = self._package_symbols(self.definitions, node_by_id)
        return replace(
            self,
            nodes=nodes,
            node_by_id=node_by_id,
            functions_by_package=functions,
            methods_by_package=methods,
        )

    @staticmethod
    def _package_symbols(
        definitions: tuple[_Definition, ...],
        node_by_id: dict[str, Node],
    ) -> tuple[
        dict[tuple[str, str], tuple[Node, ...]],
        dict[tuple[str, str], tuple[Node, ...]],
    ]:
        functions: dict[tuple[str, str], list[Node]] = defaultdict(list)
        methods: dict[tuple[str, str], list[Node]] = defaultdict(list)
        for definition in definitions:
            node = node_by_id[definition.node_id]
            if node.kind == "class":
                continue
            key = (definition.package_dir, node.name)
            target = methods if _is_method_id(definition.node_id) else functions
            target[key].append(node)
        return (
            {
                key: tuple(sorted(found, key=lambda node: node.id))
                for key, found in functions.items()
            },
            {
                key: tuple(sorted(found, key=lambda node: node.id))
                for key, found in methods.items()
            },
        )


class GoAdapter:
    """Map Go packages into one deterministic, parser-proven graph."""

    language = "go"
    file_extensions = _EXTENSIONS
    ignored_directories = _IGNORED_DIRECTORIES

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact Go source scope accepted by this adapter."""

        normalized = path.expanduser().resolve()
        try:
            discovery = discover_source_files(
                normalized,
                self.file_extensions,
                ignored_directories=self.ignored_directories,
            )
        except SourceDiscoveryError as error:
            raise GoParseError(str(error)) from error
        if not discovery.files:
            if normalized.is_file():
                raise GoParseError(f"expected a Go file or directory: {normalized}")
            raise GoParseError(f"no Go files found under: {normalized}")
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse ``path`` using the official tree-sitter Go grammar wheel."""

        project_root, files = self.discover(path)
        return self.parse_files(project_root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        """Parse Go files already owned by this adapter."""

        parsed_files = tuple(_parse_file(file, project_root) for file in files)

        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            nodes.append(_module_node(parsed))
            file_nodes, file_definitions = _collect_definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        index = _GoIndex.build(parsed_files, tuple(definitions), tuple(nodes))
        entrypoint_ranks = _entrypoint_ranks(index)
        index = index.with_nodes(
            tuple(
                replace(node, entrypoint_rank=entrypoint_ranks.get(node.id))
                for node in index.nodes
            )
        )

        module_path = _module_path(project_root)
        import_edges: set[Edge] = set()
        bindings_by_module: dict[str, list[_ImportBinding]] = defaultdict(list)
        for parsed in parsed_files:
            edges, bindings = _imports_for_file(parsed, module_path, index)
            import_edges.update(edges)
            bindings_by_module[parsed.module_id].extend(bindings)

        draft = Graph(
            nodes=index.nodes,
            edges=(*import_edges, *_call_edges(index, bindings_by_module)),
            entrypoint_candidates=(),
            project_root=str(project_root),
            file_hashes={parsed.relative_path: parsed.digest for parsed in parsed_files},
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
            raise GoParseError(str(error)) from error

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only tree-sitter-proven concepts owned by ``node``."""

        if node.partial or node.language != self.language:
            return []
        raw = source.encode("utf-8")
        parsed = _build_parsed_file(Path(node.file), Path("."), node.file, raw)
        module_node = _module_node(parsed)
        file_nodes, definitions = _collect_definitions(parsed)
        index = _GoIndex.build(
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
    parsed = _build_parsed_file(
        path,
        project_root,
        path.relative_to(project_root).as_posix(),
        raw,
    )
    note_file_parsed()
    return parsed


def _build_parsed_file(
    path: Path,
    project_root: Path,
    relative: str,
    raw: bytes,
) -> _ParsedFile:
    tree = Parser(_GO_LANGUAGE).parse(raw)
    return _ParsedFile(
        path=path,
        project_root=project_root,
        relative_path=relative,
        module_id=f"go:{relative}",
        package_dir=_package_dir(relative),
        package_name=_package_name(tree.root_node, raw),
        raw=raw,
        source=raw.decode("utf-8", errors="replace"),
        digest=hashlib.sha256(raw).hexdigest(),
        tree=tree,
    )


def _package_dir(relative: str) -> str:
    """The directory that owns this file, which in Go is the package itself."""

    parent = Path(relative).parent.as_posix()
    return "" if parent == "." else parent


def _package_name(root: SyntaxNode, raw: bytes) -> str | None:
    for child in root.named_children:
        if child.type != "package_clause" or child.has_error:
            continue
        identifier = next(
            (item for item in child.named_children if item.type == "package_identifier"),
            None,
        )
        if identifier is not None:
            return _node_text(identifier, raw)
    return None


def _module_path(project_root: Path) -> str | None:
    """Read the module path from ``go.mod`` so imports can resolve exactly.

    Without it an import path cannot be proven to point inside this project,
    which is routine rather than exceptional: Codemble is often pointed at a
    subdirectory whose ``go.mod`` sits above the chosen scope.
    """

    manifest = project_root / "go.mod"
    if not manifest.is_file():
        return None
    for raw_line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("module ") and (path := line[len("module ") :].strip()):
            return path.strip('"')
    return None


def _module_node(parsed: _ParsedFile) -> Node:
    line_count = max(1, len(parsed.source.splitlines()))
    return Node(
        id=parsed.module_id,
        kind="module",
        # A Go file's own name is what a learner opens, but the package clause
        # is what the language calls it; the id keeps the path unambiguous.
        name=parsed.path.stem,
        language="go",
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
    """Collect the top-level structures Go declares in one file.

    Go has no nested named declarations, so this walk stays flat: a closure
    inside a function is anonymous and belongs to that function rather than
    becoming a structure of its own.
    """

    nodes: list[Node] = []
    definitions: list[_Definition] = []
    used_ids: set[str] = {parsed.module_id}

    def add(syntax: SyntaxNode, name: str, kind: str, qualifier: str) -> None:
        base_id = f"{parsed.module_id}::{qualifier}{name}"
        node_id = _unique_node_id(base_id, syntax, used_ids)
        used_ids.add(node_id)
        lineno, end_lineno = _line_span(syntax)
        nodes.append(
            Node(
                id=node_id,
                kind=kind,  # type: ignore[arg-type]
                name=name,
                language="go",
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
                module_id=parsed.module_id,
                package_dir=parsed.package_dir,
            )
        )

    for child in parsed.tree.root_node.named_children:
        if child.has_error or child.type not in _DEFINITION_TYPES:
            continue
        if child.type == "function_declaration":
            name = _field_text(child, "name", parsed.raw, {"identifier"})
            if name:
                add(child, name, "function", "")
        elif child.type == "method_declaration":
            name = _field_text(child, "name", parsed.raw, {"field_identifier"})
            receiver = _receiver_qualifier(child, parsed.raw)
            # A method belongs to its receiver type, so the id says so: two
            # types in one file may each declare `Close`, and a bare `Close`
            # would merge them into one structure that does not exist.
            if name and receiver:
                add(child, name, "function", f"{receiver}.")
        else:
            for spec in child.named_children:
                if spec.type != "type_spec" or spec.has_error:
                    continue
                declared = spec.child_by_field_name("type")
                name = _field_text(spec, "name", parsed.raw, {"type_identifier"})
                if name and declared is not None and declared.type in _CLASS_TYPES:
                    add(spec, name, "class", "")
    return nodes, definitions


def _declared_type_names(parsed: _ParsedFile) -> set[str]:
    """Every name this file introduces as a type, node-worthy or not."""

    names: set[str] = set()
    for child in parsed.tree.root_node.named_children:
        if child.has_error or child.type != "type_declaration":
            continue
        for spec in child.named_children:
            if spec.type not in {"type_spec", "type_alias"} or spec.has_error:
                continue
            name = _field_text(spec, "name", parsed.raw, {"type_identifier"})
            if name:
                names.add(name)
    return names


def _receiver_qualifier(syntax: SyntaxNode, raw: bytes) -> str | None:
    """Return the receiver spelled the way Go's own documentation spells it."""

    receiver = syntax.child_by_field_name("receiver")
    if receiver is None or receiver.has_error:
        return None
    declaration = next(
        (
            child
            for child in receiver.named_children
            if child.type == "parameter_declaration"
        ),
        None,
    )
    if declaration is None:
        return None
    declared_type = declaration.child_by_field_name("type")
    if declared_type is None:
        return None
    pointer = declared_type.type == "pointer_type"
    base = next(
        (item for item in (declared_type, *_walk(declared_type)) if item.type == "type_identifier"),
        None,
    )
    if base is None:
        return None
    name = _node_text(base, raw)
    return f"(*{name})" if pointer else f"({name})"


def _is_method_id(node_id: str) -> bool:
    return node_id.rsplit("::", 1)[-1].startswith("(")


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


def _field_text(
    syntax: SyntaxNode,
    field: str,
    raw: bytes,
    allowed: AbstractSet[str],
) -> str | None:
    child = syntax.child_by_field_name(field)
    if child is None or child.has_error or child.type not in allowed:
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


def _concept_annotations(index: _GoIndex) -> tuple[ConceptAnnotation, ...]:
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
                frozenset(),
                include_owner=True,
            )
        )
    return tuple(sorted(annotations, key=_annotation_key))


def _annotation_key(annotation: ConceptAnnotation) -> tuple[str, str, int, str, int]:
    return (
        annotation.language,
        annotation.node_id,
        annotation.lineno,
        annotation.concept,
        annotation.end_lineno,
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
    candidates = (syntax, *walked) if include_owner else walked
    annotations: set[ConceptAnnotation] = set()
    source_lines = parsed.source.splitlines()
    for candidate in candidates:
        if candidate.has_error:
            continue
        for concept in _concepts_for_syntax(candidate, parsed.raw):
            lineno, end_lineno = _line_span(candidate)
            snippet = (
                source_lines[lineno - 1].strip() if 0 < lineno <= len(source_lines) else ""
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


def _concepts_for_syntax(syntax: SyntaxNode, raw: bytes) -> tuple[str, ...]:
    concepts: list[str] = []
    if syntax.type == "go_statement":
        concepts.append("goroutine")
    if syntax.type == "defer_statement":
        concepts.append("defer")
    if syntax.type in {"channel_type", "send_statement"} or (
        syntax.type == "unary_expression" and _operator_text(syntax, raw) == "<-"
    ):
        concepts.append("channel")
    if syntax.type == "type_parameter_list":
        concepts.append("generics")
    if syntax.type in {"function_declaration", "method_declaration"} and _returns_error(
        syntax,
        raw,
    ):
        concepts.append("error-return")
    if syntax.type == "field_declaration" and syntax.child_by_field_name("name") is None:
        concepts.append("struct-embedding")
    if syntax.type == "var_spec" and _is_interface_assertion(syntax, raw):
        concepts.append("interface-assertion")
    return tuple(concepts)


def _operator_text(syntax: SyntaxNode, raw: bytes) -> str | None:
    operator = syntax.child_by_field_name("operator")
    return None if operator is None else _node_text(operator, raw)


def _returns_error(syntax: SyntaxNode, raw: bytes) -> bool:
    result = syntax.child_by_field_name("result")
    if result is None:
        return False
    return any(
        item.type == "type_identifier" and _node_text(item, raw) == "error"
        for item in (result, *_walk(result))
    )


def _is_interface_assertion(syntax: SyntaxNode, raw: bytes) -> bool:
    """Detect ``var _ Iface = (*T)(nil)``, Go's compile-time satisfaction check.

    The blank name, the explicit type and the initializer are all in the parse
    tree; whether ``T`` really satisfies ``Iface`` is the compiler's answer, not
    one this adapter claims.
    """

    name = syntax.child_by_field_name("name")
    declared = syntax.child_by_field_name("type")
    value = syntax.child_by_field_name("value")
    return (
        name is not None
        and declared is not None
        and value is not None
        and _node_text(name, raw) == "_"
    )


def _imports_for_file(
    parsed: _ParsedFile,
    module_path: str | None,
    index: _GoIndex,
) -> tuple[list[Edge], list[_ImportBinding]]:
    edges: list[Edge] = []
    bindings: list[_ImportBinding] = []
    for syntax in _walk(parsed.tree.root_node):
        if syntax.type != "import_spec" or syntax.has_error:
            continue
        import_path = _import_path(syntax, parsed.raw)
        if import_path is None:
            continue
        target = _resolve_package(import_path, module_path, index)
        edges.extend(_import_edges(parsed, syntax, import_path, target, index))
        binding = _import_binding(syntax, parsed.raw, import_path, target, index)
        if binding is not None:
            bindings.append(binding)
    return edges, bindings


def _import_path(syntax: SyntaxNode, raw: bytes) -> str | None:
    path_node = syntax.child_by_field_name("path")
    if path_node is None or path_node.type != "interpreted_string_literal":
        return None
    text = _node_text(path_node, raw)
    if len(text) < 2 or text[0] != '"' or text[-1] != '"' or "\\" in text:
        return None
    return text[1:-1]


def _resolve_package(
    import_path: str,
    module_path: str | None,
    index: _GoIndex,
) -> _ResolvedPackage | None:
    """Map an import path onto a package directory in this project.

    An import path is only *proven* to point inside the project when ``go.mod``
    declares the module prefix it starts with. Everything else falls back to a
    longest-suffix match, which is a guess and is marked as one -- except for
    the standard library, whose paths the language itself distinguishes by
    having no dot in their first element.
    """

    if module_path is not None:
        if import_path == module_path:
            return _package_if_present("", index, certain=True)
        prefix = f"{module_path}/"
        if import_path.startswith(prefix):
            return _package_if_present(import_path[len(prefix) :], index, certain=True)
    if "." not in import_path.split("/", 1)[0]:
        return None
    segments = import_path.split("/")
    for start in range(len(segments)):
        candidate = "/".join(segments[start:])
        resolved = _package_if_present(candidate, index, certain=False)
        if resolved is not None:
            return resolved
    return None


def _package_if_present(
    package_dir: str,
    index: _GoIndex,
    *,
    certain: bool,
) -> _ResolvedPackage | None:
    if not _importable_files(package_dir, index):
        return None
    return _ResolvedPackage(package_dir, certain)


def _importable_files(package_dir: str, index: _GoIndex) -> tuple[_ParsedFile, ...]:
    return tuple(
        parsed
        for parsed in index.files_by_package.get(package_dir, ())
        if not parsed.is_test_file
    )


def _import_edges(
    parsed: _ParsedFile,
    syntax: SyntaxNode,
    import_path: str,
    target: _ResolvedPackage | None,
    index: _GoIndex,
) -> list[Edge]:
    lineno = syntax.start_point.row + 1
    if target is None:
        return [
            Edge(
                src=parsed.module_id,
                dst=f"external:{import_path}",
                kind="import",
                certain=True,
                lineno=lineno,
                external=True,
            )
        ]
    # Go's import unit is the package and a package is every non-test file in
    # its directory, so the compiler genuinely requires each of them. One edge
    # per file is the same fact expressed at this graph's file granularity.
    return [
        Edge(
            src=parsed.module_id,
            dst=imported.module_id,
            kind="import",
            certain=target.certain,
            lineno=lineno,
        )
        for imported in sorted(
            _importable_files(target.package_dir, index),
            key=lambda item: item.module_id,
        )
        if imported.module_id != parsed.module_id
    ]


def _import_binding(
    syntax: SyntaxNode,
    raw: bytes,
    import_path: str,
    target: _ResolvedPackage | None,
    index: _GoIndex,
) -> _ImportBinding | None:
    name_node = syntax.child_by_field_name("name")
    if name_node is not None:
        # `_` imports only for side effects and `.` drops names straight into
        # file scope; neither leaves a qualifier a call can be resolved through.
        if name_node.type != "package_identifier":
            return None
        return _ImportBinding(
            _node_text(name_node, raw),
            target,
            None if target is not None else import_path,
        )
    if target is not None:
        local = _package_clause_name(target.package_dir, index)
        if local is None:
            return None
        return _ImportBinding(local, target, None)
    # An external package's name need not match its path's last element, so
    # this binding is a convention rather than evidence -- which is one reason
    # calls made through it are never certain.
    return _ImportBinding(import_path.rsplit("/", 1)[-1], None, import_path)


def _package_clause_name(package_dir: str, index: _GoIndex) -> str | None:
    names = sorted(
        {
            parsed.package_name
            for parsed in _importable_files(package_dir, index)
            if parsed.package_name is not None
        }
    )
    return names[0] if len(names) == 1 else None


def _call_edges(
    index: _GoIndex,
    bindings_by_module: dict[str, list[_ImportBinding]],
) -> list[Edge]:
    edges: list[Edge] = []
    for definition in index.definitions:
        parsed = index.parsed_by_module[definition.module_id]
        binding_map = {
            binding.local_name: binding
            for binding in bindings_by_module[definition.module_id]
        }
        for syntax in _walk(definition.syntax):
            if syntax.has_error:
                continue
            if syntax.type == "call_expression":
                edges.extend(
                    _resolve_call(
                        definition,
                        syntax,
                        syntax.child_by_field_name("function"),
                        parsed.raw,
                        binding_map,
                        index,
                        certain_allowed=True,
                    )
                )
            elif syntax.type == "type_conversion_expression":
                # The grammar cannot tell `Map[int](xs)` -- an explicit generic
                # instantiation, which IS a call -- from `[]byte(s)`, which is
                # not. Where the head names a function this project declares,
                # that is a call the parser could not prove: kept, never upgraded.
                edges.extend(
                    _resolve_call(
                        definition,
                        syntax,
                        syntax.child_by_field_name("type"),
                        parsed.raw,
                        binding_map,
                        index,
                        certain_allowed=False,
                    )
                )
    return edges


def _resolve_call(
    definition: _Definition,
    syntax: SyntaxNode,
    target: SyntaxNode | None,
    raw: bytes,
    bindings: dict[str, _ImportBinding],
    index: _GoIndex,
    *,
    certain_allowed: bool,
) -> list[Edge]:
    lineno = syntax.start_point.row + 1
    if target is None:
        return [_dynamic_call_edge(definition.node_id, lineno)]
    # An explicit type argument list wraps the callee; `Map[int]` and `Map` name
    # the same function.
    while target.type in {"index_expression", "generic_type"}:
        operand = target.child_by_field_name("operand") or target.child_by_field_name("type")
        if operand is None:
            return [_dynamic_call_edge(definition.node_id, lineno)]
        target = operand

    package = definition.package_dir
    local_names = index.local_bindings_by_owner[definition.node_id]

    # `type_identifier` is the same name reached through generic-instantiation
    # syntax; the grammar labels the head by where it sits, not by what it is.
    if target.type in {"identifier", "type_identifier"}:
        name = _node_text(target, raw)
        if name in local_names:
            # A local name shadows the package scope, so this calls a function
            # value whose target the parse tree does not name.
            return [_unresolved_edge(definition.node_id, f"{definition.node_id}:{name}", lineno)]
        declared_types = index.type_names_by_package.get(package, frozenset())
        if name in declared_types or name in _PREDECLARED:
            # A conversion or a builtin: real syntax, but not a call to any
            # structure this project declares.
            return []
        found = index.functions_by_package.get((package, name), ())
        if found:
            return _edges_to(definition.node_id, found, lineno, certain=certain_allowed)
        if certain_allowed:
            return [
                _unresolved_edge(definition.node_id, f"{definition.module_id}:{name}", lineno)
            ]
        return []

    if target.type in {"selector_expression", "qualified_type"}:
        return _resolve_qualified_call(
            definition,
            target,
            raw,
            bindings,
            index,
            lineno,
            certain_allowed=certain_allowed,
        )

    if target.type == "func_literal":
        return [_dynamic_call_edge(definition.node_id, lineno)]

    # Every remaining head is type syntax -- `(*T)(v)`, `map[string]int(m)`,
    # `chan int(c)` -- which converts a value rather than calling anything.
    # A parenthesized function value, `(f)(x)`, is swept up with them; skipping
    # a rare real call is safer than asserting a call where Go has none.
    return []


def _resolve_qualified_call(
    definition: _Definition,
    target: SyntaxNode,
    raw: bytes,
    bindings: dict[str, _ImportBinding],
    index: _GoIndex,
    lineno: int,
    *,
    certain_allowed: bool,
) -> list[Edge]:
    operand = target.child_by_field_name("operand") or target.child_by_field_name("package")
    field = target.child_by_field_name("field") or target.child_by_field_name("name")
    if operand is None or field is None:
        return [_dynamic_call_edge(definition.node_id, lineno)]
    name = _node_text(field, raw)

    if operand.type in {"identifier", "package_identifier"}:
        qualifier = _node_text(operand, raw)
        # A parameter or variable of the same name shadows the import, so the
        # qualifier is a value rather than a package.
        shadowed = qualifier in index.local_bindings_by_owner[definition.node_id]
        binding = None if shadowed else bindings.get(qualifier)
        if binding is not None and binding.external_path is not None:
            return [
                Edge(
                    definition.node_id,
                    f"external:{binding.external_path}.{name}",
                    "call",
                    certain=False,
                    lineno=lineno,
                    external=True,
                )
            ]
        if binding is not None and binding.target is not None:
            found = index.functions_by_package.get((binding.target.package_dir, name), ())
            if found:
                return _edges_to(
                    definition.node_id,
                    found,
                    lineno,
                    certain=certain_allowed and binding.target.certain,
                )
            if name in index.type_names_by_package.get(
                binding.target.package_dir, frozenset()
            ):
                # `units.Celsius(1)` converts a value; Go has no call here. The
                # same-package spelling was already excluded, and the imported
                # package was parsed too, so its declared type names are the
                # same evidence rather than an assumption about the name.
                return []
            return [
                _unresolved_edge(
                    definition.node_id,
                    f"go:{binding.target.package_dir}:{name}",
                    lineno,
                )
            ]

    # Anything else is a selector on a value. Go resolves that by the value's
    # static type, which this adapter does not infer -- and an interface value
    # or a func-typed field is not decided until run time at all. Methods of
    # this package that share the name are the honest set of possibilities.
    possible = index.methods_by_package.get((definition.package_dir, name), ())
    if possible:
        return _edges_to(definition.node_id, possible, lineno, certain=False)
    return [
        _unresolved_edge(
            definition.node_id,
            f"{definition.module_id}:{_node_text(target, raw)}",
            lineno,
        )
    ]


def _edges_to(
    src: str,
    targets: tuple[Node, ...],
    lineno: int,
    *,
    certain: bool,
) -> list[Edge]:
    unambiguous = certain and len(targets) == 1
    return [
        Edge(src, node.id, "call", certain=unambiguous, lineno=lineno)
        for node in sorted(targets, key=lambda item: item.id)
    ]


def _unresolved_edge(src: str, suffix: str, lineno: int) -> Edge:
    return Edge(src, f"unresolved:{suffix}", "call", certain=False, lineno=lineno)


def _dynamic_call_edge(src: str, lineno: int) -> Edge:
    return Edge(
        src,
        f"external:dynamic-call@{lineno}",
        "call",
        certain=False,
        lineno=lineno,
        external=True,
    )


def _local_binding_names(syntax: SyntaxNode, raw_source: bytes) -> set[str]:
    """Names bound anywhere inside this declaration, which shadow package scope.

    Keyed on the node types that introduce a name rather than on the fields of
    the declaration itself, because a binding can appear at any depth: a closure
    passed as an argument brings its own parameter list, ``case v := <-ch``
    binds through a receive statement, and a type switch binds through its
    alias. Reading only the declaration's own ``parameters`` missed all three,
    and a missed shadow is not a missed edge -- it is a *certain* edge to the
    package-scope function the local name is hiding, which the code never calls.

    Over-collecting is the safe direction: a name gathered from a scope the call
    is not in only costs certainty, while a name missed invents a relationship.
    """

    names: set[str] = set()
    for child in (syntax, *_walk(syntax)):
        bound: SyntaxNode | None = None
        if child.type in _BINDING_LISTS:
            bound = child
        elif (field := _BINDING_STATEMENTS.get(child.type)) is not None:
            bound = child.child_by_field_name(field)
        elif child.type in {"var_spec", "const_spec"}:
            names.update(
                _node_text(item, raw_source)
                for item in child.named_children
                if item.type == "identifier"
            )
        if bound is not None:
            names.update(
                _node_text(item, raw_source)
                for item in (bound, *_walk(bound))
                if item.type == "identifier"
            )
    return names


def _entrypoint_ranks(index: _GoIndex) -> dict[str, int]:
    """Rank the ways a Go project can start, strongest evidence first.

    Rank 0 is the *file* holding ``func main`` in ``package main`` rather than
    the function, because Home is a region and a region is a file; the function
    follows at rank 1 so the strongest evidence still reads as one pair.
    """

    ranks: dict[str, int] = {}
    for definition in sorted(index.definitions, key=lambda item: item.node_id):
        node = index.node_by_id[definition.node_id]
        if node.kind != "function" or _is_method_id(node.id):
            continue
        parsed = index.parsed_by_module[definition.module_id]
        is_command = parsed.package_name == "main"
        if is_command and node.name == "main":
            ranks[parsed.module_id] = 0
            ranks[node.id] = 1
        elif node.name == "TestMain":
            ranks[node.id] = 2
        elif is_command and node.name[:1].isupper():
            ranks[node.id] = 3
    return ranks


__all__ = ["GoAdapter", "GoParseError"]
