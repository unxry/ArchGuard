from collections import defaultdict
from uuid import UUID, uuid5

from archguard.architecture.classification.models import ArchitectureClassification
from archguard.architecture.conformance.dependencies import location_order
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    DependencyProof,
    GraphBuildResult,
    GraphDiagnostic,
    GraphEdge,
    GraphEdgeId,
    GraphNode,
    GraphNodeId,
    ProjectionStatistics,
)
from archguard.architecture.graph.provenance import dependency_proof
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import Language, NodeKind
from archguard.iam.model import ArchitectureModel
from archguard.iam.nodes import ArchitectureNode

COMPONENT_KINDS = {NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.ENUM, NodeKind.FUNCTION}


class GraphResourceLimitError(Exception):
    pass


class GraphBuilder:
    version = "1.0.0"

    def build(
        self,
        model: ArchitectureModel,
        config: GraphAnalysisConfig,
        classification: ArchitectureClassification | None = None,
        spec_fingerprint: str | None = None,
    ) -> GraphBuildResult:
        model = ArchitectureModel.model_validate(model)
        projection = config.projection
        diagnostics: list[GraphDiagnostic] = []
        stats = ProjectionStatistics(
            iam_nodes_input=len(model.nodes),
            iam_edges_input=len(model.edges),
            external_nodes_excluded=sum(
                node.kind == NodeKind.EXTERNAL_DEPENDENCY for node in model.nodes
            )
            if not projection.include_external
            else 0,
        )
        empty = ArchitectureGraph(project_id=model.project.id, projection=projection)
        if projection.projection in {
            GraphProjection.TARGET_LAYER,
            GraphProjection.TARGET_MODULE,
        } and (classification is None or not classification.is_valid or spec_fingerprint is None):
            return GraphBuildResult(
                graph=empty,
                statistics=stats,
                is_valid=False,
                is_complete=False,
                diagnostics=(
                    GraphDiagnostic(
                        code="CLASSIFICATION_REQUIRED",
                        message=(
                            "target projection requires valid architecture classification "
                            "and specification"
                        ),
                    ),
                ),
            )
        try:
            mapping, projected = self._nodes(
                model, config, classification, spec_fingerprint, diagnostics
            )
            counts = stats.model_dump()
            counts["unmapped_nodes"] = sum(
                node.id not in mapping and node.file_id is not None for node in model.nodes
            )
            if projection.projection in {
                GraphProjection.TARGET_LAYER,
                GraphProjection.TARGET_MODULE,
            }:
                counts["unclassified_nodes_excluded"] = counts["unmapped_nodes"]
            groups: dict[tuple[GraphNodeId, GraphNodeId], list[DependencyProof]] = defaultdict(list)
            nodes = {node.id: node for node in model.nodes}
            complete = not any(item.code == "PACKAGE_LANGUAGE_UNSUPPORTED" for item in diagnostics)
            for edge in sorted(model.edges, key=lambda item: str(item.id)):
                left, right = mapping.get(edge.source_id), mapping.get(edge.target_id)
                if edge.kind not in projection.included_relations or left is None or right is None:
                    counts["filtered_edges"] += 1
                    continue
                if left == right and not projection.include_self_edges:
                    counts["self_edges_removed"] += 1
                    continue
                source = nodes[edge.source_id]
                if source.source_location is None:
                    counts["unproven_edges"] += 1
                    complete = False
                    continue
                try:
                    proof = dependency_proof(
                        edge,
                        source.source_location.file_path,
                        nodes[edge.target_id].kind == NodeKind.EXTERNAL_DEPENDENCY,
                    )
                except ValueError:
                    counts["unproven_edges"] += 1
                    complete = False
                    continue
                groups[left, right].append(proof)
                if len(groups) > config.max_graph_edges:
                    raise GraphResourceLimitError
                if proof.provenance_truncated:
                    complete = False
                    diagnostics.append(
                        GraphDiagnostic(
                            code="PROVENANCE_TRUNCATED",
                            message="projected edge has bounded incomplete provenance",
                            subject_id=edge.id,
                        )
                    )
            if counts["unproven_edges"]:
                diagnostics.append(
                    GraphDiagnostic(
                        code="UNPROVEN_DEPENDENCY",
                        message="unproven IAM dependencies were excluded",
                    )
                )
            edges = tuple(
                GraphEdge(
                    id=GraphEdgeId(
                        uuid5(
                            model.project.id,
                            f"graph-edge-v1:{projection.projection}:{left}:{right}",
                        )
                    ),
                    source_id=left,
                    target_id=right,
                    relation_kinds=tuple(sorted({proof.relation for proof in proofs})),
                    proofs=tuple(sorted(proofs, key=lambda item: str(item.iam_edge_id))),
                )
                for (left, right), proofs in sorted(
                    groups.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
                )
            )
            graph = ArchitectureGraph(
                project_id=model.project.id,
                projection=projection,
                nodes=tuple(sorted(projected, key=lambda item: str(item.id))),
                edges=edges,
            )
            counts.update(graph_nodes=len(graph.nodes), graph_edges=len(graph.edges))
            return GraphBuildResult(
                graph=graph,
                statistics=ProjectionStatistics.model_validate(counts),
                diagnostics=tuple(diagnostics),
                is_complete=complete,
            )
        except GraphResourceLimitError:
            return GraphBuildResult(
                graph=empty,
                statistics=stats,
                is_valid=False,
                is_complete=False,
                diagnostics=(
                    GraphDiagnostic(
                        code="GRAPH_RESOURCE_LIMIT",
                        message="graph projection exceeds configured node or edge budget",
                    ),
                ),
            )

    def _nodes(
        self,
        model: ArchitectureModel,
        config: GraphAnalysisConfig,
        classification: ArchitectureClassification | None,
        spec_hash: str | None,
        diagnostics: list[GraphDiagnostic],
    ) -> tuple[dict[NodeId, GraphNodeId], list[GraphNode]]:
        mode = config.projection.projection
        nodes = {node.id: node for node in model.nodes}
        files = {file.id: file for file in model.source_files}
        file_nodes = {node.file_id: node for node in model.nodes if node.kind == NodeKind.FILE}
        packages = {package.id: package for package in model.packages}
        assignments = (
            {item.node_id: item for item in classification.nodes} if classification else {}
        )
        components = {
            node.id: node
            for node in model.nodes
            if node.kind in COMPONENT_KINDS
            or (node.kind == NodeKind.MODULE and node.symbol_id is not None)
        }
        by_file: dict[UUID, list[ArchitectureNode]] = defaultdict(list)
        for node in components.values():
            if node.file_id is not None:
                by_file[node.file_id].append(node)
        groups: dict[GraphNodeId, list[ArchitectureNode]] = defaultdict(list)
        labels: dict[GraphNodeId, tuple[str, NodeKind | None]] = {}
        mapping: dict[NodeId, GraphNodeId] = {}
        unsupported_package = False
        for node in sorted(model.nodes, key=lambda item: str(item.id)):
            graph_id = None
            label = node.qualified_name
            kind: NodeKind | None = node.kind
            if node.kind == NodeKind.EXTERNAL_DEPENDENCY:
                if config.projection.include_external:
                    graph_id = GraphNodeId(node.id)
            elif node.file_id is not None:
                file = files[node.file_id]
                if mode == GraphProjection.COMPONENT:
                    owner = node
                    visited = set()
                    while owner.id not in components and owner.kind != NodeKind.FILE:
                        if owner.id in visited:
                            raise ValueError("cyclic IAM containment")
                        visited.add(owner.id)
                        raw_parent = owner.attributes.get("parent_node_id")
                        parent = (
                            nodes.get(NodeId(UUID(raw_parent)))
                            if isinstance(raw_parent, str)
                            else None
                        )
                        owner = parent if parent is not None else file_nodes[file.id]
                    if owner.kind == NodeKind.FILE and len(by_file[file.id]) == 1:
                        owner = by_file[file.id][0]
                    graph_id, label, kind = GraphNodeId(owner.id), owner.qualified_name, owner.kind
                elif mode == GraphProjection.FILE:
                    graph_id = GraphNodeId(file_nodes[file.id].id)
                    label, kind = file.file_path, NodeKind.FILE
                elif mode == GraphProjection.PACKAGE:
                    if file.language == Language.JAVA and file.package_id is not None:
                        package = packages[file.package_id]
                        graph_id = GraphNodeId(
                            uuid5(model.project.id, "graph-package-v1:" + package.qualified_name)
                        )
                        label, kind = package.qualified_name or "<default>", NodeKind.PACKAGE
                    else:
                        unsupported_package = True
                else:
                    assigned = assignments.get(node.id)
                    scope = (
                        assigned.layer
                        if assigned and mode == GraphProjection.TARGET_LAYER
                        else assigned.module
                        if assigned
                        else None
                    )
                    if scope is not None:
                        graph_id = GraphNodeId(
                            uuid5(model.project.id, f"graph-target-v1:{mode}:{spec_hash}:{scope}")
                        )
                        label, kind = scope, None
            if graph_id is not None:
                mapping[node.id] = graph_id
                groups[graph_id].append(node)
                labels[graph_id] = label, kind
                if len(groups) > config.max_graph_nodes:
                    raise GraphResourceLimitError
        if unsupported_package:
            diagnostics.append(
                GraphDiagnostic(
                    code="PACKAGE_LANGUAGE_UNSUPPORTED",
                    message="PACKAGE projection only represents Java packages; ES files excluded",
                )
            )
        projected = [
            GraphNode(
                id=graph_id,
                label=labels[graph_id][0],
                kind=labels[graph_id][1],
                iam_node_ids=tuple(sorted((node.id for node in members), key=str)),
                locations=tuple(
                    sorted(
                        {
                            node.source_location
                            for node in members
                            if node.source_location is not None
                        },
                        key=location_order,
                    )
                ),
                member_count=sum(
                    node.symbol_id is not None
                    and node.id != graph_id
                    and node.kind not in COMPONENT_KINDS | {NodeKind.MODULE}
                    for node in members
                ),
                method_count=sum(node.kind == NodeKind.METHOD for node in members),
            )
            for graph_id, members in groups.items()
        ]
        return mapping, projected
