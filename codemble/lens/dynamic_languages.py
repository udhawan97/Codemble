"""Evidence captions for Ruby and PHP syntax."""

from __future__ import annotations

from codemble.adapters.base import ConceptAnnotation

_VOICES: dict[str, dict[str, tuple[str, dict[str, str]]]] = {
    "ruby": {
        "block": (
            "Block",
            {
                "easy": "This hands a small piece of behaviour to another method, often so it can run once for each value.",
                "expert": "A Ruby block. It closes over its lexical scope and is yielded to by the receiving method.",
            },
        ),
        "exception-handling": (
            "Rescue",
            {
                "easy": "This catches a failure so the program can respond instead of stopping here.",
                "expert": "A rescue clause. The exception classes it catches determine which failures are intercepted.",
            },
        ),
        "safe-navigation": (
            "Safe navigation",
            {
                "easy": "This calls the next method only when the value exists; otherwise it quietly returns nothing.",
                "expert": "The `&.` operator short-circuits to nil when its receiver is nil.",
            },
        ),
        "singleton-method": (
            "Class-level method",
            {
                "easy": "This behaviour belongs to the class or object itself, not to one instance made from it.",
                "expert": "A singleton method, defined on this object's eigenclass rather than as an instance method.",
            },
        ),
        "string-interpolation": (
            "String interpolation",
            {
                "easy": "This puts a calculated value directly inside some text.",
                "expert": "An interpolated string expression evaluated when the string is constructed.",
            },
        ),
        "symbol": (
            "Symbol",
            {
                "easy": "This is a stable name used as a lightweight label or key.",
                "expert": "A Ruby Symbol: an immutable, interned identifier commonly used for hash keys and protocol names.",
            },
        ),
    },
    "php": {
        "arrow-function": (
            "Arrow function",
            {
                "easy": "This is a short function written beside the code that uses it.",
                "expert": "A PHP arrow function. Variables from the outer scope are captured automatically by value.",
            },
        ),
        "attribute": (
            "Attribute",
            {
                "easy": "This attaches a label and details that a framework or tool can read.",
                "expert": "A PHP 8 attribute. Its runtime meaning depends on the reflected attribute class.",
            },
        ),
        "enum": (
            "Enum",
            {
                "easy": "This limits a value to one of a named set of choices.",
                "expert": "A PHP enum, optionally backed by scalar values and capable of implementing interfaces.",
            },
        ),
        "match-expression": (
            "Match expression",
            {
                "easy": "This chooses one result by comparing a value against several exact cases.",
                "expert": "A strict, exhaustive `match` expression. Unlike switch, it returns a value and does not coerce comparisons.",
            },
        ),
        "named-argument": (
            "Named argument",
            {
                "easy": "This says which parameter receives the value, so the call is easier to read.",
                "expert": "A named argument bound by parameter name rather than position.",
            },
        ),
        "nullsafe-access": (
            "Nullsafe access",
            {
                "easy": "This continues only when the value exists; otherwise the whole chain returns null.",
                "expert": "The nullsafe operator short-circuits the remaining access chain when its receiver is null.",
            },
        ),
        "union-type": (
            "Union type",
            {
                "easy": "This value is allowed to be any one of several listed types.",
                "expert": "A union type checked by PHP's runtime type system at the parameter, property, or return boundary.",
            },
        ),
    },
}


def dynamic_lens_notes(
    language: str,
    annotations: list[ConceptAnnotation],
) -> list[dict[str, object]]:
    """Turn parser-proven Ruby/PHP annotations into audience-paired notes."""

    vocabulary = _VOICES.get(language, {})
    notes: list[dict[str, object]] = []
    for annotation in annotations:
        voice = vocabulary.get(annotation.concept)
        if voice is None:
            continue
        title, explanations = voice
        notes.append(
            {
                "language": language,
                "concept": annotation.concept,
                "title": title,
                "line": annotation.lineno,
                "end_line": annotation.end_lineno,
                "snippet": annotation.snippet,
                "explanations": explanations,
            }
        )
    return notes


__all__ = ["dynamic_lens_notes"]
