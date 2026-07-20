import ForceGraph3D from "3d-force-graph";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { createDressing, createStarfield, seedFromHashes } from "./galaxyMaterials.js";
import { LEVELS, galaxyData, linkLabel, nebulaTintKey, nodeLabel, systemData } from "./graphData.js";

const CAMERA_DURATION = 420;
const NODE_REL_SIZE = 1.6;

export function GalaxyCanvas({
  graph,
  level,
  region,
  selectedNode,
  hoverNodeId,
  onHoverNode,
  onAdvance,
  onRetreat,
}) {
  const hostRef = useRef(null);
  const rendererRef = useRef(null);
  const advanceRef = useRef(onAdvance);
  const retreatRef = useRef(onRetreat);
  const hoverRef = useRef(onHoverNode);
  const highlightRef = useRef({ activeId: null, neighborIds: new Set() });
  const wheelLockRef = useRef(0);
  const dressingRef = useRef(null);
  const focusedIdRef = useRef(null);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [renderError, setRenderError] = useState("");
  const palette = useMemo(readPalette, []);
  const data = useMemo(() => {
    if (level === LEVELS.GALAXY) return galaxyData(graph, palette);
    return systemData(graph, region?.id, palette, {
      selectedId: selectedNode?.id,
    });
  }, [graph, level, palette, region?.id, selectedNode?.id]);

  useEffect(() => {
    advanceRef.current = onAdvance;
    retreatRef.current = onRetreat;
    hoverRef.current = onHoverNode;
  }, [onAdvance, onRetreat, onHoverNode]);

  function nodeColor(node) {
    const { activeId, neighborIds } = highlightRef.current;
    if (!activeId) return node.color;
    if (node.id === activeId) return palette.orbit;
    return neighborIds.has(node.id) ? node.color : palette.faded;
  }

  function linkColor(link) {
    const { activeId, neighborIds } = highlightRef.current;
    const base = link.certain ? palette.route : palette.routePossible;
    if (!activeId) return base;
    const source = linkEndId(link.source);
    const target = linkEndId(link.target);
    if (source === activeId || target === activeId) return palette.orbit;
    return neighborIds.has(source) && neighborIds.has(target) ? base : palette.faded;
  }

  function linkWidth(link) {
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
      const renderer = ForceGraph3D()(host)
        .backgroundColor(palette.ground)
        .showNavInfo(false)
        .enableNavigationControls(false)
        .warmupTicks(0)
        .cooldownTicks(0)
        .nodeId("id")
        .nodeLabel(nodeLabel)
        .nodeVal("val")
        .nodeColor(nodeColor)
        .nodeRelSize(NODE_REL_SIZE)
        .nodeResolution(8)
        .nodeOpacity(0.82)
        .nodeThreeObject((node) => makeMarker(node, palette, dressing, focusedIdRef.current))
        .nodeThreeObjectExtend(true)
        .linkColor(linkColor)
        .linkLabel(linkLabel)
        .linkOpacity(0.32)
        .linkWidth(linkWidth)
        .linkHoverPrecision(4)
        .linkDirectionalArrowRelPos(1)
        .linkDirectionalArrowColor(linkColor)
        .onNodeHover((node) => {
          host.style.cursor = node ? "pointer" : "default";
          hoverRef.current(node?.id ?? null);
        })
        .onNodeClick((node) => advanceRef.current(node));
      const hideNavigationHint = requestAnimationFrame(() => {
        host.querySelector(".scene-nav-info")?.remove();
      });
      rendererRef.current = renderer;

      const resize = new ResizeObserver(([entry]) => {
        renderer.width(entry.contentRect.width).height(entry.contentRect.height);
      });
      resize.observe(host);
      return () => {
        resize.disconnect();
        cancelAnimationFrame(hideNavigationHint);
        renderer.pauseAnimation();
        dressing.dispose();
        dressingRef.current = null;
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
      // Arrows only where an edge means a direction the learner can act on.
      .linkDirectionalArrowLength(level === LEVELS.GALAXY ? 0 : 3.2)
      .graphData(data);
    if (level === LEVELS.GALAXY) {
      renderer.cameraPosition({ x: 0, y: 105, z: 310 }, { x: 0, y: 0, z: 0 }, CAMERA_DURATION);
    } else {
      renderer.cameraPosition({ x: 0, y: 52, z: 150 }, { x: 0, y: 0, z: 0 }, CAMERA_DURATION);
    }
    setFocusedIndex(0);
  }, [data, level]);

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
    const starfield = createStarfield(seedFromHashes(graph.file_hashes), palette);
    scene.add(starfield);
    return () => {
      scene.remove(starfield);
      starfield.geometry.dispose();
      starfield.material.dispose();
    };
  }, [graph.file_hashes, palette]);

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

  useEffect(() => {
    const benchmarking = new URLSearchParams(window.location.search).has("benchmark");
    if (!benchmarking || data.nodes.length < 900) return undefined;
    document.documentElement.removeAttribute("data-codemble-fps");
    const begin = setTimeout(() => {
      const graphRenderer = rendererRef.current;
      if (!graphRenderer) return;
      const webglRenderer = graphRenderer.renderer();
      const frameCount = 60;
      const startedAt = performance.now();
      for (let frame = 0; frame < frameCount; frame += 1) {
        webglRenderer.render(graphRenderer.scene(), graphRenderer.camera());
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

  function handleWheel(event) {
    const now = performance.now();
    if (now < wheelLockRef.current || Math.abs(event.deltaY) < 24) return;
    wheelLockRef.current = now + 620;
    if (event.deltaY > 0 && focusedNode) advanceRef.current(focusedNode);
    if (event.deltaY < 0) retreatRef.current();
  }

  if (renderError) {
    return (
      <section className="webgl-error" role="alert">
        <h1>The sky could not open.</h1>
        <p>{renderError}</p>
      </section>
    );
  }

  return (
    <div
      className="galaxy-frame"
      role="application"
      tabIndex="0"
      aria-label={`Codemble ${level.toLowerCase()} view. Use arrow keys to choose a node and Enter to move closer.`}
      onKeyDown={handleKeyDown}
      onWheel={handleWheel}
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
  const radius = Math.cbrt(node.val ?? 1) * NODE_REL_SIZE;
  // Dimmed nodes keep their true colour and lose their glow. Dimming by
  // removing light rather than shifting hue keeps a lit star recognisably lit.
  if (!node.focusDim) group.add(dressing.halo(node, radius));
  if (node.kind === "region") {
    const tint = nebulaTintKey(node.language);
    if (tint) group.add(dressing.nebula(palette[tint], radius * 14));
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
  });
}
