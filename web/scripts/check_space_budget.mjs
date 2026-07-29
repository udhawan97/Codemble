/**
 * The shell's space budget, asserted instead of remembered.
 *
 * `styles.css` is 3,216 lines across 17 media blocks and carries the product's
 * entire layout contract with no seam and no assertion. Three of the last eight
 * bugfixes were exactly that, and none could be caught by any JS seam:
 *
 *   13b3c06  chrome spending 47% of a 720px window on itself
 *   99b6875  a `@media` block that was dead code, out-specified by a panel rule
 *   55147ac  a canvas measuring 43px at 1280x720 and 0px at 320px
 *
 * Each was verified by a human reading DevTools and pasting the numbers into a
 * commit message. Those numbers are the contract; this re-reads them. `99b6875`
 * in particular is a bug in *cascade resolution* -- visible only to a browser,
 * which is why this is the one gate that runs one.
 *
 * Needs a running Codemble. Point `CODEMBLE_URL` at one; it is deliberately not
 * part of `npm run check`, which stays Node-only, offline and fast.
 */

import assert from "node:assert/strict";

import { chromium } from "playwright";

const url = process.env.CODEMBLE_URL;
if (!url) {
  throw new Error("CODEMBLE_URL is required (e.g. http://127.0.0.1:8899).");
}

// Measured on this repository at v0.8.0 and recorded in 13b3c06. The budget is
// the shipped result plus a little slack, so drift fails before a learner sees
// it -- not a target nobody has hit.
const VIEWPORTS = [
  { width: 1440, height: 720, maxChromeShare: 0.42, minCanvas: 150 },
  { width: 1280, height: 720, maxChromeShare: 0.42, minCanvas: 150 },
  // Below 1024 the compact shell takes over; it spends less on chrome but has
  // far less to spend, so the canvas floor is what matters there.
  { width: 375, height: 720, maxChromeShare: 0.55, minCanvas: 90 },
  { width: 320, height: 720, maxChromeShare: 0.58, minCanvas: 90 },
];

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl"],
});

let failures = 0;
const report = [];

try {
  for (const viewport of VIEWPORTS) {
    for (const register of ["easy", "expert"]) {
      const page = await browser.newPage({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: 1,
      });
      try {
        await page.goto(url, { waitUntil: "networkidle" });
        await settleFirstRun(page, register);
        const measured = await measure(page);
        report.push({ ...viewport, register, ...measured });

        const label = `${viewport.width}x${viewport.height} ${register}`;
        try {
          assert.ok(
            measured.chromeShare <= viewport.maxChromeShare,
            `${label}: chrome is ${(measured.chromeShare * 100).toFixed(1)}% of the window ` +
              `(budget ${(viewport.maxChromeShare * 100).toFixed(0)}%) -- ` +
              `header ${measured.header}, guidance ${measured.guidance}, footer ${measured.footer}`,
          );
          if (measured.canvas !== null) {
            assert.ok(
              measured.canvas >= viewport.minCanvas,
              `${label}: the drawing is ${measured.canvas}px, floor ${viewport.minCanvas}px`,
            );
          }
          // 55147ac's real failure mode: the text was reachable but invisible,
          // because macOS draws no scrollbar until scrolled, so a clipped
          // paragraph read as a rendering bug rather than as more text.
          for (const clipped of measured.clipped) {
            assert.fail(
              `${label}: "${clipped.selector}" clips its own content silently ` +
                `(${clipped.scrollHeight}px of content in ${clipped.clientHeight}px)`,
            );
          }
          // The whole page must never scroll sideways.
          assert.ok(
            measured.horizontalOverflow <= 1,
            `${label}: the page scrolls horizontally by ${measured.horizontalOverflow}px`,
          );
        } catch (error) {
          failures += 1;
          console.error(`  FAIL ${error.message}`);
        }
      } finally {
        await page.close();
      }
    }
  }
} finally {
  await browser.close();
}

console.table(
  report.map((row) => ({
    viewport: `${row.width}x${row.height}`,
    register: row.register,
    header: row.header,
    guidance: row.guidance,
    footer: row.footer,
    chrome: `${(row.chromeShare * 100).toFixed(1)}%`,
    canvas: row.canvas ?? "-",
  })),
);

if (failures > 0) {
  throw new Error(`${failures} space-budget assertion(s) failed`);
}
console.log("space-budget contracts passed");

/**
 * Clear the first-run sequence -- audience, then Home, then coaching -- and
 * settle on the requested register. Every step is optional: the server may
 * already carry a learner's answers, and a clean run is not required here.
 */
async function settleFirstRun(page, register) {
  const gate = page.locator("dialog[open]").first();
  for (let step = 0; step < 4; step += 1) {
    if ((await gate.count()) === 0) break;
    const skip = gate.getByRole("button", { name: /^(Skip|Explore without Home)$/ });
    const choose = gate.getByRole("button").first();
    if ((await skip.count()) > 0) await skip.first().click();
    else if ((await choose.count()) > 0) await choose.click();
    else break;
    await page.waitForTimeout(120);
  }
  // The register toggle lives in the header at desktop and behind the
  // disclosure at compact widths, so open that first if it is there.
  const more = page.getByRole("button", { name: /^(More|Menu)$/ });
  if ((await more.count()) > 0 && (await more.first().isVisible())) {
    await more.first().click();
    await page.waitForTimeout(80);
  }
  const radio = page.getByRole("radio", { name: register });
  if ((await radio.count()) > 0 && (await radio.first().isVisible())) {
    await radio.first().click();
    await page.waitForTimeout(250);
  }
  await page.waitForTimeout(350);
}

function measure(page) {
  return page.evaluate(() => {
    const height = (selector) => {
      const element = document.querySelector(selector);
      return element ? Math.round(element.getBoundingClientRect().height) : 0;
    };
    const optionalHeight = (selector) => {
      const element = document.querySelector(selector);
      return element ? Math.round(element.getBoundingClientRect().height) : null;
    };

    const header = height("header");
    const guidance = height(".hint-chip");
    const footer = height("footer");
    const viewportHeight = window.innerHeight;

    // Anything that scrolls a *child* rather than the column it sits in. The
    // scrollbar is invisible until scrolled, so this reads as a rendering bug
    // rather than as more text -- 55147ac's actual failure mode.
    const clipped = [];
    for (const selector of [".map-note", ".region-copy", ".map-caption", ".orientation-copy"]) {
      for (const element of document.querySelectorAll(selector)) {
        const style = getComputedStyle(element);
        if (style.overflowY !== "auto" && style.overflowY !== "scroll") continue;
        if (element.scrollHeight > element.clientHeight + 1) {
          clipped.push({
            selector,
            scrollHeight: element.scrollHeight,
            clientHeight: element.clientHeight,
          });
        }
      }
    }

    return {
      header,
      guidance,
      footer,
      chromeShare: (header + guidance + footer) / viewportHeight,
      // The Map's drawing. Absent on the Galaxy layer, where the canvas fills
      // whatever is left and has no floor of its own to check.
      canvas: optionalHeight(".map-canvas"),
      clipped,
      horizontalOverflow:
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
}
