# Codemble share operations

This is the selected zero-license-cost deployment shape for M20. It uses one
user-owned application host, one independently controlled backup machine or NAS,
and a second independently controlled append-only journal target such as another
owned machine or recovery NAS. It does not require a paid cloud account.
Hardware, storage media, electricity, DNS, and network access can still cost
money.

The software stack is entirely free and open source:

| Project | Role | License |
| --- | --- | --- |
| [Caddy](https://github.com/caddyserver/caddy) | Public TLS termination | Apache-2.0 |
| [restic](https://github.com/restic/restic) | Encrypted snapshots, verification, restore, and prune | BSD-2-Clause |
| [rest-server](https://github.com/restic/rest-server) | Append-only writer endpoint on the backup machine | BSD-2-Clause |

Codemble uses Python's SQLite online-backup interface for one consistent
encrypted database snapshot. It does not use Litestream. The target is a
one-hour RPO, two-hour RTO, seven days of retained snapshots, hourly active
sweeping, and daily full-data verification plus prune.

## Authority layout

The application service account receives only the writer configuration and its private
files. That role may append encrypted database snapshots to the primary TLS
endpoint and must anchor each Retirement Journal entry to both configured,
distinct TLS repositories before the journal high-water advances. Every
`rest-server` is started with `--append-only`, so the writer cannot prune a
repository. The normal writer interface has no restore or forget method.

The root-only operator runs on the application host with the writer's
`codemble-share` group so restore promotion, retirement sealing, and the writer
cycle share the real `active_root`, `journal_root`, filesystem, and stable
parent lock. It reaches the backup machine's
exact private repository through a root-only POSIX mount at
`/mnt/codemble-restic/codemble-writer/codemble`; the backup machine never receives
the operator configuration and the operator never uses the public REST endpoint.
It alone runs full-data checks, the seven-day prune, quarantine restore, and
explicit snapshot removal during final key-store retirement. The separately
held `recovery_key_file` is mounted only for attestation, restore, sealing, and
retirement commands and must contain the same 32-byte storage-encryption key as
the active store. A different key cannot authenticate or restore the database.

The writer service account cannot read the root-only operator configuration or
its repository credential. Each role
runs `writer-attest` or `operator-attest` locally after authenticating the live
restic repository ID. The resulting canonical JSON contains only repository
IDs and domain-separated proofs derived from credentials that must be generated
with high entropy. Treat these credential-derived receipts as sensitive: move
them over an authenticated secure channel, compare them only on an offline review
workstation, and destroy the review copies afterward. `validate-deployment`
rejects a wrong backup repository, retargeted journal anchor,
mismatched recovery key, or shared writer/operator authority without
co-locating either role's credentials.

## Provisioning checklist

1. Build or download reviewed Caddy, restic, and rest-server releases. Put restic
   and rest-server at the absolute paths used by the TOML and service files, and
   provision Caddy through the operator's own service manager. Record and
   independently verify each SHA-256 digest. Codemble enforces the restic digest
   in both TOML files, and the included rest-server unit fixes its absolute
   executable path. The repository supplies only `Caddyfile.example` for Caddy;
   it does not manage or pin a Caddy executable path.
2. Create dedicated non-login accounts for the application writer and backup
   receiver; keep the local backup operator at UID `root` but give its systemd
   unit the writer's `codemble-share` primary group. Install
   `codemble-share-tmpfiles.conf` as `/etc/tmpfiles.d/codemble-share.conf` and
   run `systemd-tmpfiles --create /etc/tmpfiles.d/codemble-share.conf` before
   enabling either timer. It provisions the stable application-host parent as
   `0750 root:codemble-share`, the replaceable `active`, `retirement-journal`,
   and `backup-staging` stores as `0700 codemble-share:codemble-share`, and the pre-created
   `.active.share-operations.lock` as `0660 root:codemble-share`. The writer can
   open and lock the file but cannot unlink, rename, or replace its root-owned
   pathname; both services refuse to start without that lock.
   Restrict every credential, key, password, cache, database, journal, and
   repository directory/file to its service owner (`0700`/`0600`).
3. On the backup and recovery machines, initialize distinct restic repositories,
   add separate writer and local-operator keys and passwords to each, create
   distinct writer htpasswd entries for every repository, and make the first URL
   path segment equal that entry's username as required by `--private-repos`,
   install `codemble-rest-server.service`, and put Caddy in front of each
   loopback listener. Do not expose a non-append-only rest-server listener.
4. On the application host, fill `share-writer.toml`, install the writer service
   and timer, run one foreground cycle, and confirm that the closed receipt names
   a snapshot without printing capabilities, artifact bytes, paths, or passwords.
5. On the application host, mount the backup machine's private repository
   root-only at `/mnt/codemble-restic`, install the root-only operator config,
   and set its schema-2 `writer_uid` and `writer_gid` to the non-zero outputs of
   `id -u codemble-share` and `id -g codemble-share`. Restore fails closed if
   either identity is root or if the verified `0700`/`0600` ownership handoff
   cannot be applied to the restored active store and rehydrated journal. Then
   run `codemble share-ops writer-attest --config
   /etc/codemble/share-writer.toml > writer-attestation.json`. From the same host
   but as the root-only operator run `codemble share-ops operator-attest --config
   /etc/codemble/share-operator.toml > operator-attestation.json`. Transfer only
   those two credential-derived receipts securely to the offline review workstation and run `codemble
   share-ops validate-deployment --writer-attestation writer-attestation.json
   --operator-attestation operator-attestation.json`.
6. Keep one private `share-journal-operator.toml` on each independent journal
   node. It uses that node's exact local repository path and a separate restic
   operator key; it receives no REST credential. Confirm one terminal test event
   receives a receipt whose replica name, repository ID, snapshot ID, and entry
   digest all match that node. A missing receipt, changed repository ID, gapped
   chain, fork, or disagreement blocks high-water. Never reuse a repository
   password or REST credential across roles or repositories.
7. On every application, backup, and recovery node, install
   `codemble-share-alert@.service` and
   `codemble-share-alert-tmpfiles.conf`, then provision a private
   `/etc/codemble/share-alert.toml` from the example. The configured notifier
   must be an absolute, operator-owned executable whose SHA-256 digest matches
   the config. It reads one canonical JSON event from stdin and must return zero
   only after the operator's chosen notification channel has durably accepted
   the event. The event contains only a random alert ID, UTC time, the closed
   `service-failure` kind, and one of the three monitored unit names. The
   notifier must deduplicate retries by alert ID and must not add capabilities,
   request targets, repository credentials, or artifact bytes to its output.

## Failure alert handoff

The writer, operator, and append-only receiver units each trigger
`codemble-share-alert@%n.service` on failure. The relay writes the event to the
root-owned private spool before invoking the pinned local notifier. A failed or
timed-out notifier leaves that exact event pending; systemd retries every five
minutes with the same alert ID. Success moves the immutable event into the
delivered directory, allowing the next failure of that unit to receive a fresh
identity. This is at-least-once delivery: the notifier must use the alert ID as
its deduplication key because a process can stop after the external handoff and
before the local success rename.

Before enabling the operational timers, start one alert instance deliberately
on every node and verify both the external notification and the matching
delivered event. Then cause one safe foreground failure for each monitored unit
and confirm `OnFailure` reaches the same channel. A unit file, local spool, or
green test is not alert evidence; retain a token-free operator receipt naming
the unit, alert ID, channel acknowledgement time, and result.

The examples use systemd. Equivalent launchd or NAS scheduling is acceptable
only when it preserves the exact commands, service identities, hourly/daily
cadence, private modes, append-only writer endpoint, and failure alerting.

## Recovery and anti-resurrection drill

Run this against the real backup machine before any public release, and repeat
it after a toolchain, topology, credential, retention, or schema change:

1. Stop delivery and the hourly writer. Record the last successful snapshot and
   the authenticated repository IDs and journal heads from every replica.
2. On each independent journal node, run the local repository operator with
   `codemble share-ops
   operator-materialize-journal --config /etc/codemble/share-journal-operator.toml
   --destination /srv/codemble-materialized-journal --quarantine
   /srv/codemble-journal-quarantine`. Transfer each token-free materialized
   result into the exact application-host path and repository ID declared by the
   root-only operator's `[journal_replicas.*]` binding.
3. On the application host, mount the private backup repository and recovery-key
   media, then run a restic full-data check. Use `codemble share-ops
   operator-restore` with the exact snapshot, a new private local quarantine
   directory, and an explicit local rollback path when the configured active
   destination exists. This is the production restore interface; it performs
   the mounted-repository restore and guarded local promotion together. It also
   atomically rehydrates the writer's complete local journal from the agreeing
   name-to-repository-bound replicas, recursively verifies its configured
   writer UID/GID and private modes, and performs the same ownership handoff on
   the restored store before promotion; a fresh host cannot resume with an empty
   or unrelated chain.
4. The restore authenticates the database, backup-repository ID, manifest, and
   every repository-bound anchor receipt; requires identical complete chains;
   replays every post-snapshot revocation and expiry; purges; revalidates; and refuses
   promotion without an explicit rollback path for an existing destination.
5. Exercise a capability that was retired after the restored snapshot. It must
   remain unavailable. Record the restore duration, exact snapshot identity,
   manifest digest, journal head, replica inventory, full-data-check receipt,
   rollback path, and result without recording raw capabilities.
6. Re-enable delivery only after the atomic promotion and the no-resurrection
   check both pass. Investigate any missing receipt instead of retrying a
   destructive step blindly.

An **actual independent-node restore drill** is release evidence. Unit tests,
loopback rest-server, two directories on one disk, a successful backup command,
or green CI are not substitutes.

## Deletion and finite security-metadata retirement

Each revoke or expiry commits a token-free terminal event and anchors its
create-only chained entry before an eligible share row can be unlinked. Restore
binds a database snapshot to the journal high-water and replays later events.
Daily operator maintenance retains snapshots for seven days and performs a
full-data check before and after prune. Together with the hourly sweep, the
operational deletion deadline is eight days.

Stop delivery and the hourly writer on the application host first. Mount the
private backup repository and recovery-key media there. Obtain the exact live snapshot IDs from `codemble share-ops
operator-list-backups --config /etc/codemble/share-operator.toml`, then run
`codemble share-ops operator-retire-backups
--config /etc/codemble/share-operator.toml --snapshot-id ID` once for every ID
in that closed inventory. When the authenticated inventory is already empty, use
`--confirm-empty-inventory` instead of any `--snapshot-id`; this explicit path
still installs the required durable seal. This command refuses a missing live
database instead of creating a shadow store, acquires the same host-local operation
lock as the hourly writer, atomically installs a durable retirement seal before
deletion, refuses an inventory mismatch, removes only the explicit IDs, runs a
full-data check, and proves the authenticated repository empty. The seal makes
every later share create and hourly backup fail closed.

`codemble share-ops operator-authorize-retirement` then queries the operator's
live authenticated repository inventory rather than accepting an asserted
empty list.
`SecurityMetadataRetirementGuard` authorizes whole-key-store retirement only
when the sealed authenticated active store has no rows, every named journal
replica is present and bound to its immutable repository ID, the operator's
matching share-backup inventory is empty, and at least eight days plus the
48-hour safety margin have elapsed after the last terminal event. Its receipt
binds the seal epoch, repository ID, empty-inventory digest, and journal head.
The authorization is not key deletion by itself. The operator must
then destroy the exact active storage key, encrypted offline recovery key,
detached-guard database, and every inventoried journal replica under the host's
approved media-erasure procedure, and retain only a token-free aggregate receipt.

Do not check M20 complete or publish a release until the real service timers,
alerts, append-only endpoint, daily prune, complete-copy inventory, operational
deletion, key retirement, and independent-node restore drill have all been
observed on the intended independent deployment.
