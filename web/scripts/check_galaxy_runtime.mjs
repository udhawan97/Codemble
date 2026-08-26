import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

globalThis.window = {};
const { createGalaxyRuntime, galaxyRuntimeStartDelay, LARGE_GALAXY_DEFER_MS } =
  await import("../src/galaxyRuntime.js");

assert.equal(galaxyRuntimeStartDelay(900), 0, "ordinary galaxies start immediately");
assert.equal(
  galaxyRuntimeStartDelay(901),
  LARGE_GALAXY_DEFER_MS,
  "large galaxies yield briefly to an explicit Map transition",
);

function fakeClock() {
  let next = 1;
  const frames = new Map();
  const intervals = new Map();
  const timeouts = new Map();
  return {
    requestFrame(callback) {
      const handle = next++;
      frames.set(handle, callback);
      return handle;
    },
    cancelFrame(handle) {
      frames.delete(handle);
    },
    setInterval(callback) {
      const handle = next++;
      intervals.set(handle, callback);
      return handle;
    },
    clearInterval(handle) {
      intervals.delete(handle);
    },
    setTimeout(callback) {
      const handle = next++;
      timeouts.set(handle, callback);
      return handle;
    },
    clearTimeout(handle) {
      timeouts.delete(handle);
    },
    now: () => 100,
    flushFrames() {
      const pending = [...frames.entries()];
      frames.clear();
      for (const [, callback] of pending) callback(100);
    },
    counts() {
      return { frames: frames.size, intervals: intervals.size, timeouts: timeouts.size };
    },
  };
}

function disposable(name, events) {
  return {
    disposed: 0,
    dispose() {
      this.disposed += 1;
      events.push(name);
    },
  };
}

function harness({ reducedMotion = false, dawnReady = true, size = { width: 900, height: 600 } } = {}) {
  const events = [];
  const callbacks = {};
  const seeds = [];
  const dawns = [];
  const consumed = [];
  const hovers = [];
  const advances = [];
  const atlasPlacements = [];
  const clock = fakeClock();
  const sceneObjects = new Map();
  const scene = {
    add(object) {
      events.push(`scene:add:${object.name}`);
      if (object.name) sceneObjects.set(object.name, object);
    },
    remove(object) {
      events.push(`scene:remove:${object.name}`);
      if (object.name) sceneObjects.delete(object.name);
    },
    getObjectByName(name) {
      if (dawnReady && name.startsWith("codemble-system-")) return { name };
      return sceneObjects.get(name) ?? null;
    },
    traverse() {},
  };
  const controlListeners = new Map();
  const controls = {
    target: {},
    addEventListener(name, callback) {
      controlListeners.set(name, callback);
      events.push(`controls:add:${name}`);
    },
    removeEventListener(name, callback) {
      assert.equal(controlListeners.get(name), callback);
      controlListeners.delete(name);
      events.push(`controls:remove:${name}`);
    },
  };
  const accessors = new Map();
  let width = size.width;
  let height = size.height;
  const camera = {
    fov: 45,
    position: {
      distanceTo: () => 100,
      length: () => 100,
    },
  };
  const renderer = {
    controls: () => controls,
    scene: () => scene,
    camera: () => camera,
    width(value) {
      if (value === undefined) return width;
      width = value;
      events.push("renderer:width");
      return this;
    },
    height(value) {
      if (value === undefined) return height;
      height = value;
      events.push("renderer:height");
      return this;
    },
    cameraPosition(_position, _lookAt, duration) {
      events.push(`renderer:cameraPosition:${duration}`);
      return this;
    },
    graphData(value) {
      events.push("renderer:graphData");
      accessors.set("graphData", value);
      return this;
    },
    refresh() {
      events.push("renderer:refresh");
      return this;
    },
    pauseAnimation() {
      events.push("renderer:pause");
    },
    _destructor() {
      events.push("renderer:destructor");
    },
  };
  const chainMethods = [
    "backgroundColor", "showNavInfo", "enableNavigationControls", "enableNodeDrag",
    "warmupTicks", "cooldownTicks", "nodeId", "nodeLabel", "nodeVal", "nodeColor",
    "nodeRelSize", "nodeResolution", "nodeOpacity", "nodeThreeObject",
    "nodeThreeObjectExtend", "linkColor", "linkLabel", "linkOpacity", "linkWidth",
    "linkCurvature", "linkThreeObject", "linkPositionUpdate", "linkVisibility",
    "linkHoverPrecision", "linkDirectionalArrowRelPos", "linkDirectionalArrowColor",
    "linkDirectionalParticles", "linkDirectionalParticleSpeed",
    "linkDirectionalParticleWidth", "linkDirectionalParticleResolution",
    "linkDirectionalParticleColor",
    "linkDirectionalArrowLength", "onNodeHover", "onNodeClick",
  ];
  for (const method of chainMethods) {
    renderer[method] = function accessor(value) {
      if (arguments.length === 0) return accessors.get(method);
      accessors.set(method, value);
      events.push(`${method}:${String(value)}`);
      if (method === "onNodeHover" || method === "onNodeClick") callbacks[method] = value;
      return this;
    };
  }

  const host = {
    style: {},
    getBoundingClientRect: () => ({ ...size }),
    querySelector: () => null,
    closest: () => null,
    replaceChildren: () => events.push("host:clear"),
  };
  class FakeResizeObserver {
    constructor(callback) {
      this.callback = callback;
    }
    observe(target) {
      assert.equal(target, host);
      events.push("observer:observe");
    }
    disconnect() {
      events.push("observer:disconnect");
    }
  }
  const navigator = {
    name: "codemble-navigator",
    visible: false,
    scale: { setScalar: () => events.push("navigator:scale") },
    position: { set: () => events.push("navigator:position") },
    removeFromParent: () => events.push("navigator:remove"),
  };
  const dressing = {
    dispose: () => events.push("dressing:dispose"),
    reticle: () => navigator,
  };
  const bodyGeometry = { dispose: () => events.push("body:dispose") };
  const bloom = { dispose: () => events.push("bloom:dispose") };
  const dependencies = {
    assertWebGL: () => events.push("webgl:ok"),
    rendererFactory: () => renderer,
    ResizeObserver: FakeResizeObserver,
    createDressing: () => dressing,
    createBodyGeometry: () => bodyGeometry,
    createBodySpin: () => {
      events.push("spin:start");
      return () => events.push("spin:stop");
    },
    createSystemOrbitGuides: () => ({ name: "guides" }),
    disposeSystemOrbitGuides: () => events.push("guides:dispose"),
    createStarfield(seed) {
      seeds.push(seed);
      return {
        name: "codemble-starfield",
        geometry: disposable("starfield:geometry", events),
        material: disposable("starfield:material", events),
      };
    },
    createGalacticGlow: () => ({
      name: "codemble-galactic-glow",
      material: { ...disposable("glow:material", events), map: disposable("glow:map", events) },
    }),
    createSystemAura: () => ({
      name: "codemble-system-aura",
      material: disposable("aura:material", events),
    }),
    attachBloom(_renderer, receivedSize) {
      events.push(`bloom:size:${receivedSize.width}x${receivedSize.height}`);
      return bloom;
    },
    guardOrbitPointerState: () => {
      events.push("pointer:add");
      return () => events.push("pointer:remove");
    },
    runDawnSequence(args) {
      dawns.push(args);
      return () => events.push("dawn:stop");
    },
    createNameAtlas: () => ({
      place: (options) => {
        atlasPlacements.push(options);
        events.push("atlas:place");
      },
      hide: () => events.push("atlas:hide"),
    }),
    documentElement: () => ({ removeAttribute() {}, dataset: {} }),
    search: () => "",
  };
  const runtime = createGalaxyRuntime({
    host,
    palette: {
      ground: "#000",
      orbit: "#0ff",
      faded: "#555",
      route: "#444",
      routePossible: "#fa4",
    },
    reducedMotion,
    onHoverNode: (id) => hovers.push(id),
    onAdvance: (node) => advances.push(node),
    onDawnConsumed: (id) => consumed.push(id),
    dependencies,
    clock,
  });
  return {
    runtime,
    renderer,
    callbacks,
    events,
    seeds,
    dawns,
    consumed,
    hovers,
    advances,
    atlasPlacements,
    clock,
  };
}

function snapshot(overrides = {}) {
  return {
    graph: {
      region_edges: [
        { src: "home", dst: "target", certain: true },
        { src: "maybe", dst: "target", certain: false },
      ],
      regions: [
        { id: "home", hops_from_home: 0 },
        { id: "target", hops_from_home: 1 },
      ],
    },
    data: { nodes: [{ id: "target" }], links: [] },
    level: "GALAXY",
    mode: "hard",
    orbitPlan: [],
    selectedNode: null,
    hoverNodeId: null,
    pendingDawnRegionId: "target",
    starfieldSeed: 17,
    focusedNodeId: "target",
    ...overrides,
  };
}

const first = harness();
assert.equal(first.renderer.enableNodeDrag(), false, "immutable graph disables drag at runtime");
first.runtime.update(snapshot());
assert.equal(
  first.renderer.nodeColor()({ id: "target", color: "#abc" }),
  "#0ff",
  "keyboard focus uses the same interaction ink as pointer focus",
);
assert.equal(
  first.atlasPlacements.at(-1).activeNodeId,
  "target",
  "keyboard focus also drives the neighborhood label order",
);
const beforeFocusClear = first.events.length;
first.runtime.update(snapshot({ focusedNodeId: null, pendingDawnRegionId: null }));
const focusClearEvents = first.events.slice(beforeFocusClear);
assert.ok(
  focusClearEvents.lastIndexOf("navigator:remove") >
    focusClearEvents.lastIndexOf(`nodeColor:${String(first.renderer.nodeColor())}`),
  "the flight navigator retires after the new highlight accessor is installed",
);
assert.equal(
  first.renderer.nodeColor()({ id: "target", color: "#abc" }),
  "#abc",
  "clearing keyboard focus restores the standing node colour",
);

const neighborhood = {
  nodes: [
    { id: "target", color: "#111" },
    { id: "neighbor", color: "#222" },
    { id: "far", color: "#333" },
    { id: "alone", color: "#666" },
  ],
  links: [
    { source: "target", target: "neighbor", certain: true, color: "#444" },
    { source: "neighbor", target: "far", certain: false, color: "#555" },
  ],
};
first.runtime.update(
  snapshot({
    data: neighborhood,
    focusedNodeId: "target",
    hoverNodeId: "neighbor",
    pendingDawnRegionId: null,
  }),
);
assert.equal(first.renderer.nodeColor()(neighborhood.nodes[1]), "#0ff");
assert.equal(first.renderer.nodeColor()(neighborhood.nodes[0]), "#111");
assert.equal(first.renderer.nodeColor()(neighborhood.nodes[2]), "#333");
assert.equal(
  first.renderer.nodeColor()(neighborhood.nodes[3]),
  "#666",
  "free exploration keeps the full galaxy visibly colourful during hover",
);
assert.equal(first.renderer.linkColor()(neighborhood.links[0]), "#0ff");
assert.equal(
  first.renderer.linkColor()(neighborhood.links[1]),
  "#fa4",
  "an active possible route keeps uncertainty ink",
);
assert.equal(
  first.renderer.linkDirectionalParticles()(neighborhood.links[0]),
  3,
  "the active parser-proven galaxy route carries navigation motion",
);
assert.equal(
  first.renderer.linkDirectionalParticles()(neighborhood.links[1]),
  0,
  "a possible route never gains navigation motion",
);
assert.equal(first.atlasPlacements.at(-1).activeNodeId, "neighbor");
assert.deepEqual([...first.atlasPlacements.at(-1).neighborIds], ["target", "far"]);

first.runtime.update(
  snapshot({
    data: neighborhood,
    focusedNodeId: "target",
    hoverNodeId: "neighbor",
    firstFlightActive: true,
    pendingDawnRegionId: null,
  }),
);
assert.equal(
  first.renderer.nodeColor()(neighborhood.nodes[3]),
  "#555",
  "guided learning may recede systems outside the active neighborhood",
);

first.runtime.update(
  snapshot({
    data: neighborhood,
    focusedNodeId: "target",
    hoverNodeId: null,
    pendingDawnRegionId: null,
  }),
);
assert.equal(
  first.renderer.nodeColor()(neighborhood.nodes[0]),
  "#0ff",
  "retiring hover restores the keyboard subject's interaction material",
);
assert.equal(first.atlasPlacements.at(-1).activeNodeId, "target");
assert.deepEqual([...first.atlasPlacements.at(-1).neighborIds], ["neighbor"]);
assert.ok(
  first.events.indexOf("renderer:graphData") <
    first.events.findIndex((event) => event.startsWith("renderer:cameraPosition:")),
  "graph commits before framing",
);
assert.deepEqual(first.seeds, [17], "the project seed reaches the starfield factory unchanged");
first.clock.flushFrames();
assert.deepEqual(first.consumed, ["target"], "Dawn is claimed exactly once");
assert.equal(first.dawns.length, 1);
assert.deepEqual(first.dawns[0].routes, snapshot().graph.region_edges);
assert.deepEqual([...first.dawns[0].hopsById], [["home", 0], ["target", 1]]);

first.callbacks.onNodeHover({ id: "target" });
first.callbacks.onNodeClick({ id: "target" });
assert.deepEqual(first.hovers, ["target"]);
assert.deepEqual(first.advances, [{ id: "target" }]);

first.runtime.update(snapshot({ starfieldSeed: 18, pendingDawnRegionId: null }));
assert.deepEqual(first.seeds, [17, 18]);
assert.equal(first.events.filter((event) => event === "starfield:geometry").length, 1);
first.runtime.dispose();
const disposalCount = first.events.length;
first.runtime.dispose();
assert.equal(first.events.length, disposalCount, "dispose is idempotent");
assert.ok(first.events.includes("observer:disconnect"));
assert.ok(first.events.includes("controls:remove:start"));
assert.ok(first.events.includes("pointer:remove"));
assert.ok(first.events.indexOf("renderer:pause") < first.events.indexOf("bloom:dispose"));
assert.ok(first.events.indexOf("bloom:dispose") < first.events.indexOf("renderer:destructor"));
assert.ok(first.events.indexOf("renderer:destructor") < first.events.indexOf("dressing:dispose"));
assert.ok(first.events.indexOf("dressing:dispose") < first.events.indexOf("body:dispose"));
first.callbacks.onNodeHover({ id: "late" });
first.callbacks.onNodeClick({ id: "late" });
assert.deepEqual(first.hovers, ["target"], "renderer callbacks no-op after disposal");
assert.deepEqual(first.advances, [{ id: "target" }]);
assert.deepEqual(first.clock.counts(), { frames: 0, intervals: 0, timeouts: 0 });

const waiting = harness({ dawnReady: false });
waiting.runtime.update(snapshot());
waiting.runtime.dispose();
waiting.clock.flushFrames();
assert.equal(waiting.dawns.length, 0, "a disposed retry cannot start Dawn later");

const still = harness({ reducedMotion: true });
still.runtime.update(
  snapshot({
    level: "SYSTEM",
    orbitPlan: [{ radius: 20 }],
    firstFlightActive: false,
  }),
);
const beforeFlightFrame = still.events.length;
still.runtime.update(
  snapshot({
    level: "GALAXY",
    firstFlightActive: true,
    pendingDawnRegionId: null,
  }),
);
assert.ok(
  still.events.slice(beforeFlightFrame).includes("renderer:cameraPosition:0"),
  "reduced-motion First Flight reaches the renderer as a zero-duration jump cut",
);
assert.equal(still.renderer.linkDirectionalParticles()({ kind: "call", certain: true }), 0);
still.runtime.update(snapshot({ pendingDawnRegionId: "target" }));
assert.deepEqual(still.consumed, ["target"]);
still.clock.flushFrames();
assert.equal(still.dawns.length, 0, "reduced motion settles without a Dawn animation");
still.runtime.dispose();

const remount = harness({ size: { width: 900, height: 600 } });
assert.ok(remount.events.includes("bloom:size:900x600"), "same-size remount sizes bloom from host");
remount.runtime.dispose();

const canvasSource = readFileSync(new URL("../src/GalaxyCanvas.jsx", import.meta.url), "utf8");
assert.match(
  canvasSource,
  /onPointerLeave=\{\(\) => hoverRef\.current\(null\)\}/,
  "leaving WebGL for overlay chrome clears a hover spotlight that the renderer cannot see leave",
);

console.log("galaxy runtime contract: ok");
