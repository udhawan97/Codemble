---
title: "Build log: the living cosmos"
description: Bloom, nebulae, a seeded starfield, call-depth orbits, and a second 2D map layer.
---

**July 20, 2026 · Milestone M12 scope**

System orbits now encode flow instead of member order: a structure's ring is
its call depth from the region's entry node, found by walking only *certain*
calls so an unproven "possible call" can never decide where something sits.
Members no sibling calls reach join ring one alongside the entry's direct
callees, and anything still unreached takes the outermost ring, ordered by
node id, rather than being guessed into place. Layout stays deterministic and
hash-seeded — no clock, no random source — and although coordinates moved
once, saved progress did not: region signatures are hashed from file content,
never from position.

A second **Map** layer now sits beside the galaxy, switchable from the header.
Both of its tabs — Architecture, and Workflow — read a new `GET /api/map`
built entirely in `codemble/graph/`, the same graph layer the 3D galaxy reads
through `GET /api/graph`, so the two views cannot disagree. Architecture groups
modules by directory and layers them by import distance from Home, cutting
cycles rather than looping forever; modules with no import route from Home get
their own row instead of a guess. Workflow walks the call tree from your
entrypoint — its first hop is labelled `defines`, not `calls`, because a module
containing a function is parser-observed containment, not a call the parser
ever saw. The Map is plain SVG: it draws possible relationships as genuinely
dashed lines and needs no WebGL, so it still works where the galaxy cannot draw.

The galaxy itself gained real depth. Every node now carries a canvas-generated
halo (no image assets ship — the textures are drawn at runtime), lit stars
bloom through the renderer's own compositor, and each system sits inside a
faint nebula tinted by language. A background starfield is seeded from the
project's own file hashes, so the same project always renders the same sky.
Drifting particles now mark certain call edges only; a possible call stays
visible but motionless, so motion can never imply proof the parser doesn't have.
Passing a region's checks triggers a roughly 1.2-second "nebula dawn" — amber
washing across that system's fog as its star flares — and a learner who has
asked for reduced motion gets the finished, lit state instantly instead of a
faster version of the same animation.

Easy mode now lands on the Map by default and Expert lands on the galaxy, but
an explicit layer switch always wins over what the mode picked, in either
direction. Easy mode also hides everything but a selection's own connections
instead of just fading them, and shows a hint chip naming the nearest unlit
region to Home, counted in graph route hops with ties broken by region id —
deterministic graph truth, never a model's guess, and the hint only ever names
a place to look, not a claim about what the code does. First-run coach-marks
explain what you see, how to move, and what lights a star; dismissing them is
a local UI preference, never mixed into saved progress. The breadcrumb is now
a real, clickable control instead of static text, and the legend gained a
swatch per language plus a possible-relationship entry that matches whichever
layer is on screen — a dash on the Map, a colour on the galaxy, because
`3d-force-graph` has no line-dash support to draw a 3D dash with.
