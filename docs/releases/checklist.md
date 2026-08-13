# Release checklist

Follow the evidence bar set by v0.2.0 (docs/releases/v0.2.0.md): tag from
exact `main`, CI green, live docs verified, wheel + sdist + SHA256SUMS attached,
fresh-download checksum and isolated install verified.

## Before tagging

1. Bump the version in every place it appears and keep them equal:
   `pyproject.toml` — the source of truth — plus `web/package.json`,
   `web/package-lock.json`, `docs-site/package.json`.
   `codemble/__init__.py` is **not** on this list and must not be added back:
   `__version__` derives from the installed distribution's metadata, so re-run
   `pip install -e ".[dev]"` after the bump and the app follows — the smoke test
   `test_the_running_app_reports_the_packaged_version` fails if it does not.
   `docs-site/release.json` gates all four manifests, its tag and predictable
   release-asset URLs. Update its UTC `sourceDateEpoch` to the release date;
   both local and CI builds use it so their bytes are reproducible.
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
6. Build with the manifest timestamp, record the exact artifact digests in
   `docs-site/release.json` and the download guide, then prove the manifest
   against those bytes:

   ```bash
   export SOURCE_DATE_EPOCH=$(node -p "require('./docs-site/release.json').sourceDateEpoch")
   python -m build
   node docs-site/scripts/check-release-facts.mjs --dist dist
   ```

## Publishing

PyPI publishing is automated: `.github/workflows/publish-pypi.yml` runs on
GitHub **release published** (trusted publishing, no token). It rebuilds the
reproducible sdist and wheel, proves them against the committed manifest,
publishes them to PyPI, then attaches those exact files plus `SHA256SUMS.txt`
to the GitHub release. Its last gate downloads the public assets and checks
PyPI metadata, GitHub metadata, both artifact digests, and the checksum ledger.
So the sequence is: tag → create the GitHub release → wait for the publish
workflow and its outside-in check.

Then verify from the outside, not from this checkout:

1. `uvx codemble==<version>` cold-starts the picker on a clean machine.
2. `npm run check:release:live` passes against PyPI, GitHub, and fresh bytes.
3. The downloaded release asset's SHA256 matches the published SHA256SUMS.
4. The live docs site reflects the release.
