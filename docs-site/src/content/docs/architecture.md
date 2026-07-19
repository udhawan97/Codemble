---
title: Architecture
description: The adapter seam, the render-ready graph, and why the LLM only narrates.
---

## Three load-bearing decisions

### 1. Language adapters (the seam)

Every language plugs in behind one interface: `parse()` produces the structural
graph; `concepts()` produces idiom annotations for the lens. Python ships first
using the stdlib `ast` module (precise, dependency-free); later languages use
tree-sitter adapters. Nothing above the seam hardcodes a language.

### 2. The graph is render-ready

The graph layer computes everything the renderer needs — language, size,
centrality, entrypoint rank, region, understood-state — and the 3D frontend is a
**pure consumer**. No layout or game logic lives in the renderer. This is what
keeps a future read-only share link (and any alternative renderer) cheap.

### 3. The LLM narrates; it never decides

Structure comes from parsers. Check answers come from the graph. The model's
job is prose: explaining code it is shown, teaching idioms the parser found.
Every explanation links to real `file:line` so you can verify it yourself.

## Stack

Python 3.11+ · FastAPI · Vite + React · `3d-force-graph` (three.js) ·
Anthropic / OpenAI (bring your own key) · local JSON persistence.
