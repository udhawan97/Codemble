---
title: "Build log: the TS/JS Lens"
description: M9 turns exact tree-sitter constructs into language-specific lessons and collision-free star-chart evidence.
---

**July 18, 2026 · Milestone M9 Lens scope**

The JavaScript/TypeScript adapter now emits concept annotations while it owns
the syntax tree. Each annotation includes the owning graph node, language,
concept ID, exact line span, and source snippet. No UI heuristic and no model
call decides that a concept exists.

The first JS/TS concept set covers async/await, arrow functions, destructuring,
optional chaining, nullish coalescing, import/export module syntax, TypeScript
annotations, interfaces, generics, and JSX. The deterministic Lens translates
only those IDs into teaching copy and adds the real `file:line` citation in the
Study module.

Graph schema 4 makes the annotation language explicit. The star chart keys rows
by language plus concept, so Python and TypeScript async/await evidence cannot
merge accidentally. The same distinction flows through encountered, studied,
and check-derived understood counts.

Error recovery stays conservative: a broken module receives no module-level
Lens claims, while a valid sibling function may keep annotations proven inside
its own error-free tree. Tests compare Study notes exactly to serialized parser
annotations and exercise every concept family against the mixed fixture.

M10 is next: an accessible language-focus control, real mixed-project browser
QA, documentation/install updates, and the Phase 1 tester release.
