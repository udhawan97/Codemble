# Codemble web UI

The galaxy renderer lives here: Vite + React + `3d-force-graph` (three.js).
It is a pure consumer of the graph JSON emitted by `codemble/graph` — no layout
or game logic in the renderer. See `CLAUDE.md` §Architecture rules.

```bash
npm install
npm run dev      # proxies /api to Codemble on port 8000
npm run build
```

For an end-to-end development loop from the repository root:

```bash
./scripts/dev.sh ./tests/fixtures/sampleproj
```

The renderer disables free-flight controls and consumes only graph-provided
coordinates. On a system with at least 900 nodes, append `?benchmark=1` to run
the built-in direct-render throughput probe; the result is written to the
document's `data-codemble-fps` attribute.
