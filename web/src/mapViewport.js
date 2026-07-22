const ZOOM_MIN = 0.05;
const ZOOM_MAX = 2.5;

export function clampMapZoom(scale) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, scale));
}

export function fitMapZoom(viewportWidth, viewportHeight, contentWidth, contentHeight) {
  if (!viewportWidth || !viewportHeight || !contentWidth || !contentHeight) return 1;
  return clampMapZoom(
    Math.min(viewportWidth / contentWidth, viewportHeight / contentHeight),
  );
}

export function centerMapPoint({ viewportWidth, viewportHeight, scale, point }) {
  return {
    scrollLeft: Math.max(0, point.x * scale - viewportWidth / 2),
    scrollTop: Math.max(0, point.y * scale - viewportHeight / 2),
  };
}

/**
 * Whether a saved viewport still has the given content point on screen.
 *
 * A stored scroll position is only worth restoring while it shows the learner
 * something: a desktop scroll restored into a phone-sized viewport pointed at
 * empty layer bands with no hint that content existed anywhere. The caller
 * falls back to centring on its parser-backed focus point when this is false.
 */
export function viewportShowsPoint({
  viewportWidth,
  viewportHeight,
  scale,
  scrollLeft,
  scrollTop,
  point,
}) {
  if (!point || !viewportWidth || !viewportHeight) return false;
  const x = point.x * scale;
  const y = point.y * scale;
  return (
    x >= scrollLeft &&
    x <= scrollLeft + viewportWidth &&
    y >= scrollTop &&
    y <= scrollTop + viewportHeight
  );
}

/**
 * Fit the drawing's WIDTH and let its height scroll.
 *
 * True fit is honest about the whole shape but useless on a 1:3+ diagram: this
 * project's architecture fits at 7%, a thumbnail with no names. Fitting width
 * keeps layers readable and reachable by scrolling, which is what an overview
 * of a layered import diagram is actually for. Capped at 1 so a small drawing
 * is never inflated past its crisp size.
 */
export function fitMapWidthZoom(viewportWidth, contentWidth) {
  if (!viewportWidth || !contentWidth) return 1;
  return clampMapZoom(Math.min(1, viewportWidth / contentWidth));
}

/**
 * Ephemeral renderer state, deliberately separate from learnerSession. Zoom and
 * pan are not graph truth, but keeping them through a map-data refresh prevents
 * a passed check from throwing the learner to a tiny, unrelated viewport.
 */
export function createMapViewportStore() {
  const views = new Map();
  return Object.freeze({
    read(key) {
      const value = views.get(key);
      return value ? { ...value } : null;
    },
    write(key, view) {
      views.set(key, {
        scale: clampMapZoom(view.scale),
        scrollLeft: Math.max(0, view.scrollLeft),
        scrollTop: Math.max(0, view.scrollTop),
      });
    },
    clear() {
      views.clear();
    },
  });
}
