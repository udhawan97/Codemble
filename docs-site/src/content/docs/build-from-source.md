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

codemble ./some-project
```

Docs site:

```bash
cd docs-site
npm install
npm run brand:build # regenerate committed SVG/PNG brand assets
npm run check     # astro check (CI gate)
npm run build
```

Preview separately because the development server stays open:

```bash
cd docs-site
npm run dev       # http://localhost:4321
```

For live frontend work, run `./scripts/dev.sh ./some-project` from the
repository root. Vite serves the UI at `http://127.0.0.1:5173` and proxies its
API calls to the local Codemble server.

Build the Python wheel and verify the packaged SPA without Node at runtime:

```bash
python -m pip wheel . --no-deps --wheel-dir /tmp/codemble-wheel
python -m venv /tmp/codemble-install
/tmp/codemble-install/bin/pip install /tmp/codemble-wheel/codemble-*.whl
cd /tmp
/tmp/codemble-install/bin/codemble --version
```

The committed product screenshots are reproducible with Chrome, Python, and the
web dependencies installed:

```bash
(cd web && npm run capture:docs)
```

The command starts its own current-source server on a random loopback port with
a unique temporary `CODEMBLE_DATA_DIR`. Provider keys and provider settings are
removed from that child process, the progress reset must succeed before capture
continues, and the server plus temporary data are removed afterward. It refuses
`CODEMBLE_CAPTURE_URL` so it cannot be pointed at a normal Codemble session.
Set `CODEMBLE_CAPTURE_PYTHON` only when the desired Python executable is not
named `python`.
