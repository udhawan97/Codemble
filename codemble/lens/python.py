"""Teachable Python notes keyed only by parser-detected concept IDs."""

from __future__ import annotations

from codemble.adapters.base import ConceptAnnotation

_PYTHON_NOTES = {
    "dataclass": (
        "Dataclass",
        {
            "easy": "The @dataclass line writes the boring parts for you: how one of these is created, how it prints, and how two of them are compared. That is why you cannot see that code here.",
            "expert": "@dataclass generates __init__, __repr__ and __eq__ from the annotated fields; eq/order/frozen change what is generated.",
        },
    ),
    "protocol": (
        "Protocol",
        {
            "easy": "This lists what something has to be able to do. Anything that can do those things counts, without having to say it is related to this.",
            "expert": "A typing.Protocol: structural typing checked by the type checker, with no inheritance required at runtime.",
        },
    ),
    "pattern-matching": (
        "Pattern matching",
        {
            "easy": "This takes a value apart and does something different depending on what shape it turned out to be.",
            "expert": "A match statement. Patterns destructure as they test, and a bare name in a case binds rather than compares.",
        },
    ),
    "f-string": (
        "f-string",
        {
            "easy": "The f before the quotes lets you drop values straight into the text inside the curly braces.",
            "expert": "A formatted string literal; expressions are evaluated at runtime and formatted through __format__.",
        },
    ),
    "walrus": (
        "Walrus operator",
        {
            "easy": "The := sign stores a value and uses it in the same breath, so the same thing is not worked out twice.",
            "expert": "An assignment expression: it binds in the enclosing scope and evaluates to the bound value.",
        },
    ),
    "decorator": (
        "Decorator",
        {
            "easy": "The @ line above wraps this in extra behavior before it runs. Think of it as a sticker that adds a rule.",
            "expert": "Python evaluates this decorator while defining the structure and binds the returned object to its name.",
        },
    ),
    "comprehension": (
        "Comprehension",
        {
            "easy": "This is a short way to build a list, set, or dictionary by looping in one line, instead of writing a longer loop.",
            "expert": "This expression builds a collection through inline iteration and optional filtering.",
        },
    ),
    "generator": (
        "Generator",
        {
            "easy": "This hands back one value at a time instead of building everything at once, which saves memory.",
            "expert": "This construct produces values lazily instead of building the complete sequence at once.",
        },
    ),
    "context-manager": (
        "Context manager",
        {
            "easy": "The `with` line opens something and promises to close it again, even if an error happens.",
            "expert": "The `with` protocol brackets this block with managed setup and cleanup behavior.",
        },
    ),
    "async-await": (
        "Async / await",
        {
            "easy": "This can pause while waiting for slow work, letting other things run instead of blocking.",
            "expert": "This construct participates in Python's asynchronous protocol and may yield control while work is pending.",
        },
    ),
    "dunder-method": (
        "Dunder method",
        {
            "easy": "The double underscores mean Python calls this for you, for things like len() or printing.",
            "expert": "Python calls this specially named method through a language protocol such as length, comparison, or display.",
        },
    ),
    # One concept id covers `try`, `try*` and `raise` (python_ast visits all
    # three), so the copy has to be true of a line that *signals* a problem as
    # well as one that catches it. The old easy note taught catching only, and
    # anchored to `raise SystemExit(main())` it claimed roughly the opposite of
    # what that line does.
    "exception-handling": (
        "Exception handling",
        {
            "easy": "This treats failure as part of the plan: code like this either raises a problem for whoever called it, or catches one so the program can react instead of crashing.",
            "expert": "This construct makes failure part of explicit control flow by catching, grouping, or raising an exception.",
        },
    ),
    "type-hint": (
        "Type hint",
        {
            "easy": "This is a note about what kind of value belongs here. Python does not enforce it; it helps readers and tools.",
            "expert": "This annotation communicates an expected type to readers and tooling; Python does not enforce it by default.",
        },
    ),
}


def python_lens_notes(
    annotations: list[ConceptAnnotation],
) -> list[dict[str, object]]:
    """Attach deterministic teaching copy to proven Python annotations."""

    notes: list[dict[str, object]] = []
    for annotation in annotations:
        if annotation.language != "python":
            continue
        note = _PYTHON_NOTES.get(annotation.concept)
        if note is None:
            continue
        title, explanation = note
        notes.append(
            {
                "node_id": annotation.node_id,
                "language": annotation.language,
                "concept": annotation.concept,
                "title": title,
                "note_voices": explanation,
                "line": annotation.lineno,
                "end_line": annotation.end_lineno,
                "snippet": annotation.snippet,
            }
        )
    return notes


__all__ = ["python_lens_notes"]
