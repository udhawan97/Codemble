"""Language lens: parser-detected idiom annotations to teachable notes."""

from codemble.adapters.base import ConceptAnnotation
from codemble.lens.javascript_typescript import javascript_typescript_lens_notes
from codemble.lens.python import python_lens_notes


def lens_notes(language: str, annotations: list[ConceptAnnotation]) -> list[dict[str, object]]:
    """Route proven annotations to the matching language lens."""

    if language == "python":
        return python_lens_notes(annotations)
    if language in {"javascript", "typescript"}:
        return javascript_typescript_lens_notes(language, annotations)
    return []


__all__ = ["lens_notes"]
