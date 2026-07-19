# Phase 1 — JavaScript/TypeScript and polyglot focus

Status: technically complete and published as v0.2.0 from exact-main commit
`b6b7776` on 2026-07-19. M6 external learner acceptance continues separately
in GitHub issue #13 and is not treated as complete.

## Outcome

A learner can run one local Codemble command on a Python, JavaScript,
TypeScript, or mixed project and receive one parser-grounded galaxy. Each
language keeps its own Lens; checks, progress, study, and rendering continue to
consume the same language-neutral graph.

## Correctness boundaries

- Tree-sitter is the only structural source for JS/TS nodes, spans, imports,
  calls, entrypoints, and idiom annotations.
- No package scripts, build tools, source modules, or user code are executed.
- Exact relationships are `certain`; heuristic resolution is retained and
  labeled `possible call` rather than upgraded to fact.
- Tree-sitter error recovery keeps the module visible and marks it partial;
  structures overlapping error nodes are not claimed as complete.
- Python's v0.1.0 graph IDs and graph bytes remain compatible when no other
  supported language is present.

## Waves

| Wave | Deliverable | Merge gate |
| --- | --- | --- |
| M7 | Project parser and language registry | Python byte parity; mixed fake-adapter tests; all existing gates |
| M8 | JS/TS/TSX structural adapter | Exact fixture structures/edges/spans; partial parse; mixed determinism |
| M9 | JS/TS Lens | Every note backed by an exact parser annotation; no annotations inside invalid claims |
| M10 | Language focus and tester release | UI QA, packaged SPA/wheel, docs, tag and downloaded-asset verification |

Each wave lands through a dedicated branch and pull request, is verified on
the branch, and is merged to `main` before the next wave starts.

## Language surface

- JavaScript: `.js`, `.jsx`, `.mjs`, `.cjs`
- TypeScript: `.ts`, `.tsx`, `.mts`, `.cts`
- Mixed JavaScript/TypeScript imports resolve inside one adapter so the graph
  above the seam does not learn Node resolution rules.
- `node_modules`, generated hidden directories, and `.gitignore` matches stay
  outside discovery. The existing 300-source-file cap applies across all
  supported languages combined.

## Interface decision

`ProjectParser.discover(path)` and `ProjectParser.parse(path, entrypoint=...)`
form the project-level interface. The implementation selects registered
adapters by extension, composes their graphs, rejects node-ID/hash conflicts,
and resolves Home globally. Callers do not choose an adapter and do not merge
graphs themselves.

Each `LanguageAdapter` owns only:

- `language` and `file_extensions`
- `discover(path)`
- `parse(path, entrypoint=...)`
- `concepts(node, source)`

This keeps grammar details local while preserving one interface for CLI,
server, tests, and future languages.
