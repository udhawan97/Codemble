const CLICK_OBSTRUCTION_SELECTOR =
  ".orientation-copy--system, .system-navigator, .legend-toggle";
const NAME_OBSTRUCTION_SELECTOR =
  ".orientation-bar, .orientation-copy--system, .system-navigator, .keyboard-focus";

/**
 * Measure the usable canvas and classify the DOM drawn over it.
 *
 * The returned rectangles use canvas-local CSS pixels. Consumers decide what
 * to do with those facts: galaxyView frames around click obstructions and the
 * Name Atlas rejects labels under name obstructions.
 */
export function measureCanvasOcclusion({
  host,
  renderer,
  getStyle = (element) => getComputedStyle(element),
}) {
  const origin = host?.getBoundingClientRect?.();
  const viewport = measuredViewport(origin, renderer);
  const stage = host?.closest?.(".map-stage");
  if (!stage || !origin) {
    return Object.freeze({
      viewport,
      clickObstructions: Object.freeze([]),
      nameObstructions: Object.freeze([]),
    });
  }

  return Object.freeze({
    viewport,
    clickObstructions: boxesFor(stage, CLICK_OBSTRUCTION_SELECTOR, origin, {
      accepts: (element) => getStyle(element).pointerEvents !== "none",
    }),
    nameObstructions: boxesFor(stage, NAME_OBSTRUCTION_SELECTOR, origin),
  });
}

function measuredViewport(origin, renderer) {
  if (origin?.width && origin?.height) {
    return Object.freeze({ width: origin.width, height: origin.height });
  }
  const width = renderer?.width?.();
  const height = renderer?.height?.();
  return width && height ? Object.freeze({ width, height }) : null;
}

function boxesFor(stage, selector, origin, { accepts = () => true } = {}) {
  const boxes = [];
  for (const element of stage.querySelectorAll(selector)) {
    if (!accepts(element)) continue;
    const box = element.getBoundingClientRect();
    if (!box.width || !box.height) continue;
    boxes.push(
      Object.freeze({
        left: box.left - origin.left,
        right: box.right - origin.left,
        top: box.top - origin.top,
        bottom: box.bottom - origin.top,
      }),
    );
  }
  return Object.freeze(boxes);
}
