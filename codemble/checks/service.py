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
        self._graph = graph
        self._progress = progress or ProgressStore(graph)
        self._checks = {
            region.id: generate_checks(graph, region.id) for region in graph.regions
        }
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
        self._checks = {
            region.id: generate_checks(self._graph, region.id)
            for region in self._graph.regions
        }
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

        answer_labels = [
            option.label for option in check.options if option.id in check.answer_ids
        ]
        return {
            "correct": correct,
            "check_id": check.id,
            "answer_ids": list(check.answer_ids),
            "answer_labels": answer_labels,
            "evidence": list(check.evidence),
            "message": (
                "Correct. That answer is fixed by the parser graph."
                if correct
                else "Not yet. Re-read the graph relationship and try again."
            ),
            "region_understood": complete,
        }

    def _region_checks(self, region_id: str) -> tuple[Check, ...]:
        if region_id not in self._checks:
            raise UnknownCheckError(region_id)
        return self._checks[region_id]


def generate_checks(graph: Graph, region_id: str) -> tuple[Check, ...]:
    """Build up to four stable questions from parser-owned evidence."""

    if not any(region.id == region_id for region in graph.regions):
        raise UnknownCheckError(region_id)
    nodes = {node.id: node for node in graph.nodes}
    checks: list[Check] = []

    first_call = _first_call_check(graph, region_id, nodes)
    if first_call:
        checks.append(first_call)
    importer = _importer_check(graph, region_id, nodes)
    if importer:
        checks.append(importer)
    impact = _impact_check(graph, region_id, nodes)
    if impact:
        checks.append(impact)
    entrypoint = _entrypoint_check(graph, region_id, nodes)
    if entrypoint:
        checks.append(entrypoint)
    return tuple(check for check in checks if _proves_understanding(check))


def _proves_understanding(check: Check) -> bool:
    """Reject a question every option answers; passing it would prove nothing."""

    return bool({option.id for option in check.options} - set(check.answer_ids))


def _first_call_check(
    graph: Graph, region_id: str, nodes: dict[str, Node]
) -> Check | None:
    calls_by_source: dict[str, list[Edge]] = {}
    for edge in graph.edges:
        source = nodes.get(edge.src)
        if (
            edge.kind == "call"
            and edge.certain
            and not edge.external
            and source is not None
            and source.region == region_id
            and edge.dst in nodes
        ):
            calls_by_source.setdefault(edge.src, []).append(edge)
    if not calls_by_source:
        return None
    source_id = sorted(calls_by_source)[0]
    edge = min(calls_by_source[source_id], key=lambda item: (item.lineno, item.dst))
    answers = (edge.dst,)
    return _check(
        graph,
        region_id,
        "first-call",
        source_id,
        {
            "easy": f"Which piece of code does {source_id} call first?",
            "expert": f"Which structure does {source_id} call first?",
        },
        answers,
        _node_options(nodes, answers, kind="function"),
        (f"{nodes[source_id].file}:{edge.lineno}",),
    )


def _importer_check(
    graph: Graph, region_id: str, nodes: dict[str, Node]
) -> Check | None:
    incoming = sorted(
        (
            edge
            for edge in graph.edges
            if edge.kind == "import"
            and edge.certain
            and not edge.external
            and edge.dst == region_id
            and edge.src in nodes
        ),
        key=lambda edge: (edge.src, edge.lineno),
    )
    if incoming:
        answers = tuple(sorted({edge.src for edge in incoming}))
        return _check(
            graph,
            region_id,
            "direct-importer",
            region_id,
            {
                "easy": f"Which of your files brings in {region_id} directly?",
                "expert": f"Which project module imports {region_id} directly?",
            },
            answers,
            _node_options(nodes, answers, kind="module"),
            tuple(f"{nodes[edge.src].file}:{edge.lineno}" for edge in incoming),
        )

    outgoing = sorted(
        (
            edge
            for edge in graph.edges
            if edge.kind == "import"
            and edge.certain
            and not edge.external
            and edge.src == region_id
            and edge.dst in nodes
        ),
        key=lambda edge: (edge.lineno, edge.dst),
    )
    if not outgoing:
        return None
    first = outgoing[0]
    answers = (first.dst,)
    return _check(
        graph,
        region_id,
        "direct-importer",
        region_id,
        {
            "easy": f"Which of your files does {region_id} bring in first?",
            "expert": f"Which project module does {region_id} import first?",
        },
        answers,
        _node_options(nodes, answers, kind="module"),
        (f"{nodes[region_id].file}:{first.lineno}",),
    )


def _impact_check(
    graph: Graph, region_id: str, nodes: dict[str, Node]
) -> Check | None:
    callers_by_target: dict[str, list[Edge]] = {}
    for edge in graph.edges:
        target = nodes.get(edge.dst)
        if (
            edge.kind == "call"
            and edge.certain
            and not edge.external
            and target is not None
            and target.region == region_id
            and edge.src in nodes
        ):
            callers_by_target.setdefault(edge.dst, []).append(edge)
    if not callers_by_target:
        return None
    target_id = sorted(
        callers_by_target,
        key=lambda candidate: (-len(callers_by_target[candidate]), candidate),
    )[0]
    callers = sorted(callers_by_target[target_id], key=lambda edge: (edge.src, edge.lineno))
    answers = tuple(sorted({edge.src for edge in callers}))
    return _check(
        graph,
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
        _node_options(nodes, answers, kind="function"),
        tuple(f"{nodes[edge.src].file}:{edge.lineno}" for edge in callers),
    )


def _entrypoint_check(
    graph: Graph, region_id: str, nodes: dict[str, Node]
) -> Check | None:
    ranked = [candidate for candidate in graph.entrypoint_candidates if candidate in nodes]
    selected = graph.selected_entrypoint
    if not ranked or selected is None or nodes[selected].region != region_id:
        return None
    answers = (selected,)
    pool = ranked + [node.id for node in graph.nodes if node.id not in ranked]
    return _check(
        graph,
        region_id,
        "entrypoint",
        selected,
        {
            "easy": "Which part of your code does the program start from?",
            "expert": "Which parser-ranked structure is selected as Home for this run?",
        },
        answers,
        _options(nodes, answers, pool),
        (f"{nodes[selected].file}:{nodes[selected].lineno}",),
    )


def _node_options(
    nodes: dict[str, Node], answers: tuple[str, ...], *, kind: str
) -> tuple[CheckOption, ...]:
    pool = [node.id for node in nodes.values() if node.kind == kind]
    if len(set(pool) | set(answers)) < 2:
        pool = list(nodes)
    return _options(nodes, answers, pool)


def _options(
    nodes: dict[str, Node], answers: tuple[str, ...], pool: list[str]
) -> tuple[CheckOption, ...]:
    """Offer every answer plus wrong options, or nothing if none exist.

    The ceiling must clear ``len(answers)``; capping at four alone offered a
    multi-answer check no wrong option, so selecting everything always passed.
    """

    candidates = list(answers)
    ceiling = max(4, len(answers) + _MINIMUM_DISTRACTORS)
    for candidate in sorted(set(pool)):
        if candidate not in candidates and len(candidates) < ceiling:
            candidates.append(candidate)
    if len(candidates) == len(answers):
        return ()
    return tuple(CheckOption(candidate, nodes[candidate].id) for candidate in candidates)


def _check(
    graph: Graph,
    region_id: str,
    kind: CheckKind,
    subject: str,
    prompt: dict[str, str],
    answers: tuple[str, ...],
    options: tuple[CheckOption, ...],
    evidence: tuple[str, ...],
) -> Check:
    check_id = hashlib.sha256(
        f"{graph.schema_version}|{region_id}|{kind}|{subject}".encode()
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
