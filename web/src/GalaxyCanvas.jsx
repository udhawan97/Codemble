import ForceGraph3D from "3d-force-graph";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { attachBloom, prefersReducedMotion, runNebulaDawn } from "./galaxyEffects.js";
import { createDressing, createStarfield, seedFromHashes } from "./galaxyMaterials.js";
import { LEVELS, galaxyData, linkLabel, nebulaTintKey, nodeLabel, systemData } from "./graphData.js";

const CAMERA_DURATION = 420;
const NODE_REL_SIZE = 1.6;
// Bounded orbit, per the 2026-07-21 Decision Log entry. Free flight stays a
// Non-Goal: panning is off, so the camera can only ever swing around the
// current subject and never translate away from it. These clamps are what make
// "you cannot get lost" still true once the mouse can move the view -- each
// level's default distance sits inside its own range, so arriving somewhere
// never fights the clamp.
const CAMERA_BOUNDS = {
  GALAXY: { min: 120, max: 640 },
  SYSTEM: { min: 55, max: 320 },
  STUDY: { min: 22, max: 170 },
};
// Never straight down and never edge-on: at 0 the galaxy plane collapses to a
// line, and past ~86 degrees the learner is under the plane looking up at a sky
// that reads as a different project.
const MIN_POLAR_ANGLE = 0.16;
const MAX_POLAR_ANGLE = 1.5;
// Label declutter. Recomputed on a timer rather than per frame: at 169 systems
// this is a projection plus a sort, and doing it 60 times a second to reprint
// text that has not moved is how a readable sky becomes a slow one.
const LABEL_TICK_MS = 110;
const LABEL_CELL_PX = { width: 132, height: 30 };
const LABEL_BUDGET = { far: 14, near: 44 };
// Slots a name may take around its star, in plate-heights above it, tried in
// this order. A star is a point feature, so its name can sit anywhere nearby;
// offering only the resting slot threw away most of the sky's capacity, since
// at galaxy zoom the systems cluster and nearly every plate lost to the one
// already sitting above it. Kept vertical so a name is never ambiguous about
// which star it belongs to.
const LABEL_SLOTS = [0, -1, 1, -2, 2];
const LABEL_SLOT_GAP_PX = 4;
// 3d-force-graph mutates the scene on its own render tick, not the React
// commit that flips `level` to GALAXY, so the newly-lit system's group may
// not exist for a frame or two. A handful of retry frames covers that
// without hanging forever if the target genuinely never appears (e.g. the
// region is hidden by the current language focus).
const MAX_DAWN_RETRY_FRAMES = 6;

export function GalaxyCanvas({
  graph,
  level,
  region,
  selectedNode,
  hoverNodeId,
  pendingDawnRegionId,
  revealedRegionIds,
  mode,
  onHoverNode,
  onAdvance,
  onRetreat,
  onDawnConsumed,
}) {
  const hostRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const advanceRef = useRef(onAdvance);
  const retreatRef = useRef(onRetreat);
  const hoverRef = useRef(onHoverNode);
  const pendingDawnRef = useRef(pendingDawnRegionId);
  const onDawnConsumedRef = useRef(onDawnConsumed);
  const dawnStartedRef = useRef(null);
  const highlightRef = useRef({ activeId: null, neighborIds: new Set() });
  const dressingRef = useRef(null);
  const bloomRef = useRef(null);
  const focusedIdRef = useRef(null);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [renderError, setRenderError] = useState("");
  const palette = useMemo(readPalette, []);
  const reducedMotion = useMemo(prefersReducedMotion, []);
  // The seed's *value*, not the identity of the object it came from: every
  // session commit rebuilds file_hashes while a language focus is active
  // (learnerSession.js deriveSnapshot), and depending on that identity rebuilt
  // the whole starfield on unrelated state changes.
  const starfieldSeed = seedFromHashes(graph.file_hashes);
  const data = useMemo(() => {
    if (level === LEVELS.GALAXY) return galaxyData(graph, palette, revealedRegionIds);
    return systemData(graph, region?.id, palette, {
      selectedId: selectedNode?.id,
    });
  }, [graph, level, palette, region?.id, revealedRegionIds, selectedNode?.id]);

  useEffect(() => {
    advanceRef.current = onAdvance;
    retreatRef.current = onRetreat;
    hoverRef.current = onHoverNode;
    pendingDawnRef.current = pendingDawnRegionId;
    onDawnConsumedRef.current = onDawnConsumed;
  }, [onAdvance, onRetreat, onHoverNode, pendingDawnRegionId, onDawnConsumed]);

  function nodeColor(node) {
    const { activeId, neighborIds } = highlightRef.current;
    if (!activeId) return node.color;
    if (node.id === activeId) return palette.orbit;
    return neighborIds.has(node.id) ? node.color : palette.faded;
  }

  function linkColor(link) {
    // Study level: a link not touching the selection recedes regardless of
    // hover, so the selection's own call connections stay the subject. It
    // recedes to `faded`, the token that exists for exactly that -- painting a
    // *certain* edge in the uncertainty colour claimed something the parser
    // never said, and now that uncertainty is legible it would also have made
    // the receding links the brightest thing at study level.
    if (link.focusDim) return palette.faded;
    const { activeId, neighborIds } = highlightRef.current;
    const base = link.certain ? palette.route : palette.routePossible;
    if (!activeId) return base;
    const source = linkEndId(link.source);
    const target = linkEndId(link.target);
    if (source === activeId || target === activeId) return palette.orbit;
    return neighborIds.has(source) && neighborIds.has(target) ? base : palette.faded;
  }

  function linkWidth(link) {
    if (link.focusDim) return 0.4;
    const { activeId } = highlightRef.current;
    const base = Math.min(2.2, 0.45 + (link.weight ?? 1) * 0.25);
    if (!activeId) return base;
    const source = linkEndId(link.source);
    const target = linkEndId(link.target);
    return source === activeId || target === activeId ? base + 0.9 : base;
  }

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    const probe = document.createElement("canvas");
    if (!probe.getContext("webgl2") && !probe.getContext("webgl")) {
      setRenderError("Codemble needs WebGL to draw your galaxy. Enable WebGL and reload.");
      return undefined;
    }

    try {
      const dressing = createDressing(palette);
      dressingRef.current = dressing;
      // controlType is construction-time only in this library, so orbit has to
      // be chosen here rather than toggled later.
      const renderer = ForceGraph3D({ controlType: "orbit" })(host)
        .backgroundColor(palette.ground)
        .showNavInfo(false)
        .enableNavigationControls(true)
        .warmupTicks(0)
        .cooldownTicks(0)
        .nodeId("id")
        .nodeLabel(nodeLabel)
        .nodeVal("val")
        .nodeColor(nodeColor)
        .nodeRelSize(NODE_REL_SIZE)
        .nodeResolution(8)
        // Study level no longer dims the whole scene: focusDim removes the glow
        // from unconnected nodes instead, so the selection's connections stay
        // visible while everything else recedes.
        .nodeOpacity(0.82)
        .nodeThreeObject((node) => makeMarker(node, palette, dressing, focusedIdRef.current))
        .nodeThreeObjectExtend(true)
        .linkColor(linkColor)
        .linkLabel(linkLabel)
        .linkOpacity(0.32)
        .linkWidth(linkWidth)
        .linkCurvature(0.12)
        .linkVisibility((link) => !(mode === "easy" && link.focusDim))
        .linkHoverPrecision(4)
        .linkDirectionalArrowRelPos(1)
        .linkDirectionalArrowColor(linkColor)
        // Particles drift only on CERTAIN call edges. A possible call stays
        // still, so motion can never imply proof -- and reduced motion means no
        // continuous drift at all, the same contract the nebula dawn honours.
        // Certainty keeps a colour channel either way, so nothing is lost.
        .linkDirectionalParticles((link) =>
          link.kind === "call" && link.certain && !link.focusDim && !reducedMotion ? 2 : 0,
        )
        .linkDirectionalParticleSpeed(0.006)
        .linkDirectionalParticleWidth(1.1)
        .linkDirectionalParticleColor(() => palette.orbit)
        .onNodeHover((node) => {
          host.style.cursor = node ? "pointer" : "default";
          hoverRef.current(node?.id ?? null);
        })
        .onNodeClick((node) => advanceRef.current(node));
      const hideNavigationHint = requestAnimationFrame(() => {
        host.querySelector(".scene-nav-info")?.remove();
      });

      // The bounded half of "bounded orbit". Panning is the degree of freedom
      // that lets a learner drift into empty space with nothing on screen to
      // navigate back by, so it is the one that stays off; rotation and zoom
      // are clamped rather than removed. Damping is safe because the library
      // calls controls.update() every frame.
      const controls = renderer.controls();
      controls.enablePan = false;
      controls.enableDamping = true;
      controls.dampingFactor = 0.12;
      controls.rotateSpeed = 0.55;
      controls.zoomSpeed = 0.7;
      controls.minPolarAngle = MIN_POLAR_ANGLE;
      controls.maxPolarAngle = MAX_POLAR_ANGLE;
      controlsRef.current = controls;

      bloomRef.current = attachBloom(renderer);
      rendererRef.current = renderer;

      const resize = new ResizeObserver(([entry]) => {
        renderer.width(entry.contentRect.width).height(entry.contentRect.height);
      });
      resize.observe(host);
      return () => {
        resize.disconnect();
        cancelAnimationFrame(hideNavigationHint);
        renderer.pauseAnimation();
        bloomRef.current?.dispose();
        bloomRef.current = null;
        // The only thing that frees the WebGL context: _destructor empties the
        // scene and disposes the controls, the renderer and the composer
        // (three-render-objects.mjs:466-472). Without it, every Galaxy<->Map
        // switch and every Star chart visit stranded a live context, and after
        // ~16 the browser force-lost the oldest ones -- the galaxy went blank
        // with nothing in the console to say why.
        renderer._destructor();
        // After _destructor, not before: it empties the scene, which hands the
        // shared halo/nebula resources to three-forcegraph's deallocator. That
        // is a no-op by design (see galaxyMaterials), so this is the real free.
        dressing.dispose();
        dressingRef.current = null;
        controlsRef.current = null;
        host.replaceChildren();
        rendererRef.current = null;
      };
    } catch (error) {
      setRenderError(`The galaxy could not start: ${error.message}`);
      return undefined;
    }
  }, [palette]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer
      .nodeResolution(data.nodes.length >= 900 ? 4 : 8)
      .linkVisibility((link) => !(mode === "easy" && link.focusDim))
      // Arrows only where an edge means a direction the learner can act on.
      .linkDirectionalArrowLength(level === LEVELS.GALAXY ? 0 : 3.2)
      .graphData(data);
    // Re-clamp before the move, so the tween never lands outside the range it
    // is about to be held to. cameraPosition's lookAt writes controls.target
    // directly now that controls are enabled (three-render-objects setLookAt),
    // which is what re-anchors the orbit on every level change for free.
    const bounds = CAMERA_BOUNDS[level] ?? CAMERA_BOUNDS.GALAXY;
    if (controlsRef.current) {
      controlsRef.current.minDistance = bounds.min;
      controlsRef.current.maxDistance = bounds.max;
    }
    if (level === LEVELS.GALAXY) {
      renderer.cameraPosition({ x: 0, y: 105, z: 310 }, { x: 0, y: 0, z: 0 }, CAMERA_DURATION);
    } else {
      renderer.cameraPosition({ x: 0, y: 52, z: 150 }, { x: 0, y: 0, z: 0 }, CAMERA_DURATION);
    }
    setFocusedIndex(0);
  }, [data, level, mode]);

  useEffect(() => {
    focusedIdRef.current = data.nodes[focusedIndex]?.id ?? null;
    rendererRef.current?.refresh();
  }, [data.nodes, focusedIndex]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return undefined;
    const scene = renderer.scene();
    const previous = scene.getObjectByName("codemble-starfield");
    if (previous) {
      scene.remove(previous);
      previous.geometry.dispose();
      previous.material.dispose();
    }
    // Seeded by the project's own file hashes: same code, same sky, every run.
    const starfield = createStarfield(starfieldSeed, palette);
    scene.add(starfield);
    return () => {
      scene.remove(starfield);
      starfield.geometry.dispose();
      starfield.material.dispose();
    };
  }, [starfieldSeed, palette]);

  // Keyed on `level` (not pendingDawnRegionId) so a normal galaxy-level
  // re-render never re-triggers this: the region to play is read from a ref
  // instead. That matters because this effect consumes the pending signal
  // itself -- if `pendingDawnRegionId` were a dependency, clearing it would
  // change that dependency and tear this same effect straight back down,
  // cancelling the dawn a frame after starting it. dawnStartedRef then makes
  // "exactly once" airtight even before that consume round-trip lands: a
  // second GALAXY entry for the same region id is a guaranteed no-op.
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || level !== LEVELS.GALAXY) return undefined;
    const regionId = pendingDawnRef.current;
    if (!regionId || dawnStartedRef.current === regionId) return undefined;
    dawnStartedRef.current = regionId;
    onDawnConsumedRef.current?.(regionId);

    let cancelled = false;
    let stopDawn = () => {};
    // requestAnimationFrame always calls its callback with a timestamp, so a
    // default parameter (`frame = 0`) never applies on the first tick -- the
    // retry count must be threaded through explicitly instead, or the very
    // first check reads as "budget already exhausted" and the retry never
    // actually retries.
    const attempt = (frame) => {
      if (cancelled) return;
      const scene = renderer.scene();
      const found = Boolean(scene.getObjectByName(`codemble-system-${regionId}`));
      if (found || frame >= MAX_DAWN_RETRY_FRAMES) {
        stopDawn = runNebulaDawn({ scene, regionId, palette });
        return;
      }
      frameHandle = requestAnimationFrame(() => attempt(frame + 1));
    };
    let frameHandle = requestAnimationFrame(() => attempt(0));

    return () => {
      cancelled = true;
      cancelAnimationFrame(frameHandle);
      stopDawn();
    };
  }, [level, palette]);

  useEffect(() => {
    // At study level the selection is the subject even without a pointer, so
    // its connections stay legible instead of the scene fading to 0.16.
    const activeId = hoverNodeId ?? (level === LEVELS.STUDY ? selectedNode?.id ?? null : null);
    const neighborIds = new Set();
    if (activeId) {
      for (const link of data.links) {
        const source = linkEndId(link.source);
        const target = linkEndId(link.target);
        if (source === activeId) neighborIds.add(target);
        if (target === activeId) neighborIds.add(source);
      }
    }
    highlightRef.current = { activeId, neighborIds };
    const renderer = rendererRef.current;
    if (!renderer) return;
    // Re-setting an accessor to itself is the library's own refresh idiom.
    renderer
      .nodeColor(renderer.nodeColor())
      .linkColor(renderer.linkColor())
      .linkWidth(renderer.linkWidth())
      .linkDirectionalArrowColor(renderer.linkDirectionalArrowColor());
  }, [data, hoverNodeId, level, selectedNode?.id]);

  // Label declutter. Ranking is graph truth (Home, then proven, then how many
  // places call it); only the budget and the collision test depend on the
  // camera. Nothing here decides what a node *is* -- it decides how many names
  // fit on screen before they start overlapping each other.
  const labelRank = useMemo(() => {
    const ranked = data.nodes
      .filter((node) => node.label)
      .map((node) => ({
        id: node.id,
        weight:
          (node.home ? 3_000_000 : 0) +
          (node.understood ? 1_000_000 : 0) +
          (node.centrality ?? 0) * 1000,
        nodeId: node.id,
      }))
      .sort((left, right) => right.weight - left.weight || left.nodeId.localeCompare(right.nodeId));
    return new Map(ranked.map((entry, index) => [entry.id, index]));
  }, [data.nodes]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || !labelRank.size) return undefined;
    const projected = new THREE.Vector3();
    const origin = new THREE.Vector3();

    function relabel() {
      // Read from the live scene rather than a map maintained alongside it.
      // three-forcegraph re-runs nodeThreeObject on every refresh(), not only
      // when the data changes, so a map accumulated a second sprite per node
      // while the detached originals kept a non-null `parent` and sailed past
      // the obvious guard -- those invisible leftovers then ate the whole
      // budget and claimed the cells, leaving exactly one name on screen.
      // A list derived per tick cannot go stale.
      const sprites = [];
      renderer.scene().traverse((object) => {
        if (object.userData?.codembleLabel) sprites.push(object);
      });
      if (!sprites.length) return;
      const camera = renderer.camera();
      const controls = controlsRef.current;
      const width = renderer.width();
      const height = renderer.height();
      const bounds = CAMERA_BOUNDS[level] ?? CAMERA_BOUNDS.GALAXY;
      const distance = controls
        ? camera.position.distanceTo(controls.target)
        : camera.position.length();
      // Closer camera, more names: at the near clamp the sky is sparse enough
      // on screen to carry them, at the far clamp it is not.
      const span = Math.max(1, bounds.max - bounds.min);
      const nearness = 1 - Math.min(1, Math.max(0, (distance - bounds.min) / span));
      const budget = Math.round(
        LABEL_BUDGET.far + (LABEL_BUDGET.near - LABEL_BUDGET.far) * nearness,
      );

      // Screen position of a point `offsetY` world-units above the node, or
      // null when it is behind the camera or off-screen.
      function place(origin, offsetY) {
        projected.set(origin.x, origin.y + offsetY, origin.z).project(camera);
        if (projected.z > 1) return null;
        const screenX = (projected.x * 0.5 + 0.5) * width;
        const screenY = (-projected.y * 0.5 + 0.5) * height;
        if (screenX < 0 || screenX > width || screenY < 0 || screenY > height) return null;
        return { screenX, screenY };
      }

      const candidates = [];
      for (const sprite of sprites) {
        const nodeId = sprite.userData.nodeId;
        sprite.visible = false;
        const star = sprite.parent;
        if (!star) continue;
        star.getWorldPosition(origin);
        const base = sprite.userData.baseOffsetY ?? 0;
        const anchor = place(origin, base);
        if (!anchor) continue;
        // How far one screen pixel is in world units at this node's depth,
        // measured rather than assumed: the alternative slots below are
        // expressed in plate-heights, and a fixed world offset would be a
        // different number of pixels for a near star than a far one.
        const oneUnit = place(origin, base + 1);
        const pixelsPerUnit = oneUnit ? Math.abs(oneUnit.screenY - anchor.screenY) : 0;
        candidates.push({
          sprite,
          origin: origin.clone(),
          base,
          pixelsPerUnit,
          anchor,
          // How wide this plate actually is on screen. Reserving one fixed cell
          // per label regardless of its text let `parse_progress.py` overlap
          // three neighbours while still passing the collision test.
          halfWidth: ((sprite.userData.screenWidthFraction ?? 0.14) * height) / 2,
          halfHeight: ((sprite.userData.screenHeightFraction ?? 0.034) * height) / 2,
          // Hover always wins a slot: pointing at something and being told
          // nothing is the exact failure labels exist to fix.
          rank: nodeId === hoverNodeId ? -1 : labelRank.get(nodeId) ?? Infinity,
        });
      }
      candidates.sort((left, right) => left.rank - right.rank);

      // Highest-ranked plate claims every cell its rectangle actually covers;
      // a later, lower-ranked plate overlapping any of them is dropped. Both
      // axes matter: claiming a single cell let a wide name cover three
      // neighbours, and claiming only a row of cells let two plates that
      // straddle the same horizontal boundary still collide.
      const taken = new Set();
      let shown = 0;
      for (const candidate of candidates) {
        if (shown >= budget) break;
        // Try the resting slot first, then alternates around the star. A star
        // is a point feature and a name can sit anywhere near it, so testing
        // only one spot threw away most of the sky's capacity: at galaxy zoom
        // the systems cluster tightly and nearly every plate lost to the one
        // above it, leaving a handful of names for twenty-odd charted systems.
        const step = candidate.pixelsPerUnit
          ? (candidate.halfHeight * 2 + LABEL_SLOT_GAP_PX) / candidate.pixelsPerUnit
          : 0;
        let placed = null;
        for (const slot of LABEL_SLOTS) {
          const offset = slot * step;
          const at = slot === 0 ? candidate.anchor : place(candidate.origin, candidate.base + offset);
          if (!at) continue;
          const cells = coveredCells(at, candidate);
          if (cells.some((cell) => taken.has(cell))) continue;
          placed = { cells, offset };
          break;
        }
        if (!placed) continue;
        for (const cell of placed.cells) taken.add(cell);
        candidate.sprite.position.y = candidate.base + placed.offset;
        candidate.sprite.visible = true;
        shown += 1;
      }
    }

    // Wrapped because this runs on a timer: an exception mid-pass leaves every
    // plate in the hidden state the pass starts from, so the whole sky silently
    // loses its names with nothing on screen to say why. Reporting it and
    // stopping the timer turns that into something diagnosable.
    let timer = null;
    function tick() {
      try {
        relabel();
      } catch (error) {
        if (timer !== null) clearInterval(timer);
        console.error("Codemble: label declutter failed, names disabled", error);
      }
    }
    tick();
    timer = setInterval(tick, LABEL_TICK_MS);
    return () => clearInterval(timer);
  }, [data, hoverNodeId, labelRank, level]);

  useEffect(() => {
    const benchmarking = new URLSearchParams(window.location.search).has("benchmark");
    if (!benchmarking || data.nodes.length < 900) return undefined;
    document.documentElement.removeAttribute("data-codemble-fps");
    const begin = setTimeout(() => {
      const graphRenderer = rendererRef.current;
      if (!graphRenderer) return;
      const webglRenderer = graphRenderer.renderer();
      const composer = graphRenderer.postProcessingComposer();
      const frameCount = 60;
      const startedAt = performance.now();
      for (let frame = 0; frame < frameCount; frame += 1) {
        // Must go through the composer: rendering the scene directly would skip
        // the bloom pass and report a framerate the learner never sees.
        composer.render();
      }
      webglRenderer.getContext().finish();
      const elapsed = performance.now() - startedAt;
      document.documentElement.dataset.codembleFps = ((frameCount * 1000) / elapsed).toFixed(1);
    }, 1000);
    return () => clearTimeout(begin);
  }, [data.nodes.length]);

  useEffect(() => {
    if (!selectedNode || !rendererRef.current || level !== LEVELS.STUDY) return;
    rendererRef.current.cameraPosition(
      { x: selectedNode.system_x + 20, y: selectedNode.system_y + 15, z: selectedNode.system_z + 42 },
      { x: selectedNode.system_x, y: selectedNode.system_y, z: selectedNode.system_z },
      CAMERA_DURATION,
    );
  }, [level, selectedNode]);

  const focusedNode = data.nodes[focusedIndex] ?? null;

  function handleKeyDown(event) {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      setFocusedIndex((index) => (index + 1) % Math.max(1, data.nodes.length));
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      setFocusedIndex((index) => (index - 1 + data.nodes.length) % Math.max(1, data.nodes.length));
    } else if (event.key === "Enter" && focusedNode) {
      event.preventDefault();
      advanceRef.current(focusedNode);
    } else if (event.key === "Escape" || event.key === "Backspace") {
      event.preventDefault();
      retreatRef.current();
    }
  }

  // The wheel is the orbit's zoom now, so it no longer changes level: two
  // meanings on one gesture meant every attempt to look closer also teleported
  // the learner somewhere else. Level changes are click, Enter, Escape and the
  // breadcrumb, all of which say what they will do before they do it.

  if (renderError) {
    return (
      <section className="webgl-error" role="alert">
        <h1>The sky could not open.</h1>
        <p>{renderError}</p>
        {/* The 2D layer draws from the same parser graph without WebGL, and its
            switch is in the header rail one step away -- cheaper and kinder than
            leaving a stranded learner with only "enable WebGL and reload". */}
        <p>
          The {mode === "easy" ? "Diagram" : "Map"} layer works without WebGL —
          switch to it at the top of the window to explore the same code.
        </p>
      </section>
    );
  }

  return (
    <div
      className="galaxy-frame"
      role="application"
      tabIndex="0"
      aria-label={`Codemble ${level.toLowerCase()} view. Drag to orbit, scroll to zoom. Use arrow keys to choose a node and Enter to move closer.`}
      onKeyDown={handleKeyDown}
    >
      <div ref={hostRef} className="galaxy-canvas" aria-hidden="true" />
      {focusedNode ? (
        <output className="keyboard-focus" aria-live="polite">
          {nodeLabel(focusedNode)}
        </output>
      ) : null}
    </div>
  );
}

function makeMarker(node, palette, dressing, focusedId) {
  const group = new THREE.Group();
  group.name = node.kind === "region" ? `codemble-system-${node.id}` : `codemble-node-${node.id}`;
  const radius = Math.cbrt(node.val ?? 1) * NODE_REL_SIZE;
  // An uncharted region is drawn, not deleted: it keeps its true position and
  // stays clickable, so the sky never misreports how large the project is. It
  // simply carries no glow, no fog and no name until the learner reaches it.
  const uncharted = node.charted === false;
  // Dimmed nodes keep their true colour and lose their glow. Dimming by
  // removing light rather than shifting hue keeps a lit star recognisably lit.
  if (!node.focusDim && !uncharted) group.add(dressing.halo(node, radius));
  if (node.kind === "region" && !uncharted) {
    const tint = nebulaTintKey(node.language);
    if (tint) group.add(dressing.nebula(palette[tint], radius * 14));
  }
  if (node.label) {
    const plate = dressing.label(node.label, radius);
    // The declutter pass finds plates by walking the live scene, so the id it
    // needs to rank them by has to travel on the sprite itself.
    plate.userData.nodeId = node.id;
    group.add(plate);
  }
  if (node.home) {
    const homeRing = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 1.7, Math.max(0.18, radius * 0.07), 8, 36),
      new THREE.MeshBasicMaterial({ color: palette.home }),
    );
    homeRing.rotation.x = Math.PI / 2.8;
    group.add(homeRing);
  }
  if (node.selected) {
    const selectedRing = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 2.1, Math.max(0.16, radius * 0.05), 6, 24),
      new THREE.MeshBasicMaterial({ color: palette.orbit }),
    );
    selectedRing.rotation.x = Math.PI / 2.8;
    group.add(selectedRing);
  }
  if (node.id === focusedId) group.add(dressing.reticle(radius));
  return group;
}

// Which screen cells a plate covers when its centre sits at `at`. Both axes
// matter: claiming a single cell let a wide name cover three neighbours, and
// claiming only a row let two plates straddling the same boundary collide.
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

// The force layout swaps link endpoints from ids to node objects in place.
function linkEndId(end) {
  return typeof end === "object" && end !== null ? end.id : end;
}

// A custom property hands back its authored text, so a token written as
// color-mix() reaches WebGL as a string three.js cannot parse and renders black.
// Painting it once turns any CSS colour the browser understands into plain rgb.
function toRenderableColor(value) {
  const context = document.createElement("canvas").getContext("2d");
  context.fillStyle = "#000000";
  context.fillStyle = value;
  context.fillRect(0, 0, 1, 1);
  const [red, green, blue] = context.getImageData(0, 0, 1, 1).data;
  return `rgb(${red}, ${green}, ${blue})`;
}

function readPalette() {
  const styles = getComputedStyle(document.documentElement);
  const value = (token) =>
    toRenderableColor(styles.getPropertyValue(token).trim());
  return Object.freeze({
    ground: value("--cm-ground"),
    home: value("--cm-ink"),
    orbit: value("--cm-orbit"),
    // The unlit ramp tops out at --cm-ink-2 so understanding stays the
    // brightest thing in the sky; a lit star uses --cm-star-high above it.
    nodeBright: value("--cm-ink-2"),
    node: value("--cm-ink-3"),
    nodeDim: value("--cm-node-unlit"),
    route: value("--cm-hairline"),
    routePossible: value("--cm-route-possible"),
    // Everything outside the current selection or hover recedes to this;
    // it stays a plain value so readPalette can hand WebGL real rgb().
    faded: value("--cm-hairline-soft"),
    star: value("--cm-star-high"),
    starHalo: value("--cm-star-halo"),
    nebPython: value("--cm-neb-python"),
    nebJs: value("--cm-neb-js"),
    nebTs: value("--cm-neb-ts"),
    // Read raw, NOT through toRenderableColor: these two are painted with a 2D
    // canvas context, which understands any CSS colour including the plate's
    // alpha. Flattening them to rgb() the way WebGL requires would silently
    // make the label plate opaque.
    labelPlate: styles.getPropertyValue("--cm-label-plate").trim(),
    labelInk: styles.getPropertyValue("--cm-label-ink").trim(),
  });
}
