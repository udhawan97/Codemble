---
title: Installation
description: Requirements and setup, including bring-your-own-key configuration.
---

:::caution[Pre-release]
Codemble is under active construction. Until the first release, install from
source — see [Build from source](/Codemble/build-from-source/).
:::

## Requirements

- **Python 3.11+**
- A modern browser with WebGL (the galaxy is rendered locally in your browser)
- An **Anthropic (Claude)** or **OpenAI** API key

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
