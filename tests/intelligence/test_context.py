import hashlib
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from archguard.application.analyze_architecture_semantics import AnalyzeArchitectureSemantics
from archguard.architecture.graph.enums import NeighbourhoodDirection as Direction
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.fragments import extract_fragments
from archguard.architecture.intelligence.models import (
    AIAnalysisConfig,
    SelectedNode,
    canonical,
    serialize_ai,
)
from archguard.architecture.intelligence.models import (
    ContextSelectionConfig as Config,
)
from archguard.architecture.intelligence.models import (
    ContextStrategy as Strategy,
)
from archguard.architecture.intelligence.selection import (
    ContextSelectionError,
    filtered_graph,
    resolve_node,
    select_context_nodes,
)
from archguard.core.locations import SourceLocation
from archguard.core.model.enums import EdgeKind, NodeKind
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.intelligence.conftest import building


def pack(chain, name="B", **kwargs):
    inputs, workspace, _ = chain
    return GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, name),
        inputs.iam,
        inputs.graph,
        workspace,
        Config(**kwargs),
        discovery=inputs.discovery,
    )


@pytest.mark.parametrize(
    "name,direction,hops,expected",
    [
        ("B", Direction.BOTH, 1, {"A", "B", "C"}),
        ("A", Direction.OUT, 1, {"A", "B"}),
        ("A", Direction.IN, 1, {"A"}),
        ("A", Direction.OUT, 2, {"A", "B", "C"}),
        ("B", Direction.BOTH, 0, {"B"}),
    ],
)
def test_k_hop_direction_and_unrelated_node(chain, name, direction, hops, expected):
    result = pack(
        chain, name, direction=direction, hop_count=hops, included_relations=(EdgeKind.CALLS,)
    )
    names = {n.id: n.name for n in chain[0].iam.nodes}
    assert {names[n.node_id] for n in result.manifest.selected_nodes} == expected
    assert result.manifest.selected_nodes[0].node_id == resolve_node(chain[0].iam, name)
    assert len(canonical(result.untrusted_data())) == result.manifest.context_chars


@pytest.mark.parametrize(
    "strategy,expected",
    [(Strategy.LOCAL_ONLY, 1), (Strategy.GRAPH_GUIDED, 3), (Strategy.EXPANDED_BASELINE, 4)],
)
def test_strategies_and_canonical_manifest(chain, strategy, expected):
    first, second = pack(chain, strategy=strategy), pack(chain, strategy=strategy)
    assert len(first.manifest.selected_nodes) == expected
    assert serialize_ai(first.manifest) == serialize_ai(second.manifest)
    assert "PRIVATE_SOURCE_MARKER" not in serialize_ai(first.manifest)
    assert "PRIVATE_SOURCE_MARKER" in canonical(first.untrusted_data())
    assert not first.manifest.truncated
    for fragment in first.fragments:
        assert fragment.reference.content_hash == hashlib.sha256(fragment.text.encode()).hexdigest()


def test_relation_filter_preserves_only_matching_proofs(chain):
    graph = chain[0].graph.graph
    assert any(EdgeKind.CALLS in e.relation_kinds for e in graph.edges)
    filtered = filtered_graph(graph, Config(included_relations=(EdgeKind.IMPORTS,)))
    assert not filtered.edges
    assert len(pack(chain, included_relations=(EdgeKind.IMPORTS,)).manifest.selected_nodes) == 1
    first = graph.edges[0]
    proof = first.proofs[0].model_copy(
        update={"relation": EdgeKind.IMPORTS, "iam_edge_id": chain[0].iam.edges[-1].id}
    )
    # Distinct proof ID even when the fixture's last edge happens to be this proof.
    from uuid import uuid4

    proof = proof.model_copy(update={"iam_edge_id": uuid4()})
    proofs = tuple(sorted((*first.proofs, proof), key=lambda p: str(p.iam_edge_id)))
    mixed = first.model_copy(
        update={"proofs": proofs, "relation_kinds": tuple(sorted({p.relation for p in proofs}))}
    )
    graph = graph.model_copy(update={"edges": (mixed,)})
    filtered = filtered_graph(graph, Config(included_relations=(EdgeKind.IMPORTS,)))
    assert filtered.edges[0].proofs == (proof,)
    assert filtered.edges[0].relation_kinds == (EdgeKind.IMPORTS,)


@pytest.mark.parametrize(
    "budgets",
    [
        {"max_nodes": 1},
        {"max_files": 1},
        {"max_fragments": 1},
        {"max_fragment_chars": 30},
        {"max_total_chars": 512},
        {"max_total_chars": 700},
        {"max_lines_per_fragment": 1},
    ],
)
def test_hard_context_budgets(chain, budgets):
    result = pack(chain, **budgets)
    config, manifest = result.manifest.configuration, result.manifest
    assert manifest.truncated
    assert len(manifest.selected_nodes) <= config.max_nodes
    assert manifest.files <= config.max_files and len(manifest.fragments) <= config.max_fragments
    assert all(len(f.text) <= config.max_fragment_chars for f in result.fragments)
    assert manifest.context_chars <= config.max_total_chars


def test_context_uses_existing_neighbourhood_and_target_first(chain):
    with patch(
        "archguard.architecture.intelligence.selection.neighbourhood",
        wraps=__import__(
            "archguard.architecture.graph.algorithms", fromlist=["neighbourhood"]
        ).neighbourhood,
    ) as query:
        result = pack(chain, hop_count=2)
    assert query.call_count == 2
    assert [n.reason for n in result.manifest.selected_nodes] == [
        "TARGET",
        "DIRECT_OUTGOING",
        "DIRECT_INCOMING",
    ]


def test_fingerprint_uses_selected_source_and_relevant_metadata(chain):
    inputs, workspace, _ = chain
    baseline = pack(chain)

    class Reader:
        @contextmanager
        def open_source_file(self, path):
            with workspace.open_source_file(path) as stream:
                data = stream.read()
            if path == "B.java":
                data = data.replace(b"PRIVATE_SOURCE_MARKER", b"CHANGED_SOURCE_MARKER")
            yield BytesIO(data)

    changed = GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, "B"),
        inputs.iam,
        inputs.graph,
        Reader(),
        Config(),
        discovery=inputs.discovery,
    )
    assert changed.manifest.context_fingerprint != baseline.manifest.context_fingerprint

    # An unrelated fragment reader change is never even consulted.
    class UnrelatedReader:
        @contextmanager
        def open_source_file(self, path):
            assert path != "D.java"
            with workspace.open_source_file(path) as stream:
                yield stream

    unrelated = GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, "B"),
        inputs.iam,
        inputs.graph,
        UnrelatedReader(),
        Config(),
        discovery=inputs.discovery,
    )
    assert serialize_ai(unrelated.manifest) == serialize_ai(baseline.manifest)
    assert all(
        e.data["normative"] is False
        for e in baseline.manifest.evidence
        if e.kind == "DISCOVERY_HYPOTHESIS"
    )


def test_file_and_overlapping_fragment_dedup(chain):
    inputs, workspace, _ = chain
    target = resolve_node(inputs.iam, "B")
    method = next(
        n
        for n in inputs.iam.nodes
        if n.kind == NodeKind.METHOD and n.source_location.file_path == "B.java"
    )
    selected = (
        SelectedNode(node_id=target, distance=0, reason="TARGET"),
        SelectedNode(node_id=method.id, distance=0, reason="SAME_FILE"),
    )
    with patch.object(workspace, "open_source_file", wraps=workspace.open_source_file) as read:
        fragments, _, _, _ = extract_fragments(inputs.iam, selected, workspace, Config(), None)
    assert len(fragments) == 1 and read.call_count == 1
    assert set(fragments[0].reference.node_ids) == {target, method.id}


def test_large_file_method_window_is_streamed_and_bounded(tmp_path):
    text = (
        "package p; class Large {\n"
        + "\n" * 10000
        + "void middle() { int x = 42; }\n"
        + "\n" * 10000
        + "}\n"
    )
    (tmp_path / "Large.java").write_text(text)
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        inputs = AnalyzeArchitectureSemantics(building()).prepare(
            repo.snapshot, repo.workspace, AIAnalysisConfig()
        )
        method = next(n for n in inputs.iam.nodes if n.kind == NodeKind.METHOD)

        class Reader:
            lines = 0

            @contextmanager
            def open_source_file(self, path):
                with repo.workspace.open_source_file(path) as stream:

                    class Stream:
                        def readline(inner, count):
                            self.lines += 1
                            return stream.readline(count)

                        def read(inner, *args):
                            raise AssertionError("whole-file context reads forbidden")

                    yield Stream()

        reader = Reader()
        result = GraphGuidedContextBuilder().build(
            method.id, inputs.iam, inputs.graph, reader, Config(strategy=Strategy.LOCAL_ONLY)
        )
        assert "middle" in result.fragments[0].text
        assert reader.lines < 10010
        assert (
            result.fragments[0].reference.end_line - result.fragments[0].reference.start_line <= 4
        )


@pytest.mark.parametrize(
    "path", ["/etc/passwd", "../secret", "a/../../secret", "C:/secret", "a\\b"]
)
def test_relative_path_validation(path):
    with pytest.raises(ValidationError):
        SourceLocation(file_path=path, start_line=1)


def test_invalid_target_and_token_budget_truthfulness(chain):
    with pytest.raises(ContextSelectionError):
        resolve_node(chain[0].iam, "nonexistent")
    with pytest.raises(ContextSelectionError):
        resolve_node(chain[0].iam, "run")
    assert (
        pack(chain, token_budget=100).manifest.diagnostics[0].code
        == "CONTEXT_TOKEN_BUDGET_UNMEASURABLE"
    )


def test_hub_node_budget_and_stable_uuid_order(chain):
    from uuid import uuid5

    from archguard.architecture.graph.models import GraphEdge, GraphNode

    inputs = chain[0]
    origin = next(n for n in inputs.graph.graph.nodes if n.label == "p.B")
    template = next(n for n in inputs.iam.nodes if n.id == origin.id)
    proof = inputs.graph.graph.edges[0].proofs[0]
    nodes, edges, iam_nodes = [origin], [], list(inputs.iam.nodes)
    for index in range(100):
        key = uuid5(inputs.iam.project.id, f"context-hub:{index}")
        iam_nodes.append(template.model_copy(update={"id": key, "name": f"Hub{index}"}))
        nodes.append(GraphNode(id=key, label=f"Hub{index}", iam_node_ids=(key,)))
        edges.append(
            GraphEdge(
                id=uuid5(key, "edge"),
                source_id=origin.id,
                target_id=key,
                relation_kinds=(proof.relation,),
                proofs=(proof,),
            )
        )
    graph = inputs.graph.graph.model_copy(update={"nodes": tuple(nodes), "edges": tuple(edges)})
    iam = inputs.iam.model_copy(update={"nodes": tuple(iam_nodes)})
    selected, dropped = select_context_nodes(iam, graph, origin.id, Config(max_nodes=10))
    assert len(selected) == 10 and dropped == 91 and selected[0].node_id == origin.id
    assert [str(n.node_id) for n in selected[1:]] == sorted(str(n.id) for n in nodes[1:])[:9]


def test_relevant_normalized_target_constraints_do_not_promote_discovery(chain):
    from archguard.architecture.specification.models import ArchitectureSpecification

    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                "layers": [
                    {"name": "selected", "include": ["B.java"]},
                    {"name": "unrelated", "include": ["D.java"]},
                ]
            },
            "rules": [
                {
                    "id": "ARCH001",
                    "type": "forbidden_dependency",
                    "from": {"layer": "selected"},
                    "to": {"layer": "unrelated"},
                    "description": "PRIVATE_UNUSED_RULE_TEXT",
                },
                {
                    "id": "ARCH002",
                    "type": "layer_dependency",
                    "from": "unrelated",
                    "deny": ["selected"],
                },
            ],
        }
    )
    inputs, workspace, _ = chain
    result = GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, "B"),
        inputs.iam,
        inputs.graph,
        workspace,
        Config(strategy=Strategy.LOCAL_ONLY),
        spec,
        inputs.discovery,
    )
    constraints = [e for e in result.manifest.evidence if e.kind == "TARGET_CONSTRAINT"]
    assert len(constraints) == 1 and constraints[0].data["constraint"]["id"] == "ARCH001"
    assert constraints[0].data["normative"] is True
    assert "PRIVATE_UNUSED_RULE_TEXT" not in canonical(result.untrusted_data())


@pytest.mark.parametrize("limits", [{"max_scan_bytes_per_file": 10}, {"max_line_bytes": 10}])
def test_stream_scan_limits_are_visible(chain, limits):
    result = pack(chain, **limits)
    assert result.manifest.truncated


def test_source_failures_are_sanitized_and_redaction_is_explicit(chain):
    inputs, workspace, _ = chain

    class Reader:
        def open_source_file(self, path):
            raise RuntimeError("PRIVATE_SOURCE_MARKER")

    result = GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, Reader()
    )
    assert result.manifest.truncated and result.manifest.diagnostics
    assert "PRIVATE_SOURCE_MARKER" not in serialize_ai(result.manifest)

    class Redactor:
        redactor_id = "fixture-redactor-v1"

        def redact(self, text):
            return text.replace("PRIVATE_SOURCE_MARKER", "REDACTED")

    redacted = GraphGuidedContextBuilder(Redactor()).build(
        resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, workspace
    )
    assert redacted.manifest.redactor_id == "fixture-redactor-v1"
    assert "PRIVATE_SOURCE_MARKER" not in canonical(redacted.untrusted_data())


def test_all_five_relevant_normalized_builtin_constraints(chain):
    from archguard.architecture.specification.models import ArchitectureSpecification

    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                "layers": [
                    {"name": "selected", "include": ["B.java"]},
                    {"name": "other", "include": ["D.java"]},
                ],
                "modules": [
                    {"name": "selected", "include": ["B.java"]},
                    {"name": "other", "include": ["D.java"]},
                ],
            },
            "rules": [
                {
                    "id": "ARCH001",
                    "type": "forbidden_dependency",
                    "from": {"layer": "selected"},
                    "to": {"layer": "other"},
                },
                {
                    "id": "ARCH002",
                    "type": "layer_dependency",
                    "from": "selected",
                    "deny": ["other"],
                },
                {"id": "ARCH003", "type": "circular_dependency"},
                {
                    "id": "ARCH004",
                    "type": "reverse_dependency",
                    "expected": {"from": "selected", "to": "other"},
                },
                {"id": "ARCH005", "type": "module_boundary", "from": "selected", "deny": ["other"]},
            ],
        }
    )
    inputs, workspace, _ = chain
    result = GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, workspace, spec=spec
    )
    assert {
        e.data["constraint"]["id"]
        for e in result.manifest.evidence
        if e.kind == "TARGET_CONSTRAINT"
    } == {"ARCH001", "ARCH002", "ARCH003", "ARCH004", "ARCH005"}


def test_envelope_node_budget_without_source_is_still_enforced(tmp_path):
    for index in range(25):
        (tmp_path / f"Component{index}.java").write_text(f"class Component{index} {{}}\n")
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        inputs = AnalyzeArchitectureSemantics(building()).prepare(
            repo.snapshot, repo.workspace, AIAnalysisConfig()
        )
        result = GraphGuidedContextBuilder().build(
            resolve_node(inputs.iam, "Component0"),
            inputs.iam,
            inputs.graph,
            repo.workspace,
            Config(strategy=Strategy.EXPANDED_BASELINE, max_total_chars=512),
        )
    assert result.manifest.context_chars <= 512 and result.manifest.dropped_nodes > 5
    assert not result.fragments and result.manifest.truncated


@pytest.mark.parametrize("fails", [True, False])
def test_redactor_failure_or_line_shift_cannot_export_source_or_wrong_coordinates(chain, fails):
    inputs, workspace, _ = chain

    class Redactor:
        redactor_id = "broken-fixture-redactor"

        def redact(self, text):
            if fails:
                raise RuntimeError("PRIVATE_SOURCE_MARKER")
            return text + "\n"

    result = GraphGuidedContextBuilder(Redactor()).build(
        resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, workspace
    )
    assert not result.fragments and result.manifest.diagnostics and result.manifest.truncated
    assert "PRIVATE_SOURCE_MARKER" not in serialize_ai(result.manifest)
