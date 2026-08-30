# Read-only share privacy boundary — design spec

Date: 2026-08-26 · Approved by: UD (promoted the next phase and confirmed the
artifact seam) · Status: M20 local artifact, confirmation, capability lifecycle,
and standalone HTTPS/browser delivery implemented; provider connection and
operational storage/deletion remain gated

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

## 4. Exact preview is local; provider connection remains blocked

Current source adds one app workbench plus strict same-origin loopback routes for
preview and confirmation. They retain one exact candidate in process memory,
return `Cache-Control: no-store`, and deliberately expose `upload_available:
false`. Project release, replacement, or process exit discards the candidate.

Behind that still-local boundary, `ShareDelivery` now owns three operations:
`create(artifact)`, `view(view_capability)`, and
`revoke(delete_capability, confirmed=True)`. It issues independent 256-bit
capabilities, stores only domain-separated derived lookups, reuse-detection
fingerprints, and capability-keyed record bindings, validates the closed schema,
bounds, relationships, digests, and bound storage identity on every view,
enforces expiry from its server clock, and makes revocation atomic and retry-safe
even across clock rollback.
`ShareStoragePort` is the provider-neutral seam; `InMemoryShareStorage` is the
reference adapter and an independent recording adapter exercises the same port in
tests. Revocation immediately removes active artifact bytes while retaining a
non-serving tombstone through expiry for idempotent confirmation.

`create_share_delivery_app(delivery, allowed_hosts=...)` now wraps that core in
one standalone ASGI module. It accepts only HTTPS, exact configured Host values,
and query-free `GET /v/<view capability>`; normalizes view and unknown paths in
the ASGI scope before access logging; renders context-encoded artifact facts in static
HTML with no script, form, service worker, third-party asset, or outbound link;
and applies `no-store`, `no-referrer`, restrictive CSP, no-index, MIME, frame,
permissions, and cross-origin headers to success and error responses alike.
Confirmed revocation is `POST /revoke` with the deletion capability in the
`Authorization` header and one exact JSON field. The header is removed from the
scope before dispatch, `GET` cannot revoke, and invalid, expired, revoked, and
tampered view authority stays one `404` response.

`ShareDelivery` also owns a closed lifecycle-log port. Its structured adapter
accepts only internal non-capability share ID, UTC timestamp, operation, and
outcome; it has no field for capabilities, request targets, artifacts, IP
addresses, User-Agent data, or free-form metadata. Telemetry is best-effort and
non-authoritative so an unavailable sink cannot strand active bytes after create
or alter view/revocation truth; operational sink monitoring remains a deployment
configuration gate. Chromium and WebKit run the
standalone module through disposable TLS and prove compact rendering, header
enforcement, no cookies or other browser storage/service worker, no third-party request, inert
reload, revocation, and token-redacted Uvicorn access logs.

The standalone application is not connected to the local preview routes. There
is still no CLI publishing option, preview-to-delivery handoff, persistent or
remote storage adapter, provider dependency, deployment, account, analytics,
upload, or cloud request.

Before any upload is authorized, M20 requires:

1. **Complete:** a local preview of the exact artifact and explicit confirmation
   of label and understanding exposure;
2. **Complete in the provider-neutral core:** independent unguessable view and
   deletion capabilities;
3. **Partial:** immutable validation, server-enforced expiry, inert core reads,
   confirmed idempotent revocation, removal from the active in-memory adapter,
   and uniform view failures are complete; persistent active/back-up purge
   deadlines and deletion without resurrection remain gated;
4. **Partial:** strict schema/bounds validation, HTTPS, no-store/no-referrer
   responses, restrictive CSP, no third parties, token-safe application/access
   logs, and authenticated payload/manifest verification are complete in the
   standalone in-memory application. Encrypted least-privilege persistent and
   backup storage remains gated;
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
- Preview defaults both sensitive choices off, offers only one-, seven-, or
  thirty-day lifetimes, and displays the exact canonical bytes and payload digest.
- Confirmation requires review, matches each sensitive acknowledgement to the
  retained unexpired artifact, and stays idempotent without creating an upload
  capability.
- Strict JSON loopback routes are no-store; unknown fields, form posts, stale
  or expired preview IDs, changed digests, and mismatched acknowledgements fail
  closed.
- The workbench remains usable at 320 px and restores focus to the rail after
  Close or Escape in Chromium and WebKit.
- Focused tests, Ruff, full pytest, and Graphify update pass before integration.
- Capability tests additionally prove independent generation, derived-only
  storage values, cross-role non-reuse, inert repeated reads, uniform
  invalid/expired/revoked view results, explicit deletion confirmation, atomic
  retry-safe revocation, irreversible observed expiry, closed-schema and derived-
  orbit-relationship revalidation after storage tampering, and capability-keyed
  stored identity/metadata/digest binding for both view and revocation receipts.
- HTTP tests and disposable Chromium/WebKit TLS journeys additionally prove
  exact Host and HTTPS refusal, known/unknown path plus header/query redaction, static context
  encoding, hardened headers on success and every failure, no browser storage,
  no cookies, service worker, or third-party request, inert reload, header-only confirmed
  revocation, uniform post-revocation failure, and token-free structured plus
  Uvicorn access logs.
