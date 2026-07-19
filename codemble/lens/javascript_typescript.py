"""Teachable JS/TS notes keyed only by tree-sitter concept evidence."""

from __future__ import annotations

from codemble.adapters.base import ConceptAnnotation

_NOTES = {
    "async-await": (
        "Async / await",
        {
            "easy": "This waits for something slow, like loading data, without freezing the rest of the page.",
            "expert": "This syntax pauses the current async flow until the awaited value settles without blocking the JavaScript event loop.",
        },
    ),
    "arrow-function": (
        "Arrow function",
        {
            "easy": "A shorter way to write a function. The `=>` is the arrow it is named after.",
            "expert": "This compact function form captures `this` from its surrounding scope instead of creating its own `this` binding.",
        },
    ),
    "destructuring": (
        "Destructuring",
        {
            "easy": "This unpacks values out of an object or list and gives each one its own name, in one line.",
            "expert": "This pattern binds selected array positions or object properties directly to local names.",
        },
    ),
    "optional-chaining": (
        "Optional chaining",
        {
            "easy": "The `?.` checks whether something exists before reaching inside it, so a missing value cannot crash the code.",
            "expert": "This chain stops and yields `undefined` when the value before `?.` is `null` or `undefined`.",
        },
    ),
    "nullish-coalescing": (
        "Nullish coalescing",
        {
            "easy": "The `??` supplies a backup value, but only when the first one is missing. A zero or empty text still counts as a real value.",
            "expert": "This expression uses its right side only when the left side is `null` or `undefined`, preserving values such as `0` and an empty string.",
        },
    ),
    "module-syntax": (
        "Module syntax",
        {
            "easy": "This line either borrows code from another file or offers this file's code to others.",
            "expert": "This declaration makes a dependency or exported binding explicit in the source module graph.",
        },
    ),
    "type-annotation": (
        "Type annotation",
        {
            "easy": "This says what kind of value belongs here, so your editor can warn you before you run the code.",
            "expert": "TypeScript uses this annotation for static checking and editor tooling; the annotation itself does not become a runtime check.",
        },
    ),
    "interface": (
        "Interface",
        {
            "easy": "This describes the shape a value must have — which fields it needs — without creating anything that exists while the program runs.",
            "expert": "This TypeScript declaration names a structural type contract for checking and tooling without creating a runtime value.",
        },
    ),
    "generic": (
        "Generic",
        {
            "easy": "This lets one piece of code work with many kinds of value while remembering which kind it was given.",
            "expert": "This type parameter preserves a relationship between types while letting callers supply a concrete type.",
        },
    ),
    "jsx": (
        "JSX",
        {
            "easy": "This is HTML-looking code written inside JavaScript. A build step turns it into real JavaScript.",
            "expert": "This syntax describes an element or component tree that the configured toolchain transforms into JavaScript.",
        },
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
                "note": explanation["easy"],
                "note_voices": explanation,
                "line": annotation.lineno,
                "end_line": annotation.end_lineno,
                "snippet": annotation.snippet,
            }
        )
    return notes


__all__ = ["javascript_typescript_lens_notes"]
