# Changelog

All notable changes to Codemble are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- The study panel now shows what the parser knows before any model is asked: a
  plain-language or expert structural summary that needs no key, no network,
  and no provider.
- Grounded narration finally reaches the panel. The explanation endpoint had
  shipped but was never called, so the narration block always rendered empty.
- A Connections section lists every parser relationship into and out of the
  selected structure — direction, certainty, and a `file:line` citation per
  row — with a small diagram of callers, this structure, and callees. Clicking
  a row opens that structure's study.
- An Easy/Expert toggle in the header. Easy uses plain language for narration,
  check questions, panel labels, and the legend; Expert keeps full terminology.
  The choice persists and never touches graph truth, coordinates, progress, or
  how a check is scored.
- Switch project: a header control releases the current project and returns to
  the picker, so a second project no longer needs a terminal.
- Change Home: the entrypoint picker can be reopened at any time, and the Home
  you select is remembered for the next run of the same project.
- Guidance when no model is configured, including how to narrate entirely
  locally with Ollama, driven by what is actually installed and running.
- Correct check answers now get an affirmation, not just silence.
- A complete legend: size, brightness, amber-understood, unchartable files, and
  certain versus possible relationships.
- Edge arrowheads below the galaxy level, hover tooltips on every edge, and
  hover/selection highlighting that brightens the selected structure's
  connections and fades the rest.
- A `<noscript>` message and a React error boundary, so a render failure
  explains itself and offers a reload instead of showing a blank page.
- A second **Map** layer sits beside the galaxy, switchable from the header. Its
  Architecture tab lays modules out by directory and by import distance from
  Home; its Workflow tab walks the call tree from your entrypoint. Both layouts
  are computed by the parser-backed graph layer and served by a new
  `GET /api/map`, so the map and the galaxy can never disagree.
- The Map layer renders without WebGL, so a machine that cannot draw the galaxy
  can still read the project.
- First-run coach-marks explain what you see, how to move, and what lights
  stars. Dismissing them is a local UI preference, not progress.
- Easy mode now lands on the Map, hides everything but the selected structure's
  connections, and shows a hint chip naming the nearest unlit region to Home.
  The hint is counted in import routes from the graph; no model chooses it.
- The breadcrumb is clickable. The legend adds a swatch per language and now
  matches whichever layer is on screen: possible relationships dash on the Map
  and stay colour-only in the galaxy.

### Changed
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
- The galaxy gained depth: every node carries a canvas-generated halo, lit stars
  bloom, each system sits in a faint language-tinted nebula, and a background
  starfield is seeded from the project's own file hashes — the same code always
  produces the same sky.
- Passing a region's checks now triggers a ~1.2s "nebula dawn": amber washes
  across that system's fog and its star flares. `prefers-reduced-motion` gets
  the finished lit state with no animation at all.
- System orbits are laid out by call depth from the module's entry node instead
  of by member index, so an inner ring means "this runs first". Structures no
  call reaches keep the outermost ring rather than being placed by guesswork.
  Layout coordinates changed once; saved progress is unaffected because region
  signatures are derived from file hashes, not coordinates.
- Drifting particles mark **certain** call edges only in the galaxy. A possible
  call stays still, so motion can never imply proof.

### Fixed
- The partial-parse notice rode a code path that never executed; it now renders
  with the narration block, and the structural summary states it as well.
- A failed graph load offered only "Restart Codemble and reload this page"; it
  now retries in place.

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
