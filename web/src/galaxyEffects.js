import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { CopyShader } from "three/addons/shaders/CopyShader.js";
import * as THREE from "three";

// 3d-force-graph builds the composer already seeded with a RenderPass and always
// renders through it, so bloom is one addPass. Verified against 3d-force-graph
// 1.80.0 / three 0.185.1.
const BLOOM_STRENGTH = 0.9;
const BLOOM_RADIUS = 0.45;
// Tuned so a lit amber star blooms hard and the unlit ramp barely does: the
// threshold sits above --cm-ink-2's luminance and below --cm-star-high's.
const BLOOM_THRESHOLD = 0.52;
// Bloom is the expensive pass: its mip chain starts at half the buffer and runs
// a separable blur over every level, so on a 2x display it costs ~4x what it
// costs at 1x. Capping it via `composer.setPixelRatio(1)` -- what this used to
// do -- works, but EffectComposer.setSize multiplies that ratio into
// renderTarget1/2 AND every pass (EffectComposer.js:152,296,317-333), including
// the RenderPass that draws the scene and the copy that presents it. The whole
// galaxy rendered at 1x and upscaled: soft at every zoom level on retina.
// Clamp the bloom pass's own resolution instead. A blur is the one thing in the
// chain that cannot show the difference, and its screen-space spread is
// resolution-independent (invSize is derived from the mip size).
const BLOOM_MAX_DIMENSION = 1600;

/** The blur's own resolution, clamped; the scene keeps the size it was given. */
function cappedBloomSize(width, height) {
  const scale = Math.min(1, BLOOM_MAX_DIMENSION / Math.max(width, height, 1));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

/**
 * Add the bloom pass, and size the chain from the element being drawn into.
 *
 * `size` is not optional politeness. `composer._width`/`_height` hold whatever
 * the library last applied, and on a re-mount into a host of the SAME size it
 * applies nothing: the width/height props are diffed, an unchanged prop is
 * skipped, and `composer.setSize` is the only thing that sizes the pass chain.
 * The bloom pass then keeps the 1x1 it was constructed with -- and because the
 * composer PRESENTS through that chain, the whole galaxy arrives through a
 * one-pixel buffer. Correctly sized canvas, no console error, nothing drawn.
 *
 * That is the blank stage after switching Diagram -> Galaxy. It looked
 * engine-specific for a while, and the reason is worth keeping: it needs the
 * re-mount to land on an identical size, so a fresh page load differs from the
 * library's defaults, gets a real resize for free, and never shows it. A driver
 * that always starts from a new page therefore cannot reproduce it, which is
 * exactly what happened. Sizing here removes the dependence on a resize
 * arriving at all.
 */
export function attachBloom(renderer, size) {
  const composer = renderer.postProcessingComposer();
  const width = Math.max(1, Math.round(size?.width || composer._width || 1));
  const height = Math.max(1, Math.round(size?.height || composer._height || 1));
  // Capped at construction as well as on resize: UnrealBloomPass allocates its
  // whole mip chain from the resolution it is handed, and the wrapper below
  // cannot exist until after that call -- so handing it the raw host size would
  // allocate the full-resolution chain and only shrink it on the first resize,
  // which is the retina cost this cap exists to avoid.
  const capped = cappedBloomSize(width, height);
  const pass = new UnrealBloomPass(
    new THREE.Vector2(capped.width, capped.height),
    BLOOM_STRENGTH,
    BLOOM_RADIUS,
    BLOOM_THRESHOLD,
  );
  // Installed before addPass, which sizes the pass immediately on insert.
  const sizePass = pass.setSize.bind(pass);
  pass.setSize = (nextWidth, nextHeight) => {
    const bloom = cappedBloomSize(nextWidth, nextHeight);
    sizePass(bloom.width, bloom.height);
  };
  composer.addPass(pass);
  // Whichever pass renders last re-applies the renderer's sRGB output encode
  // on top of a buffer that 3d-force-graph's own RenderPass already wrote in
  // display-encoded form (verified empirically: swapping in three.js's own
  // recommended `OutputPass` -- or just leaving UnrealBloomPass last, which
  // does the same encode internally when it is the final pass -- doubles the
  // gamma curve on every pixel; measured empty-background luma rising from
  // ~11 to ~59 with NO dependence on bloom strength/threshold/radius, which
  // is what gave away that this was an encoding bug and not a content-driven
  // glow). A plain copy as the final pass -- the same primitive EffectComposer
  // itself uses for its internal buffer swaps -- writes the already-encoded
  // buffer through untouched, so the screen gets exactly one encode.
  const passthrough = new ShaderPass(CopyShader);
  composer.addPass(passthrough);
  // Unconditional and idempotent, unlike the width/height props: this is what
  // guarantees the chain is sized whether or not a resize ever arrives.
  composer.setSize(width, height);
  return {
    pass,
    composer,
    dispose() {
      composer.removePass(passthrough);
      passthrough.dispose();
      composer.removePass(pass);
      pass.dispose();
    },
  };
}

const DAWN_DURATION = 1200;

export function prefersReducedMotion() {
  return globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

// The one bold moment in the app: amber washes across the lit system's fog and
// its star flares. Reduced motion gets the finished lit state instantly -- not a
// faster animation, no animation at all.
export function runNebulaDawn({ scene, regionId, palette }) {
  // Nothing to restore in either case: the lit colour the dawn celebrates is
  // already committed to the graph, so the finished state is what is on screen.
  if (prefersReducedMotion()) return () => {};
  const target = scene.getObjectByName(`codemble-system-${regionId}`);
  if (!target) return () => {};
  const sprites = [];
  target.traverse((child) => {
    // The full scale VECTOR, never scale.x alone: a name plate is non-uniform
    // (x = aspect * y), and a scalar snapshot restored through setScalar
    // squashed the lit system's plate square and left it that way until the
    // next level change rebuilt the marker.
    if (child.isSprite) sprites.push([child, child.material.opacity, child.scale.clone()]);
  });
  const amber = new THREE.Color(palette.star);
  const originals = sprites.map(([sprite]) => sprite.material.color.clone());

  let frame = 0;
  const startedAt = performance.now();
  const step = () => {
    const progress = Math.min(1, (performance.now() - startedAt) / DAWN_DURATION);
    // Ease out: the flare arrives fast and settles, like a light coming up.
    const eased = 1 - (1 - progress) ** 3;
    const wash = Math.sin(progress * Math.PI);
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]).lerp(amber, wash * 0.85);
      sprite.material.opacity = baseOpacity + wash * 0.5;
      sprite.scale.copy(baseScale).multiplyScalar(1 + wash * 0.45);
    });
    if (progress < 1) {
      frame = requestAnimationFrame(step);
      return;
    }
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]);
      sprite.material.opacity = baseOpacity;
      sprite.scale.copy(baseScale);
    });
  };
  frame = requestAnimationFrame(step);
  return () => {
    cancelAnimationFrame(frame);
    sprites.forEach(([sprite, baseOpacity, baseScale], index) => {
      sprite.material.color.copy(originals[index]);
      sprite.material.opacity = baseOpacity;
      sprite.scale.copy(baseScale);
    });
  };
}
