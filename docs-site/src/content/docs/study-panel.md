---
title: The study panel
description: What the parser knows, what a model adds, and what happens when you have no key.
---

## Five sections, in order of certainty

![The study panel for create_app: kind, span, thirty-six callers, a structural summary marked "No model needed", guidance for setting a provider key or pointing Codemble at the local Ollama already running, and a parser connections diagram above an inbound call citing a real file and line.](/Codemble/shots/study-panel.png)

Open a planet and the panel builds itself from the most certain evidence
outward:

1. **What this is** — a summary written from parser facts alone: kind, file and
   line, size, how many things use it, how many it uses, and how many of those
   links are possible rather than certain. No key, no network, no model.
2. **The explanation** — grounded narration from your configured provider, with
   a `file:line` citation on every claim. Codemble refuses to display provider
   output that names anything outside the parsed graph.
3. **Connections** — every relationship the parser observed into and out of this
   structure, grouped inbound and outbound. Each row states direction, whether
   the relationship is certain or only possible, and the `file:line` where the
   *other* structure is defined, so you can go read it. Click any row to study
   that structure. A small diagram above the list shows callers, this structure,
   and callees at a glance.
4. **Real source** — the exact lines, numbered, straight from your file.
5. **The language lens** — idiom notes anchored to constructs the parser
   actually detected.

Sections 1, 3, 4 and 5 never involve a model. If narration fails or is not
configured, they are all still there.

## Easy and Expert

The header's **Mode** toggle changes how Codemble talks to you, and how much it
puts on screen at once:

| | Easy | Expert |
| --- | --- | --- |
| Narration | Short sentences, every term explained in place | Concise, assumes fluency |
| Check questions | "Which piece of code…" | "Which structure…" |
| Labels | "Used by", "Possible connection" | "Callers", "Possible relationship" |
| Lens notes | The idiom in plain words | The precise language mechanic |
| Density | Opens on the Map, hides unrelated galaxy edges, larger type | Opens on the Galaxy, shows everything |

Easy mode also shows a hint chip naming the nearest unlit region to Home,
counted in import-route hops over the graph — no model picks it for you. Its
action follows the current level: open the suggested system, switch from Map to
Galaxy to see that system's structures, then choose one. Once the correct next
step is already on screen, the chip becomes an instruction instead of leaving a
button that cannot move you forward.

Mode never changes the graph, the coordinates, your progress, or how a check is
scored: both question voices are generated up front and scoring compares option
IDs, which have no voice at all. It is remembered per project.

## No key? Nothing important is missing

Codemble is bring-your-own-key. Without one, the panel says so and everything
except the narration prose keeps working.

To narrate without sending your code anywhere, use a local model:

```bash
ollama pull gemma4:12b
export CODEMBLE_PROVIDER=ollama
export CODEMBLE_OLLAMA_MODEL=gemma4:12b
```

The panel tells you whether Ollama is already running on this machine and which
model it recommends. Honest caveat: grounding validation catches an invented
identifier, not a wrong claim about a real one, and smaller local models make
that second kind of mistake more often.

## Partial parses

If a file has a syntax error, Codemble keeps it visible and refuses to invent
structure inside it. Narration stays off for that file, and both the structural
summary and the narration block say why.
