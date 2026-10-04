import pytest
from pydantic import ValidationError

from archguard.core.evidence import Evidence, EvidenceType
from archguard.core.findings.confidence import CalibrationStatus, Confidence
from archguard.core.findings.enums import FindingNamespace, Severity
from archguard.core.findings.model import Finding
from archguard.core.traces import Trace


def test_arch_finding_roundtrip(synthetic_arch_finding: Finding) -> None:
    finding = synthetic_arch_finding
    assert Finding.model_validate_json(finding.model_dump_json()) == finding
    assert finding.namespace == FindingNamespace.ARCH
    assert finding.confidence is None
    assert finding.severity == Severity.HIGH


def test_sec_future_schema_roundtrip(synthetic_sec_finding: Finding) -> None:
    finding = synthetic_sec_finding
    assert Finding.model_validate_json(finding.model_dump_json()) == finding
    assert finding.namespace == FindingNamespace.SEC
    assert finding.evidence[0].type == EvidenceType.SECRET_PATTERN


@pytest.mark.parametrize("rule", ["SEC001", "ARCH02", "ARCH002extra", "ARCH٠٠٢", "ARCH-002"])
def test_arch_invalid_rule_prefix(rule: str, synthetic_arch_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="rule_id"):
        Finding.model_validate(synthetic_arch_finding.model_dump() | {"rule_id": rule})


def test_sec_cannot_use_arch_rule(synthetic_sec_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="rule_id"):
        Finding.model_validate(synthetic_sec_finding.model_dump() | {"rule_id": "ARCH002"})


@pytest.mark.parametrize("source", ["GRAPH", "LLM", "HYBRID"])
def test_sec_cannot_use_arch_detector(source: str, synthetic_sec_finding: Finding) -> None:
    data = synthetic_sec_finding.model_dump(mode="json")
    data["detector"]["source"] = source
    with pytest.raises(ValidationError, match="detector source"):
        Finding.model_validate(data)


def test_arch_cannot_use_security_detector(synthetic_arch_finding: Finding) -> None:
    data = synthetic_arch_finding.model_dump(mode="json")
    data["detector"]["source"] = "SECURITY_LLM"
    with pytest.raises(ValidationError, match="detector source"):
        Finding.model_validate(data)


def test_cross_namespace_evidence_rejected(
    synthetic_arch_finding: Finding, synthetic_sec_finding: Finding
) -> None:
    with pytest.raises(ValidationError, match="evidence must match"):
        Finding.model_validate(
            synthetic_arch_finding.model_dump() | {"evidence": synthetic_sec_finding.evidence}
        )


def test_evidence_is_required_and_unique(synthetic_arch_finding: Finding) -> None:
    for evidence in [(), synthetic_arch_finding.evidence * 2]:
        with pytest.raises(ValidationError):
            Finding.model_validate(synthetic_arch_finding.model_dump() | {"evidence": evidence})


def test_invalid_severity_and_schema(synthetic_arch_finding: Finding) -> None:
    for changes in [{"severity": "URGENT"}, {"finding_schema_version": "2.0"}]:
        with pytest.raises(ValidationError):
            Finding.model_validate(synthetic_arch_finding.model_dump() | changes)


def test_evidence_serialization(synthetic_arch_finding: Finding) -> None:
    evidence = synthetic_arch_finding.evidence[0]
    assert Evidence.model_validate_json(evidence.model_dump_json()) == evidence
    assert evidence.properties["synthetic"] is True


@pytest.mark.parametrize("value", [object(), {1: "non-string-key"}, {"nested": float("nan")}])
def test_properties_must_be_json(value: object, synthetic_arch_finding: Finding) -> None:
    with pytest.raises(ValidationError):
        Evidence.model_validate(
            synthetic_arch_finding.evidence[0].model_dump() | {"properties": value}
        )


@pytest.mark.parametrize(
    "kind", ["SECRET_PATTERN", "DEPENDENCY_DATABASE", "CONFIGURATION", "DATA_FLOW", "TAINT_PATH"]
)
def test_arch_cannot_use_security_evidence(kind: str, synthetic_arch_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="security-specific"):
        Evidence.model_validate(synthetic_arch_finding.evidence[0].model_dump() | {"type": kind})


@pytest.mark.parametrize("score", [-0.1, 1.1, float("inf"), float("nan"), True])
def test_invalid_confidence(score: float) -> None:
    with pytest.raises(ValidationError):
        Confidence(score=score)


def test_confidence_semantics() -> None:
    assert Confidence(score=0).status == CalibrationStatus.NOT_CALIBRATED
    confidence = Confidence(
        score=1,
        status=CalibrationStatus.CALIBRATED,
        calibration_reference="test-calibration-artifact",
    )
    assert Confidence.model_validate_json(confidence.model_dump_json()) == confidence
    with pytest.raises(ValidationError):
        Confidence(score=0.8, status=CalibrationStatus.CALIBRATED)
    with pytest.raises(ValidationError):
        Confidence(score=0.8, calibration_reference="unjustified")


def test_trace_roundtrip(synthetic_arch_finding: Finding) -> None:
    trace = synthetic_arch_finding.trace
    assert trace is not None
    assert Trace.model_validate_json(trace.model_dump_json()) == trace
    assert [step.sequence for step in trace.steps] == [1, 2, 3]


@pytest.mark.parametrize("sequences", [[], [0], [2], [1, 1, 2], [1, 3, 4], [2, 1, 3], [True]])
def test_trace_must_be_contiguous(sequences: list[int], synthetic_arch_finding: Finding) -> None:
    trace = synthetic_arch_finding.trace
    assert trace is not None
    data = trace.model_dump(mode="json")
    step = data["steps"][0]
    data["steps"] = [step | {"sequence": sequence} for sequence in sequences]
    with pytest.raises(ValidationError):
        Trace.model_validate(data)
