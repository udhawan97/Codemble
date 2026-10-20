# P1.1a learner intake review and verification

Date: 2026-10-20 (America/Chicago). Base:
`ae2e2400ad611ac6151947cf3892eb58d1f1240c`.
Candidate branch: `docs/p11a-learner-intake`.
The candidate is the commit containing this receipt; its exact SHA and final
integration result must be checked in the branch's pull request.

## Scope

This packet corrects TESTING.md, the early-tester issue form, the historical
Phase 1 cap statement, the Unreleased documentation note, and maintained
execution state. It changes no runtime code, dependencies, packaged SPA,
release manifest, automation or public-sharing connection.

The form retains every existing field ID. Its `lit` question now records
illumination separately from the new assistance question. Existing historical
reports retain their original question text and must not be reinterpreted under
the revised question. Installation failures, unfinished trials, no confusion,
assisted illumination and untested restart persistence remain reportable.

## Council gates

Two complete plan rounds passed, with four independent reviewers per round:
evidence, coverage, risk and outcome. The implemented plan preserves issue
#13's v0.7.0-or-later floor and three independent unaided Python successes,
permits truthful no-confusion/unfinished responses, and states that public
reports are associated with the reporter's GitHub handle.

Two complete implementation rounds accepted the final documentation and
receipts, with the same four independent roles in each round and no remaining
material blockers. No application behavior was added or inferred from reviews.
Neither council establishes native Safari or unaided learner acceptance.

## Local verification

- Full Python suite in a disposable environment tied to this worktree:
  **794 passed**. One upstream Starlette `TestClient` deprecation warning was
  reported; no failure was waived.
- `ruff check .`: passed.
- Temporary intake validation: strict YAML parsing with duplicate-key/ID checks,
  retained field IDs, GitHub form field shapes and string-valued dropdowns;
  required/optional field checks; synthetic unaided, assisted, installation
  failure, restart failure and unfinished-restart responses: passed.
- Guide commands and labels checked against CLI, parser cap and current UI
  source; candidate-installed `codemble --version` reports 0.24.0.
- Local links resolve. GitHub issue/form targets returned HTTP 200. The
  unchanged Astral documentation link was retrieved through the web tool after
  its server refused a direct HEAD request.
- `git diff --check`: passed.

The temporary checker, raw logs, environment and reviewer transcripts are
private local evidence, outside the source tree. No documentation-mirroring
tests or dependencies were added to the repository.

## Content binding

The normative intake changes reviewed in both implementation rounds have
these SHA-256 digests:

| File | SHA-256 |
| --- | --- |
| TESTING.md | `ced7ae064976820d764ec04e4f5a033b15c00ac05e9f2d21ac6a25ff38a2d1f8` |
| .github/ISSUE_TEMPLATE/early_tester.yml | `a33fc71f4e2aee4d598e1cee82957dee457b7ab19b82cd1aa64b3976e7d91d25` |
| docs/plans/phase-1.md | `bd6870e9b67000bea9f96d3d11854e7af271fe87b89e08d0cc17921e0e676c7f` |
| CHANGELOG.md | `23658d7702dfbbd08b9f8165ba2a6edc4cd2fda644cacf55f27ab99ec4db2e03` |

The completion metadata records the current councils and queue state. Exact
candidate tree, source digests and raw receipt digests are retained with the
private review packet; the commit and PR provide the public artifact identity.

## Integration gates and next action

All five hosted CI jobs must pass on the exact final candidate before merge.
Record their result in the pull request; inspect the merged commit and remote
main afterward. The prior planning commit's CI is not this packet's evidence.
Required protections and reviews remain in force.

The next packet after successful integration is P1.1b, native Safari rehearsal.
P2 is independently eligible after P1.1a if P1.1b has an unchanged external
HOLD. Issue #13 stays open; mixed-language reports and agent checks do not
replace three independent unaided Python learner successes.

The earlier scheduled-phase council record binds the initial planning snapshot.
This receipt covers the subsequent intake implementation and execution-state
updates rather than claiming the initial plan digest covers those changes.
