"""Evidence-bounded feature journeys shared by Easy and Expert modes.

The journey layer only composes parser-owned nodes, edges, and role evidence.
It never inspects source text, guesses framework meaning from names, or lets a
possible relationship enter the canonical route.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path

from codemble.adapters.base import Edge, Graph, Node, RoleEvidence
from codemble.graph.impact import BlastRadiusIndex

JOURNEY_SCHEMA_VERSION = 1
MAX_PRESENTED_STEPS = 32
MAX_POSSIBLE_FRONTIER = 12
_APPLICATION_ROLES = frozenset({"application-entry", "route-handler", "ui-renderer"})
_ROLE_ORDER = {
    "application-entry": 0,
    "route-handler": 1,
    "ui-renderer": 2,
    "test": 3,
}


class LearningJourneyIndex:
    """Per-graph indexes for repeated local study requests."""

    def __init__(
        self,
        graph: Graph,
        *,
        impact_index: BlastRadiusIndex | None = None,
    ) -> None:
        self.graph = graph
        self.nodes = {node.id: node for node in graph.nodes}
        self.modules_by_region: dict[str, Node] = {}
        for node in sorted(graph.nodes, key=lambda item: item.id):
            if node.kind == "module":
                self.modules_by_region.setdefault(node.region, node)
        self.certain_imports = _adjacency(graph.edges, self.nodes, "import", certain=True)
        self.certain_calls = _adjacency(graph.edges, self.nodes, "call", certain=True)
        self.reverse_certain_imports = _reverse_adjacency(self.certain_imports)
        self.reverse_certain_calls = _reverse_adjacency(self.certain_calls)
        self.certain_pairs = frozenset(
            (edge.src, edge.dst, edge.kind)
            for edge in graph.edges
            if edge.certain and not edge.external
        )
        self.possible_edges = tuple(
            edge
            for edge in graph.edges
            if not edge.certain
            and not edge.external
            and edge.src in self.nodes
            and edge.dst in self.nodes
        )
        external_by_source: dict[str, list[Edge]] = {}
        for edge in graph.edges:
            if edge.external and edge.src in self.nodes:
                external_by_source.setdefault(edge.src, []).append(edge)
        self.external_by_source = {
            source: tuple(edges) for source, edges in external_by_source.items()
        }
        self.impact = impact_index or BlastRadiusIndex(graph)
        self.fingerprint_seed = {
            "schema": JOURNEY_SCHEMA_VERSION,
            "project_root": Path(graph.project_root).resolve().as_posix(),
            "file_hashes": sorted(graph.file_hashes.items()),
        }

    def build(self, node_id: str) -> dict[str, object]:
        target = self.nodes.get(node_id)
        if target is None:
            raise KeyError(node_id)
        fingerprint = _digest(
            {**self.fingerprint_seed, "home": self.graph.selected_entrypoint, "target": node_id}
        )
        result = _empty_result(target, fingerprint)

        if target.partial:
            result["break"] = _break_at_node(
                "target-source-partial",
                "The selected source file could not be fully parsed, so no route is claimed.",
                target,
            )
            return result

        home = self.nodes.get(self.graph.selected_entrypoint or "")
        if home is None:
            result["break"] = {
                "reason": "home-not-selected",
                "message": "Choose a parser-ranked Home before tracing this feature.",
            }
            return result
        if home.partial:
            result["break"] = _break_at_node(
                "home-source-partial",
                "The selected Home file could not be fully parsed.",
                home,
            )
            return result

        home_module = self._module_for(home)
        target_module = self._module_for(target)
        home_step = _node_step("home", "home", home, is_target=home.id == target.id)
        result["home_context"] = home_step
        canonical = [home_step]

        if target.kind == "module":
            corridor = _path(home_module.id, target_module.id, self.certain_imports)
            if corridor is None:
                result.update(
                    status="broken",
                    runtime_status="not_applicable",
                    steps=canonical,
                    break_=_break_at_node(
                        "file-route-not-proven",
                        "No certain import route connects Home to this file.",
                        target,
                    ),
                )
                result["break"] = result.pop("break_")
            else:
                file_steps = [self._edge_step(edge, "file-corridor", target.id) for edge in corridor]
                canonical.extend(file_steps)
                result.update(
                    status="complete",
                    runtime_status="not_applicable",
                    file_corridor=file_steps,
                    steps=canonical,
                    break_=None,
                )
                result["break"] = result.pop("break_")
            return self._finish(result, target, canonical)

        chosen = self._choose_surface(home_module, target)
        if chosen is None:
            corridor = _path(home_module.id, target_module.id, self.certain_imports)
            file_steps = (
                [self._edge_step(edge, "file-corridor", target.id) for edge in corridor]
                if corridor is not None
                else []
            )
            canonical.extend(file_steps)
            result.update(
                file_corridor=file_steps,
                steps=canonical,
                break_=_break_at_node(
                    "application-surface-not-proven",
                    "The parser found the file, but not a proven application surface that calls this structure.",
                    target,
                ),
            )
            result["break"] = result.pop("break_")
            return self._finish(result, target, canonical)

        role, corridor, runtime = chosen
        file_steps = [self._edge_step(edge, "file-corridor", target.id) for edge in corridor]
        surface_node = self.nodes[role.node_id]
        surface_step = _role_step(role, surface_node, is_target=surface_node.id == target.id)
        runtime_steps = [self._edge_step(edge, "runtime", target.id) for edge in runtime]
        canonical.extend(file_steps)
        canonical.append(surface_step)
        canonical.extend(runtime_steps)
        result.update(
            status="complete",
            runtime_status="complete",
            file_corridor=file_steps,
            application_surface=surface_step,
            runtime_steps=runtime_steps,
            steps=canonical,
            break_=None,
        )
        result["break"] = result.pop("break_")
        return self._finish(result, target, canonical)

    def _module_for(self, node: Node) -> Node:
        if node.kind == "module":
            return node
        module = self.modules_by_region.get(node.region)
        if module is None:
            raise KeyError(f"node has no parser module: {node.id}")
        return module

    def _choose_surface(
        self,
        home_module: Node,
        target: Node,
    ) -> tuple[RoleEvidence, list[Edge], list[Edge]] | None:
        candidates: list[tuple[tuple[object, ...], RoleEvidence, list[Edge], list[Edge]]] = []
        for evidence in self.graph.role_evidence:
            if evidence.role not in _APPLICATION_ROLES:
                continue
            surface = self.nodes.get(evidence.node_id)
            if surface is None or surface.partial:
                continue
            surface_module = self._module_for(surface)
            corridor = _path(home_module.id, surface_module.id, self.certain_imports)
            runtime = _path(surface.id, target.id, self.certain_calls)
            if corridor is None or runtime is None:
                continue
            key = (
                len(corridor) + len(runtime),
                _ROLE_ORDER[evidence.role],
                evidence.file,
                evidence.lineno,
                evidence.end_lineno,
                evidence.rule_id,
                evidence.node_id,
            )
            candidates.append((key, evidence, corridor, runtime))
        if not candidates:
            return None
        _, evidence, corridor, runtime = min(candidates, key=lambda item: item[0])
        return evidence, corridor, runtime

    def _edge_step(self, edge: Edge, layer: str, target_id: str) -> dict[str, object]:
        source = self.nodes[edge.src]
        destination = self.nodes[edge.dst]
        payload = {
            "layer": layer,
            "relation": edge.kind,
            "source_node_id": source.id,
            "node_id": destination.id,
            "name": destination.name,
            "kind": destination.kind,
            "language": destination.language,
            "certain": True,
            "observation": _citation(source.file, edge.lineno),
            "declaration": _citation(destination.file, destination.lineno),
            "citation": f"{destination.file}:{destination.lineno}",
            "is_target": destination.id == target_id,
        }
        payload["id"] = _step_id(payload)
        return payload

    def _finish(
        self,
        result: dict[str, object],
        target: Node,
        canonical: list[dict[str, object]],
    ) -> dict[str, object]:
        possible, possible_omitted = self._possible_frontier(target)
        result["possible_frontier"] = possible
        result["possible_frontier_truncated"] = possible_omitted > 0
        result["possible_frontier_omitted_count"] = possible_omitted
        result["external_boundaries"] = self._external_boundaries(canonical)
        result["verification_candidates"] = self._verification_candidates(target.id)
        if len(canonical) > MAX_PRESENTED_STEPS:
            result["steps"] = canonical[:MAX_PRESENTED_STEPS]
            result["truncated"] = True
            result["omitted_step_count"] = len(canonical) - MAX_PRESENTED_STEPS
            result["status"] = "truncated"
            result["break"] = {
                "reason": "presentation-limit",
                "message": "The proven route continues beyond the displayed step limit.",
            }
        return result

    def _possible_frontier(self, target: Node) -> tuple[list[dict[str, object]], int]:
        call_ancestors = _reverse_reachable(target.id, self.reverse_certain_calls)
        target_module = self._module_for(target)
        import_ancestors = _reverse_reachable(
            target_module.id, self.reverse_certain_imports
        )
        home = self.nodes.get(self.graph.selected_entrypoint or "")
        if home is None:
            return [], 0
        certain_import_sources = _reachable(self._module_for(home).id, self.certain_imports)
        certain_runtime_sources: set[str] = set()
        for evidence in self.graph.role_evidence:
            if evidence.role not in _APPLICATION_ROLES:
                continue
            surface = self.nodes.get(evidence.node_id)
            if surface is None or self._module_for(surface).id not in certain_import_sources:
                continue
            certain_runtime_sources.update(_reachable(surface.id, self.certain_calls))
        entries: list[dict[str, object]] = []
        for edge in self.possible_edges:
            if (edge.src, edge.dst, edge.kind) in self.certain_pairs:
                continue
            relevant = (
                edge.kind == "call"
                and edge.src in certain_runtime_sources
                and edge.dst in call_ancestors
            ) or (
                edge.kind == "import"
                and edge.src in certain_import_sources
                and edge.dst in import_ancestors
            )
            if not relevant:
                continue
            source = self.nodes[edge.src]
            destination = self.nodes[edge.dst]
            entries.append(
                {
                    "relation": edge.kind,
                    "source_node_id": source.id,
                    "target_node_id": destination.id,
                    "certain": False,
                    "observation": _citation(source.file, edge.lineno),
                    "declaration": _citation(destination.file, destination.lineno),
                }
            )
        entries.sort(
            key=lambda item: (
                item["relation"],
                item["observation"]["file"],
                item["observation"]["line"],
                item["source_node_id"],
                item["target_node_id"],
            )
        )
        omitted = max(0, len(entries) - MAX_POSSIBLE_FRONTIER)
        return entries[:MAX_POSSIBLE_FRONTIER], omitted

    def _external_boundaries(
        self,
        canonical: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        route_nodes = {str(step["node_id"]) for step in canonical}
        entries = []
        for source_id in route_nodes:
            source = self.nodes.get(source_id)
            if source is None:
                continue
            for edge in self.external_by_source.get(source_id, ()):
                entries.append(
                    {
                        "source_node_id": edge.src,
                        "external_target": edge.dst,
                        "relation": edge.kind,
                        "certain": edge.certain,
                        "observation": _citation(source.file, edge.lineno),
                        "declaration": None,
                    }
                )
        return sorted(
            entries,
            key=lambda item: (
                item["observation"]["file"],
                item["observation"]["line"],
                item["external_target"],
            ),
        )

    def _verification_candidates(self, target_id: str) -> list[dict[str, object]]:
        affects = {
            str(item["node_id"]): item
            for item in self.impact.build(target_id)["affects"]
        }
        candidates = []
        for evidence in self.graph.role_evidence:
            if evidence.role != "test" or evidence.node_id not in affects:
                continue
            node = self.nodes[evidence.node_id]
            impact = affects[evidence.node_id]
            candidates.append(
                {
                    "node_id": node.id,
                    "name": node.name,
                    "depth": impact["depth"],
                    "certain": impact["certain"],
                    "role_observation": _citation(evidence.file, evidence.lineno),
                    "declaration": _citation(node.file, node.lineno),
                }
            )
        return sorted(
            candidates,
            key=lambda item: (item["depth"], not item["certain"], item["node_id"]),
        )


def learning_journey(graph: Graph, node_id: str) -> dict[str, object]:
    """Return one deterministic journey payload for either audience mode."""

    return LearningJourneyIndex(graph).build(node_id)


def _adjacency(
    edges: tuple[Edge, ...],
    nodes: dict[str, Node],
    kind: str,
    *,
    certain: bool,
) -> dict[str, tuple[Edge, ...]]:
    grouped: dict[str, list[Edge]] = {}
    for edge in edges:
        if (
            edge.kind != kind
            or edge.certain is not certain
            or edge.external
            or edge.src not in nodes
            or edge.dst not in nodes
        ):
            continue
        grouped.setdefault(edge.src, []).append(edge)
    return {
        source: tuple(sorted(items, key=lambda edge: (edge.dst, edge.lineno)))
        for source, items in grouped.items()
    }


def _path(start: str, target: str, adjacency: dict[str, tuple[Edge, ...]]) -> list[Edge] | None:
    if start == target:
        return []
    queue = deque([start])
    previous: dict[str, tuple[str, Edge]] = {}
    seen = {start}
    while queue:
        current = queue.popleft()
        for edge in adjacency.get(current, ()):
            if edge.dst in seen:
                continue
            seen.add(edge.dst)
            previous[edge.dst] = (current, edge)
            if edge.dst == target:
                route = []
                cursor = target
                while cursor != start:
                    parent, observed = previous[cursor]
                    route.append(observed)
                    cursor = parent
                route.reverse()
                return route
            queue.append(edge.dst)
    return None


def _reverse_adjacency(
    adjacency: dict[str, tuple[Edge, ...]],
) -> dict[str, tuple[str, ...]]:
    reverse: dict[str, set[str]] = {}
    for edges in adjacency.values():
        for edge in edges:
            reverse.setdefault(edge.dst, set()).add(edge.src)
    return {
        target: tuple(sorted(sources)) for target, sources in reverse.items()
    }


def _reverse_reachable(
    target: str,
    reverse: dict[str, tuple[str, ...]],
) -> set[str]:
    reached = {target}
    queue = deque([target])
    while queue:
        current = queue.popleft()
        for source in sorted(reverse.get(current, ())):
            if source in reached:
                continue
            reached.add(source)
            queue.append(source)
    return reached


def _reachable(start: str, adjacency: dict[str, tuple[Edge, ...]]) -> set[str]:
    reached = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in adjacency.get(current, ()):
            if edge.dst in reached:
                continue
            reached.add(edge.dst)
            queue.append(edge.dst)
    return reached


def _node_step(layer: str, relation: str, node: Node, *, is_target: bool) -> dict[str, object]:
    payload = {
        "layer": layer,
        "relation": relation,
        "source_node_id": None,
        "node_id": node.id,
        "name": node.name,
        "kind": node.kind,
        "language": node.language,
        "certain": True,
        "observation": None,
        "declaration": _citation(node.file, node.lineno),
        "citation": f"{node.file}:{node.lineno}",
        "is_target": is_target,
    }
    payload["id"] = _step_id(payload)
    return payload


def _role_step(evidence: RoleEvidence, node: Node, *, is_target: bool) -> dict[str, object]:
    payload = {
        "layer": "application-surface",
        "relation": "role",
        "source_node_id": None,
        "node_id": node.id,
        "name": node.name,
        "kind": node.kind,
        "language": node.language,
        "certain": True,
        "role": evidence.role,
        "rule_id": evidence.rule_id,
        "observation": _citation(evidence.file, evidence.lineno),
        "declaration": _citation(node.file, node.lineno),
        "citation": f"{node.file}:{node.lineno}",
        "is_target": is_target,
    }
    payload["id"] = _step_id(payload)
    return payload


def _citation(file: str, line: int) -> dict[str, object]:
    return {"file": file, "line": line, "citation": f"{file}:{line}"}


def _break_at_node(reason: str, message: str, node: Node) -> dict[str, object]:
    return {
        "reason": reason,
        "message": message,
        "citation": f"{node.file}:{node.lineno}",
    }


def _empty_result(target: Node, fingerprint: str) -> dict[str, object]:
    return {
        "schema_version": JOURNEY_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "target": {
            "node_id": target.id,
            "name": target.name,
            "kind": target.kind,
            "language": target.language,
            "citation": f"{target.file}:{target.lineno}",
        },
        "status": "broken",
        "runtime_status": "broken",
        "home_context": None,
        "file_corridor": [],
        "application_surface": None,
        "runtime_steps": [],
        "steps": [],
        "break": None,
        "possible_frontier": [],
        "possible_frontier_truncated": False,
        "possible_frontier_omitted_count": 0,
        "external_boundaries": [],
        "verification_candidates": [],
        "truncated": False,
        "omitted_step_count": 0,
    }


def _step_id(payload: dict[str, object]) -> str:
    return f"journey-{_digest({'schema': JOURNEY_SCHEMA_VERSION, 'step': payload})[:16]}"


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = ["JOURNEY_SCHEMA_VERSION", "LearningJourneyIndex", "learning_journey"]
