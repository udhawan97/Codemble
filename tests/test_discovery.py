"""Unsupported-language files stay counted instead of vanishing silently."""

from __future__ import annotations

from pathlib import Path

from codemble.adapters.discovery import SourceOwnership, discover_project_sources

PYTHON = SourceOwnership("python", frozenset({".py"}), frozenset())
TYPESCRIPT = SourceOwnership("typescript", frozenset({".ts", ".tsx"}), frozenset())


def _project(root: Path, files: dict[str, str]) -> Path:
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def test_known_code_extensions_no_adapter_owns_are_counted(tmp_path: Path) -> None:
    """A learner must be able to tell a whole language was left out."""

    root = _project(
        tmp_path,
        {
            "app.py": "x = 1\n",
            "server/main.go": "package main\n",
            "server/util.go": "package main\n",
            "core/lib.rs": "fn main() {}\n",
        },
    )

    discovered = discover_project_sources(root, (PYTHON,))

    assert [(row.extension, row.language, row.count) for row in discovered.unsupported] == [
        (".go", "Go", 2),
        (".rs", "Rust", 1),
    ]


def test_an_owned_extension_is_never_reported_as_unsupported(tmp_path: Path) -> None:
    """Self-exclusion: shipping an adapter must silence its own extension."""

    root = _project(tmp_path, {"app.py": "x = 1\n", "web/main.ts": "export {}\n"})

    owned_by_nobody = discover_project_sources(root, (PYTHON,))
    owned_by_typescript = discover_project_sources(root, (PYTHON, TYPESCRIPT))

    assert [row.extension for row in owned_by_nobody.unsupported] == [".ts"]
    assert owned_by_typescript.unsupported == ()


def test_files_that_are_not_chartable_code_are_not_reported(tmp_path: Path) -> None:
    """Shell and docs sit beside every project and signal nothing about it."""

    root = _project(
        tmp_path,
        {
            "app.py": "x = 1\n",
            "README.md": "# hi\n",
            "deploy.sh": "echo hi\n",
            "schema.sql": "SELECT 1;\n",
            "logo.png": "not really a png\n",
            "uv.lock": "lock\n",
        },
    )

    assert discover_project_sources(root, (PYTHON,)).unsupported == ()


def test_an_ambiguous_extension_is_reported_without_a_language_claim(tmp_path: Path) -> None:
    """``.h`` is C or C++ and ``.m`` is Objective-C or MATLAB; say neither."""

    root = _project(tmp_path, {"app.py": "x = 1\n", "vendor/thing.h": "#pragma once\n"})

    (row,) = discover_project_sources(root, (PYTHON,)).unsupported
    assert (row.extension, row.language, row.count) == (".h", None, 1)


def test_the_tally_is_deterministic_and_ignores_gitignored_and_vendor_trees(
    tmp_path: Path,
) -> None:
    """Same project, same answer -- and vendored code is not the learner's."""

    root = _project(
        tmp_path,
        {
            ".gitignore": "build/\n",
            "app.py": "x = 1\n",
            "a.go": "package main\n",
            "build/generated.go": "package main\n",
            "node_modules/dep/index.go": "package main\n",
        },
    )

    first = discover_project_sources(root, (PYTHON,)).unsupported
    second = discover_project_sources(root, (PYTHON,)).unsupported

    assert first == second
    assert [(row.extension, row.count) for row in first] == [(".go", 1)]
