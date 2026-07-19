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

cd web
npm install
npm run check           # production galaxy build (CI gate)
cd ..

codemble ./some-python-project
```

Docs site:

```bash
cd docs-site
npm install
npm run dev       # http://localhost:4321
npm run check     # astro check (CI gate)
```

For live frontend work, run `./scripts/dev.sh ./some-python-project` from the
repository root. Vite serves the UI at `http://127.0.0.1:5173` and proxies its
API calls to the local Codemble server.
