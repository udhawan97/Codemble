# Design: Audience modes, structural summaries, and local narration

Date: 2026-07-19 · Status: approved by UD (this session) · Owner: UD

## Problem

Codemble speaks one voice to everyone. A beginner who does not know what a
decorator is and a working developer onboarding onto an unfamiliar codebase get
identical prose, identical lens notes, and identical check wording. One of them
is always being failed.

Two further gaps sharpen it:

1. **Without an LLM key the study panel is mostly empty.** The galaxy, lens, and
   checks work, but where an explanation would be there is only "add your key".
   The tool has plenty of parser-proven facts it could state and does not.
2. **With a key, the study panel waits.** `/api/node/{id}/study` returns source,
   neighbours, lens, and narration in one response, so opening a planet blocks on
   a network round trip to a model.

## Goal

Two audiences, one truth. A learner picks **Easy** ("explain it like I am ten")
or **Expert** ("onboard me onto this codebase"), and every text surface adapts
without a single graph fact changing. Narration becomes optional depth on top of
a floor that is always present, and the panel never blocks on a model.

## Decisions (all approved by UD)

1. **Three explanation tiers.** Tier 0 structural summary (deterministic, always
   present), Tier 1 local model via Ollama, Tier 2 cloud model via BYO key.
   Narration only ever *adds*; its absence never subtracts.
2. **Mode is presentation, never truth.** Graph bytes, layout, determinism,
   check answers, and edge certainty are identical in both modes.
3. **Dual-voice payloads.** Lens notes, check prompts, and Tier 0 summaries are
   generated in both voices and shipped together; the frontend picks. Toggling is
   instant and needs no refetch.
4. **Ollama is allowed**, reversing the 2026-07-18 "no Ollama" Non-Goal. Recorded
   in the Decision Log with the guardrails in this document.
5. **`gemma4:12b` is the recommended local model**; `qwen3:8b` is the low-RAM
   fallback. Local output is labelled as local.
6. **Endpoint split for latency.** Structure returns immediately; narration is a
   second request.
7. **Graphics are meaning-carrying only**: authored icons, graph-derived
   mini-diagrams, and richer typography. No decorative art.

## Non-Goals for this change

- No new languages (HTML/CSS remain workstream A, unspecced).
- No parser, graph, adapter, or determinism changes.
- No change to how check answers are decided; they stay graph-only.
- No streaming/SSE transport. The endpoint split makes it unnecessary for now.
- No authored per-concept illustrations (considered, rejected as game art).

---

## Architecture

### The three tiers

```
Tier 0  Structural summary   graph facts → fixed templates   always rendered
Tier 1  Local model (Ollama) narration, labelled "local"     optional
Tier 2  Cloud model (BYO)    narration, best quality         optional
```

Tier 0 is pinned above any narration, in both modes, whether or not a model is
configured. It cannot hallucinate because it performs no inference: it renders
facts the graph already owns through fixed sentence templates.

Tiers 1 and 2 both flow through the **existing** `NarrationProvider` protocol in
`codemble/llm/providers.py` (`name`, `model`, `complete(prompt) -> str`). Ollama
is a third implementation beside Anthropic and OpenAI. It receives the same
grounded prompt and passes through the same `_validate_explanation` grounding
check; no model is granted new trust.

### Mode plumbing

`mode` is one of `"easy"` or `"expert"`.

| Surface | Where the two voices are produced | Crosses the wire? |
| --- | --- | --- |
| Lens notes | `codemble/lens/*.py` — note tables gain an easy and an expert string | No; both shipped |
| Check prompts | `codemble/checks/service.py` — prompt built in both voices | No; both shipped |
| Tier 0 summary | New `codemble/llm/structural.py` — both templates rendered | No; both shipped |
| Tier 1/2 narration | `_grounded_prompt` varies its style block by mode | **Yes** — `?mode=` |

Only narration needs the server to know the mode, because only narration is
*generated* rather than selected.

### Cache correctness

`_cache_key` currently hashes `(PROMPT_VERSION, provider.name, provider.model,
node.id, file_hash)`. Mode changes the prompt but not the key, so easy and expert
would serve each other's text from cache. **`mode` is added to the key material**
and `PROMPT_VERSION` bumps to `study-v3` to retire pre-mode entries.

### Endpoint split

`GET /api/node/{id}/study` stops calling the provider. It returns source,
neighbours, lens (both voices), and the Tier 0 summary (both voices) — all local,
all fast.

`GET /api/node/{id}/explanation?mode=easy|expert` is new and performs the
provider call. The study panel renders instantly and fills narration in when it
arrives. A slow or absent model degrades to Tier 0 with a status line, never to a
blank panel or a spinner that owns the screen.

### Latency guardrails

- Provider timeouts: 60s cloud (the existing `_post_json` value, unchanged), 120s
  local — local generation on a 12B model is legitimately slower and the cloud cap
  would fail healthy setups.
- The narration request is abortable and is cancelled by navigation, exactly like
  the existing study request in `learnerSession.js`.
- On timeout: Tier 0 stays, status reads "narration timed out — retry", with a
  retry affordance. Never a blank panel.
- Cache means any given node is slow at most once per mode per model.
- A one-time setup hardware note recommends `qwen3:8b` under 16 GB RAM, before the
  learner downloads 7.6 GB and discovers it swaps.

### Frontend session

`web/src/learnerSession.js` gains:

- `mode` in state (default `"easy"`, hydrated from the server's persisted value)
- `SET_MODE` dispatch event → commits mode, persists it, refetches **narration
  only** (lens/checks/Tier 0 switch locally with no request)
- `explanation`/`explanationError` state separate from `studyData`, with its own
  `AbortController` following the existing controller pattern

All picker-mode/pre-graph work from the in-flight install-ux branch touches this
same file. Whichever lands second rebases; the two changes are additive (a new
state field and a new event each) and do not overlap in logic.

### Mode persistence

Mode is stored per project beside progress in `~/.codemble/`, through
`ProgressStore`. It is a learner preference, not graph truth, and is therefore
kept out of the graph payload and out of region signatures — changing mode must
never re-dim a region.

First run for a project shows one friendly question ("New to coding?" / "I build
software"). Thereafter a header toggle switches at any time.

---

## Tier 0 structural summary

Rendered from `Node` fields and parser-proven edges only: name, kind, file, line
span, language, inbound/outbound neighbour counts, certain-vs-possible split, and
detected lens concepts. Every sentence traces to a graph field.

**Easy voice** — short sentences, no jargon, counts spelled out:

> This is `parse_files`, a function. It lives in `adapters/python_ast.py`,
> starting on line 41. Two other parts of your code use it. It uses three other
> parts. Python ideas found here: a decorator, a comprehension.

**Expert voice** — dense, scannable, precise:

> `parse_files` · function · `adapters/python_ast.py:41-88` (48 lines)
> Inbound 2 (1 possible) · Outbound 3 · Concepts: decorator, comprehension

Uncertainty is stated, never smoothed: a possible call is counted and labelled
possible in both voices.

---

## Local narration (Ollama)

### Why this reverses a Non-Goal

The 2026-07-18 decision banned Ollama because "learners can't catch a weak
model's errors." That risk is real and is *not* fully solved. What changed:

- Grounding validation rejects ungrounded output regardless of which model
  produced it — fake identifiers, out-of-span line citations, and relationships
  outside the parser graph all fail closed.
- Tier 0 is now the floor, so a local model competes with honest deterministic
  text rather than with an empty panel.
- Checks never touch a model, so illumination stays truthful in every
  configuration.

**Residual risk, stated plainly:** validation catches invented *identifiers*, not
wrong *claims about real ones*. "This function sorts the list" when it filters is
grounded and wrong. Small models make this error more often. The guardrails below
mitigate; they do not eliminate.

### Guardrails

- Local narration is visibly labelled ("Local model — may be less accurate than a
  cloud model").
- Tier 0 remains pinned above it, so a structural truth is always adjacent.
- Ollama is never selected silently: if no provider is configured and a local
  server is detected, the UI *offers* it; it does not switch to it.
- Model recommendations are re-verified against Ollama's library at
  implementation time, not hardcoded from memory.

### Transport

`OllamaProvider` implements `NarrationProvider`:

- `POST http://localhost:11434/api/generate`, `{model, prompt, stream: false}`
- Response text read from `response`
- No API key; host/port overridable via `CODEMBLE_OLLAMA_HOST`
- Errors raise `ProviderError` with no body echoed, matching existing providers
- Plain HTTP to loopback only — the existing `_post_json` helper is documented as
  HTTPS-only, so local transport is a separate function rather than a widened one

`GET /api/llm/status` reports `{configured_provider, ollama_running,
installed_models, recommended}` for the setup guide, by querying
`http://localhost:11434/api/tags`.

### In-app setup guide

A dedicated panel, reachable from the "add your key" state and from the header,
with the smallest possible steps and live state:

1. **Install Ollama** — link to `https://ollama.com/download`, one line per OS.
2. **Download the model** — `ollama pull gemma4:12b`, with a copy button, plus
   the size (7.6 GB) and the RAM note.
3. **Done** — the panel detects the model and turns the step green with no
   restart, by polling `/api/llm/status`.

Cloud keys get the parallel three-step treatment (where to get a key, where to
put it, confirmation) so neither path is second-class.

---

## Graphics

Three approved categories, all truth-bearing:

1. **Meaning-carrying icons** — language marks, a glyph per lens concept, a
   per-check-type icon, a mode badge. Authored, static, in the existing Formal Edo
   palette. Ruri marks interaction, kohaku marks understanding; kohaku may never
   mark a navigation state.
2. **Graph-derived mini-diagrams** — a small inbound/outbound arrow figure in the
   study panel drawn from the same edges the galaxy uses. Deterministic, and
   possible edges are drawn in the same uncertain style the canvas uses.
3. **Richer typography** — easy mode gets larger type, shorter measure, more
   spacing, plain labels; expert mode gets denser layout and code-adjacent
   labels. This is the primary "beautification" lever and costs no new art.

Every icon must survive the anti-drift test: it carries meaning a learner needs,
or it does not ship.

---

## Testing

Parser/graph/checks/persistence logic lands with unit tests; UI is verified by
running it.

**Python**
- Tier 0 templates: both voices for function/class/module nodes, a possible-edge
  case, a zero-neighbour case, and a partial-parse node.
- Cache key includes mode: easy and expert do not collide (regression test for the
  bug this design found).
- Dual-voice lens notes exist for every concept in both languages; no concept has
  a missing voice.
- Dual-voice check prompts: both voices present; answers byte-identical across
  modes (the contract test).
- `OllamaProvider`: success, malformed payload, connection refused, timeout — all
  through an injected transport, no network in tests.
- `/api/llm/status` shapes for running/absent Ollama.
- Endpoint split: `/study` performs no provider call; `/explanation` does.
- Mode persistence round-trips and does **not** affect region signatures.

**Frontend**
- `learnerSession` mode transitions through the existing in-memory adapter:
  SET_MODE switches local text without a request, refetches narration, and
  cancels in-flight narration on navigation.

**Manual**
- Run with no key, with a cloud key, and with Ollama; verify Tier 0 in all three,
  both modes, at 320 px.

## Rollout

Six phases, one PR each, merged to main:

1. Tier 0 structural summary + endpoint split (backend)
2. Mode plumbing: dual-voice lens, checks, cache key, persistence
3. Ollama provider + `/api/llm/status`
4. Frontend: mode state, first-run ask, header toggle, UI density
5. Graphics: icons, mini-diagrams, typography
6. Docs, setup guide copy, `web_dist` rebuild, CHANGELOG, Decision Log

`codemble/web_dist` is a committed build artifact: any phase touching `web/`
must rebuild and commit it, or users see nothing.
