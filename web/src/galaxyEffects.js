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

export function attachBloom(renderer) {
  const composer = renderer.postProcessingComposer();
  // UnrealBloomPass's constructor resolution is overwritten on the first
  // composer resize, so the cap that actually survives is the pixel ratio:
  // at 1 the bloom mip chain stays in CSS pixels even on a retina display.
  composer.setPixelRatio(1);
  const pass = new UnrealBloomPass(
    new THREE.Vector2(composer._width ?? 1, composer._height ?? 1),
    BLOOM_STRENGTH,
    BLOOM_RADIUS,
    BLOOM_THRESHOLD,
  );
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
