# Planetary expedition — design review candidate

Status: implemented, verified and merged through PR #47; public release remains gated. Owner request (2026-09-10): full creative control for a lifelike, game-quality Galaxy, design council before implementation, validation, main cleanup, deployment and a new release.

## Direction

Codemble becomes a luminous expedition through the learner's actual code. The signature is the arrival at a detailed world: lit coastlines, cloud shadows, icy ridges or swirling mineral bands with a crisp atmospheric horizon, then the real source beside that same world. This is illustrative space art, not an astronomical simulation or a claim about the code's purpose.

References, consulted 2026-09-10: [No Man's Sky Worlds II](https://www.nomanssky.com/worlds-part-ii-update/) for differentiated terrain and material response; [Outer Wilds](https://www.mobiusdigitalgames.com/outer-wilds.html) for memorable individual destinations and readable exploration. Original shaders only; no copied code, game assets, new service, or runtime network requests.

## Three views

Galaxy: retain every parser-owned system and its exact coordinates. Replace the faint repetitive spiral wash with layered, filamented blue/lapis interstellar dust, dark lanes and a luminous distant centre. Use only a fixed number of backdrop draws and the existing bounded star buffers. Backdrop remains below labels/routes, cannot intercept clicks, and never borrows check-only amber. Do not put per-planet procedural shaders on the 5,000-system Galaxy tier.

System: retain the module Sun and exact function/class positions. Worlds gain distinct seeded oceanic, glacial, rocky and banded surface treatments, derivative terrain normals, polar caps, thin optically layered atmosphere and slow cloud movement; existing language profiles modulate them without inventing a role. Surface archetypes vary by node ID, and the Key must say surface detail is illustrative. Class rings remain an explicit kind channel. No fake moons, stations, routes, coordinates, temperature or habitability data. Keep current safe body extents until live inspection proves any enlargement safe; no altered graph layout. Refine the Sun into granular plasma with a restrained corona so surfaces remain legible. Remove the flat artificial system floor disc and replace it with depth behind the real bodies.

Study arrival: use the existing click/Enter/First Flight landing. Frame the actual selected body close enough to read terrain, in the unobstructed area beside the existing Study panel. Camera decisions remain in galaxyView; runtime supplies the measured viewport and control/panel obstructions. Keep the full body in view, fit the true rendered radius, and reframe on resize without stealing a user's deliberate orbit. Compact screens retain the full Study experience instead of squeezing in a decorative thumbnail. Escape/Home/Find retain their existing semantics. No new navigation mode, first-run gate or progression.

## Visual system

Preserve the app's existing Formal Edo typography: Shippori Mincho for sparse destination headings, Zen Kaku Gothic New for readable copy, JetBrains Mono for real identifiers. Keep existing token meanings and accessible controls. Scene palette: abyss #091226, kachi #131f4b, ruri #9abfff, icy gofun #dce7f5, muted blue-teal #75b9bd; kohaku comes only from the existing understood token. Materials derive semantic tints from readPalette/graphData; new cool scene shades must not repaint communities or language identity. No bloom increase as a substitute for detail. No blur on names or source.

## Motion and resources

One existing runtime owns and disposes all meshes/materials/textures/listeners. Share sphere geometry. Bound fragment work; reuse noise samples where possible. Surfaces rotate around their own centre, never move graph positions. Reduced motion freezes clouds, spins and camera arrivals immediately, including Study; no ambient screen shake, flashes, auto-camera orbit or mandatory animation. Scene survives Galaxy/Map remounts and repeated navigation. Map remains the complete non-WebGL path.

## Implementation and acceptance

Primary files: celestialBodies.js (surfaces/atmosphere/Sun), galaxyMaterials.js (backdrop), galaxyView.js and galaxyRuntime.js (measured close arrival), small Key copy and targeted style changes only if needed for legibility. Renderer contract tests cover deterministic identity, semantic colours, uncertainty, reduced motion, radius/framing and recursive disposal. Live before/after captures at 1440x900 and 320x640, both motion modes, Galaxy→System→Study→System→Galaxy, neighboring-system travel, keyboard/Find/Map, real code source, shader compilation and console errors. Exercise a multi-world system and all nine language profiles. Run full frontend/Python/docs gates, existing Chromium/WebKit flows, space/Escape/panel checks and complete 5,000-module gate. Measure normal-speed visible frame intervals on the documented host; report measured scope, never a universal FPS promise.

## Delivery boundary

Current main is 566624e; public stable is v0.22.0. Main contains M20 local share machinery with an explicit independent-node operational release gate. This design does not enable or deploy share delivery, weaken that gate, or claim independent infrastructure evidence. Finish graphics and all local gates first; prepare a concrete release candidate. Publication must satisfy the existing gate or obtain an explicit, narrowly scoped owner amendment after the candidate is reviewable. GitHub reads and SSH pushes work; PR #47 was created through the authenticated browser because connector writes are unavailable.

Main cleanup inventories every local/remote branch and worktree, preserves the dirty high-end-galaxy worktree and two intentional root backup markers, integrates only independently verified unique relevant source, and removes only proven redundant refs after synchronization. The prior interrupted Codex task “Clean up Codemble branches” can be archived once its work is actually superseded; do not archive unrelated work or unresolved decisions. No false release-completion claim if authentication or existing operational gates remain blocked.

## Final pre-implementation acceptance contract

Reference host: Apple M4, 24 GiB memory, macOS; record browser/OS versions with receipts. Compare baseline and candidate on the same fixture, viewport, DPR=1, motion mode and visible/headed engine, after a five-second warmup, for 15 seconds. Median and p95 frame interval may regress by no more than 25% (allow 2 ms scheduling noise); ordinary self-parse System/Study must also keep p95 below 50 ms on this host. Report results only for this host. Test a dense single-module 250-structure fixture independently; preserve all bodies and simplify decorative material work if its candidate exceeds the baseline by 25% or p95 exceeds 100 ms. Existing complete-Map gate thresholds remain unchanged and must pass in both engines.

Shader limits: four octaves per fBm, at most four fBm calls plus three single noise samples per planet fragment, one surface plus one atmosphere shell (clouds integrated in the surface, no additional mesh), shared sphere geometry. Background adds at most two fixed draws beyond current sky. Dense systems may use a cheaper shader with the same seeded archetype/tint/identity; never remove structures. No texture fetch or generated per-world image cache is needed.

Visual acceptance: same-fixture before/after Galaxy and System framing; System examples visibly distinguish the four archetypes at ordinary desktop zoom. Desktop Study targets a complete body diameter of 180–320 CSS px in a clear area at least 360 px wide, with terrain, clouds and horizon distinguishable. Include actual ring/atmosphere extents in camera fitting. If viewport cannot provide that space, preserve evidence and navigation with the ordinary compact Study layout; claim no cinematic close-up there. Sun glare and distant dust must remain subordinate to destination/name/source, checked in captured shadowed and illuminated hemispheres, overlapping bodies, and matched understood/ununderstood states.

Edge matrix: module-only, single-world, 250-world dense module, real classes and long identifiers, possible calls, all nine languages, all four surface archetypes, ununderstood/understood/partial states. Names and focus remain readable on the brightest backdrop; possible routes stay dashed and recognisable in greyscale. At 320×640 and 200% zoom, complete source, controls, Key, Find and Map remain reachable.

Camera/lifecycle: rapid successive selections finish at the last selected real node. Arrival and automatic resize fit into the measured clear rectangle; user orbit is preserved on ordinary updates and resize unless safety requires a distance-only correction to avoid clipping the subject. Return from Study restores the System overview. Changing reduced-motion preference during travel cancels animation and lands at the same deterministic final frame. After ten full Galaxy→System→Study→System→Map→Galaxy loops and a final warmup, renderer geometry/texture/program counts must plateau (allow one-time shader compilation only), with no surviving runtime timers after teardown.

Design gate completed before implementation: Round 1 evidence, coverage, risk and outcome each APPROVE_WITH_NITS; the appended acceptance contract resolves their requested measurable visual, performance, edge-case and lifecycle criteria. Round 2 each APPROVE with no remaining design blocker. This receipt approves the design, not an untested implementation or release.

## Implementation evidence

The implementation adds four seeded surface archetypes, integrated moving clouds and relief, thin atmospheric horizons, granular Sun plasma, a feathered corona and a fixed-cost nebula vault. Study fits the selected body beside source, keeps labels attached and preserves deliberate orbit on safe resizes. A safety resize changes distance/aim only when needed. Class rings remain distinct. Reduced motion updates live, and disposed renderers release their GPU contexts. Long Study citations now wrap inside their own grid track.

Visible Chromium 149, DPR 1, 1440×900 on the documented Mac: 5 s warmup and 15 s samples. Baseline/candidate p95: fixture System 17.4/17.5 ms, Study 17.4/17.6 ms, 250-world dense System 17.4/17.6 ms; same-source self-parse System 17.6/17.2 ms and Study 17.5/17.3 ms. All medians approximately 16.7 ms. Ten navigation loops plateaued live GPU allocations; switching to reduced motion preserved selection and produced identical rendered frames 600 ms apart. These are host-specific frame intervals, not universal FPS guarantees.

The 19-capture matrix covers all nine languages, partial/module-only systems, Study landing briefs for real code, narrow layouts, serial selection and actual check-earned understanding. Its CSS-magnified frame is exploratory, not full-browser zoom acceptance. The separate interaction gate reaches actual source, Key, Find and Map at a 720×450 effective viewport (1440×900 at 200% zoom); this proves responsive reachability rather than browser zoom rasterization. Three overlapping selections complete at the last selected structure; changing motion preference during its 420 ms arrival preserves selection. Settled frames 600 ms apart allow only isolated one-level GPU rounding, with the pointer parked outside the scene so hover labels do not affect the comparison. Native Safari rendered Galaxy, System and Study. The scene is detailed illustrative space art; no photorealism claim.

The unchanged 5,000-module acceptance gate exposed repeated whole-project scans in Python import resolution and check generation. A dotted-prefix index preserves implicit namespace and alias behavior; check generation only unions tiny option pools. Pinned check suites and namespace/external-prefix regression coverage pass. Full Python suite: 677 passed. The complete 5,000-module gate passes unchanged in Chromium and WebKit: 2.294 s cold activation, 1.097 s warm activation, 204,636,160-byte peak RSS. Earlier loaded-host failures remain in the local evidence directory. All five hosted checks passed on final candidate `7cffd7d` in run `34548695851`.


## Cleanup disposition

Baseline `566624e`; candidate PR [#47](https://github.com/udhawan97/Codemble/pull/47). Source changes and matching built assets are at `b2aaa29`; performance receipts predate that commit but match its recorded graphics digest. Evidence directory: `/tmp/codemble-planetary-evidence`.

| Candidate | Evidence and disposition |
| --- | --- |
| m20-ops-alerting, m20-share-ops-deepening, userflow-v0.19.2 | Ancestor-merged, no unique relevant work, unattached; removed local branches. |
| M20 encrypted-storage and privacy worktrees | Clean, already merged tips `01288d6` and `5b6dfb9`; removed exact worktrees and branches. |
| high-end-galaxy | Committed tip is already ancestral; dirty files remain user-owned. Rescued citation grid/wrapping fixes and a maintained containment gate into this candidate. Preserve the worktree and branch. |
| friendly-wizard-claude/work-planning-f2e933 | Unique `34c740e` pause/resume planning record; preserve. |
| Dependabot PRs #43–46 | Unique parser/cryptography/font dependency changes need their own compatibility review; preserve all four remote branches. |
| Root backup markers | `.git-backup-remote` and `.last-git-backup-ts` are intentional user state; preserve. |
| Planetary candidate and detached comparison | Owned by this run; remove only after candidate integration and final evidence capture. |

Implementation council completed two rounds with all four roles. Reviewers accepted the evidence-bounded candidate; coverage required the complete-Map, interrupted-travel and effective-zoom checks above. The coverage reviewer re-inspected the completed gates and approved local graphics acceptance; hosted checks then passed on the final candidate. M20 operational proof and any public-release exception remain separate, explicit gates.


Promotion receipt: PR #47 squash-merged as `e1cf18f8ce0fecc17d9f02bc4d8e682dc05ee389`; candidate and merge share tree `263c2a8469f7d9b34f0ed90ea19ab822f416e0f8` and identical combined patches. Both owned worktrees and the local/remote planetary branch were removed after proof. The two superseded Codex tasks were archived. All 32 protected files retained their exact pre-merge hashes. Main's graph was refreshed and a scoped Study-resize query passed. This subsequent documentation-only receipt records completion without altering the verified application. Public stable remains v0.22.0; no release tag or provider deployment was created.
