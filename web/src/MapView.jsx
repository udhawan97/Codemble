import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  importCycleSummary,
  unsupportedSummary,
} from "./graphData.js";
import {
  MAP_CANVAS_GEOMETRY,
  architectureBoxLabel,
  architectureKeyboardTarget,
  canvasMapPalette,
  drawArchitectureCanvas,
  drawWorkflowCanvas,
  hitArchitectureCanvas,
  hitWorkflowCanvas,
  prepareArchitectureCanvas,
  prepareWorkflowCanvas,
  workflowKeyboardTarget,
  workflowRowLabel,
} from "./mapCanvasRenderer.js";
import {
  centerMapPoint,
  clampMapZoom,
  mapOverviewZoom,
  viewportShowsPoint,
} from "./mapViewport.js";

// Low enough that Fit can always reach a true fit. A deep call tree is far
// taller than any architecture map -- this project's is 9484px against a ~600px
// viewport -- and a floor of 0.25 meant the control labelled Fit stopped four
// times short of fitting while disabling the button that would have gone
// further. At these scales the drawing is a shape rather than a readable
// diagram, which is exactly what an overview is for.
const ZOOM_STEP = 1.25;

/**
 * The Map's answer to the galaxy's bounded orbit: zoom, fit, and drag-to-pan
 * over a diagram far larger than the window. This project's architecture map is
 * 960x2640, so a plain scroll box showed roughly four of its nine import layers
 * and gave no way to see the shape of the whole thing.
 *
 * Panning rides the container's own scroll rather than a transform, so native
 * scrollbars, wheel scrolling, keyboard scrolling and screen-reader behaviour
 * all keep working. Zoom only scales the rendered size -- every coordinate
 * painted into the viewport canvas is still the backend's, untouched, so this
 * stays a pure renderer of graph-owned geometry.
 */
function MapCanvas({
  contentWidth,
  contentHeight,
  label,
  viewKey,
  viewportStore,
  focusPoint,
  centerInline = false,
  children,
}) {
  const scrollRef = useRef(null);
  const initialViewRef = useRef(viewportStore.read(viewKey));
  const [scale, setScale] = useState(() => initialViewRef.current?.scale ?? 1);
  const [panning, setPanning] = useState(false);
  const drag = useRef(null);
  const initialized = useRef(false);
  const viewportFrame = useRef(0);
  const [viewport, setViewport] = useState({
    width: 0,
    height: 0,
    scrollLeft: 0,
    scrollTop: 0,
  });
  const zoomPercent = Math.round(scale * 100);

  const publishViewport = useCallback(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const next = {
      width: scroller.clientWidth,
      height: scroller.clientHeight,
      scrollLeft: scroller.scrollLeft,
      scrollTop: scroller.scrollTop,
    };
    setViewport((current) =>
      current.width === next.width &&
      current.height === next.height &&
      current.scrollLeft === next.scrollLeft &&
      current.scrollTop === next.scrollTop
        ? current
        : next,
    );
  }, []);

  const queueViewport = useCallback(() => {
    cancelAnimationFrame(viewportFrame.current);
    viewportFrame.current = requestAnimationFrame(publishViewport);
  }, [publishViewport]);

  useEffect(
    () => () => cancelAnimationFrame(viewportFrame.current),
    [],
  );

  const rememberViewport = useCallback(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    viewportStore.write(viewKey, {
      scale,
      scrollLeft: scroller.scrollLeft,
      scrollTop: scroller.scrollTop,
    });
  }, [scale, viewKey, viewportStore]);

  // Deliberately not run on mount. The map opens at true size, which already
  // fits horizontally and is the only scale its labels are readable at; Fit is
  // the zoom-out you ask for when you want the whole shape. Auto-fitting also
  // measured the scroller before flex layout had settled and landed on a scale
  // that was neither fitted nor honest.
  //
  // mapOverviewZoom owns which of the three overview cases applies; see its
  // comment. Fit stays deterministic -- it does not read the current scale --
  // so pressing it twice lands in the same place.
  const fit = useCallback(() => {
    const box = scrollRef.current?.getBoundingClientRect();
    if (!box || !contentWidth || !contentHeight) return;
    setScale(mapOverviewZoom(box.width, box.height, contentWidth, contentHeight));
  }, [contentWidth, contentHeight]);

  // A compact viewport opens at readable 100%, centred on Home (or the selected
  // parser-backed target). Fit remains an explicit overview command. If the
  // map temporarily unmounts while refreshed graph data arrives, restore the
  // exact scale and scroll position instead of silently auto-fitting again.
  useLayoutEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller || initialized.current) return undefined;
    let frame = 0;
    frame = requestAnimationFrame(() => {
      const box = scroller.getBoundingClientRect();
      const saved = initialViewRef.current;
      // A saved viewport is replayed only while it still shows the focus
      // point. Restoring a desktop scroll into a phone-sized viewport pointed
      // the learner at empty layer bands with nothing on screen to say why.
      const savedStillHonest =
        saved &&
        (!focusPoint ||
          viewportShowsPoint({
            viewportWidth: box.width,
            viewportHeight: box.height,
            scale: saved.scale,
            scrollLeft: saved.scrollLeft,
            scrollTop: saved.scrollTop,
            point: focusPoint,
          }));
      if (savedStillHonest) {
        scroller.scrollLeft = saved.scrollLeft;
        scroller.scrollTop = saved.scrollTop;
      } else if (box.width < 640 && focusPoint) {
        const position = centerMapPoint({
          viewportWidth: box.width,
          viewportHeight: box.height,
          scale,
          point: focusPoint,
        });
        scroller.scrollLeft = position.scrollLeft;
        scroller.scrollTop = position.scrollTop;
      } else if (saved && !savedStillHonest) {
        // Desktop fallback: the stale scroll is dropped and the drawing opens
        // from its origin, the same first-landing state as a fresh session.
        scroller.scrollLeft = 0;
        scroller.scrollTop = 0;
      }
      initialized.current = true;
      rememberViewport();
      publishViewport();
    });
    return () => cancelAnimationFrame(frame);
  }, [focusPoint, publishViewport, rememberViewport, scale]);

  useEffect(() => {
    if (!initialized.current) return undefined;
    const frame = requestAnimationFrame(() => {
      rememberViewport();
      publishViewport();
    });
    return () => cancelAnimationFrame(frame);
  }, [publishViewport, rememberViewport]);

  // The mount-time honesty check has a live twin: a window RESIZE never
  // remounts this component, so shrinking a desktop window to phone width
  // kept the desktop scroll and showed empty layer bands. When a size change
  // pushes the focus point fully off screen, re-centre on it; a learner who
  // keeps their focus visible keeps their scroll position untouched.
  useEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller) return undefined;
    let last = null;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const previous = last;
      last = { width, height };
      if (!previous || !focusPoint || !initialized.current) return;
      if (Math.abs(width - previous.width) < 1 && Math.abs(height - previous.height) < 1) return;
      const honest = viewportShowsPoint({
        viewportWidth: width,
        viewportHeight: height,
        scale,
        scrollLeft: scroller.scrollLeft,
        scrollTop: scroller.scrollTop,
        point: focusPoint,
      });
      if (honest) return;
      const position = centerMapPoint({
        viewportWidth: width,
        viewportHeight: height,
        scale,
        point: focusPoint,
      });
      scroller.scrollLeft = position.scrollLeft;
      scroller.scrollTop = position.scrollTop;
      rememberViewport();
      queueViewport();
    });
    observer.observe(scroller);
    return () => observer.disconnect();
  }, [focusPoint, queueViewport, rememberViewport, scale]);

  const offsetX = centerInline
    ? Math.max(0, (viewport.width - contentWidth * scale) / 2)
    : 0;

  const revealPoint = useCallback(
    (point, inlineOffset = 0) => {
      const scroller = scrollRef.current;
      if (!scroller || !point) return;
      const x = point.x * scale + inlineOffset;
      const y = point.y * scale;
      scroller.scrollLeft = Math.max(0, x - scroller.clientWidth / 2);
      scroller.scrollTop = Math.max(0, y - scroller.clientHeight / 2);
      rememberViewport();
      queueViewport();
    },
    [queueViewport, rememberViewport, scale],
  );

  function onPointerDown(event) {
    // Left button on empty diagram space only. The canvas surface stops this
    // event when its backend-geometry hit test finds a box or row; empty pixels
    // bubble here and retain the native scroll-backed drag-to-pan path.
    if (event.button !== 0 || event.target.closest("[role='button']")) return;
    const scroller = scrollRef.current;
    drag.current = {
      x: event.clientX,
      y: event.clientY,
      left: scroller.scrollLeft,
      top: scroller.scrollTop,
    };
    setPanning(true);
    scroller.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event) {
    if (!drag.current) return;
    const scroller = scrollRef.current;
    scroller.scrollLeft = drag.current.left - (event.clientX - drag.current.x);
    scroller.scrollTop = drag.current.top - (event.clientY - drag.current.y);
  }

  function endPan(event) {
    if (!drag.current) return;
    drag.current = null;
    setPanning(false);
    scrollRef.current?.releasePointerCapture?.(event.pointerId);
  }

  return (
    <div className="map-canvas">
      <div className="map-zoom" role="group" aria-label={`Zoom ${label}`}>
        <button
          type="button"
          aria-label="Zoom out"
          disabled={scale <= 0.05}
          onClick={() => setScale((value) => clampMapZoom(value / ZOOM_STEP))}
        >
          −
        </button>
        <button type="button" onClick={fit}>Fit</button>
        <button
          type="button"
          aria-label={`Reset zoom to 100%. Current zoom ${zoomPercent}%.`}
          title="Reset zoom to 100%"
          onClick={() => setScale(1)}
        >
          {zoomPercent}%
        </button>
        <button
          type="button"
          aria-label="Zoom in"
          disabled={scale >= 2.5}
          onClick={() => setScale((value) => clampMapZoom(value * ZOOM_STEP))}
        >
          +
        </button>
      </div>
      <div
        ref={scrollRef}
        className="map-scroll"
        data-panning={panning || undefined}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endPan}
        onPointerCancel={endPan}
        onScroll={() => {
          if (initialized.current) {
            rememberViewport();
            queueViewport();
          }
        }}
      >
        <div
          className="map-canvas__sized"
          style={{ width: contentWidth * scale, height: contentHeight * scale }}
        >
          {typeof children === "function"
            ? children({
                offsetX,
                revealPoint,
                scale,
                viewport: { ...viewport, offsetX, scale },
              })
            : children}
        </div>
      </div>
    </div>
  );
}

function CanvasMapSurface({
  ariaLabel,
  canvasClassName,
  drawScene,
  edgeCount,
  fallbackItem,
  hitTarget,
  itemForKey,
  itemIdentity,
  itemKey,
  itemLabel,
  itemPoint,
  itemReadout,
  keyboardTarget,
  onActivate,
  preferredKey,
  revealPoint,
  scene,
  viewport,
}) {
  const canvasRef = useRef(null);
  const pressedKeyRef = useRef(null);
  const optionBaseId = useId();
  const previousPreferredKeyRef = useRef(preferredKey);
  const [activeKey, setActiveKey] = useState(
    preferredKey ?? (fallbackItem ? itemKey(fallbackItem) : null),
  );
  const [hoverKey, setHoverKey] = useState(null);
  const [keyboardFocused, setKeyboardFocused] = useState(false);
  const [fontRevision, setFontRevision] = useState(0);
  const palette = useMemo(
    () => canvasMapPalette(getComputedStyle(document.documentElement)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    document.fonts?.ready?.then(() => {
      if (!cancelled) setFontRevision((value) => value + 1);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const preferredChanged = previousPreferredKeyRef.current !== preferredKey;
    previousPreferredKeyRef.current = preferredKey;
    setActiveKey((current) => {
      if (
        preferredChanged &&
        preferredKey !== null &&
        preferredKey !== undefined &&
        itemForKey(preferredKey)
      ) {
        return preferredKey;
      }
      if (itemForKey(current)) return current;
      if (
        preferredKey !== null &&
        preferredKey !== undefined &&
        itemForKey(preferredKey)
      ) {
        return preferredKey;
      }
      return fallbackItem ? itemKey(fallbackItem) : null;
    });
  }, [fallbackItem, itemForKey, itemKey, preferredKey]);

  const activeItem = activeKey === null ? null : itemForKey(activeKey);
  const hoverItem = hoverKey === null ? null : itemForKey(hoverKey);
  const activeLabel = activeItem ? itemLabel(activeItem) : "";
  const readoutItem = hoverItem ?? (keyboardFocused ? activeItem : null);
  const items = scene.kind === "architecture" ? scene.boxes : scene.rows;
  const activePosition = activeItem
    ? items.findIndex((item) => itemKey(item) === itemKey(activeItem)) + 1
    : 0;
  const activeIdentity = activeItem
    ? [...new TextEncoder().encode(String(itemIdentity(activeItem)))]
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("")
    : "";
  const optionId = activePosition && activeIdentity
    ? `${optionBaseId}-active-${activePosition}-${activeIdentity}`
    : undefined;

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || viewport.width < 1 || viewport.height < 1) return;
    const ratio = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    const pixelWidth = Math.max(1, Math.round(viewport.width * ratio));
    const pixelHeight = Math.max(1, Math.round(viewport.height * ratio));
    if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
    if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, viewport.width, viewport.height);
    const stats = drawScene(context, {
      activeKey,
      hoverKey,
      keyboardFocused,
      palette,
      viewport,
    });
    canvas.dataset.visibleItems = String(stats.visibleItems);
    canvas.dataset.visibleEdges = String(stats.visibleEdges);
  }, [
    activeKey,
    drawScene,
    fontRevision,
    hoverKey,
    keyboardFocused,
    palette,
    viewport,
  ]);

  function logicalPoint(event) {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x:
        (event.clientX - rect.left + viewport.scrollLeft - (viewport.offsetX || 0)) /
        viewport.scale,
      y: (event.clientY - rect.top + viewport.scrollTop) / viewport.scale,
    };
  }

  function reveal(item) {
    revealPoint(itemPoint(item), viewport.offsetX || 0);
  }

  function onKeyDown(event) {
    if (event.key === "Enter" || event.key === " ") {
      if (!activeItem) return;
      event.preventDefault();
      onActivate(activeItem);
      return;
    }
    if (!/^(ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Home|End)$/.test(event.key)) return;
    event.preventDefault();
    const target = keyboardTarget(scene, activeKey, event.key);
    if (!target) return;
    setActiveKey(itemKey(target));
    reveal(target);
  }

  function pointerTarget(event) {
    return hitTarget(scene, logicalPoint(event));
  }

  return (
    <div
      className={`map-canvas-surface ${canvasClassName}`}
      role="listbox"
      tabIndex={0}
      aria-label={`${ariaLabel}. Use arrow keys to move, Home or End to jump, and Enter or Space to open.`}
      aria-activedescendant={optionId}
      data-item-count={items.length}
      data-edge-count={edgeCount}
      onFocus={() => setKeyboardFocused(true)}
      onBlur={() => setKeyboardFocused(false)}
      onKeyDown={onKeyDown}
      style={{ width: viewport.width, height: viewport.height }}
    >
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        title={readoutItem ? itemReadout(readoutItem) : activeLabel}
        onPointerDown={(event) => {
          const target = pointerTarget(event);
          pressedKeyRef.current = target ? itemKey(target) : null;
          if (target) event.stopPropagation();
        }}
        onPointerMove={(event) => {
          if (event.buttons) return;
          const target = pointerTarget(event);
          setHoverKey(target ? itemKey(target) : null);
        }}
        onPointerLeave={() => setHoverKey(null)}
        onClick={(event) => {
          const target = pointerTarget(event);
          if (!target || itemKey(target) !== pressedKeyRef.current) return;
          setActiveKey(itemKey(target));
          onActivate(target);
        }}
      />
      {readoutItem ? (
        <span className="map-canvas-readout" aria-hidden="true">
          {itemReadout(readoutItem)}
        </span>
      ) : null}
      {activeItem ? (
        <span
          id={optionId}
          role="option"
          aria-selected="true"
          aria-posinset={activePosition}
          aria-setsize={items.length}
          className="map-canvas-active-option"
        >
          {activeLabel}
        </span>
      ) : null}
    </div>
  );
}

// Every coordinate here comes from GET /api/map. This file draws numbers and
// decides nothing: no layout, no ordering, no layering happens client-side.

export function MapView({
  data,
  mapTab,
  mode,
  communityIndexByRegion,
  selectedRegionId,
  hasEntrypointCandidates,
  // A project-level fact from the graph, not the map payload: the two
  // documents must not each carry their own copy of the same truth.
  unsupportedSources,
  importCycles,
  error,
  onSelectTab,
  onSelectRegion,
  onSelectNode,
  onRetry,
  viewportStore,
  languageFocusLabel = "",
  onClearLanguageFocus,
  // The drill-down copy for the selected module, given a row of its own in
  // this column. The galaxy can float the same element over its canvas; the
  // drawing below starts at this component's top-left corner, so here it must
  // occupy space rather than overlap the first boxes and tree rows.
  children,
}) {
  return (
    <section className="map-view" aria-label="Two-dimensional project map">
      <nav className="map-tabs" aria-label="Map view">
        <button
          type="button"
          aria-pressed={mapTab === "architecture"}
          onClick={() => onSelectTab("architecture")}
        >
          {mode === "easy" ? "How it fits together" : "Architecture"}
        </button>
        <button
          type="button"
          aria-pressed={mapTab === "workflow"}
          onClick={() => onSelectTab("workflow")}
        >
          {mode === "easy" ? "What runs first" : "Workflow"}
        </button>
      </nav>
      {children}
      {error ? (
        <div className="map-state" role="alert">
          <h2>The map did not load.</h2>
          <p>{error} The galaxy layer is unaffected.</p>
          <button className="check-primary" type="button" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : !data ? (
        <p className="map-loading" role="status">Laying out parser evidence…</p>
      ) : mapTab === "architecture" ? (
        <CanvasArchitectureMap
          architecture={data.architecture}
          mode={mode}
          communityIndexByRegion={communityIndexByRegion}
          selectedRegionId={selectedRegionId}
          hasEntrypointCandidates={hasEntrypointCandidates}
          onSelectRegion={onSelectRegion}
          viewportStore={viewportStore}
          languageFocusLabel={languageFocusLabel}
          onClearLanguageFocus={onClearLanguageFocus}
        />
      ) : (
        <CanvasWorkflowTree
          workflow={data.workflow}
          mode={mode}
          selectedRegionId={selectedRegionId}
          hasEntrypointCandidates={hasEntrypointCandidates}
          onSelectNode={onSelectNode}
          viewportStore={viewportStore}
          languageFocusLabel={languageFocusLabel}
          onClearLanguageFocus={onClearLanguageFocus}
        />
      )}
      {/* Easy mode lands here, not on the galaxy, so the layer this audience
          actually sees has to say what it could not read. Both tabs draw the
          same project, so the note belongs to the section, not to one tab. */}
      {unsupportedSummary(unsupportedSources, mode) ? (
        <p className="map-note">
          {unsupportedSummary(unsupportedSources, mode)}
          {mode === "easy"
            ? " — Codemble does not read that language yet, so none of it is drawn here."
            : " — outside every registered adapter; no structure is inferred for them."}
        </p>
      ) : null}
      {importCycleSummary(importCycles, mode) ? (
        <p className="map-note">{importCycleSummary(importCycles, mode)}</p>
      ) : null}
    </section>
  );
}

const boxKey = (box) => box.id;
const boxPoint = (box) => ({
  x: box.drawX + box.width / 2,
  y: box.drawY + box.height / 2,
});
const workflowKey = (row) => row.order;
const workflowPoint = (row) => ({ x: row.drawX + 8, y: row.drawY + 16 });

function CanvasArchitectureMap({
  architecture,
  mode,
  communityIndexByRegion,
  selectedRegionId,
  hasEntrypointCandidates,
  onSelectRegion,
  viewportStore,
  languageFocusLabel,
  onClearLanguageFocus,
}) {
  const unreachableSet = useMemo(
    () => new Set(architecture.unreachable),
    [architecture.unreachable],
  );
  const everyBoxUnreachable =
    architecture.boxes.length > 0 &&
    architecture.boxes.every((box) => unreachableSet.has(box.id));
  const scene = useMemo(
    () =>
      prepareArchitectureCanvas(architecture, {
        communityIndexByRegion,
      }),
    [architecture, communityIndexByRegion],
  );
  const focusBox =
    scene.boxById.get(selectedRegionId) ??
    scene.boxById.get(architecture.home) ??
    scene.boxes.find((box) => box.home) ??
    scene.boxes[0] ??
    null;
  const focusPoint = focusBox ? boxPoint(focusBox) : null;
  const itemForKey = useCallback((key) => scene.boxById.get(key) ?? null, [scene]);
  const drawScene = useCallback(
    (context, state) => {
      const stats = drawArchitectureCanvas(context, scene, state.viewport, state.palette, {
        activeId: state.activeKey,
        hoverId: state.hoverKey,
        keyboardFocused: state.keyboardFocused,
        mode,
        selectedId: selectedRegionId,
      });
      return { visibleItems: stats.visibleBoxes, visibleEdges: stats.visibleEdges };
    },
    [mode, scene, selectedRegionId],
  );
  const mapLabel = architecture.home
    ? `${architecture.boxes.length} modules in ${architecture.layer_count} import layers from Home`
    : `${architecture.boxes.length} modules in ${architecture.layer_count} import layers, measured from the modules nothing imports`;

  return (
    <>
      <MapCanvas
        contentWidth={architecture.width + MAP_CANVAS_GEOMETRY.architecturePadding * 2}
        contentHeight={architecture.height + MAP_CANVAS_GEOMETRY.architecturePadding * 2}
        label="the architecture map"
        viewKey={`architecture:${architecture.home ?? "none"}`}
        viewportStore={viewportStore}
        focusPoint={focusPoint}
        centerInline
      >
        {({ revealPoint, viewport }) => (
          <CanvasMapSurface
            ariaLabel={mapLabel}
            canvasClassName="architecture-map-canvas"
            drawScene={drawScene}
            edgeCount={scene.edges.length}
            fallbackItem={focusBox}
            hitTarget={hitArchitectureCanvas}
            itemForKey={itemForKey}
            itemIdentity={(box) => box.id}
            itemKey={boxKey}
            itemLabel={architectureBoxLabel}
            itemPoint={boxPoint}
            itemReadout={(box) => box.label}
            keyboardTarget={architectureKeyboardTarget}
            onActivate={(box) => onSelectRegion(box.id)}
            preferredKey={scene.boxById.has(selectedRegionId) ? selectedRegionId : focusBox?.id}
            revealPoint={revealPoint}
            scene={scene}
            viewport={viewport}
          />
        )}
      </MapCanvas>
      {architecture.home ? null : (
        <p className="map-note">
          No Home is selected, so these layers run from the modules nothing else
          imports rather than from your entrypoint. Both are read from your imports,
          not guessed.{" "}
          {hasEntrypointCandidates
            ? "Pick your starting point with “Change Home” to see the same modules layered by what the project runs first."
            : "This project has no parser-recognisable entrypoint, so there is no “runs first” order to layer by instead."}
        </p>
      )}
      {everyBoxUnreachable ? (
        <p className="map-note">
          {languageFocusLabel
            ? `Home is not written in ${languageFocusLabel}, so none of these ${architecture.boxes.length} ${architecture.boxes.length === 1 ? "module" : "modules"} has an import route to it. They are drawn in file order rather than layered by guesswork.`
            : `None of these ${architecture.boxes.length} ${architecture.boxes.length === 1 ? "module" : "modules"} has an import route from Home, so they are drawn in file order rather than layered by guesswork.`}{" "}
          {languageFocusLabel && onClearLanguageFocus ? (
            <button type="button" className="map-note__toggle" onClick={onClearLanguageFocus}>
              Show all languages
            </button>
          ) : null}
        </p>
      ) : architecture.unreachable.length ? (
        <p className="map-note">
          {architecture.unreachable.length}{" "}
          {architecture.unreachable.length === 1 ? "module has" : "modules have"} no import
          route from Home, so {architecture.unreachable.length === 1 ? "it sits" : "they sit"}
          {" "}in the bottom rows rather than being placed by guesswork. Every module remains
          searchable, drawable, and keyboard reachable.
        </p>
      ) : null}
    </>
  );
}

function CanvasWorkflowTree({
  workflow,
  mode,
  selectedRegionId,
  hasEntrypointCandidates,
  onSelectNode,
  viewportStore,
  languageFocusLabel,
  onClearLanguageFocus,
}) {
  if (workflow.root && workflow.nodes.length === 0) {
    return (
      <div className="map-state">
        <h2>
          {languageFocusLabel
            ? `Nothing in ${languageFocusLabel} runs from Home.`
            : "Nothing runs from Home yet."}
        </h2>
        <p>
          {languageFocusLabel
            ? `This tab follows what Home calls, and Home is not written in ${languageFocusLabel} — so no ${languageFocusLabel} structure appears on a parser-proven call route. The other tab still maps how these modules import each other.`
            : "This tab follows what Home calls, and the parser proved no call route out of it yet."}
        </p>
        {languageFocusLabel && onClearLanguageFocus ? (
          <button className="check-primary" type="button" onClick={onClearLanguageFocus}>
            Show all languages
          </button>
        ) : null}
      </div>
    );
  }
  if (!workflow.root) {
    return hasEntrypointCandidates ? (
      <div className="map-state">
        <h2>No Home is selected.</h2>
        <p>
          The workflow tree starts at your entrypoint. Pick Home and this tab will
          show what runs first, then what that calls.
        </p>
      </div>
    ) : (
      <div className="map-state">
        <h2>No “runs first” order to show.</h2>
        <p>
          This project has no parser-recognisable entrypoint — nothing here declares
          a startup structure Codemble recognises, and it will not guess one. The
          other tab still maps how your modules import each other.
        </p>
      </div>
    );
  }
  return (
    <CanvasWorkflowDiagram
      workflow={workflow}
      mode={mode}
      selectedRegionId={selectedRegionId}
      onSelectNode={onSelectNode}
      viewportStore={viewportStore}
    />
  );
}

function CanvasWorkflowDiagram({
  workflow,
  mode,
  selectedRegionId,
  onSelectNode,
  viewportStore,
}) {
  const scene = useMemo(() => prepareWorkflowCanvas(workflow), [workflow]);
  const selectedRow = scene.rows.find((row) => row.region === selectedRegionId) ?? null;
  const focusRow =
    selectedRow ?? scene.rows.find((row) => row.id === workflow.root) ?? scene.rows[0] ?? null;
  const focusPoint = focusRow ? workflowPoint(focusRow) : null;
  const itemForKey = useCallback(
    (key) => scene.rowByOrder.get(Number(key)) ?? null,
    [scene],
  );
  const drawScene = useCallback(
    (context, state) => {
      const stats = drawWorkflowCanvas(context, scene, state.viewport, state.palette, {
        activeOrder: state.activeKey,
        hoverOrder: state.hoverKey,
        keyboardFocused: state.keyboardFocused,
        mode,
        selectedRegionId,
      });
      return { visibleItems: stats.visibleRows, visibleEdges: stats.visibleEdges };
    },
    [mode, scene, selectedRegionId],
  );
  return (
    <>
      <MapCanvas
        contentWidth={workflow.width + MAP_CANVAS_GEOMETRY.workflowPadding * 2}
        contentHeight={workflow.height + MAP_CANVAS_GEOMETRY.workflowPadding * 2}
        label="the workflow tree"
        viewKey={`workflow:${workflow.root}`}
        viewportStore={viewportStore}
        focusPoint={focusPoint}
      >
        {({ revealPoint, viewport }) => (
          <CanvasMapSurface
            ariaLabel={`Call tree from ${workflow.root}, ${workflow.nodes.length} steps deep to ${workflow.depth_count} levels`}
            canvasClassName="workflow-map-canvas"
            drawScene={drawScene}
            edgeCount={scene.edges.length}
            fallbackItem={focusRow}
            hitTarget={hitWorkflowCanvas}
            itemForKey={itemForKey}
            itemIdentity={(row) => `${row.order}:${row.id}:${row.file}:${row.lineno}`}
            itemKey={workflowKey}
            itemLabel={workflowRowLabel}
            itemPoint={workflowPoint}
            itemReadout={(row) => `${row.label} · ${row.file}:${row.lineno}`}
            keyboardTarget={workflowKeyboardTarget}
            onActivate={(row) => onSelectNode(row.id)}
            preferredKey={focusRow?.order}
            revealPoint={revealPoint}
            scene={scene}
            viewport={viewport}
          />
        )}
      </MapCanvas>
      {workflow.unreachable.length ? (
        <p className="map-note">
          {workflow.unreachable.length}{" "}
          {workflow.unreachable.length === 1 ? "structure is" : "structures are"} never
          reached from Home by a parser-proven call. They are listed as unreached rather
          than attached to the tree by guesswork.
        </p>
      ) : null}
    </>
  );
}
