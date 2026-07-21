# Recent

```

# Recent

## 2026-07-19
Shipped folder picker (v0.3.0 PyPI) and easy/expert modes with Ollama narration. Backend phases 1-4 complete (134+ tests, 3 shipped PRs); phases 5-6 in progress. Fixed learner-loop bugs (cache collision, file:// scheme bypass, call-count). Code review surfaced 6 defects. Began 3-phase UI overhaul (39-task spec, 27-decision register). Also shipped Codemble website redesign (parallax hero, expandable search, Starlight docs).

## 2026-07-20
Galaxy UI redesign 3-phase rollout completed: Phase A (study panel, header controls), Phase B (orbits, map endpoint, WCAG tokens), Phase C (threading, caching, 1K-file scale) shipped v0.5.1 PyPI. Merged 55-commit main collision, fixed 2 silent reverts + 2 correctness gaps. Pre-merge critical issues handled (map-click lang-focus, WebGL leak, legend encoding). Discovered file-read freeze bug post-release.

## Identity Candidates
- IDENTITY CANDIDATE: Multi-phase concurrent rollout with collision recovery—3-phase galaxy redesign (Phase A→C, v0.3.1→v0.5.1 in parallel) merged across 55-commit main divergence; silent reverts + correctness gaps identified and fixed pre-ship.