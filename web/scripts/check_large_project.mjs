/**
 * Cross-engine acceptance gate for Codemble's complete 5,000-module Map.
 *
 * The corpus and data root are disposable. Receipts contain timings, counts,
 * and byte totals only: never source, paths, graph payloads, or provider data.
 */

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium, webkit } from "playwright";

import { PROVIDER_ENVIRONMENT_KEYS } from "./capture_support.mjs";

const FILES = 5_000;
const BUDGETS = Object.freeze({
  coldActivationMs: 12_000,
  noChangeActivationMs: 2_500,
  serverPeakRssBytes: 512 * 1024 * 1024,
  domElements: 2_000,
  resourceBytes: 16 * 1024 * 1024,
  usableMs: 5_000,
  inputP95Ms: 200,
  canvasKeyboardMs: 200,
  eventLoopLagMs: 2_000,
  pageOverflowPx: 1,
});

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const repoRoot = path.dirname(webRoot);
const python = process.env.CODEMBLE_PYTHON || "python3.12";
const outputArgument = process.argv.indexOf("--output");
const output = outputArgument === -1 ? null : process.argv[outputArgument + 1];
if (outputArgument !== -1 && !output) throw new Error("--output requires a path");

const disposableRoot = mkdtempSync(path.join(tmpdir(), "codemble-scale-browser-"));
const projectRoot = path.join(disposableRoot, "project");
const dataRoot = path.join(disposableRoot, "data");
let child = null;
const results = [];
let serverEvidence = null;
let serverUrl = null;
let currentEngine = "backend";
let gateError = null;

try {
  try {
    generateProject(projectRoot);
    const server = await startCodemble(projectRoot, dataRoot);
    child = server.child;
    serverUrl = server.url;
    const coldActivationMs = await activateProject(server.url, projectRoot);
    const noChangeActivationMs = await reactivateProject(server.url, projectRoot);
    serverEvidence = {
      startupReadyMs: server.readyMs,
      coldActivationMs,
      noChangeActivationMs,
      peakRssBytes: null,
    };
    assert.ok(
      coldActivationMs <= BUDGETS.coldActivationMs,
      `cold activation ${coldActivationMs.toFixed(1)}ms exceeds ${BUDGETS.coldActivationMs}ms`,
    );
    assert.ok(
      noChangeActivationMs <= BUDGETS.noChangeActivationMs,
      `no-change activation ${noChangeActivationMs.toFixed(1)}ms exceeds ${BUDGETS.noChangeActivationMs}ms`,
    );

    for (const [engine, browserType] of [
      ["chromium", chromium],
      ["webkit", webkit],
    ]) {
      currentEngine = engine;
      const browser = await browserType.launch({ headless: true });
      try {
        const main = await checkCompleteMap(browser, engine, server.url);
        const recovery = await checkRecoveryAndNarrowLayout(
          browser,
          engine,
          server.url,
        );
        results.push({ engine, ...main, ...recovery });
      } finally {
        await browser.close();
      }
    }
  } catch (error) {
    gateError = error;
  }

  if (serverEvidence && serverUrl) {
    try {
      serverEvidence.peakRssBytes = await serverPeakRssBytes(serverUrl);
    } catch (error) {
      currentEngine = gateError ? "multiple" : "backend";
      gateError = gateError
        ? new Error(`${String(gateError.message || gateError)}; ${String(error.message || error)}`)
        : error;
    }
  }
  if (
    !gateError &&
    serverEvidence &&
    serverEvidence.peakRssBytes > BUDGETS.serverPeakRssBytes
  ) {
    currentEngine = "backend";
    gateError = new Error(
      `server peak RSS ${serverEvidence.peakRssBytes} exceeds ${BUDGETS.serverPeakRssBytes}`,
    );
  }

  const receipt = {
    schema_version: 4,
    status: gateError ? "fail" : "pass",
    fixture_kind: "deterministic-sparse-python-import-chain",
    files: FILES,
    server_startup_ready_ms: serverEvidence
      ? round(serverEvidence.startupReadyMs)
      : null,
    cold_activation_ms: serverEvidence
      ? round(serverEvidence.coldActivationMs)
      : null,
    no_change_activation_ms: serverEvidence
      ? round(serverEvidence.noChangeActivationMs)
      : null,
    server_peak_rss_bytes: serverEvidence?.peakRssBytes ?? null,
    backend_budget_pass:
      serverEvidence !== null &&
      serverEvidence.coldActivationMs <= BUDGETS.coldActivationMs &&
      serverEvidence.noChangeActivationMs <= BUDGETS.noChangeActivationMs &&
      serverEvidence.peakRssBytes !== null &&
      serverEvidence.peakRssBytes <= BUDGETS.serverPeakRssBytes,
    budgets: BUDGETS,
    engines: results,
    failure: gateError
      ? {
          engine: currentEngine,
          message: sourceFreeFailure(gateError),
        }
      : null,
  };
  emitReceipt(receipt);
  if (gateError) throw gateError;
  console.log(`large-project browser gate passed (${results.map((row) => row.engine).join(", ")})`);
} finally {
  if (child) await stopChild(child);
  assert.ok(
    path.basename(disposableRoot).startsWith("codemble-scale-browser-"),
    "refusing to remove an unexpected disposable root",
  );
  rmSync(disposableRoot, { force: true, recursive: true });
}

function emitReceipt(receipt) {
  const encoded = `${JSON.stringify(receipt, null, 2)}\n`;
  if (output) {
    writeFileSync(output, encoded, { encoding: "utf8", mode: 0o600 });
    chmodSync(output, 0o600);
  } else {
    process.stdout.write(encoded);
  }
}

function sourceFreeFailure(error) {
  return String(error?.message || error)
    .replaceAll(disposableRoot, "<disposable-project>")
    .replaceAll(repoRoot, "<repository>")
    .replace(/\u001b\[[0-9;]*m/g, "")
    .slice(0, 2_000);
}

async function checkCompleteMap(browser, engine, url) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  const problems = [];
  const responseBytes = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`page: ${error.message}`));
  page.on("response", (response) => {
    const value = Number(response.headers()["content-length"] || 0);
    if (Number.isFinite(value) && value > 0) responseBytes.push(value);
  });
  await installResponsivenessProbe(page);

  try {
    const started = performance.now();
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await settleAppOnMap(page);
    await page.locator(".architecture-map-canvas canvas").waitFor();
    await page.evaluate(() => document.fonts.ready);
    const usableMs = performance.now() - started;
    await page.waitForTimeout(250);

    const measurements = await page.evaluate(() => {
      const surface = document.querySelector(".architecture-map-canvas");
      const canvas = surface?.querySelector("canvas");
      const scroller = surface?.closest(".map-scroll");
      return {
        domElements: document.getElementsByTagName("*").length,
        boxes: Number(surface?.dataset.itemCount || 0),
        edges: Number(surface?.dataset.edgeCount || 0),
        visibleBoxes: Number(canvas?.dataset.visibleItems || 0),
        visibleEdges: Number(canvas?.dataset.visibleEdges || 0),
        scrollExtentHeight: scroller?.scrollHeight || 0,
        maxEventLoopLagMs: Math.max(0, ...(window.__codembleLoopLag || [0])),
        maxLongTaskMs: Math.max(0, ...(window.__codembleLongTasks || [0])),
        pageOverflowPx: Math.max(
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
          document.body.scrollWidth - document.body.clientWidth,
        ),
        performanceResourceBytes: [
          ...performance.getEntriesByType("navigation"),
          ...performance.getEntriesByType("resource"),
        ].reduce(
          (total, entry) => total + (entry.encodedBodySize || entry.transferSize || 0),
          0,
        ),
      };
    });
    const resourceBytes = Math.max(
      responseBytes.reduce((total, value) => total + value, 0),
      measurements.performanceResourceBytes,
    );

    assert.equal(problems.length, 0, `${engine}: ${problems.join("; ")}`);
    assert.equal(measurements.boxes, FILES, `${engine}: incomplete Map`);
    assert.equal(measurements.edges, FILES - 1, `${engine}: incomplete route mesh`);
    assert.ok(
      measurements.visibleBoxes > 0 && measurements.visibleBoxes < FILES,
      `${engine}: canvas delivery did not virtualize the complete Map`,
    );
    assert.ok(
      measurements.scrollExtentHeight > 100_000,
      `${engine}: complete backend geometry did not reach the native scroll surface`,
    );
    assert.ok(
      measurements.domElements <= BUDGETS.domElements,
      `${engine}: ${measurements.domElements} DOM elements exceed ${BUDGETS.domElements}`,
    );
    assert.ok(
      resourceBytes <= BUDGETS.resourceBytes,
      `${engine}: ${resourceBytes} resource bytes exceed ${BUDGETS.resourceBytes}`,
    );
    assert.ok(
      usableMs <= BUDGETS.usableMs,
      `${engine}: Map usable in ${usableMs.toFixed(1)}ms, budget ${BUDGETS.usableMs}ms`,
    );
    assert.ok(
      measurements.maxEventLoopLagMs <= BUDGETS.eventLoopLagMs,
      `${engine}: event-loop lag ${measurements.maxEventLoopLagMs.toFixed(1)}ms`,
    );
    assert.ok(
      measurements.maxLongTaskMs <= BUDGETS.eventLoopLagMs,
      `${engine}: long task ${measurements.maxLongTaskMs.toFixed(1)}ms`,
    );
    assert.ok(
      measurements.pageOverflowPx <= BUDGETS.pageOverflowPx,
      `${engine}: desktop page overflow ${measurements.pageOverflowPx}px`,
    );

    const canvasKeyboardMs = await reachFinalCanvasModule(page, engine);
    assert.ok(
      canvasKeyboardMs <= BUDGETS.canvasKeyboardMs,
      `${engine}: canvas End-key arrival ${canvasKeyboardMs.toFixed(1)}ms exceeds ${BUDGETS.canvasKeyboardMs}ms`,
    );
    const inputP95Ms = await findFinalModuleByKeyboard(page, engine);
    assert.ok(
      inputP95Ms <= BUDGETS.inputP95Ms,
      `${engine}: Finder input p95 ${inputP95Ms.toFixed(1)}ms`,
    );

    return {
      usable_ms: round(usableMs),
      dom_elements: measurements.domElements,
      architecture_boxes: measurements.boxes,
      architecture_edges: measurements.edges,
      visible_architecture_boxes: measurements.visibleBoxes,
      visible_architecture_edges: measurements.visibleEdges,
      map_scroll_extent_height: measurements.scrollExtentHeight,
      canvas_keyboard_ms: round(canvasKeyboardMs),
      resource_bytes: resourceBytes,
      input_p95_ms: round(inputP95Ms),
      max_event_loop_lag_ms: round(measurements.maxEventLoopLagMs),
      max_long_task_ms: round(measurements.maxLongTaskMs),
    };
  } finally {
    await context.close();
  }
}

async function checkRecoveryAndNarrowLayout(browser, engine, url) {
  const context = await browser.newContext({
    viewport: { width: 320, height: 640 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  await page.route("**/api/map", (route) => route.abort());
  try {
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await settleOpeningDecisions(page);
    await page.locator(".map-state").waitFor();
    await page.unroute("**/api/map");
    const started = performance.now();
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await page.locator(".architecture-map-canvas canvas").waitFor();
    await page.waitForFunction(
      () =>
        Number(
          document.querySelector(".architecture-map-canvas canvas")?.dataset
            .visibleItems || 0,
        ) > 0,
      undefined,
      { timeout: BUDGETS.usableMs },
    );
    const recoveryMs = performance.now() - started;
    const narrow = await page.evaluate(() => ({
      boxes: Number(document.querySelector(".architecture-map-canvas")?.dataset.itemCount || 0),
      visibleBoxes: Number(document.querySelector(".architecture-map-canvas canvas")?.dataset.visibleItems || 0),
      pageOverflowPx: Math.max(
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
        document.body.scrollWidth - document.body.clientWidth,
      ),
    }));
    assert.equal(narrow.boxes, FILES, `${engine}: recovery returned an incomplete Map`);
    assert.ok(narrow.visibleBoxes > 0, `${engine}: recovery left the canvas blank`);
    assert.ok(
      recoveryMs <= BUDGETS.usableMs,
      `${engine}: Map recovery took ${recoveryMs.toFixed(1)}ms`,
    );
    assert.ok(
      narrow.pageOverflowPx <= BUDGETS.pageOverflowPx,
      `${engine}: 320px page overflow ${narrow.pageOverflowPx}px`,
    );
    return {
      recovery_ms: round(recoveryMs),
      narrow_page_overflow_px: narrow.pageOverflowPx,
    };
  } finally {
    await context.close();
  }
}

async function reachFinalCanvasModule(page, engine) {
  const surface = page.locator(".architecture-map-canvas");
  await surface.focus();
  await surface.evaluate((node) => {
    window.__codembleCanvasKeys = [];
    node.addEventListener("keydown", (event) => {
      window.__codembleCanvasKeys.push(event.key);
    });
  });
  const initialDescendant = await surface.getAttribute("aria-activedescendant");
  const initialLabel = await surface.locator(".map-canvas-active-option").innerText();
  const started = performance.now();
  await surface.press("End");
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  const active = surface.locator(".map-canvas-active-option");
  const diagnostic = await surface.evaluate((node) => ({
    activeDescendant: node.getAttribute("aria-activedescendant"),
    activeElementClass: document.activeElement?.className,
    keys: window.__codembleCanvasKeys,
    scrollTop: node.closest(".map-scroll")?.scrollTop,
  }));
  assert.notEqual(
    await active.innerText(),
    initialLabel,
    `${engine}: End did not reach the final canvas module (${JSON.stringify(diagnostic)})`,
  );
  const accessibility = await active.evaluate((option) => ({
    id: option.id,
    position: option.getAttribute("aria-posinset"),
    size: option.getAttribute("aria-setsize"),
  }));
  assert.notEqual(
    accessibility.id,
    initialDescendant,
    `${engine}: active-descendant identity did not move with the final module`,
  );
  assert.deepEqual(
    { position: accessibility.position, size: accessibility.size },
    { position: String(FILES), size: String(FILES) },
    `${engine}: active canvas option does not announce its position in the complete set`,
  );
  return performance.now() - started;
}

async function findFinalModuleByKeyboard(page, engine) {
  await page.keyboard.press("Meta+K");
  const finder = page.locator(".module-finder[open]");
  await finder.waitFor();
  const input = finder.getByRole("searchbox", { name: "Find a module by name or path" });
  await input.evaluate((node) => {
    window.__codembleInputLatency = [];
    node.addEventListener("input", () => {
      const started = performance.now();
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          window.__codembleInputLatency.push(performance.now() - started);
        }),
      );
    });
  });
  await input.pressSequentially("module_04999");
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const option = finder.getByRole("option").first();
  await option.waitFor();
  assert.match(await option.innerText(), /module_04999/, `${engine}: final module is not findable`);
  await page.keyboard.press("Enter");
  await finder.waitFor({ state: "detached" });
  await page.locator(".orientation-copy--system").waitFor();
  try {
    await page.waitForFunction(
      () => document.activeElement?.classList.contains("orientation-copy--system"),
      null,
      { timeout: 2_000 },
    );
  } catch (error) {
    const diagnostic = await page.evaluate(() => ({
      activeTag: document.activeElement?.tagName,
      activeClass: document.activeElement?.className,
      activeText: document.activeElement?.textContent?.trim().slice(0, 120),
      breadcrumb: document.querySelector(".location [aria-current='page']")?.textContent,
      systemConnected: Boolean(document.querySelector(".orientation-copy--system")),
    }));
    throw new Error(`${engine}: Finder focus handoff failed: ${JSON.stringify(diagnostic)}`, {
      cause: error,
    });
  }
  assert.match(
    await page.locator(".location [aria-current='page']").innerText(),
    /module_04999/,
    `${engine}: Finder did not arrive at the final module`,
  );
  const latencies = await page.evaluate(() => window.__codembleInputLatency || []);
  assert.ok(latencies.length >= 12, `${engine}: Finder latency probe did not observe every input`);
  return percentile(latencies, 0.95);
}

async function settleAppOnMap(page) {
  await settleOpeningDecisions(page);
  const mapButton = page
    .getByRole("navigation", { name: "View layer" })
    .getByRole("button", { name: /^(Diagram|Map)$/ });
  if ((await mapButton.getAttribute("aria-pressed")) !== "true") await mapButton.click();
}

async function settleOpeningDecisions(page) {
  let stableReadyChecks = 0;
  for (let step = 0; step < 20; step += 1) {
    const mode = page.locator(".mode-gate[open]");
    if (await mode.count()) {
      stableReadyChecks = 0;
      await mode
        .getByRole("button", { name: "New to coding?", exact: true })
        .click({ timeout: BUDGETS.usableMs });
    } else {
      const home = page.locator(".entrypoint-picker[open]");
      if (await home.count()) {
        stableReadyChecks = 0;
        await home
          .locator(".entrypoint-candidates button")
          .first()
          .click({ timeout: BUDGETS.usableMs });
      } else {
        const coach = page.locator(".coach-marks[open]");
        if (await coach.count()) {
          stableReadyChecks = 0;
          await coach
            .getByRole("button", { name: "Skip", exact: true })
            .click({ timeout: BUDGETS.usableMs });
        } else if (await page.locator(".app-shell").count()) {
          stableReadyChecks += 1;
          if (stableReadyChecks >= 3) return;
        }
      }
    }
    await page.waitForTimeout(150);
  }
  await page.locator(".app-shell").waitFor();
}

async function installResponsivenessProbe(page) {
  await page.addInitScript(() => {
    window.__codembleLoopLag = [];
    window.__codembleLongTasks = [];
    let expected = performance.now() + 50;
    setInterval(() => {
      const now = performance.now();
      window.__codembleLoopLag.push(Math.max(0, now - expected));
      expected = now + 50;
    }, 50);
    if (globalThis.PerformanceObserver?.supportedEntryTypes?.includes("longtask")) {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) window.__codembleLongTasks.push(entry.duration);
      }).observe({ type: "longtask", buffered: true });
    }
  });
}

function generateProject(destination) {
  mkdirSync(destination, { recursive: true });
  for (let index = 0; index < FILES; index += 1) {
    const previous = index > 0 ? `import module_${String(index - 1).padStart(5, "0")}\n\n` : "";
    const name = String(index).padStart(5, "0");
    const body =
      index === FILES - 1
        ? `${previous}def main() -> int:\n    return module_${String(index - 1).padStart(5, "0")}.function_${String(index - 1).padStart(5, "0")}()\n\nif __name__ == "__main__":\n    main()\n`
        : `${previous}def function_${name}() -> int:\n    return ${index}\n`;
    writeFileSync(path.join(destination, `module_${name}.py`), body, "utf8");
  }
}

async function startCodemble(project, data) {
  const port = await openPort();
  const env = {
    ...process.env,
    CODEMBLE_DATA_DIR: data,
    PYTHONUNBUFFERED: "1",
  };
  for (const key of PROVIDER_ENVIRONMENT_KEYS) delete env[key];
  const started = performance.now();
  const processChild = spawn(
    python,
    [
      path.join(repoRoot, "scripts", "serve_large_project_gate.py"),
      "--browse-root",
      path.dirname(project),
      "--max-files",
      String(FILES),
      "--port",
      String(port),
    ],
    {
      cwd: repoRoot,
      env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let outputBuffer = "";
  processChild.stdout.on("data", (chunk) => {
    outputBuffer = `${outputBuffer}${chunk}`.slice(-20_000);
  });
  processChild.stderr.on("data", (chunk) => {
    outputBuffer = `${outputBuffer}${chunk}`.slice(-20_000);
  });
  const url = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (processChild.exitCode !== null) {
      throw new Error(`Codemble exited before readiness:\n${outputBuffer}`);
    }
    try {
      const response = await fetch(url, { redirect: "error" });
      if (response.ok) {
        return {
          child: processChild,
          url,
          readyMs: performance.now() - started,
        };
      }
    } catch {
      // The disposable loopback server is not ready yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  await stopChild(processChild);
  throw new Error(`Codemble did not become ready:\n${outputBuffer}`);
}

async function activateProject(url, project) {
  const started = performance.now();
  const selected = await fetch(`${url}/api/picker/select`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path: project }),
  });
  if (selected.status !== 202) {
    throw new Error(`project activation returned ${selected.status}: ${await selected.text()}`);
  }
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const response = await fetch(`${url}/api/picker/progress`);
    if (!response.ok) throw new Error(`activation progress returned ${response.status}`);
    const progress = await response.json();
    if (progress.state === "ready") return performance.now() - started;
    if (progress.state === "error") {
      throw new Error(`project activation failed: ${String(progress.error || "unknown error")}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("project activation did not complete within 30 seconds");
}

async function reactivateProject(url, project) {
  const released = await fetch(`${url}/api/picker/reset`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ confirmed: true }),
  });
  if (!released.ok) {
    throw new Error(`project release returned ${released.status}: ${await released.text()}`);
  }
  return activateProject(url, project);
}

async function serverPeakRssBytes(url) {
  const response = await fetch(`${url}/__scale_gate__/metrics`);
  if (!response.ok) throw new Error(`backend high-water metric returned ${response.status}`);
  const payload = await response.json();
  assert.ok(
    Number.isSafeInteger(payload.max_rss_bytes) && payload.max_rss_bytes > 0,
    "backend high-water metric was not a positive integer",
  );
  return payload.max_rss_bytes;
}

function openPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

async function stopChild(processChild) {
  if (processChild.exitCode !== null) return;
  const exited = new Promise((resolve) => processChild.once("exit", resolve));
  processChild.kill("SIGTERM");
  await Promise.race([
    exited,
    new Promise((resolve) => setTimeout(resolve, 3_000)),
  ]);
  if (processChild.exitCode === null) {
    processChild.kill("SIGKILL");
    await exited;
  }
}

function percentile(values, fraction) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * fraction) - 1)];
}

function round(value) {
  return Math.round(value * 1_000) / 1_000;
}
