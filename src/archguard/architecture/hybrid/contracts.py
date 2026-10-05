from typing import Protocol, Self

from pydantic import model_validator

# The original batch contracts remain the compatibility facade. These typed case
# contracts are the same boundary's detailed representation; they never clone Findings.
from archguard.architecture.hybrid.models import (
    HybridAnalysisResult as HybridAnalysisResult,
)
from archguard.architecture.hybrid.models import (
    HybridCase as HybridCase,
)
from archguard.architecture.hybrid.models import (
    HybridDecision as HybridDecision,
)
from archguard.architecture.hybrid.models import (
    HybridEvidenceBundle as HybridEvidenceBundle,
)
from archguard.architecture.hybrid.policies import HybridDecisionPolicy as HybridDecisionPolicy
from archguard.core.evidence import Evidence, EvidenceType
from archguard.core.findings.enums import DetectorSource, FindingNamespace
from archguard.core.findings.model import Finding
from archguard.core.identifiers import AnalysisId
from archguard.core.model.base import DomainModel
from archguard.iam.model import ArchitectureModel


class ArchitectureEvidenceBundle(DomainModel):
    analysis_id: AnalysisId
    static_evidence: tuple[Evidence, ...] = ()
    graph_evidence: tuple[Evidence, ...] = ()
    semantic_evidence: tuple[Evidence, ...] = ()
    deterministic_findings: tuple[Finding, ...] = ()

    @model_validator(mode="after")
    def validate_architecture_input(self) -> Self:
        channels = (
            (
                self.static_evidence,
                {
                    EvidenceType.STATIC_RULE,
                    EvidenceType.SOURCE_CODE,
                    EvidenceType.ARCHITECTURE_RULE,
                },
            ),
            (self.graph_evidence, {EvidenceType.GRAPH_PATH, EvidenceType.GRAPH_METRIC}),
            (self.semantic_evidence, {EvidenceType.LLM_RESULT}),
        )
        for evidence_group, allowed_types in channels:
            if any(
                evidence.namespace != FindingNamespace.ARCH or evidence.type not in allowed_types
                for evidence in evidence_group
            ):
                raise ValueError("hybrid channels accept only the corresponding ARCH evidence")
        if any(
            finding.namespace != FindingNamespace.ARCH
            or finding.detector.source != DetectorSource.STATIC
            for finding in self.deterministic_findings
        ):
            raise ValueError("confirmed deterministic findings must be static ARCH findings")
        return self


class ArchitectureDecision(DomainModel):
    analysis_id: AnalysisId
    findings: tuple[Finding, ...]

    @model_validator(mode="after")
    def validate_architecture_output(self) -> Self:
        if any(finding.namespace != FindingNamespace.ARCH for finding in self.findings):
            raise ValueError("Hybrid Architecture Decision may produce only ARCH findings")
        return self


class HybridDecisionEngine(Protocol):
    """Batch compatibility facade, implemented by HybridAnalyzer with deterministic precedence."""

    def decide(
        self, model: ArchitectureModel, evidence: ArchitectureEvidenceBundle, /
    ) -> ArchitectureDecision: ...
