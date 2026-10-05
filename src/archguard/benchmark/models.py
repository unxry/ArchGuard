from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from archguard.architecture.hybrid.models import HybridFeatureVector
from archguard.core.identifiers import NodeId
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language, NodeKind
from archguard.core.model.types import JsonObject, NonEmptyString

RuleId = Annotated[str, Field(pattern=r"^ARCH[012]0[1-5]$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Count = Annotated[int, Field(strict=True, ge=0)]


class Split(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class Origin(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    MUTATION = "MUTATION"
    CURATED = "CURATED"
    REAL_WORLD = "REAL_WORLD"


class Label(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    UNKNOWN = "UNKNOWN"


class AnnotationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    CURATED = "CURATED"
    MUTATION_DERIVED = "MUTATION_DERIVED"
    PROVISIONAL = "PROVISIONAL"


class RuleFamily(StrEnum):
    DETERMINISTIC_CONFORMANCE = "DETERMINISTIC_CONFORMANCE"
    STRUCTURAL_GRAPH = "STRUCTURAL_GRAPH"
    SEMANTIC = "SEMANTIC"


def rule_family(rule: str) -> RuleFamily:
    return (RuleFamily.DETERMINISTIC_CONFORMANCE, RuleFamily.STRUCTURAL_GRAPH, RuleFamily.SEMANTIC)[
        int(rule[4])
    ]


class Task(StrEnum):
    CONFIRMED_VIOLATION_DETECTION = "CONFIRMED_VIOLATION_DETECTION"
    STRUCTURAL_SIGNAL_RETRIEVAL = "STRUCTURAL_SIGNAL_RETRIEVAL"
    SEMANTIC_CANDIDATE_DETECTION = "SEMANTIC_CANDIDATE_DETECTION"
    CALIBRATED_HYBRID_DETECTION = "CALIBRATED_HYBRID_DETECTION"

    @property
    def family(self) -> RuleFamily | None:
        return {
            Task.CONFIRMED_VIOLATION_DETECTION: RuleFamily.DETERMINISTIC_CONFORMANCE,
            Task.STRUCTURAL_SIGNAL_RETRIEVAL: RuleFamily.STRUCTURAL_GRAPH,
            Task.SEMANTIC_CANDIDATE_DETECTION: RuleFamily.SEMANTIC,
        }.get(self)


class Mode(StrEnum):
    STATIC_ONLY = "STATIC_ONLY"
    GRAPH_ONLY = "GRAPH_ONLY"
    LLM_ONLY = "LLM_ONLY"
    HYBRID = "HYBRID"


class Ablation(StrEnum):
    STATIC = "STATIC"
    GRAPH = "GRAPH"
    LLM = "LLM"
    STATIC_GRAPH = "STATIC_GRAPH"
    STATIC_LLM = "STATIC_LLM"
    GRAPH_LLM = "GRAPH_LLM"
    STATIC_GRAPH_LLM = "STATIC_GRAPH_LLM"


def relative_path(value: str) -> str:
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or ":" in value
        or any(p in {"", ".", ".."} for p in value.split("/"))
    ):
        raise ValueError("expected canonical relative POSIX path")
    return value


class Locator(DomainModel):
    path: NonEmptyString
    language: Language
    qualified_name: NonEmptyString
    kind: NodeKind
    signature: NonEmptyString | None = None

    _path = field_validator("path")(relative_path)


class Subjects(DomainModel):
    locators: Annotated[tuple[Locator, ...], Field(min_length=1)]
    directed: bool = False

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.directed and len(self.locators) != 2:
            raise ValueError("directed subjects require source and target")
        keys = [x.model_dump_json() for x in self.locators]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate subject locator")
        if not self.directed and keys != sorted(keys):
            raise ValueError("unordered subjects must be canonical")
        return self


class AnnotatedSubject(DomainModel):
    rule_id: RuleId
    subjects: Subjects


class AnnotationScope(DomainModel):
    rules: tuple[RuleId, ...]
    fully_annotated_rules: tuple[RuleId, ...] = ()
    fully_annotated_subjects: tuple[AnnotatedSubject, ...] = ()
    fully_annotated_files: tuple[str, ...] = ()
    fully_annotated_modules: tuple[str, ...] = ()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if not set(self.fully_annotated_rules) <= set(self.rules):
            raise ValueError("full rule must be in annotation rules")
        if any(x.rule_id not in self.rules for x in self.fully_annotated_subjects):
            raise ValueError("subject rule must be in annotation rules")
        for path in self.fully_annotated_files + self.fully_annotated_modules:
            relative_path(path)
        return self

    def contains(self, rule: str, subjects: Subjects) -> bool:
        if rule not in self.rules:
            return False
        if rule in self.fully_annotated_rules or any(
            x.rule_id == rule and x.subjects == subjects for x in self.fully_annotated_subjects
        ):
            return True
        return all(
            x.path in self.fully_annotated_files
            or any(x.path.startswith(p + "/") for p in self.fully_annotated_modules)
            for x in subjects.locators
        )


class ReviewMetadata(DomainModel):
    annotators: tuple[NonEmptyString, ...] = ()
    status: Literal["UNREVIEWED", "REVIEWED"] = "UNREVIEWED"
    notes: str = ""
    agreement: Annotated[float, Field(ge=0, le=1)] | None = None


class GroundTruthCase(DomainModel):
    case_id: UUID
    repository_id: NonEmptyString
    rule_id: RuleId
    rule_family: RuleFamily
    label: Label
    subjects: Subjects
    scope: Literal["LOGICAL_SUBJECT"] = "LOGICAL_SUBJECT"
    rationale: NonEmptyString
    origin: Origin
    annotation_status: AnnotationStatus
    expected_evidence: tuple[NonEmptyString, ...] = ()
    mutation_id: UUID | None = None
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.rule_family != rule_family(self.rule_id):
            raise ValueError("rule family mismatch")
        if self.annotation_status == AnnotationStatus.MUTATION_DERIVED and (
            self.origin != Origin.MUTATION or self.mutation_id is None
        ):
            raise ValueError("mutation-derived truth requires mutation provenance")
        return self


class BenchmarkRepository(DomainModel):
    repository_id: NonEmptyString
    repository_family_id: NonEmptyString
    name: NonEmptyString
    origin: Origin
    languages: Annotated[tuple[Language, ...], Field(min_length=1)]
    source_path: NonEmptyString
    source_fingerprint: Digest
    ground_truth: NonEmptyString
    dataset_split: Split
    architecture_spec: NonEmptyString | None = None
    graph_config: NonEmptyString | None = None
    base_repository_id: NonEmptyString | None = None
    mutation_manifest: NonEmptyString | None = None
    annotation_scope: AnnotationScope
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        for p in (
            self.source_path,
            self.ground_truth,
            self.architecture_spec,
            self.graph_config,
            self.mutation_manifest,
        ):
            if p is not None:
                relative_path(p)
        if self.origin == Origin.MUTATION and not (
            self.base_repository_id and self.mutation_manifest
        ):
            raise ValueError("mutant must identify base and manifest")
        return self


class BenchmarkDataset(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: NonEmptyString
    dataset_version: NonEmptyString
    namespace: UUID
    split_seed: NonEmptyString
    split_manifest: str = "splits.json"
    split_algorithm: Literal["sha256-ranked-families-v1"] = "sha256-ranked-families-v1"
    purpose: Literal["ENGINEERING_SEED"] = "ENGINEERING_SEED"
    repositories: Annotated[tuple[BenchmarkRepository, ...], Field(min_length=1, max_length=500)]


class PredictionState(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    ABSTAIN = "ABSTAIN"
    CANDIDATE = "CANDIDATE"


class BenchmarkPrediction(DomainModel):
    prediction_id: UUID
    repository_id: NonEmptyString
    rule_id: RuleId
    subjects: Subjects
    subject_ids: tuple[NodeId, ...] = ()
    state: PredictionState
    source: Mode
    task: Task
    origin_artifact_ids: tuple[UUID, ...] = ()
    evidence: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def task_family(self) -> Self:
        if self.task.family is not None and rule_family(self.rule_id) != self.task.family:
            raise ValueError("prediction rule/task mismatch")
        if (
            self.task == Task.CONFIRMED_VIOLATION_DETECTION
            and self.state == PredictionState.CANDIDATE
        ):
            raise ValueError("candidate is not a confirmed violation")
        return self


class PredictionArtifact(DomainModel):
    closed_world_complete: bool = False
    schema_version: Literal["1.0"] = "1.0"
    dataset_fingerprint: Digest
    predictions: Annotated[tuple[BenchmarkPrediction, ...], Field(max_length=100000)]


class Confusion(DomainModel):
    tp: Count = 0
    fp: Count = 0
    fn: Count = 0
    tn: Count = 0
    abstain: Count = 0
    no_prediction: Count = 0
    out_of_scope: Count = 0
    unresolved_truth: Count = 0
    unknown_truth: Count = 0
    explicit_negatives: Count = 0
    scoped_extra_fp: Count = 0
    eligible: Count = 0


class Metrics(DomainModel):
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    fpr: float | None = None
    fnr: float | None = None
    abstention_rate: float | None = None
    prediction_coverage: float | None = None


class EvaluationGroup(DomainModel):
    key: str
    confusion: Confusion
    metrics: Metrics


class BenchmarkRun(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: Digest
    splits: tuple[Split, ...]
    mode: Mode
    task: Task
    status: Literal["VALID", "PARTIAL"]
    predictions: tuple[BenchmarkPrediction, ...]
    confusion: Confusion
    metrics: Metrics
    per_rule: tuple[EvaluationGroup, ...]
    per_language: tuple[EvaluationGroup, ...]
    per_repository: tuple[EvaluationGroup, ...]
    macro_rule: Metrics
    macro_repository: Metrics
    diagnostics: tuple[str, ...]
    tool_versions: dict[str, str]
    reproducibility: dict[str, str]


class HybridTrainingRecord(DomainModel):
    repository_id: str
    repository_family_id: str
    split: Split
    case_id: UUID
    hybrid_case_id: UUID
    rule_family: RuleFamily
    subjects: Subjects
    subject_ids: tuple[NodeId, ...]
    feature_schema_version: str
    feature_fingerprint: Digest
    features: HybridFeatureVector
    ground_truth_label: Label
    annotation_status: AnnotationStatus
    evidence_availability: tuple[str, ...]

    @model_validator(mode="after")
    def coherent_record(self) -> Self:
        if (
            self.features.case_id != self.hybrid_case_id
            or self.features.fingerprint != self.feature_fingerprint
            or self.features.schema_version != self.feature_schema_version
        ):
            raise ValueError("record feature provenance mismatch")
        return self
