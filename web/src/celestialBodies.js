import * as THREE from "three";

/**
 * Procedural celestial bodies for the System level.
 *
 * Authorised by the 2026-07-29 Decision Log entry, which amends the "elaborate
 * game art" Non-Goal. The decorative crust, banding and resting orientation are
 * seeded only by the node's own id, so the same code always yields the same
 * world. The atmosphere repeats the finished community hue but carries no new
 * fact and never borrows understanding-only amber. Every SEMANTIC channel a
 * body wears -- size, brightness, community hue, amber for understood, the
 * class ring, the fracture on an unreadable file -- is still decided by
 * `graphData.js` from parser truth and is passed in here as a finished value.
 *
 * Level-of-detail is the reason this module exists at all rather than being
 * folded into `galaxyMaterials`. A galaxy draws up to ~5,000 systems and cannot
 * afford a four-octave noise loop per fragment, so it keeps the cheap halo
 * sprites. A system draws a few dozen members at close range, which is both
 * where the cost is affordable and where the learner is actually looking.
 */

// Four octaves is the whole procedural budget. Evaluated only on System-level
// bodies; the galaxy tier never compiles this shader.
const NOISE_GLSL = `
float cbHash(vec3 p){
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float cbNoise(vec3 x){
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(cbHash(i), cbHash(i + vec3(1,0,0)), f.x),
        mix(cbHash(i + vec3(0,1,0)), cbHash(i + vec3(1,1,0)), f.x), f.y),
    mix(mix(cbHash(i + vec3(0,0,1)), cbHash(i + vec3(1,0,1)), f.x),
        mix(cbHash(i + vec3(0,1,1)), cbHash(i + vec3(1,1,1)), f.x), f.y),
    f.z);
}
float cbFbm(vec3 p){
  float amplitude = 0.5;
  float total = 0.0;
  for (int octave = 0; octave < 4; octave += 1) {
    total += amplitude * cbNoise(p);
    p *= 2.03;
    amplitude *= 0.5;
  }
  return total;
}
`;

/**
 * A decorative world family for every language Codemble parses.
 *
 * These values change terrain cadence, atmospheric movement and resting spin;
 * they never alter size, position, graph state, or understanding. The mapping
 * is explicit so adding a language cannot silently borrow another language's
 * visual identity.
 */
export const LANGUAGE_WORLD_PROFILES = Object.freeze({
  python: Object.freeze({ terrain: 0.18, bands: 0.24, shimmer: 0.16, spin: 0.82 }),
  javascript: Object.freeze({ terrain: 0.72, bands: 0.12, shimmer: 0.38, spin: 1.28 }),
  typescript: Object.freeze({ terrain: 0.58, bands: 0.42, shimmer: 0.3, spin: 1.04 }),
  go: Object.freeze({ terrain: 0.34, bands: 0.7, shimmer: 0.22, spin: 1.18 }),
  java: Object.freeze({ terrain: 0.8, bands: 0.54, shimmer: 0.14, spin: 0.7 }),
  rust: Object.freeze({ terrain: 0.92, bands: 0.3, shimmer: 0.1, spin: 0.62 }),
  csharp: Object.freeze({ terrain: 0.46, bands: 0.62, shimmer: 0.2, spin: 0.94 }),
  ruby: Object.freeze({ terrain: 0.86, bands: 0.16, shimmer: 0.34, spin: 0.76 }),
  php: Object.freeze({ terrain: 0.26, bands: 0.82, shimmer: 0.26, spin: 1.1 }),
});

const DEFAULT_WORLD_PROFILE = Object.freeze({
  terrain: 0.5,
  bands: 0.5,
  shimmer: 0.18,
  spin: 0.9,
});

export function languageWorldProfile(language) {
  return LANGUAGE_WORLD_PROFILES[language] ?? DEFAULT_WORLD_PROFILE;
}

// Both layers share one sphere buffer. Terrain stays in object space while
// illumination is coherent in view space; derivatives add relief without a
// second geometry or a per-world texture allocation.
const BODY_VERTEX = `
varying vec3 vObject;
varying vec3 vViewNormal;
varying vec3 vViewPosition;
void main(){
  vObject = normalize(position);
  vViewNormal = normalize(normalMatrix * normal);
  vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
  vViewPosition = viewPosition.xyz;
  gl_Position = projectionMatrix * viewPosition;
}
`;

const BODY_FRAGMENT = `
${NOISE_GLSL}
uniform vec3 uBase;
uniform vec3 uAmber;
uniform vec3 uCool;
uniform vec3 uLanguage;
uniform float uSeed;
uniform float uWorld;
uniform float uLit;
uniform float uPartial;
uniform float uClass;
uniform float uDim;
uniform float uTerrain;
uniform float uBands;
uniform float uShimmer;
uniform float uTime;
varying vec3 vObject;
varying vec3 vViewNormal;
varying vec3 vViewPosition;

void main(){
  vec3 sphereNormal = normalize(vViewNormal);
  vec3 eye = normalize(-vViewPosition);
  vec3 key = normalize(vec3(-0.58, 0.48, 0.66));
  vec3 p = vObject * (3.1 + uTerrain) + vec3(uSeed * 47.0);
  float warp = cbNoise(p * 0.64);
  float continent = cbFbm(p + warp * 1.4);
  float detail = cbFbm(p * 5.8 + vec3(4.7, 1.2, 8.3));
  float ridges = 1.0 - abs(detail * 2.0 - 1.0);
  float latitude = abs(vObject.y);
  float strata = 0.5 + 0.5 * sin(vObject.y * (36.0 + uBands * 28.0) + continent * 17.0);
  float land = smoothstep(0.43, 0.49, continent);
  float coast = smoothstep(0.39, 0.44, continent) * (1.0 - land);
  float ice = smoothstep(0.72, 0.9, latitude + (continent - 0.5) * 0.3);
  float relief = continent * 0.65 + ridges * 0.35;
  vec3 pale = mix(uCool, uBase, 0.16);
  vec3 albedo;
  float water = 0.0;
  if (uWorld < 0.5) {
    water = 1.0 - land;
    vec3 ocean = mix(uBase * 0.13, uLanguage * 0.48, coast);
    vec3 terrain = mix(uBase * 0.48, pale * 0.78, smoothstep(0.45, 0.76, continent));
    terrain *= 0.65 + ridges * 0.5;
    albedo = mix(ocean, terrain, land);
    albedo = mix(albedo, pale * 0.92, ice);
    relief *= land;
  } else if (uWorld < 1.5) {
    float fissure = 1.0 - smoothstep(0.012, 0.065, abs(continent - 0.49));
    albedo = mix(pale * (0.6 + detail * 0.52), uLanguage * 0.22, fissure * 0.76);
    relief += fissure * 0.18;
  } else if (uWorld < 2.5) {
    float basin = smoothstep(0.29, 0.55, continent);
    albedo = mix(uBase * 0.26, uBase * 0.95, basin) * (0.56 + ridges * 0.58);
    albedo = mix(albedo, pale * 0.62, pow(ridges, 14.0) * 0.45);
    relief += detail * 0.24;
  } else {
    float storm = cbNoise(p * 1.8 + vec3(strata * 0.8));
    albedo = mix(uBase * 0.3, pale * 0.76, strata * 0.7 + storm * 0.3);
    albedo = mix(albedo, uLanguage * 0.72, smoothstep(0.65, 0.86, storm) * 0.48);
    relief = strata * 0.08;
  }
  // Class strata repeat the already-labelled kind; they never invent a role.
  albedo *= 1.0 - uClass * 0.11 * (1.0 - strata);

  vec3 dpdx = dFdx(vViewPosition);
  vec3 dpdy = dFdy(vViewPosition);
  vec3 tangentX = cross(dpdy, sphereNormal);
  vec3 tangentY = cross(sphereNormal, dpdx);
  float determinant = dot(dpdx, tangentX);
  vec3 gradient = sign(determinant) * (dFdx(relief) * tangentX + dFdy(relief) * tangentY);
  vec3 normal = normalize(max(abs(determinant), 0.000001) * sphereNormal - gradient * 0.24);
  float incidence = dot(sphereNormal, key);
  float daylight = smoothstep(-0.18, 0.24, incidence);
  float diffuse = max(dot(normal, key), 0.0);
  float rim = pow(1.0 - max(dot(sphereNormal, eye), 0.0), 3.4);
  float specular = pow(max(dot(reflect(-key, sphereNormal), eye), 0.0), 70.0);
  vec3 color = albedo * (0.14 + diffuse * 0.94);
  color += pale * specular * water * daylight * 0.46;

  // One cloud field, composited into the surface: a bounded third fBm call.
  // Offset advection moves clouds, never the coastline or parser-owned body.
  vec3 cloudPoint = vObject * 4.7 + vec3(uSeed * 13.0, 0.0, uTime * (0.008 + uShimmer * 0.015));
  float cloudField = cbFbm(cloudPoint + vec3(warp * 1.2));
  float clouds = smoothstep(0.51, 0.67, cloudField);
  clouds *= uWorld < 0.5 ? 0.85 : uWorld < 1.5 ? 0.22 : uWorld < 2.5 ? 0.12 : 0.4;
  color *= 1.0 - clouds * daylight * 0.25;
  color = mix(color, pale * (0.2 + max(incidence, 0.0) * 0.85), clouds);
  color += mix(uBase, uLanguage, 0.58) * rim * (0.1 + daylight * 0.33);

  // Preserve the visible material after earning understanding, and reserve
  // the emissive amber channel exclusively for that parser/check-owned state.
  color = mix(color, uAmber * (0.42 + diffuse * 0.48 + detail * 0.24), uLit * 0.84);
  color += uAmber * rim * uLit * 0.66;
  if (uPartial > 0.5) {
    float fracture = step(0.42, fract((vObject.x + vObject.y * 1.7 + vObject.z * 0.6) * 5.5 + uSeed * 7.0));
    color = mix(color * 0.30, color, fracture);
  }
  color *= 1.0 - uDim * 0.78;
  gl_FragColor = vec4(color, 1.0);
}
`;

const ATMOSPHERE_VERTEX = BODY_VERTEX;
const ATMOSPHERE_FRAGMENT = `
uniform vec3 uBase;
uniform vec3 uCool;
uniform vec3 uLanguage;
uniform float uDim;
varying vec3 vViewNormal;
varying vec3 vViewPosition;
void main(){
  vec3 normal = normalize(vViewNormal);
  vec3 eye = normalize(-vViewPosition);
  float grazing = 1.0 - abs(dot(normal, eye));
  float rim = pow(grazing, 4.0);
  float edge = pow(grazing, 12.0);
  float daylight = smoothstep(-0.4, 0.6, dot(normal, normalize(vec3(-0.58, 0.48, 0.66))));
  vec3 air = mix(uLanguage, uCool, 0.36);
  air = mix(air, uBase, 0.12);
  vec3 color = mix(air, uCool, edge * 0.45);
  float alpha = (rim * 0.38 + edge * 0.23) * (0.18 + daylight * 0.82);
  gl_FragColor = vec4(color, alpha * (1.0 - uDim * 0.78));
}
`;

const SYSTEM_STAR_VERTEX = `
varying vec3 vObject;
varying vec3 vViewNormal;
void main(){
  vObject = normalize(position);
  vViewNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const SYSTEM_STAR_FRAGMENT = `
${NOISE_GLSL}
uniform vec3 uBase;
uniform vec3 uLanguage;
uniform vec3 uCool;
uniform vec3 uAmber;
uniform float uSeed;
uniform float uLit;
uniform float uPartial;
uniform float uDim;
uniform float uTime;
varying vec3 vObject;
varying vec3 vViewNormal;

void main(){
  vec3 point = vObject * 3.4 + vec3(uSeed * 31.0);
  float plasma = cbFbm(point + vec3(uTime * 0.035, -uTime * 0.02, uTime * 0.025));
  float granules = cbNoise(point * 9.0 + vec3(uTime * 0.05));
  float filament = pow(1.0 - abs(plasma * 2.0 - 1.0), 6.0);
  float rim = pow(1.0 - abs(normalize(vViewNormal).z), 2.2);
  vec3 coolCore = mix(uLanguage, uCool, 0.56);
  vec3 color = mix(uBase * 0.68, coolCore * 0.94, 0.38 + plasma * 0.46);
  color *= 0.9 + granules * 0.34;
  color += uLanguage * filament * 0.12;
  color += coolCore * rim * 0.42;
  color = mix(color, uAmber * (0.92 + plasma * 0.55), uLit * 0.86);
  if (uPartial > 0.5) {
    float fracture = step(0.42, fract((vObject.x + vObject.y * 1.7 + vObject.z * 0.6) * 5.5 + uSeed * 7.0));
    color *= 0.25 + fracture * 0.75;
  }
  color = mix(color, color * 0.3, uDim);
  gl_FragColor = vec4(color, 1.0);
}
`;

/**
 * The shader sources, exported so a contract test can read them.
 *
 * A GLSL link failure is invisible from JavaScript: three.js logs
 * "useProgram: program not valid" and draws nothing, which reads as a styling
 * problem rather than a broken build. Making the source inspectable is what
 * lets the suite catch a reserved-word slip before a human has to notice that
 * the planets went missing.
 */
export const BODY_SHADER_SOURCE = Object.freeze({
  vertex: BODY_VERTEX,
  fragment: BODY_FRAGMENT,
});

export const ATMOSPHERE_SHADER_SOURCE = Object.freeze({
  vertex: ATMOSPHERE_VERTEX,
  fragment: ATMOSPHERE_FRAGMENT,
});

export const SYSTEM_STAR_SHADER_SOURCE = Object.freeze({
  vertex: SYSTEM_STAR_VERTEX,
  fragment: SYSTEM_STAR_FRAGMENT,
});

/** FNV-1a over the node id: same code, same world, every run. */
export function worldArchetype(nodeId) {
  return Math.floor(bodySeed(`${nodeId}:world`) * 4);
}

export function bodySeed(nodeId) {
  let hash = 0x811c9dc5;
  const text = String(nodeId ?? "");
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0) / 4294967296;
}

/**
 * One shared sphere geometry for every body.
 *
 * Bodies differ by uniform, never by geometry, so a system of sixty members
 * uploads one buffer rather than sixty.
 */
export function createBodyGeometry(segments = 64) {
  return new THREE.SphereGeometry(1, segments, Math.max(8, segments / 2));
}

/**
 * A body material for one node.
 *
 * Deliberately per-node rather than shared: the surface varies by seed, and a
 * System level holds a few dozen members, so a material each is affordable
 * where it would not be for a 5,000-system galaxy. These are NOT registered as
 * shared resources, so three-forcegraph's deallocator freeing them with their
 * node object is exactly right.
 */
export function createBodyMaterial({ node, color, palette }) {
  const profile = languageWorldProfile(node.language);
  return new THREE.ShaderMaterial({
    vertexShader: BODY_VERTEX,
    fragmentShader: BODY_FRAGMENT,
    uniforms: {
      uBase: { value: new THREE.Color(color) },
      uAmber: { value: new THREE.Color(palette.star) },
      uCool: { value: new THREE.Color(palette.starCool ?? palette.nodeBright) },
      uLanguage: {
        value: new THREE.Color(node.languageColor ?? palette.nebula?.[node.language] ?? color),
      },
      uSeed: { value: bodySeed(node.id) },
      uWorld: { value: worldArchetype(node.id) },
      uLit: { value: node.understood ? 1 : 0 },
      uPartial: { value: node.partial ? 1 : 0 },
      uClass: { value: node.kind === "class" ? 1 : 0 },
      uDim: { value: node.focusDim ? 1 : 0 },
      uTerrain: { value: profile.terrain },
      uBands: { value: profile.bands },
      uShimmer: { value: profile.shimmer },
      uTime: { value: 0 },
    },
  });
}

export function createAtmosphereMaterial({ node, communityColor, languageColor, palette }) {
  return new THREE.ShaderMaterial({
    vertexShader: ATMOSPHERE_VERTEX,
    fragmentShader: ATMOSPHERE_FRAGMENT,
    uniforms: {
      uBase: { value: new THREE.Color(communityColor ?? palette.nodeDim) },
      uCool: { value: new THREE.Color(palette.starCool ?? palette.nodeBright) },
      uLanguage: { value: new THREE.Color(languageColor ?? communityColor ?? palette.nodeDim) },
      uDim: { value: node.focusDim ? 1 : 0 },
    },
    side: THREE.BackSide,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
}

export function createSystemStarMaterial({ node, color, languageColor, palette }) {
  return new THREE.ShaderMaterial({
    vertexShader: SYSTEM_STAR_VERTEX,
    fragmentShader: SYSTEM_STAR_FRAGMENT,
    uniforms: {
      uBase: { value: new THREE.Color(color) },
      uLanguage: { value: new THREE.Color(languageColor ?? color) },
      uCool: { value: new THREE.Color(palette.nodeBright ?? palette.starCool) },
      uAmber: { value: new THREE.Color(palette.star) },
      uSeed: { value: bodySeed(node.id) },
      uLit: { value: node.understood ? 1 : 0 },
      uPartial: { value: node.partial ? 1 : 0 },
      uDim: { value: node.focusDim ? 1 : 0 },
      uTime: { value: 0 },
    },
  });
}

function createSystemStarGlow(color) {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const center = size / 2;
  const gradient = context.createRadialGradient(center, center, 0, center, center, center);
  gradient.addColorStop(0, "rgba(255,255,255,0.92)");
  gradient.addColorStop(0.16, "rgba(255,255,255,0.48)");
  gradient.addColorStop(0.48, "rgba(255,255,255,0.12)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  context.save();
  context.translate(center, center);
  context.globalCompositeOperation = "lighter";
  for (let ray = 0; ray < 4; ray += 1) {
    context.save();
    context.rotate((ray * Math.PI) / 2);
    const flare = context.createLinearGradient(0, 0, center * 0.92, 0);
    flare.addColorStop(0, "rgba(255,255,255,0.62)");
    flare.addColorStop(0.2, "rgba(255,255,255,0.2)");
    flare.addColorStop(1, "rgba(255,255,255,0)");
    context.strokeStyle = flare;
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(center * 0.08, 0);
    context.lineTo(center * 0.92, 0);
    context.stroke();
    context.restore();
  }
  context.restore();
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({
    map,
    color: new THREE.Color(color),
    transparent: true,
    opacity: 0.36,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const dispose = material.dispose.bind(material);
  material.dispose = () => {
    map.dispose();
    dispose();
  };
  const glow = new THREE.Sprite(material);
  glow.name = "codemble-system-star-glow";
  glow.scale.setScalar(4.8);
  glow.renderOrder = 5;
  return glow;
}

export function createSystemStar({ node, color, languageColor, palette, radius, geometry }) {
  const group = new THREE.Group();
  const coreMaterial = createSystemStarMaterial({ node, color, languageColor, palette });
  const core = new THREE.Mesh(geometry, coreMaterial);
  core.name = "codemble-system-star-core";
  core.userData.codembleAnimatedMaterial = coreMaterial;
  const coronaColor = node.understood ? palette.star : languageColor ?? color;
  const coronaMaterial = (strength) => new THREE.ShaderMaterial({
    vertexShader: BODY_VERTEX,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uStrength;
      varying vec3 vViewNormal;
      varying vec3 vViewPosition;
      void main(){
        float facing = abs(dot(normalize(vViewNormal), normalize(-vViewPosition)));
        gl_FragColor = vec4(uColor, pow(facing, 3.0) * uStrength);
      }
    `,
    uniforms: {
      uColor: { value: new THREE.Color(coronaColor) },
      uStrength: { value: strength * (node.focusDim ? 0.25 : 1) },
    },
    transparent: true, depthWrite: false, side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
  });
  const innerCorona = new THREE.Mesh(geometry, coronaMaterial(0.24));
  innerCorona.name = "codemble-system-star-corona";
  innerCorona.scale.setScalar(1.42);
  const outerCorona = new THREE.Mesh(geometry, coronaMaterial(0.11));
  outerCorona.scale.setScalar(1.9);
  group.add(core, innerCorona, outerCorona, createSystemStarGlow(coronaColor));
  group.scale.setScalar(radius * 2.45);
  group.userData.codembleBody = true;
  group.userData.codembleSystemStar = true;
  group.userData.codembleSpinRate = 0.09;
  return group;
}

/**
 * The System-level body for one parser-proven structure.
 *
 * Returns a tiny scene graph sized to the caller's radius: the engraved world
 * plus one low-alpha shell. The caller owns placement; this owns only how the
 * body looks.
 */
export function createBody({
  node,
  color,
  communityColor,
  languageColor,
  palette,
  radius,
  geometry,
}) {
  if (node.isSystemCore) {
    return createSystemStar({ node, color, languageColor, palette, radius, geometry });
  }
  const group = new THREE.Group();
  const profile = languageWorldProfile(node.language);
  const surfaceMaterial = createBodyMaterial({ node, color, palette });
  const surface = new THREE.Mesh(
    geometry,
    surfaceMaterial,
  );
  surface.name = "codemble-world-surface";
  surface.userData.codembleAnimatedMaterial = surfaceMaterial;
  const atmosphere = new THREE.Mesh(
    geometry,
    createAtmosphereMaterial({ node, communityColor, languageColor, palette }),
  );
  atmosphere.name = "codemble-world-atmosphere";
  atmosphere.scale.setScalar(1.085);
  atmosphere.renderOrder = 1;
  group.add(surface, atmosphere);
  group.scale.setScalar(radius * 1.42);
  // A deterministic resting tilt, so a system does not read as a row of
  // identically-oriented balls. Decorative, seeded, and never animated into a
  // different value.
  group.rotation.set(
    bodySeed(`${node.id}:tilt`) * 0.9 - 0.45,
    bodySeed(node.id) * Math.PI * 2,
    bodySeed(`${node.id}:roll`) * 0.18 - 0.09,
  );
  group.userData.codembleBody = true;
  group.userData.codembleSpinRate =
    (0.04 + bodySeed(`${node.id}:spin`) * 0.028) * profile.spin;
  return group;
}

/**
 * Turn every body in the scene slowly.
 *
 * Rotation is the one animated thing here and it moves only a body's own
 * surface -- never its position, which is parser-owned layout. Reduced motion
 * skips this entirely and gets still worlds, not slower ones.
 */
export function createBodySpin(scene, { reducedMotion = false } = {}) {
  if (reducedMotion) return () => {};
  let frame = 0;
  let previous = performance.now();
  const step = () => {
    const now = performance.now();
    const delta = Math.min(0.05, (now - previous) / 1000);
    previous = now;
    scene.traverse((object) => {
      if (object.userData?.codembleBody) {
        object.rotation.y += delta * (object.userData.codembleSpinRate ?? 0.06);
      }
      const animated = object.userData?.codembleAnimatedMaterial;
      if (animated?.uniforms?.uTime) animated.uniforms.uTime.value += delta;
    });
    frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
  return () => cancelAnimationFrame(frame);
}
