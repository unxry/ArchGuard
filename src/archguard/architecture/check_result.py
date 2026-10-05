from typing import Literal, Self

from pydantic import model_validator

from archguard.architecture.conformance.models import (
    ConformanceReproducibility,
    ConformanceStatus,
    StaticConformanceResult,
    StaticConformanceStatistics,
)
from archguard.architecture.graph.conformance import GraphConformanceResult
from archguard.core.findings.model import Finding
from archguard.core.model.base import DomainModel


class ArchitectureCheckResult(DomainModel):
    result_schema_version: Literal["1.0"] = "1.0"
    analysis_kind: Literal["architecture_check"] = "architecture_check"
    status: ConformanceStatus
    is_valid: bool
    is_complete: bool
    static_result: StaticConformanceResult
    graph_result: GraphConformanceResult
    findings: tuple[Finding, ...]
    statistics: StaticConformanceStatistics
    reproducibility: ConformanceReproducibility

    @model_validator(mode="after")
    def aggregate_agrees(self) -> Self:
        expected = (
            ConformanceStatus.INVALID
            if not self.is_valid
            else ConformanceStatus.NON_CONFORMANT
            if self.findings
            else ConformanceStatus.CONFORMANT
            if self.is_complete
            else ConformanceStatus.INCOMPLETE
        )
        if self.status != expected or self.statistics.findings_total != len(self.findings):
            raise ValueError("architecture aggregate status and statistics must agree")
        if not self.is_valid and self.findings:
            raise ValueError("invalid aggregate cannot claim conformance findings")
        if self.is_valid and set(item.id for item in self.findings) != set(
            item.id for item in (*self.static_result.findings, *self.graph_result.findings)
        ):
            raise ValueError("aggregate must retain all independent conformance findings")
        return self
