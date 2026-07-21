---
title: Quickstart
description: From one command to your first lit star system.
---

## 1. Install uv

Codemble runs through [uv](https://docs.astral.sh/uv/), which fetches the
current release on demand and leaves nothing in your system Python. Install it
once:

```bash
brew install uv
```

No Homebrew? Use the official installer — `curl -LsSf
https://astral.sh/uv/install.sh | sh` on macOS and Linux, or `powershell
-ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` on
Windows. If you would rather install Codemble permanently, `pipx install
codemble` needs no uv at all.

## 2. Point it at your project

```bash
uvx codemble
```

Codemble opens your browser to an in-app picker: browse your home folders or
reopen a recent project, then pick your Python, JavaScript, TypeScript, or
mixed project. To skip the picker, pass a path directly:

```bash
codemble ./my-project
```

Codemble parses locally, chooses a free localhost port, and opens the galaxy.
It keeps syntax-error files visible and labels unresolved calls instead of
guessing. Use `--no-open` when you want to copy the printed URL yourself.
Codemble reads supported source; it never runs your project or package scripts.

For a project above 1,000 supported source files, the picker offers the
busiest-first subdirectories as buttons and accepts a typed path, right in the
UI. From the CLI, select the scope yourself:

```bash
codemble --path ./my-project/src
```

## 3. Find Home

Your entrypoint system is marked **Home** — where execution starts. If the
entrypoint is ambiguous, Codemble shows only parser-ranked candidates and you
pick. The CLI equivalent is `--entrypoint module.qualname`; an unranked value
is rejected rather than guessed.

## 4. Choose a layer, then zoom in

The header switches between two layers. **Galaxy** is the 3D view; its camera
moves on rails through three levels. **Map** is a flat diagram with two tabs.
Easy mode starts on the Map, Expert starts on the Galaxy, and you can switch at
any time. In a mixed project, use the **Focus** control to show All, Python,
JavaScript, or TypeScript. Focus and layer are only views: neither alters
coordinates, progress, or graph evidence.

| Galaxy level | What you see | What it's for |
| --- | --- | --- |
| **Galaxy** | Source modules as star systems, imports as routes | Orientation |
| **System** | Functions and classes in call-depth orbits — the inner ring runs first | Structure |
| **Study** | Real source with line numbers and a validated, cached explanation | Learning |

| Map tab | What you see | What it's for |
| --- | --- | --- |
| **Architecture** | Modules as boxes, grouped by folder, layered by import distance from Home | Seeing how the project fits together |
| **Workflow** | The call tree from your entrypoint, depth by depth | Seeing what runs first |

On a compact screen the Map opens at readable 100%, centred on Home or the
selected parser-backed target. Use **Fit** when you want the whole diagram as an
overview, and press the percentage button to return to 100%. Codemble keeps your
zoom and pan when fresh Map data arrives or you briefly switch layers.

No API key is required to inspect source and parser relationships. With a key,
Codemble sends only the selected source context directly to your configured
provider when you open Study; it does not run narration in the background.

## 5. Light it up

Pass a region's checks and its stars light up — permanently. Watch your
[star chart](/Codemble/star-chart/) grow as you meet new language concepts.

A fully lit galaxy means you understand your project. That's the game.

Ready to help? Follow the [ten-minute early-tester guide](https://github.com/udhawan97/Codemble/blob/main/TESTING.md)
and report the first confusing moment in your own words.
