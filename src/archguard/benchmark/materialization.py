"""Label-free experiment anchors; never produce detector findings or decisions."""

from enum import StrEnum
from uuid import uuid5

from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.conformance.models import StaticConformanceResult
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.conformance import GraphConformanceResult
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.hybrid.assembler import HybridEvidenceAssembler
from archguard.architecture.hybrid.features import extract_features, feature_schema
from archguard.architecture.hybrid.models import (
    FeatureAvailability,
    FeatureValueType,
    HybridCase,
    HybridCaseType,
    HybridEvidenceBundle,
    HybridFeature,
    HybridFeatureDefinition,
    HybridFeatureSchema,
    HybridFeatureVector,
    SubjectPair,
)
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.architecture.intelligence.models import AIAnalysisResult
from archguard.benchmark.identity import resolved_key, subject_key
from archguard.benchmark.models import RuleId, Subjects, rule_family
from archguard.benchmark.resolver import LocatorResolver
from archguard.core.identifiers import NodeId
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel

VERSION = "calibration-evidence-v1"


class CohortVariant(StrEnum):
    STRUCTURAL = "STRUCTURAL"
    WITHOUT_STATIC = "WITHOUT_STATIC"
    WITHOUT_GRAPH = "WITHOUT_GRAPH"
    BOUNDED_METRICS = "BOUNDED_METRICS"


class AISource(StrEnum):
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    SCRIPTED_TEST = "SCRIPTED_TEST"
    REAL_PROVIDER = "REAL_PROVIDER"


class EvaluationAnchor(DomainModel):
    repository_id: str
    rule_id: RuleId
    subjects: Subjects


class MaterializedEvaluationCase(DomainModel):
    anchor: EvaluationAnchor
    variant: CohortVariant
    case: HybridCase
    bundle: HybridEvidenceBundle
    features: HybridFeatureVector
    ai_source: AISource
    resolved_subject_ids: tuple[NodeId, ...]
    static_available: bool
    graph_available: bool
    discovery_available: bool
    ai_target_selected: bool
    candidate_present: bool


def calibration_feature_schema() -> HybridFeatureSchema:
    definitions = list(feature_schema().definitions)
    definitions.extend(
        HybridFeatureDefinition(name=name, value_type=FeatureValueType.BOOLEAN)
        for name in (
            "selection.candidate_present",
            "selection.static_generated",
            "selection.graph_generated",
            "ai.target_selected",
            "channel.static_available",
            "channel.graph_available",
            "channel.discovery_available",
            "channel.ai_available",
        )
    )
    definitions.append(
        HybridFeatureDefinition(name="task.family", value_type=FeatureValueType.CATEGORICAL)
    )
    # Directed pair subjects keep separate measurements; no unrelated averaging.
    for side in ("source", "target"):
        for name, kind in (
            ("Ca", FeatureValueType.INTEGER),
            ("Ce", FeatureValueType.INTEGER),
            ("coupling", FeatureValueType.INTEGER),
            ("I", FeatureValueType.FLOAT),
        ):
            definitions.append(
                HybridFeatureDefinition(name=f"graph.{side}.{name}", value_type=kind)
            )
    return HybridFeatureSchema(version=VERSION, definitions=tuple(definitions))


def logical_subjects(case: HybridCase, resolver: LocatorResolver) -> Subjects:
    ids = case.primary_subject_ids
    pair = bool(case.subject_pairs) and case.rule_id != "ARCH003"
    if pair:
        ids = (case.subject_pairs[0].source_id, case.subject_pairs[0].target_id)
    kind = (
        NodeKind.FILE
        if case.rule_id in {"ARCH001", "ARCH002", "ARCH004", "ARCH005"}
        else NodeKind.CLASS
    )
    return resolver.from_ids(ids, directed=pair, kind=kind)


class MaterializeEvaluationCase:
    def __init__(
        self,
        iam: ArchitectureModel,
        static: StaticConformanceResult | None,
        graph: GraphAnalysisResult | None,
        discovery: ArchitectureDiscoveryResult | None,
        ai: AIAnalysisResult | None = None,
        conformance: GraphConformanceResult | None = None,
    ) -> None:
        iam_hash = iam_fingerprint(iam)
        if static and (
            static.reproducibility.iam_fingerprint != iam_hash
            or static.reproducibility.project_id != iam.project.id
        ):
            raise ValueError("static evidence must refer to the same IAM")
        if graph and (
            graph.reproducibility.iam_fingerprint != iam_hash
            or graph.graph.project_id != iam.project.id
            or graph.graph.projection.projection != GraphProjection.COMPONENT
        ):
            raise ValueError("graph evidence must be the actual component graph for this IAM")
        if discovery and (
            graph is None
            or discovery.reproducibility.iam_fingerprint != iam_hash
            or discovery.graph.reproducibility != graph.reproducibility
        ):
            raise ValueError("discovery evidence must refer to the same actual graph")
        self.iam, self.static, self.graph, self.discovery, self.ai = (
            iam,
            static,
            graph,
            discovery,
            ai,
        )
        self.resolver = LocatorResolver(iam)
        self.assembler = HybridEvidenceAssembler(iam, static, graph, discovery, ai, conformance)

    def execute(
        self, anchor: EvaluationAnchor, variant: CohortVariant = CohortVariant.STRUCTURAL
    ) -> MaterializedEvaluationCase:
        anchor = EvaluationAnchor.model_validate(anchor)
        resolved = self.resolver.subjects(anchor.subjects)
        if resolved is None:
            raise ValueError("evaluation anchor must resolve uniquely")
        key = resolved_key(anchor.subjects, resolved)
        matching = []
        for production_case, proof in self.assembler.anchors:
            if production_case.rule_id != anchor.rule_id:
                continue
            subjects = logical_subjects(production_case, self.resolver)
            ids = self.resolver.subjects(subjects)
            if ids is not None and resolved_key(subjects, ids) == key:
                matching.append((production_case, proof))
        # IDs depend on locators/rule/variant, never a truth case ID or label.
        identity = uuid5(
            self.iam.project.id,
            f"benchmark-anchor-v1:{anchor.repository_id}:{anchor.rule_id}:{subject_key(anchor.subjects)}:{variant}",
        )
        primary = tuple(
            dict.fromkeys(self.resolver.normalize(i, NodeKind.CLASS).id for i in resolved)
        )
        pairs = (
            (SubjectPair(source_id=primary[0], target_id=primary[1]),)
            if anchor.subjects.directed
            else ()
        )
        case = self.assembler.case(
            HybridCaseType.COMPOSITE,
            primary,
            pairs,
            "CALLER",
            anchor.rule_id,
            identity,
            "BENCHMARK_EVALUATION_ONLY",
        )
        proof = next((p for _, p in matching if p is not None), None)
        bundle = self.assembler.assemble(case, proof)
        selected = (
            any(
                t.candidate_rule_id == anchor.rule_id
                and self.resolver.normalize(t.node_id, NodeKind.CLASS).id in primary
                for t in self.ai.targets
            )
            if self.ai
            else False
        )
        static_generated = any(c.origin == "STATIC" for c, _ in matching)
        graph_generated = any(c.origin in {"GRAPH", "GRAPH_CONFORMANCE"} for c, _ in matching)
        present = any(
            c.origin in {"STATIC", "GRAPH", "GRAPH_CONFORMANCE", "AI"} for c, _ in matching
        )
        providers = {c.provider_id for c in self.ai.candidates} if self.ai else set()
        source = (
            AISource.SCRIPTED_TEST
            if any(p.startswith("scripted") for p in providers)
            else AISource.REAL_PROVIDER
            if providers
            else AISource.AI_UNAVAILABLE
        )
        values = list(extract_features(case, bundle).values)
        additions: dict[str, bool | int | float | str | None] = {
            "selection.candidate_present": present,
            "selection.static_generated": static_generated,
            "selection.graph_generated": graph_generated,
            "ai.target_selected": selected,
            "channel.static_available": self.static is not None,
            "channel.graph_available": self.graph is not None,
            "channel.discovery_available": self.discovery is not None,
            "channel.ai_available": bool(providers),
            "task.family": rule_family(anchor.rule_id).value,
        }
        measurement_refs: dict[str, tuple[str, ...]] = {}
        for side, index in (("source", 0), ("target", 1)):
            measurement = next(
                (
                    m
                    for m in bundle.graph_measurements
                    if anchor.subjects.directed and m.subject_id == primary[index]
                ),
                None,
            )
            for name, attribute in (
                ("Ca", "afferent_coupling"),
                ("Ce", "efferent_coupling"),
                ("coupling", "total_unique_neighbors"),
                ("I", "instability"),
            ):
                measurement_refs[f"graph.{side}.{name}"] = (
                    (measurement.provenance_ref,) if measurement else ()
                )
                additions[f"graph.{side}.{name}"] = (
                    getattr(measurement.metrics, attribute) if measurement else None
                )
        for definition in calibration_feature_schema().definitions[len(values) :]:
            value = additions[definition.name]
            values.append(
                HybridFeature(
                    name=definition.name,
                    value_type=definition.value_type
                    if value is not None
                    else FeatureValueType.MISSING,
                    value=value,
                    availability=FeatureAvailability.AVAILABLE
                    if value is not None
                    else FeatureAvailability.MISSING,
                    provenance_refs=measurement_refs.get(
                        definition.name, (f"benchmark-extraction:{variant}:{definition.name}",)
                    )
                    if value is not None
                    else (),
                )
            )
        vector = HybridFeatureVector(
            case_id=case.case_id,
            schema_version=VERSION,
            values=tuple(values),
            fingerprint=fingerprint(
                {"schema_version": VERSION, "values": [f.model_dump(mode="json") for f in values]}
            ),
        )
        return MaterializedEvaluationCase(
            anchor=anchor,
            variant=variant,
            case=case,
            bundle=bundle,
            features=vector,
            ai_source=source,
            resolved_subject_ids=resolved,
            static_available=self.static is not None,
            graph_available=self.graph is not None,
            discovery_available=self.discovery is not None,
            ai_target_selected=selected,
            candidate_present=present,
        )
