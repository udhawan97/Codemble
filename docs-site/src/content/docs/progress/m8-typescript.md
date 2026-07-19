---
title: "Build log: TS/JS structure"
description: M8 adds parser-grounded JavaScript and TypeScript without teaching language rules to the rest of Codemble.
---

**July 18, 2026 · Milestone M8 structural scope**

Phase 1 makes the language seam real. A project-level parser now discovers all
supported source files, selects language adapters, merges their graphs, resolves
Home across languages, and stops if adapters produce conflicting node IDs or
file hashes. Running the existing Python fixture through that interface produces
byte-identical graph JSON.

The second adapter uses the official tree-sitter runtime and JavaScript,
TypeScript, and TSX grammar wheels. It supports `.js`, `.jsx`, `.mjs`, `.cjs`,
`.ts`, `.tsx`, `.mts`, and `.cts` without invoking Node, package scripts, or user
code. Modules, functions, classes, methods, imports, exports-from, calls, source
spans, hashes, and parser-proven entrypoint candidates feed the same graph used
by Python.

Certainty stays conservative. Exact file paths plus one matching symbol may
produce a certain call. TypeScript `.js` substitution, extensionless imports,
ambiguous names, namespace uncertainty, and dynamic calls stay possible. An
error-recovered file remains visible as partial; only valid sibling structures
outside the error are retained.

The fixture gate covers every registered extension, exact and possible edges,
external imports, class and arrow-function nodes, valid siblings in a broken
file, mixed Python/JS/TS Home ambiguity, and repeated byte determinism. The next
wave adds parser-anchored JS/TS idiom annotations and learner-facing Lens notes.
