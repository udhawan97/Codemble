---
title: The star chart
description: Language concepts you've met and mastered, tracked across your galaxy.
---

## Concepts, not just code

Understanding *your* project and understanding *the language* compound each
other. As you study, Codemble's **language lens** spots real idioms in your code
— decorators, comprehensions, generators, context managers, async/await — and
teaches them right there, anchored to the line where they live.

## The chart

The star chart is your second progress screen. Its four measures deliberately
mean different things, and they are ordered from the weakest claim to the
strongest:

- **Systems explored** counts the systems you have flown to. It is earned by
  travel and says nothing at all about comprehension.
- **Encountered** comes from syntax the parser found in the current project.
- **Studied** counts structures you opened during this session.
- **Understood** stays dark until a graph-derived check passes.

Opening a Study view can move Studied, but it cannot claim you understand the
concept. It only ever claims a concept exists where the parser actually detected
it — the lens never guesses.

Each language brings its own lens:

| Language | Idioms the lens recognizes |
| --- | --- |
| Python | decorators, comprehensions, generators, context managers, async/await, dunder methods, exception handling, type hints, dataclasses, protocols, pattern matching, f-strings, the walrus operator |
| JavaScript / TypeScript | async/await, arrow functions, destructuring, optional chaining, nullish coalescing, module syntax, type annotations, interfaces, generics, JSX |
| Go | goroutines, channels, `defer`, error returns, struct embedding, interface assertions, generics |
| Java | annotations, lambdas, streams, records, sealed types, default methods, try-with-resources, generics |
| Rust | ownership and borrowing, mutable borrows, lifetimes, traits, `impl` blocks, pattern matching, `Result`/`Option`, the `?` operator, macros, `unsafe`, async/await |
| C# | LINQ queries, extension methods, properties, records, nullable types, pattern matching, generics, async/await |

Some idioms are worth teaching for what they take *out* of the file. A
`@dataclass` generates the class's `__init__`, `__repr__` and `__eq__` from its
annotated fields, so none of that code appears anywhere you could read it. An
absence is the hardest thing to look up when you did not write the code
yourself, which is exactly the position this project's readers are in.

Each note carries its real source snippet and a clickable `file:line` anchor.
Nested structures own their own annotations, so a parent does not absorb syntax
found only inside a child. Chart rows are keyed by language plus concept: a
Python async/await encounter and a TypeScript async/await encounter remain
separate evidence even though their display names match.

In a mixed project, the chart follows the current language focus. This changes
only the rows and session counts you are viewing; the underlying project graph
and persisted understanding remain intact when you return to **All**.

**Modules** and **Find** remain available while the chart is open. The module
index opens beside the chart, and `⌘K` / `Ctrl-K` opens the same project-wide
finder used by the Map and Galaxy, including modules not yet charted.

"Studied" counts the structures you have opened **in this session** and resets
when you reload — that is deliberate. Opening a file is not evidence that you
understood it.

Two measures do persist, and they say different things. "Systems explored" is
saved because a map you filled in by travelling should still be filled in
tomorrow; it claims only that you went there. "Understood" is saved because you
proved it with graph-derived checks. Clearing a project's progress clears both.
