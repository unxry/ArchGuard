import shutil
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

from archguard.application.build_iam import BuildIAM
from archguard.application.check_architecture import CheckArchitecture
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.check_result import ArchitectureCheckResult
from archguard.architecture.conformance.models import ConformanceStatus
from archguard.architecture.graph.analyzer import GraphAnalyzer, serialize_graph_result
from archguard.architecture.graph.config import GraphAnalysisConfig, GraphProjectionSpec
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.core.findings.enums import DetectorSource, Severity
from archguard.core.model.enums import EdgeKind, NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam.model import ArchitectureModel
from archguard.iam_building.serialization import serialize_iam
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.graph_configuration import load_graph_configuration
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/graph"
SPEC = ROOT / "examples/architecture/circular-component.yaml"


def building() -> BuildIAM:
    return BuildIAM(
        ParseRepository(create_parser_registry()),
        create_extractor_registry(),
        ExtractionConfig(repository_namespace="graph-tests"),
    )


def build(path: Path) -> ArchitectureModel:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(path))
    ) as repository:
        return building().execute(repository.snapshot, repository.workspace).iam


@pytest.fixture(scope="module")
def cyclic() -> ArchitectureModel:
    return build(FIXTURES / "cyclic/java")


@pytest.mark.parametrize(
    "fixture,nodes,edges,cycles",
    [
        ("acyclic/java", 3, 2, 0),
        ("cyclic/java", 3, 3, 1),
        ("cyclic/typescript", 3, 3, 1),
        ("mixed", 7, 6, 2),
    ],
)
def test_real_java_typescript_tsx_and_mixed_pipeline(
    fixture: str, nodes: int, edges: int, cycles: int
) -> None:
    iam = build(FIXTURES / fixture)
    result = GraphAnalyzer().analyze(iam)
    assert result.is_valid and result.is_complete
    assert len(result.graph.nodes) == nodes and len(result.graph.edges) == edges
    assert len(result.cycles) == cycles and not result.findings and not result.candidates
    assert len(result.metrics) == nodes
    lookup = {node.id: node for node in iam.nodes}
    assert all(
        lookup[proof.source_node_id].language == lookup[proof.target_node_id].language
        for edge in result.graph.edges
        for proof in edge.proofs
    )


def test_arch003_requires_explicit_rule_and_has_grounded_closed_trace(
    cyclic: ArchitectureModel,
) -> None:
    without = GraphAnalyzer().analyze(cyclic)
    assert len(without.cycles) == 1 and not without.findings and without.conformance is None
    result = GraphAnalyzer().analyze(cyclic, spec=load_architecture_file(SPEC))
    (finding,) = result.findings
    assert finding.rule_id == "ARCH003" and finding.detector.source == DetectorSource.GRAPH
    assert finding.severity == Severity.HIGH and finding.confidence is None
    assert finding.trace and finding.trace.steps[0].node_id == finding.trace.steps[-1].node_id
    assert [step.label for step in finding.trace.steps] == [
        "sample.a.A",
        "sample.b.B",
        "sample.c.C",
        "sample.a.A",
    ]
    assert len(finding.metadata["scc_members"]) == 3
    iam_ids = {edge.id for edge in cyclic.edges}
    for step in finding.trace.steps[1:]:
        assert step.location and step.edge_id
        assert set(step.metadata["iam_edge_ids"]) <= {str(item) for item in iam_ids}
    graph_evidence = finding.evidence[1].properties
    assert (
        graph_evidence["edges"]
        and graph_evidence["representative_cycle"]["node_ids"][0]
        == graph_evidence["representative_cycle"]["node_ids"][-1]
    )
    raw = serialize_graph_result(result)
    restored = GraphAnalysisResult.model_validate_json(raw)
    assert serialize_graph_result(restored) == raw
    assert "GRAPH_PRIVATE_SOURCE_MARKER" not in raw and str(ROOT) not in raw
    assert result.conformance.status == ConformanceStatus.NON_CONFORMANT


@pytest.mark.parametrize("projection", list(GraphProjection))
def test_all_five_projections_and_provenance(
    cyclic: ArchitectureModel, projection: GraphProjection
) -> None:
    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                "layers": [{"name": name, "include": [name + "/**"]} for name in "abc"],
                "modules": [{"name": name, "include": [name + "/**"]} for name in "abc"],
            },
        }
    )
    before = serialize_iam(cyclic)
    result = GraphAnalyzer().analyze(
        cyclic, GraphAnalysisConfig(projection=GraphProjectionSpec(projection=projection)), spec
    )
    assert result.is_valid and result.is_complete
    assert len(result.graph.nodes) == len(result.graph.edges) == 3 and len(result.cycles) == 1
    assert serialize_iam(cyclic) == before
    assert result.projection_statistics.self_edges_removed == 3
    assert all(
        set(edge.relation_kinds) == {EdgeKind.IMPORTS, EdgeKind.CALLS}
        for edge in result.graph.edges
    )
    assert all(sum(proof.occurrences for proof in edge.proofs) == 3 for edge in result.graph.edges)
    assert all(len(edge.proofs) == 2 for edge in result.graph.edges)
    if projection == GraphProjection.COMPONENT:
        assert all(
            node.kind == NodeKind.CLASS and node.method_count == node.member_count == 2
            for node in result.graph.nodes
        )
    if projection == GraphProjection.PACKAGE:
        assert {node.label for node in result.graph.nodes} == {"sample.a", "sample.b", "sample.c"}


def test_package_does_not_create_fake_ts_packages() -> None:
    result = GraphAnalyzer().analyze(
        build(FIXTURES / "cyclic/typescript"),
        GraphAnalysisConfig(projection=GraphProjectionSpec(projection=GraphProjection.PACKAGE)),
    )
    assert not result.graph.nodes and not result.is_complete
    assert result.diagnostics[0].code == "PACKAGE_LANGUAGE_UNSUPPORTED"


@pytest.mark.parametrize(
    "projection", [GraphProjection.TARGET_LAYER, GraphProjection.TARGET_MODULE]
)
def test_target_projection_requires_valid_classification(
    cyclic: ArchitectureModel, projection: GraphProjection
) -> None:
    config = GraphAnalysisConfig(projection=GraphProjectionSpec(projection=projection))
    assert not GraphAnalyzer().analyze(cyclic, config).is_valid
    dimension = "layers" if projection == GraphProjection.TARGET_LAYER else "modules"
    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                dimension: [
                    {"name": "all", "include": ["**"]},
                    {"name": "overlap", "include": ["**"]},
                ]
            },
        }
    )
    invalid = GraphAnalyzer().analyze(cyclic, config, spec)
    assert not invalid.is_valid and not invalid.findings
    raw = spec.model_dump(mode="json")
    raw["rules"] = [{"id": "ARCH003", "type": "circular_dependency", "projection": projection}]
    conformance = GraphAnalyzer().analyze(
        cyclic, spec=ArchitectureSpecification.model_validate(raw)
    )
    assert not conformance.is_valid and not conformance.findings and conformance.cycles
    spec = ArchitectureSpecification.model_validate(
        {"version": "1.0", "architecture": {dimension: [{"name": "a", "include": ["a/**"]}]}}
    )
    partial = GraphAnalyzer().analyze(cyclic, config, spec)
    assert partial.is_valid and len(partial.graph.nodes) == 1
    assert partial.projection_statistics.unclassified_nodes_excluded > 0
    assert {node.label for node in partial.graph.nodes} == {"a"}


def test_file_import_with_multiple_components_retains_file_node(tmp_path: Path) -> None:
    (tmp_path / "a.ts").write_text(
        'import { B } from "./b"; export class A { static run() { B.ping(); } }'
    )
    (tmp_path / "b.ts").write_text("export class B { static ping() {} } export class C {}")
    result = GraphAnalyzer().analyze(build(tmp_path))
    lookup = {node.id: node for node in result.graph.nodes}
    imports = next(edge for edge in result.graph.edges if EdgeKind.IMPORTS in edge.relation_kinds)
    calls = next(edge for edge in result.graph.edges if EdgeKind.CALLS in edge.relation_kinds)
    assert lookup[imports.target_id].kind == NodeKind.FILE
    assert (
        lookup[calls.target_id].kind == NodeKind.CLASS
        and lookup[calls.target_id].label == "b.ts::B"
    )
    assert imports.target_id != calls.target_id


def test_external_self_and_relation_filters(tmp_path: Path, cyclic: ArchitectureModel) -> None:
    (tmp_path / "a.ts").write_text(
        'import { External } from "library"; '
        "export class A { static ping() {} static run() { A.ping(); } }"
    )
    iam = build(tmp_path)
    default = GraphAnalyzer().analyze(iam)
    assert default.projection_statistics.external_nodes_excluded == 1 and not default.graph.edges
    assert default.projection_statistics.self_edges_removed == 1
    explicit = GraphAnalyzer().analyze(
        iam,
        GraphAnalysisConfig(
            projection=GraphProjectionSpec(include_external=True, include_self_edges=True)
        ),
    )
    assert len(explicit.graph.nodes) == 2 and len(explicit.graph.edges) == 2
    assert not explicit.cycles
    empty = GraphAnalyzer().analyze(
        cyclic, GraphAnalysisConfig(projection=GraphProjectionSpec(included_relations=()))
    )
    assert not empty.graph.edges and not empty.cycles
    assert all(item.instability is None for item in empty.metrics)


@pytest.mark.parametrize("limit", ["max_graph_nodes", "max_graph_edges"])
def test_graph_resource_limits_return_invalid_diagnostic(
    cyclic: ArchitectureModel, limit: str
) -> None:
    result = GraphAnalyzer().analyze(cyclic, GraphAnalysisConfig.model_validate({limit: 1}))
    assert not result.is_valid and not result.graph.nodes and not result.graph.edges
    assert result.diagnostics[0].code == "GRAPH_RESOURCE_LIMIT"
    assert not result.metrics and not result.findings


def test_cycle_trace_limit_cannot_claim_partial_finding(cyclic: ArchitectureModel) -> None:
    result = GraphAnalyzer().analyze(
        cyclic, GraphAnalysisConfig(max_cycle_trace_length=3), load_architecture_file(SPEC)
    )
    assert result.is_valid and not result.is_complete
    assert result.cycles[0].truncated and not result.findings
    assert any(item.code == "CYCLE_TRACE_LIMIT" for item in result.diagnostics)
    assert result.conformance.status == ConformanceStatus.INCOMPLETE


def test_rule_projection_and_relations_are_independent_of_discovery_config(
    cyclic: ArchitectureModel,
) -> None:
    data = load_architecture_file(SPEC).model_dump(mode="json", by_alias=True)
    data["rules"][0]["relations"] = ["CALLS"]
    result = GraphAnalyzer().analyze(
        cyclic,
        GraphAnalysisConfig(
            projection=GraphProjectionSpec(projection=GraphProjection.FILE, included_relations=())
        ),
        ArchitectureSpecification.model_validate(data),
    )
    assert not result.cycles and len(result.findings) == 1
    assert result.conformance.graph.projection.projection == GraphProjection.COMPONENT
    assert all(edge.relation_kinds == (EdgeKind.CALLS,) for edge in result.conformance.graph.edges)
    data["rules"][0]["relations"] = ["CREATES"]
    assert (
        not GraphAnalyzer()
        .analyze(cyclic, spec=ArchitectureSpecification.model_validate(data))
        .findings
    )
    data["rules"][0]["enabled"] = False
    disabled = GraphAnalyzer().analyze(cyclic, spec=ArchitectureSpecification.model_validate(data))
    assert disabled.cycles and not disabled.findings and disabled.conformance is None


def test_multiple_cycle_findings_are_per_scc_not_per_simple_cycle(tmp_path: Path) -> None:
    for name, targets in {"A": ["B"], "B": ["A", "C"], "C": ["B"], "D": ["E"], "E": ["D"]}.items():
        imports = " ".join(f'import {{ {target} }} from "./{target}";' for target in targets)
        calls = " ".join(f"{target}.ping();" for target in targets)
        (tmp_path / f"{name}.ts").write_text(
            f"{imports} export class {name} {{ static run() {{ {calls} }} static ping() {{}} }}"
        )
    result = GraphAnalyzer().analyze(build(tmp_path), spec=load_architecture_file(SPEC))
    assert len(result.cycles) == len(result.findings) == 2
    assert sorted(len(finding.metadata["scc_members"]) for finding in result.findings) == [2, 3]


def test_real_candidate_thresholds_and_proof_counts() -> None:
    model = build(FIXTURES / "hub")
    config = load_graph_configuration(ROOT / "examples/graph/research-demo.json")
    result = GraphAnalyzer().analyze(model, config)
    assert result.is_valid and result.is_complete and not result.findings
    assert result.statistics.candidate_count_by_rule == {
        "ARCH101": 2,
        "ARCH102": 1,
        "ARCH103": 1,
        "ARCH104": 1,
        "ARCH105": 2,
    }
    labels = {node.id: node.label for node in result.graph.nodes}
    hub = next(item for item in result.metrics if labels[item.node_id] == "Stable.ts::Stable")
    assert hub.afferent_coupling == 4 and hub.efferent_coupling == 1 and hub.instability == 0.2
    assert (
        Counter(item.rule_id for item in result.candidates)
        == result.statistics.candidate_count_by_rule
    )
    raw = serialize_graph_result(result)
    assert raw == serialize_graph_result(GraphAnalysisResult.model_validate_json(raw))


def test_architecture_check_aggregates_static_and_graph_once() -> None:
    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                "layers": [{"name": name, "include": [name + "/**"]} for name in "abc"]
            },
            "rules": [
                {"id": "ARCH002", "type": "layer_dependency", "from": "a", "allow": ["c"]},
                {"id": "ARCH003", "type": "circular_dependency"},
            ],
        }
    )
    engine = building()
    with (
        create_discovery().open(
            RepositoryInput(
                source_type=RepositorySourceType.LOCAL, location=str(FIXTURES / "cyclic/java")
            )
        ) as repository,
        patch.object(engine, "execute", wraps=engine.execute) as execute,
    ):
        result = CheckArchitecture(engine).execute(repository.snapshot, repository.workspace, spec)
        assert execute.call_count == 1
    assert isinstance(result, ArchitectureCheckResult)
    assert result.status == ConformanceStatus.NON_CONFORMANT
    assert [item.rule_id for item in result.findings] == ["ARCH002", "ARCH003"]
    assert result.statistics.rules_enabled == result.statistics.rules_evaluated == 2
    assert len(result.static_result.findings) == len(result.graph_result.findings) == 1
    graph_only = GraphAnalyzer().analyze(build(FIXTURES / "cyclic/java"), spec=spec)
    assert [item.rule_id for item in graph_only.findings] == ["ARCH003"]


@pytest.mark.parametrize("projection", list(GraphProjection))
def test_arch003_projections_have_closed_grounded_traces(
    cyclic: ArchitectureModel, projection: GraphProjection
) -> None:
    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                dimension: [{"name": name, "include": [name + "/**"]} for name in "abc"]
                for dimension in ("layers", "modules")
            },
            "rules": [{"id": "ARCH003", "type": "circular_dependency", "projection": projection}],
        }
    )
    result = GraphAnalyzer().analyze(cyclic, spec=spec)
    assert result.is_valid and result.is_complete and len(result.findings) == 1
    assert result.conformance and result.conformance.graph
    trace = result.findings[0].trace
    assert trace and trace.steps[0].node_id == trace.steps[-1].node_id
    assert len(trace.steps) == 4
    graph_ids = {str(node.id) for node in result.conformance.graph.nodes}
    assert all(str(step.node_id) in graph_ids for step in trace.steps)


def test_mixed_import_call_cycle_respects_selected_relations(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_text(
        "package sample; import sample.B; public class A { public static void ping() {} }"
    )
    (tmp_path / "B.java").write_text(
        "package sample; public class B { static void run() { sample.A.ping(); } }"
    )
    iam = build(tmp_path)
    all_relations = GraphAnalyzer().analyze(iam, spec=load_architecture_file(SPEC))
    assert len(all_relations.cycles) == len(all_relations.findings) == 1
    assert {edge.relation_kinds for edge in all_relations.graph.edges} == {
        (EdgeKind.IMPORTS,),
        (EdgeKind.CALLS,),
    }
    for kind in (EdgeKind.IMPORTS, EdgeKind.CALLS):
        filtered = GraphAnalyzer().analyze(
            iam, GraphAnalysisConfig(projection=GraphProjectionSpec(included_relations=(kind,)))
        )
        assert len(filtered.graph.edges) == 1 and not filtered.cycles


def test_truncated_provenance_remains_honest_and_grounded(cyclic: ArchitectureModel) -> None:
    iam = cyclic.model_copy(deep=True)
    for edge in iam.edges:
        if edge.attributes["occurrences"] > 1:
            edge.attributes["provenance"].pop()
            edge.attributes["provenance_truncated"] = 1
    result = GraphAnalyzer().analyze(iam, spec=load_architecture_file(SPEC))
    assert result.is_valid and not result.is_complete and len(result.findings) == 1
    assert any(proof.provenance_truncated for edge in result.graph.edges for proof in edge.proofs)


def test_order_root_line_stability_and_no_source_metadata(
    cyclic: ArchitectureModel, tmp_path: Path
) -> None:
    spec = load_architecture_file(SPEC)
    expected = GraphAnalyzer().analyze(cyclic, spec=spec)
    shuffled = cyclic.model_copy(
        update={
            "nodes": tuple(reversed(cyclic.nodes)),
            "edges": tuple(reversed(cyclic.edges)),
            "source_files": tuple(reversed(cyclic.source_files)),
        }
    )
    assert serialize_graph_result(
        GraphAnalyzer().analyze(shuffled, spec=spec)
    ) == serialize_graph_result(expected)
    copy = tmp_path / "another-root"
    shutil.copytree(FIXTURES / "cyclic/java", copy)
    assert serialize_graph_result(
        GraphAnalyzer().analyze(build(copy), spec=spec)
    ) == serialize_graph_result(expected)
    path = copy / "a/A.java"
    path.write_text("\n" + path.read_text().replace("B.ping();", "B.ping(); B.ping();"))
    updated = GraphAnalyzer().analyze(build(copy), spec=spec)
    assert updated.findings[0].id == expected.findings[0].id
    assert updated.findings[0].related_locations != expected.findings[0].related_locations
    assert (
        updated.reproducibility.snapshot_fingerprint
        != expected.reproducibility.snapshot_fingerprint
    )


def test_incomplete_unproven_and_invalid_iam_do_not_invent_dependencies(
    cyclic: ArchitectureModel,
) -> None:
    changed = cyclic.model_copy(deep=True)
    changed.metadata["is_complete"] = False
    result = GraphAnalyzer().analyze(changed, spec=load_architecture_file(SPEC))
    assert not result.is_complete and result.findings
    changed.metadata["is_valid"] = False
    invalid = GraphAnalyzer().analyze(changed, spec=load_architecture_file(SPEC))
    assert not invalid.is_valid and not invalid.findings
    uncertain = cyclic.model_copy(deep=True)
    for edge in uncertain.edges:
        edge.attributes["provenance"][0]["resolution_status"] = "AMBIGUOUS"
    excluded = GraphAnalyzer().analyze(uncertain, spec=load_architecture_file(SPEC))
    assert not excluded.graph.edges and not excluded.findings and not excluded.is_complete
    assert excluded.projection_statistics.unproven_edges > 0
    private = cyclic.model_copy(deep=True)
    for edge in private.edges:
        edge.attributes["provenance"][0]["raw_source"] = "PRIVATE_RAW_SOURCE"
    assert "PRIVATE_RAW_SOURCE" not in serialize_graph_result(GraphAnalyzer().analyze(private))
