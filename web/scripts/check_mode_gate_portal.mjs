import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/ModeControl.jsx", import.meta.url), "utf8");

assert.match(source, /import \{ createPortal \} from "react-dom";/);
assert.match(
  source,
  /return createPortal\([\s\S]*?<dialog[\s\S]*?document\.body,/,
  "the modal gate must not inherit display:none from responsive header chrome",
);
assert.match(source, /Choose your launch/, "first run must ask how the learner wants to enter");
assert.match(source, /Explore freely/, "the game-first route must be explicit");
assert.match(source, /Take a first flight/, "the guided route must be explicit");
assert.match(
  source,
  /Explanation detail/,
  "voyage and explanation depth must remain separate learner choices",
);
assert.match(
  source,
  /launchSelectionRef\.current\.modeTouched = true/,
  "the checked register must reach the launch action before React's next render",
);
assert.match(
  source,
  /launchSelectionRef\.current\.voyageTouched = true/,
  "the checked voyage must reach the launch action before React's next render",
);
assert.match(
  source,
  /input\[name="first-register"\]:checked/,
  "launch must read the browser-owned checked register at the action boundary",
);

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
assert.match(
  appSource,
  /onChoose=\{async[\s\S]*?const saved = await session\.dispatch\(\{[\s\S]*?type: "SET_MODE"/,
  "the selected register must persist before a guided voyage starts",
);
assert.match(
  appSource,
  /if \(!saved\)[\s\S]*?Launch was not saved/,
  "a refused register write must reopen the launch gate instead of starting a voyage",
);
assert.match(
  appSource,
  /pendingVoyage !== "guided"[\s\S]*?entrypointOpen[\s\S]*?visitFirstFlightStop\(0\)/,
  "guided intent must wait through Home calibration and resume after selection",
);

console.log("mode gate portal contract: ok");
