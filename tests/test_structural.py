"""Tier 0 renders graph facts only; it must never infer."""

from codemble.adapters.base import Node
from codemble.llm.structural import structural_summary


def _node(**overrides: object) -> Node:
    values: dict[str, object] = {
        "id": "pkg/app.py::run",
        "kind": "function",
        "name": "run",
        "language": "python",
        "file": "pkg/app.py",
        "lineno": 41,
        "end_lineno": 88,
        "loc": 48,
        "region": "pkg/app.py",
    }
    values.update(overrides)
    return Node(**values)  # type: ignore[arg-type]


def _neighbor(direction: str, certain: bool = True) -> dict[str, object]:
    return {
        "node_id": "pkg/other.py::helper",
        "name": "helper",
        "kind": "function",
        "file": "pkg/other.py",
        "line": 3,
        "citation": "pkg/other.py:3",
        "relationship": "call",
        "certain": certain,
        "direction": direction,
        "observed_line": 44,
    }


def test_both_voices_name_the_structure_and_its_location():
    summary = structural_summary(_node(), [], [])
    assert "run" in summary["easy"]
    assert "pkg/app.py" in summary["easy"]
    assert "pkg/app.py:41-88" in summary["expert"]


def test_easy_voice_spells_small_counts_and_expert_uses_digits():
    neighbors = [_neighbor("inbound"), _neighbor("inbound"), _neighbor("outbound")]
    summary = structural_summary(_node(), neighbors, [])
    assert "Two other parts" in summary["easy"]
    assert "Inbound 2" in summary["expert"]
    assert "Outbound 1" in summary["expert"]


def test_possible_relationships_stay_labelled_possible_in_both_voices():
    neighbors = [_neighbor("inbound", certain=False)]
    summary = structural_summary(_node(), neighbors, [])
    assert "possible" in summary["easy"].lower()
    assert "possible" in summary["expert"].lower()


def test_zero_neighbours_is_stated_not_omitted():
    summary = structural_summary(_node(), [], [])
    assert "Nothing else in your code uses it yet." in summary["easy"]
    assert "Inbound 0" in summary["expert"]


def test_partial_parse_is_disclosed_in_both_voices():
    summary = structural_summary(_node(partial=True), [], [])
    assert "could not be fully read" in summary["easy"]
    assert "partial parse" in summary["expert"]


def test_lens_concepts_are_listed_when_present_and_omitted_when_not():
    lens = [{"concept": "decorator", "title": "Decorator"}]
    with_concepts = structural_summary(_node(), [], lens)
    assert "Decorator" in with_concepts["easy"]
    assert "decorator" in with_concepts["expert"]
    without = structural_summary(_node(), [], [])
    assert "ideas" not in without["easy"]
