from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import (
    ComponentRole,
    DiscoveredLayer,
    DiscoveryEvidenceKind,
    DiscoveryStrength,
)
from archguard.architecture.graph.config import NonnegativeInt, UnitFloat
from archguard.architecture.graph.models import (
    CycleObservation,
    GraphDiagnostic,
    GraphEdgeId,
    GraphNodeId,
)
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.core.identifiers import NodeId, ProjectId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language
from archguard.core.model.types import JsonObject, NonEmptyString, RepositoryPath


class DiscoveryEvidence(DomainModel):
    id: UUID
    kind: DiscoveryEvidenceKind
    subject_id: GraphNodeId
    observed_value: NonEmptyString
    signal: NonEmptyString
    strength: DiscoveryStrength
    role_hint: ComponentRole | None = None
    layer_hint: DiscoveredLayer | None = None
    location: SourceLocation | None = None
    metadata: JsonObject = Field(default_factory=dict)


class RoleHypothesis(DomainModel):
    id: UUID
    subject_id: GraphNodeId
    role: ComponentRole
    strength: DiscoveryStrength
    candidate_roles: tuple[ComponentRole, ...] = ()
    conflicting_roles: tuple[ComponentRole, ...] = ()
    evidence: tuple[DiscoveryEvidence, ...] = ()
    explanation: NonEmptyString


class LayerHypothesis(DomainModel):
    id: UUID
    subject_id: GraphNodeId
    label: DiscoveredLayer
    strength: DiscoveryStrength
    candidate_layers: tuple[DiscoveredLayer, ...] = ()
    role_hypothesis_id: UUID
    evidence: tuple[DiscoveryEvidence, ...] = ()
    explanation: NonEmptyString


class DiscoveredComponent(DomainModel):
    id: GraphNodeId
    iam_node_id: NodeId
    name: NonEmptyString
    qualified_name: NonEmptyString
    language: Language
    file_path: RepositoryPath
    location: SourceLocation | None
    role: RoleHypothesis
    layer: LayerHypothesis
    module_id: UUID | None = None


class LayerGroup(DomainModel):
    label: DiscoveredLayer
    members: tuple[GraphNodeId, ...]
    strength_counts: dict[str, NonnegativeInt]
    internal_edges: NonnegativeInt
    incoming_edges: NonnegativeInt
    outgoing_edges: NonnegativeInt


class ModuleCandidate(DomainModel):
    id: UUID
    structural_name: NonEmptyString
    seed_kind: Literal["java_package", "source_directory"]
    namespace: NonEmptyString
    members: tuple[GraphNodeId, ...]
    strength: DiscoveryStrength
    shared_support: bool
    evidence: tuple[DiscoveryEvidence, ...]
    internal_component_count: NonnegativeInt
    internal_dependency_edges: NonnegativeInt
    incoming_cross_module_edges: NonnegativeInt
    outgoing_cross_module_edges: NonnegativeInt
    cohesion_ratio: UnitFloat | None
    incoming_module_ids: tuple[UUID, ...] = ()
    outgoing_module_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def members_agree(self) -> Self:
        if self.members != tuple(
            sorted(set(self.members), key=str)
        ) or self.internal_component_count != len(self.members):
            raise ValueError("module members must be unique, sorted and agree with size")
        denominator = (
            self.internal_dependency_edges
            + self.incoming_cross_module_edges
            + self.outgoing_cross_module_edges
        )
        expected = self.internal_dependency_edges / denominator if denominator else None
        if (expected is None) != (self.cohesion_ratio is None):
            raise ValueError("undefined cohesion must be null")
        if (
            expected is not None
            and self.cohesion_ratio is not None
            and abs(expected - self.cohesion_ratio) > 1e-12
        ):
            raise ValueError("cohesion must agree with dependency counts")
        return self


class DependencyMatrixCell(DomainModel):
    source: NonEmptyString
    target: NonEmptyString
    unique_projected_edges: NonnegativeInt
    internal: bool
    graph_edge_ids: tuple[GraphEdgeId, ...]

    @model_validator(mode="after")
    def edge_counts(self) -> Self:
        if (
            self.graph_edge_ids != tuple(sorted(set(self.graph_edge_ids), key=str))
            or self.unique_projected_edges != len(self.graph_edge_ids)
            or self.internal != (self.source == self.target)
        ):
            raise ValueError("matrix counts and internal flag must agree with unique edges")
        return self


class DependencyMatrix(DomainModel):
    labels: tuple[str, ...]
    cells: tuple[DependencyMatrixCell, ...]
    excluded_noncomponent_edges: NonnegativeInt

    @model_validator(mode="after")
    def valid_axes(self) -> Self:
        pairs = tuple((cell.source, cell.target) for cell in self.cells)
        if self.labels != tuple(sorted(set(self.labels))) or pairs != tuple(sorted(set(pairs))):
            raise ValueError("matrix axes and cells must be sorted and unique")
        if any(
            cell.source not in self.labels or cell.target not in self.labels for cell in self.cells
        ):
            raise ValueError("matrix endpoints must occur on its axes")
        return self


class TopologyRank(DomainModel):
    node_id: GraphNodeId
    value: float = Field(ge=0, allow_inf_nan=False)


class TopologySummary(DomainModel):
    component_count: NonnegativeInt
    graph_node_count: NonnegativeInt
    dependency_count: NonnegativeInt
    cyclic_sccs: tuple[CycleObservation, ...]
    highest_fan_in: tuple[TopologyRank, ...]
    highest_fan_out: tuple[TopologyRank, ...]
    highest_betweenness: tuple[TopologyRank, ...]
    graph_candidate_ids: tuple[UUID, ...]


class DiscoveredArchitecture(DomainModel):
    components: tuple[DiscoveredComponent, ...]
    layer_groups: tuple[LayerGroup, ...]
    module_candidates: tuple[ModuleCandidate, ...]
    unclassified_components: tuple[GraphNodeId, ...]
    ambiguous_components: tuple[GraphNodeId, ...]
    module_unassigned_components: tuple[GraphNodeId, ...]
    layer_dependency_matrix: DependencyMatrix
    module_dependency_matrix: DependencyMatrix
    topology: TopologySummary


class DiscoveryStatistics(DomainModel):
    components_total: NonnegativeInt
    role_hypotheses: NonnegativeInt
    role_strength_counts: dict[str, NonnegativeInt]
    role_counts: dict[str, NonnegativeInt]
    role_unknown: NonnegativeInt
    role_ambiguous: NonnegativeInt
    layer_counts: dict[str, NonnegativeInt]
    layer_assigned: NonnegativeInt
    layer_unknown: NonnegativeInt
    layer_ambiguous: NonnegativeInt
    module_candidates: NonnegativeInt
    module_assigned_components: NonnegativeInt
    module_unassigned_components: NonnegativeInt
    evidence_count_by_type: dict[str, NonnegativeInt]
    role_coverage: UnitFloat | None
    layer_coverage: UnitFloat | None

    @model_validator(mode="after")
    def counts_agree(self) -> Self:
        count = self.components_total
        if (
            self.role_hypotheses != count
            or sum(self.role_counts.values()) + self.role_ambiguous != count
            or sum(self.role_strength_counts.values()) != count
            or self.role_unknown != self.role_counts.get(ComponentRole.UNKNOWN.value, 0)
            or self.role_ambiguous
            != self.role_strength_counts.get(DiscoveryStrength.AMBIGUOUS.value, 0)
            or sum(self.layer_counts.values()) != count
            or self.layer_assigned + self.layer_unknown + self.layer_ambiguous != count
            or self.module_assigned_components + self.module_unassigned_components != count
        ):
            raise ValueError("discovery statistics must cover all eligible components")
        for assigned, coverage in (
            (count - self.role_unknown - self.role_ambiguous, self.role_coverage),
            (self.layer_assigned, self.layer_coverage),
        ):
            if not count:
                if coverage is not None:
                    raise ValueError("empty discovery coverage must be null")
            elif coverage is None or abs(coverage - assigned / count) > 1e-12:
                raise ValueError("coverage must agree with unambiguous assignments")
        return self


class DiscoveryReproducibility(DomainModel):
    project_id: ProjectId
    snapshot_fingerprint: str | None
    iam_schema_version: str
    iam_fingerprint: str
    upstream_versions: JsonObject
    graph_engine_version: str
    discovery_engine_version: Literal["1.0.0"] = "1.0.0"
    configuration: ArchitectureDiscoveryConfig
    configuration_fingerprint: str
    not_calibrated: Literal[True] = True


class ArchitectureDiscoveryResult(DomainModel):
    result_schema_version: Literal["1.0"] = "1.0"
    analysis_kind: Literal["architecture_discovery"] = "architecture_discovery"
    status: Literal["COMPLETE", "INCOMPLETE", "INVALID"]
    is_valid: bool
    is_complete: bool
    discovered: DiscoveredArchitecture
    graph: GraphAnalysisResult
    diagnostics: tuple[GraphDiagnostic, ...]
    statistics: DiscoveryStatistics
    reproducibility: DiscoveryReproducibility

    @model_validator(mode="after")
    def result_agrees(self) -> Self:
        if (
            self.graph.findings
            or self.graph.conformance is not None
            or self.graph.reproducibility.architecture_spec_fingerprint is not None
        ):
            raise ValueError("discovery cannot consume target conformance analysis")
        if self.status != (
            "INVALID" if not self.is_valid else "COMPLETE" if self.is_complete else "INCOMPLETE"
        ):
            raise ValueError("discovery status must agree with processing state")
        components = self.discovered.components
        graph_ids = {node.id for node in self.graph.graph.nodes}
        modules = {module.id: module for module in self.discovered.module_candidates}
        ids = tuple(item.id for item in components)
        if (
            ids != tuple(sorted(set(ids), key=str))
            or self.statistics.components_total != len(components)
            or self.statistics.role_hypotheses != len(components)
        ):
            raise ValueError("component IDs and counts must agree")
        for component in components:
            if component.id not in graph_ids or (
                component.module_id is not None
                and (
                    component.module_id not in modules
                    or component.id not in modules[component.module_id].members
                )
            ):
                raise ValueError("discovered component must refer to an actual graph node/module")
            if (
                component.role.subject_id != component.id
                or component.layer.subject_id != component.id
                or component.layer.role_hypothesis_id != component.role.id
            ):
                raise ValueError("hypotheses must refer to their actual component")
        if (
            self.statistics.module_candidates != len(self.discovered.module_candidates)
            or self.statistics.module_assigned_components
            + self.statistics.module_unassigned_components
            != len(components)
        ):
            raise ValueError("module statistics must cover components")
        return self
