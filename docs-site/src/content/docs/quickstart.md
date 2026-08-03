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
reopen a recent project, then pick it. Python, JavaScript, TypeScript, Go, Java,
Rust, C#, and any mix of them are read the same way. To skip the picker, pass a
path directly:

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

Your entrypoint system is marked **Home** — where execution starts. On most
projects Codemble settles it without asking. A candidate that lives in a test
folder (`tests/`, `test/`, `testing/`, `__tests__/`, `spec/`), or is named like
one (`test_*`, `*_test`, `conftest`), ranks below your project's own code — so a
repository whose fixtures carry their own `main()` no longer buries the real
entrypoint among them.

That rule reads the file's **path**, so it holds for every language Codemble
reads, not just the one whose test convention you happen to use. It has to: a
Go, Java, Rust or C# fixture under `tests/` usually carries an ordinary,
unmarked `main()` that no language's own test marker (`#[test]`, `@Test`,
`[Fact]`) would ever catch. Test candidates are demoted, not removed: a project
that *is* a test suite still gets a Home, and the rank you are shown is the
real one.

When candidates genuinely tie for best rank, Codemble asks rather than guessing.
It offers only parser-ranked candidates; the CLI equivalent is `--entrypoint
module.qualname`, and an unranked value is rejected.

The picker states how many candidates there are and groups them by the
top-level folder each one really lives in. The best-ranked group opens first,
and **Explore without Home** stays on screen however long the list is: every
system, check, explanation and lens note works without a Home.

## 4. Choose a layer, then zoom in

The header switches between two layers. **Galaxy** is the 3D view; its camera
moves on rails through three levels. **Map** is a flat diagram with two tabs.
Easy mode starts on the Map, Expert starts on the Galaxy, and you can switch at
any time. In a mixed project the **Focus** control offers **All** plus one
button per language actually present, with its system count. Focus and layer are
only views: neither alters coordinates, progress, or graph evidence.

| Galaxy level | What you see | What it's for |
| --- | --- | --- |
| **Galaxy** | Source modules as star systems, imports as routes | Orientation |
| **System** | Functions and classes in call-depth orbits — the inner ring runs first | Structure |
| **Study** | Real source with line numbers, what a change here reaches, and a validated, cached explanation | Learning |

| Map tab | What you see | What it's for |
| --- | --- | --- |
| **Architecture** | Modules as boxes, grouped by folder, layered by import distance from Home | Seeing how the project fits together |
| **Workflow** | The call tree from your entrypoint, depth by depth | Seeing what runs first |

Easy mode labels the same surfaces in plainer words — the layer is **Diagram**
and the tabs are **How it fits together** and **What runs first**. The views are
identical; only the wording follows the audience.

Click a box and the Map offers both halves of a step: **Read the source** opens
that module's real source, lens notes and relationships without leaving the
layer, and **Prove understanding** starts its checks. Escape steps back a level,
as it does in the Galaxy.

On a compact screen the Map opens at readable 100%, centred on Home or the
selected parser-backed target. Use **Fit** when you want the whole diagram as an
overview, and press the percentage button to return to 100%. Codemble keeps your
zoom and pan when fresh Map data arrives or you briefly switch layers.

No API key is required to inspect source, parser relationships, or the **Impact**
lists that show what a change to a structure would reach and what it depends on.
With a key, Codemble sends only the selected source context directly to your
configured provider when you open Study; it does not run narration in the
background.

## 5. Explore, then light it up

Flying to a system charts it: its import routes stay drawn, and the star chart
counts it under **Systems explored**. That is saved with the rest of your
progress, and it is the smaller of the two claims Codemble makes about you.

The larger one is earned. Pass a region's checks and its stars light up —
permanently. Watch your [star chart](/Codemble/star-chart/) grow as you meet new
language concepts.

A fully lit galaxy means you understand your project. That's the game.

Ready to help? Follow the [ten-minute early-tester guide](https://github.com/udhawan97/Codemble/blob/main/TESTING.md)
and report the first confusing moment in your own words.
