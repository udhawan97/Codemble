import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
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
  return {
    pass,
    composer,
    dispose() {
      composer.removePass(pass);
      pass.dispose();
    },
  };
}
