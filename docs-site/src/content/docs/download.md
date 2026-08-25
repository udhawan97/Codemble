---
title: Download
description: Run Codemble, download its verified release artifacts, or build v0.21.1 from source.
---

The one-command route, direct downloads, current source, and screenshots all
match **Codemble v0.21.1**.

<div class="cm-version-ledger" role="list" aria-label="Codemble download routes">
  <section class="cm-version-route cm-version-route--recommended" role="listitem">
    <div class="cm-version-route__title">
      <img src="/Codemble/brand/icons/run.svg" alt="" width="30" height="30">
      <div><p>Recommended</p><h2>Run without installing</h2></div>
    </div>
    <p>uv fetches the published v0.21.1 wheel in an isolated environment, opens Codemble, and leaves your system Python alone.</p>
    <pre><code>uvx --from codemble==0.21.1 codemble</code></pre>
    <p class="cm-version-route__note">Pass a folder to skip the picker: <code>uvx --from codemble==0.21.1 codemble ./your-project</code>. Use <code>uvx codemble</code> when you intentionally want the newest PyPI release.</p>
  </section>
  <section class="cm-version-route" role="listitem" id="direct-artifacts">
    <div class="cm-version-route__title">
      <img src="/Codemble/brand/icons/package.svg" alt="" width="30" height="30">
      <div><p>Direct</p><h2>Download v0.21.1</h2></div>
    </div>
    <p>GitHub mirrors the exact wheel and source archive published to PyPI, beside one plain-text SHA256 ledger.</p>
    <div class="cm-artifact-links">
      <a class="cm-artifact-primary" href="https://github.com/udhawan97/Codemble/releases/download/v0.21.1/codemble-0.21.1-py3-none-any.whl"><img src="/Codemble/brand/icons/download-on-fill.svg" alt="" width="20" height="20">Download wheel</a>
      <a href="https://github.com/udhawan97/Codemble/releases/download/v0.21.1/codemble-0.21.1.tar.gz"><img src="/Codemble/brand/icons/code.svg" alt="" width="20" height="20">Source archive</a>
      <a href="https://github.com/udhawan97/Codemble/releases/download/v0.21.1/SHA256SUMS.txt"><img src="/Codemble/brand/icons/shield.svg" alt="" width="20" height="20">SHA256SUMS</a>
      <a href="https://pypi.org/project/codemble/0.21.1/#files">PyPI files</a>
      <a href="https://github.com/udhawan97/Codemble/releases/tag/v0.21.1"><img src="/Codemble/brand/icons/release.svg" alt="" width="20" height="20">Release notes</a>
    </div>
  </section>
</div>

## Which route should I choose?

<dl class="cm-choice-list">
  <div>
    <dt>Try this exact release</dt>
    <dd><code>uvx --from codemble==0.21.1 codemble</code><span>One isolated command, pinned to the screens on this site.</span></dd>
  </div>
  <div>
    <dt>Keep the command</dt>
    <dd><code>pipx install codemble==0.21.1</code><span>An isolated app environment with <code>codemble</code> on your path.</span></dd>
  </div>
  <div>
    <dt>Install from a local file</dt>
    <dd><strong>Wheel download</strong><span>The Codemble package and production web app travel together; first-time installation still needs its Python dependencies online or already cached. Node.js is not needed.</span></dd>
  </div>
  <div>
    <dt>Contribute</dt>
    <dd><strong>Source checkout</strong><span>An editable install plus the repository verification gates.</span></dd>
  </div>
</dl>

## Verify a downloaded artifact

The same SHA256 digests are published in `SHA256SUMS.txt`, the GitHub asset
ledger, and PyPI metadata:

```text
ba515552a14a7a24eaa7846b19ed3278b06e16eada16f1961cf9c7e42eb90212  codemble-0.21.1-py3-none-any.whl
588c910f180418e12e93f2999f8803af1714069084ee001d16494629cf2613c0  codemble-0.21.1.tar.gz
```

To check the wheel on macOS or Linux:

```bash
printf '%s  %s\n' \
  ba515552a14a7a24eaa7846b19ed3278b06e16eada16f1961cf9c7e42eb90212 \
  codemble-0.21.1-py3-none-any.whl | shasum -a 256 -c -
```

Then install it into an isolated app environment:

```bash
pipx install ./codemble-0.21.1-py3-none-any.whl
codemble --version
```

The expected version is `0.21.1`.

## Build from source

```bash
git clone --branch v0.21.1 --depth 1 https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
codemble
```

This checks out and runs the same v0.21.1 app with an editable Python environment. Continue
with [Installation](/Codemble/installation/) for provider setup and failure
boundaries, or [Build from source](/Codemble/build-from-source/) for the full
contributor gates.
