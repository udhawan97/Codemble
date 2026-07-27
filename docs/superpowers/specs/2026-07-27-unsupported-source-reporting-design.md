# Unsupported-source reporting — design

**Date:** 2026-07-27 · **Status:** approved by UD · **Milestone:** Phase 1 tester evidence

## Problem

`discover_project_sources` walks every non-gitignored file and keeps only what an
adapter's `SourceOwnership` claims. Files no adapter owns are dropped with no
count anywhere in the graph, the API, or the UI.

A learner running Codemble on a Go backend with a TypeScript frontend therefore
gets a TypeScript-only galaxy and **nothing tells them a whole language was left
out**. The Correctness Contract's letter holds — no structure is invented — but
its purpose does not: this is precisely a wrong the audience cannot detect.

The graph already has the matching precedent. `Graph.partial_files` records
files that failed to parse, and the orientation bar renders it as a counted,
scope-attributed summary. Unsupported files are the same class of omission and
should use the same shape.

## What counts as an unsupported source file

A committed table lists extensions of languages **whose code Codemble's model
applies to** — modules, functions, classes, imports and calls.

This is deliberately narrower than "is it code". The rule was chosen against
evidence, not taste. Counting every code-ish extension was measured on three
real repositories:

| Repository | Reported under "any code extension" | Reported under this rule |
| --- | --- | --- |
| Codemble | 2 `.sh` | *nothing* |
| FolioOrb | 7 `.sh` | *nothing* |
| Golavo | 7 `.rs`, 3 `.sh` | 7 `.rs` |

Shell scripts sit beside a project regardless of what it is written in, so their
presence carries no information about missing architecture. Two of the three
repositories would have raised a false alarm, and FolioOrb's entire report would
have been noise. `.sh` has no module graph and `.sql` has no call graph, so
neither is something Codemble could chart; both stay out. Go, Rust and Java —
the Phase 2 adapters — stay in.

The table holds supported extensions too (`.py`, `.ts`, …). A file is tallied
only when its suffix is in the table **and** no adapter's ownership rule claimed
it during this run. That makes the feature self-maintaining: when the Go adapter
ships, `.go` becomes owned and automatically stops being reported, with no
second list to keep in sync.

A language name is attached only where the extension is unambiguous. `.go` is
Go. `.h` is C or C++ and `.m` is Objective-C or MATLAB, so both are reported by
extension with no language claim — consistent with the contract's rule to say
*"unclear from the code"* rather than guess.

### The table

Named: `.go` Go · `.rs` Rust · `.java` Java · `.kt`/`.kts` Kotlin · `.scala`
Scala · `.swift` Swift · `.cs` C# · `.rb` Ruby · `.php` PHP · `.ex`/`.exs`
Elixir · `.erl` Erlang · `.hs` Haskell · `.clj`/`.cljs` Clojure · `.lua` Lua ·
`.dart` Dart · `.zig` Zig · `.jl` Julia · `.groovy` Groovy · `.c` C · `.cc`/
`.cpp`/`.cxx` C++ · `.hpp` C++ · `.mm` Objective-C++ · `.py` Python · `.js`/
`.jsx`/`.mjs`/`.cjs` JavaScript · `.ts`/`.tsx`/`.mts`/`.cts` TypeScript.

Unnamed (ambiguous, reported by extension only): `.h` · `.m` · `.pl` · `.ml` ·
`.fs` · `.r`.

Deliberately absent: `.sh`, `.sql`, `.vue`, `.svelte`, and every non-code
extension. The first two are argued above. The last two are component formats
whose module semantics Codemble has not modelled; adding them would be a claim
it cannot yet support.

## Architecture

One filesystem walk, no extra I/O; the walk already visits these files.

| Layer | Change |
| --- | --- |
| `codemble/adapters/discovery.py` | Curated table; tally inside the existing `discover_project_sources` walk; new field on `ProjectSourceDiscovery` |
| `codemble/adapters/base.py` | `Graph.unsupported_sources`: `(extension, language, count)` records sorted by extension; serialized in `to_dict()`; schema 7 → 8 |
| `codemble/adapters/project.py` | `ProjectParser` carries the discovery tally into the composed graph |
| `codemble/graph/finalize.py` | Canonical deterministic ordering, as with `partial_files` |
| `web/src/App.jsx` | One line beside the existing `partial-summary`, mode-aware copy |

The tally is computed in `discover_project_sources` because that is the only
place that sees every adapter's ownership at once. `discover_source_files`, the
single-owner helper, must **not** compute it — a Python-only call there would
wrongly report every `.ts` file in the project as unsupported.

## Data flow

```
one os.walk  →  suffix in table AND unclaimed  →  tally by extension
             →  ProjectSourceDiscovery.unsupported
             →  ProjectParser composes into Graph.unsupported_sources
             →  finalize_graph orders canonically
             →  GET /api/graph
             →  orientation bar, beside the partial-files summary
```

## Correctness Contract

1. **No structure is invented.** No node, edge, region or concept is created.
   The output is a file count keyed by extension.
2. **The claim is filesystem-true**, not parser-inferred: these files exist, and
   Codemble did not read them.
3. **Language names are attached only to unambiguous extensions.** Ambiguous
   ones report the extension alone.
4. **Check identity is unaffected.** Generated check IDs seed from
   `_CHECK_SCHEMA_VERSION`, which is independent of the graph schema, so the
   7 → 8 bump cannot churn a pinned suite.
5. **Determinism holds.** Ordering is canonical, so repeated parses are
   byte-identical.

## Testing

- A fixture with `.go` and `.rs` files beside Python reports both, with counts.
- `.md`, `.lock`, `.png` and `.sh` never appear.
- An extension an adapter owns is excluded — proves self-exclusion, and is the
  regression guard for the Phase 2 adapters.
- An ambiguous extension (`.h`) reports with no language name.
- Repeated parses of the same project are byte-identical.
- Existing fixture graphs are unchanged apart from the additive field.

## Out of scope

- Per-file listing. A count plus extension is the honest unit; naming every file
  invites the learner to think Codemble knows something about them.
- Any "add Go support" prompt or roadmap link.
- A new API endpoint. This rides `GET /api/graph`.
- Any change to parsing, checks, progress, or narration.
