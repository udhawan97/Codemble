---
title: Architecture
description: The adapter seam, the render-ready graph, and why the LLM only narrates.
---

:::note[v0.22.0 architecture]
This page describes the nine-language packaged app and current source tree.
:::

## Three load-bearing decisions

### 1. Language adapters (the seam)

Every language plugs in behind one interface: `parse()` produces the structural
graph; `concepts()` produces idiom annotations for the lens; and role evidence
names parser-observed app entries, route handlers, UI renderers, and tests. Python uses the
stdlib `ast` module; JavaScript/TypeScript, Go, Java, Rust, C#, Ruby, and PHP use official
tree-sitter grammar wheels. Nothing above the seam hardcodes a language, and the
registry of adapters is a single tuple in `codemble/adapters/project.py` — that
plus the deterministic Lens note table is the whole of what the two new
languages had to touch outside their adapter files.

One project parser selects adapters by extension, merges their graphs, resolves
Home globally, and rejects node-ID or file-hash conflicts. Adapters walk files
in stable order, keep syntax-error files visible as partial modules, and record
project, external, and unresolved relationships without guessing. Exact path
and unique-name resolution can be certain; extension substitution, extensionless
resolution, and ambiguous candidates remain labeled possible.

Calls resolve on the same principle. A receiver constructed at the call site and
a method inherited from an in-project base class each identify one declaration,
so both are certain; a receiver known only by its type annotation resolves to
that class but stays possible, because the runtime type may be a subclass that
overrides it. A name no evidence narrows is still recorded as a possible
relationship rather than dropped.

### 2. The graph is render-ready

The graph layer computes everything the renderer needs — language, size,
centrality, entrypoint rank, region, understood-state — and the 3D frontend is a
**pure consumer**. No layout or game logic lives in the renderer. This is what
keeps a future read-only share link (and any alternative renderer) cheap.

Graph JSON is schema-versioned and byte-deterministic. Schema 11 carries stable node
IDs, source spans, regions, entrypoint ranks, call in-degree, file hashes,
parser-owned concept annotations, parser-owned role evidence, and explicit
certainty/external flags on edges. A role record has a closed role name, stable
parser-rule ID, observation file, and exact line span. Framework roles also
require matching import/factory/binding provenance; a familiar method or
annotation name alone is not enough. Its observation may
differ from the declaration it identifies—for example, a route registration
that points at a handler declared in another file. Finalization rejects unknown
roles, missing or partial nodes/files, invalid paths, and out-of-range spans.
Adapters discard role candidates from a file the parser marked partial before
that validation boundary, so safe partial graph evidence remains available.
The graph also separates parser-ranked entrypoint candidates from the explicit
Home selection, so ambiguous rank-zero candidates remain unselected until the
learner chooses. Later revisions added the import community a region belongs to,
its hop distance from Home, each node's call-depth orbit, a count of files in
languages no adapter read, and which communities are large enough to be given a
colour family — all of them facts the renderer would otherwise have to infer.
Schema 11 retains canonical **import cycle groups**: strongly connected groups
of regions computed only from imports whose certainty flag is true. Members and
components are sorted only for stable bytes—not displayed as a direct arrow
path—the field is replaced on every finalization pass, and a loop made only of
possible imports is not reported. Concept annotations contain the exact node, line span, and
source snippet that the Lens is allowed to teach. Each annotation also carries
its language, so identically named concepts stay separate in the star chart.
Several of the supported languages have an `async/await`, and each keeps its own
evidence rather than pooling it under one row. The file hashes are the cache and progress invalidation key.

The learning-journey index is one bounded, model-free projection over this
graph. A fingerprint of schema, root, sorted file hashes, Home, and target keys
its result. A stable breadth-first walk can complete a route only with directed,
certain imports and calls; generic containment is context, never traversal.
When no complete route exists, the index reports the break separately and may
offer only target-relevant possible edges as a bounded frontier. Test-role nodes
inside the existing blast radius are verification candidates, never proof of
coverage or a test result. The server sends this single mode-neutral payload to
Study; Easy and Expert are presentations of the same step IDs, so changing mode
does not create a second architecture truth.

The mixed-project language focus is a pure frontend projection over that graph.
It retains the original node and region records, coordinates, metadata,
uncertainty, progress, and outward external/unresolved edges. No filtered view
is written back to the parser or persistence layer.

Because it is a projection, a focus can legitimately leave a view with nothing
to draw: Home is written in one language, and on a polyglot project nothing in
another language necessarily has an import route to it. Both Map tabs treat that
as a state to explain rather than an empty canvas — they say that Home is not
written in the focused language, and offer a control to show all languages
again.

Launch choice and landing briefs are projections too. `LearnerSession` commits
the selected Easy/Expert mode before a guided First Flight begins; React then
renders the already-selected graph target. **Land and learn** deterministically
chooses the first complete parser-owned declaration in source order, then reuses
the safe module anchor when necessary, then reuses the ordinary Study and check
events. The landing brief derives kind,
source span, parser summary, and inbound/outbound connections from the same node
and edge records used by Study. Decorative terrain, atmosphere, spiral dust,
and star shells are seeded by existing graph identity and never write evidence
or progress back into the session.

### 3. The LLM narrates; it never decides

Structure comes from parsers. Check answers come from the graph. The model's
job is prose: explaining code it is shown, teaching idioms the parser found.
Every explanation links to real `file:line` so you can verify it yourself.

The server exposes one deep study interface. It loads the selected source span,
collects the parser-owned journey and neighbors, builds the correctness-contract prompt, calls
the configured provider, validates every returned line and relationship, and
only then writes a local cache entry keyed by provider, model, node, and file
hash. Invalid provider output is withheld rather than softened into a guess.

Lens notes take a separate, model-free path: the language adapter emits a
concept ID only for a proven syntax node, and a deterministic language module
maps that ID to a teachable note. The star chart aggregates those same graph
annotations. Studied state is ephemeral; understood state remains check-owned,
and the explored set — which systems the learner has visited — is persisted
beside it as its own record, so neither can ever be read as the other.

The impact trace takes the same model-free path. It is a bounded breadth-first
walk over the graph's own edges, out to three hops in each direction, recording
the shallowest depth at which each structure is reached and marking a row
uncertain when no fully proven route to it exists. No provider is involved, so
the section renders identically with no key configured.

Checks use another deep interface with no provider dependency. `CheckService`
derives stable question suites from certain calls, project imports, direct
callers, and entrypoint ranks, then validates exact option IDs against those
generated answers. Only a completed suite asks `ProgressStore` to persist the
region. The store projects valid file signatures onto immutable nodes and
regions when graph JSON is requested; stale signatures simply remain dim.

## Stack

Python 3.11+ · FastAPI · tree-sitter · Vite + React · `3d-force-graph` (three.js) ·
Canvas 2D for the complete flat map · Anthropic / OpenAI (bring your own key) · local JSON
persistence.

Both the 3D galaxy coordinates and the 2D map layouts are computed in
`codemble/graph/` and served as data — `GET /api/graph` and `GET /api/map`. The
renderer places what the graph already decided. That is why "same code → same
sky" holds, and why adding a second renderer needed no second source of truth.
