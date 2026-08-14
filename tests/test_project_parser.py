"""Language-neutral project discovery and graph-composition contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import codemble.adapters.discovery as source_discovery
from codemble.adapters.base import ConceptAnnotation, Graph, Node
from codemble.adapters.discovery import discover_source_files
from codemble.adapters.parse_progress import ParseCancelled
from codemble.adapters.project import ProjectIntake, ProjectParseError, ProjectParser
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.graph import build_map

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"


class _FixtureAdapter:
    language = "typescript"
    file_extensions = frozenset({".ts"})
    ignored_directories = frozenset()

    def discover(self, path: Path) -> tuple[Path, tuple[Path, ...]]:
        discovery = discover_source_files(path, self.file_extensions)
        return discovery.root, discovery.files

    def parse(self, path: Path, *, entrypoint: str | None = None) -> Graph:
        root, files = self.discover(path)
        return self.parse_files(root, files, entrypoint=entrypoint)

    def parse_files(
        self,
        root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
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

    def parse_files(
        self,
        root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
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


class _CountingFixtureAdapter(_FixtureAdapter):
    def __init__(self) -> None:
        self.parse_calls = 0

    def parse_files(
        self,
        root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        self.parse_calls += 1
        return super().parse_files(root, files, entrypoint=entrypoint)


class _CountingPythonAdapter(PythonAstAdapter):
    def __init__(self) -> None:
        self.parse_calls = 0

    def parse_files(
        self,
        project_root: Path,
        files: tuple[Path, ...],
        *,
        entrypoint: str | None = None,
    ) -> Graph:
        self.parse_calls += 1
        return super().parse_files(project_root, files, entrypoint=entrypoint)


def test_default_project_parser_preserves_the_python_graph() -> None:
    assert ProjectParser().parse(FIXTURE).to_json() == PythonAstAdapter().parse(FIXTURE).to_json()


def test_unchanged_project_reuses_exact_derived_evidence(tmp_path: Path) -> None:
    source = tmp_path / "main.ts"
    source.write_text("export function main() {}\n", encoding="utf-8")
    adapter = _CountingFixtureAdapter()
    parser = ProjectParser((adapter,))

    cold = parser.parse(tmp_path)
    warm = parser.parse(tmp_path)

    assert adapter.parse_calls == 1
    assert warm.to_json() == cold.to_json()
    assert json.dumps(
        build_map(warm), separators=(",", ":"), ensure_ascii=False
    ) == json.dumps(build_map(cold), separators=(",", ":"), ensure_ascii=False)


def test_cache_retains_no_concept_snippet_source_text(tmp_path: Path) -> None:
    marker = "CACHE_PRIVATE_MARKER_6f0c1b9d"
    (tmp_path / "app.py").write_text(
        f"def main() -> list[int]:  # {marker}\n    return []\n",
        encoding="utf-8",
    )
    parser = ProjectParser((PythonAstAdapter(),))

    cold = parser.parse(tmp_path)
    assert marker in cold.to_json()
    assert marker not in repr(parser._evidence_cache._entries)

    warm = parser.parse(tmp_path)
    assert warm.to_json() == cold.to_json()
    assert json.dumps(
        build_map(warm), separators=(",", ":"), ensure_ascii=False
    ) == json.dumps(build_map(cold), separators=(",", ":"), ensure_ascii=False)


def test_polyglot_cache_rehydrates_exact_graph_and_map_snippets() -> None:
    parser = ProjectParser()

    cold = parser.parse(POLYGLOT_FIXTURE)
    warm = parser.parse(POLYGLOT_FIXTURE)

    assert warm.to_json() == cold.to_json()
    assert json.dumps(
        build_map(warm), separators=(",", ":"), ensure_ascii=False
    ) == json.dumps(build_map(cold), separators=(",", ":"), ensure_ascii=False)


def test_fingerprint_cancellation_stops_before_later_files_and_does_not_poison_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("a.ts", "b.ts", "c.ts"):
        (tmp_path / name).write_text("export const value = 1;\n", encoding="utf-8")

    class _CancelledProgress:
        cancelled = False

        def stage(self, _stage: str) -> None:
            return

        def files_total(self, _total: int) -> None:
            return

        def file_parsed(self) -> None:
            return

        def detail(self, _detail: str) -> None:
            return

    progress = _CancelledProgress()
    original_read_bytes = Path.read_bytes
    sources_read: list[str] = []

    def read_then_cancel(path: Path) -> bytes:
        raw = original_read_bytes(path)
        if path.suffix == ".ts":
            sources_read.append(path.name)
            progress.cancelled = True
        return raw

    monkeypatch.setattr(Path, "read_bytes", read_then_cancel)
    parser = ProjectParser((_FixtureAdapter(),))

    with pytest.raises(ParseCancelled):
        parser.parse(tmp_path, progress=progress)

    assert sources_read == ["a.ts"]
    assert parser.cache_info()["entries"] == 0
    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)
    assert parser.parse(tmp_path).to_json() == ProjectParser(
        (_FixtureAdapter(),)
    ).parse(tmp_path).to_json()


@pytest.mark.parametrize("change", ["edit", "delete", "rename"])
def test_changed_source_rebuilds_and_matches_a_fresh_parser(
    tmp_path: Path,
    change: str,
) -> None:
    (tmp_path / "main.ts").write_text(
        "export function main() {}\n", encoding="utf-8"
    )
    helper = tmp_path / "helper.ts"
    helper.write_text("export const helper = 1;\n", encoding="utf-8")
    adapter = _CountingFixtureAdapter()
    parser = ProjectParser((adapter,))
    parser.parse(tmp_path)
    parser.parse(tmp_path)

    if change == "edit":
        helper.write_text("export function main() {}\n", encoding="utf-8")
    elif change == "delete":
        helper.unlink()
    else:
        helper.rename(tmp_path / "renamed.ts")

    rebuilt = parser.parse(tmp_path)
    fresh = ProjectParser((_FixtureAdapter(),)).parse(tmp_path)

    assert adapter.parse_calls == 2
    assert rebuilt.to_json() == fresh.to_json()
    assert json.dumps(
        build_map(rebuilt), separators=(",", ":"), ensure_ascii=False
    ) == json.dumps(build_map(fresh), separators=(",", ":"), ensure_ascii=False)
    assert parser.cache_info()["evictions"] == 1


def test_changed_source_preserves_only_matching_file_evidence(
    tmp_path: Path,
) -> None:
    for name in ("main.ts", "one.ts", "two.ts"):
        (tmp_path / name).write_text(
            f"export const {Path(name).stem} = 1;\n",
            encoding="utf-8",
        )
    adapter = _CountingFixtureAdapter()
    parser = ProjectParser((adapter,))

    parser.parse(tmp_path)
    before = parser.cache_info()
    (tmp_path / "two.ts").write_text(
        "export function changed() {}\n",
        encoding="utf-8",
    )
    rebuilt = parser.parse(tmp_path)
    after = parser.cache_info()

    assert rebuilt.to_json() == ProjectParser((_FixtureAdapter(),)).parse(
        tmp_path
    ).to_json()
    assert adapter.parse_calls == 2
    assert before["file_entries"] == after["file_entries"] == 3
    assert after["partial_file_matches"] - before["partial_file_matches"] == 2
    assert after["file_invalidations"] - before["file_invalidations"] == 1


def test_partial_file_recovery_removes_stale_evidence(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def broken(:\n", encoding="utf-8")
    adapter = _CountingPythonAdapter()
    parser = ProjectParser((adapter,))

    partial = parser.parse(tmp_path)
    warm_partial = parser.parse(tmp_path)
    source.write_text("def ready() -> None:\n    pass\n", encoding="utf-8")
    recovered = parser.parse(tmp_path)
    fresh = ProjectParser((PythonAstAdapter(),)).parse(tmp_path)

    assert partial.partial_files == ("app.py",)
    assert warm_partial.to_json() == partial.to_json()
    assert recovered.partial_files == ()
    assert recovered.to_json() == fresh.to_json()
    assert adapter.parse_calls == 2


def test_unsupported_sources_refresh_around_a_supported_cache_hit(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.ts").write_text(
        "export function main() {}\n", encoding="utf-8"
    )
    adapter = _CountingFixtureAdapter()
    parser = ProjectParser((adapter,))
    parser.parse(tmp_path)
    (tmp_path / "service.go").write_text("package main\n", encoding="utf-8")

    refreshed = parser.parse(tmp_path)

    assert adapter.parse_calls == 1
    assert [row.extension for row in refreshed.unsupported_sources] == [".go"]


def test_cache_identity_includes_project_root_and_adapter_version(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    for root in (first_root, second_root):
        (root / "main.ts").write_text(
            "export function main() {}\n", encoding="utf-8"
        )
    adapter = _CountingFixtureAdapter()
    parser = ProjectParser((adapter,))

    first = parser.parse(first_root)
    second = parser.parse(second_root)
    adapter.evidence_version = "2"
    versioned = parser.parse(second_root)

    assert adapter.parse_calls == 3
    assert first.project_root == str(first_root.resolve())
    assert second.project_root == versioned.project_root == str(second_root.resolve())
    assert versioned.to_json() == ProjectParser((_FixtureAdapter(),)).parse(
        second_root
    ).to_json()


def test_dialect_change_rebuilds_and_matches_a_fresh_parser(tmp_path: Path) -> None:
    source = tmp_path / "main.ts"
    source.write_text("export function main() {}\n", encoding="utf-8")
    adapter = _CountingFixtureAdapter()
    adapter.file_extensions = frozenset({".js", ".ts"})
    parser = ProjectParser((adapter,))
    parser.parse(tmp_path)
    source.rename(tmp_path / "main.js")

    rebuilt = parser.parse(tmp_path)
    fresh_adapter = _FixtureAdapter()
    fresh_adapter.file_extensions = frozenset({".js", ".ts"})
    fresh = ProjectParser((fresh_adapter,)).parse(tmp_path)

    assert adapter.parse_calls == 2
    assert rebuilt.to_json() == fresh.to_json()
    assert json.dumps(
        build_map(rebuilt), separators=(",", ":"), ensure_ascii=False
    ) == json.dumps(build_map(fresh), separators=(",", ":"), ensure_ascii=False)


def test_discovery_configuration_change_removes_stale_facts_and_matches_fresh(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.ts").write_text(
        "export function main() {}\n", encoding="utf-8"
    )
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "stale.ts").write_text(
        "export const stale = true;\n", encoding="utf-8"
    )
    adapter = _CountingFixtureAdapter()
    parser = ProjectParser((adapter,))
    assert len(parser.parse(tmp_path).nodes) == 2
    adapter.ignored_directories = frozenset({"generated"})

    rebuilt = parser.parse(tmp_path)
    fresh_adapter = _FixtureAdapter()
    fresh_adapter.ignored_directories = frozenset({"generated"})
    fresh = ProjectParser((fresh_adapter,)).parse(tmp_path)

    assert adapter.parse_calls == 2
    assert [node.file for node in rebuilt.nodes] == ["main.ts"]
    assert rebuilt.to_json() == fresh.to_json()
    assert json.dumps(
        build_map(rebuilt), separators=(",", ":"), ensure_ascii=False
    ) == json.dumps(build_map(fresh), separators=(",", ":"), ensure_ascii=False)


def test_project_intake_reuses_discovered_file_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = PythonAstAdapter()
    parser = ProjectParser((adapter,))

    intake = parser.intake(FIXTURE)
    monkeypatch.setattr(
        adapter,
        "parse",
        lambda *_args, **_kwargs: pytest.fail("path-based parse rediscovered the project"),
    )
    graph = parser.parse(intake)

    assert isinstance(intake, ProjectIntake)
    assert intake.root == FIXTURE.resolve()
    assert len(intake.files) == 11
    assert graph.to_json() == PythonAstAdapter().parse(FIXTURE).to_json()


def test_project_intake_resolves_all_adapter_ownership_in_one_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "main.ts").write_text("export function main() {}\n", encoding="utf-8")
    walk = source_discovery.os.walk
    walk_count = 0

    def counting_walk(path: Path):  # type: ignore[no-untyped-def]
        nonlocal walk_count
        walk_count += 1
        return walk(path)

    monkeypatch.setattr(source_discovery.os, "walk", counting_walk)

    intake = ProjectParser((PythonAstAdapter(), _FixtureAdapter())).intake(tmp_path)

    assert walk_count == 1
    assert [file.name for file in intake.files] == ["app.py", "main.ts"]


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


def test_intake_scope_counts_orders_busiest_directories_first(tmp_path: Path) -> None:
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "one.py").write_text("A = 1\n", encoding="utf-8")
    (tmp_path / "api" / "two.py").write_text("B = 2\n", encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "app.py").write_text("C = 3\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("D = 4\n", encoding="utf-8")

    intake = ProjectParser().intake(tmp_path)

    assert intake.scope_counts() == (("api", 2), (".", 1), ("web", 1))


def test_progress_reporting_leaves_the_language_adapter_seam_unchanged() -> None:
    """Progress is bound around adapters, never threaded through their signatures."""

    import inspect

    from codemble.adapters.base import LanguageAdapter

    assert list(inspect.signature(LanguageAdapter.discover).parameters) == [
        "self",
        "path",
    ]
    assert list(inspect.signature(LanguageAdapter.parse).parameters) == [
        "self",
        "path",
        "entrypoint",
    ]
    assert list(inspect.signature(LanguageAdapter.parse_files).parameters) == [
        "self",
        "project_root",
        "files",
        "entrypoint",
    ]
    assert list(inspect.signature(LanguageAdapter.concepts).parameters) == [
        "self",
        "node",
        "source",
    ]


def test_a_parsed_project_reports_the_languages_it_could_not_chart(tmp_path: Path) -> None:
    """The galaxy must not look complete when a whole language is missing."""

    (tmp_path / "app.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "main.go").write_text("package main\n", encoding="utf-8")
    (tmp_path / "svc" / "api.go").write_text("package main\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    graph = ProjectParser([PythonAstAdapter()]).parse(tmp_path)

    assert [
        (row.extension, row.language, row.count) for row in graph.unsupported_sources
    ] == [(".go", "Go", 2)]
    assert graph.to_dict()["unsupported_sources"] == [
        {"extension": ".go", "language": "Go", "count": 2}
    ]


def test_an_adapter_that_owns_the_extension_silences_the_report(tmp_path: Path) -> None:
    """Registering a language must remove it from the not-charted list."""

    (tmp_path / "app.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
    (tmp_path / "widget.ts").write_text("export const a = 1;\n", encoding="utf-8")

    python_only = ProjectParser([PythonAstAdapter()]).parse(tmp_path)
    with_typescript = ProjectParser([PythonAstAdapter(), _FixtureAdapter()]).parse(tmp_path)

    assert [row.extension for row in python_only.unsupported_sources] == [".ts"]
    assert with_typescript.unsupported_sources == ()
