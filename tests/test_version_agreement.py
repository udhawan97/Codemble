"""One version, and every spot that repeats it must agree with ``pyproject.toml``.

``pyproject.toml`` is the source of truth: it builds the wheel and it is what the
git tag matches. ``codemble.__version__`` is no longer a second literal — it
reads the installed distribution's own metadata — so this suite guards the two
ways that can still drift:

* a **stale install**. Metadata is written at install time, so bumping
  ``pyproject.toml`` without reinstalling leaves the app reporting the old
  version. Locally that is a nuisance; in a built wheel it cannot happen at all,
  because the wheel's metadata *is* the ``pyproject.toml`` it was built from.
* the **npm manifests**, which nothing derives and nothing else checks. The
  release checklist requires them to match; before this test that requirement
  was enforced only by a human reading a list, which is exactly how
  ``codemble/__init__.py`` came to ship a release behind.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import codemble

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that restate the version and cannot derive it. `web/package-lock.json`
# carries it twice — at the top level and again under `packages[""]`.
NPM_MANIFESTS = ("web/package.json", "docs-site/package.json")


def _pyproject_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def test_the_running_app_reports_the_packaged_version() -> None:
    """What `--version`, the API and the outbound user-agent all report."""

    declared = _pyproject_version()

    assert codemble.__version__ == declared, (
        f"codemble.__version__ is {codemble.__version__!r} but pyproject declares "
        f"{declared!r}. __version__ reads the installed distribution's metadata, so "
        'a stale install says this too — re-run `pip install -e ".[dev]"`.'
    )


def test_the_npm_manifests_carry_the_same_version() -> None:
    declared = _pyproject_version()

    for relative in NPM_MANIFESTS:
        found = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))["version"]
        assert found == declared, (
            f"{relative} is at {found!r}, pyproject at {declared!r}."
        )


def test_the_web_lockfile_carries_the_same_version_in_both_spots() -> None:
    lockfile = json.loads(
        (REPO_ROOT / "web/package-lock.json").read_text(encoding="utf-8")
    )
    declared = _pyproject_version()

    assert lockfile["version"] == declared
    assert lockfile["packages"][""]["version"] == declared
