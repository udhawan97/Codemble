"""Python's stdlib-AST implementation of the Codemble language seam."""

from __future__ import annotations

import ast
import builtins
import hashlib
import tokenize
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from codemble.adapters.base import AdapterParseError, ConceptAnnotation, Edge, Graph, Node
from codemble.adapters.discovery import SourceDiscoveryError, discover_source_files
from codemble.graph.finalize import GraphFinalizationError, finalize_graph

_APP_FACTORIES = {"FastAPI", "Flask", "Typer"}
_BUILTIN_NAMES = frozenset(dir(builtins))


class PythonParseError(AdapterParseError):
    """The requested Python project cannot be discovered safely."""


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    path: Path
    relative_path: str
    module: str
    source: str
    digest: str
    tree: ast.Module | None


@dataclass(frozen=True, slots=True)
class _Definition:
    node_id: str
    syntax: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    parent_id: str
    enclosing_class_id: str | None
    function_ancestors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    local_name: str
    target: str
    external: bool


class _DefinitionCollector(ast.NodeVisitor):
    """Collect definitions while retaining their lexical ownership."""

    def __init__(self, parsed: _ParsedFile) -> None:
        self.parsed = parsed
        self.nodes: list[Node] = []
        self.definitions: list[_Definition] = []
        self._qualname: list[str] = []
        self._scope_ids: list[str] = [parsed.module]
        self._class_ids: list[str] = []
        self._function_ids: list[str] = []

    def visit_ClassDef(self, syntax: ast.ClassDef) -> None:
        node_id = self._node_id(syntax.name)
        self.nodes.append(self._node(syntax, node_id, "class"))
        self.definitions.append(
            _Definition(
                node_id=node_id,
                syntax=syntax,
                parent_id=self._scope_ids[-1],
                enclosing_class_id=self._class_ids[-1] if self._class_ids else None,
                function_ancestors=tuple(self._function_ids),
            )
        )
        self._qualname.append(syntax.name)
        self._scope_ids.append(node_id)
        self._class_ids.append(node_id)
        self.generic_visit(syntax)
        self._class_ids.pop()
        self._scope_ids.pop()
        self._qualname.pop()

    def visit_FunctionDef(self, syntax: ast.FunctionDef) -> None:
        self._visit_function(syntax)

    def visit_AsyncFunctionDef(self, syntax: ast.AsyncFunctionDef) -> None:
        self._visit_function(syntax)

    def _visit_function(self, syntax: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        node_id = self._node_id(syntax.name)
        self.nodes.append(self._node(syntax, node_id, "function"))
        self.definitions.append(
            _Definition(
                node_id=node_id,
                syntax=syntax,
                parent_id=self._scope_ids[-1],
                enclosing_class_id=self._class_ids[-1] if self._class_ids else None,
                function_ancestors=tuple(self._function_ids),
            )
        )
        self._qualname.append(syntax.name)
        self._scope_ids.append(node_id)
        self._function_ids.append(node_id)
        self.generic_visit(syntax)
        self._function_ids.pop()
        self._scope_ids.pop()
        self._qualname.pop()

    def _node_id(self, name: str) -> str:
        return ".".join((self.parsed.module, *self._qualname, name))

    def _node(
        self,
        syntax: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        node_id: str,
        kind: str,
    ) -> Node:
        end_lineno = syntax.end_lineno or syntax.lineno
        return Node(
            id=node_id,
            kind=kind,  # type: ignore[arg-type]
            name=syntax.name,
            language="python",
            file=self.parsed.relative_path,
            lineno=syntax.lineno,
            end_lineno=end_lineno,
            loc=end_lineno - syntax.lineno + 1,
            region=_region_for(self.parsed.module),
        )


class _ScopeFacts(ast.NodeVisitor):
    """Collect facts owned by one lexical scope, excluding nested scopes."""

    def __init__(self) -> None:
        self.imports: list[ast.Import | ast.ImportFrom] = []
        self.calls: list[ast.Call] = []

    def visit_Import(self, syntax: ast.Import) -> None:
        self.imports.append(syntax)

    def visit_ImportFrom(self, syntax: ast.ImportFrom) -> None:
        self.imports.append(syntax)

    def visit_Call(self, syntax: ast.Call) -> None:
        self.calls.append(syntax)
        self.generic_visit(syntax)

    def visit_ClassDef(self, syntax: ast.ClassDef) -> None:
        return

    def visit_FunctionDef(self, syntax: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, syntax: ast.AsyncFunctionDef) -> None:
        return

    def collect(self, statements: list[ast.stmt]) -> _ScopeFacts:
        for statement in statements:
            self.visit(statement)
        return self


class _ConceptCollector(ast.NodeVisitor):
    """Collect concepts inside one lexical owner without crossing into children."""

    def __init__(self, node_id: str, language: str, source: str) -> None:
        self.node_id = node_id
        self.language = language
        self.source_lines = source.splitlines()
        self.annotations: set[ConceptAnnotation] = set()

    def add(self, concept: str, syntax: ast.AST) -> None:
        lineno = getattr(syntax, "lineno", None)
        if not isinstance(lineno, int):
            return
        end_lineno = getattr(syntax, "end_lineno", lineno)
        if not isinstance(end_lineno, int):
            end_lineno = lineno
        snippet = self.source_lines[lineno - 1].strip() if lineno <= len(self.source_lines) else ""
        self.annotations.add(
            ConceptAnnotation(
                node_id=self.node_id,
                language=self.language,
                concept=concept,
                lineno=lineno,
                end_lineno=end_lineno,
                snippet=snippet[:240],
            )
        )

    def visit_FunctionDef(self, syntax: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, syntax: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, syntax: ast.ClassDef) -> None:
        return

    def visit_ListComp(self, syntax: ast.ListComp) -> None:
        self.add("comprehension", syntax)
        self.generic_visit(syntax)

    def visit_SetComp(self, syntax: ast.SetComp) -> None:
        self.add("comprehension", syntax)
        self.generic_visit(syntax)

    def visit_DictComp(self, syntax: ast.DictComp) -> None:
        self.add("comprehension", syntax)
        self.generic_visit(syntax)

    def visit_GeneratorExp(self, syntax: ast.GeneratorExp) -> None:
        self.add("generator", syntax)
        self.generic_visit(syntax)

    def visit_Yield(self, syntax: ast.Yield) -> None:
        self.add("generator", syntax)
        self.generic_visit(syntax)

    def visit_YieldFrom(self, syntax: ast.YieldFrom) -> None:
        self.add("generator", syntax)
        self.generic_visit(syntax)

    def visit_With(self, syntax: ast.With) -> None:
        self.add("context-manager", syntax)
        self.generic_visit(syntax)

    def visit_AsyncWith(self, syntax: ast.AsyncWith) -> None:
        self.add("context-manager", syntax)
        self.add("async-await", syntax)
        self.generic_visit(syntax)

    def visit_Await(self, syntax: ast.Await) -> None:
        self.add("async-await", syntax)
        self.generic_visit(syntax)

    def visit_AsyncFor(self, syntax: ast.AsyncFor) -> None:
        self.add("async-await", syntax)
        self.generic_visit(syntax)

    def visit_Try(self, syntax: ast.Try) -> None:
        self.add("exception-handling", syntax)
        self.generic_visit(syntax)

    def visit_TryStar(self, syntax: ast.TryStar) -> None:
        self.add("exception-handling", syntax)
        self.generic_visit(syntax)

    def visit_Raise(self, syntax: ast.Raise) -> None:
        self.add("exception-handling", syntax)
        self.generic_visit(syntax)

    def visit_AnnAssign(self, syntax: ast.AnnAssign) -> None:
        self.add("type-hint", syntax.annotation)
        self.generic_visit(syntax)


def _concepts_for_target(
    node: Node,
    target: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
) -> list[ConceptAnnotation]:
    collector = _ConceptCollector(node.id, node.language, source)
    if isinstance(target, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in target.decorator_list:
            collector.add("decorator", decorator)
    if isinstance(target, ast.AsyncFunctionDef):
        collector.add("async-await", target)
    if isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if target.name.startswith("__") and target.name.endswith("__"):
            collector.add("dunder-method", target)
        arguments = [
            *target.args.posonlyargs,
            *target.args.args,
            *target.args.kwonlyargs,
        ]
        if target.args.vararg is not None:
            arguments.append(target.args.vararg)
        if target.args.kwarg is not None:
            arguments.append(target.args.kwarg)
        for argument in arguments:
            if argument.annotation is not None:
                collector.add("type-hint", argument.annotation)
        if target.returns is not None:
            collector.add("type-hint", target.returns)
    for statement in target.body:
        collector.visit(statement)
    return sorted(
        collector.annotations,
        key=lambda item: (item.lineno, item.concept, item.end_lineno, item.snippet),
    )


class PythonAstAdapter:
    """Parse Python source into deterministic, render-ready graph data."""

    language = "python"
    file_extensions = frozenset({".py"})
    ignored_directories = frozenset()

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        """Return the parser's exact project root and accepted Python files."""

        return _discover_python_files(path.expanduser().resolve())

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        project_root, files = self.discover(path)
        parsed_files = tuple(_parse_file(file, project_root) for file in files)

        nodes: list[Node] = []
        definitions: list[_Definition] = []
        definition_by_id: dict[str, _Definition] = {}
        parsed_by_module = {parsed.module: parsed for parsed in parsed_files}
        modules = set(parsed_by_module)

        for parsed in parsed_files:
            module_node = _module_node(parsed)
            nodes.append(module_node)
            if parsed.tree is None:
                continue
            collector = _DefinitionCollector(parsed)
            collector.visit(parsed.tree)
            for node, definition in zip(collector.nodes, collector.definitions, strict=True):
                if node.id in definition_by_id:
                    continue
                nodes.append(node)
                definitions.append(definition)
                definition_by_id[node.id] = definition

        node_by_id = {node.id: node for node in nodes}
        entrypoint_ranks = _entrypoint_ranks(parsed_files, node_by_id)
        nodes = [
            replace(node, entrypoint_rank=entrypoint_ranks.get(node.id)) for node in nodes
        ]
        node_by_id = {node.id: node for node in nodes}

        import_edges: set[Edge] = set()
        module_bindings: dict[str, list[_ImportBinding]] = defaultdict(list)
        scope_bindings: dict[str, list[_ImportBinding]] = defaultdict(list)

        for parsed in parsed_files:
            if parsed.tree is None:
                continue
            for syntax in ast.walk(parsed.tree):
                if isinstance(syntax, (ast.Import, ast.ImportFrom)):
                    edges, _ = _resolve_import(parsed, syntax, modules, node_by_id)
                    import_edges.update(edges)

            module_facts = _ScopeFacts().collect(parsed.tree.body)
            for syntax in module_facts.imports:
                _, bindings = _resolve_import(parsed, syntax, modules, node_by_id)
                module_bindings[parsed.module].extend(bindings)

        definition_by_id = {definition.node_id: definition for definition in definitions}
        for definition in definitions:
            facts = _ScopeFacts().collect(definition.syntax.body)
            parsed = parsed_by_module[_module_from_node_id(definition.node_id, modules)]
            for syntax in facts.imports:
                _, bindings = _resolve_import(parsed, syntax, modules, node_by_id)
                scope_bindings[definition.node_id].extend(bindings)

        call_edges: list[Edge] = []
        children_by_parent: dict[str, list[Node]] = defaultdict(list)
        for definition in definitions:
            children_by_parent[definition.parent_id].append(node_by_id[definition.node_id])
        nodes_by_name: dict[str, list[Node]] = defaultdict(list)
        for node in nodes:
            if node.kind != "module":
                nodes_by_name[node.name].append(node)

        for definition in definitions:
            module = _module_from_node_id(definition.node_id, modules)
            facts = _ScopeFacts().collect(definition.syntax.body)
            bindings = list(module_bindings[module])
            for ancestor_id in definition.function_ancestors:
                bindings.extend(scope_bindings[ancestor_id])
            bindings.extend(scope_bindings[definition.node_id])
            binding_map = {binding.local_name: binding for binding in bindings}
            for call in facts.calls:
                call_edges.extend(
                    _resolve_call(
                        definition,
                        call,
                        module,
                        binding_map,
                        node_by_id,
                        nodes_by_name,
                        children_by_parent,
                    )
                )

        all_edges = [*import_edges, *call_edges]
        annotations: list[ConceptAnnotation] = []
        for parsed in parsed_files:
            if parsed.tree is None:
                continue
            annotations.extend(
                _concepts_for_target(node_by_id[parsed.module], parsed.tree, parsed.source)
            )
        for definition in definitions:
            annotations.extend(
                _concepts_for_target(
                    node_by_id[definition.node_id],
                    definition.syntax,
                    parsed_by_module[
                        _module_from_node_id(definition.node_id, modules)
                    ].source,
                )
            )
        draft = Graph(
            nodes=tuple(nodes),
            edges=tuple(all_edges),
            entrypoint_candidates=(),
            project_root=str(project_root),
            file_hashes={parsed.relative_path: parsed.digest for parsed in parsed_files},
            concept_annotations=tuple(annotations),
            partial_files=tuple(
                parsed.relative_path for parsed in parsed_files if parsed.tree is None
            ),
        )
        try:
            return finalize_graph(draft, entrypoint=entrypoint)
        except GraphFinalizationError as error:
            raise PythonParseError(str(error)) from error

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        """Return only AST-proven concepts owned by ``node``."""

        if node.partial:
            return []
        try:
            tree = ast.parse(source, filename=node.file)
        except (SyntaxError, ValueError):
            return []
        target: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef | None
        target = tree if node.kind == "module" else None
        if target is None:
            expected_types = {
                "class": (ast.ClassDef,),
                "function": (ast.FunctionDef, ast.AsyncFunctionDef),
            }[node.kind]
            target = next(
                (
                    candidate
                    for candidate in ast.walk(tree)
                    if isinstance(candidate, expected_types)
                    and candidate.name == node.name
                    and candidate.lineno == node.lineno
                ),
                None,
            )
        return _concepts_for_target(node, target, source) if target is not None else []


def _discover_python_files(requested: Path) -> tuple[Path, tuple[Path, ...]]:
    normalized = requested.expanduser().resolve()
    try:
        discovery = discover_source_files(normalized, PythonAstAdapter.file_extensions)
    except SourceDiscoveryError as error:
        raise PythonParseError(str(error)) from error
    if not discovery.files:
        if normalized.is_file():
            raise PythonParseError(f"expected a Python file or directory: {normalized}")
        raise PythonParseError(f"no Python files found under: {normalized}")
    return discovery.root, discovery.files


def _parse_file(path: Path, project_root: Path) -> _ParsedFile:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    relative = path.relative_to(project_root)
    try:
        with tokenize.open(path) as source_file:
            source = source_file.read()
        tree: ast.Module | None = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        source = raw.decode("utf-8", errors="replace")
        tree = None
    return _ParsedFile(
        path=path,
        relative_path=relative.as_posix(),
        module=_module_name(relative, project_root),
        source=source,
        digest=digest,
        tree=tree,
    )


def _module_name(relative: Path, project_root: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if (project_root / "__init__.py").is_file():
        parts.insert(0, project_root.name)
    if not parts:
        return project_root.name
    return ".".join(parts)


def _module_node(parsed: _ParsedFile) -> Node:
    line_count = max(1, len(parsed.source.splitlines()))
    return Node(
        id=parsed.module,
        kind="module",
        name=parsed.module.rsplit(".", 1)[-1],
        language="python",
        file=parsed.relative_path,
        lineno=1,
        end_lineno=line_count,
        loc=line_count,
        region=_region_for(parsed.module),
        partial=parsed.tree is None,
    )


def _region_for(module: str) -> str:
    return module


def _entrypoint_ranks(
    parsed_files: tuple[_ParsedFile, ...], node_by_id: dict[str, Node]
) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for parsed in parsed_files:
        if parsed.tree is None:
            continue
        module_rank: int | None = None
        if any(_is_main_guard(statement) for statement in parsed.tree.body):
            module_rank = 0
        for statement in parsed.tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                candidate_id = f"{parsed.module}.{statement.name}"
                if statement.name == "main" and candidate_id in node_by_id:
                    ranks[candidate_id] = min(ranks.get(candidate_id, 1), 1)
            if _is_app_assignment(statement):
                module_rank = min(module_rank if module_rank is not None else 2, 2)
        if parsed.path.name == "__main__.py":
            module_rank = min(module_rank if module_rank is not None else 3, 3)
        if module_rank is not None:
            ranks[parsed.module] = module_rank
    return ranks


def _is_main_guard(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.If) or not isinstance(statement.test, ast.Compare):
        return False
    comparison = statement.test
    if len(comparison.ops) != 1 or not isinstance(comparison.ops[0], ast.Eq):
        return False
    if len(comparison.comparators) != 1:
        return False
    left, right = comparison.left, comparison.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name)
        and right.id == "__name__"
        and isinstance(left, ast.Constant)
        and left.value == "__main__"
    )


def _is_app_assignment(statement: ast.stmt) -> bool:
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target, value = statement.targets[0], statement.value
    elif isinstance(statement, ast.AnnAssign):
        target, value = statement.target, statement.value
    if not isinstance(target, ast.Name) or target.id != "app" or not isinstance(value, ast.Call):
        return False
    factory = _dotted_name(value.func)
    return bool(factory and factory.rsplit(".", 1)[-1] in _APP_FACTORIES)


def _resolve_import(
    parsed: _ParsedFile,
    syntax: ast.Import | ast.ImportFrom,
    modules: set[str],
    node_by_id: dict[str, Node],
) -> tuple[list[Edge], list[_ImportBinding]]:
    edges: list[Edge] = []
    bindings: list[_ImportBinding] = []
    if isinstance(syntax, ast.Import):
        for alias in syntax.names:
            target = alias.name
            project_module = target if target in modules else None
            external = project_module is None
            edge_target = project_module or f"external:{target}"
            edges.append(
                Edge(parsed.module, edge_target, "import", certain=True, lineno=syntax.lineno, external=external)
            )
            local_name = alias.asname or target.split(".", 1)[0]
            binding_target = target if alias.asname else target.split(".", 1)[0]
            binding_external = not any(
                module == binding_target or module.startswith(f"{binding_target}.")
                for module in modules
            )
            bindings.append(_ImportBinding(local_name, binding_target, binding_external))
        return edges, bindings

    base = _absolute_import_base(parsed, syntax)
    for alias in syntax.names:
        candidate = f"{base}.{alias.name}" if base else alias.name
        edge_module = candidate if candidate in modules else base if base in modules else None
        external = edge_module is None
        edge_target = edge_module or f"external:{base or candidate}"
        edges.append(
            Edge(parsed.module, edge_target, "import", certain=True, lineno=syntax.lineno, external=external)
        )
        target = candidate
        target_external = target not in node_by_id and base not in modules
        bindings.append(_ImportBinding(alias.asname or alias.name, target, target_external))
    return edges, bindings


def _absolute_import_base(parsed: _ParsedFile, syntax: ast.ImportFrom) -> str:
    if syntax.level == 0:
        return syntax.module or ""
    module_parts = parsed.module.split(".")
    package_parts = module_parts if parsed.path.name == "__init__.py" else module_parts[:-1]
    ascend = syntax.level - 1
    if ascend > len(package_parts):
        return syntax.module or ""
    prefix = package_parts[: len(package_parts) - ascend]
    if syntax.module:
        prefix.extend(syntax.module.split("."))
    return ".".join(prefix)


def _resolve_call(
    definition: _Definition,
    syntax: ast.Call,
    module: str,
    bindings: dict[str, _ImportBinding],
    node_by_id: dict[str, Node],
    nodes_by_name: dict[str, list[Node]],
    children_by_parent: dict[str, list[Node]],
) -> list[Edge]:
    dotted = _dotted_name(syntax.func)
    name = _call_leaf_name(syntax.func)
    if name is None:
        return [
            Edge(
                definition.node_id,
                f"external:dynamic-call@{syntax.lineno}",
                "call",
                certain=False,
                lineno=syntax.lineno,
                external=True,
            )
        ]

    root = dotted.split(".", 1)[0] if dotted else name
    binding = bindings.get(root)
    if binding is not None:
        suffix = dotted.split(".", 1)[1] if dotted and "." in dotted else ""
        target = f"{binding.target}.{suffix}" if suffix else binding.target
        if target in node_by_id and node_by_id[target].kind != "module":
            return [_call_edge(definition.node_id, target, syntax.lineno, True, False)]
        if binding.external:
            return [
                _call_edge(definition.node_id, f"external:{target}", syntax.lineno, False, True)
            ]
        matches = nodes_by_name.get(name, [])
        if matches:
            return [
                _call_edge(definition.node_id, match.id, syntax.lineno, False, False)
                for match in sorted(matches, key=lambda node: node.id)
            ]
        return [
            _call_edge(
                definition.node_id, f"unresolved:{target}", syntax.lineno, False, False
            )
        ]

    if isinstance(syntax.func, ast.Attribute) and isinstance(syntax.func.value, ast.Name):
        if syntax.func.value.id in {"self", "cls"} and definition.enclosing_class_id:
            class_matches = [
                node
                for node in children_by_parent[definition.enclosing_class_id]
                if node.name == name
            ]
            if len(class_matches) == 1:
                return [
                    _call_edge(
                        definition.node_id, class_matches[0].id, syntax.lineno, True, False
                    )
                ]

    if isinstance(syntax.func, ast.Name):
        lexical_parents = (*reversed(definition.function_ancestors), module)
        for parent_id in lexical_parents:
            matches = [node for node in children_by_parent[parent_id] if node.name == name]
            if matches:
                certain = len(matches) == 1
                return [
                    _call_edge(definition.node_id, match.id, syntax.lineno, certain, False)
                    for match in sorted(matches, key=lambda node: node.id)
                ]

    matches = nodes_by_name.get(name, [])
    if matches:
        return [
            _call_edge(definition.node_id, match.id, syntax.lineno, False, False)
            for match in sorted(matches, key=lambda node: node.id)
        ]

    external_name = dotted or name
    if name in _BUILTIN_NAMES:
        external_name = f"builtins.{name}"
    return [
        _call_edge(
            definition.node_id,
            f"external:{external_name}",
            syntax.lineno,
            False,
            True,
        )
    ]


def _call_edge(src: str, dst: str, lineno: int, certain: bool, external: bool) -> Edge:
    return Edge(src, dst, "call", certain=certain, lineno=lineno, external=external)


def _dotted_name(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        parent = _dotted_name(expression.value)
        return f"{parent}.{expression.attr}" if parent else expression.attr
    return None


def _call_leaf_name(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return None


def _module_from_node_id(node_id: str, modules: set[str]) -> str:
    return max(
        (module for module in modules if node_id == module or node_id.startswith(f"{module}.")),
        key=len,
    )


__all__ = ["PythonAstAdapter", "PythonParseError"]
