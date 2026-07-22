# Cinematic public-site refinement

## Purpose

Turn a broad request for a more impressive Codemble website into a scoped,
product-truthful landing-page improvement that can be designed, implemented,
verified, reviewed, and published without weakening the learning contract.

## Trigger

An owner request to redesign, enhance, or visually elevate the public Codemble
website.

## Inputs

- The owner’s desired audience, primary action, and tone.
- `CLAUDE.md`, including the Correctness Contract, Non-Goals, Current State,
  and Decision Log.
- `docs-site/design.md` and `docs-site/src/styles/tokens.css`.
- The current rendered landing page at desktop and compact widths.
- Real product screenshots under `docs-site/public/shots/`.

## Workflow

1. Read the operating guide and locked design system in full.
2. Confirm one experience brief: audience, primary action, tone, and whether
   the landing page or the whole documentation surface is in scope.
3. Inspect the current rendered page before proposing effects. Identify the
   first point where the experience stops communicating the product clearly.
4. Write a file-level plan. Name every file expected to be created, modified,
   or deleted; deletion requires explicit owner approval.
5. Keep one memorable visual signature. Motion, perspective, screenshots, and
   SVGs must explain a real product transition rather than decorate empty space.
6. Implement within the existing Astro/Starlight and generated-art boundaries.
   Preserve `/Codemble`, the token order, accent semantics, and truthful copy.
7. Verify the production build and the real browser surface at 320, 375, 414,
   768, 1280, and 1440 CSS pixels, plus dark, light, keyboard, and reduced-motion
   states. Check horizontal overflow, console errors, image loading, and touch
   target size.
8. Run Hallmark’s final slop test and the repository’s two-axis code review.
   Fix every actionable finding and rerun the affected gates.
9. Refresh Graphify and verify one scoped query. Treat a failed refresh as a
   publish blocker.
10. Commit only the scoped files. Merge into `main`, push `main`, and verify
    local `main`, `origin/main`, CI, Pages, and the public URL before closing.

## Checkpoint

Push the human checkpoint immediately after the rendered baseline and proposed
experience brief. Present one recommendation and one confirm-or-redirect
question. After approval, complete implementation and verification before
asking for attention again.

The approved brief for this run is:

- Audience: early/intermediate developers trying to understand AI-assisted code.
- Primary action: **Chart your project**.
- Tone: cinematic, premium Edo star atlas; atmospheric but precise.
- Scope: the public landing page is cinematic; documentation remains restrained.
- Publication: commit, merge to `main`, and push after the full gate passes.

## Acceptance contract

- The first viewport remains legible and action-led without relying on motion.
- The product demonstration uses real Codemble screenshots and never redraws
  fake browser, terminal, phone, or IDE chrome.
- Desktop motion communicates Galaxy → Map → System → Study semantic depth.
- Compact layouts pair every screenshot with its copy and use no sticky or 3D
  choreography.
- Reduced motion shows the complete static story with no spatial transitions.
- No feature, metric, testimonial, parser fact, or capability is invented.
- No route, documentation page, app behavior, parser contract, or release
  artifact changes.
- Astro check/build, responsive browser QA, Hallmark, code review, and Graphify
  all pass before publication.

## Brief

At the final publication checkpoint, report only: what changed, why it is
truthful, the verification evidence, the commit merged to `main`, and the live
surface status. Link to the implementation spec and important files; do not
paste raw build logs.
