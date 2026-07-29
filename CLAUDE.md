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
| `codemble/adapters/` | LanguageAdapter seam; `python_ast.py` is the first adapter (M1) |
| `codemble/graph/` | Language-tagged graph + render-ready metadata (the frontend is a pure consumer) |
| `codemble/lens/` | Language lens: parser-detected idiom annotations → teachable notes |
| `codemble/checks/` | Active checks generated FROM the graph; answers never come from the LLM |
| `codemble/llm/` | Anthropic + OpenAI providers, BYO key, disk cache; narration only |
| `codemble/server/` | FastAPI: serves SPA + graph/checks JSON API |
| `codemble/progress/` | Local persistence: illumination + star chart (`~/.codemble/`) |
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
- **Semantic zoom, three levels, no free flight:** 1) **Galaxy** — modules =
  star systems, imports = routes, entrypoint = Home; camera on rails. 2)
  **System** — functions/classes as planets in deterministic orbits, call
  edges. 3) **Study** — panel with real source, grounded explanation, language
  lens note, checks; scene dims behind it. Scripted fly-to transitions.
- **Illumination is the game:** nodes start dim; passing a region's checks
  lights them permanently. **A region = one star system = one module** — the
  unit of checks, lighting, and invalidation. Star chart tracks language
  concepts. No other meta-progression.
- **Persistence:** local JSON in `~/.codemble/`, keyed by project path + file
  hashes; a changed file re-dims only its region.
- **Polyglot (from Phase 1):** nodes are language-tagged; users filter/focus
  the galaxy by language, each language with its own idiom lens.

## Architecture rules

1. **LanguageAdapter seam:** every language implements `discover(path)`,
   `parse(path) -> Graph`, `parse_files(root, files) -> Graph`, and
   `concepts(node) -> [ConceptAnnotation]`. Python first via stdlib `ast`; all
   later languages via tree-sitter. Nothing above the seam hardcodes a language.
   The JS/TS adapter reuses one internal syntax-evidence index across entrypoint,
   call, binding, and concept passes without widening this public seam.
2. **The graph is render-ready:** graph layer computes language, LOC,
   centrality, entrypoint rank, region id, understood-state. `LearnerSession`
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
5. **Check answers come from the graph, never the model.**
6. **Approximate call edges are labeled "possible call."**

## Repo, docs & website ops

- **Docs site:** Astro 7 + Starlight 0.41 in `docs-site/`, deployed by
  `.github/workflows/pages.yml` to `https://udhawan97.github.io/Codemble/`.
  `base: "/Codemble"` is case-sensitive and must equal the repo name.
- **Sidebar is hand-authored** in `astro.config.mjs` — every new docs page
  needs a manual `{label, slug}` entry or it won't appear.
- **Design system:** `docs-site/design.md` is locked; `src/styles/tokens.css`
  is the value source of truth and **must load before** `custom.css`. Genre is
  the Edo star atlas on the Formal Edo palette. Two accents, one job each:
  kohaku amber = understanding/progress, ruri lapis = interaction — kohaku may
  never mark a navigation state. WCAG 4.5:1 floor on both grounds.
- **Plate artwork is generated:** `node docs-site/scripts/build-plates.mjs`
  rewrites `public/brand/plates/` from a fixed seed. Edit the script, never the
  SVGs; commit the output (the site never runs it at build time).
- **Site search is Pagefind**, which only exists after `npm run build` — the
  field says so in `npm run dev` rather than failing silently.
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

**NOW — Phase 1 tester evidence.** Exercise the shipped v0.2.0
Python/JavaScript/TypeScript and mixed-project loop on real learner projects.
The v0.1.0 Python learner-acceptance issue stays open in parallel; technical
completion does not claim those external runs passed.

**NEXT — Phase 2 (months ~3–6).** Go/Rust/Java adapters, LOD culling +
clustering for larger repos.

**LATER — Phase 3 (months ~7–9).** Shareable read-only galaxy link (the only
cloud touch). Extra quest types: trace-a-request, fix-the-failing-test.
Polish, then the coordinated launch (Show HN / X; lit-galaxy GIF as hero).

## Current State **[AGENT-MAINTAINED]**

**Current milestone: Phase 1 tester evidence** · Last updated: 2026-07-29 ·
Session note: the public website no longer assumes browser zoom. Its reading
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

## Decision Log **[AGENT-MAINTAINED — append only]**

| Date | Decision | Why |
| --- | --- | --- |
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
| 2026-07-29 | The public site uses an 18px prose baseline and 14px informational floor; 1440px product captures stay on a readable full-size canvas with explicit horizontal pan on narrow screens. The cinematic Atlas Journey runs only at ≥120rem and widens its measure there | The previous layout rendered supporting copy at 12–14px, desktop captures at 704px, and mobile captures at 333px. That made the real UI inside the images impossible to inspect without browser zoom. The website scale is intentionally separate from the dense local-app instrument scale, and the tatebanko remains the site's one decorative signature |

## Non-Goals — do NOT build (point here when asked)

- ❌ ~~Free-flight 3D navigation~~ — superseded 2026-07-21: **bounded orbit** is
  approved (see Decision Log). The camera may rotate and zoom around the current
  subject; panning, free translation, and any control that can leave the subject
  off screen remain out
- ❌ XP, streaks, levels, leaderboards
- ❌ ~~A second 2D renderer/toggle in v1~~ — superseded 2026-07-19: the 2D Map layer is approved (see Decision Log); free-form/client-computed 2D layouts remain out
- ❌ Accounts, cloud hosting, multi-user; share link waits for Phase 3
- ❌ Extra quest types before Phase 3
- ❌ GitHub-URL ingestion in v1
- ❌ ~~Elaborate game art before the loop teaches well~~ — **amended
  2026-07-29** (see Decision Log): deterministic procedural celestial art is
  approved **at the System tier only**. Bodies there carry an fBm crust, a rim
  atmosphere and slow surface rotation. What remains OUT: procedural surfaces
  at Galaxy range (a level-of-detail limit, not a taste one — up to ~1,000
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
- **`web/src/tokens.css` imports the docs-site tokens across directories** —
  editing `docs-site/src/styles/tokens.css` restyles the app with no signal and
  no rebuild. `codemble/web_dist` is a committed build artifact, so a token
  change only reaches users after `cd web && npm run build` is re-run and the
  result committed.
- **Canvas colours must be plain values, never `color-mix()`** — WebGL receives
  a custom property's authored text, so a computed token renders black. Add new
  canvas tokens through `readPalette`, which resolves them.
- **`var()` never works in an SVG presentation attribute** — `fill="var(--x)"`
  is invalid and falls back to the cascade *silently*, which is how the map's
  language stripe rendered box-navy for a release while the legend advertised
  three colours. Use `style={{ fill: … }}` (a CSS property) for any
  token-driven SVG paint.

## Edge cases & limits

- >~1,000 supported source files → prompt to scope to a subdirectory (LOD arrives Phase 2)
- No clear entrypoint → ranked candidates; user picks Home
- Syntax errors / partial parses → parse what you can, flag the rest, never crash
- Missing/invalid key → galaxy + structure + checks work; explanations show "add your key"
- Unsupported-language files → outside the graph and never guessed
- No WebGL → clear requirements message (no 2D fallback in v1)

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
