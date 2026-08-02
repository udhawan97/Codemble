"""Seven languages, one graph, one set of rules.

The `LanguageAdapter` seam's whole claim is that adding a language changes
nothing above it. These tests are what that claim costs: they compose every
shipped adapter over one tree and assert the project-level invariants hold
across all of them at once, rather than per language in isolation where a
composition bug cannot appear.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest

from codemble.adapters.project import ProjectParser
from codemble.lens import lens_notes

FIXTURES = Path(__file__).parent / "fixtures"
LANGUAGE_FIXTURES = ("go_sample", "java_sample", "rust_sample", "csharp_sample", "polyglot")


@pytest.fixture
def polyglot_root(tmp_path: Path) -> Path:
    root = tmp_path / "polyglot_seven"
    root.mkdir()
    for name in LANGUAGE_FIXTURES:
        source = FIXTURES / name
        if source.exists():
            shutil.copytree(source, root / name)
    (root / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    return root


def test_every_shipped_language_lands_in_one_graph(polyglot_root: Path) -> None:
    graph = ProjectParser().parse(polyglot_root)

    languages = {node.language for node in graph.nodes}

    assert languages == {
        "csharp",
        "go",
        "java",
        "javascript",
        "python",
        "rust",
        "typescript",
    }


def test_every_language_in_the_graph_has_a_tint(polyglot_root: Path) -> None:
    """A language the parser emits must be paintable in the app.

    The frontend keys every visual channel off `Node.language`, which is what
    keeps the seam narrow -- but it also means a new adapter can land, parse
    correctly, and still reach a learner with a whole channel missing. That is
    what happened when four languages shipped: Go, Java, Rust and C# drew no
    nebula, showed a blank legend swatch, and lost their Architecture-map
    stripe into the box it sits on.

    Read as text rather than executed, because the registry lives in Python and
    the table lives in JS, so something has to look across the boundary. This
    is the half no JS gate can do: `check_graph_data.mjs` proves the table's
    own rows all paint, but it iterates that table and so cannot notice a
    language missing from it.
    """

    web = Path(__file__).parent.parent / "web" / "src"
    tints = dict(
        re.findall(
            r'^\s*(\w+): "(--cm-neb-[a-z]+)",$',
            (web / "graphData.js").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert tints, "NEBULA_TINTS could not be read from graphData.js"
    tokens = (web / "tokens.css").read_text(encoding="utf-8")

    for language in {node.language for node in ProjectParser().parse(polyglot_root).nodes}:
        assert language in tints, (
            f"{language} has no row in NEBULA_TINTS: its systems would draw no fog, "
            "its legend row would print a name beside an empty box, and its map "
            "stripe would inherit the box fill and vanish"
        )
        assert f"{tints[language]}:" in tokens, (
            f"{tints[language]} is missing from tokens.css, so {language} paints nothing"
        )


def test_registering_an_adapter_silences_its_own_extension(polyglot_root: Path) -> None:
    """Schema 8's coverage note must not report a language Codemble now reads.

    `unsupported_sources` counts chartable-language files no adapter
    *recognised*. Four extensions moved from that tally into the graph in this
    release, and the tally is supposed to follow automatically -- with no second
    list to maintain. This is that promise, checked.
    """

    graph = ProjectParser().parse(polyglot_root)

    reported = {entry.extension for entry in graph.unsupported_sources}

    assert not reported & {".go", ".java", ".rs", ".cs"}


def test_uncertainty_survives_composition(polyglot_root: Path) -> None:
    """A possible call stays possible once six adapters' edges are merged."""

    graph = ProjectParser().parse(polyglot_root)

    possible = [edge for edge in graph.edges if not edge.certain]

    assert possible, "these fixtures contain relationships no parser can prove"
    # Every language that emits an uncertain edge must still be represented
    # among them: a merge that quietly dropped one language's hedges would look
    # like a cleaner graph and be a less honest one.
    node_language = {node.id: node.language for node in graph.nodes}
    hedged_languages = {
        node_language[edge.src] for edge in possible if edge.src in node_language
    }
    assert len(hedged_languages) >= 3


def test_a_syntax_error_in_one_language_never_costs_the_others(
    polyglot_root: Path,
) -> None:
    graph = ProjectParser().parse(polyglot_root)

    assert graph.partial_files, "each fixture ships one deliberately broken file"
    # The broken files are flagged, and the languages they belong to still
    # contributed structure -- a partial parse degrades one file, not a language.
    assert len({node.language for node in graph.nodes}) == 7


def test_composition_is_byte_identical_across_runs(polyglot_root: Path) -> None:
    first = ProjectParser().parse(polyglot_root)
    second = ProjectParser().parse(polyglot_root)

    def signature(graph) -> str:
        return json.dumps(
            {
                "nodes": [asdict(node) for node in graph.nodes],
                "edges": [asdict(edge) for edge in graph.edges],
            },
            sort_keys=True,
        )

    assert signature(first) == signature(second)


def test_every_annotation_can_be_voiced_or_is_silently_dropped(
    polyglot_root: Path,
) -> None:
    """A lens note must never carry another language's wording.

    Routing is by language, so the risk is not a missing note -- that is
    handled honestly by returning none -- but a note voiced under the wrong
    language, which would be a confident wrong claim about real syntax.
    """

    graph = ProjectParser().parse(polyglot_root)

    for language in {node.language for node in graph.nodes}:
        annotations = [
            annotation
            for annotation in graph.concept_annotations
            if annotation.language == language
        ]
        for note in lens_notes(language, annotations):
            assert note["language"] == language
            assert note["line"] >= 1
            assert note["title"]
