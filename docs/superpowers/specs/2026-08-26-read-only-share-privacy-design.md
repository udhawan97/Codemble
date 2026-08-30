# Read-only share privacy boundary — design spec

Date: 2026-08-26 · Approved by: UD (promoted the next phase and confirmed the
artifact seam) · Status: M20 local artifact, confirmation, capability lifecycle,
standalone HTTPS/browser delivery, encrypted persistence, and the free
backup/anti-resurrection reference implementation are complete; public delivery
connection and independent-node operational evidence remain gated

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
interpret_share_artifact(encoded) -> ShareArtifactDocument
```

This is one in-process deep module. Callers do not select fields, remap IDs,
canonicalize JSON, compute digests, or reason about source exclusions. The
interpreter is the one trusted consumer of those bytes: it either returns the
closed document plus derived facts or rejects the artifact. Preview, delivery,
and storage do not maintain competing validators. Tests use the same interfaces.

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
marked external or an absent target claimed certain fails closed. The parser's
full region routes are first checked against its full internal imports. The
private graph then lays out and derives route weights, Home distance, centrality,
and orbit semantics from the exact deduplicated viewer marks it serializes;
line-distinct edges cannot survive only as an inflated region weight.

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

One `SharePreviewRun` owns the learner-visible lifecycle from choosing policy
through compilation, exact inspection, acknowledgement, and confirmation. It
assigns request identities, refuses stale responses, derives readiness from the
current artifact's exposure flags, invalidates confirmation on restart or project
release, and names the next focus destination. `LearnerSession` performs network
effects; the dialog renders the run and owns only DOM focus.

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

`EncryptedSQLiteShareStorage(root, encryption_key)` is a second production-shaped,
POSIX-only adapter behind the same three-operation seam. It keeps the 256-bit key
outside the storage directory, binds one database to that key with an authenticated
sentinel, validates the exact schema before touching an existing store, and
AES-GCM encrypts and authenticates the complete record body. A keyed commitment
authenticates the complete retained nonce and capability-guard history on every
operation, including detached guards.
Share-derived sensitive plaintext is limited to internal share IDs, ciphertext
lengths, nonces, and capability-derived lookup/fingerprint guards. Every 96-bit record nonce is
durably reserved before encryption; committed capability guards detach rather than
disappear after purge so neither authority nor nonces can be reassigned while the
key store lives. Strict SQLite tables plus immediate transactions own concurrency.
The adapter rejects non-POSIX systems and group/world-readable roots or database
files, rechecking modes on every use; SQLite secure deletion is enabled before
record mutation. Revocation replaces the active ciphertext atomically. `purge(now)`
also expires shares that were never viewed and makes the share row plus serving
index linkage eligible for removal after a configured terminal-retention
threshold—measured from revocation time or absolute expiry—24 hours by default.
Actual removal time includes sweep latency. Detached reuse/nonce guards remain
until key-store retirement.

The selected operations reference uses only free and open-source software:
Caddy (Apache-2.0), restic (BSD-2-Clause), and rest-server (BSD-2-Clause).
Zero license cost does not promise zero operating cost; independently controlled
hardware or storage, media, electricity, DNS, and network access may still cost
money. The application writer can append encrypted snapshots only through TLS
rest-server endpoints started append-only. Every terminal event must receive a
named receipt binding replica, authenticated repository, snapshot, and entry
digest from two distinct configured repositories before the journal's anchored
high-water advances. A separately configured local
operator alone can run `check --read-data`, retain seven days, prune, inventory,
restore to quarantine, or explicitly remove snapshots. Configuration rejects
reused writer authority paths, mismatched journal inventories, unpinned restic
bytes, duplicate or non-HTTPS writer repositories, and non-local primary
operator repositories. Role-local attestations authenticate the live repository
IDs and prove the separately held recovery key matches the active store's exact
32-byte encryption key without co-locating either configuration; shared
authority material is rejected.

Every revocation or expiry creates a token-free `ShareRetirementEvent` in a
create-only chained Retirement Journal and requires an off-host anchor before an
eligible row is acknowledged as unlinkable. A consistent backup contains the
encrypted SQLite database plus a manifest binding its digest, journal high-water,
authenticated backup-repository ID, and exact name-to-repository replica
inventory. The operations runner captures the fully anchored high-water before
taking the SQLite snapshot, so any concurrent later retirement must either
already be reflected in the database or remain eligible for replay. One
store-wide operation lock prevents concurrent writer cycles or retirement from
deleting each other's staging or racing the final seal. The journal uses thread
and process serialization, refuses a new event behind a partially anchored
predecessor, and binds its immutable replica inventory. An independent
journal-node operator can materialize its repository into repository-bound local
evidence. `RestoreGuard` authenticates the quarantine, requires all named
replicas to present one complete agreeing chain, replays every later terminal
event, purges, revalidates, atomically rehydrates the writer journal, and permits
promotion only with an explicit rollback path. Final backup removal first
atomically installs an authenticated retirement seal that closes future Share
creates and writer cycles, then deletes only an exact live snapshot inventory.
`SecurityMetadataRetirementGuard` authorizes—but does not perform—whole-key-store
retirement only after the sealed active store and live authenticated snapshot
inventory are empty, every repository-bound replica agrees, and the eight-day
deadline plus a 48-hour safety margin has elapsed.

`codemble share-ops` exposes bounded writer cycle and attestation, operator
maintenance, authenticated inventory, restore, journal materialization, explicit
backup retirement, retirement authorization, operator attestation, and offline
attestation-validation commands without adding a publishing entrypoint. Failed
writer cycles remove only their two expected staging files while an unexpected
file or lock contention fails closed. Systemd, Caddy, and TOML templates
document the intended independent topology. This is executable
backup and anti-resurrection machinery, not operational proof: an actual
independent-node restore drill, timers, alerts, complete-copy inventory,
deletion observation, and approved key/media erasure remain release gates.

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
is still no CLI publishing option, preview-to-delivery handoff, remote delivery
provider, deployment, account, analytics, upload, or cloud request. The encrypted
SQLite adapter remains disconnected from that application; the operations CLI
can sweep and back up that store but cannot publish it.

Before any upload is authorized, M20 requires:

1. **Complete:** a local preview of the exact artifact and explicit confirmation
   of label and understanding exposure;
2. **Complete in the provider-neutral core:** independent unguessable view and
   deletion capabilities;
3. **Implemented; operational proof pending:** immutable validation,
   server-enforced expiry, inert core reads,
   confirmed idempotent revocation, uniform view failures, persistent encrypted
   active storage, immediate transactional byte removal, and a finite terminal
   share-unlink sweep are complete. The replicated retirement journal, restore
   replay, bounded backup purge, and whole-key-store retirement guard are complete
   in source; real independent-node restoration, deletion, and media erasure
   remain gated;
4. **Implemented; deployment proof pending:** strict schema/bounds validation,
   HTTPS, no-store/no-referrer
   responses, restrictive CSP, no third parties, token-safe application/access
   logs, and authenticated payload/manifest verification are complete. Local
   POSIX file permissions prove the reference adapter's local least-privilege
   floor and unsupported permission models fail closed. Separate append-only
   writer-service and application-host root-operator configurations plus encrypted
   backup commands are complete. The operator uses a root-only mounted independent
   repository, refuses to create a missing active-store shadow, and shares the
   live store's local operation lock; the intended independent multi-target
   configuration, scheduled execution, alerts,
   and authority probes remain gated;
5. automated, configuration, and operational release evidence for all of the
   above, including the actual no-resurrection restore drill.

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
- Duplicate line-level relationships cannot inflate a region route that the
  serialized viewer graph represents only once; the resulting artifact passes
  the same trusted interpreter used by preview, storage, and delivery.
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
- The Share Preview Run refuses stale create/confirm responses, derives exact
  acknowledgement readiness, and clears retained preview state on restart,
  close, and project release.
- Focused tests, Ruff, full pytest, and Graphify update pass before integration.
- Capability tests additionally prove independent generation, derived-only
  storage values, cross-role non-reuse, inert repeated reads, uniform
  invalid/expired/revoked view results, explicit deletion confirmation, atomic
  retry-safe revocation, irreversible observed expiry, closed-schema and derived-
  orbit-relationship revalidation after storage tampering, and capability-keyed
  stored identity/metadata/digest binding for both view and revocation receipts.
- Persistent-storage tests additionally prove an externally supplied key with no
  adjacent key file, authenticated database/key binding including concurrent
  initialization, exact-schema and sentinel reauthentication on every operation,
  fail-closed database replacement, authenticated retained guard history, no plaintext artifact
  in the database, POSIX mode revalidation/non-POSIX refusal, reopen,
  multi-instance uniqueness, persistent revocation and expiry across clock
  rollback, revocation/expiry-relative unlink timing, post-purge capability
  non-reassignment, ciphertext/index/history tamper rejection, and durable
  nonce-reuse refusal even after a failed create or deleted reservation.
- HTTP tests and disposable Chromium/WebKit TLS journeys additionally prove
  exact Host and HTTPS refusal, known/unknown path plus header/query redaction, static context
  encoding, hardened headers on success and every failure, no browser storage,
  no cookies, service worker, or third-party request, inert reload, header-only confirmed
  revocation, uniform post-revocation failure, and token-free structured plus
  Uvicorn access logs.
- Operations tests additionally prove create-only retryable journal anchoring,
  repository/snapshot/entry-bound two-target receipts, cross-thread and
  cross-process serialization, repository-retarget/fork/gap/stale-replica
  refusal, anchored-high-water-before-snapshot ordering, manifest/database/
  repository/high-water binding, concurrent post-backup retirement replay before
  atomic promotion, writer-journal rehydration, and explicit rollback. They also
  prove append-only writer versus local operator authority, disjoint primary and
  journal repository identities/targets, role-local credential-derived
  attestations, pinned restic execution, application-host-local store-wide cycle exclusion, exact
  staging recovery after a transient failure, full-data checks around seven-day
  prune, independent-node journal materialization, closed CLI errors, fixed
  schedules, shadow-store refusal, exact live-inventory deletion behind a durable store seal, authenticated empty
  inventory before retirement authorization, and the eight-day deadline plus
  48-hour margin. These are local proofs, not the required real independent-node
  drill.
