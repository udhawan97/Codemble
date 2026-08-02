---
title: Correctness contract
description: The six rules that outrank every feature.
---

Codemble's audience often **cannot detect when a tool is wrong** — that is
precisely why they need it. A tool that teaches a beginner something false is
worse than no tool. So these rules outrank every feature request:

1. **Structure is never invented.** Nodes, edges, entrypoints, and idiom
   locations come only from the parser. The LLM may not add, rename, or infer
   structure.
2. **Explanations are grounded.** The model explains only what is present in
   the source it is shown, references real identifiers, and says *"unclear from
   the code"* rather than guess.
3. **Lens claims attach only to parser-detected constructs.**
4. **Every explanation links to a real `file:line`** so you can check it.
5. **Check answers come from the graph, never the model.**
6. **Approximate call edges are labeled "possible call"** — never stated as fact.

Rule 6 travels. When the study panel traces what a change would reach, a chain
that passes through one unproven relationship is labelled possible for its whole
length — an uncertain first step cannot be laundered into a certain third one.

## Hedging less by proving more

Rule 6 governs what Codemble refuses to claim. It is not a licence to stop
trying, and a call matched on nothing but its name is a weak thing to draw. A
call to `.parse()` used to reach *every* class in the project that declared a
method by that name.

Codemble now reads three further kinds of parser evidence first:

- A receiver constructed where it is called — `Thing().run()` — names its class
  outright. **Certain.**
- A method inherited from a base class in the same project, resolved by walking
  the base chain. **Certain** when that walk finds one declaration.
- A receiver carrying a type annotation — `def f(a: Adapter): a.parse()` —
  resolves to that class but stays **possible**, because Python dispatches on
  the runtime type and a subclass may override the method the annotation points
  at.

That third case is the contract working rather than an exception to it: real
evidence narrowed the target, and it still was not proof. Anything no evidence
narrows is still drawn as a possible relationship — nothing is dropped for being
hard to prove, and nothing is promoted without proof.

Measured on Codemble's own source, 8,508 call edges became 6,778, with 1,993
fewer of them unproven; the gap between those two numbers is relationships that
moved from possible to certain rather than disappearing. The unproven share fell
from 79% to 70%.

This belongs on a correctness page rather than in a changelog because three
things you are invited to read as facts about your project are computed from
those edges: how brightly a module glows, how far the study panel's Impact lists
say a change reaches, and how dense the Architecture map's route mesh looks. All
three were previously padded with relationships that did not exist.

Rule 2 has a matching rule about failure. Codemble withholds provider output
that falls outside parser evidence, and it says so in those words *only* when
that is what happened. A network it could not reach, a request the provider
rejected, a reply it could not parse, and a model taking too long each say what
they are. A connectivity fault reported as a correctness refusal teaches the
wrong lesson about both.

## What is missing is stated too

Inventing nothing is only half the job. A galaxy drawn from part of your project
looks exactly like a galaxy drawn from all of it, so Codemble names its own
gaps:

- **Files it could not read.** A source file with a syntax error is counted and
  attributed to the directory it came from, so you know the error is in that
  file and not in your understanding.
- **Languages it does not speak.** Codemble reads seven: Python, JavaScript,
  TypeScript, Go, Java, Rust, and C#. If your project has Kotlin, Ruby, or Swift
  beside them, the count and the language are stated on the Galaxy and Map
  layers. Nothing about those files is guessed — they contribute no box, no
  star, and no connection — but you are told they exist. Shipping an adapter
  silences its own extension, so the count shrinks when a language moves from
  unread to read rather than needing a second list to be kept in step.

Extensions that belong to more than one language are reported by extension
alone. `.h` is C or C++ and `.m` is Objective-C or MATLAB, and naming one would
be the same guess the contract forbids everywhere else.

Found a violation? That's a bug of the highest severity —
[report it](https://github.com/udhawan97/Codemble/issues).
