---
title: Quickstart
description: From `codemble ./my-project` to your first lit star system.
---

## 1. Point it at your project

```bash
codemble parse ./my-project --out graph.json
```

The current M1 build parses Python into deterministic, schema-versioned graph
JSON. It keeps syntax-error files visible and labels unresolved calls instead of
guessing. More languages are on the [roadmap](/Codemble/roadmap/).

The browser command (`codemble ./my-project`) arrives with M2. The remaining
steps describe the complete Phase 0 learning loop now being built.

## 2. Find Home

Your entrypoint system is marked **Home** — where execution starts. If the
entrypoint is ambiguous, Codemble shows ranked candidates and you pick.

## 3. Zoom in

The camera moves on rails through three levels:

| Level | What you see | What it's for |
| --- | --- | --- |
| **Galaxy** | Modules as star systems, imports as routes | Orientation |
| **System** | Functions and classes as planets in tidy orbits, call edges | Structure |
| **Study** | Real source, grounded explanation, language lens, checks | Learning |

## 4. Light it up

Pass a region's checks and its stars light up — permanently. Watch your
[star chart](/Codemble/star-chart/) grow as you meet new language concepts.

A fully lit galaxy means you understand your project. That's the game.
