"""Language lens: parser-detected idiom annotations to teachable notes."""

from codemble.adapters.base import ConceptAnnotation
from codemble.lens.javascript_typescript import javascript_typescript_lens_notes
from codemble.lens.python import python_lens_notes
from codemble.lens.systems_languages import SUPPORTED_LANGUAGES, systems_lens_notes


def lens_notes(language: str, annotations: list[ConceptAnnotation]) -> list[dict[str, object]]:
    """Route proven annotations to the matching language lens.

    A language with no lens returns no notes rather than borrowing another's:
    an idiom note is a claim about a specific language's syntax, and the wrong
    language's wording on a real construct is still a wrong claim.
    """

    if language == "python":
        return python_lens_notes(annotations)
    if language in {"javascript", "typescript"}:
        return javascript_typescript_lens_notes(language, annotations)
    if language in SUPPORTED_LANGUAGES:
        return systems_lens_notes(language, annotations)
    return []


__all__ = ["lens_notes"]
