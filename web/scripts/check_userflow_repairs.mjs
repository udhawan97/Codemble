/**
 * Browser contracts for the three repaired audit journeys.
 *
 * This gate owns isolated Codemble processes for the product journey, picker,
 * four launch/register combinations, refused persistence, and Home-calibration
 * boundaries. They use disposable source/data roots, inherit no provider
 * credentials, and are always stopped in `finally`, so UI checks cannot read
 * or change a developer's real progress.
 */

import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
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
const sourceRoots = [];
const launchProjects = createLaunchProjects();

try {
  const project = await startCodemble({ project: repoRoot, dataRoot: dataRoots[0] });
  const picker = await startCodemble({ project: null, dataRoot: dataRoots[1] });

  for (const [engine, browserType] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const launchDataRoot = mkdtempSync(path.join(tmpdir(), `codemble-launch-${engine}-`));
    dataRoots.push(launchDataRoot);
    const launch = await startCodemble({
      project: launchProjects.ready,
      dataRoot: launchDataRoot,
    });
    const browser = await browserType.launch({ headless: true });
    try {
      await checkGuidedLaunchAndLanding(browser, engine, launch.url);
      await checkLaunchChoiceMatrix(browser, engine, launchProjects.ready);
      await checkRefusedLaunch(browser, engine, launchProjects.ready);
      await checkGuidedHomeCalibration(browser, engine, launchProjects);
      await checkHomeGeometry(browser, engine, project.url);
      await checkCompactRailEscape(browser, engine, project.url);
      await checkCompactQuizVisibility(browser, engine, project.url);
      await checkCanvasMapInteraction(browser, engine, project.url);
      await checkGuidanceFocus(browser, engine, project.url);
      await checkPickerRecovery(browser, engine, picker.url);
    } finally {
      await browser.close();
    }
  }
} finally {
  await Promise.all(children.map(stopChild));
  for (const dataRoot of dataRoots) rmSync(dataRoot, { force: true, recursive: true });
  for (const sourceRoot of sourceRoots) rmSync(sourceRoot, { force: true, recursive: true });
}

function createLaunchProjects() {
  const ready = mkdtempSync(path.join(tmpdir(), "codemble-launch-ready-"));
  const ambiguous = mkdtempSync(path.join(tmpdir(), "codemble-launch-ambiguous-"));
  const noHome = mkdtempSync(path.join(tmpdir(), "codemble-launch-no-home-"));
  sourceRoots.push(ready, ambiguous, noHome);
  writeFileSync(
    path.join(ready, "main.py"),
    "from helper import work\n\ndef main():\n    return work()\n\nif __name__ == '__main__':\n    main()\n",
  );
  writeFileSync(path.join(ready, "helper.py"), "def work():\n    return 'charted'\n");
  writeFileSync(
    path.join(ambiguous, "alpha.py"),
    "def main():\n    return 'alpha'\n\nif __name__ == '__main__':\n    main()\n",
  );
  writeFileSync(
    path.join(ambiguous, "beta.py"),
    "def main():\n    return 'beta'\n\nif __name__ == '__main__':\n    main()\n",
  );
  writeFileSync(path.join(noHome, "values.py"), "ANSWER = 42\n");
  return { ready, ambiguous, noHome };
}

async function checkGuidedLaunchAndLanding(browser, engine, url) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(30_000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    // A provider-free disposable server intentionally rejects optional model
    // narration; the landing brief, source, relationships, and language lens
    // remain local parser evidence. Keep actual runtime errors in the gate.
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) {
      pageErrors.push(message.text());
    }
  });
  try {
    await page.goto(url, { waitUntil: "networkidle" });
    const gate = page.locator(".mode-gate[open]");
    await gate.waitFor();
    assert.equal(
      await gate.getByRole("heading", { name: "Choose your launch", exact: true }).count(),
      1,
      `${engine}: first run does not begin with the launch decision`,
    );
    assert.equal(
      await gate.getByRole("radio", { name: /^Explore freely/ }).count(),
      1,
      `${engine}: free exploration is not a first-run choice`,
    );
    await gate.getByRole("radio", { name: /^Take a first flight/ }).check();
    await gate.getByRole("radio", { name: "I build software", exact: true }).check();
    assert.equal(
      await gate.locator('input[name="first-register"]:checked').getAttribute("value"),
      "expert",
      `${engine}: Expert selection did not reach the launch form`,
    );
    await gate.getByRole("button", { name: "Begin first flight", exact: true }).click();
    await page.locator(".flight-hud").waitFor();
    assert.match(
      await page.locator(".flight-hud").innerText(),
      /First flight · stop 1\/\d+/,
      `${engine}: guided launch did not expose voyage progress`,
    );
    const launchModeState = await page.evaluate(async () => ({
      ui: document.querySelector(".app-shell")?.getAttribute("data-mode"),
      stored: await fetch("/api/mode").then((response) => response.json()),
    }));
    assert.deepEqual(
      launchModeState,
      { ui: "expert", stored: { mode: "expert", chosen: true } },
      `${engine}: launch explanation choice did not reach the persistent register`,
    );

    await page.locator(".first-flight").getByRole("button", { name: "Land and learn" }).click();
    const study = page.locator(".study-preview");
    await study.waitFor();
    await study.getByRole("heading", { name: "Landing brief", exact: true }).waitFor();
    assert.equal(
      await study.locator('input[name="landing-register"][value="expert"]').isChecked(),
      true,
      `${engine}: landing did not retain the expert explanation`,
    );
    await study.locator('input[name="landing-register"][value="easy"]').check();
    assert.equal(
      await study.locator('input[name="landing-register"][value="easy"]').isChecked(),
      true,
      `${engine}: landing register cannot switch to Easy`,
    );
    assert.match(
      await study.locator(".landing-brief").innerText(),
      /Arriving links[\s\S]*Leaving links/i,
      `${engine}: landing brief does not explain where the structure connects`,
    );
    await page.getByRole("button", { name: "Prove understanding", exact: true }).click();
    await page.locator(".check-panel").waitFor();
    assert.equal(
      await page.locator(".check-panel").getAttribute("aria-label"),
      "Graph-derived understanding checks",
      `${engine}: guided landing did not continue into the existing quiz route`,
    );
    assert.deepEqual(pageErrors, [], `${engine}: guided launch browser errors`);
    results.push(`${engine} guided launch and Easy/Expert landing`);
  } finally {
    await page.close();
  }
}

async function checkLaunchChoiceMatrix(browser, engine, project) {
  for (const { voyage, register } of [
    { voyage: "explore", register: "easy" },
    { voyage: "explore", register: "expert" },
    { voyage: "guided", register: "easy" },
  ]) {
    const dataRoot = mkdtempSync(path.join(tmpdir(), `codemble-launch-${engine}-`));
    dataRoots.push(dataRoot);
    const launch = await startCodemble({ project, dataRoot });
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.setDefaultTimeout(20_000);
    try {
      await page.goto(launch.url, { waitUntil: "networkidle" });
      const gate = page.locator(".mode-gate[open]");
      await gate.waitFor();
      await completeModeGate(gate, { voyage, register });
      await gate.waitFor({ state: "detached" });
      await page.locator(".galaxy-frame").waitFor();
      const persisted = await page.evaluate(async () => ({
        mode: document.querySelector(".app-shell")?.getAttribute("data-mode"),
        stored: await fetch("/api/mode").then((response) => response.json()),
      }));
      assert.deepEqual(
        persisted,
        { mode: register, stored: { mode: register, chosen: true } },
        `${engine}: ${voyage}/${register} did not persist before launch`,
      );
      if (voyage === "guided") {
        await page.locator(".flight-hud").waitFor();
      } else {
        assert.equal(
          await page.locator(".flight-hud").count(),
          0,
          `${engine}: free ${register} launch started a guided flight`,
        );
      }
      results.push(`${engine} ${voyage}/${register} launch`);
    } finally {
      await page.close();
      await stopChild(launch.child);
    }
  }
}

async function checkRefusedLaunch(browser, engine, project) {
  const dataRoot = mkdtempSync(path.join(tmpdir(), `codemble-launch-refused-${engine}-`));
  dataRoots.push(dataRoot);
  const launch = await startCodemble({ project, dataRoot });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(20_000);
  try {
    await page.route("**/api/mode", async (route) => {
      if (route.request().method() === "PUT") {
        await route.fulfill({ status: 503, body: "mode write refused" });
        return;
      }
      await route.continue();
    });
    await page.goto(launch.url, { waitUntil: "networkidle" });
    const gate = page.locator(".mode-gate[open]");
    await gate.waitFor();
    await completeModeGate(gate, { voyage: "guided", register: "expert" });
    await gate.waitFor();
    await gate.getByRole("alert").waitFor();
    assert.match(
      await gate.getByRole("alert").innerText(),
      /Launch was not saved/,
      `${engine}: refused launch did not explain the retry`,
    );
    assert.equal(
      await page.locator(".flight-hud").count(),
      0,
      `${engine}: refused mode persistence still started First Flight`,
    );
    assert.deepEqual(
      await page.evaluate(async () => ({
        mode: document.querySelector(".app-shell")?.getAttribute("data-mode"),
        stored: await fetch("/api/mode").then((response) => response.json()),
      })),
      { mode: "easy", stored: { mode: "easy", chosen: false } },
      `${engine}: refused launch did not roll back to server-confirmed state`,
    );
    results.push(`${engine} refused launch stays gated`);
  } finally {
    await page.close();
    await stopChild(launch.child);
  }
}

async function checkGuidedHomeCalibration(browser, engine, projects) {
  const ambiguousRoot = mkdtempSync(path.join(tmpdir(), `codemble-home-ambiguous-${engine}-`));
  dataRoots.push(ambiguousRoot);
  const ambiguous = await startCodemble({
    project: projects.ambiguous,
    dataRoot: ambiguousRoot,
  });
  const ambiguousPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  ambiguousPage.setDefaultTimeout(20_000);
  try {
    await ambiguousPage.goto(ambiguous.url, { waitUntil: "networkidle" });
    await completeModeGate(ambiguousPage.locator(".mode-gate[open]"), {
      voyage: "guided",
      register: "easy",
    });
    const home = ambiguousPage.locator(".entrypoint-picker[open]");
    await home.waitFor();
    assert.match(
      await home.innerText(),
      /requested flight will begin there/,
      `${engine}: guided intent was not visible during Home calibration`,
    );
    await home.locator(".entrypoint-candidates button").first().click();
    await home.waitFor({ state: "detached" });
    await ambiguousPage.locator(".flight-hud").waitFor();
    results.push(`${engine} guided launch resumes after Home calibration`);
  } finally {
    await ambiguousPage.close();
    await stopChild(ambiguous.child);
  }

  const noHomeRoot = mkdtempSync(path.join(tmpdir(), `codemble-home-none-${engine}-`));
  dataRoots.push(noHomeRoot);
  const noHome = await startCodemble({ project: projects.noHome, dataRoot: noHomeRoot });
  const noHomePage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  noHomePage.setDefaultTimeout(20_000);
  try {
    await noHomePage.goto(noHome.url, { waitUntil: "networkidle" });
    await completeModeGate(noHomePage.locator(".mode-gate[open]"), {
      voyage: "guided",
      register: "expert",
    });
    const calibration = noHomePage.locator(".entrypoint-picker[open]");
    await calibration.waitFor();
    assert.match(
      await calibration.innerText(),
      /Codemble will not invent one/,
      `${engine}: no-Home guided launch did not state its evidence boundary`,
    );
    const fallback = calibration.getByRole("button", {
      name: "Explore without a flight",
      exact: true,
    });
    await fallback.click();
    await calibration.waitFor({ state: "detached" });
    assert.equal(
      await noHomePage.locator(".flight-hud").count(),
      0,
      `${engine}: no-Home fallback invented a guided flight`,
    );
    await noHomePage.locator(".galaxy-frame").waitFor();
    results.push(`${engine} no-Home guided fallback is explicit`);
  } finally {
    await noHomePage.close();
    await stopChild(noHome.child);
  }
}

async function checkCanvasMapInteraction(browser, engine, url) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(15_000);
  try {
    await page.goto(url, { waitUntil: "networkidle" });
    await settleApp(page);
    const mapTruth = await page.evaluate(async () => {
      const [mapResponse, graphResponse] = await Promise.all([
        fetch("/api/map"),
        fetch("/api/graph"),
      ]);
      if (!mapResponse.ok) throw new Error(`map truth returned ${mapResponse.status}`);
      if (!graphResponse.ok) throw new Error(`graph truth returned ${graphResponse.status}`);
      const map = await mapResponse.json();
      const graph = await graphResponse.json();
      const unreachableTarget = map.architecture.unreachable.at(-1);
      return {
        boxCount: map.architecture.boxes.length,
        unreachableCount: map.architecture.unreachable.length,
        unreachableTarget,
        unreachableFile:
          graph.nodes.find((node) => node.region === unreachableTarget)?.file ?? unreachableTarget,
      };
    });
    const architecture = page.locator(".architecture-map-canvas");
    assert.ok(
      mapTruth.unreachableCount > 8,
      `${engine}: complete-default fixture no longer has more than eight unreachable modules`,
    );
    assert.equal(
      Number(await architecture.getAttribute("data-item-count")),
      mapTruth.boxCount,
      `${engine}: default Architecture scene folded parser-owned modules`,
    );
    await architecture.focus();
    await architecture.press("Home");
    const allLanguageActive = await architecture.locator(".map-canvas-active-option").evaluate(
      (option) => ({ id: option.id, position: option.getAttribute("aria-posinset"), text: option.textContent }),
    );
    await architecture.press("Meta+K");
    const finder = page.locator(".module-finder[open]");
    await finder.waitFor();
    const search = finder.getByRole("searchbox", { name: "Find a module by name or path" });
    await search.fill(mapTruth.unreachableFile);
    await finder.getByRole("option").first().waitFor();
    await search.press("Enter");
    await finder.waitFor({ state: "detached" });
    assert.ok(
      (await page.locator(".location [aria-current='page']").innerText()).includes(mapTruth.unreachableTarget),
      `${engine}: Finder did not reach an unfolded-default unreachable module`,
    );
    const javascriptFocus = page.getByRole("button", { name: /^Focus JavaScript:/ });
    await javascriptFocus.click();
    await page.waitForFunction(
      () => document.querySelector(".language-focus button[aria-pressed='true']")?.getAttribute("aria-label")?.startsWith("Focus JavaScript:"),
    );
    const focusedArchitecture = page.locator(".architecture-map-canvas");
    await focusedArchitecture.focus();
    await focusedArchitecture.press("Home");
    const focusedLanguageActive = await focusedArchitecture.locator(".map-canvas-active-option").evaluate(
      (option) => ({ id: option.id, position: option.getAttribute("aria-posinset"), text: option.textContent }),
    );
    assert.equal(allLanguageActive.position, "1", `${engine}: all-language Home did not select position 1`);
    assert.equal(focusedLanguageActive.position, "1", `${engine}: focused language Home did not select position 1`);
    assert.notEqual(
      focusedLanguageActive.text,
      allLanguageActive.text,
      `${engine}: language projection did not replace the first active item fixture`,
    );
    assert.notEqual(
      focusedLanguageActive.id,
      allLanguageActive.id,
      `${engine}: active-descendant identity did not change for a same-position projection swap`,
    );
    const pythonFocus = page.getByRole("button", { name: /^Focus Python:/ });
    await pythonFocus.click();
    await page.waitForFunction(
      () => document.querySelector(".language-focus button[aria-pressed='true']")?.getAttribute("aria-label")?.startsWith("Focus Python:"),
    );
    await page.getByRole("button", { name: "What runs first", exact: true }).click();
    const surface = page.locator(".workflow-map-canvas");
    await surface.waitFor();
    await surface.focus();
    await surface.press("End");
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
    const focusedPosition = await surface.locator(".map-canvas-active-option").evaluate((option) => ({
      position: option.getAttribute("aria-posinset"),
      size: option.getAttribute("aria-setsize"),
    }));
    assert.equal(
      focusedPosition.position,
      focusedPosition.size,
      `${engine}: focused Workflow keyboard did not reach its final retained row`,
    );
    assert.ok(
      Number(await surface.locator("canvas").getAttribute("data-visible-items")) > 0,
      `${engine}: focused Workflow culled every visible row`,
    );

    await surface.press("Home");
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
    const canvas = surface.locator("canvas");
    await canvas.click({ position: { x: 44, y: 32 } });
    await page.locator(".study-preview").waitFor();
    await closeStudy(page);

    const scroller = surface.locator("xpath=ancestor::*[contains(@class,'map-scroll')]");
    await scroller.evaluate((node) => { node.scrollTop = 0; });
    const box = await canvas.boundingBox();
    assert.ok(box, `${engine}: Workflow canvas has no pointer box`);
    await page.mouse.move(box.x + box.width - 8, box.y + Math.min(320, box.height - 24));
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 8, box.y + 80, { steps: 6 });
    await page.mouse.up();
    assert.ok(
      (await scroller.evaluate((node) => node.scrollTop)) > 0,
      `${engine}: blank far-right canvas space did not drag-to-pan`,
    );
    assert.equal(
      await page.locator(".study-preview").count(),
      0,
      `${engine}: blank far-right canvas space activated a workflow row`,
    );
    results.push(`${engine} focused Workflow keyboard, pointer, and blank-space pan`);
  } finally {
    await page.close();
  }

  const narrow = await browser.newPage({ viewport: { width: 320, height: 640 } });
  narrow.setDefaultTimeout(15_000);
  try {
    await narrow.goto(url, { waitUntil: "networkidle" });
    await settleApp(narrow);
    const surface = narrow.locator(".architecture-map-canvas");
    await surface.focus();
    const longLabel = "a/complete/module/identifier/that/remains/readable/at/two-hundred-percent.py";
    const measured = await surface.locator(".map-canvas-readout").evaluate((readout, text) => {
      readout.textContent = text;
      const style = getComputedStyle(readout);
      const rect = readout.getBoundingClientRect();
      return {
        text: readout.textContent,
        whiteSpace: style.whiteSpace,
        overflowX: style.overflowX,
        completeHeight: readout.scrollHeight <= readout.clientHeight + 1,
        completeWidth: readout.scrollWidth <= readout.clientWidth + 1,
        inViewport: rect.left >= -1 && rect.right <= innerWidth + 1,
      };
    }, longLabel);
    assert.deepEqual(
      measured,
      {
        text: longLabel,
        whiteSpace: "normal",
        overflowX: "visible",
        completeHeight: true,
        completeWidth: true,
        inViewport: true,
      },
      `${engine}: full canvas label is clipped at 320px`,
    );
    results.push(`${engine} full canvas label at 320px`);
  } finally {
    await narrow.close();
  }
}

for (const result of results) console.log(`PASS  ${result}`);
console.log(`user-flow repair contracts passed (${results.length} assertions)`);

async function checkCompactRailEscape(browser, engine, url) {
  const page = await browser.newPage({ viewport: { width: 320, height: 640 } });
  page.setDefaultTimeout(15_000);
  try {
    await page.goto(url, { waitUntil: "networkidle" });
    await settleApp(page);
    const menu = page.getByRole("button", { name: "Menu", exact: true });
    const breadcrumbBefore = await page.locator("nav[aria-label='Breadcrumb']").innerText();

    // A real pointer activation matters here. WebKit does not necessarily
    // focus a button after clicking it, so a subtree key handler can miss the
    // Escape entirely even though Chromium happens to keep focus on Menu.
    await menu.click();
    assert.equal(await menu.getAttribute("aria-expanded"), "true", `${engine} Menu did not open`);
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => {
      const trigger = document.querySelector(".mobile-menu-trigger");
      return trigger?.getAttribute("aria-expanded") === "false" && document.activeElement === trigger;
    });

    assert.equal(
      await page.locator("nav[aria-label='Breadcrumb']").innerText(),
      breadcrumbBefore,
      `${engine} compact Menu Escape also navigated away`,
    );
    results.push(`${engine} compact pointer Menu Escape`);
  } finally {
    await page.close();
  }
}

async function checkCompactQuizVisibility(browser, engine, url) {
  // These are the measured failure boundary, not a comfortable sample: the
  // final option was almost wholly behind the sticky action at 320-331px,
  // partly covered through 405px, and first clear at 406px before this repair.
  for (const width of [320, 331, 332, 405, 406, 414]) {
    const page = await browser.newPage({ viewport: { width, height: 640 } });
    page.setDefaultTimeout(15_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleApp(page);
      const map = page.locator(".architecture-map-canvas").first();
      await map.focus();
      await page.keyboard.press("Enter");
      const prove = page.getByRole("button", {
        name: /^(Prove understanding|Review understanding|Check availability)$/,
      }).first();
      await prove.click();
      await page.locator(".check-panel .active-check").waitFor();
      // The panel enters over 420ms and the question realigns once its local
      // fonts settle. Measure the learner's actual contract after both rather
      // than racing the first animation frame on a slower CI runner.
      await page.waitForTimeout(500);

      const measured = await page.locator(".check-panel").evaluate((panel) => {
        const options = [...panel.querySelectorAll(".check-options label")];
        const bar = panel.querySelector(".check-submit-bar");
        const submit = bar?.querySelector("button");
        if (!(bar instanceof HTMLElement) || !(submit instanceof HTMLElement)) return null;
        const panelBox = panel.getBoundingClientRect();
        const barBox = bar.getBoundingClientRect();
        const optionBoxes = options.map((option) => {
          const box = option.getBoundingClientRect();
          return { top: box.top, bottom: box.bottom, height: box.height };
        });
        return {
          optionCount: options.length,
          allOptionsClear: optionBoxes.every(
            (box) => box.top >= panelBox.top - 1 && box.bottom <= barBox.top + 1,
          ),
          options: optionBoxes,
          legend: (() => {
            const box = panel.querySelector("legend")?.getBoundingClientRect();
            return box ? { top: box.top, bottom: box.bottom, height: box.height } : null;
          })(),
          optionText: (() => {
            const style = options[0] ? getComputedStyle(options[0].querySelector("span")) : null;
            return style ? { fontFamily: style.fontFamily, fontSize: style.fontSize, lineHeight: style.lineHeight } : null;
          })(),
          scrollTop: panel.scrollTop,
          lastOption: optionBoxes.at(-1),
          panel: { top: panelBox.top, bottom: panelBox.bottom, height: panelBox.height },
          barTop: barBox.top,
          barBottom: barBox.bottom,
          submitVisible: barBox.top >= panelBox.top && barBox.bottom <= panelBox.bottom + 1,
        };
      });

      const label = `${engine} quiz ${width}x640`;
      assert.ok(measured, `${label}: submit bar did not render`);
      assert.equal(measured.optionCount, 4, `${label}: regression fixture no longer has four options`);
      assert.equal(
        measured.allOptionsClear,
        true,
        `${label}: an answer remains behind the sticky action (${JSON.stringify(measured)})`,
      );
      assert.equal(measured.submitVisible, true, `${label}: sticky submit action left the panel`);
      results.push(label);
    } finally {
      await page.close();
    }
  }
}

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
    { width: 330, height: 720 },
    { width: 360, height: 720 },
  ]) {
    const page = await browser.newPage({ viewport });
    page.setDefaultTimeout(15_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleApp(page);
      const label = `${engine} ${viewport.width}x${viewport.height}`;

      // The explicit source route begins before its evidence request finishes.
      // If that request fails, the promised section never mounts, so the
      // module heading is the stable interim target and the visible failure
      // heading becomes the final target rather than <body>.
      await page.route("**/api/node/*/study", (route) =>
        route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"test outage"}' }),
      );
      await openStudy(page);
      await assertFailedStudyArrival(page, label);
      await page.unroute("**/api/node/*/study");
      await page.locator(".study-preview").getByRole("button", { name: "Try again", exact: true }).click();
      await assertStudyArrival(page, label, viewport);
      await closeStudy(page);

      // Ordinary Study failure has the same-node retry shape but a different
      // destination: recovery stays at the module heading, not source.
      await page.route("**/api/node/*/study", (route) =>
        route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"test outage"}' }),
      );
      await openStudyNormally(page);
      await assertFailedStudyArrival(page, label);
      await page.unroute("**/api/node/*/study");
      await page.locator(".study-preview").getByRole("button", { name: "Try again", exact: true }).click();
      await page.locator(".source-study").waitFor();
      await assertModuleStudyArrival(page, `${label} ordinary retry`);
      await closeStudy(page);

      // Exercise the ordinary Map-tree path separately from Read the source.
      // Its destination is the module heading, at the top of a reset panel.
      // Hold the response after the panel mounts so moving focus to Close can
      // prove that ordinary data readiness does not steal it back. Fail the
      // independent narration request in the same visit so its retry can prove
      // the persistent module heading receives focus before that button unmounts.
      let releaseStudy;
      const heldStudy = new Promise((resolve) => { releaseStudy = resolve; });
      await page.route("**/api/node/*/study", async (route) => {
        const response = await route.fetch();
        await heldStudy;
        await route.fulfill({ response });
      });
      await page.route("**/api/node/*/explanation**", (route) =>
        route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"test outage"}' }),
      );
      await openStudyNormally(page);
      await assertModuleStudyArrival(page, label);
      const close = page.locator(".study-preview").getByRole("button", { name: "Close", exact: true });
      await close.focus();
      releaseStudy();
      await page.locator(".source-study").waitFor();
      assert.equal(
        await close.evaluate((button) => document.activeElement === button),
        true,
        `${label}: ordinary Study completion stole user-selected focus`,
      );
      await page.unroute("**/api/node/*/study");
      const narrationFailure = page.getByRole("heading", {
        name: "The explanation request failed.",
        exact: true,
      });
      await narrationFailure.waitFor();
      await page.unroute("**/api/node/*/explanation**");
      await narrationFailure.locator("..").getByRole("button", { name: "Try again", exact: true }).click();
      await page.getByText("Everything else on this panel is parser evidence and works without any model at all.").waitFor();
      assert.equal(
        await page.locator(".study-preview h1").evaluate((heading) => document.activeElement === heading),
        true,
        `${label}: narration retry drops focus from the persistent module heading`,
      );
      await closeStudy(page);

      await openStudy(page);
      await assertStudyArrival(page, label, viewport);
      await followStudyConnection(page, label);
      await closeStudy(page);
      await returnToHomeModule(page);
      await openStudy(page);
      await assertStudyArrival(page, label, viewport);
      await followStudyGuidance(page);
      await assertChecksHeadingFocus(page, label);

      await page.keyboard.press("Escape");
      await assertReturnedToProve(page, `${label} Escape`);

      await openStudy(page);
      await assertStudyArrival(page, label, viewport);
      await followStudyGuidance(page);
      await assertChecksHeadingFocus(page, label);
      await page.locator(".check-panel").getByRole("button", { name: "Close", exact: true }).click();
      await assertReturnedToProve(page, `${label} Close`);
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
      await completeModeGate(mode, { voyage: "explore", register: "easy" });
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
      await completeModeGate(mode, { voyage: "explore", register: "easy" });
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

async function completeModeGate(gate, { voyage, register }) {
  const voyageName = voyage === "guided" ? "Take a first flight" : "Explore freely";
  const registerName = register === "expert" ? "I build software" : "New to coding?";
  await gate.getByRole("radio", { name: new RegExp(`^${voyageName}`) }).check();
  await gate.getByRole("radio", { name: registerName, exact: true }).check();
  const launchName = voyage === "guided" ? "Begin first flight" : "Open the galaxy";
  await gate.getByRole("button", { name: launchName, exact: true }).click();
}

async function openStudy(page) {
  const read = page.getByRole("button", { name: "Read the source", exact: true });
  if (!(await read.count()) || !(await read.first().isVisible())) {
    const map = page.locator(".architecture-map-canvas").first();
    await map.focus();
    await page.keyboard.press("Enter");
    await read.first().waitFor();
  }
  await read.first().click();
  await page.locator(".study-preview").waitFor();
}

async function openStudyNormally(page) {
  const workflow = page.getByRole("button", { name: "What runs first", exact: true });
  await workflow.click();
  const tree = page.locator(".workflow-map-canvas");
  await tree.waitFor();
  await tree.focus();
  await page.keyboard.press("Enter");
  await page.locator(".study-preview").waitFor();
}

async function closeStudy(page) {
  const panel = page.locator(".study-preview");
  await panel.getByRole("button", { name: "Close", exact: true }).click();
  await panel.waitFor({ state: "detached" });
}

async function returnToHomeModule(page) {
  await page.getByRole("button", { name: "All modules", exact: true }).click();
  await page.getByRole("button", { name: "codemble.cli", exact: true }).click();
  await page.getByRole("button", { name: "Read the source", exact: true }).waitFor();
}

async function assertFailedStudyArrival(page, label) {
  const failure = page.getByRole("heading", { name: "Study data did not load.", exact: true });
  await failure.waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent?.trim() === "Study data did not load.");
  const focused = await failure.evaluate(
    (heading) => document.activeElement === heading,
  );
  assert.equal(focused, true, `${label}: failed source request drops Study focus`);
}

async function assertModuleStudyArrival(page, label) {
  await page.waitForFunction(() => document.activeElement?.matches(".study-preview h1"));
  const measured = await page.locator(".study-preview").evaluate((panel) => ({
    focused: document.activeElement === panel.querySelector("h1"),
    scrollTop: panel.scrollTop,
  }));
  assert.equal(measured.focused, true, `${label}: ordinary Study heading does not own focus`);
  assert.ok(measured.scrollTop <= 1, `${label}: ordinary Study opens at scrollTop ${measured.scrollTop}`);
}

async function assertStudyArrival(page, label, viewport) {
  await page.waitForFunction(() => document.activeElement?.id === "source-heading");
  const measured = await page.evaluate(() => {
    const heading = document.querySelector("#source-heading");
    const hint = document.querySelector(".hint-chip");
    const actions = [...document.querySelectorAll(".hint-chip > button")];
    if (!heading || !hint || actions.length < 2) return null;
    const headingRect = heading.getBoundingClientRect();
    const headingLineHeight = Number.parseFloat(getComputedStyle(heading).lineHeight);
    const actionRects = actions.map((button) => button.getBoundingClientRect());
    return {
      focused: document.activeElement === heading,
      headingIsOneLine: headingRect.height <= headingLineHeight * 1.2,
      actionsShareRow: Math.abs(actionRects[0].top - actionRects[1].top) <= 1,
      guidanceShare: hint.getBoundingClientRect().height / innerHeight,
    };
  });
  assert.ok(measured, `${label}: Study arrival surface did not render`);
  assert.equal(measured.focused, true, `${label}: source heading does not own arrival focus`);
  if (viewport.width <= 360) {
    assert.equal(measured.headingIsOneLine, true, `${label}: Real source wraps in the compact range`);
    assert.equal(measured.actionsShareRow, true, `${label}: Study guidance actions stack in the compact range`);
    assert.ok(
      measured.guidanceShare < 0.25,
      `${label}: Study guidance consumes ${(measured.guidanceShare * 100).toFixed(1)}% of the viewport`,
    );
  }
}

async function followStudyConnection(page, label) {
  const panel = page.locator(".study-preview");
  const support = panel.locator(".journey-support");
  if (!(await support.getAttribute("open"))) await support.locator("summary").click();
  const connection = panel.locator(".connection-list button").first();
  await connection.waitFor();
  await connection.scrollIntoViewIfNeeded();
  const before = await panel.evaluate((node) => node.scrollTop);
  assert.ok(before > 1, `${label}: connection test did not begin from a scrolled panel`);
  const previous = await panel.locator("h1").innerText();
  await connection.click();
  await page.waitForFunction(
    (oldHeading) =>
      document.activeElement?.matches(".study-preview h1") &&
      document.activeElement.textContent.trim() !== oldHeading,
    previous,
  );
  const measured = await panel.evaluate((node) => ({
    focused: document.activeElement === node.querySelector("h1"),
    scrollTop: node.scrollTop,
  }));
  assert.equal(measured.focused, true, `${label}: connection arrival heading does not own focus`);
  assert.ok(measured.scrollTop <= 1, `${label}: connection arrival retained scrollTop ${measured.scrollTop}`);
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
  if (child.exitCode !== null || child.signalCode !== null) return;
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
