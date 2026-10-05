from typing import Annotated, Literal, NewType, Self
from uuid import UUID

from pydantic import Field, model_validator

from archguard.architecture.graph.config import GraphProjectionSpec, NonnegativeInt, UnitFloat
from archguard.core.identifiers import EdgeId, NodeId, ProjectId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import EdgeKind, NodeKind
from archguard.core.model.types import JsonObject, NonEmptyString

GraphNodeId = NewType("GraphNodeId", UUID)
GraphEdgeId = NewType("GraphEdgeId", UUID)


class GraphDiagnostic(DomainModel):
    code: NonEmptyString
    message: NonEmptyString
    subject_id: UUID | None = None


class GraphNode(DomainModel):
    id: GraphNodeId
    label: NonEmptyString
    kind: NodeKind | None = None
    iam_node_ids: tuple[NodeId, ...] = ()
    locations: tuple[SourceLocation, ...] = ()
    member_count: NonnegativeInt = 0
    method_count: NonnegativeInt = 0


class DependencyProof(DomainModel):
    iam_edge_id: EdgeId
    source_node_id: NodeId
    target_node_id: NodeId
    relation: EdgeKind
    locations: Annotated[tuple[SourceLocation, ...], Field(min_length=1)]
    provenance: Annotated[tuple[JsonObject, ...], Field(min_length=1)]
    occurrences: Annotated[int, Field(strict=True, gt=0)]
    provenance_truncated: NonnegativeInt = 0

    @model_validator(mode="after")
    def consistent_counts(self) -> Self:
        if self.occurrences != len(self.provenance) + self.provenance_truncated:
            raise ValueError("proof counts must agree")
        if len(self.locations) != len(self.provenance):
            raise ValueError("each provenance record must have a location")
        return self


class GraphEdge(DomainModel):
    id: GraphEdgeId
    source_id: GraphNodeId
    target_id: GraphNodeId
    relation_kinds: Annotated[tuple[EdgeKind, ...], Field(min_length=1)]
    proofs: Annotated[tuple[DependencyProof, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def canonical_proof(self) -> Self:
        if self.relation_kinds != tuple(sorted({item.relation for item in self.proofs})):
            raise ValueError("relation kinds must be sorted, unique and match proof")
        ids = tuple(item.iam_edge_id for item in self.proofs)
        if ids != tuple(sorted(set(ids), key=str)):
            raise ValueError("proof references must be sorted and unique")
        return self


class ArchitectureGraph(DomainModel):
    graph_schema_version: Literal["1.0"] = "1.0"
    project_id: ProjectId
    projection: GraphProjectionSpec
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()

    @model_validator(mode="after")
    def valid_graph(self) -> Self:
        nodes = {item.id for item in self.nodes}
        if len(nodes) != len(self.nodes) or len({edge.id for edge in self.edges}) != len(
            self.edges
        ):
            raise ValueError("graph IDs must be unique")
        pairs = {(item.source_id, item.target_id) for item in self.edges}
        if len(pairs) != len(self.edges):
            raise ValueError("parallel typed IAM edges must be aggregated")
        for edge in self.edges:
            if edge.source_id not in nodes or edge.target_id not in nodes:
                raise ValueError("graph endpoints must exist")
            if edge.source_id == edge.target_id and not self.projection.include_self_edges:
                raise ValueError("self edges are disabled")
        return self


class ProjectionStatistics(DomainModel):
    iam_nodes_input: NonnegativeInt
    iam_edges_input: NonnegativeInt
    graph_nodes: NonnegativeInt = 0
    graph_edges: NonnegativeInt = 0
    self_edges_removed: NonnegativeInt = 0
    external_nodes_excluded: NonnegativeInt = 0
    unmapped_nodes: NonnegativeInt = 0
    unclassified_nodes_excluded: NonnegativeInt = 0
    filtered_edges: NonnegativeInt = 0
    unproven_edges: NonnegativeInt = 0


class GraphBuildResult(DomainModel):
    graph: ArchitectureGraph
    statistics: ProjectionStatistics
    diagnostics: tuple[GraphDiagnostic, ...] = ()
    is_valid: bool = True
    is_complete: bool = True


class StronglyConnectedComponent(DomainModel):
    id: UUID
    members: Annotated[tuple[GraphNodeId, ...], Field(min_length=1)]
    internal_edge_count: NonnegativeInt

    size: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def valid_members(self) -> Self:
        if self.size != len(self.members) or self.members != tuple(
            sorted(set(self.members), key=str)
        ):
            raise ValueError("SCC members must be sorted, unique and agree with size")
        return self


class CycleObservation(DomainModel):
    scc_id: UUID
    members: tuple[GraphNodeId, ...]
    node_ids: tuple[GraphNodeId, ...] = ()
    edge_ids: tuple[GraphEdgeId, ...] = ()
    truncated: bool = False

    @model_validator(mode="after")
    def closed_proof(self) -> Self:
        if self.truncated:
            if self.node_ids or self.edge_ids:
                raise ValueError("truncated cycle cannot claim a closed proof")
        elif (
            len(self.node_ids) < 3
            or self.node_ids[0] != self.node_ids[-1]
            or len(self.edge_ids) != len(self.node_ids) - 1
        ):
            raise ValueError("cycle proof must be closed with corresponding edges")
        return self


class GraphNodeMetrics(DomainModel):
    node_id: GraphNodeId
    in_degree_edges: NonnegativeInt
    out_degree_edges: NonnegativeInt
    unique_in_neighbors: NonnegativeInt
    unique_out_neighbors: NonnegativeInt
    afferent_coupling: NonnegativeInt
    efferent_coupling: NonnegativeInt
    total_unique_neighbors: NonnegativeInt
    instability: UnitFloat | None
    in_degree_centrality: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    out_degree_centrality: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    betweenness_centrality: UnitFloat | None
    pagerank: UnitFloat | None
    scc_size: NonnegativeInt
    is_cyclic: bool


class GraphPath(DomainModel):
    node_ids: tuple[GraphNodeId, ...] = ()
    edge_ids: tuple[GraphEdgeId, ...] = ()
    iam_edge_ids: tuple[EdgeId, ...] = ()


class GraphNeighbourhood(DomainModel):
    node_ids: tuple[GraphNodeId, ...]
    edge_ids: tuple[GraphEdgeId, ...]
    iam_edge_ids: tuple[EdgeId, ...]
    truncated: bool
