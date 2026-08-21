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
  // 1024 and 1023 are a pair, and they are the most load-bearing rows here.
  // The rail's wide layout starts at 64rem, and the 2026-07-28 entry moved it
  // there because the wide arrangement measured *worse* than the compact shell
  // everywhere below 1024 -- 199px of rail at 768 against 124px compact. The
  // pair asserts the breakpoint is still where that decision put it: 1023 must
  // measure as the compact shell and 1024 as the wide one. If it ever slipped
  // back to 40rem, 768 below would inherit that 199px rail and fail.
  { width: 1024, height: 720, maxChromeShare: 0.42, minCanvas: 150 },
  { width: 1023, height: 720, maxChromeShare: 0.42, minCanvas: 150 },
  // Narrow desktop: a window that looks like a desktop and gets the compact
  // shell. Hand-checked once when the breakpoint moved, never gated until now.
  { width: 768, height: 720, maxChromeShare: 0.42, minCanvas: 150 },
  { width: 640, height: 720, maxChromeShare: 0.50, minCanvas: 120 },
  // Phones. The compact shell spends less on chrome but has far less to spend,
  // so the canvas floor is what matters here rather than the share.
  { width: 375, height: 720, maxChromeShare: 0.55, minCanvas: 90 },
  { width: 320, height: 720, maxChromeShare: 0.58, minCanvas: 90 },
];

// The header height each shell produces, which is the cheapest signal that the
// right shell is in play at all. Measured on this repository; asserted only
// where the two shells differ enough that a swap could not be a rounding error.
const SHELL_HEADER = { wide: 148, compact: 124 };

// The widths that render the wide rail. Every one of them has to hold its
// actions on one row at every level, not just at the top of the loop.
const WIDE_WIDTHS = [1440, 1280, 1100, 1024];

// 640 CSS pixels at DPR 2 is the reflow geometry of a 1280x800 window at
// 200% browser zoom. Keep the phone row too: both can be narrow, but only the
// former is short enough to expose a disclosure that sizes itself from `vh`
// while forgetting the stage begins below the header.
const KEY_VIEWPORTS = [
  { width: 1280, height: 720, deviceScaleFactor: 1, label: "1280px desktop" },
  { width: 640, height: 400, deviceScaleFactor: 2, label: "1280x800 at 200%" },
  { width: 640, height: 360, deviceScaleFactor: 2, label: "1280x720 at 200%" },
  { width: 320, height: 640, deviceScaleFactor: 1, label: "320px reflow" },
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
      // A cold seven-language graph and its first WebGL frame can legitimately
      // consume several seconds. Keep the normal Playwright ceiling so this
      // remains a geometry gate instead of a machine-load race.
      page.setDefaultTimeout(30_000);
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
          assert.deepEqual(
            measured.overlaps,
            [],
            `${label}: header controls sit on top of each other -- ${measured.overlaps.join("; ")}`,
          );
          assert.equal(
            measured.mapScrollCue,
            true,
            `${label}: the Map column scrolls without a visible continuation cue`,
          );
          // The breakpoint pair: which shell rendered, not just how much it
          // spent. A budget alone cannot catch the breakpoint moving, because
          // the compact shell is *cheaper* -- that is why it was extended down
          // to 1023 in the first place. Only the header height says which one
          // is on screen, and only in Easy, where both shells carry guidance.
          if (register === "easy" && (viewport.width === 1024 || viewport.width === 1023)) {
            const expected =
              viewport.width === 1024 ? SHELL_HEADER.wide : SHELL_HEADER.compact;
            assert.equal(
              measured.header,
              expected,
              `${label}: expected the ${viewport.width === 1024 ? "wide" : "compact"} shell ` +
                `(header ${expected}px) but measured ${measured.header}px -- the rail's 64rem ` +
                `breakpoint has moved`,
            );
          }
        } catch (error) {
          failures += 1;
          console.error(`  FAIL ${error.message}`);
        }
      } finally {
        await page.close();
      }
    }
  }

  // Everything above measures the *top* level, which is the one state where the
  // rail carries its fewest actions. The learner spends the loop below it, and
  // each level down adds the way back out -- "Back to map" at region, "Back to
  // the module" at study, the widest label in the row. Those states wrapped the
  // wide rail to two and three rows (header 148 -> 199 -> 259, 52.2% of a 720px
  // window) while every row above passed, because nothing here ever went a
  // level deep.
  for (const width of WIDE_WIDTHS) {
    const page = await browser.newPage({
      viewport: { width, height: 720 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(30_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy", { home: true });
      for (const level of ["region", "study"]) {
        if (!(await descend(page, level))) {
          failures += 1;
          console.error(`  FAIL ${width}x720 easy: could not reach ${level} level`);
          break;
        }
        const measured = await measure(page);
        report.push({ width, height: 720, register: `easy/${level}`, ...measured });
        try {
          assert.equal(
            measured.header,
            SHELL_HEADER.wide,
            `${width}x720 easy at ${level} level: header is ${measured.header}px, not ` +
              `${SHELL_HEADER.wide}px -- the rail's actions have wrapped to another row`,
          );
          assert.ok(
            measured.horizontalOverflow <= 1,
            `${width}x720 easy at ${level} level: the page scrolls horizontally by ` +
              `${measured.horizontalOverflow}px -- the actions no longer fit without wrapping`,
          );
          assert.deepEqual(
            measured.overlaps,
            [],
            `${width}x720 easy at ${level} level: header controls sit on top of ` +
              `each other -- ${measured.overlaps.join("; ")}`,
          );
          assert.equal(
            measured.mapScrollCue,
            true,
            `${width}x720 easy at ${level} level: the Map column scrolls without a visible continuation cue`,
          );
        } catch (error) {
          failures += 1;
          console.error(`  FAIL ${error.message}`);
        }
      }
    } finally {
      await page.close();
    }
  }

  // The brand's second line is the learner's own directory name, so its length
  // belongs to the user. It used to size the rail's first column to max-content
  // while the actions held the only flexible track, which made the header's
  // height a property of what the folder happened to be called: a 60-character
  // name measured 199px at 1440, where a 6-character one measured 148px.
  {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 720 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(30_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy", { home: true });
      await descend(page, "region");
      await descend(page, "study");
      const before = (await measure(page)).header;
      await page.evaluate(() => {
        const line = document.querySelector(".brand-lockup div span");
        if (line) line.textContent = "a-very-long-project-directory-name-".repeat(2);
      });
      await page.waitForTimeout(250);
      const after = await measure(page);
      try {
        assert.equal(
          after.header,
          before,
          `1440x720 easy: a ${70}-character project name changed the header from ` +
            `${before}px to ${after.header}px -- the rail is sized by the folder's name`,
        );
        assert.ok(
          after.horizontalOverflow <= 1,
          `1440x720 easy: a long project name made the page scroll horizontally by ` +
            `${after.horizontalOverflow}px`,
        );
      } catch (error) {
        failures += 1;
        console.error(`  FAIL ${error.message}`);
      }
      report.push({ width: 1440, height: 720, register: "easy/long-name", ...after });
    } finally {
      await page.close();
    }
  }

  // The Key is part of the Galaxy's evidence contract, not optional desktop
  // decoration. Prove its compact form against real layout: fully contained,
  // opaque over WebGL, internally scrollable, and carrying a non-colour dash
  // for possible routes. Keyboard selection must survive moving focus into it.
  for (const viewport of KEY_VIEWPORTS) {
    const page = await browser.newPage({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: viewport.deviceScaleFactor,
    });
    page.setDefaultTimeout(30_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy", { home: true });

      let galaxy = page.getByRole("button", { name: "Galaxy", exact: true });
      if (!(await galaxy.isVisible().catch(() => false))) {
        const menu = page.getByRole("button", { name: "Menu", exact: true });
        if (await menu.isVisible().catch(() => false)) await menu.click();
        galaxy = page.getByRole("button", { name: "Galaxy", exact: true });
      }
      await galaxy.click();
      await page.waitForTimeout(900);

      // On one full-size canvas, find a real Three.js node with the mouse.
      // The force-graph tooltip appears only after its raycaster has hit a
      // rendered node, so this is a live WebGL hover rather than a dispatched
      // React event. Moving to Key must retire that tooltip while leaving the
      // keyboard subject intact.
      const hovered = viewport.width === 1280 ? await hoverRenderedNode(page) : null;

      const frame = page.getByRole("application", { name: /Codemble galaxy view/ });
      await frame.focus();
      await page.keyboard.press("ArrowRight");
      const readout = page.locator(".keyboard-focus");
      const subjectBefore = await readout.textContent();

      await page.getByRole("button", { name: "Key", exact: true }).click();
      const legend = page.getByLabel("Galaxy legend");
      await legend.waitFor({ state: "visible" });
      await legend.focus();
      await page.keyboard.press("End");
      const keyboardScrollTop = await legend.evaluate((element) => element.scrollTop);
      const measured = await legend.evaluate((element) => {
        const panel = element.getBoundingClientRect();
        const stage = element.closest(".map-stage")?.getBoundingClientRect();
        const style = getComputedStyle(element);
        const possible = element.querySelector(".legend-route--possible");
        return {
          panel: { top: panel.top, bottom: panel.bottom },
          stage: stage ? { top: stage.top, bottom: stage.bottom } : null,
          viewportBottom: window.innerHeight,
          background: style.backgroundColor,
          overflowY: style.overflowY,
          clientHeight: element.clientHeight,
          scrollHeight: element.scrollHeight,
          possibleStyle: possible ? getComputedStyle(possible).borderTopStyle : null,
          tabIndex: element.tabIndex,
        };
      });
      const subjectAfter = await readout.textContent();
      const tooltipAfter =
        hovered === null
          ? null
          : await page.locator(".float-tooltip-kap").evaluate((element) => ({
              display: getComputedStyle(element).display,
              text: element.textContent?.trim() ?? "",
            }));

      try {
        if (hovered !== null) {
          assert.ok(hovered.text, `${viewport.label}: WebGL hover produced no named subject`);
          assert.equal(
            tooltipAfter?.display,
            "none",
            `${viewport.label}: moving from WebGL into Key left the old hover visible`,
          );
        }
        assert.equal(
          subjectAfter,
          subjectBefore,
          `${viewport.label}: opening the Key retired the keyboard-selected system`,
        );
        assert.ok(measured.stage, `${viewport.label}: Key has no drawing-stage owner`);
        assert.ok(
          measured.panel.top >= measured.stage.top - 1 &&
            measured.panel.bottom <= measured.viewportBottom - 1,
          `${viewport.label}: Key escapes the viewport (${JSON.stringify(measured)})`,
        );
        assert.notEqual(
          measured.background,
          "rgba(0, 0, 0, 0)",
          `${viewport.label}: WebGL can read through the Key`,
        );
        assert.equal(measured.overflowY, "auto", `${viewport.label}: Key does not own its overflow`);
        assert.equal(measured.tabIndex, 0, `${viewport.label}: Key is not keyboard focusable`);
        assert.ok(
          measured.clientHeight >= 80,
          `${viewport.label}: Key leaves only ${measured.clientHeight}px for its scrollable reference`,
        );
        assert.ok(
          measured.scrollHeight <= measured.clientHeight || keyboardScrollTop > 0,
          `${viewport.label}: keyboard input cannot reach the Key's hidden rows`,
        );
        assert.equal(
          measured.possibleStyle,
          "dashed",
          `${viewport.label}: possible route is distinguished by colour alone`,
        );
      } catch (error) {
        failures += 1;
        console.error(`  FAIL ${error.message}`);
      }
      report.push({
        width: viewport.width,
        height: viewport.height,
        register: `easy/key (${viewport.label})`,
        header: "-",
        guidance: "-",
        footer: "-",
        chromeShare: 0,
        canvas: measured.clientHeight,
      });
    } finally {
      await page.close();
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
 * Find one actual rendered node by moving the real pointer across the canvas.
 * `float-tooltip-kap` is owned by three-forcegraph and is shown only when its
 * WebGL raycaster resolves a node, which makes it a useful outside-in signal.
 */
async function hoverRenderedNode(page) {
  const canvas = page.locator(".galaxy-canvas canvas");
  const bounds = await canvas.boundingBox();
  assert.ok(bounds && bounds.width > 0 && bounds.height > 0, "Galaxy canvas has no hoverable area");
  const tooltip = page.locator(".float-tooltip-kap");
  for (let y = bounds.y + 16; y < bounds.y + bounds.height - 16; y += 24) {
    for (let x = bounds.x + 16; x < bounds.x + bounds.width - 16; x += 24) {
      await page.mouse.move(x, y);
      const state = await tooltip.evaluate((element) => ({
        display: getComputedStyle(element).display,
        text: element.textContent?.trim() ?? "",
      }));
      if (state.display !== "none" && state.text) return state;
    }
  }
  assert.fail("The real pointer could not reach any rendered Galaxy node");
}

/**
 * Clear the first-run sequence -- audience, then Home, then coaching -- and
 * settle on the requested register. Every step is optional: the server may
 * already carry a learner's answers, and a clean run is not required here.
 */
async function settleFirstRun(page, register, { home = false } = {}) {
  const gate = page.locator("dialog[open]").first();
  // The gates arrive one after another and each one mounts when the previous
  // one's answer has been round-tripped, so a fixed pause between them is a bet
  // on how fast the machine is. It lost on CI: the Home dialog had not appeared
  // 120ms after the audience answer, the loop saw no open dialog and stopped,
  // and the *next* click was then intercepted by the dialog that arrived a
  // moment later. Wait for each one to actually go instead.
  for (let step = 0; step < 6; step += 1) {
    if ((await gate.count()) === 0) {
      // Give a late-arriving gate a chance to mount before deciding they are
      // all done; nothing is waiting on this but the next assertion.
      await page
        .waitForSelector("dialog[open]", { timeout: 1500 })
        .catch(() => {});
      if ((await gate.count()) === 0) break;
    }
    // Picking a Home is the state the learning loop actually runs in, and the
    // breadcrumb it produces is wider than "Home unselected" -- which is the
    // half of the row that has to yield. Skipping it measures a shell no
    // learner stays in.
    const candidate = gate.getByRole("button").filter({ hasText: /candidate 1/ });
    const skip = gate.getByRole("button", { name: /^(Skip|Explore without Home)$/ });
    const choose = gate.getByRole("button").first();
    const target =
      home && (await candidate.count()) > 0
        ? candidate.first()
        : (await skip.count()) > 0
          ? skip.first()
          : (await choose.count()) > 0
            ? choose
            : null;
    if (!target) break;
    const openBefore = await page.locator("dialog[open]").count();
    await target.click();
    // The dialog this click answered has to be gone before the next iteration
    // reads `dialog[open]`, or it reads the same one twice.
    await page
      .waitForFunction(
        (count) => document.querySelectorAll("dialog[open]").length < count,
        openBefore,
        { timeout: 4000 },
      )
      .catch(() => {});
  }
  // Coach marks are an overlay rather than a dialog, so the loop above never
  // sees them.
  const coach = page.getByRole("button", { name: "Skip", exact: true }).first();
  if ((await coach.count()) > 0 && (await coach.isVisible().catch(() => false))) {
    await coach.click();
    await page.waitForTimeout(150);
  }
  // Nothing below may be clicked through an overlay, and a gate that arrives
  // late is exactly what broke this on CI -- the click landed on the dialog
  // rather than the control and failed 30 seconds later somewhere unrelated.
  // Sweep whatever is still up rather than waiting for it to leave on its own.
  for (let sweep = 0; sweep < 3; sweep += 1) {
    if ((await gate.count()) === 0) break;
    const button = gate.getByRole("button").first();
    if ((await button.count()) === 0) break;
    await button.click().catch(() => {});
    await page.waitForTimeout(300);
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

/**
 * Take the learner one level deeper: top -> region -> study. Returns false when
 * the step could not be taken, so a renamed control fails the gate rather than
 * silently measuring the level above.
 */
async function descend(page, level) {
  if (level === "region") {
    const box = page.locator("[role='button'][aria-label*='structure']").first();
    if ((await box.count()) === 0) return false;
    await box.click({ timeout: 8000 }).catch(() => {});
  } else {
    const read = page.getByRole("button", { name: /read the source/i }).first();
    if ((await read.count()) === 0) return false;
    await read.click({ timeout: 8000 }).catch(() => {});
  }
  await page.waitForTimeout(900);
  const exit = page.getByRole("button", { name: /^Back to (map|galaxy|the module)$/ });
  return (await exit.count()) > 0;
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
    const mapView = document.querySelector(".map-view");
    const mapScrollCue =
      !mapView ||
      mapView.scrollHeight <= mapView.clientHeight + 1 ||
      getComputedStyle(mapView).backgroundImage.includes("radial-gradient");

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

    // Two controls in the same place. Height alone cannot see this: a row that
    // refuses to wrap keeps the header at 148px and spills sideways instead,
    // and `justify-content: flex-end` spills *leftwards* -- straight over the
    // breadcrumb. Measured at 1024 at study level, the actions ran 177px past
    // their own column and put "Modules" and "Find" on top of the two crumbs,
    // so clicking where the app said you were pressed a button instead.
    const clickable = [...document.querySelectorAll("header button, header a[href], header [role='button']")].filter(
      (element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return (
          box.width > 0 &&
          box.height > 0 &&
          style.visibility !== "hidden" &&
          style.display !== "none"
        );
      },
    );
    // The rect a control actually occupies on screen. An ancestor that hides
    // its overflow clips both the paint and the hit test, so a breadcrumb crumb
    // running past its own column is neither visible nor clickable out there --
    // comparing raw bounding boxes would report that as a collision when the
    // learner can see and press exactly the right thing.
    const visibleRect = (element) => {
      let box = element.getBoundingClientRect();
      for (let node = element.parentElement; node; node = node.parentElement) {
        const style = getComputedStyle(node);
        // `display: contents` generates no box, so it clips nothing however its
        // overflow computes. The wide rail turns the disclosure panel into one,
        // and it reports `overflow: auto` on a 0x0 rect -- clipping to that made
        // every control in the header zero-sized and the check unable to fail.
        if (style.display === "contents") continue;
        if (style.overflow === "visible" && style.overflowX === "visible") continue;
        const clip = node.getBoundingClientRect();
        box = {
          left: Math.max(box.left, clip.left),
          right: Math.min(box.right, clip.right),
          top: Math.max(box.top, clip.top),
          bottom: Math.min(box.bottom, clip.bottom),
        };
      }
      return box;
    };

    const overlaps = [];
    for (let i = 0; i < clickable.length; i += 1) {
      for (let j = i + 1; j < clickable.length; j += 1) {
        const [first, second] = [clickable[i], clickable[j]];
        if (first.contains(second) || second.contains(first)) continue;
        const a = visibleRect(first);
        const b = visibleRect(second);
        const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (x > 1 && y > 1) {
          overlaps.push(
            `"${(first.textContent || "").trim().slice(0, 20)}" over ` +
              `"${(second.textContent || "").trim().slice(0, 20)}" (${Math.round(x)}x${Math.round(y)}px)`,
          );
        }
      }
    }

    return {
      header,
      guidance,
      footer,
      mapScrollCue,
      overlaps,
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
