import ForceGraph3D from "3d-force-graph";
import * as THREE from "three";

import { createBody, createBodyGeometry, createBodySpin } from "./celestialBodies.js";
import { measureCanvasOcclusion } from "./canvasOcclusion.js";
import { runDawnSequence } from "./dawnSequence.js";
import { attachBloom } from "./galaxyEffects.js";
import {
  CAMERA_DURATION,
  cameraBoundsFor,
  frameLevel,
  frameStudy,
  viewportAspect,
} from "./galaxyView.js";
import {
  LEVELS,
  NODE_REL_SIZE,
  highlightColor,
  highlightLinkColor,
  isUncharted,
  linkLabel,
  nodeLabel,
  nodeRadius,
} from "./graphData.js";
import {
  createDressing,
  createGalacticGlow,
  createStarfield,
} from "./galaxyMaterials.js";
import { createNameAtlas } from "./nameAtlas.js";
import { guardOrbitPointerState } from "./orbitPointerGuard.js";
import {
  createPossibleRoute,
  refreshPossibleRoutes,
  updateRouteGeometry,
} from "./possibleRoutes.js";
import {
  createSystemOrbitGuides,
  disposeSystemOrbitGuides,
} from "./systemOrbits.js";

const MIN_POLAR_ANGLE = 0.16;
const MAX_POLAR_ANGLE = 1.5;
const LABEL_TICK_MS = 110;
const MAX_DAWN_RETRY_FRAMES = 6;

const defaultClock = Object.freeze({
  requestFrame: (callback) => requestAnimationFrame(callback),
  cancelFrame: (handle) => cancelAnimationFrame(handle),
  setInterval: (callback, delay) => setInterval(callback, delay),
  clearInterval: (handle) => clearInterval(handle),
  setTimeout: (callback, delay) => setTimeout(callback, delay),
  clearTimeout: (handle) => clearTimeout(handle),
  now: () => performance.now(),
});

const defaultDependencies = Object.freeze({
  rendererFactory: (host) => ForceGraph3D({ controlType: "orbit" })(host),
  assertWebGL() {
    const probe = document.createElement("canvas");
    if (!probe.getContext("webgl2") && !probe.getContext("webgl")) {
      throw new Error("Codemble needs WebGL to draw your galaxy. Enable WebGL and reload.");
    }
  },
  ResizeObserver: globalThis.ResizeObserver,
  createDressing,
  createBodyGeometry,
  createBodySpin,
  createSystemOrbitGuides,
  disposeSystemOrbitGuides,
  createStarfield,
  createGalacticGlow,
  attachBloom,
  guardOrbitPointerState,
  runDawnSequence,
  createNameAtlas,
  documentElement: () => document.documentElement,
  search: () => window.location.search,
});

/**
 * Own the complete lifetime of one galaxy renderer.
 *
 * React supplies render-ready snapshots. This module owns every mutable scene,
 * timer, listener, and WebGL resource behind a two-operation interface.
 */
export function createGalaxyRuntime({
  host,
  palette,
  reducedMotion,
  onHoverNode,
  onAdvance,
  onDawnConsumed,
  dependencies = {},
  clock = defaultClock,
}) {
  const deps = { ...defaultDependencies, ...dependencies };
  let closed = false;
  let snapshot = null;
  let renderer = null;
  let controls = null;
  let dressing = null;
  let bodyGeometry = null;
  let bloom = null;
  let resizeObserver = null;
  let removePointerGuard = () => {};
  let removeControlsListener = () => {};
  let hideNavigationFrame = null;
  let reframe = null;
  let userFramed = false;
  let focusedNodeId = null;
  let highlight = { activeId: null, neighborIds: new Set() };
  let sky = null;
  let guides = null;
  let stopSpin = () => {};
  let dawnToken = null;
  let dawnStartedId = null;
  let atlas = null;
  let atlasTimer = null;
  let benchmarkTimer = null;

  const nodeColor = (node) => highlightColor(node, highlight, palette);
  const linkColor = (link) => highlightLinkColor(link, highlight, palette, linkEndId);
  const linkWidth = (link) => {
    if (link.focusDim) return 0.4;
    const base = Math.min(2.2, 0.45 + (link.weight ?? 1) * 0.25);
    if (!highlight.activeId) return base;
    const source = linkEndId(link.source);
    const target = linkEndId(link.target);
    return source === highlight.activeId || target === highlight.activeId ? base + 0.9 : base;
  };

  function setUp() {
    deps.assertWebGL();
    dressing = deps.createDressing(palette);
    bodyGeometry = deps.createBodyGeometry();
    renderer = deps.rendererFactory(host)
      .backgroundColor(palette.ground)
      .showNavInfo(false)
      .enableNavigationControls(true)
      .enableNodeDrag(false)
      .warmupTicks(0)
      .cooldownTicks(0)
      .nodeId("id")
      .nodeLabel(nodeLabel)
      .nodeVal("val")
      .nodeColor(nodeColor)
      .nodeRelSize(NODE_REL_SIZE)
      .nodeResolution(8)
      .nodeOpacity(0.82)
      .nodeThreeObject((node) =>
        makeMarker(node, palette, dressing, focusedNodeId, {
          level: snapshot?.level,
          bodyGeometry,
        }),
      )
      .nodeThreeObjectExtend(true)
      .linkColor(linkColor)
      .linkLabel(linkLabel)
      .linkOpacity(0.5)
      .linkWidth(linkWidth)
      .linkCurvature(0.12)
      .linkThreeObject((link) =>
        link.certain ? null : createPossibleRoute(link, linkColor(link)),
      )
      .linkPositionUpdate((object, { start, end }, link) =>
        link.certain ? false : updateRouteGeometry(object, link.__curve, start, end),
      )
      .linkVisibility((link) => !(snapshot?.mode === "easy" && link.focusDim))
      .linkHoverPrecision(4)
      .linkDirectionalArrowRelPos(1)
      .linkDirectionalArrowColor(linkColor)
      .linkDirectionalParticles((link) =>
        link.kind === "call" && link.certain && !link.focusDim && !reducedMotion ? 2 : 0,
      )
      .linkDirectionalParticleSpeed(0.006)
      .linkDirectionalParticleWidth(1.1)
      .linkDirectionalParticleColor(() => palette.orbit)
      .onNodeHover((node) => {
        if (closed) return;
        host.style.cursor = node ? "pointer" : "default";
        onHoverNode(node?.id ?? null);
      })
      .onNodeClick((node) => {
        if (!closed) onAdvance(node);
      });

    hideNavigationFrame = clock.requestFrame(() => {
      if (!closed) host.querySelector(".scene-nav-info")?.remove();
    });
    controls = renderer.controls();
    controls.enablePan = false;
    controls.enableDamping = !reducedMotion;
    controls.dampingFactor = 0.12;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.7;
    controls.minPolarAngle = MIN_POLAR_ANGLE;
    controls.maxPolarAngle = MAX_POLAR_ANGLE;
    const markUserFramed = () => {
      if (!closed) userFramed = true;
    };
    controls.addEventListener("start", markUserFramed);
    removeControlsListener = () => controls?.removeEventListener("start", markUserFramed);
    removePointerGuard = deps.guardOrbitPointerState(host, controls);
    bloom = deps.attachBloom(renderer, host.getBoundingClientRect());
    resizeObserver = new deps.ResizeObserver(([entry]) => {
      if (closed) return;
      const { width, height } = entry.contentRect;
      renderer.width(width).height(height);
      const aspect = viewportAspect(entry.contentRect);
      if (!userFramed && aspect !== null) reframe?.(aspect);
    });
    resizeObserver.observe(host);
  }

  function applyFraming(duration, aspect) {
    if (!snapshot) return;
    const { data, level, orbitPlan } = snapshot;
    const occlusion = measureCanvasOcclusion({ host, renderer });
    const framed = frameLevel({
      level,
      nodes: data.nodes,
      orbitPlan,
      fov: renderer.camera()?.fov,
      aspect:
        aspect ??
        viewportAspect(host.getBoundingClientRect()) ??
        viewportAspect({ width: renderer.width(), height: renderer.height() }),
      viewport: occlusion.viewport,
      chrome: level === LEVELS.SYSTEM ? occlusion.clickObstructions : [],
    });
    controls.minDistance = framed.min;
    controls.maxDistance = framed.max;
    renderer.cameraPosition(framed.position, framed.target, duration);
  }

  function replaceGuides() {
    stopSpin();
    stopSpin = () => {};
    if (guides) {
      renderer.scene().remove(guides);
      deps.disposeSystemOrbitGuides(guides);
      guides = null;
    }
    if (snapshot.level === LEVELS.GALAXY || !snapshot.orbitPlan.length) return;
    guides = deps.createSystemOrbitGuides(snapshot.orbitPlan, palette, dressing);
    renderer.scene().add(guides);
    stopSpin = deps.createBodySpin(renderer.scene(), { reducedMotion });
  }

  function replaceSky() {
    disposeSky();
    const starfield = deps.createStarfield(snapshot.starfieldSeed, palette);
    const glow = deps.createGalacticGlow(palette);
    renderer.scene().add(starfield);
    renderer.scene().add(glow);
    sky = { starfield, glow };
  }

  function disposeSky() {
    if (!sky || !renderer) return;
    renderer.scene().remove(sky.starfield);
    sky.starfield.geometry?.dispose();
    sky.starfield.material?.dispose();
    renderer.scene().remove(sky.glow);
    sky.glow.material?.map?.dispose();
    sky.glow.material?.dispose();
    sky = null;
  }

  function cancelDawn() {
    if (!dawnToken) return;
    dawnToken.cancelled = true;
    if (dawnToken.frame !== null) clock.cancelFrame(dawnToken.frame);
    dawnToken.stop();
    dawnToken = null;
  }

  function startDawn(regionId) {
    dawnStartedId = regionId;
    onDawnConsumed?.(regionId);
    if (reducedMotion) return;
    cancelDawn();
    const token = { cancelled: false, frame: null, stop: () => {} };
    dawnToken = token;
    const attempt = (frame) => {
      if (closed || token.cancelled || dawnToken !== token) return;
      const scene = renderer.scene();
      const found = Boolean(scene.getObjectByName(`codemble-system-${regionId}`));
      if (found || frame >= MAX_DAWN_RETRY_FRAMES) {
        token.frame = null;
        token.stop = deps.runDawnSequence({
          scene,
          regionId,
          palette,
          dressing,
          routes: snapshot?.graph?.region_edges ?? [],
          hopsById: new Map(
            (snapshot?.graph?.regions ?? []).map((item) => [item.id, item.hops_from_home]),
          ),
        });
        return;
      }
      token.frame = clock.requestFrame(() => attempt(frame + 1));
    };
    token.frame = clock.requestFrame(() => attempt(0));
  }

  function replaceAtlas() {
    if (atlasTimer !== null) clock.clearInterval(atlasTimer);
    if (atlas && renderer) atlas.hide(renderer.scene());
    atlasTimer = null;
    atlas = deps.createNameAtlas(snapshot.data.nodes);
    const scene = renderer.scene();
    const tick = () => {
      if (closed || !atlas) return;
      try {
        const camera = renderer.camera();
        const fallback = cameraBoundsFor(snapshot.level);
        const bounds = controls
          ? {
              min: controls.minDistance ?? fallback.min,
              max: controls.maxDistance ?? fallback.max,
            }
          : fallback;
        const distance = controls
          ? camera.position.distanceTo(controls.target)
          : camera.position.length();
        const occlusion = measureCanvasOcclusion({ host, renderer });
        atlas.place({
          scene,
          camera,
          width: renderer.width(),
          height: renderer.height(),
          distance,
          distanceBounds: bounds,
          hoverNodeId: snapshot.hoverNodeId,
          chrome: occlusion.nameObstructions,
        });
      } catch (error) {
        if (atlasTimer !== null) clock.clearInterval(atlasTimer);
        atlasTimer = null;
        atlas.hide(scene);
        console.error("Codemble: label declutter failed, names disabled", error);
      }
    };
    tick();
    atlasTimer = clock.setInterval(tick, LABEL_TICK_MS);
  }

  function replaceBenchmark() {
    if (benchmarkTimer !== null) clock.clearTimeout(benchmarkTimer);
    benchmarkTimer = null;
    const benchmarking = new URLSearchParams(deps.search()).has("benchmark");
    if (!benchmarking || snapshot.data.nodes.length < 900) return;
    deps.documentElement().removeAttribute("data-codemble-fps");
    benchmarkTimer = clock.setTimeout(() => {
      benchmarkTimer = null;
      if (closed) return;
      const webglRenderer = renderer.renderer();
      const composer = renderer.postProcessingComposer();
      const frameCount = 60;
      const startedAt = clock.now();
      for (let frame = 0; frame < frameCount; frame += 1) composer.render();
      webglRenderer.getContext().finish();
      const elapsed = clock.now() - startedAt;
      deps.documentElement().dataset.codembleFps = ((frameCount * 1000) / elapsed).toFixed(1);
    }, 1000);
  }

  function update(next) {
    if (closed) return;
    const previous = snapshot;
    snapshot = next;

    const graphChanged =
      !previous ||
      previous.data !== next.data ||
      previous.level !== next.level ||
      previous.mode !== next.mode ||
      previous.orbitPlan !== next.orbitPlan;
    if (graphChanged) {
      renderer
        .nodeResolution(next.data.nodes.length >= 900 ? 4 : 8)
        .nodeThreeObjectExtend(next.level === LEVELS.GALAXY)
        .linkVisibility((link) => !(next.mode === "easy" && link.focusDim))
        .linkDirectionalArrowLength(next.level === LEVELS.GALAXY ? 0 : 3.2)
        .graphData(next.data);
      applyFraming(CAMERA_DURATION);
      userFramed = false;
      reframe = (aspect) => applyFraming(0, aspect);
    }

    if (!previous || previous.focusedNodeId !== next.focusedNodeId) {
      focusedNodeId = next.focusedNodeId;
      renderer.refresh();
    }
    if (
      !previous ||
      previous.level !== next.level ||
      previous.orbitPlan !== next.orbitPlan
    ) {
      replaceGuides();
    }
    if (!previous || previous.starfieldSeed !== next.starfieldSeed) replaceSky();

    if (next.level !== LEVELS.GALAXY) {
      cancelDawn();
    } else if (next.pendingDawnRegionId && next.pendingDawnRegionId !== dawnStartedId) {
      startDawn(next.pendingDawnRegionId);
    }

    if (
      !previous ||
      previous.data !== next.data ||
      previous.hoverNodeId !== next.hoverNodeId ||
      previous.level !== next.level ||
      previous.selectedNode?.id !== next.selectedNode?.id
    ) {
      const activeId =
        next.hoverNodeId ??
        (next.level === LEVELS.STUDY ? next.selectedNode?.id ?? null : null);
      const neighborIds = new Set();
      if (activeId) {
        for (const link of next.data.links) {
          const source = linkEndId(link.source);
          const target = linkEndId(link.target);
          if (source === activeId) neighborIds.add(target);
          if (target === activeId) neighborIds.add(source);
        }
      }
      highlight = { activeId, neighborIds };
      renderer
        .nodeColor(renderer.nodeColor())
        .linkColor(renderer.linkColor())
        .linkWidth(renderer.linkWidth())
        .linkDirectionalArrowColor(renderer.linkDirectionalArrowColor());
      refreshPossibleRoutes(renderer.scene(), linkColor);
    }

    if (
      !previous ||
      previous.data.nodes !== next.data.nodes ||
      previous.hoverNodeId !== next.hoverNodeId ||
      previous.level !== next.level
    ) {
      replaceAtlas();
    }
    if (!previous || previous.data.nodes.length !== next.data.nodes.length) replaceBenchmark();
    if (
      next.level === LEVELS.STUDY &&
      (!previous || previous.level !== next.level || previous.selectedNode !== next.selectedNode)
    ) {
      const framed = frameStudy(next.selectedNode);
      if (framed) renderer.cameraPosition(framed.position, framed.target, CAMERA_DURATION);
    }
  }

  function dispose() {
    if (closed) return;
    closed = true;
    resizeObserver?.disconnect();
    resizeObserver = null;
    removeControlsListener();
    removeControlsListener = () => {};
    if (hideNavigationFrame !== null) clock.cancelFrame(hideNavigationFrame);
    hideNavigationFrame = null;
    removePointerGuard();
    removePointerGuard = () => {};
    stopSpin();
    stopSpin = () => {};
    if (guides && renderer) {
      renderer.scene().remove(guides);
      deps.disposeSystemOrbitGuides(guides);
      guides = null;
    }
    cancelDawn();
    if (atlasTimer !== null) clock.clearInterval(atlasTimer);
    atlasTimer = null;
    if (atlas && renderer) atlas.hide(renderer.scene());
    atlas = null;
    if (benchmarkTimer !== null) clock.clearTimeout(benchmarkTimer);
    benchmarkTimer = null;
    disposeSky();
    renderer?.pauseAnimation();
    bloom?.dispose();
    bloom = null;
    renderer?._destructor();
    dressing?.dispose();
    dressing = null;
    bodyGeometry?.dispose();
    bodyGeometry = null;
    controls = null;
    renderer = null;
    host.replaceChildren();
    reframe = null;
  }

  try {
    setUp();
  } catch (error) {
    dispose();
    throw error;
  }
  return Object.freeze({ update, dispose });
}

function makeMarker(node, palette, dressing, focusedId, { level, bodyGeometry } = {}) {
  const group = new THREE.Group();
  group.name = node.kind === "region" ? `codemble-system-${node.id}` : `codemble-node-${node.id}`;
  const radius = nodeRadius(node);
  const worldTier = level && level !== LEVELS.GALAXY && bodyGeometry;
  if (worldTier) {
    group.add(createBody({ node, color: node.color, palette, radius, geometry: bodyGeometry }));
  }
  const uncharted = isUncharted(node);
  if (!node.focusDim && !uncharted && !worldTier) group.add(dressing.halo(node, radius));
  if (node.kind === "region" && !uncharted) {
    const tint = palette.nebula[node.language];
    if (tint) group.add(dressing.nebula(tint, radius * 14));
  }
  if (node.label) {
    const plate = dressing.label(node.label, radius);
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
  if (node.kind === "class" && !node.focusDim) {
    const classRing = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 1.45, Math.max(0.1, radius * 0.045), 6, 28),
      new THREE.MeshBasicMaterial({ color: palette.route }),
    );
    classRing.rotation.x = Math.PI / 2.4;
    group.add(classRing);
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

function linkEndId(end) {
  return typeof end === "object" && end !== null ? end.id : end;
}
