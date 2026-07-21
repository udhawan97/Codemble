---
title: The galaxy
description: How your code becomes a sky — and why the camera stays on rails.
---

## Your code, mapped honestly

![Codemble at galaxy level: eighty dim star systems parsed from real source, with the legend, the language focus buttons, and a notice that two files are unchartable because their parser reported a syntax error.](/Codemble/shots/galaxy.png)

The galaxy is not an artist's impression. Every visual property encodes a fact
from the parsed structure of your code:

| Visual | Meaning |
| --- | --- |
| Star system | One source module |
| Planet | A function or class |
| Route between systems | An import |
| Edge between planets | A call (uncertain calls are labeled "possible call") |
| Size | Lines of code |
| Brightness and glow | How many distinct places call it (centrality) |
| Nebula tint | Language |
| Lit amber / dim | Understood / not yet |
| Drifting particles | A call the parser proved; possible calls stay still |
| Orbit ring | Call depth — the inner ring runs first |

Nothing that is merely busy can outshine something you understand: the unlit
brightness ramp stops below the amber a lit star uses. Brightness counts the
distinct places that call a structure, not how many call sites they contain —
a helper hammered in one loop is not more depended-on than a shared utility.

## While a large project loads

Parsing runs on a background thread, so the browser stays responsive. The
loading screen names the stage it is in — finding files, reading each file,
connecting imports and calls, building checks, placing the galaxy — with a
real file count while files are being read. The stages after that advance by
naming the real sub-step running rather than a count, because none of them has
a per-file total to report honestly. If the parse fails, you land back on the
picker with the parser's own error message and a one-click retry for the same
folder — no need to restart Codemble. Cancelling works the same way: it
returns you to the picker and stops the parse at the next file boundary.

## Light that means something

The sky is lit rather than drawn. Every star carries a halo generated on a
canvas at runtime, and a bloom pass is tuned so the amber of an understood
system blooms hard while the unlit ramp barely registers — brightness in this
sky is a claim, so it is spent where a claim exists.

The background starfield is not decoration either. It is generated from a seed
derived from your project's own file hashes, so the same code always produces
the same sky. At galaxy level, Python, JavaScript, and TypeScript systems sit
in a faint language-tinted nebula; a system in any other language renders no
fog at all rather than borrowing a colour that would imply evidence Codemble
does not have.

When you pass a region's checks, the next time you are at galaxy level that
system plays a 1.2-second **nebula dawn**: amber washes out across its halo and
fog, then recedes. The lit state is already saved before the animation runs, so
it celebrates a fact rather than delivering one. Under
`prefers-reduced-motion` the dawn is skipped entirely and you get the finished
lit state — not a faster animation, none at all.

Keyboard focus carries a visible reticle in the 3D scene as well as a live text
readout, so arrow-key navigation is never a guess about where you are.

## Bounded orbit, not free flight

Drag to orbit the current subject and use the wheel to zoom. Panning is off,
distance and polar angle are clamped for each level, and clicking a node moves
between galaxy, system, and study with a scripted transition. The parser owns
every node position, so nodes do not drag away from the graph. Reading never
happens "in space": the study panel takes the foreground, and the sky behind it
recedes to the structure you are reading and its connections.

At narrow widths the header's secondary actions live behind **Menu**, guidance
occupies its own row below the stage, and Study becomes a full-stage scrolling
sheet. The map/canvas and the local-only status remain in the viewport instead
of being squeezed behind controls. Opening Modules, Find, or the Star chart
moves keyboard focus into the new surface; closing it returns focus to the
invoking action or to the visible Menu button.

## Two layers, one truth

The header switches between the 3D **Galaxy** and a flat **Map**. The Map has
two tabs: *Architecture* lays your modules out by folder and by how far they sit
from Home along import routes, and *Workflow* walks the call tree from your
entrypoint. Both layouts are computed by the same parser-backed graph the galaxy
draws — the map cannot show you a relationship the galaxy does not have. Modules
with no import route from Home are placed in their own row and labelled, never
guessed into position. Clicking anything in either layer opens the same study
panel, and a lit system is amber in both.

The Map opens at readable 100% on compact screens and centres Home or the
selected target instead of shrinking every box into a whole-diagram thumbnail.
Use **Fit** for that overview and the percentage button to return to 100%.
Codemble remembers zoom and pan through fresh Map data and layer switches, but
clears renderer-only view state when you switch projects. The Map needs no
WebGL, so it still works where the galaxy cannot draw.

## A region = one star system

![One star system, codemble.server.app, with its functions and classes in call-depth orbits, the call edges between them, and a keyboard focus reticle around the focused structure.](/Codemble/shots/system.png)

A **region** is one module — the unit of checks, illumination, and progress.
Change a file and only its region goes dim again; the rest of your sky stays lit.
Its members orbit by call depth, and a **Prove understanding** button opens that
region's checks.

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

Hover or select a structure and it and its edges take the interaction blue while
its neighbours hold their own colour and everything else recedes. In the study
level the selected structure stays highlighted with its connections, so the
panel and the sky agree about what you are reading. In Easy mode the unrelated
edges are hidden outright rather than faded.

Drifting particles travel a call edge the parser proved, below the galaxy level
where call edges exist. A possible call stays still, so motion can never imply
proof — and under `prefers-reduced-motion` nothing drifts at all.

The legend in the corner names every encoding: size, brightness, amber for
understood, the unchartable colour for syntax-error files, one swatch per
language, and certain versus possible relationships. In Easy mode it says the
same things in plain language.

## Switching project and changing Home

**Switch project** in the header releases the current project and returns you to
the picker; progress is stored per project, so the galaxy comes back lit. This
works whether you started from the picker or passed a path. In the compact Menu,
the first click reveals the saved-progress confirmation without closing the
Menu; Cancel returns focus to **Switch project**.

**Change Home** reopens the entrypoint picker whenever the parser ranked at
least one candidate. The Home you choose is remembered for the next run of the
same project, and a saved choice the parser no longer ranks is dropped rather
than restored.

On a first run with more than one honest Home candidate, Codemble asks for your
audience first, then Home, then opens the three-step coach. Those decisions do
not stack on top of one another.
