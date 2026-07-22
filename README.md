
<p align="center">
  <a href="https://udhawan97.github.io/Codemble/">
    <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/mark-animated.svg" alt="Codemble — an open lapis ensō whose amber star systems light up" width="152">
  </a>
</p>

<h1 align="center">Codemble</h1>

<p align="center"><strong>Turn AI-built code into a galaxy you actually understand.</strong></p>

<p align="center">
  Codemble is a local-first learning game for projects built with Claude Code,
  Codex, and other coding agents. It maps real parser evidence into a 3D galaxy
  and a flat architecture map, then lights each region only after you prove you
  understand it.
</p>

<p align="center"><strong>Your project · Your key · Your machine · No invented structure</strong></p>

<p align="center">
  <a href="https://github.com/udhawan97/Codemble/releases/latest"><img src="https://img.shields.io/github/v/release/udhawan97/Codemble?style=flat-square&label=release&color=2b4d96" alt="Latest release"></a>
  <a href="https://github.com/udhawan97/Codemble/actions/workflows/ci.yml"><img src="https://github.com/udhawan97/Codemble/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status"></a>
  <img src="https://img.shields.io/badge/Python-3.11+-2b4d96?style=flat-square" alt="Python 3.11 or newer">
  <img src="https://img.shields.io/badge/maps-Python_·_JavaScript_·_TypeScript-3f6ac0?style=flat-square" alt="Maps Python, JavaScript, and TypeScript projects">
  <img src="https://img.shields.io/badge/license-Apache_2.0-070b1c?style=flat-square" alt="Apache 2.0 license">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-the-learning-loop-works">Learning loop</a> ·
  <a href="https://udhawan97.github.io/Codemble/">Documentation</a> ·
  <a href="https://github.com/udhawan97/Codemble/blob/main/TESTING.md">Test Codemble</a>
</p>

<p align="center">
  <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/galaxy.png" alt="Codemble at galaxy level: 109 star systems parsed from real source, 23 charted and named by file path, constellations wearing their import-community colour families in traditional Japanese hues around an amber lit Home, with language focus buttons, a Key disclosure, and a notice that two files could not be read — all under tests/" width="960">
</p>

<p align="center"><sub>
  Galaxy level. Every system is one module; size is lines of code, brightness is
  how many distinct structures call it. Files the parser could not read stay
  visible and say so.
</sub></p>

> [!IMPORTANT]
> **Codemble is in its Phase 1 tester release.** It maps Python,
> JavaScript, TypeScript, and mixed projects in one parser-proven galaxy,
> installable straight from PyPI with an in-app project picker. The
> technical release is complete; unaided learner runs are the evidence still
> being collected. [Try the ten-minute tester loop](https://github.com/udhawan97/Codemble/blob/main/TESTING.md).

## Quick start

Two steps. The first is once per machine; the second is how you run Codemble
from then on.

| | Step | Command |
| :---: | --- | --- |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/install.svg" width="22" height="22" alt=""> | **1 · Install uv** — the runner that fetches Codemble on demand | `brew install uv` |
| <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/brand/icons/asterism.svg" width="22" height="22" alt=""> | **2 · Chart your project** — nothing to install, nothing left behind | `uvx codemble` |

<details>
<summary><strong>Installing uv without Homebrew</strong></summary>

```bash
# macOS · Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Already have `pipx`? You can skip uv entirely: `pipx install codemble`, then run
`codemble`. Plain `pip install codemble` works too. uv is the recommended path
because `uvx` runs the current release without adding anything to your system
Python.

</details>

Codemble opens your browser — pick your project folder there. To skip the
picker, pass a path: `codemble ./your-ai-built-project`.

The wheel already contains the web app, so Node.js is not required. No API key
is needed for the galaxy, the map, the structural summary, source viewer,
language Lens, checks, lighting, or saved progress. Add your own Anthropic or
OpenAI key only if you want grounded prose explanations:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY=sk-...
```

Prefer to send nothing anywhere? Point Codemble at a local
[Ollama](https://ollama.com) instead — same grounding validation, loopback only,
never automatic:

```bash
ollama pull gemma4:12b && export CODEMBLE_PROVIDER=ollama
```

[Installation, configuration, and troubleshooting →](https://udhawan97.github.io/Codemble/installation/)

## How the learning loop works

| Step | What Codemble does | What you gain |
| --- | --- | --- |
| **1. Chart** | Parses your project without running its code or package scripts | A deterministic map made from source evidence |
| **2. Navigate** | Two layers over one graph: a 3D galaxy on scripted camera rails, and a flat map of architecture and workflow | Orientation without getting lost in free flight |
| **3. Study** | Shows the real source, exact line numbers, neighbors, and parser-detected language idioms | Context tied to code you can inspect |
| **4. Prove** | Generates and scores checks from the graph—never from the model | A region lights only when understanding is demonstrated |
| **5. Return** | Saves progress locally; changing one file re-dims only its module | A living map that stays honest as the project changes |

No XP. No streaks. No leaderboard. The visible reward is the useful one: more
of your own code becomes a sky you understand.

## What it looks like

<p align="center">
  <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/system.png" alt="A single star system, codemble.server.app, its functions and classes as planets in the system's own colour family, in call-depth orbits with the call edges between them" width="900">
</p>

<p align="center"><sub>
  System level. Members orbit by call depth, so the inner ring runs first.
</sub></p>

<p align="center">
  <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/study-panel.png" alt="The study panel for create_app, showing kind, span, 53 callers, parser-proven resolution, and a structural summary marked no model needed" width="900">
</p>

<p align="center"><sub>
  Study. Everything on this panel except the narration comes from the parser —
  and this one has no model configured at all.
</sub></p>

<p align="center">
  <img src="https://github.com/udhawan97/Codemble/raw/main/docs-site/public/shots/loading.png" alt="Codemble's staged loading screen mapping a large project, with five named stages — finding source files, reading each file, connecting imports and calls, building graph-only checks, placing your galaxy — a live count reading 13 of 900 files, and a cancel button" width="900">
</p>

<p align="center"><sub>
  Large projects (up to roughly 1,000 source files) parse in the background with
  visible staged progress — a real file count while reading, named steps while
  resolving — so a big project never looks like a frozen tab. Cancel any time to
  pick another.
</sub></p>

## Two layers over one graph

Codemble draws the same parser evidence two ways, switchable in the header. The
map cannot show you a relationship the galaxy does not have — both layouts are
computed in the graph layer and served as data.

| Layer | What it is | When it helps |
| --- | --- | --- |
| **Galaxy** | 3D, camera on rails through galaxy → system → study | Orientation, and the shape of the whole project |
| **Map · Architecture** | Modules as boxes, grouped by folder, layered by import distance from Home | Seeing how the project fits together |
| **Map · Workflow** | The call tree from your entrypoint, depth by depth | Seeing what runs first |

The Map is plain SVG, so it still works on a machine that cannot draw WebGL.
Click a box and it offers both halves of a step — **Read the source** opens that
module's real source, lens notes and relationships without leaving the layer,
and **Prove understanding** starts its checks. Escape steps back a level, as in
the Galaxy. On a compact screen the Map opens at readable 100% around Home or
the selected target; **Fit** is an explicit whole-diagram overview. Zoom and pan
survive Map refreshes and layer switches instead of snapping back after a passed
check.

In Easy mode these surfaces carry plainer labels — the layer is **Diagram** and
the tabs are **How it fits together** and **What runs first**. Same views, same
evidence; only the wording follows the audience.

## Open a structure, read what the parser knows first

The study panel builds itself outward from the most certain evidence: a
structural summary written from parser facts alone — no key, no network, no
model — then grounded narration if you configured a provider, then every
connection into and out of the structure with its direction, its certainty, and
a `file:line` you can click, then the real source and the language Lens notes.

Sections other than the narration never involve a model at all.

## Easy or Expert

A header toggle changes how Codemble talks to you and how much it puts on
screen: plain language, larger type, the Map by default, and a hint chip naming
the nearest unlit region to Home — counted in import hops over the graph, not
chosen by a model, and broken by parser-proven structure count when several sit
the same distance away. The hint opens that system, offers to read its source,
then becomes an instruction rather than an enabled no-op. It waits until the
first-run choices are done before it appears at all, and it never changes graph
truth, coordinates, progress, or how a check is scored.

Codemble asks which audience you are **once** — the question is about you, not
about the project — and each project still keeps its own mode.

You can also switch project or change Home without leaving the app.

## Read the galaxy

| In the galaxy | In your project |
| --- | --- |
| A star system | One source module |
| A planet | A function or class |
| The Home system | The selected parser-ranked entrypoint |
| A route or edge | An import or call; approximate calls are labeled **possible** |
| Size | Lines of code |
| Brightness and glow | How many **distinct** structures call it |
| Colour family | Import community — modules that import each other share one of eight traditional Japanese hues |
| Nebula tint | Language, at galaxy level |
| Orbit ring | Call depth — the inner ring runs first |
| Drifting particles | A call the parser proved; a possible call stays still |
| Dim → lit | Not yet proven → understood |

Understanding owns the top of the brightness range: the unlit ramp stops below
the amber a lit star uses, so a busy module you have not proven can never
outshine one you have — every community hue is lightness-capped beneath it, and
the amber band is excluded from the community wheel entirely. Pass a region's
checks and that system plays a short amber "nebula dawn" — after the light is
already saved, so the animation marks a fact rather than delivering one. On the
flat Map, modules with no import route from Home fold into a counted shelf
(**Show them** draws every one), so test scaffolding never buries the connected
core it cannot reach.

Python-only, JavaScript-only, TypeScript-only, and mixed projects share the same
graph contract. Language focus changes only what you are looking at; it never
changes coordinates, progress, or parser truth.

## Honest by construction

Codemble is built for learners who may not yet be able to spot a confident
mistake. Accuracy therefore outranks spectacle:

- Structure, entrypoints, concepts, imports, and calls come from parsers.
- Every explanation points to a real `file:line` and may name only supplied
  identifiers and relationships.
- Language Lens notes appear only where a parser detected the construct.
- Check answers come from the graph, never an LLM.
- Approximate relationships stay visibly uncertain — a distinct colour and no
  drifting particles in the 3D galaxy, a genuinely dashed line in the 2D map,
  and the legend swatch follows whichever layer is on screen.
- Provider output that fails grounding validation is withheld instead of being
  softened into a guess.

Read the full [correctness contract](https://udhawan97.github.io/Codemble/correctness/).
A wrong explanation is a highest-severity bug—[report it without mercy](https://github.com/udhawan97/Codemble/issues).

## Local-first, with an explicit AI boundary

| Stays on your machine | Leaves only when you ask |
| --- | --- |
| Project discovery and parsing | The bounded Study context sent to your configured provider |
| Graph, structural summary, language Lens, and checks | A request triggered only when you open Study |
| Local server and packaged web app | Nothing in the background |
| Progress and explanation cache in `~/.codemble/` | No accounts, telemetry, or Codemble cloud |
| Narration too, if you choose a local Ollama | Nothing at all in that case |

No model at all? Codemble remains a complete parser-backed map and learning
game; only the optional prose narration is unavailable.

## Boundaries that keep the map truthful

- **Supported source:** Python 3.11+, JavaScript/JSX, TypeScript/TSX, and mixed
  projects. Unsupported languages stay outside the graph rather than being guessed.
- **Scale:** above roughly 1,000 supported source files, choose a subdirectory —
  the in-app picker offers the busiest scopes as buttons and accepts a typed
  path, or pass `codemble --path ./project/subdirectory`.
- **Ambiguous Home:** choose a parser-ranked entrypoint in the app or pass
  `--entrypoint NODE_ID`.
- **Broken source:** syntax errors remain visible; Codemble maps safe partial
  evidence instead of crashing or inventing the missing structure.
- **Rendering:** the 3D galaxy needs WebGL. If your machine cannot draw it, the
  Map layer still works — it is plain SVG over the same parser evidence, not a
  degraded guess.

## Help test the release

The most valuable contribution right now is not a feature request. It is a
first run on a real AI-built project:

1. Follow the [ten-minute tester guide](https://github.com/udhawan97/Codemble/blob/main/TESTING.md).
2. Light at least one system.
3. Report confusion verbatim—never paste private source or API keys.

[Open an early-tester report →](https://github.com/udhawan97/Codemble/issues/new?template=early_tester.yml)

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .

(cd web && npm install && npm run check)
(cd docs-site && npm install && npm run check && npm run build)
```

The load-bearing design and architecture contracts are documented, not implied:

- [Architecture](https://udhawan97.github.io/Codemble/architecture/)
- [Contributing](https://github.com/udhawan97/Codemble/blob/main/CONTRIBUTING.md)
- [Formal Edo design system](https://github.com/udhawan97/Codemble/blob/main/docs-site/design.md)
- [Agent operating guide and current state](https://github.com/udhawan97/Codemble/blob/main/CLAUDE.md)

## Roadmap

| Horizon | Work |
| --- | --- |
| **Now** | Collect unaided first-run evidence on the current release across supported project types |
| **Next** | Go, Rust, and Java adapters; level-of-detail rendering for larger repositories |
| **Later** | Read-only share links, new quest types, and the coordinated public launch |

The [public roadmap](https://udhawan97.github.io/Codemble/roadmap/) separates
shipped work from planned work. Milestones move only when their acceptance
evidence exists.

## Acknowledgements

- [dagre](https://github.com/dagrejs/dagre) and [Eclipse ELK](https://github.com/eclipse-elk/elk) for the layered-diagram approach.
- [tt-a1i/archify](https://github.com/tt-a1i/archify) for 2D architecture-diagram inspiration.
- [Graphify](https://github.com/Graphify-Labs/graphify) for the community-constellation idea.
- Codemble's shipped open-source stack: [3d-force-graph](https://github.com/vasturiano/3d-force-graph), [tree-sitter](https://github.com/tree-sitter/tree-sitter), [FastAPI](https://github.com/fastapi/fastapi), [Vite](https://github.com/vitejs/vite), and [React](https://github.com/facebook/react).

## License

Codemble is released under the [Apache License 2.0](https://github.com/udhawan97/Codemble/blob/main/LICENSE).

---

<p align="center"><sub>
  Built for the moment after “AI made it work” and before “I know how it works.”
</sub></p>
