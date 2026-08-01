"""Codemble — a learning game that turns the code AI wrote for you into a galaxy
you light up by understanding it. See CLAUDE.md for the agent brief and roadmap."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Derived, never restated. `pyproject.toml` is the one source of truth, and
    # a built wheel's metadata *is* the pyproject it was built from — so the
    # version the app reports cannot disagree with the version users installed.
    # Held as a literal here it silently could, and did: v0.8.0 shipped a wheel
    # whose app reported 0.7.0.
    __version__ = version("codemble")
except PackageNotFoundError:  # imported from a checkout with nothing installed
    __version__ = "0.0.0+unknown"
