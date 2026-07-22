"""Deterministic active checks whose answers come only from the graph."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from codemble.adapters.base import Edge, Graph, Node
from codemble.graph.layout import with_entrypoint
from codemble.progress import ProgressStore

CheckKind = Literal["first-call", "direct-importer", "removal-impact", "entrypoint"]

# Wrong options a check offers beyond its answers, when the graph holds that many.
_MINIMUM_DISTRACTORS = 2


class UnknownCheckError(KeyError):
    """Raised for a region or check absent from the current graph."""


class InvalidCheckSubmission(ValueError):
    """Raised when a submitted option was not offered by the check."""


@dataclass(frozen=True, slots=True)
class CheckOption:
    id: str
    label: str


@dataclass(frozen=True, slots=True)
class Check:
    id: str
    region_id: str
    kind: CheckKind
    prompt: dict[str, str] = field(hash=False)
    options: tuple[CheckOption, ...]
    answer_ids: tuple[str, ...]
    evidence: tuple[str, ...]

    def public(self, *, passed: bool) -> dict[str, object]:
        """Serialize the question without exposing its graph-derived answer."""

        return {
            "id": self.id,
            "kind": self.kind,
            "prompt_voices": self.prompt,
            "multiple": len(self.answer_ids) > 1,
            "options": [
                {"id": option.id, "label": option.label} for option in self.options
            ],
            "passed": passed,
        }


class CheckService:
    """Generate, validate, and persist one graph-owned region check flow."""

    def __init__(self, graph: Graph, progress: ProgressStore | None = None) -> None:
        self._progress = progress or ProgressStore(graph)
        self._graph = _restored_entrypoint(graph, self._progress)
        self._checks = _suites(self._graph)
        self._passed: dict[str, set[str]] = {}

    @property
    def progress(self) -> ProgressStore:
        """Expose the local progress store for preference reads and writes."""

        return self._progress

    def graph(self) -> Graph:
        """Return render data hydrated from currently valid local progress."""

        hydrated = self._progress.hydrated_graph()
        return (
            with_entrypoint(hydrated, self._graph.selected_entrypoint)
            if self._graph.selected_entrypoint
            else hydrated
        )

    def select_entrypoint(self, node_id: str) -> Graph:
        """Apply an explicit parser-ranked Home choice to graph and check suites."""

        self._graph = with_entrypoint(self._graph, node_id)
        self._progress.set_selected_entrypoint(node_id)
        self._checks = _suites(self._graph)
        return self.graph()

    def for_region(self, region_id: str) -> dict[str, object]:
        """Return a region suite with answer values withheld."""

        checks = self._region_checks(region_id)
        understood = region_id in self._progress.understood_regions()
        passed = self._passed.get(region_id, set())
        return {
            "region_id": region_id,
            "region_understood": understood,
            "checks": [
                check.public(passed=understood or check.id in passed) for check in checks
            ],
        }

    def submit(
        self, region_id: str, check_id: str, selected_ids: list[str]
    ) -> dict[str, object]:
        """Score exact option IDs against the immutable generated answer."""

        checks = self._region_checks(region_id)
        check = next((candidate for candidate in checks if candidate.id == check_id), None)
        if check is None:
            raise UnknownCheckError(check_id)
        offered = {option.id for option in check.options}
        selected = set(selected_ids)
        if not selected or not selected <= offered:
            raise InvalidCheckSubmission("Select one or more offered answers.")

        correct = selected == set(check.answer_ids)
        if correct:
            self._passed.setdefault(region_id, set()).add(check.id)
        passed = self._passed.get(region_id, set())
        complete = bool(checks) and all(candidate.id in passed for candidate in checks)
        if complete:
            self._progress.mark_understood(region_id)

        result: dict[str, object] = {
            "correct": correct,
            "check_id": check.id,
            "message": (
                "Correct. That answer is fixed by the parser graph."
                if correct
                else "Not yet. Re-read the relationship in your own code and try again."
            ),
            "region_understood": complete,
        }
        if not correct:
            # A miss returns no answer and no citations. An importer check
            # cites the very files that are its answer, so handing either back
            # let the next submission replay what the screen had just shown --
            # and a region lit that way proves nothing.
            return result
        result["answer_ids"] = list(check.answer_ids)
        result["answer_labels"] = [
            option.label for option in check.options if option.id in check.answer_ids
        ]
        result["evidence"] = list(check.evidence)
        return result

    def _region_checks(self, region_id: str) -> tuple[Check, ...]:
        if region_id not in self._checks:
            raise UnknownCheckError(region_id)
        return self._checks[region_id]


def _restored_entrypoint(graph: Graph, progress: ProgressStore) -> Graph:
    """Re-apply a persisted Home only when the parser still ranks it.

    An explicit CLI or picker choice wins outright, and a saved id the parser
    no longer ranks is dropped rather than invented back into the graph.
    """

    if graph.selected_entrypoint is not None:
        return graph
    saved = progress.selected_entrypoint()
    if saved is None or saved not in graph.entrypoint_candidates:
        return graph
    return with_entrypoint(graph, saved)


class _CheckIndex:
    """One O(nodes + edges) pass over the graph that every region reads.

    Generating each region's suite independently re-scanned ``graph.edges``
    up to four times, so binding a project cost O(regions x edges) before the
    galaxy could render.  Every bucket below is filled in ``graph.edges``
    order, which is what the per-region scans saw, so the stable sorts and
    ``min`` calls downstream break ties exactly as they did before.
    """

    __slots__ = (
        "graph",
        "nodes",
        "region_ids",
        "all_ids",
        "ids_by_kind",
        "calls_out_by_region",
        "calls_in_by_region",
        "imports_into",
        "imports_out",
        "ranked_entrypoints",
    )

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.nodes: dict[str, Node] = {node.id: node for node in graph.nodes}
        self.region_ids = frozenset(region.id for region in graph.regions)
        self.all_ids = tuple(sorted(self.nodes))
        by_kind: dict[str, list[str]] = {}
        for node in self.nodes.values():
            by_kind.setdefault(node.kind, []).append(node.id)
        self.ids_by_kind = {kind: tuple(sorted(ids)) for kind, ids in by_kind.items()}
        self.calls_out_by_region: dict[str, dict[str, list[Edge]]] = {}
        self.calls_in_by_region: dict[str, dict[str, list[Edge]]] = {}
        self.imports_into: dict[str, list[Edge]] = {}
        self.imports_out: dict[str, list[Edge]] = {}
        for edge in graph.edges:
            if not edge.certain or edge.external:
                continue
            if edge.kind == "call":
                source = self.nodes.get(edge.src)
                target = self.nodes.get(edge.dst)
                if source is None or target is None:
                    continue
                self.calls_out_by_region.setdefault(source.region, {}).setdefault(
                    edge.src, []
                ).append(edge)
                self.calls_in_by_region.setdefault(target.region, {}).setdefault(
                    edge.dst, []
                ).append(edge)
            elif edge.kind == "import":
                if edge.src in self.nodes:
                    self.imports_into.setdefault(edge.dst, []).append(edge)
                if edge.dst in self.nodes:
                    self.imports_out.setdefault(edge.src, []).append(edge)
        self.ranked_entrypoints = [
            candidate
            for candidate in graph.entrypoint_candidates
            if candidate in self.nodes
        ]


def _suites(graph: Graph) -> dict[str, tuple[Check, ...]]:
    """Generate every region's suite from a single shared index."""

    index = _CheckIndex(graph)
    return {region.id: _region_checks(index, region.id) for region in graph.regions}


def generate_checks(graph: Graph, region_id: str) -> tuple[Check, ...]:
    """Build up to four stable questions from parser-owned evidence."""

    return _region_checks(_CheckIndex(graph), region_id)


def _region_checks(index: _CheckIndex, region_id: str) -> tuple[Check, ...]:
    if region_id not in index.region_ids:
        raise UnknownCheckError(region_id)
    checks: list[Check] = []
    for build in (_first_call_check, _importer_check, _impact_check, _entrypoint_check):
        check = build(index, region_id)
        if check:
            checks.append(check)
    return tuple(check for check in checks if _proves_understanding(check))


def _proves_understanding(check: Check) -> bool:
    """Reject a question every option answers; passing it would prove nothing."""

    return bool({option.id for option in check.options} - set(check.answer_ids))


def _first_call_check(index: _CheckIndex, region_id: str) -> Check | None:
    calls_by_source = index.calls_out_by_region.get(region_id)
    if not calls_by_source:
        return None
    source_id = sorted(calls_by_source)[0]
    edge = min(calls_by_source[source_id], key=lambda item: (item.lineno, item.dst))
    answers = (edge.dst,)
    return _check(
        index,
        region_id,
        "first-call",
        source_id,
        {
            "easy": f"Which piece of code does {source_id} call first?",
            "expert": f"Which structure does {source_id} call first?",
        },
        answers,
        _node_options(index, answers, kind="function"),
        (f"{index.nodes[source_id].file}:{edge.lineno}",),
    )


def _importer_check(index: _CheckIndex, region_id: str) -> Check | None:
    incoming = sorted(
        index.imports_into.get(region_id, ()),
        key=lambda edge: (edge.src, edge.lineno),
    )
    if incoming:
        answers = tuple(sorted({edge.src for edge in incoming}))
        return _check(
            index,
            region_id,
            "direct-importer",
            region_id,
            {
                "easy": f"Which of your files brings in {region_id} directly?",
                "expert": f"Which project module imports {region_id} directly?",
            },
            answers,
            _node_options(index, answers, kind="module"),
            tuple(f"{index.nodes[edge.src].file}:{edge.lineno}" for edge in incoming),
        )

    outgoing = sorted(
        index.imports_out.get(region_id, ()),
        key=lambda edge: (edge.lineno, edge.dst),
    )
    if not outgoing:
        return None
    first = outgoing[0]
    answers = (first.dst,)
    return _check(
        index,
        region_id,
        "direct-importer",
        region_id,
        {
            "easy": f"Which of your files does {region_id} bring in first?",
            "expert": f"Which project module does {region_id} import first?",
        },
        answers,
        _node_options(index, answers, kind="module"),
        (f"{index.nodes[region_id].file}:{first.lineno}",),
    )


def _impact_check(index: _CheckIndex, region_id: str) -> Check | None:
    callers_by_target = index.calls_in_by_region.get(region_id)
    if not callers_by_target:
        return None
    # Distinct callers, never call sites: a private helper called five times
    # from one function must not outrank a utility called from three modules.
    # Matches Node.centrality; see codemble/graph/finalize.py.
    target_id = sorted(
        callers_by_target,
        key=lambda candidate: (
            -len({edge.src for edge in callers_by_target[candidate]}),
            candidate,
        ),
    )[0]
    callers = sorted(callers_by_target[target_id], key=lambda edge: (edge.src, edge.lineno))
    answers = tuple(sorted({edge.src for edge in callers}))
    return _check(
        index,
        region_id,
        "removal-impact",
        target_id,
        {
            "easy": f"Which piece of code uses {target_id} directly and would break if it disappeared?",
            "expert": (
                f"Which structure directly depends on {target_id} "
                "and could break if it disappeared?"
            ),
        },
        answers,
        _node_options(index, answers, kind="function"),
        tuple(f"{index.nodes[edge.src].file}:{edge.lineno}" for edge in callers),
    )


def _entrypoint_check(index: _CheckIndex, region_id: str) -> Check | None:
    ranked = index.ranked_entrypoints
    selected = index.graph.selected_entrypoint
    if not ranked or selected is None or index.nodes[selected].region != region_id:
        return None
    answers = (selected,)
    # The old pool was the ranked candidates followed by every other node, and
    # _options only ever consumed sorted(set(pool)) -- which is exactly every
    # node id, already sorted and unique on the index.
    return _check(
        index,
        region_id,
        "entrypoint",
        selected,
        {
            "easy": "Which part of your code does the program start from?",
            "expert": "Which parser-ranked structure is selected as Home for this run?",
        },
        answers,
        _options(index, answers, index.all_ids),
        (f"{index.nodes[selected].file}:{index.nodes[selected].lineno}",),
    )


def _node_options(
    index: _CheckIndex, answers: tuple[str, ...], *, kind: str
) -> tuple[CheckOption, ...]:
    pool = index.ids_by_kind.get(kind, ())
    if len(set(pool) | set(answers)) < 2:
        pool = index.all_ids
    return _options(index, answers, pool)


def _options(
    index: _CheckIndex, answers: tuple[str, ...], pool: tuple[str, ...]
) -> tuple[CheckOption, ...]:
    """Offer every answer plus wrong options, or nothing if none exist.

    ``pool`` arrives from the index already sorted and unique, so this walks it
    directly and stops once the ceiling is reached; the previous
    ``sorted(set(pool))`` re-sorted every node id on every check.

    The ceiling must clear ``len(answers)``; capping at four alone offered a
    multi-answer check no wrong option, so selecting everything always passed.
    """

    candidates = list(answers)
    ceiling = max(4, len(answers) + _MINIMUM_DISTRACTORS)
    for candidate in pool:
        if len(candidates) >= ceiling:
            break
        if candidate not in candidates:
            candidates.append(candidate)
    if len(candidates) == len(answers):
        return ()
    return tuple(
        CheckOption(candidate, index.nodes[candidate].id) for candidate in candidates
    )


def _check(
    index: _CheckIndex,
    region_id: str,
    kind: CheckKind,
    subject: str,
    prompt: dict[str, str],
    answers: tuple[str, ...],
    options: tuple[CheckOption, ...],
    evidence: tuple[str, ...],
) -> Check:
    check_id = hashlib.sha256(
        f"{index.graph.schema_version}|{region_id}|{kind}|{subject}".encode()
    ).hexdigest()[:16]
    return Check(
        id=check_id,
        region_id=region_id,
        kind=kind,
        prompt=prompt,
        options=options,
        answer_ids=answers,
        evidence=evidence,
    )


__all__ = [
    "Check",
    "CheckKind",
    "CheckService",
    "InvalidCheckSubmission",
    "UnknownCheckError",
    "generate_checks",
]
