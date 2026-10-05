import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from archguard.architecture.graph.config import GraphAnalysisConfig, GraphProjectionSpec
from archguard.architecture.graph.enums import GraphProjection, NeighbourhoodDirection
from archguard.architecture.specification.models import DEFAULT_RELATIONS
from archguard.core.identifiers import NodeId
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import EdgeKind, Language
from archguard.core.model.types import JsonObject, RepositoryPath

Positive = Annotated[int, Field(strict=True, gt=0)]
Count = Annotated[int, Field(strict=True, ge=0)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=1500)]
ProviderIdentity = Annotated[
    str, Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
]
RuleId = Literal["ARCH201", "ARCH202", "ARCH203", "ARCH204", "ARCH205"]
RULES: dict[RuleId, str] = {
    "ARCH201": "Responsibility Mismatch",
    "ARCH202": "Business Logic in Controller",
    "ARCH203": "Infrastructure Leakage",
    "ARCH204": "Misplaced Component",
    "ARCH205": "Suspicious Cross-Layer Responsibility",
}
PROMPT_VERSION = "architecture-semantic-v1"
SCHEMA_VERSION = "semantic-assessment-v1"


def canonical(value: object) -> str:
    if isinstance(value, DomainModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class ContextStrategy(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    GRAPH_GUIDED = "GRAPH_GUIDED"
    EXPANDED_BASELINE = "EXPANDED_BASELINE"


class ContextSelectionConfig(DomainModel):
    strategy: ContextStrategy = ContextStrategy.GRAPH_GUIDED
    hop_count: Annotated[int, Field(strict=True, ge=0, le=8)] = 1
    direction: NeighbourhoodDirection = NeighbourhoodDirection.BOTH
    included_relations: tuple[EdgeKind, ...] = DEFAULT_RELATIONS
    max_nodes: Annotated[int, Field(strict=True, gt=0, le=1000)] = 20
    max_files: Annotated[int, Field(strict=True, gt=0, le=1000)] = 10
    max_fragments: Annotated[int, Field(strict=True, gt=0, le=1000)] = 20
    max_fragment_chars: Positive = 4000
    max_total_chars: Annotated[int, Field(strict=True, ge=512)] = 20000
    max_lines_per_fragment: Positive = 120
    before_lines: Count = 2
    after_lines: Count = 2
    max_line_bytes: Positive = 65536
    max_scan_bytes_per_file: Positive = 33554432
    include_spec: StrictBool = True
    include_discovery: StrictBool = True
    include_metrics: StrictBool = True
    include_dependency_paths: StrictBool = True
    token_budget: Positive | None = None

    @model_validator(mode="after")
    def supported_relations(self) -> Self:
        normalized = GraphProjectionSpec(included_relations=self.included_relations)
        object.__setattr__(self, "included_relations", normalized.included_relations)
        return self


class ContextDiagnostic(DomainModel):
    code: str
    message: str
    subject_node_id: NodeId | None = None


class SelectedNode(DomainModel):
    node_id: NodeId
    distance: Count | None
    reason: str


class FragmentReference(DomainModel):
    evidence_id: str
    relative_path: RepositoryPath
    start_line: Positive
    end_line: Positive
    node_ids: tuple[NodeId, ...]
    language: Language
    purpose: str
    truncated: bool
    content_hash: Digest
    chars: Count

    @model_validator(mode="after")
    def ordered_lines(self) -> Self:
        if self.end_line < self.start_line:
            raise ValueError("fragment end precedes start")
        return self


class SourceFragment(DomainModel):
    reference: FragmentReference
    text: str = Field(repr=False)

    @model_validator(mode="after")
    def hash_matches(self) -> Self:
        if (
            len(self.text) != self.reference.chars
            or hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.reference.content_hash
        ):
            raise ValueError("fragment text must agree with its reference")
        return self


class ContextEvidence(DomainModel):
    evidence_id: str
    kind: Literal["DEPENDENCY", "TARGET_CONSTRAINT", "DISCOVERY_HYPOTHESIS", "GRAPH_METRIC"]
    subject_node_ids: tuple[NodeId, ...]
    data: JsonObject


class ContextManifest(DomainModel):
    context_schema_version: Literal["1.0"] = "1.0"
    target_node_id: NodeId
    configuration: ContextSelectionConfig
    selected_nodes: tuple[SelectedNode, ...]
    fragments: tuple[FragmentReference, ...]
    evidence: tuple[ContextEvidence, ...]
    context_fingerprint: Digest
    context_chars: Count
    files: Count
    truncated: bool
    dropped_nodes: Count = 0
    dropped_files: Count = 0
    dropped_fragments: Count = 0
    dropped_evidence: Count = 0
    redactor_id: str | None = None
    diagnostics: tuple[ContextDiagnostic, ...] = ()

    @model_validator(mode="after")
    def bounded_references(self) -> Self:
        nodes = {n.node_id for n in self.selected_nodes}
        refs = [f.evidence_id for f in self.fragments] + [e.evidence_id for e in self.evidence]
        if (
            self.target_node_id not in nodes
            or len(nodes) != len(self.selected_nodes)
            or len(refs) != len(set(refs))
            or self.files != len({f.relative_path for f in self.fragments})
            or self.files > self.configuration.max_files
            or len(self.fragments) > self.configuration.max_fragments
            or len(nodes) > self.configuration.max_nodes
            or self.context_chars > self.configuration.max_total_chars
            or any(
                f.chars > self.configuration.max_fragment_chars or not set(f.node_ids) <= nodes
                for f in self.fragments
            )
            or any(not set(e.subject_node_ids) <= nodes for e in self.evidence)
        ):
            raise ValueError("context references or budgets are inconsistent")
        return self


class ArchitectureContextPack(DomainModel):
    manifest: ContextManifest
    fragments: tuple[SourceFragment, ...] = Field(repr=False)

    @model_validator(mode="after")
    def manifest_matches(self) -> Self:
        if (
            tuple(f.reference for f in self.fragments) != self.manifest.fragments
            or len(canonical(self.untrusted_data())) != self.manifest.context_chars
        ):
            raise ValueError("context pack must agree with the manifest")
        return self

    def untrusted_data(self) -> JsonObject:
        return {
            "trust": "UNTRUSTED_DATA",
            "target_node_id": str(self.manifest.target_node_id),
            "selected_node_ids": [str(item.node_id) for item in self.manifest.selected_nodes],
            "source_fragments": [item.model_dump(mode="json") for item in self.fragments],
            "evidence": [item.model_dump(mode="json") for item in self.manifest.evidence],
        }


class SemanticDecision(StrEnum):
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class SemanticArchitectureAssessment(DomainModel):
    candidate_rule_id: RuleId
    decision: SemanticDecision
    subject_node_ids: Annotated[tuple[NodeId, ...], Field(min_length=1, max_length=20)]
    short_reason: ShortText
    evidence_refs: Annotated[tuple[str, ...], Field(max_length=50)]
    suggested_role: Annotated[str, Field(max_length=128)] | None
    suggested_layer: Annotated[str, Field(max_length=128)] | None
    assumptions: Annotated[tuple[ShortText, ...], Field(max_length=10)]
    limitations: Annotated[tuple[ShortText, ...], Field(max_length=10)]
    recommendation: ShortText | None

    @model_validator(mode="after")
    def supported_needs_evidence(self) -> Self:
        if self.decision == SemanticDecision.SUPPORTED and not self.evidence_refs:
            raise ValueError("supported assessment requires evidence references")
        if len(set(self.subject_node_ids)) != len(self.subject_node_ids) or len(
            set(self.evidence_refs)
        ) != len(self.evidence_refs):
            raise ValueError("subjects and evidence references must be unique")
        return self


class SemanticAnalysisTarget(DomainModel):
    node_id: NodeId
    candidate_rule_id: RuleId
    reason: str


class TargetSelectionConfig(DomainModel):
    explicit_targets: tuple[str, ...] = ()
    rules: tuple[RuleId, ...] = ()
    include_ambiguous: StrictBool = True
    include_unknown: StrictBool = False
    include_controllers: StrictBool = True
    graph_candidate_rules: tuple[str, ...] = ("ARCH101", "ARCH103", "ARCH104", "ARCH105")
    max_targets: Annotated[int, Field(strict=True, gt=0, le=1000)] = 10


class AIAnalysisBudget(DomainModel):
    max_calls: Positive = 10
    max_candidates: Positive = 10
    max_total_input_tokens: Positive | None = None
    timeout_seconds: Annotated[float, Field(gt=0, le=300)] = 30.0
    max_output_tokens: Positive = 2000


class AIAnalysisConfig(DomainModel):
    context: ContextSelectionConfig = Field(default_factory=ContextSelectionConfig)
    targets: TargetSelectionConfig = Field(default_factory=TargetSelectionConfig)
    budget: AIAnalysisBudget = Field(default_factory=AIAnalysisBudget)
    graph: GraphAnalysisConfig = Field(default_factory=GraphAnalysisConfig)
    allow_remote_source: StrictBool = False
    include_discovery: StrictBool = True

    @model_validator(mode="after")
    def internal_component_graph(self) -> Self:
        projection = self.graph.projection
        if (
            projection.projection != GraphProjection.COMPONENT
            or projection.include_external
            or projection.include_self_edges
        ):
            raise ValueError(
                "semantic context requires an internal component graph without self edges"
            )
        return self


class LLMUsage(DomainModel):
    input_tokens: Count | None = None
    output_tokens: Count | None = None
    total_tokens: Count | None = None
    provider_reported_cost: Annotated[float, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def known_totals_agree(self) -> Self:
        if (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("reported token totals must agree")
        return self


class ProviderCapabilities(DomainModel):
    remote: bool
    structured_output: bool = True
    input_token_counting: bool = False


class StructuredLLMRequest(DomainModel):
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    system_instructions: str
    task: JsonObject
    untrusted_context: JsonObject = Field(repr=False)
    response_schema: JsonObject
    timeout_seconds: float
    max_output_tokens: Positive


class StructuredLLMResponse(DomainModel):
    structured_json: str = Field(repr=False)
    provider_id: ProviderIdentity
    model_id: ProviderIdentity
    request_id: ProviderIdentity | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)


class SemanticArchitectureCandidate(DomainModel):
    candidate_id: UUID
    assessment: SemanticArchitectureAssessment
    context_fingerprint: Digest
    strategy: ContextStrategy
    provider_id: str
    model_id: str
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    not_calibrated: Literal[True] = True


class AIInvocation(DomainModel):
    invocation_id: UUID
    target: SemanticAnalysisTarget
    provider_id: str
    model_id: str
    provider_request_id: str | None
    usage: LLMUsage
    latency_seconds: Annotated[float, Field(ge=0)]
    generation_parameters: JsonObject
    diagnostic: ContextDiagnostic | None = None


class AIAnalysisResult(DomainModel):
    result_schema_version: Literal["1.0"] = "1.0"
    status: Literal["DRY_RUN", "COMPLETE", "PARTIAL", "UNAVAILABLE", "INCOMPLETE", "INVALID"]
    targets: tuple[SemanticAnalysisTarget, ...]
    manifests: tuple[ContextManifest, ...]
    request_metadata: tuple[JsonObject, ...]
    candidates: tuple[SemanticArchitectureCandidate, ...] = ()
    invocations: tuple[AIInvocation, ...] = ()
    diagnostics: tuple[ContextDiagnostic, ...] = ()
    calls: Count = 0
    skipped_targets: Count = 0


def serialize_ai(value: DomainModel) -> str:
    return canonical(value) + "\n"
