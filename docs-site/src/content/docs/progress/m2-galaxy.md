---
title: "Build log: the first galaxy"
description: M2 turns parser-proven Python structure into a deterministic, on-rails local galaxy.
---

**Week of July 19, 2026 · Milestone M2 complete**

`codemble ./project` now parses a local Python project, starts a FastAPI server
on localhost, and opens the production React galaxy. The browser receives a
render-ready graph: it does not invent positions, grouping, routes, or progress.

The first playable map has three deliberate states:

- **Galaxy:** one source module per star system, imports as routes, and the
  ranked entrypoint marked Home.
- **System:** functions and classes in deterministic orbits with parser-derived
  call edges.
- **Study preview:** a selected structure and its real metadata, with the scene
  dimmed behind it. Source and explanations belong to M3.

There is no free-flight camera. Scroll, click, or keyboard input advances the
scripted camera; Escape or Backspace moves out. The UI also has an honest WebGL
failure state instead of silently switching to a second renderer.

Acceptance evidence:

- byte-identical graph JSON and coordinates across independent parses
- 11 module-scoped systems from the adversarial fixture project
- keyboard and pointer transitions checked in the production build
- no horizontal overflow at 320, 375, 414, or 768 CSS pixels
- 1,001-node dense-system probe at 595 FPS direct-render throughput on the
  development Mac after the scripted camera settled
- Python tests, Ruff, Vite production build, Astro check, and docs build green

M3 is next: real source with line numbers, provider-neutral grounded
explanations, local cache, and a useful no-key state.
