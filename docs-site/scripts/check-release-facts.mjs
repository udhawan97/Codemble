import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(docsRoot, "..");
const read = (path) => readFile(resolve(repositoryRoot, path), "utf8");
const release = JSON.parse(await read("docs-site/release.json"));
const args = process.argv.slice(2);
const live = args.includes("--live");
const distFlag = args.indexOf("--dist");
const distDirectory = distFlag === -1 ? null : args[distFlag + 1];
assert(!(live && distDirectory), "choose either --live or --dist, not both");
if (distFlag !== -1) assert(distDirectory, "--dist requires a directory");

const pyproject = await read("pyproject.toml");
const pythonVersion = pyproject.match(/^version = "([^"]+)"/m)?.[1];
assert.equal(pythonVersion, release.version, "release.json must match pyproject.toml");
assert.equal(release.tag, `v${release.version}`, "release tag must match version");
assert(Number.isInteger(release.sourceDateEpoch), "sourceDateEpoch must be an integer");
assert(release.sourceDateEpoch >= 315532800, "sourceDateEpoch must be 1980-01-01 or later");

const releaseBase = `https://github.com/udhawan97/Codemble/releases`;
const assetBase = `${releaseBase}/download/${release.tag}`;
assert.equal(release.releaseUrl, `${releaseBase}/tag/${release.tag}`);
assert.equal(release.pypiFilesUrl, `https://pypi.org/project/codemble/${release.version}/#files`);
assert.equal(release.checksums.filename, "SHA256SUMS.txt");
assert.equal(release.checksums.url, `${assetBase}/${release.checksums.filename}`);

for (const artifact of [release.wheel, release.sdist]) {
  assert.match(artifact.sha256, /^[a-f0-9]{64}$/, `${artifact.filename} needs a SHA256 digest`);
  assert.equal(artifact.url, `${assetBase}/${artifact.filename}`);
}

for (const path of ["docs-site/package.json", "web/package.json", "web/package-lock.json"]) {
  const packageData = JSON.parse(await read(path));
  assert.equal(packageData.version, release.version, `${path} must match release.json`);
  if (packageData.packages?.[""]?.version) {
    assert.equal(packageData.packages[""].version, release.version, `${path} root package must match`);
  }
}

const readme = await read("README.md");
for (const match of readme.matchAll(/<img\b[^>]*\bsrc="([^"]+)"/g)) {
  assert.match(match[1], /^https:\/\//, `README image is not PyPI-safe: ${match[1]}`);
}
for (const match of readme.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
  assert.match(match[1], /^(?:https:\/\/|#|mailto:)/, `README link is not PyPI-safe: ${match[1]}`);
}

const atlasJourney = await read("docs-site/src/components/AtlasJourney.astro");
const systemJourney = atlasJourney.slice(
  atlasJourney.indexOf('id: "system"'),
  atlasJourney.indexOf('id: "impact"'),
);
assert.match(systemJourney, /image: "system\.png"/, "System journey must show the System capture");
assert.doesNotMatch(systemJourney, /study-panel\.png/, "System journey still points at Study");
const galaxyGuide = await read("docs-site/src/content/docs/the-galaxy.md");
assert.match(
  galaxyGuide,
  /system\.png" alt="[^"]*codemble\.cli[^"]*four named worlds[^"]*five parser-owned import routes/i,
  "System capture alt text must match the current codemble.cli four-world image",
);

const downloadGuide = await read("docs-site/src/content/docs/download.md");
const installationGuide = await read("docs-site/src/content/docs/installation.md");
const quickstartGuide = await read("docs-site/src/content/docs/quickstart.md");
const introductionGuide = await read("docs-site/src/content/docs/introduction.md");
const parserScaleGuide = await read("docs-site/src/content/docs/parser-scale.md");
const landing = await read("docs-site/src/pages/index.astro");
const sharedFacts = [
  release.version,
  release.tag,
  release.releaseUrl,
  release.pypiFilesUrl,
  release.checksums.url,
  release.wheel.filename,
  release.wheel.url,
  release.sdist.filename,
  release.sdist.url,
];
for (const [surface, text, values] of [
  ["README", readme, sharedFacts],
  ["download guide", downloadGuide, [...sharedFacts, release.wheel.sha256, release.sdist.sha256]],
  ["installation guide", installationGuide, [release.version]],
  ["quickstart guide", quickstartGuide, [release.version]],
]) {
  for (const value of values) {
    assert(text.includes(value), `${surface} is missing release fact: ${value}`);
  }
}

const pinnedRunCommand = `uvx --from codemble==${release.version} codemble`;
const pinnedNoOpenCommand = `${pinnedRunCommand} --no-open`;
for (const [surface, text] of [
  ["README", readme],
  ["download guide", downloadGuide],
  ["installation guide", installationGuide],
  ["quickstart guide", quickstartGuide],
]) {
  assert(text.includes(pinnedRunCommand), `${surface} is missing the pinned run command`);
  for (const pin of text.matchAll(/codemble==([0-9]+(?:\.[0-9]+){2}(?:[A-Za-z0-9.-]+)?)/g)) {
    assert.equal(
      pin[1],
      release.version,
      `${surface} contains a stale Codemble version pin: ${pin[0]}`,
    );
  }
}
for (const [surface, text] of [
  ["README", readme],
  ["installation guide", installationGuide],
  ["quickstart guide", quickstartGuide],
  ["introduction guide", introductionGuide],
]) {
  for (const version of text.matchAll(/(?:\bv|codemble==)(0\.\d+\.\d+)\b/g)) {
    assert.equal(
      version[1],
      release.version,
      `${surface} contains a stale current-version label: ${version[0]}`,
    );
  }
}
assert(
  parserScaleGuide.includes(`The current v${release.version} source receipt`),
  "parser-scale guide is missing the current source-receipt version",
);
assert(
  landing.includes("v{VERSION}") && !/v0\.\d+\.\d+/.test(landing),
  "landing current-version labels must derive from release.json",
);
assert(
  atlasJourney.includes("v{VERSION}") && !/v0\.\d+\.\d+/.test(atlasJourney),
  "Atlas journey current-version labels must derive from release.json",
);
assert(
  installationGuide.includes(`git clone --branch ${release.tag} --depth 1`),
  "installation source-build command is not pinned to the current release tag",
);
assert(
  installationGuide.includes(`Run \`codemble --version\` to confirm ${release.tag}`),
  "installation confirmation does not name the current release tag",
);
const browserRecovery = installationGuide.slice(
  installationGuide.indexOf("## If the browser does not open"),
  installationGuide.indexOf("## Build an editable checkout"),
);
assert(browserRecovery.includes(pinnedNoOpenCommand), "browser recovery needs the pinned no-open command");
assert.match(browserRecovery, /active server already prints an `Open http:\/\/127\.0\.0\.1:PORT`/);
assert.match(browserRecovery, /Leave that process running and open its printed URL/);
assert.match(browserRecovery, /future launch, after stopping the current server with `Ctrl-C`/);
assert(
  browserRecovery.indexOf("Leave that process running") < browserRecovery.indexOf(pinnedNoOpenCommand),
  "browser recovery must use the active URL before offering no-open for a future launch",
);

const artifacts = [release.wheel, release.sdist];
const expectedLedger = `${artifacts
  .map((artifact) => `${artifact.sha256}  ${artifact.filename}`)
  .join("\n")}\n`;

async function digestFile(path) {
  const bytes = await readFile(path);
  return createHash("sha256").update(bytes).digest("hex");
}

if (distDirectory) {
  for (const artifact of artifacts) {
    const path = resolve(repositoryRoot, distDirectory, artifact.filename);
    assert.equal(await digestFile(path), artifact.sha256, `${artifact.filename} build drifted`);
  }
  const sdistPath = resolve(repositoryRoot, distDirectory, release.sdist.filename);
  const archiveEntries = execFileSync("tar", ["-tzf", sdistPath], {
    encoding: "utf8",
  }).trim().split("\n");
  const forbiddenArchiveEntry = archiveEntries.find((entry) =>
    /(?:^|\/)(?:\.git(?:\/|$)|\.git-backup-remote$|\.last-git-backup-ts$|\.playwright-cli(?:\/|$)|\.env(?:\.(?!example$)[^/]+)?$|\.DS_Store$|tests\/fixtures\/sampleproj\/(?:generated(?:\/|$)|ignored\.py$))/.test(entry),
  );
  assert.equal(
    forbiddenArchiveEntry,
    undefined,
    `source archive contains developer, ignored fixture, or sensitive state: ${forbiddenArchiveEntry}`,
  );
  process.stdout.write(`release artifact build passed (${release.tag}; local dist)\n`);
  process.exit(0);
}

if (!live) {
  process.stdout.write(`release facts passed (${release.tag}; structural)\n`);
  process.exit(0);
}

async function fetchJson(url) {
  const response = await fetch(url, { redirect: "error" });
  assert(response.ok, `${url} returned HTTP ${response.status}`);
  return response.json();
}

const [pypi, github] = await Promise.all([
  fetchJson("https://pypi.org/pypi/codemble/json"),
  fetchJson("https://api.github.com/repos/udhawan97/Codemble/releases/latest"),
]);
assert.equal(pypi.info.version, release.version, "PyPI latest release drifted from public docs");
assert.equal(github.tag_name, release.tag, "GitHub latest release drifted from public docs");
assert.equal(github.html_url, release.releaseUrl, "GitHub release URL drifted from public docs");
const githubAssets = new Map(github.assets.map((asset) => [asset.name, asset]));
assert.deepEqual(
  [...githubAssets.keys()].sort(),
  [...artifacts.map((artifact) => artifact.filename), release.checksums.filename].sort(),
  "GitHub release assets drifted from the public artifact ledger",
);

for (const artifact of artifacts) {
  const published = pypi.urls.find((item) => item.filename === artifact.filename);
  assert(published, `${artifact.filename} is absent from PyPI metadata`);
  assert.equal(published.digests.sha256, artifact.sha256, `${artifact.filename} digest drifted`);
  const githubAsset = githubAssets.get(artifact.filename);
  assert.equal(githubAsset.browser_download_url, artifact.url, `${artifact.filename} URL drifted`);
  const response = await fetch(artifact.url);
  assert(response.ok, `${artifact.filename} returned HTTP ${response.status}`);
  const digest = createHash("sha256").update(Buffer.from(await response.arrayBuffer())).digest("hex");
  assert.equal(digest, artifact.sha256, `${artifact.filename} bytes failed SHA256 verification`);
}

const checksumAsset = githubAssets.get(release.checksums.filename);
assert.equal(checksumAsset.browser_download_url, release.checksums.url, "checksum URL drifted");
const checksumResponse = await fetch(release.checksums.url);
assert(checksumResponse.ok, `${basename(release.checksums.url)} returned HTTP ${checksumResponse.status}`);
assert.equal(await checksumResponse.text(), expectedLedger, "published checksum ledger drifted");

process.stdout.write(`release facts passed (${release.tag}; PyPI + GitHub assets + checksum bytes)\n`);
