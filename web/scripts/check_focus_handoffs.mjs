import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const mode = readFileSync(new URL("../src/ModeControl.jsx", import.meta.url), "utf8");
const followHint = app.slice(
  app.indexOf("  function followHint()"),
  app.indexOf("  function dismissCoachmarks()"),
);

assert.match(app, /function restoreRailFocus/);
assert.match(
  followHint,
  /session\.getSnapshot\(\)\.showChecks[\s\S]*restoreRailFocus\(systemCopyRef\)/,
  "guidance must not steal focus back from a checks panel it just opened",
);
assert.match(
  app,
  /function closeChecks[\s\S]*?restoreRailFocus\(checksTriggerRef, systemCopyRef\)/,
  "closing hint-opened checks returns to the remounted prove control or its system context",
);
assert.doesNotMatch(
  followHint,
  /requestAnimationFrame/,
  "focus handoffs wait for a React commit task, not a software-WebGL frame",
);
assert.match(app, /const finderArrivalRef = useRef\(false\)/);
assert.match(app, /function goFromFinder[\s\S]*?finderArrivalRef\.current = true/);
assert.match(
  app,
  /function closeFinder\(\) \{[\s\S]*?if \(finderArrivalRef\.current\) return/,
  "the dialog close event cannot turn a selected arrival into a cancellation",
);
assert.match(
  app,
  /useLayoutEffect\(\(\) => \{[\s\S]*?finderArrivalRef\.current[\s\S]*?systemCopyRef\.current\?\.focus/,
  "Finder arrival focus waits for the committed module context",
);
assert.doesNotMatch(
  app.slice(app.indexOf("  function goFromFinder"), app.indexOf("  function followHint")),
  /requestAnimationFrame/,
  "Finder arrival cannot race a large React commit on the next frame",
);
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
