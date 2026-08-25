"""Tier 0 narration: parser facts rendered through fixed templates.

This module performs no inference and calls no model.  Every clause traces to
a field the graph already owns, which is why it is safe to render with no key,
no network, and no provider configured at all.
"""

from __future__ import annotations

from codemble.adapters.base import Node, RoleEvidence

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

_EASY_ROLE_PURPOSE = {
    "application-entry": "The parser proves this is a place where the application starts.",
    "route-handler": "The parser proves this receives an application route.",
    "ui-renderer": "The parser proves this renders part of the user interface.",
    "test": "The parser proves this is test code; it does not claim the test passed.",
}

_EXPERT_ROLE_PURPOSE = {
    "application-entry": "application entry",
    "route-handler": "route handler",
    "ui-renderer": "UI renderer",
    "test": "test",
}


def structural_summary(
    node: Node,
    neighbors: list[dict[str, object]],
    lens: list[dict[str, object]],
    roles: list[RoleEvidence] | tuple[RoleEvidence, ...] = (),
) -> dict[str, str]:
    """Return the same parser facts in a beginner and an expert voice."""

    inbound = [item for item in neighbors if item.get("direction") == "inbound"]
    outbound = [item for item in neighbors if item.get("direction") == "outbound"]
    possible = [item for item in neighbors if not item.get("certain", True)]
    titles = [str(item.get("title", "")) for item in lens if item.get("title")]
    concepts = [str(item.get("concept", "")) for item in lens if item.get("concept")]
    return {
        "easy": _easy_voice(node, inbound, outbound, possible, titles, roles),
        "expert": _expert_voice(node, inbound, outbound, possible, concepts, roles),
    }


def _inbound_sentence(inbound: list[dict[str, object]]) -> str:
    """Say WHICH relation reaches this structure, not just how many do.

    The panel prints "Called by 0" — `centrality`, which counts call edges
    only — directly above this sentence. Saying "two other parts of your code
    use it" about two *imports* put two different questions side by side
    wearing the same word, and "called by" and "use" are synonyms to the early
    coder this register exists for. Both numbers were right and the pair was
    unreadable. Naming the relation is what separates them; neither count moves.
    """

    if not inbound:
        return "Nothing else in your code brings it in yet."
    imports = [item for item in inbound if item.get("relationship") == "import"]
    calls = [item for item in inbound if item.get("relationship") == "call"]
    clauses: list[str] = []
    if imports:
        clauses.append(
            f"{_count_word(len(imports))} other "
            f"{'file brings' if len(imports) == 1 else 'files bring'} it in"
        )
    if calls:
        count = _count_word(len(calls))
        clauses.append(
            f"{count.lower() if clauses else count} other "
            f"{'part calls' if len(calls) == 1 else 'parts call'} it"
        )
    if not clauses:
        return "Nothing else in your code brings it in yet."
    return f"{' and '.join(clauses)}."


def _easy_voice(
    node: Node,
    inbound: list[dict[str, object]],
    outbound: list[dict[str, object]],
    possible: list[dict[str, object]],
    titles: list[str],
    roles: list[RoleEvidence] | tuple[RoleEvidence, ...],
) -> str:
    kind = _KIND_WORDS.get(node.kind, node.kind)
    sentences = [
        f"This is {node.name}, a {kind}.",
        f"It lives in {node.file}, starting on line {node.lineno}.",
        f"It is {_line_count(node.loc)} long.",
        _easy_purpose(roles),
    ]
    sentences.append(_inbound_sentence(inbound))
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
    roles: list[RoleEvidence] | tuple[RoleEvidence, ...],
) -> str:
    # Prose, not a "·"-joined field list. The expert register is terse, but the
    # old single metadata line sat under a heading reading "Structural summary"
    # beside Easy's five sentences, and read as a section that had failed to
    # load -- which is exactly what learners reported. Every fact it carried is
    # still here; only the presentation changed. Digits stay (Easy spells small
    # counts; the two voices differ on purpose).
    edges = len(inbound) + len(outbound)
    sentences = [
        (
            f"{node.name} is a {node.kind} at "
            f"{node.file}:{node.lineno}-{node.end_lineno} ({_line_count(node.loc)})."
        ),
        (
            f"It has {len(inbound)} inbound and {len(outbound)} outbound "
            f"parser-observed graph {'edge' if edges == 1 else 'edges'}."
        ),
        _expert_purpose(roles),
    ]
    if possible:
        count = len(possible)
        sentences.append(
            f"{count} possible {'edge is' if count == 1 else 'edges are'} "
            "unproven rather than parser-certain."
        )
    if concepts:
        sentences.append(f"Concepts: {', '.join(concepts)}.")
    if node.partial:
        sentences.append("A partial parse means this structure is incomplete.")
    return " ".join(sentences)


def _easy_purpose(roles: list[RoleEvidence] | tuple[RoleEvidence, ...]) -> str:
    if not roles:
        return "The parser describes its structure and observed connections, but not its purpose."
    descriptions = sorted({_EASY_ROLE_PURPOSE[evidence.role] for evidence in roles})
    return " ".join(descriptions)


def _expert_purpose(roles: list[RoleEvidence] | tuple[RoleEvidence, ...]) -> str:
    if not roles:
        return "No parser-owned role evidence describes its purpose."
    labels = sorted({_EXPERT_ROLE_PURPOSE[evidence.role] for evidence in roles})
    rules = sorted({evidence.rule_id for evidence in roles})
    return f"Parser roles: {', '.join(labels)} (rules: {', '.join(rules)})."


def _count_word(count: int) -> str:
    return _COUNT_WORDS[count] if count < len(_COUNT_WORDS) else str(count)


def _line_count(count: int) -> str:
    return f"{count} line" if count == 1 else f"{count} lines"


def _join_words(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} and {values[-1]}"


__all__ = ["structural_summary"]
