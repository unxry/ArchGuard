from collections import Counter
from typing import Literal, Self

from pydantic import Field, model_validator

from archguard.architecture.graph.candidates import GraphCandidate
from archguard.architecture.graph.config import GraphAnalysisConfig, NonnegativeInt
from archguard.architecture.graph.conformance import GraphConformanceResult
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    CycleObservation,
    GraphDiagnostic,
    GraphNodeMetrics,
    ProjectionStatistics,
    StronglyConnectedComponent,
)
from archguard.core.findings.enums import DetectorSource, FindingNamespace
from archguard.core.findings.model import Finding
from archguard.core.identifiers import ProjectId
from archguard.core.model.base import DomainModel


class GraphStatistics(DomainModel):
    scc_count: NonnegativeInt
    cyclic_scc_count: NonnegativeInt
    cycle_observation_count: NonnegativeInt = 0
    cycle_findings: NonnegativeInt
    candidate_count_by_rule: dict[str, NonnegativeInt] = Field(default_factory=dict)
    metric_node_count: NonnegativeInt
    metrics_computed: tuple[str, ...]
    metrics_skipped: tuple[str, ...]


class GraphReproducibility(DomainModel):
    project_id: ProjectId
    snapshot_fingerprint: str | None
    iam_schema_version: str
    iam_fingerprint: str
    graph_engine_version: str = "1.0.0"
    networkx_version: str
    configuration: GraphAnalysisConfig
    configuration_fingerprint: str
    projection_fingerprint: str
    architecture_spec_fingerprint: str | None
    canonical_float_decimal_places: Literal[12] = 12


class GraphAnalysisResult(DomainModel):
    result_schema_version: Literal["1.0"] = "1.0"
    status: Literal["COMPLETE", "INCOMPLETE", "INVALID"]
    is_valid: bool
    is_complete: bool
    graph: ArchitectureGraph
    projection_statistics: ProjectionStatistics
    statistics: GraphStatistics
    metrics: tuple[GraphNodeMetrics, ...]
    sccs: tuple[StronglyConnectedComponent, ...]
    cycles: tuple[CycleObservation, ...]
    findings: tuple[Finding, ...] = ()
    candidates: tuple[GraphCandidate, ...] = ()
    conformance: GraphConformanceResult | None = None
    diagnostics: tuple[GraphDiagnostic, ...] = ()
    reproducibility: GraphReproducibility

    @model_validator(mode="after")
    def result_agrees(self) -> Self:
        if self.status != (
            "INVALID" if not self.is_valid else "COMPLETE" if self.is_complete else "INCOMPLETE"
        ):
            raise ValueError("analysis status must agree with validity and completeness")
        if any(
            f.namespace != FindingNamespace.ARCH
            or f.rule_id != "ARCH003"
            or f.detector.source != DetectorSource.GRAPH
            for f in self.findings
        ):
            raise ValueError("graph conformance only produces GRAPH ARCH003 findings")
        if self.findings and (
            not self.is_valid
            or self.conformance is None
            or self.findings != self.conformance.findings
        ):
            raise ValueError("findings require valid explicit graph conformance")
        if (
            self.statistics.scc_count != len(self.sccs)
            or self.statistics.cyclic_scc_count != len(self.cycles)
            or self.statistics.cycle_observation_count != len(self.cycles)
            or self.statistics.cycle_findings != len(self.findings)
        ):
            raise ValueError("cycle statistics must agree")
        if self.statistics.candidate_count_by_rule != dict(
            Counter(c.rule_id for c in self.candidates)
        ):
            raise ValueError("candidate statistics must agree")
        if self.statistics.metric_node_count != len(self.metrics):
            raise ValueError("metric statistics must agree")
        if self.projection_statistics.graph_nodes != len(
            self.graph.nodes
        ) or self.projection_statistics.graph_edges != len(self.graph.edges):
            raise ValueError("projection statistics must agree")
        return self
