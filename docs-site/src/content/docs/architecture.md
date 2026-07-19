---
title: Architecture
description: The adapter seam, the render-ready graph, and why the LLM only narrates.
---

## Three load-bearing decisions

### 1. Language adapters (the seam)

Every language plugs in behind one interface: `parse()` produces the structural
graph; `concepts()` produces idiom annotations for the lens. Python uses the
stdlib `ast` module; JavaScript/TypeScript use the official tree-sitter grammar
wheels. Nothing above the seam hardcodes a language.

One project parser selects adapters by extension, merges their graphs, resolves
Home globally, and rejects node-ID or file-hash conflicts. Adapters walk files
in stable order, keep syntax-error files visible as partial modules, and record
project, external, and unresolved relationships without guessing. Exact path
and unique-name resolution can be certain; extension substitution, extensionless
resolution, and ambiguous candidates remain labeled possible.

### 2. The graph is render-ready

The graph layer computes everything the renderer needs — language, size,
centrality, entrypoint rank, region, understood-state — and the 3D frontend is a
**pure consumer**. No layout or game logic lives in the renderer. This is what
keeps a future read-only share link (and any alternative renderer) cheap.

Graph JSON is schema-versioned and byte-deterministic. Schema 4 includes stable
node IDs, source spans, regions, entrypoint ranks, call in-degree, file hashes,
parser-owned concept annotations, and explicit certainty/external flags on
edges. It also separates parser-ranked entrypoint candidates from the explicit
Home selection, so ambiguous rank-zero candidates remain unselected until the
learner chooses. Concept annotations contain the exact node, line span, and
source snippet that the Lens is allowed to teach. Each annotation also carries
its language so identically named Python and JS/TS concepts remain separate in
the star chart. The file hashes are the cache and progress invalidation key.

### 3. The LLM narrates; it never decides

Structure comes from parsers. Check answers come from the graph. The model's
job is prose: explaining code it is shown, teaching idioms the parser found.
Every explanation links to real `file:line` so you can verify it yourself.

The server exposes one deep study interface. It loads the selected source span,
collects parser-proven neighbors, builds the correctness-contract prompt, calls
the configured provider, validates every returned line and relationship, and
only then writes a local cache entry keyed by provider, model, node, and file
hash. Invalid provider output is withheld rather than softened into a guess.

Lens notes take a separate, model-free path: the language adapter emits a
concept ID only for a proven syntax node, and a deterministic language module
maps that ID to a teachable note. The star chart aggregates those same graph
annotations. Studied state is ephemeral; understood state remains check-owned.

Checks use another deep interface with no provider dependency. `CheckService`
derives stable question suites from certain calls, project imports, direct
callers, and entrypoint ranks, then validates exact option IDs against those
generated answers. Only a completed suite asks `ProgressStore` to persist the
region. The store projects valid file signatures onto immutable nodes and
regions when graph JSON is requested; stale signatures simply remain dim.

## Stack

Python 3.11+ · FastAPI · tree-sitter · Vite + React · `3d-force-graph` (three.js) ·
Anthropic / OpenAI (bring your own key) · local JSON persistence.
