"""Validate and interpret canonical Share Artifact bytes in one trusted module."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

import rfc8785

from codemble.share.artifact import (
    _DECLARED_EXCLUSIONS,
    _EDGE_KINDS,
    _LANGUAGES,
    _NODE_KINDS,
    _ORBIT_KINDS,
    _SUPPORTED_GRAPH_SCHEMA_VERSION,
    MAX_LABEL_UTF8_BYTES,
    MAX_RENDER_COORDINATE,
    MAX_SAFE_INTEGER,
    MAX_SHARE_LIFETIME,
    MAX_SHARE_REGIONS,
    SHARE_SCHEMA_VERSION,
)

_NODE_ID_PATTERN = re.compile(r"^n[0-9a-f]{32}$")
_REGION_ID_PATTERN = re.compile(r"^r[0-9a-f]{32}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class InvalidShareArtifactError(ValueError):
    """Canonical bytes do not satisfy the closed Share Artifact contract."""


@dataclass(frozen=True, slots=True)
class ShareArtifactFacts:
    """Validated facts shared by preview, delivery, and browser rendering."""

    byte_length: int
    node_count: int
    region_count: int
    route_count: int
    source_file_count: int
    partial_source_count: int
    unsupported_source_count: int
    label_count: int
    understood_region_count: int
    labels_included: bool
    understanding_included: bool
    created_at: datetime
    expires_at: datetime
    payload_digest: str
    artifact_digest: str


@dataclass(frozen=True, slots=True)
class ShareArtifactDocument:
    """One validated canonical document and its already-derived facts."""

    manifest: Mapping[str, object]
    payload: Mapping[str, object]
    facts: ShareArtifactFacts


def interpret_share_artifact(encoded: bytes) -> ShareArtifactDocument:
    try:
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError
        document = json.loads(encoded, object_pairs_hook=_unique_object)
        if rfc8785.dumps(document) != encoded:
            raise ValueError
        _exact_object(document, {"manifest", "payload"})
        manifest = document["manifest"]
        payload = document["payload"]
        _validate_manifest(manifest)
        partial_regions = _validate_payload(payload)
        _validate_coverage(manifest, payload, partial_regions=partial_regions)
        payload_bytes = rfc8785.dumps(payload)
        expected_payload_digest = f"sha256:{sha256(payload_bytes).hexdigest()}"
        if manifest["payload_digest"] != expected_payload_digest:
            raise ValueError
        created_at = _parse_time(manifest["created_at"])
        expires_at = _parse_time(manifest["expires_at"])
        if expires_at <= created_at or expires_at - created_at > MAX_SHARE_LIFETIME:
            raise ValueError
        facts = ShareArtifactFacts(
            byte_length=len(encoded),
            node_count=len(payload["nodes"]),
            region_count=len(payload["regions"]),
            route_count=len(payload["region_edges"]),
            source_file_count=manifest["coverage"]["source_files"],
            partial_source_count=manifest["coverage"]["partial_sources"],
            unsupported_source_count=manifest["coverage"]["unsupported_sources"],
            label_count=(
                sum("label" in item for item in payload["nodes"])
                + sum("label" in item for item in payload["regions"])
                if payload["labels_included"] is True
                else 0
            ),
            understood_region_count=(
                sum(item.get("understood") is True for item in payload["regions"])
                if payload["understanding_included"] is True
                else 0
            ),
            labels_included=payload["labels_included"],
            understanding_included=payload["understanding_included"],
            created_at=created_at,
            expires_at=expires_at,
            payload_digest=expected_payload_digest,
            artifact_digest=f"sha256:{sha256(encoded).hexdigest()}",
        )
        return ShareArtifactDocument(manifest=manifest, payload=payload, facts=facts)
    except InvalidShareArtifactError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise InvalidShareArtifactError(
            "share artifact is outside the closed immutable schema"
        ) from error


def _validate_manifest(value: object) -> None:
    _exact_object(
        value,
        {
            "schema_version",
            "producer",
            "created_at",
            "expires_at",
            "payload_digest",
            "declared_exclusions",
            "coverage",
        },
    )
    assert isinstance(value, dict)
    if value["schema_version"] != SHARE_SCHEMA_VERSION:
        raise ValueError
    producer = value["producer"]
    _exact_object(producer, {"codemble_version", "graph_schema_version"})
    assert isinstance(producer, dict)
    if (
        not isinstance(producer["codemble_version"], str)
        or not producer["codemble_version"]
        or len(producer["codemble_version"].encode("utf-8")) > 128
        or producer["graph_schema_version"] != _SUPPORTED_GRAPH_SCHEMA_VERSION
    ):
        raise ValueError
    if value["declared_exclusions"] != list(_DECLARED_EXCLUSIONS):
        raise ValueError
    if _DIGEST_PATTERN.fullmatch(value["payload_digest"] or "") is None:
        raise ValueError
    coverage = value["coverage"]
    _exact_object(
        coverage,
        {
            "source_files",
            "nodes",
            "regions",
            "partial_sources",
            "unsupported_sources",
        },
    )
    assert isinstance(coverage, dict)
    if any(not _safe_int(item) for item in coverage.values()):
        raise ValueError


def _validate_payload(value: object) -> set[str]:
    _exact_object(
        value,
        {
            "schema_version",
            "labels_included",
            "understanding_included",
            "nodes",
            "edges",
            "regions",
            "region_edges",
        },
    )
    assert isinstance(value, dict)
    if value["schema_version"] != SHARE_SCHEMA_VERSION:
        raise ValueError
    labels_included = value["labels_included"]
    understanding_included = value["understanding_included"]
    if not isinstance(labels_included, bool) or not isinstance(understanding_included, bool):
        raise TypeError
    nodes = value["nodes"]
    edges = value["edges"]
    regions = value["regions"]
    region_edges = value["region_edges"]
    if not all(isinstance(items, list) for items in (nodes, edges, regions, region_edges)):
        raise ValueError
    if len(regions) > MAX_SHARE_REGIONS:
        raise ValueError

    node_ids: set[str] = set()
    node_regions: dict[str, str] = {}
    node_languages: dict[str, str] = {}
    node_kinds: dict[str, str] = {}
    node_locs: dict[str, int] = {}
    partial_regions: set[str] = set()
    members_by_region: dict[str, list[str]] = defaultdict(list)
    entrypoints: list[str] = []
    for node in nodes:
        fields = {
            "id",
            "region_id",
            "kind",
            "language",
            "loc",
            "centrality",
            "entrypoint",
            "partial",
            "system_position",
            "system_orbit",
        }
        if labels_included:
            fields.add("label")
        if understanding_included:
            fields.add("understood")
        _exact_object(node, fields)
        assert isinstance(node, dict)
        node_id = node["id"]
        region_id = node["region_id"]
        if (
            not isinstance(node_id, str)
            or _NODE_ID_PATTERN.fullmatch(node_id) is None
            or node_id in node_ids
            or not isinstance(region_id, str)
            or _REGION_ID_PATTERN.fullmatch(region_id) is None
            or node["kind"] not in _NODE_KINDS
            or node["language"] not in _LANGUAGES
            or not _safe_int(node["loc"])
            or not _safe_int(node["centrality"])
            or not isinstance(node["entrypoint"], bool)
            or not isinstance(node["partial"], bool)
        ):
            raise ValueError
        _validate_position(node["system_position"])
        _validate_orbit(node["system_orbit"])
        if labels_included and not _valid_label(node["label"]):
            raise ValueError
        if understanding_included and not isinstance(node["understood"], bool):
            raise ValueError
        node_ids.add(node_id)
        node_regions[node_id] = region_id
        node_languages[node_id] = node["language"]
        node_kinds[node_id] = node["kind"]
        node_locs[node_id] = node["loc"]
        members_by_region[region_id].append(node_id)
        if node["partial"]:
            partial_regions.add(region_id)
        if node["entrypoint"]:
            entrypoints.append(node_id)
    if [node["id"] for node in nodes] != sorted(node_ids) or len(entrypoints) > 1:
        raise ValueError

    edge_marks: list[tuple[str, str, str, bool]] = []
    callers: dict[str, set[str]] = defaultdict(set)
    route_certainties: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for edge in edges:
        _exact_object(edge, {"source_id", "target_id", "kind", "certain"})
        assert isinstance(edge, dict)
        mark = (edge["source_id"], edge["target_id"], edge["kind"], edge["certain"])
        if (
            not all(isinstance(item, str) for item in mark[:3])
            or not isinstance(mark[3], bool)
            or mark[0] not in node_ids
            or mark[1] not in node_ids
            or mark[2] not in _EDGE_KINDS
        ):
            raise ValueError
        edge_marks.append(mark)
        if mark[2] == "call":
            callers[mark[1]].add(mark[0])
        elif node_regions[mark[0]] != node_regions[mark[1]]:
            route_certainties[(node_regions[mark[0]], node_regions[mark[1]])].append(mark[3])
    if edge_marks != sorted(set(edge_marks)):
        raise ValueError
    if any(node["centrality"] != len(callers[node["id"]]) for node in nodes):
        raise ValueError
    _validate_orbit_truth(nodes, edge_marks)

    region_ids: set[str] = set()
    homes: list[str] = []
    regions_by_id: dict[str, dict[str, object]] = {}
    for region in regions:
        fields = {
            "id",
            "language",
            "loc",
            "centrality",
            "node_count",
            "home",
            "layout",
            "community",
            "hops_from_home",
            "community_family",
        }
        if labels_included:
            fields.add("label")
        if understanding_included:
            fields.add("understood")
        _exact_object(region, fields)
        assert isinstance(region, dict)
        region_id = region["id"]
        if (
            not isinstance(region_id, str)
            or _REGION_ID_PATTERN.fullmatch(region_id) is None
            or region_id in region_ids
            or region["language"] not in _LANGUAGES
            or any(
                not _safe_int(region[field])
                for field in ("loc", "centrality", "node_count", "community")
            )
            or not isinstance(region["home"], bool)
            or (region["hops_from_home"] is not None and not _safe_int(region["hops_from_home"]))
            or (
                region["community_family"] is not None
                and (not _safe_int(region["community_family"]) or region["community_family"] > 7)
            )
        ):
            raise ValueError
        _validate_position(region["layout"])
        if labels_included and not _valid_label(region["label"]):
            raise ValueError
        if understanding_included and not isinstance(region["understood"], bool):
            raise ValueError
        members = members_by_region[region_id]
        member_languages = {node_languages[node_id] for node_id in members}
        module_loc = sum(
            node_locs[node_id] for node_id in members if node_kinds[node_id] == "module"
        )
        expected_loc = module_loc or sum(node_locs[node_id] for node_id in members)
        expected_centrality = sum(len(callers[node_id]) for node_id in members)
        if (
            not members
            or member_languages != {region["language"]}
            or region["node_count"] != len(members)
            or region["loc"] != expected_loc
            or region["centrality"] != expected_centrality
        ):
            raise ValueError
        region_ids.add(region_id)
        regions_by_id[region_id] = region
        if region["home"]:
            homes.append(region_id)
    if [region["id"] for region in regions] != sorted(region_ids):
        raise ValueError
    if set(node_regions.values()) != region_ids:
        raise ValueError
    expected_homes = [node_regions[entrypoints[0]]] if entrypoints else []
    if homes != expected_homes:
        raise ValueError

    route_marks: list[tuple[str, str, int, bool]] = []
    for route in region_edges:
        _exact_object(route, {"source_id", "target_id", "weight", "certain"})
        assert isinstance(route, dict)
        mark = (route["source_id"], route["target_id"], route["weight"], route["certain"])
        if (
            not isinstance(mark[0], str)
            or not isinstance(mark[1], str)
            or mark[0] not in region_ids
            or mark[1] not in region_ids
            or not _safe_int(mark[2])
            or mark[2] <= 0
            or not isinstance(mark[3], bool)
        ):
            raise ValueError
        route_marks.append(mark)
    if route_marks != sorted(set(route_marks)):
        raise ValueError
    expected_routes = sorted(
        (source, target, len(certainties), all(certainties))
        for (source, target), certainties in route_certainties.items()
    )
    if route_marks != expected_routes:
        raise ValueError

    expected_hops = _hops(region_ids, route_marks, homes[0] if homes else None)
    if any(
        region["hops_from_home"] != expected_hops.get(region_id)
        for region_id, region in regions_by_id.items()
    ):
        raise ValueError

    return partial_regions


def _validate_coverage(
    manifest: dict[str, object],
    payload: dict[str, object],
    *,
    partial_regions: set[str],
) -> None:
    coverage = manifest["coverage"]
    assert isinstance(coverage, dict)
    nodes = payload["nodes"]
    regions = payload["regions"]
    assert isinstance(nodes, list)
    assert isinstance(regions, list)
    if (
        coverage["source_files"] != len(regions)
        or coverage["nodes"] != len(nodes)
        or coverage["regions"] != len(regions)
        or coverage["partial_sources"] != len(partial_regions)
    ):
        raise ValueError


def _hops(
    region_ids: set[str],
    routes: list[tuple[str, str, int, bool]],
    home: str | None,
) -> dict[str, int]:
    if home is None:
        return {}
    neighbors: dict[str, set[str]] = {region_id: set() for region_id in region_ids}
    for source, target, _weight, _certain in routes:
        neighbors[source].add(target)
        neighbors[target].add(source)
    hops = {home: 0}
    queue = [home]
    for current in queue:
        for neighbor in sorted(neighbors[current]):
            if neighbor in hops:
                continue
            hops[neighbor] = hops[current] + 1
            queue.append(neighbor)
    return hops


def _validate_orbit_truth(
    nodes: list[object],
    edges: list[tuple[str, str, str, bool]],
) -> None:
    """Recompute semantic call layers without trusting stored orbit claims."""

    nodes_by_id: dict[str, dict[str, object]] = {}
    members_by_region: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in nodes:
        assert isinstance(item, dict)
        node_id = item["id"]
        region_id = item["region_id"]
        assert isinstance(node_id, str)
        assert isinstance(region_id, str)
        nodes_by_id[node_id] = item
        members_by_region[region_id].append(item)

    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = defaultdict(int)
    for source, target, kind, certain in edges:
        if (
            kind != "call"
            or not certain
            or source == target
            or nodes_by_id[source]["region_id"] != nodes_by_id[target]["region_id"]
        ):
            continue
        if target not in outgoing[source]:
            indegree[target] += 1
        outgoing[source].add(target)

    for members in members_by_region.values():
        ordered = sorted(
            members,
            key=lambda node: (node["kind"] != "module", node["id"]),
        )
        entry = ordered[0]["id"]
        assert isinstance(entry, str)
        layers: dict[str, tuple[int, int | None, str]] = {entry: (0, 0, "origin")}
        certain_entry_calls = outgoing[entry]
        roots = certain_entry_calls | {
            node_id
            for node in ordered
            if (node_id := node["id"]) != entry
            and isinstance(node_id, str)
            and indegree[node_id] == 0
        }
        queue: deque[str] = deque()
        for node_id in sorted(roots):
            layers[node_id] = (
                1,
                1,
                "certain-call" if node_id in certain_entry_calls else "call-root",
            )
            queue.append(node_id)
        while queue:
            current = queue.popleft()
            current_depth = layers[current][1]
            assert current_depth is not None
            for target in sorted(outgoing[current]):
                if target not in layers:
                    layers[target] = (
                        current_depth + 1,
                        current_depth + 1,
                        "certain-call",
                    )
                    queue.append(target)

        outermost = max(layer[0] for layer in layers.values()) + 1
        for node in ordered:
            node_id = node["id"]
            orbit = node["system_orbit"]
            assert isinstance(node_id, str)
            assert isinstance(orbit, dict)
            expected = layers.get(node_id, (outermost, None, "unreached"))
            actual = (orbit["ring"], orbit["call_depth"], orbit["kind"])
            if actual != expected:
                raise ValueError


def _validate_position(value: object) -> None:
    _exact_object(value, {"x", "y", "z"})
    assert isinstance(value, dict)
    if any(not _bounded_number(value[axis]) for axis in ("x", "y", "z")):
        raise ValueError


def _validate_orbit(value: object) -> None:
    _exact_object(value, {"ring", "radius", "call_depth", "kind"})
    assert isinstance(value, dict)
    if (
        not _safe_int(value["ring"])
        or not _bounded_number(value["radius"])
        or value["radius"] < 0
        or (value["call_depth"] is not None and not _safe_int(value["call_depth"]))
        or value["kind"] not in _ORBIT_KINDS
    ):
        raise ValueError


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _exact_object(value: object, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError
    return parsed.astimezone(UTC)


def _safe_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SAFE_INTEGER


def _bounded_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) <= MAX_RENDER_COORDINATE
    )


def _valid_label(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return len(value.encode("utf-8")) <= MAX_LABEL_UTF8_BYTES
    except UnicodeEncodeError:
        return False

__all__ = [
    "InvalidShareArtifactError",
    "ShareArtifactDocument",
    "ShareArtifactFacts",
    "interpret_share_artifact",
]
