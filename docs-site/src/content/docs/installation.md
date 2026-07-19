---
title: Installation
description: Requirements and setup, including bring-your-own-key configuration.
---

:::note[Polyglot tester release]
The complete learning loop supports Python, JavaScript, TypeScript, and mixed
projects. Human first-run evidence is still being collected separately.
:::

## Requirements

- **Python 3.11+**
- A modern browser with WebGL (the galaxy is rendered locally in your browser)
- **[uv](https://docs.astral.sh/uv/)** — install it first; it fetches and runs
  Codemble without touching your system Python

An Anthropic or OpenAI key is optional and enables only explanation prose.

## Install and run

<ol class="cm-steps">
  <li>
    <svg class="cm-step-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5v9.5"/><path d="M8.25 9.5 12 13.25 15.75 9.5"/><path d="M4.5 15.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/></svg>
    <div class="cm-step-body">
      <p class="cm-step-title">Install uv</p>
      <p class="cm-step-note">Once per machine.</p>
      <pre class="cm-step-cmd"><code>brew install uv</code></pre>
    </div>
  </li>
  <li>
    <svg class="cm-step-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 17.25 11 8.25l7.5 2.75"/><circle cx="5" cy="17.25" r="1.6"/><circle cx="11" cy="8.25" r="1.6"/><circle cx="18.5" cy="11" r="1.6"/></svg>
    <div class="cm-step-body">
      <p class="cm-step-title">Chart your project</p>
      <p class="cm-step-note">Every time you want the atlas. Nothing is left behind.</p>
      <pre class="cm-step-cmd"><code>uvx codemble</code></pre>
    </div>
  </li>
</ol>

### Installing uv without Homebrew

```bash
# macOS · Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Prefer a permanent install? `pipx install codemble` (then run `codemble`) and
plain `pip install codemble` both work and need no uv.

Codemble opens your browser to an in-app picker — browse your
home folders or reopen a recent project, no path typing required. To skip the
picker, pass a path directly: `codemble ./your-project`.

The Python wheel already contains the production web app. Node is needed only
when developing Codemble itself.

## Bring your own key

Codemble never ships or proxies a key. Set one of:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or
export OPENAI_API_KEY=sk-...
```

or create `~/.codemble/config`:

```toml
provider = "anthropic"   # or "openai"
api_key  = "sk-..."
model    = "claude-sonnet-5"   # optional; provider default shown
```

Your code is parsed **locally**. The only network calls are the LLM requests
you configured, sent directly from your machine to your provider.

## No key? Still useful

Without a key you still get the full galaxy, source, parser relationships,
language lens, and checks — only the prose explanations need the model.

## Limits that fail honestly

- More than 300 supported source files: run
  `codemble --path ./project/subdirectory`; the picker prompts for the same
  busiest-first subdirectory choice in the UI.
- Ambiguous startup: choose Home in the app or pass a parser-ranked node with
  `--entrypoint NODE_ID`.
- Syntax error: the file remains visible as **Unchartable**, with raw source;
  no inner structure or model narration is invented.

Supported source extensions are `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`,
`.tsx`, `.mts`, and `.cts`. Codemble parses them; it does not run source files,
package scripts, compilers, or bundlers.
