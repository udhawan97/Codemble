"""Tree-sitter Rust implementation of the language seam."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from pathlib import Path

import tree_sitter_rust
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

_RUST_EXTENSIONS = frozenset({".rs"})
# Cargo writes every build artifact, including generated and vendored sources,
# under `target`. Those files are output rather than the project's own code.
_GENERATED_DIRECTORIES = frozenset({"target"})
# `crate`, `self` and `super` root a path inside the current crate. Anything
# else is either an in-scope module (Rust 2018 uniform paths) or an external
# crate, and the parser alone cannot tell those apart -- see `_resolve_use`.
_CRATE_LOCAL_ROOTS = frozenset({"crate", "self", "super"})
_PATH_SEGMENT_TYPES = frozenset(
    {
        "crate",
        "identifier",
        "metavariable",
        "primitive_type",
        "self",
        "super",
        "type_identifier",
    }
)
# A container is any structure a method or nested item can be qualified under.
# `impl` blocks carry the type they are written for, which is what makes
# `Formatter::new` resolvable without type inference.
_CONTAINER_KINDS = frozenset({"enum_item", "impl_item", "mod_item", "struct_item", "trait_item"})

_LANGUAGE = Language(tree_sitter_rust.language())


class RustParseError(AdapterParseError):
    """Rust source could not be mapped safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    project_root: Path
    relative_path: str
    module_id: str
    # The file's crate-relative module path, e.g. `src/util/text.rs` ->
    # ("util", "text"). Rust resolves `use` paths against this, so it is the
    # only thing that lets an in-project import be proven from the tree.
    module_path: tuple[str, ...]
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
    # The `Self` type of the nearest enclosing `impl`/`struct`/`enum`/`trait`,
    # which is how a `self.other()` call finds a method declared in a *different*
    # block for the same type.
    self_type: str | None


@dataclass(frozen=True, slots=True)
class _ResolvedModule:
    module_id: str
    certain: bool


@dataclass(frozen=True, slots=True)
class _UseBinding:
    local_name: str
    imported_name: str
    targets: tuple[_ResolvedModule, ...]
    external_crate: str | None


@dataclass(frozen=True, slots=True)
class _SyntaxEvidenceIndex:
    """Reusable ownership and lookup evidence derived from one syntax parse."""

    parsed_files: tuple[_ParsedFile, ...]
    definitions: tuple[_Definition, ...]
    nodes: tuple[Node, ...]
    parsed_by_module: dict[str, _ParsedFile]
    modules_by_path: dict[tuple[str, ...], tuple[str, ...]]
    definitions_by_module: dict[str, tuple[_Definition, ...]]
    definition_by_id: dict[str, _Definition]
    node_by_id: dict[str, Node]
    children_by_parent: dict[str, tuple[Node, ...]]
    nodes_by_module_name: dict[tuple[str, str], tuple[Node, ...]]
    containers_by_self_type: dict[tuple[str, str], tuple[str, ...]]
    nested_ranges_by_owner: dict[str, frozenset[tuple[int, int]]]
    local_bindings_by_owner: dict[str, frozenset[str]]

    @classmethod
    def build(
        cls,
        parsed_files: tuple[_ParsedFile, ...],
        definitions: tuple[_Definition, ...],
        nodes: tuple[Node, ...],
    ) -> _SyntaxEvidenceIndex:
        parsed_by_module = {parsed.module_id: parsed for parsed in parsed_files}
        modules_by_path: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for parsed in parsed_files:
            modules_by_path[parsed.module_path].append(parsed.module_id)

        definition_by_id = {definition.node_id: definition for definition in definitions}
        definitions_by_module_lists: dict[str, list[_Definition]] = defaultdict(list)
        nested_ranges: dict[str, set[tuple[int, int]]] = defaultdict(set)
        for definition in definitions:
            definitions_by_module_lists[definition.module_id].append(definition)
            syntax_range = (definition.syntax.start_byte, definition.syntax.end_byte)
            nested_ranges[definition.module_id].add(syntax_range)
            ancestor = definition.parent_id
            while ancestor in definition_by_id:
                nested_ranges[ancestor].add(syntax_range)
                ancestor = definition_by_id[ancestor].parent_id

        node_by_id = {node.id: node for node in nodes}
        children_by_parent, nodes_by_module_name = cls._node_lookups(definitions, node_by_id)
        containers: dict[tuple[str, str], list[str]] = defaultdict(list)
        for definition in definitions:
            if definition.self_type is None:
                continue
            if definition.syntax.type not in _CONTAINER_KINDS:
                continue
            containers[(definition.module_id, definition.self_type)].append(definition.node_id)
        frozen_ranges = {owner: frozenset(ranges) for owner, ranges in nested_ranges.items()}
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
            parsed_by_module=parsed_by_module,
            modules_by_path={
                path: tuple(sorted(module_ids))
                for path, module_ids in modules_by_path.items()
            },
            definitions_by_module={
                module_id: tuple(module_definitions)
                for module_id, module_definitions in definitions_by_module_lists.items()
            },
            definition_by_id=definition_by_id,
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            nodes_by_module_name=nodes_by_module_name,
            containers_by_self_type={
                key: tuple(sorted(ids)) for key, ids in containers.items()
            },
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
    ) -> tuple[dict[str, tuple[Node, ...]], dict[tuple[str, str], tuple[Node, ...]]]:
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


class RustAdapter:
    """Map Rust source into one deterministic, parser-proven graph."""

    language = "rust"
    file_extensions = _RUST_EXTENSIONS
    ignored_directories = _GENERATED_DIRECTORIES

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the exact Rust source scope accepted by this adapter."""

        normalized = path.expanduser().resolve()
        try:
            discovery = discover_source_files(
                normalized,
                self.file_extensions,
                ignored_directories=self.ignored_directories,
            )
        except SourceDiscoveryError as error:
            raise RustParseError(str(error)) from error
        if not discovery.files:
            if normalized.is_file():
                raise RustParseError(f"expected a Rust file or directory: {normalized}")
            raise RustParseError(f"no Rust files found under: {normalized}")
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        """Parse ``path`` using the official tree-sitter Rust grammar."""

        project_root, files = self.discover(path)
        return self.parse_files(project_root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        """Parse Rust files already owned by this adapter."""

        parsed_files = tuple(_parse_file(file, project_root) for file in files)

        nodes: list[Node] = []
        definitions: list[_Definition] = []
        for parsed in parsed_files:
            nodes.append(_module_node(parsed))
            file_nodes, file_definitions = _collect_definitions(parsed)
            nodes.extend(file_nodes)
            definitions.extend(file_definitions)

        index = _SyntaxEvidenceIndex.build(parsed_files, tuple(definitions), tuple(nodes))
        entrypoint_ranks = _entrypoint_ranks(index)
        index = index.with_nodes(
            tuple(
                replace(node, entrypoint_rank=entrypoint_ranks.get(node.id))
                for node in index.nodes
            )
        )

        import_edges: set[Edge] = set()
        bindings_by_module: dict[str, list[_UseBinding]] = defaultdict(list)
        for parsed in parsed_files:
            edges, bindings = _imports_for_file(parsed, index)
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
            raise RustParseError(str(error)) from error

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only tree-sitter-proven concepts owned by ``node``."""

        if node.partial or node.language != self.language:
            return []
        raw = source.encode("utf-8")
        relative = node.file
        parsed = _ParsedFile(
            path=Path(relative),
            project_root=Path("."),
            relative_path=relative,
            module_id=node.region,
            module_path=_module_path(relative),
            raw=raw,
            source=source,
            digest=hashlib.sha256(raw).hexdigest(),
            tree=Parser(_LANGUAGE).parse(raw),
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
    parsed = _ParsedFile(
        path=path,
        project_root=project_root,
        relative_path=relative,
        module_id=f"rust:{relative}",
        module_path=_module_path(relative),
        raw=raw,
        source=raw.decode("utf-8", errors="replace"),
        digest=hashlib.sha256(raw).hexdigest(),
        tree=Parser(_LANGUAGE).parse(raw),
    )
    note_file_parsed()
    return parsed


def _module_path(relative_path: str) -> tuple[str, ...]:
    """Map a file to the crate-relative module path Cargo would give it.

    This is filename convention rather than a reading of the crate's `mod`
    declarations, which is why every resolution built on it stays conservative:
    two files can land on the same path (`util.rs` beside `util/mod.rs`), and
    that ambiguity is reported rather than resolved.
    """

    parts = list(Path(relative_path).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "mod":
        parts = parts[:-1]
    if parts in (["lib"], ["main"]):
        parts = []
    return tuple(parts)


def _module_node(parsed: _ParsedFile) -> Node:
    line_count = max(1, len(parsed.source.splitlines()))
    return Node(
        id=parsed.module_id,
        kind="module",
        name=Path(parsed.relative_path).stem,
        language="rust",
        file=parsed.relative_path,
        lineno=1,
        end_lineno=line_count,
        loc=line_count,
        region=parsed.module_id,
        partial=parsed.tree.root_node.has_error,
    )


def _collect_definitions(parsed: _ParsedFile) -> tuple[list[Node], list[_Definition]]:
    nodes: list[Node] = []
    definitions: list[_Definition] = []
    used_ids: set[str] = {parsed.module_id}

    def add_definition(
        syntax: SyntaxNode,
        name: str,
        kind: str,
        segment: str,
        qualname: tuple[str, ...],
        parent_id: str,
        self_type: str | None,
    ) -> tuple[str, tuple[str, ...]]:
        next_qualname = (*qualname, segment)
        node_id = _unique_node_id(
            f"{parsed.module_id}::{'.'.join(next_qualname)}",
            syntax,
            used_ids,
        )
        used_ids.add(node_id)
        lineno, end_lineno = _line_span(syntax)
        nodes.append(
            Node(
                id=node_id,
                kind=kind,  # type: ignore[arg-type]
                name=name,
                language="rust",
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
                self_type=self_type,
            )
        )
        return node_id, next_qualname

    def visit(
        container: SyntaxNode,
        qualname: tuple[str, ...],
        parent_id: str,
        self_type: str | None,
    ) -> None:
        for child in container.named_children:
            if child.has_error:
                continue
            described = _describe_item(child, parsed.raw)
            if described is None:
                visit(child, qualname, parent_id, self_type)
                continue
            name, kind, segment, child_self_type = described
            node_id, child_qualname = add_definition(
                child,
                name,
                kind,
                segment,
                qualname,
                parent_id,
                self_type if child_self_type is None else child_self_type,
            )
            visit(
                child,
                child_qualname,
                node_id,
                self_type if child_self_type is None else child_self_type,
            )

    visit(parsed.tree.root_node, (), parsed.module_id, None)
    return nodes, definitions


def _describe_item(
    syntax: SyntaxNode,
    raw: bytes,
) -> tuple[str, str, str, str | None] | None:
    """Return ``(name, kind, id segment, self type)`` for one Rust structure.

    ``mod`` blocks, structs, enums, traits and impls all become ``class`` nodes
    because they are the containers a learner navigates into; ``NodeKind`` has no
    finer container word and inventing one would change a contract this seam does
    not own.
    """

    if syntax.type == "mod_item":
        # `mod util;` names a file that is parsed in its own right. Emitting a
        # node here would claim a second structure for that same source.
        if syntax.child_by_field_name("body") is None:
            return None
        name = _field_text(syntax, "name", raw)
        return None if name is None else (name, "class", name, name)
    if syntax.type in {"struct_item", "enum_item", "union_item", "trait_item"}:
        name = _field_text(syntax, "name", raw)
        return None if name is None else (name, "class", name, name)
    if syntax.type == "impl_item":
        return _describe_impl(syntax, raw)
    if syntax.type in {"function_item", "function_signature_item"}:
        name = _field_text(syntax, "name", raw)
        return None if name is None else (name, "function", name, None)
    return None


def _describe_impl(syntax: SyntaxNode, raw: bytes) -> tuple[str, str, str, str | None] | None:
    self_type_node = syntax.child_by_field_name("type")
    if self_type_node is None:
        return None
    self_type = _type_name(self_type_node, raw)
    if self_type is None:
        return None
    trait_node = syntax.child_by_field_name("trait")
    trait_name = _type_name(trait_node, raw) if trait_node is not None else None
    if trait_name is None:
        # `#` cannot appear in a Rust path, so an id segment built with it can
        # never collide with the `struct Formatter` declared beside the block,
        # and `impl` is a keyword no trait can be named.
        return (f"impl {self_type}", "class", f"{self_type}#impl", self_type)
    return (
        f"impl {trait_name} for {self_type}",
        "class",
        f"{self_type}#{trait_name}",
        self_type,
    )


def _type_name(syntax: SyntaxNode, raw: bytes) -> str | None:
    """Return the bare type name a path or generic application is written on."""

    if syntax.type in {"type_identifier", "identifier", "primitive_type"}:
        return _node_text(syntax, raw)
    if syntax.type in {"generic_type", "scoped_type_identifier", "scoped_identifier"}:
        for field in ("type", "name"):
            child = syntax.child_by_field_name(field)
            if child is not None:
                return _type_name(child, raw)
    if syntax.type == "reference_type":
        child = syntax.child_by_field_name("type")
        return None if child is None else _type_name(child, raw)
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
        "field_identifier",
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


def _path_segments(syntax: SyntaxNode | None, raw: bytes) -> tuple[str, ...] | None:
    if syntax is None or syntax.has_error:
        return None
    if syntax.type in _PATH_SEGMENT_TYPES:
        return (_node_text(syntax, raw),)
    if syntax.type in {"scoped_identifier", "scoped_type_identifier"}:
        name = syntax.child_by_field_name("name")
        tail = _path_segments(name, raw)
        if tail is None:
            return None
        path = syntax.child_by_field_name("path")
        if path is None:
            return tail
        head = _path_segments(path, raw)
        return None if head is None else head + tail
    if syntax.type == "generic_type":
        return _path_segments(syntax.child_by_field_name("type"), raw)
    return None


def _resolve_use(
    parsed: _ParsedFile,
    segments: tuple[str, ...],
    index: _SyntaxEvidenceIndex,
) -> tuple[tuple[_ResolvedModule, ...], str | None]:
    """Resolve one `use`-style path to project modules and/or an external crate.

    Returns the modules the path provably reaches plus the external crate name
    when the path could instead name a dependency. A crate-local root proves the
    path stays inside the project; a bare root does not, because Rust 2018
    uniform paths let `use util::x` mean either an in-scope module or a crate of
    the same name, so a project match there is only ever *possible*.
    """

    if not segments:
        return (), None
    root = segments[0]
    if root == "crate":
        return _match_modules(((segments[1:], 0),), index, certain=True), None
    if root == "self":
        return (
            _match_modules(((parsed.module_path + segments[1:], 0),), index, certain=True),
            None,
        )
    if root == "super":
        base = parsed.module_path
        rest = segments
        while rest and rest[0] == "super":
            if not base:
                # `super` at the crate root has no parent; nothing is proven.
                return (), None
            base = base[:-1]
            rest = rest[1:]
        return _match_modules(((base + rest, 0),), index, certain=True), None
    # A bare root is read both as a sibling of the current module and from the
    # crate root. Each reading must consume at least the path's own first
    # segment, or `use std::fmt::Write` inside `util` would "match" `util`
    # itself on the empty remainder.
    candidates = (
        (parsed.module_path + segments, len(parsed.module_path) + 1),
        (segments, 1),
    )
    return _match_modules(candidates, index, certain=False), root


def _match_modules(
    candidates: tuple[tuple[tuple[str, ...], int], ...],
    index: _SyntaxEvidenceIndex,
    *,
    certain: bool,
) -> tuple[_ResolvedModule, ...]:
    """Take the longest module path each candidate proves, never a shorter one.

    Rust resolves `crate::util::helper` to the submodule `util::helper` when that
    file exists and to an item inside `util` otherwise, so only the longest
    matching prefix is evidence. Several files sharing one module path is a real
    ambiguity, so each of them is reported as possible rather than exact.
    """

    resolved: dict[str, bool] = {}
    for candidate, minimum_length in candidates:
        for length in range(len(candidate), minimum_length - 1, -1):
            module_ids = index.modules_by_path.get(candidate[:length])
            if not module_ids:
                continue
            exact = certain and len(module_ids) == 1
            for module_id in module_ids:
                resolved[module_id] = resolved.get(module_id, False) or exact
            break
    return tuple(
        _ResolvedModule(module_id, module_certain)
        for module_id, module_certain in sorted(resolved.items())
    )


def _use_leaves(
    syntax: SyntaxNode,
    prefix: tuple[str, ...],
    raw: bytes,
) -> list[tuple[tuple[str, ...], str | None]]:
    """Flatten one `use` argument into (path, local name) pairs.

    A local name of ``None`` means the form binds no single importable name --
    a glob, or `use crate::util::{self}` -- so it yields an import edge but never
    a call binding.
    """

    if syntax.has_error:
        return []
    if syntax.type == "use_as_clause":
        path = _path_segments(syntax.child_by_field_name("path"), raw)
        alias = syntax.child_by_field_name("alias")
        if path is None or alias is None:
            return []
        return [(prefix + path, _node_text(alias, raw))]
    if syntax.type == "use_wildcard":
        inner = next((child for child in syntax.named_children), None)
        path = _path_segments(inner, raw) if inner is not None else ()
        return [] if path is None else [(prefix + path, None)]
    if syntax.type == "scoped_use_list":
        path = _path_segments(syntax.child_by_field_name("path"), raw) or ()
        listing = syntax.child_by_field_name("list")
        if listing is None:
            return []
        return _use_leaves(listing, prefix + path, raw)
    if syntax.type == "use_list":
        leaves: list[tuple[tuple[str, ...], str | None]] = []
        for child in syntax.named_children:
            leaves.extend(_use_leaves(child, prefix, raw))
        return leaves
    if syntax.type == "self":
        return [(prefix, None)]
    path = _path_segments(syntax, raw)
    if path is None:
        return []
    return [(prefix + path, path[-1])]


def _imports_for_file(
    parsed: _ParsedFile,
    index: _SyntaxEvidenceIndex,
) -> tuple[list[Edge], list[_UseBinding]]:
    edges: list[Edge] = []
    bindings: list[_UseBinding] = []
    for syntax in _walk(parsed.tree.root_node):
        if syntax.has_error or syntax.type != "use_declaration":
            continue
        argument = syntax.child_by_field_name("argument")
        if argument is None:
            continue
        lineno = syntax.start_point.row + 1
        for path, local_name in _use_leaves(argument, (), parsed.raw):
            resolved, external_crate = _resolve_use(parsed, path, index)
            edges.extend(_import_edges(parsed, lineno, path, resolved, external_crate))
            if local_name is not None:
                bindings.append(
                    _UseBinding(local_name, path[-1], resolved, None if resolved else external_crate)
                )
    return edges, bindings


def _import_edges(
    parsed: _ParsedFile,
    lineno: int,
    path: tuple[str, ...],
    resolved: tuple[_ResolvedModule, ...],
    external_crate: str | None,
) -> list[Edge]:
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
    if external_crate is not None:
        return [
            Edge(
                src=parsed.module_id,
                dst=f"external:{external_crate}",
                kind="import",
                certain=True,
                lineno=lineno,
                external=True,
            )
        ]
    return [
        Edge(
            src=parsed.module_id,
            dst=f"unresolved:{parsed.module_id}:{'::'.join(path)}",
            kind="import",
            certain=False,
            lineno=lineno,
        )
    ]


def _call_edges(
    index: _SyntaxEvidenceIndex,
    bindings_by_module: dict[str, list[_UseBinding]],
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
            if syntax.has_error or syntax.type != "call_expression":
                continue
            edges.extend(
                _resolve_call(
                    definition,
                    syntax,
                    parsed,
                    binding_map,
                    index,
                    index.local_bindings_by_owner[definition.node_id],
                )
            )
    return edges


def _resolve_call(
    definition: _Definition,
    syntax: SyntaxNode,
    parsed: _ParsedFile,
    bindings: dict[str, _UseBinding],
    index: _SyntaxEvidenceIndex,
    local_binding_names: frozenset[str],
) -> list[Edge]:
    lineno = syntax.start_point.row + 1
    target = syntax.child_by_field_name("function")
    if target is not None and target.type == "generic_function":
        target = target.child_by_field_name("function")
    if target is None:
        return [_dynamic_call_edge(definition.node_id, lineno)]

    if target.type == "identifier":
        return _resolve_named_call(
            definition,
            _node_text(target, parsed.raw),
            lineno,
            bindings,
            index,
            local_binding_names,
        )

    if target.type == "field_expression":
        return _resolve_method_call(definition, target, parsed, lineno, index)

    segments = _path_segments(target, parsed.raw)
    if segments is None:
        return [_dynamic_call_edge(definition.node_id, lineno)]
    if len(segments) == 1:
        return _resolve_named_call(
            definition,
            segments[0],
            lineno,
            bindings,
            index,
            local_binding_names,
        )
    return _resolve_path_call(definition, segments, parsed, lineno, bindings, index)


def _resolve_named_call(
    definition: _Definition,
    name: str,
    lineno: int,
    bindings: dict[str, _UseBinding],
    index: _SyntaxEvidenceIndex,
    local_binding_names: frozenset[str],
) -> list[Edge]:
    nested = [
        node
        for node in index.children_by_parent.get(definition.node_id, ())
        if node.name == name
    ]
    if nested:
        return _candidate_edges(definition.node_id, nested, lineno, certain=len(nested) == 1)
    if name in local_binding_names:
        # A local `let` or parameter shadows every item of the same name, so the
        # module-level function that shares it is not what is being called.
        return [_unresolved_call_edge(definition.node_id, definition.node_id, name, lineno)]
    siblings = [
        node
        for node in index.children_by_parent.get(definition.parent_id, ())
        if node.name == name
    ]
    if siblings:
        return _candidate_edges(definition.node_id, siblings, lineno, certain=len(siblings) == 1)
    module_level = list(index.nodes_by_module_name.get((definition.module_id, name), ()))
    if module_level:
        return _candidate_edges(
            definition.node_id,
            module_level,
            lineno,
            certain=len(module_level) == 1,
        )
    binding = bindings.get(name)
    if binding is not None:
        return _binding_call_edges(definition.node_id, binding, binding.imported_name, lineno, index)
    return [_unresolved_call_edge(definition.node_id, definition.module_id, name, lineno)]


def _resolve_method_call(
    definition: _Definition,
    target: SyntaxNode,
    parsed: _ParsedFile,
    lineno: int,
    index: _SyntaxEvidenceIndex,
) -> list[Edge]:
    field = target.child_by_field_name("field")
    if field is None:
        return [_dynamic_call_edge(definition.node_id, lineno)]
    name = _node_text(field, parsed.raw)
    receiver = target.child_by_field_name("value")
    if receiver is not None and receiver.type == "self" and definition.self_type is not None:
        candidates = _self_type_members(definition, name, index)
        if candidates:
            return _candidate_edges(
                definition.node_id,
                candidates,
                lineno,
                certain=len(candidates) == 1,
            )
    # Any other receiver needs the type of an expression, which no syntax tree
    # carries: a trait object or a generic parameter can be any implementation.
    # Same-name structures in this module are offered as possible calls only.
    possible = list(index.nodes_by_module_name.get((definition.module_id, name), ()))
    if possible:
        return _candidate_edges(definition.node_id, possible, lineno, certain=False)
    return [_unresolved_call_edge(definition.node_id, definition.module_id, name, lineno)]


def _self_type_members(
    definition: _Definition,
    name: str,
    index: _SyntaxEvidenceIndex,
) -> list[Node]:
    """Return same-type members, across every block written for that type."""

    members: list[Node] = []
    for container_id in index.containers_by_self_type.get(
        (definition.module_id, definition.self_type or ""),
        (),
    ):
        members.extend(
            node
            for node in index.children_by_parent.get(container_id, ())
            if node.name == name
        )
    return members


def _resolve_path_call(
    definition: _Definition,
    segments: tuple[str, ...],
    parsed: _ParsedFile,
    lineno: int,
    bindings: dict[str, _UseBinding],
    index: _SyntaxEvidenceIndex,
) -> list[Edge]:
    name = segments[-1]
    prefix = segments[:-1]

    if len(prefix) == 1:
        local_members = [
            node
            for container_id in index.containers_by_self_type.get(
                (definition.module_id, prefix[0]),
                (),
            )
            for node in index.children_by_parent.get(container_id, ())
            if node.name == name
        ]
        if local_members:
            return _candidate_edges(
                definition.node_id,
                local_members,
                lineno,
                certain=len(local_members) == 1,
            )
        binding = bindings.get(prefix[0])
        if binding is not None:
            return _binding_member_edges(definition.node_id, binding, name, lineno, index)

    resolved, external_crate = _resolve_use(parsed, prefix, index)
    candidates: list[tuple[Node, bool]] = []
    for target in resolved:
        candidates.extend(
            (node, target.certain)
            for node in index.nodes_by_module_name.get((target.module_id, name), ())
        )
    if candidates:
        unambiguous = len(candidates) == 1
        return [
            _call_edge(definition.node_id, node.id, lineno, certain=unambiguous and path_certain)
            for node, path_certain in sorted(candidates, key=lambda item: item[0].id)
        ]
    if external_crate is not None or segments[0] not in _CRATE_LOCAL_ROOTS:
        return [
            Edge(
                definition.node_id,
                f"external:{'::'.join(segments)}",
                "call",
                certain=False,
                lineno=lineno,
                external=True,
            )
        ]
    return [
        _unresolved_call_edge(
            definition.node_id,
            definition.module_id,
            "::".join(segments),
            lineno,
        )
    ]


def _binding_call_edges(
    src: str,
    binding: _UseBinding,
    imported_name: str,
    lineno: int,
    index: _SyntaxEvidenceIndex,
) -> list[Edge]:
    candidates: list[tuple[Node, bool]] = []
    for target in binding.targets:
        candidates.extend(
            (node, target.certain)
            for node in index.nodes_by_module_name.get((target.module_id, imported_name), ())
        )
    if candidates:
        unambiguous = len(candidates) == 1
        return [
            _call_edge(src, node.id, lineno, certain=unambiguous and path_certain)
            for node, path_certain in sorted(candidates, key=lambda item: item[0].id)
        ]
    if binding.external_crate is not None:
        return [
            Edge(
                src,
                f"external:{binding.external_crate}::{imported_name}",
                "call",
                certain=False,
                lineno=lineno,
                external=True,
            )
        ]
    targets = ",".join(target.module_id for target in binding.targets)
    return [
        Edge(
            src,
            f"unresolved:{targets}:{imported_name}",
            "call",
            certain=False,
            lineno=lineno,
        )
    ]


def _binding_member_edges(
    src: str,
    binding: _UseBinding,
    name: str,
    lineno: int,
    index: _SyntaxEvidenceIndex,
) -> list[Edge]:
    """Resolve `Imported::member()` through the type the `use` brought in."""

    candidates: list[tuple[Node, bool]] = []
    for target in binding.targets:
        for container_id in index.containers_by_self_type.get(
            (target.module_id, binding.imported_name),
            (),
        ):
            candidates.extend(
                (node, target.certain)
                for node in index.children_by_parent.get(container_id, ())
                if node.name == name
            )
    if candidates:
        unambiguous = len(candidates) == 1
        return [
            _call_edge(src, node.id, lineno, certain=unambiguous and path_certain)
            for node, path_certain in sorted(candidates, key=lambda item: item[0].id)
        ]
    return _binding_call_edges(src, binding, name, lineno, index)


def _candidate_edges(src: str, nodes: list[Node], lineno: int, *, certain: bool) -> list[Edge]:
    return [
        _call_edge(src, node.id, lineno, certain=certain)
        for node in sorted(nodes, key=lambda node: node.id)
    ]


def _call_edge(src: str, dst: str, lineno: int, certain: bool) -> Edge:
    return Edge(src, dst, "call", certain=certain, lineno=lineno)


def _unresolved_call_edge(src: str, scope: str, name: str, lineno: int) -> Edge:
    return Edge(src, f"unresolved:{scope}:{name}", "call", certain=False, lineno=lineno)


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
    names: set[str] = set()
    parameters = syntax.child_by_field_name("parameters")
    if parameters is not None:
        names.update(_pattern_identifiers(parameters, raw))
    for child in _walk_owned(syntax, nested_definition_ranges):
        if child.type in {"let_declaration", "for_expression", "let_condition"}:
            pattern = child.child_by_field_name("pattern")
            if pattern is not None:
                names.update(_pattern_identifiers(pattern, raw))
        elif child.type == "closure_parameters":
            names.update(_pattern_identifiers(child, raw))
    return names


def _pattern_identifiers(syntax: SyntaxNode, raw: bytes) -> set[str]:
    return {
        _node_text(node, raw)
        for node in (syntax, *_walk(syntax))
        if node.type == "identifier"
    }


def _concept_annotations(index: _SyntaxEvidenceIndex) -> tuple[ConceptAnnotation, ...]:
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
    source_lines = parsed.source.splitlines()
    for candidate in candidates:
        if candidate.has_error:
            continue
        for concept in _concepts_for_syntax(candidate, parsed.raw):
            lineno, end_lineno = _line_span(candidate)
            snippet = source_lines[lineno - 1].strip() if 0 < lineno <= len(source_lines) else ""
            annotations.add(
                ConceptAnnotation(
                    node_id=owner.id,
                    language="rust",
                    concept=concept,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    snippet=snippet[:240],
                )
            )
    return annotations


def _concepts_for_syntax(syntax: SyntaxNode, raw: bytes) -> tuple[str, ...]:
    concepts: list[str] = []
    if syntax.type in {"reference_type", "self_parameter", "reference_expression"}:
        borrowed = syntax.type != "self_parameter" or any(
            child.type == "&" for child in syntax.children
        )
        if borrowed:
            concepts.append("borrowing")
            if any(child.type == "mutable_specifier" for child in syntax.children):
                concepts.append("mutable-borrow")
    if syntax.type in {"lifetime", "lifetime_parameter"}:
        concepts.append("lifetime")
    if syntax.type == "trait_item":
        concepts.append("trait")
    if syntax.type == "impl_item":
        concepts.append("impl")
    if syntax.type in {"match_expression", "let_condition"}:
        concepts.append("pattern-matching")
    if syntax.type == "try_expression":
        concepts.append("question-mark-operator")
    if syntax.type == "type_identifier" and _node_text(syntax, raw) in {"Option", "Result"}:
        concepts.append("result-option")
    if syntax.type in {"macro_invocation", "macro_definition"}:
        concepts.append("macro")
    if syntax.type == "await_expression":
        concepts.append("async-await")
    if syntax.type == "unsafe_block":
        concepts.append("unsafe")
    if syntax.type == "function_modifiers":
        modifiers = {child.type for child in syntax.children}
        if "async" in modifiers:
            concepts.append("async-await")
        if "unsafe" in modifiers:
            concepts.append("unsafe")
    return tuple(concepts)


def _entrypoint_ranks(index: _SyntaxEvidenceIndex) -> dict[str, int]:
    """Rank `fn main` in main.rs first, then lib.rs's public API, tests last."""

    ranks: dict[str, int] = {}
    for parsed in index.parsed_files:
        file_name = Path(parsed.relative_path).name
        definitions = index.definitions_by_module.get(parsed.module_id, ())
        top_level = [
            definition for definition in definitions if definition.parent_id == parsed.module_id
        ]
        if file_name == "main.rs":
            for definition in top_level:
                node = index.node_by_id[definition.node_id]
                if node.kind == "function" and node.name == "main":
                    ranks[node.id] = 0
        elif file_name == "lib.rs":
            ranks[parsed.module_id] = 1
            for definition in top_level:
                if _has_visibility(definition.syntax):
                    ranks[definition.node_id] = 2
        for definition in definitions:
            if _is_test(definition.syntax, parsed.raw):
                # Tests rank last even when they are also public API, because a
                # learner's Home should be the code under test.
                ranks[definition.node_id] = 3
    return ranks


def _has_visibility(syntax: SyntaxNode) -> bool:
    return any(child.type == "visibility_modifier" for child in syntax.children)


def _is_test(syntax: SyntaxNode, raw: bytes) -> bool:
    """Report whether `#[test]` is attached, reading only preceding attributes.

    Attributes are siblings of the item they decorate in this grammar, so the
    evidence is the unbroken run of `attribute_item` nodes immediately above it.
    """

    sibling = syntax.prev_named_sibling
    while sibling is not None and sibling.type == "attribute_item":
        for attribute in sibling.named_children:
            if attribute.type != "attribute":
                continue
            path = _path_segments(attribute.named_children[0], raw) if (
                attribute.named_child_count
            ) else None
            if path is not None and path[-1] == "test":
                return True
        sibling = sibling.prev_named_sibling
    return False


__all__ = ["RustAdapter", "RustParseError"]
