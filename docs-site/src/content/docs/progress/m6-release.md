---
title: "Build log: the tester release"
description: M6 packages the real app, hardens first-run limits, and prepares honest human acceptance.
---

**Week of July 19, 2026 · Milestone M6 technical scope complete**

The v0.1.0 wheel now contains the production React app, so a Git-tag install
through `pipx` or `uvx` needs only Python at runtime. An isolated wheel install
was launched outside the checkout and served both the packaged HTML and schema
3 graph API successfully.

First-run uncertainty now has explicit product states:

- ambiguous rank-zero startup candidates open Home calibration; no candidate
  is silently preferred, and `--entrypoint` accepts only parser-ranked IDs
- more than 300 Python files requires an interactive subdirectory or explicit
  `--path`, with a clear non-interactive error instead of an unbounded render
- syntax-error files stay visible as Unchartable raw source while inner
  structure, Lens claims, and model narration remain off

The one sanctioned 420 ms illumination pulse now marks a completed check suite,
with an opacity-only reduced-motion variant. `scripts/record_demo.sh` drives the
real fixture, captures galaxy → system → checks → lighting through Chrome, and
rebuilds the README GIF with `ffmpeg`.

Automated gates cover ambiguous Home selection, invalid overrides, the 301-file
scope boundary, partial narration suppression, packaged assets, and every prior
correctness contract. Desktop and 320 px browser checks cover Home calibration
and Unchartable source with no overflow or console errors.

The technical release is ready. The human acceptance item remains deliberately
open until 3–5 learners complete an unaided run; Phase 1 is not promoted early.
