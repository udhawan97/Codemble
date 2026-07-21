# Changelog

All notable changes to Codemble are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Changed
- The 2D Architecture map is now a deterministic layered diagram rather than
  a straight-line grid: four barycenter sweeps reduce import-edge crossings,
  backend-assigned ports keep fan-out distinct, weighted arrowed paths expose
  direction, and cycles or long routes travel around the diagram flank. Possible
  relationships remain dashed, and React still consumes graph-owned geometry.

## [0.5.3] - 2026-07-21

### Fixed
- **A fresh install crashed on every JavaScript/TypeScript project.** The
  dependency range allowed `tree-sitter` 0.26.0, which is ABI-incompatible with
  the newest published grammar wheels (`tree-sitter-javascript` 0.25.0,
  `tree-sitter-typescript` 0.23.2 — the only ones that exist). Partway through a
  real project the parser died with a SIGSEGV inside `node_get_named_children`,
  taking the whole process down with it: `codemble <path>` exited with no
  traceback, and the app's local server vanished mid-parse, so the loading
  screen reported "Lost contact with the local server" and stopped there.
  Bisected on one machine, one project, one Python: 0.26.0 crashes every run,
  0.25.2 is clean. The core is now pinned `<0.26`.
  An install that already had 0.25.x kept working, which is why this stayed
  invisible from a developer checkout — it only reached people installing
  fresh, including through the documented `uvx codemble` path.
- A dependency guard now asserts the resolved `tree-sitter` version stays below
  the segfaulting release. A behavioural test cannot catch this: a small snippet
  parses and walks fine on 0.26.0, and every fixture in the suite is small,
  which is exactly how it reached a release.

## [0.5.2] - 2026-07-20

### Fixed
- "Cancel and pick another project" now works when the local server has stopped.
  The teardown that returns you to the picker used to run only after the reset
  request came back, so when that request could not reach the server at all, the
  loading screen never released you — the one escape hatch depended on the very
  server it was escaping. A reset the server *refuses* still stays put and
  reports inline, because the project is genuinely still bound there.
- The loading screen stops over-reassuring during a long outage. A brief failed
  poll still says the parse may be running fine; after eight consecutive
  failures (~18 seconds of no answer) it says instead that the local server has
  not responded and may have stopped, and points at cancelling and running
  `codemble` again. It keeps retrying either way.
- A load failure with no server on the other end now names the local server and
  what to do about it, instead of showing the browser's bare "Failed to fetch".

## [0.5.1] - 2026-07-20

### Fixed
- Cancelling a parse (returning to the picker) now stops the `resolving` stage
  too, not only the file-reading loop. Resolving is the slowest stage on a large
  project and only reported sub-steps, so a cancel there left a worker burning
  CPU to completion — and a second selection could run two parses at once. Each
  resolving sub-step is now a cancellation checkpoint, matching the per-file one.
- Clicking a module box on the 2D Map now visibly highlights it (in the
  interaction accent, never the amber that means "understood"), so a click on
  the Easy-default layer no longer looks like it did nothing. The system-level
  copy on the Map now says plainly that a module's internal structures are drawn
  as planets in the Galaxy layer and that the Map shows how modules connect, not
  what is inside them — it no longer points at the Workflow tab, which has no
  rows for a module the program never reaches.

## [0.5.0] - 2026-07-20

### Added
- Large projects now show a staged loading screen instead of a frozen tab.
  Parsing runs on a worker thread; the app polls `GET /api/picker/progress` and
  names the stage it is in — discovering, parsing, resolving, checks, layout —
  with a real file count while files are read, and a narrated sub-step
  (resolving imports, resolving calls, building the galaxy map, composing the
  project) once the parse moves past counting files. A failed parse reports
  the parser's own message and offers an in-app retry; cancelling stops the
  parse at the next file boundary. A realistic 1,000-file Python project
  parses and renders an interactive galaxy end to end; the parse itself is
  1.56x faster after removing a parser hotspot (below), and the one-pass check
  index builds a full 1,000-region suite in under a second.
- The over-cap prompt is actionable in-app: the busiest subdirectories are
  buttons that navigate the picker, and a typed path field accepts any folder
  inside your home directory. Outside-home paths are still refused.
- A **Clear this project's progress** control on the star chart, behind a
  confirmation, scoped to the open project only.
- A non-interactive `codemble` run now prints the busiest-scope suggestions
  with the scale refusal instead of a bare message.

### Changed
- The scale cap moved from 300 to 1,000 supported source files. LOD and
  clustering remain Phase 2 work.
- `POST /api/picker/select` returns `202 {"state": "parsing"}` instead of
  blocking until the graph is ready.
- `CODEMBLE_DATA_DIR` now relocates **everything** Codemble keeps under your home
  directory — saved progress, the narration cache, and the `config` file — rather
  than progress alone. All three resolve through one helper, so pointing the
  variable somewhere else moves them together. Unset, the default is unchanged:
  `~/.codemble`.
- Language focus now also projects onto the **2D Map**, matching the galaxy: a
  focused language keeps its boxes, rows, and edges while the others are dropped,
  and the survivors keep their backend-computed coordinates. The projection
  happens in the frontend and never re-lays-out or mutates the immutable graph,
  so focus finally means the same thing on both layers.
- The no-WebGL message now points the learner to the Map/Diagram layer, which
  draws the same parser evidence as plain SVG and is one switch away, instead of
  only stating that the galaxy needs WebGL.

### Fixed
- Check generation walked every graph edge up to four times per region, and
  rebuilt the node lookup and the option pool per region — an O(regions × graph)
  freeze at bind. One index is now built per bind in a single pass, measured
  ~16x faster at 1,000 files. A committed golden fixture proves the generated
  suites and answers are byte-identical for the Python and mixed fixtures.
- `GET /api/graph` and `GET /api/map` re-hydrated progress and re-sorted every
  node and edge on every request. The serialized document is cached and
  invalidated on region light-up, Home selection, and project bind or reset —
  measured ~25-26x faster warm.
- The Python adapter resolved a node's owning module with an O(definitions ×
  modules) scan; it now walks the node id's own dotted prefixes in O(depth),
  a further 1.56x on total parse wall-clock. Output is byte-identical.
- The test suite no longer reads the developer's `~/.codemble/config` or their
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`. Every server test that built an app
  without an explicit study service inherited whatever the machine had
  configured, so the same test could construct a live provider locally and none
  in CI. The two tests that request `/explanation` would then make a real, billed
  API call and cache the reply under the developer's home directory.
- First-run onboarding assumed the learner was on the galaxy, but Easy — the
  default audience — opens on the 2D Map. The coach-marks and the footer control
  hint now key on the active layer, so a learner on the Map reads map guidance
  ("click a box or row to study, switch tabs") instead of galaxy scroll/camera
  controls that are not on screen.
- The audience-mode gate and the first-run coach-marks no longer open as two
  stacked modals on a genuine first run; the coach-marks wait until a mode has
  been chosen, so the gate resolves first.
- With no parser-recognisable entrypoint the "Change Home" control is not
  rendered, so both Map tabs now state that reason instead of pointing at a
  button that is not there. The has-candidates-but-unselected copy is unchanged.
- A project bind slow enough to outlast a parse cancellation could commit after
  the picker had already been reset, resurrecting the just-released project or
  clobbering the next selection. The commit now re-checks cancellation under the
  same lock that performs it, so a stale bind can never rebind a released project.

## [0.4.0] - 2026-07-20

The galaxy read as flat spheres on a plain background, connections were hard to
follow at any zoom level, and once a project was bound the only way to open a
different one was killing the server. This release lands the redesign, adds a
second way to look at the same graph, and puts what the parser already knew on
screen.

### Added
- A second **Map** layer beside the galaxy, switchable from the header. Its
  *Architecture* tab lays modules out as boxes grouped by directory and layered
  by import distance from Home; its *Workflow* tab walks the call tree from your
  entrypoint, where the first hop is the `defines` relation the parser recorded
  and deeper hops are `calls`. Both layouts are computed by the parser-backed
  graph layer and served by a new `GET /api/map`, so the map and the galaxy can
  never disagree.
- The Map layer is plain SVG and needs no WebGL, so a machine that cannot draw
  the galaxy can still read the project.
- The study panel now shows what the parser knows before any model is asked: a
  structural summary rendered from parser facts through fixed templates, with no
  key, no network, and no provider involved.
- Grounded narration finally reaches the panel. The explanation endpoint had
  shipped but was never called, so the narration block always rendered empty.
- A Connections section lists every parser relationship into and out of the
  selected structure, grouped inbound and outbound, each row stating direction,
  certainty, and a `file:line` citation for where that structure is defined —
  plus a small SVG diagram of callers, this structure, and callees. Clicking a
  row opens that structure's study.
- Local narration through Ollama, so a learner with no API key can still get
  grounded prose without their source leaving the machine. It is explicit
  opt-in (`CODEMBLE_PROVIDER=ollama`, or `provider = "ollama"` in
  `~/.codemble/config`) with no auto-detection, the host is refused at
  construction unless it is plain `http` on loopback, no credential is ever
  sent, and the output passes exactly the same grounding validation as a cloud
  provider. Honest caveat: that validation catches an invented identifier, not
  a wrong claim about a real one, and smaller local models make the second kind
  of mistake more often.
- Guidance when no model is configured, including the local Ollama path, driven
  by whether a loopback Ollama is actually reachable and which models it has.
- An Easy/Expert audience toggle in the header. Easy uses plain language for
  narration, check questions, panel labels, Lens notes, and the legend; Expert
  keeps full terminology. The choice persists per project and never changes
  graph truth, coordinates, progress, or how a check is scored.
- Easy mode opens on the Map, hides galaxy links unrelated to the selected
  structure, and shows a hint chip naming the nearest unlit region to Home. The
  hint is counted in import-route hops over the graph; no model chooses it.
- Switch project: a header control releases the current project and returns to
  the picker, so a second project no longer needs a terminal.
- Change Home: the entrypoint picker can be reopened whenever the parser ranked
  at least one candidate, and the Home you select is remembered for the next run
  of the same project.
- Edge arrowheads below the galaxy level, hover tooltips on every edge naming
  both structures, the relationship, its certainty and the line it was seen on,
  and hover/selection highlighting.
- First-run coach-marks explain what you see, how to move, and what lights
  stars. Dismissing them is a local UI preference, not progress.
- A clickable breadcrumb, and a legend naming dim, amber-understood, unchartable
  syntax-error files, certain versus possible relationships, and one swatch per
  language. It describes only the encodings the layer on screen actually draws:
  size and brightness are galaxy-only, language tint appears at galaxy level and
  on the Architecture tab, and the possible-relationship swatch dashes on the Map
  to match the SVG while staying colour-only for the galaxy.
- Correct check answers now get an affirmation, not just silence.
- A `<noscript>` message and a React error boundary, so a render failure
  explains itself and offers a reload instead of showing a blank page.

### Changed
- The galaxy gained depth: nodes carry a canvas-generated halo, an
  `UnrealBloomPass` is tuned so lit amber blooms hard while the unlit ramp
  barely registers, and a background starfield is seeded by hashing the
  project's own file hashes — the same code always produces the same sky.
- At galaxy level, Python, JavaScript and TypeScript systems sit in a faint
  language-tinted nebula. A system in any other language renders no fog rather
  than borrowing another language's hue.
- Keyboard focus in the galaxy now carries a visible reticle as well as its
  live text readout.
- Passing a region's checks plays a 1.2s "nebula dawn" the next time you are at
  galaxy level: amber washes across that system's halo and fog and recedes. The
  lit state is already committed before it runs, so the animation celebrates a
  fact rather than delivering it. `prefers-reduced-motion` skips it entirely and
  goes straight to the finished lit state.
- System orbits are laid out by call depth instead of by member index, so an
  inner ring means "this runs first". Ring 1 is what the module's entry node
  calls directly plus every member no sibling calls; members no certain call
  reaches keep the outermost ring rather than being placed by guesswork. Only
  certain calls decide placement. Layout coordinates changed once; saved
  progress is unaffected because region signatures derive from file hashes, not
  coordinates.
- Drifting particles mark **certain** call edges only, at system and study
  level. A possible call stays still, so motion can never imply proof.
  `prefers-reduced-motion` stops them too.
- Centrality now counts the distinct structures that call a node, not the call
  sites they contain, so a helper hammered from one loop no longer outshines a
  shared utility. The study panel's label follows: "Callers", not "Calls in".
- The study panel leads with the structural summary and narration, then
  connections, then source and lens notes.
- The study level keeps the selected structure's connections visible instead of
  dimming the whole scene.
- A region with no safe check now explains that Codemble refuses to ask a
  question the graph cannot answer, rather than only stating that none exists.
- The zero-candidate Home screen no longer tells you to restart with a CLI
  flag; every option is in the app.
- The star chart labels studied counts "this session", which is what they have
  always measured.

### Fixed
- The partial-parse notice rode a code path that never executed; it now renders
  with the narration block, and the structural summary states it as well.
- A failed graph load offered only "Restart Codemble and reload this page"; it
  now retries in place.
- Contributors only: pinned the docs site back to TypeScript 6.x. An automated
  7.0.2 bump had broken the `astro check` CI gate, because TypeScript's native
  7.x compiler does not yet expose the programmatic API that check relies on.

## [0.3.1] - 2026-07-19

### Changed
- Packaging metadata only, no behavior change: added PyPI classifiers (Beta
  status, Python 3.11-3.13, Apache-2.0 license, dev/education audience), moved
  license metadata to the PEP 639 SPDX form so the License field is concise
  instead of dumping the full Apache text, made README links absolute so the
  PyPI project page renders them, and excluded internal tooling directories
  from the sdist.

## [0.3.0] - 2026-07-19

### Added
- Bare `codemble` now opens the browser to an in-app project picker: browse
  home folders, reopen recent projects, and re-scope over-cap projects without
  touching the terminal.
- The local server rejects foreign `Host` headers, keeping the picker API
  reachable only from the learner's own machine.
- Codemble is published to PyPI, so installing is `uvx codemble` or
  `pipx install codemble` with no git URL or tag.

### Changed
- `codemble` with flags but no path serves the picker instead of the current
  directory; pass a path (or `--path`) for the previous behaviour.
- Rebuilt the packaged app on the Formal Edo palette, so the galaxy and the
  public site finally share one set of values. The app's tokens already imported
  the site's, but `codemble/web_dist` had not been rebuilt since before the
  redesign, so every shipped build still rendered the retired palette.
- Self-hosted Shippori Mincho and Zen Kaku Gothic New in the app and dropped
  Sora and Inter. The site loads these faces from the Google Fonts CDN; the app
  must not, because it runs locally and offline. Net bundle change is smaller.
- Illumination now owns the top of the brightness range: the unlit centrality
  ramp stops at `--cm-ink-2` (8.2:1) and a lit star uses `--cm-star-high`
  (12.1:1). Previously a busy un-understood module outshone an understood one
  17.4:1 to 8.5:1, which inverted the meaning of lighting a region.

### Fixed
- Canvas colours authored as `color-mix()` reached WebGL as unparsed text and
  rendered black, because a custom property returns its authored value rather
  than a resolved colour. Affected unchartable nodes and every "possible call"
  edge — exactly the uncertainty the Correctness Contract requires to stay
  visible. Palette values are now resolved to plain `rgb()` before rendering.
- The partial-parse notice said "its language parser" when reporting more than
  one file.
- Multi-answer checks offered no wrong option once a question had four or more
  correct answers, so selecting every option lit the region without proving
  anything. Checks now always offer wrong options alongside their answers, and a
  question the graph cannot supply a wrong option for is dropped rather than
  asked. On this repository the change removed all 17 such questions out of 107
  while leaving every region's check count unchanged.

### Added
- Expanding site search in the header of both the landing page and every docs
  page, backed by Pagefind with keyboard shortcut, arrow-key navigation, and an
  explicit message when the index has not been built yet.
- Generated Edo star-atlas plate artwork (`docs-site/scripts/build-plates.mjs`),
  emitted from a fixed seed so the same script always produces the same sky.
- A standalone landing page at `docs-site/src/pages/index.astro`, structured as
  four numbered plates in 起承転結 order with a layered tatebanko hero.

### Changed
- Centralized graph canonicalization, Home selection, centrality, annotation
  normalization, edge deduplication, and deterministic layout behind one graph
  finalization interface shared by every language adapter and project composition.
- Moved scale guarding and scope selection into `ProjectParser`, with one
  reusable project intake that preserves adapter file ownership through parsing
  instead of rediscovering the same scope in each adapter.
- Moved learner navigation, language focus, study/check/Home requests, progress
  refresh, and illumination sequencing behind one testable learner-session
  interface with HTTP and in-memory adapters, leaving React to render snapshots.
- Reused one internal JavaScript/TypeScript syntax-evidence index across
  entrypoint, concept, call, binding, and imported-symbol resolution passes,
  eliminating repeated ownership maps and whole-graph symbol scans.
- Rebuilt the public site on the Formal Edo palette (kachi indigo, ruri lapis,
  kohaku amber, gofun white) with Shippori Mincho and Zen Kaku Gothic New. The
  accent contracts are unchanged: kohaku still means understanding, ruri still
  means interaction.

### Fixed
- The current docs page was marked with a filled kohaku pill, which claimed
  "understood" about a navigation state; it now uses ruri, the interaction accent.
- The landing hero overflowed a 320px viewport, putting a call to action and the
  install command outside the clipped area where they could not be reached.

### Removed
- `docs-site/src/content/docs/index.mdx`, replaced by the standalone landing
  page; its content moved there.

## [0.2.0] - 2026-07-19

### Added
- Language-neutral `ProjectParser` discovery and graph composition with global
  Home selection, adapter collision checks, and Python graph-byte compatibility.
- Official tree-sitter JavaScript/TypeScript adapter for JS, JSX, MJS, CJS, TS,
  TSX, MTS, and CTS modules, definitions, imports, calls, entrypoint ranking,
  exact source spans, file hashes, and honest partial-parse recovery.
- Language-tagged graph schema 4 concept annotations plus deterministic
  JavaScript/TypeScript Lens notes for async/await, arrows, destructuring,
  optional chaining, nullish coalescing, modules, types, interfaces, generics,
  and JSX.
- Accessible language focus for mixed galaxies, systems, Study navigation, and
  the star chart. It filters a view of the graph without changing coordinates,
  progress, source truth, uncertainty, or cross-language navigation.
- Phase 1 mixed-project fixtures, pure frontend focus/chart contracts, packaged
  production SPA, public documentation, and a versioned `v0.2.0` wheel.

## [0.1.0] - 2026-07-19

### Added
- Repository scaffold: README, CLAUDE.md agent brief, docs, docs-site (Astro + Starlight), CI, community files.
- Deterministic Python AST parser with language-neutral graph models, source spans,
  imports and calls with explicit certainty, entrypoint ranking, render metadata,
  file hashes, partial-parse reporting, and schema-versioned JSON.
- `codemble parse <path> --out graph.json` CLI command.
- Parser fixture suite covering exact resolution, ambiguity, external calls,
  ignored files, syntax errors, entrypoints, centrality, and byte determinism.
- Deterministic galaxy and system coordinates with one source module per region,
  aggregated import routes, LOC sizing, centrality brightness, and Home markers.
- `codemble <path>` local FastAPI server with graph/source APIs, production SPA
  serving, scripted three-level semantic zoom, keyboard navigation, responsive
  observatory UI, WebGL failure handling, and a 1,000-node renderer probe.
- Web build gate in CI and `scripts/dev.sh` for the backend/Vite development loop.
- Study payloads with exact source lines, parser-proven neighbor evidence, and
  clickable `file:line` citations in the responsive study panel.
- Deep narration module with direct Anthropic Messages and OpenAI Responses
  adapters, environment/TOML BYO-key configuration, file-hash disk caching,
  response grounding validation, and explicit no-key/error states.
- Parser-proven Python concept annotations for decorators, comprehensions,
  generators, context managers, async/await, dunder methods, exception handling,
  and type hints, serialized in graph schema 2.
- Python Lens notes anchored to exact source lines plus a language star chart
  that separates concepts encountered, structures studied this session, and
  graph-derived understanding without inventing progress.
- Four deterministic active-check families derived and scored only from call
  edges, import edges, direct callers, and parser-ranked entrypoints.
- Region illumination persisted atomically under `~/.codemble/progress`, with
  per-region file signatures so editing one file re-dims only its own system.
- Responsive System check flow with explicit wrong-answer evidence, suite
  progress, restart-safe completion, and star-chart understanding updates.
- Honest Home calibration when top-ranked entrypoints are ambiguous, plus a
  parser-validated `--entrypoint` override.
- A 300-file Phase 0 guard with interactive subdirectory selection and an
  explicit non-interactive `--path` route.
- Unchartable syntax-error nodes, raw-source access, and model narration
  suppression for partial parses.
- Production SPA assets inside the Python wheel, versioned `pipx`/`uvx` Git
  install routes, an automated real-app demo recorder, and the v0.1.0 GIF.
