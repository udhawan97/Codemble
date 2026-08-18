---
title: Download
description: Run Codemble, download its verified release artifacts, or build v0.19.0 from source.
---

The one-command route, direct downloads, current source, and screenshots all
match **Codemble v0.19.0**.

<div class="cm-version-ledger" role="list" aria-label="Codemble download routes">
  <section class="cm-version-route cm-version-route--recommended" role="listitem">
    <div class="cm-version-route__title">
      <img src="/Codemble/brand/icons/run.svg" alt="" width="30" height="30">
      <div><p>Recommended</p><h2>Run without installing</h2></div>
    </div>
    <p>uv fetches the published v0.19.0 wheel in an isolated environment, opens Codemble, and leaves your system Python alone.</p>
    <pre><code>uvx --from codemble==0.19.0 codemble</code></pre>
    <p class="cm-version-route__note">Pass a folder to skip the picker: <code>uvx --from codemble==0.19.0 codemble ./your-project</code>. Use <code>uvx codemble</code> when you intentionally want the newest PyPI release.</p>
  </section>
  <section class="cm-version-route" role="listitem" id="direct-artifacts">
    <div class="cm-version-route__title">
      <img src="/Codemble/brand/icons/package.svg" alt="" width="30" height="30">
      <div><p>Direct</p><h2>Download v0.19.0</h2></div>
    </div>
    <p>GitHub mirrors the exact wheel and source archive published to PyPI, beside one plain-text SHA256 ledger.</p>
    <div class="cm-artifact-links">
      <a class="cm-artifact-primary" href="https://github.com/udhawan97/Codemble/releases/download/v0.19.0/codemble-0.19.0-py3-none-any.whl"><img src="/Codemble/brand/icons/download-on-fill.svg" alt="" width="20" height="20">Download wheel</a>
      <a href="https://github.com/udhawan97/Codemble/releases/download/v0.19.0/codemble-0.19.0.tar.gz"><img src="/Codemble/brand/icons/code.svg" alt="" width="20" height="20">Source archive</a>
      <a href="https://github.com/udhawan97/Codemble/releases/download/v0.19.0/SHA256SUMS.txt"><img src="/Codemble/brand/icons/shield.svg" alt="" width="20" height="20">SHA256SUMS</a>
      <a href="https://pypi.org/project/codemble/0.19.0/#files">PyPI files</a>
      <a href="https://github.com/udhawan97/Codemble/releases/tag/v0.19.0"><img src="/Codemble/brand/icons/release.svg" alt="" width="20" height="20">Release notes</a>
    </div>
  </section>
</div>

## Which route should I choose?

<dl class="cm-choice-list">
  <div>
    <dt>Try this exact release</dt>
    <dd><code>uvx --from codemble==0.19.0 codemble</code><span>One isolated command, pinned to the screens on this site.</span></dd>
  </div>
  <div>
    <dt>Keep the command</dt>
    <dd><code>pipx install codemble==0.19.0</code><span>An isolated app environment with <code>codemble</code> on your path.</span></dd>
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
96b712a93f18778165c2327456c98a93b1b22490082a261040c516472d388982  codemble-0.19.0-py3-none-any.whl
dcbe7d3c34f4d667786292d9f61973828d5265e3120a59a3600bec237ecaab2d  codemble-0.19.0.tar.gz
```

To check the wheel on macOS or Linux:

```bash
printf '%s  %s\n' \
  96b712a93f18778165c2327456c98a93b1b22490082a261040c516472d388982 \
  codemble-0.19.0-py3-none-any.whl | shasum -a 256 -c -
```

Then install it into an isolated app environment:

```bash
pipx install ./codemble-0.19.0-py3-none-any.whl
codemble --version
```

The expected version is `0.19.0`.

## Build from source

```bash
git clone --branch v0.19.0 --depth 1 https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
codemble
```

This checks out and runs the same v0.19.0 app with an editable Python environment. Continue
with [Installation](/Codemble/installation/) for provider setup and failure
boundaries, or [Build from source](/Codemble/build-from-source/) for the full
contributor gates.
