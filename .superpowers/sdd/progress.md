# Audience modes backend — SDD progress

Plan: docs/plans/2026-07-19-audience-modes-backend-plan.md
Branch: friendly-wizard-claude/work-planning-f2e933
Base at start: 7aeb9bb (plan commit), amended by backward-compat pre-flight fix

Pre-flight finding (verified in web/src/App.jsx, resolved before Task 1):
  committed web_dist SPA renders explanation/note/prompt directly with no
  tolerant fallback. Plan amended: /study omits `explanation`; lens keeps
  `note` string + adds `note_voices`; checks keep `prompt` string + add
  `prompt_voices`. Phase 4 drops the legacy keys.

## Tasks
Task 1: complete (commits 08be8da..17d0709, review clean; Important test-rigor finding fixed + mutation-verified)
Task 2: complete (commits d65ec40..58474d7, re-review clean; 1 Critical + 3 Important + 2 Minor fixed)
Task 3: complete (commit f11d4af, review clean; 2 Minor noted - explain() partial adds cached:False; no_key end-to-end coverage returns in Task 4)
Task 4: complete (commits e8df8ef..ed3699a, review clean; 2 Important coverage gaps closed + shadowing mutation-verified)
Task 5: complete (in squash e7b54d5; Critical comprehension accuracy bug + Important JS/TS coverage gap fixed)
PHASE 1 MERGED to main as e7b54d5 (tasks 1-5). Branch reset to origin/main. Main is now v0.3.1 with picker landed.
Task 6: complete (commits d469772..1b13689; 2 Important fixed - easy wording dropped 'directly' making transitive answers defensible; Check unhashable)
Task 7: complete (commits a72ab05..3e0deee; cache-key mode fix + style/contract bridge sentence)
Task 8: complete (commits 8cabf2a..ca781117; mark_understood payload-clobber bug found+fixed; vacuous re-dim test strengthened + mutation-verified)
PHASE 2 COMPLETE (tasks 5-8). 99 tests passing.
Task 9: complete (commits c1d6004..4ff29b3; SECURITY: brief's guard checked hostname not scheme, file://localhost passed -> local file disclosure; fixed + frozen dataclass)
Task 10: complete (commit 5c8d988, review clean; try/except ValueError containment verified across 8 failure combos)
Task 11: complete (commits d3d082f..48bf394; Critical never-raise hole - http.client.HTTPException not caught; pre-existing network-touching test fixed)
PHASE 3 COMPLETE (tasks 9-11). 128 tests passing. ALL 11 TASKS DONE.
