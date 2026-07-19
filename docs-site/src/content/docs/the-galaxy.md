---
title: The galaxy
description: How your code becomes a sky — and why the camera stays on rails.
---

## Your code, mapped honestly

The galaxy is not an artist's impression. Every visual property encodes a fact
from the parsed structure of your code:

| Visual | Meaning |
| --- | --- |
| Star system | One source module |
| Planet | A function or class |
| Route between systems | An import |
| Edge between planets | A call (uncertain calls are labeled "possible call") |
| Size | Lines of code |
| Brightness | How often it's called (centrality) |
| Color | Language |
| Lit / dim | Understood / not yet |

## Semantic zoom, not free flight

Free-flight 3D looks fun in demos and is where comprehension goes to die.
Codemble's camera moves on rails between three levels — galaxy for orientation,
system for structure, study for learning — with scripted fly-to transitions.
Reading never happens "in space": the study panel dims the scene behind it.

## A region = one star system

A **region** is one module — the unit of checks, illumination, and progress.
Change a file and only its region goes dim again; the rest of your sky stays lit.
