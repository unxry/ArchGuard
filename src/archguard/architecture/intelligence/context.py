import hashlib

from archguard.architecture.classification.classifier import ArchitectureClassifier
from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.intelligence.fragments import extract_fragments
from archguard.architecture.intelligence.models import (
    ArchitectureContextPack,
    ContextDiagnostic,
    ContextEvidence,
    ContextManifest,
    ContextSelectionConfig,
    SelectedNode,
    SourceFragment,
    canonical,
    digest,
)
from archguard.architecture.intelligence.ports import ContextRedactor, SourceReader
from archguard.architecture.intelligence.selection import (
    ContextSelectionError,
    filtered_graph,
    graph_owner,
    select_context_nodes,
)
from archguard.architecture.specification.models import (
    ArchitectureSpecification,
    CircularDependencySpecification,
    ForbiddenDependencySpecification,
    LayerDependencySpecification,
    ModuleBoundarySpecification,
    ReverseDependencySpecification,
)
from archguard.core.identifiers import NodeId
from archguard.core.model.types import JsonObject
from archguard.iam.model import ArchitectureModel


def _constraints(
    iam: ArchitectureModel, spec: ArchitectureSpecification, subjects: set[NodeId]
) -> list[ContextEvidence]:
    classified = [
        n for n in ArchitectureClassifier().classify(iam, spec).nodes if n.node_id in subjects
    ]
    layers = {n.layer for n in classified if n.layer is not None}
    modules = {n.module for n in classified if n.module is not None}
    result: list[ContextEvidence] = []
    for rule in spec.rules:
        relevant = False
        if isinstance(rule, ForbiddenDependencySpecification):
            relevant = any(
                s.layer in layers or s.module in modules for s in (rule.source, rule.target)
            )
        elif isinstance(rule, LayerDependencySpecification):
            relevant = rule.source in layers
        elif isinstance(rule, ModuleBoundarySpecification):
            relevant = rule.source in modules
        elif isinstance(rule, ReverseDependencySpecification):
            relevant = rule.expected.source in layers or rule.expected.target in layers
        elif isinstance(rule, CircularDependencySpecification):
            relevant = bool(classified)
        if relevant and rule.enabled:
            normalized = rule.model_dump(mode="json", by_alias=True, exclude={"description"})
            result.append(
                ContextEvidence(
                    evidence_id=f"ARC{len(result) + 1:03}",
                    kind="TARGET_CONSTRAINT",
                    subject_node_ids=tuple(sorted(subjects, key=str)),
                    data={
                        "normative": True,
                        "constraint": normalized,
                        "matched_layers": [layer for layer in sorted(layers)],
                        "matched_modules": [module for module in sorted(modules)],
                        "classification_ambiguous": any(
                            n.layer_candidates
                            and not n.layer
                            or n.module_candidates
                            and not n.module
                            for n in classified
                        ),
                    },
                )
            )
    return result


class GraphGuidedContextBuilder:
    def __init__(self, redactor: ContextRedactor | None = None) -> None:
        self.redactor = redactor

    def build(
        self,
        target: NodeId,
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        workspace: SourceReader,
        config: ContextSelectionConfig | None = None,
        spec: ArchitectureSpecification | None = None,
        discovery: ArchitectureDiscoveryResult | None = None,
        *,
        allow_invalid_iam_context: bool = False,
    ) -> ArchitectureContextPack:
        config = ContextSelectionConfig.model_validate(config or ContextSelectionConfig())
        partial_iam = (
            allow_invalid_iam_context
            and iam.metadata.get("is_valid") is False
            and "INVALID_IAM" in {d.code for d in graph.diagnostics}
            and {d.code for d in graph.diagnostics} <= {"INVALID_IAM", "INCOMPLETE_IAM"}
        )
        if (
            (not graph.is_valid and not partial_iam)
            or graph.graph.project_id != iam.project.id
            or graph.reproducibility.iam_fingerprint != iam_fingerprint(iam)
        ):
            raise ContextSelectionError("context requires a valid graph for this IAM")
        if discovery is not None and discovery.graph.reproducibility != graph.reproducibility:
            raise ContextSelectionError("discovery must refer to the supplied graph analysis")
        filtered = filtered_graph(graph.graph, config)
        selected, dropped_nodes = select_context_nodes(
            iam,
            filtered,
            target,
            config,
            {node for cycle in graph.cycles for node in cycle.members},
        )
        fragments, dropped_files, dropped_fragments, errors = extract_fragments(
            iam, selected, workspace, config, self.redactor
        )
        subjects = {item.node_id for item in selected}
        owners = {graph_owner(filtered, node): node for node in subjects}
        evidence: list[ContextEvidence] = []
        if spec is not None and config.include_spec:
            evidence.extend(_constraints(iam, spec, subjects))
        if config.include_dependency_paths:
            for edge in sorted(filtered.edges, key=lambda item: str(item.id)):
                if edge.source_id in owners and edge.target_id in owners:
                    index = 1 + sum(e.kind == "DEPENDENCY" for e in evidence)
                    evidence.append(
                        ContextEvidence(
                            evidence_id=f"DEP{index:03}",
                            kind="DEPENDENCY",
                            subject_node_ids=(owners[edge.source_id], owners[edge.target_id]),
                            data={
                                "graph_edge_id": str(edge.id),
                                "source": str(owners[edge.source_id]),
                                "target": str(owners[edge.target_id]),
                                "proofs": [
                                    {
                                        "iam_edge_id": str(p.iam_edge_id),
                                        "source_node_id": str(p.source_node_id),
                                        "target_node_id": str(p.target_node_id),
                                        "relation": p.relation.value,
                                        "locations": [
                                            loc.model_dump(mode="json") for loc in p.locations
                                        ],
                                        "provenance": "RESOLVED_IAM_DEPENDENCY",
                                        "occurrences": p.occurrences,
                                        "provenance_truncated": p.provenance_truncated,
                                    }
                                    for p in edge.proofs
                                ],
                            },
                        )
                    )
        if discovery is not None and config.include_discovery:
            modules = {module.id: module for module in discovery.discovered.module_candidates}
            for component in sorted(discovery.discovered.components, key=lambda item: str(item.id)):
                if component.id in owners:
                    module = modules.get(component.module_id) if component.module_id else None
                    index = 1 + sum(e.kind == "DISCOVERY_HYPOTHESIS" for e in evidence)
                    evidence.append(
                        ContextEvidence(
                            evidence_id=f"DISC{index:03}",
                            kind="DISCOVERY_HYPOTHESIS",
                            subject_node_ids=(owners[component.id],),
                            data={
                                "normative": False,
                                "status": "HYPOTHESIS",
                                "not_calibrated": True,
                                "role": component.role.role.value,
                                "role_strength": component.role.strength.value,
                                "layer": component.layer.label.value,
                                "layer_strength": component.layer.strength.value,
                                "candidate_layers": [
                                    layer.value for layer in component.layer.candidate_layers
                                ],
                                "module": {
                                    "id": str(module.id),
                                    "namespace": module.namespace,
                                    "strength": module.strength.value,
                                    "shared_support": module.shared_support,
                                }
                                if module
                                else None,
                                "evidence": [
                                    {
                                        "kind": e.kind.value,
                                        "signal": e.signal,
                                        "strength": e.strength.value,
                                    }
                                    for e in component.role.evidence
                                ],
                            },
                        )
                    )
        if config.include_metrics:
            for metric in sorted(graph.metrics, key=lambda item: str(item.node_id)):
                if metric.node_id in owners:
                    index = 1 + sum(e.kind == "GRAPH_METRIC" for e in evidence)
                    evidence.append(
                        ContextEvidence(
                            evidence_id=f"GRAPH{index:03}",
                            kind="GRAPH_METRIC",
                            subject_node_ids=(owners[metric.node_id],),
                            data={
                                "metric_scope": "FULL_ORIGINAL_PROJECTION",
                                "Ca": metric.afferent_coupling,
                                "Ce": metric.efferent_coupling,
                                "I": round(metric.instability, 12)
                                if metric.instability is not None
                                else None,
                                "betweenness": round(metric.betweenness_centrality, 12)
                                if metric.betweenness_centrality is not None
                                else None,
                                "cycle_membership": metric.is_cyclic,
                                "scc_size": metric.scc_size,
                            },
                        )
                    )
        diagnostics = tuple(
            ContextDiagnostic(
                code="CONTEXT_SOURCE_UNAVAILABLE",
                message="selected source could not be read safely",
            )
            for _ in errors
        )
        if partial_iam:
            diagnostics += (
                ContextDiagnostic(
                    code="CONTEXT_INVALID_IAM_PARTIAL_DATA",
                    message="Raw resolved dependencies from globally invalid IAM; "
                    "source and topology remain untrusted, incomplete context data",
                ),
            )
        if config.token_budget is not None:
            diagnostics += (
                ContextDiagnostic(
                    code="CONTEXT_TOKEN_BUDGET_UNMEASURABLE",
                    message="token budget requires provider token counting",
                ),
            )

        def data(
            parts: tuple[SourceFragment, ...],
            items: list[ContextEvidence],
            nodes: tuple[SelectedNode, ...],
        ) -> JsonObject:
            return {
                "trust": "UNTRUSTED_DATA",
                "target_node_id": str(target),
                "selected_node_ids": [str(n.node_id) for n in nodes],
                "source_fragments": [part.model_dump(mode="json") for part in parts],
                "evidence": [item.model_dump(mode="json") for item in items],
            }

        dropped_evidence = 0
        while len(canonical(data(fragments, evidence, selected))) > config.max_total_chars:
            if evidence:
                evidence.pop()
                dropped_evidence += 1
            elif len(fragments) > 1:
                fragments = fragments[:-1]
                dropped_fragments += 1
            elif fragments:
                original = fragments[0]
                excess = (
                    len(canonical(data(fragments, evidence, selected))) - config.max_total_chars
                )
                text = original.text[: max(0, len(original.text) - excess)]
                if not text:
                    fragments = ()
                    dropped_fragments += 1
                    continue
                reference = original.reference.model_copy(
                    update={
                        "truncated": True,
                        "chars": len(text),
                        "end_line": original.reference.start_line
                        + max(0, len(text.splitlines()) - 1),
                        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    }
                )
                fragments = (SourceFragment(reference=reference, text=text),)
            elif len(selected) > 1:
                selected = selected[:-1]
                dropped_nodes += 1
            else:
                raise ContextSelectionError("context envelope exceeds character budget")
        material = {
            "context_schema_version": "1.0",
            "target_node_id": str(target),
            "configuration": config.model_dump(mode="json"),
            "selected_nodes": [n.model_dump(mode="json") for n in selected],
            "fragments": [part.reference.model_dump(mode="json") for part in fragments],
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "redactor_id": self.redactor.redactor_id if self.redactor else None,
        }
        manifest = ContextManifest(
            target_node_id=target,
            configuration=config,
            selected_nodes=selected,
            fragments=tuple(part.reference for part in fragments),
            evidence=tuple(evidence),
            context_fingerprint=digest(material),
            context_chars=len(canonical(data(fragments, evidence, selected))),
            files=len({part.reference.relative_path for part in fragments}),
            truncated=bool(
                dropped_nodes
                or dropped_files
                or dropped_fragments
                or dropped_evidence
                or any(part.reference.truncated for part in fragments)
            ),
            dropped_nodes=dropped_nodes,
            dropped_files=dropped_files,
            dropped_fragments=dropped_fragments,
            dropped_evidence=dropped_evidence,
            redactor_id=self.redactor.redactor_id if self.redactor else None,
            diagnostics=diagnostics,
        )
        return ArchitectureContextPack(manifest=manifest, fragments=fragments)
