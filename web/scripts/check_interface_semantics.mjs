import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

for (const [name, label] of [
  ["project-path", "the local project path"],
  ["module-search", "the module finder"],
]) {
  const start = app.indexOf(`name="${name}"`);
  assert.notEqual(start, -1, `${label} has a stable form-control name`);
  const input = app.slice(start, app.indexOf("/>", start));
  assert.match(input, /autoComplete="off"/, `${label} does not invite credential autofill`);
  assert.match(input, /spellCheck={false}/, `${label} does not mark code identifiers as misspelled`);
}

assert.match(
  styles,
  /html\s*{[^}]*color-scheme:\s*dark;/s,
  "native browser controls inherit the app's dark palette",
);
assert.match(
  styles,
  /\.map-legend,\s*\.map-view\s*{[^}]*background-image:/s,
  "the Map column shares the visible scroll continuation cue used by long panels",
);
assert.match(
  styles,
  /\.map-view\s*{[^}]*background-color:\s*var\(--cm-ground\);/s,
  "the Map background does not erase its shared scroll cue",
);

console.log("interface semantics contracts passed");
