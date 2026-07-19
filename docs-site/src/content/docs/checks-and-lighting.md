---
title: Checks & lighting
description: The game loop — prove you understand a region, light it up forever.
---

## Why checks exist

Reading an explanation is the weakest form of learning. Codemble makes you
**prove** understanding with short active checks before a region lights up.

## Where questions come from

Every check is generated from your code's real graph, so the answer is always
verifiably correct:

- *"Which function does `main()` call first?"* — from call edges
- *"Which files import `utils`?"* — from import edges
- *"If you deleted `foo()`, what would break?"* — from its callers
- *"Where does execution start?"* — from the entrypoint

The LLM phrases questions and feedback. It **never decides the answer** — the
graph does. A check that could be wrong does not ship.

## Lighting rules

- Pass a region's checks → its stars light **permanently**.
- Progress is saved locally and survives restarts.
- Edit a file → only that region re-dims. Understanding is re-earned where the
  code actually changed, never globally revoked.
