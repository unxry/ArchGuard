import json
import re
from collections import Counter

from pydantic import JsonValue

from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.discovery.classification import (
    LayerInferenceEngine,
    StructuralRoleClassifier,
    dependency_signals,
)
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import ComponentRole, DiscoveredLayer, DiscoveryStrength
from archguard.architecture.discovery.models import (
    ArchitectureDiscoveryResult,
    DiscoveredArchitecture,
    DiscoveredComponent,
    DiscoveryReproducibility,
    DiscoveryStatistics,
)
from archguard.architecture.discovery.modules import ModuleDiscovery
from archguard.architecture.discovery.summary import (
    dependency_matrix,
    layer_groups,
    topology_summary,
)
from archguard.architecture.graph.analyzer import serialize_graph_result
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import NodeKind
from archguard.core.model.types import JsonObject
from archguard.iam.model import ArchitectureModel

COMPONENT_KINDS = {
    NodeKind.CLASS,
    NodeKind.INTERFACE,
    NodeKind.ENUM,
    NodeKind.FUNCTION,
    NodeKind.MODULE,
}


def upstream_versions(iam: ArchitectureModel) -> JsonObject:
    versions: JsonObject = {}
    for key in ("builder_version", "resolver_version"):
        value = iam.metadata.get(key)
        if isinstance(value, str) and re.fullmatch(r"[\w.-]{1,128}", value):
            versions[key] = value
    for key in ("extractor_versions", "parser_versions"):
        records = iam.metadata.get(key)
        if isinstance(records, list):
            clean: list[JsonValue] = []
            for record in records:
                if isinstance(record, dict):
                    clean.append(
                        {
                            name: value
                            for name, value in sorted(record.items())
                            if name.endswith(("_version", "_id"))
                            and isinstance(value, str)
                            and re.fullmatch(r"[\w.-]{1,128}", value)
                        }
                    )
            versions[key] = sorted(clean, key=lambda record: json.dumps(record, sort_keys=True))
    return versions


class ArchitectureDiscoveryAnalyzer:
    def analyze(
        self,
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        config: ArchitectureDiscoveryConfig | None = None,
    ) -> ArchitectureDiscoveryResult:
        iam = ArchitectureModel.model_validate(iam)
        graph = GraphAnalysisResult.model_validate(graph)
        config = ArchitectureDiscoveryConfig.model_validate(
            config if config is not None else ArchitectureDiscoveryConfig()
        )
        if (
            graph.graph.project_id != iam.project.id
            or graph.reproducibility.iam_fingerprint != iam_fingerprint(iam)
            or graph.reproducibility.configuration != config.graph
        ):
            raise ValueError("discovery graph must match the same IAM and graph configuration")
        if (
            graph.findings
            or graph.conformance is not None
            or graph.reproducibility.architecture_spec_fingerprint is not None
        ):
            raise ValueError("target conformance context cannot be used for discovery")
        nodes = {node.id: node for node in iam.nodes}
        files = {file.id: file for file in iam.source_files}
        metrics = {item.node_id: item for item in graph.metrics}
        classifier = StructuralRoleClassifier(iam)
        inference = LayerInferenceEngine()
        extra = dependency_signals(iam, graph, config) if graph.is_valid else {}
        components = []
        for projected in graph.graph.nodes if graph.is_valid else ():
            node = nodes.get(NodeId(projected.id))
            if node is None or node.kind not in COMPONENT_KINDS or node.file_id not in files:
                continue
            role = classifier.classify(
                node,
                projected,
                iam,
                graph,
                config,
                metrics.get(projected.id),
                extra.get(projected.id, ()),
            )
            components.append(
                DiscoveredComponent(
                    id=projected.id,
                    iam_node_id=node.id,
                    name=node.name,
                    qualified_name=node.qualified_name,
                    language=node.language,
                    file_path=files[node.file_id].file_path,
                    location=node.source_location,
                    role=role,
                    layer=inference.infer(role, iam, config),
                )
            )
        initial = tuple(sorted(components, key=lambda item: str(item.id)))
        refined = inference.refine({c.id: c.layer for c in initial}, iam, graph, config)
        initial = tuple(c.model_copy(update={"layer": refined[c.id]}) for c in initial)
        modules, assigned, module_diagnostics = ModuleDiscovery().discover(
            initial, iam, graph, config
        )
        final = tuple(c.model_copy(update={"module_id": assigned.get(c.id)}) for c in initial)
        layer_matrix = dependency_matrix(
            {c.id: c.layer.label.value for c in final},
            graph,
            tuple(item.value for item in DiscoveredLayer),
        )
        module_matrix = dependency_matrix(
            {c.id: str(c.module_id) if c.module_id else "UNASSIGNED" for c in final},
            graph,
            (*tuple(str(m.id) for m in modules), "UNASSIGNED"),
        )
        ambiguous = tuple(
            c.id
            for c in final
            if c.role.strength == DiscoveryStrength.AMBIGUOUS
            or c.layer.label == DiscoveredLayer.AMBIGUOUS
        )
        ambiguous_ids = set(ambiguous)
        unclassified = tuple(
            c.id
            for c in final
            if c.id not in ambiguous_ids
            and (c.role.role == ComponentRole.UNKNOWN or c.layer.label == DiscoveredLayer.UNKNOWN)
        )
        unassigned = tuple(c.id for c in final if c.module_id is None)
        discovered = DiscoveredArchitecture(
            components=final,
            layer_groups=layer_groups(final, layer_matrix),
            module_candidates=modules,
            unclassified_components=unclassified,
            ambiguous_components=ambiguous,
            module_unassigned_components=unassigned,
            layer_dependency_matrix=layer_matrix,
            module_dependency_matrix=module_matrix,
            topology=topology_summary(final, graph, config),
        )
        role_counts = Counter(
            c.role.role.value for c in final if c.role.strength != DiscoveryStrength.AMBIGUOUS
        )
        role_ambiguous = sum(c.role.strength == DiscoveryStrength.AMBIGUOUS for c in final)
        layer_counts = Counter(c.layer.label.value for c in final)
        role_assigned = len(final) - role_counts[ComponentRole.UNKNOWN] - role_ambiguous
        layer_assigned = (
            len(final)
            - layer_counts[DiscoveredLayer.UNKNOWN]
            - layer_counts[DiscoveredLayer.AMBIGUOUS]
        )
        evidences = {item.id: item for c in final for item in (*c.role.evidence, *c.layer.evidence)}
        evidences.update({item.id: item for m in modules for item in m.evidence})
        statistics = DiscoveryStatistics(
            components_total=len(final),
            role_hypotheses=len(final),
            role_strength_counts=dict(
                sorted(Counter(c.role.strength.value for c in final).items())
            ),
            role_counts=dict(sorted(role_counts.items())),
            role_unknown=role_counts[ComponentRole.UNKNOWN],
            role_ambiguous=role_ambiguous,
            layer_counts=dict(sorted(layer_counts.items())),
            layer_assigned=layer_assigned,
            layer_unknown=layer_counts[DiscoveredLayer.UNKNOWN],
            layer_ambiguous=layer_counts[DiscoveredLayer.AMBIGUOUS],
            module_candidates=len(modules),
            module_assigned_components=len(assigned),
            module_unassigned_components=len(unassigned),
            evidence_count_by_type=dict(
                sorted(Counter(e.kind.value for e in evidences.values()).items())
            ),
            role_coverage=role_assigned / len(final) if final else None,
            layer_coverage=layer_assigned / len(final) if final else None,
        )
        return ArchitectureDiscoveryResult(
            status=graph.status,
            is_valid=graph.is_valid,
            is_complete=graph.is_complete,
            discovered=discovered,
            graph=graph,
            diagnostics=(*graph.diagnostics, *module_diagnostics),
            statistics=statistics,
            reproducibility=DiscoveryReproducibility(
                project_id=iam.project.id,
                snapshot_fingerprint=graph.reproducibility.snapshot_fingerprint,
                iam_schema_version=iam.iam_schema_version,
                iam_fingerprint=graph.reproducibility.iam_fingerprint,
                upstream_versions=upstream_versions(iam),
                graph_engine_version=graph.reproducibility.graph_engine_version,
                configuration=config,
                configuration_fingerprint=config.fingerprint,
            ),
        )


def serialize_discovery(result: ArchitectureDiscoveryResult) -> str:
    value = ArchitectureDiscoveryResult.model_validate(result).model_dump(mode="json")
    value["graph"] = json.loads(serialize_graph_result(result.graph))
    for name in ("role_coverage", "layer_coverage"):
        if value["statistics"][name] is not None:
            value["statistics"][name] = round(value["statistics"][name], 12)
    for module in value["discovered"]["module_candidates"]:
        if module["cohesion_ratio"] is not None:
            module["cohesion_ratio"] = round(module["cohesion_ratio"], 12)
    for item in value["discovered"]["topology"]["highest_betweenness"]:
        item["value"] = round(item["value"], 12)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
