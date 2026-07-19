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

The star chart is your second progress screen. Its three measures deliberately
mean different things:

- **Encountered** comes from syntax the parser found in the current project.
- **Studied** counts structures you opened during this session.
- **Understood** stays dark until a graph-derived check passes.

Opening a Study view can move Studied, but it cannot claim you understand the
concept. It only ever claims a concept exists where the parser actually detected
it — the lens never guesses.

The Python Lens recognizes decorators, comprehensions, generators, context
managers, async/await, dunder methods, exception handling, and type hints. The
JavaScript/TypeScript Lens recognizes async/await, arrow functions,
destructuring, optional chaining, nullish coalescing, module syntax, type
annotations, interfaces, generics, and JSX.

Each note carries its real source snippet and a clickable `file:line` anchor.
Nested structures own their own annotations, so a parent does not absorb syntax
found only inside a child. Chart rows are keyed by language plus concept: a
Python async/await encounter and a TypeScript async/await encounter remain
separate evidence even though their display names match.

In a mixed project, the chart follows the current language focus. This changes
only the rows and session counts you are viewing; the underlying project graph
and persisted understanding remain intact when you return to **All**.
