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

Questions and answers are deterministic in v1. The check service uses exactly
four parser-owned evidence families:

- first certain project call, ordered by real source line
- direct project imports
- direct callers that depend on a structure
- parser-ranked execution entrypoint

The provider is not called to phrase, score, or explain a check. The response
sent to the browser withholds the answer; submission is compared against the
immutable generated option IDs. After an attempt, Codemble shows the graph-owned
answer and its real `file:line` evidence. A check that cannot be derived with
certainty is not offered.

## Lighting rules

- Pass a region's checks → its stars light **permanently**. Back at galaxy
  level that system plays a 1.2-second **nebula dawn** — amber washing out
  through its halo and fog and receding. The lit state is saved before the
  animation runs, so the dawn marks a fact rather than delivering it, and
  `prefers-reduced-motion` skips straight to the finished lit state.
- Progress is saved locally and survives restarts.
- Edit a file → only that region re-dims. Understanding is re-earned where the
  code actually changed, never globally revoked.

Progress lives in a project-keyed JSON record under `~/.codemble/progress` and
is written only after every offered check in the region passes. Each region is
bound to a deterministic signature of its current parser file hashes. On the
next run, matching regions light and changed regions stay dim; no background
watcher or network service is involved.

## Right answers say so

A correct answer is confirmed in place — "Correct. That answer is fixed by the
parser graph." — before the next question loads. A wrong answer still shows the
graph's answer and the evidence behind it.

## Why a region can stay dim forever

Every question Codemble asks is answered by the parser graph, and every question
must offer at least one wrong option. A region with no certain relationship
gives Codemble nothing to build a question from, so it stays dim and says so.
Lighting it anyway would mean the amber said something untrue about what you
understand. Import that module somewhere, or call something inside it, and its
checks appear.

## Starting a project over

The star chart has a **Clear this project's progress** control behind a
confirmation. It forgets the understood regions for the project you have open
and nothing else: progress is stored per project in `~/.codemble/progress/`,
and other projects keep theirs. Your Easy/Expert preference survives the reset.
