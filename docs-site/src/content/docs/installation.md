---
title: Installation
description: Requirements and setup, including bring-your-own-key configuration.
---

:::note[v0.2.0 polyglot tester release]
The complete learning loop supports Python, JavaScript, TypeScript, and mixed
projects. Human first-run evidence is still being collected separately.
:::

## Requirements

- **Python 3.11+**
- A modern browser with WebGL (the galaxy is rendered locally in your browser)
- `pipx` for a persistent install, or `uv` for an isolated one-off run

An Anthropic or OpenAI key is optional and enables only explanation prose.

## Install and run

```bash
uvx codemble            # or: pipx install codemble && codemble
```

Codemble opens your browser to an in-app picker — browse your home folders or
reopen a recent project, no path typing required. To skip the picker, pass a
path directly: `codemble ./your-project`.

> Until the first PyPI release (v0.3.0) lands, install from the tag instead:
>
> ```bash
> pipx install git+https://github.com/udhawan97/Codemble.git@v0.2.0
> codemble
> ```

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
  `codemble --path ./project/subdirectory`, or pick that folder in the picker —
  it prompts for the same busiest-first subdirectory choice in the UI.
- Ambiguous startup: choose Home in the app or pass a parser-ranked node with
  `--entrypoint NODE_ID`.
- Syntax error: the file remains visible as **Unchartable**, with raw source;
  no inner structure or model narration is invented.

Supported source extensions are `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`,
`.tsx`, `.mts`, and `.cts`. Codemble parses them; it does not run source files,
package scripts, compilers, or bundlers.
