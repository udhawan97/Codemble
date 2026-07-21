import * as THREE from "three";

const LABEL_CELL_PX = Object.freeze({ width: 132, height: 30 });
const LABEL_BUDGET = Object.freeze({ far: 14, near: 44 });
const LABEL_SLOTS = Object.freeze([0, -1, 1, -2, 2]);
const LABEL_SLOT_GAP_PX = 4;
const LABEL_SCREEN_HEIGHT = 0.034;

export function configureNamePlate(sprite, { radius, aspect }) {
  sprite.scale.set(LABEL_SCREEN_HEIGHT * aspect, LABEL_SCREEN_HEIGHT, 1);
  sprite.userData.baseOffsetY = radius * 2.2 + 1.2;
  sprite.position.set(0, sprite.userData.baseOffsetY, 0);
  sprite.visible = false;
  sprite.userData.codembleLabel = true;
  sprite.userData.screenWidthFraction = LABEL_SCREEN_HEIGHT * aspect;
  sprite.userData.screenHeightFraction = LABEL_SCREEN_HEIGHT;
  return sprite;
}

export function createNameAtlas(nodes) {
  const rank = rankNames(nodes);
  const projected = new THREE.Vector3();
  const origin = new THREE.Vector3();

  function place({
    scene,
    camera,
    width,
    height,
    distance,
    distanceBounds,
    hoverNodeId = null,
  }) {
    const sprites = namePlates(scene);
    for (const sprite of sprites) sprite.visible = false;
    if (!sprites.length || !rank.size) {
      return Object.freeze({ budget: 0, shown: 0, visibleIds: Object.freeze([]) });
    }

    const budget = labelBudget(distance, distanceBounds);
    const candidates = [];
    for (const sprite of sprites) {
      const nodeId = sprite.userData.nodeId;
      const star = sprite.parent;
      if (!star) continue;
      star.getWorldPosition(origin);
      const base = sprite.userData.baseOffsetY ?? 0;
      const anchor = project(origin, base, camera, width, height, projected);
      if (!anchor) continue;
      const oneUnit = project(origin, base + 1, camera, width, height, projected);
      const pixelsPerUnit = oneUnit ? Math.abs(oneUnit.screenY - anchor.screenY) : 0;
      candidates.push({
        sprite,
        nodeId,
        origin: origin.clone(),
        base,
        pixelsPerUnit,
        anchor,
        halfWidth: ((sprite.userData.screenWidthFraction ?? 0.14) * height) / 2,
        halfHeight: ((sprite.userData.screenHeightFraction ?? 0.034) * height) / 2,
        rank: nodeId === hoverNodeId ? -1 : rank.get(nodeId) ?? Infinity,
      });
    }
    candidates.sort(
      (left, right) =>
        left.rank - right.rank || left.nodeId.localeCompare(right.nodeId),
    );

    const taken = new Set();
    const visibleIds = [];
    for (const candidate of candidates) {
      if (visibleIds.length >= budget) break;
      const placement = chooseSlot(candidate, {
        camera,
        width,
        height,
        projected,
        taken,
      });
      if (!placement) continue;
      for (const cell of placement.cells) taken.add(cell);
      candidate.sprite.position.y = candidate.base + placement.offset;
      candidate.sprite.visible = true;
      visibleIds.push(candidate.nodeId);
    }
    return Object.freeze({
      budget,
      shown: visibleIds.length,
      visibleIds: Object.freeze(visibleIds),
    });
  }

  function hide(scene) {
    for (const sprite of namePlates(scene)) sprite.visible = false;
  }

  return Object.freeze({ hide, place });
}

function rankNames(nodes) {
  const ranked = nodes
    .filter((node) => node.label)
    .map((node) => ({
      id: node.id,
      weight:
        (node.home ? 3_000_000 : 0) +
        (node.understood ? 1_000_000 : 0) +
        (node.centrality ?? 0) * 1000,
    }))
    .sort(
      (left, right) =>
        right.weight - left.weight || left.id.localeCompare(right.id),
    );
  return new Map(ranked.map((entry, index) => [entry.id, index]));
}

function namePlates(scene) {
  const sprites = [];
  scene.traverse((object) => {
    if (object.userData?.codembleLabel) sprites.push(object);
  });
  return sprites;
}

function labelBudget(distance, bounds) {
  const span = Math.max(1, bounds.max - bounds.min);
  const nearness = 1 - Math.min(1, Math.max(0, (distance - bounds.min) / span));
  return Math.round(
    LABEL_BUDGET.far + (LABEL_BUDGET.near - LABEL_BUDGET.far) * nearness,
  );
}

function project(origin, offsetY, camera, width, height, projected) {
  projected.set(origin.x, origin.y + offsetY, origin.z).project(camera);
  if (projected.z > 1) return null;
  const screenX = (projected.x * 0.5 + 0.5) * width;
  const screenY = (-projected.y * 0.5 + 0.5) * height;
  if (screenX < 0 || screenX > width || screenY < 0 || screenY > height) return null;
  return { screenX, screenY };
}

function chooseSlot(candidate, { camera, width, height, projected, taken }) {
  const step = candidate.pixelsPerUnit
    ? (candidate.halfHeight * 2 + LABEL_SLOT_GAP_PX) / candidate.pixelsPerUnit
    : 0;
  for (const slot of LABEL_SLOTS) {
    const offset = slot * step;
    const at =
      slot === 0
        ? candidate.anchor
        : project(
            candidate.origin,
            candidate.base + offset,
            camera,
            width,
            height,
            projected,
          );
    if (!at) continue;
    const cells = coveredCells(at, candidate);
    if (cells.some((cell) => taken.has(cell))) continue;
    return { cells, offset };
  }
  return null;
}

function coveredCells(at, { halfWidth, halfHeight }) {
  const firstColumn = Math.floor((at.screenX - halfWidth) / LABEL_CELL_PX.width);
  const lastColumn = Math.floor((at.screenX + halfWidth) / LABEL_CELL_PX.width);
  const firstRow = Math.floor((at.screenY - halfHeight) / LABEL_CELL_PX.height);
  const lastRow = Math.floor((at.screenY + halfHeight) / LABEL_CELL_PX.height);
  const cells = [];
  for (let column = firstColumn; column <= lastColumn; column += 1) {
    for (let row = firstRow; row <= lastRow; row += 1) cells.push(`${column}:${row}`);
  }
  return cells;
}
