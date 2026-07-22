"""Graph-only check generation and file-scoped progress contracts."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter
from codemble.checks import CheckService, generate_checks
from codemble.progress import ProgressStore

FIXTURE = Path(__file__).parent / "fixtures" / "sampleproj"
POLYGLOT_FIXTURE = Path(__file__).parent / "fixtures" / "polyglot"
IMPACT_FIXTURE = Path(__file__).parent / "fixtures" / "impact"
GOLDEN = Path(__file__).parent / "fixtures" / "check_suites.json"


def _suite_shapes(graph) -> dict:  # type: ignore[no-untyped-def]
    """Serialize every region's whole suite, answers included."""

    return {
        region.id: [
            {
                "id": check.id,
                "kind": check.kind,
                "prompt": check.prompt,
                "options": [
                    {"id": option.id, "label": option.label} for option in check.options
                ],
                "answer_ids": list(check.answer_ids),
                "evidence": list(check.evidence),
            }
            for check in generate_checks(graph, region.id)
        ]
        for region in graph.regions
    }


def test_generated_check_suites_match_the_pinned_golden() -> None:
    """A performance change to generation must not move one byte of a suite.

    ``impact`` is in the golden on purpose. Neither sampleproj nor polyglot
    contains a single target called more than once from one caller, so both
    rank identically whether the generator counts call sites or distinct
    callers -- a golden built from those two alone would pass while silently
    reintroducing the bug b7dc5aa fixed.
    """

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert _suite_shapes(PythonAstAdapter().parse(FIXTURE)) == golden["sampleproj"]
    assert (
        _suite_shapes(JavaScriptTypeScriptAdapter().parse(POLYGLOT_FIXTURE))
        == golden["polyglot"]
    )
    assert _suite_shapes(PythonAstAdapter().parse(IMPACT_FIXTURE)) == golden["impact"]


def test_the_service_generates_the_same_suites_as_the_public_function(
    tmp_path: Path,
) -> None:
    """The bound service and the one-off function must never disagree."""

    graph = PythonAstAdapter().parse(FIXTURE)
    service = CheckService(graph, ProgressStore(graph, tmp_path))

    for region in graph.regions:
        suite = service.for_region(region.id)["checks"]
        expected = generate_checks(graph, region.id)
        assert [question["id"] for question in suite] == [check.id for check in expected]
        assert [question["options"] for question in suite] == [
            [{"id": option.id, "label": option.label} for option in check.options]
            for check in expected
        ]


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


def test_a_missed_check_never_hands_back_its_own_answer(tmp_path: Path) -> None:
    """Revealing the answer on a miss lets a resubmission light a region.

    The evidence citations are withheld too: an importer check cites the very
    files that are its answer, so returning them is the same reveal by another
    name. Both are returned once the learner has proven the answer.
    """

    graph = PythonAstAdapter().parse(FIXTURE)
    service = CheckService(graph, ProgressStore(graph, tmp_path))
    check = generate_checks(graph, "app")[0]
    wrong = next(option.id for option in check.options if option.id not in check.answer_ids)

    missed = service.submit("app", check.id, [wrong])

    assert missed["correct"] is False
    assert "answer_ids" not in missed
    assert "answer_labels" not in missed
    assert "evidence" not in missed
    assert not any(
        answer in str(missed) for answer in check.answer_ids
    ), f"the miss response still names an answer: {missed}"

    proven = service.submit("app", check.id, list(check.answer_ids))
    assert proven["correct"] is True
    assert proven["answer_ids"] == list(check.answer_ids)
    assert proven["evidence"] == list(check.evidence)


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


def test_removal_impact_targets_the_most_depended_on_structure() -> None:
    """Call sites are evidence; distinct callers are the measure of impact.

    Ranking by call sites let a private helper called five times from one
    function outrank a utility called from three modules, so the question
    shipped with a single correct answer — the weakest form of "what depends
    on this?". The decoy sorts first alphabetically, so passing this test
    requires the ranking, not the tiebreak.

    The fixture is checked in rather than built here because the golden suite
    comparison needs the same divergence; see the golden test's docstring.
    """

    graph = PythonAstAdapter().parse(IMPACT_FIXTURE)

    impact = next(
        check
        for check in generate_checks(graph, "helpers")
        if check.kind == "removal-impact"
    )

    assert impact.answer_ids == ("alpha.go", "beta.go", "gamma.go"), (
        "helpers.log has three distinct callers; helpers.cache_key has one "
        "caller across five call sites"
    )
    assert "helpers.log" in impact.prompt["expert"]
    assert len(impact.evidence) == 4, "every call site stays cited, including both in alpha"
    assert sum("alpha.py" in item for item in impact.evidence) == 2


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
            assert "prompt" not in public, (
                "phase 4 retired the legacy string; prompt_voices is now the only source"
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

    # A never-existed id is one edge case; a real node the parser simply never
    # ranked as an entrypoint is the one the guard actually exists for. A
    # mutant that checks `graph.nodes` membership instead of
    # `entrypoint_candidates` would restore this one, since "shared" is a
    # genuine node -- only the ranking says it can't be Home. The fixture
    # project has one unambiguous rank-0 candidate ("app"), which
    # `finalize_graph` auto-selects, so force the "no Home chosen yet" state
    # the guard actually runs under -- exactly like an ambiguous reparse --
    # while keeping the fixture's real parser-derived nodes and candidates.
    fixture_graph = replace(PythonAstAdapter().parse(FIXTURE), selected_entrypoint=None)
    assert "shared" in {node.id for node in fixture_graph.nodes}
    assert "shared" not in fixture_graph.entrypoint_candidates
    ProgressStore(fixture_graph, progress_root).set_selected_entrypoint("shared")

    fixture_restarted = CheckService(fixture_graph, ProgressStore(fixture_graph, progress_root))

    assert fixture_restarted.graph().selected_entrypoint is None


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


def test_check_generation_walks_every_edge_once(tmp_path: Path) -> None:
    """Per-region full-edge scans are the bind freeze at ~1,000 files.

    Binding generated every region's suite by re-scanning ``graph.edges`` up
    to four times per region, so the learner waited on O(regions x edges)
    while the galaxy stayed blank.
    """

    graph = PythonAstAdapter().parse(FIXTURE)
    passes = 0

    class _CountingEdges(tuple):  # noqa: SLOT001 - a plain tuple is the point
        """A real tuple that records how many times a consumer walked it."""

        def __iter__(self):  # type: ignore[no-untyped-def]
            nonlocal passes
            passes += 1
            return super().__iter__()

    counted = replace(graph, edges=_CountingEdges(graph.edges))
    # The store is built from the uncounted graph, so every recorded pass
    # belongs to check generation and none to progress hydration.
    CheckService(counted, ProgressStore(graph, tmp_path))

    assert len(graph.regions) > 1
    assert passes == 1
