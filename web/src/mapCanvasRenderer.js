const ARCHITECTURE_PADDING = 32;
const WORKFLOW_PADDING = 16;
const SPATIAL_BAND_HEIGHT = 64;
const WORKFLOW_HIT_HEIGHT = 32;
const BOX_LABEL_FONT_PX = 13;
const BOX_LABEL_CHAR_EM = 0.62;
const BOX_LABEL_X = 14;
const BOX_LABEL_RIGHT_PAD = 6;
const VIEWPORT_OVERSCAN = 48;

function boundsFromPoints(points) {
  return points.reduce(
    (bounds, [x, y]) => ({
      left: Math.min(bounds.left, x),
      top: Math.min(bounds.top, y),
      right: Math.max(bounds.right, x),
      bottom: Math.max(bounds.bottom, y),
    }),
    { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity },
  );
}

function intersects(first, second) {
  return !(
    first.right < second.left ||
    first.left > second.right ||
    first.bottom < second.top ||
    first.top > second.bottom
  );
}

function indexByVerticalBand(items, boundsOf) {
  const bands = new Map();
  for (const item of items) {
    const bounds = boundsOf(item);
    const first = Math.floor(bounds.top / SPATIAL_BAND_HEIGHT);
    const last = Math.floor(bounds.bottom / SPATIAL_BAND_HEIGHT);
    for (let band = first; band <= last; band += 1) {
      const members = bands.get(band) ?? [];
      members.push(item);
      bands.set(band, members);
    }
  }
  return bands;
}

function logicalViewport(viewport) {
  const scale = Math.max(viewport.scale || 1, 0.0001);
  return {
    left: (viewport.scrollLeft - (viewport.offsetX || 0)) / scale - VIEWPORT_OVERSCAN,
    top: viewport.scrollTop / scale - VIEWPORT_OVERSCAN,
    right:
      (viewport.scrollLeft - (viewport.offsetX || 0) + viewport.width) / scale +
      VIEWPORT_OVERSCAN,
    bottom: (viewport.scrollTop + viewport.height) / scale + VIEWPORT_OVERSCAN,
  };
}

export function fitBoxLabel(label, boxWidth) {
  const available = boxWidth - BOX_LABEL_X - BOX_LABEL_RIGHT_PAD;
  const maxChars = Math.max(
    1,
    Math.floor(available / (BOX_LABEL_FONT_PX * BOX_LABEL_CHAR_EM)),
  );
  if (label.length <= maxChars) return label;
  return `${label.slice(0, Math.max(1, maxChars - 1))}…`;
}

export function prepareArchitectureCanvas(
  architecture,
  { communityIndexByRegion = null } = {},
) {
  const boxes = architecture.boxes
    .map((box) => ({
      ...box,
      drawX: box.x + ARCHITECTURE_PADDING,
      drawY: box.y + ARCHITECTURE_PADDING,
      communityFamily: communityIndexByRegion?.get(box.id) ?? null,
    }))
    .sort((left, right) => left.y - right.y || left.x - right.x || left.id.localeCompare(right.id));
  const boxById = new Map(boxes.map((box) => [box.id, box]));
  const boxBounds = (box) => ({
    left: box.drawX,
    top: box.drawY,
    right: box.drawX + box.width,
    bottom: box.drawY + box.height,
  });
  const boxesByBand = indexByVerticalBand(boxes, boxBounds);
  const edges = architecture.edges
    .filter((edge) => boxById.has(edge.src) && boxById.has(edge.dst))
    .map((edge) => {
      const points = edge.points.map(([x, y]) => [
        x + ARCHITECTURE_PADDING,
        y + ARCHITECTURE_PADDING,
      ]);
      return { ...edge, points, bounds: boundsFromPoints(points) };
    });
  return Object.freeze({
    kind: "architecture",
    boxes,
    boxById,
    boxesByBand,
    edges,
    padding: ARCHITECTURE_PADDING,
  });
}

export function visibleArchitectureCanvas(scene, viewport) {
  const bounds = logicalViewport(viewport);
  return {
    boxes: scene.boxes.filter((box) =>
      intersects(bounds, {
        left: box.drawX,
        top: box.drawY,
        right: box.drawX + box.width,
        bottom: box.drawY + box.height,
      }),
    ),
    edges: scene.edges.filter((edge) => intersects(bounds, edge.bounds)),
  };
}

export function hitArchitectureCanvas(scene, point) {
  return (
    scene.boxesByBand
      .get(Math.floor(point.y / SPATIAL_BAND_HEIGHT))
      ?.find(
        (box) =>
          point.x >= box.drawX &&
          point.x <= box.drawX + box.width &&
          point.y >= box.drawY &&
          point.y <= box.drawY + box.height,
      ) ?? null
  );
}

function directionalTarget(items, activeId, key, idOf, centerOf) {
  if (!items.length) return null;
  if (key === "Home") return items[0];
  if (key === "End") return items.at(-1);
  const activeIndex = Math.max(0, items.findIndex((item) => idOf(item) === activeId));
  const active = items[activeIndex] ?? items[0];
  const origin = centerOf(active);
  const direction = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, -1],
    ArrowDown: [0, 1],
  }[key];
  if (!direction) return active;
  const candidates = items
    .filter((item) => idOf(item) !== idOf(active))
    .map((item) => {
      const point = centerOf(item);
      const dx = point.x - origin.x;
      const dy = point.y - origin.y;
      const forward = dx * direction[0] + dy * direction[1];
      const cross = Math.abs(dx * direction[1] - dy * direction[0]);
      return { item, forward, cross };
    })
    .filter((candidate) => candidate.forward > 0)
    .sort(
      (left, right) =>
        left.cross / left.forward - right.cross / right.forward ||
        Math.hypot(left.forward, left.cross) -
          Math.hypot(right.forward, right.cross) ||
        idOf(left.item).localeCompare(idOf(right.item)),
    );
  if (candidates.length) return candidates[0].item;
  const fallback = key === "ArrowLeft" || key === "ArrowUp" ? activeIndex - 1 : activeIndex + 1;
  return items[Math.max(0, Math.min(items.length - 1, fallback))];
}

export function architectureKeyboardTarget(scene, activeId, key) {
  return directionalTarget(
    scene.boxes,
    activeId,
    key,
    (box) => box.id,
    (box) => ({ x: box.drawX + box.width / 2, y: box.drawY + box.height / 2 }),
  );
}

export function architectureBoxLabel(box) {
  return `${box.label}, ${box.node_count} ${box.node_count === 1 ? "structure" : "structures"}, ${box.loc} ${box.loc === 1 ? "line" : "lines"}${box.understood ? ", understood" : ", not yet understood"}${box.home ? ", Home" : ""}${box.reachable ? "" : ", no import route from Home"}${box.partial ? ", unchartable, syntax error" : ""}`;
}

export function prepareWorkflowCanvas(workflow) {
  const rows = [...workflow.nodes]
    .sort((left, right) => left.order - right.order)
    .map((row) => {
      const drawX = row.x + WORKFLOW_PADDING;
      const drawY = row.y + WORKFLOW_PADDING;
      const labelWidth = row.label.length * 13 * BOX_LABEL_CHAR_EM;
      const metaWidth = Math.max(
        workflowRowMeta(row, "easy").length,
        workflowRowMeta(row, "expert").length,
      ) * 11 * BOX_LABEL_CHAR_EM;
      return {
        ...row,
        drawX,
        drawY,
        bounds: {
          left: drawX,
          top: drawY,
          right: drawX + 20 + labelWidth + metaWidth + 8,
          bottom: drawY + WORKFLOW_HIT_HEIGHT,
        },
      };
    });
  const lastById = new Map();
  const edges = [];
  for (const row of rows) {
    const parent = row.parent === null ? null : lastById.get(row.parent) ?? null;
    if (parent) {
      const points = [
        [parent.drawX + 8, parent.drawY + 20],
        [parent.drawX + 8, row.drawY + 12],
        [row.drawX + 8, row.drawY + 12],
      ];
      edges.push({ row, parent, points, bounds: boundsFromPoints(points) });
    }
    lastById.set(row.id, row);
  }
  return Object.freeze({
    kind: "workflow",
    rows,
    rowByOrder: new Map(rows.map((row) => [row.order, row])),
    rowsByBand: indexByVerticalBand(rows, (row) => row.bounds),
    edges,
    padding: WORKFLOW_PADDING,
  });
}

export function visibleWorkflowCanvas(scene, viewport) {
  const bounds = logicalViewport(viewport);
  return {
    rows: scene.rows.filter((row) => intersects(bounds, row.bounds)),
    edges: scene.edges.filter((edge) => intersects(bounds, edge.bounds)),
  };
}

export function hitWorkflowCanvas(scene, point) {
  return (
    scene.rowsByBand
      .get(Math.floor(point.y / SPATIAL_BAND_HEIGHT))
      ?.find(
        (row) =>
          point.x >= row.bounds.left &&
          point.x <= row.bounds.right &&
          point.y >= row.bounds.top &&
          point.y <= row.bounds.bottom,
      ) ?? null
  );
}

export function workflowKeyboardTarget(scene, activeOrder, key) {
  if (!scene.rows.length) return null;
  if (key === "Home") return scene.rows[0];
  if (key === "End") return scene.rows.at(-1);
  const currentIndex = Math.max(
    0,
    scene.rows.findIndex((row) => row.order === activeOrder),
  );
  const current = scene.rows[currentIndex] ?? scene.rows[0];
  if (key === "ArrowLeft" && current.parent !== null) {
    return scene.rows
      .slice(0, currentIndex)
      .reverse()
      .find((row) => row.id === current.parent) ?? current;
  }
  if (key === "ArrowRight") {
    return scene.rows.slice(currentIndex + 1).find((row) => row.parent === current.id) ?? current;
  }
  const delta = key === "ArrowUp" ? -1 : key === "ArrowDown" ? 1 : 0;
  return scene.rows[currentIndex + delta] ?? current;
}

export function workflowRowMeta(row, mode) {
  const parts = [];
  if (row.relation === "defines") {
    parts.push(mode === "easy" ? "lives here" : "defined in this module");
  } else if (!row.certain) {
    parts.push("possible call");
  }
  if (row.cut === "cycle") parts.push("loops back");
  if (row.cut === "repeat") parts.push("shown above");
  if (row.partial) parts.push(mode === "easy" ? "could not be read" : "unchartable");
  return parts.map((part) => ` — ${part}`).join("");
}

export function workflowRowLabel(row) {
  return `${row.label} at ${row.file}:${row.lineno}${row.certain ? "" : ", possible call"}${row.cut === "cycle" ? ", repeats an earlier step" : ""}${row.cut === "repeat" ? ", already shown above" : ""}${row.partial ? ", unchartable, syntax error" : ""}`;
}

function cssValue(style, property, fallback) {
  return style?.getPropertyValue?.(property)?.trim() || fallback;
}

function rgbChannels(value) {
  const hex = value.match(/^#([0-9a-f]{6})$/i)?.[1];
  if (hex) return [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16));
  const rgb = value.match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  return rgb ? rgb.slice(1).map(Number) : null;
}

function mixPaint(foreground, background, weight) {
  const front = rgbChannels(foreground);
  const back = rgbChannels(background);
  if (!front || !back) return background;
  return `rgb(${front.map((value, index) => Math.round(value * weight + back[index] * (1 - weight))).join(" ")})`;
}

export function canvasMapPalette(style) {
  const ground2 = cssValue(style, "--cm-ground-2", "#101a3e");
  const communities = Array.from({ length: 8 }, (_, index) =>
    mixPaint(cssValue(style, `--cm-com-${index}`, ground2), ground2, 0.16),
  );
  return Object.freeze({
    ground2,
    hairline: cssValue(style, "--cm-hairline", "#24325c"),
    ink: cssValue(style, "--cm-ink", "#eef2fa"),
    ink3: cssValue(style, "--cm-ink-3", "#7d8aa8"),
    route: cssValue(style, "--cm-route", "rgb(96 113 152)"),
    possible: cssValue(style, "--cm-route-possible", "rgb(146 160 194)"),
    understood: cssValue(style, "--cm-star-high", "#f6d087"),
    interaction: cssValue(style, "--cm-orbit", "#82abec"),
    mono: cssValue(style, "--cm-font-mono", "monospace"),
    communities,
    language: {
      python: cssValue(style, "--cm-neb-python", "rgb(112 166 144)"),
      javascript: cssValue(style, "--cm-neb-js", "rgb(161 151 185)"),
      typescript: cssValue(style, "--cm-neb-ts", "rgb(119 161 186)"),
      go: cssValue(style, "--cm-neb-go", "rgb(132 178 161)"),
      java: cssValue(style, "--cm-neb-java", "rgb(177 154 137)"),
      rust: cssValue(style, "--cm-neb-rust", "rgb(183 145 132)"),
      csharp: cssValue(style, "--cm-neb-csharp", "rgb(157 146 184)"),
    },
  });
}

function roundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function beginViewport(context, viewport) {
  context.save();
  context.translate((viewport.offsetX || 0) - viewport.scrollLeft, -viewport.scrollTop);
  context.scale(viewport.scale, viewport.scale);
  context.lineCap = "round";
  context.lineJoin = "round";
}

function drawArrow(context, points, paint) {
  if (points.length < 2) return;
  const [fromX, fromY] = points.at(-2);
  const [toX, toY] = points.at(-1);
  const angle = Math.atan2(toY - fromY, toX - fromX);
  context.save();
  context.translate(toX, toY);
  context.rotate(angle);
  context.fillStyle = paint;
  context.beginPath();
  context.moveTo(0, 0);
  context.lineTo(-9, -4);
  context.lineTo(-9, 4);
  context.closePath();
  context.fill();
  context.restore();
}

export function drawArchitectureCanvas(context, scene, viewport, palette, options = {}) {
  const visible = visibleArchitectureCanvas(scene, viewport);
  beginViewport(context, viewport);
  for (const edge of visible.edges) {
    const paint = edge.certain && !edge.cycle ? palette.route : palette.possible;
    context.strokeStyle = paint;
    context.lineWidth = 1 + Math.min(2.5, (Math.max(1, edge.weight) - 1) * 0.5);
    context.setLineDash(edge.certain ? [] : [5, 4]);
    context.beginPath();
    edge.points.forEach(([x, y], index) =>
      index === 0 ? context.moveTo(x, y) : context.lineTo(x, y),
    );
    context.stroke();
    context.setLineDash([]);
    drawArrow(context, edge.points, paint);
  }
  for (const box of visible.boxes) {
    const x = box.drawX;
    const y = box.drawY;
    const fill =
      box.communityFamily === null
        ? palette.ground2
        : palette.communities[box.communityFamily] ?? palette.ground2;
    roundedRect(context, x, y, box.width, box.height, 3);
    context.fillStyle = fill;
    context.fill();
    context.strokeStyle = box.understood
      ? palette.understood
      : box.partial
        ? palette.possible
        : palette.hairline;
    context.lineWidth = box.home ? 2 : 1;
    context.setLineDash(box.reachable ? [] : [4, 3]);
    context.stroke();
    context.setLineDash([]);
    context.fillStyle = palette.language[box.language] ?? palette.hairline;
    context.fillRect(x, y, 4, box.height);
    if (box.partial) {
      context.fillStyle = palette.possible;
      context.beginPath();
      context.moveTo(x + box.width - 16, y + 2);
      context.lineTo(x + box.width - 2, y + 2);
      context.lineTo(x + box.width - 2, y + 16);
      context.closePath();
      context.fill();
    }
    if (box.id === options.selectedId || box.id === options.activeId || box.id === options.hoverId) {
      roundedRect(context, x - 3, y - 3, box.width + 6, box.height + 6, 5);
      context.strokeStyle = palette.interaction;
      context.lineWidth = box.id === options.activeId && options.keyboardFocused ? 2.5 : 1.5;
      context.stroke();
    }
    context.fillStyle = palette.ink;
    context.font = `13px ${palette.mono}`;
    context.fillText(fitBoxLabel(box.short_label ?? box.label, box.width), x + 14, y + 24);
    context.fillStyle = palette.ink3;
    context.font = `11px ${palette.mono}`;
    const meta =
      options.mode === "easy"
        ? `${box.node_count} ${box.node_count === 1 ? "piece" : "pieces"}`
        : `${box.node_count} ${box.node_count === 1 ? "node" : "nodes"} · ${box.loc} LOC`;
    context.fillText(meta, x + 14, y + 42);
  }
  context.restore();
  return { visibleBoxes: visible.boxes.length, visibleEdges: visible.edges.length };
}

export function drawWorkflowCanvas(context, scene, viewport, palette, options = {}) {
  const visible = visibleWorkflowCanvas(scene, viewport);
  beginViewport(context, viewport);
  for (const edge of visible.edges) {
    context.strokeStyle = edge.row.certain ? palette.route : palette.possible;
    context.lineWidth = 1.2;
    context.setLineDash(edge.row.certain ? [] : [5, 4]);
    context.beginPath();
    edge.points.forEach(([x, y], index) =>
      index === 0 ? context.moveTo(x, y) : context.lineTo(x, y),
    );
    context.stroke();
  }
  context.setLineDash([]);
  for (const row of visible.rows) {
    const x = row.drawX;
    const y = row.drawY;
    context.fillStyle = row.understood
      ? palette.understood
      : row.partial || row.cut
        ? palette.possible
        : palette.ink3;
    context.beginPath();
    context.arc(x + 8, y + 16, 4, 0, Math.PI * 2);
    context.fill();
    if (
      row.region === options.selectedRegionId ||
      row.order === options.activeOrder ||
      row.order === options.hoverOrder
    ) {
      context.strokeStyle = palette.interaction;
      context.lineWidth = row.order === options.activeOrder && options.keyboardFocused ? 2.5 : 1.5;
      context.beginPath();
      context.arc(x + 8, y + 16, 7, 0, Math.PI * 2);
      context.stroke();
    }
    context.fillStyle = palette.ink;
    context.font = `13px ${palette.mono}`;
    const labelWidth = context.measureText(row.label).width;
    context.fillText(row.label, x + 20, y + 20);
    context.fillStyle = palette.ink3;
    context.font = `11px ${palette.mono}`;
    context.fillText(workflowRowMeta(row, options.mode), x + 20 + labelWidth, y + 20);
  }
  context.restore();
  return { visibleRows: visible.rows.length, visibleEdges: visible.edges.length };
}

export const MAP_CANVAS_GEOMETRY = Object.freeze({
  architecturePadding: ARCHITECTURE_PADDING,
  workflowPadding: WORKFLOW_PADDING,
});
