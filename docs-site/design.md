# Codemble design system — locked

> **Contract (family convention, same as Golavo):** every page — docs, landing,
> app UI — reads this file before emitting code. Extend or amend it here;
> never regenerate styles per page. `src/styles/tokens.css` is the single
> source of truth for values; this file explains them. Change them together.

## Genre

**Observatory instrument.** Codemble's UI is a precise, quiet instrument for
looking at something vast — closer to a planetarium console than a game HUD.
Wonder comes from the *subject* (your code as a sky), never from decoration.

**Banned for this genre:** gradient pill buttons; glassmorphism / any
`backdrop-filter`; soft radial glows; centred-everything heroes; pure black or
pure white grounds; sci-fi HUD clichés (scanlines, hex grids, fake terminals);
decorative numbering; italic words inside roman headings (the most reliable
AI tell — banned outright).

## Color — every accent has exactly one job

| Token | Job (the only job) | Dark | Light |
| --- | --- | --- | --- |
| `--cm-star` | **Illumination = understanding.** Lit states, progress, brand core. | `#facc15` | `#a16207` |
| `--cm-orbit` | **Interaction.** Links, focus rings, actionable elements. | `#67e8f9` | `#0e7490` |

Rules: a star-gold element must always mean "understood/progress"; an
orbit-cyan element must always be interactive. Accents cover **< 5% of any
viewport**. Everything else is ground + ink.

**Contrast floor:** every ink/accent token clears **4.5:1 (WCAG AA)** against
both `--cm-ground` and `--cm-ground-2`, measured on the worse surface. The
per-token ratios are annotated in `tokens.css`; re-measure when changing either
side of any pair.

## Surfaces

Paper, never glass. Solid grounds (`--cm-ground`, `--cm-ground-2`) separated by
hairline rules (`--cm-hairline`). Depth comes from layering solids, not blur or
transparency. The dark ground is the primary brand surface (the sky); light
ground exists for long-form docs reading.

## Typography

- Display: **Sora** (600/700) — headings, numerals in stats.
- Body: **Inter** (400/600).
- Code: **JetBrains Mono** (400/500).
- Headings are roman, always. Italic is body-copy emphasis only.
- Scale via `clamp()` anchors; no fixed pixel headings.

## Motion

- House easing `--cm-ease: cubic-bezier(0.16, 0.7, 0.3, 1)` everywhere —
  never default `ease`, never bounce. (The app's camera rails share it.)
- Reveal = opacity + rise ≤ 16px, once, on enter. No scroll-snap, no parallax.
- `prefers-reduced-motion`: opacity-only, ≤ 150ms.
- The one sanctioned flourish: **lighting a star** may glow-pulse once
  (`--cm-dur-reveal`) when a region is understood. It is the product's core
  reward and the only self-celebrating animation allowed.

## Macrostructure

- Docs pages: Starlight long-document layout, reached through tokens only.
- Landing page (future): narrative workflow — problem → the galaxy → the loop
  → proof (correctness contract) → install. Left-aligned hero, one CTA.
- CTAs: flat fill, 4px radius, active verb naming what happens ("Explore your
  galaxy", "Read the contract"). One primary CTA per view.

## Every page MUST share

Tokens for all color/space/type/motion values; the contrast floor; the accent
one-job rules; hairline-separated solid surfaces; roman headings; the house
easing. **Pages MAY differ on:** density, illustration, section rhythm, and
which accent (if either) appears.
