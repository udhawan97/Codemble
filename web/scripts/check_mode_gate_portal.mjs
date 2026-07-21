import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/ModeControl.jsx", import.meta.url), "utf8");

assert.match(source, /import \{ createPortal \} from "react-dom";/);
assert.match(
  source,
  /return createPortal\([\s\S]*?<dialog[\s\S]*?document\.body,/,
  "the modal gate must not inherit display:none from responsive header chrome",
);

console.log("mode gate portal contract: ok");
