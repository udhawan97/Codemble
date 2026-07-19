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

Found a violation? That's a bug of the highest severity —
[report it](https://github.com/udhawan97/Codemble/issues).
