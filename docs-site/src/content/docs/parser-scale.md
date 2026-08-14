---
title: Parser evidence and scale
description: What Codemble caches, how semantic quality is measured, and why the public limit remains 1,000 files.
---

Codemble now keeps one `ProjectParser` alive across explicit project release and
reactivation. Its cache is process-memory only, thread-safe, and bounded to 24
root/adapter/version buckets plus a 128 MiB canonical-JSON accounting ceiling by
default. That ceiling is deterministic but is not an exact process-RSS claim.
Nothing is watched in the background and nothing is written to disk.

The cache retains immutable graph evidence partitioned by exact file identity:
canonical root, relative path, SHA-256 of captured bytes, language or dialect,
adapter/parser/grammar/evidence version, and discovery configuration. Captured
source bytes are discarded. The bounded source-line snippets already present
in a Graph are not retained either: a cache hit reconstructs them transiently
from current bytes only after their SHA-256 still matches. Captured source
bytes, raw source-line snippets, and syntax trees therefore never remain in the
cache. A no-change activation
recomposes the matching file evidence and performs global finalization again.
An edit, deletion, rename, dialect/version/configuration change, or cancelled
activation cannot reuse or publish stale evidence. Parsed evidence stays
invisible until the same acceptance lock publishes both it and the live
project, including when cancellation arrives after extraction but before
acceptance. When any file changed, the adapter currently takes the conservative
path and reparses before full-project resolution, so Codemble does **not** claim
that a structural one-file change is incremental yet.

That distinction matters: a fast index is not a smarter parser. Warm and fresh
parses must produce byte-identical Graph and Map payloads, and full resolution
must remove stale nodes, edges, roles, concepts, and partial-file notices.

## Repeatable gates

Run the source-free scale benchmark from the repository root:

```bash
python scripts/benchmark_parser_scale.py --output /tmp/codemble-scale.jsonl
```

The output is created with mode `0600` and contains timings, counts, digests,
memory, cache counters, and equivalence results—never source or project paths.
On a disposable sparse-Python fixture generated deterministically by the
committed script on macOS with Python 3.12.7, the implementation pass measured:

| Files | Cold parse | No-change parse | One-file change | Fresh-equivalent |
| ---: | ---: | ---: | ---: | :---: |
| 1,000 | 0.388 s | 0.119 s | 0.379 s | yes |
| 5,000 | 3.823 s | 0.644 s | 3.956 s | yes |
| 10,000 | 12.834 s | 1.521 s | 13.062 s | yes |

These are fixture-specific engineering receipts, not universal promises.
Layout and Map construction now pre-index graph routes instead of repeatedly
scanning every edge. Study, impact, and journey share immutable graph indexes.
Their separate reproducible control is:

```bash
python scripts/benchmark_study_queries.py --nodes 10000 --queries 20 \
  --output /tmp/codemble-study-scale.json
```

On its deterministic 10,000-module star graph, the pre-index whole-graph scan
control measured 11.308 ms median and 14.282 ms p95; indexed queries measured
1.503 ms median and 2.485 ms p95. All 20 canonical payload digests matched.

## Semantic intelligence is a separate gate

```bash
python scripts/audit_parser_evidence.py
```

The hand-authored oracle covers Python, JavaScript, TypeScript, Go, Java, Rust,
C#, and one mixed project. It checks bounded representative expectations:
supported and partial counts, named edge sources and concept owners, required
entrypoint and role subsets, and selected journey proof breaks. It is designed
to detect both invented facts and omissions in those scopes; it is not a claim
of exhaustive language semantics. Follow-up work is ordered by risk: invented
certainty first, false roles/Home/journeys second, missing certain journey
structure third, and bounded precision or coverage improvements last. No
narrator or provider decides those facts.

## Why the public limit is still 1,000

The public cap can move to 5,000 only when the complete Map passes the same
predeclared gate in Chromium and WebKit:

```bash
cd web
CODEMBLE_PYTHON=python3.12 npm run check:large-project -- \
  --output /tmp/codemble-browser-scale.json
```

The 5,000-module backend passed a 4.956 s cold activation, a 1.666 s no-change
activation, and a 166,789,120-byte process RSS high-water mark reported by the
operating system. Chromium passed 5,000 boxes and 4,999 routes, 35,102 DOM
elements, 11.48 MB of resources, 4.161 s to usable, 29.1 ms Finder input p95,
0.960 s maximum event-loop lag, successful Map retry, zero page overflow at
320 px, and keyboard arrival at the final module.

WebKit did not pass. While the complete 5,000-box Map committed, the first-run
**Skip** control did not become stable within the 5 s interaction budget. The
gate therefore exits non-zero and the ordinary picker remains capped at 1,000
supported files. `--path` still allows an explicit larger scope, but the
cross-engine result is why that is not the default.

The next scale milestone is a canvas-backed **complete Map** renderer followed
by the same two-engine gate. It may change delivery, not truth: every module
must remain represented, searchable, keyboard reachable, and recoverable. A
logical LOD that hides modules is not an acceptable shortcut.

## Open-source inspiration and credit

The design was implemented independently. No source code or assets were
copied, and no runtime dependency, account, paid service, or free-tier service
was added. Licenses were verified at these exact revisions:

- [Graphify](https://github.com/Graphify-Labs/graphify/tree/7fe58b0b0f3873be9a21c30106b8b8527c353aa6)
  ([Apache-2.0](https://github.com/Graphify-Labs/graphify/blob/7fe58b0b0f3873be9a21c30106b8b8527c353aa6/LICENSE)) inspired versioned,
  conservative per-file cache identity and bounded work.
- [Understand Anything](https://github.com/Egonex-AI/Understand-Anything/tree/32944829e7a63a9fa9c55d811d7f98a9530c6a6a)
  ([MIT](https://github.com/Egonex-AI/Understand-Anything/blob/32944829e7a63a9fa9c55d811d7f98a9530c6a6a/LICENSE)) inspired fingerprints,
  deletion/new-file handling, and conservative fallback. Its cosmetic-change
  skip was deliberately not adopted because small edits can change parser
  facts.
- [Archify](https://github.com/tt-a1i/archify/tree/45f0611dfc0dc824e9a13a12efcac207a8a2bdce)
  ([MIT](https://github.com/tt-a1i/archify/blob/45f0611dfc0dc824e9a13a12efcac207a8a2bdce/LICENSE)) inspired validating a
  complete candidate before replacing last-good evidence.
- [Headroom](https://github.com/headroomlabs-ai/headroom/tree/2d88e31a404e2be6c1c428deb2a387599eb820ba)
  ([Apache-2.0](https://github.com/headroomlabs-ai/headroom/blob/2d88e31a404e2be6c1c428deb2a387599eb820ba/LICENSE)) is credited only for a
  future reversible narration-delivery principle; parser evidence is never
  compressed or replaced.
- [Streamlit](https://github.com/streamlit/streamlit/tree/d6f7c0dd3707a83ec505e2343c05b180f59e4f23)
  ([Apache-2.0](https://github.com/streamlit/streamlit/blob/d6f7c0dd3707a83ec505e2343c05b180f59e4f23/LICENSE)) and
  [TensorFlow](https://github.com/tensorflow/tensorflow/tree/27e6bb9d5de1cd9370768a9bdd759ee15a4910eb)
  ([Apache-2.0](https://github.com/tensorflow/tensorflow/blob/27e6bb9d5de1cd9370768a9bdd759ee15a4910eb/LICENSE)) are future representative
  and stress corpora, not vendored fixtures or dependencies.
