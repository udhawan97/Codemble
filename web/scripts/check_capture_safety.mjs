import assert from "node:assert/strict";

import {
  PROVIDER_ENVIRONMENT_KEYS,
  assertLoopbackCaptureUrl,
  buildCaptureEnvironment,
} from "./capture_support.mjs";

const environment = buildCaptureEnvironment(
  Object.fromEntries([
    ["PATH", "/usr/bin"],
    ...PROVIDER_ENVIRONMENT_KEYS.map((key) => [key, "must-not-survive"]),
  ]),
  "/tmp/disposable-codemble-data",
);

assert.equal(environment.PATH, "/usr/bin");
assert.equal(environment.CODEMBLE_DATA_DIR, "/tmp/disposable-codemble-data");
assert.equal(environment.PYTHONUNBUFFERED, "1");
for (const key of PROVIDER_ENVIRONMENT_KEYS) assert.equal(environment[key], undefined);

assert.equal(assertLoopbackCaptureUrl("http://127.0.0.1:8150").hostname, "127.0.0.1");
assert.equal(assertLoopbackCaptureUrl("http://localhost:8150").hostname, "localhost");
assert.throws(() => assertLoopbackCaptureUrl("https://127.0.0.1:8150"), /plain HTTP/);
assert.throws(() => assertLoopbackCaptureUrl("http://example.com"), /loopback/);

process.stdout.write("capture safety contracts passed\n");
