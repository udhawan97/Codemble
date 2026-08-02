---
title: The galaxy
description: How your code becomes a sky — and why the camera stays on rails.
---

## Your code, mapped honestly

<figure class="cm-product-shot">
  <div class="cm-product-shot__viewport" tabindex="0" aria-label="Galaxy product screen. Scroll sideways to inspect it at a readable size.">
    <img src="/Codemble/shots/galaxy.png" alt="Codemble at galaxy level on a first run: star systems parsed from real source, each named by its file path and wearing its import-community colour family in traditional Japanese hues, with import routes drawn around the systems charted so far and an as-yet unlit Home, plus the language focus buttons, a Key disclosure, a notice that two files could not be read — all under tests/ — and a prompt to study codemble.cli next.">
  </div>
  <figcaption>Full-size product screen · drag, swipe, or use arrow keys to inspect the interface.</figcaption>
</figure>

The galaxy is not an artist's impression. Every visual property encodes a fact
from the parsed structure of your code:

| Visual | Meaning |
| --- | --- |
| Star system | One source module |
| Planet | A function or class |
| Route between systems | An import |
| Edge between planets | A call — solid when proven, dashed and labeled "possible call" when not |
| Size | Lines of code |
| Brightness and glow | How many distinct places call it (centrality) |
| Colour family | Import community — modules that import each other share a hue |
| Nebula tint | Language |
| Lit amber / dim | Understood / not yet |
| Drifting particles | A call the parser proved; possible calls stay still |
| Orbit guide | Solid = call layer from certain calls; dashed = no proven call path |
| Routes drawn around a system | You have flown there; the system is charted |

Every system is drawn, coloured and named from the very first frame, whether or
not you have been near it. What fills in as you explore is the web of **import
routes** between systems — drawing all of them at once is what makes a large
project unreadable — along with the frame the camera opens on, so a first run
starts among the modules closest to Home rather than staring at the whole disc
from far enough away to read none of it.

Hover a star and it names itself and reports how many structures use it and how
many it uses. A count of zero is left out rather than printed.

Nothing that is merely busy can outshine something you understand: the unlit
brightness ramp stops below the amber a lit star uses. Brightness counts the
distinct places that call a structure, not how many call sites they contain —
a helper hammered in one loop is not more depended-on than a shared utility.

Hue answers a different question: **which part of the project is this?** The
parser proves import communities — groups of modules that import each other —
and the project's **eight largest** communities each wear one of eight
traditional Japanese colours (seiji, fuji, koke, asagi, toki, umenezumi,
wakatake, kikyō). Real projects have more communities than that — this one has
thirty-eight — so the rest carry no hue at all and keep the plain brightness
ramp. That is deliberate: a colour shared by two unrelated groups would answer
"which part of the project is this?" wrongly, and no hue honestly says "not one
of this project's main groups". Assignment is by size, ties broken by id, so
the same code always yields the same sky. Every hue is lightness-capped at the unlit ceiling, so a lit amber
star remains the brightest object by a wide margin, and the amber band itself
is excluded from the wheel so no community can ever read as "understood".
Inside a system its planets inherit the family hue, with lightness still
answering callers.

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
the same sky. The ground it sits on carries its own colour and a band of ambient
light rather than matching the app's panels, and the unlit brightness range is
wide enough that a module belonging to none of your project's main groups is
plainly visible — while a lit amber star remains the brightest thing in the sky
by a wide margin.

At galaxy level, every system sits in a faint language-tinted nebula — one hue
for each of the seven languages Codemble reads. The seven are held at the same
lightness as each other, so no language reads as more important than another,
and all of them stay clear of the amber band, which belongs to understanding
alone. A file in a language Codemble does not read is not in the graph at all,
so there is no system to tint; the galaxy states how many such files it saw
rather than drawing a colourless one.

When you pass a region's checks, the next time you are at galaxy level that
system plays a 1.2-second **nebula dawn**: amber washes out across its halo and
fog, then recedes. The lit state is already saved before the animation runs, so
it celebrates a fact rather than delivering one. Under
`prefers-reduced-motion` the dawn is skipped entirely and you get the finished
lit state — not a faster animation, none at all.

Keyboard focus carries a visible reticle in the 3D scene as well as a live text
readout, so arrow-key navigation is never a guess about where you are.

## The trail you leave by exploring

Flying to a system **charts** it. Its import routes stay drawn from then on, the
orientation line counts it among the charted systems, and the star chart records
it under **Systems explored**. This survives restarts, saved beside the rest of
your progress.

Charting is deliberately not lighting. It is earned by travel and says only that
you went there; the amber of an understood system is earned by answering
questions drawn from your own code. Keeping them apart is the point — a map that
filled in as a reward for moving around would eventually claim you understood a
project you had only toured. Opening a module from the workflow tree, the
connections list, or the impact panel charts it too, exactly as flying to it
does.

Clearing a project's progress clears both: the understood regions and the
explored trail.

## Bounded orbit, not free flight

Drag to orbit the current subject and use the wheel to zoom. Panning is off,
distance and polar angle are clamped for each level, and clicking a node moves
between galaxy, system, and study with a scripted transition. The parser owns
every node position, so nodes do not drag away from the graph. Reading never
happens "in space": the study panel takes the foreground, and the sky behind it
recedes to the structure you are reading and its connections.

Keyboard: arrow keys move the selection between siblings and **Enter** opens the
selected one, at every level including study, where it re-targets the panel.
**Escape** steps back a level — on the Map as well as in the Galaxy — and closes
the star chart, returning focus to the control that opened it.

On a wide screen the header keeps **Modules**, **Find**, the level exit and
**Star chart** on screen, and the two occasional controls — **Change Home** and
**Switch project** — sit behind a **More** disclosure. Six permanent buttons
need more width than a header can give them without wrapping to a second row,
and the stage pays for that in height, so the two you reach least often step
aside. Below that, every secondary control lives behind a single **Menu**
button instead, because a wide header that has to wrap costs more height than
the compact one it replaces. Opening either disclosure never moves the stage.

At narrow widths guidance also occupies its own row below the stage, and Study
becomes a full-stage scrolling sheet. The map/canvas and the local-only status
remain in the viewport instead of being squeezed behind controls. Opening
Modules, Find, the Star chart or a region's checks moves keyboard focus into the
new surface; closing it returns focus to the invoking action or to the visible
Menu or More button. **Escape** closes an open disclosure without also stepping
back a level. Within the checks panel, answering keeps focus on the result
rather than dropping it back to the page.

## Two layers, one truth

The header switches between the 3D **Galaxy** and a flat **Map**. The Map has
two tabs: *Architecture* lays your modules out by folder and by how far they sit
from Home along import routes, and *Workflow* walks the call tree from your
entrypoint. Both layouts are computed by the same parser-backed graph the galaxy
draws — the map cannot show you a relationship the galaxy does not have. Modules
with no import route from Home are never guessed into position: when more than a
handful exist they fold into a counted shelf — the note says exactly how many
and **Show them** draws every one — so a project whose test fixtures outnumber
its source keeps a readable connected core without hiding a single module from
the count. Clicking anything in either layer opens the same study panel, and a
lit system is amber in both. Architecture boxes carry their community's colour
family and a language stripe, and routes are drawn in their own ink so a
connection never disappears beside a box border.

The Map opens at readable 100% on compact screens and centres Home or the
selected target instead of shrinking every box into a whole-diagram thumbnail.
**Fit** gives the overview: on a wide drawing it fits the whole shape, and on a
tall one it fits the width so layers stay readable while the height scrolls,
instead of landing on an unreadable thumbnail. The percentage button returns to
100%. Codemble remembers zoom and pan through fresh Map data and layer
switches, re-centres on your focus when a window resize would leave it staring
at empty space, and clears renderer-only view state when you switch projects.
The Map needs no WebGL, so it still works where the galaxy cannot draw.

## A region = one star system

<figure class="cm-product-shot">
  <div class="cm-product-shot__viewport" tabindex="0" aria-label="System product screen. Scroll sideways to inspect it at a readable size.">
    <img src="/Codemble/shots/system.png" alt="One star system, codemble.server.app, its 31 parser-proven structures as lit worlds in the system's own colour family, each with a procedural surface and a rim atmosphere, laid out on labelled Layer 1 and Layer 2 call guides with the call edges and drifting particles between them, and a keyboard focus reticle around the focused structure.">
  </div>
  <figcaption>Full-size product screen · drag, swipe, or use arrow keys to inspect the interface.</figcaption>
</figure>

A **region** is one module — the unit of checks, illumination, and progress.
Change a file and only its region goes dim again; the rest of your sky stays lit.
Its members orbit in labelled call layers derived from certain calls. Solid
guides mark proven layers; a cyclic or otherwise unreached structure stays
visible behind a dashed **No proven path** guide rather than receiving a
fabricated depth. A **Prove understanding** button opens that region's checks.

## Focus a mixed sky without changing it

When a project contains more than one supported language, the top rail offers an
**All** button plus one button per language actually present, each with its
system count — JavaScript and TypeScript are shortened to **JS** and **TS**, and
the rest are named in full. Focus filters the current view, its routes,
partial-file notices, and star-chart rows. It does not reparse code, move
systems, erase progress, or hide external and unresolved relationships
originating from the focused language.

Switching focus away from the system you are viewing returns safely to the
focused galaxy. Following a real relationship into another supported language
switches focus to that target instead of creating a dead end.

## Reading the connections

Below the galaxy level, every edge carries an arrowhead pointing from caller to
callee. Hover an edge for its tooltip: the two structures, whether it is an
import or a call, whether the parser is certain, and the line it was seen on. A
relationship the parser could not prove reads "possible call" or "possible
import", and is drawn **dashed** in the uncertainty colour — never as fact. The
dash matters as much as the colour: it survives colour-blindness, a dim screen
and a greyscale screenshot, and both layers now break an unproven line the same
way rather than the galaxy relying on hue alone.

Hover or select a structure and it and its edges take the interaction blue while
its neighbours hold their own colour and everything else recedes. In the study
level the selected structure stays highlighted with its connections, so the
panel and the sky agree about what you are reading. In Easy mode the unrelated
edges are hidden outright rather than faded.

Drifting particles travel a call edge the parser proved, below the galaxy level
where call edges exist. A possible call stays still, so motion can never imply
proof — and under `prefers-reduced-motion` nothing drifts at all.

Certain connections are drawn in a dedicated route ink on both layers, distinct
from panel rules and box borders, and a possible relationship is deliberately
the *more* visible of the two — an unproven claim should never be the one you
miss. The legend in the corner names every encoding: size, brightness, amber
for understood, a corner-flag mark for syntax-error files, the colour-family
row, a row for each language present, and certain versus possible relationships
— and every swatch is drawn in the same ink the sky actually uses, read from
the same table, so the key and the sky cannot drift apart. In Easy mode the
legend says the same things in plain language.

## Switching project and changing Home

Both controls live behind the header's disclosure — **More** on a wide screen,
**Menu** at narrow widths.

**Switch project** releases the current project and returns you to the picker;
progress is stored per project, so the galaxy comes back lit. This works whether
you started from the picker or passed a path. The first click reveals the
saved-progress confirmation without closing the disclosure; Cancel returns focus
to **Switch project**.

**Change Home** reopens the entrypoint picker whenever the parser ranked at
least one candidate. The Home you choose is remembered for the next run of the
same project, and a saved choice the parser no longer ranks is dropped rather
than restored.

On a first run Codemble asks for your audience, then opens the three-step coach.
Home becomes a question between them only when candidates tie for best rank —
test-scoped candidates rank below your project's own code, so on most projects
it is settled without asking. Those decisions do not stack on top of one
another, and Easy-mode guidance waits until they are finished before it suggests
anything.

The audience question is about **you**, so it is asked once and remembered for
the next project you open. Each project still keeps its own mode, which the
header's Easy/Expert toggle changes at any time.
