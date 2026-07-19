"""Language-neutral project discovery and graph-composition contracts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from codemble.adapters.base import ConceptAnnotation, Graph, Node
from codemble.adapters.discovery import discover_source_files
from codemble.adapters.project import ProjectParseError, ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


class _FixtureAdapter:
    language = "typescript"
    file_extensions = frozenset({".ts"})

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        discovery = discover_source_files(path, self.file_extensions)
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        root, files = self.discover(path)
        nodes: list[Node] = []
        hashes: dict[str, str] = {}
        for file in files:
            relative = file.relative_to(root).as_posix()
            raw = file.read_bytes()
            source = raw.decode("utf-8")
            node_id = f"typescript:{relative}"
            nodes.append(
                Node(
                    id=node_id,
                    kind="module",
                    name=file.stem,
                    language=self.language,
                    file=relative,
                    lineno=1,
                    end_lineno=max(1, len(source.splitlines())),
                    loc=max(1, len(source.splitlines())),
                    region=node_id,
                    entrypoint_rank=0 if "main" in source else None,
                )
            )
            hashes[relative] = hashlib.sha256(raw).hexdigest()
        candidates = tuple(
            node.id for node in nodes if node.entrypoint_rank is not None
        )
        return Graph(
            nodes=tuple(nodes),
            edges=(),
            entrypoint_candidates=candidates,
            project_root=str(root),
            file_hashes=hashes,
        )

    def concepts(self, node: Node, source: str) -> list[ConceptAnnotation]:
        return []


class _CollidingAdapter(_FixtureAdapter):
    language = "javascript"

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        root, files = self.discover(path)
        relative = files[0].relative_to(root).as_posix()
        raw = files[0].read_bytes()
        return Graph(
            nodes=(
                Node(
                    id="app",
                    kind="module",
                    name="app",
                    language=self.language,
                    file=relative,
                    lineno=1,
                    end_lineno=1,
                    loc=1,
                    region="app",
                ),
            ),
            edges=(),
            entrypoint_candidates=(),
            project_root=str(root),
            file_hashes={relative: hashlib.sha256(raw).hexdigest()},
        )


def test_default_project_parser_preserves_the_python_graph() -> None:
    assert ProjectParser().parse(FIXTURE).to_json() == PythonAstAdapter().parse(FIXTURE).to_json()


def test_project_parser_composes_languages_and_resolves_home_globally(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text(
        'if __name__ == "__main__":\n    print("python")\n',
        encoding="utf-8",
    )
    (tmp_path / "main.ts").write_text("export function main() {}\n", encoding="utf-8")
    parser = ProjectParser((PythonAstAdapter(), _FixtureAdapter()))

    root, files = parser.discover(tmp_path)
    graph = parser.parse(tmp_path)

    assert root == tmp_path.resolve()
    assert [file.name for file in files] == ["app.py", "main.ts"]
    assert {node.language for node in graph.nodes} == {"python", "typescript"}
    assert graph.entrypoint_candidates == ("app", "typescript:main.ts")
    assert graph.selected_entrypoint is None
    selected = parser.parse(tmp_path, entrypoint="typescript:main.ts")
    assert selected.selected_entrypoint == "typescript:main.ts"
    assert next(region for region in selected.regions if region.home).language == "typescript"


def test_project_parser_rejects_cross_adapter_node_id_collisions(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("main\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")
    parser = ProjectParser((PythonAstAdapter(), _CollidingAdapter()))

    with pytest.raises(ProjectParseError, match="same node ID"):
        parser.parse(tmp_path)
