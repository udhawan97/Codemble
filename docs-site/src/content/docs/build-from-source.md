---
title: Build from source
description: Run Codemble from a clone while it's pre-release.
---

```bash
git clone https://github.com/udhawan97/Codemble.git
cd Codemble
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest && ruff check .   # the CI gates
codemble --version
codemble parse ./some-python-project --out graph.json
```

Docs site:

```bash
cd docs-site
npm install
npm run dev       # http://localhost:4321
npm run check     # astro check (CI gate)
```

The `web/` galaxy renderer arrives with milestone M2 — see the
[roadmap](/Codemble/roadmap/).
