# Release checklist

Follow the evidence bar set by v0.2.0 (docs/releases/v0.2.0.md): tag from
exact `main`, CI green, live docs verified, wheel + SHA256SUMS attached,
fresh-download checksum and isolated install verified.

New since v0.2.0 — PyPI:

1. One-time: claim the `codemble` name on PyPI (UD account) before the first
   publish.
2. After the tag is verified: `python -m build` (or reuse the release wheel)
   and `uv publish` / `twine upload` from the tagged commit.
3. Verify `uvx codemble==<version>` cold-starts the picker on a clean machine
   before announcing the PyPI install path.
