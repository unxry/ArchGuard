from collections import Counter, defaultdict

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import DiscoveredLayer
from archguard.architecture.discovery.models import (
    DependencyMatrix,
    DependencyMatrixCell,
    DiscoveredComponent,
    LayerGroup,
    TopologyRank,
    TopologySummary,
)
from archguard.architecture.graph.models import GraphEdgeId, GraphNodeId
from archguard.architecture.graph.result import GraphAnalysisResult


def dependency_matrix(
    assignments: dict[GraphNodeId, str],
    graph: GraphAnalysisResult,
    labels: tuple[str, ...],
) -> DependencyMatrix:
    cells: dict[tuple[str, str], list[GraphEdgeId]] = defaultdict(list)
    excluded = 0
    for edge in graph.graph.edges:
        if edge.source_id not in assignments or edge.target_id not in assignments:
            excluded += 1
            continue
        cells[assignments[edge.source_id], assignments[edge.target_id]].append(edge.id)
    return DependencyMatrix(
        labels=tuple(sorted(set(labels))),
        excluded_noncomponent_edges=excluded,
        cells=tuple(
            DependencyMatrixCell(
                source=left,
                target=right,
                internal=left == right,
                unique_projected_edges=len(ids),
                graph_edge_ids=tuple(sorted(ids, key=str)),
            )
            for (left, right), ids in sorted(cells.items())
        ),
    )


def layer_groups(
    components: tuple[DiscoveredComponent, ...], matrix: DependencyMatrix
) -> tuple[LayerGroup, ...]:
    groups = []
    for label in sorted(DiscoveredLayer):
        members = tuple(c.id for c in components if c.layer.label == label)
        groups.append(
            LayerGroup(
                label=label,
                members=members,
                strength_counts=dict(
                    sorted(
                        Counter(
                            c.layer.strength.value for c in components if c.layer.label == label
                        ).items()
                    )
                ),
                internal_edges=sum(
                    cell.unique_projected_edges
                    for cell in matrix.cells
                    if cell.source == label and cell.target == label
                ),
                incoming_edges=sum(
                    cell.unique_projected_edges
                    for cell in matrix.cells
                    if cell.target == label and not cell.internal
                ),
                outgoing_edges=sum(
                    cell.unique_projected_edges
                    for cell in matrix.cells
                    if cell.source == label and not cell.internal
                ),
            )
        )
    return tuple(groups)


def topology_summary(
    components: tuple[DiscoveredComponent, ...],
    graph: GraphAnalysisResult,
    config: ArchitectureDiscoveryConfig,
) -> TopologySummary:
    eligible = {c.id for c in components}
    metrics = [item for item in graph.metrics if item.node_id in eligible]

    def ranked(field: str) -> tuple[TopologyRank, ...]:
        values = [
            (item.node_id, getattr(item, field))
            for item in metrics
            if getattr(item, field) is not None
        ]
        return tuple(
            TopologyRank(node_id=node, value=value)
            for node, value in sorted(values, key=lambda pair: (-pair[1], str(pair[0])))[
                : config.topology_rank_limit
            ]
        )

    return TopologySummary(
        component_count=len(components),
        graph_node_count=len(graph.graph.nodes),
        dependency_count=len(graph.graph.edges),
        cyclic_sccs=graph.cycles,
        highest_fan_in=ranked("afferent_coupling"),
        highest_fan_out=ranked("efferent_coupling"),
        highest_betweenness=ranked("betweenness_centrality"),
        graph_candidate_ids=tuple(item.candidate_id for item in graph.candidates),
    )
