import { chromium } from "playwright";

const demoUrl = process.env.CODEMBLE_DEMO_URL;
const framesDirectory = process.env.CODEMBLE_DEMO_FRAMES;
if (!demoUrl || !framesDirectory) {
  throw new Error("CODEMBLE_DEMO_URL and CODEMBLE_DEMO_FRAMES are required.");
}

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl"],
});
const page = await browser.newPage({
  viewport: { width: 1000, height: 640 },
  deviceScaleFactor: 1,
});
let frame = 0;

async function capture(hold = 4) {
  const image = await page.screenshot();
  for (let index = 0; index < hold; index += 1) {
    frame += 1;
    const name = `${framesDirectory}/frame-${String(frame).padStart(3, "0")}.png`;
    await import("node:fs/promises").then(({ writeFile }) => writeFile(name, image));
  }
}

await page.goto(demoUrl, { waitUntil: "networkidle" });
const galaxy = page.getByRole("application");
await galaxy.waitFor();
await capture(5);

await galaxy.focus();
await galaxy.press("ArrowRight");
await galaxy.press("ArrowRight");
await galaxy.press("Enter");
await page.waitForTimeout(500);
await capture(5);

await page.getByRole("button", { name: "Prove understanding" }).click();
await page.getByRole("group", { name: /Which structure does/ }).waitFor();
await capture(5);

const answers = ["pkg.service.Service", "cli", "cli.launch", "app"];
for (const answer of answers) {
  await page.getByRole("radio", { name: answer, exact: true }).click();
  await page.getByRole("button", { name: "Check answer" }).click();
  await page.waitForTimeout(180);
  await capture(answer === "app" ? 3 : 2);
}
await page.waitForTimeout(500);
await capture(6);

await browser.close();
