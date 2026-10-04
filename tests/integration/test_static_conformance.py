import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from archguard.application.build_iam import BuildIAM
from archguard.application.check_architecture import CheckArchitecture
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.classification.classifier import ArchitectureClassifier
from archguard.architecture.classification.models import ClassificationStatus
from archguard.architecture.conformance.analyzer import (
    StaticConformanceAnalyzer,
    serialize_conformance,
)
from archguard.architecture.conformance.models import ConformanceStatus, StaticConformanceResult
from archguard.architecture.hybrid.contracts import ArchitectureEvidenceBundle
from archguard.architecture.rules.registry import StaticRuleRegistry
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.core.evidence import EvidenceType
from archguard.core.findings.enums import DetectorSource, FindingNamespace, Severity
from archguard.core.identifiers import AnalysisId
from archguard.core.model.enums import EdgeKind, NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam.model import ArchitectureModel
from archguard.iam_building.models import IAMBuildResult
from archguard.iam_building.serialization import serialize_iam
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

FIXTURES = Path(__file__).parents[1] / "fixtures" / "conformance"
EXAMPLES = Path(__file__).parents[2] / "examples" / "architecture"


def build(path: Path, strict: bool = False) -> IAMBuildResult:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(path))
    ) as repository:
        return BuildIAM(
            ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=strict)),
            create_extractor_registry(),
            ExtractionConfig(repository_namespace="conformance-tests"),
        ).execute(repository.snapshot, repository.workspace)


def specification(name: str = "layered-clean") -> ArchitectureSpecification:
    return load_architecture_file(EXAMPLES / f"{name}.yaml")


@pytest.fixture(scope="module")
def violating() -> ArchitectureModel:
    return build(FIXTURES / "violating/java").iam


@pytest.mark.parametrize("language", ["java", "typescript"])
@pytest.mark.parametrize("stage,expected", [("clean", 0), ("violating", 1)])
def test_real_java_and_typescript_pipeline(language: str, stage: str, expected: int) -> None:
    iam = build(FIXTURES / stage / language)
    result = StaticConformanceAnalyzer().analyze(iam.iam, specification())
    assert result.is_valid and result.is_complete
    assert len(result.findings) == expected
    assert result.statistics.rules_evaluated == 1
    assert result.statistics.nodes_unclassified == 0
    assert result.status == (
        ConformanceStatus.NON_CONFORMANT if expected else ConformanceStatus.CONFORMANT
    )
    if expected:
        assert result.findings[0].rule_id == "ARCH002"
    else:
        assert result.statistics.edges_considered > 0


@pytest.mark.parametrize(
    "fixture,rule", [("forbidden", "ARCH001"), ("reverse", "ARCH004"), ("module", "ARCH005")]
)
def test_additional_rules_use_real_resolved_edges(fixture: str, rule: str) -> None:
    result = StaticConformanceAnalyzer().analyze(
        build(FIXTURES / fixture).iam, specification("layered-strict")
    )
    assert result.is_valid and result.is_complete
    assert [finding.rule_id for finding in result.findings] == [rule]
    assert result.statistics.findings_by_rule == {rule: 1}
    assert result.statistics.rules_evaluated == 4


def test_mixed_project_keeps_language_boundaries() -> None:
    built = build(FIXTURES / "violating")
    result = StaticConformanceAnalyzer().analyze(built.iam, specification())
    assert result.is_valid and result.is_complete
    assert len(result.findings) == 2
    nodes = {node.id: node for node in built.iam.nodes}
    assert all(
        nodes[edge.source_id].language == nodes[edge.target_id].language for edge in built.iam.edges
    )
    assert {finding.primary_location.file_path.split("/")[0] for finding in result.findings} == {
        "java",
        "typescript",
    }


def test_finding_contract_aggregation_locations_and_trace(violating: ArchitectureModel) -> None:
    result = StaticConformanceAnalyzer().analyze(violating, specification())
    (finding,) = result.findings
    assert finding.namespace == FindingNamespace.ARCH
    assert finding.detector.source == DetectorSource.STATIC
    assert finding.severity == Severity.HIGH and finding.confidence is None
    assert finding.primary_location and finding.primary_location.start_line == 2
    assert finding.recommendation and finding.description
    assert finding.metadata["source_component"] == "controller/Controller.java"
    assert finding.metadata["target_component"] == "repository/Repository.java"
    assert {"IMPORTS", "CALLS", "USES", "CREATES"} <= set(finding.metadata["relation_kinds"])
    assert finding.evidence[0].type == EvidenceType.ARCHITECTURE_RULE
    assert finding.evidence[0].properties["expected"]["allow"] == ["application"]
    edge_ids = set(finding.metadata["edge_ids"])
    proofs = finding.evidence[1:]
    assert len(proofs) == len(edge_ids) and all(
        item.type == EvidenceType.STATIC_RULE for item in proofs
    )
    calls = next(item for item in proofs if item.properties["relation"] == "CALLS")
    assert calls.properties["occurrences"] == 3
    locations = [finding.primary_location, *finding.related_locations]
    assert {7, 8, 9} <= {item.start_line for item in locations}
    assert all(item.file_path == "controller/Controller.java" for item in locations)
    assert finding.trace and len(finding.trace.steps) == 2
    first, second = finding.trace.steps
    actual = next(edge for edge in violating.edges if edge.id == second.edge_id)
    assert first.node_id == actual.source_id and second.node_id == actual.target_id
    assert second.relation == actual.kind
    assert set(finding.trace.metadata["edge_ids"]) == edge_ids
    assert result.statistics.findings_total == 1
    assert result.statistics.findings_by_severity == {"HIGH": 1}
    bundle = ArchitectureEvidenceBundle(
        analysis_id=AnalysisId(uuid4()),
        static_evidence=finding.evidence,
        deterministic_findings=result.findings,
    )
    assert bundle.deterministic_findings == result.findings
    canonical = serialize_conformance(result)
    assert StaticConformanceResult.model_validate_json(canonical) == result
    assert canonical == serialize_conformance(
        StaticConformanceAnalyzer().analyze(violating, specification())
    )
    assert "PRIVATE_CONFORMANCE_MARKER" not in canonical and str(FIXTURES) not in canonical


def test_same_edge_two_rules_remains_two_findings(violating: ArchitectureModel) -> None:
    data = specification().model_dump(mode="json", by_alias=True)
    data["rules"].append(
        {
            "id": "ARCH001",
            "type": "forbidden_dependency",
            "from": {"layer": "presentation"},
            "to": {"layer": "persistence"},
        }
    )
    spec = ArchitectureSpecification.model_validate(data)
    result = StaticConformanceAnalyzer().analyze(violating, spec)
    assert [item.rule_id for item in result.findings] == ["ARCH001", "ARCH002"]
    assert len({item.id for item in result.findings}) == 2
    data["rules"].reverse()
    assert serialize_conformance(result) == serialize_conformance(
        StaticConformanceAnalyzer().analyze(
            violating, ArchitectureSpecification.model_validate(data)
        )
    )


def test_disabled_rule_and_relation_filter(violating: ArchitectureModel) -> None:
    data = specification().model_dump(mode="json", by_alias=True)
    data["rules"][0]["enabled"] = False
    disabled = StaticConformanceAnalyzer().analyze(
        violating, ArchitectureSpecification.model_validate(data)
    )
    assert disabled.statistics.rules_enabled == disabled.statistics.rules_evaluated == 0
    assert not disabled.findings
    data["rules"][0]["enabled"] = True
    data["rules"][0]["relations"] = ["CALLS"]
    filtered = StaticConformanceAnalyzer().analyze(
        violating, ArchitectureSpecification.model_validate(data)
    )
    assert len(filtered.findings) == 1
    assert filtered.findings[0].metadata["relation_kinds"] == ["CALLS"]
    assert filtered.findings[0].metadata["occurrences"] == 3
    assert (
        filtered.findings[0].id
        == StaticConformanceAnalyzer().analyze(violating, specification()).findings[0].id
    )


def test_classification_inherits_includes_excludes_and_does_not_mutate(tmp_path: Path) -> None:
    (tmp_path / "a.ts").write_text(
        "import { External } from 'library'; "
        "export namespace Outer { export class Inner { method() {} } }"
    )
    (tmp_path / "excluded.ts").write_text("export class Excluded {}")
    iam = build(tmp_path).iam
    before = serialize_iam(iam)
    spec = ArchitectureSpecification.model_validate(
        {
            "version": "1.0",
            "architecture": {
                "layers": [{"name": "app", "include": ["**"], "exclude": ["excluded.ts"]}],
                "modules": [{"name": "main", "include": ["a.ts"]}],
            },
        }
    )
    classification = ArchitectureClassifier().classify(iam, spec)
    records = {item.node_id: item for item in classification.nodes}
    for node in iam.nodes:
        if node.kind in {NodeKind.EXTERNAL_DEPENDENCY, NodeKind.PROJECT, NodeKind.PACKAGE}:
            assert node.id not in records
        if node.symbol_id and node.source_location.file_path == "a.ts":
            assert records[node.id].layer == "app" and records[node.id].module == "main"
    assert any(item.status == ClassificationStatus.UNCLASSIFIED for item in records.values())
    assert classification.is_valid and before == serialize_iam(iam)
    result = StaticConformanceAnalyzer().analyze(iam, spec)
    assert result.status == ConformanceStatus.CONFORMANT
    assert result.statistics.edges_ignored >= 1


@pytest.mark.parametrize("dimension", ["layers", "modules"])
def test_overlapping_classification_is_invalid_without_findings(
    violating: ArchitectureModel, dimension: str
) -> None:
    data = specification().model_dump(mode="json", by_alias=True)
    data["architecture"][dimension] += [
        {"name": "overlapA", "include": ["**"]},
        {"name": "overlapB", "include": ["**"]},
    ]
    result = StaticConformanceAnalyzer().analyze(
        violating, ArchitectureSpecification.model_validate(data)
    )
    assert result.status == ConformanceStatus.INVALID and not result.is_valid
    assert result.statistics.ambiguous_nodes > 0
    assert result.statistics.rules_evaluated == 0 and not result.findings
    assert all("AMBIGUOUS" in item.code for item in result.diagnostics)
    assert (
        all(item.layer is None for item in result.classification.nodes)
        if dimension == "layers"
        else all(item.module is None for item in result.classification.nodes)
    )


def test_unclassified_dependencies_do_not_invent_violation(violating: ArchitectureModel) -> None:
    data = specification().model_dump(mode="json", by_alias=True)
    for layer in data["architecture"]["layers"]:
        layer["include"] = ["not-present/**"]
    result = StaticConformanceAnalyzer().analyze(
        violating, ArchitectureSpecification.model_validate(data)
    )
    assert result.is_valid and not result.findings
    assert result.statistics.nodes_unclassified == result.statistics.nodes_considered


@pytest.mark.parametrize("case", ["missing", "unresolved", "method", "kind", "location", "count"])
def test_invalid_provenance_never_becomes_findings(violating: ArchitectureModel, case: str) -> None:
    changed = violating.model_copy(deep=True)
    for edge in changed.edges:
        proof = edge.attributes["provenance"]
        if case == "missing":
            edge.attributes.pop("provenance")
        elif case == "unresolved":
            proof[0]["resolution_status"] = "AMBIGUOUS"
        elif case == "method":
            proof[0]["resolution_method"] = "ASSUMED"
        elif case == "kind":
            proof[0]["reference_kind"] = "CREATE" if edge.kind != EdgeKind.CREATES else "IMPORT"
        elif case == "location":
            proof[0]["source_location"]["file_path"] = "different.ts"
        else:
            edge.attributes["occurrences"] = True
    result = StaticConformanceAnalyzer().analyze(changed, specification())
    assert not result.findings and not result.is_complete
    assert result.status == ConformanceStatus.INCOMPLETE
    assert all(item.code == "UNPROVEN_DEPENDENCY" for item in result.diagnostics)


def test_truncated_provenance_keeps_proven_violation_but_reports_incomplete(
    violating: ArchitectureModel,
) -> None:
    changed = violating.model_copy(deep=True)
    edge = next(
        item
        for item in changed.edges
        if item.kind == EdgeKind.CALLS and item.attributes["occurrences"] == 3
    )
    edge.attributes["provenance"].pop()
    edge.attributes["provenance_truncated"] = 1
    result = StaticConformanceAnalyzer().analyze(changed, specification())
    assert len(result.findings) == 1 and not result.is_complete
    assert result.findings[0].metadata["provenance_truncated"] == 1
    assert any(item.code == "PROVENANCE_TRUNCATED" for item in result.diagnostics)


def test_whitelist_proof_does_not_export_raw_metadata(violating: ArchitectureModel) -> None:
    changed = violating.model_copy(deep=True)
    for edge in changed.edges:
        edge.attributes["source_text"] = "PRIVATE_RAW_SOURCE"
        edge.attributes["provenance"][0]["arbitrary"] = "PRIVATE_RAW_SOURCE"
    result = StaticConformanceAnalyzer().analyze(changed, specification())
    assert result.findings and "PRIVATE_RAW_SOURCE" not in serialize_conformance(result)


def test_invalid_iam_and_missing_registry_suppress_findings(violating: ArchitectureModel) -> None:
    invalid = violating.model_copy(deep=True)
    invalid.metadata["is_valid"] = False
    result = StaticConformanceAnalyzer().analyze(invalid, specification())
    assert not result.is_valid and not result.findings
    assert any(item.code == "INVALID_IAM" for item in result.diagnostics)
    missing = StaticConformanceAnalyzer(registry=StaticRuleRegistry()).analyze(
        violating, specification()
    )
    assert not missing.is_valid and not missing.findings
    assert any(item.code == "MISSING_RULE_EVALUATOR" for item in missing.diagnostics)


def test_incomplete_iam_cannot_claim_conformance(violating: ArchitectureModel) -> None:
    model = violating.model_copy(deep=True)
    model.metadata["is_complete"] = False
    result = StaticConformanceAnalyzer().analyze(model, specification())
    assert result.findings and not result.is_complete
    assert result.status == ConformanceStatus.NON_CONFORMANT
    empty = specification().model_dump(mode="json", by_alias=True)
    empty["rules"] = []
    assert (
        StaticConformanceAnalyzer()
        .analyze(model, ArchitectureSpecification.model_validate(empty))
        .status
        == ConformanceStatus.INCOMPLETE
    )


def test_unknown_and_ambiguous_references_are_not_dependencies(tmp_path: Path) -> None:
    (tmp_path / "controller").mkdir()
    (tmp_path / "controller" / "Unknown.ts").write_text(
        "export function run() { unknownReceiver.save(); new Missing(); }"
    )
    built = build(tmp_path)
    assert built.statistics.references_unresolved >= 2
    result = StaticConformanceAnalyzer().analyze(built.iam, specification())
    assert not result.findings and result.statistics.edges_considered == 0
    ambiguous = build(Path(__file__).parents[1] / "fixtures/extraction/java/ambiguous")
    assert ambiguous.statistics.references_ambiguous > 0
    assert not StaticConformanceAnalyzer().analyze(ambiguous.iam, specification()).findings


def test_ids_survive_added_callsites_and_lines(tmp_path: Path) -> None:
    root = tmp_path / "java"
    shutil.copytree(FIXTURES / "violating/java", root)
    path = root / "controller/Controller.java"
    before = StaticConformanceAnalyzer().analyze(build(root).iam, specification())
    path.write_text(
        "\n\n"
        + path.read_text().replace("Repository.save();", "Repository.save(); Repository.save();")
    )
    after = StaticConformanceAnalyzer().analyze(build(root).iam, specification())
    assert before.findings[0].id == after.findings[0].id
    assert before.findings[0].metadata["occurrences"] < after.findings[0].metadata["occurrences"]
    assert before.reproducibility.snapshot_fingerprint != after.reproducibility.snapshot_fingerprint
    assert before.findings[0].related_locations != after.findings[0].related_locations


def test_iam_and_filesystem_order_and_root_do_not_change_canonical_result(
    violating: ArchitectureModel, tmp_path: Path
) -> None:
    shuffled = violating.model_copy(
        update={
            "nodes": tuple(reversed(violating.nodes)),
            "edges": tuple(reversed(violating.edges)),
            "source_files": tuple(reversed(violating.source_files)),
            "symbols": tuple(reversed(violating.symbols)),
        }
    )
    expected = serialize_conformance(
        StaticConformanceAnalyzer().analyze(violating, specification())
    )
    assert (
        serialize_conformance(StaticConformanceAnalyzer().analyze(shuffled, specification()))
        == expected
    )
    copy = tmp_path / "java"
    shutil.copytree(FIXTURES / "violating/java", copy)
    assert (
        serialize_conformance(StaticConformanceAnalyzer().analyze(build(copy).iam, specification()))
        == expected
    )


def test_use_case_reuses_streaming_builder() -> None:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(FIXTURES / "clean"))
    ) as repository:
        result = CheckArchitecture(
            BuildIAM(ParseRepository(create_parser_registry()), create_extractor_registry())
        ).execute(repository.snapshot, repository.workspace, specification())
    assert result.status == ConformanceStatus.CONFORMANT and result.statistics.iam_edges_total > 0


def test_result_rejects_inconsistent_statistics_and_status(violating: ArchitectureModel) -> None:
    result = StaticConformanceAnalyzer().analyze(violating, specification())
    data = json.loads(serialize_conformance(result))
    data["status"] = "CONFORMANT"
    with pytest.raises(ValidationError):
        StaticConformanceResult.model_validate(data)
    data["status"] = "NON_CONFORMANT"
    data["statistics"]["nodes_considered"] += 1
    with pytest.raises(ValidationError):
        StaticConformanceResult.model_validate(data)
