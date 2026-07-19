# Changelog

All notable changes to Codemble are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Changed
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
