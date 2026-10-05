from collections import Counter

from pydantic import Field

from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.conformance.models import StaticConformanceResult
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.conformance import GraphConformanceResult
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.hybrid.assembler import HybridEvidenceAssembler, HybridInputError
from archguard.architecture.hybrid.contracts import ArchitectureDecision, ArchitectureEvidenceBundle
from archguard.architecture.hybrid.features import VERSION, extract_features, feature_schema
from archguard.architecture.hybrid.models import (
    EvidenceAgreement,
    HybridAnalysisResult,
    HybridCaseType,
    HybridDecisionState,
    HybridReproducibility,
    HybridStatistics,
)
from archguard.architecture.hybrid.policies import (
    DeterministicPrecedencePolicy,
    HybridDecisionPolicy,
    HybridPolicyError,
)
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.architecture.intelligence.models import AIAnalysisConfig, AIAnalysisResult
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.core.findings.enums import DetectorSource, FindingNamespace
from archguard.core.model.base import DomainModel
from archguard.iam.model import ArchitectureModel


class HybridAnalysisConfig(DomainModel):
    ai: AIAnalysisConfig = Field(default_factory=AIAnalysisConfig)
    max_candidate_cases: int = Field(default=1000, strict=True, gt=0, le=100000)


class HybridAnalyzer:
    def __init__(self, policy: HybridDecisionPolicy | None = None) -> None:
        self.policy = policy or DeterministicPrecedencePolicy()

    def decide(
        self, model: ArchitectureModel, evidence: ArchitectureEvidenceBundle, /
    ) -> ArchitectureDecision:
        """Backward compatible batch boundary: preserve existing Finding objects, never rescore."""
        ArchitectureModel.model_validate(model)
        evidence = ArchitectureEvidenceBundle.model_validate(evidence)
        return ArchitectureDecision(
            analysis_id=evidence.analysis_id, findings=evidence.deterministic_findings
        )

    def analyze(
        self,
        iam: ArchitectureModel,
        static: StaticConformanceResult | None = None,
        graph: GraphAnalysisResult | None = None,
        discovery: ArchitectureDiscoveryResult | None = None,
        ai: AIAnalysisResult | None = None,
        spec: ArchitectureSpecification | None = None,
        graph_conformance: GraphConformanceResult | None = None,
        config: HybridAnalysisConfig | None = None,
    ) -> HybridAnalysisResult:
        iam = ArchitectureModel.model_validate(iam)
        config = HybridAnalysisConfig.model_validate(config or HybridAnalysisConfig())
        if self.policy.metadata.feature_schema_version != VERSION:
            raise HybridPolicyError("policy requires a compatible feature schema")
        iam_hash = iam_fingerprint(iam)
        spec_hash = spec.fingerprint if spec else None
        if static:
            static = StaticConformanceResult.model_validate(static)
            if (
                static.reproducibility.iam_fingerprint != iam_hash
                or static.reproducibility.project_id != iam.project.id
                or static.reproducibility.architecture_spec_fingerprint != spec_hash
            ):
                raise HybridInputError(
                    "static result must match the same IAM and target specification"
                )
        if graph:
            graph = GraphAnalysisResult.model_validate(graph)
            if graph.graph.projection.projection != GraphProjection.COMPONENT:
                raise HybridInputError(
                    "Hybrid candidate alignment requires an actual component graph"
                )
            if (
                graph.reproducibility.iam_fingerprint != iam_hash
                or graph.graph.project_id != iam.project.id
            ):
                raise HybridInputError("graph result must match the same IAM")
            if graph.reproducibility.architecture_spec_fingerprint not in {None, spec_hash}:
                raise HybridInputError("graph result must match the target specification")
        if discovery:
            discovery = ArchitectureDiscoveryResult.model_validate(discovery)
            if (
                graph is None
                or discovery.reproducibility.iam_fingerprint != iam_hash
                or discovery.graph.reproducibility.configuration_fingerprint
                != graph.reproducibility.configuration_fingerprint
                or discovery.graph.reproducibility.projection_fingerprint
                != graph.reproducibility.projection_fingerprint
            ):
                raise HybridInputError("discovery must match the same IAM and actual graph")
        conformance = graph_conformance or (graph.conformance if graph else None)
        if conformance:
            conformance = GraphConformanceResult.model_validate(conformance)
            if any(
                f.rule_id != "ARCH003"
                or f.detector.source != DetectorSource.GRAPH
                or f.namespace != FindingNamespace.ARCH
                for f in conformance.findings
            ):
                raise HybridInputError("graph conformance must supply only GRAPH ARCH003 proof")
            if conformance.findings and (
                spec is None
                or not conformance.rule_enabled
                or not conformance.is_valid
                or conformance.graph is None
                or conformance.graph.project_id != iam.project.id
                or conformance.reproducibility.get("spec_fingerprint") != spec_hash
                or conformance.reproducibility.get("iam_fingerprint") != iam_hash
            ):
                raise HybridInputError("ARCH003 requires valid enabled explicit target conformance")
        if spec:
            enabled = {rule.id: rule for rule in spec.rules if rule.enabled}
            for finding in static.findings if static else ():
                if (
                    finding.rule_id not in enabled
                    or finding.severity != enabled[finding.rule_id].severity
                ):
                    raise HybridInputError(
                        "deterministic finding must retain its enabled target rule severity"
                    )
            for finding in conformance.findings if conformance else ():
                if "ARCH003" not in enabled or finding.severity != enabled["ARCH003"].severity:
                    raise HybridInputError(
                        "ARCH003 requires its enabled rule and original severity"
                    )
        if ai:
            ai = AIAnalysisResult.model_validate(ai)
            if ai.candidates and ai.status not in {"COMPLETE", "PARTIAL"}:
                raise HybridInputError(
                    "only completed or partial AI analysis may supply candidates"
                )
            known = {n.id for n in iam.nodes}
            if (
                len({c.candidate_id for c in ai.candidates}) != len(ai.candidates)
                or any(t.node_id not in known for t in ai.targets)
                or any(not {n.node_id for n in m.selected_nodes} <= known for m in ai.manifests)
            ):
                raise HybridInputError("AI targets and selected context must refer to the same IAM")
        assembler = HybridEvidenceAssembler(iam, static, graph, discovery, ai, graph_conformance)
        selected = []
        candidates = omitted = 0
        for anchor in assembler.anchors:
            if anchor[0].case_type != HybridCaseType.DETERMINISTIC_CONFORMANCE:
                if candidates >= config.max_candidate_cases:
                    omitted += 1
                    continue
                candidates += 1
            selected.append(anchor)
        cases = tuple(case for case, _ in selected)
        bundles = tuple(assembler.assemble(case, proof) for case, proof in selected)
        cases = tuple(
            case.model_copy(
                update={
                    "related_subject_ids": tuple(
                        sorted(
                            (
                                {n for signal in bundle.graph for n in signal.subject_ids}
                                | {n for semantic in bundle.ai for n in semantic.subject_ids}
                                | {
                                    n
                                    for context in bundle.context
                                    for n in context.selected_subject_ids
                                }
                                | {d.subject_id for d in bundle.discovery}
                            )
                            - set(case.primary_subject_ids),
                            key=str,
                        )
                    )
                }
            )
            for case, bundle in zip(cases, bundles, strict=True)
        )
        features = tuple(
            extract_features(case, bundle) for case, bundle in zip(cases, bundles, strict=True)
        )
        decisions = tuple(
            self.policy.decide(case, bundle, vector)
            for case, bundle, vector in zip(cases, bundles, features, strict=True)
        )
        for bundle, vector, decision in zip(bundles, features, decisions, strict=True):
            if (
                decision.policy != self.policy.metadata
                or decision.feature_fingerprint != vector.fingerprint
                or decision.evidence_fingerprint != fingerprint(bundle)
            ):
                raise HybridPolicyError(
                    "policy output must refer to its actual metadata and features"
                )
            if not bundle.static and decision.state == HybridDecisionState.CONFIRMED_DETERMINISTIC:
                raise HybridPolicyError("only deterministic proof can confirm a Finding")
            if bundle.static and (
                decision.state != HybridDecisionState.CONFIRMED_DETERMINISTIC
                or decision.confirmed_finding_ids != (bundle.static[0].finding_id,)
                or decision.severity != bundle.static[0].severity
            ):
                raise HybridPolicyError(
                    "policy cannot suppress deterministic proof or change severity"
                )
        diagnostics = set()
        for channel, result in (
            ("STATIC", static),
            ("GRAPH", graph),
            ("DISCOVERY", discovery),
            ("GRAPH_CONFORMANCE", conformance),
        ):
            if result is not None and not result.is_valid:
                diagnostics.add("INVALID")
                diagnostics.add(f"INVALID_{channel}_ANALYSIS")
            elif result is not None and not result.is_complete:
                diagnostics.add(f"PARTIAL_{channel}_ANALYSIS")
        if omitted:
            diagnostics.add("CANDIDATE_CASE_BUDGET_TRUNCATED")
        if iam.metadata.get("is_complete") is False:
            diagnostics.add("PARTIAL_SOURCE_MODEL")
        if ai and ai.status not in {"COMPLETE", "DRY_RUN"}:
            diagnostics.add(f"AI_{ai.status}")
        return HybridAnalysisResult(
            cases=cases,
            evidence_bundles=bundles,
            feature_schema=feature_schema(),
            features=features,
            decisions=decisions,
            confirmed_finding_ids=tuple(
                sorted({f for d in decisions for f in d.confirmed_finding_ids}, key=str)
            ),
            review_case_ids=tuple(
                d.case_id for d in decisions if d.state == HybridDecisionState.REVIEW_REQUIRED
            ),
            diagnostics=tuple(sorted(diagnostics)),
            statistics=HybridStatistics(
                cases_by_type=dict(Counter(c.case_type.value for c in cases)),
                decisions_by_state=dict(Counter(d.state.value for d in decisions)),
                channel_cases={
                    name: sum(
                        bool(getattr(b, name)) or (name == "graph" and bool(b.graph_measurements))
                        for b in bundles
                    )
                    for name in ("static", "graph", "ai", "discovery", "context")
                },
                ai_decisions=dict(
                    Counter(s.decision.value for s in assembler.semantic_signals.values())
                ),
                agreements=sum(
                    a.agreement == EvidenceAgreement.SUPPORTING
                    for b in bundles
                    for a in b.alignments
                ),
                conflicts=sum(
                    a.agreement == EvidenceAgreement.CONTRADICTING
                    for b in bundles
                    for a in b.alignments
                ),
                missing=sum(
                    a.agreement == EvidenceAgreement.MISSING for b in bundles for a in b.alignments
                ),
                omitted_candidate_cases=omitted,
            ),
            reproducibility=HybridReproducibility(
                max_candidate_cases=config.max_candidate_cases,
                iam_fingerprint=iam_hash,
                iam_schema_version=iam.iam_schema_version,
                snapshot_fingerprint=str(iam.metadata["snapshot_fingerprint"])
                if iam.metadata.get("snapshot_fingerprint")
                else None,
                static_engine_version=static.reproducibility.analyzer_version if static else None,
                spec_fingerprint=spec_hash,
                graph_engine_version=graph.reproducibility.graph_engine_version if graph else None,
                graph_configuration_fingerprint=graph.reproducibility.configuration_fingerprint
                if graph
                else None,
                graph_projection_fingerprint=graph.reproducibility.projection_fingerprint
                if graph
                else None,
                discovery_engine_version=discovery.reproducibility.discovery_engine_version
                if discovery
                else None,
                discovery_configuration_fingerprint=discovery.reproducibility.configuration_fingerprint
                if discovery
                else None,
                ai_inputs=tuple(
                    assembler.semantic_signals[s]
                    for s in sorted(assembler.semantic_signals, key=str)
                ),
                feature_schema_version=VERSION,
                policy=self.policy.metadata,
            ),
        )
