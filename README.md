<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs-site/src/assets/codemble-mark-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs-site/src/assets/codemble-mark-light.svg">
    <img src="docs-site/src/assets/codemble-mark-light.svg" alt="Codemble mark — a lit node on its orbit" width="180">
  </picture>
</p>

<h1 align="center">Codemble</h1>

<p align="center"><em>Your code is a galaxy. Light it up.</em></p>

<p align="center">
  You built it with AI — Claude Code, Codex — and it works.<br>
  But do you <em>understand</em> it? Codemble turns your own project into a
  3D galaxy<br> you illuminate by proving, region by region, that you actually get it.
</p>

<p align="center"><strong>Local-first · Your key, your machine · Zero invented facts</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/status-phase_0_·_building_in_public-facc15?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/runs-100%25_locally-2ea44f?style=flat-square" alt="Local-first">
  <img src="https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square" alt="Apache 2.0">
</p>

<p align="center">
  <kbd><a href="#what-it-does">🌌 What it does</a></kbd> ·
  <kbd><a href="#the-game">🎮 The game</a></kbd> ·
  <kbd><a href="#setup">🚀 Setup</a></kbd> ·
  <kbd><a href="#honesty-is-the-product">🔍 Honesty</a></kbd> ·
  <kbd><a href="#whats-brewing">🗺️ Roadmap</a></kbd> ·
  <kbd><a href="#for-developers">🛠️ Developers</a></kbd>
</p>

---

> [!NOTE]
> **Codemble is in Phase 0 — the first end-to-end slice is being built in public.**
> Star the repo to follow along; the [roadmap](https://udhawan97.github.io/Codemble/roadmap/)
> moves only when milestones actually land.

## What it does

The AI wrote it. That doesn't mean you own it. Codemble parses your project
into a real structural map — no hallucinated architecture — and renders it as a
galaxy you can actually learn from.

| You see | It means |
| --- | --- |
| ⭐ A star system | A module or package in your project |
| 🪐 A planet in orbit | A function or class |
| 🏠 The Home system | Your entrypoint — where execution starts |
| ✨ Routes & edges | Real imports and calls (uncertain ones say so) |
| 💡 Brightness & size | How central it is, how big it is |
| 🌑 → 🌟 Dim → lit | Not yet understood → understood, *proven* |

Zoom is semantic, not free-flight: **galaxy** for orientation, **system** for
structure, **study** for learning — where you get the real source, a grounded
explanation, and the language idiom it demonstrates, every claim linked to a
real `file:line`.

## The game

| Do this | Get this |
| --- | --- |
| 🔭 Explore a region of your code | Explanations grounded in your actual source |
| 🧠 Pass its checks — answers come from the code's real graph, never the model | The region lights up. **Permanently.** |
| 📖 Meet idioms your code uses (decorators, async, comprehensions…) | Your **star chart** of language concepts grows |
| 🌌 Light the whole galaxy | You can debug, extend, and explain your own project |

No XP. No streaks. One score that matters: how much of your sky is lit.

## Setup

> [!WARNING]
> Pre-release: install from source until the first tagged release.

<details>
<summary><strong>Run from source</strong></summary>

```bash
git clone https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

codemble ./your-ai-built-project
```

</details>

<details>
<summary><strong>Bring your own key (Claude or OpenAI)</strong></summary>

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY=sk-...
```

Or put it in `~/.codemble/config`. Your code is parsed locally; the only
network calls are the LLM requests you configure, sent straight to your
provider. No key? The galaxy, structure, and checks still work — only the
prose explanations need the model.

</details>

Full guide: **[udhawan97.github.io/Codemble](https://udhawan97.github.io/Codemble/)**

## Honesty is the product

Codemble's users often *can't tell* when a tool is wrong — that's exactly why
they need it. So the [correctness contract](https://udhawan97.github.io/Codemble/correctness/)
outranks every feature: structure comes only from parsers, check answers only
from the graph, every explanation links to the line it explains, and uncertain
edges are labeled uncertain. A wrong explanation is our highest-severity bug —
[file it](https://github.com/udhawan97/Codemble/issues) without mercy.

## What's brewing

**NOW** — Phase 0: the complete v1 loop for Python (parser → galaxy → grounded
explanations → language lens → checks → illumination).
**NEXT** — TypeScript/JavaScript adapter, language switching for polyglot
projects, more languages.
**LATER** — shareable read-only galaxy links, new quest types, the loud launch.

Details: [roadmap](https://udhawan97.github.io/Codemble/roadmap/) · progress
lives in [CLAUDE.md](CLAUDE.md) and moves only when milestones land.

## For developers

```bash
pip install -e ".[dev]"
pytest && ruff check .        # CI gates
cd docs-site && npm install && npm run dev   # docs at localhost:4321
```

Architecture (the three load-bearing decisions), contribution rules, and the
agent operating guide: [docs](https://udhawan97.github.io/Codemble/architecture/) ·
[CONTRIBUTING.md](CONTRIBUTING.md) · [CLAUDE.md](CLAUDE.md).

## Privacy

Local-first, no accounts, no telemetry, no hosted code. The only network
traffic is the LLM calls you configure with your own key.

## Contributing

Issues, PRs, and screenshots of your galaxy are all welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Especially valuable early: run Codemble on
your own AI-built project and report anything it explains wrong.

## License

Released under the [Apache License 2.0](LICENSE).

---

<p align="center"><sub>
  If Codemble helped you finally understand your own code, consider leaving a ⭐ —
  it lights up <em>our</em> galaxy.
</sub></p>
