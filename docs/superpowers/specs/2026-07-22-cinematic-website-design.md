# Cinematic website — semantic-zoom landing experience

**Date:** 2026-07-22

**Status:** approved by UD

**Scope:** public landing page only; documentation and product app behavior are
unchanged.

## Problem

The current landing page opens with a strong tatebanko hero, then loses visual
authority. Plate two explains Galaxy, System, and Study through three equal,
static illustration cards. The page describes Codemble’s semantic zoom instead
of letting a visitor experience it, and the real shipped interface appears
nowhere on the landing page.

Adding generic particles, floating orbs, autoplay GIFs, or a WebGL object would
make the page louder without making Codemble clearer. The improvement must make
the product’s actual learning loop more visible.

## Approved direction

Keep the locked Edo star-atlas system and the four-act kishōtenketsu narrative.
Replace plate two’s static card grid with an **Atlas Journey**: a scroll-directed
product stage made from real Codemble screenshots.

- **Galaxy:** begin with the whole parser-proven sky.
- **Map:** flatten the same truth into the Architecture layer.
- **System:** move from modules to functions and classes in deterministic orbits.
- **Study:** land on a real structure, source evidence, and grounded summary.

The stage is the page’s one new orchestrated motion primitive. Its scale and
crossfade communicate semantic zoom; no motion exists only for spectacle.

## Structure

### Hero

The existing left-biased copy, primary CTA, install command, and tatebanko
remain. Refine its material depth without adding another motif or an unrelated
effect. The hero must still work if its artwork is removed.

### Plate two — Atlas Journey

Desktop (`>= 60rem`):

- A two-column scroll passage.
- The real product plate is sticky within the section.
- Four screenshots occupy the same physical plate and transition through
  opacity and transform only.
- Copy steps remain in normal document flow and activate their matching image
  through `IntersectionObserver`.
- The active step has a ruri interaction marker; the final understood state may
  use kohaku because it denotes illumination.

Compact (`< 60rem`):

- No sticky positioning, perspective, or overlapping media.
- Every step renders its screenshot directly above its own copy.
- Images lazy-load with explicit intrinsic dimensions.

Reduced motion:

- The sticky cinematic stage is disabled.
- All four step-image pairs render as a static reading sequence.
- No spatial transition, parallax, or animated reveal is required to understand
  the page.

No-JavaScript fallback:

- The first desktop frame is visible.
- All explanatory copy remains readable.
- Compact layouts remain fully paired through CSS alone.

### Plates three and four

Retain the turn, correctness contract, installation sequence, and footer. Their
job is evidence and commitment, so they remain visually quieter than plate two.

## Visual treatment

- Real screenshots are shown as border-only atlas plates, never with redrawn
  browser or device chrome.
- A restrained perspective on the desktop media plane creates physical depth;
  the screenshot itself remains undistorted at the active state.
- Inactive frames move no more than a few percent in scale or sixteen pixels in
  translation.
- Screenshot edges are square or near-square, matching Edo joinery and the
  existing token geometry.
- Existing generated SVG tatebanko and kasumi assets remain the illustration
  system. No stock media, generated raster, Lottie, Three.js, GSAP, or new
  dependency is introduced.

## Motion contract

- Animation properties: `transform` and `opacity` only.
- House easing: `--cm-ease`.
- Scene transition: at most `--cm-dur-slow`.
- Scene activation uses `IntersectionObserver`, not a scroll listener.
- The stage activates only above the desktop motion breakpoint.
- `prefers-reduced-motion: reduce` renders final static states in <= 150 ms.
- Existing button, copy, theme, and focus behavior is unchanged.

## Accessibility

- The textual steps form the accessible explanation; overlapping desktop media
  is marked presentation-only to avoid four duplicate screen descriptions.
- Compact media uses concise, truthful `alt` text beside its matching copy.
- Heading order stays `h1` → `h2` → `h3`.
- Every interactive target remains at least 44 x 44 CSS pixels on coarse
  pointers.
- Focus indicators remain immediate and use ruri.
- No state relies on color alone; active steps also gain a marker and type
  treatment.

## Performance

- Reuse committed PNG screenshots; no new raster assets.
- Desktop stage images are lazy-loaded below the fold and decoded async.
- Browsers deduplicate compact/desktop references to the same asset URLs.
- Zero runtime dependencies; one bounded observer controls scene state.
- No layout property is animated and no global scroll handler is introduced.

## Files

- New: `docs-site/src/components/AtlasJourney.astro`.
- Replace the plate-two card markup in `docs-site/src/pages/index.astro`.
- Add stage and responsive rules to `docs-site/src/styles/landing.css`.
- Update the Hallmark record in `docs-site/src/styles/tokens.css`.
- Amend `docs-site/design.md`, `CHANGELOG.md`, and `CLAUDE.md` with the approved
  behavior and verification evidence.

## Acceptance

- Astro `check` and production `build` pass with no errors or warnings.
- 320, 375, 414, 768, 1280, and 1440 widths have zero horizontal overflow.
- Desktop scroll activates Galaxy, Map, System, and Study in order.
- Compact views show four correctly paired images without sticky overlap.
- Reduced motion shows the complete static sequence.
- Light and dark modes preserve screenshot contrast and token semantics.
- Keyboard navigation, copy controls, search, theme toggle, and anchors remain
  usable.
- Browser console has no errors.
- Hallmark 58/58 and both review axes report no unresolved findings.
- Graphify refresh succeeds and one scoped docs-site query resolves.
