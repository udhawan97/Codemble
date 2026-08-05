<p align="center">
  <a href="https://udhawan97.github.io/Codemble/">
    <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/mark-animated.svg" alt="Codemble — an open lapis ensō whose amber star systems light up" width="144">
  </a>
</p>

<h1 align="center">Codemble</h1>

<p align="center"><strong>Explore the code AI left behind.</strong></p>

<p align="center">
  Codemble reads a project on your machine and turns its real structure into a
  galaxy you can explore or a diagram you can follow. Study any file, see what
  a change reaches, and light only what you prove you understand.
</p>

<p align="center">
  <a href="https://github.com/udhawan97/Codemble/releases/tag/v0.16.0"><img src="https://img.shields.io/badge/stable-v0.16.0-2b4d96?style=flat-square" alt="Stable release v0.16.0"></a>
  <a href="https://github.com/udhawan97/Codemble/actions/workflows/ci.yml"><img src="https://github.com/udhawan97/Codemble/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status"></a>
  <img src="https://img.shields.io/badge/Python-3.11+-2b4d96?style=flat-square" alt="Python 3.11 or newer">
  <img src="https://img.shields.io/badge/maps-7_languages-3f6ac0?style=flat-square" alt="Maps seven languages">
  <img src="https://img.shields.io/badge/license-Apache_2.0-070b1c?style=flat-square" alt="Apache 2.0 license">
</p>

<p align="center">
  <a href="#start-here">Start here</a> ·
  <a href="#see-the-learning-loop">See the loop</a> ·
  <a href="#what-codemble-can-prove">Trust boundary</a> ·
  <a href="https://udhawan97.github.io/Codemble/">Website</a> ·
  <a href="https://udhawan97.github.io/Codemble/introduction/">Docs</a>
</p>

<p align="center">
  <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/galaxy.png" alt="Codemble v0.16.0 showing 171 represented systems across seven languages, with ranked labels, selective import routes, 30 systems charted, six unreadable test fixtures called out, and Home still unlit." width="1000">
</p>

<p align="center"><sub>
  Codemble v0.16.0 · every module is represented before the first lesson ·
  labels declutter automatically and every parser-owned name is available on hover ·
  visiting charts a route; passing checks lights a system amber
</sub></p>

> [!IMPORTANT]
> **The screen above and the packaged app are both v0.16.0.** The PyPI release
> maps Python, JavaScript, TypeScript, Go, Java, Rust, C#, and mixed projects;
> it includes the explorer trail, parser-owned Impact, and automatic Home
> selection. The pinned command and direct downloads below resolve to the same
> verified release.

## Start here

### Run v0.16.0 — recommended

Install [uv](https://docs.astral.sh/uv/) once, then open Codemble whenever you
need it:

| | Step | Command |
| :---: | --- | --- |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/install.svg" width="22" height="22" alt=""> | **Install uv** — a clean Python app runner | `brew install uv` |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/run.svg" width="22" height="22" alt=""> | **Open this release** — pick a project in the browser | `uvx --from codemble==0.16.0 codemble` |

No Homebrew? Use uv's [official installer](https://docs.astral.sh/uv/getting-started/installation/),
or install permanently with `pipx install codemble==0.16.0` and run `codemble`.
Pass a folder to skip the project picker:
`uvx --from codemble==0.16.0 codemble ./my-project`.
Use the shorter `uvx codemble` when you intentionally want whatever release is
newest on PyPI.

<p align="center">
  <a href="https://pypi.org/project/codemble/0.16.0/#files">
    <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/download-codemble.svg" alt="Download Codemble — wheel, source archive, SHA256 digests, and release notes" width="760">
  </a>
</p>

<p align="center">
  <a href="https://files.pythonhosted.org/packages/de/da/4d075717ef02d371bf5598c8845446a4e16479c15150c6acbd7089152137/codemble-0.16.0-py3-none-any.whl"><img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/download.svg" alt="" width="18"> Wheel</a> ·
  <a href="https://files.pythonhosted.org/packages/8f/7b/efde0d4188a4bfa2f59a87b704eb651077384791a156a629cf4c7e7fba8c/codemble-0.16.0.tar.gz"><img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/package.svg" alt="" width="18"> Source archive</a> ·
  <a href="https://pypi.org/project/codemble/0.16.0/#files"><img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/shield.svg" alt="" width="18"> SHA256 digests</a> ·
  <a href="https://github.com/udhawan97/Codemble/releases/tag/v0.16.0"><img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/release.svg" alt="" width="18"> Release notes</a>
</p>

### Build the same v0.16.0 app from source

Use this route when you want an editable checkout:

```bash
git clone --branch v0.16.0 --depth 1 https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
codemble
```

Read the
[full build guide](https://udhawan97.github.io/Codemble/build-from-source/) for
the verification commands.

## What Codemble does

| | Plain-English answer |
| :---: | --- |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/compass.svg" width="24" height="24" alt=""> | **Explore first.** Every module is represented and coloured on the first frame. Labels rank and declutter; hover reveals every parser-owned name. Visiting leaves a local trail without claiming understanding. |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/map.svg" width="24" height="24" alt=""> | **See how it fits together.** Switch between a 3D galaxy, an import architecture map, and the call workflow from Home. |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/impact.svg" width="24" height="24" alt=""> | **Know what a change touches.** Impact traces what depends on a structure and what it depends on, with real file locations and certainty labels. |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/check.svg" width="24" height="24" alt=""> | **Prove what you understand.** Graph-derived checks—not a narrator—are the only way to light a system amber. |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/shield.svg" width="24" height="24" alt=""> | **Keep the project local.** Parsing, maps, source, Impact, checks, and progress stay on your machine. |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/languages.svg" width="24" height="24" alt=""> | **Read mixed projects.** Python, JavaScript, TypeScript, Go, Java, Rust, and C# share one graph and one honesty contract. |

Codemble reads supported source. It does **not** run your app, package scripts,
compilers, or tests.

## See the learning loop

| 01 · Explore | 02 · Map |
| --- | --- |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/galaxy.png" alt="Current Codemble galaxy with visible named modules and selective import routes." width="600"> | <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/map-architecture.png" alt="Current Codemble architecture map with Home, connected modules, and a counted shelf for modules without a proven import route." width="600"> |
| Fly to a module. Its routes remain charted. | Follow real imports from Home; unreachable modules are counted, not erased. |

| 03 · Inspect | 04 · Prove |
| --- | --- |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/study-impact.png" alt="Current Codemble Expert study panel showing parser-owned Impact lists over the architecture map." width="600"> | <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/home-proved.png" alt="Current Codemble Home system after its graph-derived checks were passed, with all four parser-proven structures glowing amber." width="600"> |
| See what a structure controls and what can break it—no model needed. | Pass checks drawn from the graph; only then does the system turn amber. |

### One graph, two useful views

| View | What it shows | When it helps |
| --- | --- | --- |
| **Galaxy** | Modules as systems and structures as worlds | Learn the shape of the whole project |
| **Map · Architecture** | Modules grouped by folder and layered by proven imports from Home | See how parts fit together |
| **Map · Workflow** | Certain calls from the selected entrypoint, depth by depth | See what runs first |
| **Study** | Real source, Impact, relationships, Lens notes, and optional narration | Understand one structure in context |

The Map is plain SVG, so it remains usable on a machine that cannot render the
WebGL galaxy. Easy mode uses plainer labels and lower density; Expert mode shows
more graph detail. Neither changes the underlying evidence or scoring.

## What Codemble can prove

Codemble is built for readers who may not yet spot a confident mistake, so its
limits are part of the interface:

- Nodes, routes, language concepts, and Home candidates come from parsers.
- Unproven relationships are labelled **possible** and drawn differently on
  both the galaxy and the map.
- Impact and check answers come from the graph and need no API key.
- Unsupported or broken source is counted and named instead of silently hidden.
- Charting records where you went. Only a passed check records understanding.
- Changing a file re-dims only that file's proof; the rest of your progress stays.

Read the [correctness contract](https://udhawan97.github.io/Codemble/correctness/).
A wrong node, edge, citation, Lens note, or check answer is a highest-severity
bug—[report it](https://github.com/udhawan97/Codemble/issues/new/choose).

## Local-first, with an explicit AI boundary

| Stays on your machine | Leaves only when Study opens with a configured narrator |
| --- | --- |
| Project discovery and parsing | A bounded Study excerpt sent to your configured narrator |
| Graph, maps, source, structural summary, Impact, Lens, and checks | A request triggered when you open Study |
| Progress and narration cache in `~/.codemble/` | No background requests |
| Narration too, when you choose local Ollama | No accounts, telemetry, or Codemble cloud |

No model? Everything except optional prose narration remains available. To add
cloud narration, set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. To keep narration
local as well:

```bash
ollama pull gemma4:12b
export CODEMBLE_PROVIDER=ollama
export CODEMBLE_OLLAMA_MODEL=gemma4:12b
```

<details>
<summary><strong>Project and rendering limits</strong></summary>

- **Supported languages:** `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`,
  `.tsx`, `.mts`, `.cts`, `.go`, `.java`, `.rs`, and `.cs`.
- **Scale:** above roughly 1,000 supported files, choose a subdirectory in the
  picker or pass `--path ./project/src`.
- **Ambiguous Home:** choose a parser-ranked candidate in the app or pass
  `--entrypoint NODE_ID`.
- **Broken source:** safe partial evidence stays visible; Codemble never invents
  the missing structure.
- **Rendering:** the galaxy needs WebGL; the flat Map does not.

</details>

<details>
<summary><strong>Develop and verify</strong></summary>

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .

(cd web && npm install && npm run check)
(cd docs-site && npm install && npm run check && npm run build)
```

The [architecture](https://udhawan97.github.io/Codemble/architecture/),
[contributing guide](https://github.com/udhawan97/Codemble/blob/main/CONTRIBUTING.md),
[design system](https://github.com/udhawan97/Codemble/blob/main/docs-site/design.md),
and [agent operating guide](https://github.com/udhawan97/Codemble/blob/main/CLAUDE.md)
keep the load-bearing decisions explicit.

</details>

## Help test the loop

The most useful contribution is a ten-minute first run on a real AI-built
project:

1. Follow the [privacy-safe tester guide](https://github.com/udhawan97/Codemble/blob/main/TESTING.md).
2. Light one system without maintainer help.
3. Report the first confusing moment in your own words—never paste private code,
   project names, credentials, or API keys.

[🧭 Open an early-tester report](https://github.com/udhawan97/Codemble/issues/new/choose)

## Roadmap

| Horizon | Work |
| --- | --- |
| **Now** | Collect unaided learner evidence and correctness reports on v0.16.0 |
| **Next** | Level-of-detail rendering and clustering for larger repositories |
| **Later** | Read-only sharing, new quest types, and a coordinated public launch |

Milestones move only when their acceptance evidence exists. See the
[public roadmap](https://udhawan97.github.io/Codemble/roadmap/).

## License and acknowledgements

Codemble is released under the [Apache License 2.0](https://github.com/udhawan97/Codemble/blob/main/LICENSE). It is built with
[tree-sitter](https://github.com/tree-sitter/tree-sitter),
[FastAPI](https://github.com/fastapi/fastapi),
[React](https://github.com/facebook/react), and
[3d-force-graph](https://github.com/vasturiano/3d-force-graph). The flat-map
approach draws inspiration from [dagre](https://github.com/dagrejs/dagre),
[Eclipse ELK](https://github.com/kieler/elkjs), and
[archify](https://github.com/tt-a1i/archify); the community constellations were
inspired by [Graphify](https://github.com/Graphify-Labs/graphify).

---

<p align="center"><sub>
  Built for the moment after “AI made it work” and before “I know how it works.”
</sub></p>
