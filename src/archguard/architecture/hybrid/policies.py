from typing import Protocol
from uuid import uuid5

from archguard.architecture.hybrid.features import VERSION
from archguard.architecture.hybrid.models import (
    CalibrationStatus,
    EvidenceAgreement,
    HybridCase,
    HybridDecision,
    HybridDecisionState,
    HybridEvidenceBundle,
    HybridFeatureVector,
    HybridPolicyMetadata,
)
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.architecture.intelligence.models import SemanticDecision
from archguard.core.identifiers import FindingId


class HybridPolicyError(ValueError):
    code = "INVALID_HYBRID_POLICY"


class HybridDecisionPolicy(Protocol):
    @property
    def metadata(self) -> HybridPolicyMetadata: ...

    def decide(
        self, case: HybridCase, evidence: HybridEvidenceBundle, features: HybridFeatureVector
    ) -> HybridDecision: ...


class DeterministicPrecedencePolicy:
    @property
    def metadata(self) -> HybridPolicyMetadata:
        return HybridPolicyMetadata(
            policy_id="deterministic-precedence",
            policy_version="1.0.0",
            feature_schema_version=VERSION,
            calibration_status=CalibrationStatus.UNCALIBRATED,
        )

    def decide(
        self, case: HybridCase, evidence: HybridEvidenceBundle, features: HybridFeatureVector
    ) -> HybridDecision:
        if features.schema_version != self.metadata.feature_schema_version:
            raise HybridPolicyError("policy requires a compatible feature schema")
        reasons: list[str] = []
        confirmed: tuple[FindingId, ...] = ()
        severity = None
        calibration = CalibrationStatus.UNCALIBRATED
        if evidence.static:
            proof = evidence.static[0]
            state = HybridDecisionState.CONFIRMED_DETERMINISTIC
            confirmed, severity = (proof.finding_id,), proof.severity
            calibration = CalibrationStatus.DETERMINISTIC
            reasons.append(
                "DET_GRAPH_CYCLE_RULE_PROOF"
                if proof.rule_id == "ARCH003"
                else "DET_STATIC_RULE_PROOF"
            )
        elif case.origin == "GRAPH":
            state = HybridDecisionState.REVIEW_REQUIRED
            reasons.append("UNCALIBRATED_GRAPH_SIGNAL")
        elif any(
            s.candidate_id in case.anchor_ids
            and s.decision != SemanticDecision.INSUFFICIENT_CONTEXT
            for s in evidence.ai
        ):
            state = HybridDecisionState.REVIEW_REQUIRED
            reasons.append("UNCALIBRATED_SEMANTIC_SIGNAL")
        else:
            state = HybridDecisionState.INSUFFICIENT_EVIDENCE
        if not evidence.ai:
            reasons.append("MISSING_AI_EVIDENCE")
        if any(s.decision == SemanticDecision.INSUFFICIENT_CONTEXT for s in evidence.ai):
            reasons.append("AI_INSUFFICIENT_CONTEXT")
        if any(s.decision == SemanticDecision.NOT_SUPPORTED for s in evidence.ai):
            reasons.append("AI_NOT_SUPPORTED_UNCALIBRATED")
        if evidence.completeness.iam_complete is False:
            reasons.append("PARTIAL_SOURCE_MODEL")
        if evidence.completeness.ai_partial:
            reasons.append("PARTIAL_AI_ANALYSIS")
        if evidence.completeness.context_truncated:
            reasons.append("TRUNCATED_AI_CONTEXT")
        if not reasons:
            reasons.append("MISSING_CHANNEL_EVIDENCE")
        refs = {
            agreement: tuple(
                sorted(
                    {
                        r
                        for a in evidence.alignments
                        if a.agreement == agreement
                        for r in a.source_refs
                    }
                )
            )
            for agreement in (
                EvidenceAgreement.SUPPORTING,
                EvidenceAgreement.CONTRADICTING,
                EvidenceAgreement.MISSING,
            )
        }
        bundle_hash = fingerprint(evidence)
        identity = (
            f"hybrid-decision-v1:{self.metadata.policy_id}:{self.metadata.policy_version}:"
            f"{features.fingerprint}:{bundle_hash}"
        )
        return HybridDecision(
            decision_id=uuid5(case.case_id, identity),
            case_id=case.case_id,
            state=state,
            policy=self.metadata,
            calibration_status=calibration,
            feature_fingerprint=features.fingerprint,
            evidence_fingerprint=bundle_hash,
            reason_codes=tuple(reasons),
            supporting_refs=refs[EvidenceAgreement.SUPPORTING],
            contradicting_refs=refs[EvidenceAgreement.CONTRADICTING],
            missing_refs=refs[EvidenceAgreement.MISSING],
            confirmed_finding_ids=confirmed,
            severity=severity,
        )
