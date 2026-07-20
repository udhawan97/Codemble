---
title: The study panel
description: What the parser knows, what a model adds, and what happens when you have no key.
---

## Five sections, in order of certainty

Open a planet and the panel builds itself from the most certain evidence
outward:

1. **What this is** — a summary written from parser facts alone: kind, file and
   line, size, how many things use it, how many it uses, and how many of those
   links are possible rather than certain. No key, no network, no model.
2. **The explanation** — grounded narration from your configured provider, with
   a `file:line` citation on every claim. Codemble refuses to display provider
   output that names anything outside the parsed graph.
3. **Connections** — every relationship the parser observed into and out of this
   structure. Each row states direction, whether the relationship is certain or
   only possible, and where it was seen. Click any row to study that structure.
4. **Real source** — the exact lines, numbered, straight from your file.
5. **The language lens** — idiom notes anchored to constructs the parser
   actually detected.

Sections 1, 3, 4 and 5 never involve a model. If narration fails or is not
configured, they are all still there.

## Easy and Expert

The header's **Mode** toggle changes wording only:

| | Easy | Expert |
| --- | --- | --- |
| Narration | Short sentences, every term explained in place | Concise, assumes fluency |
| Check questions | "Which piece of code…" | "Which structure…" |
| Labels | "Used by", "Possible connection" | "Calls in", "possible call" |

Mode never changes the graph, the coordinates, your progress, or how a check is
scored. It is remembered per project.

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
