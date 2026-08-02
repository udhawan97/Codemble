"""Lens voices for the Go, Java, Rust and C# adapters.

One module for four languages rather than four, because these tables are pure
data of an identical shape and splitting them would produce four files
differing only in their contents. The lookup stays language-scoped: Rust and C#
both detect ``async-await`` and each deserves its own wording, and ``generic``
means different enough things in Java and C# to be worth saying differently.

Every note here captions a construct the parser proved is present at an exact
span. Nothing may describe a construct the adapter did not find, and nothing may
generalise past the syntax detected -- these are captions on evidence, not
teaching material written in advance. A concept with no entry here yields no
note at all, which is the honest outcome: an invented caption on real evidence
is still an invented claim.
"""

from __future__ import annotations

from codemble.adapters.base import ConceptAnnotation

# language -> concept -> (title, {voice: copy}). The shape the Python and JS/TS
# lenses already publish, so the study panel needs no new branch.
_VOICES: dict[str, dict[str, tuple[str, dict[str, str]]]] = {
    "go": {
        "goroutine": (
            "Goroutine",
            {
                "easy": "This starts a separate task that runs alongside the rest of the program, so the code here does not have to wait for it to finish.",
                "expert": "A `go` statement schedules this call on the Go runtime; it returns immediately and the goroutine's completion is not awaited here.",
            },
        ),
        "channel": (
            "Channel",
            {
                "easy": "This is a pipe between separate tasks: one side puts a value in, the other takes it out, and whoever arrives first waits for the other.",
                "expert": "A channel operation. Sends and receives synchronise the two goroutines unless the channel is buffered.",
            },
        ),
        "defer": (
            "Deferred call",
            {
                "easy": "This schedules some cleanup to happen when the surrounding function finishes, no matter which way it exits.",
                "expert": "A `defer` statement. It runs on function return, including panics, in last-in-first-out order.",
            },
        ),
        "error-return": (
            "Error returned as a value",
            {
                "easy": "Instead of crashing, this hands back a description of what went wrong so the caller decides what to do about it.",
                "expert": "The idiomatic Go error return; the caller is expected to inspect it rather than rely on an exception.",
            },
        ),
        "interface-assertion": (
            "Type assertion",
            {
                "easy": "This checks what kind of value it actually has before using it.",
                "expert": "A type assertion or type switch on an interface value. The concrete type is not known statically here, which is why calls through it stay possible rather than certain.",
            },
        ),
        "struct-embedding": (
            "Embedded struct",
            {
                "easy": "This puts one thing inside another so it borrows its fields and behaviour without repeating them.",
                "expert": "Struct embedding: the embedded type's exported fields and methods are promoted onto the outer type.",
            },
        ),
        "generics": (
            "Generics",
            {
                "easy": "This works with more than one kind of value without writing the code out again for each one.",
                "expert": "A type parameter list; the constraint is what the compiler checks the argument against.",
            },
        ),
    },
    "java": {
        "annotation": (
            "Annotation",
            {
                "easy": "This is a label attached to the code that tools and frameworks read to decide how to treat it.",
                "expert": "An annotation. Whether it has runtime effect depends on its retention policy, which is not visible from this file.",
            },
        ),
        "lambda": (
            "Lambda",
            {
                "easy": "This is a small piece of behaviour written inline and handed to something else to run later.",
                "expert": "A lambda expression implementing a functional interface.",
            },
        ),
        "generic": (
            "Generics",
            {
                "easy": "This works with more than one kind of value without writing it out again for each one.",
                "expert": "A type parameter. Java erases it at runtime, so the type is checked at compile time only.",
            },
        ),
        "record": (
            "Record",
            {
                "easy": "This is a small holder for a few values, where the usual boilerplate is written for you.",
                "expert": "A record: implicitly final, with generated accessors, equals, hashCode and toString.",
            },
        ),
        "sealed-type": (
            "Sealed type",
            {
                "easy": "This limits which other code is allowed to build on it.",
                "expert": "A sealed type; the permitted subtypes are fixed at compile time.",
            },
        ),
        "default-method": (
            "Default method",
            {
                "easy": "This gives an interface a ready-made version of a method, so anything using it does not have to write its own.",
                "expert": "A default method on an interface, providing an implementation without breaking existing implementors.",
            },
        ),
        "try-with-resources": (
            "Try-with-resources",
            {
                "easy": "This makes sure something is closed properly when the block finishes, even if something goes wrong.",
                "expert": "A try-with-resources block; the resource is closed automatically in reverse declaration order.",
            },
        ),
        "stream": (
            "Stream pipeline",
            {
                "easy": "This describes a series of steps over a collection of values rather than looping over them by hand.",
                "expert": "A stream pipeline. Intermediate operations are lazy; nothing runs until a terminal operation.",
            },
        ),
    },
    "rust": {
        "trait": (
            "Trait",
            {
                "easy": "This is a list of things a type promises it can do, so different types can be used the same way.",
                "expert": "A trait: a set of required behaviour. Dispatch through a trait object is dynamic, which is why such calls stay possible rather than certain.",
            },
        ),
        "impl": (
            "Implementation block",
            {
                "easy": "This is where a type's own behaviour is written.",
                "expert": "An impl block. An inherent impl and an `impl Trait for Type` are different things and are recorded separately.",
            },
        ),
        "borrowing": (
            "Borrowing",
            {
                "easy": "This looks at a value without taking ownership of it, so whoever owned it still does afterwards.",
                "expert": "A shared reference. Any number may exist at once, and none may mutate.",
            },
        ),
        "mutable-borrow": (
            "Mutable borrow",
            {
                "easy": "This is allowed to change the value, and while it can, nothing else may touch it.",
                "expert": "A unique reference. Exclusivity is what the borrow checker enforces.",
            },
        ),
        "lifetime": (
            "Lifetime",
            {
                "easy": "This says how long a borrowed value has to stay alive for this code to be safe.",
                "expert": "An explicit lifetime parameter, relating the validity of one reference to another.",
            },
        ),
        "pattern-matching": (
            "Pattern matching",
            {
                "easy": "This takes a value apart and does something different depending on what shape it turned out to be.",
                "expert": "A match expression. The compiler checks the arms cover every case.",
            },
        ),
        "result-option": (
            "Result and Option",
            {
                "easy": "This says outright that there might be no value, or that something might have failed, so it cannot be forgotten.",
                "expert": "A Result or Option. Absence and failure are in the type rather than in a convention.",
            },
        ),
        "question-mark-operator": (
            "The ? operator",
            {
                "easy": "This passes a failure straight back to the caller instead of handling it here.",
                "expert": "The `?` operator: an early return of the error variant, converted through `From`.",
            },
        ),
        "async-await": (
            "Async and await",
            {
                "easy": "This lets the program get on with other work while it waits for something slow.",
                "expert": "An async function or await point. Rust futures are lazy and do nothing until polled by an executor.",
            },
        ),
        "macro": (
            "Macro",
            {
                "easy": "This writes code for you before the program is built.",
                "expert": "A macro invocation, expanded at compile time. The expansion is not visible to this parser, so nothing is claimed about what it generates.",
            },
        ),
        "unsafe": (
            "Unsafe block",
            {
                "easy": "This turns off some of the language's safety checks, so the person who wrote it is taking responsibility for getting it right.",
                "expert": "An unsafe block. The compiler's guarantees are suspended inside it; the invariants become the author's obligation.",
            },
        ),
    },
    "csharp": {
        "linq-query": (
            "LINQ query",
            {
                "easy": "This describes what to select from a collection rather than looping over it step by step.",
                "expert": "A LINQ query. Execution is deferred until the sequence is enumerated.",
            },
        ),
        "async-await": (
            "Async and await",
            {
                "easy": "This lets the program get on with other work while it waits for something slow.",
                "expert": "An async method or await expression; the continuation resumes on a context that depends on the synchronisation context in force.",
            },
        ),
        "property-accessors": (
            "Property",
            {
                "easy": "This looks like a plain value from outside but can run code when it is read or written.",
                "expert": "A property with accessors. Reads and writes are method calls.",
            },
        ),
        "record": (
            "Record",
            {
                "easy": "This is a small holder for a few values, compared by what it contains rather than by which one it is.",
                "expert": "A record: value equality and a generated copy constructor.",
            },
        ),
        "nullable-type": (
            "Nullable type",
            {
                "easy": "This says out loud that the value might be missing, so it has to be checked before it is used.",
                "expert": "A nullable reference or value type; the compiler tracks null-state flow when the feature is enabled.",
            },
        ),
        "pattern-matching": (
            "Pattern matching",
            {
                "easy": "This takes a value apart and does something different depending on what shape it turned out to be.",
                "expert": "A switch expression or pattern. Exhaustiveness is checked where the compiler can prove it.",
            },
        ),
        "extension-method": (
            "Extension method",
            {
                "easy": "This adds a method to a type from outside it, without changing the original.",
                "expert": "An extension method: a static method the compiler lets you call with instance syntax.",
            },
        ),
        "generic": (
            "Generics",
            {
                "easy": "This works with more than one kind of value without writing it out again for each one.",
                "expert": "A type parameter. Unlike Java, C# generics are reified and survive to runtime.",
            },
        ),
    },
}


def systems_lens_notes(
    language: str, annotations: list[ConceptAnnotation]
) -> list[dict[str, object]]:
    """Return teachable notes for proven Go/Java/Rust/C# constructs."""

    voices = _VOICES.get(language)
    if not voices:
        return []
    notes: list[dict[str, object]] = []
    for annotation in annotations:
        if annotation.language != language:
            continue
        voice = voices.get(annotation.concept)
        if voice is None:
            continue
        title, note_voices = voice
        notes.append(
            {
                "node_id": annotation.node_id,
                "language": annotation.language,
                "concept": annotation.concept,
                "title": title,
                "note_voices": note_voices,
                "line": annotation.lineno,
                "end_line": annotation.end_lineno,
                "snippet": annotation.snippet,
            }
        )
    return notes


SUPPORTED_LANGUAGES = frozenset(_VOICES)

__all__ = ["SUPPORTED_LANGUAGES", "systems_lens_notes"]
