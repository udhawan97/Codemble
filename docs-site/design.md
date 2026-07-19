# Codemble design system — locked

> **Contract (family convention, same as Golavo):** every page — docs, landing,
> app UI — reads this file before emitting code. Extend or amend it here;
> never regenerate styles per page. `src/styles/tokens.css` is the single
> source of truth for values; this file explains them. Change them together.

## Genre

**Edo star atlas (天文図).** Edo astronomers published the sky as numbered
plates: gold stars and constellation lines on deep indigo, each plate framed,
annotated, and signed by the astronomer who vouched for it. Codemble makes
exactly that of a codebase, so the site *is* one of those atlases rather than a
page about one. The instrument voice from the previous system is preserved —
precise, quiet, made for looking at something vast — but it now has a material:
paper, ink, and gold.

Wonder comes from the *subject* (your code as a sky), never from decoration.

**Banned for this genre:** gradient pill buttons; glassmorphism / any
`backdrop-filter`; centred-everything heroes; pure black or pure white grounds;
sci-fi HUD clichés (scanlines, hex grids, fake terminal title bars); italic
words inside roman headings (the most reliable AI tell — banned outright).

## Color — every accent has exactly one job

Palette is **Formal Edo**, from `codemble_design/assets/palette.json`.

| Token | Job (the only job) | Dark | Light |
| --- | --- | --- | --- |
| `--cm-star` | **Illumination = understanding.** Lit states, progress, brand core. | `#e89b2e` kohaku 琥珀 | `#7d4a06` |
| `--cm-orbit` | **Interaction.** Links, focus, current page, actionable elements. | `#82abec` ruri 瑠璃 | `#2b4d96` |

Grounds are kachi 勝色 indigo (`#070b1c` night, `#101a3e` surface) in dark and
gofun 胡粉 shell-white (`#faf7f0`) in light.

Rules: a kohaku element must always mean "understood/progress"; a ruri element
must always be interactive. **Kohaku may never mark a navigation state** — that
is interaction, and claiming "understood" about a nav position is a lie in the
palette. Accents cover **< 5% of any viewport**; the asset brief's ratio is
~90% ground/ink, ~9% ruri, ~1% kohaku.

**Contrast floor:** every ink/accent token clears **4.5:1 (WCAG AA)** against
both `--cm-ground` and `--cm-ground-2`, measured on the worse surface. Ratios
are annotated in `tokens.css`; re-measure when changing either side of a pair.
Note ruri-500 `#3f6ac0` measures only 3.8:1 on night — it is a **fill** colour
only, never text. Text-weight lapis is ruri-200.

## Surfaces

Paper, never glass. Solid grounds separated by hairline rules; depth comes from
layering solids, not blur or transparency. The dark ground is the primary brand
surface (the sky); the light ground exists for long-form docs reading and reads
as washi.

## Typography

- Display: **Shippori Mincho** (500/700) — a formal Japanese mincho. Sharp
  vertical stress, high stroke contrast, native kana/kanji. Carries the Edo
  register a Latin high-contrast serif cannot.
- Body: **Zen Kaku Gothic New** (400/500/700) — its gothic counterpart.
- Code/data: **JetBrains Mono** (400/500).
- Headings are roman, always. Italic is body-copy emphasis only.
- Scale via `clamp()` anchors; no fixed pixel headings.

## Motion

- House easing `--cm-ease: cubic-bezier(0.16, 0.7, 0.3, 1)` everywhere —
  never default `ease`, never bounce. (The app's camera rails share it.)
- Reveal = opacity + rise ≤ 16px, once, on enter. No scroll-snap.
- Parallax is allowed **only** for the tatebanko hero, where it is the medium
  rather than an effect.
- `prefers-reduced-motion`: opacity-only, ≤ 150ms; parallax and the breathing
  gold both stop.
- The one sanctioned flourish: **lighting a star** may glow-pulse when a region
  is understood. It is the product's core reward and the only self-celebrating
  animation allowed.

## Macrostructure

- Docs pages: Starlight long-document layout, reached through tokens only.
- Landing: **numbered plates in 起承転結 (kishōtenketsu)** order — 起 the chart,
  承 the instrument, 転 the turn, 結 the contract. The four-act form is used
  because it is true of the content: the third plate is a genuine turn, where a
  visualisation reveals a pass/fail gate. A vertical tategaki rail marks reading
  position. Left-aligned hero, one primary CTA.
- CTAs: flat fill, 3px radius, active verb naming what happens ("Chart your
  project", "Read the contract"). One primary CTA per view.

## Signature

**The tatebanko hero** (立版古 — the Edo paper diorama): three printed sheets —
field, chart, gold — drifting at different rates against pointer and scroll.
Depth comes from parallax between flat prints, not from perspective maths, so
the artwork stays a print you could hold. One signature per site; a future page
wanting a different one *replaces* this, it does not join it.

## Motifs

- **Enso 円相** — the open circle is the brand mark and the hero's chart.
- **Kasumi 霞** — lobed heraldic mist, used *only* as the rule between plates.
  (Golavo owns seigaiha waves; the family stays legible by not repeating them.)
- **Asanoha 麻の葉** — the triangular hemp-leaf lattice, docs ground only, at a
  whisper.
- **Kaō 花押** — the brush cipher that signs the correctness contract.

One motif, one job — the same discipline as the accents.

## Artwork

Plate art is **generated, not hand-drawn**: `scripts/build-plates.mjs` emits
`public/brand/plates/*.svg` from a fixed seed. Geometric art (tapered brush
arcs, star fields, lobed mist) gets exact coordinates and a readable diff this
way, and "same seed → same sky" mirrors the app's determinism rule. Output is
committed; the site never runs the script at build time.

## Every page MUST share

Tokens for all colour/space/type/motion values; the contrast floor; the accent
one-job rules; hairline-separated solid surfaces; roman headings; the house
easing. **Pages MAY differ on:** density, plate artwork, section rhythm, and
which accent (if either) appears.

## Known traps

- Grid and flex children default to `min-width: auto`. A non-wrapping element
  (a long install command) will force its track wider than the viewport, and
  with `overflow-x: clip` on `<body>` the overspill becomes unreachable rather
  than scrollable. Set `min-width: 0` on any container holding one.
- Astro scopes `<style>` by stamping attributes at build time. Markup injected
  later with `innerHTML` never receives them — reach it via `:global()` through
  a parent that *is* in the template.
- The CSS minifier drops `-webkit-box-orient`, and a `-webkit-box` without it
  lays out horizontally. Clamp line counts with `max-height`, not `-webkit-box`.
