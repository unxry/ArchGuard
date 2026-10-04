from uuid import UUID

import pytest
from pydantic import ValidationError

from archguard.architecture.hybrid.contracts import ArchitectureDecision, ArchitectureEvidenceBundle
from archguard.core.evidence import Evidence
from archguard.core.findings.model import Finding
from archguard.core.identifiers import AnalysisId

ANALYSIS_ID = AnalysisId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))


def test_arch_only_bundle_and_decision_roundtrip(synthetic_arch_finding: Finding) -> None:
    bundle = ArchitectureEvidenceBundle(
        analysis_id=ANALYSIS_ID,
        static_evidence=synthetic_arch_finding.evidence,
        deterministic_findings=(synthetic_arch_finding,),
    )
    assert ArchitectureEvidenceBundle.model_validate_json(bundle.model_dump_json()) == bundle
    decision = ArchitectureDecision(analysis_id=ANALYSIS_ID, findings=(synthetic_arch_finding,))
    assert ArchitectureDecision.model_validate_json(decision.model_dump_json()) == decision


@pytest.mark.parametrize("channel", ["static_evidence", "graph_evidence", "semantic_evidence"])
def test_sec_evidence_never_enters_hybrid(channel: str, synthetic_sec_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="ARCH evidence"):
        ArchitectureEvidenceBundle.model_validate(
            {"analysis_id": ANALYSIS_ID, channel: synthetic_sec_finding.evidence}
        )


def test_generic_security_llm_evidence_is_rejected(synthetic_sec_finding: Finding) -> None:
    evidence = Evidence.model_validate(
        synthetic_sec_finding.evidence[0].model_dump() | {"type": "LLM_RESULT"}
    )
    with pytest.raises(ValidationError, match="ARCH evidence"):
        ArchitectureEvidenceBundle(analysis_id=ANALYSIS_ID, semantic_evidence=(evidence,))


def test_misrouted_arch_evidence_rejected(synthetic_arch_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="corresponding"):
        ArchitectureEvidenceBundle(
            analysis_id=ANALYSIS_ID, graph_evidence=synthetic_arch_finding.evidence
        )


def test_sec_deterministic_findings_rejected(synthetic_sec_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="static ARCH"):
        ArchitectureEvidenceBundle(
            analysis_id=ANALYSIS_ID, deterministic_findings=(synthetic_sec_finding,)
        )


def test_sec_decision_output_rejected(synthetic_sec_finding: Finding) -> None:
    with pytest.raises(ValidationError, match="only ARCH"):
        ArchitectureDecision(analysis_id=ANALYSIS_ID, findings=(synthetic_sec_finding,))
