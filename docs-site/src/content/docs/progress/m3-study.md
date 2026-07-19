---
title: "Build log: study without guessing"
description: M3 adds real source, provider-neutral narration, validation, and a local file-hash cache.
---

**Week of July 19, 2026 · Milestone M3 complete**

The Study level now opens the exact parser-selected source span with stable line
numbers. It also shows an explanation only after Codemble can bind every line
and relationship in the provider response back to supplied evidence.

The narration module has one small provider interface and two real adapters:
Anthropic Messages and OpenAI Responses. Keys come from environment variables
or `~/.codemble/config`; requests go from the learner's machine directly to the
chosen provider. Nothing runs in the background—opening a node is the trigger.

Grounding is enforced after the model responds:

- walkthrough lines must stay inside the selected parser span
- relationship IDs must already exist among parser-observed neighbors
- each displayed explanation block carries a real `file:line`
- invalid JSON or out-of-graph evidence is withheld with an honest error state
- only validated results enter the local cache

The cache key includes the provider, model, node ID, prompt version, and current
file hash. Reopening the same node is a disk-cache hit; editing its file produces
a different key. Removing the API key leaves source and relationships intact.

Acceptance evidence: provider adapters exercised through injected local
transports; cache reopen and file-hash invalidation covered by tests; grounded
and deliberately invalid responses checked in the production UI; no-key desktop
and 320 px states clean; Python, Ruff, Vite, Astro, and docs gates green.

M4 is next: parser-detected Python idioms and the first star chart.
