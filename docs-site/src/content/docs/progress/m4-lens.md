---
title: "Build log: syntax becomes a lesson"
description: M4 adds AST-proven Python concepts, source-anchored Lens notes, and an honest star chart.
---

**Week of July 19, 2026 · Milestone M4 complete**

Codemble can now teach the Python constructs already present in a learner's
project. The adapter detects eight concept families with the standard-library
AST: decorators, comprehensions, generators, context managers, async/await,
dunder methods, exception handling, and type hints.

Every annotation belongs to one lexical structure. A parent module does not
inherit syntax found only inside a child function or class. Each annotation
carries its real line span and source snippet in deterministic graph schema 2.
That evidence flows through two model-free views:

- the Python Lens maps only detected concept IDs to concise teaching notes and
  links every note to its exact `file:line`
- the star chart aggregates encountered concepts, records structures studied
  during the current session, and reserves Understood for check-derived state

Viewing source is not treated as mastery. That distinction is visible in the
UI: opening a structure increments Studied for its concepts while Understood
stays dark until the next milestone's graph-only checks pass.

Acceptance evidence: exact concept ownership and Lens/source equality are
covered by tests; a fixture with all eight concept families was exercised in the
production UI; the chart updated only the studied structure; desktop and 320 px
browser checks showed no overflow or console errors; Python, Ruff, Vite, Astro,
and docs gates are green.

M5 is next: graph-only checks, permanent illumination, and file-scoped progress
invalidation.
