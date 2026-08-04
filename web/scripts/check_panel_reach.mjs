/**
 * A panel may not hide its own content, and may not deface it.
 *
 * Two panels in this app scroll their own box: the study panel and the checks
 * panel. On macOS neither draws a scrollbar until you scroll one, so a panel
 * that overflows looks exactly like a panel that has ended. This project has
 * already fixed that failure twice at other addresses -- the Map's region
 * caption (55147ac) and the Map's own drawing, whose scroll shadows carry the
 * comment this gate exists to generalise -- and both times the bug reached a
 * release because nothing re-read the numbers.
 *
 * Measured on this repository at v0.15.0, before the fix:
 *
 *   study panel, 1440x900 easy   7.8 viewports of content, 9 headings below
 *                                the fold, no cue of any kind
 *   checks panel, 1280x720 easy  options 1 and 2 covered 43% and 32% by the
 *                                sticky submit; options 3 and 4 off screen
 *   checks panel, 320x640 easy   the QUESTION covered 64%, and 0 of 4 answer
 *                                options visible -- a quiz showing no answers
 *
 * Scrolling recovered all of it, which is what keeps these Major rather than
 * Blockers, and is also exactly why they survived: every automated check that
 * scrolled first saw a correct panel.
 *
 * Needs a running Codemble. Point `CODEMBLE_URL` at one; like the space budget
 * it stays out of `npm run check`, which is Node-only and offline.
 */

import assert from "node:assert/strict";

import { chromium } from "playwright";

const url = process.env.CODEMBLE_URL;
if (!url) {
  throw new Error("CODEMBLE_URL is required (e.g. http://127.0.0.1:8899).");
}

// The quiz is the product's central action -- it is the only way a module ever
// lights -- so it is measured at the extremes rather than at one comfortable
// width. 320x640 is where it failed worst and 1440x900 is where it looked fine.
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 375, height: 720 },
  { width: 320, height: 640 },
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
    const page = await browser.newPage({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(12_000);
    const label = `${viewport.width}x${viewport.height} easy`;
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy");

      if (!(await descendToRegion(page))) {
        failures += 1;
        console.error(`  FAIL ${label}: could not reach a module from the map`);
        continue;
      }

      // --- the study panel ------------------------------------------------
      if (await openStudy(page)) {
        const study = await measurePanel(page, ".study-preview");
        report.push({ label, panel: "study", ...study });
        try {
          assert.ok(
            !study.overflows || study.hasOverflowCue,
            `${label}: the study panel holds ${study.viewports} viewports of content ` +
              `(${study.headingsBelowFold} headings below the fold) and draws nothing to ` +
              `say so -- on macOS its scrollbar is invisible until scrolled`,
          );
        } catch (error) {
          failures += 1;
          console.error(`  FAIL ${error.message}`);
        }
        await leaveStudy(page);
      }

      // --- the checks panel -----------------------------------------------
      if (!(await openChecks(page))) {
        failures += 1;
        console.error(`  FAIL ${label}: could not open the checks panel`);
        continue;
      }
      const quiz = await measureQuiz(page);
      report.push({ label, panel: "checks", ...quiz });

      try {
        // The panel's own question may never be covered by the panel's own
        // control. This is the assertion that fails hardest today: 64% at 320.
        assert.equal(
          quiz.questionCoveredPct,
          0,
          `${label}: the sticky submit covers ${quiz.questionCoveredPct}% of the question ` +
            `the learner is being asked -- the quiz defaces its own prompt`,
        );
        // A quiz that shows no answers is not a quiz. One fully visible option
        // is the floor; the cue below is what makes the rest discoverable.
        assert.ok(
          quiz.optionsFullyVisible >= 1,
          `${label}: the quiz opens with ${quiz.optionsFullyVisible} of ${quiz.optionCount} ` +
            `answer options visible -- the learner sees a question and a disabled button`,
        );
        assert.ok(
          !quiz.overflows || quiz.hasOverflowCue,
          `${label}: the checks panel holds ${quiz.viewports} viewports of content and draws ` +
            `nothing to say so -- ${quiz.optionCount - quiz.optionsFullyVisible} of ` +
            `${quiz.optionCount} options are out of view with no scrollbar to reveal them`,
        );
        // Every option has to be reachable once scrolled, or the sticky control
        // has taken space the list can never clear.
        assert.equal(
          quiz.optionsVisibleAfterScroll,
          quiz.optionCount,
          `${label}: after scrolling to the bottom only ${quiz.optionsVisibleAfterScroll} of ` +
            `${quiz.optionCount} options are clear of the submit control`,
        );
      } catch (error) {
        failures += 1;
        console.error(`  FAIL ${error.message}`);
      }
    } finally {
      await page.close();
    }
  }

  // The star chart is the same bug at a third address: 130 concept rows and
  // 14.6 viewports at 1440x900, in a surface reachable from every level, with
  // nothing on screen to say the list continued past the fold.
  {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(12_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy");
      const more = page.getByRole("button", { name: /^(More|Menu)$/ });
      if ((await more.count()) > 0 && (await more.first().isVisible())) {
        await more.first().click();
        await page.waitForTimeout(120);
      }
      const chart = page.getByRole("button", { name: /star chart/i }).first();
      if ((await chart.count()) === 0) {
        failures += 1;
        console.error("  FAIL 1440x900 easy: could not reach the star chart");
      } else {
        await chart.click({ timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(900);
        const measured = await measurePanel(page, ".star-chart-screen");
        report.push({ label: "1440x900 easy", panel: "star chart", ...measured });
        try {
          assert.ok(
            !measured.missing,
            "1440x900 easy: the star chart did not open, so its overflow was never measured",
          );
          assert.ok(
            measured.missing || !measured.overflows || measured.hasOverflowCue,
            `1440x900 easy: the star chart holds ${measured.viewports} viewports of ` +
              `concepts and draws nothing to say so`,
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

  // The enumeration above finds the surfaces someone thought of. This finds the
  // rest: open everything a learner can open, then assert that *nothing* on
  // screen scrolls its own box without saying so. Written as a sweep because
  // the same bug turned up at five separate addresses -- fixing them one at a
  // time is how the sixth ships.
  {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(12_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy");
      const surfaces = [
        { name: "module index", open: /^Modules$/ },
        { name: "find palette", open: /^Find/ },
        { name: "star chart", open: /star chart/i },
      ];
      for (const surface of surfaces) {
        const more = page.getByRole("button", { name: /^(More|Menu)$/ });
        if ((await more.count()) > 0 && (await more.first().isVisible())) {
          await more.first().click();
          await page.waitForTimeout(120);
        }
        const control = page.getByRole("button", { name: surface.open }).first();
        if ((await control.count()) === 0) {
          failures += 1;
          console.error(`  FAIL sweep: could not reach the ${surface.name}`);
          continue;
        }
        await control.click({ timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(700);
        const silent = await page.evaluate(() => {
          const cued = (element) => {
            const style = getComputedStyle(element);
            return (
              /gradient/.test(style.backgroundImage) ||
              (style.maskImage !== "none" && style.maskImage !== "") ||
              ["::before", "::after"].some(
                (part) => getComputedStyle(element, part).content !== "none",
              ) ||
              element.offsetWidth - element.clientWidth > 2
            );
          };
          return [...document.querySelectorAll("*")]
            .filter((element) => {
              const style = getComputedStyle(element);
              // A scroll container tall enough that a whole row can hide in it.
              // The 48px floor keeps a one-line rounding overflow out of this.
              return (
                element.scrollHeight > element.clientHeight + 48 &&
                /auto|scroll/.test(style.overflowY) &&
                element.clientHeight > 0
              );
            })
            .filter((element) => !cued(element))
            .map((element) => {
              const name =
                (typeof element.className === "string" && element.className) ||
                element.tagName.toLowerCase();
              return `${name} (${(element.scrollHeight / element.clientHeight).toFixed(1)} viewports)`;
            });
        });
        try {
          assert.deepEqual(
            silent,
            [],
            `sweep (${surface.name}): ${silent.length} surface(s) scroll their own box ` +
              `with nothing on screen to say so -- ${silent.join("; ")}`,
          );
        } catch (error) {
          failures += 1;
          console.error(`  FAIL ${error.message}`);
        }
        await page.keyboard.press("Escape");
        await page.waitForTimeout(300);
      }
    } finally {
      await page.close();
    }
  }

  // `position: sticky` was applied to `.check-primary`, which is the app's
  // shared primary-button class on ten buttons across six components. Only the
  // quiz submit is inside a scrolling panel that needs it; the other nine
  // inherited it silently. Scope, asserted rather than remembered.
  {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 720 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(12_000);
    try {
      await page.goto(url, { waitUntil: "networkidle" });
      await settleFirstRun(page, "easy");
      const stuck = await page.evaluate(() => {
        const probe = document.createElement("button");
        probe.className = "check-primary";
        probe.textContent = "probe";
        document.body.append(probe);
        const position = getComputedStyle(probe).position;
        probe.remove();
        return position;
      });
      try {
        assert.notEqual(
          stuck,
          "sticky",
          `a bare .check-primary computes position: ${stuck} -- the shared primary-button ` +
            `class carries the quiz submit's stickiness to nine unrelated buttons`,
        );
      } catch (error) {
        failures += 1;
        console.error(`  FAIL ${error.message}`);
      }
    } finally {
      await page.close();
    }
  }
} finally {
  await browser.close();
}

console.table(
  report.map((row) => ({
    viewport: row.label,
    panel: row.panel,
    viewports: row.viewports,
    cue: row.hasOverflowCue ? "yes" : "no",
    questionCovered: row.questionCoveredPct === undefined ? "-" : `${row.questionCoveredPct}%`,
    optionsVisible:
      row.optionCount === undefined ? "-" : `${row.optionsFullyVisible}/${row.optionCount}`,
  })),
);

if (failures > 0) {
  throw new Error(`${failures} panel-reach assertion(s) failed`);
}
console.log("panel-reach contracts passed");

/** Clear the first-run sequence and settle on a register. */
async function settleFirstRun(page, register) {
  const gate = page.locator("dialog[open]").first();
  for (let step = 0; step < 6; step += 1) {
    if ((await gate.count()) === 0) {
      await page.waitForSelector("dialog[open]", { timeout: 1500 }).catch(() => {});
      if ((await gate.count()) === 0) break;
    }
    const skip = gate.getByRole("button", { name: /^(Skip|Explore without Home)$/ });
    const target = (await skip.count()) > 0 ? skip.first() : gate.getByRole("button").first();
    if ((await target.count()) === 0) break;
    const openBefore = await page.locator("dialog[open]").count();
    await target.click();
    await page
      .waitForFunction(
        (count) => document.querySelectorAll("dialog[open]").length < count,
        openBefore,
        { timeout: 4000 },
      )
      .catch(() => {});
  }
  const coach = page.getByRole("button", { name: "Skip", exact: true }).first();
  if ((await coach.count()) > 0 && (await coach.isVisible().catch(() => false))) {
    await coach.click();
    await page.waitForTimeout(150);
  }
  const more = page.getByRole("button", { name: /^(More|Menu)$/ });
  const usedDisclosure = (await more.count()) > 0 && (await more.first().isVisible());
  if (usedDisclosure) {
    await more.first().click();
    await page.waitForTimeout(80);
  }
  const radio = page.getByRole("radio", { name: register });
  if ((await radio.count()) > 0 && (await radio.first().isVisible())) {
    await radio.first().click();
    await page.waitForTimeout(250);
  }
  // At compact widths every rail action lives behind this disclosure, and an
  // open panel covers the map. Leaving it open made the box click below land on
  // the panel instead: the gate then reported "could not reach a module", which
  // is indistinguishable from the defect it exists to catch. Close what we
  // opened.
  if (usedDisclosure && (await more.first().isVisible().catch(() => false))) {
    await more.first().click();
    await page.waitForTimeout(120);
  }
  await page.waitForTimeout(350);
}

async function descendToRegion(page) {
  const box = page.locator("[role='button'][aria-label*='structure']").first();
  if ((await box.count()) === 0) return false;
  await box.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(700);
  // Confirm the level from the breadcrumb, not from the "Back to map" action.
  // At compact widths that action lives inside the Menu disclosure, which is
  // `display: none` while closed -- so it is absent from the accessibility tree
  // and `getByRole` counts zero even though the descent worked perfectly. The
  // breadcrumb is rendered at every width and is the thing that states the
  // level anyway.
  const crumbs = await page.evaluate(() => {
    const nav = document.querySelector("nav[aria-label='Breadcrumb']");
    return nav ? nav.textContent.trim() : "";
  });
  return crumbs.includes("/");
}

async function openStudy(page) {
  const read = page.getByRole("button", { name: /read the source/i }).first();
  if ((await read.count()) === 0) return false;
  await read.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(900);
  // "Read the source" scrolls the panel to the source on purpose; the cue is a
  // property of the panel at rest, so measure it from the top.
  await page.evaluate(() => {
    const panel = document.querySelector(".study-preview");
    if (panel) panel.scrollTop = 0;
  });
  return (await page.locator(".study-preview").count()) > 0;
}

async function leaveStudy(page) {
  const back = page.getByRole("button", { name: /^Back to the module$/ }).first();
  if ((await back.count()) > 0) {
    await back.click().catch(() => {});
    await page.waitForTimeout(500);
  }
}

async function openChecks(page) {
  const prove = page.getByRole("button", { name: /prove understanding/i }).first();
  if ((await prove.count()) === 0) return false;
  await prove.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(900);
  return (await page.locator(".check-panel .active-check").count()) > 0;
}

/**
 * Does this panel say, at rest, that it continues past its own edge? The Map's
 * drawing answers with `local`/`scroll` background gradients, which appear and
 * disappear on their own and cost the content no height; anything equivalent
 * counts here, so the assertion is about the cue existing rather than about how
 * it is drawn.
 */
function measurePanel(page, selector) {
  return page.evaluate((sel) => {
    const panel = document.querySelector(sel);
    if (!panel) return { missing: true };
    const style = getComputedStyle(panel);
    const overflows = panel.scrollHeight > panel.clientHeight + 1;
    const cueFromBackground = /gradient/.test(style.backgroundImage);
    const cueFromMask = style.maskImage !== "none" && style.maskImage !== "";
    const cueFromEdges = ["::before", "::after"].some(
      (part) => getComputedStyle(panel, part).content !== "none",
    );
    // A scrollbar that actually takes layout width is itself an honest cue;
    // macOS overlay scrollbars reserve nothing, which is the whole problem.
    const cueFromScrollbar = panel.offsetWidth - panel.clientWidth > 2;
    return {
      overflows,
      viewports: +(panel.scrollHeight / panel.clientHeight).toFixed(1),
      headingsBelowFold: [...panel.querySelectorAll("h2,h3")].filter(
        (heading) => heading.getBoundingClientRect().top > window.innerHeight,
      ).length,
      hasOverflowCue: cueFromBackground || cueFromMask || cueFromEdges || cueFromScrollbar,
    };
  }, selector);
}

function measureQuiz(page) {
  return page.evaluate(() => {
    const panel = document.querySelector(".check-panel");
    const legend = panel.querySelector("legend");
    const submit = [...panel.querySelectorAll("button")].find((button) =>
      /check answer/i.test(button.textContent),
    );
    const options = [...panel.querySelectorAll(".check-options label")];
    const covered = (element) => {
      if (!submit) return 0;
      const a = element.getBoundingClientRect();
      const b = submit.getBoundingClientRect();
      const overlap = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
      return Math.round((100 * overlap) / a.height);
    };
    // "Fully visible" means inside the window AND clear of the submit control:
    // an option the learner can read and click without moving anything.
    const clearlyVisible = () =>
      options.filter((option) => {
        const box = option.getBoundingClientRect();
        return box.top >= 0 && box.bottom <= window.innerHeight && covered(option) === 0;
      }).length;

    const style = getComputedStyle(panel);
    const atOpen = {
      questionCoveredPct: legend ? covered(legend) : 0,
      optionCount: options.length,
      optionsFullyVisible: clearlyVisible(),
      overflows: panel.scrollHeight > panel.clientHeight + 1,
      viewports: +(panel.scrollHeight / panel.clientHeight).toFixed(1),
      hasOverflowCue:
        /gradient/.test(style.backgroundImage) ||
        (style.maskImage !== "none" && style.maskImage !== "") ||
        ["::before", "::after"].some(
          (part) => getComputedStyle(panel, part).content !== "none",
        ) ||
        panel.offsetWidth - panel.clientWidth > 2,
    };
    panel.scrollTop = panel.scrollHeight;
    return { ...atOpen, optionsVisibleAfterScroll: options.filter((o) => covered(o) === 0).length };
  });
}
