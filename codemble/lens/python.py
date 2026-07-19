"""Teachable Python notes keyed only by parser-detected concept IDs."""

from __future__ import annotations

from codemble.adapters.base import ConceptAnnotation

_PYTHON_NOTES = {
    "decorator": (
        "Decorator",
        "Python evaluates this decorator while defining the structure and binds the returned object to its name.",
    ),
    "comprehension": (
        "Comprehension",
        "This expression builds a collection through inline iteration and optional filtering.",
    ),
    "generator": (
        "Generator",
        "This construct produces values lazily instead of building the complete sequence at once.",
    ),
    "context-manager": (
        "Context manager",
        "The `with` protocol brackets this block with managed setup and cleanup behavior.",
    ),
    "async-await": (
        "Async / await",
        "This construct participates in Python's asynchronous protocol and may yield control while work is pending.",
    ),
    "dunder-method": (
        "Dunder method",
        "Python calls this specially named method through a language protocol such as length, comparison, or display.",
    ),
    "exception-handling": (
        "Exception handling",
        "This construct makes failure part of explicit control flow by catching, grouping, or raising an exception.",
    ),
    "type-hint": (
        "Type hint",
        "This annotation communicates an expected type to readers and tooling; Python does not enforce it by default.",
    ),
}


def python_lens_notes(
    annotations: list[ConceptAnnotation],
) -> list[dict[str, object]]:
    """Attach deterministic teaching copy to proven Python annotations."""

    notes: list[dict[str, object]] = []
    for annotation in annotations:
        note = _PYTHON_NOTES.get(annotation.concept)
        if note is None:
            continue
        title, explanation = note
        notes.append(
            {
                "node_id": annotation.node_id,
                "concept": annotation.concept,
                "title": title,
                "note": explanation,
                "line": annotation.lineno,
                "end_line": annotation.end_lineno,
                "snippet": annotation.snippet,
            }
        )
    return notes


__all__ = ["python_lens_notes"]
