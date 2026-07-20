---
title: Introduction
description: What Codemble is, who it is for, and why it exists.
---

**Codemble is a learning game that turns the code AI wrote for you into a galaxy
you light up by understanding it.**

## The problem

People increasingly learn to code by building with AI agents — Claude Code,
Codex — and end up with working apps they **don't understand**. They can't debug
them, extend them, or explain them. Existing tools explain *at* you: passive
tours, generated summaries. None of them make you **prove** you understood, and
none teach the *language* as it appears in your own code.

## The idea

Point Codemble at your project. It parses your code into a real structural
graph — no guessing — and gives you two ways to look at that one graph: a **3D
galaxy** where modules are star systems, functions are planets and your
entrypoint is Home, and a flat **Map** that lays out architecture and workflow
as a diagram. Every node starts dim.

You explore, read what the parser knows before any model is asked, read
explanations grounded in your actual source, learn the language idioms your code
uses, and pass short **checks** whose answers come from the code's real
structure. Each region you truly understand **lights up — permanently**. The
goal state is a fully lit galaxy.

## Who it's for

Early and intermediate coders who built something with AI and want to actually
own it. Everything runs locally on your machine. Prose explanations are the one
optional extra: bring your own Claude or OpenAI key, or run a local model
through Ollama and send nothing anywhere.

:::note[Status]
Codemble is in its Phase 1 tester release, installable from PyPI. Python,
JavaScript, TypeScript, and mixed projects run through the same local learning
loop. The original unaided Python
learner-acceptance issue remains open; technical completion does not substitute
for human evidence. Follow on [GitHub](https://github.com/udhawan97/Codemble) —
the roadmap stays public.
:::
