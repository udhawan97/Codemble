"""Reading a source file the way its own language declares it should be read."""

from __future__ import annotations

import tokenize
from pathlib import Path

# Python is the only supported language that lets a file declare its own
# encoding, so it is the only one with an entry. Everything else is decoded as
# UTF-8 with replacement, which never raises and never silently drops a line --
# an unreadable byte becomes a visible replacement character in the panel rather
# than a missing structure.
#
# This lives beside the adapters because it is a language fact. It was a branch
# inside `codemble/llm/study.py`, which had no business knowing about PEP 263.
_DECLARED_ENCODING_LANGUAGES = frozenset({"python"})


def read_source_text(path: Path, language: str) -> str:
    """Return ``path`` decoded as ``language`` says it should be."""

    if language in _DECLARED_ENCODING_LANGUAGES:
        with tokenize.open(path) as source_file:
            return source_file.read()
    return path.read_bytes().decode("utf-8", errors="replace")


__all__ = ["read_source_text"]
