# Product screenshot recapture after the v0.8.0 shell change

**Date:** 2026-07-28 · **Status:** approved by UD

## Why

`13b3c06` reshaped the app shell: **Change Home** and **Switch project** moved
behind a **More** disclosure at desktop, the four permanent actions stopped
wrapping to two rows, and the Audience legend moved beside its radios. Every
committed screenshot in `docs-site/public/shots/` predates it. `easy-mode.png`
and `system.png` give roughly half their 1440x716 frame to chrome — precisely
the bug the release fixed — so the published docs currently advertise it.

Measuring the shots first turned up three things the symptom did not name.

**Only five of the eight are displayed anywhere.** `easy-mode.png`,
`galaxy-lit.png` and `map-workflow.png` appear in no README, docs page or
landing component. `NOTES.md` frames the directory as a library of real product
captures to be preferred over invented media, so they are stock rather than
cruft, and stay.

**The header is the newest layer of drift, not the only one.** `easy-mode.png`
and `galaxy-lit.png` both render Expert vocabulary ("2 unchartable · syntax
error") under a selected Easy radio, `easy-mode.png` has grey stars from before
the v0.7.0 community colours, and `galaxy-lit.png` recommends
`tests.test_python_ast` as the next study target — guidance from before the
test-path penalty. `map-architecture.png` carries a different, older header than
`galaxy.png` and `system.png`. The set was captured across several builds and
has never been internally consistent.

**Recapturing would publish a false coverage claim.** See below.

## The numbers

The repository moved from 1081 nodes / 6724 edges / 109 regions to **1120 /
6991 / 111**. Far less prose depends on that than expected:

| Quoted value | Old | Now | Action |
| --- | --- | --- | --- |
| star systems | 109 | **111** | edit (2 sites) |
| charted | 23 | measured at capture | edit (2 sites) |
| nodes · edges | 1081 · 6724 | 1120 · 6991 | visible in-frame only, quoted in no caption |
| "two files could not be read — all under tests/" | 2 | 2 | unchanged — both are still `tests/fixtures/...` |
| `create_app` callers | 53 | 53 | unchanged |
| `codemble.server.app` structures | 31 | 31 | unchanged |
| `create_app` span / location | `app.py:85`, 257 lines | identical | unchanged |

## Decision 1 — fix the false coverage claim before capturing

The repository now reports one unsupported JavaScript file, and it is
`codemble/web_dist/assets/index-*.js`: the committed build artifact that
`typescript_tree_sitter.py` deliberately excludes as generated. Easy mode
renders **"1 JavaScript file not included"**. That is the channel graph schema 8
added specifically to be truthful about coverage, telling a learner something
untrue — and it would be baked into every recaptured galaxy and map frame plus
their alt text.

Root cause is a fall-through at the shared guard, not a `web_dist` special case.
`_ignore_project_directory` prunes a directory only when **every** adapter
ignores it; Python's `ignored_directories` is empty, so `web_dist` is walked.
Per file, `.js` matches the TS rule's extensions, the path then hits that rule's
`ignored_directories`, `claimed` stays `False`, and the file falls into
`_note_unsupported`.

The fix separates *no adapter recognises this extension* from *an adapter
recognises it and deliberately skips this location*, by tracking recognition
alongside the existing claim:

```python
recognized = True   # set when the extension matches a rule, before the skip
...
if not recognized:
    _note_unsupported(candidate, unsupported)
```

This restores behaviour the v0.8.0 changelog already advertises — *"Registering
an adapter automatically silences its own extension"* — which today holds
everywhere except inside that adapter's own ignore list. It lands as its own
commit with a regression test beside
`test_an_owned_extension_is_never_reported_as_unsupported`. On this repository
`unsupported_sources` returns to `()`.

## Decision 2 — `loading.png` is deliberately left unchanged

It is a pre-app, full-window state carrying no header, so the shell change
cannot have altered a pixel of it. It is 1280x900 from a different rig, and its
"13 of 900 files" describes a synthetic `codemble-c10/big` project rather than
this repository, so it takes no part in the renumbering and its README alt text
needs no edit. Recapturing would mean fabricating a ~900-file tree and winning a
timing race for no visible gain.

## Decision 3 — `easy-mode.png` moves to the Map

Captured faithfully it would be a near-duplicate of `galaxy.png`: both are
Galaxy / Easy / nothing lit, and today the only real difference is its stale
grey stars. Easy mode *defaults to the Map*, so capturing it there makes the
filename true and gives the library a genuine Easy-register frame — the Diagram
tab label, "could not be read", the guidance chip — instead of a second galaxy.

## Capture

Serve from the worktree root with `cd` and `PYTHONPATH` in one command; the
Bash tool's working directory persists between calls, and a stale `$PWD` sends
the editable install to a different worktree:

```bash
cd <worktree> && PYTHONPATH=$PWD python3 -c "from codemble.cli import main; main()" \
  serve . --no-open --port 8150
```

Whole repository, no `--path` scope. Viewport 1440x720, viewport-clipped so the
output is exactly 1440x720. Home is `codemble.cli` on every frame, matching the
originals. `AtlasJourney.astro` hardcodes `height="716"` in two places and is
updated to 720 so intrinsic size stays honest and the plate does not shift.

| Shot | Layer | Audience | Level | Extra |
| --- | --- | --- | --- | --- |
| `galaxy.png` | Galaxy | Easy | galaxy | nothing lit |
| `easy-mode.png` | Map | Easy | galaxy | Architecture tab |
| `galaxy-lit.png` | Galaxy | Easy | galaxy | one region lit by passing its checks |
| `system.png` | Galaxy | Easy | system | `codemble.server.app` |
| `study-panel.png` | Galaxy | Expert | study | `create_app` |
| `map-architecture.png` | Map | Expert | galaxy | Architecture tab |
| `map-workflow.png` | Map | Expert | galaxy | Workflow tab |

`galaxy-lit.png` requires actually passing a region's checks: progress is keyed
by project path and this worktree has none, so nothing is lit by default.

## Text to update

`README.md` (galaxy hero), `docs-site/src/content/docs/the-galaxy.md` (galaxy
and system), `AtlasJourney.astro` (four alts plus the two height attributes),
`CLAUDE.md` (close the "Left open" paragraph), `CHANGELOG.md` (`[Unreleased]`,
for the discovery fix — it is user-visible). `study-panel.md` and the
`loading.png` alt need no edit.

## Verification

`pytest` · `ruff check .` · frontend contract checks · `web_dist` rebuild
determinism · `npm run check` and `npm run build` in `docs-site` · the landing
atlas plate read through all four frames at desktop and compact · README render.

## Out of scope

Recapturing `loading.png`; any change to parser, graph, checks, progress or HTTP
behaviour beyond the discovery fix; any redesign of the shots' content beyond
the `easy-mode.png` layer decision above.
