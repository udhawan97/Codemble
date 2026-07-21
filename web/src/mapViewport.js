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
