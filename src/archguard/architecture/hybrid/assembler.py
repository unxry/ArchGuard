from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Literal, cast
from uuid import UUID, uuid5

from archguard.architecture.conformance.models import StaticConformanceResult
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.conformance import GraphConformanceResult
from archguard.architecture.graph.models import GraphEdge
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.hybrid.alignment import HybridEvidenceAligner, concern_agreement
from archguard.architecture.hybrid.models import (
    AlignmentMethod,
    ContextReference,
    ContextSummary,
    DiscoverySignal,
    EvidenceAgreement,
    EvidenceAlignment,
    EvidenceCompleteness,
    GraphMeasurement,
    GraphSignal,
    HybridCase,
    HybridCaseType,
    HybridEvidenceBundle,
    NumericObservation,
    SemanticSignal,
    StaticProof,
    SubjectPair,
)
from archguard.architecture.intelligence.models import (
    AIAnalysisResult,
    ContextManifest,
    SemanticDecision,
)
from archguard.core.evidence import EvidenceType
from archguard.core.findings.enums import FindingNamespace
from archguard.core.findings.model import Finding
from archguard.core.identifiers import EdgeId, NodeId
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel

LiteralOrigin = Literal["STATIC", "GRAPH_CONFORMANCE", "GRAPH", "AI", "CALLER"]


class HybridInputError(ValueError):
    code = "INVALID_HYBRID_INPUT"


def ordered_pairs(pairs: list[SubjectPair]) -> tuple[SubjectPair, ...]:
    return tuple(sorted(set(pairs), key=lambda pair: (str(pair.source_id), str(pair.target_id))))


def numeric_observations(values: Mapping[str, object]) -> tuple[NumericObservation, ...]:
    if any(value is not None and type(value) not in {int, float} for value in values.values()):
        raise HybridInputError("graph observations must be numeric or missing")
    return tuple(
        NumericObservation(name=name, value=cast(int | float | None, value))
        for name, value in sorted(values.items())
    )


class HybridEvidenceAssembler:
    def __init__(
        self,
        iam: ArchitectureModel,
        static: StaticConformanceResult | None,
        graph: GraphAnalysisResult | None,
        discovery: ArchitectureDiscoveryResult | None,
        ai: AIAnalysisResult | None,
        graph_conformance: GraphConformanceResult | None,
    ) -> None:
        self.iam, self.static, self.graph, self.discovery, self.ai = (
            iam,
            static,
            graph,
            discovery,
            ai,
        )
        self.graph_conformance = graph_conformance or (graph.conformance if graph else None)
        self.aligner = HybridEvidenceAligner(iam)
        self.edges = {edge.id: edge for edge in iam.edges}
        self.graph_signals: dict[UUID, GraphSignal] = {}
        self.semantic_signals: dict[UUID, SemanticSignal] = {}
        self.discovery_signals: dict[NodeId, DiscoverySignal] = {}
        self.measurements: dict[NodeId, GraphMeasurement] = {}
        self.manifests = {m.context_fingerprint: m for m in ai.manifests} if ai else {}
        self.contexts_by_target: dict[NodeId, set[str]] = defaultdict(set)
        self.target_counts = Counter(t.node_id for t in ai.targets) if ai else Counter()
        for selected_manifest in self.manifests.values():
            self.contexts_by_target[selected_manifest.target_node_id].add(
                selected_manifest.context_fingerprint
            )
            for owner in self.aligner.ancestors(selected_manifest.target_node_id):
                self.contexts_by_target[owner].add(selected_manifest.context_fingerprint)
        self.graph_by_node: dict[NodeId, set[UUID]] = defaultdict(set)
        self.ai_by_node: dict[NodeId, set[UUID]] = defaultdict(set)
        self.neighbors: dict[NodeId, set[NodeId]] = defaultdict(set)
        self.owner: dict[NodeId, NodeId] = {}
        self.anchors: list[tuple[HybridCase, StaticProof | None]] = []
        if discovery:
            modules = {m.id: m for m in discovery.discovered.module_candidates}
            for component in discovery.discovered.components:
                module = modules.get(component.module_id) if component.module_id else None
                self.discovery_signals[component.iam_node_id] = DiscoverySignal(
                    subject_id=component.iam_node_id,
                    role_hypothesis_id=component.role.id,
                    role=component.role.role,
                    role_strength=component.role.strength,
                    candidate_roles=component.role.candidate_roles,
                    conflicting_roles=component.role.conflicting_roles,
                    layer_hypothesis_id=component.layer.id,
                    layer=component.layer.label,
                    layer_strength=component.layer.strength,
                    module_id=component.module_id,
                    module_strength=module.strength if module else None,
                )
        if graph:
            representatives = (
                {c.id: c.iam_node_id for c in discovery.discovered.components} if discovery else {}
            )
            for node in graph.graph.nodes:
                subjects = [
                    self.aligner.nodes[s] for s in node.iam_node_ids if s in self.aligner.nodes
                ]
                subject = representatives.get(node.id)
                if subject is None and subjects:
                    subject = min(
                        subjects,
                        key=lambda n: (
                            n.kind in {NodeKind.FILE, NodeKind.METHOD, NodeKind.FIELD},
                            str(n.id),
                        ),
                    ).id
                if subject is not None:
                    self.owner[NodeId(node.id)] = subject
            for edge in graph.graph.edges:
                for dependency_proof in edge.proofs:
                    self.check_edge(dependency_proof.model_dump(mode="json"))
                left, right = (
                    self.owner.get(NodeId(edge.source_id)),
                    self.owner.get(NodeId(edge.target_id)),
                )
                if left is not None and right is not None:
                    self.neighbors[left].add(right)
                    self.neighbors[right].add(left)
                    self.aligner.dependencies.add((left, right))
            membership = {member: scc for scc in graph.sccs for member in scc.members}
            cycles = {cycle.scc_id: cycle for cycle in graph.cycles}
            for metric in graph.metrics:
                subject = self.owner.get(NodeId(metric.node_id))
                if subject is not None:
                    scc = membership.get(metric.node_id)
                    cycle = cycles.get(scc.id) if scc else None
                    self.measurements[subject] = GraphMeasurement(
                        subject_id=subject,
                        metrics=metric,
                        provenance_ref=f"graph-metric:{metric.node_id}:{graph.reproducibility.configuration_fingerprint}",
                        scc_id=scc.id if scc else None,
                        scc_member_ids=tuple(
                            sorted(
                                {
                                    self.owner[NodeId(n)]
                                    for n in scc.members
                                    if NodeId(n) in self.owner
                                },
                                key=str,
                            )
                        )
                        if scc
                        else (),
                        cycle_edge_ids=cycle.edge_ids if cycle else (),
                    )
            graph_edges = {e.id: e for e in graph.graph.edges}
            for candidate in graph.candidates:
                pairs: tuple[SubjectPair, ...] = ()
                if candidate.subject_node_id is not None:
                    subject = self.owner.get(NodeId(candidate.subject_node_id))
                    subjects_tuple: tuple[NodeId, ...] = (subject,) if subject else ()
                elif candidate.subject_edge_id in graph_edges:
                    edge = graph_edges[candidate.subject_edge_id]
                    pairs = ordered_pairs(
                        [
                            SubjectPair(source_id=p.source_node_id, target_id=p.target_node_id)
                            for p in edge.proofs
                        ]
                    )
                    subjects_tuple = tuple(
                        sorted({n for p in pairs for n in (p.source_id, p.target_id)}, key=str)
                    )
                else:
                    subjects_tuple = ()
                if not subjects_tuple:
                    raise HybridInputError("graph candidate requires a resolvable IAM subject")
                signal = GraphSignal(
                    candidate_id=candidate.candidate_id,
                    rule_id=candidate.rule_id,
                    subject_ids=subjects_tuple,
                    pairs=pairs,
                    projection=candidate.projection.value,
                    metrics=numeric_observations(dict(candidate.metrics)),
                    thresholds=numeric_observations(dict(candidate.thresholds)),
                    engine_version=graph.reproducibility.graph_engine_version,
                    configuration_fingerprint=graph.reproducibility.configuration_fingerprint,
                )
                self.graph_signals[signal.candidate_id] = signal
                for subject in signal.subject_ids:
                    self.graph_by_node[subject].add(signal.candidate_id)
                self.anchors.append(
                    (
                        self.case(
                            HybridCaseType.GRAPH_STRUCTURAL,
                            subjects_tuple,
                            pairs,
                            "GRAPH",
                            signal.rule_id,
                            signal.candidate_id,
                            signal.projection,
                        ),
                        None,
                    )
                )
        findings = (
            tuple(static.findings if static else ())
            + tuple(graph.findings if graph else ())
            + tuple(graph_conformance.findings if graph_conformance else ())
        )
        seen: dict[UUID, Finding] = {}
        for finding in findings:
            if finding.id in seen:
                if seen[finding.id] != finding:
                    raise HybridInputError("duplicate Finding ID has conflicting proof")
                continue
            seen[finding.id] = finding
            proof = self.proof(finding)
            subjects_tuple = tuple(
                sorted({n for p in proof.pairs for n in (p.source_id, p.target_id)}, key=str)
            )
            self.anchors.append(
                (
                    self.case(
                        HybridCaseType.DETERMINISTIC_CONFORMANCE,
                        subjects_tuple,
                        proof.pairs,
                        "GRAPH_CONFORMANCE" if finding.rule_id == "ARCH003" else "STATIC",
                        finding.rule_id,
                        finding.id,
                        str(finding.metadata.get("projection", "iam-dependency")),
                    ),
                    proof,
                )
            )
        if ai:
            target_keys = {(t.node_id, t.candidate_rule_id) for t in ai.targets}
            invocation_by_target = {
                (i.target.node_id, i.target.candidate_rule_id): i
                for i in ai.invocations
                if i.diagnostic is None
            }
            completed: set[tuple[NodeId, str]] = set()
            for semantic_candidate in ai.candidates:
                manifest = self.manifests.get(semantic_candidate.context_fingerprint)
                if manifest is None:
                    raise HybridInputError(
                        "semantic candidate requires its source-free context manifest"
                    )
                assessment = semantic_candidate.assessment
                if (
                    (manifest.target_node_id, assessment.candidate_rule_id) not in target_keys
                    or semantic_candidate.strategy != manifest.configuration.strategy
                ):
                    raise HybridInputError(
                        "semantic candidate must match a requested target and context strategy"
                    )
                refs = {r.evidence_id for r in manifest.fragments} | {
                    r.evidence_id for r in manifest.evidence
                }
                selected_subjects = {s.node_id for s in manifest.selected_nodes}
                if (
                    not set(assessment.subject_node_ids) <= selected_subjects
                    or not set(assessment.evidence_refs) <= refs
                    or manifest.target_node_id not in assessment.subject_node_ids
                ):
                    raise HybridInputError(
                        "semantic subjects and references must match their selected context"
                    )
                pairs_list: list[SubjectPair] = []
                for evidence in manifest.evidence:
                    if (
                        evidence.kind == "DEPENDENCY"
                        and evidence.evidence_id in assessment.evidence_refs
                    ):
                        proofs = evidence.data.get("proofs")
                        if isinstance(proofs, list):
                            for record in proofs:
                                if isinstance(record, dict):
                                    self.check_edge(record)
                                    pairs_list.append(
                                        SubjectPair(
                                            source_id=NodeId(UUID(str(record["source_node_id"]))),
                                            target_id=NodeId(UUID(str(record["target_node_id"]))),
                                        )
                                    )
                invocation = invocation_by_target.get(
                    (manifest.target_node_id, assessment.candidate_rule_id)
                )
                if invocation and (
                    invocation.provider_id != semantic_candidate.provider_id
                    or invocation.model_id != semantic_candidate.model_id
                ):
                    raise HybridInputError(
                        "semantic usage must match the actual candidate provider and model"
                    )
                usage = invocation.usage if invocation else None
                signal_ai = SemanticSignal(
                    candidate_id=semantic_candidate.candidate_id,
                    rule_id=assessment.candidate_rule_id,
                    decision=assessment.decision,
                    subject_ids=tuple(sorted(assessment.subject_node_ids, key=str)),
                    pairs=ordered_pairs(pairs_list),
                    evidence_refs=tuple(sorted(assessment.evidence_refs)),
                    context_fingerprint=semantic_candidate.context_fingerprint,
                    strategy=semantic_candidate.strategy,
                    provider_id=semantic_candidate.provider_id,
                    model_id=semantic_candidate.model_id,
                    prompt_version=semantic_candidate.prompt_version,
                    schema_version=semantic_candidate.schema_version,
                    usage=usage,
                    usage_available=usage is not None
                    and any(v is not None for v in usage.model_dump().values()),
                )
                self.semantic_signals[signal_ai.candidate_id] = signal_ai
                for subject in signal_ai.subject_ids:
                    self.ai_by_node[subject].add(signal_ai.candidate_id)
                    for owner in self.aligner.ancestors(subject):
                        self.ai_by_node[owner].add(signal_ai.candidate_id)
                completed.add((manifest.target_node_id, signal_ai.rule_id))
                self.anchors.append(
                    (
                        self.case(
                            HybridCaseType.SEMANTIC,
                            signal_ai.subject_ids,
                            signal_ai.pairs,
                            "AI",
                            signal_ai.rule_id,
                            signal_ai.candidate_id,
                            "semantic-assessment",
                        ),
                        None,
                    )
                )
            for target in ai.targets:
                if (target.node_id, target.candidate_rule_id) not in completed:
                    anchor = uuid5(
                        iam.project.id,
                        f"requested-semantic-target-v1:{target.node_id}:{target.candidate_rule_id}",
                    )
                    self.anchors.append(
                        (
                            self.case(
                                HybridCaseType.SEMANTIC,
                                (target.node_id,),
                                (),
                                "CALLER",
                                target.candidate_rule_id,
                                anchor,
                                "requested-semantic-target",
                            ),
                            None,
                        )
                    )
        order = {
            HybridCaseType.DETERMINISTIC_CONFORMANCE: 0,
            HybridCaseType.GRAPH_STRUCTURAL: 1,
            HybridCaseType.SEMANTIC: 2,
            HybridCaseType.COMPOSITE: 3,
        }
        self.anchors.sort(
            key=lambda item: (order[item[0].case_type], item[0].rule_id, str(item[0].case_id))
        )

    def case(
        self,
        kind: HybridCaseType,
        subjects: tuple[NodeId, ...],
        pairs: tuple[SubjectPair, ...],
        origin: LiteralOrigin,
        rule: str,
        anchor: UUID,
        scope: str,
    ) -> HybridCase:
        identity = ":".join(
            [
                "hybrid-case-v1",
                kind.value,
                origin,
                rule,
                str(anchor),
                scope,
                *sorted(map(str, subjects)),
            ]
        )
        case_id = uuid5(self.iam.project.id, identity)
        return HybridCase(
            case_id=case_id,
            case_type=kind,
            primary_subject_ids=subjects,
            subject_pairs=pairs,
            origin=origin,
            rule_id=rule,
            anchor_ids=(anchor,),
            scope=scope,
            bundle_id=uuid5(case_id, "evidence-bundle-v1"),
        )

    def check_edge(self, record: Mapping[str, object]) -> None:
        try:
            edge_id = EdgeId(UUID(str(record.get("iam_edge_id", record.get("edge_id")))))
        except ValueError:
            raise HybridInputError("proof requires a valid IAM edge identifier") from None
        edge = self.edges.get(edge_id)
        if (
            edge is None
            or str(edge.source_id) != record.get("source_node_id")
            or str(edge.target_id) != record.get("target_node_id")
            or edge.kind.value != record.get("relation")
        ):
            raise HybridInputError("proof must match an actual directed IAM relation")

    def proof(self, finding: Finding) -> StaticProof:
        if (
            finding.namespace != FindingNamespace.ARCH
            or finding.metadata.get("deterministic") is not True
        ):
            raise HybridInputError(
                "only confirmed ARCH deterministic findings may seed proof cases"
            )
        pairs: list[SubjectPair] = []
        edge_ids: list[EdgeId] = []
        relations: set[str] = set()
        occurrences = truncated = 0
        spec_hash = None
        for evidence in finding.evidence:
            if evidence.type == EvidenceType.ARCHITECTURE_RULE:
                spec_hash = evidence.properties.get("spec_fingerprint")
            records: list[dict[str, object]] = []
            if evidence.type == EvidenceType.STATIC_RULE:
                records.append(dict(evidence.properties))
            elif evidence.type == EvidenceType.GRAPH_PATH:
                serialized = evidence.properties.get("edges")
                if isinstance(serialized, list):
                    path = tuple(GraphEdge.model_validate(item) for item in serialized)
                    if (
                        not path
                        or path[0].source_id != path[-1].target_id
                        or any(
                            left.target_id != right.source_id
                            for left, right in zip(path, path[1:], strict=False)
                        )
                    ):
                        raise HybridInputError(
                            "ARCH003 proof must contain a closed directed graph path"
                        )
                    for item in serialized:
                        edge = GraphEdge.model_validate(item)
                        records.extend(dict(p.model_dump(mode="json")) for p in edge.proofs)
            for record in records:
                self.check_edge(record)
                pairs.append(
                    SubjectPair(
                        source_id=NodeId(UUID(str(record["source_node_id"]))),
                        target_id=NodeId(UUID(str(record["target_node_id"]))),
                    )
                )
                edge_ids.append(EdgeId(UUID(str(record.get("iam_edge_id", record.get("edge_id"))))))
                relations.add(str(record["relation"]))
                count, missing = record.get("occurrences"), record.get("provenance_truncated")
                occurrences += count if type(count) is int else 0
                truncated += missing if type(missing) is int else 0
        if not isinstance(spec_hash, str):
            raise HybridInputError("deterministic finding requires target specification provenance")
        expected_hash = (
            self.static.reproducibility.architecture_spec_fingerprint if self.static else None
        )
        if finding.rule_id == "ARCH003" and self.graph_conformance:
            recorded_hash = self.graph_conformance.reproducibility.get("spec_fingerprint")
            expected_hash = recorded_hash if isinstance(recorded_hash, str) else None
        if expected_hash is not None and spec_hash != expected_hash:
            raise HybridInputError("finding proof must match the target specification fingerprint")
        if finding.rule_id == "ARCH003" and (
            finding.trace is None
            or finding.trace.steps[0].node_id != finding.trace.steps[-1].node_id
        ):
            raise HybridInputError("ARCH003 proof requires a closed directed trace")
        return StaticProof(
            finding_id=finding.id,
            rule_id=cast(
                Literal["ARCH001", "ARCH002", "ARCH003", "ARCH004", "ARCH005"], finding.rule_id
            ),
            detector_source=finding.detector.source,
            detector_name=finding.detector.name,
            detector_version=finding.detector.version,
            severity=finding.severity,
            pairs=ordered_pairs(pairs),
            edge_ids=tuple(sorted(set(edge_ids), key=str)),
            relation_kinds=tuple(sorted(relations)),
            evidence_ids=tuple(sorted({e.id for e in finding.evidence}, key=str)),
            locations=tuple(
                location
                for location in (finding.primary_location, *finding.related_locations)
                if location is not None
            ),
            provenance_count=occurrences,
            provenance_truncated=truncated,
            spec_fingerprint=spec_hash,
        )

    def related_ids(self, case: HybridCase) -> set[NodeId]:
        subjects = set(case.primary_subject_ids)
        for subject in case.primary_subject_ids:
            subjects.update(self.aligner.ancestors(subject))
            if not case.subject_pairs:
                subjects.update(self.neighbors[subject])
        return subjects

    def assemble(self, case: HybridCase, proof: StaticProof | None) -> HybridEvidenceBundle:
        subjects = self.related_ids(case)
        graph_ids = {ref for node in subjects for ref in self.graph_by_node[node]}
        ai_ids = {ref for node in subjects for ref in self.ai_by_node[node]}
        selected_graph: list[GraphSignal] = []
        selected_ai: list[SemanticSignal] = []
        alignments: list[EvidenceAlignment] = []
        for ref in sorted(graph_ids, key=str):
            signal = self.graph_signals[ref]
            method = self.aligner.match(
                case, signal.subject_ids, signal.pairs, ref in case.anchor_ids
            )
            if method is not None:
                selected_graph.append(signal)
                alignments.append(
                    EvidenceAlignment(
                        target_case_id=case.case_id,
                        source_refs=(f"graph:{ref}",),
                        method=method,
                        agreement=EvidenceAgreement.NEUTRAL,
                        reason_code="STRUCTURAL_CONTEXT",
                    )
                )
        for ref in sorted(ai_ids, key=str):
            semantic = self.semantic_signals[ref]
            method = self.aligner.match(
                case, semantic.subject_ids, semantic.pairs, ref in case.anchor_ids
            )
            if method is None:
                continue
            selected_ai.append(semantic)
            agreement = EvidenceAgreement.NEUTRAL
            reason = "ALIGNED_IDENTITY_DIFFERENT_CONCERN"
            graph_rule = case.rule_id if case.origin == "GRAPH" else None
            if graph_rule:
                agreement = concern_agreement(
                    graph_rule, semantic.rule_id, semantic.decision, method
                )
                reason = (
                    "MAPPED_GRAPH_SEMANTIC_CONCERN"
                    if agreement != EvidenceAgreement.NEUTRAL
                    else reason
                )
            elif case.origin == "AI":
                agreement = (
                    EvidenceAgreement.MISSING
                    if semantic.decision == SemanticDecision.INSUFFICIENT_CONTEXT
                    else EvidenceAgreement.NEUTRAL
                )
            elif (
                proof
                and method == AlignmentMethod.EXACT_SUBJECT_PAIR
                and semantic.rule_id == "ARCH205"
                and proof.rule_id in {"ARCH001", "ARCH002", "ARCH004", "ARCH005"}
            ):
                manifest = self.manifests[semantic.context_fingerprint]
                linked = any(
                    e.kind == "TARGET_CONSTRAINT"
                    and e.evidence_id in semantic.evidence_refs
                    and isinstance(constraint := e.data.get("constraint"), dict)
                    and constraint.get("id") == proof.rule_id
                    for e in manifest.evidence
                )
                if linked:
                    agreement = (
                        EvidenceAgreement.MISSING
                        if semantic.decision == SemanticDecision.INSUFFICIENT_CONTEXT
                        else EvidenceAgreement.SUPPORTING
                        if semantic.decision == SemanticDecision.SUPPORTED
                        else EvidenceAgreement.CONTRADICTING
                    )
                    reason = "EXPLICIT_TARGET_PAIR_CONTEXT_CONCERN"
            alignments.append(
                EvidenceAlignment(
                    target_case_id=case.case_id,
                    source_refs=(f"ai:{ref}",),
                    method=method,
                    agreement=agreement,
                    reason_code=reason,
                )
            )
        if case.origin == "AI":
            anchor_ai = next((s for s in selected_ai if s.candidate_id in case.anchor_ids), None)
            if anchor_ai:
                for signal in selected_graph:
                    method = self.aligner.match(case, signal.subject_ids, signal.pairs)
                    alignments.append(
                        EvidenceAlignment(
                            target_case_id=case.case_id,
                            source_refs=(
                                f"graph:{signal.candidate_id}",
                                f"ai:{anchor_ai.candidate_id}",
                            ),
                            method=method,
                            agreement=concern_agreement(
                                signal.rule_id, anchor_ai.rule_id, anchor_ai.decision, method
                            ),
                            reason_code="MAPPED_GRAPH_SEMANTIC_CONCERN",
                        )
                    )
        if proof:
            alignments.insert(
                0,
                EvidenceAlignment(
                    target_case_id=case.case_id,
                    source_refs=(f"finding:{proof.finding_id}",),
                    method=AlignmentMethod.EXPLICIT_CANDIDATE_LINK,
                    agreement=EvidenceAgreement.SUPPORTING,
                    reason_code="DETERMINISTIC_PROOF",
                ),
            )
        for channel, present in (("ai", selected_ai), ("graph", selected_graph)):
            if not present:
                name = "graph_candidate" if channel == "graph" and self.graph else channel
                alignments.append(
                    EvidenceAlignment(
                        target_case_id=case.case_id,
                        source_refs=(f"missing:{name}",),
                        method=None,
                        agreement=EvidenceAgreement.MISSING,
                        reason_code=f"MISSING_{name.upper()}_EVIDENCE",
                    )
                )
        local_subjects = set(case.primary_subject_ids)
        local_subjects.update(
            owner for node in case.primary_subject_ids for owner in self.aligner.ancestors(node)
        )
        discovery = tuple(
            self.discovery_signals[n]
            for n in sorted(local_subjects, key=str)
            if n in self.discovery_signals
        )
        if not discovery:
            alignments.append(
                EvidenceAlignment(
                    target_case_id=case.case_id,
                    source_refs=("missing:discovery",),
                    method=None,
                    agreement=EvidenceAgreement.MISSING,
                    reason_code="MISSING_DISCOVERY_EVIDENCE",
                )
            )
        for signal_discovery in discovery:
            method = self.aligner.match(case, (signal_discovery.subject_id,))
            alignments.append(
                EvidenceAlignment(
                    target_case_id=case.case_id,
                    source_refs=(
                        f"discovery:{signal_discovery.role_hypothesis_id}",
                        f"discovery:{signal_discovery.layer_hypothesis_id}",
                    ),
                    method=method,
                    agreement=EvidenceAgreement.NEUTRAL,
                    reason_code=f"DISCOVERY_ROLE_LAYER_CONTEXT_{case.rule_id}",
                )
            )
        measurements = tuple(
            self.measurements[n] for n in sorted(local_subjects, key=str) if n in self.measurements
        )
        alignments.extend(
            EvidenceAlignment(
                target_case_id=case.case_id,
                source_refs=(m.provenance_ref,),
                method=self.aligner.match(case, (m.subject_id,)),
                agreement=EvidenceAgreement.NEUTRAL,
                reason_code="GRAPH_MEASUREMENT_CONTEXT",
            )
            for m in measurements
        )
        relevant_manifests = {s.context_fingerprint for s in selected_ai}
        if self.ai:
            relevant_manifests.update(
                h for node in case.primary_subject_ids for h in self.contexts_by_target[node]
            )
        contexts = tuple(
            self.context_summary(self.manifests[h]) for h in sorted(relevant_manifests)
        )
        return HybridEvidenceBundle(
            bundle_id=case.bundle_id,
            static=(proof,) if proof else (),
            graph=tuple(selected_graph),
            graph_measurements=measurements,
            ai=tuple(selected_ai),
            discovery=discovery,
            context=contexts,
            completeness=self.completeness(case, selected_ai, contexts),
            alignments=tuple(alignments),
        )

    @staticmethod
    def context_summary(manifest: ContextManifest) -> ContextSummary:
        references = [
            ContextReference(
                evidence_id=f.evidence_id,
                kind="SOURCE_REFERENCE",
                subject_ids=tuple(sorted(f.node_ids, key=str)),
                relative_path=f.relative_path,
                start_line=f.start_line,
                end_line=f.end_line,
                content_hash=f.content_hash,
            )
            for f in manifest.fragments
        ]
        references.extend(
            ContextReference(
                evidence_id=e.evidence_id,
                kind=e.kind,
                subject_ids=tuple(sorted(e.subject_node_ids, key=str)),
            )
            for e in manifest.evidence
        )
        return ContextSummary(
            context_fingerprint=manifest.context_fingerprint,
            target_id=manifest.target_node_id,
            strategy=manifest.configuration.strategy,
            selected_subject_ids=tuple(
                sorted((n.node_id for n in manifest.selected_nodes), key=str)
            ),
            references=tuple(sorted(references, key=lambda r: r.evidence_id)),
            truncated=manifest.truncated,
            dropped_nodes=manifest.dropped_nodes,
            dropped_files=manifest.dropped_files,
            dropped_fragments=manifest.dropped_fragments,
            dropped_evidence=manifest.dropped_evidence,
        )

    def completeness(
        self, case: HybridCase, signals: list[SemanticSignal], contexts: tuple[ContextSummary, ...]
    ) -> EvidenceCompleteness:
        raw = self.iam.metadata.get("statistics")
        statistics = raw if isinstance(raw, dict) else {}

        def count(name: str) -> int | None:
            value = statistics.get(name)
            return value if type(value) is int and value >= 0 else None

        parse_errors = count("files_with_parse_errors")
        local_targets = set(case.primary_subject_ids) | {context.target_id for context in contexts}
        requested = sum(self.target_counts[n] for n in local_targets) if self.ai else None
        completed = len({(s.context_fingerprint, s.rule_id) for s in signals}) if self.ai else None
        return EvidenceCompleteness(
            iam_complete=cast(bool, self.iam.metadata["is_complete"])
            if type(self.iam.metadata.get("is_complete")) is bool
            else None,
            parse_errors_present=parse_errors > 0 if parse_errors is not None else None,
            unresolved_references=count("references_unresolved"),
            ambiguous_references=count("references_ambiguous"),
            graph_complete=self.graph.is_complete if self.graph else None,
            metrics_skipped=self.graph.statistics.metrics_skipped if self.graph else None,
            discovery_complete=self.discovery.is_complete if self.discovery else None,
            discovery_unknown=self.discovery.statistics.role_unknown if self.discovery else None,
            discovery_ambiguous=self.discovery.statistics.role_ambiguous
            if self.discovery
            else None,
            ai_requested=requested,
            ai_completed=completed,
            ai_partial=(completed < requested)
            if completed is not None and requested is not None
            else None,
            ai_insufficient=sum(
                s.decision == SemanticDecision.INSUFFICIENT_CONTEXT for s in signals
            )
            if self.ai
            else None,
            context_truncated=any(c.truncated for c in contexts) if contexts else None,
        )
