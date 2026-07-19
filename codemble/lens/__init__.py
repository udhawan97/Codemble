"""Language lens: parser-detected idiom annotations to teachable notes."""

from codemble.adapters.base import ConceptAnnotation
from codemble.lens.python import python_lens_notes


def lens_notes(language: str, annotations: list[ConceptAnnotation]) -> list[dict[str, object]]:
    """Route proven annotations to the matching language lens."""

    if language == "python":
        return python_lens_notes(annotations)
    return []


__all__ = ["lens_notes"]
