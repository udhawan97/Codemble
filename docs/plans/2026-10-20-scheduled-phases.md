# Codemble scheduled implementation phases

Date: 2026-10-20 (America/Chicago). Planning baseline:
`de0debe930317da18bc65b3c6c373c780d836910`.

This is the canonical implementation queue for scheduled Codemble work.
It elaborates the existing M20 roadmap and the parallel learner-acceptance
work in [CLAUDE.md](../../CLAUDE.md). The owner requested detailed phases with
council review for scheduled implementation. That authorizes preparing this
queue and routing existing scheduled runs to it; it does not promote NEXT or
LATER, provision infrastructure, contact testers, or enable public sharing.

The useful next step is **P1.1a: correct the learner intake**, followed by
**P1.1b: rehearse it in native Safari**.
Then make M20's remaining operational evidence collectable and reviewable.
Do not rebuild the completed sharing foundations or replace missing real-world
evidence with additional unit tests.

## Current evidence and boundaries

Verified during planning:

- Local main is `de0debe`; its latest reported CI and Pages runs succeeded
  (`37667515303`, `37667515379`). These are historical run results for that SHA,
  not validation of future changes.
- The repository release ledger identifies v0.24.0 as stable. This planning
  pass did not redownload release assets or retest the installed release.
- [Issue #13](https://github.com/udhawan97/Codemble/issues/13) is open and its
  acceptance checklist is unchecked. Automated rehearsal is not an unaided
  learner result.
- [TESTING.md](../../TESTING.md) recommends at most 1,000 supported files and
  describes that as the prompt boundary; current roadmap/source documentation
  records the verified 5,000-file cap. A small recommended tester project and
  the supported cap must be stated separately.
- The local preview, capability core, standalone HTTP viewer, encrypted store,
  backup/retirement machinery, and alert relay already exist. The preview has
  no public-delivery handoff. [The operations runbook](../../ops/share/README.md)
  explicitly requires independent-node evidence before connecting it.
- `tests/test_share_operations_assets.py` and `tests/test_share_alerts.py`
  passed together: **14 tests**. This checks source preflights and relay
  behavior; it proves neither systemd execution nor external alert delivery.
- Open dependency PRs at planning time:
  [#50 Hatchling](https://github.com/udhawan97/Codemble/pull/50) and
  [#51 Starlight](https://github.com/udhawan97/Codemble/pull/51).
  Their eligibility and current checks must be re-established before work.
- The locally discoverable weekly CAPO heartbeat is active, Sundays at noon
  America/Chicago. Its global priority order and two-substantial-repository
  limit remain authoritative. Daily Elf/Mobster schedules were not found in
  the local automation inventory; this plan does not claim to configure them.

Preserve the parser-owned structure/roles/certainty, directed proven journeys,
graph-only check answers, check-only amber, module-scoped progress, complete
5,000-module Map, existing adapter seam, and bounded camera. No accounts,
telemetry, automatic uploads, new hosting, new quest family, or speculative
parser rewrite enters this queue.

## Queue and dependencies

Statuses describe eligibility, not completed work. `READY` means a future
authorized run may start after preflight and its current plan council.
`WAITING` means a dependency is missing. `DECISION` requires a specific owner
decision. `HOLD` means a required verification failed or is unavailable.

| Phase | Outcome | Initial status | Dependency | Expected packet size |
| --- | --- | --- | --- | --- |
| P1 | Accurate learner intake and evidence-driven repairs | P1.1a READY; P1.1b follows; human results WAITING | None | One docs packet, one rehearsal, then one reproduced defect per packet |
| P2 | Offline operational evidence index and fail-closed completeness checker | READY after P1.1a or an explicit priority decision | Existing M20 contract; P1.1b may remain HOLD | Three small source/tooling packets |
| P3 | Disposable operational rehearsal through existing interfaces | WAITING | P2 schema and checker | Two or more bounded scenario packets |
| P4 | Independent deployment, restore, deletion, and alert acceptance | DECISION | P2/P3 plus named infrastructure and operator authority | Several real observation windows |
| P5 | Explicit exact-preview-to-delivery handoff | DECISION | P4 passes; approved handoff design and endpoint | Design first, then three bounded implementation packets |
| P6 | Qualified release and post-release verification | Preparation WAITING; publication authority rechecked per candidate | Complete useful candidate plus applicable explicit or standing publication authority | Preparation, publication, outside-in verification |

P1 learner evidence continues alongside P2–P4. P6 can package an independently
useful local improvement without completing public sharing when the invoking
run has applicable publication authority. Historical v0.23.0/v0.24.0 approvals
are scoped precedents, not automatic authority for a future version.
Public-sharing claims require P4 and P5. No phase is a
promise to finish in one weekly run. P4 elapsed-time requirements cannot be
compressed by scheduling more agents.

## Rules for each scheduled run

1. Read CLAUDE.md in full, this queue, applicable instructions, the latest run
   record, and any candidate's branch/PR. Use Graphify before cross-file
   exploration and corroborate claims against source.
2. Verify repository ownership and mutation authority, current default SHA,
   worktrees, dirty/untracked state, remote changes, open PRs, required checks,
   and existing release/deployment triggers. Preserve unrelated work, including
   `.git-backup-remote` and `.last-git-backup-ts`.
3. Reconcile every candidate packet against actual commits and behavior.
   Resume an existing candidate before creating another. Never infer completion
   from a checked box or old council verdict.
4. Select **one** ready packet, subject to CAPO's global priorities. Urgent
   security/regression work takes precedence; otherwise resume actionable
   unfinished verification before taking the next packet below. A verification
   HOLD with unchanged external prerequisites does not block independent ready
   work. If all work is externally blocked, record the
   exact missing input and stop. No recurring filler commits.
5. Claim the packet in the queue's run record with branch/worktree/PR,
   starting SHA, owner/run identifier, and status. Re-read the record and remote
   immediately before editing and integration. Git is not a distributed lock:
   another active claim or incompatible head means defer, not overwrite.
6. Define its exact allowed files, behavior, failure cases, commands, rollback,
   and authority boundary. Run the two-round plan council described below.
   A newly discovered defect outside the packet is recorded separately unless
   it must be fixed to make that packet correct.
7. Implement the smallest complete change. Add meaningful behavior-level
   regression tests for parser/graph/check/persistence/operations code.
   Exercise UI changes in a running app. Do not add tests that merely echo
   documentation or duplicate an already-proven invariant.
8. Run appropriate focused and repository-required checks. Review the final
   diff, generated bundle when touched, docs, failure paths, and privacy.
   Run a fresh two-round implementation council before integration.
9. Commit only the packet. Preserve DCO/contribution rules, required reviews
   and protections. Integrate only on current successful evidence, without
   force pushes or bypasses. A changed base invalidates affected tests/reviews.
10. Record tested SHA/tree, command exits and evidence locations, both council
    summaries, integration/default-branch SHA, CI state, remaining blockers,
    and the next exact packet. Update CLAUDE.md's maintained state without
    marking M20 or human acceptance complete prematurely.

If interrupted, leave the candidate branch and its last verified stage.
On resumption, inspect actual state before retrying an action with side effects.
Never retry publish, restore, retirement, or upload blindly after an uncertain
result. Record an unchanged blocker once and notify again only when actionable.

## Council procedure for every phase

Use the installed council-review skill. Exactly **two full rounds**, each with
four independent reviewers: evidence, coverage, risk, and outcome. With only
three free agent slots, run the fourth reviewer after a slot becomes available.
Reviewers receive the same request, constraints, source references, candidate
plan, acceptance matrix, risks, and proposed result; they do not receive one
another's deliberations.

Round 1 challenges each phase's scope, authority, source grounding, failure
cases, verification strength, and useful stopping point. Revise the plan and
resolve disagreements against evidence. Round 2 reviews the revised packet.
Every reviewer returns APPROVE, APPROVE_WITH_NITS, or BLOCK with specific
corrections. Resolve every valid blocker; material later corrections require
targeted acceptance by the reviewer who raised the blocker.

The initial council reviews **all six phase plans**, including conditional
phases. Before future implementation, refresh the packet's plan council against
the actual base and current evidence. A separate implementation council reviews
the exact changed tree and test receipts. Neither council substitutes for
human learner results, independent infrastructure, native browser acceptance,
required GitHub reviews, or the owner's reserved decisions.

Store only concise outcomes and material corrections in public repository
records. Keep reviewer transcripts and sensitive evidence outside the repo.
Bind a review to the plan/content digest, candidate SHA/tree, and verification
receipt digest; any material scope, contract, topology, or behavior change
invalidates that acceptance.

## P1 — Learner intake and measured improvements

### P1.1a — Correct the intake

**Problem:** the testing guide mixes a sensible small-project recommendation
with an obsolete supported limit. The open learner gate needs consistent,
privacy-preserving evidence tied to the actual tested release.

**Files:** `TESTING.md`, `.github/ISSUE_TEMPLATE/early_tester.yml`,
`docs/plans/phase-1.md` only where current instructions disagree, and the
maintained portions of CLAUDE.md. Read the form first; retain existing fields
that already serve the purpose.

**Implementation:**

1. State the verified 5,000-file supported cap separately from a recommendation
   to choose a smaller project for a ten-minute trial. Recheck the actual
   parser limit first. Preserve historical release claims.
2. Clarify recording the installed version, OS/browser, chosen flow/register,
   whether help was needed, first confusion verbatim, illumination result, and
   restart persistence. Use pseudonymous reports and coarse project counts;
   never request source, paths, credentials, or private repository identities.
3. Keep minimum three independent unaided Python successes for issue #13;
   mixed-language observations are additional evidence. Existing later owner
   approvals supersede the issue body's old Phase-1 promotion prohibition.
**Acceptance for P1.1a:** the guide's commands/control names and cap agree with
source; the issue form parses; existing useful fields are retained; links
resolve and privacy requirements remain explicit. This docs packet may land
independently. P2 may begin once P1.1a passes even if P1.1b is on HOLD.

### P1.1b — Rehearse the corrected intake

Rehearse the written route with a disposable synthetic project and isolated
   `CODEMBLE_DATA_DIR`, provider variables/configuration removed. Explicitly
   label the result an agent rehearsal. Do not send invitations, comments, or
   messages to testers without specific authorization.

**Acceptance for P1.1b:** every instruction resolves to a current control or command;
the supported-cap statement agrees with source; keyless Explore/Study/check/
restart works; no progress writes escape the disposable directory. Run native
Safari for the manual path through the Safari plugin and label any unavailable
target as HOLD. Keep P1.1b unfinished when unavailable; do not repeat an
unchanged blocked attempt or hold independent P2 work behind it.

**Failure cases:** no Home, partial source, failed/incorrect answer, no safe
checks, save refusal, and project restart. Reuse existing gates for their
coverage; manual rehearsal need not falsely certify every case.

**Rollback:** revert the documentation/form changes. No user data migration.
Do not close issue #13 from this packet.

### P1.2 — Process actual learner evidence

When owner-supplied or authorized accessible reports exist, record version,
assistance and outcome independently. Reproduce each actionable confusion
using a minimal synthetic fixture. A repair packet must name the observed
defect, root cause, allowed files, red regression, expected experience and
rollback before implementation. No blanket UX redesign or speculative feature
list is authorized by a failed trial.

**Done:** the smallest repair passes relevant gates and the queue names whether
an independent human rerun is still needed. Only three genuine unaided
successes plus their records can satisfy the original learner acceptance.
If reports are absent, leave this packet WAITING and continue P2.

## P2 — Operational evidence that cannot overclaim

### P2.1 — Define a small evidence index

**Problem:** M20's remaining evidence is listed in the runbook but is not a
machine-checkable, versioned handoff for a later run. Schema-valid summaries
must not turn into fabricated operational approval.

**Proposed files:** `ops/share/evidence.schema.json`,
`ops/share/evidence.example.json`, a short runbook section. Reuse an existing
equivalent if discovered at execution time. Keep this tooling outside the
runtime share/artifact schemas.

Define a closed, bounded index with schema version, candidate SHA, deployment
alias, configuration/toolchain digests, observation interval, evidence kind
(`simulated`, `local-rehearsal`, `independent-operation`), required gate IDs,
result, and opaque private-receipt references/digests. Separate presence,
integrity, and human verification status. Missing/unknown is never pass.
A digest detects changes; it does not authenticate who made a claim.

Required gate IDs cover: topology/role separation, scheduler observations,
active sweeping, writer denial of destructive operations, full-data
verification/prune, per-node alert receipt, backup freshness/RPO, restore/RTO,
post-snapshot revoke and expiry replay, deletion deadline, complete-copy
inventory, retirement seal/guard, and approved key/media erasure.

Only synthetic examples belong in Git. Real repository IDs, snapshot/journal
receipts, credential-derived attestations, host inventory, filesystem paths,
capabilities and actual operator evidence stay private. Public records contain
aggregate pass/hold and opaque receipt references, never the receipt contents.

**Acceptance:** trace each gate to the existing runbook/design; examples make
simulation obvious; no schema field can grant upload or retirement authority.
The schema has an explicit maximum document size and bounded lists/strings.

### P2.2 — Add an offline completeness checker

**Proposed files:** `scripts/check_share_operations_evidence.py`,
`tests/test_share_operations_evidence.py`. Use existing dependencies; avoid
adding a schema library merely for this small closed contract.

The command reads only an explicitly supplied bounded index and trusted
`--expected-candidate-sha` / `--expected-config-digest` arguments taken from the
reviewed execution packet, independently of that index. Require exact equality;
a missing expected value cannot silently disable either comparison. It performs no
network access, config discovery, credential reads, referenced-file traversal,
shell interpolation, service start, or deletion. Validate types, unknown fields,
duplicate gate IDs, result enums, finite times and ordering, digest syntax,
candidate/config binding, and the declared evidence class. Sanitize diagnostics:
print only known field/gate codes, never arbitrary input values.

Report **incomplete**, **structurally complete but operator review required**,
or **invalid**. It must never print “safe to deploy”, “erased”, or operational
approval merely because all rows say pass. Simulated/local evidence cannot
satisfy independent-operation requirements. Explicit owner/operator review
is recorded separately from machine validation.

**Tests:** missing gate, false pass with no receipt reference, duplicate IDs,
unknown fields, future/reversed observation dates, wrong SHA/config, malformed
digests, oversized input, embedded secrets in invalid fields (not echoed),
declared evidence-class inconsistencies, and valid synthetic input.
An index author can lie about an observation's origin; this checker cannot
detect relabelled fabricated receipts. The independent operator must inspect
the private underlying evidence and establish that origin.
Define clock tolerance in the packet instead of guessing it in implementation.

**Done:** negative fixtures fail for the intended reason; valid input produces
only the limited structural claim. Existing M20 tests remain green.

### P2.3 — Put evidence requirements in the operator handoff

Add a concise checklist linking each existing command to its gate and private
receipt. Resolve any stale research/spec wording against newer append-only
Decision Log entries; do not silently rewrite the selected topology or legal
claims. Avoid importing an old “not selected” statement over the later selected
backup design.

**Rollback for P2:** revert tooling/docs. The live store, artifact wire format,
timers, credentials, and authority boundaries are unchanged. The index is
evidence navigation, never an alternative source of operational truth.

## P3 — Disposable rehearsal of the existing operations

### P3.1 — Close orchestration gaps only where evidence is missing

**Entry:** P2 contract exists and the existing operations/CLI tests are mapped
to each scenario. Do not rewrite tests already proving the behavior.

**Proposed files:** `scripts/rehearse_share_operations.py` if an orchestration
gap remains; corresponding focused tests; existing `tests/test_share_ops_cli.py`,
`tests/test_share_operations*.py` and `ops/share/README.md` as needed.

Use a unique task-owned temporary root, synthetic artifacts and keys, explicit
paths and fixture transports. Exercise the real public Python/CLI boundaries
where possible. No sudo, service installation, provider invocation, real
notifier, home config discovery, or existing live store. Distinguish a fake
restic transport from a local subprocess rehearsal in every receipt.

Split the scenario matrix into bounded packets:

- **Lifecycle:** create → consistent backup → revoke/expiry → stale backup
  restore → denied retired capability; preserve original terminal timestamps.
- **Refusal/recovery:** absent/retargeted journal replica, repository mismatch,
  wrong recovery key, incomplete anchor acknowledgement, lock contention,
  interrupted promotion and rollback, malformed store, ownership refusal.
- **Alerts and retirement:** persist-before-notify, retry same event identity,
  duplicate suppression, seal preventing later create/writer cycle, refusal of
  unexpected backup inventory, and refusal of retirement before the deadline.

Do not bypass root/non-root permission checks to make a macOS rehearsal pass.
Use existing supported test seams, or mark the real ownership/systemd part
unverified for P4. Local directories never count as independent nodes.

**Acceptance:** bounded deterministic scenarios reproduce their documented
success/refusal; deliberate bad evidence fails closed; only owned temporary
state is cleaned up; interrupted cleanup leaves a named private path for
recovery. A fake clock may test logic, never elapsed real-world retention.

### P3.2 — Handoff with explicit limitations

Produce a private synthetic evidence index using P2 and a short aggregate
receipt in the run record. Record which gates have code/rehearsal coverage and
which still need independent operation. Repair only reproduced defects,
preserving production signatures and existing storage format unless a separate
review explicitly requires a migration.

**Rollback:** revert new harness/code changes. Failed restore tests never touch
the real active root. No local success advances P4 or connects delivery.

## P4 — Real independent operational acceptance

**Reserved decision:** the owner/operator must identify the intended
application host, independently controlled backup and second journal target,
notification channel, key custodian, complete-copy inventory owner, media
erasure procedure, and specific authorized drill environment. Infrastructure
cost, credentials, host access and destructive authority are not inferred from
this plan or from CAPO's repository mutation authority.

Until those inputs exist, prepare only the runbook and exact command review.
Do not provision services or run destructive commands. If blocked, a scheduled
run may continue a ready P1 repair or separately authorized maintenance.

Once authorized, split work by evidence, not by optimistic calendar deadlines:

1. **Topology and authority:** run role-local attestations on the intended
   hosts, securely compare them offline, authenticate the distinct repositories,
   prove writer/operator separation and writer destructive-operation denial.
   Use sacrificial drill data, never a production repository for denial probes.
2. **Schedulers and alerts:** observe actual hourly writer and daily operator
   runs, including a restart/missed-run scenario and required failure paths.
   Cause missing-lock failure only on the disposable deployment. For every
   monitored service/node, match the private spool event to actual channel
   acknowledgement; notifier exit alone is insufficient.
3. **Backup and restore:** demonstrate consistent snapshot and fully anchored
   journal ordering, full-data checks, and quarantine restoration with
   post-snapshot revocation AND expiry. Verify the restored capability stays
   unavailable, writer ownership/journal rehydration, rollback, and safe resume.
   Measure the runbook's one-hour RPO and two-hour RTO against declared start/
   end events; report measured results separately from targets.
4. **Deletion and retirement:** observe active-row unlink after its 24-hour
   eligibility plus actual sweep latency; daily seven-day prune; and the
   eight-day operational deletion deadline. Whole-key-store retirement needs
   the sealed empty active store, authenticated empty inventory, every replica,
   and eight days plus 48 hours after the last terminal event. Simulated time
   cannot satisfy this. Inventory staging, rollback/quarantine, caches,
   backups, replicas and recovery-key copies before erasure.
5. **Operator erasure and review:** an authorized operator executes the
   approved procedure on the disposable retiring store/media and produces the
   aggregate receipt. Guard authorization alone is not erasure. Keep actual
   copies/credentials/receipt transfer private; sanitize the public outcome.

**Acceptance:** all required receipts agree on candidate, topology, configuration
and observation interval; P2 completeness plus an independent operator review
find no missing copy or unsupported deadline. Repeat affected drills after
toolchain, topology, credential, retention or schema change.

**Failure containment:** keep public delivery disconnected; stop the affected
drill writer and preserve diagnosis evidence. Resume only via the runbook.
After retirement, never “roll back” by reactivating a sealed key-store or
restoring retired data. Use a new independently validated deployment epoch.

## P5 — Accountless delivery after the operational gate

**Entry:** P4 verified, owner-approved endpoint/deployment and handoff design,
and explicit approval to connect public delivery. The implementation contract
must resolve authentication/admission, abuse/resource bounds, ambiguous upload
outcomes, deletion-capability custody/recovery, and lifecycle invalidation
before any route exists. Do not add an unauthenticated public upload endpoint
as an incidental implementation detail.

### P5.1 — Review the delivery contract

**Existing seams:** `codemble/share/preview.py`, `delivery.py`,
`persistent_storage.py`, `http_delivery.py`, `codemble/server/`,
`web/src/sharePreviewRun.js` and `web/src/SharePreviewDialog.jsx`
(confirm filenames at execution). Reuse the canonical artifact interpreter,
preview binding and capability lifecycle.

Specify the exact confirmed bytes/digest/expiry sent, explicit endpoint policy,
timeouts/body limits, no redirects to arbitrary hosts, TLS/Host validation,
closed response schema and independent view/delete capabilities. The user sees
the full disclosure and exact expiry before each upload. Labels and
understanding remain separate opt-ins, default off.

Resolve lost-response semantics before coding: an upload that succeeded
remotely but lost its response must not silently create another live share or
lose all deletion authority. Choose and review one bounded recovery/idempotency
design without accounts, plaintext bearer persistence, or capability reuse.
If it requires new stored security metadata, amend P2/P4 inventories and
retention/restore tests and rerun affected operational gates before activation.

### P5.2 — Implement the bounded bridge

Keep the transport behind one narrow owner, not spread across React callbacks.
The local server accepts only same-origin loopback requests and the exact
active preview confirmation. A changed candidate/project, revoked confirmation,
expired artifact, cancelled attempt, stale response or repeated click cannot
upload new bytes or commit capabilities to another project.

Implement the reviewed capability-custody choice. Offer deliberate copy/save
actions with truthful failure states and no implied account recovery. Never
log/store capabilities in recents, progress, analytics, URLs other than the
intended view link, browser persistence, or diagnostics. Do not alter the inert
GET/static-viewer contract merely to make the bridge easier.

### P5.3 — Verify the real handoff and off switch

**Tests:** exact-byte transport, all opt-in combinations, stale preview/project,
double-submit, timeout/lost response/retry, expired token, revocation and retry,
adversarial returned strings, rejected redirect, copy/save failure, narrow
layout, keyboard/focus/Escape, reduced motion, and capability absence from
logs/proxy/crash traces. Validate against a designated synthetic canary in the
approved deployment only after activation authority is explicit.

Test the rollback itself: disable creation at both client and service admission,
prove new creation is refused, and prove an existing synthetic canary remains
viewable/revocable and continues through expiry and scheduled sweeping.

Run native Safari acceptance through its plugin and maintained Chromium/WebKit
gates against the exact bundled artifact. Engine success does not claim native
Safari, VoiceOver or physical-device validation. Update product/docs copy in
the same candidate, with claims tied to the actual delivered behavior.

**Rollback:** disable creation at both client and service admission; retain
view/expiry/revocation, sweeping, alerts and deletion obligations for already
created shares. Do not delete the service or keys while active shares remain.
An emergency stop of view traffic does not excuse retirement obligations.

## P6 — Release only a complete, useful candidate

Use [the existing checklist](../releases/checklist.md), not a new parallel
publisher. No release is justified by this planning document, an evidence
schema alone, elapsed time, or commit count.

Preparation may proceed, but tagging, GitHub release creation, PyPI publication
and stable promotion require explicit owner authorization covering the candidate/
version or verified standing authorization that expressly covers it. The saved
CAPO prompt supplies standing release authority subject to its gates; re-read
it for the invoking run, preserve repository restrictions and HOLD on conflict.
Historical v0.23.0/v0.24.0 approvals alone do not authorize future publication.

1. Describe delivered user value, exact scope and the applicable publication
   authority. Public sharing requires P4/P5; a useful local learner repair can
   remain a disconnected-foundation release when explicitly covered by the
   invoking run's authority, including CAPO's verified standing authorization.
2. Reconcile versions, changelog, current versus stable screenshots, docs,
   installation instructions and release manifest. Rebuild `web_dist` for
   frontend changes and recapture product evidence when behavior changed.
3. Run full required CI/local tests, package and browser gates, and native
   target acceptance where applicable. Refresh Graphify and verify a scoped
   query before release build/tag/publish. Failure is HOLD.
4. Seal the exact source/artifacts and run two full release council rounds.
   Preserve immutable published artifacts and historical digests.
5. Follow the repository's candidate-PR/tag-first sequence: exact candidate
   hosted CI, reviewed local-main tag, trusted publishing, outside-in bytes/
   checksums, then that same commit to origin/main. Never publish future stable
   claims on default-branch README before registry verification.
6. Verify fresh GitHub/PyPI bytes against manifest and SHA256SUMS, cold install,
   main CI, Pages deployment and actual public surface. Report source merged,
   package published and site deployed as separate outcomes.

**Rollback:** preserve tags/artifacts, stop promotion on failed evidence, and
prepare a separately reviewed corrective release. A withdrawn or failed
candidate never becomes stable by editing the status prose.

## Verification matrix

Commands below exist at the planning baseline; re-read current manifests before
execution. Use a disposable environment tied to the candidate; do not repoint
another session's editable installation. Provider configuration stays absent
from tests and synthetic app runs.

| Change | Minimum focused verification | Broader gate before integration/release |
| --- | --- | --- |
| Intake/docs | Link/command/source consistency; form parse; isolated rehearsal when changed | Relevant docs checks; public-site gate only if public docs change |
| Operations evidence tooling | New negative/positive fixtures and existing share operations/identity/CLI tests | `pytest`, `ruff check .`; privacy/diff review |
| Store/delivery/operations behavior | Relevant `tests/test_share_*.py`, fault injection, exact artifact lifecycle | Full Python suite; `web` share-delivery gate when HTTP behavior changes |
| Learner UI/handoff | `cd web && npm run check`; maintained userflows and relevant focus/Escape/reach checks | Rebuilt committed SPA; affected Chromium/WebKit matrices; native Safari acceptance |
| Parser/layout/scale, if an approved reproduced defect requires it | Exact fixtures, `python scripts/audit_parser_evidence.py` | Full suite, complete 5k cross-engine gate; no cap promotion by inference |
| Public docs | `cd docs-site && npm run check && npm run build` | Preview plus `CODEMBLE_SITE_URL=<preview>/Codemble npm run check:site` from `web` before push |
| Release | Existing release checklist, reproducible package/manifest checks | Hosted exact candidate; outside-in downloads, cold install, actual site |

`npm run check:userflows`, `check:share-delivery`, and `check:large-project`
live in `web`. Some gates own disposable servers, while `check:space`,
`check:escape`, and `check:text` require `CODEMBLE_URL`; inspect the scripts
instead of assuming they all launch a server. Never point state-changing
rehearsals at the user's active Codemble instance.

## Maintenance interruptions

Urgent verified security/regression work may preempt the queue under CAPO's
priority rules. Reuse existing dependency PRs.

- **Hatchling #50:** verify wheel/sdist reproducibility and inclusion from a
  clean candidate. A build-tool change may alter bytes even with unchanged
  package version. Preserve the immutable v0.24.0 manifest and assets; do not
  reseal them to match a new toolchain. If current release checks couple the
  new toolchain to old manifest digests, HOLD integration and prepare a reviewed
  future-release transition rather than weaken the check.
- **Starlight #51:** the pinned-stack/design rules require a recorded owner
  decision before a stack-version change. Prepare compatibility evidence:
  sidebar/search, dark/light themes, fonts/tokens, responsive widths, keyboard,
  production Pagefind, build and actual Safari surface. Do not merge simply
  because Dependabot's CI is green.

Do not independently change either PR during this planning task.

## Scheduled handoff

The existing weekly CAPO heartbeat should read this file when Codemble is
selected, preserve its global priority/two-repository limit, reconcile completed
packets and active claims, and implement the first ready authorized packet.
Do not add another schedule or change cadence, enabled state, model, or other
repositories' routing. Daily Elf/Mobster can use this same queue when separately
configured; this file is not proof that they read it.

The saved prompt should require the plan and implementation councils, exact
verification receipts, conservative integration, the explicit P4/P5 authority
stops, and an exact next action. Preserve quiet behavior for unchanged or
non-actionable state; report meaningful progress, completion, failure or an
owner decision. No scheduled run may interpret the council's approval as
permission to send messages, provision infrastructure, erase media or publish
an otherwise gated release.

## Run record

Append one concise record per meaningful run; update packet statuses above only
when supported. Keep raw logs, real operational receipts and council transcripts
private. The review record contains the public aggregate council outcome.

| Date | Packet | Base and candidate | Result and evidence | Next action |
| --- | --- | --- | --- | --- |
| 2026-10-20 | Planning | `de0debe`; candidate is the commit introducing this queue | [Two-round council completed](2026-10-20-scheduled-phases-review.md); 14 focused operations/alert tests passed; weekly CAPO routing saved and reread with settings and existing routes preserved; no product implementation | P1.1a intake correction, then P1.1b rehearsal; P2 may proceed if P1.1b has an unchanged external HOLD |

Future record fields: run/claim owner; branch/worktree/PR; starting SHA; plan
digest; council outcomes; test command exits and private receipt references;
candidate/integrated SHA; CI status; retained blockers; next packet. A passing
test on the pre-change base cannot close a changed candidate.
