---
title: Installation
description: Run Codemble v0.15.0 and configure optional narration.
---

:::note[One current version]
The packaged app, current source, screenshots, and these instructions all match
**v0.15.0**. [Download the wheel or source archive](/Codemble/download/) when
you do not want the one-command route.
:::

## Requirements

- **Python 3.11+**
- A modern browser. WebGL draws the 3D galaxy; the plain-SVG Map still works
  without it
- **[uv](https://docs.astral.sh/uv/)** for the recommended no-install run, or
  `pipx` for a permanent command

An Anthropic or OpenAI key is optional and enables only explanation prose. A
local Ollama can narrate instead, with nothing leaving your machine.

## Run Codemble

<ol class="cm-steps">
  <li>
    <img class="cm-step-icon" src="/Codemble/brand/icons/install.svg" alt="" width="24" height="24">
    <div class="cm-step-body">
      <p class="cm-step-title">Install uv</p>
      <p class="cm-step-note">Once per machine.</p>
      <pre class="cm-step-cmd"><code>brew install uv</code></pre>
    </div>
  </li>
  <li>
    <img class="cm-step-icon" src="/Codemble/brand/icons/run.svg" alt="" width="24" height="24">
    <div class="cm-step-body">
      <p class="cm-step-title">Open Codemble</p>
      <p class="cm-step-note">Pick a project in the browser. Nothing is added to your system Python.</p>
      <pre class="cm-step-cmd"><code>uvx --from codemble==0.15.0 codemble</code></pre>
    </div>
  </li>
</ol>

Use uv's [official installation guide](https://docs.astral.sh/uv/getting-started/installation/)
if you do not use Homebrew. Prefer a permanent install? Run `pipx install
codemble==0.15.0`, then `codemble`. Plain `pip install codemble==0.15.0` also works inside a
virtual environment.

The shorter `uvx codemble` intentionally follows the newest PyPI release. The
version-pinned command above stays aligned with this guide and its screenshots.

Codemble opens an in-app picker. To skip it, pass a folder:

```bash
uvx --from codemble==0.15.0 codemble ./your-project
```

The package contains the production web app, so Node.js is not required.

## Build an editable checkout

```bash
git clone --branch v0.15.0 --depth 1 https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
codemble
```

Run `codemble --version` to confirm v0.15.0. Contributors should follow the
[full source build and verification guide](/Codemble/build-from-source/).

## Bring your own key—or do not

The galaxy, Map, structural summary, Impact, source viewer, language Lens,
checks, lighting, and progress are model-free. To add optional cloud narration,
set one of:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or
export OPENAI_API_KEY=sk-...
```

You can also create `~/.codemble/config`:

```toml
provider = "anthropic"   # or "openai"
api_key  = "sk-..."
model    = "claude-sonnet-5"   # optional
```

Your project is parsed locally. If you configure a narrator, opening Study
automatically sends a bounded excerpt to that provider; there is no separate
“send” button. Without a configured narrator, Study stays entirely local.

## Keep narration local with Ollama

```bash
ollama pull gemma4:12b
export CODEMBLE_PROVIDER=ollama
export CODEMBLE_OLLAMA_MODEL=gemma4:12b
```

Codemble never auto-selects Ollama, and a configured Ollama host must use plain
HTTP on loopback. Local output passes the same grounding validation as cloud
output.

:::caution[What grounding can and cannot prove]
Validation catches an invented identifier. It cannot catch every wrong claim
about a real identifier, and smaller local models make that second kind of error
more often. The structural summary, source, Impact, Lens, and checks are
parser-owned.
:::

## Limits that fail honestly

- Above roughly 1,000 supported source files, choose a subdirectory in the
  picker or pass `--path ./project/src`.
- When several entrypoints genuinely tie, choose Home in the app or pass a
  parser-ranked `--entrypoint NODE_ID`.
- A syntax-error file stays visible as **Unchartable**; Codemble does not invent
  inner structure or narration for it.
- Codemble parses supported source. It does not run source files, package
  scripts, compilers, or bundlers.

Supported extensions are `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`,
`.mts`, `.cts`, `.go`, `.java`, `.rs`, and `.cs`.
