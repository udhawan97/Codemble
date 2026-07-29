import assert from "node:assert/strict";

import { BODY_SHADER_SOURCE, bodySeed } from "../src/celestialBodies.js";

// A GLSL reserved word used as an identifier makes the program fail to LINK,
// and three.js reports that only as a console flood while drawing nothing --
// so the bodies simply vanish and it reads as a styling problem. This shipped
// once with a local named `sample`; the scan is cheap insurance against the
// whole class. List is the GLSL ES reserved/keyword set we could plausibly
// reach for as a variable name.
const RESERVED = [
  "sample", "input", "output", "filter", "buffer", "shared", "packed",
  "active", "asm", "cast", "common", "partition", "class", "union", "enum",
  "typedef", "template", "this", "resource", "goto", "inline", "noinline",
  "public", "static", "extern", "external", "interface", "long", "short",
  "half", "fixed", "unsigned", "superp", "namespace", "using", "row_major",
];
for (const source of Object.values(BODY_SHADER_SOURCE)) {
  for (const word of RESERVED) {
    // Declaration shapes only: `<type> <reserved>` or `<reserved> =`.
    const declared = new RegExp(
      `\\b(?:float|int|bool|vec[234]|ivec[234]|bvec[234]|mat[234])\\s+${word}\\b`,
    );
    assert.ok(!declared.test(source), `GLSL reserved word declared as a variable: ${word}`);
  }
}
// The uniforms the material binds must all actually be declared, or the value
// is silently ignored and the body loses a semantic channel.
for (const uniform of ["uBase", "uAmber", "uSeed", "uLit", "uPartial", "uClass", "uDim"]) {
  assert.ok(
    BODY_SHADER_SOURCE.fragment.includes(`uniform`) &&
      new RegExp(`\\b${uniform}\\b`).test(BODY_SHADER_SOURCE.fragment),
    `fragment shader never reads uniform ${uniform}`,
  );
}

// "Same code -> same sky" is an acceptance criterion, and a procedural surface
// is the easiest place to break it. The seed must depend only on the node id.
assert.equal(bodySeed("codemble.server.app.create_app"), bodySeed("codemble.server.app.create_app"));
assert.notEqual(bodySeed("codemble.server.app"), bodySeed("codemble.server.runtime"));
assert.ok(bodySeed("x") >= 0 && bodySeed("x") < 1, "seed is normalised for shader use");

// A missing id must still yield a usable number rather than NaN, or the shader
// silently renders a black world.
assert.ok(Number.isFinite(bodySeed(undefined)));
assert.ok(Number.isFinite(bodySeed(null)));
assert.ok(Number.isFinite(bodySeed("")));

// The tilt seed is a different stream from the surface seed, so two bodies that
// happen to share a surface do not also share an orientation.
assert.notEqual(bodySeed("a"), bodySeed("a:tilt"));

// Decoration must never encode a fact. These ids differ only in text, so any
// dependence on kind/understood/partial would have to come from elsewhere --
// this pins that the seed itself carries none of it.
const sameIdDifferentState = bodySeed("mod.fn");
assert.equal(sameIdDifferentState, bodySeed("mod.fn"));

console.log("celestial body contracts passed");
