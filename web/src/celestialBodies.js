import * as THREE from "three";

/**
 * Procedural celestial bodies for the System level.
 *
 * Authorised by the 2026-07-29 Decision Log entry, which amends the "elaborate
 * game art" Non-Goal. Everything here is DECORATIVE: the crust, the banding and
 * the atmosphere carry no fact and are seeded only by the node's own id, so the
 * same code always yields the same world. Every SEMANTIC channel a body wears
 * -- size, brightness, community hue, amber for understood, the class ring, the
 * fracture on an unreadable file -- is still decided by `graphData.js` from
 * parser truth and is passed in here as a finished value.
 *
 * Level-of-detail is the reason this module exists at all rather than being
 * folded into `galaxyMaterials`. A galaxy draws up to ~1,000 systems and cannot
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
uniform float uSeed;
uniform float uLit;
uniform float uPartial;
uniform float uClass;
uniform float uDim;
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
  crust = mix(crust, band, 0.45);
  float shade = 0.72 + 0.55 * crust;

  // A class is a container of methods -- a parser fact -- so it wears strata.
  // The ring in makeMarker already says "class"; this only gives the same fact
  // a surface treatment, and says nothing the ring does not.
  shade *= 1.0 + uClass * 0.16 * sin(vObject.y * 13.0 + uSeed * 20.0);

  // One key light fixed in view space, so a system reads as one engraved plate
  // rather than a scatter of independently lit balls.
  vec3 key = normalize(vec3(-0.45, 0.55, 0.72));
  float diffuse = max(dot(normal, key), 0.0);
  float rim = pow(1.0 - max(normal.z, 0.0), 2.4);

  // An unlit body is genuinely dark. That is what lets amber read as light
  // ARRIVING rather than as merely a warmer tint, which is the whole reward.
  vec3 color = uBase * shade * (0.16 + diffuse * 0.95);

  // Atmosphere: a rim band in the body's own community hue. Never amber --
  // amber means understood and nothing else.
  color += uBase * rim * 0.55;

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
 * where it would not be for a 1,000-system galaxy. These are NOT registered as
 * shared resources, so three-forcegraph's deallocator freeing them with their
 * node object is exactly right.
 */
export function createBodyMaterial({ node, color, palette }) {
  return new THREE.ShaderMaterial({
    vertexShader: BODY_VERTEX,
    fragmentShader: BODY_FRAGMENT,
    uniforms: {
      uBase: { value: new THREE.Color(color) },
      uAmber: { value: new THREE.Color(palette.star) },
      uSeed: { value: bodySeed(node.id) },
      uLit: { value: node.understood ? 1 : 0 },
      uPartial: { value: node.partial ? 1 : 0 },
      uClass: { value: node.kind === "class" ? 1 : 0 },
      uDim: { value: node.focusDim ? 1 : 0 },
    },
  });
}

/**
 * The System-level body for one parser-proven structure.
 *
 * Returns a mesh sized to the caller's radius. The caller owns placement; this
 * owns only how the body looks.
 */
export function createBody({ node, color, palette, radius, geometry }) {
  const mesh = new THREE.Mesh(geometry, createBodyMaterial({ node, color, palette }));
  mesh.scale.setScalar(radius);
  // A deterministic resting tilt, so a system does not read as a row of
  // identically-oriented balls. Decorative, seeded, and never animated into a
  // different value.
  mesh.rotation.set(bodySeed(`${node.id}:tilt`) * 0.9 - 0.45, bodySeed(node.id) * Math.PI * 2, 0);
  mesh.userData.codembleBody = true;
  return mesh;
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
      if (object.userData?.codembleBody) object.rotation.y += delta * 0.06;
    });
    frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
  return () => cancelAnimationFrame(frame);
}
