/**
 * Escape, pressed for real, on every surface, at every shell width.
 *
 * `check_escape_arbiter.mjs` proves the *decision* -- which surface owns the
 * key, and the answer for every combination. It cannot prove the key arrives,
 * that the surface actually closes, or that focus lands somewhere a keyboard
 * user can carry on from. Those need a browser, and every Escape bug this
 * project has shipped was one of them:
 *
 *   - the rail disclosure closed *and* retreated a level on one keypress,
 *     which only compact widths could reach
 *   - the checks panel and the module index never claimed the key at all
 *   - the star chart dismissed itself and then retreated on top of it
 *
 * Width matters because the shell is two shells. Above 64rem the rail actions
 * sit in the header; below it every one of them -- Modules, Find, the star
 * chart, the layer switcher -- lives behind the Menu disclosure, so reaching
 * any surface means opening a *second* surface first. That is precisely the
 * arrangement the double-fire needed, and it is unreachable at desktop.
 *
 * The in-app browser pane cannot stand in for this: it reports
 * `document.hidden === true`, which throttles requestAnimationFrame, and the
 * galaxy's frames run 1-4s under software WebGL. The first assertion guards it.
 *
 * Needs a running Codemble; point `CODEMBLE_URL` at one. Deliberately not part
 * of `npm run check`, which stays Node-only, offline and fast.
 */

import { chromium } from "playwright";

const url = process.env.CODEMBLE_URL;
if (!url) {
  throw new Error("CODEMBLE_URL is required (e.g. http://127.0.0.1:8899).");
}

// One wide shell plus three compact ones. 768 is compact because the rail's
// wide layout starts at 64rem -- a width that looks like a desktop and behaves
// like a phone, which is where a width-only bug hides best.
const VIEWPORTS = [
  { width: 1440, height: 900, shell: "wide" },
  { width: 768, height: 1024, shell: "compact" },
  { width: 375, height: 812, shell: "compact" },
  { width: 320, height: 720, shell: "compact" },
];

const DISCLOSURE = /^(More|Menu)$/;

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl"],
});

const results = [];

for (const viewport of VIEWPORTS) {
  const label = `${viewport.width}x${viewport.height}`;
  const page = await browser.newPage({
    viewport: { width: viewport.width, height: viewport.height },
  });
  // A control that has been renamed or removed should fail this gate, not hang
  // it. Playwright's 30s default, times a dozen locators, reads as a stuck job.
  page.setDefaultTimeout(15_000);
  try {
    await runViewport(page, viewport, label);
  } catch (error) {
    results.push({ label, surface: "run", note: `threw: ${error.message.split("\n")[0]}`, ok: false });
  } finally {
    await page.close();
  }
}

await browser.close();

const width = Math.max(...results.map((result) => `${result.label} ${result.surface}`.length));
let shown = "";
for (const result of results) {
  if (result.label !== shown) {
    console.log(`\n── ${result.label} ─────────────────────────────`);
    shown = result.label;
  }
  const name = `${result.label} ${result.surface}`.padEnd(width);
  console.log(`${result.ok ? "PASS" : "FAIL"}  ${name}  ${result.note}`);
}

const failed = results.filter((result) => !result.ok);
console.log("");
if (failed.length > 0) {
  throw new Error(
    `${failed.length} escape assertion(s) failed: ` +
      failed.map((f) => `${f.label} ${f.surface}`).join("; "),
  );
}
console.log(`escape-surface contracts passed (${results.length} assertions across ${VIEWPORTS.length} widths)`);

async function runViewport(page, viewport, label) {
  const record = (surface, note, ok) => results.push({ label, surface, note, ok });

  /** Everything an Escape assertion needs to read, in one round trip. */
  const state = () =>
    page.evaluate(() => ({
      hidden: document.hidden,
      chart: !!document.querySelector(".chart-stage"),
      sidebar: !!document.querySelector("[class*='index-sidebar'], aside[class*='sidebar']"),
      checks: !!document.querySelector("[class*='check-panel']"),
      dialog: !!document.querySelector("dialog[open]"),
      railOpen: !!document.querySelector(".rail-overflow[data-open]"),
      // The breadcrumb is the level and layer the learner can see. A
      // double-fire shows up here and nowhere else.
      breadcrumb: document.querySelector("header")?.innerText.split("\n")[2] ?? "",
      focus: (() => {
        const active = document.activeElement;
        if (!active || active === document.body) return "(body)";
        const text = active.textContent || active.getAttribute("aria-label") || "";
        return `${active.tagName}:${text.trim().slice(0, 24)}`;
      })(),
    }));

  const locate = (name) =>
    page
      .getByRole("button", typeof name === "string" ? { name, exact: true } : { name })
      .first();

  const trigger = () => locate(DISCLOSURE);

  /**
   * Bring a rail control within reach, opening the Menu disclosure when the
   * compact shell has hidden it there.
   */
  const reveal = async (name) => {
    let button = locate(name);
    if ((await button.count()) > 0 && (await button.isVisible())) return button;
    const menu = trigger();
    if ((await menu.count()) === 0) return null;
    await menu.click();
    await page.waitForTimeout(300);
    button = locate(name);
    if ((await button.count()) === 0 || !(await button.isVisible())) return null;
    return button;
  };

  const click = async (name) => {
    const button = await reveal(name);
    if (!button || !(await button.isEnabled())) return false;
    await button.click();
    await page.waitForTimeout(350);
    return true;
  };

  /**
   * Press Escape and wait for the shell to settle, rather than for a fixed
   * delay. A hard sleep cannot measure this: focus return is deferred, and how
   * long that takes depends on how busy the page is -- the galaxy's frames run
   * 1-4s under software WebGL. Waiting for the condition is neither flaky nor
   * slow, and still fails if focus never arrives.
   */
  const escape = async () => {
    await page.keyboard.press("Escape");
    await page
      .waitForFunction(() => document.activeElement !== document.body, null, { timeout: 8000 })
      .catch(() => {});
    await page.waitForTimeout(150);
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

  const start = await state();
  record(
    "foreground",
    `document.hidden=${start.hidden}; rAF is throttled when hidden and the galaxy's frames run 1-4s`,
    start.hidden === false,
  );

  /** A surface the caller closes: it shuts, the level stays, focus comes back. */
  async function dismisses(name, opener, field, { expectFocus = true } = {}) {
    // Taken *before* opening: while the star chart is open the breadcrumb reads
    // "Star chart", so comparing open-vs-closed compares two different correct
    // states rather than detecting a double-fire.
    const baseline = await state();
    if (!(await click(opener))) {
      record(name, `could not reach its control`, false);
      return;
    }
    const opened = await state();
    if (!opened[field]) {
      record(name, `its control did not open it`, false);
      return;
    }
    const closed = await escape();
    record(name, `open -> ${closed[field] ? "STILL OPEN" : "closed"}`, !closed[field]);
    record(
      `${name} / stays put`,
      `"${baseline.breadcrumb}" -> "${closed.breadcrumb}"`,
      baseline.breadcrumb === closed.breadcrumb,
    );
    // The compact shell reaches a rail action *through* the Menu, and the Menu
    // closes itself on the way. Escape must not then find it open.
    record(`${name} / menu not left open`, `railOpen=${closed.railOpen}`, closed.railOpen === false);
    if (expectFocus) record(`${name} / focus`, closed.focus, closed.focus !== "(body)");
  }

  await dismisses("star chart", "Star chart", "chart");
  await dismisses("modules", "Modules", "sidebar");
  await dismisses("find", /^Find/, "dialog", { expectFocus: false });

  // The disclosure itself, which is the one surface that exists at every width
  // and is the only way to reach the others below 64rem.
  {
    const baseline = await state();
    const menu = trigger();
    if ((await menu.count()) === 0) {
      record("rail disclosure", "no disclosure at this width", false);
    } else {
      await menu.click();
      await page.waitForTimeout(300);
      const opened = await state();
      const closed = await escape();
      record("rail disclosure", `open=${opened.railOpen} -> ${closed.railOpen}`,
        opened.railOpen && !closed.railOpen);
      record("rail disclosure / stays put", `"${baseline.breadcrumb}" -> "${closed.breadcrumb}"`,
        baseline.breadcrumb === closed.breadcrumb);
      record("rail disclosure / focus", closed.focus, closed.focus !== "(body)");
    }
  }

  // ── The checks panel, reached the way a learner reaches it ───────────────

  // The layer switcher is named for the register: Easy calls it "Diagram" and
  // Expert calls it "Map". This ran Easy and clicked "Map", so it never left the
  // Galaxy -- the box click below then found nothing, and four widths reported
  // "could not reach the prove control" and a retreat that never had anywhere
  // to retreat from. A gate that cannot reach its own surface fails loudly for
  // the wrong reason, which is indistinguishable from the bug it exists to
  // catch.
  await click(/^(Map|Diagram)$/);
  await page.waitForTimeout(600);
  const box = page.locator("svg g[class*='map-box'], svg [class*='box']").first();
  if ((await box.count()) > 0) await box.click({ force: true }).catch(() => {});
  await page.waitForTimeout(600);

  const checksBaseline = await state();
  if (!(await click(/Prove understanding|Review understanding|Check availability/))) {
    record("checks panel", "could not reach the prove control from the map", false);
  } else {
    const opened = await state();
    const closed = await escape();
    record("checks panel", `open=${opened.checks} -> ${closed.checks}`,
      opened.checks && !closed.checks);
    record("checks panel / stays put", `"${checksBaseline.breadcrumb}" -> "${closed.breadcrumb}"`,
      checksBaseline.breadcrumb === closed.breadcrumb);
    record("checks panel / focus", closed.focus, closed.focus !== "(body)");
  }

  // ── Escape must never navigate while the learner is typing ───────────────

  if (await click(/^Find/)) {
    const field = page.locator("dialog[open] input").first();
    if ((await field.count()) > 0) {
      await field.fill("codemble");
      const typing = await state();
      const after = await escape();
      record("typing in a field", `"${typing.breadcrumb}" -> "${after.breadcrumb}"`,
        typing.breadcrumb === after.breadcrumb);
    }
  }

  // ── Retreat, and the one place there is nothing to retreat to ────────────

  await click(/^(Map|Diagram)$/);
  await page.waitForTimeout(600);
  const deep = page.locator("svg g[class*='map-box'], svg [class*='box']").first();
  if ((await deep.count()) > 0) await deep.click({ force: true }).catch(() => {});
  await page.waitForTimeout(600);
  const inside = await state();
  const back = await escape();
  record("map retreat", `"${inside.breadcrumb}" -> "${back.breadcrumb}"`,
    inside.breadcrumb !== back.breadcrumb || inside.breadcrumb === "");

  await click("Galaxy");
  await page.waitForTimeout(600);
  const top = await state();
  const stillTop = await escape();
  record("galaxy top level", `"${top.breadcrumb}" -> "${stillTop.breadcrumb}" (nothing above it)`,
    top.breadcrumb === stillTop.breadcrumb);
}
