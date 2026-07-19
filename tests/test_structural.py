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
    one = structural_summary(_node(), [_neighbor("inbound", certain=False)], [])
    assert (
        "One of those links is a possible connection, not a certain one."
        in one["easy"]
    )
    assert "1 possible" in one["expert"]

    three = structural_summary(
        _node(), [_neighbor("inbound", certain=False) for _ in range(3)], []
    )
    assert (
        "Three of those links are possible connections, not certain ones."
        in three["easy"]
    )
    assert "3 possible" in three["expert"]


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


def test_both_voices_state_the_structures_length():
    summary = structural_summary(_node(), [], [])
    assert "It is 48 lines long." in summary["easy"]
    assert "(48 lines)" in summary["expert"]

    single_line = structural_summary(_node(lineno=41, end_lineno=41, loc=1), [], [])
    assert "It is 1 line long." in single_line["easy"]
    assert "(1 lines)" in single_line["expert"]


def test_more_than_ten_neighbours_render_as_digits_not_words():
    neighbors = [_neighbor("inbound") for _ in range(11)]
    summary = structural_summary(_node(), neighbors, [])
    assert "11 other parts of your code use it." in summary["easy"]
    assert "Inbound 11" in summary["expert"]


def test_two_or_more_lens_concepts_join_with_a_comma_and_and():
    lens = [
        {"concept": "decorator", "title": "Decorators"},
        {"concept": "comprehension", "title": "Comprehensions"},
        {"concept": "generator", "title": "Generators"},
    ]
    summary = structural_summary(_node(), [], lens)
    assert (
        "Ideas found here: Decorators, Comprehensions and Generators."
        in summary["easy"]
    )
    assert "Concepts: decorator, comprehension, generator" in summary["expert"]
