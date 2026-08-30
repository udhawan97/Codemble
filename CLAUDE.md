# Codemble — agent brief & operating guide

Python 3.11 + FastAPI backend, Vite + React + `3d-force-graph` galaxy frontend.
A **learning game**, not a visualization tool and not a repo-tour generator:
*Codemble turns the code AI wrote for you into a galaxy you light up by
understanding it.*

This file is both the product spec and the agent's operating rules. Sections
marked **[AGENT-MAINTAINED]** are updated by the agent as work completes;
everything else changes only when the human owner (UD) approves via the
Decision Log.

## Commands

```bash
pip install -e ".[dev]"        # setup (venv recommended)
pytest                          # tests — CI gate
ruff check .                    # lint  — CI gate
codemble ./some-project         # run the CLI against a target project
codemble --version

cd docs-site && npm install
npm run dev                     # docs site at localhost:4321
npm run check                   # astro check — CI gate
npm run build                   # what the Pages workflow runs
```

## Layout

| Path | What |
| --- | --- |
| `codemble/adapters/` | LanguageAdapter seam. Nine languages: `python_ast.py` (stdlib `ast`), plus `typescript_tree_sitter.py`, `go_tree_sitter.py`, `java_tree_sitter.py`, `rust_tree_sitter.py`, `csharp_tree_sitter.py`, `ruby_tree_sitter.py`, and `php_tree_sitter.py` (tree-sitter). The registry is one tuple in `project.py` |
| `codemble/graph/` | Language-tagged graph + render-ready metadata (the frontend is a pure consumer) |
| `codemble/lens/` | Language lens: parser-detected idiom annotations → teachable notes |
| `codemble/checks/` | Active checks generated FROM the graph; answers never come from the LLM |
| `codemble/llm/` | Anthropic + OpenAI providers, BYO key, disk cache; narration only |
| `codemble/server/` | FastAPI: serves SPA + graph/checks JSON API |
| `codemble/progress/` | Local persistence: illumination + star chart (`~/.codemble/`) |
| `codemble/share/` | Raw-source-free artifacts, exact local preview, least-authority capabilities, and standalone token-redacted HTTPS delivery |
| `web/` | Galaxy renderer source (Vite + React + 3d-force-graph) |
| `codemble/web_dist/` | Versioned production SPA bundled in the Python wheel |
| `tests/` | Pytest suite |
| `docs/` | Internal: `adr/`, `plans/`, `research/` |
| `docs-site/` | Public site (Astro + Starlight → GitHub Pages) |

## Session protocol — read first, every session

**"What should we work on today?"**
1. Read **Current State** below; find the current milestone and next unchecked task.
2. Spot-check the repo matches the checkboxes (verify the last checked item runs).
3. Propose the **smallest next task** with a brief plan (files, verification).
4. On completion: check the box, update Current State (date + one-line note),
   append decisions to the Decision Log.

**"Plan the future" / "what's next?"** — answer from **Roadmap** (NOW → NEXT →
LATER). Do not invent scope; proposed changes enter the plan only with human
approval, recorded in the Decision Log.

**Milestone transitions** — a milestone advances only when its acceptance
criteria actually pass. Phase promotions (NOW→ NEXT items moving up) are
human-approved only; never self-promote.

**Standing rules**
- Never build **Non-Goals**. If a request conflicts, say so and point there.
- Ambiguity → ask the human; don't silently assume or expand scope.
- Small diffs; the project runs end-to-end after every session.
- Parser/graph/checks/persistence logic lands **with unit tests**; UI is
  verified by running it. A task isn't done until this file reflects it.
- The **Correctness Contract** outranks every feature request, including from
  the human — flag conflicts rather than quietly violating it.
- Anti-drift test for every feature: *"does this help a learner understand
  their code, or just decorate?"* Decoration waits.

## Product spec (locked)

- **Target user:** early/intermediate coder who built a project with Claude
  Code/Codex, doesn't fully understand it, can install a CLI, has a Claude or
  OpenAI key.
- **Local-first:** `codemble ./my-project` parses a local folder (no GitHub
  push needed) and serves the galaxy at localhost.
- **Semantic zoom, three levels, no free flight:** first run chooses free
  exploration or the bounded First Flight, plus Easy or Expert explanation.
  1) **Galaxy** — modules = star systems, imports = routes, entrypoint = Home;
  camera on rails. 2)
  **System** — functions/classes as planets in deterministic orbits, call
  edges. 3) **Study** — one parser-owned journey from Home to the selected
  feature, beginning with an Easy/Expert landing brief, then real source,
  grounded explanation, language lens, and checks; scene dims behind it.
  Scripted fly-to transitions.
- **Illumination is the game:** nodes start dim; passing a region's checks
  lights them permanently. **A region = one star system = one module** — the
  unit of checks, lighting, and invalidation. Star chart tracks language
  concepts. No other meta-progression.
- **Persistence:** local JSON in `~/.codemble/`, keyed by project path + file
  hashes; a changed file re-dims only its region.
- **Polyglot (from Phase 1):** nodes are language-tagged; users filter/focus
  the galaxy by language, each language with its own idiom lens. Nine ship
  today: Python, JavaScript, TypeScript, Go, Java, Rust, C#, Ruby and PHP.

## Architecture rules

1. **LanguageAdapter seam:** every language implements `discover(path)`,
   `parse(path) -> Graph`, `parse_files(root, files) -> Graph`, and
   `concepts(node) -> [ConceptAnnotation]`; adapters also emit closed-enum
   `RoleEvidence` for app entries, route handlers, UI renderers, and tests.
   Python first via stdlib `ast`; all
   later languages via tree-sitter. Nothing above the seam hardcodes a language.
   The JS/TS adapter reuses one internal syntax-evidence index across entrypoint,
   call, binding, and concept passes without widening this public seam.
2. **The graph is render-ready:** graph layer computes language, LOC,
   centrality, entrypoint rank, region id, understood-state, and one bounded
   mode-neutral learning journey over certain imports/calls. `LearnerSession`
   owns session transitions and local HTTP sequencing behind one external-store
   interface. React is a pure renderer of those truths — **no layout or game
   logic in React/the renderer.** This keeps the Phase-3 share-link viewer and
   any future renderer cheap.
3. **LLM narrates, never decides:** providers Anthropic + OpenAI, BYO key (env
   or `~/.codemble/config`), calls go direct from the user's machine, disk
   cache keyed by node + file hash. Input: real source + neighbors + concept
   annotations.
4. **Pinned stack:** Python 3.11+, FastAPI, Vite + React, `3d-force-graph`.
   Changes require a human-approved Decision Log entry.

## Correctness Contract — HARD CONSTRAINT

The audience cannot detect when the tool is wrong. Therefore:
1. **Structure is never invented** — nodes, edges, entrypoints, idiom locations
   come only from the parser.
2. **Explanations are grounded** — real identifiers only; say *"unclear from
   the code"* rather than guess.
3. **Lens claims attach only to parser-detected constructs.**
4. **Every explanation links to a real `file:line`.**
5. **Application and test roles require parser-owned rule and line evidence.**
   Framework roles also require matching import/factory/binding provenance;
   familiar method or annotation names alone are not evidence.
6. **A journey completes only over directed, certain imports and calls;**
   possible evidence remains beyond a visible proof break.
7. **Check answers come from the graph, never the model.**
8. **Approximate call edges are labeled "possible call."**

## Repo, docs & website ops

- **Docs site:** Astro 7 + Starlight 0.41 in `docs-site/`, deployed by
  `.github/workflows/pages.yml` to `https://udhawan97.github.io/Codemble/`.
  `base: "/Codemble"` is case-sensitive and must equal the repo name.
- **Sidebar is hand-authored** in `astro.config.mjs` — every new docs page
  needs a manual `{label, slug}` entry or it won't appear.
- **Design system:** `docs-site/design.md` is locked; `src/styles/tokens.css`
  is the value source of truth and **must load before** `custom.css`. Genre is
  the Formal Edo evidence workbench. Two accents, one job each: kohaku amber =
  understanding/progress, ruri lapis = interaction — kohaku may never mark a
  navigation state. WCAG 4.5:1 floor on both grounds.
- **Brand artwork is generated:** `npm run brand:build` in `docs-site/`
  rewrites the plate reserve, icons, README download banner, and social card
  from fixed inputs. Edit the script, never generated SVG/PNG output; commit
  both (the site never runs the generator during its build).
- **Product screenshots are reproducible:** `npm run capture:docs` in `web/`
  starts its own current-source server on a random loopback port and unique
  temporary `CODEMBLE_DATA_DIR`, strips provider configuration, exercises the
  real first-run UI and graph checks, then removes both server and data. It
  refuses an external capture URL.
- **Public release truth:** **v0.22.0 is the verified stable release.** Annotated
  tag `v0.22.0` (`a3a2c5d`) peels to exact release commit `407a8aa`. Candidate
  PR #42 CI run `32928613735`, trusted publish run `32929397290`, main CI run
  `32929522840`, and Pages run `32929522861` passed. Fresh GitHub and PyPI
  bytes plus `SHA256SUMS.txt` agree on wheel
  (`ae8af55bc415990970cb54095f4e2774278e2de26d983d61f9364fd5180f0b25`)
  and sdist (`0bdba3e4faafbdf121004c8301c3d95712cb8932f33e9e14e47050f0bd3a0e77`).
  `check:release:live` reconciled both registries and fresh downloaded bytes; a
  cold Python 3.12 install reported `codemble 0.22.0` and carried
  `index-C3498IDT.js` plus `index-ZndcOj-s.css`. Obscura rendered the deployed
  217-system Pages surface, and the maintained public-site gate passed 320,
  375, 414, 768, 1280, and 1440 px, 200% reflow, reduced motion, docs routes,
  images, and console checks. Native Safari directly passed the Galaxy-to-System
  semantic and keyboard/pointer journey; its automation capture omitted the
  WebGL layer, so visual rendering remains claimed only from the Chromium and
  WebKit acceptance suites.
  Issue #13's unaided-learner gate remains open. A later tag is not stable until
  it repeats all of that.
- **Digests are taken from the tree you are about to tag, never earlier.**
  `readme = "README.md"` embeds the README in the wheel's own METADATA, so a
  dist/ built before a README edit describes a wheel that no longer exists —
  which is exactly how v0.19.0's first publish attempt failed. The build itself
  was never at fault: rebuilding from the tagged tree reproduced CI's wheel
  byte-for-byte, which is the pinned hatchling and `SOURCE_DATE_EPOCH` working.
  Recording the digests cannot invalidate them, because the two files that
  carry them (`release.json`, the download guide) are both outside the wheel
  and `docs-site` is excluded from the sdist — proven by rebuilding after the
  edit and getting the same digests back.
- **Site search is Pagefind**, which only exists after `npm run build` — the
  field says so in `npm run dev` rather than failing silently.
- **Public browser proof is a pre-push gate:** build and preview `docs-site/`,
  then run `CODEMBLE_SITE_URL=<preview>/Codemble npm run check:site` from
  `web/`. It covers the landing at six widths, docs at mobile/desktop, keyboard
  inspection, themes, images, routes, and both clipboard-failure paths.
- **Docs cadence:** a milestone that changes user-facing behavior updates the
  relevant docs page(s) + sidebar in the same PR. CHANGELOG.md gets an entry
  per meaningful change (Keep a Changelog format).
- **Build in public:** weekly progress note; WIP galaxy shots are the content.
  README badges stay static until CI/releases exist, then switch to live
  shields (`github/v/release`, workflow status — FolioOrb pattern).
- **Community files:** Apache-2.0, Contributor Covenant 2.1, SECURITY.md
  (private advisories + `CODEMBLE SECURITY` email tag), issue forms, PR
  template with parser/LLM conditional checklists, Conventional Commits + DCO.

## Roadmap — NOW / NEXT / LATER

**NOW — the privacy boundary for read-only sharing.** UD promoted M20 on
2026-08-26. Its first slice defines the complete source-exclusion, provenance,
expiry, and deletion contract and compiles one canonical local artifact with
per-artifact keyed identities and source-ID-independent graph-owned placement
before any provider, upload route, or cloud authority exists. Its local
workbench now shows the exact artifact and binds explicit confirmation to that
in-memory candidate. A separate provider-neutral capability core now issues
independent view/delete authority, rejects capability reuse, irreversibly
tombstones observed expiry, and atomically revokes active bytes without adding
an upload route. A standalone provider-neutral application now proves HTTPS-only
static viewing, header-authorized revocation, hardened browser responses, and
token-redacted lifecycle/access logs without connecting preview to delivery or
choosing storage. Lifecycle telemetry is best-effort and non-authoritative so a
failed sink cannot strand an active share; monitored operational logging remains
part of the deployment gate. A disconnected encrypted SQLite adapter now accepts
an external key without writing an adjacent key file, authenticates database/key
identity, exact schema, retained guard history, and record bodies, enforces
fail-closed POSIX permissions, atomically removes active bytes, sweeps unobserved
expiry, and provides a finite terminal share-unlink mechanism without choosing a
remote provider. Detached reuse/nonce guards remain until key-store retirement.
The source now also contains the selected free/open-source operations reference:
an append-only restic writer behind Caddy/rest-server, a separately held local
operator, repository-bound replicated Retirement Journal, role-local deployment
attestations, consistent backup manifest, independent journal materialization,
quarantined Restore Guard with writer-journal rehydration, durable retirement
seal, explicit snapshot retirement, and finite key-store-retirement
authorization. These mechanisms are not connected to public delivery, and the
required independent-node restore/deletion evidence has not been produced. Phase 1 tester
evidence continues in parallel — the v0.1.0 Python learner-acceptance issue stays
open, and technical completion does not claim those external runs passed.

**NEXT — accountless share delivery after the privacy gates.** The parser and
scale slate is complete through v0.22.0: nine languages, bounded parser
evidence, and a complete canvas Map that passes the 5,000-module backend,
Chromium, and WebKit gate. The exact local preview and explicit exposure
confirmation now exist. Independent view/delete capabilities, irreversible local
expiry, standalone token-safe HTTP/browser delivery, and encrypted authenticated
local persistence with a finite terminal-unlink mechanism are now complete. The
free backup, journal replay, restore, role-separation, and retirement machinery is
implemented and configured in source. M20 still needs public-delivery connection
and real independent-target evidence for scheduled sweeping, append-only authority,
full-data verification/prune, restore without resurrection, deletion deadlines,
complete-copy inventory, alerts, and approved key/media erasure.

The prior scale decisions remain recorded because the measurements are reusable:

**All three items previously listed here were measured, and two of them were
refused on the evidence.** Recorded because the measurements are reusable:

- **Framework entrypoints — done** (v0.13.0). Was real: a FastAPI service, a
  Flask app whose variable is not called `app`, a typer CLI and a click CLI
  all resolved Home to *nothing*.
- **Relative/namespace imports — nothing to fix.** Measured 500 Python import
  edges on this project: zero possible, zero project modules missed. Python
  import resolution is already complete.
- **LOD culling — not the constraint at the supported cap.** The galaxy draws
  *regions*, not nodes: 171 stars in the v0.15 self-parse, and at a real 1,000-module project
  1,000 stars with the route mesh thinned by reveal to 5 charted. It renders
  with no console error, and the existing guards (node resolution dropping
  above 900, reveal, the label budget) are aimed exactly here. **Honest limit:
  framerate itself was not measured** — the in-app browser reports
  `document.hidden`, which throttles `requestAnimationFrame`, so the evidence
  is structural rather than a frame count. The later 2026-08-14 complete-Map
  gate made the next constraint measurable: the backend and Chromium passed at
  5,000 modules, but WebKit could not stabilize the first-run Skip control
  within the 5 s interaction budget while 5,000 SVG boxes committed.

The canvas Map changes delivery only: every module remains represented,
searchable, keyboard reachable, and recoverable; logical LOD that hides modules
is still not acceptable. The ordinary cap is 5,000 after the schema-4 candidate
gate passed both engines.

**LATER — learning depth and launch.** Extra quest types: trace-a-request and
fix-the-failing-test. Polish, then the coordinated launch (Show HN / X;
lit-galaxy GIF as hero).

## Current State **[AGENT-MAINTAINED]**

**Current milestone: M20 private read-only share foundation** · Last updated:
2026-08-30 · Session note: the local privacy workbench still binds confirmation
to one exact raw-source-free artifact, and a separate provider-neutral capability
module issues independent 256-bit view/delete authority over only validated
canonical bytes. A standalone ASGI delivery module now admits only HTTPS and an
exact Host, normalizes view and unknown paths plus query strings and deletion headers before access
logging, serves a static context-encoded viewer with no-store/no-referrer/CSP and
no third-party/cookie/browser-persistence surface, and accepts deletion only through a
confirmed header-authorized POST. Closed lifecycle events contain only an internal
share ID, UTC time, operation, and outcome; sink failure cannot alter capability
state. A separate encrypted SQLite adapter persists the same storage interface
using an externally supplied key and strict local file permissions, without
writing an adjacent key file or claiming custody for that key; it is
not connected to preview or the standalone application. No upload, remote
provider, account, deployment, or cloud request exists. One trusted artifact
interpreter now supplies derived facts to preview, storage, and delivery, and one
Share Preview Run owns the learner-visible lifecycle and stale-response refusal.

**The local artifact, confirmation, capability-core, standalone browser-delivery,
encrypted persistence, and free backup/anti-resurrection source slices are
complete; public connection and operational release evidence remain gated.** The deep
`ShareArtifact.from_graph(graph, policy, created_at)` interface owns the closed
allowlist, keyed remapping plus graph-owned re-layout, opt-ins, RFC 8785 bytes, manifest payload
digest, source-safe coverage, and expiry validation. It fails closed when an
internal node, region, Home, or closed-schema fact cannot be represented. The
project-owned preview service retains only one candidate, and strict no-store
loopback routes plus the Formal Edo workbench expose and acknowledge it without
upload authority. `ShareDelivery.create/view/revoke` owns the capability lifecycle
behind a three-operation `ShareStoragePort`; its in-memory reference adapter and
an independent test adapter exercise create/read/revoke without coupling the
service to the reference adapter; the reference adapter owns the atomicity. The
`EncryptedSQLiteShareStorage` adapter keeps its 256-bit key outside the database,
binds the database to that key, and authenticates the complete record body with
AES-GCM. Its keyed history commitment also authenticates every retained nonce and
capability guard; exact-schema validation precedes any existing-store mutation.
Share-derived sensitive plaintext is limited to the internal share ID,
ciphertext length, nonces, and derived lookup/fingerprint guards. It durably refuses nonce and capability
reuse, fails closed outside POSIX, rechecks private modes on every use, and uses
immediate SQLite transactions plus secure deletion for record mutations. Revocation replaces active
ciphertext; its maintenance pass expires unobserved shares and removes the share
row plus serving-index linkage once the configured terminal-retention threshold
has elapsed after revocation or expiry. The default threshold is 24 hours; actual
removal includes sweep latency. Detached guards deliberately remain until key-store
retirement; fixed hourly/eight-day scheduling is configured in source, while its
observed deadline and finite operational deletion stay gated. The
standalone `create_share_delivery_app` interface owns HTTPS/Host admission,
bearer/unknown-target redaction, static rendering, security headers, and strict revocation
delivery behind the same core. The selected zero-license-cost operations
reference uses operator-managed Caddy configuration, pinned restic bytes, a fixed
absolute rest-server executable path, and separate append-only writer/local
operator credentials. Each terminal event is serialized
and must receive receipts binding replica, authenticated repository, snapshot,
and entry digest from two named, distinct append-only repositories before the
journal high-water advances. Role-local attestations prove the live repository
topology, matching storage/recovery key, and separate authority without
co-locating either configuration. Hourly `share-ops writer-cycle`
sweeps and stages one consistent encrypted database plus a manifest bound to the
fully anchored Retirement Journal high-water captured before the SQLite snapshot
and the exact name-to-repository replica inventory. One stable application-host
operation lock outside the replaceable active store uses a root-owned `0750`
parent, pre-provisioned writer-owned `0700` active/journal/staging stores, and a
pre-created `root:codemble-share` `0660` lock. The runtime opens the lock through
a trusted directory descriptor and verifies its ownership, link count, mode,
and inode before and after acquisition, so the non-root writer cannot unlink,
rename, or replace the lock while writer, restore, and retirement processes
exclude one another. The public writer cycle locks before opening or creating
the store and journal. Root restore verifies a recursive `0700`/`0600`
UID/GID handoff to the configured non-root writer before promotion. Daily
`operator-maintain` performs full-data checks around a fixed seven-day prune.
The separately held operator recovery file contains the same storage key while
authority secrets remain distinct. Production `operator-restore` and
`operator-authorize-retirement` commands use the guarded interfaces; separate
journal-node operators materialize their local repositories. Restore Guard
requires every named create-only journal replica and repository-bound receipt to agree, replays
post-backup terminal facts, revalidates, rehydrates the writer journal, and
promotes atomically with rollback. Explicit backup retirement first installs an
authenticated durable seal that closes every later create and writer cycle, then
deletes only the exact authenticated live snapshot inventory. Security Metadata
Retirement re-queries that repository and can be authorized only after a sealed
empty active store and empty backup inventory plus the eight-day deadline and
48-hour margin. The guard
does not erase media. The research contract and approved design still gate
preview-to-delivery connection and actual independent-target timers, alerts, authority
probes, restore-without-resurrection, deletion, complete-copy inventory, and
approved key/media-erasure evidence.

Previously (2026-08-25) · Session note: verified stable v0.22.0 keeps every
system colourful and legible in free Explore, turns the parser-owned module
anchor into the System Sun, names every structure world, gives each parsed
language a deterministic visual character, and exposes parser-owned neighbouring
imports without changing certainty, checks, progression, or the bounded camera.

**The M19 implementation loop and full release gate are complete.**
Explore no longer blacks out unrelated systems during hover or selection, and
unvisited systems retain their language atmosphere. Within a selected module,
the safe module anchor is a central language-coloured star; functions and
classes are named planets in parser-owned call placement that distinguishes
direct certain calls, call roots, and no-path placement; a nearby-systems console
lists inbound and outbound imports with split certainty and opens the selected
destination. Possible routes stay possible, reduced motion removes animation rather than content, and
amber remains exclusive to passed checks. The full local gate, fresh Graphify,
exactly two council rounds, reproducible artifacts, candidate PR CI, exact-tag
trusted publication, outside-in package proof, cold install, main CI, Pages,
native Safari semantics, and public responsive-site acceptance pass.

The 2026-08-26 post-release public-surface refresh preserves the Formal Edo
Workbench and current v0.22.0 product captures while tightening the first-time
route: public copy says explore rather than implying free-flight, stops route
claims where parser proof stops, explains the local-server/browser recovery
path, and lists Ruby/PHP extensions beside the other seven languages. The
standalone landing now carries one canonical URL and complete Open Graph /
Twitter metadata from the same title, description, social card, and image-alt
text. No package code, application behavior, release manifest, published wheel
or sdist bytes, or tag changed. The main push updates the default-branch README
and triggers the repository's existing Pages workflow; deployment success is a
separate post-push verification, not a package release. Because `README.md` is
embedded in package metadata, a wheel built from this source tree would carry
its refreshed project description; the tracked documentation test also changes
a source archive built from this tree. Neither would be byte-identical to the
published v0.22.0 artifacts.
The fresh schema-4 scale receipt also passes on v0.22.0 source: 5.691 s cold,
1.585 s no-change, 167,788,544-byte process RSS high-water, 1.743 s Chromium
usable and 2.387 s WebKit usable, with all 5,000 modules / 4,999 routes retained,
99 DOM elements per engine, and zero compact overflow.

Previously (2026-08-25) · Session note: verified stable v0.21.1 added a
deliberate free-explore or First Flight launch, Easy/Expert landing briefs,
seeded game-level space art, and conservative Ruby/PHP adapters without
changing evidence or progression.

**Two implementation loops and the full release gate are complete.** First
run now persists the selected explanation register before either opening the
complete Galaxy or starting the existing bounded First Flight. Landing on a
structure exposes its real kind/span and inbound/outbound graph connections in
Easy or Expert language. Every guided stop now offers an explicit parser-owned
landing and continues into the existing graph-derived checks without a second
quiz or progression system. Galaxy scenery adds a seeded spiral disc, dust/core,
layered star shells, nebula variants, reticle and route motion; System worlds
add deterministic terrain, mineral bands, atmosphere, tilt, and rotation. All
new scenery adds no unsupported fact, is reduced-motion aware, and is
recursive-disposal covered. Language tint mirrors parser truth; amber and its
starburst still mean passed checks and nothing else.

The immutable `v0.21.0` tag is retained as a blocked prerelease. Its trusted
workflow stopped before PyPI because a local `uv run --with build` created an
untracked `uv.lock` that entered only the local sdist; the clean CI sdist
correctly disagreed with the manifest. v0.21.1 explicitly excludes that
developer lockfile. Its replacement clean build, exact-tag publish, and
outside-in proof all agree.

Ruby and PHP now pass through the same adapter/finalization seam as the existing
languages, with syntax-backed concepts, conservative calls, safe partial-file
fallback, exact fixtures, and a ten-case semantic oracle. The pinned Rails
corpus (`1f0c247…`) parsed 3,452 Ruby files into 53,478 nodes with zero partial
files and 298,355 edges in 21.760 s; Laravel Framework (`9b21ce0…`) parsed
3,034 PHP files into 38,540 nodes with one partial file and 207,232 edges in
43.573 s. Immediate repeats were
deterministic. The released candidate passes 542 Python tests, Ruff, the full
frontend build/contracts, and all 48 Chromium/WebKit user-flow receipts. The
final 5,000-module gate reaches a usable app in 1.48 s in Chromium and 2.03 s in
WebKit after large Galaxy startup began yielding for 650 ms; Map takeover
cancels the pending WebGL construction.

Post-release re-verification found two bounded presentation defects in the
otherwise unchanged v0.21.1 source. Successful free exploration left focus on
`BODY` after its opener-less modal closed, and the font-settled 320×640 Study
landing put the complete connection-count disclosure at y=610–654 against a
panel ending at y=640. The current source now transfers focus once to the
layer-correct Galaxy frame after a successful free-only commit, while refused
saves retain dialog focus. Compact Study yields only card inset and local gaps;
the complete 44 px disclosure now clears the panel by at least 8 px. Its gate
uses Playwright's pinned Chromium and waits for self-hosted fonts after Study
mounts. Fresh Chromium/WebKit receipts, native Safari pointer and keyboard
launches, the full panel sweep, 29-state space budget, and 104 Escape assertions
pass. This is an unreleased source correction: v0.21.1 remains the stable public
release, and no release tag moved.

For the v0.21.1 release itself, native Safari acceptance was attempted but
ScreenCaptureKit could not start the capture; that release record names WebKit
only as engine evidence. Annotated tag object
`913d641` peels to release commit `9f52778`; replacement candidate PR CI
`32831499727`, trusted publish `32832515968`, main CI `32832683519`, and Pages
`32832683592` are green. Fresh GitHub/PyPI bytes and `SHA256SUMS.txt` agree on
wheel `ba515552…90212` and sdist `588c910f…613c0`; a cold Python 3.11 install
reports 0.21.1 and carries `index-Is2yGdJX.js` plus `index-DVgxDoNx.css`.
v0.21.1 is the stable public release. Issue #13 remains open.

Previously (2026-08-24) · Session note: verified stable v0.20.0 replaced
per-item Map SVG DOM with complete viewport canvas delivery and promoted the
ordinary supported-file cap after its full gate passed. Exact release commit
`436cbee`, annotated tag object `9abf14a`, candidate PR CI `32769180402`, trusted
publish `32770056876`, main CI `32770203502`, and Pages `32770203426` are green.

Previously (2026-08-21) · Session note: two compact user-flow repairs shipped
as verified stable v0.19.2 without changing parser, graph, checks, progress,
providers, or then-current release-scale truth.

**The v0.19.2 candidate closed two measured P2 gaps.** WebKit may leave focus on
`<body>` after a pointer activates Menu, so the disclosure's subtree handler
never received Escape; the existing window arbiter now owns that dismissal and
returns focus without retreating a level. At 320–405px widths, the sticky quiz
action covered the final answer on first paint; the compact checks surface now
uses the footer row below the instrument rail, keeping all four options clear
while the action stays visible. The disposable Chromium/WebKit gate covers the
pointer path and exact 320, 331, 332, 405, 406, and 414px boundary widths.
The first exact-main candidate exposed one additional engine boundary rather
than being waved through: Ubuntu WebKit ignored the question's
`scrollIntoView({behavior: "instant"})` during panel entry and left the final
answer below the action at 320px. The follow-up sets the panel's scroll position
directly, realigns after local fonts settle, and measures after the declared
420ms entrance. This preserves the rail and every full identifier and 44px
target; it does not compress, truncate, or hide quiz evidence to satisfy CI.
All nine public product frames were recaptured from the exact candidate with
disposable progress and provider configuration removed; the self-parse remains
199 systems and now contains 2,228 nodes and 14,219 edges.

**v0.19.2 completed the full outside-in gate.** The annotated tag peels to
`466c130`; exact-main CI, Pages, and all three trusted publish jobs are green.
Fresh GitHub downloads match the manifest and `SHA256SUMS.txt`, PyPI reports
the same bytes, and a cold Python 3.11 install includes the tagged SPA. Obscura
rendered live Pages with 27 intact images, zero horizontal overflow, and no
console errors. Issue #13 remains open and the normal cap remains 1,000, so
release proof does not advance M16 or claim unaided learner acceptance.

Previously (2026-08-21) · Session note: five bounded app-polish loops shipped
as verified stable v0.19.1 without changing parser, graph, checks, progress, or
release scale truth.

**v0.19.1 completed the exact release gate.** The annotated tag peels to
`198c0d7`; main CI, Pages, and all three trusted publish jobs are green. Fresh
GitHub downloads match the manifest and `SHA256SUMS.txt`, PyPI reports the same
bytes, and a cold Python 3.11 install includes the tagged SPA. Issue #13 remains
open and the normal cap remains 1,000, so release proof does not advance M16 or
claim unaided learner acceptance.

**The five loops close interaction ambiguity rather than add capability.** The
Map percentage control now names its reset action and current value; First
Flight's final stop has one completion action; local path and module search
inputs opt out of credential autofill and code-token spellchecking; native
controls inherit the dark instrument palette; and the compact Map column now
shows the same scroll-continuation cue as every other long app surface. Focus,
Escape, reduced-motion, uncertainty, and amber-understanding contracts remain
unchanged and executable.

**The public surface follows the same release ledger.** All nine product shots
were recaptured from the current worktree with disposable progress and no
provider configuration. README, landing, current guides, download routes, and
release manifest now agree on v0.19.1 and 199 represented systems; the stale
190-system landing caption and v0.18 journey caption were removed. Issue #13
still requires unaided human learner evidence, so M16 does not advance.

Previously (2026-08-21) · Session note: a bounded live-app polish pass repaired Study's
arrival and the narrowest supported learning loop without changing parser,
game, graph layout, palette, or Galaxy truth.

**Study now owns the focus handoff its trigger used to abandon.** Opening the
panel removes the button or graph control that launched it, which left keyboard
focus on `<body>` even though the new evidence surface was visible. Ordinary
arrivals now reset the panel and focus the selected module heading; the explicit
"Read the source" route scrolls to and focuses `Real source`, the exact section
it promised. Following an Impact or Connection row was verified separately:
the prior panel scroll is cleared and the new module heading owns focus. A
failed source request moves from the interim module heading to its visible
failure heading, while ordinary data readiness is not an arrival and may not
steal focus back from a control the learner has already chosen. Study retry is
separate from navigation, so a recovered explicit source request retains that
intent and lands on `Real source` rather than silently returning to panel top.
Ordinary Study and narration retry focus the persistent module heading before
their transient retry controls unmount.

**The 320px source loop gives the code back a visible row.** The two full
guidance actions missed fitting by 10px under Easy density, so they stacked into
two separate rows and made the persistent strip 185.8px tall — 29.0% of a
320×640 viewport. Only Study's local gap and button padding yield through the
measured 320-350px failure band;
the labels and meaning stay intact. The strip now measures 125.7px (19.6%), the
buttons share one row, `Real source` stays on one line while the coordinate
ellipsises, and document horizontal overflow remains zero.

**Acceptance:** the complete frontend contract/build passes; the disposable
Chromium/WebKit user-flow gate passes 16 journeys including the new focus and
compact-layout assertions; the space budget passes all 29 width/level rows;
the Escape sweep passes 104 assertions across four widths; and the panel-reach
sweep passes all nine study/check/chart measurements. Live Chromium inspection
at 320×640 confirmed the exact focus target and geometry. The milestone does
not advance and no release is implied: issue #13 still requires human tester
evidence.

Previously (2026-08-18) · Session note: three evidence-led user-flow loops against the served
build found two real gaps, both fixed and re-verified live, and released as
**v0.19.0** together with the previously unreleased M16 parser work.

**Home never resolved on this project, and the evidence was sitting in
`pyproject.toml` the whole time.** Five candidates tied at rank 0 — `codemble.cli`
plus four maintenance scripts, each carrying an ordinary `__main__` guard — so
`selected_entrypoint` was `None` and a first-run learner met a 34-candidate
picker in four scopes *before seeing the galaxy at all*. The manifest already
declared which module the installed command runs, which is strictly stronger
evidence than a `__main__` guard: the guard says a file *can* be run, the
manifest says this one *is* the program. `[project.scripts]` and
`[project.gui-scripts]` now order candidates ahead of every other signal.
Ranking only, and the three guardrails are what keep it inside the Correctness
Contract: the stored `entrypoint_rank` is untouched so the picker still shows
the parser's own number, a declared module the parser never saw contributes
nothing so no structure is invented, and a missing or malformed manifest is
ignored rather than failing the parse. It biases the **sort key**, not the
field, so the double finalization the normal path performs cannot compound it —
the lesson `finalize_graph`'s own history already taught. Measured in both
directions: `None` + 34 candidates before, `codemble.cli` with no question
asked after. The recaptured hero screenshot now shows a resolved Home.

**The guidance chip then contradicted the breadcrumb, and it is the v0.16.0 bug
wearing different clothes.** "Is a Home chosen?" was asked of the
*language-focused* projection. Home is written in one language, so focusing
another filtered it out of `graph.regions` entirely and the chip read "No Home
is chosen" two rows under a breadcrumb reading "Home codemble.cli". Same
root-cause shape as the Map defect that broke 5 of 7 languages: a whole-project
question answered from a filtered view. The fact now comes from the unfocused
graph, and a Home outside the current focus gets its own honest reason naming
the language. **The first version of that copy was wrong for a reason worth
recording**: written as a full explanatory sentence it measured 106px of
guidance strip against 62px, and that strip is already the tightest thing on a
320px screen — so it now reads in one clause like every sibling reason, which
costs nothing and says the same thing. The four distance reasons also moved out
of a five-deep nested ternary into one named helper; telling them apart is the
whole job, and collapsing any two tells the learner something untrue.

**The third loop found nothing, and that is recorded as-is.** It swept the
Expert register, the study panel, the impact widget, the v0.18 journey stepper
(Back disabled at step 1, Next disabled at step 5, Replay available — no dead
end), the module index and both recovery controls. Sixteen language×tab
combinations on the Map and eight register×focus combinations on the Galaxy all
drew correctly, and the non-Python Workflow empty states name their cause and
offer "Show all languages". Inflating something into a finding would have been
worse than reporting a clean sweep.

**Two measurement traps were avoided rather than fallen into.** A rapid
selector-sweep probe reported the galaxy canvas at 0×0 and an empty stage; a
clean-path screenshot rendered it perfectly, and the canvas measured 2880×1270
with a live WebGL context — the probe was reading a throttled, hidden pane
(`document.hidden === true`), the same trap this file already records twice. And
a 256px guidance chip at 320px under a Rust focus turned out to be driven by the
long fixture region ID printed twice, not by the new copy, which is 8 characters
longer than the baseline.

The three requested architecture loops were **not run**: `/improve-codebase-architecture`
is explicit-invocation-only and cannot be called on the agent's behalf. UD chose
to release the two verified user-flow fixes rather than wait.

532 pytest, Ruff clean, 21 frontend contract checks, reproducible bundle and
reproducible wheel/sdist matching the release manifest, space budget green at 28
width/level rows, 104 escape assertions across 4 widths, panel reach green, all
nine product screenshots recaptured from current source. The milestone does not
advance: issue #13 still requires human tester evidence.

Previously (2026-08-14) · Session note: one `ProjectActivation` now injects a long-lived
`ProjectParser` with a bounded, thread-safe, process-memory cache of source-free
per-file graph evidence; concept snippets are reconstructed transiently from
hash-verified current bytes. Exact root/path/content/dialect/version/config
keys, deterministic invalidation, and safe full-adapter fallback preserve
byte-exact Graph and Map results across no-change, edit, delete, rename,
partial recovery, dialect/version/config changes, fingerprint cancellation,
late pre-acceptance cancellation, and cross-root use. Prepared evidence becomes
visible only under the same acceptance lock as the live project. Finalization/layout scans
and Study/impact/journey queries now reuse immutable indexes only where exact
payload equivalence holds. A hand-authored seven-language plus mixed oracle
separately catches invented facts and omissions in bounded representative
scopes. The 5,000-module backend and
Chromium budgets passed, while WebKit failed the 5 s first-run interaction
budget, so `scale_cap` remains 1,000 and the next renderer must be a complete
canvas Map rather than hidden-module LOD. Project Mapping clears obsolete scale
guidance only after successful navigation; Finder arrival focus now waits for
the committed module context at large scale. Pinned Apache-2.0/MIT inspirations
are credited; no code/assets, runtime dependency, provider, account, paid
service, disk cache, watcher, or publication was added. Issue #13 still
requires human tester evidence.

Previously (2026-08-13):
M15's v0.18.0 candidate added the shared parser-owned learning journey, graph
schema 11 role evidence, visible proof breaks, role-backed verification
candidates, and exact cross-mode step continuity. Its tag remains subject to
the external publish and cold-install gates.

Previously (2026-08-09):
M15 is complete: Galaxy Runtime owns WebGL lifetime, Canvas
Occlusion owns role-aware measurements, and five tree-sitter adapters share one
private discovery/parse/finalization lifecycle without changing graph bytes or
public contracts. The preceding default-branch cleanup integrated the Formal Edo public surface
and three scoped GitHub Actions upgrades, while preserving active or unmerged
work that ancestry could not prove redundant. Only `setup-python@v7` ran in CI;
the upload/download artifact handoff in the release-published workflow remains
a next-publish verification point. The v0.16.0 release
context follows: three evidence-led audit loops against the served v0.15.0
build found eight gaps; UD then reported six more from the running app, and
**the ones UD found were the more serious**, which is the finding worth
keeping. Released as **v0.16.0**.

**A language focus emptied the Map, and that broke 5 of the 7 languages this
project ships.** Home is written in one language and nothing in another has an
import route to it, so focusing Rust drew **0 of 5** boxes on a 1396x509 canvas
while the guidance chip said "No Home is chosen" two rows under a header saying
"Home codemble.cli". Two independent causes behind one symptom. The Architecture
tab folds unrouted boxes away to keep the connected core readable, but
`useState` runs its initialiser **once**: the component mounts unfocused (132
unreachable, collapsed), the focus then cuts the set to 5, and the collapse
sticks. The principle the fix restores is the useful part — folding is only ever
a trade made *for* a connected core, so with no core to protect it is never
right, and that is now a derived guard rather than a second piece of state that
can go stale. The Workflow tab was worse: its empty-state guard only caught a
*missing* root, so a focus that filters out every row of a tree whose root still
exists fell straight through and rendered a void with no message and no way
back. Three audit loops never found this because every one of them audited a
single-language path.

**Nothing in the app said what the project was.** Every surface answered a
question *about* something the learner had already found — a module, a
structure, a concept — and the one screen reachable from every level opened onto
a 130-row concept inventory. `projectOverview` in `graphData.js` answers the
first question instead, from the graph: files, structures, languages by size,
where it starts, biggest, most-called, how much is proved, what fell outside.
Parser truth end to end, so it works with no API key and cannot disagree with
the galaxy or the map. Held to the app's own rules — no Home reports none rather
than inventing one, and it says "called from the most places" rather than "most
important", because centrality counts the distinct structures that call in and
that is all it can claim.

**Five surfaces scrolled in silence, and the fix is one the Map already
carried.** macOS draws no scrollbar until you scroll one, so an overflowing
panel is pixel-identical to a finished one: study panel 7.8 viewports at
1440x900 and **19.9** at 320x640 with 9-10 headings below the fold, checks panel
**0 of 4** answer options at three widths, star chart 14.6 across 130 rows, Find
4.8, Modules sidebar 11.4. The Map's drawing has carried scroll shadows for this
exact failure, with a comment describing it. The lesson is the sweep rather than
the fix: five addresses for one defect means fixing them one at a time is how
the sixth ships, so `check_panel_reach.mjs` opens every surface a learner can
open and asserts nothing scrolls without a cue, naming the offender and its
depth. Proven in both directions.

**Two shipped fixes had made things worse in ways only measurement showed.**
v0.14.0 made the quiz submit reachable by putting `position: sticky` on
`.check-primary` — which is the app's *shared* primary-button class, ten buttons
across six components, only one of them inside a scrolling panel. And a 191px
sticky button inside a 627px option row floats *across* content rather than
covering it: at 320x640 it was drawn over **64% of the question** with zero
answers visible. The bar sticks now, not the button. Separately, a Workflow row
drew its meta as a second `<text>` offset by `dx={label.length * 0.62}em`, and
`em` resolves against the meta's own 11px while the mono label advances at 13px
— a systematic ~15% undershoot, so every row printed "— possible call" through
the tail of the name it described.

**Two exits simply did not exist.** The study panel had no Close at all — only
"Back to the module" in the header rail, while the checks panel in the same slot
has carried one since it shipped. And Home was named in the breadcrumb and
clickable nowhere: the only control carrying the word was **Change Home**, which
*redefines* which module Home is, so the one thing that looked like the way back
would have changed the learner's starting point instead.

**Measurement withdrew three candidate findings, one of which was my own bad
instrument.** The galaxy sky looked washed out, and a `readPixels` sample
seemed to confirm it — but it returned all zeros because the drawing buffer is
not preserved after compositing, so the reading was invalid rather than
contradictory. `--cm-sky` is `#131f4b` by design since the 2026-08-02 decision
and the glow is the approved nebula. Focus after the coach marks lands on
`.map-stage[tabindex="-1"]`, deliberately. And "Called by 0" beside "Two other
files bring it in" are both correct about different relations.

**Stated rather than implied:** this release adds the project summary that was
missing and heads the concept inventory after it, but it is **not** the star
chart redesign, and "Easy mode is still hard" is only partly served by it. Both
want their own pass.

428 pytest, Ruff clean, 17 frontend contract checks, space budget green, 84
escape assertions, panel-reach green including its sweep, zero console errors
across the journey. The milestone does not advance: issue #13 still requires
human tester evidence.

Previously (2026-08-02):
Session note: an evidence-led user-flow audit of the served v0.13.0 build, run
as a first-run Easy learner on this repository at 1440/1280/1100/1024/375/320 in
both registers, found six gaps; a seventh arrived from UD mid-audit. Six are
fixed and re-verified live, released as **v0.14.0**. The entrypoint-order repair
and control-aware camera framing followed as **v0.14.1** and **v0.15.0**.

**The most useful finding was one the project's own gate had already been
reporting.** `check_space_budget` had failed on every `main` run since
`cc8647f`, through **three tagged releases** — v0.11.0, v0.12.0 and v0.13.0 were
each tagged with `browser-checks` red, and it was the *only* failing job. The
defect is real and its cause is worth recording: the language focus control
renders one permanent chip per language, so **its width is a property of the
learner's project, not of the design** — seven languages measure 673px, and
below about 1280px that plus the layer switcher and the audience toggle no
longer fits one row. The rail took a third row, header 148 → 216px, and the
Map's drawing fell to 106px at region level, which is the **compact** shell at
1023px beating the wide shell at 1024px three times over. `min-width: 0` and
`overflow-x: auto` were already on that element and could not help, and the
reason is the load-bearing part: a wrapping flex container breaks lines using
each item's *hypothetical* main size and only shrinks within a line afterwards,
so a max-content item is moved to its own row before shrinking is ever
considered. A small `flex-basis` is what keeps it on the row.

**Home stopped resolving itself when the language slate grew, and the fix is a
seam correction rather than a heuristic one.** Rank 0 held six candidates:
`codemble.cli` plus a C#, Go, Java, Rust and TypeScript fixture, so
`selected_entrypoint` was None and a first-run learner met a picker of 26
candidates with 22 under `tests/`. The tempting diagnosis — "the new adapters
have no test demotion" — is **wrong**, and checking it mattered: Rust reads
`#[test]`, Java `@Test`, C# `[Fact]`/`[TestMethod]`, Go the `_test.go` suffix.
Every one of them has a rule; none of them fires, because a fixture's entry is
an ordinary unmarked `main()` in a file not named like a test. Only Python asked
the *path* question. That question needs no parser evidence and is identical in
every language, so it now lives once in `graph/finalize.py` — the funnel every
adapter already returns through — and the Python copy is deleted. An eighth
language is demoted for free, the same promise `unsupported_sources` makes.

**Two panel fixes share one root and are recorded together deliberately.** The
control named "Read the source" opened the study panel at the top with the
source **4144px** down (6.6 viewports) behind the summary, impact widget and
connections; and the quiz's submit button was 47% covered by the status line at
1440x900 and 101px *below the fold* at 1280x720, in a container whose
`overflow: auto` draws no scrollbar until you scroll. Both are the same shape:
a panel putting its own primary content or control out of reach with no
affordance — the class this project already fixed once on the Map's region
caption. Worth stating precisely because it changed the severity: **keyboard
users were never blocked**, since focusing the submit button scrolls it into
view (measured, `scrollTop` 0 → 241). It failed silently for pointer users only,
which is why no gate and no keyboard sweep had caught it.

**The seventh finding came from UD looking at the Map and is a geometry bug, not
a styling one.** Flank routes — cycles, backward edges, anything skipping a
layer — ran the corridor straight to the destination's own top-edge y and then
turned in *horizontally*. An SVG marker orients to its last segment, so every
one of those arrowheads arrived sideways lying flush along the border: a row of
small triangles that read as sawtooth decoration on the box rather than as
routes arriving, with no visible stub to trace back to a source. Routes now
descend to a stub 24px above the box and turn **down** into the port (the row
gap is 64px, so the stub can never cross the row above), and the head is sized
in user space so a thin route gets the same arrow as a thick one. All 248 edges
on this project now end with a vertical segment; the test asserts the property
for every edge rather than for the flank case alone.

**The seventh finding was deferred, then asked for and done properly in
v0.15.0.** A planet the camera projected under the System panel's button could
not be clicked; the click reached the button and opened the quiz. The layout is
parser-owned, so the body cannot move — the camera does, which is exactly the
rule `nameAtlas` has always applied to name plates, extended to what the camera
aims at. `aimIntoClearRegion` takes the largest rectangle of the canvas that no
*control* covers, offsets the aim into it, and pushes back only if the sky no
longer fits.

**What made this affordable in the module with three shipped framing
regressions is one property**: with no chrome the clear region *is* the canvas,
so the scale is 1 and the offset is 0 and the result is bit-identical to the
frame it was handed. Every existing framing contract therefore keeps asserting
the numbers it always did, and only the new behaviour needed new assertions.
Only controls are reserved, never the prose beside them — a
`pointer-events: none` paragraph over a star costs nothing, since the star stays
clickable and visible around the text, while reserving the whole 417×328 panel
would have pushed every system back for a problem only its buttons have. The
gate is proven in both directions, and the first fixture written for it **failed
to reproduce the defect** and said so, which is the reason it is trustworthy:
the points projected nowhere near the control, and a gate that cannot see the
bug it guards is worse than none.

**Measurement discipline paid twice.** A candidate finding — "Expert has no Read
the source" — was **withdrawn** on evidence: holding the layer constant showed
it is absent on Galaxy and present on the Map in *both* registers, so it is
layer-specific and correct. And the ambient `codemble` install resolves to a
different worktree at v0.9.0, so the whole audit ran from a throwaway venv built
from this tree; testing the ambient one would have audited the wrong code.

**v0.14.1 exists because the release was verified rather than trusted, and both
defects it fixes are worth recording.** The test-bias was applied **twice**:
`finalize_graph` runs once inside an adapter's `parse_files` and again when
`ProjectParser` composes, and a rule that *adds* to `entrypoint_rank` is not
idempotent — measured, rank 4 became rank 8. It changed no outcome on the
projects to hand, which is precisely why it survived a green suite: every new
test called `finalize_graph` directly, once, and the composed path is the one
every real run takes. It also quietly broke a promise the picker makes and the
docs repeat — that the rank shown is the parser's own. Biasing the **sort key**
instead of the field fixes both at once and cannot compound however many times
finalization runs. The second defect is the same half-wiring shape as the 2026-08-02
`recordVisit` note: `revealSource` was cleared on the study panel's own
navigation but not on the Map's Workflow rows, which dispatch selection
directly, so the button's effect leaked onto a module the learner never asked
about.

428 pytest, Ruff clean, 17 frontend contract checks, the space budget green at
every width and level it asserts, 84 escape assertions, reproducible bundle
(two builds, identical content hashes). The milestone does not advance: issue
#13 still requires human tester evidence.

Previously (2026-08-02): UD's complaint was that the galaxy is "too dark and hard to just
explore even if you are not learning", that the product's main goal is
exploring code like an astronaut with learning **optional**, and that
explanations are "too complex for a casual user" while "for experts most of the
stuff in that view doesn't load". A grilling session resolved those into an
approved four-phase redesign
(`docs/superpowers/specs/2026-08-02-explorable-galaxy-redesign.md`); the first
three shipped and are on `main`.

**Public presentation now matches that current app.** README and website use a
Formal Edo Workbench led by reproducible 1440×720 product captures instead of a
decorative hero: current Galaxy → Map → System → Impact → proved Galaxy. The
download surface follows the FolioOrb clarity pattern—icon-led artifacts,
published digests, a one-command route, and an explicit source-build route—while
keeping its own visual language. Packaged stable, current source, and the
screens are all v0.16.0; PyPI owns the downloadable wheel and sdist because the
GitHub release has no binary assets. No app, parser, graph, checks, progress, or
release behavior changed.

**The darkness was not a bug, and that is why it needed a decision.** The unlit
ramp was capped below a *text* token so amber would always win, and progressive
reveal drew everything uncharted faint, unnamed and edgeless — about 100 of 128
systems here. The sky was faithfully rendering "you have not learned this yet"
and charging exploration for the privilege. UD chose a presentation flip rather
than an identity flip: every meaning rule is intact, amber still means
understanding and is still the brightest thing in the sky, checks are still the
only way to earn it — but none of that may make the galaxy unexplorable first.
So reveal now gates the **route mesh and the camera's opening frame only**,
which is what the hairball actually was, and every module is represented and
coloured from the first frame; labels are ranked and decluttered, and every
parser-owned name is available on hover. Travel earns something of its own: visiting a
region **charts** it, persisted, drawing its routes permanently and counting on
the star chart as "Systems explored" — deliberately a separate row from
understood, because been-there is not know-it. It is not signature-scoped the
way `understood` is, and the asymmetry is the point: a proof of understanding
is a claim about code and must retire when that code changes, while having been
somewhere is a fact about the learner's own history that no edit can undo.

**"Most of the stuff doesn't load" was never a panel bug.** Every route was a
plain `def`, so all of them shared anyio's request threadpool, and `urlopen`
cannot be cancelled — once a worker is inside it that thread is gone until the
provider answers. Enough in-flight explanations starved `/api/graph`,
`/api/map`, `/study` and `/checks` alike, and experts hit it first because they
click through structures fastest. Narration now runs under a `CapacityLimiter`
of its own, so the default limiter is never acquired. **The regression test for
it is worth reading before writing another one like it**: the cascade is *not*
reproducible in-process, because `TestClient` gives each threaded request its
own event loop — measured, 45 concurrent requests against the old sync route
ran 45 provider calls at once and `/api/graph` still answered in 0.01s. A test
asserting "the parser endpoints stay responsive" passes with the fix reverted
and is worth nothing. What is gated is the bound (28 pre-fix, 4 post-fix).
Review then caught the same defect class arriving through the dependency graph:
`abandon_on_cancel` was named `cancellable` before anyio 4.1, and anyio only
ever reached Codemble through Starlette's `>=3.6.2,<5`, so an older resolution
would have raised TypeError on every narration request. It is a direct
dependency now, with a gate.

**The Expert panel stopped depending on a model for its lead content.**
`codemble/graph/impact.py` computes blast radius from proven edges — what feels
a change here, what this depends on, depth-capped and cited — and ships in the
`/study` payload, which never touches a provider. Certainty comes from a
*second* walk restricted to certain edges, because the shallowest route to a
node and its only proven route are frequently different routes, and one pass
forces a choice between reporting the true distance and the true certainty. A
chain through one unproven edge is unproven for its whole length. Hovering any
star now answers the same question in miniature (`used by 7 · uses 2`), direct
edges only. Explanations lead with what a thing is *for* in at most three
sentences, the line-by-line walkthrough moved behind a closed disclosure, and
Easy may use an everyday comparison where Expert may not.

**Two gates were added because prose was doing their job.** `check_sky_palette`
measures the meaning rules out of `tokens.css` — ordering, per-family parity,
the reserved kohaku hue band, the legend floor, uncertainty louder than
certainty, bloom threshold bracketing, no invisible star — and refuses an
`@import` back to the docs tokens, so the palette fork cannot quietly undo
itself. Proven in three directions. And review found `recordVisit` claiming in
its own docstring to cover "every route into a system" while missing
`selectStudyNode` — the handler behind the Workflow tree, the Connections list
and the new Impact rows, all of which can land on a module never flown to; that
claim is now gated rather than restated. Measured palette: lit 0.665 > family
0.470 > ramp 0.439/0.220 > sky 0.0163.

**Phase 4 shipped the language slate but not its deepening, and the split is
deliberate.** Go, Java, Rust and C# now parse behind the unchanged seam —
adding them was a tuple in `project.py`, four adapter files and four lens
tables, which is the seam's claim actually being cashed. Written by four
parallel agents each followed by an adversarial verifier, then composed: seven
languages in one deterministic graph (csharp 39, go 24, java 43, javascript 4,
python 4, rust 28, typescript 17 = 159 nodes, 137 edges, 33 regions). The
number worth watching is that **82 of those 137 edges are hedged** — a Go call
through an interface value, a Java call on a variable whose type the tree does
not give, a Rust trait-object dispatch, a C# call on a `var` local. That is the
honest figure rather than a flattering one, and it is also the argument for
what comes next: the *deepening* (Python and TypeScript call resolution) was
scoped into this release and is **not** done, and it now outranks a sixth
language, because every edge that becomes provable sharpens the impact widget,
the checks and the map at once. Schema 8 needed no second list — `.go`,
`.java`, `.rs` and `.cs` left `unsupported_sources` automatically, which is
what that design promised, and there is now a test for the promise.

**v0.11.0 started the deepening, and the useful part is how nearly it went
wrong.** 79% of Python call edges were unproven, but the number was the less
important half: `.parse()` drew an edge to every class in the project defining
`parse`, so eight in nine were relationships that do not exist — quietly
inflating brightness, blast radius and the route mesh while staying technically
within the contract. The first fix (base-class walk plus annotated receivers)
was reasoned from what *ought* to be common and moved the count the **wrong
way**, +65 edges. Counting which call sites actually produced the fan-out took
one command and named the real shape: `Adapter().parse()`, a receiver
constructed on the spot, which is also the one form Python makes fully
provable. Result 8508 → 6778 edges, 1993 fewer unproven, and `.parse` gone from
the unresolved list entirely; what tops it now is builtins, correctly external.
The lens also stopped being silent on the Python this audience actually meets —
dataclass, Protocol, `match`, f-string, walrus — with a gate asserting every
emitted concept can be voiced, since the adapter and lens are separate files
and a concept can ship detected-and-silent. **v0.12.0 then measured TypeScript the same way and mostly refused the work.**
80% of its unproven edges are already `external:` and 1% is in-project fan-out,
so TS has no ambiguity explosion and porting Python's receiver resolution would
have been effort against a problem that is not there. What the measurement did
find was a *category* error: `Set`, `Map`, `AbortController` and
`requestAnimationFrame` reported as `unresolved:javascript:graphData.js:Set` —
"we think this is yours and cannot find it" — when they are language globals
that leave the project exactly as `Math.max` does. 258 → 114 unresolved. And
Home stopped being unanswerable: five of seven candidates here were test
fixtures with three tied at rank 0, so `selected_entrypoint` was **None** and a
first-run learner met a picker listing mostly `tests/`. Test-scoped candidates
now take a bounded penalty — demoted, never dropped, since a project that *is*
a test suite still needs a Home — and this one resolves to `codemble.cli` with
no question asked.

Released as **v0.10.0**. 379 pytest, Ruff clean, 19 frontend contract checks,
bundle rebuilt reproducibly, verified against a running server at 1440 and
narrow widths in both registers. Note the suite count is from a **clean venv**:
the ambient editable install points at another session's worktree, so the
version-agreement test reads stale metadata locally — see the memory note
rather than reinstalling, which would repoint that session's environment. The
milestone does not advance: issue #13 still requires human tester evidence.

Previously (2026-08-01):
Session note: an evidence-led user-flow audit of the served build, run as a
first-run Easy learner on this repository at 1440/1024/768/375/320 with a
keyboard pass, found **two** gaps — and the more interesting fact is that both
had already survived the CI job built to catch exactly them. **Clearing your
progress made a proved module impossible to light again.** `ProgressStore` owns
which regions are understood and `CheckService._passed` owns which individual
checks were answered, and the endpoint reached *through* the service to the
store, so the store emptied and the pass set did not: every module went dim
while every question stayed marked answered. `for_region` then reported a suite
that was fully passed on a region that was not understood, the renderer has no
branch for that, and **the panel drew a title and a Close button over nothing**.
The product's central action, on the recovery control the app itself offers,
with no route back short of restarting the server. One caller now clears both
halves. The panel also gained an honest branch for that shape, because the
server can no longer produce it but a second tab holding a stale suite still
can. **The header wrapped to two and three rows across 1024–1279px** — 148 →
199 at region level and 259 at study (52.2% of a 720px window, the diagram down
to 190px). The cause is which column yields: brand and breadcrumb were `auto`
tracks taking max-content while the actions held the only flexible track, so
every pixel either text column wanted came out of the buttons, and buttons
cannot shrink. Inverted — the actions size to their content and the two
ellipsising text columns absorb the shortfall, breadcrumb keeping its 9rem floor
because "where am I" may not be erased, brand yielding first because it is
identity rather than navigation. Two details were load-bearing and neither is
obvious: a wrapping flex container's min-content is its *widest single item*, so
`auto` alone left the track frozen at one button and grid then shared the
leftover out **equally** with the brand; and `.rail-actions` declares
`min-width: 0`, which tells grid the buttons are willing to be zero wide.
**Why CI was green through all of this is the lesson.** The space budget
measured only the *top* level, where the rail carries one action fewer, so the
wrap was one click below anything asserted. And the brand's second line is the
learner's own directory name, so the header's height was a property of what the
folder is called — GitHub checks out into `Codemble`, eight characters, where it
fits; this worktree is `navigation-design-clarity-92b110`, 31, where it does
not. A 60-character name reproduced the wrap at **1440**. The budget now walks
region and study level at four wide widths, fails on overlapping header controls
(clip-aware, since an ancestor hiding its overflow clips the hit test too), and
injects a 70-character project name. Proven in both directions: the new
assertions fail on the old CSS naming the exact collision. A third finding was
the gates themselves — `check_escape_surfaces.mjs` clicks a control named "Map"
while the Easy register renames it "Diagram", so it never left the Galaxy and
**eight of its 84 assertions had been failing for the wrong reason**, reporting
"could not reach the prove control" rather than exercising the checks panel and
the map retreat. Fixed; 84 pass. Stated as a limitation rather than hidden: at
1024–1059px at study level only, the "Codemble" wordmark clips by 2px, accepted
over truncating the breadcrumb or demoting a 36px band of widths to the compact
shell. 266 pytest, Ruff 0.16 clean, 18 frontend contract checks, the space
budget at 8 widths plus 4 wide widths × 2 levels, 84 escape assertions,
byte-identical rebuild. Released as **v0.9.0** (`docs/releases/v0.9.0.md`),
carrying everything accumulated since v0.8.0. The milestone does not advance:
issue #13 still requires human tester evidence.

Previously: the app stopped misreporting its own version. It was written down
twice, and v0.8.0 shipped a wheel whose app called itself 0.7.0 — through
`--version`, the FastAPI title, and the user-agent on every narration request,
so the number was wrong in three channels at once. The literal is deleted and
`__version__` now reads the installed distribution's metadata, which for a built
wheel *is* the `pyproject.toml` it was built from, so a shipped artifact can no
longer disagree with its tag. Golavo's `scripts/bump_version.py` was considered
and deliberately not copied — see the Decision Log for why enforced agreement is
right there and wrong here. The one drift that remains is gated, in
`tests/test_smoke.py`: the app must report `pyproject.toml`'s version, and the
failure names the reinstall when a stale local install is the disagreement. The
npm manifests are deliberately left ungated at UD's call — nothing reads their
`version` field and neither package is published, so a drift there is cosmetic
and not worth failing CI on a release branch. The machine turned out to hold **three**
versions at once, not the two reported: pyproject at 0.8.0, the source literal
*and* the active pyenv install at 0.7.0, and the project venv at 0.6.2. Both
installs were refreshed against the main checkout, so neither editable target
moved. 268 pytest, Ruff 0.16 clean; the uninstalled fallback was verified in a
genuinely isolated interpreter rather than argued for.

Previously: the public website no longer assumes browser zoom. Its reading
scale is now 18px with a 14px informational floor, while the denser local app
keeps its own scale. At ordinary desktop widths the four real product captures
use the full content column (1174px at 1440, up from 704px); at narrow widths
they keep a 960px readable canvas inside a labelled touch-and-keyboard-scrollable
viewport instead of compressing to 333px. The same treatment now wraps every
product shot in the long-form docs. The Atlas Journey crossfade is reserved for
canvases at least 120rem wide and expands its content measure there so the frame
still clears 1000px. Verified on the built site at 1440/375/320, in landing and
docs shells: zero page overflow, keyboard horizontal scroll, no broken loaded
images or console errors, Astro check/build clean.

Previously: two faults found by *running* the app rather than testing it, both
of which the suites were structurally unable to catch. **The blank galaxy stage**
is finally understood: `composer.setSize` is the only thing that sizes the pass
chain the scene is presented through, the width/height props that trigger it are
diffed, and a re-mount into a host of the SAME size skips them -- so the bloom
pass kept its constructed 1x1 and the whole galaxy arrived through a one-pixel
buffer. Correctly sized canvas, no console error, nothing drawn. That also
explains why it read as engine-specific across two sessions: it needs the
re-mount to land on an identical size, so a fresh page load differs from the
library's defaults, gets a real resize for free, and never shows it -- a driver
that always starts from a new page cannot reproduce what a human hits on the
first layer switch. Stated as evidence rather than proof: three clean switches
after the fix against one blank before it. **A name plate was printed across the
chrome**: the orientation line sits *over* the canvas, `nameAtlas` knew only
about the canvas edge, and on this repository a plate was drawn straight through
"24 charted · 2 could not be read · all under tests/" -- the line graph schema 8
added so a learner is not misled about coverage. The first attempt at that fix
was a silent no-op (it scoped the DOM query to `host.parentElement`, three divs
below the wrong subtree) and looked correct until the plates were counted, which
is the second thing running it caught. 265 pytest, Ruff 0.16 clean, 18 frontend
contract checks, byte-identical rebuild.

**Process note, recorded because it nearly cost someone else's work:** the shared
`Codemble` checkout is not always on `main`. A parallel session had it on
`feat/dawn-sequence` with uncommitted changes to `galaxyEffects.js` and a new
`dawnSequence.js`, and this session edited the same files there before noticing.
Nothing was lost -- the edits were hand-reverted, their tree rebuilt to the exact
bundle hash they had staged, and their check re-run green -- but `git branch
--show-current` and `git status` belong *before* the first edit in a shared
checkout, not after. Work happens in the worktree; only the push touches `main`.

Previously: the galaxy camera now **aims** at what it is framing, closing the
follow-up the merge below left open. Knowing how far back to stand says nothing
about where to look, and the camera still stared at the origin, which a
parser-derived layout is not arranged around: the charted sky opened 15 points
left of centre and 27 high, top 42% of the canvas empty, lowest module cut by
the bottom edge. The obvious fix is wrong and is why this is worth recording --
aiming at the points' world-space centre made the vertical **worse** (29.6
against 27.1), because under perspective a near point at a given offset projects
further from centre than a far one. What must be centred is the *projected*
extent, which depends on the distance, which depends on the aim. `frameAround`
solves the three together: each pass aims exactly for the distance it has, by
bisecting a strictly monotone imbalance rather than stepping toward it, then
refits the distance for that aim. Stepping was tried first and stalls where the
subject is large relative to its own distance -- a system sits 66 units from a
ring of radius 58 and it settled 15 points off. Fixed pass counts, so "same code
-> same sky" does not come to depend on a tolerance. Two things fell out of
running it. A shorter distance comes free (a centred subject needs less
standoff), so the sky arrives filling **90% of the canvas height where it filled
63%**, with two more names on screen. And that immediately **cropped the stars**:
a layout coordinate is a star's centre, its halo reaches 9-15 units past it, and
the framing had only ever fitted centres -- safe until the standoff shrank.
Points now carry the radius of what is drawn at them, per point rather than one
global pad, because a system fits its planets *and* the guide circles they sit
on and a guide has no glow. Verified before/after on the served build at
1440/1280/375/320 in both registers: the lowest module was clipped by the bottom
edge and is not now. 265 pytest, Ruff 0.16 clean, 17 frontend contract checks,
byte-identical rebuild.

Previously: the seven in-app screenshots were recaptured on the Living Atlas
build. Two sessions did this independently and the merge is worth recording,
because the tie-break was **not** "take the newer capture". The parallel set
reported `125 systems · 1192 nodes · Python 73`, this one `123 · 1188 · 71`,
with edges identical at 7295 — exactly +2 Python regions and +4 nodes, and no
new edges. A parse of the committed tree gives 123/1188/71, so the parallel
capture was served from a tree holding two Python files that never landed;
its screenshots documented a project that does not exist at any commit. The
images here are the ones that match what a reader gets from `codemble .`, and
the other session's **wording** was the better half and is kept — it names the
procedural worlds and rim atmospheres the release actually added, which this
session's alt text did not. Corrected in the merge: 125 → 123, 95 → 93
unrouted modules, and "thirty-nine" communities → thirty-eight, which was
stale in prose before either capture. The `galaxy-lit` alt also stopped
claiming every dim star wears a community colour: under the size-ranked
families 30 of 123 regions correctly wear none. `loading.png` remains
untouched for the reason recorded below.

Previously: an evidence-led user-flow audit of the served v0.8.0 build, run as
a first-run Easy learner on this repository at 320/375/768/1440 with a keyboard
pass, found twelve gaps; eleven are implemented and re-verified against the
rebuilt bundle in two Chromium builds, and the twelfth was already fixed better
on `main` — see the collision note below. **Fit** was the sharpest find, and not
merely a no-op: `fitMapWidthZoom` capped the width fit at `1`, so on any viewport
wider than the 1024px drawing it returned exactly the scale the map already opens
at — and pressed from 64% it zoomed *in*, taking the visible diagram 33.5% →
21.5%. The control that promises the whole shape was the one hiding more of it.
`mapOverviewZoom` keeps the old width-fit where the drawing is wider than the
viewport and drops to the readable floor where there is no width left to fit:
21.5% → 61.4% at 1440x720. Its check states the property — from any scale at or
above the floor, Fit must not zoom in — rather than a number somebody eyeballed.
Three fixes were one right rule applied to the wrong thing: `.active-check
legend` wrapped a question that *quotes an identifier* at the prose measure
(28ch) with `overflow-wrap: anywhere`, splitting `ProjectParser` into
`Project`/`Parser` with 210px of the 627px fieldset unused (`break-word`, because
only `anywhere` also shrinks the intrinsic minimum, which is what let a narrow cap
force a break the space never required); `.map-canvas`'s 96px floor is written for
the drawing, but at compact widths the zoom toolbar rejoins the flow *inside* that
box, so the drawing got 56px of a ten-layer diagram — 96 → 187px at 320x640; and
`moduleIndex` sets `label = pathTail(file)`, which on a subdirectory scope *is*
the file, so all 32 Find rows printed their path twice. **Escape was
systematically half-wired**: the window handler bailed for each overlay so the
overlay could own the key, but the checks panel and the module index never
claimed it — while the coach marks teach "Escape to come back" — and every
overlay that did claim it double-fired, because that handler reads the session at
event time and the close has already cleared the flag it bails on. Closing the
star chart from inside a module also retreated a level. The first fix put
`stopPropagation` in each panel and **it did not hold**: the common Easy path
reaches the quiz from the guidance chip, which unmounts as the panel opens, so
focus sits on `<body>` and a container keydown never hears the key — the very
reason that listener is on the window. So the window handler now *dismisses* an
open panel rather than bailing for it. Verified as a matrix: four overlays, each
closing on one press, each holding its level, plus a guard that Escape with
nothing open still retreats. The compact rail disclosure keeps its own handler,
because it is read from the DOM rather than session state, which is why it never
had the bug. Also: the breadcrumb says **All modules** instead of borrowing the
renderer's word (an Easy learner on the Map read `aria-current="page"` Galaxy in
one control and `aria-pressed="false"` Galaxy in another, 30px apart); guidance
covers study level, where the loop's deepest step had none and the panel ended on
a lens note with nothing to do next, and yields while the quiz is open; the map's
edges shade while the drawing continues past them, since the platform draws no
scrollbar until you scroll; and a wrong answer no longer pushes "try again" off
the panel. **Left open, stated rather than claimed:** the blank System stage
after a Diagram→Galaxy remount reproduced twice in the Claude in-app browser and
not at all in Playwright, so no fix was kept for it — it is a race whose blast
radius depends on the GPU path, and it wants instrumenting before it wants
patching. 254 pytest, Ruff 0.16 clean, 13 frontend contract checks, astro
check/build, byte-identical rebuild of the committed bundle.

**Collision, reconciled:** a parallel session shipped the galaxy-camera fix to
`main` (`0c6caf4`…`a2cf48f`) while this branch was in flight, and this branch had
implemented the same thing under the same two filenames. **Main's is kept
wholesale and this branch's was dropped**, because main's is better and this
branch's first diagnosis was partly wrong. Both sessions found that a
`PerspectiveCamera`'s `fov` is *vertical* — but main measured that against the
real layout the aspect changes the required distance by **nothing** (1061 at 3.8,
at 3.16 and at 1.9), and that the binding constraint was the near edge: the
layout is a disc of radius ~628 while the camera sat 327 out, so 15 of 113
regions fell *behind* the camera. This branch measured a 32-module subdirectory
scope, where that never happens, and concluded the aspect was the cause. Main's
version also fits the **charted** set rather than the whole disc, re-frames on
resize, and keeps name plates on the canvas — none of which this branch had. The
one idea worth carrying forward is this branch's: main aims at the origin and
solves only for distance, while the layout's bounding-box centre is nowhere near
it, so the sky still opens off-centre with dead space on one side. Nothing is
clipped, which was the defect; re-targeting is a follow-up to measure against
main's new spacing, not something to graft in unverified.

Previously: the galaxy camera now frames what is actually there. It had used a
Session note: an architecture review found one shape behind most of the
frontend's recent bugs — **the extraction line in `web/src` was drawn at "does
it import `three` or React?", not at "is this a decision?"** Every pure module
on the near side of that line is tested; every decision that happened to sit
inside a component is not, and that is exactly where the last three camera
faults landed. `framingDistance` is the most tested function in this frontend
and has never been the bug: `0c6caf4`, `c64a88a` and `5bdb110` were all about
*what it was handed*, and `c64a88a` shipped with no check-script change because
there was nowhere to put one. `galaxyView.js` now owns which points to fit, at
what aspect, inside what clamps, and where study stands off a structure, with a
regression fixture per fault. Three faults fell out of writing those tests: the
aspect had two sources and now has one (the host element, never the library's
batched copy — that was the stale-aspect bug's actual cause); `frameLevel`
returns its own `distance` because re-deriving it with `Math.hypot` disagrees in
the last bit; and the name atlas had been budgeting labels against the *static*
bounds while the camera was clamped to the *fitted* ones. A fourth was caught by
running it rather than by the suite, which is the point: preferring the host
rect made it the *only* source, and an element not yet laid out yields no
aspect, which silently reopened the fixed-distance clipping — the renderer's
size is the fallback. **One real defect surfaced on the backend**: focusing
Python on a mixed project reported *zero* never-called structures where the
polyglot fixture has two, because the renderer filtered `workflow.unreachable`
by an `id.startsWith("<language>:")` prefix that only the JS/TS adapter mints.
The contract check agreed with the bug because its fixture spelled Python ids
the JS way. Map schema 3 → 4 gives each row its own `language`. Also: Escape
precedence is an ordered list instead of an eleven-term disjunction plus a
second shorter copy on the chart stage; "what colour is this node right now" is
one function beside the standing answer rather than a closure the halo could not
reach; `with_entrypoint` refuses a graph that never reached `layout_graph`
instead of returning a starless one, and re-selecting the current Home is a
no-op rather than a full BFS per hydration. **CI now asserts the shell's space
budget** against a running Codemble — this amends the standing rule "UI is
verified by running it", approved by UD, because three of the last eight
bugfixes were `styles.css` and `99b6875` was a cascade-resolution bug no JS seam
can reach. It reproduces `13b3c06`'s own numbers (header 148, chrome 36.8%) and
is proven in both directions. Deliberately **not** done: the audit's remaining
"language leaks" are one-line-per-language tables whose removal would cost
widening the protected four-method `LanguageAdapter` seam, and two of them
(`conceptTitle`, `shortLanguageLabel`) need no edit for a new language at all.
Escape was then swept on every surface with real key presses, which found one
pre-existing gap and closed it: leaving the **quiz** returned focus nowhere,
where every other panel hands it back, so a keyboard learner who had just worked
through a region landed on `<body>`. That sweep is now a gate —
`check_escape_surfaces.mjs`, beside the space budget in a `browser-checks` job.
Two measurement errors are worth recording because both produced confident wrong
readings: the in-app browser pane reports `document.hidden === true`, which
throttles `requestAnimationFrame` and therefore `restoreRailFocus`, so focus
return read as broken everywhere until it was re-run in a foreground browser;
and comparing the breadcrumb while a panel is *open* against after it closes
compares two different correct states, which reported a double-fire that was not
one. Both are guarded in the check itself. 265 pytest, Ruff 0.16 clean, **14**
frontend contract checks, the space budget at four widths in both registers, 18
escape-surface assertions, reproducible rebuilt bundle.

Previously: the galaxy camera began framing what is actually there. It had used a
fixed distance, and **the first diagnosis of why was wrong**: a
`PerspectiveCamera`'s `fov` is vertical, so v0.8.0's taller canvas did narrow
the horizontal field — but measured against the real layout the aspect changed
the required distance by *nothing at all* (1061 at 3.8, at 3.16 and at 1.9).
The binding constraint was the near edge. This repository's layout is a disc of
radius ~628 while the camera sat 327 from the origin, so nodes reached 552
along the view axis and fell **behind** the camera: 15 of 113 regions gone
outright, 16 more off screen, 82 of 113 visible. The layout had outgrown the
distance, which no aspect explains and which predated v0.8.0. `framingDistance`
now solves for the smallest distance holding every point inside the frustum,
given the tilt, the vertical fov and the aspect; the tilt stays art direction.
Three more faults surfaced only by running it. Fitting **all** 113 systems
framed the whole disc and left the charted core a thumbnail — nothing off
screen, nothing legible either — so the camera fits the *charted* set while the
far clamp is still set from the whole project, which keeps the uncharted rim
reachable without opening there; **Show all** charts everything, so that case
fits the lot. The re-frame on resize read a stale `camera.aspect`, because
Kapsule batches `width`/`height` and applies them on its next tick, so the
aspect is now passed in. And name plates are far wider than their stars and
keep their pixel width whatever the camera does, so **no** share of the frame
reserved by the camera can cover them on a narrow window — at 900px the widest
paths, which are the most useful ones, hung over the edge. That belongs to
`nameAtlas`, whose `chooseSlot` already had the plate's pixel rectangle and
already rejects a slot it cannot have; it now also rejects one that would fall
off the canvas and tries the next, exactly as it does for a collision. A system
view fits its orbit **guides** as well as its planets, since a guide is a
circle through the planets and its widest point on screen falls between them.
Verified at 1440x720, 1280x720, 900x1000 and 375x720, on Show all, across
resizes, and with a manual zoom preserved through one. Counts moved
1121/6995/111 → 1137/7054/113 because the fix's own two files are parsed, so
every shot and every quoted count was redone. 254 pytest, Ruff 0.16 clean,
**13** frontend contract checks (camera framing is new), astro check/build,
reproducible rebuilt bundle.

Previously: the eight product screenshots were recaptured on the v0.8.0 shell,
paying the debt the release left open. Measuring them first changed the job
three times. Only **five of the eight were displayed anywhere** — `easy-mode`,
`galaxy-lit` and `map-workflow` appeared in no README, docs page or landing —
and `NOTES.md` frames the directory as a library to be preferred over invented
media, so they stayed and were recaptured too. `galaxy-lit` has since been
placed under **Lighting rules** on the checks-and-lighting page, where one
amber system among dim ones is the claim the page is making; `easy-mode` and
`map-workflow` remain library stock. The header was also only the
newest drift: `easy-mode` and `galaxy-lit` rendered **Expert** vocabulary under
a selected **Easy** radio, `easy-mode` still had grey stars from before the
v0.7.0 community colours, `galaxy-lit` recommended a test module as the next
study target (pre-dating the test-path penalty), and `map-architecture` carried
a third header again — the set was captured across several builds and had never
been internally consistent. Two real bugs surfaced and were fixed before any
capture, because both would have been published. **`unsupported_sources`
counted the bundled SPA**: `_ignore_project_directory` prunes a directory only
when *every* adapter ignores it and Python ignores none, so `codemble/web_dist`
was walked, the `.js` matched the TS rule, the path then hit that rule's
`ignored_directories`, and the file fell through to the tally — the galaxy told
a learner "1 JavaScript file not included" about a file excluded on purpose, in
the one channel schema 8 added to be truthful about coverage, and a case the
v0.8.0 changelog already promised was handled. Recognition, not ownership, now
decides the tally. **`.mobile-menu-trigger` had no `background`**, so the UA's
`buttonface` (#efefef) won and ruri text sat on it at 2.0:1 against a mandated
4.5:1 floor; pre-existing at compact widths, but v0.8.0 promoted the control to
every desktop width as **More**, so it appeared in all seven frames as a light
slab in a dark header. Deliberate calls: `loading.png` is **unchanged** — a
pre-app, full-window state with no header, 1280x900 from a different rig, whose
"13 of 900 files" describes a synthetic project and so takes no part in the
renumbering; `easy-mode.png` moved to the **Map**, which is what Easy actually
opens, because captured as a galaxy it was a near-duplicate of `galaxy.png`;
and `galaxy.png` is now a true first-run **unlit** state, so its alt text no
longer claims an amber lit Home — that is `galaxy-lit.png`'s job, which earns
its place as the after to the hero's before. Counts moved 1081/6724/109 →
1121/6995/111, but far less prose depended on them than expected: `53 callers`,
`fifty-three callers`, `31` structures and "two files could not be read — all
under tests/" were all still exactly right and were left alone. Capture at
1440x720 rather than the old 716 also required `AtlasJourney.astro`'s two
`height` attributes and `landing.css`'s `aspect-ratio: 1440 / 716` to move in
step, or the plate would letterbox. The galaxy opened clipped and both galaxy
shots were framed by zooming out by hand; that has since been fixed properly —
see the entry above. 254 pytest, Ruff 0.16 clean, 12 frontend contract checks,
astro check/build, reproducible rebuilt bundle.

Previously: **v0.8.0** — the shell stopped spending more height on chrome than
on the stage it frames. Easy mode at 1280x720 gave 338px of 720 (47%) to header,
guidance and footer and left the Map's drawing 82px, roughly one 56px row of
boxes; at 375 only 41px of an 80px canvas was ever on screen, so the layer Easy
mode *lands on* opened with no diagram visible. The header was the cause and it
was a width problem billed as a height one: six permanent buttons need 913px on
this repository, the desktop grid handed that group 522px and handed the brand
an equal 522px for 147px of content, so the actions wrapped to two 44px lines and
the controls were exiled to a second row. Measurement settled the design rather
than taste — freeing the width alone buys 0px, and packing everything into one
row crushes the breadcrumb to 0px width, which is the `short_label` failure
class, so something had to yield. Change Home and Switch project moved behind the
disclosure compact widths already have, reusing its open state, Escape handling
and focus return instead of growing a second one; Modules, Find, the level exit
and Star chart stay permanent. Three smaller faults were found by measuring: a
`<legend>` renders above its fieldset whatever the fieldset's display is, so one
word cost 22px until floated; `.check-launch` carried the floating variant's
margin while `.orientation-copy__actions` also set a gap, so two 44px buttons
measured 136px at 375; and the guidance chip offered **Read the source** while
the region panel rendered the identical button above it from the identical
condition. Two latent bugs surfaced and were fixed at their shared guard: the
panel's descendant rule forced auto placement that an old `minmax(0,1fr)` column
had been absorbing, and the compact `[data-open]` rule out-specified the desktop
`display: contents`, so opening More re-nested the permanent groups and grew the
header to 301px. Escape with a rail disclosure open had always double-fired —
closing it *and* retreating a level — reachable only at compact widths before.
Result: header 221 → 148, chrome 47% → 37%, canvas 82 → 158 at 1280x720; at 375
and 320 the drawing is whole and fully visible at 96px where half a box used to
be. The two map notes were deliberately **not** collapsed: they sit *below* the
canvas, so measurement shows they starve nothing, and hiding a correctness fact
behind a disclosure to save scroll length is the wrong trade. The screenshot
debt this left open has since been paid — see the entry above. 253
pytest, Ruff 0.16, 12 frontend contract checks, astro check/build, reproducible
rebuilt bundle.

**Collision, reconciled:** a parallel session shipped `99b6875` to main against
the same symptom while this branch was in flight, and UD had approved *that*
session's row-swap variant too — all six actions spanning row 2, controls in the
row-1 corner, no control demoted, rail 221→161 and canvas 82→142. This branch's
disclosure variant was taken because it is the later approval, reaches 148/158,
and carries four fixes the row-swap does not (the duplicated guidance control,
the doubled actions-row margin, the Escape double-fire, the canvas floor). The
row-swap's own contribution was kept and is the better half of the shared
discovery: **both** sessions independently found that
`.rail-overflow__panel .rail-*` (0,2,0) outranked the desktop placement rules
(0,1,0), making the whole `@media (min-width: 40rem)` block dead code; scoping
that reset with `@media not all and (min-width: 40rem)` — the exact complement,
so no width falls through — is a genuine repair, where out-specifying it merely
outranks it, so the merge keeps the scoping and drops this branch's workaround.
Its measurement of narrow desktop is what caught the one real fault in the
merged result: at the old 40rem breakpoint this branch's arrangement measured
199px of rail at 768 and **319px at 640**, against the compact shell's 124px at
those very same widths — a wide layout losing to the one it replaces. So the
rail's wide rules moved to their own `@media (min-width: 64rem)` block, lifted
out of the 40rem block that also carries unrelated panel rules, with the
compact reset's complement moved to match. 640–1023px now keeps the compact
shell: 768 went 451 → 124, and the 1023/1024 boundary was checked in both
directions with the breadcrumb whole on each side.

Previously (main, 99b6875), the parallel row-swap fix: The six rail actions needed ~883px but
were boxed into a `1fr` third of the grid (~495px), so they wrapped to two 44px
rows — while the layer switcher and audience toggle sat alone on the row below
using 370px of 1236px. The rail spent 221px of a 720px window, and ~866px of its
second row was empty. Investigating it turned up why: `.rail-overflow__panel
.rail-actions` (0,2,0) outranked the desktop placement rules (0,1,0), so the
`@media (min-width: 40rem)` block was **dead code** and the desktop rail was
arranged by grid auto-placement that merely looked deliberate. That reset is now
scoped to the compact shell with `@media not all and (min-width: 40rem)` — the
exact complement, so no width falls through — which lets the desktop rules mean
what they say. Each group then takes the row that suits it: the actions span the
full width (one row, never two), the controls take the row-1 corner. Approved by
UD as the row-swap option over two more ambitious variants. Measured: rail
221→161px and canvas 82→142px (+73%) at 1280x720 Easy; Expert 202→146px; and
narrow desktop was far worse than reported — 640px went 511→271px, 768px
451→271px. Verified at 640/768/1280/1440, both registers, with the 639/640
boundary checked in both directions and the compact Menu panel unchanged. No
parser, graph, checks, progress or HTTP behaviour touched; no control removed.
253 pytest, Ruff 0.16, 12 frontend contract checks, reproducible bundle.

Previously: The Map's region
description no longer truncates, and the deferred
clip from the previous session is closed. The reported symptom — the final word
cut in half at 1280x720 — was the visible end of a layout that silently hid
content: the copy's `max-block-size: 45%` was a share of the *whole* column,
which also carries the tabs, two notes and four gaps, so the cap really claimed
55% of the distributable space and the only flexible row, the drawing itself,
absorbed every shortfall. Measured on this repository the map canvas was 43px at
1280x720 and **0px at 320px**, where the paragraph showed 22px of its 128px —
the layer's own explanation and its diagram were both effectively gone, and
`overflow-y: auto` on the paragraph is what made it silent, since macOS draws no
scrollbar until scrolled. The cause of the extra height was inheritance: the
inline variant kept the *floating* overlay's 28rem measure, written to avoid
covering the 3D scene, so 152 characters wrapped to four lines inside 348px of a
1236px row. The caption now opts out of the Easy reading measure, the column
scrolls instead of clipping a child, and the drawing gets a stated floor rather
than a percentage proxy. Verified against the served bundle, not just the dev
server: at 1280x720 the paragraph is whole with no column scroll and the canvas
went 43px → 82px; at 375 and 320 the copy is whole and fully visible without
scrolling and the canvas holds 80px; a 3× longer caption still never clips.
Checked in both registers, on both Map tabs, and on the Galaxy's floating
variant, which is byte-unchanged. No parser, graph, checks, progress or HTTP
behaviour was touched. 253 pytest, Ruff 0.16, 12 frontend contract checks, and a
reproducible rebuilt bundle. Previously: graph schema 8 states what Codemble
could not read. A project with
Go or Rust beside its Python and TypeScript used to render a galaxy with no sign
that a whole component was missing — the one omission a smaller galaxy cannot
show, because it looks complete. `Graph.unsupported_sources` now counts
chartable-language files no adapter claimed, and the Galaxy and Map layers state
it; nothing about those files is guessed, so they contribute no node, edge or
region. The scope rule was settled by measurement, not taste: counting every
code-ish extension reported 2 `.sh` on this repository and 7 `.sh` on FolioOrb,
where nothing is missing, while only Golavo's 7 `.rs` was a true signal. The
table covers languages Codemble's model applies to, includes supported
extensions, and only reports a file no adapter in the run claimed — so the
Phase 2 Go adapter will silence `.go` with no second list to maintain. Verified
end to end on a real 4140-node project (7 Rust reported, zero noise from 210
JSON / 101 Markdown / 94 CSV / 26 PNG) and in the running app in both registers
on both layers. 253 pytest, Ruff 0.16, 12 frontend contract checks, rebuilt
bundle. A pre-existing clip of the Map's region copy was found while verifying,
measured identical with the new note hidden, and left for its own change — since
fixed, see the top of this section. Previously: two gate repairs, no product change. CI now fails when a rebuild
of `web/` changes the committed `codemble/web_dist`, closing the one path by
which a source or design-token edit could pass every gate and still ship a
stale app to users; the `web-check` job already rebuilt the bundle, so the gate
is one step asserting the rebuild changed nothing. Proven in both directions
before landing, and the build is reproducible byte-for-byte. Ruff then moved
from the temporary `<0.16` cap to `>=0.16,<0.17` with all 35 deferred findings
triaged. Bounded on purpose: no `select` is configured, so the gate is Ruff's
default rule set and an open range hands it back to the release calendar. Two
findings were traps rather than chores — `TRY004` wanted an exception type that
`ollama_status`'s own `except` narrows on, which would have broken a function
documented never to raise, and `FURB192` touched the check generator whose
suites are pinned by a golden fixture. Parser, graph, map, and generated-check
output is byte-for-byte unchanged on an unmodified fixture; 243 pytest, Ruff
0.16 and 0.15, all 12 frontend contract checks, and the rebuilt bundle pass.
The milestone does not advance: issue #13 still requires human tester evidence.
Previously: System view now renders backend-owned, labelled orbit guides from
graph schema 7. Solid guides mean parser-proven call layers; cycles and other
structures with no certain-call route stay visible on a dashed **No proven
path** guide with `call_depth: null`, so deterministic fallback placement never
masquerades as evidence. Wide layers occupy disjoint radial bands instead of
overlapping the next layer. Check IDs now use their own stable contract version
instead of the render schema, preserving the pinned suites. Backend/renderer
contracts, the full local suite, the rebuilt packaged SPA, and live desktop/
320 px checks cover two-layer and cyclic systems. The milestone does not
advance: issue #13 still requires human tester evidence. The post-merge CI run
also exposed an unbounded Ruff dev dependency: 0.16 changed the effective rule
set and reported 35 pre-existing findings, so the gate is capped below 0.16
until that migration is reviewed separately. Previously: the public
landing's second plate demonstrates Codemble's semantic zoom with four real
shipped frames — Galaxy, Architecture Map, System, and Study — in a desktop
scroll-directed atlas stage. Compact and
reduced-motion layouts instead pair every frame directly with its explanation;
the existing tatebanko remains the one decorative signature, documentation
pages remain restrained, and no parser, graph, checks, progress, provider, app,
or release behavior changed. Browser verification covers 320, 375, 414, 768,
1280, and 1440 px, dark/light themes, reduced motion, coarse-pointer targets,
keyboard focus, production Pagefind, image loading, overflow, and console state.
Astro check/build, all 241 pytest tests, ruff, and all frontend contract checks
pass; Hallmark is 58/58 and both Standards and Spec review axes are clean after
their findings were resolved. The milestone does not advance: issue #13 still
requires human tester evidence. Previously: v0.7.0 implements all fourteen findings of a fresh evidence-based
user-flow audit of the served v0.6.4 build (run as a first-run Easy learner on
this repository at 1280/375/320, with before/after screenshots) plus the
approved D1 design direction: parser-proven import communities now wear eight
deterministic traditional Japanese colour families (galaxy stars, planets, and
Architecture-box tints), lightness-capped beneath the unlit ceiling with the
amber band excluded so understanding stays the brightest claim in the sky.
Routes on both layers moved from the 1.6:1 border hairline to a dedicated
4.0:1 route ink (possible relationships stay dashed and deliberately more
visible); the Architecture map folds modules with no route from Home into a
counted shelf behind a Show-them control; Fit fits width when whole-shape fit
would be unreadable; and Easy guidance charges test-scoped paths a bounded
+1.5-hop penalty so a learner's own code outranks its test suite at equal
distance. Mechanical fixes: the nebula dawn restores sprite scale as a vector
(it squashed the lit system's name plate square), the map's language stripe
paints via a style property (an SVG fill attribute cannot resolve var() and
silently rendered navy), Escape on the Map is a window-level handler that
works with focus on body, stale map viewports re-centre on the focus point on
restore and on live resizes, the open Key stacks below the zoom controls, the
region panel's actions no longer clip, study connection dots carry names, and
the Easy register replaces parser vocabulary end to end ("candidate 1",
"Quiz · answers come from your code, not AI", "What it is / Length /
Evidence", fixture errors attributed "all under tests/"). Parser, graph,
checks, progress, provider, and HTTP contracts are byte-unchanged; the suite
grew a nebula-dawn scale-restore check plus community-colour, viewport, and
guidance-penalty contract assertions (241 pytest, ruff clean, 12 frontend
checks, rebuilt web_dist). Full planet realism explicitly remains a Phase 3
decision under the game-art Non-Goal. The milestone does not advance: issue
#13 still requires human tester evidence. Previously: v0.6.4 closes all twenty findings of a fresh end-to-end user-flow
audit run against the served build on three real projects (Codemble, Golavo,
FolioOrb) at 1280/375/320 px with a keyboard pass. The headline fix is a
Correctness Contract one: a missed check printed the parser answer and its
evidence and then accepted that answer, so a region could light without
understanding; a miss now returns neither, and both appear only after the
learner proves it. The Easy default layer gained the reading path it never had
(**Read the source** on the Map, guidance that says read-before-prove, Escape
stepping back a level), the checks panel became keyboard-usable (focus handoff
on open, focus preserved across submits), Enter now opens the arrow-selected
structure at study level, and the guidance chip is docked into its own strip
and hidden until the first-run decisions finish. Home calibration is now a
viewport-sized modal that states its candidate count, groups candidates by
their real scope, and keeps its escape hatch on screen; the audience question
is asked once per learner instead of once per project; the star chart is
reachable from every level and closes with Escape; exits name the layer they
return to; galaxy plates and the module index use path tails; Find opens on
Home and the busiest modules; and compact Map controls no longer share touch
targets (zero overlapping interactive rectangles at 320 and 375). Parser,
graph, checks, progress, and provider contracts are unchanged except for the
deliberate withholding of answers on a failed submission. Previously, v0.6.3
closed the four follow-up findings from the earlier user-flow audit. Easy guidance is now level-aware and never offers an enabled
no-op; compact Maps open at readable 100% around Home and preserve zoom/pan
through data refreshes; Switch project confirms on the first compact-Menu click
without leaking disclosure state across project or breakpoint changes; and Home
calibration, the coach, Modules, Find, and the Star chart own explicit keyboard
focus handoffs. Parser, graph, checks, progress, and provider contracts remain
unchanged. The bundled app is verified across compact and desktop widths; the
milestone does not advance because issue #13 still requires human tester
evidence. v0.6.2 was the immediate installed-artifact fix that moved the
first-run audience modal to the document top layer, and v0.6.1 remains the
responsive learning-loop release. The v0.6.0
architecture-depth pass is complete in five
behavior-preserving waves: project selection owns the home-jailed filesystem
policy; project activation atomically owns parse-to-live binding and graph/map
caches; project mapping owns picker attempts, polling, retry, outage, stale
responses, and release; the Name Atlas owns deterministic plate placement; and
the indexed Learner Projection reuses every unaffected derived view. The
1,000-node hover benchmark moved from ~0.331 ms to ~0.001 ms per commit, while
the HTTP, graph, check, persistence, and UI contracts stayed fixed. The current
milestone does not advance: issue #13 still requires human tester evidence.
Earlier architecture-deepening maintenance completed after the verified v0.2.0
release; all four report recommendations merged in phases. The public site was
then redesigned to the Formal Edo palette and Edo star-atlas genre, with an
expanding Pagefind search shared by the landing and docs; no parser, graph,
checks, persistence, or app behaviour was touched. A tester-run rehearsal of
the shipped loop then
verified Home calibration, study source, checks, illumination, and restart
persistence end to end, and found one real defect: multi-answer checks with four
or more answers offered no wrong option, so select-all lit a region without
proving understanding. Fixed with a regression test; 17 of 107 questions on this
repository were affected and no region lost a check. The root README was then
restructured around the learning loop, fast tester setup, correctness, and the
local/AI boundary. Its top mark now uses self-contained, GitHub-safe motion with
a static reduced-motion state; no product or app behavior changed. Bare
`codemble` now serves an in-app project picker (home-jailed browse +
recents, Host-header allowlisted) instead of the current directory; README,
docs-site, the changelog, and a new PyPI release checklist now lead with
`uvx codemble` ahead of the pending first PyPI publish. A galaxy UX overhaul
design was then interviewed and approved (spec
`docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md`): three phases —
light up the shipped-but-inert narration/mode/connections surface plus project
switching, then the "living cosmos" visual overhaul with a 2D Map layer, then
~1,000-file scale with staged parse progress; four Decision Log entries record
the approved Non-Goal and binding relaxations. Phase A (the narration/mode/
connections surface and project switching) and Phase B (M12: call-depth
orbits, the 2D Map layer, and the living-cosmos visual overhaul) have both
since shipped, and were released together as **v0.4.0** (tag `v0.4.0`, published
to PyPI, verified end to end from a clean `uvx codemble==0.4.0` install: the
wheel's SPA bundle is byte-identical to the tag, all 27 regions draw unclipped,
and the galaxy renders deep space with no console errors). Phase C (M13:
~1,000-file scale with staged parse progress) has since shipped from that
plan: parsing now runs on a worker thread behind a `202`-accepted picker
select and a polled `GET /api/picker/progress` through five honest stages,
cancellation is checked between files and a crashed worker reports as an
in-app error rather than a hung server, the scale cap moved 300 → 1,000 with
the over-cap prompt offering clickable busiest scopes plus a home-jailed typed
path, a one-pass check index replaced the per-region edge scans
(byte-identical suites, pinned by a golden fixture before the refactor),
`/api/graph` and `/api/map` responses are now cached with invalidation on
light-up, Home change, and binding, and a Clear this project's progress
control was added to the star chart. A dedicated verification pass at a
realistic ~1,000-file project then found the `resolving` stage — the slowest
one — showed no moving signal for most of the wait; the fix narrates its real
sub-steps instead of leaving the screen static, and a parser hotspot found
alongside it (an O(definitions × modules) module-resolution scan in the Python
adapter) was fixed too, together taking real parse wall-clock on a 1,000-file
Python project from roughly 11.5s to roughly 7.5s with byte-identical output.
Suite hermeticity was also closed on the read side: `CODEMBLE_DATA_DIR` now
relocates the narration cache and the `config` file as well as saved progress
through one `codemble/paths.py` helper, and the test suite clears every
provider variable `from_environment` reads, so a server test can no longer make
a real billed API call against a developer's exported key. A pre-release
re-audit then closed a cluster of first-run gaps that converged on the
Easy-default learner (who lands on the 2D Map): the coach-marks and footer now
teach the layer the learner is actually on, the audience gate and coach-marks
no longer stack as two modals, the no-entrypoint Map tabs stop pointing at a
Change Home button that isn't shown, language focus now filters the Map as a
frontend projection, and a parse `bind` that outlasts a cancel can no longer
rebind a released project. Phase C plus that gap-fix wave shipped as **v0.5.0**;
the parse work collided with an independent implementation of the same three
foundational commits on `main`, reconciled by taking the branch's verified
superset while preserving main's unique `CODEMBLE_DATA_DIR`/config-isolation
fix, which lived in files the branch never touched. The Architecture map now
uses deterministic barycenter ordering and backend-routed, directional,
weight-scaled SVG paths; cycle and long-span routes use clear flank corridors,
while possible relationships remain dashed and React remains a pure renderer.
Galaxy regions now place in deterministic constellations derived only from
parser-proven import communities, with the community ID exposed in graph schema
5 and progress signatures remaining coordinate-independent. A tester then
reported the 169-system galaxy unnavigable and undifferentiated, which resolved
into four separate defects: the camera could not move at all, no star carried a
name and there was no search or index, every region route drew unconditionally
so the mesh outshone the stars, and a display-size heading plus a twelve-row
always-on legend covered the stage. All four are fixed — bounded orbit,
progressive reveal keyed to a new `hops_from_home` graph field (schema 6),
ranked and decluttered name plates, a command palette plus an index sidebar over
one shared module index, and chrome demoted to a single line with the legend
behind a disclosure. On this repository the default galaxy went from 90 systems
with their whole route mesh to 22 charted with the rest drawn faint, unnamed and
edgeless; nothing was removed from the graph and no region re-dimmed. Four
defects were caught by running it rather than by the suite: a sprite map cleared
by an effect that ran after the one that filled it, an undefined constant that
threw inside the declutter timer and silently erased every name, plates that
claimed one screen cell regardless of their real width, and an open sidebar
occluding the system panel's primary action. A fifth followed: labels offered
only one position each, directly above their star, so at galaxy zoom nearly
every plate lost its slot to a neighbour and a 90-system sky carried one name.
Names now try a short list of slots around the star and collision-test where the
plate actually draws rather than where its star sits — 1 name became roughly 24
with everything shown, 9 by default. The same navigation and clarity pass was
then applied to the Map layer, where two of the three galaxy problems turned out
to exist in a sharper form: a fixed-width box truncated the dotted region id, so
`codemble.server.app` and `codemble.server.runtime` both rendered as
`codemble.server…` — identical text for different modules — and a 960x2640
diagram sat in a plain scroll box showing four of its nine import layers. Boxes
are now named by the tail of their real path (map schema 3, zero visible-text
collisions across all 90 boxes on this repository) and the Map gained zoom, Fit,
and drag-to-pan. Progressive reveal was deliberately not extended to the Map.

### M0 — Repo, docs & website scaffold ✅ (2026-07-19)
- [x] Root: README, LICENSE (Apache-2.0), CoC, SECURITY, CONTRIBUTING,
      CHANGELOG, .gitignore, .env.example, pyproject
- [x] `.github/`: CI (pytest+ruff / astro check), Pages deploy, issue forms,
      PR template, dependabot
- [x] Package skeleton (`codemble/` with module docstrings), smoke tests
- [x] docs-site: Starlight scaffold, tokens + design.md, 12 seeded pages,
      hand-authored sidebar, brand marks

### M1 — Parser & graph ✅ (2026-07-19)
- [x] `adapters/base.py`: LanguageAdapter interface + Graph/Node/Edge/ConceptAnnotation models
- [x] `python_ast.py`: modules, functions, classes with file + line spans
- [x] Import edges (project-resolved where possible; external flagged)
- [x] Call edges by name resolution (unresolved flagged "possible call")
- [x] Entrypoint ranking (`__main__`, `main()`, app objects)
- [x] Render metadata (LOC, centrality, region id, language)
- [x] Graph JSON serialization + fixture-project unit tests

**Acceptance:** runs on a real ~50-file Python project in <5s; 20 hand-verified
edges correct; unresolved calls flagged, never dropped or invented.

### M2 — Galaxy renderer + semantic zoom (weeks 2–4)
- [x] FastAPI serves SPA + graph JSON
- [x] Galaxy level: systems/stars/routes, deterministic layout
- [x] Encoding: size=LOC, brightness=centrality, color=language, Home marked
- [x] Semantic zoom galaxy → system (tidy orbits + call edges), camera on rails
- [x] Dim/lit states rendered from graph JSON

**Acceptance:** same code → identical layout; interactive framerate at ~1k
nodes on a mid-range laptop; transitions scripted, no free flight anywhere.

### M3 — Study panel + grounded explanations (weeks 4–5)
- [x] Study panel: click planet → source with line numbers
- [x] Provider abstraction (Anthropic + OpenAI), BYO key config
- [x] Grounded prompt template (source + neighbors + annotations; contract embedded)
- [x] `file:line` links in every explanation
- [x] Disk cache by node + file hash
- [x] Graceful no-key state (galaxy + checks still work)

**Acceptance:** explanations cite only real identifiers; cache hit on re-open;
pulling the key degrades gracefully.

### M4 — Language lens + star chart (weeks 5–6)
- [x] `concepts()` for Python: decorators, comprehensions, generators, context
      managers, async/await, dunder methods, exceptions, type hints
- [x] Lens notes in study panel, anchored to detected construct lines
- [x] Star chart screen: concepts encountered vs. understood

**Acceptance:** every lens note points at a parser-detected construct at a real
location; chart updates as concepts are studied.

### M5 — Checks + illumination + persistence (weeks 6–7)
- [x] Check generator (four types), answers validated from graph only
- [x] Region "understood" flow → permanent lighting
- [x] Persistence in `~/.codemble/`; changed file re-dims only its region

**Acceptance:** no check answer ever comes from the LLM; progress survives
restart; editing one file re-dims only that region.

### M6 — Polish + first testers (weeks 7–8)
- [x] Entrypoint picker when ambiguous; scale-cap prompt (>~300 files → subdir)
- [x] Partial-parse handling (syntax errors flagged; galaxy never crashes)
- [x] README demo GIF; `pipx`/`uvx` install path
- [ ] 3–5 early testers onboarded from learner communities

**Acceptance:** a stranger runs it on their own AI-built project without help
and lights up at least one system.

### M7 — Language orchestration (Phase 1 wave 1)
- [x] Make `LanguageAdapter` discovery and file ownership explicit
- [x] Add one language-neutral `ProjectParser` interface for discovery, scale
      guarding, graph composition, Home selection, and collision rejection
- [x] Route CLI and local server through `ProjectParser` without changing the
      Python-only graph bytes

**Acceptance:** the existing Python fixture is byte-identical through the new
interface; injected second-adapter tests prove deterministic mixed graph merge,
global Home ambiguity, and fail-closed node-ID collision handling.

### M8 — JavaScript/TypeScript structure (Phase 1 wave 2)
- [x] Add official tree-sitter runtime + JS/TS/TSX grammar wheels
- [x] Parse JS/JSX/MJS/CJS/TS/TSX/MTS/CTS modules, functions, classes, methods,
      imports/exports, calls, source spans, file hashes, and partial syntax
- [x] Resolve same-project JS/TS imports and statically provable calls; label
      all approximate relationships as possible
- [x] Rank parser-proven JS/TS entrypoints and compose mixed Python+TS projects

**Acceptance:** fixture assertions hand-check exact structures/edges/spans;
syntax errors remain visible and partial; repeated mixed parses are byte-identical.

### M9 — JavaScript/TypeScript language lens (Phase 1 wave 3)
- [x] Detect JS/TS idioms only from tree-sitter nodes at exact source spans
- [x] Add learner-facing notes for async/await, arrow functions, destructuring,
      optional chaining, nullish coalescing, modules, types/interfaces, generics,
      and JSX where parser evidence exists
- [x] Keep star-chart concepts language-tagged and collision-free

**Acceptance:** every TS/JS Lens note maps to a parser annotation and real
`file:line`; malformed source yields no invented concepts.

### M10 — Polyglot focus + Phase 1 tester release (Phase 1 wave 4)
- [x] Add an accessible language focus control for mixed galaxies without
      changing graph truth, deterministic coordinates, or progress
- [x] Verify focus behavior at galaxy/system/study levels and at 320 px
- [x] Update README, public docs, packaged SPA, changelog, and release evidence
- [x] Publish and verify the Phase 1 tester release from the exact `main` tag

**Acceptance:** Python-only behavior remains intact; a mixed fixture can focus
Python, JavaScript, or TypeScript without hiding uncertainty; source install,
wheel install, web build, docs build, and downloaded release asset all pass.

### M11 — Architecture deepening maintenance ✅ (2026-07-19)
- [x] Centralize canonical graph finalization across language adapters and project composition
- [x] Deepen `ProjectParser` project intake and reuse discovered file evidence
- [x] Move learner-session transitions behind one testable frontend interface
- [x] Reuse one internal JS/TS syntax-evidence index across parser passes

**Acceptance:** existing Python and mixed graph bytes stay deterministic; project
intake avoids repeated discovery; learner transitions are tested above local HTTP;
JS/TS certainty and concept evidence remain parser-proven through the unchanged
`LanguageAdapter` interface.

### M12 — Living cosmos + 2D map (galaxy UX overhaul, Phase B) ✅ (2026-07-20)
- [x] System orbits in labelled call layers from certain intra-system calls,
      hash-seeded and deterministic; dashed fallback guides say when no proven
      path exists, and saved progress does not depend on coordinates
- [x] `GET /api/map`: deterministic Architecture and Workflow 2D layouts
      computed in `codemble/graph/`, reading the same graph as `GET /api/graph`
- [x] A 2D Map layer (Architecture + Workflow tabs) switchable from the header,
      plain SVG, no WebGL dependency
- [x] Canvas-generated halos, language-tinted nebulae, a hash-seeded starfield,
      composited bloom, and drifting particles on certain call edges only
- [x] The ~1.2s nebula-dawn light-up moment, with an instantly finished lit
      state under reduced motion
- [x] Easy mode defaults to the Map with reduced edge density and a
      graph-derived hint chip; Expert defaults to the galaxy; an explicit
      layer choice always beats the mode default
- [x] First-run coach-marks, a clickable breadcrumb, and a language-tint
      legend key

**Acceptance:** the map and the galaxy read one graph and cannot disagree;
uncertainty renders distinctly in both — colour-only in the 3D galaxy (no
line-dash support there), genuinely dashed in the 2D map; region signatures
hash file content, never coordinates, so the orbit relayout did not re-dim any
region; reduced motion always yields the finished lit state with zero
animation.

### M13 — Galaxy UX Phase C: scale ✅ (2026-07-20)
- [x] Threaded parse behind `202` select, `GET /api/picker/progress`, and a
      staged loading screen with real file counts
- [x] Cancellation checked between files; a crashed worker becomes an error
      state, never a hung server
- [x] Scale cap 300 → 1,000; clickable busiest scopes plus a jailed path field;
      suggestions in the non-TTY CLI refusal
- [x] One per-bind check index replacing the per-region edge scans, pinned by a
      golden suite fixture
- [x] Cached `/api/graph` and `/api/map` documents invalidated on light-up,
      Home, and binding
- [x] Terminal stage lines for `codemble <path>`; reset-progress control

**Acceptance:** a ~1,000-file project parses with live progress and reaches an
interactive galaxy; re-fetching the graph does not re-sort the world; the scale
prompt is actionable entirely in-app; generated check suites are byte-identical
to before the index change.

### M14 — Architecture depth and indexed learner views ✅ (2026-07-21)
- [x] Put canonical browse-root resolution, folder listing, and recent-project
      filtering behind `ProjectSelector`
- [x] Make parse-to-live binding, stale-worker refusal, release, and graph/map
      cache lifetime atomic behind `ProjectActivation`
- [x] Put picker attempts, parse polling/backoff, retry, outage, reset, and
      stale-response guards behind one Project Mapping Run
- [x] Put name ranking, camera budget, projection, slots, collision cells,
      sprite metadata, and cleanup behind one deterministic Name Atlas
- [x] Index learner projections by their real dependencies and prove hover-only
      commits reuse stable outputs; benchmark the 1,000-node case

**Acceptance:** public HTTP payloads and parser/check/persistence contracts are
unchanged; focused module suites and the existing end-to-end session/server
suites pass; the production SPA is rebuilt; the 1,000-node projection benchmark
shows lower repeated-commit work without changing derived values.

### M15 — Runtime, occlusion, and adapter lifecycle depth ✅ (2026-08-09)
- [x] Put renderer admission, scene updates, asynchronous visual work, and
      strict WebGL cleanup behind one Galaxy Runtime
- [x] Put canvas viewport and overlay-role measurement behind one Canvas
      Occlusion operation
- [x] Put shared tree-sitter discovery, parse, and finalization behind one
      private lifecycle core while preserving all five adapter contracts

**Acceptance:** React stays a shallow galaxy adapter; framing and label
decisions remain in their existing deep modules; five tree-sitter adapters keep
byte-identical canonical graph output and exact public signatures/errors; each
wave passes focused and complete gates and lands as one reversible commit.

### M16 — Parser evidence compiler and scale gates ✅ (2026-08-14)
- [x] Inject one long-lived `ProjectParser` across explicit activation release
      and reactivation
- [x] Retain only bounded process-memory per-file graph evidence with exact
      content/version/root/config identity; no captured source bytes, raw
      source-line snippet, or syntax tree is retained, and no disk cache,
      narration/LLM provider call, watcher, or background parse is added
- [x] Preserve byte-exact Graph and Map payloads across cache hits and every
      invalidation case, including dialect/config changes, cancelled
      fingerprinting, and cancellation after extraction but before acceptance;
      publish evidence and the live project under one acceptance lock
- [x] Replace repeated layout/finalization scans and materially expensive
      Study/impact/journey work with immutable indexes only under exact-output
      equivalence
- [x] Add private/source-free 1k/5k/10k benchmark receipts and a false-positive
      plus omission-detecting seven-language/mixed semantic oracle over bounded
      representative expectations, plus a reproducible Study scan control
- [x] Run the predeclared complete 5k Map gate in Chromium and WebKit; retain
      the 1,000-file cap because WebKit misses the interaction budget
- [x] Clear stale scale guidance only after successful folder navigation and
      make Finder focus wait for the committed large-Map arrival
- [x] Credit exact pinned open-source inspirations and add no copied code,
      assets, runtime dependency, account, paid service, or free-tier service

**Acceptance:** 525 Python tests, Ruff, the complete frontend contract/build,
docs check/build, the semantic oracle, and exact Graph/Map equivalence pass;
Chromium's complete 5,000-module view passes every declared budget, WebKit's
failure remains visible and prevents a cap increase, and the production SPA is
rebuilt from the reviewed source.

### M17 — Complete canvas Map and 5,000-file scale ✅ (2026-08-24)
- [x] Replace per-module/per-route SVG DOM with complete viewport-rendered
      Architecture and Workflow canvas scenes while preserving backend layout
- [x] Keep every module represented, searchable, keyboard reachable, and
      recoverable; add no logical LOD or second source of truth
- [x] Provide one focusable Map surface with directional, Home/End, and
      Enter/Space navigation plus a full-label readout
- [x] Preserve native scroll extent, zoom, fit, empty-space drag-to-pan,
      parser-owned pointer hits, responsive geometry, and reduced motion
- [x] Pass the schema-4 complete 5,000-module backend, Chromium, and WebKit gate
      before moving the ordinary cap from 1,000 to 5,000

**Acceptance:** 532 Python tests, Ruff, the complete frontend contract/build,
the semantic oracle, and exact 5,000-module source-scene counts pass; both
engines remain below the DOM, resource, usable-time, input, keyboard, recovery,
event-loop, memory, and 320 px overflow budgets; the production SPA and public
evidence are rebuilt from the reviewed source.

### M18 — Adventure launch, landings, and Ruby/PHP ✅ (2026-08-25)
- [x] Separate first-run free exploration from the existing bounded First
      Flight and durably commit Easy/Expert before guided navigation begins
- [x] Continue First Flight through an explicit parser-owned landing and the
      existing graph-derived Prove understanding route
- [x] Add an in-place Easy/Expert landing brief with real kind/span and exact
      inbound/outbound graph connections
- [x] Deepen deterministic Galaxy scenery and System world materials without
      adding free flight, semantic decoration, new progression, or new quests
- [x] Add conservative Ruby and PHP tree-sitter adapters, Lens notes, fixtures,
      ten-case semantic-oracle coverage, and pinned Rails/Laravel corpus receipts
- [x] Rebuild the bundled SPA, nine public captures, brand social card, README,
      guides, changelog, release notes, and provenance record
- [x] Preserve the blocked v0.21.0 tag as failure evidence and exclude
      developer-only `uv.lock` state from the reproducible source archive
- [x] Complete two council rounds, candidate PR CI, exact-tag v0.21.1 publish,
      outside-in artifact proof, main CI/Pages, and cold-install verification
- [x] Close the post-release free-launch focus gap with one successful
      free-only Galaxy handoff; preserve guided launch and refused-save focus
- [x] Reproduce the 320×640 Study miss after fonts settle, pin the maintained
      gate, and restore a complete 44 px connection summary with an 8 px guard
- [x] Rebuild the bundled SPA and pass 542 Python tests, Ruff, frontend
      contracts, 48 Chromium/WebKit receipts, panel reach, 29 space-budget
      states, 104 Escape assertions, and native Safari pointer/keyboard launch

**Acceptance complete:** 542 Python tests, Ruff, frontend contract/build,
semantic oracle, 48 disposable Chromium/WebKit receipts, compact panel-reach,
and the 5,000-module backend/browser budget pass. Native Safari is not claimed
for the v0.21.1 release because ScreenCaptureKit could not start its capture;
the later source correction claims only its directly repeated pointer/keyboard
launch focus. Fresh Graphify, two
council rounds, hosted candidate CI, reproducible artifacts, exact-tag trusted
publication, outside-in package proof, cold install, main CI, and Pages pass.

### M19 — Luminous galaxies and living solar systems ✅ (2026-08-25)
- [x] Keep every system visible, colourful, and contextually legible throughout
      free Explore hover and selection; retain guided dimming only for Learning
- [x] Make the parser-owned module anchor the central System Sun and provide
      parser-owned display labels for every function and class world
- [x] Give all nine parsed languages deterministic, reduced-motion-aware world
      terrain, banding, atmosphere, shimmer, tilt, and rotation profiles
- [x] Add a nearby-systems console for parser-owned inbound and outbound imports while
      preserving proven and possible certainty and direct system navigation
- [x] Reframe System around the actual world/Sun extents and both orientation
      consoles; brighten layered sky, local language depth, routes, and labels
- [x] Preserve amber as check-only, add no inferred role or structure, and add
      no XP, new quest, free-flight camera, provider, account, or cloud touch
- [x] Rebuild the bundled SPA and public captures; pass the complete local,
      browser, documentation, Hallmark, Graphify, and release-artifact gates
- [x] Complete exactly two council rounds, candidate PR CI, exact-tag v0.22.0
      publication, outside-in package proof, main CI/Pages, and cold install

**Acceptance complete:** 542 Python tests, Ruff, frontend contract/build, two
consecutive 52-receipt Chromium/WebKit journeys, 29 space-budget states, 104
Escape assertions, 5,000-module cross-engine scale, public responsive-site
acceptance, native Safari semantics, Hallmark, Graphify, exactly two council
rounds, deterministic artifacts, candidate/main CI, exact-tag trusted publish,
outside-in package proof, cold install, and Pages pass.

### M20 — Private read-only share foundation (started 2026-08-26)
- [x] Define the primary-source-backed threat model and exact requirements for
      source exclusion, label/understanding disclosure, expiry, deletion, browser
      delivery, logging, storage, provenance, and release evidence
- [x] Add one local `ShareArtifact` interface with an immutable, versioned,
      canonical RFC 8785 payload and source-safe manifest
- [x] Replace source-derived IDs and coordinates with fresh CSPRNG-seeded,
      HMAC-derived snapshot-local identities and run the existing collision-aware
      layout over the opaque graph; exclude source,
      paths, file hashes, source positions, external targets, checks, narration,
      provider state, visits, recents, and logs
- [x] Require separate label/understanding opt-ins, absolute future expiry, and a
      30-day maximum; bind the exact payload digest without self-reference
- [x] Close ordinary construction; validate schema/language/value/coverage
      bounds; recompute centrality, routes, Home distance, and orbit meaning;
      omit unresolved possible targets; fail on missing certain truth; deduplicate
      viewer edges; prove fixed-entropy order invariance and fresh-ID placement
- [x] Preview the exact local artifact and confirm each sensitive opt-in before
      any upload authority is available
- [x] Add independent unguessable view/delete capabilities, strict immutable
      storage validation, server-enforced expiry, and confirmed idempotent
      revocation behind a provider-neutral storage port
- [x] Prove HTTPS-only no-store/no-referrer/CSP browser delivery, static
      context encoding, no browser persistence or third parties, header-only
      revocation, and token-safe lifecycle/access logs in a standalone app
- [x] Add authenticated encrypted SQLite persistence with an externally supplied
      key and no adjacent key file,
      authenticated key/schema/retained-history binding, fail-closed POSIX
      permissions, durable nonce/capability-reuse refusal, transactional
      revocation, unobserved-expiry sweeping, and a finite terminal share-unlink
      mechanism
- [x] Implement the selected free encrypted backup reference with separate
      append-only writer/local operator authority, pinned restic bytes, hourly
      sweep/consistent backup, daily full-data-check/prune, process-serialized
      create-only retirement history with two repository-bound anchor receipts,
      anchored high-water-before-snapshot ordering, role-local deployment
      attestations, independent journal materialization, application-host-local
restore replay plus writer-journal rehydration before atomic promotion, stable
non-replaceable operation locking with process-level exclusion proof, exact live-inventory deletion behind a durable retirement
      seal, and bounded whole-key-store retirement authorization
- [ ] Prove the intended independent-node configuration, scheduled active
      sweeping, alerts, append-only least authority, full-data prune, backup
      restore without resurrection, complete-copy inventory, operational
      deletion, and approved key/media erasure before public release

**Acceptance is partial:** 126 focused artifact/preview/capability/HTTP/storage/operations
cases, the full 669-test Python suite, repository-wide Ruff, the complete frontend contract/build,
a live Chromium desktop exact-preview/confirmation journey, an observed WebKit
320 px journey, and the maintained Chromium 320 px share-panel reach gate,
four disposable Chromium/WebKit TLS delivery receipts covering compact rendering,
hardened success/error headers, no browser storage/service worker/third-party
request, inert reload, revocation, and token-redacted Uvicorn access logs,
documentation check/build, sample-project and current self-parse
artifact/digest/path-exclusion checks, 5,001-node/one-region and 5,000-region
scale probes, a targeted 53,478-node/one-region acceptance, and two fresh
5,000-region runs with greater than 43-unit minimum separation all pass.
Wheel/sdist inclusion with the RFC 8785 and cryptography runtime dependencies and the refreshed
Graphify update/query also pass. The browser-delivery module is not connected to
preview or a provider. M20 does not authorize a cloud touch, claim operational
erasure, or advance to release until every unchecked delivery gate is implemented
and evidenced.

## Decision Log **[AGENT-MAINTAINED — append only]**

| Date | Decision | Why |
| --- | --- | --- |
| 2026-08-30 | Share bytes have one trusted `interpret_share_artifact` consumer, while `ShareArtifact.from_graph` separately validates the parser's full routes and derives the private layout and region weights from the exact deduplicated edge marks it serializes. One `SharePreviewRun` owns choose/compile/inspect/acknowledge/confirm/restart/release state, request identity, readiness, stale-response refusal, and focus requests; `LearnerSession` owns effects and the dialog owns DOM focus only | Preview, HTTP delivery, and storage previously repeated artifact interpretation, and the session/dialog divided one learner attempt across two state machines. One closed interpreter makes schema evolution and derived facts local, while distinct raw-graph and projected-graph checks prevent line-level duplicate imports from surviving only as inflated viewer route weights. The run module gives the volatile workbench one release boundary without moving network authority or DOM behavior into it. The repository's self-parse exposed and now proves the duplicate-import projection case; the compact acceptance proves restart, confirmation, local-only truth, and focus return. |
| 2026-08-30 | M20's selected operations reference is the free/open-source Caddy + restic + rest-server topology with a writer that must anchor every terminal event to two named, distinct append-only repositories and a separately held local operator. Each receipt binds replica, authenticated repository, snapshot, and entry digest; backups bind that immutable repository inventory and the fully anchored Retirement Journal high-water to one consistent encrypted SQLite copy. Restore Guard replays later facts and rehydrates the writer journal before promotion. Final snapshot removal installs a durable authenticated seal on the existing application-host store that closes creates and writer cycles before deleting one exact live inventory, and Security Metadata Retirement re-queries that repository before authorizing whole-key-store erasure after the eight-day deadline plus 48-hour margin | This is the smallest owned topology that can prove encrypted backup, bounded retention, restore without resurrection, and separate destructive authority without introducing a paid service or a second application storage model. The writer service has no restore/prune surface; the root-only operator runs on the application host against the same live-store lock and a private mount of the independently hosted repository, and it refuses to create a missing shadow store. The primary repository identity and target must be disjoint from every journal anchor. Independent journal-node operators materialize their local repositories. Role-local credential-derived attestations prove the live repository topology, matching active/recovery storage key, and distinct authority without bringing both secret configurations into either service process; operators handle those proofs as sensitive review material. Journal writes are thread/process serialized, writer and retirement cycles share one nonblocking operation lock, restic bytes are pinned, checks read all data, and explicit inventory/removal, restore, and authorization have production CLI paths. The code, CLI, tests, and service templates are complete, but free software is not necessarily zero-cost infrastructure. Unit tests, loopback, or directories on one disk cannot satisfy independent-target failure or media-erasure proof, so M20 and a fresh release remain blocked until the intended timers, alerts, authority probe, restore/deletion drill, complete-copy inventory, and approved erasure receipt exist. |
| 2026-08-29 | Persistent share storage is one POSIX-only `EncryptedSQLiteShareStorage(root, encryption_key)` adapter behind the unchanged `ShareStoragePort`; it authenticates database/key identity and the complete record body with AES-GCM, validates the exact schema before touching an existing store, authenticates retained nonce/capability history with a keyed commitment, revalidates private modes, and owns expiry sweeping plus terminal-retention eligibility | A provider adapter should not reimplement serialization, crypto, concurrency, tombstones, or retention mechanics. Keeping the existing three-operation seam gives both in-memory and SQLite adapters the same capability lifecycle while concentrating persistence policy in one deep module. One immediate transaction initializes only a genuinely empty file; every later operation reauthenticates identity, schema, and retained guards inside the same read snapshot or immediate write transaction that owns the operation, and SQLite secure deletion is requested for record changes. Once 24 hours have elapsed after revocation or expiry, the default policy makes the share row and serving-index linkage eligible for removal on the next sweep; actual maximum includes sweep latency and remains operationally gated. Share-derived sensitive plaintext still includes internal share IDs, ciphertext lengths, nonces, and derived guards. Detached lookup/fingerprint guards and nonce reservations remain until key-store retirement so committed capabilities and encryption nonces cannot be reassigned. Tests prove concurrent exact-key binding, 120 distinct successful creates across eight adapters, reopen, wrong-key/sentinel/schema/database-replacement failure, authenticated detached history, durable nonce refusal across failed creates or deleted reservations, clock-rollback-safe revocation/expiry, unobserved expiry, revocation-relative retention eligibility, and post-purge non-reassignment. This is a local executable reference, not provider configuration or operational proof: preview and HTTP delivery remain disconnected, the key is supplied rather than managed, and an active-purge deadline, finite guard retirement, encrypted backups, scheduled sweeping, restore without resurrection, operator access, cloud deployment, and public release remain gated. |
| 2026-08-29 | The browser-delivery seam is one standalone `create_share_delivery_app` ASGI module over `ShareDelivery`: exact Host plus HTTPS admission, query-free `GET /v/<view capability>`, confirmed `POST /revoke` with deletion authority in `Authorization`, bearer removal and all-target normalization before dispatch, static context-encoded HTML, and one hardened response-header set for every outcome. `ShareDelivery` also owns a closed lifecycle-log port with structured and in-memory adapters; telemetry failure is non-authoritative and never changes capability state | Connecting the local preview to a provider before storage and erasure policy exists would widen authority, while postponing browser delivery would leave capability-URL leakage and inert-GET semantics untested. The standalone module makes the HTTP/browser contract executable without adding upload, persistence, deployment, account, analytics, or cloud state. Its CSP permits only the exact inline stylesheet hash and denies scripts, connections, forms, frames, fonts, images, and objects; Chromium/WebKit TLS receipts prove compact rendering, no cookies or other browser stores/service workers/third-party requests, reload, revocation, and Uvicorn path redaction. Lifecycle records have fields only for internal share ID, UTC time, closed operation, and closed outcome, so raw capabilities, full targets, artifacts, IP/User-Agent data, and free-form metadata have no logging interface. Making a failed sink best-effort prevents the create-log ordering from withholding capabilities while leaving active bytes; sink monitoring remains an operational deployment gate. Encrypted persistent/backup storage, provider configuration, upstream proxy/CDN/crash-trace redaction, purge deadlines, and deletion without resurrection remain the final unchecked M20 gate. |
| 2026-08-28 | **Corrects the capability-storage row below:** capability-derived view/delete record bindings authenticate the immutable metadata and artifact digest without storing either bearer secret; stored orbit meaning is independently recomputed from represented certain calls, and a valid revocation receipt remains retry-safe across a server-clock rollback | Shape and digest checks alone let a faulty adapter return self-consistent altered bytes, while a tombstone timestamp compared with the current clock made a successful revocation look invalid after rollback. Each bearer capability can authenticate only its own operation, the view binding also fixes the retained deletion binding, and semantic orbit recomputation prevents relationship-derived falsehoods before serving. Persistent encrypted/authenticated storage, purge deadlines, and operational erasure remain separate unchecked gates. |
| 2026-08-28 | The accountless capability lifecycle is one deep `ShareDelivery.create/view/revoke` module behind a three-operation `ShareStoragePort`; view and deletion each receive independent 256-bit authority, storage sees only derived lookups/fingerprints, and the reference adapter removes active bytes atomically while retaining a non-serving tombstone for retry-safe revocation | Capability generation, strict artifact revalidation, absolute server-clock expiry, uniform invalid/expired/revoked view failure, and explicit confirmed revocation are security behavior that must not be rebuilt in HTTP routes or a future provider adapter. The in-memory adapter plus an independent recording adapter make the port real without choosing a cloud. Cross-role fingerprints prevent a token from being reassigned even if a faulty entropy source repeats it; record representations suppress raw capabilities, derived lookups, and artifact bytes. This slice adds no route, link, persistent provider, encryption claim, purge deadline, deployment, account, or cloud touch; those remain the final M20 gate. |
| 2026-08-26 | Exact share preview and confirmation stay owned by the active project: one in-memory candidate, strict same-origin loopback JSON routes, and a three-step app workbench with no upload callback or delivery port | Confirmation is meaningful only if it refers to the same bytes the learner inspected. A preview ID plus payload digest binds the request to the retained artifact; replacement invalidates the older candidate, project release drops the service with the graph, and process exit erases everything. Labels and learner understanding default off and each included choice earns its own acknowledgement after the exact canonical JSON is visible. `Cache-Control: no-store`, rejected unknown/form fields, and an explicit `upload_available: false` keep the local HTTP seam narrow. The exposure ledger and artifact seal use ruri interaction semantics rather than amber, which remains understanding-only. Chromium proves the desktop journey, WebKit proves the observed 320 px journey, and the maintained Chromium reach gate proves the compact scroll cue; no provider, persistent state, bearer link, network upload, tag, or release enters this slice. |
| 2026-08-26 | M20 begins with one local `ShareArtifact` seam and no storage adapter: fresh per-artifact IDs plus graph-owned opaque placement, separate label/understanding opt-ins, a required absolute expiry capped at 30 days, and a source-safe manifest whose digest covers the exact RFC 8785 payload | `/api/graph` contains local-only paths, hashes, snippets, line evidence, external targets, learner state, and fixed source-ID-derived coordinates, so uploading it or filtering it in a caller would make privacy depend on every future call site. The deep module keeps allowlisting, keyed remapping, collision-aware re-layout, derived-truth validation, provenance, and canonicalization in one test surface. Labels-off is explicitly not anonymity: topology and orbit structure remain fingerprints. The primary-source contract requires independent view/delete capabilities, inert GET, idempotent revocation, finite purge deadlines, token-safe delivery, and authenticated storage later; no provider, route, account, or cloud request enters this slice. |
| 2026-08-26 | The v0.22.0 public surface keeps the approved Formal Edo Workbench and real product captures; this refresh tightens route truth, completes registry-checked nine-language installation coverage, adds explicit local-server recovery, and makes landing metadata canonical from one source | The full live/source pass found no visual redesign gap or release-ledger drift, so replacing the proven landing would add churn rather than clarity. It did find one concrete contradiction: Installation listed only the first seven languages' extensions while every other current surface says nine. “Fly through” and a guaranteed Home-to-surface route also outran the bounded camera and proof-break contract. The corrected copy, active-server-first recovery path, metadata and image-alt parity gate, parser-registry documentation test, and current-version checks improve first-run trust without changing package code, the app, brand, published release bytes, or fixed tag. `README.md` feeds future wheel metadata, and the tracked documentation test changes a future source archive, so locally rebuilt artifacts would differ from published v0.22.0. The test skips only when the intentionally excluded docs tree is absent from an extracted sdist. A fresh schema-4 v0.22.0 source run retains all 5,000 modules / 4,999 routes and passes Chromium/WebKit budgets with 99 DOM elements and zero compact overflow. |
| 2026-08-25 | v0.22.0 becomes stable only after the luminous Galaxy candidate passes exactly two council rounds and the complete tag-first outside-in release sequence | Annotated tag `v0.22.0` (`a3a2c5d`) peels to exact candidate commit `407a8aa`; PR #42 CI `32928613735`, trusted publish `32929397290`, main CI `32929522840`, and Pages `32929522861` are green. Fresh GitHub/PyPI bytes and `SHA256SUMS.txt` agree on wheel `ae8af55b…f0b25` and sdist `0bdba3e4…0e77`; a cold Python 3.12 install reports 0.22.0 and carries `index-C3498IDT.js` plus `index-ZndcOj-s.css`. Obscura and the maintained responsive-site gate prove the deployed v0.22.0 Pages surface. Native Safari proves the semantic Galaxy-to-System interaction but not the WebGL capture; Chromium/WebKit own that visual claim. This evidence-only follow-up must never move the fixed release tag. |
| 2026-08-25 | System navigation reports certain and possible import counts separately, labels call roots without implying a call edge, cues every overflow, and focuses the destination System heading after travel | Two council rounds found three ways visual polish could outrun evidence: a mixed route list was collectively called proven, call roots shared a ring labelled direct calls, and the fifth route looked absent behind a silent scroller. The corrected console preserves direction and certainty in visible and accessible names; orbit plans carry both `guideCertain` and `containsCallRoots`; desktop and compact overflow state the continuation; and two consecutive fresh full runs each passed all 52 Chromium/WebKit receipts, including 320 px keyboard and reduced-motion travel. |
| 2026-08-25 | Free Explore keeps the full galaxy luminous and colourful; guided Learning may soften unrelated context. The safe module anchor becomes the System Sun, structure worlds vary by parser-owned language, and connected-system navigation uses only existing import edges | The owner explicitly separated display/exploration from learning focus and requested a world-class solar-system metaphor. Visibility is not proof: amber remains check-only. Language is already parser evidence, so it can safely drive deterministic surface character; import direction and certainty already exist, so the nearby-systems console can improve continuation without inventing a connection. The bounded rail camera, one graph, and no-XP/non-cloud contracts remain unchanged |
| 2026-08-25 | A successful free first-run launch focuses the existing Galaxy application frame once after commit; compact Study's first view owns an 8 px bottom guard measured by pinned Chromium after local fonts settle | The opener-less launch modal left Chromium, WebKit, and native Safari on `BODY` even though the named `.galaxy-frame` was already the correct target. A free-only post-commit flag closes that seam without touching guided launch, hydration, later layer changes, or refused-save dialog focus. Separately, pinned bundled Chromium and system Chrome reproduced the same 320×640 geometry: the complete 44 px connection summary ended at 654 against a panel ending at 640. Compact-only inset and gap changes restore the first view without shrinking type or controls, hiding graph evidence, or changing document order. The historical v0.21.1 record is preserved; this correction is unreleased and moves no tag |
| 2026-08-25 | v0.21.1 becomes stable only after the v0.21.0 archive mismatch is preserved, repaired, and the replacement exact tag passes every outside-in gate | The v0.21.0 trusted workflow `32831002724` stopped before PyPI when an untracked local `uv.lock` polluted only the local sdist; its immutable tag remains a blocked prerelease. v0.21.1 excludes that developer file. Annotated tag `v0.21.1` (`913d641`) peels to `9f52778`; replacement candidate CI `32831499727`, trusted publish `32832515968`, main CI `32832683519`, and Pages `32832683592` are green. Fresh GitHub/PyPI bytes and `SHA256SUMS.txt` agree on wheel `ba515552…90212` and sdist `588c910f…613c0`; a cold Python 3.11 install reports 0.21.1 and carries `index-Is2yGdJX.js` plus `index-DVgxDoNx.css`. The follow-up changes only this operating truth and must never move the release tag |
| 2026-08-25 | Every First Flight stop offers an explicit **Land and learn** action that selects the first complete non-module declaration in source order, falling back to the module anchor, then hands off to the existing Study and graph-derived check flow | A system-only tour did not satisfy the requested guided learning or quiz route, and a manual canvas Enter was not guidance. Source order is deterministic parser evidence, not an invented importance rank. Reusing `SELECT_STUDY_NODE`, Study guidance, and `OPEN_CHECKS` preserves the one visit, explanation, and check pipeline without a second lesson or progression state |
| 2026-08-25 | First Flight is a tour of Home's direct proven imports, not a claim that each consecutive stop connects to the next; guided intent waits through Home calibration. Landing states parser-owned role purpose when present and explicitly unknown purpose otherwise. Semantic art channels mirror existing truth rather than becoming unlabelled decoration | Round-one outcome review found that `Home → alpha → beta` reads as a path even when only `Home → alpha` and `Home → beta` exist, that a guided choice fell through to free exploration when Home was unresolved, and that metadata-only prose could not satisfy a promise to explain purpose. The corrected tour copy, pending guided state, role-rule narration, and explicit unknown preserve the adventure without inventing an edge, a Home, or a job. Language nebulae and understood starbursts are truthful encodings, so the boundary is no unsupported fact, not no semantics |
| 2026-08-25 | Projects above 900 source files yield 650 ms before constructing the Galaxy runtime; the honest preparation state is cancellable when the complete Map takes over. Compact Study keeps the landing explanation and exact connection counts in the first viewport, with full facts and journey in document order | The 5,000-module first-run route initially spent 10.9 s building a 3D scene the scale gate would immediately replace. A bounded yield preserves immediate entry for ordinary projects and lets the existing evidence-complete renderer win without duplicate work. At 320 px, showing every connection before the explanation hid the reason for landing; progressive disclosure preserves every fact while putting meaning before inventory |
| 2026-07-18 | Learning-game identity; galaxy serves it | Resolved 3-way identity fight |
| 2026-07-18 | Galaxy IS the map in v1 via semantic zoom; free flight banned | Wonder + readable study |
| 2026-07-18 | Light gamification only (illumination + star chart) | The light-up IS the reward |
| 2026-07-18 | Phase 0 ≈ 6–8 weeks, nothing slipped | Honest budget for 3D in v1 |
| 2026-07-18 | Python first via stdlib `ast` behind adapter seam; tree-sitter later | Precision now, plugin languages later |
| 2026-07-18 | BYO Claude/OpenAI key; no Ollama | Learners can't catch a weak model's errors |
| 2026-07-18 | Local-first; no GitHub ingestion in v1 | Beginners' code isn't pushed yet |
| 2026-07-18 | Stack: Py3.11+/FastAPI/Vite+React/3d-force-graph | Solo-friendly, proven |
| 2026-07-18 | v1 scale cap ~300 files; LOD in Phase 2 | Beginner projects are small |
| 2026-07-18 | Build in public day 1; loud launch at Phase 3 | Users first, launch when ready |
| 2026-07-19 | Name: **Codemble** | Chosen by UD |
| 2026-07-19 | Repo layout, docs-site (Astro+Starlight 0.41, Pages), community files mirror FolioOrb/Golavo | Family consistency across UD's projects |
| 2026-07-19 | Apache-2.0; Contributor Covenant 2.1; Conventional Commits + DCO | Match sibling repos |
| 2026-07-19 | Brand: star-gold=understanding, orbit-cyan=interaction; observatory-instrument genre | design.md locked |
| 2026-07-19 | M1 graph adds `Edge.external`, `Node.partial`, and `Graph.partial_files` | The playbook requires external and failed parses to stay explicit; these fields prevent consumers from inferring or inventing that state |
| 2026-07-19 | One source module is one region; layout coordinates and import routes are computed in the graph layer | Progress invalidation is module-scoped and the renderer must remain a deterministic pure consumer |
| 2026-07-19 | Semantic zoom is input-driven and scripted; 3D navigation controls remain disabled | Preserves the locked no-free-flight learning contract while keeping the map keyboard-accessible |
| 2026-07-19 | `StudyService.study(node_id)` is the study seam; provider adapters expose only `complete(prompt)` | Source loading, prompt construction, validation, and caching stay local while the two true external transports remain replaceable |
| 2026-07-19 | `~/.codemble/config` accepts TOML (or JSON) and validated explanations cache by prompt/provider/model/node/file hash | Keeps BYO configuration readable and prevents stale prose after source or model changes |
| 2026-07-19 | Graph schema 2 carries parser-owned concept annotations; star-chart studied state is session-local while understood state comes only from checks | The Lens can teach exact syntax without guessing, and viewing a structure cannot masquerade as mastery |
| 2026-07-19 | `CheckService` owns four deterministic graph-only check families; `ProgressStore` owns atomic region signatures separately from the graph parser | No model can decide correctness, and changed source invalidates only the region whose file evidence changed |
| 2026-07-19 | A region with zero safe graph checks stays dim and says why instead of auto-lighting on visit | Auto-light would claim understanding without evidence and violate the Correctness Contract, so this intentionally overrides the Phase 0 playbook fallback |
| 2026-07-19 | Graph schema 3 separates ranked entrypoint candidates from selected Home; ambiguous rank-zero candidates require the learner or `--entrypoint` | Parser rank is evidence, but choosing between equal candidates is a user decision and must not be guessed |
| 2026-07-19 | Commit the production SPA under `codemble/web_dist` and bundle it in the wheel | `pipx`/`uvx` Git installs must run without Node or a source checkout; the Vite build and isolated wheel smoke test keep the bundle honest |
| 2026-07-19 | v0.1.0 is a tester release; keep Phase 1 out of NOW until 3–5 unaided learner runs pass | Technical completion cannot substitute for the human first-run acceptance criterion |
| 2026-07-18 | Owner explicitly promoted Phase 1 implementation while v0.1.0 learner acceptance continues in issue #13 | Build authorization is explicit; keeping the issue open prevents the promotion from fabricating human evidence |
| 2026-07-18 | `ProjectParser` is the one project-level interface; language adapters own file syntax and node IDs, while composition owns global Home and collision checks | The second adapter makes the seam real without leaking registry or language rules into CLI, server, graph, checks, or UI |
| 2026-07-18 | One tree-sitter adapter owns JS and TS dialects; exact paths may be certain, but extension substitution and extensionless resolution remain possible | Cross-JS/TS resolution stays local to one implementation and never upgrades a configuration-dependent guess into fact |
| 2026-07-18 | Graph schema 4 adds an explicit language to every concept annotation; the star chart keys concepts by language plus concept ID | Python and JS/TS may share names such as async/await, but their evidence and learning progress must never collide silently |
| 2026-07-19 | Language focus is a frontend projection over the immutable mixed graph, not a parser mode or saved preference | Filtering must never mutate coordinates, progress, uncertainty, or parser truth; cross-language navigation remains available |
| 2026-07-19 | v0.2.0 is tagged from exact-main commit `b6b7776` with a wheel and SHA256SUMS release asset | A release is complete only after CI, live docs, fresh download, checksum, isolated install, and mixed parse all pass |
| 2026-07-19 | Canonical graph finalization is one graph interface shared by adapters and project composition | Home selection, edge deduplication, centrality, annotation ordering, and layout are language-neutral truth and must not drift per adapter |
| 2026-07-19 | `ProjectIntake` carries one normalized scope and its adapter-owned files from scale selection through parsing | `ProjectParser` owns the 300-file policy, and adapters must not rediscover file evidence that project intake already resolved |
| 2026-07-19 | `LearnerSession` owns frontend transitions and request sequencing behind snapshot, subscription, lifecycle, and event-dispatch operations | React remains a renderer of session truth, local HTTP is replaceable, and transition races are testable through an in-memory adapter |
| 2026-07-19 | One internal `_SyntaxEvidenceIndex` owns JS/TS parse, definition, ownership, binding, and symbol lookups across parser passes | Rebuilding overlapping maps made certainty-sensitive passes harder to reason about and imported-call resolution scanned every node; the public `LanguageAdapter` seam stays unchanged |
| 2026-07-19 | Public-site palette moves to **Formal Edo** (kachi/ruri/kohaku/gofun) from `codemble_design/assets`; accent *jobs* are unchanged | UD supplied the palette and approved the redesign. Star-gold→kohaku and orbit-cyan→ruri swap values only: illumination still means understanding, interaction still means ruri. `design.md` was locked, so this entry is the approval record |
| 2026-07-19 | Site genre becomes **Edo star atlas**; landing is numbered plates in 起承転結 order, signature is a tatebanko paper-diorama hero | A canvas of dots in space is what every code-graph tool ships. The atlas makes "space exploration" and the Japanese theme one object instead of two glued together, and the four-act form is true of the content — plate three is a real turn |
| 2026-07-19 | Landing lives at `src/pages/index.astro` (standalone), replacing `src/content/docs/index.mdx` | Three of four sibling sites use a standalone landing; it gives scoped CSS and its own `<head>`, and the two files would otherwise collide on `/Codemble/`. Content moved, not lost |
| 2026-07-19 | Plate artwork is generated by a committed script from a fixed seed, not hand-authored | Geometric art needs exact coordinates and a readable diff; "same seed → same sky" mirrors the app's determinism rule. Output is committed so the site never runs it at build time |
| 2026-07-19 | One expanding `Search.astro` serves both the Starlight header and the landing nav | Family convention (Golavo and FolioOrb each override this slot). Pagefind only exists post-build, so the field states that in dev rather than failing silently |
| 2026-07-19 | Every check must offer a wrong option; a question the graph cannot supply one for is dropped, not asked | A four-or-more-answer check offered only its own answers, so select-all lit a region while proving nothing. Correct answers still came from the graph, so the Correctness Contract held — but illumination stopped meaning understanding, which is the product's core claim |
| 2026-07-19 | The app self-hosts the Formal Edo faces; it never loads the site's Google Fonts CDN | `web/src/tokens.css` imports the site's tokens, so the redesign silently changed the app's requested faces. The app is local-first and says "Local only" in its own footer, so a CDN request would break offline use and contradict that promise |
| 2026-07-19 | Understanding owns the top of the canvas brightness range: the unlit centrality ramp caps at `--cm-ink-2` and lit stars use `--cm-star-high` | Lit at 8.5:1 sat below the unlit ceiling of 17.4:1, so a busy un-understood module looked more lit than an understood one. Approved by UD; uses existing tokens only, so `design.md` is unchanged |
| 2026-07-19 | Canvas palette values are resolved to `rgb()` before they reach WebGL | A custom property returns its authored text, so `color-mix()` tokens rendered black — silently hiding unchartable nodes and every "possible call" edge, which the Correctness Contract requires to stay visible |
| 2026-07-19 | The root README uses a self-contained animated ensō mark; app icons and favicons remain static | GitHub strips page-level scripting, so motion belongs inside the referenced SVG. The loop is restrained to illumination, transforms, and opacity, and reduced-motion users receive the finished lit state |
| 2026-07-19 | Bare `codemble` serves a one-shot in-app project picker (browse + recents) on a single two-phase server; binding is one-shot and the API is home-jailed with a Host-header allowlist | Approved by UD this session: easiest possible run flow for learners without a second server, without free filesystem enumeration, and without changing the one-graph app model |
| 2026-07-19 | Codemble publishes to PyPI from the next tagged release; install collapses to `uvx codemble` | Approved by UD this session: the git+tag install was the biggest onboarding hurdle for the target learner |
| 2026-07-19 | Local models (Ollama) are now allowed, reversing the 2026-07-18 Non-Goal; guardrails: loopback-and-`http`-only enforced at construction, explicit opt-in with no auto-detection, the same grounding validation applied to every provider, and the deterministic Tier 0 summary always available as a floor | Approved by UD this session. Residual risk stated honestly: grounding validation catches an invented identifier, not a wrong claim about a real one, and small local models make that second kind of error more often |
| 2026-07-19 | A 2D Map layer (architecture + workflow-tree tabs) joins the 3D galaxy behind one switcher, superseding the "no second 2D renderer in v1" Non-Goal; layouts are computed deterministically in the graph layer and React stays a pure SVG renderer | Approved by UD in the galaxy UX overhaul interview (spec `docs/superpowers/specs/2026-07-19-galaxy-ux-overhaul-design.md`); beginners read flat maps more easily and the render-ready graph rule makes the second view cheap and truthful |
| 2026-07-19 | Scale target raised to ~1,000 supported files with a worker-thread parse, polled staged progress, and an honest loading screen; the subdirectory prompt moves to the new cap | Approved by UD: a deliberate partial pull-forward of Phase 2 scale work; full LOD/clustering stays in Phase 2 |
| 2026-07-19 | One-shot project binding relaxed to an explicit in-app reset (`POST /api/picker/reset`); home jail and Host allowlist unchanged | Approved by UD: learners must be able to switch projects without killing the server; per-project progress makes switching safe |
| 2026-07-19 | App art direction is "living cosmos" within the Formal Edo palette: halo sprites, bloom, hash-seeded starfield, language-tinted nebulae, call-depth system orbits (layout bytes change once, still deterministic), and an Easy/Expert UI toggle riding the shipped audience-mode backend | Approved by UD section-by-section; amber keeps its monopoly on understanding, uncertainty stays dashed in both layers, and Easy-mode guidance is graph-deterministic (nearest unlit region by route hops), never model-decided |
| 2026-07-20 | System orbits are call depth from the module's entry node, with the seed widened to include members no sibling calls | A module node makes no intra-project calls, so the spec's literal seed was always empty and stranded every member in the outermost ring. Both spec rules are preserved: the entry's callees are ring 1, and unreachable members take the outermost ring by node id |
| 2026-07-20 | The workflow tree's first hop is labelled `defines`, not `calls` | The selected entrypoint is usually a module, and the parser observed no call from a module to its own function. Containment is real parser truth (`Node.region`); relabelling it a call would have invented an edge |
| 2026-07-20 | Nebula tints ship lighter than the values in the design spec | The spec's starting values measured 3.19–4.46:1 against `--cm-ground-2` and failed the 4.5:1 legend floor. Hue is held; only lightness moved, and all three stay below `--cm-ink-2` so amber's monopoly is intact |
| 2026-07-20 | Bloom resolution is capped with `composer.setPixelRatio(1)`, not the `UnrealBloomPass` constructor | `EffectComposer.setSize` forwards the canvas size to every pass on resize, overwriting the constructor's `resolution`. The pixel ratio is the cap that survives |
| 2026-07-20 | **Corrects the row above**: bloom is capped by wrapping the bloom pass's own `setSize`, and the composer keeps the renderer's pixel ratio | The pixel ratio *did* cap bloom, but `EffectComposer.setSize` multiplies it into `renderTarget1/2` and every pass, so the whole scene rendered at 1x and upscaled — measured 1280x611 scene passes on a 2560x1221 buffer at dpr 2. Wrapping the one pass caps the one expensive thing: scene now 2560x1221, bloom mip 0 800x382 (1280x611 uncapped), `?benchmark` at 951 nodes unchanged at 928.8 → 961.5 fps median |
| 2026-07-20 | **Corrects "binding is one-shot"** (2026-07-19 picker row): binding is one-*at-a-time*. `serve_project` attaches `PickerConfig(browse_root=Path.home())` too, so a `codemble <path>` run also exposes the picker endpoints after a reset, and browse then enumerates non-hidden directories under `$HOME` | The Switch project control has to work without a process restart, which is what that config is for — but the earlier row still claimed a permanent 409 for the path-opened flow, and this file is the source of truth. The home jail and the Host-header allowlist are unchanged; only the "one-shot" claim was false. An app built with no `PickerConfig` at all remains genuinely one-shot and refuses reset |
| 2026-07-20 | `CODEMBLE_DATA_DIR` owns every home-directory path — progress, the narration cache, and the `config` file — through one `codemble/paths.py` helper; the test suite additionally clears every provider variable `StudyService.from_environment` reads | The variable redirected progress only, while `StudyService` hardcoded `Path.home()` for the other two, so `create_app`'s default study service read the developer's real config and `ANTHROPIC_API_KEY`. Two server tests GET `/explanation` and assert only that a `status` key came back — true of `no_key`, `ready`, and `error` alike — so on a machine with a key they made a real billed API call and cached the reply under the developer's home while still passing. Redirecting the directory does nothing about the process environment, which is why the suite must clear the keys as well. No new variable is introduced, the default stays `~/.codemble`, and explicit `environ`/`config_path`/`cache_root` arguments still win over both channels |
| 2026-07-20 | Progress reporting is a thread-scoped per-file hook (`note_file_parsed`) bound by `ProjectParser`, not a new `LanguageAdapter` parameter | The public adapter seam must stay unchanged for Phase 2 languages; one hook site per adapter also gives cancellation its exact "between files" meaning |
| 2026-07-20 | Phase C adds `DELETE /api/progress`, the `CLEAR_PROGRESS` session event, and a `clearProgress` adapter method beyond the shared contract's Phase C rows | The contract's Phase C rows covered parse progress only, while the no-reset-progress-control gap is mapped to Phase C by the spec; recorded here rather than silently widened |
| 2026-07-20 | Generated check suites are pinned by a committed golden fixture before any performance work touches `checks/service.py` | The Correctness Contract makes suite drift top-severity, and a refactor that changes an answer is invisible without a byte-level pin |
| 2026-07-20 | Architecture map edges get backend-computed ports, barycenter ordering, arrowheads, and weight-scaled strokes; `MAP_SCHEMA_VERSION` 2; directory groups stay payload metadata | Within-layer order was arbitrary and direction was invisible in 2D while being parser truth; ordering stays deterministic (fixed sweeps, sorted ties); group containers wait for hierarchical layout |
| 2026-07-20 | Galaxy regions place by deterministic import-community constellations (pure-Python label propagation in `layout.py`); `community` is an additive Region field; layout bytes change once | Hash-order placement scattered coupled modules; communities are parser-truth-derived and deterministic; progress signatures hash file content so nothing re-dims (M12 precedent) |
| 2026-07-21 | **Bounded orbit** replaces the fixed camera, amending the free-flight Non-Goal: `controlType('orbit')` with panning disabled, per-level distance clamps, and clamped polar angle. The wheel becomes zoom; level changes move to click/Enter/Escape/breadcrumb | Approved by UD after a tester reported the galaxy unnavigable. Panning is the one degree of freedom that can strand a learner in empty space with nothing to navigate back by, so it stays off — rotation and zoom are clamped instead, which keeps "you cannot get lost" true. One gesture cannot mean both zoom and change-level, so the wheel's old meaning had to move |
| 2026-07-21 | Galaxy uses **progressive reveal**: floor (within 2 import hops of Home) ∪ neighbours of every lit region ∪ the current selection's neighbours, with a persisted Show-all toggle. An unrevealed region is drawn faint, unnamed, edgeless — never removed | Approved by UD. 169 systems and their whole route mesh was the hairball; dropping the *edges* of what is not yet charted thins the sky without a separate density control. Regions stay drawn and clickable because hiding one would misreport the project's size, which is precisely the kind of wrong a learner cannot detect. Reveal is recomputed from proven progress, never stored, so it cannot drift out of step with it |
| 2026-07-21 | `Region.hops_from_home` is graph-layer truth (schema 6): undirected BFS from Home over proven import routes, `None` when unreachable; `with_entrypoint` recomputes it | Reveal is game logic and belongs in `LearnerSession`, but the *distance* is a fact about the project and belongs in the graph. The frontend was already re-walking this exact BFS for the Easy-mode hint, so the two could in principle have disagreed about one number; there is now one source. `None` is never softened to a large number, or "unreachable" would read as "very far" |
| 2026-07-21 | Canvas name plates are ranked (Home → lit → centrality), budgeted by camera distance, and decluttered by claiming the full screen-cell rectangle each plate covers | A name is the cheapest differentiation there is and the sky had none. Claiming one cell per plate let a wide name cover three neighbours, and claiming only a row let two plates straddling a boundary collide — the rectangle is the only version that actually holds. Plate geometry is published on the sprite by the module that sizes it, so the constant is not duplicated across files |
| 2026-07-21 | Finding a module is a command palette **and** an index sidebar over one shared `moduleIndex`; sidebar rows show each path minus its group's shared prefix | Approved by UD. Progressive reveal makes targeted retrieval mandatory — a thinned sky must never hide a module from someone who knows its name — and both surfaces reach every module whether charted or not. Basenames alone are useless in a Python project where every package carries an `__init__.py`, so rows keep enough real path to be told apart |
| 2026-07-21 | Progressive reveal stays **galaxy-only**; the Map always draws every module | Approved by UD when the navigation work was extended to the Map. The Map's job is "how it all fits together", and a layered import diagram with holes in it teaches less than a complete one; the galaxy already offers the thinned view for learners who want it |
| 2026-07-21 | Architecture boxes are named by the tail of their file path (`short_label`, map schema 3); `label` keeps the full identifier for title and aria | A box is a fixed width, so its text always truncates on a real project — and truncating a dotted region id rendered `codemble.server.app` and `codemble.server.runtime` as the same glyphs. Identical text for different modules is worse than no label, and it is exactly the kind of wrong a learner cannot detect. The path tail also survives the `__init__.py` collision a basename alone cannot |
| 2026-07-21 | The Map gains zoom, Fit, and drag-to-pan; panning rides the container's own scroll and zoom only scales the rendered size | The 2D counterpart of bounded orbit: a 960x2640 diagram in a plain scroll box showed four of nine layers and no way to see the whole shape. Scroll-based panning keeps native scrollbars, keyboard scrolling and screen-reader behaviour intact, and because every coordinate inside the SVG stays backend-computed, React remains a pure renderer of graph-owned geometry. It opens at true size rather than auto-fitting: fitting on mount measured the scroller before layout settled and landed on a scale that was neither fitted nor honest |
| 2026-07-21 | v0.6.0 deepens five private boundaries without changing the HTTP, graph, check, persistence, or learner-visible contracts: Project Selection, Project Activation, Project Mapping Run, Name Atlas, and Learner Projection | Approved by UD as five behavior-preserving waves in one release PR. The deletion test now holds at each seam, stale activation and mapping responses lose atomically, and dependency-scoped learner projections measured ~0.331 ms → ~0.001 ms per hover commit on a synthetic 1,000-node project while preserving derived outputs |
| 2026-07-21 | v0.6.1 treats Modules and Find as global surfaces, sequences first-run decisions as audience → required Home → coach, and makes the 3D parser-owned layout explicitly non-draggable | Approved by UD as implementation of every verified user-flow audit finding. Global commands must never accept hidden state, onboarding must expose one foreground decision at a time, and learners orbit the immutable graph rather than editing its coordinates. The compact shell is a structural breakpoint of the existing Formal Edo interface, not a new visual system |
| 2026-07-21 | First-run audience modal portals to `document.body`; the persistent Easy/Expert toggle remains in responsive header chrome | A native modal inside the closed compact Menu entered the top layer but inherited `display:none` from its ancestor, leaving an invisible backdrop that blocked fresh mobile runs. Modal ownership is a document boundary, not header layout. Caught only by the clean public v0.6.1 installed-artifact smoke; PyPI immutability requires v0.6.2 rather than replacing 0.6.1 |
| 2026-07-21 | Easy guidance actions are derived from level, region, and layer, then executed by `LearnerSession`; the chip renders no button when the next step is already on screen | React must not guess a structure or own navigation truth, and an enabled action that commits the same state is a false promise. The nearest unlit region remains graph-derived; only the honest route to it changes with the learner's current context |
| 2026-07-21 | Map zoom/pan is renderer-local state keyed by tab and Home, preserved through transient data remounts but cleared with the project lifecycle; compact Maps start at 100% centred on the parser-backed target | Auto-fitting made 56 px boxes as little as 8–18 px tall and re-ran after check-driven map refreshes. Fit is still a valid explicit overview, while session state stays reserved for graph and learning truth |
| 2026-07-21 | Responsive disclosures and global surfaces own explicit focus handoffs; compact Menu closes on project exit and when crossing to the desktop rail | DOM focus and disclosure visibility are view concerns, but leaving focus on removed or hidden controls makes a successful navigation indistinguishable from a dead action to a keyboard or screen-reader user |
| 2026-07-21 | A wrong check submission returns no answer, no answer labels and no evidence; all three are returned only once the learner answers correctly | The response printed the parser answer on every miss and the same question then accepted it, so a region could light on an answer the app itself had just displayed — illumination stopped meaning understanding, the same failure class as the 2026-07-19 "every check needs a wrong option" fix. Evidence is withheld with the answer because an importer check cites exactly the files that *are* its answer |
| 2026-07-21 | The 2D Map gets a reading path: region focus offers **Read the source** beside the checks, Easy guidance recommends reading before proving, and Escape steps back a level there as it does in the Galaxy | Easy mode lands on the Map, where the only action was a quiz about code the layer could not show. The study panel is layer-neutral (`/api/node/:id/study`), so the Map only needed to select the module node the parser already produced — no new truth, and the audience that most needs to read first stops being sent to another layer to do it |
| 2026-07-21 | The audience answer is stored per learner as well as per project (`learner.json` beside progress); a fresh bind seeds from it and skips the gate, while the header toggle still overrides one project | The gate asks who the *learner* is, but the answer lived only under the project key, so every new project re-asked an expert whether they were new to coding. The file carries no `schema_version`, which is what keeps recents from reading it as a project |
| 2026-07-21 | Home calibration is a native modal sized to the viewport, grouped by the candidates' real top-level scope, with the candidate count stated and "Explore without Home" outside the scrolling list | It is the second step of the same required sequence as the audience gate and deserves the same shape. As a card capped to a share of the stage it showed one candidate of eleven with the escape hatch thousands of pixels below the fold, and a flat list put `tests/fixtures/...` beside the learner's entrypoint with nothing to tell them apart. Scope and rank are parser facts already in the payload; the leading group always opens so a project whose best candidate is rank 1 is never met by an all-collapsed list |
| 2026-07-21 | Galaxy name plates use the same path-tail rule as map schema 3's `short_label`; the shared module index and the command palette use it too, and the palette's unfiltered order is Home → lit → centrality | Basenames collide hard in a Python project — every package carries an `__init__.py` — so identical plates named different modules, which is precisely the wrong a learner cannot detect, and the palette opened on a screen of indistinguishable rows |
| 2026-07-22 | **Hue means import community.** Each parser-proven community takes one of eight traditional Japanese colour tokens (`--cm-com-0..7`) by `community id mod 8`; stars, planets and Architecture boxes all read the same arithmetic in `graphData.communityShade`. This amends the M2 encoding row: colour was "language", which is now the nebula/stripe channel only | Approved by UD. The sky had one hue for 109 systems, so nothing could be tracked without reading every plate — and the graph had proven communities since schema 5 that nothing rendered. Guardrails that keep the Correctness Contract intact: every token is lightness-tuned to `--cm-ink-2`'s luminance (0.389) so a lit star at 0.598 always wins, the kohaku band (~40°) is excluded so no community can read as "understood", a missing community id falls back to the old neutral ramp rather than borrowing a hue, and the mapping is pure arithmetic on graph truth so the same code always yields the same sky |
| 2026-07-22 | Routes get their own ink (`--cm-route`, 4.0:1) on both layers, and it sits deliberately BELOW `--cm-route-possible` (6.4:1) | Edges borrowed `--cm-hairline`, the ink of box borders and panel rules, measuring 1.57:1 on the canvas ground — the relationships the product exists to teach were its least visible marks, which is the literal complaint that opened the audit. Ordering the two inks this way keeps the 2026-07-19 rule that an unproven claim must be the more visible one |
| 2026-07-22 | Architecture-map modules with no import route from Home fold into a counted shelf behind an explicit control (auto-folded above 8), and Fit fits WIDTH when a whole-shape fit would land below 35% | On this repository 80 of 109 boxes are test fixtures and scripts, making the drawing 1:3.2 tall so the connected core fit at an unreadable 7%. Folding is view state, never truth: the note carries the exact count, **Show them** draws every one, and both surfaces still reach every module. Distinct from progressive reveal, which stays galaxy-only |
| 2026-07-22 | Easy guidance charges test-scoped paths a bounded +1.5-hop penalty; the displayed hop count stays the real one | A CLI's nearest neighbour is usually its own test suite, so pure hop-distance sent a brand-new learner from Home straight into `tests/`. The penalty is bounded so a non-test module one hop farther wins while a distant one does not, and an all-tests project is still guided. Both inputs stay parser truth (the BFS count and the recorded file path); only the ranking key is biased, never the reported fact |
| 2026-07-22 | The public landing may use a desktop Atlas Journey that crossfades and settles real Galaxy → Map → System → Study product frames; compact and reduced-motion views are static, and the tatebanko remains the sole decorative signature | Approved by UD for the Apple-level public-site refinement. The choreography demonstrates the shipped semantic zoom instead of adding decorative motion: one `IntersectionObserver` selects normal-flow copy steps, overlapping media is presentation-only, and every screenshot/capability remains product-truthful. Documentation pages and the app stay outside the effect |
| 2026-07-27 | Graph schema 7 serializes each node's `system_orbit` (`ring`, exact `radius`, proven `call_depth`, and `origin` / `call-root` / `certain-call` / `unreached` kind); System view labels solid proven layers and a dashed no-proven-path fallback, while overflow circles occupy disjoint radial bands | Approved by UD as the high-confidence implementation. React must not reverse-engineer meaning from XYZ, and deterministic outer placement for a cycle must not masquerade as a parser-proven call depth. The previous fixed-radius formula also placed a layer-1 overflow circle and layer 2 at the same radius |
| 2026-07-27 | Generated check IDs use an independent check-contract version seed rather than `Graph.schema_version` | Graph schema 7 adds render metadata but changes no question, answer, option, or evidence. Coupling learner-flow identity to an additive renderer contract churned every ID and failed the pinned golden suite; the check seed now changes only with an intentional check-contract change |
| 2026-07-27 | The `dev` extra caps Ruff below 0.16 until a deliberate repo-wide lint migration | CI resolved the previously open-ended `ruff>=0.6` dependency to 0.16 and immediately activated 35 existing findings across unrelated modules, while the established 0.15 gate remained clean. A linter release must not change the merge gate by calendar date |
| 2026-07-27 | CI fails when a rebuild of `web/` changes the committed `codemble/web_dist` | The bundle is a build artifact that is committed *and* shipped inside the wheel, so the Gotchas rule "a token change only reaches users after `npm run build` is re-run and the result committed" was enforced by human memory alone. The `web-check` job already rebuilt it and discarded the result; asserting on that result costs one step. Verified both ways before landing — a deliberately stale bundle fails, the current tree passes — and the build is reproducible (a fresh build reproduces the committed bundle byte-for-byte, same content hashes) |
| 2026-07-27 | Graph schema 8 states what Codemble could **not** read: `Graph.unsupported_sources` counts chartable-language files no adapter claimed, keyed by extension, named only where the extension is unambiguous | Approved by UD. Inventing nothing is only half the Correctness Contract — a galaxy drawn from part of a project looks exactly like one drawn from all of it, so a Go backend beside a TS frontend rendered as a complete TS galaxy. This is the `partial_files` precedent applied to the other kind of omission: a count, never a node, edge or region. Scope was decided against measurement rather than taste — counting every code-ish extension reported 2 `.sh` on Codemble and 7 `.sh` on FolioOrb, where nothing is missing, and only Golavo's 7 `.rs` was a true signal, so the table covers languages Codemble's model applies to (modules, functions, classes, imports, calls) and shell/SQL stay out. The table includes supported extensions and a file is only counted when no adapter in the run claimed it, so the Phase 2 Go adapter will silence `.go` with no second list. `.h` and `.m` report without a language, because naming one would be the guess the contract forbids |
| 2026-07-27 | The unsupported-source note renders on the **Map** as well as the Galaxy, and survives a language focus | Easy mode defaults to the Map, so a galaxy-only orientation bar would have hidden this from exactly the audience least able to notice the gap — the same failure the Map's "Read the source" fix addressed. The count is a project-level fact passed down from the graph rather than added to the map payload, so the two documents cannot disagree; a language focus filters nodes, and must not filter a fact about source that was never parsed at all |
| 2026-07-28 | The desktop rail gives the actions a full-width second row and the layer/audience controls the row-1 corner; the compact panel's placement reset is scoped to `@media not all and (min-width: 40rem)` | Approved by UD over two more ambitious variants. The six actions need ~883px and had ~495px, so they wrapped to two rows while the controls used 370px of the 1236px row below — 221px of a 720px window spent on chrome around a stage that then squeezed the map canvas to 82px. Swapping which row holds what removes no control, adds no component, and needs no overflow menu: measured rail 221→161px and canvas 82→142px at 1280x720 Easy, and it is a bigger win at narrow desktop widths, which were quietly far worse (640px 511→271px, 768px 451→271px). The scoping fix is the real repair: `.rail-overflow__panel .rail-actions` kept matching above 40rem where the panel is `display: contents`, and at (0,2,0) it outranked the (0,1,0) rules in the min-width block, so those were dead and the desktop rail was laid out by auto-placement. `not all and (min-width: 40rem)` is the exact complement of the existing breakpoint, so no width falls through; the 639/640 boundary was checked in both directions and the compact Menu is unchanged. A single row is arithmetically impossible here — brand + breadcrumb + actions alone is 1290px against 1236px — so anything further would have to hide controls behind a desktop overflow |
| 2026-07-27 | The Map column scrolls when over-subscribed; the drawing keeps a stated `min-block-size` floor; and the region caption opts out of the Easy 46ch reading measure. This **replaces** the copy's `max-block-size: 45%` and its inner `overflow-y: auto` | A percentage of the whole column was the wrong guard: the column also carries the tabs, two notes and four gaps, so "45%" claimed 55% of what was actually distributable, and the drawing — the only flexible row — absorbed the rest, measuring 43px at 1280x720 and 0px at 320px. The cap therefore failed at the one job its comment claimed. Clipping *one child* is also the wrong failure mode for a layer whose Easy default is a learner's first screen: the inner scroll left the region's own description reachable but invisible, because macOS draws no scrollbar until scrolled, so it read as a rendering bug rather than as more text. The extra height was inherited, not intrinsic — the inline variant kept the floating overlay's 28rem measure, which exists to avoid covering the 3D scene and buys nothing for a row above a drawing, wrapping 152 characters to four lines inside 348px of a 1236px row. A caption is not a surface read at length, so it may run wider than prose. Verified on the served bundle at 1280/375/320 in both registers and on both tabs; a 3× longer caption scrolls the column rather than hiding a word |
| 2026-07-27 | **Completes the row above**: Ruff moves to `>=0.16,<0.17` with all 35 findings triaged; four rules are suppressed per-site with a stated reason rather than globally | The cap stays bounded because no `select` is configured, so the gate is Ruff's *default* rule set and an open range still hands the merge gate to the release calendar. Suppressions are per-site so the rule keeps working everywhere it fits: `TRY004` ×2 would have been an actual regression — `ollama_status` promises never to raise, and its `except` narrows on the very `ValueError` the rule wanted replaced; `BLE001` guards a worker thread where a missing catch-all strands the picker on "parsing" for ever; `FLY002` would repeat the NUL separator five times inside a cache key. `B023` ×4 were false alarms (the sort consumes the closure in-iteration) but were fixed by binding anyway, so correctness stops depending on where the function happens to be called. Byte-identical parser, graph, map, and check output proven on an unmodified fixture |
| 2026-07-28 | Desktop keeps four permanent header actions; **Change Home** and **Switch project** move behind the existing compact disclosure, relabelled **More** at `min-width: 40rem` | Approved by UD. This narrows the 2026-07-21 "global surfaces" entry to the surfaces that entry actually names — Modules, Find and the star chart — and leaves the two occasional controls one click away. Measurement, not preference, forced it: six buttons need 913px on this repository and no column a 1280px header can offer them exceeds 522px, so they wrapped to two 44px lines and pushed the controls to a second row, spending 221px of a 720px viewport. Freeing the wasted width buys 0px on its own, and every genuine one-row layout ellipsises or erases the breadcrumb — a 1280px test crushed it to 0px, the `short_label` failure class applied to "where am I". Reusing the one disclosure keeps a single open state, Escape handler and focus return rather than a second copy of all three |
| 2026-07-28 | The Map's two `.map-note` rows stay full always-on prose; only the header, the actions row and the guidance strip yield | Deliberate scope refusal, recorded because the approved scope named the notes. They render *below* the canvas, so measurement shows they push nothing: at 375 the drawing's visibility is set entirely by the tabs and the region copy above it. Their only cost is scroll length in a column that already scrolls by design (55147ac), and the trade for that is putting a Correctness-Contract fact — what Codemble could not read, and how many modules no route reaches — behind an interaction. A count that must be stated is worth more than 116px of scrolling |
| 2026-07-28 | The rail's wide layout starts at `min-width: 64rem`, not 40rem, in its own media block | Measured, the wide arrangement was worse than the compact shell everywhere below 1024px: 199px of rail at 768 and 319px at 640, against 124px compact at both. Below that width the brand, breadcrumb, four permanent actions and the More trigger cannot share a row, and the actions -- pinned to the leftover column -- wrap to three and four lines. A layout that loses to the one it replaces should not run there. The rail rules were lifted out of the 40rem block, which also carries unrelated study-panel and status-line rules, so the two breakpoints stay independent; the compact reset's `not all and` complement moved with it, so no width falls through both |
| 2026-07-28 | An open rail disclosure owns Escape: the window-level handler yields to `.rail-overflow[data-open]` as it already yields to `dialog[open]` | The handler bails for the finder, sidebar, checks, entrypoint picker and native dialogs but never for the rail, so Escape closed the Menu *and* retreated a level in one keypress. It was always wrong and only compact widths could reach it; making the disclosure exist at desktop, where Escape is the documented way back, made it ordinary. Read from the DOM rather than session state because the disclosure's open state is view-local — the same reason the dialog check beside it is a DOM query |
| 2026-07-28 | `unsupported_sources` counts a file only when **no adapter recognised its extension**, not when no adapter claimed the path | An adapter that skips a file as generated output has still read the extension, so the file was excluded on purpose rather than missed. `_ignore_project_directory` prunes a directory only when *every* adapter ignores it, and Python's ignore set is empty, so `codemble/web_dist` was always walked and its bundled `.js` fell through to the tally. The galaxy and map then told a learner "1 JavaScript file not included" about the app's own committed SPA — a false claim in the exact channel graph schema 8 added to be truthful about coverage, and one the v0.8.0 changelog already advertised as handled ("registering an adapter automatically silences its own extension"). Recognition is the honest test; ownership is not |
| 2026-07-28 | `.mobile-menu-trigger` sets its own `background`, matching `.rail-action` | The rule set border, radius, colour, cursor and weight but no background, so the UA's `buttonface` (#efefef) won and ruri text sat on it at **2.0:1** — under the 4.5:1 floor `design.md` mandates. It was wrong at compact widths from the start, but v0.8.0 promoted the control to every desktop width as **More**, which is how it reached all seven product screenshots as a light slab in a dark navy header |
| 2026-07-28 | The product shots are captured from a git worktree named `Codemble`, at 1440x720, with `loading.png` excluded | The brand line renders the project directory's own name, so serving a worktree published `silly-swanson-53d316` to the docs. Capturing at 720 rather than the old 716 is one round number, but it couples: `AtlasJourney.astro`'s two `height` attributes and `landing.css`'s `aspect-ratio` both encode the frame and must move together or the atlas plate letterboxes. `loading.png` is a pre-app, full-window state with no header, from a different rig and a synthetic 900-file project, so no shell change can affect it and its counts are not this repository's |
| 2026-07-29 | `Fit` resolves to the most zoomed-out **readable** overview (`mapOverviewZoom`), replacing `fitMapWidthZoom`'s `Math.min(1, …)` ceiling | The ceiling read as "never inflate a small drawing past its crisp size", but on any viewport wider than the drawing it returned exactly `1` — the scale the map already opens at. So Fit was a silent no-op at 100% and an actual zoom *in* from anywhere below it: 64% → 100% cut the visible diagram from 33.5% to 21.5%. The control that promises the whole shape was the one hiding more of it. Where the drawing is wider than the viewport the old width-fit behaviour is preserved exactly; where it is narrower there is no width left to fit, so it drops to the readable floor (21.5% → 61.4% at 1440x720). The check states it as a property — from any scale at or above the floor, Fit must not zoom in — rather than as a number |
| 2026-07-29 | The breadcrumb's top crumb is **"All modules"**, not "Galaxy" | The breadcrumb names the semantic-zoom *level* and the switcher beside it names the render *layer*, and both said "Galaxy". An Easy learner lands on the Map, so their first screen showed `aria-current="page"` Galaxy in the breadcrumb while the switcher 30px below reported Galaxy `aria-pressed="false"`: two visible controls, one accessible name, contradictory state, answering "where am I?" wrongly half the time. The level is about scope, so it can say so without borrowing the renderer's word |
| 2026-07-29 | The **window-level** Escape handler dismisses an open panel before it retreats a level, instead of bailing out for each one. Panel-local handlers are removed | The bail-outs assumed each panel would own the key from its own subtree. The checks panel and the module index never claimed it, so Escape there did nothing at all — while the coach marks teach "Escape to come back" — and every panel that *did* claim it double-fired, because the window handler reads the session at event time and the panel's own close has already cleared the flag it bails on: closing the star chart from inside a module also retreated a level. A panel-local handler cannot be the fix either, and for the reason this listener is on the window in the first place: the common Easy path reaches the quiz from the guidance chip, which unmounts as the panel opens, so focus is on `<body>` or on a node that has just gone, and a container keydown never hears the key. One owner, one action per press, and a regression guard that Escape with nothing open still retreats. The compact rail disclosure keeps its own handler: it is read from the DOM (`.rail-overflow[data-open]`), and a React state update has not landed by the time the window listener runs, which is why it never had the bug |
| 2026-07-29 | Easy guidance covers **study level**, offering the prove step; and it is suppressed while the checks panel is open | `nextStudyHint` returned `null` at study level on the claim that "the Study panel already owns the learner's next action". It does not: the panel ends on a lens note, and the only route onward is noticing "Back to the module" in the header — so the deepest step of the loop was its least guided. It stays graph-derived (same nearest-unlit ranking, same penalty) and the action retreats out of study before opening the quiz, so the chip's one promise is one move. Suppressing it during the quiz is the same "no stale advice" rule one step later: at 320px it was spending 183px of a 640px viewport telling a learner to read before proving while they were already proving |
| 2026-07-29 | A parallel session's galaxy-camera fix on `main` is taken **wholesale**; this branch's independent implementation of the same thing is dropped, not merged | Both sessions wrote `web/src/cameraFraming.js` and `web/scripts/check_camera_framing.mjs` from the same symptom, and both found that a `PerspectiveCamera`'s `fov` is vertical. Main's is kept because it is measurably better *and* because this branch's diagnosis was partly wrong: main measured that the aspect changes the required distance by nothing against the real layout, and that the near edge binds — 15 of 113 regions were *behind* the camera. This branch measured a 32-module subdirectory scope, where nodes never get behind the camera, and concluded the aspect was the cause. Main's also fits the charted set rather than the whole disc, re-frames on resize, and keeps name plates on the canvas. The one idea worth carrying forward was this branch's: main aims at the origin and solves only for distance, while the layout's centre is nowhere near it. That follow-up has since been done — see the two rows below, which also show the branch's version of it was itself too naive |
| 2026-07-29 | `attachBloom` takes the host's size and calls `composer.setSize` itself, instead of trusting the composer to have been sized | The composer PRESENTS through the pass chain, so a chain that was never sized draws an empty canvas -- correctly sized element, no console error, nothing on it. `composer.setSize` is the only thing that sizes it, and the width/height props that trigger it are diffed: re-mounting the renderer into a host of the SAME size skips them, so the bloom pass kept the 1x1 it is constructed with and the whole galaxy arrived through a one-pixel buffer. That is the blank stage after switching Diagram -> Galaxy. It looked engine-specific for two sessions, and the reason is the useful part: it needs the re-mount to land on an identical size, so a fresh page load differs from the library's defaults, gets a real resize for free, and hides it -- which is why a driver that always starts from a new page could not reproduce what a human hit immediately. Honest limit: three clean switches after the fix against one blank before it is evidence, not proof that this was the only cause |
| 2026-07-29 | `nameAtlas` treats the chrome drawn over the canvas as unavailable, the same way it already treats the canvas edge | The canvas is not all sky: the orientation line sits over its top-left and the keyboard readout over its bottom-left, both `pointer-events: none` DOM the scene knows nothing about. A plate was printed straight through them -- on this repository across "24 charted · 2 could not be read · all under tests/", the line graph schema 8 added so a learner is not misled about coverage. Covering that is worse than showing no name. Rectangles rather than a reserved top band, so chrome in one corner does not cost the sky the whole row; and read from the DOM each pass, because the line's width changes with the language focus, with Show all and with the register's wording. Worth recording how the first attempt failed: it scoped the query to `host.parentElement`, which is three divs below `.galaxy-frame` and a different subtree from `.orientation-bar` entirely, so it found nothing and was a silent no-op that looked exactly like a working fix until the plates were counted |
| 2026-07-29 | The camera **aims** at the projected centre of what it is framing, solved jointly with the distance (`frameAround`), instead of staring at the origin. `frameLevel` returns that target and `cameraPosition` uses it | Knowing how far back to stand says nothing about where to look, and a parser-derived layout is not arranged around `(0,0,0)`: measured on this repository the charted sky opened 15 points left of centre and 27 high, with the top 42% of the canvas empty and the lowest module cut by the bottom edge. The obvious fix is wrong and worth recording — aiming at the points' world-space centre made the VERTICAL worse (29.6 points against 27.1), because under perspective a near point at a given offset projects further from centre than a far one. What has to be centred is the projected extent, which depends on the distance, which depends on the aim. Solved by passes: each aims exactly for the distance it has (a bisection on a strictly monotone imbalance, so it holds however deep the perspective) then refits the distance for that aim. Fixed counts, so "same code → same sky" does not come to depend on a tolerance. A shorter distance falls out for free — a centred subject needs less standoff — so the sky arrives filling 90% of the canvas height where it filled 63%, with two more names on screen |
| 2026-07-29 | A point handed to `framingDistance` may carry the `radius` of what is DRAWN there; `graphData` owns that number for every node (`drawnRadius`) | A layout coordinate is a star's centre, and a star is drawn far past it: the sphere is 2.7–4.6 units and its halo reaches 9–15. Fitting the coordinates fits the centres and crops the stars, which was invisible only because the camera stood further back than it needed to — correcting the aim shortened the standoff and immediately clipped them. The `margin` fraction cannot express this: a share of the frame is a different number of world units at every distance, so it over-reserves on a wide sky and under-reserves on a tight one. Per point rather than one global pad, because the sets are mixed — a system fits its planets *and* the guide circles they sit on, and a guide is a line with no glow to reserve for. The nebula (14×) is deliberately not counted: it is a soft wash with no edge to clip, and reserving for it would push every sky back a third to protect a boundary nobody can see |
| 2026-07-28 | The galaxy camera's **distance** is solved from the nodes each time; only its tilt stays hardcoded. `CAMERA_BOUNDS` become floors that the fitted distance may raise, so a level always opens inside the range it is then held to | A fixed distance is a bet that the layout will never outgrow it, and this one had: the disc reaches radius ~628 while the camera sat at 327, so 15 of 113 regions were *behind* the camera and 31 were not on screen at all. Diagnosis is worth recording because the obvious answer was wrong — a `PerspectiveCamera`'s `fov` is vertical, so v0.8.0's taller canvas genuinely did narrow the horizontal field, but measured against the real layout the aspect moved the required distance by nothing (1061 at every aspect tried). The near edge binds, not the sides. Determinism is preserved because the fit is a pure function of node positions, tilt, fov and aspect — "same code → same sky" now also means "same window" |
| 2026-07-28 | The galaxy opens fitted to the **charted** systems, not to all of them; the far clamp is still set from the whole project | Fitting everything is defensible and unusable: on this repository it framed the full disc and shrank the charted core to a thumbnail, trading a bug where you could not see a third of the sky for one where you could not read any of it. Progressive reveal already decides what the learner is meant to be reading, so the camera follows it. The uncharted rim stays drawn, stays clickable, and stays reachable by zooming out — which is what the whole-project clamp is for. **Show all** charts every region, so it fits everything with no special case |
| 2026-07-28 | Keeping a name plate on the canvas is `nameAtlas`'s job, not the camera's | A plate holds its pixel width whatever the camera does, so the share of the frame it needs grows as the window narrows — no constant margin the camera reserves can cover it, and at 900px the widest paths, the most useful ones, hung off the edge. `chooseSlot` already computes the plate's pixel rectangle and already rejects a slot that collides; rejecting one that falls off the canvas is the same test against a different obstacle, and a plate with no slot is simply not drawn, exactly as when it loses to a neighbour |
| 2026-07-28 | `galaxy.png` shows a genuine first-run **unlit** galaxy; the lit Home lives only in `galaxy-lit.png` | The previous hero was captured mid-session with Home already lit, so its alt text promised "an amber lit Home" that a new reader would not see on their own first run. Splitting the two makes the pair a before and after and gives `galaxy-lit.png` — displayed nowhere until now — a reason to exist. Illumination is the product's central claim, so it should be shown being *earned*, not preset |
| 2026-07-29 | Constellation spacing is **derived from** region spacing (`_CONSTELLATION_SPACING = _REGION_SPACING * 2.25`) rather than being an independent literal; layout bytes change once. The guard is the relationship (ratio must stay ≤ 3) plus a fixture extent bound, not a universal packing invariant | Written as unrelated numbers, the two had drifted to 4.5x — the same packing question at two scales answered inconsistently. Measured on this project that left the sky **98.7% empty**: constellation centres a median 728 units apart while the widest constellation spanned 137, so the (now correctly fitting) camera framed mostly void and every system rendered as a speck. 2.25 is the smallest multiple measured to leave the closest pair no tighter than 4.5 did, on this project (radius 768 → 415, closest pair unchanged at 18.4) and on the polyglot fixture (191 → 125, unchanged at 37.5). **Stated honestly as a measurement, not a proof**: whether the closest pair falls between constellations or inside one depends on the community histogram — a synthetic 14-community/31-region shape crosses that line at *both* ratios — so an earlier draft of this row claiming 2.25 "never packs two constellations tighter than their own members" was over-claimed and is corrected here. Nothing re-dims: `_region_signatures` hashes `(file, file_hash)` pairs only, verified by 104 of 117 regions moving with zero signature changes |
| 2026-07-29 | **Corrects M12's acceptance note that uncertainty is "colour-only in the 3D galaxy (no line-dash support there)"**: an unproven route now supplies its own `THREE.Line` with a `LineDashedMaterial` through `linkThreeObject`, positioned by `linkPositionUpdate` along the library's own `link.__curve` at its own resolution, with `computeLineDistances()` run on every geometry write. Proven routes keep the default cylinder. Lives in `web/src/possibleRoutes.js`, pinned by `check_possible_routes.mjs` | The original note was accurate about the *default* link and wrong about the layer: `three-forcegraph` picks a cylinder mesh whenever `linkWidth` is non-zero (`useCylinder = !!widthAccessor(link)`), and a mesh cannot be dashed — but the library also accepts a custom object per link, which a cylinder never had to be. Colour is the weakest possible encoding for the one claim a learner must never misread as fact: it vanishes under colour-blindness, on a dim panel, and in every greyscale capture of the galaxy, and it left the two layers disagreeing about how loudly they admit doubt. Dash phase is arc length, so `computeLineDistances` is load-bearing — without it every vertex reports distance 0 and the line silently renders solid, restoring the exact defect. Opacity is 0.62 rather than the solid link's 0.5 because a dash cycle is only 57% ink, and matching opacity would have made the *unproven* claim the fainter mark — the inversion the 2026-07-22 route-ink row exists to prevent |
| 2026-07-29 | **Corrects the 2026-07-22 "Hue means import community" row**: a community's colour family is assigned by the graph layer to the project's **eight largest** communities (size descending, community id breaking ties) and serialized as `Region.community_family` (schema 8 → 9). Communities past the cut carry `None` and keep the neutral centrality ramp. `community id mod 8` is deleted from the renderer; `graphData.communityFamilyIndex` now only *validates* a graph-assigned family and never wraps | That row's guardrail — "the mapping is pure arithmetic on graph truth so the same code always yields the same sky" — was true and still insufficient. Deterministic is not the same as truthful: with thirty-nine communities on this repository the modulo put five distinct communities on family 4, so two parts of the codebase that share no import wore one colour while the legend promised hue meant "which part of the project is this". A learner tracking a group by its colour got a wrong answer with nothing on screen to reveal it, which is the exact failure class the Correctness Contract exists to prevent. Ranking and stopping at eight makes a family name at most one community, and the absence of a hue is an honest "not one of this project's main groups" where a borrowed hue was a false claim. It moved to the graph layer because the assignment depends on the WHOLE project while the frontend holds only the language-focused projection: derived there, "the eight largest" would have meant something different per filter and focusing a language would silently have repainted the sky — violating the 2026-07-19 rule that focus never mutates parser truth |
| 2026-07-29 | `web/src/galaxyView.js` owns every camera decision — which points to fit, at what aspect, inside what clamps, and where study stands off a structure. `cameraFraming.js` keeps only the arithmetic | The extraction line in `web/src` was drawn at "does it import `three` or React?", not at "is this a decision?". `framingDistance` is the most tested function in the frontend and has never been the bug; all three shipped framing faults (`0c6caf4`, `c64a88a`, `5bdb110`) were about *what it was handed*, and every one of those decisions was module-private inside a 742-line component — `c64a88a` shipped with no check-script change because there was nowhere to put one. `nameAtlas` already proved three.js runs headless in plain Node, so WebGL was never the reason. Three faults fell out of writing the tests: the aspect now has one source (the host element, never the library's batched copy), `frameLevel` returns its own `distance` because re-deriving it with `Math.hypot` disagreed in the last bit, and the name atlas had been budgeting labels against the *static* bounds while the camera was clamped to the *fitted* ones |
| 2026-07-29 | Escape precedence is an ordered list in `web/src/escapeArbiter.js`; `escapeFacts` is the one place the session and the document are read for it | It was an eleven-term disjunction in `App.jsx` plus a second, shorter copy on the chart stage, so a new global surface had to be added to both — and forgetting has already shipped, which the 2026-07-28 rail-disclosure row records. A list makes a new surface one entry in one file and states outright which surface wins. Three facts stay DOM reads because they genuinely have no session field: a native dialog's open state belongs to the top layer, a disclosure's is view-local, and what has focus is the document's business. Gathering them in one shim keeps the arbiter a pure function of stated facts rather than a second thing that queries the DOM |
| 2026-07-29 | "What colour is this node right now" is `graphData.highlightColor`, beside the standing answer it overrides | The transient hover/fade colour lived as a closure inside `GalaxyCanvas`, reachable by nothing — which is how the halo came to be painted from `node.color` while the sphere in front of it was painted from the closure. Two owners of one fact, and only one of them hears about hover. Reveal state had the same shape of problem in miniature: `node.charted` in one place and `node.charted === false` in another, equivalent only because `galaxyData` happens to always write a boolean, and genuinely different questions for a system member that carries no reveal state at all |
| 2026-07-29 | Map schema 3 → 4: a `workflow.unreachable` row is `{id, language}` rather than a bare id | The renderer filtered them with `id.startsWith("<language>:")`, which is the JS/TS adapter's private id convention; Python mints dotted module paths and carries no prefix. Focusing Python on a mixed project therefore reported **zero** never-called structures where the polyglot fixture has two — a count a learner cannot check, in a note whose only job is to state a count. The contract check agreed with the bug because its fixture spelled Python ids the JS way; it now mints each language's ids the way that adapter actually mints them |
| 2026-07-29 | `with_entrypoint` refuses a graph that never reached `layout_graph`, and re-selecting the Home a graph already carries is a no-op | It measures every distance against `graph.regions`, which only `layout_graph` fills, and returned a valid-looking graph with zero regions when handed one that skipped it — a galaxy with no stars, reported as success. The no-op is the common case rather than an edge one: `CheckService.graph` re-selects the current Home on every hydration, paying a full breadth-first walk to rebuild the regions it had just been given. Layout's second definition of `Region.understood` went with it — unreachable, but it read as a specification and was not the rule `ProgressStore` applies |
| 2026-07-29 | CI asserts the shell's space budget in its own job, against a running Codemble. **Amends the standing rule "UI is verified by running it"** | Approved by UD. `styles.css` is 3,216 lines across 17 media blocks carrying the entire layout contract with no seam and no assertion, and three of the last eight bugfixes were exactly that — `99b6875` a bug in *cascade resolution*, which no JS seam can reach. Each was verified by a human reading DevTools and pasting the numbers into a commit message; those numbers were the contract and nothing re-read them. The check reproduces `13b3c06`'s own measurements (header 148, chrome 36.8%) and is proven in both directions. It serves the committed bundle against this repository rather than a fixture, so there is nothing to drift from the app, and `npm run check` stays Node-only, offline and fast |
| 2026-07-29 | **The Living Atlas Orrery art direction is approved**, amending the "elaborate game art" Non-Goal: System-level structures are drawn as procedural worlds (`web/src/celestialBodies.js`) with a four-octave fBm crust, one key light fixed in view space, a rim atmosphere in the body's own community hue, class strata, a fracture treatment for files the parser could not read, and slow surface rotation. Galaxy range keeps its halo sprites | Approved by UD. The guardrails are what make it safe rather than decorative: the crust is seeded only by FNV-1a of the node id, so the same code yields the same worlds and no surface can encode a fact; every semantic channel (size, community hue, amber for understood, the class ring, the fracture) is still decided in `graphData.js` from parser truth and handed to the shader as a finished value; amber stays exclusive to `understood` and the atmosphere never borrows it; and rotation moves a body's own surface, never a position, because layout is parser-owned. The tier split is a measured limit, not a preference — a per-fragment noise loop is affordable for a few dozen members at close range and not for ~1,000 systems, so `nodeThreeObjectExtend` follows the level. Removing every body still leaves a correct, navigable learning model |
| 2026-07-29 | The space budget adds **1024, 1023, 768 and 640**, and the 1024/1023 pair asserts *which shell rendered* rather than only what it spent | Phones were covered from the start (375, 320, both registers); the gap was the band between them and 1280 — exactly where v0.8.0 went wrong. The 2026-07-28 entry moved the rail's breakpoint to 64rem because the wide arrangement measured *worse* than the compact shell below 1024 (199px of rail at 768 against 124px compact), and those widths were hand-checked once and never gated. A budget alone cannot catch that breakpoint moving, because the compact shell is **cheaper** — a regression would look like an improvement. Only the header height says which shell is on screen: 1023 must measure 124px and 1024 must measure 148px. Proven by moving the breakpoint back to 40rem, which fails three rows and names the cause on one of them; 768's header balloons to **327px** (61.7% chrome), worse than the 199px originally measured because the wide rail then has more to fit |
| 2026-07-29 | `check_escape_surfaces.mjs` runs its whole matrix at **1440, 768, 375 and 320** — 84 assertions, 82s | Width is not a detail here, it is two different shells. Above 64rem the rail actions sit in the header; below it *every* one of them — Modules, Find, the star chart, the layer switcher — lives behind the Menu disclosure, so reaching any surface means opening a **second** surface first. That is exactly the arrangement the double-fire needed, and the 2026-07-28 entry records that only compact widths could reach it. 768 earns its place for looking like a desktop and behaving like a phone. The matrix also pins a compact-only rule the wide shell cannot express: after reaching a rail action *through* the Menu, Escape must not find the Menu still open. Focus at compact returns to the **Menu trigger** rather than to Modules or Star chart, which is correct rather than a gap — those controls are inside the collapsed panel, so the trigger is the way back to them, and it is what `restoreRailFocus`'s fallback chain exists to reach |
| 2026-07-29 | The CI job that needs a browser is `browser-checks`, and it hosts two gates: the space budget and `check_escape_surfaces.mjs` | `check_escape_arbiter` proves the *decision* — which surface owns Escape, for every combination. It cannot prove the key arrives, that the surface closes, or that focus lands somewhere a keyboard learner can carry on from, and **every Escape bug this project has shipped was one of those**: the rail disclosure closing *and* retreating, the checks panel and module index never claiming the key, the star chart retreating on top of its own dismissal. One server and one Chromium install answer both gates, so the second costs almost nothing. The in-app browser pane cannot substitute — it reports `document.hidden === true`, which throttles `requestAnimationFrame`, and `restoreRailFocus` is rAF-based, so focus return reads as broken there whether or not it is. The check's first assertion guards that trap so the gate can never pass by measuring a throttled page |
| 2026-07-29 | `restoreRailFocus` defers to a **task**, not to a frame | Focus is a DOM operation and needs nothing painted — it only has to run after React has committed the close. `requestAnimationFrame` also waits for the galaxy to render, and a frame is not 16ms when the scene is heavy: traced against this repository under software WebGL, frames arrived every **972–3751ms**, so focus landed on the right control **0.4–4.4s** after the key. It always arrived, which is why this never read as broken and why the browser gate was flaky rather than failing — but a keyboard learner pressing Escape and waiting a second for focus is a real cost, and it grows with the project. Found by chasing a 1-in-4 flake through two wrong hypotheses: a stale-focus race (wrong — focus was never stolen) and a commit-ordering race (wrong — a double-rAF re-assert made it *worse*, 3 in 6). Tracing the actual frame timeline settled it in one run |
| 2026-07-29 | Leaving the quiz returns focus to **Prove understanding**, from Escape and from the panel's own control, through one `closeChecks` helper | Every other dismissible surface returned focus; this one dropped it, so a learner who had just worked through a region by keyboard was left on `<body>` and had to tab in from the top. Pre-existing and shared with `e00b3fe` on both paths, which is why both go through one helper now rather than one being fixed and the other drifting. The trigger stays mounted behind the panel, so there is somewhere obvious to return to — no new component, no new state |
| 2026-08-01 | Clearing a project's progress is `CheckService.clear_progress()`, which empties the store **and** the in-flight pass set; `DELETE /api/progress` calls it instead of reaching through to `progress.clear()` | Two owners of one fact. Understood regions are persisted; which individual checks a learner has answered lives on the service for the life of the process. Clearing only the store dimmed every module while every question stayed `passed`, so `for_region` returned a fully-passed suite for a region that was not understood — a shape the renderer has no branch for, so **the quiz drew a title and a Close button over nothing**. Illumination is the game, and the documented recovery control turned it off permanently for every region proved in that session, with no route back short of restarting the server. The panel also gained a branch for that state: the server can no longer produce it, but a second tab holding a suite from before the reset still can, and no surface here may be a dead end |
| 2026-08-01 | In the wide rail the **actions** size to their content and never wrap (`flex-wrap: nowrap`, `min-width: max-content`); the brand and breadcrumb absorb the shortfall, the breadcrumb keeping its 9rem floor and the brand capped at 18rem | Which column yields is the whole bug. Brand and breadcrumb were `auto` — max-content — while the actions held the only flexible track, so every pixel either text column wanted came out of the buttons, and buttons cannot shrink: measured 148 → 199px at region level and **259px at study** (52.2% of a 720px window, the diagram down to 190px) across 1024–1279px. The brand's second line is the learner's own directory name, which made the header's height a property of what the folder is called — a 60-character name reproduced the wrap at **1440**. Two details were load-bearing: a wrapping flex container's min-content is its *widest single item*, so an `auto` track alone froze at one button and grid shared the leftover out **equally** with the brand; and `.rail-actions` sets `min-width: 0`, telling grid the buttons would accept zero width. The priority order is deliberate — the breadcrumb is navigation and keeps its floor, the brand is identity and yields first. Accepted cost, recorded rather than hidden: at 1024–1059px at study level the wordmark clips by 2px, which beats truncating the breadcrumb or demoting a 36px band of widths to the compact shell |
| 2026-08-01 | The space budget walks **region and study level** at every wide width, fails on overlapping header controls, and asserts the header does not move when the project name is 70 characters | Both gaps above passed the existing gate, and for two structural reasons rather than bad luck. It measured only the top level, where the rail carries one action fewer than the loop the learner actually spends their time in — the wrap was one click below anything asserted. And it ran against a checkout directory named `Codemble`, eight characters, where the row fits; the bug needs a real learner's folder name. Overlap is checked clip-aware, because an ancestor that hides its overflow clips the hit test too and comparing raw boxes reports collisions a learner cannot experience — and `display: contents` must be skipped outright, since the wide rail turns the disclosure panel into one and it reports `overflow: auto` on a 0x0 rect, which silently zeroed every control and made the check unable to fail |
| 2026-08-01 | `check_escape_surfaces.mjs` clicks the layer switcher by either register's label (`/^(Map\|Diagram)$/`) | It clicked "Map" while running Easy, which renames the layer "Diagram", so it never left the Galaxy: the box click below found nothing and **eight of its 84 assertions had been failing for the wrong reason**, reporting "could not reach the prove control from the map" instead of exercising the checks panel and the map retreat. A gate that cannot reach its own surface fails in a way indistinguishable from the bug it exists to catch, which is worse than not having it |
| 2026-07-29 | The public site uses an 18px prose baseline and 14px informational floor; 1440px product captures stay on a readable full-size canvas with explicit horizontal pan on narrow screens. The cinematic Atlas Journey runs only at ≥120rem and widens its measure there | The previous layout rendered supporting copy at 12–14px, desktop captures at 704px, and mobile captures at 333px. That made the real UI inside the images impossible to inspect without browser zoom. The website scale is intentionally separate from the dense local-app instrument scale, and the tatebanko remains the site's one decorative signature |
| 2026-08-01 | `codemble.__version__` is **derived** from `importlib.metadata.version("codemble")` rather than restated as a literal; `pyproject.toml` is the single source of truth, and `tests/test_version_agreement.py` holds every spot that cannot derive — both `package.json` files and `web/package-lock.json` — to that one number. `codemble/__init__.py` is struck from the release checklist's bump list | It had already failed: v0.8.0 shipped a wheel whose app reported **0.7.0**, and that number reaches users through three channels at once — `codemble --version`, the FastAPI app's advertised version, and the `user-agent` on every outbound narration request, where it misidentifies the client to Anthropic, OpenAI and Ollama alike. Golavo's `scripts/bump_version.py` was read and deliberately **not** copied, because the two projects differ in kind rather than degree: Golavo has 23 spots that genuinely cannot derive (compiled Rust, `Cargo.lock`, `tauri.conf.json`), so enforced agreement is the only option there, while Codemble is one Python package whose version the build backend already writes into the wheel's own metadata — the duplicate can be *deleted* rather than policed, and a check that polices a duplicate still leaves the duplicate. The failure mode genuinely improves rather than merely moving: a literal can be wrong inside a shipped artifact, whereas derived metadata equals `pyproject.toml` by construction for any built wheel, so what is left is a stale *local* editable install — which never ships, and which the test now names along with the reinstall command. The uninstalled-checkout branch falls back to `0.0.0+unknown` because `import codemble` must not raise: all four call sites import `__version__` at module level, so a bare `PackageNotFoundError` would take down the CLI and the server rather than mislabel them. Worth recording as measured rather than assumed: the machine held **three** versions simultaneously, not the two reported — `pyproject.toml` 0.8.0, the source literal and the active pyenv `dist-info` both 0.7.0, and the project venv 0.6.2 — so the version the app reported depended on which interpreter happened to be on PATH |
| 2026-08-01 | **Narrows the row above**: the version gate covers only what the app reports. The three npm manifests (`web/package.json`, `web/package-lock.json`, `docs-site/package.json`) are deliberately **not** gated and remain a human checklist step, and the one surviving assertion folds into `tests/test_smoke.py` instead of keeping a module of its own | Dropped at UD's call, and the right call: nothing consumes those manifests' `version` field — neither package is published and no build reads it — so a drift there is cosmetic, and a cosmetic drift is not worth failing CI on a release branch. It was also the widest part of that row, reaching past the `pyproject.toml` ↔ `codemble/__init__.py` scope that was actually asked for; policing three files nobody reads is the kind of gate that gets disabled the first time it fires inconveniently, which is worse than not having it. What stays gated is the part that reaches users, which is the whole reason this was a bug rather than an untidiness: the number in `--version`, in the FastAPI app's advertised version, and in the `user-agent` on every outbound narration request. One assertion does not need its own module, and it replaces `test_version`, which only checked that `__version__` was truthy — a check the stronger one subsumes |

| 2026-08-02 | **Exploration is the front door; illumination stays the only earned state.** The anti-drift test becomes *"does this help a learner understand **or explore** their code?"* | UD's complaint was that the galaxy is "too dark and hard to just explore even if you are not learning", and that the product's main goal is exploring code like an astronaut with learning **optional**. That is a product-identity question, not a styling one: the darkness was the game encoding working exactly as designed — the unlit ramp was capped below a text token so amber would always win, and progressive reveal drew everything uncharted faint, unnamed and edgeless (about 100 of 123 systems here). The sky was rendering "you have not learned this yet" and charging exploration for the privilege. Approved as a **presentation** flip rather than an identity flip: the meaning rules are untouched, amber still means understanding and is still the brightest thing in the sky, checks are still the only way to earn it. What changes is that none of that is allowed to make the galaxy unexplorable first |
| 2026-08-02 | Reveal gates the **route mesh and the camera's opening frame only**; every region is visible, coloured and named from the first frame | The hairball that reveal was built to solve was the *edges* — at 169 systems the route mesh outdrew the stars — and dropping the edges of what is not yet charted solves it completely. Withholding names and colour was a second tax on the same problem, and it bought nothing: a learner could not find, recognise or navigate to anything without first proving they understood their way to it. The camera still opens on the charted set, because framing all 123 systems makes every one of them a speck — visibility and framing are different questions and only the first one was wrong |
| 2026-08-02 | **The explorer's trail:** visiting a region charts it, persisted in the progress store as a top-level `visited` key. This amends the locked "no other meta-progression" rule | Approved by UD. Exploration needed some persistent trace or the astronaut has no reason to fly anywhere twice. It is not XP: nothing accumulates into a score, there are no levels, streaks or leaderboards, and it is a map record of where you have been. Deliberately **not** signature-scoped the way `understood` is, and the difference is the point — a proof of understanding is a claim about code and must retire when that code changes, while having been somewhere is a fact about the learner's own history that no edit can undo. The star chart shows the two as separate rows so been-there can never be read as know-it. `_SCHEMA_VERSION` does **not** bump: `_read` hard-rejects any payload whose version differs, so bumping it would silently discard every existing learner's understood set. `clear()` empties both halves, per the 2026-08-01 lesson that a half-reset leaves a shape no surface is written for |
| 2026-08-02 | The app **forks its palette** from `docs-site/src/styles/tokens.css`; the canvas gains its own `--cm-sky` and its own three-value unlit ramp | Retires the standing Gotcha where a public-website token edit restyled the shipped app with no signal and no rebuild. The canvas was painting `--cm-ground` — the *panel* colour, relative luminance 0.0037, black in all but name — so the sky could not be lifted without dragging every panel's contrast with it. The ramp mattered more: it borrowed `--cm-ink-2`/`--cm-ink-3`, which tied how bright an un-understood star may be to the interface's typography, and its floor is where the ~30 modules belonging to none of the eight ranked communities fell through. They were all but invisible, which is a large part of what "too dark" actually meant. Measured and re-verified against the new values rather than assumed: lit 0.665 > family 0.470 > ramp 0.439/0.220 > sky 0.0163, with legend swatches improving from 8.1:1 to 9.6:1 |
| 2026-08-02 | `check_sky_palette.mjs` **measures** the meaning rules out of `tokens.css` instead of trusting the comments that stated them | "Amber means understanding and nothing unlit may outshine it" is the product's most important visual claim and was enforced by prose. `check_graph_data.mjs` proves the *selection* (understood always takes amber) with symbolic swatches, which is right for that file and says nothing about whether the amber swatch is actually the brightest — a token edit could have inverted the whole meaning with every gate green. The gate now computes WCAG luminance for the ordering, per-family parity, the reserved kohaku hue band, the 4.5:1 legend floor, uncertainty staying louder than certainty, the bloom threshold bracketing, and that no star is invisible against the sky; it also refuses an `@import` back to the docs tokens so the fork cannot quietly undo itself. Proven in three directions before landing. Same lesson as the shell space budget: the stylesheet carries contracts, so the stylesheet gets assertions |
| 2026-08-02 | Narration runs under **its own anyio `CapacityLimiter`** on an async route, with a 45s deadline and `abandon_on_cancel` | This is the defect behind "for experts most of the stuff in that view doesn't load", and it was never a panel bug. Every route was a plain `def`, so all of them shared anyio's request threadpool, and `urlopen` cannot be cancelled — once a worker thread is inside it, that thread is gone until the provider answers. Enough in-flight explanations starved `/api/graph`, `/api/map`, `/study` and `/checks` alike, and experts hit it first because they click through structures fastest. Passing a limiter of Codemble's own means the default limiter is never acquired, so the parser endpoints keep their full budget however many explanations are stuck. Because the abandoned worker still writes the narration cache, a retry after a timeout is usually instant. **`anyio>=4.1` is now a direct dependency**: `abandon_on_cancel` was named `cancellable` before 4.1, and anyio only ever reached Codemble through Starlette's `>=3.6.2,<5` — an older resolution would have raised TypeError on every narration request, reintroducing the exact failure through the dependency graph |
| 2026-08-02 | Provider failures split into `ProviderUnavailableError` / `ProviderRejectedError` / base, and validation **salvages formatting faults but never fabrication** | Two different corrections. On error copy: a network timeout and a grounding refusal collapsed into one branch, so a dropped connection told the learner that Codemble had withheld output falling outside parser evidence — a correctness lecture for a connectivity fault. On validation: an absent walkthrough, or one item that is empty or over-long, now costs that item and is counted into `withheld`, instead of discarding a summary the learner could have read. **Narrowed deliberately during implementation**: an invented node id or a citation outside the lines the prompt actually supplied stays fatal, because that is invented structure and the Correctness Contract outranks the reliability goal. The register-keyed narration cache was also **kept** after being listed for removal — Easy and Expert prose genuinely differ, so a shared key would serve beginner prose to an expert |
| 2026-08-02 | The expert style block no longer instructs the model to "lead with this structure's role in the wider project"; long spans are sent as a **bounded, self-announcing excerpt** and the walkthrough may only cite lines the excerpt supplied | The old expert instruction contradicted the contract three lines below it, which permits naming only supplied neighbours — that pairing manufactured the fabrications that produced expert-only refusals, so the largest Expert win was upstream of the panel entirely. Separately, a module node spans its whole file, so an unbounded prompt numbered thousands of lines into a request: slow, expensive, and past a certain size answered with an HTTP 400 the panel reported as a narration failure. Confining walkthrough citations to the excerpt is a correctness improvement, not a side effect — explaining a line the model never saw is a guess even when the line is real |
| 2026-08-02 | The **impact widget** is graph-layer truth (`codemble/graph/impact.py`) shipped in the `/study` payload, and leads the Expert panel | UD asked for Expert to be "quick widget style — this controls this and this can be impacted by this" for someone onboarding a codebase. That question was already answered by the parser and was being routed through a provider that might not be configured, might be slow, and might refuse; making it graph-layer means the Expert panel's lead content **works with no API key at all**, which removes the single largest cause of the original complaint. The Correctness Contract clause that shapes the module: a chain through one unproven edge is unproven for its whole length, so certainty comes from a second walk restricted to certain edges — tracking it in one pass forces a choice between reporting the true distance and the true certainty, because the shallowest route and the only proven route are frequently different routes. External edges are excluded here (they stay in the connections list) because every row must be somewhere the learner can actually go; the depth cap is reported rather than applied silently |
| 2026-08-02 | The line-by-line walkthrough moves **behind a closed disclosure**; both registers answer in at most three sentences; **Easy may use analogy and Expert may not** | "Most of the explanations when opened up are either too complex for a casual user" — and the walkthrough was the bulk of what greeted every click, so a reader who wanted to know what a file is FOR was handed eight numbered claims about individual lines. It is genuinely useful and stays one click away. Analogy is permitted in Easy only, approved by UD: teaching a beginner without comparison to something familiar is close to impossible, and an analogy invents no structure — it restates supplied evidence in other words. The contract's existing ban on naming identifiers in prose is what keeps a comparison from becoming a claim about code that does not exist |
| 2026-08-02 | `recordVisit` is called from `selectStudyNode` as well as `advance`/`advanceRegion`, and the session check gates it | Found in review, and the impact widget had just made it worse. The helper's own docstring claimed it covered "every route into a system" and did not cover the handler behind the Workflow tree, the Connections list and the new Impact rows — all three of which can land on a module the learner has never flown to. They read its real source while the map quietly forgot they had been there, and its routes went dark again on the next move. A docstring that overstates its own coverage is how this class of half-wiring survives (the Escape sweep is the precedent), so the claim is gated rather than restated |

| 2026-08-02 | Go, Java, Rust and C# ship as four separate tree-sitter adapters, and their lens voices ship as **one** module | Two opposite calls for two different kinds of code. The adapters are genuinely different — Go's method receivers, Java's wildcard imports, Rust's inherent-vs-trait impls, C#'s file-scoped namespaces — and the project already had two independent adapters rather than a shared core, so a fifth through eighth match the established architecture and can each be verified alone. The lens tables are the opposite: pure data of identical shape, where four files would differ only in their contents. The lookup still keys by language, because Rust and C# both detect `async-await` and each deserves its own wording, and `generic` means different enough things in Java and C# to be worth saying differently. A concept with no entry yields no note rather than borrowing another language's — an invented caption on real evidence is still an invented claim |
| 2026-08-02 | Certainty is the place the new adapters were held hardest, and 82 of 137 edges on the seven-language fixture are hedged | Every language added a new way to be wrong about a call: a Go call through an interface value or function variable, a Java call on a variable whose declared type is not in the file (and a wildcard `import com.foo.*`, which names no type at all), a Rust trait-object or generic dispatch, a C# call on a `var` local, an interface-typed field or a delegate. None of those are statically provable from the parse tree, so every one is `certain=False`. Reporting a smaller hedged count would have meant guessing, and this is exactly the wrong a learner cannot detect. It is also the measurement that sets the next milestone: each edge that becomes provable through deeper resolution sharpens the impact widget, the checks and the map simultaneously |
| 2026-08-02 | Python resolves a call on a **constructed receiver** (`Adapter().parse()`) as CERTAIN, on an **inherited** method through the in-project base chain, and on an **annotated** receiver as POSSIBLE | Measured, 79% of Python call edges were unproven, and the shape was worse than the number: `.parse()` emitted an edge to every class in the project defining `parse` — nine here, 237 call sites each — so eight in nine were relationships that do not exist, inflating centrality (which drives a star's brightness), padding the impact widget's blast radius and thickening the route mesh. They were labelled possible, so the *letter* of the Correctness Contract held; this is its spirit, because a hedge is honest about a relationship that might exist, not a licence to list nine when the evidence names one. The three certainty levels are not arbitrary: a constructor names its class outright and is the most statically determined dispatch Python offers (only a `__new__` returning another type breaks it, which no parser can see); an annotation names one class but Python dispatches on the *runtime* type, so a subclass may override — the same reasoning that keeps Java's virtual dispatch hedged here. Only in-project bases and types are recorded, because `class Adapter(Protocol)` inherits from something Codemble never parsed. **Worth recording that the first attempt missed**: the hierarchy and annotation branches alone moved the number the *wrong* way (+65 edges), because this codebase's `.parse()` calls are on constructor results rather than annotated names. Measuring which call sites actually produced the fan-out is what found the branch that mattered — 8508 → 6778 edges, 1993 fewer unproven |
| 2026-08-02 | The Python lens gains dataclass, Protocol, pattern-matching, f-string and walrus, and a test asserts every emitted concept can be voiced | The lens taught eight concepts and was silent on the ones that dominate the code this product exists to explain: 47 dataclasses, 307 f-strings, 4 walrus operators and 3 Protocols on this repository alone produced no note. A dataclass is deliberately both a decorator note and its own, because the learner is looking at a class whose `__init__`, `__repr__` and `__eq__` are written for it and appear nowhere in the file — exactly the kind of absence that makes AI-written code confusing. The gate exists because the adapter and the lens are separate files, so a concept can ship *detected and silent*, which is precisely how these five stayed invisible |
| 2026-08-02 | **The TypeScript deepening was measured and then largely refused.** JS/TS gets a builtin table instead | The obvious plan was to give TS what Python got. Measuring first said not to: of 1401 unproven JS/TS call edges on `web/src`, **80% were already `external:`** — React hooks, three.js, `Math.max`, calls that genuinely leave the project and are correctly hedged — and only **1% (20 edges)** was in-project fan-out. TypeScript has no ambiguity explosion, so porting Python's receiver resolution would have been effort against a problem that is not there. What the measurement *did* find is that 45% of the remaining `unresolved:` targets were ECMAScript and host globals — `Set`, `Map`, `Error`, `AbortController`, `requestAnimationFrame` — reported as `unresolved:javascript:graphData.js:Set`, which reads as "Codemble believes this is yours and could not find it". A coverage gap and a project boundary are different facts, and that distinction is what graph schema 8 exists to keep honest; Python's adapter has drawn it since M1 and JS/TS had no equivalent. The table is deliberately not exhaustive and not inferred: a name absent from it falls through to `unresolved:`, which is the safe direction, since a missing entry costs precision while a wrong one would reclassify a learner's own code as somebody else's. 258 → 114 unresolved |
| 2026-08-02 | Test-scoped Python files take a bounded **entrypoint rank penalty**; demoted, never dropped | Home selection offered seven candidates on this repository and five were test fixtures, with three tied at rank 0 — so `selected_entrypoint` resolved to **None** and a first-run learner was handed a picker listing mostly `tests/`, with the project's own entry indistinguishable from a fixture's `main()`. Demotion rather than exclusion because a project that *is* a test suite still needs somewhere to start, and dropping them would leave it with no Home at all. Detection is path-based on purpose: `tests/fixtures/sampleproj/app.py` is not named like a test and is one, and that shape — fixtures carrying their own `main()` and `__main__` guards — is exactly what buried the real entrypoint. Same principle as the 2026-07-22 Easy-guidance penalty: bias the ranking, never the reported fact. Home now resolves to `codemble.cli` with no question asked |
| 2026-08-02 | Home is selected from the **single best-ranked** candidate rather than only from rank zero, an app object no longer has to be named `app`, and a command/route decorator ranks a module on its own | Three arbitrary limits, each of which left the commonest shapes of Python project with no Home at all. The variable name was a naming convention masquerading as evidence — the *factory* is the evidence, so `srv = Flask(__name__)` and `cli = typer.Typer()` ranked nowhere. A click CLI has no app object whatever, so the decorator is the only evidence there is. And requiring rank zero meant a web service with no `__main__` guard had its only candidate sitting at the app-object rank while Home resolved to nothing: the learner was shown a picker holding one option, asked a question with one answer. Selecting the unique best candidate at whatever rank generalises the existing rule rather than replacing it — a genuine tie still opens the picker, because that is a learner decision and not a guess. Verified against four real shapes that each previously resolved to nothing |
| 2026-08-02 | The tree-sitter `<0.26` cap is **re-verified and kept**, with the recorded cause corrected twice; dependabot #37 (`<0.27`) must not be merged | The cap's own comment invited this ("raise only once a grammar release is verified against the newer core"), and it now guards six grammars rather than two, none of the four new ones having ever been tested against 0.26. Tested in an isolated venv: 0.26.0 still SIGSEGVs (exit 139) inside the JS/TS adapter while 0.25.2 parses the same tree cleanly, deterministically, 3 runs of 3. Two corrections to what was written down. It is the **JavaScript** grammar, not JS/TS generally — parsing only `.ts` is clean, as are Go, Java, Rust, C# and Python — so the four new adapters are unaffected and only the oldest one blocks the upgrade. And it does **not** need "a corpus of real size": 23 files reproduce it. The half of the original note that held up is subtler and worth keeping — a bare traversal will not show it at all, since walking 188,755 named nodes across all six grammars on 0.26.0 is clean and only the adapter's own query and cursor work trips it, which is why a behavioural test cannot be the guard (it would have to crash the interpreter to fail) |
| 2026-08-02 | **LOD culling and Python import resolution were both measured and refused**, and the measurements are recorded so the next session does not redo them | Two more pieces of planned work that the evidence said not to do. Python's relative and namespace imports are already complete — 500 import edges on this project, zero possible, zero project modules missed — so "airtight imports" had nothing to fix. LOD is subtler: the galaxy draws *regions*, not nodes, so the 900-node resolution guard is measured against the wrong quantity to worry about. Served a real 1,000-module project at the documented cap: 1,000 stars, route mesh thinned by reveal to 5 charted, no console error, camera correctly framed on the charted set. LOD belongs with *raising* the cap rather than before it. Stated as a limit rather than hidden: **framerate itself was not measured**, because the in-app browser reports `document.hidden === true` and therefore throttles `requestAnimationFrame` — the same trap recorded on 2026-07-29 for focus return — so the evidence here is structural, not a frame count |
| 2026-08-02 | The v0.10.0 suite count is verified in a **throwaway venv**, and the ambient editable install is deliberately left alone | `test_the_running_app_reports_the_packaged_version` compares `__version__` — read from installed distribution metadata — against `pyproject.toml`, so a version bump makes it fail locally until the package is reinstalled. Its own message says so. But the pyenv editable install's `direct_url.json` pointed at *another session's worktree*, so reinstalling from here would have repointed that session's environment mid-flight. CI installs fresh from the branch and matches; a `python -m venv` install reproduces CI exactly and confirmed 379 passing. The gate is right, the local environment is stale, and the honest fix was to verify rather than to disturb somebody else's tree |
| 2026-08-02 | The "is this file inside the project's own test tree?" entrypoint demotion moves to `codemble/graph/finalize.py` and is **deleted** from `python_ast.py` | Six candidates tied at rank 0 on this repository — `codemble.cli` plus a C#, Go, Java, Rust and TypeScript fixture — so `selected_entrypoint` was None and a first-run learner met a picker of 26 candidates, 22 under `tests/`. The obvious diagnosis is wrong and checking it is what produced the right fix: every one of those adapters already demotes tests, but each by a signal only its own language has (Rust `#[test]`, Java `@Test`, C# `[Fact]`/`[TestMethod]`, Go the `_test.go` suffix), and none of them fires on a fixture's ordinary unmarked `main()` in a file not named like a test. Porting attribute detection to five adapters would have been work against the wrong problem. The path question needs no parser evidence and is identical in every language, so it belongs at the one funnel every adapter already returns through — where an eighth language inherits it for free, exactly as `unsupported_sources` promised. Demotion, never exclusion: a project that IS a test suite still resolves a Home |
| 2026-08-02 | The wide rail gives `.language-focus` a small `flex-basis` (`flex: 1 1 12rem`) rather than relying on its existing `min-width: 0` and `overflow-x: auto` | The focus control renders one permanent chip per language, so **its width is a property of the learner's project, not of the design**: seven languages measure 673px, and below ~1280px that plus the layer switcher and the audience toggle stopped fitting one row. The rail took a third row — header 148 → 216px, chrome 46.3% against a 42% budget, and the Map's drawing 197 → **106px** at region level, which is the compact shell at 1023px (325px) beating the wide shell at 1024px three times over. The scroll and `min-width: 0` were already present and could not help, and the reason is the part worth keeping: a wrapping flex container assigns items to lines by their **hypothetical** main size and only shrinks *within* a line afterwards, so a max-content item is moved to its own row before shrinking is ever considered. This also returns `check_space_budget` to green — it had been red on `main` since `cc8647f`, through three tagged releases, and was the only failing job. Which commit inside `cc8647f` tipped it was **not** bisected; the chip-count mechanism is proven separately by serving a single-language scope, where the same bundle measures 148px and the gate passes |
| 2026-08-02 | A flank route descends to a stub 24px above its destination and turns **down** into the port; the arrowhead is `markerUnits="userSpaceOnUse"` | An SVG marker orients to its last segment, and flank routes ran the corridor straight to the destination's own top-edge y before turning in horizontally — so every arrowhead on a cycle, backward or layer-skipping edge arrived **sideways, flush along the border**. On a real project that is a row of small triangles across the top of each box, which reads as sawtooth decoration rather than as routes arriving, with no visible stub to trace back to a source. Reported by UD from the served build, and it is geometry rather than styling: no marker size or colour fixes an arrow that is parallel to the edge it is entering. 24px is safe by construction because the row gap is `_ROW_HEIGHT - _BOX_HEIGHT` = 64. `userSpaceOnUse` because a strokeWidth-relative head gave the thinnest — and most numerous — routes the smallest arrows, while direction is a fact every route needs equally. The test asserts the property for **every** edge, not the flank case alone, since adjacent-layer routes already satisfied it and the reader's expectation is what is being pinned |
| 2026-08-02 | The Easy structural summary names the **relation** ("Two other files bring it in") instead of counting undifferentiated "parts"; the "Called by" label is left exactly as it was | The panel printed "Called by 0" — `centrality`, call edges only — directly above "Two other parts of your code use it", which counted two *imports*. Both numbers were right and the pair was unreadable, which for this audience spends the same trust as being wrong. The naive fix is the trap: `StudyPanel.jsx` carries a comment recording that "Called by" was chosen over "Used by" precisely to avoid this collision, so **renaming the label would have recreated the very contradiction the comment exists to prevent**. Naming the relation separates the two questions without moving either count, and it keeps import vocabulary where the evidence is an import. Neither number changed |
| 2026-08-02 | The check panel's primary action is `position: sticky`; the study panel's "Read the source" scrolls to the source | One shape, two surfaces: a panel putting its own primary content or control out of reach with no affordance — the class already fixed once on the Map's region caption. Measured: the submit button was 47% covered by the status line at 1440x900 (a hit test at its bottom edge returned the footer) and sat 101px below the fold at 1280x720; the source sat 4144px — 6.6 viewports — below a control literally named "Read the source". Severity is stated precisely because it was not what it looked like: **keyboard users were never blocked**, since focusing the submit button scrolls it into view (`scrollTop` 0 → 241, measured), so this failed silently for pointer users only, which is why neither the space budget (header overlaps only) nor the escape sweep could see it. Only the named control scrolls; every other route to a node still opens at the top of the panel |
| 2026-08-02 | A structure occluded by the System view's orientation panel is **deferred**, not fixed | Sampling six points across that panel's button returns the button at every one, so any body the camera projects into its rectangle is unclickable — the mechanism is general, the occurrence depends on the system's layout (reproduced on `codemble.cli`, absent on `codemble.adapters.base`). The correct fix is to frame the camera into the *unobstructed* canvas region, which is exactly the module that has produced three shipped regressions in this project, and the defect is P2 with three working routes to the same structure (Find, the module index, the connections list). Recorded here rather than left in a report, because the next session should not rediscover it and should not reach for a quick z-index patch either |
| 2026-08-02 | The entrypoint test-bias is a **sort key**, not an edit to `entrypoint_rank` | v0.14.0 added a penalty to the field, and `finalize_graph` runs **twice** on the normal path -- once inside an adapter's `parse_files`, again when `ProjectParser` composes -- so a rule that *adds* is not idempotent: measured, rank 4 became rank 8. It changed no outcome on the projects to hand, which is exactly why a green suite kept it: every new test called `finalize_graph` directly, once, while the composed path is the one every real run takes. It also broke a promise the picker makes and the quickstart repeats -- that the rank shown is the parser's own. A sort key fixes both at once, is idempotent by construction however many times finalization runs, and is the literal reading of the standing rule "bias the ranking, never the reported fact". The regression test goes through `ProjectParser().parse()`, at the seam where it actually happened |
| 2026-08-02 | The camera frames into the largest rectangle no **control** covers (`aimIntoClearRegion`), reserving buttons but not the prose beside them | A planet the camera projected under the System panel's button could not be clicked -- the button took the click and opened the quiz. The layout is parser-owned, so the body cannot move; the camera does, which is the rule `nameAtlas` has always applied to name plates extended to what the camera aims at. Bounded in this order: offset only while the sky still fits the clear region, and push back only as far as it must when it does not. The safety property is what made this affordable in the module that has caused three shipped framing regressions -- with no chrome the clear region IS the canvas, so the scale is 1 and the offset is 0 and the result is bit-identical to the frame it was handed, which is why every existing framing contract keeps asserting the numbers it always did. Only controls are reserved: a `pointer-events: none` paragraph over a star costs nothing, since the star stays clickable and stays visible around the text, while reserving the whole panel would push every system back for a problem only its buttons have. Proven in both directions -- the fixture asserts a body lands under the control BEFORE the fix, so the gate cannot pass vacuously |
| 2026-08-04 | A language focus may never empty a Map tab. The Architecture shelf's fold is a **derived** guard (`unfolded = showUnreached \|\| everyBoxUnreachable`), and the Workflow tab gains an empty state for a root whose rows the focus removed | Folding unrouted boxes is only ever a readability trade made FOR a connected core, so with no core to protect it is never right -- and that is exactly what a focus produces on a polyglot project, because Home is written in one language and nothing in another has an import route to it. Measured: focusing Rust drew **0 of 5** boxes on a 1396x509 canvas, and the guidance chip read "No Home is chosen" two rows below a header reading "Home codemble.cli". `useState` could not catch it alone, and that is the transferable part: its initialiser runs **once**, so the component mounted unfocused (132 unreachable, collapsed) and the focus then cut the set to 5 while the collapse stuck. The Workflow tab failed differently for the same reason -- its guard tested for a MISSING root, and a focus leaves the root and removes its rows, so it fell through to an empty canvas with no message and no way back. This affected 5 of the 7 languages shipped here and every polyglot project. Three audit loops missed it because each audited a single-language path |
| 2026-08-04 | `projectOverview(graph)` describes the project itself, and the star chart opens with it | Every surface answered a question ABOUT something the learner had already found; nothing answered "what is this project?", which is the first question somebody opening a codebase they did not write actually has. It lives in `graphData.js` because it is a derivation from the graph and belongs with the other pure ones, which also gives it the existing contract check. Parser truth end to end, so it needs no API key and cannot disagree with the galaxy or the map -- the same reason the impact widget is graph-layer. Two rules it inherits rather than invents: a project with no Home reports `null` instead of a fabricated one (the Map already carries two empty states for exactly that shape, and the summary must not be the one surface that fills the gap with a guess), and the ranking says "called from the most places" rather than "most important" because centrality counts the distinct structures that call in and that is all it can claim |
| 2026-08-04 | Every scrolling surface draws a scroll shadow, from one rule keyed by `--cm-scroll-cover`; `check_panel_reach.mjs` **sweeps** for uncued scrollers rather than listing them | macOS draws no scrollbar until you scroll one, so an overflowing panel is pixel-identical to a finished one. Five addresses, all silent: study panel 7.8 viewports at 1440x900 and **19.9** at 320x640 with 9-10 headings below the fold, checks panel **0 of 4** answer options at 1280x720/375x720/320x640, star chart 14.6 across 130 rows, Find 4.8, Modules sidebar 11.4 -- the last two being how a learner reaches a module the thinned galaxy does not show, which is the job progressive reveal makes mandatory. The Map's own drawing has carried this fix since 55147ac with a comment describing this exact failure, so nothing here is new; it was simply never generalised. The sweep is the real decision: five addresses for one defect means fixing them one at a time is how the sixth ships, so the gate opens every surface a learner can open and asserts none scrolls without a cue, naming the offender and its depth. The star chart also had to move from the `background` shorthand to `background-color`, since the shorthand reset the cue to `none` -- which is how it failed the first time |
| 2026-08-04 | `position: sticky` is scoped to the quiz's own submit **bar**, never to `.check-primary`; the quiz opens scrolled to its question | Two corrections to v0.14.0, both measured. `.check-primary` is this app's shared primary-button class -- ten buttons across six components, exactly one of them inside a scrolling panel -- so nine inherited stickiness silently. And a sticky *button* is 191px wide inside a 627px option row, so it floated across whatever it passed rather than covering it: at 320x640 it was drawn over **64% of the question the quiz was asking**, with 0 of 4 answers visible. A bar spans the panel and carries the panel's own ground. Opening at the question rather than at the panel's masthead is the other half: the preamble cost 141px of a 437px box at 320 and the answers paid for it. Only when the panel actually overflows, and only on a change of question, so it never fights the learner's own scrolling. After: 4/4 options at 1440, 1280 and 375, 3/4 at 320, question covered 0% everywhere |
| 2026-08-04 | The study panel carries its own **Close**, and the breadcrumb's Home name is a **link** | Both were missing outright rather than misplaced. The study panel's only exit was "Back to the module" in the header rail -- a different region of the screen, reading as navigation rather than as dismissing what is in front of you -- while the checks panel, which opens in the same slot, has carried a Close since it shipped. And Home was named in the breadcrumb and clickable nowhere: the only control carrying the word was **Change Home**, which redefines which module Home *is*, so a learner who had wandered had no route back and the one thing that looked like the way back would have changed their project's starting point instead |
| 2026-08-04 | A Workflow row is one `<text>` with two `<tspan>`s, never a second `<text>` positioned by an estimate of the first one's width | It was `dx={row.label.length * 0.62}em`, and `em` resolves against the meta's **own 11px** while the mono label advances at **13px** -- a systematic ~15% undershoot on every row, so "— possible call" and "— shown above" printed through the tail of the name they described. Reported from the served build as text merging into text. A guess at rendered text width is wrong by construction; tspans flow at whatever width the label actually renders, which is the same reason `nameAtlas` measures plates rather than estimating them |
| 2026-08-04 | The public surface is a **Formal Edo Workbench** led by current v0.16.0 product evidence; PyPI is the binary download source | UD requested a full README/website overhaul that matches the exploration-first app and makes downloads obvious. The previous decorative atlas led with an abstraction while the strongest proof was the product itself. The new signature is the evidence chain—Galaxy, Map, System, Impact, proof—beside an icon-led artifact ledger. The proof frame is a close Home-system view, not a distant Galaxy claim: all four structures visibly glow after the checks pass. Packaged stable and current source both report v0.16.0; the GitHub release carries notes but no uploaded binaries, so direct wheel/sdist downloads and their published SHA256 digests come from PyPI. This supersedes the landing-only parts of the 2026-07-19, 2026-07-22, and 2026-07-29 site decisions; the ensō, Formal Edo palette, reading scale, narrow-screen readable captures, and semantic accent rules remain locked |
| 2026-08-04 | Product capture **owns its disposable server** and public release truth has an executable manifest | Council review found two trust failures in tooling that otherwise looked like documentation: an externally supplied capture URL could clear real progress and inherit a narrator, while a moving package index could make a version-specific one-command claim false between reviews. `capture:docs` now starts a current-source child on a random loopback port with a unique temporary data directory, removes provider configuration, requires reset success, refuses external URLs, and tears the child down. `docs-site/release.json` is the release manifest; `check:release` verifies it against source package versions, PyPI latest metadata, GitHub latest, artifact URLs, published digests, and downloaded bytes. Exact-release commands and source clones are pinned; the short `uvx codemble` route is described honestly as intentionally moving |
| 2026-08-04 | Default-branch cleanup integrates coherent candidates, but preserves any active worktree or unmerged tip that ancestry and patch equivalence cannot prove redundant | The public-site overhaul and three Actions upgrades are coherent units, their workflow YAML parses, and the combined repository gates pass. Only `setup-python@v7` ran there; the upload/download handoff in the release-published/manual-dispatch workflow remains a next-publish verification point. The dirty Dawn Sequence checkout contains user state, the clean `cb1a5c` worktree is still attached, and the stale planning tip remains unmerged; deleting any of them would turn an evidence gap into data loss. Remote or local refs are pruned only after their exact content is reachable from synchronized `main` |
| 2026-08-09 | `galaxyRuntime` owns the complete renderer lifetime behind `update` and `dispose`; `GalaxyCanvas` owns only React projection, keyboard focus, and render-error presentation | Renderer setup, graph commit, framing, guides, particles, Dawn, Name Atlas timers, benchmark work, and WebGL teardown shared mutable refs across eleven React effects, so replacement and cleanup order were implicit. One in-process owner makes stale-callback suppression, host-sized bloom, graph-before-frame ordering, and exact one-time disposal interface outcomes without moving camera decisions out of `galaxyView` or changing public props |
| 2026-08-09 | `measureCanvasOcclusion` is the one owner of canvas viewport, overlay roles, DOM-to-canvas translation, and renderer fallback | System framing and Name Atlas need different obstruction facts, but their duplicated DOM scrapes had already drifted once to the wrong subtree. One immutable measurement result keeps click-taking controls distinct from name-covering chrome while `galaxyView` and `nameAtlas` retain every framing and placement decision |
| 2026-08-09 | Five tree-sitter adapters inherit discovery, `parse`, `parse_files`, finalization, and error translation from one private lifecycle core; their public `LanguageAdapter` signatures and language-owned `concepts` implementations stay unchanged | The five classes repeated the same source-scope and canonicalization protocol while their real value lives in different syntax indexes and graph-draft builders. Centralizing only the invariant lifecycle removes a sixth language's opportunity to drift without turning syntax evidence into a lowest-common-denominator abstraction; a real-adapter conformance suite and captured `Graph.to_json()` baselines pin the seam |
| 2026-08-12 | Home calibration owns a measured responsive decision-list floor; a guidance action yields focus to the foreground surface it opens; and read-only local-server failures retain their last successful view plus the exact retry target | Three current-main failures shared one trust problem: the UI completed its state transition while hiding the choice, moving focus behind the result, or replacing useful folder state with browser-engine jargon. The repair stays in view/mapping ownership: no parser or learner truth changes, no mutating request claims unchanged data, HTTP refusals keep server copy, and one disposable cross-engine gate holds the full failure/recovery paths |
| 2026-08-09 | The star chart exports a fully client-side Markdown project brief derived from `projectOverview(graph)` | Approved by UD as the portable handoff for the existing project summary. The renderer is pure and deterministic; the only browser-specific code creates and downloads the Blob. The brief preserves the app's truth boundaries: no resolved Home says so rather than naming a guess, centrality is described only as "called from the most places", uncertain edges remain hedged, unsupported sources stay visible, and charted remains separate from understood. Easy and Expert change only the control label, never the exported facts |
| 2026-08-09 | Graph schema 10 serializes deterministic region-level import cycles computed only from `certain=True` import edges | Approved by UD as a structural fact, not a new check family. The SCC pass reads raw import edges rather than aggregated `RegionEdge.certain`: one possible sibling makes an aggregate route conservatively possible, but it must not erase a separate proven edge that completes a cycle. Members and components sort canonically; `finalize_graph` clears the field before layout replaces it, because the normal composition path finalizes twice. Possible-only loops are excluded. The Map carries the full prose line in both registers, Easy avoids parser vocabulary, and the star-chart overview and export inherit the same field |
| 2026-08-09 | First Flight is a frontend-only, stateless and re-runnable route: Home, then at most five direct proven imports sorted by region centrality and id | Approved by UD as bounded orientation, not progression. A pure sequencer owns the order and never invents Home; React owns only ephemeral stop position. Every stop dispatches the existing `GO_TO_REGION` travel action, so the one `recordVisit` path charts it exactly like manual travel. The chip reuses galaxy region-route degree for its used-by/uses facts, Easy and Expert change words rather than behavior, and the camera uses the existing frame machinery with zero-duration jump cuts under reduced motion. One `firstFlight` entry joins the ordered Escape arbiter and existing task-deferred focus return. No API, layout mutation, persistence, completion reward, or new check family is added |
| 2026-08-13 | At Galaxy level, colour may connect a route only when the parser proves the import and both endpoints share the same coloured community; bridges stay neutral, possible routes keep uncertainty ink, and amber remains understanding-only | UD asked for subtle colour links that make the Galaxy easier to explore. Tinting every route by a source or destination would imply a shared grouping across a bridge, and tinting a possible route would let a grouping cue read as stronger evidence. A 32% family mix forms a corridor without overpowering node identity. The active pointer or keyboard subject and its one-hop neighbours on the current route mesh take label priority; keyboard selection persists while focus enters the Key, while pointer exit clears transient hover. The Key carries words plus solid/dashed styles at every width, so colour is redundant rather than exclusive |
| 2026-08-13 | Release artifacts are reproducible manifest-owned bytes, published once to PyPI and mirrored with `SHA256SUMS.txt` on GitHub | The standing checklist required a wheel and checksum asset, while the workflow uploaded no GitHub assets and the public checker asserted that absence. `docs-site/release.json` now owns a UTC build epoch, predictable release URLs, and both digests; Hatchling is pinned, `docs-site` is excluded from the sdist to avoid a digest containing itself, and local plus CI builds must match the manifest before trusted publishing. The publish job attaches those exact bytes and the ledger, then re-downloads them and reconciles both registries. Structural checks remain usable before publication; the live check is a separate outside-in gate |
| 2026-08-13 | Graph schema 11 carries parser-owned `RoleEvidence`, and Study derives one bounded, mode-neutral learning journey from certain directed import/call evidence | UD approved a guided Easy mode and change-oriented Expert mode only if both teach the same architecture truth. Roles therefore use a closed enum with stable rule, observation file, and exact span; framework roles require the exact annotation, macro, factory, and receiver binding at the observation site, with project type shadows, lexical locals, hoisted declarations, and rebinding revoking provenance; a partial file contributes no role. An observation may cite a route registration while its node cites the handler declaration. Generic containment and test roles never complete an application route. Missing proof produces a visible break before only target-relevant possible evidence. Connected test-role nodes are selected-feature verification candidates, never coverage or execution claims. Content-derived step IDs preserve place across mode changes, while Impact and Connections appear once as selected-feature facts and existing chart/check progress meanings remain separate |
| 2026-08-14 | Explicit activation owns one long-lived parser with a bounded, source-free, process-memory evidence cache; a changed project takes the conservative full-adapter path before global resolution | No-change work was being thrown away at release, but persistence, watchers, and cached source/tree state would expand privacy and lifecycle authority. Exact root/path/byte/dialect/version/config identity plus per-file graph partitions make invalidation observable without weakening correctness. Matching partitions remain identifiable across one-file changes, but the implementation does not claim structural one-file speed: until adapters expose source-free extraction IR, any miss reparses safely and exact fresh Graph/Map bytes are the gate |
| 2026-08-14 | Parser scale and semantic intelligence have separate executable gates | Faster indexing cannot prove better understanding. Disposable 1k/5k/10k receipts measure cold, no-change, and one-file-change throughput plus fresh equivalence; a hand-authored Python/JavaScript/TypeScript/Go/Java/Rust/C# and mixed oracle independently fails on invented certainty, false role/Home/journey claims, missing certain journey structure, and bounded coverage omissions. New semantic rules require a minimal regression fixture, no new false positive, and real-corpus corroboration |
| 2026-08-14 | The normal cap stays 1,000 until a complete 5,000-module Map passes both Chromium and WebKit; the next renderer is complete canvas delivery, not logical hiding | The backend was ready in 5.13 s at 142 MB RSS and Chromium passed 5,000 boxes/4,999 routes, 35,102 DOM elements, 11.48 MB resources, 4.08 s usable, 31.5 ms Finder p95, recovery, keyboard final-module arrival, and 320 px overflow. WebKit could not stabilize the first-run Skip control inside the 5 s budget while the SVG committed. One-engine success cannot raise a public limit. A canvas renderer may reduce DOM work, but every module must stay represented, searchable, keyboard reachable, and recoverable |
| 2026-08-14 | Graphify, Understand Anything, Archify, Headroom, Streamlit, and TensorFlow are credited only at verified pinned Apache-2.0/MIT revisions | Graphify informed conservative versioned cache identity; Understand Anything informed fingerprints/deletion/fallback while its cosmetic skip was rejected; Archify informed validate-before-replace; Headroom is future narration-only inspiration; Streamlit/TensorFlow are future corpora. Codemble independently reimplemented the selected concepts and added no copied code/assets, dependency, account, paid service, or provider authority |
| 2026-08-14 | The schema-2 complete-Map receipt supersedes the earlier readiness snapshot without changing the 1,000-file decision | Council found that a single current-RSS sample and no warm activation could not prove the declared backend gate. The rerun measured a 4.976 s cold activation, 1.701 s no-change activation, and 151,420,928-byte peak RSS across the full server run; Chromium passed again at 5,000 boxes, while WebKit retained the same unstable Skip failure. The cap therefore remains 1,000 on complete evidence rather than on an incomplete backend claim |
| 2026-08-14 | The schema-3 complete-Map receipt replaces RSS sampling with the server process's OS high-water mark and still keeps the cap at 1,000 | The earlier sampler observed intervals rather than the declared peak. The gate-only server now reports `ru_maxrss`: 4.888 s cold activation, 1.610 s no-change activation, and a 165,314,560-byte process high-water mark all pass the backend budgets; Chromium again passes the complete 5,000-module Map, while WebKit still cannot stabilize the first-run Skip control inside 5 s. The failed cross-engine gate remains visible and continues to block a public cap increase |
| 2026-08-14 | Prepared parser evidence and the live project publish under one activation acceptance lock | A late reset could previously arrive after the last file checkpoint while cache sizing was in progress: binding would be rejected, but exact evidence could still enter the long-lived cache from the cancelled candidate. Validation and canonical-JSON sizing now produce an invisible prepared update; only a still-current, non-cancelled activation commits that update and the live project in one linearized critical section. A regression test pauses during evidence serialization, resets with zero wait, and proves neither project nor cache entry survives |
| 2026-08-14 | The acceptance-locked candidate reruns every scale receipt before integration | Transactional cache publication changes the parser lifecycle even though its payload is byte-identical, so prior timings were not carried forward. The fresh 10k parser receipt is 12.834 s cold, 1.521 s no-change, and 13.062 s one-change with exact fresh Graph/Map equivalence; the fresh 10k Study scan/index medians are 11.308/1.503 ms with 20 exact payload digests; the schema-3 5k gate records 4.956 s cold, 1.666 s no-change, and a 166,789,120-byte OS process RSS high-water mark. Chromium passes and WebKit retains the unstable Skip failure, so the cap remains 1,000 |
| 2026-08-18 | A project's own packaging manifest outranks every other entrypoint signal: `[project.scripts]` and `[project.gui-scripts]` order candidates first in `_candidate_order` | Home never resolved on this repository — five candidates tied at rank 0 (`codemble.cli` plus four maintenance scripts, each with an ordinary `__main__` guard), so `selected_entrypoint` was `None` and a first-run learner met a **34-candidate picker in four scopes before seeing the galaxy**. The evidence was already in the repo: a `__main__` guard says a file *can* be run, while the manifest says which module the installed command *is*. That is stronger evidence, not a heuristic, which is why it may outrank the existing signals rather than merely break their ties. Three guardrails keep it inside the Correctness Contract, and each closes a specific way this could have lied: the stored `entrypoint_rank` is untouched, so the picker still shows the parser's own number as promised; a declared module the parser never saw contributes **nothing**, so a manifest can never invent a candidate; and a missing or malformed manifest is ignored rather than raising, so a broken TOML file cannot take down a parse. It biases the **sort key** rather than the field — the lesson `finalize_graph` already learned the hard way, since the normal path finalizes twice and a field mutation compounds. Proven in both directions on this repository: `None` + 34 candidates before, `codemble.cli` with no question asked after |
| 2026-08-18 | "Is a Home chosen?" is answered from the **unfocused** graph; a Home outside the current language focus gets its own reason naming the language, in one clause | The guidance chip told the learner "No Home is chosen, so there is no route to measure from." two rows under a breadcrumb reading "Home codemble.cli". `homeChosen` was computed from `graph.regions` — the *language-focused projection* — and Home is written in one language, so focusing another filtered it out and the whole-project fact flipped. Exactly the root-cause shape of the v0.16.0 Map defect that broke 5 of the 7 languages shipped here, and the same principle the 2026-07-29 `community_family` row records: a question about the whole project must not be derived from a filtered view, or the answer changes with the filter. **The first fix was itself wrong and the measurement is the reason it changed**: written as a full explanatory sentence matching the Map's empty state, the copy measured **106px of guidance strip against 62px** — and that strip is already the tightest thing on a 320px screen, where this project has had to defend it before. Naming the language is the entire fact; "so there is no route to measure" is what the missing distance already says. The four distance reasons also moved out of a five-deep nested ternary into one named helper, because telling them apart is the whole job and collapsing any two tells the learner something untrue |
| 2026-08-21 | A Study arrival focuses the evidence surface it opened; ordinary navigation owns the module heading and `Read the source` owns `Real source` | Both launch controls are removed by the route transition, so leaving focus to the browser dropped a keyboard learner onto `<body>` with no announced destination. The two routes make different promises and therefore need different focus targets. Connection navigation also resets the panel before focusing the new module, preventing a stale scroll position from presenting the middle of a different file as its beginning. A failed source request promotes its visible failure heading, while ordinary data readiness does not refocus anything — completion is not a second arrival and cannot steal a learner's chosen control. Retry is separate from navigation so a recovered explicit source request preserves its destination; ordinary Study and narration retries focus the persistent heading before their buttons unmount. This is presentation ownership only: no parser evidence, learning state, or graph navigation changed |
| 2026-08-21 | v0.19.1 is a five-loop interaction-polish patch; current public release copy and captures follow its one manifest | The five findings are all presentation or browser-semantics defects: an action named only as state, duplicate completion controls, code/path inputs inviting irrelevant browser services, native controls without a declared dark scheme, and a scrollable compact Map with no continuation cue. None authorizes a second parser truth, new progression, hidden module delivery, or a scale-cap change. Recapturing the nine product frames and replacing stale 190-system/v0.18 captions keeps public evidence aligned with the same current self-parse rather than inventing a marketing count; the fresh capture's 199 systems include the new executable interface contract itself |
| 2026-08-21 | v0.19.1 becomes stable only after exact-tag outside-in proof; the evidence-only truth commit follows the fixed tag | Two council rounds found and closed a polluted-sdist digest, an overstated cross-engine claim, and stale Architecture alt text before unanimously passing the rebuilt candidate. Tag `v0.19.1` (`d0571fc`) peels to `198c0d7`; main CI `32504359987`, Pages `32504360042`, and trusted publish `32505026702` are green. Fresh GitHub bytes, PyPI, and `SHA256SUMS.txt` agree on wheel `777f53e0…3818b` and sdist `d24c567f…3510`; a cold Python 3.11 install reports 0.19.1 and carries `index-r9nFEgOG.js` plus `index-Dtb10tPf.css`. The follow-up changes only this operating truth and must never move the release tag |
| 2026-08-21 | Compact Menu dismissal is owned by the window Escape arbiter, and the compact quiz owns the footer row below the rail | WebKit does not guarantee that a pointer-clicked button receives focus, so the rail subtree could not hear Escape when focus stayed on body; one ordered window owner closes it and restores Menu focus without navigation. The quiz's absolute panel ended above the footer with 437px at 320x640, so top-aligning the question still put the final answer under the sticky action through 405px. Using the same fixed below-rail boundary as Study gains the otherwise redundant status row while preserving the rail, sticky action, parser-owned question, and all four complete answer targets |
| 2026-08-21 | Compact quiz arrival sets the panel scroll position directly and repeats alignment after local fonts settle; its browser gate measures after the 420ms panel entrance | The first v0.19.2 exact-main CI run proved that Ubuntu WebKit could ignore `scrollIntoView({behavior: "instant"})` during panel entry even though Chromium and macOS WebKit accepted it: at 320x640 all four 84px answer rows existed, but the last sat at 779-863px behind an action beginning at 588px. Direct scroll ownership removes that engine-dependent request, and the post-font alignment makes late identifier wrapping explicit. The repair preserves the 124px navigation rail, complete parser-owned identifiers, and 44px targets rather than passing by truncating or shrinking the choices |
| 2026-08-21 | v0.19.2 becomes stable only after the failed first candidate is repaired and the replacement tag passes exact-SHA outside-in proof | The first main candidate correctly remained unreleased when Ubuntu WebKit exposed the hidden fourth quiz answer. Replacement tag `v0.19.2` (`af33aa0`) peels to `466c130`; main CI `32547669499`, Pages `32547669498`, and trusted publish `32548094677` are green. Fresh GitHub bytes, PyPI, and `SHA256SUMS.txt` agree on wheel `8d6183d2…7492a6` and sdist `b570ecc3…50ad7`; a cold Python 3.11 install reports 0.19.2 and carries `index-BpwjRXVi.js` plus `index-DgSklSeG.css`. The follow-up changes only this operating truth and must never move the release tag |
| 2026-08-24 | The complete Map uses one complete prepared scene per explicit language projection and a native-scroll viewport canvas; culling is draw delivery only, never logical LOD | A 5,000-box SVG created 35,102 DOM elements and destabilized WebKit before first-run interaction. The default all-language canvas retains all 5,000 boxes and 4,999 routes while drawing five or six visible boxes with 99 DOM elements; language focus remains a named learner-controlled projection. Backend coordinates, certainty, language, progress, Finder, recovery, and accessibility remain authoritative; one position-aware active descendant replaces thousands of tab stops, and hit testing accepts only emitted box coordinates plus renderer-owned painted-row bounds. Removing the canvas still leaves the complete current projection and every navigation target in data |
| 2026-08-24 | The ordinary supported-file cap moves from 1,000 to 5,000 only after the schema-4 backend, Chromium, and WebKit receipt passes | The final candidate records 4.870 s cold, 1.668 s no-change, 170,606,592-byte process RSS high-water, complete 5,000/4,999 source-scene counts, 99 DOM elements per engine, 32.9–40.9 ms canvas arrival with item-specific active-descendant identity and 5,000-of-5,000 set position, 30.9–31.0 ms Finder p95, 76.0–81.1 ms recovery, and zero 320 px overflow. The previous one-engine result did not authorize promotion; this cross-engine result does. Above 5,000 remains an explicit scope prompt, not a hidden or unbounded claim |
| 2026-08-24 | Pages proves the live release ledger before deploying release copy | A main version-bump commit can land before trusted publishing finishes, while the site already says the new version is stable and PyPI-published. The Pages workflow now retries the outside-in release check for a bounded ten minutes before building: ordinary docs changes pass immediately, and a release transition waits until PyPI metadata, GitHub release assets, downloaded hashes, and `SHA256SUMS.txt` match the committed manifest. This preserves exact-main CI and tag ordering without briefly publishing a future version as stable |
| 2026-08-24 | A release candidate proves hosted CI on a PR, then publishes its exact local-main tag before moving origin/main | GitHub renders default-branch README copy independently of Pages, so pushing a version-bump commit to main before PyPI would still label an unpublished version stable. The candidate branch and PR give the exact commit hosted CI; local main then fast-forwards to that reviewed commit and owns the annotated tag while origin/main remains on the prior stable release. Only after trusted publishing and outside-in artifact proof does that same commit move origin/main. README media is tag-pinned, so PyPI never borrows older default-branch screenshots during the transition |
| 2026-08-24 | Source archives exclude and reject parser-fixture outputs that are intentionally ignored by the fixture repository | Hatch's sdist selection could include `sampleproj/generated/` and `sampleproj/ignored.py` after the local parser tests exercised that fixture, even though a clean checkout of the same commit had neither file. The exact-tree gate stopped publication when the two archives differed. Explicit build exclusions now make exercised and clean checkouts byte-identical, while the release-fact gate rejects either path if it ever returns; developer/runtime marker exclusions remain independently enforced |
| 2026-08-24 | v0.20.0 becomes stable only after candidate CI, exact-tag publication, outside-in artifact proof, main CI, Pages, and a cold install agree | Annotated tag `v0.20.0` (`9abf14a`) peels to release commit `436cbee`; candidate PR CI `32769180402`, trusted publish `32770056876`, main CI `32770203502`, and Pages `32770203426` are green. Fresh GitHub bytes, PyPI, and `SHA256SUMS.txt` agree on wheel `15e42dee…cf61` and sdist `466e5f5b…b008`; a cold Python 3.11 install reports 0.20.0 and carries `index-DzCSIcHk.js` plus `index-R8cZVoqz.css`. Obscura rendered the deployed 203-system surface without failed images, overflow, or console errors. Native Safari remained unavailable on the locked Mac and is not claimed; issue #13 remains open. The follow-up changes only this operating truth and must never move the release tag |
| 2026-08-25 | First run offers **Explore freely** or **Take a first flight**, and every landing can switch Easy/Expert without changing its graph target | Approved by UD as the adventure/onboarding fork. Explore dismisses coach marks and opens the complete Galaxy; guided launch durably commits the chosen register through `LearnerSession` before starting the existing bounded First Flight. A landing brief derives its kind, source span, summary, and connections from the selected node and graph edges. No free flight, XP, score, completion badge, saved voyage, new quest type, or second truth is introduced |
| 2026-08-25 | Galaxy scenery and System worlds may deepen only as deterministic non-semantic art; amber, certainty, positions, and routes keep their prior owners | Approved by UD's game-level visual request within the existing locked limits. A hash-seeded spiral disc, core/dust, far/near star shells, nebula variants, reticle, vignette, and proven-route particles add depth at Galaxy range; seeded terrain, mineral bands, atmosphere, tilt, and slow rotation deepen System worlds. All are disposable renderer materials, respect reduced motion, and encode no fact. The existing no-procedural-surface rule at 5,000-system Galaxy range still holds: rich body surfaces remain System-only |
| 2026-08-25 | Ruby and PHP join the adapter seam with conservative certainty and official MIT grammar wheels | Both adapters extract modules, types, methods/functions, imports/includes, explicit calls, entrypoint evidence, and syntax-anchored concepts; Ruby also emits native entrypoint roles, while PHP intentionally emits no role evidence. Dynamic dispatch stays possible and partial files fail closed to module evidence. The ten-case oracle and pinned Rails/Laravel corpora guard omission, invented certainty, scale, and deterministic bytes. tree-sitter-ruby `ad907a69…` and tree-sitter-php `3fda2fb…` were license-verified; no implementation code or assets were copied |


## Non-Goals — do NOT build (point here when asked)

- ❌ ~~Free-flight 3D navigation~~ — superseded 2026-07-21: **bounded orbit** is
  approved (see Decision Log). The camera may rotate and zoom around the current
  subject; panning, free translation, and any control that can leave the subject
  off screen remain out
- ❌ XP, streaks, levels, leaderboards — **amended 2026-08-02**: the
  explorer's trail (visiting a region charts it, persisted) is approved as a
  *map record*, not meta-progression. Nothing accumulates into a score, there
  are no levels or streaks, and it may never light a star. Amber still comes
  only from checks
- ❌ ~~A second 2D renderer/toggle in v1~~ — superseded 2026-07-19: the 2D Map layer is approved (see Decision Log); free-form/client-computed 2D layouts remain out
- ❌ Accounts and multi-user. The read-only share is the only permitted cloud
  touch, and it remains blocked until M20's local preview, expiry, deletion,
  storage, browser, and operational evidence gates pass
- ❌ Extra quest types before Phase 3
- ❌ GitHub-URL ingestion in v1
- ❌ ~~Elaborate game art before the loop teaches well~~ — **amended
  2026-07-29** (see Decision Log): deterministic procedural celestial art is
  approved **at the System tier only**. Bodies there carry an fBm crust, a rim
  atmosphere and slow surface rotation. What remains OUT: procedural surfaces
  at Galaxy range (a level-of-detail limit, not a taste one — up to ~5,000
  systems draw there), and any decoration that is not seeded purely by node id.
  Decoration may never encode a fact; every semantic channel stays parser-owned

## Gotchas

- **`base: "/Codemble"` is load-bearing and case-sensitive** — wrong case
  breaks every asset/link on GitHub Pages.
- **Starlight is 0.41.x, not 1.x** — `social` is an array of
  `{icon,label,href}`; logo uses `light`/`dark` keys. Don't scaffold against
  1.x docs.
- **`tokens.css` before `custom.css`** — custom.css resolves variables tokens
  defines; reversing the order silently unstyles the site.
- **Sidebar has no autogenerate** — a new docs page without a sidebar entry is
  invisible.
- **Docs CI uses `npm install` (not ci/pnpm), node 22** — match
  `pages.yml`/`ci.yml`; don't introduce a second package manager.
- **Determinism in scripts/layout:** galaxy layout must be seeded by content
  hash, never wall-clock or Math.random at render time — "same code → same sky"
  is an acceptance criterion.
- **The learner is the invariant:** when accuracy and delight conflict,
  accuracy wins. A wrong explanation is a top-severity bug, not a nitpick.
- **The app and website palettes are forked** — `web/src/tokens.css` owns the
  dark local instrument; `docs-site/src/styles/tokens.css` owns the public
  dark/light surfaces. Preserve the shared meaning rules, but never re-add a
  cross-directory import. App CSS changes still require rebuilding and
  committing `codemble/web_dist`.
- **Canvas colours must be plain values, never `color-mix()`** — WebGL receives
  a custom property's authored text, so a computed token renders black. Add new
  canvas tokens through `readPalette`, which resolves them.
- **`var()` never works in an SVG presentation attribute** — `fill="var(--x)"`
  is invalid and falls back to the cascade *silently*, which is how the map's
  language stripe rendered box-navy for a release while the legend advertised
  three colours. Use `style={{ fill: … }}` (a CSS property) for any
  token-driven SVG paint.

## Edge cases & limits

- >~5,000 supported source files → prompt to scope to a subdirectory
- No clear entrypoint → ranked candidates; user picks Home
- Syntax errors / partial parses → parse what you can, flag the rest, never crash
- Missing/invalid key → galaxy + structure + checks work; explanations show "add your key"
- Unsupported-language files → outside the graph and never guessed
- No WebGL → the complete Canvas 2D Map remains available; the 3D Galaxy does not

## Definition of done — Phase 0

A learner runs `codemble ./their-python-project`, flies (on rails) through an
accurate galaxy of their own code, zooms into Home, reads correct grounded
explanations and Python-idiom lessons, passes checks, watches stars light up
and their star chart grow — and comes away actually understanding the project.
Zero invented facts. Screenshot-worthy at every zoom level.

## Definition of done — Phase 1

A learner runs one command on a Python, JavaScript, TypeScript, or mixed project
and gets one deterministic parser-proven galaxy. They can focus a language
without changing graph truth or progress, study exact source with that
language's parser-anchored Lens, and keep uncertain or partial evidence visibly
honest. The tagged wheel includes the production app and installs without Node.
