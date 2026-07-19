---
title: Quickstart
description: From `codemble ./my-project` to your first lit star system.
---

## 1. Point it at your project

From a source checkout, build the local web app once and point Codemble at a
Python project:

```bash
cd web && npm install && npm run build && cd ..
codemble ./my-project
```

Codemble parses locally, chooses a free localhost port, and opens the galaxy.
It keeps syntax-error files visible and labels unresolved calls instead of
guessing. Use `--no-open` when you want to copy the printed URL yourself.
More languages are on the [roadmap](/Codemble/roadmap/).

## 2. Find Home

Your entrypoint system is marked **Home** — where execution starts. If the
entrypoint is ambiguous, Codemble shows ranked candidates and you pick.

## 3. Zoom in

The camera moves on rails through three levels:

| Level | What you see | What it's for |
| --- | --- | --- |
| **Galaxy** | Source modules as star systems, imports as routes | Orientation |
| **System** | Functions and classes as planets in tidy orbits, call edges | Structure |
| **Study** | Real source with line numbers and a validated, cached explanation | Learning |

No API key is required to inspect source and parser relationships. With a key,
Codemble sends only the selected source context directly to your configured
provider when you open Study; it does not run narration in the background.

## 4. Light it up

Pass a region's checks and its stars light up — permanently. Watch your
[star chart](/Codemble/star-chart/) grow as you meet new language concepts.

A fully lit galaxy means you understand your project. That's the game.
