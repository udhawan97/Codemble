---
title: Installation
description: Requirements and setup, including bring-your-own-key configuration.
---

:::note[v0.1.0 tester release]
The complete Python loop is ready for early testing. Human first-run acceptance
is still being collected before the roadmap advances to more languages.
:::

## Requirements

- **Python 3.11+**
- A modern browser with WebGL (the galaxy is rendered locally in your browser)
- `pipx` for a persistent install, or `uv` for an isolated one-off run

An Anthropic or OpenAI key is optional and enables only explanation prose.

## Install from the v0.1.0 tag

```bash
pipx install git+https://github.com/udhawan97/Codemble.git@v0.1.0
codemble ./your-python-project
```

Or run without keeping an installation:

```bash
uvx --from git+https://github.com/udhawan97/Codemble.git@v0.1.0 \
  codemble ./your-python-project
```

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

- More than 300 Python files: run `codemble --path ./project/subdirectory`.
- Ambiguous startup: choose Home in the app or pass a parser-ranked node with
  `--entrypoint module.qualname`.
- Syntax error: the file remains visible as **Unchartable**, with raw source;
  no inner structure or model narration is invented.
