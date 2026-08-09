"""Cross-language contracts for the shared tree-sitter adapter lifecycle."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from codemble.adapters.csharp_tree_sitter import CSharpAdapter, CSharpParseError
from codemble.adapters.discovery import SourceDiscoveryError
from codemble.adapters.go_tree_sitter import GoAdapter, GoParseError
from codemble.adapters.java_tree_sitter import JavaAdapter, JavaParseError
from codemble.adapters.rust_tree_sitter import RustAdapter, RustParseError
from codemble.adapters.tree_sitter_core import _TreeSitterAdapterCore
from codemble.adapters.typescript_tree_sitter import (
    JavaScriptTypeScriptAdapter,
    JavaScriptTypeScriptParseError,
)
from codemble.graph.finalize import GraphFinalizationError

FIXTURES = Path(__file__).parent / "fixtures"
CASES = (
    pytest.param(
        JavaScriptTypeScriptAdapter,
        JavaScriptTypeScriptParseError,
        "JavaScript/TypeScript",
        FIXTURES / "polyglot",
        id="typescript",
    ),
    pytest.param(GoAdapter, GoParseError, "Go", FIXTURES / "go_sample", id="go"),
    pytest.param(
        JavaAdapter,
        JavaParseError,
        "Java",
        FIXTURES / "java_sample",
        id="java",
    ),
    pytest.param(
        RustAdapter,
        RustParseError,
        "Rust",
        FIXTURES / "rust_sample",
        id="rust",
    ),
    pytest.param(
        CSharpAdapter,
        CSharpParseError,
        "C#",
        FIXTURES / "csharp_sample",
        id="csharp",
    ),
)


@pytest.mark.parametrize("adapter_type,error_type,source_label,fixture", CASES)
def test_public_lifecycle_is_shared_but_concepts_stay_language_owned(
    adapter_type: type[Any],
    error_type: type[Exception],
    source_label: str,
    fixture: Path,
) -> None:
    del error_type, source_label, fixture
    assert adapter_type.discover is _TreeSitterAdapterCore.discover
    assert adapter_type.parse is _TreeSitterAdapterCore.parse
    assert adapter_type.parse_files is _TreeSitterAdapterCore.parse_files
    assert "concepts" in adapter_type.__dict__
    assert str(inspect.signature(adapter_type.discover)) == (
        "(self, path: 'Path') -> 'tuple[Path, tuple[Path, ...]]'"
    )
    assert str(inspect.signature(adapter_type.parse)) == (
        "(self, path: 'Path', *, entrypoint: 'str | None' = None) -> 'Graph'"
    )
    assert str(inspect.signature(adapter_type.parse_files)) == (
        "(self, project_root: 'Path', files: 'tuple[Path, ...]', *, "
        "entrypoint: 'str | None' = None) -> 'Graph'"
    )
    assert str(inspect.signature(adapter_type.concepts)) == (
        "(self, node: 'Node', source: 'str') -> 'list[ConceptAnnotation]'"
    )


@pytest.mark.parametrize("adapter_type,error_type,source_label,fixture", CASES)
def test_discovery_and_owned_file_paths_serialize_identically(
    adapter_type: type[Any],
    error_type: type[Exception],
    source_label: str,
    fixture: Path,
) -> None:
    del error_type, source_label
    adapter = adapter_type()
    project_root, files = adapter.discover(fixture)

    discovered = adapter.parse(fixture).to_json().encode("utf-8")
    owned = adapter.parse_files(project_root, files).to_json().encode("utf-8")
    repeated = adapter.parse(fixture).to_json().encode("utf-8")

    assert discovered == owned == repeated


@pytest.mark.parametrize("adapter_type,error_type,source_label,fixture", CASES)
def test_error_translation_preserves_type_message_and_cause(
    adapter_type: type[Any],
    error_type: type[Exception],
    source_label: str,
    fixture: Path,
    tmp_path: Path,
) -> None:
    adapter = adapter_type()

    with pytest.raises(error_type) as empty:
        adapter.parse(tmp_path)
    assert str(empty.value) == f"no {source_label} files found under: {tmp_path.resolve()}"
    assert empty.value.__cause__ is None

    missing_path = tmp_path / "absent"
    with pytest.raises(error_type) as missing:
        adapter.parse(missing_path)
    assert str(missing.value) == f"path does not exist: {missing_path.resolve()}"
    assert isinstance(missing.value.__cause__, SourceDiscoveryError)

    graph = adapter.parse(fixture)
    choices = ", ".join(graph.entrypoint_candidates) or "none"
    with pytest.raises(error_type) as invalid_entrypoint:
        adapter.parse(fixture, entrypoint="made-up")
    assert str(invalid_entrypoint.value) == (
        f"entrypoint is not parser-ranked: made-up (candidates: {choices})"
    )
    assert isinstance(invalid_entrypoint.value.__cause__, GraphFinalizationError)
