# Changelog

All notable changes to Codemble are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

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
