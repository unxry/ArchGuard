from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from archguard.architecture.classification.models import (
    ArchitectureClassification,
    ConformanceDiagnostic,
)
from archguard.core.findings.enums import FindingNamespace
from archguard.core.findings.model import Finding
from archguard.core.identifiers import ProjectId, SnapshotId
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject

NonnegativeInt = Annotated[int, Field(ge=0)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ConformanceStatus(StrEnum):
    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


class StaticAnalysisConfig(DomainModel):
    require_complete_iam: Literal[True] = True


class StaticConformanceStatistics(DomainModel):
    iam_nodes_total: NonnegativeInt
    iam_edges_total: NonnegativeInt
    nodes_considered: NonnegativeInt
    nodes_classified: NonnegativeInt
    nodes_unclassified: NonnegativeInt
    ambiguous_nodes: NonnegativeInt
    edges_considered: NonnegativeInt
    edges_ignored: NonnegativeInt
    rules_enabled: NonnegativeInt
    rules_evaluated: NonnegativeInt
    findings_total: NonnegativeInt
    findings_by_rule: dict[str, NonnegativeInt] = Field(default_factory=dict)
    findings_by_severity: dict[str, NonnegativeInt] = Field(default_factory=dict)
    nodes_by_layer: dict[str, NonnegativeInt] = Field(default_factory=dict)
    nodes_by_module: dict[str, NonnegativeInt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def counts_agree(self) -> Self:
        if (
            self.nodes_considered
            != self.nodes_classified + self.nodes_unclassified + self.ambiguous_nodes
        ):
            raise ValueError("classification counts must cover considered nodes")
        if self.findings_total != sum(self.findings_by_rule.values()) or self.findings_total != sum(
            self.findings_by_severity.values()
        ):
            raise ValueError("finding counts must agree")
        if self.rules_evaluated > self.rules_enabled:
            raise ValueError("cannot evaluate disabled rules")
        return self


class ConformanceReproducibility(DomainModel):
    project_id: ProjectId
    snapshot_id: SnapshotId | None = None
    snapshot_fingerprint: Sha256 | None = None
    iam_schema_version: str
    iam_fingerprint: Sha256
    architecture_spec_version: str
    architecture_spec_fingerprint: Sha256
    analyzer_version: str = "1.0.0"
    rule_engine_version: str = "1.0.0"
    classifier_version: str = "1.0.0"
    configuration: StaticAnalysisConfig


class StaticConformanceResult(DomainModel):
    result_schema_version: Literal["1.0"] = "1.0"
    status: ConformanceStatus
    is_valid: bool
    is_complete: bool
    classification: ArchitectureClassification
    statistics: StaticConformanceStatistics
    findings: tuple[Finding, ...] = ()
    diagnostics: tuple[ConformanceDiagnostic, ...] = ()
    reproducibility: ConformanceReproducibility
    specification_summary: JsonObject

    @model_validator(mode="after")
    def result_agrees(self) -> Self:
        if any(item.namespace != FindingNamespace.ARCH for item in self.findings):
            raise ValueError("static conformance only produces ARCH findings")
        if self.statistics.findings_total != len(self.findings):
            raise ValueError("finding statistics mismatch")
        if len({item.id for item in self.findings}) != len(self.findings):
            raise ValueError("findings must have unique IDs")
        expected = (
            ConformanceStatus.INVALID
            if not self.is_valid
            else ConformanceStatus.NON_CONFORMANT
            if self.findings
            else ConformanceStatus.CONFORMANT
            if self.is_complete
            else ConformanceStatus.INCOMPLETE
        )
        if self.status != expected:
            raise ValueError("conformance status must agree with validity/findings/completeness")
        if not self.is_valid and self.findings:
            raise ValueError("invalid analysis cannot claim code violations")
        return self
