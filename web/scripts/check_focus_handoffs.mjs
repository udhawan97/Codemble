import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const mode = readFileSync(new URL("../src/ModeControl.jsx", import.meta.url), "utf8");

assert.match(app, /function restoreRailFocus/);
assert.match(app, /function goFromFinder[\s\S]*?systemCopyRef\.current\?\.focus/);
assert.match(app, /function dismissCoachmarks[\s\S]*?stageRef\.current\?\.focus/);
assert.match(app, /modeChosen === true && entrypointOpen/);
assert.match(app, /function IndexSidebar[\s\S]*?closeButtonRef/);
assert.match(app, /function EntrypointPicker[\s\S]*?firstActionRef/);
assert.match(app, /function StarChart[\s\S]*?headingRef/);
assert.match(app, /data-confirming=\{confirming \|\| undefined\}/);
assert.match(app, /matchMedia\("\(min-width: 40rem\)"\)/);
assert.doesNotMatch(
  mode,
  /checkedRadioRef/,
  "the first-run audience choice must not focus a toggle hidden inside compact Menu",
);

console.log("focus and compact-flow contracts passed");
