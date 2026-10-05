from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from archguard.architecture.discovery.enums import ComponentRole, DiscoveredLayer, DiscoveryStrength
from archguard.architecture.graph.models import GraphNodeMetrics
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.architecture.intelligence.models import (
    ContextStrategy,
    LLMUsage,
    ProviderIdentity,
    SemanticDecision,
)
from archguard.core.findings.confidence import CalibrationStatus as ConfidenceCalibrationStatus
from archguard.core.findings.confidence import Confidence
from archguard.core.findings.enums import DetectorSource, Severity
from archguard.core.identifiers import EdgeId, FindingId, NodeId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.types import RepositoryPath

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Count = Annotated[int, Field(strict=True, ge=0)]


class HybridCaseType(StrEnum):
    DETERMINISTIC_CONFORMANCE = "DETERMINISTIC_CONFORMANCE"
    GRAPH_STRUCTURAL = "GRAPH_STRUCTURAL"
    SEMANTIC = "SEMANTIC"
    COMPOSITE = "COMPOSITE"


class EvidenceAgreement(StrEnum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    NEUTRAL = "NEUTRAL"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AlignmentMethod(StrEnum):
    EXACT_SUBJECT = "EXACT_SUBJECT"
    EXACT_SUBJECT_PAIR = "EXACT_SUBJECT_PAIR"
    DIRECT_GRAPH_RELATION = "DIRECT_GRAPH_RELATION"
    CONTAINMENT_OWNER = "CONTAINMENT_OWNER"
    EXPLICIT_CANDIDATE_LINK = "EXPLICIT_CANDIDATE_LINK"


class CalibrationStatus(StrEnum):
    UNCALIBRATED = "UNCALIBRATED"
    CALIBRATED = "CALIBRATED"
    DETERMINISTIC = "DETERMINISTIC"


class HybridDecisionState(StrEnum):
    CONFIRMED_DETERMINISTIC = "CONFIRMED_DETERMINISTIC"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SUPPORTED_BY_CALIBRATED_POLICY = "SUPPORTED_BY_CALIBRATED_POLICY"
    REJECTED_BY_CALIBRATED_POLICY = "REJECTED_BY_CALIBRATED_POLICY"


class SubjectPair(DomainModel):
    source_id: NodeId
    target_id: NodeId


class HybridCase(DomainModel):
    case_id: UUID
    case_type: HybridCaseType
    primary_subject_ids: Annotated[tuple[NodeId, ...], Field(min_length=1)]
    related_subject_ids: tuple[NodeId, ...] = ()
    subject_pairs: tuple[SubjectPair, ...] = ()
    origin: Literal["STATIC", "GRAPH_CONFORMANCE", "GRAPH", "AI", "CALLER"]
    rule_id: Annotated[str, Field(pattern=r"^ARCH(?:00[1-5]|10[1-5]|20[1-5])$")]
    anchor_ids: Annotated[tuple[UUID, ...], Field(min_length=1)]
    scope: str
    bundle_id: UUID


class StaticProof(DomainModel):
    finding_id: FindingId
    rule_id: Literal["ARCH001", "ARCH002", "ARCH003", "ARCH004", "ARCH005"]
    detector_source: DetectorSource
    detector_name: ProviderIdentity
    detector_version: ProviderIdentity
    severity: Severity
    pairs: tuple[SubjectPair, ...]
    edge_ids: tuple[EdgeId, ...]
    relation_kinds: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]
    locations: tuple[SourceLocation, ...]
    provenance_count: Count
    provenance_truncated: Count
    spec_fingerprint: Digest
    deterministic: Literal[True] = True

    @model_validator(mode="after")
    def deterministic_source(self) -> Self:
        expected = DetectorSource.GRAPH if self.rule_id == "ARCH003" else DetectorSource.STATIC
        if self.detector_source != expected or not self.pairs or not self.edge_ids:
            raise ValueError(
                "deterministic proof requires the proper detector and actual IAM edges"
            )
        return self


class NumericObservation(DomainModel):
    name: str
    value: int | float | None


class GraphSignal(DomainModel):
    candidate_id: UUID
    rule_id: Literal["ARCH101", "ARCH102", "ARCH103", "ARCH104", "ARCH105"]
    subject_ids: tuple[NodeId, ...]
    pairs: tuple[SubjectPair, ...] = ()
    projection: str
    metrics: tuple[NumericObservation, ...]
    thresholds: tuple[NumericObservation, ...]
    engine_version: str
    configuration_fingerprint: Digest
    not_calibrated: Literal[True] = True


class GraphMeasurement(DomainModel):
    subject_id: NodeId
    metrics: GraphNodeMetrics
    provenance_ref: str
    scc_id: UUID | None = None
    scc_member_ids: tuple[NodeId, ...] = ()
    cycle_edge_ids: tuple[UUID, ...] = ()


class SemanticSignal(DomainModel):
    candidate_id: UUID
    rule_id: Literal["ARCH201", "ARCH202", "ARCH203", "ARCH204", "ARCH205"]
    decision: SemanticDecision
    subject_ids: tuple[NodeId, ...]
    pairs: tuple[SubjectPair, ...] = ()
    evidence_refs: tuple[str, ...]
    context_fingerprint: Digest
    strategy: ContextStrategy
    provider_id: ProviderIdentity
    model_id: ProviderIdentity
    prompt_version: ProviderIdentity
    schema_version: ProviderIdentity
    usage: LLMUsage | None = None
    usage_available: bool
    not_calibrated: Literal[True] = True


class DiscoverySignal(DomainModel):
    subject_id: NodeId
    role_hypothesis_id: UUID
    role: ComponentRole
    role_strength: DiscoveryStrength
    candidate_roles: tuple[ComponentRole, ...]
    conflicting_roles: tuple[ComponentRole, ...]
    layer_hypothesis_id: UUID
    layer: DiscoveredLayer
    layer_strength: DiscoveryStrength
    module_id: UUID | None
    module_strength: DiscoveryStrength | None
    normative: Literal[False] = False


class ContextReference(DomainModel):
    evidence_id: str
    kind: str
    subject_ids: tuple[NodeId, ...]
    relative_path: RepositoryPath | None = None
    start_line: Count | None = None
    end_line: Count | None = None
    content_hash: Digest | None = None


class ContextSummary(DomainModel):
    context_fingerprint: Digest
    target_id: NodeId
    strategy: ContextStrategy
    selected_subject_ids: tuple[NodeId, ...]
    references: tuple[ContextReference, ...]
    truncated: bool
    dropped_nodes: Count
    dropped_files: Count
    dropped_fragments: Count
    dropped_evidence: Count


class EvidenceCompleteness(DomainModel):
    iam_complete: bool | None
    parse_errors_present: bool | None
    unresolved_references: Count | None
    ambiguous_references: Count | None
    graph_complete: bool | None
    metrics_skipped: tuple[str, ...] | None
    discovery_complete: bool | None
    discovery_unknown: Count | None
    discovery_ambiguous: Count | None
    ai_requested: Count | None
    ai_completed: Count | None
    ai_partial: bool | None
    ai_insufficient: Count | None
    context_truncated: bool | None


class EvidenceAlignment(DomainModel):
    target_case_id: UUID
    source_refs: Annotated[tuple[str, ...], Field(min_length=1)]
    method: AlignmentMethod | None
    agreement: EvidenceAgreement
    reason_code: str
    mapping_version: Literal["hybrid-concerns-v1"] = "hybrid-concerns-v1"


class HybridEvidenceBundle(DomainModel):
    bundle_id: UUID
    static: tuple[StaticProof, ...] = ()
    graph: tuple[GraphSignal, ...] = ()
    graph_measurements: tuple[GraphMeasurement, ...] = ()
    ai: tuple[SemanticSignal, ...] = ()
    discovery: tuple[DiscoverySignal, ...] = ()
    context: tuple[ContextSummary, ...] = ()
    completeness: EvidenceCompleteness
    alignments: tuple[EvidenceAlignment, ...] = ()


class FeatureValueType(StrEnum):
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    CATEGORICAL = "CATEGORICAL"
    SET = "SET"
    MISSING = "MISSING"


class FeatureAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HybridFeature(DomainModel):
    name: str
    value_type: FeatureValueType
    value: bool | int | float | str | tuple[str, ...] | None
    availability: FeatureAvailability
    provenance_refs: tuple[str, ...]

    @model_validator(mode="after")
    def typed_value(self) -> Self:
        valid = {
            FeatureValueType.BOOLEAN: type(self.value) is bool,
            FeatureValueType.INTEGER: type(self.value) is int,
            FeatureValueType.FLOAT: type(self.value) is float,
            FeatureValueType.CATEGORICAL: type(self.value) is str,
            FeatureValueType.SET: isinstance(self.value, tuple),
            FeatureValueType.MISSING: self.value is None,
        }
        if not valid[self.value_type] or (self.value is None) != (
            self.availability != FeatureAvailability.AVAILABLE
        ):
            raise ValueError("feature value type and availability must agree")
        if self.availability == FeatureAvailability.AVAILABLE and not self.provenance_refs:
            raise ValueError("available features require provenance")
        return self


class HybridFeatureDefinition(DomainModel):
    name: str
    value_type: FeatureValueType


class HybridFeatureSchema(DomainModel):
    version: str
    definitions: tuple[HybridFeatureDefinition, ...]


class HybridFeatureVector(DomainModel):
    case_id: UUID
    schema_version: str
    values: tuple[HybridFeature, ...]
    fingerprint: Digest


class HybridPolicyMetadata(DomainModel):
    policy_id: ProviderIdentity
    policy_version: ProviderIdentity
    feature_schema_version: ProviderIdentity
    calibration_status: CalibrationStatus


class HybridDecision(DomainModel):
    decision_id: UUID
    case_id: UUID
    state: HybridDecisionState
    policy: HybridPolicyMetadata
    calibration_status: CalibrationStatus
    feature_fingerprint: Digest
    evidence_fingerprint: Digest
    reason_codes: Annotated[tuple[str, ...], Field(min_length=1)]
    supporting_refs: tuple[str, ...]
    contradicting_refs: tuple[str, ...]
    missing_refs: tuple[str, ...]
    confirmed_finding_ids: tuple[FindingId, ...] = ()
    severity: Severity | None = None
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def state_contract(self) -> Self:
        confirmed = self.state == HybridDecisionState.CONFIRMED_DETERMINISTIC
        if confirmed != bool(self.confirmed_finding_ids) or confirmed != (
            self.calibration_status == CalibrationStatus.DETERMINISTIC
        ):
            raise ValueError("confirmed decisions require deterministic Finding references")
        if not confirmed and self.severity is not None:
            raise ValueError("candidate decisions cannot invent severity")
        if confirmed and self.severity is None:
            raise ValueError("deterministic decisions must preserve rule severity")
        if (
            self.calibration_status == CalibrationStatus.CALIBRATED
            and self.policy.calibration_status != CalibrationStatus.CALIBRATED
        ):
            raise ValueError("calibrated decisions require recorded policy calibration")
        if (
            self.confidence is not None
            and self.confidence.status != ConfidenceCalibrationStatus.CALIBRATED
        ):
            raise ValueError("numeric confidence requires a calibration reference")
        if self.calibration_status != CalibrationStatus.CALIBRATED and self.confidence is not None:
            raise ValueError("uncalibrated decisions cannot expose numeric confidence")
        if (
            self.state
            in {
                HybridDecisionState.SUPPORTED_BY_CALIBRATED_POLICY,
                HybridDecisionState.REJECTED_BY_CALIBRATED_POLICY,
            }
            and self.calibration_status != CalibrationStatus.CALIBRATED
        ):
            raise ValueError("calibrated decision states require a calibrated policy")
        return self


class HybridStatistics(DomainModel):
    cases_by_type: dict[str, Count]
    decisions_by_state: dict[str, Count]
    channel_cases: dict[str, Count]
    ai_decisions: dict[str, Count]
    agreements: Count
    conflicts: Count
    missing: Count
    omitted_candidate_cases: Count


class HybridReproducibility(DomainModel):
    max_candidate_cases: Count
    iam_fingerprint: Digest
    iam_schema_version: str
    snapshot_fingerprint: Digest | None
    static_engine_version: str | None
    spec_fingerprint: Digest | None
    graph_engine_version: str | None
    graph_configuration_fingerprint: Digest | None
    graph_projection_fingerprint: Digest | None
    discovery_engine_version: str | None
    discovery_configuration_fingerprint: Digest | None
    ai_inputs: tuple[SemanticSignal, ...]
    feature_schema_version: str
    policy: HybridPolicyMetadata
    hybrid_engine_version: Literal["1.0.0"] = "1.0.0"


class HybridAnalysisResult(DomainModel):
    result_schema_version: Literal["hybrid-analysis-v1"] = "hybrid-analysis-v1"
    cases: tuple[HybridCase, ...]
    evidence_bundles: tuple[HybridEvidenceBundle, ...]
    feature_schema: HybridFeatureSchema
    features: tuple[HybridFeatureVector, ...]
    decisions: tuple[HybridDecision, ...]
    confirmed_finding_ids: tuple[FindingId, ...]
    review_case_ids: tuple[UUID, ...]
    diagnostics: tuple[str, ...]
    statistics: HybridStatistics
    reproducibility: HybridReproducibility

    @model_validator(mode="after")
    def preserve_proofs(self) -> Self:
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)) or tuple(d.case_id for d in self.decisions) != ids:
            raise ValueError("each case requires exactly one ordered decision")
        if tuple(f.case_id for f in self.features) != ids or tuple(
            b.bundle_id for b in self.evidence_bundles
        ) != tuple(c.bundle_id for c in self.cases):
            raise ValueError("case, bundle and features must correspond")
        retained: set[FindingId] = set()
        for bundle, vector, decision in zip(
            self.evidence_bundles, self.features, self.decisions, strict=True
        ):
            if vector.schema_version != self.feature_schema.version or tuple(
                f.name for f in vector.values
            ) != tuple(d.name for d in self.feature_schema.definitions):
                raise ValueError("features must match the ordered versioned schema")
            expected_feature_hash = fingerprint(
                {
                    "schema_version": vector.schema_version,
                    "values": [f.model_dump(mode="json") for f in vector.values],
                }
            )
            if (
                vector.fingerprint != expected_feature_hash
                or decision.feature_fingerprint != vector.fingerprint
                or decision.evidence_fingerprint != fingerprint(bundle)
            ):
                raise ValueError("features and evidence must match their fingerprints")
            proofs = bundle.static
            if not proofs and decision.state == HybridDecisionState.CONFIRMED_DETERMINISTIC:
                raise ValueError("only deterministic proof can confirm a Finding")
            if proofs and (
                len(proofs) != 1
                or decision.state != HybridDecisionState.CONFIRMED_DETERMINISTIC
                or decision.confirmed_finding_ids != (proofs[0].finding_id,)
                or decision.severity != proofs[0].severity
            ):
                raise ValueError("deterministic proof and severity must survive every policy")
            retained.update(decision.confirmed_finding_ids)
        if tuple(sorted(retained, key=str)) != self.confirmed_finding_ids:
            raise ValueError("confirmed Finding references must be complete and unique")
        return self
