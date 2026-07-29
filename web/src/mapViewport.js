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
 * Below this, a true fit stops being an overview at all: this project's
 * architecture fits at 7%, a thumbnail with no names, no boxes, no routes.
 */
export const MIN_READABLE_FIT = 0.35;

/**
 * The most zoomed-out view of the drawing that is still worth looking at.
 *
 * Three cases, in order:
 *
 * 1. The whole shape fits readably -- show the whole shape. Unchanged.
 * 2. It only fits as a thumbnail and the drawing is WIDER than the viewport --
 *    fit the width and let the height scroll, which is what an overview of a
 *    layered import diagram is for.
 * 3. It only fits as a thumbnail and the drawing is NARROWER than the viewport
 *    -- there is no width left to fit, so drop to the readable floor.
 *
 * Case 3 used to be case 2 with a `Math.min(1, ...)` ceiling on the width fit,
 * which resolved to exactly 1.0 on any viewport wider than the drawing. On this
 * repository at 1440x720 that made Fit a silent no-op at 100%, and an actual
 * zoom IN from anywhere below it: pressing "Fit" at 64% took the learner to
 * 100% and cut the visible drawing from 33.5% to 21.5%. The one control that
 * promises the whole shape was the one that hid more of it.
 */
export function mapOverviewZoom(
  viewportWidth,
  viewportHeight,
  contentWidth,
  contentHeight,
) {
  if (!viewportWidth || !viewportHeight || !contentWidth || !contentHeight) return 1;
  const whole = fitMapZoom(viewportWidth, viewportHeight, contentWidth, contentHeight);
  if (whole >= MIN_READABLE_FIT) return whole;
  // Never wider than the drawing needs, never below the readable floor.
  return clampMapZoom(Math.min(MIN_READABLE_FIT, viewportWidth / contentWidth));
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
