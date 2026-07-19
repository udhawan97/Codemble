---
title: "Build log: understanding lights the map"
description: M5 adds graph-only active recall, permanent region illumination, and file-scoped local progress.
---

**Week of July 19, 2026 · Milestone M5 complete**

Codemble's core loop now closes inside the System view. A learner opens a
focused active-recall readout, answers one question at a time, and lights the
region only after its full safe suite passes.

Four check families ship: first certain call, direct importer, removal impact
through direct callers, and parser-ranked entrypoint. Prompts, options, answers,
and evidence are generated from the graph. The browser never receives the
answer before submission, and no model participates in generation or scoring.
Wrong answers leave progress untouched and return the real parser answer with
its `file:line` evidence.

`ProgressStore` persists a project-keyed record under `~/.codemble/progress`
only when the suite completes. Each region record contains a deterministic
signature of its member file hashes. A restart rehydrates matching regions;
editing one file invalidates only the signature for that file's region.

Acceptance evidence: unit tests exercise all four check families, answer
withholding, exact scoring, wrong-answer immutability, full-suite illumination,
restart persistence, and a two-region edit where only the changed region dims.
The production UI was used to fail and then pass all four Home checks, verify
the star chart update, restart the server, and confirm illumination remained.
Desktop and 320 px browser checks had no overflow or console errors; Python,
Ruff, Vite, Astro, and docs gates are green.

M6 is next: ambiguous-entrypoint guidance, scale protection, packaged install
paths, failure polish, and a tester-ready first-run experience.
