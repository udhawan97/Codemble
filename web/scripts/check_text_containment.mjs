/**
 * Browser contract for Study text containment.
 *
 * Needs a running Codemble because the failure depends on real parser-owned
 * citations and the panel's rendered width. The Rust `main` fixture is the
 * minimal red case: its long source path used to cross the grid gutter and
 * print through the plain-language explanation beside it.
 */

import assert from "node:assert/strict";

import { chromium } from "playwright";

const url = process.env.CODEMBLE_URL;
if (!url) {
  throw new Error("CODEMBLE_URL is required (e.g. http://127.0.0.1:8899).");
}

const browser = await chromium.launch({
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl"],
});

try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 720 },
    deviceScaleFactor: 1,
  });
  page.setDefaultTimeout(30_000);
  await page.goto(url, { waitUntil: "networkidle" });
  await settleFirstRun(page);
  const expert = page.getByRole("radio", {name:"Expert",exact:true});
  if(await expert.isVisible()) await expert.check();
  const galaxy = page.getByRole("button", {name:"Galaxy",exact:true});
  if(await galaxy.isVisible()) await galaxy.click();
  await openRustMainStudy(page);

  const viewports = [
    { width: 1440, height: 720, label: "1440x720" },
    { width: 1024, height: 768, label: "1024x768" },
    { width: 768, height: 720, label: "768x720" },
    { width: 375, height: 720, label: "375x720" },
    { width: 320, height: 640, label: "320x640" },
  ];
  const report = [];
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.waitForTimeout(120);
    const metric = await measureLensContainment(page);
    report.push({ viewport: viewport.label, ...metric });
    assert.equal(
      metric.collisions,
      0,
      `${viewport.label}: ${metric.collisions} lens citation(s) overlap their explanation`,
    );
    assert.equal(
      metric.overflowingLeads,
      0,
      `${viewport.label}: ${metric.overflowingLeads} lens heading column(s) bleed past their track`,
    );
    assert.equal(
      metric.panelHorizontalOverflow,
      0,
      `${viewport.label}: Study panel has ${metric.panelHorizontalOverflow}px of horizontal bleed ` +
        `(${metric.overflowingElements.join(", ") || "no child identified"})`,
    );
  }

  await page.setViewportSize({ width: 1440, height: 720 });
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  await page.waitForTimeout(120);
  const zoomed = await measureLensContainment(page);
  report.push({ viewport: "1440x720 at 200%", ...zoomed });
  assert.equal(zoomed.collisions, 0, "200%: a lens citation overlaps its explanation");
  assert.equal(zoomed.overflowingLeads, 0, "200%: a lens heading column bleeds past its track");
  assert.equal(
    zoomed.panelHorizontalOverflow,
    0,
    `200%: Study panel has ${zoomed.panelHorizontalOverflow}px of horizontal bleed`,
  );

  console.table(report);
  console.log("Study text-containment contracts passed");
} finally {
  await browser.close();
}

async function settleFirstRun(page) {
  const gate = page.getByRole("dialog", {name:"Choose your launch"});
  if(await gate.isVisible()) {
    await gate.getByRole("radio", {name:/Explore freely/}).check();
    await gate.getByRole("radio", {name:"I build software"}).check();
    await gate.getByRole("button", {name:"Open the galaxy"}).click();
  }
  await page.waitForTimeout(700);
  const skip=page.getByRole("button", {name:"Skip",exact:true});
  if(await skip.isVisible()) await skip.click();
}

async function openRustMainStudy(page) {
  await page.keyboard.press("Meta+k");
  const finder=page.locator(".module-finder[open]");
  await finder.getByRole("searchbox").fill("tests/fixtures/rust_sample/src/main.rs");
  await page.keyboard.press("Enter");
  await page.locator(".orientation-copy--system").waitFor();
  await settleFirstRun(page);
  await page.getByRole("application").focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  await page.locator(".study-preview").waitFor();
  const support=page.locator("details.journey-support");
  if(await support.count() && !(await support.evaluate(e=>e.open))) await support.locator("summary").click();
  await page.locator(".lens-note").first().waitFor();
  assert.ok(await page.locator(".lens-note .source-citation").count(), "fixture has source citations to measure");
}

function measureLensContainment(page) {
  return page.evaluate(() => {
    const panel = document.querySelector(".study-preview");
    if (!(panel instanceof HTMLElement)) throw new Error("Study panel is missing.");
    const panelBox = panel.getBoundingClientRect();
    let collisions = 0;
    let overflowingLeads = 0;
    for (const article of panel.querySelectorAll(".lens-note")) {
      if (!(article instanceof HTMLElement)) continue;
      const lead = article.firstElementChild;
      const detail = article.lastElementChild;
      const link = lead?.querySelector(".source-citation");
      const paragraph = detail?.querySelector("p");
      if (!(lead instanceof HTMLElement) || !(link instanceof HTMLElement)) continue;
      if (lead.scrollWidth > lead.clientWidth + 1) overflowingLeads += 1;
      if (!(paragraph instanceof HTMLElement)) continue;
      const citationBox = link.getBoundingClientRect();
      const paragraphBox = paragraph.getBoundingClientRect();
      const horizontal = Math.max(
        0,
        Math.min(citationBox.right, paragraphBox.right) -
          Math.max(citationBox.left, paragraphBox.left),
      );
      const vertical = Math.max(
        0,
        Math.min(citationBox.bottom, paragraphBox.bottom) -
          Math.max(citationBox.top, paragraphBox.top),
      );
      if (horizontal * vertical > 0.5) collisions += 1;
    }
    return {
      collisions,
      overflowingLeads,
      panelHorizontalOverflow: Math.max(0, panel.scrollWidth - panel.clientWidth),
      overflowingElements: [...panel.querySelectorAll("*")]
        .filter((element) => element.getBoundingClientRect().right > panelBox.right + 1)
        .slice(0, 8)
        .map((element) => {
          const box = element.getBoundingClientRect();
          return `${element.tagName.toLowerCase()}.${element.className || "-"} +${Math.round(box.right - panelBox.right)}px`;
        }),
    };
  });
}
