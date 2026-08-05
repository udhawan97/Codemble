---
title: Download
description: Run Codemble, download the exact PyPI artifacts, or build v0.16.0 from source.
---

The one-command route, direct downloads, current source, and screenshots all
match **Codemble v0.16.0**.

<div class="cm-version-ledger" role="list" aria-label="Codemble download routes">
  <section class="cm-version-route cm-version-route--recommended" role="listitem">
    <div class="cm-version-route__title">
      <img src="/Codemble/brand/icons/run.svg" alt="" width="30" height="30">
      <div><p>Recommended</p><h2>Run without installing</h2></div>
    </div>
    <p>uv fetches the published v0.16.0 wheel in an isolated environment, opens Codemble, and leaves your system Python alone.</p>
    <pre><code>uvx --from codemble==0.16.0 codemble</code></pre>
    <p class="cm-version-route__note">Pass a folder to skip the picker: <code>uvx --from codemble==0.16.0 codemble ./your-project</code>. Use <code>uvx codemble</code> when you intentionally want the newest PyPI release.</p>
  </section>
  <section class="cm-version-route" role="listitem" id="direct-artifacts">
    <div class="cm-version-route__title">
      <img src="/Codemble/brand/icons/package.svg" alt="" width="30" height="30">
      <div><p>Direct</p><h2>Download v0.16.0</h2></div>
    </div>
    <p>PyPI hosts the exact wheel and source archive installed by package tools, with a published SHA256 digest for each file.</p>
    <div class="cm-artifact-links">
      <a class="cm-artifact-primary" href="https://files.pythonhosted.org/packages/de/da/4d075717ef02d371bf5598c8845446a4e16479c15150c6acbd7089152137/codemble-0.16.0-py3-none-any.whl"><img src="/Codemble/brand/icons/download-on-fill.svg" alt="" width="20" height="20">Download wheel</a>
      <a href="https://files.pythonhosted.org/packages/8f/7b/efde0d4188a4bfa2f59a87b704eb651077384791a156a629cf4c7e7fba8c/codemble-0.16.0.tar.gz"><img src="/Codemble/brand/icons/code.svg" alt="" width="20" height="20">Source archive</a>
      <a href="https://pypi.org/project/codemble/0.16.0/#files"><img src="/Codemble/brand/icons/shield.svg" alt="" width="20" height="20">SHA256 digests</a>
      <a href="https://github.com/udhawan97/Codemble/releases/tag/v0.16.0"><img src="/Codemble/brand/icons/release.svg" alt="" width="20" height="20">Release notes</a>
    </div>
  </section>
</div>

## Which route should I choose?

<dl class="cm-choice-list">
  <div>
    <dt>Try this exact release</dt>
    <dd><code>uvx --from codemble==0.16.0 codemble</code><span>One isolated command, pinned to the screens on this site.</span></dd>
  </div>
  <div>
    <dt>Keep the command</dt>
    <dd><code>pipx install codemble==0.16.0</code><span>An isolated app environment with <code>codemble</code> on your path.</span></dd>
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

The PyPI-published SHA256 digests are:

```text
6df07d373db223a0ca0ffa134c6f3777ad7dabbb6ff1d5d71d9277152cbc9dd9  codemble-0.16.0-py3-none-any.whl
2802dc23ab962c874bb61632ee33b766a880db1dafede1b163e0ff379b5ef987  codemble-0.16.0.tar.gz
```

To check the wheel on macOS or Linux:

```bash
printf '%s  %s\n' \
  6df07d373db223a0ca0ffa134c6f3777ad7dabbb6ff1d5d71d9277152cbc9dd9 \
  codemble-0.16.0-py3-none-any.whl | shasum -a 256 -c -
```

Then install it into an isolated app environment:

```bash
pipx install ./codemble-0.16.0-py3-none-any.whl
codemble --version
```

The expected version is `0.16.0`.

## Build from source

```bash
git clone --branch v0.16.0 --depth 1 https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
codemble
```

This checks out and runs the same v0.16.0 app with an editable Python environment. Continue
with [Installation](/Codemble/installation/) for provider setup and failure
boundaries, or [Build from source](/Codemble/build-from-source/) for the full
contributor gates.
