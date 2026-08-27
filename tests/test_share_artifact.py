"""Raw-source-free, canonical read-only share artifact contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new

import pytest
import rfc8785

from codemble import __version__
from codemble.adapters.base import (
    ConceptAnnotation,
    Edge,
    Graph,
    Node,
    Region,
    RegionEdge,
    RoleEvidence,
    SystemOrbit,
    UnsupportedSource,
)
from codemble.share import ShareArtifact, SharePolicy
from codemble.share import artifact as share_artifact

CREATED_AT = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
IDENTITY_KEY = b"codemble-share-test-key-32-bytes"


@pytest.fixture(autouse=True)
def _fixed_identity_entropy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(share_artifact, "token_bytes", lambda size: IDENTITY_KEY[:size])


def _opaque_id(kind: str, source_id: str) -> str:
    domain = f"codemble-share-{kind}-id-v1".encode()
    digest = hmac_new(IDENTITY_KEY, domain + b"\0" + source_id.encode(), sha256).hexdigest()
    return f"{kind[0]}{digest[:32]}"


def _assert_closed_schema(
    document: dict[str, object],
    *,
    labels: bool,
    understanding: bool,
) -> None:
    assert set(document) == {"manifest", "payload"}
    manifest = document["manifest"]
    payload = document["payload"]
    assert isinstance(manifest, dict)
    assert isinstance(payload, dict)
    assert set(manifest) == {
        "schema_version",
        "producer",
        "created_at",
        "expires_at",
        "payload_digest",
        "declared_exclusions",
        "coverage",
    }
    assert set(manifest["producer"]) == {"codemble_version", "graph_schema_version"}
    assert set(manifest["coverage"]) == {
        "source_files",
        "nodes",
        "regions",
        "partial_sources",
        "unsupported_sources",
    }
    assert set(payload) == {
        "schema_version",
        "labels_included",
        "understanding_included",
        "nodes",
        "edges",
        "regions",
        "region_edges",
    }

    node_keys = {
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
    region_keys = {
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
    if labels:
        node_keys.add("label")
        region_keys.add("label")
    if understanding:
        node_keys.add("understood")
        region_keys.add("understood")

    for node in payload["nodes"]:
        assert set(node) == node_keys
        assert set(node["system_position"]) == {"x", "y", "z"}
        if node["system_orbit"] is not None:
            assert set(node["system_orbit"]) == {"ring", "radius", "call_depth", "kind"}
    for edge in payload["edges"]:
        assert set(edge) == {"source_id", "target_id", "kind", "certain"}
    for region in payload["regions"]:
        assert set(region) == region_keys
        assert set(region["layout"]) == {"x", "y", "z"}
    for edge in payload["region_edges"]:
        assert set(edge) == {"source_id", "target_id", "weight", "certain"}


def _sensitive_graph() -> Graph:
    root = "/Users/alice/secret-project"
    module = Node(
        id="secret.app",
        kind="module",
        name="secret.app",
        language="python",
        file="private/secret_app.py",
        lineno=1,
        end_lineno=80,
        loc=80,
        region="secret.app",
        centrality=0,
        entrypoint_rank=0,
        system_orbit=SystemOrbit(ring=0, radius=0.0, call_depth=0, kind="origin"),
    )
    function = Node(
        id="secret.app.send_payroll",
        kind="function",
        name="send_payroll",
        language="python",
        file="private/secret_app.py",
        lineno=20,
        end_lineno=30,
        loc=11,
        region="secret.app",
        centrality=1,
        understood=True,
        system_x=12.5,
        system_y=-3.0,
        system_z=9.25,
        system_orbit=SystemOrbit(
            ring=1,
            radius=34.0,
            call_depth=1,
            kind="certain-call",
        ),
    )
    return Graph(
        nodes=(module, function),
        edges=(
            Edge(
                src=module.id,
                dst=function.id,
                kind="call",
                certain=True,
                lineno=24,
            ),
            Edge(
                src=function.id,
                dst="external:requests.post",
                kind="call",
                certain=False,
                lineno=26,
                external=True,
            ),
        ),
        entrypoint_candidates=(module.id,),
        selected_entrypoint=module.id,
        project_root=root,
        file_hashes={"private/secret_app.py": "raw-file-sha256"},
        concept_annotations=(
            ConceptAnnotation(
                node_id=function.id,
                language="python",
                concept="async-await",
                lineno=20,
                end_lineno=20,
                snippet="await payroll_client.send(employee_ssn)",
            ),
        ),
        role_evidence=(
            RoleEvidence(
                node_id=function.id,
                role="route-handler",
                rule_id="fastapi-decorator",
                file="private/routes.py",
                lineno=18,
                end_lineno=18,
            ),
        ),
        regions=(
            Region(
                id="secret.app",
                language="python",
                loc=80,
                centrality=1,
                node_count=2,
                understood=True,
                home=True,
                x=100.0,
                y=50.0,
                z=-25.0,
                community=3,
                hops_from_home=0,
                community_family=2,
            ),
        ),
        region_edges=(),
        import_cycles=((module.id,),),
        partial_files=(),
        unsupported_sources=(
            UnsupportedSource(extension=".swift", language="Swift", count=2),
        ),
    )


def test_default_artifact_excludes_source_and_private_learner_state() -> None:
    artifact = ShareArtifact.from_graph(
        _sensitive_graph(),
        SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
        CREATED_AT,
    )

    encoded = artifact.to_bytes()
    document = json.loads(encoded)
    payload = document["payload"]
    module_id = _opaque_id("node", "secret.app")
    function_id = _opaque_id("node", "secret.app.send_payroll")
    region_id = _opaque_id("region", "secret.app")

    assert payload["labels_included"] is False
    assert payload["understanding_included"] is False
    assert {node["id"] for node in payload["nodes"]} == {module_id, function_id}
    nodes = {node["id"]: node for node in payload["nodes"]}
    assert nodes[module_id] == {
        "centrality": 0,
        "entrypoint": True,
        "id": module_id,
        "kind": "module",
        "language": "python",
        "loc": 80,
        "partial": False,
        "region_id": region_id,
        "system_orbit": {
            "call_depth": 0,
            "kind": "origin",
            "radius": 0,
            "ring": 0,
        },
        "system_position": {"x": 0, "y": 0, "z": 0},
    }
    function = nodes[function_id]
    assert {key: value for key, value in function.items() if key != "system_position"} == {
        "centrality": 1,
        "entrypoint": False,
        "id": function_id,
        "kind": "function",
        "language": "python",
        "loc": 11,
        "partial": False,
        "region_id": region_id,
        "system_orbit": {
            "call_depth": 1,
            "kind": "certain-call",
            "radius": 34,
            "ring": 1,
        },
    }
    assert function["system_position"] != {"x": 12.5, "y": -3.0, "z": 9.25}
    assert payload["edges"] == [
        {
            "certain": True,
            "kind": "call",
            "source_id": module_id,
            "target_id": function_id,
        }
    ]
    _assert_closed_schema(document, labels=False, understanding=False)

    forbidden = (
        b"/Users/alice",
        b"private/",
        b"secret.app",
        b"send_payroll",
        b"employee_ssn",
        b"requests.post",
        b"raw-file-sha256",
        b"fastapi-decorator",
        b'"understood":',
        b'"lineno":',
        b'"snippet":',
    )
    assert all(value not in encoded for value in forbidden)


def test_labels_and_understanding_require_explicit_publisher_choices() -> None:
    artifact = ShareArtifact.from_graph(
        _sensitive_graph(),
        SharePolicy(
            expires_at=CREATED_AT + timedelta(days=7),
            include_labels=True,
            include_understanding=True,
        ),
        CREATED_AT,
    )

    encoded = artifact.to_bytes()
    payload = json.loads(encoded)["payload"]

    nodes_by_label = {node["label"]: node for node in payload["nodes"]}
    assert set(nodes_by_label) == {"secret.app", "send_payroll"}
    assert nodes_by_label["secret.app"]["understood"] is False
    assert nodes_by_label["send_payroll"]["understood"] is True
    assert payload["regions"][0]["label"] == "secret.app"
    assert payload["regions"][0]["understood"] is True
    assert payload["regions"][0]["layout"] != {"x": 100.0, "y": 50.0, "z": -25.0}
    _assert_closed_schema(
        {"manifest": json.loads(encoded)["manifest"], "payload": payload},
        labels=True,
        understanding=True,
    )
    assert b"private/" not in encoded
    assert b"raw-file-sha256" not in encoded
    assert b"employee_ssn" not in encoded


@pytest.mark.parametrize("field", ("include_labels", "include_understanding"))
def test_disclosure_choices_require_literal_booleans(field: str) -> None:
    policy = replace(
        SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
        **{field: "yes"},
    )

    with pytest.raises(TypeError, match=f"{field} must be a boolean"):
        ShareArtifact.from_graph(_sensitive_graph(), policy, CREATED_AT)


def test_manifest_binds_expiry_and_digest_to_the_exact_payload() -> None:
    artifact = ShareArtifact.from_graph(
        _sensitive_graph(),
        SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
        CREATED_AT,
    )

    document = json.loads(artifact.to_bytes())
    payload_bytes = rfc8785.dumps(document["payload"])

    assert document["payload"]["schema_version"] == 1
    assert document["manifest"] == {
        "schema_version": 1,
        "producer": {
            "codemble_version": __version__,
            "graph_schema_version": 11,
        },
        "created_at": "2026-08-26T12:00:00Z",
        "expires_at": "2026-09-02T12:00:00Z",
        "payload_digest": f"sha256:{sha256(payload_bytes).hexdigest()}",
        "declared_exclusions": [
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
        ],
        "coverage": {
            "nodes": 2,
            "partial_sources": 0,
            "regions": 1,
            "source_files": 1,
            "unsupported_sources": 2,
        },
    }


def test_serialization_uses_rfc_8785_number_and_key_canonicalization() -> None:
    value = {
        "numbers": [1.0, -0.0, 1e-7, 1e-6],
        "\ufb33": "Hebrew letter",
        "😀": "Emoji",
        "€": "Euro",
        "\r": "Carriage return",
        "1": "One",
        "\u0080": "Control",
    }

    assert share_artifact._canonical_json(value) == (
        b'{"\\r":"Carriage return","1":"One",'
        b'"numbers":[1,0,1e-7,0.000001],"\xc2\x80":"Control",'
        b'"\xe2\x82\xac":"Euro",'
        b'"\xf0\x9f\x98\x80":"Emoji","\xef\xac\xb3":"Hebrew letter"}'
    )


def test_share_artifact_cannot_be_constructed_from_unvalidated_bytes() -> None:
    with pytest.raises(TypeError, match="must be compiled with from_graph"):
        ShareArtifact(b'{"payload":{"raw_source":"secret"}}')
    with pytest.raises(TypeError, match="must be compiled with from_graph"):
        ShareArtifact()


@pytest.mark.parametrize(
    ("created_at", "expires_at", "message"),
    (
        (
            CREATED_AT.replace(tzinfo=None),
            CREATED_AT + timedelta(days=7),
            "created_at must be timezone-aware",
        ),
        (
            CREATED_AT,
            (CREATED_AT + timedelta(days=7)).replace(tzinfo=None),
            "expires_at must be timezone-aware",
        ),
        (CREATED_AT, CREATED_AT, "expires_at must be after created_at"),
        (
            CREATED_AT,
            CREATED_AT + timedelta(days=30, seconds=1),
            "expires_at exceeds the 30-day maximum",
        ),
    ),
)
def test_expiry_is_absolute_finite_and_bounded(
    created_at: datetime,
    expires_at: datetime,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ShareArtifact.from_graph(
            _sensitive_graph(),
            SharePolicy(expires_at=expires_at),
            created_at,
        )


def test_manifest_preserves_subsecond_expiry_precision() -> None:
    created_at = CREATED_AT + timedelta(microseconds=100)
    expires_at = CREATED_AT + timedelta(microseconds=900)

    document = json.loads(
        ShareArtifact.from_graph(
            _sensitive_graph(),
            SharePolicy(expires_at=expires_at),
            created_at,
        ).to_bytes()
    )

    assert document["manifest"]["created_at"] == "2026-08-26T12:00:00.000100Z"
    assert document["manifest"]["expires_at"] == "2026-08-26T12:00:00.000900Z"


def test_artifact_routes_and_bytes_are_deterministic_across_input_order() -> None:
    graph = _sensitive_graph()
    worker = Node(
        id="secret.worker",
        kind="module",
        name="secret.worker",
        language="python",
        file="private/worker.py",
        lineno=1,
        end_lineno=25,
        loc=25,
        region="secret.worker",
        centrality=0,
        system_orbit=SystemOrbit(ring=0, radius=0.0, call_depth=0, kind="origin"),
    )
    worker_region = Region(
        id="secret.worker",
        language="python",
        loc=25,
        centrality=0,
        node_count=1,
        understood=False,
        home=False,
        x=-80.0,
        y=12.0,
        z=44.0,
        community=4,
        hops_from_home=1,
        community_family=3,
    )
    import_edge = Edge(
        src="secret.app",
        dst="secret.worker",
        kind="import",
        certain=True,
        lineno=2,
    )
    route = RegionEdge(src="secret.app", dst="secret.worker", weight=1, certain=True)
    first = replace(
        graph,
        nodes=(*graph.nodes, worker),
        edges=(*graph.edges, import_edge),
        regions=(*graph.regions, worker_region),
        region_edges=(route,),
        file_hashes={**graph.file_hashes, "private/worker.py": "worker-hash"},
    )
    second = replace(
        first,
        nodes=tuple(reversed(first.nodes)),
        edges=tuple(reversed(first.edges)),
        regions=tuple(reversed(first.regions)),
        region_edges=tuple(reversed(first.region_edges)),
        file_hashes=dict(reversed(tuple(first.file_hashes.items()))),
    )
    policy = SharePolicy(expires_at=CREATED_AT + timedelta(days=30))

    first_bytes = ShareArtifact.from_graph(first, policy, CREATED_AT).to_bytes()
    second_bytes = ShareArtifact.from_graph(second, policy, CREATED_AT).to_bytes()

    assert first_bytes == second_bytes
    assert json.loads(first_bytes)["payload"]["region_edges"] == [
        {
            "certain": True,
            "source_id": _opaque_id("region", "secret.app"),
            "target_id": _opaque_id("region", "secret.worker"),
            "weight": 1,
        }
    ]


def test_separate_artifacts_use_unlinkable_ids_and_layouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = iter((b"a" * 32, b"b" * 32))
    monkeypatch.setattr(share_artifact, "token_bytes", lambda size: next(keys)[:size])
    policy = SharePolicy(expires_at=CREATED_AT + timedelta(days=7))

    first = json.loads(ShareArtifact.from_graph(_sensitive_graph(), policy, CREATED_AT).to_bytes())
    second = json.loads(ShareArtifact.from_graph(_sensitive_graph(), policy, CREATED_AT).to_bytes())

    assert {node["id"] for node in first["payload"]["nodes"]}.isdisjoint(
        node["id"] for node in second["payload"]["nodes"]
    )
    assert {region["id"] for region in first["payload"]["regions"]}.isdisjoint(
        region["id"] for region in second["payload"]["regions"]
    )
    assert first["payload"]["regions"][0]["layout"] != second["payload"]["regions"][0][
        "layout"
    ]
    first_non_origin = next(
        node for node in first["payload"]["nodes"] if node["system_orbit"]["ring"] > 0
    )
    second_non_origin = next(
        node for node in second["payload"]["nodes"] if node["system_orbit"]["ring"] > 0
    )
    assert first_non_origin["system_position"] != second_non_origin["system_position"]
    assert first != second
    assert b"a" * 32 not in rfc8785.dumps(first)
    assert b"b" * 32 not in rfc8785.dumps(second)


def test_possible_unresolved_edges_are_omitted_and_projected_edges_are_deduplicated() -> None:
    graph = _sensitive_graph()
    duplicate = replace(graph.edges[0], lineno=25)
    unresolved = Edge(
        src="secret.app.send_payroll",
        dst="possible.private.target",
        kind="call",
        certain=False,
        lineno=28,
    )
    artifact = ShareArtifact.from_graph(
        replace(graph, edges=(*graph.edges, duplicate, unresolved)),
        SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
        CREATED_AT,
    )

    encoded = artifact.to_bytes()
    payload = json.loads(encoded)["payload"]
    assert len(payload["edges"]) == 1
    assert b"possible.private.target" not in encoded


def test_artifact_fails_closed_on_incomplete_render_relationships() -> None:
    graph = _sensitive_graph()
    invalid_graphs = (
        (
            replace(
                graph,
                nodes=(graph.nodes[0], replace(graph.nodes[1], id=graph.nodes[0].id)),
                edges=(),
            ),
            "duplicate node identity in the render graph",
        ),
        (
            replace(graph, regions=(graph.regions[0], graph.regions[0])),
            "duplicate region identity in the render graph",
        ),
        (
            replace(graph, regions=()),
            "node region is absent from the render graph",
        ),
        (
            replace(
                graph,
                edges=(
                    *graph.edges,
                    Edge(
                        src="secret.app",
                        dst="secret.missing",
                        kind="call",
                        certain=True,
                        lineno=4,
                    ),
                ),
            ),
            "certain relationship target is absent from the render graph",
        ),
        (
            replace(
                graph,
                region_edges=(
                    RegionEdge(
                        src="secret.app",
                        dst="secret.missing",
                        weight=1,
                        certain=True,
                    ),
                ),
            ),
            "region edge is outside the closed render schema",
        ),
        (
            replace(
                graph,
                edges=(replace(graph.edges[0], external=True), graph.edges[1]),
            ),
            "internal relationship is marked external",
        ),
        (
            replace(
                graph,
                region_edges=(
                    RegionEdge(
                        src="secret.app",
                        dst="secret.app",
                        weight=99,
                        certain=True,
                    ),
                ),
            ),
            "region edges do not match represented imports",
        ),
        (
            replace(graph, selected_entrypoint="secret.missing"),
            "selected entrypoint is absent from the render graph",
        ),
        (
            replace(graph, entrypoint_candidates=()),
            "selected entrypoint is not a ranked candidate",
        ),
        (
            replace(graph, regions=(replace(graph.regions[0], home=False),)),
            "Home region does not match the selected entrypoint",
        ),
        (
            replace(graph, selected_entrypoint=None),
            "Home region exists without a selected entrypoint",
        ),
        (
            replace(graph, regions=(replace(graph.regions[0], node_count=1),)),
            "region node count does not match the render graph",
        ),
        (
            replace(graph, regions=(replace(graph.regions[0], hops_from_home=17),)),
            "Home region and route distance do not match represented imports",
        ),
        (
            replace(
                graph,
                nodes=(
                    graph.nodes[0],
                    replace(
                        graph.nodes[1],
                        system_orbit=SystemOrbit(
                            ring=0,
                            radius=34,
                            call_depth=7,
                            kind="unreached",
                        ),
                    ),
                ),
            ),
            "system orbit truth does not match represented calls",
        ),
    )

    for invalid, message in invalid_graphs:
        with pytest.raises(ValueError, match=message):
            ShareArtifact.from_graph(
                invalid,
                SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
                CREATED_AT,
            )


@pytest.mark.parametrize(
    ("graph", "message"),
    (
        (
            replace(
                _sensitive_graph(),
                nodes=(replace(_sensitive_graph().nodes[0], kind="secret"),),
                edges=(),
                regions=(replace(_sensitive_graph().regions[0], node_count=1),),
            ),
            "unsupported node kind",
        ),
        (
            replace(
                _sensitive_graph(),
                nodes=(replace(_sensitive_graph().nodes[0], loc=-1), _sensitive_graph().nodes[1]),
            ),
            "node metrics must be bounded non-negative integers",
        ),
        (
            replace(
                _sensitive_graph(),
                regions=(replace(_sensitive_graph().regions[0], x=float("nan")),),
            ),
            "layout coordinates exceed the render-safe bound",
        ),
        (
            replace(
                _sensitive_graph(),
                nodes=(
                    replace(_sensitive_graph().nodes[0], system_orbit=None),
                    _sensitive_graph().nodes[1],
                ),
            ),
            "node is missing render-ready system orbit",
        ),
        (
            replace(
                _sensitive_graph(),
                nodes=(
                    replace(
                        _sensitive_graph().nodes[0],
                        language="/Users/alice/private.py",
                    ),
                    _sensitive_graph().nodes[1],
                ),
            ),
            "unsupported language in the render graph",
        ),
        (
            replace(
                _sensitive_graph(),
                file_hashes={
                    **_sensitive_graph().file_hashes,
                    "private/unrepresented.py": "fabricated",
                },
            ),
            "parser coverage does not match represented node sources",
        ),
    ),
)
def test_artifact_rejects_values_outside_the_closed_render_schema(
    graph: Graph,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ShareArtifact.from_graph(
            graph,
            SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
            CREATED_AT,
        )


def test_opted_in_labels_and_graph_schema_are_runtime_validated() -> None:
    graph = _sensitive_graph()
    invalid_label = replace(
        graph,
        nodes=(graph.nodes[0], replace(graph.nodes[1], name=42)),
    )
    with pytest.raises(ValueError, match="share label is not a bounded UTF-8 string"):
        ShareArtifact.from_graph(
            invalid_label,
            SharePolicy(
                expires_at=CREATED_AT + timedelta(days=7),
                include_labels=True,
            ),
            CREATED_AT,
        )

    object.__setattr__(graph, "schema_version", True)
    with pytest.raises(ValueError, match="unsupported render graph schema version"):
        ShareArtifact.from_graph(
            graph,
            SharePolicy(expires_at=CREATED_AT + timedelta(days=7)),
            CREATED_AT,
        )
