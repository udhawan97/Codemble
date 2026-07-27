import assert from "node:assert/strict";

import { systemOrbitPlan } from "../src/systemOrbits.js";

const plan = systemOrbitPlan([
  {
    id: "module",
    system_orbit: {
      ring: 0,
      radius: 0,
      call_depth: 0,
      kind: "origin",
    },
  },
  {
    id: "root",
    system_orbit: {
      ring: 1,
      radius: 34,
      call_depth: 1,
      kind: "call-root",
    },
  },
  {
    id: "direct",
    system_orbit: {
      ring: 1,
      radius: 34,
      call_depth: 1,
      kind: "certain-call",
    },
  },
  {
    id: "overflow",
    system_orbit: {
      ring: 1,
      radius: 46,
      call_depth: 1,
      kind: "call-root",
    },
  },
  {
    id: "deep",
    system_orbit: {
      ring: 2,
      radius: 70,
      call_depth: 2,
      kind: "certain-call",
    },
  },
  {
    id: "cycle",
    system_orbit: {
      ring: 3,
      radius: 94,
      call_depth: null,
      kind: "unreached",
    },
  },
]);

assert.deepEqual(plan, [
  {
    ring: 1,
    callDepth: 1,
    kinds: ["call-root", "certain-call"],
    radii: [34, 46],
    label: "Layer 1",
    unproven: false,
  },
  {
    ring: 2,
    callDepth: 2,
    kinds: ["certain-call"],
    radii: [70],
    label: "Layer 2",
    unproven: false,
  },
  {
    ring: 3,
    callDepth: null,
    kinds: ["unreached"],
    radii: [94],
    label: "No proven path",
    unproven: true,
  },
]);

assert.deepEqual(systemOrbitPlan([{ id: "legacy" }]), []);

console.log("system-orbit contracts passed");
