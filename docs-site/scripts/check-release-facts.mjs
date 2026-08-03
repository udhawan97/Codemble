import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(docsRoot, "..");
const read = (path) => readFile(resolve(repositoryRoot, path), "utf8");
const release = JSON.parse(await read("docs-site/release.json"));

const pyproject = await read("pyproject.toml");
const pythonVersion = pyproject.match(/^version = "([^"]+)"/m)?.[1];
assert.equal(pythonVersion, release.version, "release.json must match pyproject.toml");

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

const downloadGuide = await read("docs-site/src/content/docs/download.md");
const sharedFacts = [
  release.version,
  release.tag,
  release.releaseUrl,
  release.pypiFilesUrl,
  release.wheel.filename,
  release.wheel.url,
  release.sdist.filename,
  release.sdist.url,
];
for (const [surface, text, values] of [
  ["README", readme, sharedFacts],
  ["download guide", downloadGuide, [...sharedFacts, release.wheel.sha256, release.sdist.sha256]],
]) {
  for (const value of values) {
    assert(text.includes(value), `${surface} is missing release fact: ${value}`);
  }
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
assert.equal(github.assets.length, 0, "GitHub now hosts release assets; distribution copy must be updated");

for (const artifact of [release.wheel, release.sdist]) {
  const published = pypi.urls.find((item) => item.filename === artifact.filename);
  assert(published, `${artifact.filename} is absent from PyPI metadata`);
  assert.equal(published.url, artifact.url, `${artifact.filename} URL drifted`);
  assert.equal(published.digests.sha256, artifact.sha256, `${artifact.filename} digest drifted`);
  const response = await fetch(artifact.url, { redirect: "error" });
  assert(response.ok, `${artifact.filename} returned HTTP ${response.status}`);
  const digest = createHash("sha256").update(Buffer.from(await response.arrayBuffer())).digest("hex");
  assert.equal(digest, artifact.sha256, `${artifact.filename} bytes failed SHA256 verification`);
}

process.stdout.write(`release facts passed (${release.tag}; PyPI + GitHub + artifact bytes)\n`);
