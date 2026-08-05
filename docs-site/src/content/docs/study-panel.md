---
title: The study panel
description: What the parser knows, what a model adds, and what happens when you have no key.
---

:::note[v0.16.0 product guide]
Parser-owned Impact and the captures below match the packaged app and current
source. [Choose a run or download route](/Codemble/download/).
:::

## Six sections, in order of certainty

<figure class="cm-product-shot">
  <div class="cm-product-shot__viewport" tabindex="0" aria-label="Study panel product screen. Scroll sideways to inspect it at a readable size.">
    <img src="/Codemble/shots/study-panel.png" alt="The current source study panel for the codemble.server.app module: kind, 423-line span, parser-proven resolution, and a structural summary marked &quot;No model needed&quot; with its inbound and outbound edge counts.">
  </div>
  <figcaption>Full-size product screen · drag, swipe, or use arrow keys to inspect the interface.</figcaption>
</figure>

Open a planet and the panel builds itself from the most certain evidence
outward:

1. **What this is** — a summary written from parser facts alone: kind, file and
   line, size, what reaches it and what it reaches, and how many of those links
   are possible rather than certain. It names the *relation* — "two other files
   bring it in" for imports, "two other parts call it" for calls — because the
   panel's **Called by** figure counts calls only, and two counts of "who uses
   this" wearing one word cannot be told apart. No key, no network, no model.
2. **Impact** — what a change here would reach, and what this depends on.
3. **The explanation** — grounded narration from your configured provider, with
   a `file:line` citation on every claim. Codemble refuses to display provider
   output that names anything outside the parsed graph.
4. **Connections** — every relationship the parser observed into and out of this
   structure, grouped inbound and outbound. Each row states direction, whether
   the relationship is certain or only possible, and the `file:line` where the
   *other* structure is defined, so you can go read it. Click any row to study
   that structure. A small diagram above the list shows callers, this structure,
   and callees at a glance.
5. **Real source** — the exact lines, numbered, straight from your file.
6. **The language lens** — idiom notes anchored to constructs the parser
   actually detected.

Every section except the explanation is model-free. If narration fails or is not
configured, all of them are still there.

The panel opens at the top, because the order above runs from most certain to
least. The one exception is the Map's **Read the source** button: it names the
source, so it takes you to the source. On a module with a long impact list the
excerpt can sit thousands of pixels down, and a control that promises the file
should not land you above three other sections. Reaching the same structure any
other way — a connection row, an impact row, a planet — still opens at the top.

## Impact: what a change here reaches

<figure class="cm-product-shot">
  <div class="cm-product-shot__viewport" tabindex="0" aria-label="Impact product screen. Scroll sideways to inspect it at a readable size.">
    <img src="/Codemble/shots/study-impact.png" alt="The current Expert study panel scrolled to Impact, listing structures affected by a change and dependencies that could break it, with direct depth and real file locations.">
  </div>
  <figcaption>Codemble v0.16.0 · parser-owned Impact works without a model.</figcaption>
</figure>

Two lists, side by side. One answers *change this and what else feels it*; the
other answers *what does this need in order to work*. Each row is a real
structure with a clickable `file:line`, and each carries the depth at which it
was reached — **direct** for one hop, then how many steps out — because a
learner choosing what to read next needs that difference.

The reach is traced up to three hops. When the chain continues past that, the
panel says so instead of implying the list is complete. A row reached only
through a relationship the parser could not prove is labelled **possible**, and
that label applies to the whole chain: one unproven link makes everything beyond
it unproven, and Codemble will not round that up to a fact.

The lists are also shorter than they used to be. A method call matched on its
name alone reached every class in the project declaring that name, which padded
the blast radius with structures a change could not actually touch; several of
those cases now resolve to the one class involved. The
[correctness contract](/Codemble/correctness/) sets out the evidence that
allows it.

It is traced from the parsed graph alone, so it needs no API key and no network.
Expert mode puts it first — when you are onboarding onto a codebase, *what does
this control and what can break it* comes before prose. Easy mode states the
same two lists in plain words below the write-up.

## What the explanation is now

The write-up answers in at most three sentences and leads with what the
structure is *for*. The line-by-line walkthrough is still there and still cited
line by line, but it sits behind a closed disclosure you click to open, rather
than being the first thing you meet on every click.

In Easy mode the explanation may reach for an everyday comparison to get a
purpose across. In Expert mode it may not.

Narration runs on its own budget, so a slow model call no longer holds up the
galaxy, the diagram, the source view, or a quiz. It answers within 45 seconds
either way; because the work continues in the background, retrying after a
timeout is usually instant.

When narration cannot be produced, the panel says which thing went wrong: a
network Codemble could not reach, a request the provider rejected, a reply it
could not read, a model taking too long, or a genuine refusal to show output
that falls outside parser evidence. Only the last of those is a correctness
decision, and only it explains the grounding rules. If one item of a reply is
malformed, that item is dropped and the panel says how many were left out rather
than discarding a good explanation.

Very long files are narrated from a bounded excerpt, and the panel states which
lines were sent. Codemble will not describe a line the model was not shown.

## Easy and Expert

The header's **Mode** toggle changes how Codemble talks to you, and how much it
puts on screen at once:

| | Easy | Expert |
| --- | --- | --- |
| Narration | Short sentences, every term explained in place, an everyday comparison allowed | Concise, assumes fluency, no comparisons |
| Impact | Plain words, below the write-up | Leads the panel |
| Check questions | "Which piece of code…" | "Which structure…" |
| Labels | "Called by", "Possible connection" | "Callers", "Possible relationship" |
| Lens notes | The idiom in plain words | The precise language mechanic |
| Density | Opens on the Map, hides unrelated galaxy edges, larger type | Opens on the Galaxy, shows everything |

Some surface names change with the mode as well: the flat layer is labelled
**Diagram** in Easy and **Map** in Expert, and its two tabs read **How it fits
together** / **What runs first** in Easy against **Architecture** / **Workflow**
in Expert. They are the same two views of the same parser evidence; this
documentation uses the Expert names throughout.

Easy mode also shows a hint chip naming the nearest unlit region to Home,
counted in import-route hops over the graph — no model picks it for you. Where
several regions sit the same number of hops away, it prefers the one with more
parser-proven structures, so the first suggestion is rarely a one-line package
init. Its action follows the current level: while you are somewhere else it
opens the suggested system, and once you are inside it the chip becomes an
instruction — read it before proving it — rather than a button. That applies
both when the action could not move you forward and when the region's own panel
is already showing it: on the Map, **Read the source** sits directly above the
chip, so repeating it there would be two controls for one step.
Guidance stays out of the way until the first-run choices — audience, Home, and
the coach marks — are finished.

Mode never changes the graph, the coordinates, your progress, or how a check is
scored: both question voices are generated up front and scoring compares option
IDs, which have no voice at all. It is remembered per project.

## No key? Nothing important is missing

Codemble is bring-your-own-key. Without one, the panel says so and everything
except the narration prose keeps working — including Impact, which is the part
most people expect to need a model and which needs none.

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
