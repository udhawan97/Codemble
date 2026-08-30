"""Build the exact raw-source-free bytes a future read-only viewer may receive."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from secrets import token_bytes
from typing import Self

import rfc8785

from codemble import __version__
from codemble.adapters.base import Edge, Graph, Node, Region
from codemble.graph.layout import layout_graph

SHARE_SCHEMA_VERSION = 1
MAX_SHARE_LIFETIME = timedelta(days=30)
MAX_SHARE_REGIONS = 5_000
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_RENDER_COORDINATE = 1_000_000.0
MAX_LABEL_UTF8_BYTES = 4_096
_IDENTITY_KEY_BYTES = 32
_NODE_KINDS = frozenset(("module", "class", "function"))
_EDGE_KINDS = frozenset(("import", "call"))
_ORBIT_KINDS = frozenset(("origin", "call-root", "certain-call", "unreached"))
_LANGUAGES = frozenset(
    ("csharp", "go", "java", "javascript", "php", "python", "ruby", "rust", "typescript")
)
_SUPPORTED_GRAPH_SCHEMA_VERSION = 11
_DECLARED_EXCLUSIONS = (
    "absolute_paths",
    "check_questions_answers_attempts",
    "concept_snippets",
    "external_targets",
    "file_hashes",
    "narration",
    "repository_root_remote_vcs_identity",
    "provider_configuration",
    "raw_source",
    "source_locations",
    "visit_history_recent_projects_logs",
)


@dataclass(frozen=True, slots=True)
class SharePolicy:
    """Publisher choices that can widen an otherwise private artifact."""

    expires_at: datetime
    include_labels: bool = False
    include_understanding: bool = False


@dataclass(frozen=True, slots=True, init=False)
class ShareArtifact:
    """One immutable read-only snapshot serialized behind a small interface."""

    _encoded: bytes

    def __new__(cls, *_args: object, **_kwargs: object) -> Self:
        raise TypeError("ShareArtifact must be compiled with from_graph")

    @classmethod
    def from_graph(
        cls,
        graph: Graph,
        policy: SharePolicy,
        created_at: datetime,
    ) -> ShareArtifact:
        """Return a snapshot containing only explicitly shareable graph facts."""

        _validate_policy(policy)
        _validate_expiry(created_at, policy.expires_at)
        represented_edges = _validate_graph(graph, include_labels=policy.include_labels)
        projected_edges = _project_edges(represented_edges)
        identity_key = token_bytes(_IDENTITY_KEY_BYTES)
        if len(identity_key) != _IDENTITY_KEY_BYTES:
            raise RuntimeError("share identity entropy must contain 32 bytes")
        node_ids = {
            node.id: _opaque_id(identity_key, "node", node.id) for node in graph.nodes
        }
        region_ids = {
            region.id: _opaque_id(identity_key, "region", region.id) for region in graph.regions
        }
        if len(set(node_ids.values())) != len(node_ids) or len(set(region_ids.values())) != len(
            region_ids
        ):
            raise RuntimeError("share-local identity collision")
        private_graph = _compile_private_graph(
            graph,
            represented_edges=projected_edges,
            node_ids=node_ids,
            region_ids=region_ids,
        )
        _validate_derived_truth(graph, private_graph, node_ids=node_ids, region_ids=region_ids)
        region_labels = {private_id: source_id for source_id, private_id in region_ids.items()}
        nodes = sorted(private_graph.nodes, key=lambda node: node.id)
        regions = sorted(private_graph.regions, key=lambda region: region.id)
        payload = {
            "schema_version": SHARE_SCHEMA_VERSION,
            "labels_included": policy.include_labels,
            "understanding_included": policy.include_understanding,
            "nodes": [
                _share_node(
                    node,
                    selected_entrypoint=private_graph.selected_entrypoint,
                    include_labels=policy.include_labels,
                    include_understanding=policy.include_understanding,
                )
                for node in nodes
            ],
            "edges": _share_edges(private_graph.edges),
            "regions": [
                _share_region(
                    region,
                    label=region_labels[region.id],
                    include_labels=policy.include_labels,
                    include_understanding=policy.include_understanding,
                )
                for region in regions
            ],
            "region_edges": [
                {
                    "source_id": edge.src,
                    "target_id": edge.dst,
                    "weight": edge.weight,
                    "certain": edge.certain,
                }
                for edge in sorted(
                    private_graph.region_edges,
                    key=lambda item: (item.src, item.dst, item.weight, item.certain),
                )
            ],
        }
        payload_bytes = _canonical_json(payload)
        manifest = {
            "schema_version": SHARE_SCHEMA_VERSION,
            "producer": {
                "codemble_version": __version__,
                "graph_schema_version": graph.schema_version,
            },
            "created_at": _format_time(created_at),
            "expires_at": _format_time(policy.expires_at),
            "payload_digest": f"sha256:{sha256(payload_bytes).hexdigest()}",
            "declared_exclusions": list(_DECLARED_EXCLUSIONS),
            "coverage": {
                "source_files": len(graph.file_hashes),
                "nodes": len(graph.nodes),
                "regions": len(graph.regions),
                "partial_sources": len({node.file for node in graph.nodes if node.partial}),
                "unsupported_sources": sum(source.count for source in graph.unsupported_sources),
            },
        }
        encoded = _canonical_json({"manifest": manifest, "payload": payload})
        artifact = object.__new__(cls)
        object.__setattr__(artifact, "_encoded", encoded)
        return artifact

    def to_bytes(self) -> bytes:
        """Return the immutable canonical document bytes."""

        return self._encoded


def _share_node(
    node: Node,
    *,
    selected_entrypoint: str | None,
    include_labels: bool,
    include_understanding: bool,
) -> dict[str, object]:
    orbit = node.system_orbit
    shared = {
        "id": node.id,
        "region_id": node.region,
        "kind": node.kind,
        "language": node.language,
        "loc": node.loc,
        "centrality": node.centrality,
        "entrypoint": node.id == selected_entrypoint,
        "partial": node.partial,
        "system_position": {"x": node.system_x, "y": node.system_y, "z": node.system_z},
        "system_orbit": (
            {
                "ring": orbit.ring,
                "radius": orbit.radius,
                "call_depth": orbit.call_depth,
                "kind": orbit.kind,
            }
            if orbit is not None
            else None
        ),
    }
    if include_labels:
        shared["label"] = node.name
    if include_understanding:
        shared["understood"] = node.understood
    return shared


def _share_region(
    region: Region,
    *,
    label: str,
    include_labels: bool,
    include_understanding: bool,
) -> dict[str, object]:
    shared = {
        "id": region.id,
        "language": region.language,
        "loc": region.loc,
        "centrality": region.centrality,
        "node_count": region.node_count,
        "home": region.home,
        "layout": {"x": region.x, "y": region.y, "z": region.z},
        "community": region.community,
        "hops_from_home": region.hops_from_home,
        "community_family": region.community_family,
    }
    if include_labels:
        shared["label"] = label
    if include_understanding:
        shared["understood"] = region.understood
    return shared


def _share_edges(edges: tuple[Edge, ...]) -> list[dict[str, object]]:
    projection = sorted({(edge.src, edge.dst, edge.kind, edge.certain) for edge in edges})
    return [
        {
            "source_id": source_id,
            "target_id": target_id,
            "kind": kind,
            "certain": certain,
        }
        for source_id, target_id, kind, certain in projection
    ]


def _project_edges(edges: tuple[Edge, ...]) -> tuple[Edge, ...]:
    """Return the exact relationship marks the closed share schema can express."""

    projected: dict[tuple[str, str, str, bool], Edge] = {}
    for edge in edges:
        mark = (edge.src, edge.dst, edge.kind, edge.certain)
        current = projected.get(mark)
        if current is None or edge.lineno < current.lineno:
            projected[mark] = edge
    return tuple(projected[mark] for mark in sorted(projected))


def _canonical_json(value: object) -> bytes:
    return rfc8785.dumps(value)


def _opaque_id(identity_key: bytes, kind: str, source_id: str) -> str:
    domain = f"codemble-share-{kind}-id-v1".encode()
    digest = hmac_new(identity_key, domain + b"\0" + source_id.encode(), sha256).hexdigest()
    return f"{kind[0]}{digest[:32]}"


def _compile_private_graph(
    graph: Graph,
    *,
    represented_edges: tuple[Edge, ...],
    node_ids: dict[str, str],
    region_ids: dict[str, str],
) -> Graph:
    private = Graph(
        nodes=tuple(
            replace(node, id=node_ids[node.id], region=region_ids[node.region])
            for node in graph.nodes
        ),
        edges=tuple(
            replace(edge, src=node_ids[edge.src], dst=node_ids[edge.dst], external=False)
            for edge in represented_edges
        ),
        entrypoint_candidates=tuple(node_ids[candidate] for candidate in graph.entrypoint_candidates),
        selected_entrypoint=(
            node_ids[graph.selected_entrypoint]
            if graph.selected_entrypoint is not None
            else None
        ),
        project_root="",
        file_hashes={},
    )
    laid_out = layout_graph(private)
    understanding = {region_ids[region.id]: region.understood for region in graph.regions}
    return replace(
        laid_out,
        regions=tuple(
            replace(region, understood=understanding[region.id]) for region in laid_out.regions
        ),
    )


def _validate_derived_truth(
    graph: Graph,
    private_graph: Graph,
    *,
    node_ids: dict[str, str],
    region_ids: dict[str, str],
) -> None:
    source_routes = sorted(
        (edge.src, edge.dst, edge.weight, edge.certain) for edge in graph.region_edges
    )
    expected_source_routes = _region_route_marks(graph.nodes, graph.edges)
    private_routes = sorted(
        (edge.src, edge.dst, edge.weight, edge.certain) for edge in private_graph.region_edges
    )
    expected_private_routes = _region_route_marks(private_graph.nodes, private_graph.edges)
    if source_routes != expected_source_routes or private_routes != expected_private_routes:
        raise ValueError("region edges do not match represented imports")

    private_regions = {region.id: region for region in private_graph.regions}
    for region in graph.regions:
        private_region = private_regions[region_ids[region.id]]
        if region.node_count != private_region.node_count:
            raise ValueError("region node count does not match the render graph")
        if region.loc != private_region.loc or region.centrality != private_region.centrality:
            raise ValueError("region metrics do not match represented nodes")
        if region.language != private_region.language:
            raise ValueError("region language does not match its nodes")
        if region.home != private_region.home or region.hops_from_home != private_region.hops_from_home:
            raise ValueError("Home region and route distance do not match represented imports")

    private_nodes = {node.id: node for node in private_graph.nodes}
    for node in graph.nodes:
        private_orbit = private_nodes[node_ids[node.id]].system_orbit
        if node.system_orbit is None or private_orbit is None:
            raise ValueError("node is missing render-ready system orbit")
        if (
            node.system_orbit.ring,
            node.system_orbit.call_depth,
            node.system_orbit.kind,
        ) != (private_orbit.ring, private_orbit.call_depth, private_orbit.kind):
            raise ValueError("system orbit truth does not match represented calls")

    if any(
        not _bounded_render_number(value)
        for node in private_graph.nodes
        for value in (node.system_x, node.system_y, node.system_z)
    ) or any(
        not _bounded_render_number(value)
        for region in private_graph.regions
        for value in (region.x, region.y, region.z)
    ):
        raise ValueError("compiled share layout exceeds the render-safe coordinate bound")


def _region_route_marks(
    nodes: tuple[Node, ...],
    edges: tuple[Edge, ...],
) -> list[tuple[str, str, int, bool]]:
    node_regions = {node.id: node.region for node in nodes}
    certainties: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for edge in edges:
        source_region = node_regions.get(edge.src)
        target_region = node_regions.get(edge.dst)
        if (
            edge.kind != "import"
            or edge.external
            or source_region is None
            or target_region is None
            or source_region == target_region
        ):
            continue
        certainties[(source_region, target_region)].append(edge.certain)
    return sorted(
        (source, target, len(values), all(values))
        for (source, target), values in certainties.items()
    )


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_policy(policy: SharePolicy) -> None:
    if not isinstance(policy, SharePolicy):
        raise TypeError("policy must be a SharePolicy")
    if not isinstance(policy.include_labels, bool):
        raise TypeError("include_labels must be a boolean")
    if not isinstance(policy.include_understanding, bool):
        raise TypeError("include_understanding must be a boolean")


def _validate_expiry(created_at: datetime, expires_at: datetime) -> None:
    if not isinstance(created_at, datetime):
        raise TypeError("created_at must be a datetime")
    if not isinstance(expires_at, datetime):
        raise TypeError("expires_at must be a datetime")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise ValueError("expires_at must be timezone-aware")
    created_utc = created_at.astimezone(UTC)
    expires_utc = expires_at.astimezone(UTC)
    if expires_utc <= created_utc:
        raise ValueError("expires_at must be after created_at")
    if expires_utc - created_utc > MAX_SHARE_LIFETIME:
        raise ValueError("expires_at exceeds the 30-day maximum")


def _validate_graph(graph: Graph, *, include_labels: bool) -> tuple[Edge, ...]:
    if not isinstance(graph, Graph):
        raise TypeError("graph must be a Graph")
    if not isinstance(graph.schema_version, int) or graph.schema_version != _SUPPORTED_GRAPH_SCHEMA_VERSION:
        raise ValueError("unsupported render graph schema version")
    if len(graph.regions) > MAX_SHARE_REGIONS:
        raise ValueError("render graph exceeds the 5,000-region share maximum")
    if any(not isinstance(node.id, str) or not node.id for node in graph.nodes):
        raise ValueError("node identity must be a non-empty string")
    if any(not isinstance(region.id, str) or not region.id for region in graph.regions):
        raise ValueError("region identity must be a non-empty string")
    node_ids = {node.id for node in graph.nodes}
    region_ids = {region.id for region in graph.regions}
    if len(node_ids) != len(graph.nodes):
        raise ValueError("duplicate node identity in the render graph")
    if len(region_ids) != len(graph.regions):
        raise ValueError("duplicate region identity in the render graph")
    if any(node.region not in region_ids for node in graph.nodes):
        raise ValueError("node region is absent from the render graph")

    if any(node.kind not in _NODE_KINDS for node in graph.nodes):
        raise ValueError("unsupported node kind in the render graph")
    if any(node.language not in _LANGUAGES for node in graph.nodes) or any(
        region.language not in _LANGUAGES for region in graph.regions
    ):
        raise ValueError("unsupported language in the render graph")
    languages_by_region: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes:
        languages_by_region[node.region].add(node.language)
    if any(languages_by_region[region.id] != {region.language} for region in graph.regions):
        raise ValueError("region language does not match its nodes")
    if include_labels and (
        any(not _valid_label(node.name) for node in graph.nodes)
        or any(not _valid_label(region.id) for region in graph.regions)
    ):
        raise ValueError("share label is not a bounded UTF-8 string")

    node_files = {node.file for node in graph.nodes if isinstance(node.file, str)}
    if any(not isinstance(node.file, str) for node in graph.nodes):
        raise ValueError("node source is absent from parser coverage")
    if node_files != set(graph.file_hashes):
        raise ValueError("parser coverage does not match represented node sources")
    partial_node_files = {node.file for node in graph.nodes if node.partial}
    if partial_node_files != set(graph.partial_files):
        raise ValueError("partial-source coverage does not match partial nodes")

    if any(edge.kind not in _EDGE_KINDS for edge in graph.edges):
        raise ValueError("unsupported edge kind in the render graph")
    if any(
        not isinstance(edge.src, str)
        or not isinstance(edge.dst, str)
        or not isinstance(edge.certain, bool)
        or not isinstance(edge.external, bool)
        for edge in graph.edges
    ):
        raise ValueError("relationship fields are outside the closed render schema")
    represented_edges: list[Edge] = []
    for edge in graph.edges:
        if edge.src not in node_ids:
            raise ValueError("relationship source is absent from the render graph")
        if edge.dst in node_ids:
            if edge.external:
                raise ValueError("internal relationship is marked external")
            represented_edges.append(edge)
        elif not edge.external and edge.certain:
            raise ValueError("certain relationship target is absent from the render graph")

    if any(
        edge.src not in region_ids
        or edge.dst not in region_ids
        or not isinstance(edge.certain, bool)
        or not _positive_safe_int(edge.weight)
        for edge in graph.region_edges
    ):
        raise ValueError("region edge is outside the closed render schema")

    candidates = graph.entrypoint_candidates
    if any(not isinstance(candidate, str) for candidate in candidates):
        raise ValueError("ranked entrypoint identity must be a string")
    if len(set(candidates)) != len(candidates):
        raise ValueError("duplicate ranked entrypoint candidate")
    if any(candidate not in node_ids for candidate in candidates):
        raise ValueError("ranked entrypoint candidate is absent from the render graph")
    home_regions = {region.id for region in graph.regions if region.home is True}
    if graph.selected_entrypoint is None:
        if home_regions:
            raise ValueError("Home region exists without a selected entrypoint")
    else:
        if graph.selected_entrypoint not in node_ids:
            raise ValueError("selected entrypoint is absent from the render graph")
        if graph.selected_entrypoint not in candidates:
            raise ValueError("selected entrypoint is not a ranked candidate")
        selected_region = next(
            node.region for node in graph.nodes if node.id == graph.selected_entrypoint
        )
        if home_regions != {selected_region}:
            raise ValueError("Home region does not match the selected entrypoint")

    actual_region_counts = Counter(node.region for node in graph.nodes)
    if set(actual_region_counts) != region_ids:
        raise ValueError("region has no nodes in the render graph")
    if any(region.node_count != actual_region_counts[region.id] for region in graph.regions):
        raise ValueError("region node count does not match the render graph")

    if any(node.system_orbit is None for node in graph.nodes):
        raise ValueError("node is missing render-ready system orbit")
    if any(
        node.system_orbit is not None and node.system_orbit.kind not in _ORBIT_KINDS
        for node in graph.nodes
    ):
        raise ValueError("unsupported system orbit kind in the render graph")
    if any(
        not _safe_int(node.loc) or not _safe_int(node.centrality) for node in graph.nodes
    ):
        raise ValueError("node metrics must be bounded non-negative integers")
    if any(
        not _safe_int(region.loc)
        or not _safe_int(region.centrality)
        or not _safe_int(region.node_count)
        or not _safe_int(region.community)
        for region in graph.regions
    ):
        raise ValueError("region metrics must be bounded non-negative integers")
    if any(
        region.hops_from_home is not None and not _safe_int(region.hops_from_home)
        for region in graph.regions
    ):
        raise ValueError("Home route distance must be a bounded non-negative integer or null")
    if any(
        region.community_family is not None
        and (not _safe_int(region.community_family) or region.community_family > 7)
        for region in graph.regions
    ):
        raise ValueError("community family must be between zero and seven or null")
    if any(
        not _bounded_render_number(value)
        for node in graph.nodes
        for value in (node.system_x, node.system_y, node.system_z)
    ) or any(
        not _bounded_render_number(value)
        for region in graph.regions
        for value in (region.x, region.y, region.z)
    ):
        raise ValueError("layout coordinates exceed the render-safe bound")
    if any(
        orbit is not None
        and (
            not _safe_int(orbit.ring)
            or not _bounded_render_number(orbit.radius)
            or orbit.radius < 0
            or (orbit.call_depth is not None and not _safe_int(orbit.call_depth))
        )
        for orbit in (node.system_orbit for node in graph.nodes)
    ):
        raise ValueError("system orbit metrics are outside the closed render schema")
    if any(
        not isinstance(node.partial, bool) or not isinstance(node.understood, bool)
        for node in graph.nodes
    ) or any(
        not isinstance(region.home, bool) or not isinstance(region.understood, bool)
        for region in graph.regions
    ):
        raise ValueError("render-state flags must be booleans")
    if any(not _safe_int(source.count) for source in graph.unsupported_sources) or not _safe_int(
        sum(source.count for source in graph.unsupported_sources)
    ):
        raise ValueError("unsupported-source counts must be bounded non-negative integers")

    callers: dict[str, set[str]] = defaultdict(set)
    for edge in represented_edges:
        if edge.kind == "call":
            callers[edge.dst].add(edge.src)
    if any(node.centrality != len(callers[node.id]) for node in graph.nodes):
        raise ValueError("node centrality does not match represented calls")
    return tuple(represented_edges)


def _safe_int(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= MAX_SAFE_INTEGER
    )


def _positive_safe_int(value: object) -> bool:
    return _safe_int(value) and value > 0


def _bounded_render_number(value: object) -> bool:
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
