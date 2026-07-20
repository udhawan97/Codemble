"""Suite-wide isolation from the developer's real ``~/.codemble``."""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True, scope="session")
def isolated_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point every test's progress store at a throwaway directory.

    ``ProgressStore`` and ``list_recent_projects`` fall back to ``~/.codemble``
    whenever ``CODEMBLE_DATA_DIR`` is unset, and a test only has to *reach* one
    indirectly to write there: ``create_app`` builds a default ``CheckService``
    -- and so a default store -- for every caller that passes no
    ``check_service``.  A learner's understood-region state lives in that
    directory, so the suite must never be able to touch it.

    Set once for the whole session rather than per call site: the leak came
    from a test that never mentions the store at all, so any rule the call
    sites have to remember would miss the next one the same way.  Tests that
    set the variable themselves still win -- function-scoped ``monkeypatch``
    applies over this and is undone before the next test.
    """

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CODEMBLE_DATA_DIR", str(tmp_path_factory.mktemp("codemble-data")))
        yield
