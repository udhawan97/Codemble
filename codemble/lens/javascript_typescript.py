"""Teachable JS/TS notes keyed only by tree-sitter concept evidence."""

from __future__ import annotations

from codemble.adapters.base import ConceptAnnotation

_NOTES = {
    "async-await": (
        "Async / await",
        "This syntax pauses the current async flow until the awaited value settles without blocking the JavaScript event loop.",
    ),
    "arrow-function": (
        "Arrow function",
        "This compact function form captures `this` from its surrounding scope instead of creating its own `this` binding.",
    ),
    "destructuring": (
        "Destructuring",
        "This pattern binds selected array positions or object properties directly to local names.",
    ),
    "optional-chaining": (
        "Optional chaining",
        "This chain stops and yields `undefined` when the value before `?.` is `null` or `undefined`.",
    ),
    "nullish-coalescing": (
        "Nullish coalescing",
        "This expression uses its right side only when the left side is `null` or `undefined`, preserving values such as `0` and an empty string.",
    ),
    "module-syntax": (
        "Module syntax",
        "This declaration makes a dependency or exported binding explicit in the source module graph.",
    ),
    "type-annotation": (
        "Type annotation",
        "TypeScript uses this annotation for static checking and editor tooling; the annotation itself does not become a runtime check.",
    ),
    "interface": (
        "Interface",
        "This TypeScript declaration names a structural type contract for checking and tooling without creating a runtime value.",
    ),
    "generic": (
        "Generic",
        "This type parameter preserves a relationship between types while letting callers supply a concrete type.",
    ),
    "jsx": (
        "JSX",
        "This syntax describes an element or component tree that the configured toolchain transforms into JavaScript.",
    ),
}


def javascript_typescript_lens_notes(
    language: str,
    annotations: list[ConceptAnnotation],
) -> list[dict[str, object]]:
    """Attach deterministic teaching copy to matching JS/TS annotations."""

    if language not in {"javascript", "typescript"}:
        return []
    notes: list[dict[str, object]] = []
    for annotation in annotations:
        if annotation.language != language:
            continue
        note = _NOTES.get(annotation.concept)
        if note is None:
            continue
        title, explanation = note
        notes.append(
            {
                "node_id": annotation.node_id,
                "language": annotation.language,
                "concept": annotation.concept,
                "title": title,
                "note": explanation,
                "line": annotation.lineno,
                "end_line": annotation.end_lineno,
                "snippet": annotation.snippet,
            }
        )
    return notes


__all__ = ["javascript_typescript_lens_notes"]
