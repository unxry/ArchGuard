from archguard.architecture.discovery.enums import ComponentRole, DiscoveredLayer, DiscoveryStrength
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.algorithms import neighbourhood
from archguard.architecture.graph.models import ArchitectureGraph, GraphEdge, GraphNodeId
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.intelligence.models import (
    ContextSelectionConfig,
    ContextStrategy,
    RuleId,
    SelectedNode,
    SemanticAnalysisTarget,
    TargetSelectionConfig,
)
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel


class ContextSelectionError(Exception):
    pass


def resolve_node(iam: ArchitectureModel, name: str) -> NodeId:
    matches = [
        node.id
        for node in iam.nodes
        if name in {str(node.id), node.name, node.qualified_name}
        and node.kind not in {NodeKind.PROJECT, NodeKind.PACKAGE, NodeKind.EXTERNAL_DEPENDENCY}
    ]
    if len(matches) != 1:
        raise ContextSelectionError("target must resolve to exactly one internal IAM node")
    return matches[0]


def graph_owner(graph: ArchitectureGraph, node: NodeId) -> GraphNodeId:
    matches = [item.id for item in graph.nodes if node in item.iam_node_ids]
    if len(matches) != 1:
        raise ContextSelectionError("target must have exactly one component projection owner")
    return matches[0]


def representative(iam: ArchitectureModel, graph: ArchitectureGraph, owner: GraphNodeId) -> NodeId:
    members = next(node.iam_node_ids for node in graph.nodes if node.id == owner)
    nodes = {node.id: node for node in iam.nodes}
    return min(
        members,
        key=lambda key: (
            nodes[key].kind in {NodeKind.FILE, NodeKind.FIELD, NodeKind.METHOD},
            str(key),
        ),
    )


def filtered_graph(graph: ArchitectureGraph, config: ContextSelectionConfig) -> ArchitectureGraph:
    edges = []
    for edge in graph.edges:
        proofs = tuple(p for p in edge.proofs if p.relation in config.included_relations)
        if proofs:
            edges.append(
                GraphEdge(
                    id=edge.id,
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    proofs=proofs,
                    relation_kinds=tuple(sorted({p.relation for p in proofs})),
                )
            )
    return ArchitectureGraph(
        project_id=graph.project_id,
        projection=graph.projection.model_copy(
            update={"included_relations": config.included_relations}
        ),
        nodes=graph.nodes,
        edges=tuple(edges),
    )


def select_context_nodes(
    iam: ArchitectureModel,
    graph: ArchitectureGraph,
    target: NodeId,
    config: ContextSelectionConfig,
    cycle_members: set[GraphNodeId] | None = None,
) -> tuple[tuple[SelectedNode, ...], int]:
    owner = graph_owner(graph, target)
    distances: dict[GraphNodeId, int | None] = {owner: 0}
    if config.strategy == ContextStrategy.GRAPH_GUIDED:
        # Reuse the graph engine's bounded query; successive shells provide distances.
        for depth in range(1, config.hop_count + 1):
            query = neighbourhood(graph, owner, depth, config.direction, max(1, len(graph.nodes)))
            for node in query.node_ids:
                distances.setdefault(node, depth)
    elif config.strategy == ContextStrategy.EXPANDED_BASELINE:
        distances = {node.id: 0 if node.id == owner else None for node in graph.nodes}
    outgoing = {edge.target_id for edge in graph.edges if edge.source_id == owner}
    incoming = {edge.source_id for edge in graph.edges if edge.target_id == owner}
    cyclic = cycle_members or set()

    def priority(key: GraphNodeId) -> tuple[int, int, str]:
        distance = distances[key]
        return (
            0
            if key == owner
            else 4
            if config.strategy == ContextStrategy.EXPANDED_BASELINE
            else 1
            if key in outgoing
            else 2
            if key in incoming
            else 3
            if key in cyclic
            else 4,
            distance or 0,
            str(key),
        )

    ordered = sorted(distances, key=priority)
    result = tuple(
        SelectedNode(
            node_id=target if key == owner else representative(iam, graph, key),
            distance=distances[key],
            reason=(
                "TARGET"
                if key == owner
                else "EXPANDED_BASELINE"
                if config.strategy == ContextStrategy.EXPANDED_BASELINE
                else "DIRECT_OUTGOING"
                if key in outgoing
                else "DIRECT_INCOMING"
                if key in incoming
                else "CYCLE_MEMBER"
                if key in cyclic
                else "K_HOP"
            ),
        )
        for key in ordered[: config.max_nodes]
    )
    return result, max(0, len(ordered) - len(result))


class SemanticAnalysisTargetSelector:
    def select(
        self,
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        discovery: ArchitectureDiscoveryResult | None,
        config: TargetSelectionConfig,
    ) -> tuple[tuple[SemanticAnalysisTarget, ...], int]:
        choices: dict[tuple[NodeId, RuleId], tuple[int, str]] = {}

        def add(node: NodeId, default: RuleId, priority: int, reason: str) -> None:
            graph_owner(graph.graph, node)
            for rule in config.rules or (default,):
                key = node, rule
                value = priority, reason
                if key not in choices or value < choices[key]:
                    choices[key] = value

        if config.explicit_targets:
            for name in config.explicit_targets:
                add(resolve_node(iam, name), "ARCH201", 0, "EXPLICIT_TARGET")
        else:
            if discovery is not None:
                for component in discovery.discovered.components:
                    if config.include_ambiguous and (
                        component.role.strength == DiscoveryStrength.AMBIGUOUS
                        or component.layer.label == DiscoveredLayer.AMBIGUOUS
                    ):
                        add(component.iam_node_id, "ARCH204", 1, "AMBIGUOUS_DISCOVERY")
                    if (
                        config.include_controllers
                        and component.role.role == ComponentRole.CONTROLLER
                    ):
                        add(component.iam_node_id, "ARCH202", 2, "CONTROLLER_HYPOTHESIS")
                    if config.include_unknown and component.role.role == ComponentRole.UNKNOWN:
                        add(component.iam_node_id, "ARCH201", 4, "UNKNOWN_DISCOVERY")
            edges = {edge.id: edge for edge in graph.graph.edges}
            for candidate in graph.candidates:
                if candidate.rule_id not in config.graph_candidate_rules:
                    continue
                owner = candidate.subject_node_id
                if owner is None and candidate.subject_edge_id is not None:
                    owner = edges[candidate.subject_edge_id].source_id
                if owner is not None:
                    add(representative(iam, graph.graph, owner), "ARCH205", 3, candidate.rule_id)
        ordered = sorted(choices, key=lambda key: (choices[key][0], str(key[0]), key[1]))
        targets = tuple(
            SemanticAnalysisTarget(
                node_id=node, candidate_rule_id=rule, reason=choices[node, rule][1]
            )
            for node, rule in ordered[: config.max_targets]
        )
        return targets, max(0, len(ordered) - len(targets))
