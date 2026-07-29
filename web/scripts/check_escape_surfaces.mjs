/**
 * Escape, pressed for real, on every surface that can be open over the stage.
 *
 * `check_escape_arbiter.mjs` proves the *decision* -- which surface owns the
 * key, and what the answer is for every combination. It cannot prove the key
 * arrives, that the surface actually closes, or that focus lands somewhere a
 * keyboard user can carry on from. Those need a browser, and every Escape bug
 * this project has shipped was one of them:
 *
 *   - the rail disclosure closed *and* retreated a level on one keypress
 *   - the checks panel and the module index never claimed the key at all
 *   - the star chart dismissed itself and then retreated on top of it
 *
 * The in-app browser pane cannot stand in for this: it reports
 * `document.hidden === true`, which throttles requestAnimationFrame, and
 * `restoreRailFocus` is rAF-based -- so focus return reads as broken there
 * whether or not it is. The first assertion below guards that trap.
 *
 * Needs a running Codemble; point `CODEMBLE_URL` at one. Deliberately not part
 * of `npm run check`, which stays Node-only, offline and fast.
 */

import { chromium } from "playwright";

const url = process.env.CODEMBLE_URL;
if (!url) {
  throw new Error("CODEMBLE_URL is required (e.g. http://127.0.0.1:8899).");
}

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const results = [];
const record = (surface, note, ok) => results.push({ surface, note, ok });

/** Everything an Escape assertion needs to read, in one round trip. */
const state = () =>
  page.evaluate(() => ({
    hidden: document.hidden,
    chart: !!document.querySelector(".chart-stage"),
    sidebar: !!document.querySelector("[class*='index-sidebar'], aside[class*='sidebar']"),
    checks: !!document.querySelector("[class*='check-panel']"),
    dialog: !!document.querySelector("dialog[open]"),
    railOpen: !!document.querySelector(".rail-overflow[data-open]"),
    // The breadcrumb is the level and layer the learner can see. A double-fire
    // shows up here and nowhere else.
    breadcrumb: document.querySelector("header")?.innerText.split("\n")[2] ?? "",
    focus: (() => {
      const active = document.activeElement;
      if (!active || active === document.body) return "(body)";
      const label = active.textContent || active.getAttribute("aria-label") || "";
      return `${active.tagName}:${label.trim().slice(0, 24)}`;
    })(),
  }));

const click = async (name) => {
  // Exact for strings: "Modules" otherwise also matches the disabled
  // "All modules" breadcrumb, and Playwright waits out the click on it.
  const button = page
    .getByRole("button", typeof name === "string" ? { name, exact: true } : { name })
    .first();
  if ((await button.count()) === 0) return false;
  if (!(await button.isEnabled())) return false;
  await button.click();
  await page.waitForTimeout(350);
  return true;
};

const escape = async () => {
  await page.keyboard.press("Escape");
  await page.waitForTimeout(450);
  return state();
};

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(700);

// Clear whatever first-run steps this data directory still has.
for (let step = 0; step < 5; step += 1) {
  const dialog = page.locator("dialog[open]");
  if ((await dialog.count()) === 0) break;
  const skip = dialog.getByRole("button", { name: /^(Skip|Explore without Home)$/ });
  if ((await skip.count()) > 0) await skip.first().click();
  else await dialog.getByRole("button").first().click();
  await page.waitForTimeout(250);
}

// ── The trap this file exists to avoid ─────────────────────────────────────

const start = await state();
record(
  "foreground page",
  `document.hidden=${start.hidden}; rAF is throttled when hidden and focus return is rAF-based`,
  start.hidden === false,
);

// ── A dismissible surface: closes, stays put, hands focus back ─────────────

/**
 * @param {string} name     what to assert about
 * @param {string} opener   the control that opens it, by accessible name
 * @param {string} field    the `state()` key that says it is open
 * @param {boolean} expectFocusReturn  false only where nothing sensible remains
 */
async function dismisses(name, opener, field, expectFocusReturn = true) {
  // Taken *before* opening: while the star chart is open the breadcrumb reads
  // "Star chart", so comparing open-vs-closed compares two different correct
  // states rather than detecting a double-fire.
  const baseline = await state();
  if (!(await click(opener))) {
    record(name, `could not find the "${opener}" control`, false);
    return;
  }
  const opened = await state();
  if (!opened[field]) {
    record(name, `"${opener}" did not open it`, false);
    return;
  }
  const closed = await escape();
  record(name, `open -> ${closed[field] ? "still open" : "closed"}`, !closed[field]);
  record(
    `${name} / stays put`,
    `"${baseline.breadcrumb}" -> "${closed.breadcrumb}"`,
    baseline.breadcrumb === closed.breadcrumb,
  );
  if (expectFocusReturn) {
    record(`${name} / focus`, closed.focus, closed.focus !== "(body)");
  }
}

await dismisses("star chart", "Star chart", "chart");
await dismisses("modules sidebar", "Modules", "sidebar");
await dismisses("find palette", /^Find/, "dialog", false);
await dismisses("rail disclosure", /^(More|Menu)$/, "railOpen");

// ── The checks panel, reached the way a learner reaches it ─────────────────

await click("Map");
await page.waitForTimeout(600);
const box = page.locator("svg g[class*='map-box'], svg [class*='box']").first();
if ((await box.count()) > 0) await box.click({ force: true }).catch(() => {});
await page.waitForTimeout(600);

const checksBaseline = await state();
const opened = await click(/Prove understanding|Review understanding|Check availability/);
if (!opened) {
  record("checks panel", "could not reach the prove control from the map", false);
} else {
  const open = await state();
  const closed = await escape();
  record("checks panel", `open=${open.checks} -> ${closed.checks}`, open.checks && !closed.checks);
  record(
    "checks panel / stays put",
    `"${checksBaseline.breadcrumb}" -> "${closed.breadcrumb}"`,
    checksBaseline.breadcrumb === closed.breadcrumb,
  );
  // The quiz is opened from a control that stays on screen behind it, so
  // there is somewhere obvious to go back to. Every other dismissible surface
  // returns focus; this one dropped it on the floor.
  record("checks panel / focus", closed.focus, closed.focus !== "(body)");
}

// ── Escape must never navigate while the learner is typing ────────────────

await click(/^Find/);
const field = page.locator("dialog[open] input").first();
if ((await field.count()) > 0) {
  await field.fill("codemble");
  const typing = await state();
  const after = await escape();
  record(
    "typing in a field",
    `"${typing.breadcrumb}" -> "${after.breadcrumb}"`,
    typing.breadcrumb === after.breadcrumb,
  );
}

// ── Retreat, and the one place there is nothing to retreat to ─────────────

await click("Map");
await page.waitForTimeout(600);
const deepBox = page.locator("svg g[class*='map-box'], svg [class*='box']").first();
if ((await deepBox.count()) > 0) await deepBox.click({ force: true }).catch(() => {});
await page.waitForTimeout(600);
const inside = await state();
const back = await escape();
record(
  "map retreat",
  `"${inside.breadcrumb}" -> "${back.breadcrumb}"`,
  inside.breadcrumb !== back.breadcrumb || inside.breadcrumb === "",
);

await click("Galaxy");
await page.waitForTimeout(600);
const top = await state();
const stillTop = await escape();
record(
  "galaxy top level",
  `"${top.breadcrumb}" -> "${stillTop.breadcrumb}" (nothing above it to reach)`,
  top.breadcrumb === stillTop.breadcrumb,
);

await browser.close();

const width = Math.max(...results.map((result) => result.surface.length));
const failed = results.filter((result) => !result.ok);
for (const result of results) {
  console.log(`${result.ok ? "PASS" : "FAIL"}  ${result.surface.padEnd(width)}  ${result.note}`);
}
if (failed.length > 0) {
  throw new Error(`${failed.length} escape surface(s) misbehaved`);
}
console.log("\nescape-surface contracts passed");
