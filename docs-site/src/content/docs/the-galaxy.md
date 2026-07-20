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

## Focus a mixed sky without changing it

When a project contains more than one supported language, the top rail offers
**All**, **Python**, **JS**, and **TS** focus buttons with system counts. Focus
filters the current view, its routes, partial-file notices, and star-chart rows.
It does not reparse code, move systems, erase progress, or hide external and
unresolved relationships originating from the focused language.

Switching focus away from the system you are viewing returns safely to the
focused galaxy. Following a real relationship into another supported language
switches focus to that target instead of creating a dead end.

## Reading the connections

Below the galaxy level, every edge carries an arrowhead pointing from caller to
callee. Hover an edge for its tooltip: the two structures, whether it is an
import or a call, whether the parser is certain, and the line it was seen on. A
relationship the parser could not prove reads "possible call" or "possible
import" and is drawn in the uncertainty colour — never as fact.

Hover or select a structure and its connections brighten to the interaction
blue while its neighbours hold their colour and everything else recedes. In the
study level the selected structure stays highlighted with its connections, so
the panel and the sky agree about what you are reading.

The legend in the corner names every encoding: size, brightness, amber for
understood, the unchartable colour for syntax-error files, and certain versus
possible relationships. In Easy mode it says the same things in plain language.

## Switching project and changing Home

**Switch project** in the header releases the current project and returns you to
the picker; progress is stored per project, so the galaxy comes back lit. This
works whether you started from the picker or passed a path.

**Change Home** reopens the entrypoint picker at any time. The Home you choose
is remembered for the next run of the same project, and a saved choice the
parser no longer ranks is dropped rather than restored.
