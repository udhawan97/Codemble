# Contributing to Codemble

Thanks for helping people actually understand the code AI wrote for them.

## Golden rules (read these first)

1. **Never invent structure.** Nodes, edges, entrypoints, and idiom locations come from the parser only. The LLM narrates; it does not decide.
2. **Check answers come from the graph, not the model.** If a quiz answer can be wrong, it does not ship.
3. **The learner cannot detect our mistakes.** When accuracy and delight conflict, accuracy wins.
4. **Semantic zoom only.** No free-flight navigation; no game logic in the renderer (the graph layer owns it).
5. **Small diffs, running software.** The project must run end-to-end after every merge.

## Repository layout

| Path | What |
| --- | --- |
| `codemble/` | Python package: adapters, graph, lens, checks, llm, server, progress, CLI |
| `web/` | Galaxy renderer source (Vite + React + 3d-force-graph) |
| `codemble/web_dist/` | Built production SPA bundled in the Python wheel |
| `tests/` | Pytest suite |
| `docs/` | Internal docs: ADRs, plans, research |
| `docs-site/` | Public docs & website (Astro + Starlight → GitHub Pages) |
| `CLAUDE.md` | Agent brief & operating guide — the authoritative spec and roadmap |

## Development setup

```bash
git clone https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .
cd web && npm install && npm run build && cd ..
```

Docs site:

```bash
cd docs-site
npm install
npm run dev      # local preview
npm run check    # astro check (CI gate)
```

## Branches, commits, PRs

- Branch prefixes: `feat/`, `fix/`, `docs/`, `chore/`.
- [Conventional Commits](https://www.conventionalcommits.org/), signed off (`git commit -s`, DCO).
- Fill in the PR template; link the milestone (M1–M6) your change belongs to.

## Tests & quality gates

`pytest` and `ruff check .` must pass; parser/graph/checks changes need unit tests.
Docs-site changes must pass `npm run check` and build cleanly.

## Reporting bugs / proposing features

Use the issue templates. Security issues go through [SECURITY.md](SECURITY.md), never public issues.
