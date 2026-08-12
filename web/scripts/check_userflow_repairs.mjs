/**
 * Browser contracts for the three repaired audit journeys.
 *
 * This gate owns two disposable Codemble processes: one bound to this checkout
 * and one unbound picker. They use separate data roots, inherit no provider
 * credentials, and are always stopped in `finally`, so a UI check cannot read
 * or change a developer's real progress.
 */

import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

import { chromium, webkit } from "playwright";

import { PROVIDER_ENVIRONMENT_KEYS } from "./capture_support.mjs";
import { READ_ONLY_SERVER_UNAVAILABLE } from "../src/localServerErrors.js";

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const repoRoot = path.dirname(webRoot);
const python = process.env.CODEMBLE_PYTHON || "python";
const dataRoots = [
  mkdtempSync(path.join(tmpdir(), "codemble-userflow-project-")),
  mkdtempSync(path.join(tmpdir(), "codemble-userflow-picker-")),
];
const children = [];
const results = [];

try {
  const project = await startCodemble({ project: repoRoot, dataRoot: dataRoots[0] });
  const picker = await startCodemble({ project: null, dataRoot: dataRoots[1] });

  for (const [engine, browserType] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await browserType.launch({ headless: true });
    try {
      await checkHomeGeometry(browser, engine, project.url);
      await checkGuidanceFocus(browser, engine, project.url);
      await checkPickerRecovery(browser, engine, picker.url);
    } finally {
      await browser.close();
    }
  }
} finally {
  await Promise.all(children.map(stopChild));
  for (const dataRoot of dataRoots) rmSync(dataRoot, { force: true, recursive: true });
}

for (const result of results) console.log(`PASS  ${result}`);
console.log(`user-flow repair contracts passed (${results.length} assertions)`);

async function checkHomeGeometry(browser, engine, url) {
  for (const viewport of [
    { width: 1440, height: 900, fullCandidate: true },
    { width: 320, height: 640, fullCandidate: true },
    { width: 320, height: 400, fullCandidate: false },
  ]) {
    const page = await browser.newPage({ viewport });
    page.setDefaultTimeout(15_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await openHomeDialog(page);
      const measured = await page.evaluate(() => {
        const dialog = document.querySelector(".entrypoint-picker[open]");
        const scroll = document.querySelector(".entrypoint-scroll");
        const candidate = document.querySelector(".entrypoint-candidates button");
        const exit = document.querySelector(".entrypoint-continue");
        if (!dialog || !scroll || !candidate || !exit) return null;
        const d = dialog.getBoundingClientRect();
        const s = scroll.getBoundingClientRect();
        const c = candidate.getBoundingClientRect();
        const e = exit.getBoundingClientRect();
        const intersection = {
          width: Math.max(0, Math.min(c.right, s.right) - Math.max(c.left, s.left)),
          height: Math.max(0, Math.min(c.bottom, s.bottom) - Math.max(c.top, s.top)),
        };
        return {
          dialogRect: { top: d.top, right: d.right, bottom: d.bottom, left: d.left },
          exitRect: { top: e.top, right: e.right, bottom: e.bottom, left: e.left },
          dialogInView:
            d.top >= -1 && d.left >= -1 && d.bottom <= innerHeight + 1 && d.right <= innerWidth + 1,
          exitInView:
            e.top >= d.top - 1 && e.bottom <= d.bottom + 1 && e.left >= d.left - 1 && e.right <= d.right + 1,
          fullCandidate:
            intersection.height >= c.height - 1 && intersection.width >= c.width - 1,
          candidateFocused: document.activeElement === candidate,
          listVisible: scroll.clientHeight > 0,
          listScrollable: scroll.scrollHeight > scroll.clientHeight + 1,
          horizontalOverflow: Math.max(
            document.documentElement.scrollWidth - document.documentElement.clientWidth,
            dialog.scrollWidth - dialog.clientWidth,
          ),
        };
      });
      const label = `${engine} Home ${viewport.width}x${viewport.height}`;
      assert.ok(measured, `${label}: the Home dialog did not render its decision list`);
      assert.equal(
        measured.dialogInView,
        true,
        `${label}: dialog leaves the viewport (${JSON.stringify(measured)})`,
      );
      assert.equal(
        measured.exitInView,
        true,
        `${label}: explicit way out is clipped (${JSON.stringify(measured)})`,
      );
      assert.equal(measured.candidateFocused, true, `${label}: first ranked candidate does not own focus`);
      assert.equal(measured.listVisible, true, `${label}: decision list has no visible block size`);
      assert.ok(measured.horizontalOverflow <= 1, `${label}: horizontal overflow is ${measured.horizontalOverflow}px`);
      if (viewport.fullCandidate) {
        assert.equal(measured.fullCandidate, true, `${label}: focused candidate is only partly visible`);
      } else {
        assert.equal(measured.listScrollable, true, `${label}: short list is neither complete nor scrollable`);
      }
      results.push(label);
    } finally {
      await page.close();
    }
  }
}

async function checkGuidanceFocus(browser, engine, url) {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 320, height: 720 },
  ]) {
    const page = await browser.newPage({ viewport });
    page.setDefaultTimeout(15_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleApp(page);
      await openStudy(page);
      await followStudyGuidance(page);
      await assertChecksHeadingFocus(page, `${engine} ${viewport.width}x${viewport.height}`);

      await page.keyboard.press("Escape");
      await assertReturnedToProve(page, `${engine} ${viewport.width}x${viewport.height} Escape`);

      await openStudy(page);
      await followStudyGuidance(page);
      await assertChecksHeadingFocus(page, `${engine} ${viewport.width}x${viewport.height}`);
      await page.locator(".check-panel").getByRole("button", { name: "Close", exact: true }).click();
      await assertReturnedToProve(page, `${engine} ${viewport.width}x${viewport.height} Close`);
      results.push(`${engine} guidance focus ${viewport.width}x${viewport.height}`);
    } finally {
      await page.close();
    }
  }
}

async function checkPickerRecovery(browser, engine, url) {
  const page = await browser.newPage({ viewport: { width: 320, height: 640 } });
  page.setDefaultTimeout(15_000);
  try {
    await page.goto(url, { waitUntil: "networkidle" });
    const pathBefore = await page.locator(".picker-path").innerText();
    const folder = page.locator(".picker-browser li button").filter({ hasText: /\/$/ }).first();
    assert.ok(await folder.count(), `${engine} picker: no child folder is available to browse`);
    const folderName = (await folder.innerText()).trim().replace(/\/$/, "");

    await page.route("**/api/picker/browse**", (route) => route.abort());
    await folder.click();
    const retry = page.getByRole("button", { name: "Try this folder again", exact: true });
    await retry.waitFor();
    assert.equal(
      await page.getByRole("alert").innerText(),
      READ_ONLY_SERVER_UNAVAILABLE,
      `${engine} picker: browser-specific transport copy leaked`,
    );
    assert.equal(await retry.evaluate((node) => document.activeElement === node), true,
      `${engine} picker: retry did not receive focus`);
    assert.equal(await page.locator(".picker-path").innerText(), pathBefore,
      `${engine} picker: failed browse discarded the last successful folder`);

    await page.keyboard.press("Enter");
    await retry.waitFor();
    assert.equal(await retry.evaluate((node) => document.activeElement === node), true,
      `${engine} picker: repeated failure lost keyboard position`);

    await page.unroute("**/api/picker/browse**");
    await page.keyboard.press("Enter");
    await retry.waitFor({ state: "detached" });
    const heading = page.getByRole("heading", { name: "Browse folders", exact: true });
    await page.waitForFunction(() => document.activeElement?.id === "picker-browser-heading");
    assert.equal(await heading.evaluate((node) => document.activeElement === node), true,
      `${engine} picker: successful retry fell back to body`);
    const pathAfter = await page.locator(".picker-path").innerText();
    assert.notEqual(pathAfter, pathBefore, `${engine} picker: retry did not browse the failed target`);
    assert.ok(pathAfter.endsWith(folderName), `${engine} picker: retry reached ${pathAfter}, not ${folderName}`);
    results.push(`${engine} picker outage and retry`);
  } finally {
    await page.close();
  }
}

async function openHomeDialog(page) {
  for (let step = 0; step < 6; step += 1) {
    const home = page.locator(".entrypoint-picker[open]");
    if (await home.count()) return;
    const mode = page.locator(".mode-gate[open]");
    if (await mode.count()) {
      await mode.getByRole("button", { name: "New to coding?", exact: true }).click();
      await page.waitForTimeout(150);
      continue;
    }
    const coach = page.locator(".coach-marks[open]");
    if (await coach.count()) {
      await coach.getByRole("button", { name: "Skip", exact: true }).click();
      await page.waitForTimeout(150);
      continue;
    }
    await page.waitForTimeout(250);
  }
  let change = page.getByRole("button", { name: "Change Home", exact: true });
  if (!(await change.count()) || !(await change.first().isVisible())) {
    const menu = page.getByRole("button", { name: /^(Menu|More)$/ }).first();
    if (await menu.count()) await menu.click();
    change = page.getByRole("button", { name: "Change Home", exact: true });
  }
  await change.first().click();
  await page.locator(".entrypoint-picker[open]").waitFor();
}

async function settleApp(page) {
  for (let step = 0; step < 8; step += 1) {
    const mode = page.locator(".mode-gate[open]");
    if (await mode.count()) {
      await mode.getByRole("button", { name: "New to coding?", exact: true }).click();
    } else {
      const home = page.locator(".entrypoint-picker[open]");
      if (await home.count()) {
        await home.locator(".entrypoint-candidates button").first().click();
      } else {
        const coach = page.locator(".coach-marks[open]");
        if (await coach.count()) await coach.getByRole("button", { name: "Skip", exact: true }).click();
        else break;
      }
    }
    await page.waitForTimeout(200);
  }
  await page.locator(".app-shell").waitFor();
}

async function openStudy(page) {
  const read = page.getByRole("button", { name: "Read the source", exact: true });
  if (!(await read.count()) || !(await read.first().isVisible())) {
    const box = page.locator("[role='button'][aria-label*='structure']").first();
    await box.click({ force: true });
    await read.first().waitFor();
  }
  await read.first().click();
  await page.locator(".study-preview").waitFor();
}

async function followStudyGuidance(page) {
  const follow = page.locator(".hint-chip button").filter({ hasText: "Prove understanding" });
  await follow.waitFor();
  await follow.click();
  await page.locator(".check-panel").waitFor();
}

async function assertChecksHeadingFocus(page, label) {
  await page.waitForFunction(() => document.activeElement?.closest(".check-panel")?.matches(".check-panel") && document.activeElement?.tagName === "H1");
  const focus = await page.evaluate(() => ({
    tag: document.activeElement?.tagName,
    inPanel: Boolean(document.activeElement?.closest(".check-panel")),
  }));
  assert.deepEqual(focus, { tag: "H1", inPanel: true }, `${label}: checks heading does not own focus`);
}

async function assertReturnedToProve(page, label) {
  await page.locator(".check-panel").waitFor({ state: "detached" });
  await page.waitForFunction(() => document.activeElement?.textContent?.trim() === "Prove understanding");
  assert.equal(
    await page.getByRole("button", { name: "Prove understanding", exact: true }).evaluate(
      (node) => document.activeElement === node,
    ),
    true,
    `${label}: focus did not return to Prove understanding`,
  );
}

async function startCodemble({ project, dataRoot }) {
  const port = await openPort();
  const env = { ...process.env, CODEMBLE_DATA_DIR: dataRoot };
  for (const key of PROVIDER_ENVIRONMENT_KEYS) delete env[key];
  const args = ["-m", "codemble.cli"];
  if (project) args.push(project);
  args.push("--no-open", "--port", String(port));
  const child = spawn(python, args, {
    cwd: repoRoot,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.push(child);
  let output = "";
  child.stdout.on("data", (chunk) => { output += chunk; });
  child.stderr.on("data", (chunk) => { output += chunk; });
  const url = `http://127.0.0.1:${port}`;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`Codemble exited before readiness:\n${output}`);
    try {
      const response = await fetch(url);
      if (response.ok) return { child, url };
    } catch {
      // The listener is not ready yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Codemble did not become ready at ${url}:\n${output}`);
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

async function stopChild(child) {
  if (child.exitCode !== null) return;
  const exited = new Promise((resolve) => child.once("exit", resolve));
  child.kill("SIGTERM");
  await Promise.race([
    exited,
    new Promise((resolve) => setTimeout(resolve, 2000)),
  ]);
  if (child.exitCode === null) {
    child.kill("SIGKILL");
    await exited;
  }
}
