# Release checklist

Follow the evidence bar set by v0.2.0 (docs/releases/v0.2.0.md): tag from
exact `main`, CI green, live docs verified, wheel + SHA256SUMS attached,
fresh-download checksum and isolated install verified.

## Before tagging

1. Bump the version in every place it appears and keep them equal:
   `pyproject.toml` — the source of truth — plus `web/package.json`,
   `web/package-lock.json`, `docs-site/package.json`.
   `codemble/__init__.py` is **not** on this list and must not be added back:
   `__version__` derives from the installed distribution's metadata, so re-run
   `pip install -e ".[dev]"` after the bump and the app follows — the smoke test
   `test_the_running_app_reports_the_packaged_version` fails if it does not.
   The three npm manifests are deliberately **not** gated and stay a step you
   have to remember: nothing consumes their `version` field, neither package is
   published, so a drift there is cosmetic.
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
