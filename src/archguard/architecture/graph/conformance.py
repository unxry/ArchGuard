import json
from uuid import uuid5

import networkx as nx
from pydantic import Field, JsonValue

from archguard.architecture.classification.classifier import ArchitectureClassifier
from archguard.architecture.conformance.dependencies import location_order
from archguard.architecture.conformance.models import ConformanceStatus
from archguard.architecture.graph.algorithms import (
    cycle_observations,
    strongly_connected_components,
)
from archguard.architecture.graph.builder import GraphBuilder
from archguard.architecture.graph.config import GraphAnalysisConfig, GraphProjectionSpec
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    CycleObservation,
    GraphDiagnostic,
    StronglyConnectedComponent,
)
from archguard.architecture.specification.models import (
    ArchitectureSpecification,
    CircularDependencySpecification,
)
from archguard.core.evidence import Evidence, EvidenceType
from archguard.core.findings.detector import Detector
from archguard.core.findings.enums import DetectorSource, FindingNamespace
from archguard.core.findings.model import Finding
from archguard.core.identifiers import EdgeId, EvidenceId, FindingId, NodeId, TraceId
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject
from archguard.core.traces import Trace, TraceStep
from archguard.iam.model import ArchitectureModel


class GraphConformanceResult(DomainModel):
    status: ConformanceStatus
    is_valid: bool
    is_complete: bool
    rule_enabled: bool
    graph: ArchitectureGraph | None = None
    sccs: tuple[StronglyConnectedComponent, ...] = ()
    cycles: tuple[CycleObservation, ...] = ()
    findings: tuple[Finding, ...] = ()
    diagnostics: tuple[GraphDiagnostic, ...] = ()
    reproducibility: JsonObject = Field(default_factory=dict)


def cyclic_finding(
    graph: ArchitectureGraph,
    cycle: CycleObservation,
    rule: CircularDependencySpecification,
    spec_hash: str,
) -> Finding:
    scope = rule.model_dump(
        mode="json", by_alias=True, exclude={"severity", "description", "enabled"}
    )
    identity = json.dumps(
        ["graph-circular-finding-v1", scope, sorted(map(str, cycle.members))],
        sort_keys=True,
        separators=(",", ":"),
    )
    finding_id = FindingId(uuid5(graph.project_id, identity))
    nodes = {node.id: node for node in graph.nodes}
    edge_lookup = {edge.id: edge for edge in graph.edges}
    edges = [edge_lookup[edge_id] for edge_id in cycle.edge_ids]
    locations = sorted(
        {location for edge in edges for proof in edge.proofs for location in proof.locations},
        key=location_order,
    )
    steps = [
        TraceStep(
            sequence=1,
            node_id=NodeId(cycle.node_ids[0]),
            label=nodes[cycle.node_ids[0]].label,
            location=locations[0],
        )
    ]
    for index, edge in enumerate(edges, 2):
        proof = min(
            edge.proofs,
            key=lambda item: (
                location_order(item.locations[0]),
                item.relation.value,
                str(item.iam_edge_id),
            ),
        )
        steps.append(
            TraceStep(
                sequence=index,
                node_id=NodeId(edge.target_id),
                edge_id=EdgeId(edge.id),
                relation=proof.relation,
                label=nodes[edge.target_id].label,
                location=proof.locations[0],
                metadata={
                    "graph_edge_id": str(edge.id),
                    "iam_edge_ids": [str(item.iam_edge_id) for item in edge.proofs],
                    "relation_kinds": [kind.value for kind in edge.relation_kinds],
                },
            )
        )
    path_proof: list[JsonValue] = [edge.model_dump(mode="json") for edge in edges]
    members: list[JsonValue] = [str(member) for member in cycle.members]
    return Finding(
        id=finding_id,
        namespace=FindingNamespace.ARCH,
        rule_id="ARCH003",
        category="circular_dependency",
        title="Circular Dependency",
        description=(
            f"An explicit cycle prohibition is violated by an SCC of "
            f"{len(cycle.members)} components in the {rule.projection.value} projection."
        ),
        severity=rule.severity,
        confidence=None,
        primary_location=locations[0],
        related_locations=tuple(locations[1:]),
        evidence=(
            Evidence(
                id=EvidenceId(uuid5(finding_id, "architecture-rule")),
                namespace=FindingNamespace.ARCH,
                type=EvidenceType.ARCHITECTURE_RULE,
                message="The target specification explicitly prohibits dependency cycles.",
                properties={
                    "expected": rule.model_dump(mode="json", by_alias=True),
                    "spec_fingerprint": spec_hash,
                },
            ),
            Evidence(
                id=EvidenceId(uuid5(finding_id, "cycle-proof")),
                namespace=FindingNamespace.ARCH,
                type=EvidenceType.GRAPH_PATH,
                message="A deterministic closed directed path proves the cyclic SCC.",
                location=locations[0],
                properties={
                    "scc_id": str(cycle.scc_id),
                    "members": members,
                    "representative_cycle": cycle.model_dump(mode="json"),
                    "edges": path_proof,
                },
            ),
        ),
        trace=Trace(
            id=TraceId(uuid5(finding_id, "closed-cycle")),
            steps=tuple(steps),
            metadata={"projection": rule.projection.value, "scc_id": str(cycle.scc_id)},
        ),
        detector=Detector(
            source=DetectorSource.GRAPH, name="graph-circular-conformance", version="1.0.0"
        ),
        recommendation=(
            "Break a dependency direction in the cycle, or update the explicit "
            "target rule if the cyclic boundary is intentional."
        ),
        metadata={
            "scc_members": members,
            "projection": rule.projection.value,
            "deterministic": True,
        },
    )


class GraphConformanceAnalyzer:
    version = "1.0.0"

    def analyze(
        self,
        model: ArchitectureModel,
        spec: ArchitectureSpecification,
        config: GraphAnalysisConfig | None = None,
    ) -> GraphConformanceResult:
        model = ArchitectureModel.model_validate(model)
        spec = ArchitectureSpecification.model_validate(spec)
        rule = next(
            (
                item
                for item in spec.rules
                if isinstance(item, CircularDependencySpecification) and item.enabled
            ),
            None,
        )
        if rule is None:
            return GraphConformanceResult(
                status=ConformanceStatus.CONFORMANT,
                is_valid=True,
                is_complete=True,
                rule_enabled=False,
            )
        classifier = ArchitectureClassifier().classify(model, spec)
        if not classifier.is_valid or model.metadata.get("is_valid") is False:
            return GraphConformanceResult(
                status=ConformanceStatus.INVALID,
                is_valid=False,
                is_complete=False,
                rule_enabled=True,
                diagnostics=(
                    GraphDiagnostic(
                        code="INVALID_CONFORMANCE_INPUT",
                        message="valid IAM and unambiguous target classification are required",
                    ),
                ),
            )
        base = config if config is not None else GraphAnalysisConfig()
        actual = base.model_copy(
            update={
                "projection": GraphProjectionSpec(
                    projection=rule.projection, included_relations=rule.relations
                )
            }
        )
        built = GraphBuilder().build(model, actual, classifier, spec.fingerprint)
        sccs = strongly_connected_components(built.graph) if built.is_valid else ()
        cycles = cycle_observations(built.graph, sccs, actual.max_cycle_trace_length)
        findings = tuple(
            sorted(
                (
                    cyclic_finding(built.graph, cycle, rule, spec.fingerprint)
                    for cycle in cycles
                    if not cycle.truncated
                ),
                key=lambda item: str(item.id),
            )
        )
        diagnostics = list(built.diagnostics)
        if any(cycle.truncated for cycle in cycles):
            diagnostics.append(
                GraphDiagnostic(
                    code="CYCLE_TRACE_LIMIT",
                    message="closed cycle proof exceeds configured trace length; finding omitted",
                )
            )
        complete = (
            built.is_complete
            and not any(cycle.truncated for cycle in cycles)
            and model.metadata.get("is_complete") is not False
        )
        status = (
            ConformanceStatus.INVALID
            if not built.is_valid
            else ConformanceStatus.NON_CONFORMANT
            if findings
            else ConformanceStatus.CONFORMANT
            if complete
            else ConformanceStatus.INCOMPLETE
        )
        return GraphConformanceResult(
            status=status,
            is_valid=built.is_valid,
            is_complete=complete,
            rule_enabled=True,
            graph=built.graph,
            sccs=sccs,
            cycles=cycles,
            findings=findings,
            diagnostics=tuple(diagnostics),
            reproducibility={
                "engine_version": self.version,
                "networkx_version": nx.__version__,
                "configuration": actual.model_dump(mode="json"),
                "spec_fingerprint": spec.fingerprint,
            },
        )
