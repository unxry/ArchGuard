from math import isclose
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, JsonValue

from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    GraphEdgeId,
    GraphNodeId,
    GraphNodeMetrics,
)
from archguard.core.evidence import Evidence, EvidenceType
from archguard.core.findings.enums import FindingNamespace
from archguard.core.identifiers import EvidenceId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject


class GraphCandidate(DomainModel):
    candidate_id: UUID
    rule_id: Literal["ARCH101", "ARCH102", "ARCH103", "ARCH104", "ARCH105"]
    title: str
    subject_node_id: GraphNodeId | None = None
    subject_edge_id: GraphEdgeId | None = None
    projection: GraphProjection
    metrics: JsonObject
    thresholds: JsonObject
    reason: str
    source_locations: tuple[SourceLocation, ...] = ()
    not_calibrated: Literal[True] = True
    confidence: Literal[None] = None
    evidence: tuple[Evidence, ...]
    metadata: JsonObject = Field(default_factory=dict)


def generate_candidates(
    graph: ArchitectureGraph, metrics: tuple[GraphNodeMetrics, ...], config: GraphAnalysisConfig
) -> tuple[GraphCandidate, ...]:
    thresholds = config.candidates
    lookup = {item.node_id: item for item in metrics}
    nodes = {node.id: node for node in graph.nodes}
    edge_lookup = {edge.id: edge for edge in graph.edges}
    incident: dict[GraphNodeId, list[GraphEdgeId]] = {node.id: [] for node in graph.nodes}
    neighbors: dict[GraphNodeId, set[GraphNodeId]] = {node.id: set() for node in graph.nodes}
    for edge in graph.edges:
        if edge.source_id != edge.target_id:
            incident[edge.source_id].append(edge.id)
            incident[edge.target_id].append(edge.id)
            neighbors[edge.source_id].add(edge.target_id)
            neighbors[edge.target_id].add(edge.source_id)
    result: list[GraphCandidate] = []

    def candidate(
        rule: Literal["ARCH101", "ARCH102", "ARCH103", "ARCH104", "ARCH105"],
        title: str,
        subject: GraphNodeId | GraphEdgeId,
        values: JsonObject,
        trigger: JsonObject,
        reason: str,
        edge_subject: bool = False,
    ) -> None:
        identity = uuid5(
            graph.project_id,
            f"graph-candidate-v1:{rule}:{graph.projection.projection}:{subject}:{config.fingerprint}",
        )
        edge = edge_lookup[GraphEdgeId(subject)] if edge_subject else None
        node = nodes[edge.source_id] if edge is not None else nodes[GraphNodeId(subject)]
        relevant: list[JsonValue] = (
            [str(edge.id)]
            if edge is not None
            else [str(item) for item in sorted(incident[node.id], key=str)]
        )
        adjacent: list[JsonValue] = (
            [str(edge.source_id), str(edge.target_id)]
            if edge
            else [str(item) for item in sorted(neighbors[node.id], key=str)]
        )
        locations = (
            tuple(location for proof in edge.proofs for location in proof.locations)
            if edge
            else node.locations
        )
        result.append(
            GraphCandidate(
                candidate_id=identity,
                rule_id=rule,
                title=title + " Candidate",
                subject_node_id=None if edge_subject else node.id,
                subject_edge_id=GraphEdgeId(subject) if edge_subject else None,
                projection=graph.projection.projection,
                metrics=values,
                thresholds=trigger,
                reason=reason,
                source_locations=locations,
                evidence=(
                    Evidence(
                        id=EvidenceId(uuid5(identity, "graph-metric")),
                        namespace=FindingNamespace.ARCH,
                        type=EvidenceType.GRAPH_METRIC,
                        message=reason,
                        location=locations[0] if locations else None,
                        properties={
                            "metrics": values,
                            "thresholds": trigger,
                            "projection": graph.projection.projection.value,
                            "graph_edges": relevant,
                            "neighbors": adjacent,
                        },
                    ),
                ),
                metadata={"configuration_fingerprint": config.fingerprint},
            )
        )

    for item in metrics:
        node = nodes[item.node_id]
        if (
            thresholds.excessive_coupling is not None
            and item.total_unique_neighbors >= thresholds.excessive_coupling
        ):
            candidate(
                "ARCH101",
                "Excessive Coupling",
                node.id,
                {"total_unique_neighbors": item.total_unique_neighbors},
                {"minimum": thresholds.excessive_coupling},
                "Total distinct architectural neighbours meet the configured coupling threshold.",
            )
        if thresholds.hub_fan_in is not None and item.afferent_coupling >= thresholds.hub_fan_in:
            candidate(
                "ARCH102",
                "Dependency Hub",
                node.id,
                {"afferent_coupling": item.afferent_coupling},
                {"minimum": thresholds.hub_fan_in},
                "Distinct incoming dependents meet the configured hub threshold.",
            )
        if (
            graph.projection.projection == GraphProjection.COMPONENT
            and thresholds.god_min_members is not None
            and thresholds.god_min_coupling is not None
            and node.kind is not None
            and node.member_count >= thresholds.god_min_members
            and item.total_unique_neighbors >= thresholds.god_min_coupling
            and (
                thresholds.god_min_methods is None
                or node.method_count >= thresholds.god_min_methods
            )
        ):
            candidate(
                "ARCH103",
                "Potential God Component",
                node.id,
                {
                    "member_count": node.member_count,
                    "method_count": node.method_count,
                    "total_unique_neighbors": item.total_unique_neighbors,
                },
                {
                    "min_members": thresholds.god_min_members,
                    "min_methods": thresholds.god_min_methods,
                    "min_total_coupling": thresholds.god_min_coupling,
                },
                "Structural size and coupling meet both explicitly configured thresholds.",
            )
        if (
            thresholds.bottleneck_betweenness is not None
            and item.betweenness_centrality is not None
            and meets_float_threshold(
                item.betweenness_centrality, thresholds.bottleneck_betweenness
            )
            and (
                thresholds.bottleneck_min_neighbors is None
                or item.total_unique_neighbors >= thresholds.bottleneck_min_neighbors
            )
        ):
            candidate(
                "ARCH105",
                "Architecture Bottleneck",
                node.id,
                {
                    "betweenness": item.betweenness_centrality,
                    "total_unique_neighbors": item.total_unique_neighbors,
                },
                {
                    "min_betweenness": thresholds.bottleneck_betweenness,
                    "min_neighbors": thresholds.bottleneck_min_neighbors,
                },
                "Directed betweenness and the support condition meet configured thresholds.",
            )
    if thresholds.unstable_delta is not None:
        for edge in graph.edges:
            left, right = lookup[edge.source_id].instability, lookup[edge.target_id].instability
            if (
                left is not None
                and right is not None
                and meets_float_threshold(right - left, thresholds.unstable_delta)
            ):
                candidate(
                    "ARCH104",
                    "Unstable Dependency",
                    edge.id,
                    {
                        "source_instability": left,
                        "target_instability": right,
                        "delta": right - left,
                    },
                    {"minimum_delta": thresholds.unstable_delta},
                    "A more stable component depends on a less stable component "
                    "beyond the configured instability delta.",
                    edge_subject=True,
                )
    return tuple(sorted(result, key=lambda item: (item.rule_id, str(item.candidate_id))))


def meets_float_threshold(value: float, threshold: float) -> bool:
    return value >= threshold or isclose(value, threshold, rel_tol=1e-12, abs_tol=0.0)
