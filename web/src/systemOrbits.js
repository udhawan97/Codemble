import * as THREE from "three";

const GUIDE_SEGMENTS = 128;
const LABEL_ANGLE = -0.72;

/**
 * Collapse per-node graph metadata into the orbit bands a renderer draws.
 *
 * The backend owns every semantic field and exact radius. This helper only
 * groups identical facts for presentation; it never reconstructs a layer from
 * XYZ coordinates.
 */
export function systemOrbitPlan(nodes) {
  const byRing = new Map();
  for (const node of nodes ?? []) {
    const orbit = node.system_orbit;
    if (
      !orbit ||
      !Number.isInteger(orbit.ring) ||
      orbit.ring <= 0 ||
      !Number.isFinite(orbit.radius) ||
      orbit.radius <= 0
    ) {
      continue;
    }
    if (!byRing.has(orbit.ring)) {
      byRing.set(orbit.ring, {
        callDepths: new Set(),
        kinds: new Set(),
        radii: new Set(),
      });
    }
    const group = byRing.get(orbit.ring);
    group.callDepths.add(orbit.call_depth ?? null);
    group.kinds.add(orbit.kind);
    group.radii.add(orbit.radius);
  }

  return [...byRing.entries()]
    .sort(([left], [right]) => left - right)
    .map(([ring, group]) => {
      const depths = [...group.callDepths];
      const callDepth = depths.length === 1 ? depths[0] : null;
      const kinds = [...group.kinds].sort();
      const unproven = kinds.every((kind) => kind === "unreached");
      const guideCertain = kinds.includes("certain-call");
      const containsCallRoots = kinds.includes("call-root");
      return {
        ring,
        callDepth,
        kinds,
        radii: [...group.radii].sort((left, right) => left - right),
        label: unproven
          ? "Outer drift · no proven path"
          : containsCallRoots && guideCertain
            ? callDepth === 1
              ? "Inner orbit · direct calls + call roots"
              : `Orbit ${ring} · calls + call roots`
            : containsCallRoots
              ? "Inner orbit · call roots, no call edge"
          : callDepth === null
            ? "Mixed call evidence"
            : callDepth === 1
              ? "Inner orbit · direct calls"
              : `Orbit ${callDepth} · call depth ${callDepth}`,
        containsCallRoots,
        guideCertain,
        unproven,
      };
    });
}

export function createSystemOrbitGuides(
  plan,
  palette,
  dressing,
  { languageColor = null } = {},
) {
  const group = new THREE.Group();
  group.name = "codemble-system-orbits";

  for (const layer of plan) {
    const material = !layer.guideCertain
      ? new THREE.LineDashedMaterial({
          color: palette.faded,
          dashSize: 3,
          gapSize: 2,
          opacity: 0.72,
          transparent: true,
          depthWrite: false,
        })
      : new THREE.LineBasicMaterial({
          color: palette.route,
          opacity: 0.52,
          transparent: true,
          depthWrite: false,
        });
    const glowMaterial = !layer.guideCertain
      ? null
      : new THREE.LineBasicMaterial({
          color: languageColor ?? palette.orbit,
          opacity: 0.16,
          transparent: true,
          depthWrite: false,
        });

    for (const radius of layer.radii) {
      const points =
        Array.from({ length: GUIDE_SEGMENTS }, (_, index) => {
          const angle = (index / GUIDE_SEGMENTS) * Math.PI * 2;
          return new THREE.Vector3(
            Math.cos(angle) * radius,
            0,
            Math.sin(angle) * radius,
          );
        });
      if (glowMaterial) {
        const glow = new THREE.LineLoop(
          new THREE.BufferGeometry().setFromPoints(points),
          glowMaterial,
        );
        glow.scale.setScalar(1.012);
        glow.userData.codembleOrbitGuide = true;
        glow.renderOrder = -2;
        group.add(glow);
      }
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.LineLoop(geometry, material);
      line.userData.codembleOrbitGuide = true;
      line.renderOrder = -1;
      if (!layer.guideCertain) line.computeLineDistances();
      group.add(line);
    }

    const labelRadius = Math.max(...layer.radii);
    const label = dressing.guideLabel(layer.label);
    label.position.set(
      Math.cos(LABEL_ANGLE) * labelRadius,
      2.5,
      Math.sin(LABEL_ANGLE) * labelRadius,
    );
    label.userData.codembleOrbitGuideLabel = true;
    group.add(label);
  }

  return group;
}

export function disposeSystemOrbitGuides(group) {
  const materials = new Set();
  group.traverse((object) => {
    if (!object.userData?.codembleOrbitGuide) return;
    object.geometry?.dispose();
    if (object.material) materials.add(object.material);
  });
  for (const material of materials) material.dispose();
}
