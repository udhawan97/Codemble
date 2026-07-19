# Codemble web UI (arrives in M2)

The galaxy renderer lives here: Vite + React + `3d-force-graph` (three.js).
It is a pure consumer of the graph JSON emitted by `codemble/graph` — no layout
or game logic in the renderer. See `CLAUDE.md` §Architecture rules.
