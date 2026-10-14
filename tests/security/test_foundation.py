"""Synthetic engineering checks; no Security benchmark, provider or real secret material."""

import ast
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from archguard.architecture.hybrid.contracts import ArchitectureDecision, ArchitectureEvidenceBundle
from archguard.architecture.hybrid.models import HybridCase
from archguard.architecture.rules.registry import create_static_rule_registry
from archguard.core.findings.model import Finding
from archguard.core.identifiers import (
    AnalysisId,
    EvidenceId,
    RepositoryId,
    SnapshotId,
    SourceFileId,
)
from archguard.core.locations import SourceLocation
from archguard.iam.model import ArchitectureModel
from archguard.security.analysis import SecurityAnalyzer
from archguard.security.dataflow import SecurityAPIContract, SecurityAPIRegistry, SecurityAPIRole
from archguard.security.domain import (
    SECURITY_VERSION,
    EvidenceCapability,
    EvidenceStrength,
    FlowPath,
    FlowRole,
    FlowStep,
    SecurityAnalysisContext,
    SecurityAnalysisResult,
    SecurityEvidence,
    SecurityEvidenceKind,
    SecurityFinding,
    SecurityLanguage,
    SecurityReportSection,
    SecurityRuleId,
    SecuritySeverity,
    SecuritySourceReference,
    deduplicate_findings,
    finding_identity,
)
from archguard.security.ports import DetectorRegistration, DetectorResult
from archguard.security.rules import (
    NAMES,
    ImplementationStatus,
    SecurityRuleDefinition,
    SecurityRuleRegistry,
    canonical_rules,
)

REPO = RepositoryId(UUID(int=101))
SNAPSHOT = SnapshotId(UUID(int=102))


@pytest.fixture
def source():
    return SecuritySourceReference(
        file_id=SourceFileId(UUID(int=103)),
        location=SourceLocation(file_path="src/example.ts", start_line=2, end_line=2, end_column=9),
        language="TYPESCRIPT",
    )


@pytest.fixture
def evidence(source):
    return SecurityEvidence(
        id=EvidenceId(UUID(int=104)),
        kind="AST_PATTERN",
        source=source,
        summary="Synthetic engineering evidence",
        analysis_version=SECURITY_VERSION,
    )


@pytest.fixture
def finding(source, evidence):
    return SecurityFinding(
        id=finding_identity(REPO, SNAPSHOT, SecurityRuleId.SEC001, source, None, None),
        repository_id=REPO,
        snapshot_id=SNAPSHOT,
        rule_id="SEC001",
        title="Synthetic pattern",
        description="Engineering fixture, not a vulnerability assessment",
        severity="LOW",
        evidence_strength="HIGH",
        status="CONFIRMED_PATTERN",
        language="TYPESCRIPT",
        primary_source=source,
        evidence=(evidence,),
        evidence_refs=(evidence.id,),
        analyzer_version=SECURITY_VERSION,
    )


def test_exact_canonical_rule_set_names_order_and_contract_status():
    registry = SecurityRuleRegistry()
    assert tuple(r.rule_id for r in registry.all()) == tuple(SecurityRuleId)
    assert tuple(r.name for r in registry.all()) == NAMES
    assert len(registry.all()) == 10
    for rule in registry.all():
        assert rule.implementation_status == ImplementationStatus.CONTRACT_FROZEN
        assert rule.severity_default is None and rule.detector_ids == ()
        assert rule.evidence_requirements and rule.limitations
        assert rule.false_positive_risks and rule.false_negative_risks
        assert rule.supported_languages == tuple(SecurityLanguage)
        assert SecurityRuleDefinition.model_validate_json(rule.model_dump_json()) == rule


@pytest.mark.parametrize("rule", ["SEC000", "SEC011", "ARCH001", "sec001", "SEC01"])
def test_unknown_and_cross_domain_rule_ids_rejected(rule):
    with pytest.raises(ValueError):
        SecurityRuleRegistry().get(rule)


def test_registry_duplicates_and_capability_language_filters():
    rows = canonical_rules()
    with pytest.raises(ValueError, match="duplicate SEC"):
        SecurityRuleRegistry((rows[0], rows[0]))
    registry = SecurityRuleRegistry()
    assert len(registry.for_language(SecurityLanguage.JAVA)) == 10
    assert registry.get("SEC002") in registry.for_capability(EvidenceCapability.TAINT_FLOW)
    assert registry.get("SEC009") not in registry.for_capability(EvidenceCapability.TAINT_FLOW)


@pytest.mark.parametrize(
    "patch",
    [
        {"name": "Repurposed"},
        {"description": " "},
        {"severity_default": "URGENT"},
        {"implementation_status": "MAGIC"},
        {"evidence_requirements": []},
        {"supported_languages": ["PYTHON"]},
        {"supported_languages": ["JAVA", "JAVA"]},
        {"detector_ids": ["unimplemented"]},
    ],
)
def test_rule_metadata_validation(patch):
    with pytest.raises(ValidationError):
        SecurityRuleDefinition.model_validate(canonical_rules()[0].model_dump() | patch)


def test_rule_cannot_claim_nonexistent_implemented_detector():
    row = SecurityRuleDefinition.model_validate(
        canonical_rules()[0].model_dump()
        | {"implementation_status": "IMPLEMENTED", "detector_ids": ["missing"]}
    )
    with pytest.raises(ValueError, match="detector missing"):
        SecurityRuleRegistry((row,))


@pytest.mark.parametrize(
    "patch",
    [
        {"namespace": "ARCH"},
        {"rule_id": "ARCH001"},
        {"rule_id": "SEC011"},
        {"hybrid_score": 0.7},
        {"confidence": 0.8},
        {"evidence_strength": 0.8},
        {"severity": "UNSUPPORTED"},
        {"evidence": []},
        {"evidence_refs": []},
        {"analyzer_version": "different-version"},
        {"language": "JAVA"},
        {"id": UUID(int=105)},
    ],
)
def test_finding_validation_and_no_arch_score(finding, patch):
    with pytest.raises(ValidationError):
        SecurityFinding.model_validate(finding.model_dump() | patch)


def test_finding_roundtrip_severity_not_evidence_strength_and_stable_identity(finding):
    assert finding.severity == SecuritySeverity.LOW
    assert finding.evidence_strength == EvidenceStrength.HIGH
    changed = SecurityFinding.model_validate(finding.model_dump() | {"severity": "CRITICAL"})
    assert changed.id == finding.id
    assert SecurityFinding.model_validate_json(finding.model_dump_json()) == finding
    assert deduplicate_findings((finding, finding)) == (finding,)
    with pytest.raises(ValueError, match="merge policy"):
        deduplicate_findings((finding, changed))


@pytest.mark.parametrize("kind", list(SecurityEvidenceKind))
def test_all_evidence_kinds_are_typed_source_bound_not_detectors(evidence, kind):
    value = SecurityEvidence.model_validate(evidence.model_dump() | {"kind": kind})
    assert value.kind == kind
    assert SecurityEvidence.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(
    "patch",
    [
        {"source": None},
        {"namespace": "ARCH"},
        {"kind": "MAGIC_TAINT"},
        {"raw_value": "not-supported"},
        {"analysis_version": " "},
    ],
)
def test_evidence_requires_traceability_and_disallows_raw_configuration_values(evidence, patch):
    with pytest.raises(ValidationError):
        SecurityEvidence.model_validate(evidence.model_dump() | patch)


@pytest.mark.parametrize(
    "location",
    [
        {"file_path": "../unsafe.ts", "start_line": 1},
        {"file_path": "/absolute.ts", "start_line": 1},
        {"file_path": "src/a.ts", "start_line": 0},
        {"file_path": "src/a.ts", "start_line": 3, "end_line": 2, "end_column": 1},
    ],
)
def test_source_locations_use_existing_validated_core_ranges(source, location):
    with pytest.raises(ValidationError):
        SecuritySourceReference.model_validate(source.model_dump() | {"location": location})


def test_config_categories_do_not_expand_intake_or_enable_detector(source):
    with pytest.raises(ValidationError, match="configuration"):
        SecuritySourceReference.model_validate(
            source.model_dump() | {"input_category": "CONFIGURATION"}
        )
    config = SecuritySourceReference.model_validate(
        source.model_dump() | {"input_category": "CONFIGURATION", "configuration_category": "JSON"}
    )
    assert config.configuration_category.value == "JSON"


def test_dangling_and_duplicate_evidence_references_rejected(finding, evidence):
    for patch in (
        {"evidence_refs": [UUID(int=106)]},
        {"sink_ref": UUID(int=106)},
        {"evidence": [evidence, evidence]},
    ):
        with pytest.raises(ValidationError):
            SecurityFinding.model_validate(finding.model_dump() | patch)


def test_unknown_flow_remains_uncertain_and_is_not_a_taint_implementation(evidence):
    step = FlowStep(role=FlowRole.UNKNOWN_FLOW, evidence_ref=evidence.id)
    with pytest.raises(ValidationError):
        FlowPath(steps=(step,), complete=True)
    with pytest.raises(ValidationError):
        FlowPath(steps=(step,), complete=False)
    flow = FlowPath(steps=(step,), complete=False, uncertainty=("Unresolved call boundary",))
    assert FlowPath.model_validate_json(flow.model_dump_json()) == flow


@pytest.mark.parametrize("language", list(SecurityLanguage))
def test_foundation_production_path_emits_no_fake_findings_or_security_guarantee(language):
    context = SecurityAnalysisContext(repository_id=REPO, snapshot_id=SNAPSHOT, language=language)
    result = SecurityAnalyzer().analyze(context)
    assert result.findings == result.analyzed_rules == result.applicable_rules == ()
    assert result.unsupported_rules == tuple(SecurityRuleId)
    assert result.diagnostics[0].code == "RULE_NOT_EVALUATED"
    assert result.analysis_metadata["dataflow_implemented"] is False
    assert result.analysis_metadata["taint_solver_implemented"] is False
    assert result.zero_findings_is_security_guarantee is False
    section = SecurityReportSection(result=result)
    assert SecurityReportSection.model_validate_json(section.model_dump_json()) == section


def test_empty_requested_scope_is_not_replaced_with_all_rules():
    context = SecurityAnalysisContext(
        repository_id=REPO, snapshot_id=SNAPSHOT, language="JAVA", requested_rules=()
    )
    assert SecurityAnalyzer().analyze(context).unsupported_rules == ()


def test_iam_is_reused_read_only_and_false_bindings_rejected(source):
    iam = ArchitectureModel.model_validate_json(
        Path("tests/fixtures/synthetic_iam.json").read_text()
    )
    before = iam.model_dump_json()
    context = SecurityAnalysisContext(
        repository_id=REPO, snapshot_id=SNAPSHOT, language="JAVA", iam=iam
    )
    assert SecurityAnalyzer().analyze(context).findings == ()
    assert iam.model_dump_json() == before
    with pytest.raises(ValidationError):
        SecurityAnalysisContext(
            repository_id=REPO,
            snapshot_id=SNAPSHOT,
            language="TYPESCRIPT",
            iam=iam,
            source_references=(source,),
        )


def test_typed_api_registry_is_empty_and_tested_mechanics_do_not_claim_framework_coverage():
    assert SecurityAPIRegistry().all() == ()
    entry = SecurityAPIContract(
        id="synthetic-source",
        language="JAVA",
        qualified_api="fixture.input",
        role="SOURCE",
        rule_ids=(SecurityRuleId.SEC002,),
        conditions=("Synthetic test only",),
        limitations=("Not a framework model",),
        engineering_test_binding=__name__,
    )
    registry = SecurityAPIRegistry((entry,))
    assert registry.select(SecurityLanguage.JAVA, SecurityAPIRole.SOURCE) == (entry,)
    assert registry.get(entry.id) == entry
    with pytest.raises(ValueError, match="duplicate"):
        SecurityAPIRegistry((entry, entry))


class FixtureDetector:
    registration = DetectorRegistration(
        id="fixture-only",
        version="test-v1",
        supported_rule_ids=(SecurityRuleId.SEC001,),
        supported_languages=tuple(SecurityLanguage),
        required_capabilities=frozenset({EvidenceCapability.AST_STATIC}),
    )

    def analyze(self, context):
        return DetectorResult(evaluated_rules=context.requested_rules, applicable_rules=())


def test_detector_registration_scope_and_capability_coverage():
    detector = FixtureDetector()
    with pytest.raises(ValueError, match="undeclared"):
        SecurityRuleRegistry(detectors=(detector,))
    row = SecurityRuleDefinition.model_validate(
        canonical_rules()[0].model_dump()
        | {"implementation_status": "IMPLEMENTED", "detector_ids": [detector.registration.id]}
    )
    registry = SecurityRuleRegistry((row,), (detector,))
    context = SecurityAnalysisContext(
        repository_id=REPO,
        snapshot_id=SNAPSHOT,
        language="JAVA",
        requested_rules=(SecurityRuleId.SEC001,),
    )
    result = SecurityAnalyzer(registry).analyze(context)
    assert result.unsupported_rules == context.requested_rules
    assert result.diagnostics[0].code == "CAPABILITY_UNAVAILABLE"
    context = SecurityAnalysisContext.model_validate(
        context.model_dump() | {"available_capabilities": ["AST_STATIC"]}
    )
    result = SecurityAnalyzer(registry).analyze(context)
    assert result.analyzed_rules == context.requested_rules
    assert result.applicable_rules == result.unsupported_rules == result.findings == ()


def test_detector_output_scope_is_checked():
    class Invalid(FixtureDetector):
        def analyze(self, context):
            return DetectorResult(evaluated_rules=(SecurityRuleId.SEC002,), applicable_rules=())

    d = Invalid()
    row = SecurityRuleDefinition.model_validate(
        canonical_rules()[0].model_dump()
        | {"implementation_status": "IMPLEMENTED", "detector_ids": [d.registration.id]}
    )
    context = SecurityAnalysisContext(
        repository_id=REPO,
        snapshot_id=SNAPSHOT,
        language="JAVA",
        requested_rules=(SecurityRuleId.SEC001,),
        available_capabilities={EvidenceCapability.AST_STATIC},
    )
    with pytest.raises(ValueError, match="scope"):
        SecurityAnalyzer(SecurityRuleRegistry((row,), (d,))).analyze(context)


def test_architecture_contracts_reject_security_findings_and_ids(finding, synthetic_arch_finding):
    analysis = AnalysisId(UUID(int=201))
    with pytest.raises(ValidationError):
        ArchitectureDecision(analysis_id=analysis, findings=(finding,))
    with pytest.raises(ValidationError):
        ArchitectureEvidenceBundle(analysis_id=analysis, deterministic_findings=(finding,))
    with pytest.raises(ValidationError) as error:
        HybridCase.model_validate({"rule_id": "SEC001"})
    assert any(e["loc"] == ("rule_id",) for e in error.value.errors())
    with pytest.raises(ValidationError, match="namespace"):
        Finding.model_validate(synthetic_arch_finding.model_dump() | {"rule_id": "SEC001"})
    assert all("SEC" not in str(r) for r in create_static_rule_registry().supported_types())


def test_security_import_firewall_and_reverse_architecture_dependencies():
    for root, prohibited in (
        (
            Path("src/archguard/security"),
            (
                "archguard.architecture",
                "archguard.benchmark",
                "archguard.calibration",
                "archguard.infrastructure",
                "archguard.api",
            ),
        ),
        (Path("src/archguard/architecture"), ("archguard.security",)),
        (Path("src/archguard/benchmark"), ("archguard.security",)),
        (Path("src/archguard/calibration"), ("archguard.security",)),
    ):
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                modules = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                assert not any(m == p or m.startswith(p + ".") for m in modules for p in prohibited)


def test_security_domain_schemas_and_result_coverage_are_versioned_and_discriminated():
    schema = SecurityFinding.model_json_schema()
    assert "hybrid_score" not in schema["properties"] and "confidence" not in schema["properties"]
    assert schema["properties"]["namespace"]["const"] == "SEC"
    with pytest.raises(ValidationError, match="partition"):
        SecurityAnalysisResult(
            requested_rules=(SecurityRuleId.SEC001,),
            unsupported_rules=(),
            analyzer_version=SECURITY_VERSION,
        )


def test_rule_meaning_cannot_be_silently_repurposed():
    with pytest.raises(ValidationError, match="canonical meaning"):
        SecurityRuleDefinition.model_validate(
            canonical_rules()[0].model_dump() | {"description": "Unrelated rule meaning"}
        )


@pytest.mark.parametrize(
    "code",
    [
        "from archguard.architecture.hybrid import models",
        "import archguard.benchmark.unified_hybrid",
        "from ..architecture import graph",
        "__import__('archguard.architecture')",
    ],
)
def test_production_import_firewall_rejects_disallowed_directions(code, tmp_path, monkeypatch):
    from archguard.infrastructure import security_foundation as f

    (tmp_path / "bad.py").write_text(code)
    monkeypatch.setattr(f, "SECURITY_ROOT", tmp_path)
    with pytest.raises(ValueError, match="BOUNDARY_FAILED|ISOLATION_FAILED"):
        f.import_firewall()


def test_receipts_and_schemas_are_deterministic_public_safe(tmp_path, monkeypatch):
    from archguard.infrastructure import security_foundation as f

    monkeypatch.setattr(
        f,
        "science_freeze",
        lambda: {
            "architecture_source_hashes": {},
            "CORE_THESIS_COMPLETE": True,
            "scientific_artifacts_unchanged": "PASS",
        },
    )
    bundle = f.build({"engineering_fixture": True})
    assert bundle == f.build({"engineering_fixture": True})
    assert len(bundle["sec-rule-registry.json"]["rules"]) == 10
    assert len(bundle["security-capability-matrix.json"]["rows"]) == 10
    assert bundle["security-foundation.json"]["fake_production_findings"] == 0
    assert bundle["security-analysis-boundary.json"]["executable_detectors"] == []
    assert bundle["security-domain-model.json"]["schemas"]["SecurityFinding"]
    for name, data in bundle.items():
        p = tmp_path / name
        p.write_text(f.canonical(data))
    f.privacy(tuple(tmp_path.glob("*.json")))


def test_foundation_freeze_requires_actual_quality(tmp_path):
    from archguard.infrastructure import security_foundation as f

    q = tmp_path / "quality.json"
    q.write_text('{"make_check":"FAIL"}')
    with pytest.raises(ValueError, match="QUALITY_INCOMPLETE"):
        f.freeze(q)
