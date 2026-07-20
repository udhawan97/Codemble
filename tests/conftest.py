"""Suite-wide isolation from the developer's real machine."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

# Every variable ``StudyService.from_environment`` reads. Inherited from the
# developer's shell, any one of these builds a real provider where CI builds
# none, so the same test can pass in CI and fail locally (or the reverse).
_PROVIDER_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "CODEMBLE_ANTHROPIC_MODEL",
    "CODEMBLE_OLLAMA_HOST",
    "CODEMBLE_OLLAMA_MODEL",
    "CODEMBLE_OPENAI_MODEL",
    "CODEMBLE_PROVIDER",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True, scope="session")
def isolated_environment(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Decide provider and storage from the test alone, never from the machine.

    Two separate channels reach out of the suite, and closing one leaves the
    other open:

    *Storage.* ``CODEMBLE_DATA_DIR`` now owns every path Codemble keeps under a
    home directory -- progress, the narration cache, and the config file (see
    ``codemble.paths.data_dir``). A test only has to *reach* a default service
    to touch them: ``create_app`` builds a default ``CheckService`` and a
    default ``StudyService`` for every caller that passes neither.

    *Provider keys.* Redirecting the directory does nothing about
    ``ANTHROPIC_API_KEY`` and friends, which ``from_environment`` reads
    straight from the process environment. With one set, the ~30 bare
    ``create_app(graph, ...)`` calls in ``test_server.py`` build a live
    ``AnthropicProvider``, and the two tests that GET ``/explanation`` make a
    real, billed API call whose response is then cached under the developer's
    home. Both assert only that a ``status`` key came back -- true of
    ``no_key``, ``ready``, and ``error`` alike -- so nothing fails to reveal it.

    Set once for the whole session rather than per call site: the original leak
    came from a test that never mentions the store at all, so any rule the call
    sites have to remember would miss the next one the same way. Tests that set
    these themselves still win -- function-scoped ``monkeypatch`` applies over
    this and is undone before the next test -- as does any explicit ``environ``,
    ``config_path``, or ``cache_root`` argument, which bypasses both channels.
    """

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CODEMBLE_DATA_DIR", str(tmp_path_factory.mktemp("codemble-data")))
        for variable in _PROVIDER_VARIABLES:
            patch.delenv(variable, raising=False)
        yield
