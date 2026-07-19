---
title: Build from source
description: Run Codemble from a clone and verify its packaged web app.
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
npm run build           # refresh codemble/web_dist packaged assets
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

Build the Python wheel and verify the packaged SPA without Node at runtime:

```bash
python -m pip wheel . --no-deps --wheel-dir /tmp/codemble-wheel
python -m venv /tmp/codemble-install
/tmp/codemble-install/bin/pip install /tmp/codemble-wheel/codemble-0.1.0-*.whl
cd /tmp
/tmp/codemble-install/bin/codemble --version
```

The real README GIF is reproducible on macOS with Chrome, `ffmpeg`, and the
development dependencies installed:

```bash
./scripts/record_demo.sh
```
