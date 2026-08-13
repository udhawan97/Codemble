import { useEffect, useMemo, useRef, useState } from "react";

import { prefersReducedMotion } from "./galaxyEffects.js";
import { createGalaxyRuntime } from "./galaxyRuntime.js";
import { seedFromHashes } from "./galaxyMaterials.js";
import {
  LEVELS,
  NEBULA_TINTS,
  galaxyData,
  nodeLabel,
  systemData,
} from "./graphData.js";
import { systemOrbitPlan } from "./systemOrbits.js";

export function GalaxyCanvas({
  graph,
  level,
  region,
  selectedNode,
  hoverNodeId,
  pendingDawnRegionId,
  revealedRegionIds,
  mode,
  firstFlightActive,
  onHoverNode,
  onAdvance,
  onRetreat,
  onDawnConsumed,
}) {
  const hostRef = useRef(null);
  const runtimeRef = useRef(null);
  const advanceRef = useRef(onAdvance);
  const retreatRef = useRef(onRetreat);
  const hoverRef = useRef(onHoverNode);
  const dawnConsumedRef = useRef(onDawnConsumed);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [keyboardExploring, setKeyboardExploring] = useState(false);
  const [renderError, setRenderError] = useState("");
  const palette = useMemo(readPalette, []);
  const reducedMotion = useMemo(prefersReducedMotion, []);
  const starfieldSeed = seedFromHashes(graph.file_hashes);
  const data = useMemo(() => {
    if (level === LEVELS.GALAXY) return galaxyData(graph, palette, revealedRegionIds);
    return systemData(graph, region?.id, palette, {
      selectedId: selectedNode?.id,
    });
  }, [graph, level, palette, region?.id, revealedRegionIds, selectedNode?.id]);
  const orbitPlan = useMemo(
    () => (level === LEVELS.GALAXY ? [] : systemOrbitPlan(data.nodes)),
    [data.nodes, level],
  );

  useEffect(() => {
    advanceRef.current = onAdvance;
    retreatRef.current = onRetreat;
    hoverRef.current = onHoverNode;
    dawnConsumedRef.current = onDawnConsumed;
  }, [onAdvance, onRetreat, onHoverNode, onDawnConsumed]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    try {
      const runtime = createGalaxyRuntime({
        host,
        palette,
        reducedMotion,
        onHoverNode: (nodeId) => hoverRef.current(nodeId),
        onAdvance: (node) => advanceRef.current(node),
        onDawnConsumed: (regionId) => dawnConsumedRef.current?.(regionId),
      });
      runtimeRef.current = runtime;
      setRenderError("");
      return () => {
        runtime.dispose();
        if (runtimeRef.current === runtime) runtimeRef.current = null;
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setRenderError(
        message.startsWith("Codemble needs WebGL")
          ? message
          : `The galaxy could not start: ${message}`,
      );
      return undefined;
    }
  }, [palette, reducedMotion]);

  useEffect(() => {
    runtimeRef.current?.update({
      graph,
      data,
      level,
      mode,
      orbitPlan,
      selectedNode,
      hoverNodeId,
      pendingDawnRegionId,
      starfieldSeed,
      firstFlightActive,
      focusedNodeId: keyboardExploring ? data.nodes[focusedIndex]?.id ?? null : null,
    });
  }, [
    data,
    firstFlightActive,
    focusedIndex,
    graph,
    hoverNodeId,
    keyboardExploring,
    level,
    mode,
    orbitPlan,
    pendingDawnRegionId,
    selectedNode,
    starfieldSeed,
  ]);

  useEffect(() => {
    setFocusedIndex(0);
    setKeyboardExploring(false);
  }, [data, level, mode, orbitPlan]);

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
      // First Flight is a dismissible surface in the one Escape arbiter. Let
      // its Escape bubble there instead of retreating here first; otherwise
      // one key would leave the system and then close the tour on top of it.
      if (event.key === "Escape" && firstFlightActive) return;
      event.preventDefault();
      retreatRef.current();
    }
  }

  if (renderError) {
    return (
      <section className="webgl-error" role="alert">
        <h1>The sky could not open.</h1>
        <p>{renderError}</p>
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
      aria-label={`Codemble ${level.toLowerCase()} view. Drag to orbit, scroll to zoom. Use arrow keys to choose a node and Enter to move closer.${level === LEVELS.GALAXY ? "" : " Solid guides are parser-proven call layers; a dashed guide has no proven call path."}`}
      onFocus={() => setKeyboardExploring(true)}
      onBlur={() => {
        hoverRef.current(null);
      }}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={hostRef}
        className="galaxy-canvas"
        aria-hidden="true"
        // The frame still geometrically contains its overlay controls. The
        // WebGL host does not, so this is the boundary where a pointer leaving
        // for Key/Modules/Find can reliably retire the old neighborhood.
        onPointerLeave={() => hoverRef.current(null)}
      />
      {keyboardExploring && focusedNode ? (
        <output className="keyboard-focus" aria-live="polite">
          {nodeLabel(focusedNode)}
        </output>
      ) : null}
    </div>
  );
}

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
  const value = (token) => toRenderableColor(styles.getPropertyValue(token).trim());
  return Object.freeze({
    ground: value("--cm-sky"),
    skyGlow: value("--cm-sky-glow"),
    home: value("--cm-ink"),
    orbit: value("--cm-orbit"),
    nodeBright: value("--cm-node-bright"),
    node: value("--cm-node-mid"),
    nodeDim: value("--cm-node-unlit"),
    starCool: value("--cm-star-cool"),
    starPale: value("--cm-star-pale"),
    route: value("--cm-route"),
    routePossible: value("--cm-route-possible"),
    faded: value("--cm-hairline-soft"),
    star: value("--cm-star-high"),
    starHalo: value("--cm-star-halo"),
    nebula: Object.freeze(
      Object.fromEntries(
        Object.entries(NEBULA_TINTS).map(([language, property]) => [language, value(property)]),
      ),
    ),
    communities: Object.freeze(
      Array.from({ length: 8 }, (_, index) => value(`--cm-com-${index}`)),
    ),
    labelPlate: styles.getPropertyValue("--cm-label-plate").trim(),
    labelInk: styles.getPropertyValue("--cm-label-ink").trim(),
  });
}
