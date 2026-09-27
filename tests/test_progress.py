"""Recents derived from the local progress directory."""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from codemble.progress import list_recent_projects


def _store(tmp_path, project_name="project"):
    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore

    project = tmp_path / project_name
    project.mkdir(exist_ok=True)
    for name in ("a", "b"):
        (project / f"{name}.py").write_text("value = 1\n")
    return ProgressStore(PythonAstAdapter().parse(project), tmp_path / "progress")


@pytest.mark.parametrize(
    "first,second",
    [
        (("mark_understood", "a"), ("mark_visited", "b")),
        (("mark_understood", "a"), ("set_mode", "expert")),
        (("set_selected_entrypoint", "a"), ("mark_visited", "b")),
        (("set_mode", "expert"), ("set_mode", "easy")),
        (("mark_understood", "a"), ("clear",)),
        (("clear",), ("mark_visited", "b")),
    ],
)
def test_progress_mutations_serialize_the_complete_transaction(tmp_path, monkeypatch, first, second):
    from codemble.progress import ProgressStore

    store = _store(tmp_path)
    other = ProgressStore(store._graph, tmp_path / "progress")
    store.mark_understood("b")
    reference = ProgressStore(store._graph, tmp_path / "reference")
    reference.mark_understood("b")
    for operation in (first, second):
        getattr(reference, operation[0])(*operation[1:])
    entered = threading.Event()
    release = threading.Event()
    attempted = threading.Event()
    write = store._write

    def paused(payload):
        entered.set()
        assert release.wait(timeout=5)
        write(payload)

    def run_second():
        attempted.set()
        getattr(other, second[0])(*second[1:])

    monkeypatch.setattr(store, "_write", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        earlier = pool.submit(getattr(store, first[0]), *first[1:])
        try:
            assert entered.wait(timeout=5)
            later = pool.submit(run_second)
            assert attempted.wait(timeout=5)
            # The second operation must wait for ownership, not read an old
            # snapshot while the first writer is suspended after its read.
            with pytest.raises(TimeoutError):
                later.result(timeout=0.1)
        finally:
            release.set()
        earlier.result(timeout=5)
        later.result(timeout=5)
    assert json.loads(store.path.read_text()) == json.loads(reference.path.read_text())
    assert store.mode() == reference.mode()


def test_separate_processes_serialize_and_exit_releases_lock(tmp_path):
    store = _store(tmp_path)
    worker = """
import sys
from pathlib import Path
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.progress import ProgressStore
store = ProgressStore(PythonAstAdapter().parse(Path(sys.argv[1])), Path(sys.argv[2]))
if sys.argv[3] == 'hold':
    write = store._write
    def paused(payload):
        print('held', flush=True)
        sys.stdin.readline()
        write(payload)
    store._write = paused
    store.mark_understood('a')
else:
    print('started', flush=True)
    store.mark_visited('b')
"""
    args = [sys.executable, "-c", worker, store._graph.project_root, str(tmp_path / "progress")]
    with subprocess.Popen(args + ["hold"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as holder:
        assert holder.stdout.readline().strip() == "held"
        with subprocess.Popen(args + ["visit"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as other:
            try:
                assert other.stdout.readline().strip() == "started"
                with pytest.raises(subprocess.TimeoutExpired):
                    other.wait(timeout=0.1)
            finally:
                holder.stdin.write("release\n")
                holder.stdin.flush()
            assert holder.wait(timeout=5) == 0, holder.stderr.read()
            assert other.wait(timeout=5) == 0, other.stderr.read()
    assert store.understood_regions() == {"a"}
    assert store.visited_regions() == {"b"}
    # An abruptly exited owner must also release the OS advisory lock.
    with subprocess.Popen(args + ["hold"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as holder:
        assert holder.stdout.readline().strip() == "held"
        holder.kill()
        holder.wait(timeout=5)
    store.mark_visited("a")
    assert store.visited_regions() == {"a", "b"}


def test_failed_learner_save_rolls_back_project_mode(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.set_mode("easy")
    store.mark_understood("a")
    before = store.path.read_bytes()

    def refuse(mode):
        raise OSError("fictional learner write refusal")

    monkeypatch.setattr(store, "_write_learner_mode", refuse)
    with pytest.raises(OSError, match="fictional"):
        store.set_mode("expert")
    assert store.path.read_bytes() == before
    assert store.mode() == "easy"
    assert store.understood_regions() == {"a"}


def test_replace_failure_cleans_temporary_and_keeps_old_payload(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.mark_understood("a")
    before = store.path.read_bytes()

    def refuse(*args):
        raise OSError("fictional replace refusal")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError, match="fictional"):
        store.mark_visited("b")
    assert store.path.read_bytes() == before
    assert list((tmp_path / "progress").glob("*.tmp")) == []


@pytest.mark.parametrize("failure", ["thread_busy", "process_busy", "unsupported", "write"])
def test_lock_and_write_failure_refuse_without_leaking_ownership(tmp_path, monkeypatch, failure):
    import errno

    from codemble.progress import store as module

    store = _store(tmp_path)
    store.mark_understood("a")
    before = store.path.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(module, "_MUTATION_TIMEOUT_SECONDS", 0.03)
        if failure == "thread_busy":
            store._mutation_lock.acquire()
        elif failure in ("process_busy", "unsupported"):
            def refuse(*args, **kwargs):
                raise OSError(errno.EAGAIN if failure == "process_busy" else errno.ENOSYS, "refused")
            patch.setattr(module, "_file_lock", refuse)
        else:
            def refuse(*args, **kwargs):
                raise OSError("fictional temporary write refusal")
            patch.setattr(module.json, "dumps", refuse)
        try:
            with pytest.raises(OSError):
                store.mark_visited("b")
        finally:
            if failure == "thread_busy":
                store._mutation_lock.release()
    assert store.path.read_bytes() == before
    assert list((tmp_path / "progress").glob("*.tmp")) == []
    store.mark_visited("b")
    assert store.visited_regions() == {"b"}


def test_projects_share_learner_transaction_but_keep_their_overrides(tmp_path, monkeypatch):
    first = _store(tmp_path, "first")
    second = _store(tmp_path, "second")
    entered = threading.Event()
    release = threading.Event()
    write_learner = first._write_learner_mode

    def paused(mode):
        entered.set()
        assert release.wait(timeout=5)
        write_learner(mode)

    monkeypatch.setattr(first, "_write_learner_mode", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        earlier = pool.submit(first.set_mode, "expert")
        try:
            assert entered.wait(timeout=5)
            later = pool.submit(second.set_mode, "easy")
            with pytest.raises(TimeoutError):
                later.result(timeout=0.1)
        finally:
            release.set()
        earlier.result(timeout=5)
        later.result(timeout=5)
    assert first.mode() == "expert"
    assert second.mode() == "easy"
    assert _store(tmp_path, "third").mode() == "easy"


def test_confirmed_mode_distinguishes_initial_absence_from_saved_preferences(tmp_path):
    store = _store(tmp_path)
    assert store.confirmed_mode_state() == {"mode": "easy", "chosen": False}
    store.mark_visited("a")
    assert store.confirmed_mode_state() == {"mode": "easy", "chosen": False}
    store._learner_path.write_text('{"mode":"expert"}')
    assert store.confirmed_mode_state() == {"mode": "expert", "chosen": True}
    store.set_mode("easy")
    store._learner_path.write_text("malformed unrelated default")
    assert store.confirmed_mode_state() == {"mode": "easy", "chosen": True}


@pytest.mark.parametrize("document", ["project", "learner"])
@pytest.mark.parametrize("content", ["not JSON", "[]", "{}", '{"mode":[]}'])
def test_confirmed_mode_refuses_malformed_existing_storage(tmp_path, document, content):
    from codemble.progress import ModeReadUncertainError

    store = _store(tmp_path)
    store._root.mkdir()
    target = store.path if document == "project" else store._learner_path
    target.write_text(content)
    with pytest.raises(ModeReadUncertainError):
        store.confirmed_mode_state()


@pytest.mark.parametrize("document", ["project", "learner"])
def test_confirmed_mode_refuses_unreadable_existing_storage(tmp_path, monkeypatch, document):
    from codemble.progress import ModeReadUncertainError

    store = _store(tmp_path)
    target = store.path if document == "project" else store._learner_path
    original = Path.read_text

    def refuse(path, *args, **kwargs):
        if path == target:
            raise PermissionError("fictional read refusal")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", refuse)
    with pytest.raises(ModeReadUncertainError):
        store.confirmed_mode_state()


def test_confirmed_mode_waits_for_the_complete_two_file_mutation(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.set_mode("easy")
    entered = threading.Event()
    release = threading.Event()
    write = store._write_learner_mode

    def paused(mode):
        entered.set()
        assert release.wait(timeout=5)
        write(mode)

    monkeypatch.setattr(store, "_write_learner_mode", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        mutation = pool.submit(store.set_mode, "expert")
        try:
            assert entered.wait(timeout=5)
            recovery = pool.submit(store.confirmed_mode_state)
            with pytest.raises(TimeoutError):
                recovery.result(timeout=0.1)
        finally:
            release.set()
        mutation.result(timeout=5)
        assert recovery.result(timeout=5) == {"mode": "expert", "chosen": True}


def _write_progress(root: Path, name: str, payload: object, mtime: float) -> None:
    path = root / "progress" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_recents_lists_existing_projects_newest_first(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))
    older = tmp_path / "older-project"
    newer = tmp_path / "newer-project"
    older.mkdir()
    newer.mkdir()
    _write_progress(
        tmp_path / "data",
        "aaa",
        {
            "schema_version": 1,
            "project_root": str(older),
            "regions": {"pkg": {"signature": "s1"}},
        },
        mtime=1_000.0,
    )
    _write_progress(
        tmp_path / "data",
        "bbb",
        {
            "schema_version": 1,
            "project_root": str(newer),
            "regions": {"a": {"signature": "s2"}, "b": {"signature": "s3"}},
        },
        mtime=2_000.0,
    )
    _write_progress(
        tmp_path / "data",
        "ccc",
        {
            "schema_version": 1,
            "project_root": str(tmp_path / "deleted-project"),
            "regions": {},
        },
        mtime=3_000.0,
    )
    (tmp_path / "data" / "progress" / "junk.json").write_text(
        "not json", encoding="utf-8"
    )

    recents = list_recent_projects()

    assert recents == [
        {"project_root": str(newer), "understood_count": 2},
        {"project_root": str(older), "understood_count": 1},
    ]


def test_recents_survive_a_missing_progress_directory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "never-written"))

    assert list_recent_projects() == []


def test_clear_forgets_only_this_projects_regions(tmp_path: Path) -> None:
    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore

    fixture = Path(__file__).parent / "fixtures" / "sampleproj"
    other = tmp_path / "other"
    other.mkdir()
    (other / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")

    graph = PythonAstAdapter().parse(fixture)
    other_graph = PythonAstAdapter().parse(other)
    store = ProgressStore(graph, tmp_path / "progress")
    other_store = ProgressStore(other_graph, tmp_path / "progress")
    store.set_mode("expert")
    store.mark_understood("app")
    other_store.mark_understood("solo")

    store.clear()

    assert store.understood_regions() == frozenset()
    assert other_store.understood_regions() == frozenset({"solo"})
    assert store.mode() == "expert", "clearing progress must not reset preferences"
    assert other_store.path.exists()


def test_a_new_project_inherits_the_audience_the_learner_already_chose(
    tmp_path: Path,
) -> None:
    """The gate asks about the learner, so it must not re-ask per project.

    Mode stays per project -- it drives the default layer and can be changed
    from the header on any one of them -- but a fresh bind seeds itself from
    the last answer instead of showing the first-run gate again.
    """

    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore

    first = tmp_path / "first"
    second = tmp_path / "second"
    for project in (first, second):
        project.mkdir()
        (project / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")
    root = tmp_path / "progress"

    answered = ProgressStore(PythonAstAdapter().parse(first), root)
    answered.set_mode("expert")

    fresh = ProgressStore(PythonAstAdapter().parse(second), root)
    assert fresh.mode() == "expert"
    assert fresh.mode_chosen() is True, "a seeded project must not re-open the gate"

    fresh.set_mode("easy")
    assert fresh.mode() == "easy"
    assert answered.mode() == "expert", "per-project override must not rewrite the other"


def test_the_learner_preference_file_is_never_offered_as_a_recent_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It shares the progress directory, so recents must not read it as a project."""

    from codemble.adapters.python_ast import PythonAstAdapter
    from codemble.progress import ProgressStore, list_recent_projects

    project = tmp_path / "project"
    project.mkdir()
    (project / "solo.py").write_text("def go() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.setenv("CODEMBLE_DATA_DIR", str(tmp_path / "data"))

    store = ProgressStore(PythonAstAdapter().parse(project))
    store.set_mode("expert")
    store.mark_understood("solo")

    recents = list_recent_projects()
    assert [entry["project_root"] for entry in recents] == [str(project.resolve())]
