"""Reading a source file the way its own language declares it should be read."""

from __future__ import annotations

import io
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

    return decode_source_bytes(path.read_bytes(), language)


def decode_source_bytes(raw: bytes, language: str) -> str:
    """Decode one already-read snapshot using the language's source rules."""

    if language in _DECLARED_ENCODING_LANGUAGES:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        with io.TextIOWrapper(io.BytesIO(raw), encoding=encoding) as source_file:
            return source_file.read()
    return raw.decode("utf-8", errors="replace")


__all__ = ["decode_source_bytes", "read_source_text"]
