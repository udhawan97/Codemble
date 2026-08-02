# Explorable galaxy redesign — design spec

Date: 2026-08-02 · Approved by: UD (question-by-question, grilling session)
Status: approved design, implementation authorized in four phases

## 1. Problem

UD's complaints, restated verbatim in substance:

1. The galaxy is **too dark** and **hard to just explore** even when not learning.
2. Codemble should be a **game**: exploring the code like an astronaut is the
   main goal; learning and testing yourself is **completely optional**.
3. Explanations are **too complex for a casual user** playing a game to learn
   the code AI built for them.
4. For experts, **most of the stuff in the study view doesn't load**.
5. Wants the **top 5 languages used today**, and Python raised to "god level".
6. Wants Easy to teach in a **less technical, layman** way, and Expert to be
   **quick widget-style** — "this controls this, this can be impacted by this" —
   for a developer onboarding onto a codebase.

Two findings from grounding the complaints in the code reframe the work.

**The darkness is the game encoding, not a styling bug.** The unlit centrality
ramp is deliberately capped below `--cm-ink-2` so a lit amber star always owns
the top of the brightness range (`web/src/tokens.css:24`), and progressive
reveal draws every uncharted region faint, unnamed and edgeless. On this
repository that is roughly 100 of 123 systems rendered as anonymous grey
specks. The app is faithfully rendering "you have not learned this yet". The
complaint therefore lands on the product's central metaphor, not on its CSS.

**"Doesn't load" is four real defects, not a vibe.** Traced in full:

- Every FastAPI route is `def`, not `async def`, so each runs in anyio's
  40-slot worker threadpool, and `urlopen` blocks its thread for the full
  60 s (cloud) or 120 s (Ollama) timeout — uncancellable, so a browser abort
  frees nothing. There is no client-side timeout anywhere in
  `learnerSession.js`. Navigate faster than the provider answers and *every*
  endpoint queues behind dead narration calls: graph, map, study, checks.
  Experts navigate fastest, so experts see it first. This is the "most of the
  stuff doesn't load" report.
- The narration cache key hashes `mode` (`codemble/llm/study.py:361`), so every
  node read in Easy is a guaranteed cache miss in Expert.
- `_validate_explanation` discards the **entire** payload on any single
  violation, with no retry and no partial salvage — while the expert style
  block instructs "Lead with this structure's role in the wider project" and
  the contract permits naming only supplied neighbours, a pairing that raises
  the refusal rate specifically in Expert. A network timeout is collapsed into
  the same message, so a flaky connection is displayed as a correctness
  lecture.
- The Expert structural summary is a single `·`-joined metadata line against
  Easy's five to seven sentences; under the heading "Structural summary" it
  reads as a stub that failed to load.
- Module nodes span the whole file (`python_ast.py:522`), so a module planet
  numbers the entire file into the prompt: slow, expensive, and on a large file
  a provider HTTP 400 for context overflow.

## 2. Decisions made in the interview (all UD-approved)

| # | Question | Decision |
| --- | --- | --- |
| 1 | What is the game now? | **Presentation flip, meaning kept.** Exploration is the front door and needs zero setup; amber illumination remains the only earned state and the brightest thing in the sky. Learning is the optional meta-game, and is itself revamped to teach in layman's terms |
| 2 | What does reveal still gate? | Every system always visible, coloured, named and visitable; reveal thins **only the route mesh**. Plus a persisted **explorer's trail**: visiting a system charts it permanently |
| 3 | How far does the visual overhaul reach? | **Fork the app palette from the docs site**, and push every richness lever on top of it |
| 4 | What does flying feel like? | **Cinematic rails *and* constrained free flight** inside a clamped sphere with an always-available rescue |
| 5 | Shape of an explanation | **Three layers, progressively disclosed**, each independently validated |
| 6 | Expert impact widget | **Impact cards lead the Expert panel**, and hover-peek ships in scope |
| 7 | Analogies in Easy prose | **Allowed**, guardrailed |
| 8 | Languages | Java, Go, Rust, C# as new adapters; TypeScript deepened; **Python raised to god level** |
| 9 | Ship order | Rescue → Sky → Teacher → Languages |

## 3. What stays locked

These are unchanged and outrank every item below.

- **The Correctness Contract in full.** Structure is never invented;
  explanations are grounded in real identifiers; lens claims attach only to
  parser-detected constructs; every explanation cites a real `file:line`; check
  answers come from the graph, never the model; approximate call edges are
  labelled "possible call".
- **Amber (`kohaku`) means understanding and nothing else.** Nothing unlit may
  outshine a lit star, in any palette, at any zoom, in any mode.
- **One hue means one import community**, at most eight named families ranked
  by size (schema 9). A ninth community borrows no hue.
- **Dashed means uncertain**, on both layers.
- **Determinism.** Same code → same sky. No wall clock, no `Math.random` at
  render time. Seeds are content hashes and node ids only.
- **The graph is render-ready.** Layout, impact, reveal and colour decisions are
  computed backend-side or in a pure frontend module; React draws and decides
  nothing.
- **The `LanguageAdapter` seam.** Four public methods. New languages arrive via
  tree-sitter behind it; nothing above the seam hardcodes a language.
- **Local-first.** No CDN, no cloud, no accounts. Every new deterministic
  surface must work with no API key at all.

## 4. Phase 1 — Rescue (reliability)

The app must stop feeling broken before it is made beautiful. No new features.

1. **Narration can never stall the app.** Provider calls move off the request
   threadpool, or the routes become `async def` with the blocking work
   dispatched and capped. A hard server-side cap plus a client-side
   `AbortSignal.timeout` bound the wait. One slow provider may only ever delay
   its own narration box.
2. **Salvage formatting faults; never salvage fabrication.** *Narrowed during
   implementation, and the narrowing is the point.* An absent walkthrough stops
   being fatal, and an over-long or empty individual item is dropped rather than
   destroying the whole payload — those are formatting failures. An invented
   node id or a citation outside the studied span stays **fatal**, because that
   is invented structure and the Correctness Contract outranks the reliability
   goal. `test_provider_output_cannot_reference_an_unobserved_node` already pins
   that stance and keeps passing unchanged.

   The larger Expert-specific win is upstream: the expert style block instructs
   "Lead with this structure's role in the wider project" while the contract
   permits naming only supplied neighbours. That contradiction manufactures the
   fabrications that trigger refusals, so it is fixed at the prompt.
3. **Honest error copy.** "The explanation was withheld" is reserved for an
   actual grounding refusal. Network failure, timeout, provider HTTP error and
   context overflow each get their own message and an in-place retry.
4. **Module narration reads an excerpt, not the whole file.** Bounded, cited,
   and stated as an excerpt so the learner is not misled about coverage.
5. **A real Expert structural summary.** Prose at the same standard as Easy's,
   in Expert register — not a metadata line.
6. **Independent parser sections.** A failed `/study` may not blank the
   structural summary, connections, source and lens together; parser data that
   is already local renders regardless.
7. **The register-keyed cache is kept, deliberately.** *Reversed during
   implementation.* Easy and Expert prose genuinely differ, so a shared key
   would serve beginner prose to an expert — and
   `test_easy_and_expert_do_not_share_a_cache_entry` pins exactly that. The
   cold-miss cost is real but is the wrong thing to fix here; Phase 3's instant
   deterministic layer removes the *symptom* (an empty-looking panel) without
   serving anybody the wrong register.
8. Fix the latent `explanationLoading` reset asymmetry in `advance()`.

*Acceptance:* clicking rapidly through forty structures with a slow or absent
provider never delays the graph, map, study or checks endpoints; every failure
mode renders a distinct, accurate message with a working retry; no section
spins without a bound.

## 5. Phase 2 — The Sky (exploration)

### 5.1 Palette fork

`web/src/tokens.css` stops importing `docs-site/src/styles/tokens.css` and owns
its own values. The docs site is untouched and keeps Formal Edo exactly as
shipped. This also retires a standing Gotcha: a docs-site token edit can no
longer restyle the app with no signal.

What the fork frees: ground darkness, ambient light level, ink values, accent
vividness, and the number of distinct canvas inks. What the fork does **not**
free is listed in §3 and is re-verified against the new values: amber's
monopoly on the top of the brightness range, the 4.5:1 floor on every value
used as UI, one-hue-one-community, and dashed uncertainty.

### 5.2 Full visibility

Every region is drawn in full colour and is nameable and visitable from the
first frame. Reveal continues to gate **only** the import-route mesh, so a
169-system project does not return to a hairball. An uncharted system is a
place you have not been, not a place you cannot see.

Systems outside the eight ranked community families keep the neutral ramp for
*hue* — that mapping stays one-to-one and truthful — but gain richness through
star colour temperature, size and twinkle, which encode nothing.

### 5.3 The explorer's trail

Visiting a system **charts** it, permanently and persistently. A charted
system draws its routes. The star chart gains a second, humbler tick:
**explored** (visited) beside **understood** (amber, checks only). The two
claims stay visually and semantically distinct — been-there is not know-it.

This amends the locked "no other meta-progression" rule. It is not XP: nothing
accumulates into a score, there are no levels, streaks or leaderboards, and the
trail is a map record of where the astronaut has flown.

### 5.4 Movement

Cinematic rails **and** constrained free flight:

- Scripted warp fly-to on any selection, from anywhere, with acceleration
  easing, star streak and an arrival flourish.
- Direct system-to-system jumps, so reaching a neighbour never requires
  climbing back to galaxy level.
- Idle drift, so the sky is never frozen.
- A cruise control that chains unvisited systems for pure sightseeing.
- Bounded translation inside a sphere clamped to the layout's own extents, with
  an always-available "return to space" rescue and auto-reorientation.

"You cannot get lost" survives as an invariant, now enforced by clamps and a
rescue control rather than by the absence of the input.

### 5.5 Richness

Layered nebulae, a galactic-plane glow band lifting the ambient so the ground
reads as lit space rather than void, parallax starfield depth, per-star colour
temperature and twinkle, and re-tuned bloom. Procedural surfaces stay at System
tier only — that is a level-of-detail limit, not a taste one, since up to ~1,000
systems draw at galaxy range.

*Acceptance:* same code → identical sky; interactive framerate at 1k nodes via
`?benchmark`; amber measurably remains the brightest object; every uncharted
system is visible, named within the declutter budget and reachable; no camera
input can leave the subject off screen without the rescue restoring it.

## 6. Phase 3 — The Teacher (learning revamp)

### 6.1 Three layers, progressively disclosed

| Layer | Source | When |
| --- | --- | --- |
| 1. Instant one-liner | **Parser only. No key. Cannot fail.** | Immediately |
| 2. Story | LLM, ~3 sentences, everyday words in Easy | After, in its own box, own timeout |
| 3. Walkthrough | LLM, line-by-line | **On demand only** |

Layer 1 also replaces the Expert stub. Layer 3 being on demand removes the
wall of text that greets every click today and most context-overflow failures.
Each layer validates independently, so a bad walkthrough line can no longer
destroy a good summary.

### 6.2 Analogies in Easy

Easy prose may use analogy. Guardrails, enforced in validation: an analogy
sentence may not introduce identifier-like tokens; analogies never appear in
the relationships section, which stays literal parser fact; Expert prose stays
analogy-free.

### 6.3 The impact widget

Parser truth, therefore **works with no API key** — which is what finally
removes Expert's dependence on the LLM for its lead content.

- *Change this → these places feel it*: direct callers/importers, expandable to
  a depth-capped transitive blast radius.
- *This depends on → breaks if these change*: callees and imports.
- Every row clickable, certainty-labelled, `file:line` cited. Any chain routed
  through a possible edge is labelled possible for its whole length.
- Leads the panel in Expert; present in Easy in plain words ("3 files use this
  one"), below the story.
- Blast radius is computed in the graph layer, per the render-ready rule.

### 6.4 Hover-peek

Hovering a body surfaces a mini impact card — uses / used-by counts,
certainty-labelled — without opening the panel.

*Acceptance:* with no API key configured, both registers still receive a useful
one-liner and a complete impact widget on every node; Easy prose is readable by
someone new to programming; no single provider failure removes more than its
own layer.

## 7. Phase 4 — The Languages

Order: **Python god-level → TypeScript deepening → Go → Java → Rust → C#**,
one adapter per release so each ships verified. Existing-language deepening
comes first because it upgrades every graph the other phases already render,
and because the impact widget is only as good as the call edges beneath it.

**"God level" means maximum provable truth, never more guessing.** Concretely:
resolving attribute and method calls through class hierarchies and type hints
so fewer edges are merely "possible"; framework-aware entrypoint ranking
(FastAPI/Flask/Django routes, click/typer CLIs, pytest); a richer idiom lens
(dataclasses, protocols, pattern matching, generics); airtight relative and
namespace import resolution. Every certainty upgrade directly sharpens the
impact widget.

Each language ships adapter + idiom lens + entrypoint ranking + hand-checked
fixture tests. The schema-8 unsupported-sources table silences each extension
automatically as its adapter lands, with no second list to maintain.

*Acceptance:* per language, fixture assertions hand-check exact structures,
edges and spans; syntax errors stay visible and partial; repeated mixed parses
are byte-identical; nothing above the `LanguageAdapter` seam learns a new
language name.

## 8. Roadmap consequence

This spec promotes language work from NEXT into NOW and adds an exploration
workstream that did not exist. NOW becomes Rescue → Sky → Teacher; the language
slate becomes the new NEXT, ahead of LOD clustering. Phase 3 (share link,
extra quest types) is unchanged in LATER. Phase-1 tester evidence (issue #13)
is unaffected and still requires human runs.

## 9. Decision Log entries to append

1. Exploration is the front door; illumination remains the only earned state.
   The anti-drift test becomes "does this help a learner understand **or
   explore** their code?"
2. Reveal gates the route mesh only; every region is always visible, coloured
   and reachable.
3. The explorer's trail (visited ⇒ charted, persisted) amends "no other
   meta-progression"; it is a map record, not a score.
4. The app forks its palette from the docs site; the shared-token Gotcha is
   retired and every locked meaning rule is re-verified against new values.
5. Constrained free flight amends the free-flight Non-Goal a second time;
   "cannot get lost" is enforced by clamps and rescue.
6. Explanations become three independently validated layers; the walkthrough is
   on demand.
7. Easy narration may use analogy, under a no-identifier-tokens validation rule.
8. The impact widget is graph-layer truth and must work with no API key.
9. Language slate promoted to NEXT: Python god-level, TS deepening, Go, Java,
   Rust, C#.
