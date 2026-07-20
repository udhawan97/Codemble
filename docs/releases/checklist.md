# Release checklist

Follow the evidence bar set by v0.2.0 (docs/releases/v0.2.0.md): tag from
exact `main`, CI green, live docs verified, wheel + SHA256SUMS attached,
fresh-download checksum and isolated install verified.

## Before tagging

1. Bump the version in every place it appears and keep them equal:
   `pyproject.toml`, `codemble/__init__.py`, `web/package.json`,
   `web/package-lock.json`, `docs-site/package.json`.
2. Convert the `[Unreleased]` changelog section into a dated release section
   and open a fresh empty `[Unreleased]`.
3. Write `docs/releases/vX.Y.Z.md` — highlights and, just as importantly, the
   known limits. Do not let it claim work that only exists in a plan.
4. If the web app changed, rebuild and commit `codemble/web_dist`
   (`cd web && npm run build`); the wheel serves that committed bundle.
5. Gates: `python3 -m pytest`, `ruff check .`, `(cd web && npm run check)`,
   `(cd docs-site && npm install && npm run check)`.
   `docs-site/package-lock.json` is deliberately untracked — if `npm install`
   creates it, delete it before committing.

## Publishing

PyPI publishing is automated: `.github/workflows/publish-pypi.yml` runs on
GitHub **release published** (trusted publishing, no token). It builds the sdist
and wheel and refuses to publish a wheel that does not carry
`codemble/web_dist/`. So the sequence is: tag → create the GitHub release →
the workflow publishes.

Then verify from the outside, not from this checkout:

1. `uvx codemble==<version>` cold-starts the picker on a clean machine.
2. The downloaded release asset's SHA256 matches the published SHA256SUMS.
3. The live docs site reflects the release.
