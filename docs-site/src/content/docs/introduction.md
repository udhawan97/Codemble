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
as a diagram. Every module is drawn, coloured and named from the first frame;
every one of them starts dim.

You explore, read what the parser knows before any model is asked, see what a
change to a structure would reach, read explanations grounded in your actual
source, learn the language idioms your code uses, and pass short **checks**
whose answers come from the code's real structure. Each region you truly
understand **lights up — permanently**. The goal state is a fully lit galaxy.

Travelling counts for something too, but for something smaller: flying to a
system charts it and keeps its routes drawn, and the star chart records how many
you have explored. That is a record of where you have been, never a claim about
what you understood — only a passed check makes that claim.

## Who it's for

Early and intermediate coders who built something with AI and want to actually
own it. Everything runs locally on your machine. Prose explanations are the one
optional extra: bring your own Claude or OpenAI key, or run a local model
through Ollama and send nothing anywhere.

:::note[Status]
Codemble **v0.15.0** is published on PyPI and maps Python, JavaScript,
TypeScript, Go, Java, Rust, C#, and mixed projects. The downloadable package,
current source, screenshots, and these product guides match. The original
unaided learner-acceptance issue remains open; technical completion does not
substitute for human evidence. [Choose a run or download route](/Codemble/download/).
:::
