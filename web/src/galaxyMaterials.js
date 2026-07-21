import * as THREE from "three";

// Every texture here is drawn on a 2D canvas at runtime: no image assets ship,
// and the same code always produces the same bytes. Textures and materials are
// built once and shared, because these accessors run per node on every graph
// update and a texture per node would melt a mid-range laptop.

const HALO_TEXTURE_SIZE = 128;
const NEBULA_TEXTURE_SIZE = 256;

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

function ringTexture(size) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  context.strokeStyle = "rgba(255, 255, 255, 1)";
  context.lineWidth = size * 0.05;
  context.beginPath();
  context.arc(size / 2, size / 2, size * 0.4, 0, Math.PI * 2);
  context.stroke();
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
  const nebulaTexture = owned(radialTexture(NEBULA_TEXTURE_SIZE, [
    [0, 0.32], [0.45, 0.14], [0.8, 0.03], [1, 0],
  ]));
  const reticleTexture = owned(ringTexture(HALO_TEXTURE_SIZE));
  const haloMaterials = new Map();
  const nebulaMaterials = new Map();
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
    nebula(tint, radius) {
      if (!nebulaMaterials.has(tint)) {
        nebulaMaterials.set(
          tint,
          owned(new THREE.SpriteMaterial({
            map: nebulaTexture,
            color: new THREE.Color(tint),
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false,
            // Alpha lives here, not in the token: the token has to survive a
            // 4.5:1 legend check, the fog has to stay a whisper.
            opacity: 0.16,
          })),
        );
      }
      const sprite = new THREE.Sprite(nebulaMaterials.get(tint));
      sprite.scale.setScalar(radius);
      sprite.renderOrder = -2;
      return sprite;
    },
    reticle(radius) {
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: reticleTexture,
          color: new THREE.Color(palette.orbit),
          transparent: true,
          depthWrite: false,
          depthTest: false,
        }),
      );
      sprite.scale.setScalar(radius * 5);
      sprite.renderOrder = 3;
      return sprite;
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
      sprite.scale.set(LABEL_SCREEN_HEIGHT * aspect, LABEL_SCREEN_HEIGHT, 1);
      // Clear of the star and its halo, so the plate never sits on the glow.
      // The declutter pass may move it to another slot around the star, so it
      // keeps the resting offset to measure those alternatives from.
      sprite.userData.baseOffsetY = radius * 2.2 + 1.2;
      sprite.position.set(0, sprite.userData.baseOffsetY, 0);
      sprite.renderOrder = 4;
      sprite.visible = false;
      sprite.userData.codembleLabel = true;
      // The plate's width as a fraction of the viewport, published here because
      // this is where the sizing constant lives. The declutter pass needs it to
      // know how many screen cells a name actually covers, and deriving it over
      // there meant duplicating a constant across modules.
      sprite.userData.screenWidthFraction = LABEL_SCREEN_HEIGHT * aspect;
      sprite.userData.screenHeightFraction = LABEL_SCREEN_HEIGHT;
      return sprite;
    },
    dispose() {
      // The only real free: every shared texture and material registered above,
      // in creation order. The per-call reticle material is not shared and is
      // still freed by three-forcegraph when its node object is removed.
      for (const release of releases) release();
      releases.length = 0;
      haloMaterials.clear();
      nebulaMaterials.clear();
      labelMaterials.clear();
    },
  };
}

// Fraction of the viewport height one name plate occupies. Sprites with
// sizeAttenuation off measure their scale in that space, so this is literally
// "labels are ~3.4% of the window tall" at any zoom.
const LABEL_SCREEN_HEIGHT = 0.034;
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

export function createStarfield(seedText, palette, count = 1400, radius = 1600) {
  const random = mulberry32(fnv1a(seedText));
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    // Uniform on a sphere shell, from the seeded stream only -- never Math.random.
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    const distance = radius * (0.65 + random() * 0.35);
    positions[index * 3] = distance * Math.sin(phi) * Math.cos(theta);
    positions[index * 3 + 1] = distance * Math.cos(phi);
    positions[index * 3 + 2] = distance * Math.sin(phi) * Math.sin(theta);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const points = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      // Dust, not stars: it must read as depth, never compete with a lit system.
      color: new THREE.Color(palette.nodeDim),
      size: 2.2,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
    }),
  );
  points.name = "codemble-starfield";
  return points;
}
