/**
 * Cross-engine receipt for the standalone private-share HTTPS viewer.
 *
 * Each engine gets a fresh in-memory share, a self-signed disposable TLS
 * endpoint, and an isolated browser context. The gate proves the page performs
 * no third-party request, creates no browser persistence, survives compact
 * layout, and becomes uniformly unavailable after header-authorized revocation.
 */

import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import https from "node:https";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium, webkit } from "playwright";

import { PROVIDER_ENVIRONMENT_KEYS } from "./capture_support.mjs";

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const repoRoot = path.dirname(webRoot);
const worktreePython = path.join(repoRoot, ".venv", "bin", "python");
const python = process.env.CODEMBLE_PYTHON || (existsSync(worktreePython) ? worktreePython : "python");
const tlsRoot = mkdtempSync(path.join(tmpdir(), "codemble-share-tls-"));
const cert = path.join(tlsRoot, "cert.pem");
const key = path.join(tlsRoot, "key.pem");
const viewCapability = Buffer.alloc(32, 1).toString("base64url");
const deleteCapability = Buffer.alloc(32, 2).toString("base64url");
const results = [];

try {
  createCertificate();
  for (const [engine, browserType] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    await checkEngine(engine, browserType);
  }
} finally {
  rmSync(tlsRoot, { force: true, recursive: true });
}

for (const result of results) console.log(`✓ ${result}`);
console.log(`Share delivery browser gate: ${results.length} receipts passed`);

function createCertificate() {
  const result = spawnSync(
    "openssl",
    [
      "req",
      "-x509",
      "-newkey",
      "rsa:2048",
      "-nodes",
      "-keyout",
      key,
      "-out",
      cert,
      "-days",
      "1",
      "-subj",
      "/CN=127.0.0.1",
      "-addext",
      "subjectAltName=IP:127.0.0.1",
    ],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 0, `could not create disposable TLS certificate: ${result.stderr}`);
}

async function checkEngine(engine, browserType) {
  const port = await freePort();
  const server = startServer(port);
  const origin = `https://127.0.0.1:${port}`;
  try {
    await waitForServer(origin, server);
    assert.equal(
      await httpsStatus(`${origin}/v/${viewCapability}?target=must-not-survive`),
      404,
      `${engine}: query-bearing capability target was accepted`,
    );
    assert.equal(await httpsStatus(`${origin}/anything/${viewCapability}`), 404);
    assert.equal(await httpsStatus(`${origin}/revoke/${deleteCapability}`), 404);
    const browser = await browserType.launch({ headless: true });
    try {
      const context = await browser.newContext({
        ignoreHTTPSErrors: true,
        viewport: { width: 320, height: 640 },
      });
      const page = await context.newPage();
      const requested = [];
      const errors = [];
      page.on("request", (request) => requested.push(request.url()));
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
      });

      const viewUrl = `${origin}/v/${viewCapability}`;
      const response = await page.goto(viewUrl, { waitUntil: "domcontentloaded" });
      assert(response, `${engine}: viewer returned no main-document response`);
      assert.equal(response.status(), 200, `${engine}: viewer did not authorize its capability`);
      const responseHeaders = await response.allHeaders();
      assertPrivateHeaders(responseHeaders, engine);
      assert.equal(responseHeaders["set-cookie"], undefined, `${engine}: viewer set a cookie`);
      await page.getByRole("heading", { name: "Codemble share", exact: true }).waitFor();
      assert.equal(await page.locator("script, form, iframe, object, embed").count(), 0);
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        true,
        `${engine}: 320px viewer overflows horizontally`,
      );
      assert.equal(
        await page.evaluate(() => document.referrer),
        "",
        `${engine}: viewer inherited a referrer`,
      );
      assert.deepEqual(await browserPersistence(page), emptyPersistence());
      assert.deepEqual(await context.cookies(), [], `${engine}: viewer persisted a cookie`);
      assert(
        requested.every((url) => url.startsWith(`${origin}/`)),
        `${engine}: viewer made a third-party request: ${requested.join(", ")}`,
      );

      const reload = await page.reload({ waitUntil: "domcontentloaded" });
      assert(reload, `${engine}: reload returned no response`);
      assert.equal(reload.status(), 200, `${engine}: inert reload changed view authority`);
      assert.deepEqual(await browserPersistence(page), emptyPersistence());
      assert.deepEqual(await context.cookies(), [], `${engine}: reload persisted a cookie`);
      assert.deepEqual(errors, [], `${engine}: viewer browser errors before revocation`);

      const revocation = await context.request.post(`${origin}/revoke`, {
        data: { confirmed: true },
        headers: { Authorization: `Bearer ${deleteCapability}` },
      });
      assert.equal(revocation.status(), 200, `${engine}: confirmed revocation failed`);
      assert.equal((await revocation.json()).status, "revoked");
      assertPrivateHeaders(revocation.headers(), engine);

      const unavailable = await page.reload({ waitUntil: "domcontentloaded" });
      assert(unavailable, `${engine}: revoked reload returned no response`);
      assert.equal(unavailable.status(), 404, `${engine}: revoked share resurrected`);
      assertPrivateHeaders(await unavailable.allHeaders(), engine);
      await context.close();
      results.push(`${engine} HTTPS headers, compact view, no storage, revoke`);
    } finally {
      await browser.close();
    }
  } finally {
    await stopServer(server);
  }

  const output = server.output.join("");
  assert(!output.includes(viewCapability), `${engine}: access logs contain the view capability`);
  assert(!output.includes(deleteCapability), `${engine}: logs contain the deletion capability`);
  assert(!output.includes("target=must-not-survive"), `${engine}: logs contain a raw query target`);
  assert(
    output.includes("/v/%5Bredacted%5D"),
    `${engine}: access logs do not show encoded path redaction`,
  );
  assert(
    output.includes("/%5Bredacted%5D"),
    `${engine}: unknown access targets were not normalized`,
  );
  results.push(`${engine} token-redacted lifecycle and access logs`);
}

function startServer(port) {
  const environment = { ...process.env };
  for (const keyName of PROVIDER_ENVIRONMENT_KEYS) delete environment[keyName];
  environment.PYTHONPATH = environment.PYTHONPATH
    ? `${repoRoot}${path.delimiter}${environment.PYTHONPATH}`
    : repoRoot;
  const child = spawn(
    python,
    [
      "scripts/serve_share_delivery_fixture.py",
      "--port",
      String(port),
      "--cert",
      cert,
      "--key",
      key,
    ],
    { cwd: repoRoot, env: environment, stdio: ["ignore", "pipe", "pipe"] },
  );
  child.output = [];
  child.stdout.on("data", (chunk) => child.output.push(chunk.toString()));
  child.stderr.on("data", (chunk) => child.output.push(chunk.toString()));
  return child;
}

async function stopServer(child) {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await Promise.race([
    new Promise((resolve) => child.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, 5_000)),
  ]);
  if (child.exitCode === null) child.kill("SIGKILL");
}

async function waitForServer(origin, child) {
  let lastError = "server did not answer";
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error(`share fixture exited early (${child.exitCode}): ${child.output.join("")}`);
    }
    try {
      await httpsStatus(`${origin}/ready`);
      return;
    } catch (error) {
      lastError = error.message;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error(`${lastError}: ${child.output.join("")}`);
}

function httpsStatus(url) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, { rejectUnauthorized: false }, (response) => {
      response.resume();
      response.on("end", () => resolve(response.statusCode));
    });
    request.on("error", reject);
  });
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close((error) => {
        if (error) reject(error);
        else resolve(address.port);
      });
    });
  });
}

async function browserPersistence(page) {
  return page.evaluate(async () => ({
    cacheKeys: "caches" in window ? await caches.keys() : [],
    indexedDatabases:
      typeof indexedDB.databases === "function"
        ? (await indexedDB.databases()).map((database) => database.name || "")
        : [],
    local: localStorage.length,
    serviceWorkers:
      "serviceWorker" in navigator
        ? (await navigator.serviceWorker.getRegistrations()).map((registration) => registration.scope)
        : [],
    session: sessionStorage.length,
  }));
}

function emptyPersistence() {
  return {
    cacheKeys: [],
    indexedDatabases: [],
    local: 0,
    serviceWorkers: [],
    session: 0,
  };
}

function assertPrivateHeaders(headers, engine) {
  assert.equal(headers["cache-control"], "no-store, max-age=0", `${engine}: cache policy`);
  assert.equal(headers["referrer-policy"], "no-referrer", `${engine}: referrer policy`);
  assert.equal(headers["x-content-type-options"], "nosniff", `${engine}: MIME policy`);
  assert.match(headers["content-security-policy"], /default-src 'none'/);
  assert.match(headers["content-security-policy"], /script-src 'none'/);
  assert.match(headers["content-security-policy"], /style-src 'sha256-/);
}
