import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

import { startDisposableCaptureServer } from "./capture_support.mjs";

if (process.env.CODEMBLE_CAPTURE_URL) {
  throw new Error(
    "CODEMBLE_CAPTURE_URL is no longer accepted: capture:docs starts its own disposable, provider-free server.",
  );
}

const repositoryRoot = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const outputDirectory = resolve(
  process.env.CODEMBLE_CAPTURE_DIR || "../docs-site/public/shots",
);
const homeCandidate = /^codemble\.cli codemble\/cli\.py:1/;
const appModulePath = "server/app.py";

const captureServer = await startDisposableCaptureServer({
  projectRoot: repositoryRoot,
  python: process.env.CODEMBLE_CAPTURE_PYTHON || "python",
});
const baseUrl = captureServer.url;
let browser;

try {

await mkdir(outputDirectory, { recursive: true });

browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl"],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 720 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
});

const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") pageErrors.push(message.text());
});

async function waitForApp() {
  await page.getByText("Local only", { exact: true }).waitFor();
  await page.waitForTimeout(900);
}

async function settleFirstRun() {
  const audienceDialog = page.getByRole("dialog", {
    name: "New to coding, or do you build software already?",
  });
  if (await audienceDialog.isVisible().catch(() => false)) {
    await audienceDialog.getByRole("button", { name: "New to coding?" }).click();
    await page.waitForTimeout(350);
  }

  const homeDialog = page.getByRole("dialog", {
    name: "Where does your project start?",
  });
  if (await homeDialog.isVisible().catch(() => false)) {
    await homeDialog.getByRole("button", { name: homeCandidate }).click();
    await page.waitForTimeout(650);
  }

  const skip = page.getByRole("button", { name: "Skip", exact: true });
  if (await skip.isVisible().catch(() => false)) {
    await skip.click();
    await page.waitForTimeout(250);
  }
}

async function openApp() {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await waitForApp();
  await settleFirstRun();
}

async function setMode(mode) {
  const radio = page.getByRole("radio", { name: mode, exact: true });
  if (!(await radio.isChecked())) {
    await radio.check();
    await page.waitForTimeout(500);
  }
}

async function setLayer(layer) {
  const label = layer === "map" ? /^(Map|Diagram)$/ : /^Galaxy$/;
  const button = page.getByRole("button", { name: label });
  if ((await button.getAttribute("aria-pressed")) !== "true") {
    await button.click();
    await page.waitForTimeout(layer === "galaxy" ? 1300 : 650);
  }
}

async function capture(name) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.waitForTimeout(250);
  await page.screenshot({ path: resolve(outputDirectory, name) });
  process.stdout.write(`captured ${name}\n`);
}

async function selectAppModule() {
  const moduleButton = page.getByRole("button").filter({ hasText: appModulePath });
  await moduleButton.first().click();
  await page.waitForTimeout(500);
}

function combinations(values) {
  const result = [];
  for (let mask = 1; mask < 2 ** values.length; mask += 1) {
    result.push(values.filter((_value, index) => mask & (1 << index)));
  }
  return result;
}

async function passRegion(regionId) {
  const encodedRegion = encodeURIComponent(regionId);
  const suiteResponse = await page.request.get(
    `${baseUrl}/api/regions/${encodedRegion}/checks`,
  );
  if (!suiteResponse.ok()) throw new Error(`Could not load checks for ${regionId}.`);
  const suite = await suiteResponse.json();

  for (const check of suite.checks) {
    if (check.passed) continue;
    let correct = false;
    for (const selectedIds of combinations(check.options.map((option) => option.id))) {
      const response = await page.request.post(
        `${baseUrl}/api/regions/${encodedRegion}/checks/${encodeURIComponent(check.id)}`,
        { data: { selected_ids: selectedIds } },
      );
      if (!response.ok()) continue;
      const result = await response.json();
      if (result.correct) {
        correct = true;
        break;
      }
    }
    if (!correct) throw new Error(`Could not pass graph check ${check.id}.`);
  }
}

// Start from a clean evidence state. Home and audience are re-selected through
// the actual first-run UI if clearing progress retires those preferences.
const resetResponse = await page.request.delete(`${baseUrl}/api/progress`);
if (!resetResponse.ok()) {
  throw new Error(`Disposable progress reset failed with HTTP ${resetResponse.status()}.`);
}
await openApp();

await setMode("Easy");
await setLayer("galaxy");
await capture("galaxy.png");

await setLayer("map");
await page.getByRole("button", { name: "How it fits together", exact: true }).click();
await capture("easy-mode.png");

await setMode("Expert");
await page.getByRole("button", { name: "Architecture", exact: true }).click();
await capture("map-architecture.png");
await page.getByRole("button", { name: "Workflow", exact: true }).click();
await page.waitForTimeout(400);
await capture("map-workflow.png");

await page.getByRole("button", { name: "Architecture", exact: true }).click();
await selectAppModule();
await setLayer("galaxy");
await capture("system.png");

await setLayer("map");
await page.getByRole("button", { name: "Read the source", exact: true }).click();
await page.waitForTimeout(700);
await page.locator(".study-preview").evaluate((scroller) => {
  scroller.scrollTop = 0;
});
await capture("study-panel.png");

const impactHeading = page.getByRole("heading", { name: "Impact", exact: true });
await impactHeading.evaluate((heading) => {
  const scroller = heading.closest(".study-preview");
  if (!(scroller instanceof HTMLElement)) {
    throw new Error("Could not find the Study panel scroll container.");
  }
  const headingBox = heading.getBoundingClientRect();
  const scrollerBox = scroller.getBoundingClientRect();
  scroller.scrollTop += headingBox.top - scrollerBox.top - 44;
});
await page.waitForTimeout(250);
await page.screenshot({ path: resolve(outputDirectory, "study-impact.png") });
process.stdout.write("captured study-impact.png\n");

await passRegion("codemble.cli");
await openApp();
await setMode("Easy");
await setLayer("galaxy");
await page.getByRole("button", { name: /^Focus Python:/ }).click();
await page.waitForTimeout(1200);
await page.getByRole("button", { name: "Key", exact: true }).click();
await page.waitForTimeout(350);
await capture("galaxy-lit.png");
await page.getByRole("button", { name: "Key", exact: true }).click();
await page.getByRole("button", { name: "Modules", exact: true }).click();
await page.locator('button[title="codemble/cli.py"]').click();
await page.waitForTimeout(1300);
await page.getByRole("button", { name: "Close the project index" }).click();
await page.waitForTimeout(250);
await capture("home-proved.png");

if (pageErrors.length > 0) {
  throw new Error(`Browser errors during capture:\n${pageErrors.join("\n")}`);
}
} finally {
  if (browser) await browser.close();
  await captureServer.stop();
}
