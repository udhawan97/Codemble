# Read-only share privacy boundary — design spec

Date: 2026-08-26 · Approved by: UD (promoted the next phase and confirmed the
artifact seam) · Status: M20 local foundation implemented; delivery remains gated

Primary-source research and the complete future delivery contract live in
[`docs/research/2026-08-26-read-only-share-privacy-boundary.md`](../../research/2026-08-26-read-only-share-privacy-boundary.md).

## 1. Problem

`GET /api/graph` is a local application payload, not a share format. It contains
the project root, relative filenames, raw file hashes, source locations, concept
snippets, role-evidence locations, external targets, and check-owned understanding.
Uploading that object would turn Codemble's one planned cloud touch into source
and learner-history ingestion.

The privacy boundary must exist before a provider does. Storage is not allowed to
repair an unsafe artifact after upload.

## 2. Approved interface

```python
ShareArtifact.from_graph(graph, policy, created_at) -> ShareArtifact
artifact.to_bytes() -> bytes
```

This is one in-process deep module. Callers do not select fields, remap IDs,
canonicalize JSON, compute digests, or reason about source exclusions. Tests use
the same interface and inspect only its returned bytes.

`SharePolicy` contains the only publisher choices:

- `expires_at`: required, absolute, later than creation, at most 30 days;
- `include_labels`: false by default because names and relative module labels are
  proprietary even when no source text is present;
- `include_understanding`: false by default because understood state belongs to the
  learner, not the parser.

Expiry does not slide. A later extension will create a new immutable artifact.

## 3. Exact local artifact

The payload contains only:

- a share schema version and the two opt-in flags;
- CSPRNG-seeded, HMAC-derived snapshot-local node and region IDs;
- node kind, language, bounded size/centrality, partial state, selected-Home
  marker, collision-aware private System position/radius, and parser-owned orbit
  meaning (ring, call depth, and kind);
- deduplicated represented internal edges with kind and certainty;
- render-ready regions and region edges recomputed over the represented graph,
  with private layout, community, route distance, weight, and certainty;
- source-derived labels and understood state only under their explicit flags.

External targets and unresolved possible targets are omitted. A present target
marked external or an absent target claimed certain fails closed. Region routes,
Home distance, centrality, and orbit semantics are cross-checked against the
represented graph; line-distinct edges that project to the same viewer mark are
deduplicated.

The original graph's hash-seeded coordinates are not published because they can
act as an oracle for guessed labels. Every compilation draws a fresh 256-bit key,
uses domain-separated HMAC-SHA-256 values for 128-bit IDs, runs Codemble's existing
collision-aware graph layout over those opaque IDs, and discards the key. Payload
ordering follows opaque IDs, not source identifiers. A label-free artifact is
still not anonymous: topology, language, size, centrality, and orbit layers can
fingerprint a known project.

Schema v1 accepts graph schema 11, the nine shipped language tags, at most 5,000
regions (not nodes), 4,096-byte opted-in labels, JSON-safe non-negative integer
metrics, and bounded render coordinates. Parser coverage must match represented
node sources. New graph schemas, languages, or shareable fields require review.

The sibling manifest contains only source-safe provenance: share/graph/Codemble
versions, UTC creation and expiry, declared exclusions, aggregate coverage, and a
SHA-256 digest over the exact RFC 8785 canonical payload bytes. The digest is
outside the payload it hashes, so it is not self-referential. It detects change;
authenticated storage remains a later delivery requirement.

Always excluded:

- raw source, snippets, source locations, filesystem paths, dedicated filename
  metadata, and file hashes. Opted-in labels may still expose file- or
  module-derived names and the preview must present them as proprietary;
- repository root, remote/VCS identity, and external dependency targets;
- concept evidence, narration, prompts, provider configuration, and caches;
- check questions/answers/attempts, visits, recents, and local logs.

## 4. Delivery remains blocked

This slice adds no CLI option, app control, server route, view/delete token,
storage adapter, provider dependency, deployment, account, analytics, or cloud
request.

Before any upload is authorized, M20 still requires:

1. a local preview of the exact artifact and explicit confirmation of label and
   understanding exposure;
2. independent unguessable view and deletion capabilities;
3. immutable storage with server-enforced expiry, inert `GET`, confirmed
   idempotent deletion, active/back-up purge deadlines, and uniform revoked
   responses;
4. strict schema/bounds validation, HTTPS, no-store/no-referrer responses,
   restrictive CSP, no third parties, token-safe logs, encrypted least-privilege
   storage, and authenticated payload/manifest verification;
5. automated, configuration, and operational release evidence for all of the
   above.

## 5. Local acceptance

- Default bytes contain no source, path, hash, external target, label, source
  position, or learner understanding.
- Labels and understanding appear only under separate explicit choices.
- Input collection order cannot change artifact bytes under the same identity
  material; separate compilations deliberately change IDs and their placement.
- The manifest digest independently reproduces from the payload.
- Naive, non-future, and over-30-day expiry is rejected.
- Contradictory external flags, missing certain endpoints, fabricated region
  routes, stale Home distance, and inconsistent orbit meaning fail closed.
- Ordinary construction from arbitrary bytes is impossible; only `from_graph`
  can create the immutable value.
- Focused tests, Ruff, full pytest, and Graphify update pass before integration.
