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

const BODY_VERTEX = `
varying vec3 vObject;
varying vec3 vViewNormal;
void main(){
  vObject = normalize(position);
  vViewNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const BODY_FRAGMENT = `
${NOISE_GLSL}
uniform vec3 uBase;
uniform vec3 uAmber;
uniform vec3 uCool;
uniform vec3 uLanguage;
uniform float uSeed;
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

void main(){
  vec3 normal = normalize(vViewNormal);

  // Crust, read in OBJECT space so it turns with the body rather than swimming
  // when the camera orbits.
  //
  // Deliberately NOT named after the GLSL ES reserved word for a texture read:
  // naming a local that makes the whole program fail to link, and three.js
  // reports that only as a console flood of "useProgram: program not valid"
  // while silently drawing nothing -- so the bodies looked like faint specks
  // rather than an error. check_celestial_bodies.mjs scans for the whole class.
  vec3 crustPoint = vObject * 2.6 + vec3(uSeed * 41.0);
  float crust = cbFbm(crustPoint);
  float band = cbFbm(crustPoint * 0.6 + vec3(0.0, uSeed * 9.0, 0.0));
  float latitude = 0.5 + 0.5 * sin(vObject.y * (8.0 + uBands * 12.0) + uSeed * 14.0);
  float continental = smoothstep(0.28, 0.78, cbFbm(crustPoint * (0.72 + uTerrain * 0.58)));
  float current = 0.5 + 0.5 * sin(
    (vObject.x + vObject.z * 1.7) * (9.0 + uTerrain * 7.0) +
    uSeed * 24.0 + uTime * uShimmer
  );
  crust = mix(crust, continental, uTerrain * 0.56);
  crust = mix(crust, latitude, uBands * 0.34);
  crust += (current - 0.5) * uShimmer * 0.18;
  band = mix(band, latitude, uBands * 0.42);
  float ridge = smoothstep(0.34, 0.78, crust);
  float shade = 0.62 + 0.62 * crust;

  // A class is a container of methods -- a parser fact -- so it wears strata.
  // The ring in makeMarker already says "class"; this only gives the same fact
  // a surface treatment, and says nothing the ring does not.
  shade *= 1.0 + uClass * 0.16 * sin(vObject.y * 13.0 + uSeed * 20.0);

  // One key light fixed in view space, so a system reads as one engraved plate
  // rather than a scatter of independently lit balls.
  vec3 key = normalize(vec3(-0.45, 0.55, 0.72));
  float diffuse = max(dot(normal, key), 0.0);
  float fill = max(dot(normal, normalize(vec3(0.62, -0.18, -0.76))), 0.0);
  float rim = pow(1.0 - max(normal.z, 0.0), 2.4);
  vec3 halfVector = normalize(key + vec3(0.0, 0.0, 1.0));
  float mineralGlint = pow(max(dot(normal, halfVector), 0.0), 28.0) * smoothstep(0.56, 0.82, band);

  // An unlit body has illuminated terrain but makes no light of its own. That
  // keeps Explore mode readable while amber still reads as light ARRIVING,
  // rather than as merely a warmer surface tint.
  vec3 terrain = mix(uBase * 0.58, uBase * 1.08, ridge);
  vec3 color = terrain * shade * (0.22 + diffuse * 0.84 + fill * 0.18);

  // The language tint moves through mineral seams and cloud bands rather than
  // replacing the community-owned surface colour. A Python world and a Ruby
  // world therefore feel different while neither claims a different import
  // community or a different understanding state.
  float languageVein = smoothstep(0.58, 0.84, mix(continental, current, uShimmer));
  color = mix(color, uLanguage * (0.52 + diffuse * 0.48), languageVein * 0.42);
  color += uLanguage * (0.035 + crust * 0.055) * (1.0 - uLit);

  // Atmosphere: a rim band in the body's own community hue. Never amber --
  // amber means understood and nothing else.
  color += uBase * rim * 0.46;
  color += uCool * rim * 0.12 * (1.0 - uLit);
  color += uBase * mineralGlint * 0.16;

  // Understanding. Emissive, because it is the only light the body makes.
  color = mix(color, uAmber * (0.55 + 0.75 * shade), uLit * 0.85);
  color += uAmber * rim * uLit * 0.9;

  // Uncertainty gets a SHAPE channel, not only a colour: a file the parser
  // could not read is visibly fractured, so the claim survives greyscale and
  // colour-blindness.
  if (uPartial > 0.5) {
    float fracture = step(0.42, fract((vObject.x + vObject.y * 1.7 + vObject.z * 0.6) * 5.5 + uSeed * 7.0));
    color = mix(color * 0.30, color, fracture);
  }

  // Study level recedes everything the selection does not touch.
  color = mix(color, color * 0.22, uDim);

  gl_FragColor = vec4(color, 1.0);
}
`;

const ATMOSPHERE_VERTEX = `
varying vec3 vViewNormal;
void main(){
  vViewNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const ATMOSPHERE_FRAGMENT = `
uniform vec3 uBase;
uniform vec3 uCool;
uniform vec3 uLanguage;
uniform float uDim;
varying vec3 vViewNormal;

void main(){
  vec3 normal = normalize(vViewNormal);
  float rim = pow(1.0 - abs(normal.z), 2.15);
  float crown = pow(1.0 - abs(normal.z), 5.0);
  vec3 coolAir = mix(uCool, uLanguage, 0.62);
  coolAir = mix(coolAir, uBase, 0.18);
  vec3 color = mix(coolAir, uCool, crown * 0.24);
  float alpha = (0.028 + rim * 0.25 + crown * 0.16) * (1.0 - uDim * 0.72);
  gl_FragColor = vec4(color, alpha);
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
uniform float uDim;
uniform float uTime;
varying vec3 vObject;
varying vec3 vViewNormal;

void main(){
  vec3 point = vObject * 3.4 + vec3(uSeed * 31.0);
  float plasma = cbFbm(point + vec3(uTime * 0.035, -uTime * 0.02, uTime * 0.025));
  float filament = 0.5 + 0.5 * sin((vObject.y + plasma * 0.34) * 24.0 + uTime * 0.28);
  float rim = pow(1.0 - abs(normalize(vViewNormal).z), 2.2);
  vec3 coolCore = mix(uLanguage, uCool, 0.56);
  vec3 color = mix(uBase * 0.68, coolCore * 0.94, 0.38 + plasma * 0.46);
  color += uLanguage * filament * 0.2;
  color += coolCore * rim * 0.42;
  color = mix(color, uAmber * (0.92 + plasma * 0.55), uLit * 0.86);
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
export function createBodyGeometry(segments = 32) {
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
    opacity: 0.72,
    depthTest: false,
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
  glow.scale.setScalar(6.4);
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
  const innerCorona = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(coronaColor),
      transparent: true,
      opacity: node.focusDim ? 0.035 : 0.13,
      depthWrite: false,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
    }),
  );
  innerCorona.name = "codemble-system-star-corona";
  innerCorona.scale.setScalar(1.42);
  const outerCorona = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(coronaColor),
      transparent: true,
      opacity: node.focusDim ? 0.018 : 0.055,
      depthWrite: false,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
    }),
  );
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
  atmosphere.scale.setScalar(1.16);
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
