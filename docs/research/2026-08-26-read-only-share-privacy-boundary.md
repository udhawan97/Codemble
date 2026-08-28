# Accountless read-only share: technical privacy boundary

**Date:** 2026-08-26
**Status:** requirements contract. The local artifact compiler, exact preview,
and provider-neutral in-process capability lifecycle are selected in
`docs/superpowers/specs/2026-08-26-read-only-share-privacy-design.md`; no remote
provider, account system, persistent storage adapter, HTTP delivery, or cloud
implementation is selected.

`MUST` and `SHOULD` below are proposed Codemble product requirements, not quotations
from the cited sources or a claim of legal compliance. The sources establish the
security and privacy properties; the Codemble-specific field boundary is the design
inference.

## Security model

The view URL is a **bearer capability**: anyone who possesses it can read and copy the
snapshot until it expires or is revoked. Bearer-token guidance is explicit that an
unintended holder can use a disclosed token, and W3C capability-URL guidance warns that
these links are secure only in tightly controlled circumstances
([RFC 6750 §5.3](https://www.rfc-editor.org/rfc/rfc6750.html#section-5.3),
[W3C Capability URLs §5](https://www.w3.org/TR/capability-urls/#recommendations)).
The W3C source is a First Public Working Draft toward a TAG Finding, not a
Recommendation
([document status](https://www.w3.org/TR/capability-urls/#status-of-this-document)).
The creation UI therefore **MUST** say “Anyone with this link can view and copy this
snapshot” and show the exact expiry. Codemble cannot prevent a legitimate viewer from
redistributing the link, recording the page, or copying its contents.

## Required contract

### 1. Publish a minimal, raw-source-free snapshot

GDPR requires data minimization and storage limitation; NIST recommends minimization,
selective disclosure, and policy-governed destruction
([GDPR Article 5(1)(c),(e)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679),
[NIST Privacy Framework CT.DM-P and CT.DP-P](https://www.nist.gov/system/files/documents/2020/01/16/NIST%20Privacy%20Framework_V1.0.pdf#page=28)). Codemble **MUST**
construct the share artifact locally from a closed envelope, then preview the exact
payload and manifest before upload. The only accepted envelope is:

- `payload`: CSPRNG-seeded share-local opaque IDs and source-ID-independent layout;
  explicitly previewed user-visible relative labels; node kind, language,
  bounded size, entrypoint, parser-owned edges and certainty; plus
  understood/charted state only if the publisher explicitly elects to share it;
- `manifest`: share schema, Codemble and parser-contract versions, creation and expiry
  times, the fixed declared-exclusion list, parser coverage/partial-source summary, and
  `payload_digest`.

Both objects **MUST** reject every unlisted field. Server-only lookup IDs, capability
digests, revocation state, and the storage authentication tag are not part of the shared
artifact or upload.

These are the only fields needed to render the read-only structural snapshot and state
its bounded provenance without uploading the project.

Relative labels and identifiers remain source-derived proprietary information even
though no raw source is present. Confirmation **MUST** show the exact labels to be
published and let the publisher omit them; Codemble **MUST NOT** silently alias them in a
way that masquerades as parser truth.

Omitting labels is not anonymization: topology, language, size, and centrality can still
fingerprint a known project; orbit layers and radii can remain especially recognisable.
Each newly compiled artifact **MUST** therefore use fresh CSPRNG material for unlinkable
IDs, run collision-aware placement over those opaque identities rather than source IDs,
and keep the key material out of the artifact. Recompiling the same project deliberately
changes identity-to-position assignment; canonicalization guarantees stable bytes for one
constructed snapshot, not anonymity or resistance to topology matching.

Everything else **MUST be absent**, including raw source bytes, source snippets, line
text, absolute paths, repository remotes or commit identity, environment/user/home
names, file-content hashes, narration or prompts, provider/model/key/configuration,
narration cache, check questions/answers/attempts, visit history, recent projects, and
local logs. OWASP independently lists application source, access tokens, session IDs,
credentials, keys, and sensitive personal data as values that should not be recorded
directly in logs
([OWASP Logging, “Data to exclude”](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#data-to-exclude)).

The upload endpoint **MUST** reject unknown fields, over-versioned schemas, unbounded
strings or collections, executable HTML, and artifact-supplied URLs rather
than silently retaining them. A new shareable field requires an explicit schema review;
it may not appear merely because the local graph object gained a property.

### 2. Use an unguessable, least-authority capability

The read token **MUST** be opaque, unique, generated by a CSPRNG, contain at least 128
bits of randomness, and encode no project or user information. OWASP recommends a
CSPRNG and at least 128 bits for self-generated security tokens; URL identifiers can
leak through links, logs, browser history, referrers, and search engines
([OWASP Session Management, entropy and content](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#session-id-entropy),
[W3C Capability URLs §4.1](https://www.w3.org/TR/capability-urls/#risk-of-exposure)).
Sequential IDs, timestamps, source hashes, and non-random UUID variants therefore do
not satisfy this capability requirement.

The capability **MUST** grant only `GET` access to one immutable snapshot. It cannot
edit, refresh, extend, replace, or delete anything; W3C guidance says a `GET` capability
must not cause deletion or other side effects
([W3C Capability URLs §5.1](https://www.w3.org/TR/capability-urls/#application-design)).
Tokens **MUST NOT** be reused or reassigned after expiry/deletion.

### 3. Make expiry absolute and server-enforced

Every share **MUST** have an explicit `expires_at`; indefinite shares are out of scope.
Before launch the product **MUST** define a finite `MAX_SHARE_LIFETIME`; creation rejects
later timestamps. The publisher chooses within that policy and sees the absolute timestamp
before confirming. The server rejects the capability at or after that instant regardless
of client clock or activity. This follows the standard expiration semantic—at or after
expiry, a token must not be accepted—and the W3C recommendation that capability URLs
expire
([RFC 7519 §4.1.4](https://www.rfc-editor.org/rfc/rfc7519.html#section-4.1.4),
[W3C Capability URLs §5.1](https://www.w3.org/TR/capability-urls/#application-design)).

Access does not slide or renew expiry. Extending a share **MUST** create a new snapshot
and new capabilities so that the old artifact keeps its original provenance and
lifecycle. Standards do not choose the numeric maximum; that remains a human-approved
risk-policy decision and is a launch blocker until recorded.

### 4. Separate deletion authority from viewing

Because there is no account, creation **MUST** display once an independent, equally
strong **deletion capability** that never appears in the view URL, viewer payload, or
viewer page. It remains retryable until revocation succeeds or the share expires, then
becomes invalid. The service stores only derived lookup, reuse-detection, and
record-authentication values for both capabilities. Losing
the deletion capability means expiry is the only recovery path; the creation UI **MUST**
state that plainly. This is the accountless inference from W3C’s revocation requirement
and least-authority capability model
([W3C Capability URLs §5.1](https://www.w3.org/TR/capability-urls/#application-design)).

Deletion **MUST** require explicit confirmation followed by `POST` or `DELETE`, never a
`GET`, redirect, preview, prefetch, or link-scanner visit; the deletion capability travels
in a protected header or request body, not a URL. The operation **MUST** be concurrency-safe
and retry-safe/idempotent.

Deletion and expiry **MUST** atomically revoke view access first. No authorization check
that begins after the revocation commit may succeed; a response already authorized before
that point may finish, so deletion cannot retract bytes already in flight. They then purge
the snapshot and derived copies from active stores and indexes within a documented finite
`ACTIVE_PURGE_DEADLINE`. Backups and disposal media **MUST** have a documented finite
maximum retention, after which recovery is infeasible; until backup purge completes,
revoked data **MUST** remain inaccessible to the serving path. This distinguishes
immediate **revocation** from
eventual **erasure** instead of promising that one HTTP response instantly rewrites every
backup. GDPR Article 17 requires erasure without undue delay when its conditions apply,
while NIST defines sanitization by making target-data access infeasible
([GDPR Article 17](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679),
[NIST SP 800-88 Rev. 2](https://csrc.nist.gov/pubs/sp/800/88/r2/final)).

Lifecycle logs **MUST** use a closed allowlist: an internal non-capability share ID,
timestamps, and outcomes. They **MUST NOT** record either raw token, the full target URL,
the snapshot, behavioural analytics, or IP/User-Agent data unless a documented security
need justifies those fields and a finite retention. There is no secondary use. OWASP
recommends token-safe lifecycle logging and specifically warns against recording session
identifiers directly
([OWASP Session Management, lifecycle logging](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#logging-sessions-life-cycle-monitoring-creation-usage-and-destruction-of-session-ids)).

### 5. Treat the capability URL as a secret in HTTP and the browser

All capability traffic **MUST** use HTTPS. Every capability-bearing HTML/API response,
redirect, and error **MUST** send `Cache-Control: no-store`; application code and service
workers **MUST NOT** persist the snapshot or token in browser storage. `no-store` tells
caches not to retain or reuse the request/response, but the RFC cautions that it is not
by itself a sufficient privacy mechanism
([RFC 9111 §5.2.2.5](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.5),
[§5.2.1.5](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.1.5)).
Capability-independent static viewer assets may be cached separately.

The viewer **MUST** context-encode every artifact string, enforce a restrictive Content
Security Policy with only self-hosted assets, send `Referrer-Policy: no-referrer`, make no
third-party network requests, and give outbound links `rel="noreferrer"`. Server, proxy,
analytics, crash, and tracing configuration **MUST** redact the token and full request
target. URIs are
widely displayed and logged, and referrer control specifically exists to reduce
capability-URL leakage
([RFC 9110 §17.9](https://www.rfc-editor.org/rfc/rfc9110.html#section-17.9),
[W3C Referrer Policy §1.2](https://www.w3.org/TR/referrer-policy/#security),
[W3C Capability URLs §5.1](https://www.w3.org/TR/capability-urls/#application-design),
[W3C Content Security Policy](https://www.w3.org/TR/CSP3/)).

Stored snapshots and backups **MUST** be encrypted and limited to least-privilege service
and operator access; the service **MUST NOT** reuse them for analytics, model training, or
any purpose beyond serving and deleting the share. NIST calls for least privilege, protection
at rest/in transit, leak protection, and managed removal
([Privacy Framework PR.AC-P4 and PR.DS-P1–P5](https://www.nist.gov/system/files/documents/2020/01/16/NIST%20Privacy%20Framework_V1.0.pdf#page=30)).

### 6. Bind provenance and integrity to the exact snapshot

A share URL **MUST** name one immutable artifact. In the envelope defined in §1,
`payload` contains no digest; `payload_digest` is SHA-256 over exactly the RFC 8785
canonical payload bytes; and the sibling `manifest` contains that digest plus only the
listed source-safe facts—never a digest, URL, or identity of the source repository. SLSA defines provenance as verifiable
information about where, when, and how an artifact was produced
([SLSA 1.2 Provenance](https://slsa.dev/spec/v1.2/provenance)).

The service **MUST** authenticate the manifest and payload together in storage, then
verify authentication, recompute the payload digest, and validate schema before serving;
any mismatch fails closed.
RFC 8785 exists so hashing/signing JSON is repeatable, and NIST specifies secure hashes
as change-detection digests
([RFC 8785 §1](https://www.rfc-editor.org/rfc/rfc8785.html#section-1),
[NIST FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)). A bare digest is
not proof of authorship if an attacker can replace both payload and digest; integrity
protection therefore needs an authenticated server-side boundary, without prescribing a
cloud or storage product.

## Recommended defence in depth

- **SHOULD** rate-limit and monitor invalid-token probes without logging raw targets;
  OWASP recommends brute-force protection for URL tokens
  ([Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html#url-tokens)).
- **SHOULD** return one uniform not-found response for invalid, expired, and deleted
  capabilities; W3C permits `404 Not Found` or `410 Gone`
  ([Capability URLs §5.1](https://www.w3.org/TR/capability-urls/#application-design)).
- **SHOULD** exclude the capability path in `robots.txt`, while treating that only as a
  crawler hint, never access control
  ([Capability URLs §5.1](https://www.w3.org/TR/capability-urls/#application-design)).
- **SHOULD** give the publisher a downloadable deletion receipt containing the deletion
  capability, expiry, and non-secret artifact digest; if provided, it **MUST** repeat that
  there is no account recovery.

## Release-gate evidence

An implementation is not within this boundary until release evidence demonstrates the
whole contract. Automated tests cover acceptance of only the exact `payload` + `manifest`
envelope, rejection of every unknown field, bounds and hostile strings,
independent token-generation path, inert `GET`, accidental deletion paths, concurrent
expiry/delete, headers/browser storage, deterministic canonical bytes and the exact
manifest/payload digest scope, and fail-closed tampering. Production code/config inspection covers
CSP, logging, analytics, transport, and encrypted least-privilege storage. Operational
evidence covers active purge, backup retention/restoration without resurrection, and
deletion of allowed security metadata. No single test can prove universal non-leakage or
CSPRNG provenance.
