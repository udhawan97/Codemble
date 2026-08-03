import { mkdir, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { chromium } from "playwright";

const baseUrl = (process.env.CODEMBLE_SITE_URL || "http://127.0.0.1:4323/Codemble").replace(
  /\/$/,
  "",
);
const outputDirectory = resolve(
  process.env.CODEMBLE_SITE_CHECK_DIR || join(tmpdir(), "codemble-site-check"),
);
const release = JSON.parse(
  await readFile(new URL("../../docs-site/release.json", import.meta.url), "utf8"),
);
const viewports = [
  { name: "320", width: 320, height: 800 },
  { name: "375", width: 375, height: 812 },
  { name: "414", width: 414, height: 896 },
  { name: "768", width: 768, height: 900 },
  { name: "1280", width: 1280, height: 800 },
  { name: "1440", width: 1440, height: 900 },
];

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const failures = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}

for (const viewport of viewports) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  const response = await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
  assert(response?.ok(), `${viewport.name}: landing returned ${response?.status()}`);
  assert(
    await page.getByRole("heading", { name: "Explore the code AI left behind." }).isVisible(),
    `${viewport.name}: landing promise is not visible`,
  );
  assert(
    await page.getByRole("link", { name: "Download Codemble" }).first().isVisible(),
    `${viewport.name}: primary download action is not visible`,
  );
  if (viewport.name === "1280") {
    const proof = await page.locator(".hero-proof").boundingBox();
    assert(
      proof && proof.y < viewport.height && Math.min(proof.y + proof.height, viewport.height) - proof.y >= 180,
      "1280: the hero product focal point does not fit the first fold",
    );
  }

  const surface = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    duplicateIds: [...document.querySelectorAll("[id]")]
      .map((element) => element.id)
      .filter((id, index, ids) => ids.indexOf(id) !== index),
    brokenImages: [...document.images]
      .filter((image) => image.complete && image.naturalWidth === 0)
      .map((image) => image.currentSrc || image.src),
  }));
  assert(surface.overflow <= 1, `${viewport.name}: document overflows by ${surface.overflow}px`);
  assert(surface.duplicateIds.length === 0, `${viewport.name}: duplicate ids ${surface.duplicateIds}`);
  assert(surface.brokenImages.length === 0, `${viewport.name}: broken images ${surface.brokenImages}`);

  const themeToggle = page.locator("[data-theme-toggle]");
  const initialTheme = await page.locator("html").getAttribute("data-theme");
  await themeToggle.click();
  const toggledTheme = await page.locator("html").getAttribute("data-theme");
  assert(
    ["light", "dark"].includes(toggledTheme || "") && toggledTheme !== initialTheme,
    `${viewport.name}: theme toggle did not change ${initialTheme}`,
  );

  const copy = page.locator("[data-copy]").first();
  await copy.click();
  await page.waitForTimeout(100);
  assert(
    (await copy.locator("[data-copy-label]").textContent())?.trim() === "Copied",
    `${viewport.name}: command copy did not confirm`,
  );

  const wheel = page.getByRole("link", { name: "Download wheel" });
  assert(
    (await wheel.getAttribute("href"))?.endsWith(release.wheel.filename),
    `${viewport.name}: wheel target is wrong`,
  );

  if (viewport.name === "375") {
    const productViewport = page.locator(".product-viewport");
    await page.keyboard.press("Tab");
    await productViewport.focus();
    const focusState = await productViewport.evaluate((element) => ({
      focused: document.activeElement === element,
      visible:
        element.matches(":focus-visible") && getComputedStyle(element).outlineStyle !== "none",
      before: element.scrollLeft,
    }));
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(120);
    const after = await productViewport.evaluate((element) => element.scrollLeft);
    assert(focusState.focused && focusState.visible, "375: product proof lacks visible keyboard focus");
    assert(after > focusState.before, "375: ArrowRight did not pan the full-size product proof");
  }

  for (const step of await page.locator("[data-journey-step]").all()) {
    await step.scrollIntoViewIfNeeded();
    await page.waitForTimeout(120);
  }
  await page.locator("img").evaluateAll(async (images) => {
    images.forEach((image) => {
      image.loading = "eager";
    });
    await Promise.all(
      images.map((image) =>
        Promise.race([
          image.decode().catch(() => undefined),
          new Promise((resolve) => setTimeout(resolve, 3000)),
        ]),
      ),
    );
    scrollTo(0, 0);
  });
  await page.waitForTimeout(120);
  const imagesAfterScroll = await page.evaluate(() => ({
    broken: [...document.images]
      .filter((image) => image.complete && image.naturalWidth === 0)
      .map((image) => image.currentSrc || image.src),
    pending: [...document.images]
      .filter((image) => !image.complete)
      .map((image) => image.currentSrc || image.src),
  }));
  assert(imagesAfterScroll.broken.length === 0, `${viewport.name}: broken images ${imagesAfterScroll.broken}`);
  assert(imagesAfterScroll.pending.length === 0, `${viewport.name}: images did not load ${imagesAfterScroll.pending}`);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.waitForTimeout(180);

  await page.screenshot({
    path: join(outputDirectory, `landing-${viewport.name}.png`),
    fullPage: viewport.name === "375" || viewport.name === "1440",
  });
  assert(errors.length === 0, `${viewport.name}: browser errors: ${errors.join(" | ")}`);
  await context.close();
}

for (const route of ["download", "installation", "introduction", "build-from-source"]) {
 for (const viewport of [{ name: "375", width: 375, height: 812 }, { name: "1280", width: 1280, height: 800 }]) {
  const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  const response = await page.goto(`${baseUrl}/${route}/`, { waitUntil: "networkidle" });
  assert(response?.ok(), `${route} ${viewport.name}: returned ${response?.status()}`);
  const state = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    brokenImages: [...document.images].filter(
      (image) => image.complete && image.naturalWidth === 0,
    ).length,
  }));
  assert(state.overflow <= 1, `${route} ${viewport.name}: document overflows by ${state.overflow}px`);
  assert(state.brokenImages === 0, `${route} ${viewport.name}: ${state.brokenImages} broken images`);
  assert(errors.length === 0, `${route} ${viewport.name}: browser errors: ${errors.join(" | ")}`);
  if (route === "download" && viewport.name === "375") {
    assert(
      await page.locator("#direct-artifacts").isVisible(),
      "download: direct-artifact route is missing",
    );
    await page.screenshot({ path: join(outputDirectory, "download-375.png"), fullPage: true });
  }
  await page.context().close();
 }
}

for (const clipboardMode of ["unsupported", "denied"]) {
  const fallbackPage = await browser.newPage({ viewport: { width: 375, height: 812 } });
  const fallbackErrors = [];
  fallbackPage.on("pageerror", (error) => fallbackErrors.push(error.message));
  await fallbackPage.addInitScript((mode) => {
    Object.defineProperty(Navigator.prototype, "clipboard", {
      configurable: true,
      get: () =>
        mode === "unsupported"
          ? undefined
          : { writeText: () => Promise.reject(new DOMException("Denied", "NotAllowedError")) },
    });
  }, clipboardMode);
  await fallbackPage.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
  const fallbackCopy = fallbackPage.locator("[data-copy]").first();
  await fallbackCopy.click();
  assert(
    (await fallbackCopy.locator("[data-copy-label]").textContent())?.trim() === "Select command",
    `${clipboardMode} clipboard fallback did not label the selected command`,
  );
  const selected = await fallbackPage.evaluate(() => window.getSelection()?.toString().trim());
  assert(
    selected === `uvx --from codemble==${release.version} codemble`,
    `${clipboardMode} clipboard fallback did not select the command`,
  );
  assert(
    fallbackErrors.length === 0,
    `${clipboardMode} clipboard fallback errors: ${fallbackErrors.join(" | ")}`,
  );
  await fallbackPage.context().close();
}

await browser.close();

if (failures.length > 0) {
  throw new Error(`Public-site checks failed:\n- ${failures.join("\n- ")}`);
}

process.stdout.write(
  `Landing checks passed at 320, 375, 414, 768, 1280, and 1440 px; docs routes passed at 375 and 1280 px.\nScreenshots: ${outputDirectory}\n`,
);
