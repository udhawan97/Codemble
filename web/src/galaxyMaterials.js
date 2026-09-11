import * as THREE from "three";

import { configureNamePlate } from "./nameAtlas.js";

// Every texture here is drawn on a 2D canvas at runtime: no image assets ship,
// and the same code always produces the same bytes. Textures and materials are
// built once and shared, because these accessors run per node on every graph
// update and a texture per node would melt a mid-range laptop.

const HALO_TEXTURE_SIZE = 128;
const NEBULA_TEXTURE_SIZE = 256;
const STARBURST_TEXTURE_SIZE = 256;
const NEBULA_VARIANTS = 4;
const GUIDE_LABEL_HEIGHT = 0.026;

function radialTexture(size, stops) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const gradient = context.createRadialGradient(
    size / 2, size / 2, 0,
    size / 2, size / 2, size / 2,
  );
  for (const [offset, alpha] of stops) {
    gradient.addColorStop(offset, `rgba(255, 255, 255, ${alpha})`);
  }
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function navigatorTexture(size) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const center = size / 2;
  context.strokeStyle = "rgba(255, 255, 255, 0.96)";
  context.lineCap = "round";
  context.lineWidth = size * 0.026;
  for (let quadrant = 0; quadrant < 4; quadrant += 1) {
    const start = quadrant * Math.PI / 2 + 0.18;
    context.beginPath();
    context.arc(center, center, size * 0.39, start, start + Math.PI / 2 - 0.36);
    context.stroke();
  }
  context.globalAlpha = 0.72;
  context.lineWidth = size * 0.012;
  context.beginPath();
  context.arc(center, center, size * 0.29, 0, Math.PI * 2);
  context.stroke();
  context.globalAlpha = 1;
  context.lineWidth = size * 0.022;
  for (let tick = 0; tick < 8; tick += 1) {
    const angle = tick * Math.PI / 4;
    const inner = tick % 2 === 0 ? size * 0.34 : size * 0.365;
    const outer = size * 0.46;
    context.beginPath();
    context.moveTo(center + Math.cos(angle) * inner, center + Math.sin(angle) * inner);
    context.lineTo(center + Math.cos(angle) * outer, center + Math.sin(angle) * outer);
    context.stroke();
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function organicNebulaTexture(size, variant) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const random = mulberry32(fnv1a(`codemble-nebula:${variant}`));
  context.clearRect(0, 0, size, size);
  context.globalCompositeOperation = "lighter";

  // Four shared, seeded silhouettes break the UI-circle repetition without a
  // texture per system. Language still owns colour; this owns only cloud shape.
  for (let lobe = 0; lobe < 8; lobe += 1) {
    const angle = random() * Math.PI * 2;
    const reach = size * (0.04 + random() * 0.22);
    const x = size / 2 + Math.cos(angle) * reach;
    const y = size / 2 + Math.sin(angle) * reach * 0.62;
    const radius = size * (0.18 + random() * 0.17);
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, `rgba(255, 255, 255, ${0.11 + random() * 0.1})`);
    gradient.addColorStop(0.46, "rgba(255, 255, 255, 0.075)");
    gradient.addColorStop(1, "rgba(255, 255, 255, 0)");
    context.fillStyle = gradient;
    context.beginPath();
    context.ellipse(
      x,
      y,
      radius * (0.9 + random() * 0.5),
      radius * (0.46 + random() * 0.34),
      angle + random() * 0.5,
      0,
      Math.PI * 2,
    );
    context.fill();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function starburstTexture(size) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const center = size / 2;
  context.translate(center, center);
  context.globalCompositeOperation = "lighter";
  context.lineCap = "round";
  for (let ray = 0; ray < 8; ray += 1) {
    const angle = ray * Math.PI / 4;
    const length = ray % 2 === 0 ? size * 0.46 : size * 0.3;
    const gradient = context.createLinearGradient(0, 0, length, 0);
    gradient.addColorStop(0, "rgba(255, 255, 255, 0.78)");
    gradient.addColorStop(0.28, "rgba(255, 255, 255, 0.24)");
    gradient.addColorStop(1, "rgba(255, 255, 255, 0)");
    context.save();
    context.rotate(angle);
    context.strokeStyle = gradient;
    context.lineWidth = ray % 2 === 0 ? size * 0.018 : size * 0.01;
    context.beginPath();
    context.moveTo(size * 0.025, 0);
    context.lineTo(length, 0);
    context.stroke();
    context.restore();
  }
  const core = context.createRadialGradient(0, 0, 0, 0, 0, size * 0.19);
  core.addColorStop(0, "rgba(255, 255, 255, 0.94)");
  core.addColorStop(0.22, "rgba(255, 255, 255, 0.48)");
  core.addColorStop(1, "rgba(255, 255, 255, 0)");
  context.fillStyle = core;
  context.beginPath();
  context.arc(0, 0, size * 0.19, 0, Math.PI * 2);
  context.fill();
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function createDressing(palette) {
  // three-forcegraph frees every node object it removes, and its _deallocate
  // disposes `material.map` and `material` recursively (three-forcegraph.mjs:
  // 218-243). These resources are shared by every sprite in the scene, so one
  // galaxy->system transition would free textures and materials the next scene
  // still draws with, forcing a full re-upload each time. Ownership stays here:
  // the borrower's dispose() is a no-op and dispose() below frees them for real.
  const releases = [];
  function owned(resource) {
    const release = resource.dispose.bind(resource);
    resource.dispose = () => {};
    releases.push(release);
    return resource;
  }

  const haloTexture = owned(radialTexture(HALO_TEXTURE_SIZE, [
    [0, 0.85], [0.25, 0.42], [0.6, 0.1], [1, 0],
  ]));
  const reticleTexture = owned(navigatorTexture(HALO_TEXTURE_SIZE));
  const starburstMap = owned(starburstTexture(STARBURST_TEXTURE_SIZE));
  const haloMaterials = new Map();
  const nebulaTextures = new Map();
  const nebulaMaterials = new Map();
  const reticleMaterial = owned(new THREE.SpriteMaterial({
    map: reticleTexture,
    color: new THREE.Color(palette.orbit),
    transparent: true,
    depthWrite: false,
    depthTest: false,
    sizeAttenuation: false,
    opacity: 0.94,
  }));
  const reticleGlowMaterial = owned(new THREE.SpriteMaterial({
    map: haloTexture,
    color: new THREE.Color(palette.orbit),
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
    depthTest: false,
    sizeAttenuation: false,
    opacity: 0.18,
  }));
  const starburstMaterial = owned(new THREE.SpriteMaterial({
    map: starburstMap,
    color: new THREE.Color(palette.star),
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
    depthTest: false,
    opacity: 0.72,
  }));
  // One amber mote material shared by every spark of every dawn. Built lazily,
  // because most sessions never light a region at all.
  let sparkMaterial = null;
  // One texture per distinct label string, not per node: a project repeats
  // basenames (index.ts, __init__.py) constantly, and re-rasterising each of
  // 169 names on every graph refresh is the sort of thing that turns a
  // 60fps sky into a slideshow.
  const labelMaterials = new Map();

  function labelMaterial(text) {
    if (!labelMaterials.has(text)) {
      labelMaterials.set(text, owned(makeLabelMaterial(text, palette)));
    }
    return labelMaterials.get(text);
  }

  function haloMaterial(color) {
    if (!haloMaterials.has(color)) {
      haloMaterials.set(
        color,
        owned(new THREE.SpriteMaterial({
          map: haloTexture,
          // The white texture is multiplied by the node's own colour, so an
          // unlit node's halo can never be brighter than a lit one's.
          color: new THREE.Color(color).multiply(new THREE.Color(palette.starHalo)),
          blending: THREE.AdditiveBlending,
          transparent: true,
          depthWrite: false,
          opacity: 0.6,
        })),
      );
    }
    return haloMaterials.get(color);
  }

  return {
    // A billboard sprite: no geometry cost, always faces the camera.
    halo(node, radius) {
      const sprite = new THREE.Sprite(haloMaterial(node.color));
      sprite.scale.setScalar(radius * 6.5);
      sprite.renderOrder = -1;
      return sprite;
    },
    nebula(tint, radius, seedText = tint) {
      const variant = fnv1a(String(seedText)) % NEBULA_VARIANTS;
      const key = `${tint}:${variant}`;
      if (!nebulaTextures.has(variant)) {
        nebulaTextures.set(
          variant,
          owned(organicNebulaTexture(NEBULA_TEXTURE_SIZE, variant)),
        );
      }
      if (!nebulaMaterials.has(key)) {
        nebulaMaterials.set(
          key,
          owned(new THREE.SpriteMaterial({
            map: nebulaTextures.get(variant),
            color: new THREE.Color(tint),
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false,
            // Alpha lives here, not in the token: the token has to survive a
            // 4.5:1 legend check, the fog has to stay a whisper.
            opacity: 0.2,
            rotation: variant * 0.73,
          })),
        );
      }
      const sprite = new THREE.Sprite(nebulaMaterials.get(key));
      const breadth = 1.05 + variant * 0.08;
      const depth = 0.66 + ((variant + 1) % NEBULA_VARIANTS) * 0.06;
      sprite.scale.set(radius * breadth, radius * depth, 1);
      sprite.renderOrder = -2;
      return sprite;
    },
    starburst(radius) {
      const sprite = new THREE.Sprite(starburstMaterial);
      sprite.scale.setScalar(radius * 13.5);
      sprite.renderOrder = 1;
      sprite.userData.codembleUnderstoodBurst = true;
      return sprite;
    },
    /**
     * The amber mote the dawn runs along a proven route.
     *
     * Shares one owned material with every other spark, so a dawn that lights
     * three routes at once still uploads nothing: the sequence only adds and
     * removes sprites, and never disposes anything this module lends it.
     */
    spark() {
      if (!sparkMaterial) {
        sparkMaterial = owned(new THREE.SpriteMaterial({
          map: haloTexture,
          color: new THREE.Color(palette.star),
          blending: THREE.AdditiveBlending,
          transparent: true,
          depthWrite: false,
          opacity: 0,
        }));
      }
      const sprite = new THREE.Sprite(sparkMaterial);
      sprite.renderOrder = 2;
      return sprite;
    },
    reticle(radius = 1) {
      const group = new THREE.Group();
      const glow = new THREE.Sprite(reticleGlowMaterial);
      glow.scale.setScalar(0.23);
      glow.renderOrder = 2;
      const sight = new THREE.Sprite(reticleMaterial);
      sight.scale.setScalar(0.16);
      sight.renderOrder = 3;
      group.add(glow, sight);
      group.scale.setScalar(radius);
      group.userData.codembleNavigator = true;
      return group;
    },
    /**
     * A name plate that keeps a constant on-screen size.
     *
     * `sizeAttenuation: false` is the whole point: a perspective-scaled label
     * is unreadable at the far camera clamp and cartoonish at the near one,
     * and the label has to stay legible across the entire orbit range.
     * Starts hidden -- the declutter pass decides which plates earn a slot.
     */
    label(text, radius) {
      const material = labelMaterial(text);
      const sprite = new THREE.Sprite(material);
      const aspect = material.userData.aspect ?? 4;
      configureNamePlate(sprite, { radius, aspect });
      sprite.renderOrder = 4;
      return sprite;
    },
    /**
     * A persistent short plate for a backend-owned orbit layer.
     *
     * Unlike node name plates, this never enters Name Atlas decluttering:
     * there is one label per semantic layer and hiding one would erase the
     * meaning of the guide it names.
     */
    guideLabel(text) {
      const material = labelMaterial(text);
      const sprite = new THREE.Sprite(material);
      const aspect = material.userData.aspect ?? 4;
      sprite.scale.set(GUIDE_LABEL_HEIGHT * aspect, GUIDE_LABEL_HEIGHT, 1);
      sprite.renderOrder = 2;
      return sprite;
    },
    dispose() {
      // The only real free: every shared texture and material registered above,
      // in creation order.
      for (const release of releases) release();
      releases.length = 0;
      haloMaterials.clear();
      nebulaTextures.clear();
      nebulaMaterials.clear();
      sparkMaterial = null;
      labelMaterials.clear();
    },
  };
}

const LABEL_FONT_PX = 34;
const LABEL_PADDING_PX = 12;

function makeLabelMaterial(text, palette) {
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  const font = `${LABEL_FONT_PX}px "JetBrains Mono", ui-monospace, monospace`;
  context.font = font;
  const width = Math.ceil(context.measureText(text).width) + LABEL_PADDING_PX * 2;
  const height = LABEL_FONT_PX + LABEL_PADDING_PX * 2;
  canvas.width = width;
  canvas.height = height;
  // Resizing the canvas resets every context property, so the font must be set
  // again here -- measuring with one font and drawing with another produced
  // clipped plates.
  context.font = font;
  context.textBaseline = "middle";
  context.textAlign = "center";
  // A dark plate behind the text: a name floating on a starfield loses its
  // contrast the moment it crosses a bright nebula or a lit star's halo.
  context.fillStyle = palette.labelPlate;
  roundedRect(context, 0, 0, width, height, 8);
  context.fill();
  context.fillStyle = palette.labelInk;
  context.fillText(text, width / 2, height / 2 + 1);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
    // Depth test off so a plate is never half-swallowed by the star it names.
    depthTest: false,
    sizeAttenuation: false,
  });
  material.userData.aspect = width / height;
  const disposeMaterial = material.dispose.bind(material);
  material.dispose = () => {
    texture.dispose();
    disposeMaterial();
  };
  return material;
}

function roundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}

// FNV-1a over the project's own file hashes. Same code -> same seed -> same sky.
export function seedFromHashes(fileHashes) {
  const entries = Object.entries(fileHashes ?? {}).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  return entries.map(([file, hash]) => `${file}:${hash}`).join("|");
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return function next() {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = Math.imul(state ^ (state >>> 15), 1 | state);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function fnv1a(text) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export function skySeed(seedText) {
  return fnv1a(String(seedText ?? "")) / 4294967296;
}

function createStarLayer(seedText, palette, count, radius, { near = false } = {}) {
  const random = mulberry32(fnv1a(seedText));
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const cool = new THREE.Color(palette.starCool ?? palette.nodeDim);
  const pale = new THREE.Color(palette.starPale ?? palette.nodeBright);
  const tint = new THREE.Color();
  for (let index = 0; index < count; index += 1) {
    // Uniform on a sphere shell, from the seeded stream only -- never
    // Math.random: "same code -> same sky" is an acceptance criterion.
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    const distance = radius * (0.68 + random() * 0.32);
    // Two thirds of the dust is flattened toward the galactic plane. A uniform
    // shell reads as a featureless dome from every angle; a band gives the
    // emptiness a direction, which is what makes it read as distance rather
    // than as absence. The layout itself is a disc, so the band agrees with it.
    const flatten = index % 3 === 0 ? 1 : near ? 0.3 : 0.18;
    positions[index * 3] = distance * Math.sin(phi) * Math.cos(theta);
    positions[index * 3 + 1] = distance * Math.cos(phi) * flatten;
    positions[index * 3 + 2] = distance * Math.sin(phi) * Math.sin(theta);
    // Temperature runs blue to white and never warm: a warm tint at this
    // brightness sits in the kohaku band, and decoration may not borrow the
    // one hue that means understanding.
    tint.copy(cool).lerp(pale, random());
    colors[index * 3] = tint.r;
    colors[index * 3 + 1] = tint.g;
    colors[index * 3 + 2] = tint.b;
    if (near) {
      sizes[index] = random() < 0.11 ? 8.5 + random() * 7.5 : 3.8 + random() * 4.6;
    } else {
      sizes[index] = random() < 0.05 ? 7 + random() * 5 : 2.4 + random() * 3.2;
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
  const points = new THREE.Points(geometry, new THREE.ShaderMaterial({
    vertexShader: STARFIELD_VERTEX,
    fragmentShader: STARFIELD_FRAGMENT,
    uniforms: {
      uPointScale: { value: near ? 1.22 : 0.88 },
      uOpacity: { value: near ? 0.78 : 0.62 },
    },
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  }));
  points.name = near ? "codemble-starfield-near" : "codemble-starfield-far";
  return points;
}

export function createStarfield(seedText, palette, count = 3200, radius = 1600) {
  const total = Math.max(0, Math.floor(count));
  const farCount = total > 0 ? Math.max(1, Math.floor(total * 0.82)) : 0;
  const nearCount = total - farCount;
  const group = new THREE.Group();
  group.name = "codemble-starfield";
  if (farCount) group.add(createStarLayer(`${seedText}:far`, palette, farCount, radius));
  if (nearCount) {
    group.add(
      createStarLayer(`${seedText}:near`, palette, nearCount, radius * 0.62, { near: true }),
    );
  }
  group.rotation.y = skySeed(`${seedText}:starfield-orientation`) * Math.PI * 2;
  group.userData.codembleStarCount = total;
  return group;
}

const STARFIELD_VERTEX = `
attribute float size;
uniform float uPointScale;
varying vec3 vStarColor;
void main(){
  vStarColor = color;
  vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
  float distanceScale = 430.0 / max(320.0, -viewPosition.z);
  gl_PointSize = clamp(size * uPointScale * distanceScale, 1.0, 5.2);
  gl_Position = projectionMatrix * viewPosition;
}
`;

const STARFIELD_FRAGMENT = `
uniform float uOpacity;
varying vec3 vStarColor;
void main(){
  float distanceFromCore = length(gl_PointCoord - vec2(0.5));
  if (distanceFromCore > 0.5) discard;
  float core = 1.0 - smoothstep(0.0, 0.16, distanceFromCore);
  float halo = 1.0 - smoothstep(0.06, 0.5, distanceFromCore);
  float alpha = min(1.0, core * 0.72 + halo * 0.42);
  gl_FragColor = vec4(vStarColor, alpha * uOpacity);
}
`;

export const STARFIELD_SHADER_SOURCE = Object.freeze({
  vertex: STARFIELD_VERTEX,
  fragment: STARFIELD_FRAGMENT,
});

const GALACTIC_DISC_VERTEX = `
varying vec2 vUv;
void main(){
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const GALACTIC_DISC_FRAGMENT = `
uniform vec3 uCore;
uniform vec3 uEdge;
uniform float uSeed;
varying vec2 vUv;

float cbDiscHash(vec2 p){
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32 + uSeed * 17.0);
  return fract(p.x * p.y);
}

float cbDiscNoise(vec2 p){
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(cbDiscHash(i), cbDiscHash(i + vec2(1.0, 0.0)), f.x),
    mix(cbDiscHash(i + vec2(0.0, 1.0)), cbDiscHash(i + vec2(1.0, 1.0)), f.x),
    f.y
  );
}

void main(){
  vec2 point = (vUv - 0.5) * 2.0;
  float radius = length(point);
  if (radius > 1.0) discard;
  float angle = atan(point.y, point.x);
  float turbulence = cbDiscNoise(point * 5.4 + uSeed * 5.0);
  float fineDust = cbDiscNoise(point * 42.0 + turbulence * 3.0);
  float spiral = 0.5 + 0.5 * cos(angle * 3.0 - log(radius + 0.12) * 9.0 + turbulence * 3.4 + uSeed * 6.28318);
  float filaments = pow(smoothstep(0.3, 0.94, spiral), 2.0);
  float darkLane = smoothstep(0.32, 0.52, fineDust + turbulence * 0.16);
  float envelope = (1.0 - smoothstep(0.64, 1.0, radius));
  float core = exp(-radius * 8.5);
  float alpha = envelope * (0.01 + filaments * 0.17) * darkLane;
  alpha += core * 0.22;
  vec3 color = mix(uEdge, uCore, clamp(core * 1.4 + fineDust * 0.34, 0.0, 1.0));
  gl_FragColor = vec4(color, alpha);
}
`;

export const GALACTIC_DISC_SHADER_SOURCE = Object.freeze({
  vertex: GALACTIC_DISC_VERTEX,
  fragment: GALACTIC_DISC_FRAGMENT,
});

function createSpiralDust(seedText, palette, count, radius) {
  const random = mulberry32(fnv1a(`${seedText}:spiral-dust`));
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const edge = new THREE.Color(palette.starCool ?? palette.nodeDim);
  const core = new THREE.Color(palette.starPale ?? palette.nodeBright);
  const tint = new THREE.Color();
  for (let index = 0; index < count; index += 1) {
    const arm = index % 4;
    const reach = 0.08 + Math.sqrt(random()) * 0.92;
    const angle =
      arm * Math.PI / 2 +
      reach * 4.6 +
      skySeed(seedText) * Math.PI * 2 +
      (random() - 0.5) * (0.2 + reach * 0.36);
    const distance = reach * radius;
    positions[index * 3] = Math.cos(angle) * distance;
    positions[index * 3 + 1] = -34 + (random() - 0.5) * (12 + reach * 52);
    positions[index * 3 + 2] = Math.sin(angle) * distance;
    tint.copy(edge).lerp(core, (1 - reach) * 0.58 + random() * 0.16);
    colors[index * 3] = tint.r;
    colors[index * 3 + 1] = tint.g;
    colors[index * 3 + 2] = tint.b;
    sizes[index] = 2 + random() * 3.8;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
  const material = new THREE.ShaderMaterial({
    vertexShader: STARFIELD_VERTEX,
    fragmentShader: STARFIELD_FRAGMENT,
    uniforms: {
      uPointScale: { value: 0.82 },
      uOpacity: { value: 0.42 },
    },
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const dust = new THREE.Points(geometry, material);
  dust.name = "codemble-spiral-dust";
  dust.renderOrder = -6;
  return dust;
}

/**
 * The galactic plane: one very dim, very large additive disc.
 *
 * The complaint that opened this work was that the galaxy read as an empty
 * void. Lifting the background alone would have cost every star its contrast,
 * so the ambient comes from here instead -- light that has a shape and a
 * direction, sitting far behind everything and writing no depth, so it can
 * never occlude a star or a route.
 *
 * It encodes nothing. That is deliberate and is what makes it safe: no fact
 * about the learner's code is readable from it, so it cannot mislead.
 */
export function createGalacticGlow(seedText, palette, radius = 1050) {
  const group = new THREE.Group();
  group.name = "codemble-galactic-glow";
  const disc = new THREE.Mesh(
    new THREE.PlaneGeometry(radius * 2, radius * 2),
    new THREE.ShaderMaterial({
      vertexShader: GALACTIC_DISC_VERTEX,
      fragmentShader: GALACTIC_DISC_FRAGMENT,
      uniforms: {
        uCore: { value: new THREE.Color(palette.starPale ?? palette.nodeBright) },
        uEdge: { value: new THREE.Color(palette.skyGlow ?? palette.ground) },
        uSeed: { value: skySeed(`${seedText}:galactic-disc`) },
      },
      transparent: true,
      depthWrite: false,
      depthTest: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    }),
  );
  disc.rotation.x = -Math.PI / 2;
  disc.position.y = -58;
  disc.renderOrder = -8;
  disc.name = "codemble-galactic-disc";
  const coreMaterial = new THREE.SpriteMaterial({
    map: radialTexture(256, [
      [0, 0.72],
      [0.24, 0.3],
      [0.68, 0.045],
      [1, 0],
    ]),
    color: new THREE.Color(palette.starCool ?? palette.skyGlow ?? palette.ground),
    transparent: true,
    opacity: 0.34,
    depthWrite: false,
    depthTest: false,
    blending: THREE.AdditiveBlending,
  });
  const core = new THREE.Sprite(coreMaterial);
  core.scale.set(radius * 0.72, radius * 0.25, 1);
  core.position.y = -24;
  core.renderOrder = -7;
  core.name = "codemble-galactic-core";
  group.rotation.y = skySeed(`${seedText}:galactic-orientation`) * Math.PI * 2;
  group.add(disc, createSpiralDust(seedText, palette, 1200, radius * 0.9), core, createNebulaVault(seedText, palette));
  group.userData.codembleSeed = skySeed(seedText);
  return group;
}

/**
 * A language-tinted light well behind one solar system.
 *
 * The System level previously hid the galactic disc and left the worlds over a
 * nearly uniform navy field. This local aura restores depth without encoding a
 * new fact: its colour repeats the system's parser-owned language tint, and its
 * shape is seeded decorative atmosphere. It never uses amber, which remains
 * reserved for understanding.
 */
export function createSystemAura(seedText, palette, languageColor, radius = 180) {
  const group = new THREE.Group();
  group.name = "codemble-system-aura";
  const tint = new THREE.Color(languageColor ?? palette.skyGlow ?? palette.starCool);
  const hazeTexture = radialTexture(256, [
    [0, 0.58],
    [0.2, 0.31],
    [0.56, 0.085],
    [1, 0],
  ]);
  const hazeMaterial = new THREE.SpriteMaterial({
    map: hazeTexture,
    color: tint,
    transparent: true,
    opacity: 0.34,
    depthWrite: false,
    depthTest: false,
    blending: THREE.AdditiveBlending,
  });
  const haze = new THREE.Sprite(hazeMaterial);
  haze.name = "codemble-system-haze";
  haze.scale.set(radius * 2.4, radius * 1.18, 1);
  haze.position.y = -18;
  haze.renderOrder = -7;

  group.add(haze, createNebulaVault(seedText, palette));
  return group;
}

// A single distant sky shell. The cloud bank has volume cues and dark lanes,
// but no landmarks that could be confused with graph nodes or routes.
const NEBULA_VERTEX = `
varying vec3 vDirection;
void main(){
  vDirection = normalize(position);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;
const NEBULA_FRAGMENT = `
uniform vec3 uCool;
uniform vec3 uPale;
uniform float uSeed;
varying vec3 vDirection;
float nvHash(vec3 p){
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float nvNoise(vec3 p){
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(nvHash(i),nvHash(i+vec3(1,0,0)),f.x),
    mix(nvHash(i+vec3(0,1,0)),nvHash(i+vec3(1,1,0)),f.x),f.y),
    mix(mix(nvHash(i+vec3(0,0,1)),nvHash(i+vec3(1,0,1)),f.x),
    mix(nvHash(i+vec3(0,1,1)),nvHash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
void main(){
  vec3 direction = normalize(vDirection);
  vec3 p = direction * 4.2 + vec3(uSeed * 17.0);
  float coarse = nvNoise(p);
  float grain = nvNoise(p * 3.1 + coarse * 2.3);
  float fine = nvNoise(p * 10.7 + grain);
  float latitude = direction.y + direction.x * 0.28 + direction.z * 0.12;
  float bank = exp(-pow((latitude + (coarse - 0.5) * 0.32) * 3.8, 2.0));
  float lane = smoothstep(0.3, 0.69, grain);
  float filaments = smoothstep(0.32, 0.76, coarse * 0.52 + grain * 0.3 + fine * 0.18);
  float alpha = bank * filaments * lane * 0.34;
  vec3 tint = mix(uCool, uPale, grain * 0.34);
  gl_FragColor = vec4(tint, alpha);
}
`;
export const NEBULA_VAULT_SHADER_SOURCE = Object.freeze({vertex: NEBULA_VERTEX, fragment: NEBULA_FRAGMENT});
function createNebulaVault(seedText, palette) {
  const material = new THREE.ShaderMaterial({
    vertexShader: NEBULA_VERTEX,
    fragmentShader: NEBULA_FRAGMENT,
    uniforms: {
      uCool: {value: new THREE.Color(palette.starCool ?? palette.nodeBright)},
      uPale: {value: new THREE.Color(palette.starPale ?? palette.nodeBright)},
      uSeed: {value: skySeed(`${seedText}:vault`)},
    },
    side: THREE.BackSide,
    depthWrite: false,
    depthTest: false,
    transparent: true,
    blending: THREE.AdditiveBlending,
  });
  const vault = new THREE.Mesh(new THREE.SphereGeometry(6000, 32, 16), material);
  vault.name = "codemble-nebula-vault";
  vault.renderOrder = -20;
  return vault;
}
