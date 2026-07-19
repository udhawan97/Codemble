---
title: Quickstart
description: From one command to your first lit star system.
---

## 1. Point it at your project

```bash
uvx codemble            # or: pipx install codemble && codemble
```

Codemble opens your browser to an in-app picker: browse your home folders or
reopen a recent project, then pick your Python, JavaScript, TypeScript, or
mixed project. To skip the picker, pass a path directly:

```bash
codemble ./my-project
```

> Until the first PyPI release (v0.3.0) lands, install from the tag instead:
> `pipx install git+https://github.com/udhawan97/Codemble.git@v0.2.0`

Codemble parses locally, chooses a free localhost port, and opens the galaxy.
It keeps syntax-error files visible and labels unresolved calls instead of
guessing. Use `--no-open` when you want to copy the printed URL yourself.
Codemble reads supported source; it never runs your project or package scripts.

For a project above 300 supported source files, the picker prompts for a
busiest-first subdirectory right in the UI. From the CLI, select the scope
yourself:

```bash
codemble --path ./my-project/src
```

## 2. Find Home

Your entrypoint system is marked **Home** — where execution starts. If the
entrypoint is ambiguous, Codemble shows only parser-ranked candidates and you
pick. The CLI equivalent is `--entrypoint module.qualname`; an unranked value
is rejected rather than guessed.

## 3. Zoom in

The camera moves on rails through three levels. In a mixed project, use the
**Focus** control to show All, Python, JavaScript, or TypeScript systems. Focus
is only a view: it does not alter coordinates, progress, or graph evidence.

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

Ready to help? Follow the [ten-minute early-tester guide](https://github.com/udhawan97/Codemble/blob/main/TESTING.md)
and report the first confusing moment in your own words.
