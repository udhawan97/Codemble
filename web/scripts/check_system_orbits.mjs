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
    label: "Inner orbit · direct calls + call roots",
    containsCallRoots: true,
    guideCertain: true,
    unproven: false,
  },
  {
    ring: 2,
    callDepth: 2,
    kinds: ["certain-call"],
    radii: [70],
    label: "Orbit 2 · call depth 2",
    containsCallRoots: false,
    guideCertain: true,
    unproven: false,
  },
  {
    ring: 3,
    callDepth: null,
    kinds: ["unreached"],
    radii: [94],
    label: "Outer drift · no proven path",
    containsCallRoots: false,
    guideCertain: false,
    unproven: true,
  },
]);

assert.deepEqual(systemOrbitPlan([{ id: "legacy" }]), []);

assert.deepEqual(
  systemOrbitPlan([
    {
      id: "root-only",
      system_orbit: { ring: 1, radius: 34, call_depth: 1, kind: "call-root" },
    },
  ]),
  [
    {
      ring: 1,
      callDepth: 1,
      kinds: ["call-root"],
      radii: [34],
      label: "Inner orbit · call roots, no call edge",
      containsCallRoots: true,
      guideCertain: false,
      unproven: false,
    },
  ],
  "a call root never becomes a proven direct call",
);

console.log("system-orbit contracts passed");
