"""The one local directory every Codemble-owned path hangs off."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Return ``$CODEMBLE_DATA_DIR``, or the default ``~/.codemble``.

    All three things Codemble writes or reads under a learner's home -- saved
    progress, the narration cache, and the BYO-key config -- resolve through
    here, so one variable moves them together. Two of them used to hardcode
    ``Path.home()``, which left the test suite able to read the developer's
    real config (and so build a real provider where CI builds none) even after
    ``CODEMBLE_DATA_DIR`` redirected progress.

    Read at call time, never at import: tests set the variable with
    ``monkeypatch`` after this module is already imported.
    """

    root = os.environ.get("CODEMBLE_DATA_DIR")
    return Path(root).expanduser() if root else Path.home() / ".codemble"


__all__ = ["data_dir"]
