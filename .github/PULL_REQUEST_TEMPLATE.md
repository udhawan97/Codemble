<!-- Thanks! Keep it small and runnable. Link the CLAUDE.md milestone this serves. -->

## What & why

## Type
- [ ] feat  - [ ] fix  - [ ] docs  - [ ] refactor  - [ ] test  - [ ] chore

## Checklist
- [ ] `pytest` and `ruff check .` pass
- [ ] Conventional Commit(s), signed off (`-s`)
- [ ] No API keys, no proprietary code samples
- [ ] Project runs end-to-end after this change

## If this touches the parser / graph
- [ ] Unit tests cover the new structure
- [ ] Unresolved calls are flagged, not dropped or invented

## If this touches explanations (LLM)
- [ ] Output remains grounded (real identifiers, `file:line` links)
- [ ] Check answers still come from the graph, never the model
