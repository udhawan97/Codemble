"""Graph-only check generation and file-scoped progress contracts."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.checks import CheckService, generate_checks
from codemble.progress import ProgressStore

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"


def test_home_region_has_all_four_graph_derived_check_types() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    checks = generate_checks(graph, "app")

    assert {check.kind for check in checks} == {
        "first-call",
        "direct-importer",
        "removal-impact",
        "entrypoint",
    }
    assert all(check.answer_ids for check in checks)
    assert all(check.evidence for check in checks)
    public = [check.public(passed=False) for check in checks]
    assert all("answer_ids" not in question for question in public)


def test_only_the_complete_exact_suite_lights_a_region(tmp_path: Path) -> None:
    graph = PythonAstAdapter().parse(FIXTURE)
    progress = ProgressStore(graph, tmp_path)
    service = CheckService(graph, progress)
    checks = generate_checks(graph, "app")

    first = checks[0]
    wrong = next(option.id for option in first.options if option.id not in first.answer_ids)
    result = service.submit("app", first.id, [wrong])
    assert result["correct"] is False
    assert not progress.path.exists()

    for index, check in enumerate(checks):
        result = service.submit("app", check.id, list(check.answer_ids))
        assert result["correct"] is True
        assert result["region_understood"] is (index == len(checks) - 1)

    hydrated = service.graph()
    assert next(region for region in hydrated.regions if region.id == "app").understood
    assert all(node.understood for node in hydrated.nodes if node.region == "app")

    restarted = CheckService(graph, ProgressStore(graph, tmp_path))
    assert restarted.for_region("app")["region_understood"] is True


def test_every_check_offers_at_least_one_wrong_option(tmp_path: Path) -> None:
    """A check whose options are all correct lights a region without understanding."""

    project = tmp_path / "manyimporters"
    project.mkdir()
    (project / "core.py").write_text("def run() -> None:\n    pass\n", encoding="utf-8")
    for name in ("alpha", "beta", "gamma", "delta", "epsilon"):
        (project / f"{name}.py").write_text(
            "import core\n\n\ndef go() -> None:\n    core.run()\n", encoding="utf-8"
        )
    graph = PythonAstAdapter().parse(project)

    core = generate_checks(graph, "core")
    assert core, "the fixture must produce checks for the many-importer region"
    assert any(len(check.answer_ids) >= 4 for check in core), (
        "the fixture must exercise a check with four or more correct answers"
    )

    for region in graph.regions:
        for check in generate_checks(graph, region.id):
            distractors = {option.id for option in check.options} - set(check.answer_ids)
            assert distractors, (
                f"{region.id}/{check.kind} offers no wrong option, so selecting "
                f"every option passes it ({len(check.options)} options, all correct)"
            )


def test_editing_one_file_redims_only_its_region(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    graph = PythonAstAdapter().parse(project)
    progress_root = tmp_path / "progress"
    progress = ProgressStore(graph, progress_root)
    progress.mark_understood("app")
    progress.mark_understood("pkg.util")

    app_file = project / "app.py"
    app_file.write_text(
        app_file.read_text(encoding="utf-8") + "\n# changed after learning\n",
        encoding="utf-8",
    )
    changed_graph = PythonAstAdapter().parse(project)
    restarted = ProgressStore(changed_graph, progress_root)

    assert restarted.understood_regions() == frozenset({"pkg.util"})
    hydrated = restarted.hydrated_graph()
    assert not next(region for region in hydrated.regions if region.id == "app").understood
    assert next(region for region in hydrated.regions if region.id == "pkg.util").understood


def test_marking_a_region_understood_preserves_the_mode_preference(tmp_path: Path) -> None:
    """mark_understood must not clobber sibling keys it does not own, like mode."""

    graph = PythonAstAdapter().parse(FIXTURE)
    progress = ProgressStore(graph, tmp_path)
    progress.set_mode("expert")

    progress.mark_understood("app")

    assert progress.mode() == "expert"


def test_check_prompts_carry_both_voices() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)

    for region in graph.regions:
        for check in generate_checks(graph, region.id):
            assert set(check.prompt) == {"easy", "expert"}
            assert check.prompt["easy"].strip()
            assert check.prompt["expert"].strip()


def test_the_two_voices_ask_the_same_question_of_the_same_answer() -> None:
    graph = PythonAstAdapter().parse(FIXTURE)

    for region in graph.regions:
        for check in generate_checks(graph, region.id):
            public = check.public(passed=False)
            assert public["prompt_voices"] == check.prompt
            assert public["prompt"] == check.prompt["easy"], (
                "the legacy string keeps the shipped SPA rendering until phase 4"
            )
            assert public["multiple"] == (len(check.answer_ids) > 1)
            offered = {option["id"] for option in public["options"]}
            assert set(check.answer_ids) <= offered
            assert offered - set(check.answer_ids), "every check keeps a wrong option"


def test_easy_wording_keeps_the_qualifiers_expert_wording_relies_on() -> None:
    """A learner who reasons transitively must not be marked wrong.

    Regression for three sampleproj cases where dropping "directly" let a
    transitively-true option score as wrong: pkg.helpers/pkg.service removal
    impact both offer cli.launch (which breaks transitively via app.main);
    pkg.util removal impact offers app.main (breaks transitively via
    pkg.util.greet/pkg.helpers.log); shared's importer check offers app
    (imports shared transitively via pkg.service).
    """
    graph = PythonAstAdapter().parse(FIXTURE)

    for region_id in ("pkg.helpers", "pkg.service", "pkg.util"):
        impact = next(
            check
            for check in generate_checks(graph, region_id)
            if check.kind == "removal-impact"
        )
        assert "directly" in impact.prompt["easy"]

    importer = next(
        check for check in generate_checks(graph, "shared") if check.kind == "direct-importer"
    )
    assert "directly" in importer.prompt["easy"]

    first_call = next(
        check for check in generate_checks(graph, "app") if check.kind == "first-call"
    )
    assert "call" in first_call.prompt["easy"]
    assert "run" not in first_call.prompt["easy"]


def test_check_is_hashable_and_prompt_still_affects_equality() -> None:
    """`prompt` is a dict, so it must opt out of `__hash__` while staying in `__eq__`."""

    graph = PythonAstAdapter().parse(FIXTURE)
    check = generate_checks(graph, "app")[0]

    assert hash(check) == hash(check), "a frozen dataclass must stay hashable"

    reworded = replace(check, prompt={"easy": "different wording", "expert": "different wording"})
    assert reworded != check, "hash=False must not weaken equality"
    assert hash(reworded) == hash(check), "prompt must stay excluded from the hash"


def test_home_choice_survives_a_restart(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    progress_root = tmp_path / "progress"
    graph = PythonAstAdapter().parse(project)
    assert graph.selected_entrypoint is None

    CheckService(graph, ProgressStore(graph, progress_root)).select_entrypoint("beta")
    restarted = CheckService(graph, ProgressStore(graph, progress_root))
    hydrated = restarted.graph()

    assert hydrated.selected_entrypoint == "beta"
    assert next(region for region in hydrated.regions if region.id == "beta").home is True


def test_a_persisted_home_outside_the_parser_ranking_is_never_restored(
    tmp_path: Path,
) -> None:
    """A saved id the parser no longer ranks must be dropped, not invented back."""

    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    progress_root = tmp_path / "progress"
    graph = PythonAstAdapter().parse(project)
    ProgressStore(graph, progress_root).set_selected_entrypoint("deleted.module")

    restarted = CheckService(graph, ProgressStore(graph, progress_root))

    assert restarted.graph().selected_entrypoint is None


def test_an_explicit_home_outranks_a_persisted_one(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for module in ("alpha", "beta"):
        (project / f"{module}.py").write_text(
            'if __name__ == "__main__":\n    print("start")\n', encoding="utf-8"
        )
    progress_root = tmp_path / "progress"
    graph = PythonAstAdapter().parse(project)
    ProgressStore(graph, progress_root).set_selected_entrypoint("beta")
    explicit = PythonAstAdapter().parse(project, entrypoint="alpha")

    restarted = CheckService(explicit, ProgressStore(explicit, progress_root))

    assert restarted.graph().selected_entrypoint == "alpha"
