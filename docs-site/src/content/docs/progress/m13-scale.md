---
title: "Build log: M13 scale"
description: Threaded parsing, staged progress, a 1,000-file cap, and two removed performance cliffs.
---

**July 20, 2026 · Milestone M13 scope**

Phase C of the galaxy UX overhaul made Codemble usable on projects roughly
three times larger, without changing one byte of parser output.

## What changed

- **Parsing moved off the request thread.** `POST /api/picker/select` now
  answers `202 {"state": "parsing"}` immediately and a worker thread parses.
  `GET /api/picker/progress` reports one of `idle`, `parsing`, `ready`, or
  `error`, with the current stage and a real file count.
- **Five honest stages**, in order: discovering, parsing, resolving, checks,
  layout. The file counter moves during `parsing` only, because that is the
  only stage measured per file. `resolving` — cross-file import and call
  resolution, the slowest stage — instead narrates its own real sub-steps
  ("Resolving imports", "Resolving calls", "Building the galaxy map",
  "Composing your project") so the screen keeps moving without inventing a
  denominator it does not have.
- **Cancellation.** Resetting the picker during a parse sets a flag that is
  checked between files, so the parse stops at the next file boundary and the
  picker re-arms. A crashed parse thread becomes an error state with the
  parser's own message, surfaced back on the picker with a one-click retry —
  never a hung server.
- **The scale cap moved from 300 to 1,000** supported source files. Above it,
  the picker offers the busiest scopes as buttons and accepts a typed path,
  both still jailed to your home directory. A piped, non-interactive CLI run
  now prints those same scopes instead of a bare refusal.
- **Two measured cliffs removed.** Check generation used to walk every graph
  edge up to four times per region; it now builds one index in a single pass
  (measured ~16x faster at 1,000 files, generated suites byte-identical).
  `GET /api/graph` and `GET /api/map` used to re-hydrate and re-sort the whole
  graph on every request; the serialized document is now cached and dropped
  only when a region lights up, Home changes, or the project is rebound
  (measured ~25-26x faster warm).
- A parser hotspot in the Python adapter's own module-resolution lookup was
  also fixed — an O(definitions × modules) scan replaced with an O(depth) walk
  — for a further 1.56x on total parse wall-clock, again byte-identical.
- **Clear this project's progress** is available from the star chart, behind a
  confirmation, scoped to the open project.

## What did not change

Check suites and answers are byte-identical to before the index change; a
committed golden fixture proves it for both the Python and the mixed
JavaScript/TypeScript fixtures. Progress reporting cannot influence parser
output: the same source produces the same graph JSON with or without a
reporter attached, and a test pins that. The `LanguageAdapter` seam is
unchanged.
