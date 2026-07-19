---
title: "Build log: the Python parser"
description: M1 turns real Python source into deterministic, evidence-labeled graph data.
---

**Week of July 19, 2026 · Milestone M1 complete**

Codemble can now parse a local Python project into the structural evidence the
galaxy will consume. Modules, classes, functions, imports, calls, entrypoint
candidates, source spans, regions, and call centrality all come from Python's
standard-library AST—never from a model.

The deliberately awkward test project includes relative and external imports,
aliases, methods, ambiguous names, ignored files, and a syntax-error file. The
parser keeps ambiguity and failures visible instead of guessing or crashing.

The real-project acceptance run used FastAPI's 48-file package:

- 533 nodes and 3,136 observed edges
- zero partial parses
- 0.28 seconds end to end on the development machine
- byte-identical JSON across two independent runs
- 20 certain call edges checked directly against their source lines

There is no galaxy screenshot this week because M1 builds the evidence layer,
not decorative UI. M2 is next: the deterministic, on-rails renderer that turns
this same graph into the first real sky.
