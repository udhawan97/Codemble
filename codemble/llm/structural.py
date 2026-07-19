"""Tier 0 narration: parser facts rendered through fixed templates.

This module performs no inference and calls no model.  Every clause traces to
a field the graph already owns, which is why it is safe to render with no key,
no network, and no provider configured at all.
"""

from __future__ import annotations

from codemble.adapters.base import Node

_COUNT_WORDS = (
    "No",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
)

_KIND_WORDS = {
    "module": "file",
    "function": "function",
    "class": "class",
}


def structural_summary(
    node: Node,
    neighbors: list[dict[str, object]],
    lens: list[dict[str, object]],
) -> dict[str, str]:
    """Return the same parser facts in a beginner and an expert voice."""

    inbound = [item for item in neighbors if item.get("direction") == "inbound"]
    outbound = [item for item in neighbors if item.get("direction") == "outbound"]
    possible = [item for item in neighbors if not item.get("certain", True)]
    titles = [str(item.get("title", "")) for item in lens if item.get("title")]
    concepts = [str(item.get("concept", "")) for item in lens if item.get("concept")]
    return {
        "easy": _easy_voice(node, inbound, outbound, possible, titles),
        "expert": _expert_voice(node, inbound, outbound, possible, concepts),
    }


def _easy_voice(
    node: Node,
    inbound: list[dict[str, object]],
    outbound: list[dict[str, object]],
    possible: list[dict[str, object]],
    titles: list[str],
) -> str:
    kind = _KIND_WORDS.get(node.kind, node.kind)
    sentences = [
        f"This is {node.name}, a {kind}.",
        f"It lives in {node.file}, starting on line {node.lineno}.",
        f"It is {node.loc} line long."
        if node.loc == 1
        else f"It is {node.loc} lines long.",
    ]
    sentences.append(
        f"{_count_word(len(inbound))} other "
        f"{'part' if len(inbound) == 1 else 'parts'} of your code "
        f"{'uses' if len(inbound) == 1 else 'use'} it."
        if inbound
        else "Nothing else in your code uses it yet."
    )
    sentences.append(
        f"It uses {_count_word(len(outbound)).lower()} other "
        f"{'part' if len(outbound) == 1 else 'parts'} of your code."
        if outbound
        else "It does not use any other part of your code."
    )
    if possible:
        count_word = _count_word(len(possible))
        sentences.append(
            f"{count_word} of those links is a possible connection, not a certain one."
            if len(possible) == 1
            else f"{count_word} of those links are possible connections, not certain ones."
        )
    if titles:
        sentences.append(f"Ideas found here: {_join_words(titles)}.")
    if node.partial:
        sentences.append(
            "Your file could not be fully read, so some parts may be missing."
        )
    return " ".join(sentences)


def _expert_voice(
    node: Node,
    inbound: list[dict[str, object]],
    outbound: list[dict[str, object]],
    possible: list[dict[str, object]],
    concepts: list[str],
) -> str:
    fields = [
        f"{node.name} · {node.kind} · {node.file}:{node.lineno}-{node.end_lineno}"
        f" ({node.loc} lines)",
        f"Inbound {len(inbound)} · Outbound {len(outbound)}"
        + (f" · {len(possible)} possible" if possible else ""),
    ]
    if concepts:
        fields.append(f"Concepts: {', '.join(concepts)}")
    if node.partial:
        fields.append("partial parse — structure incomplete")
    return " · ".join(fields)


def _count_word(count: int) -> str:
    return _COUNT_WORDS[count] if count < len(_COUNT_WORDS) else str(count)


def _join_words(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} and {values[-1]}"


__all__ = ["structural_summary"]
