from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from archguard.architecture.hybrid.models import FeatureValueType
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.architecture.intelligence.models import ContextStrategy, LLMUsage
from archguard.benchmark.materialization import (
    AISource,
    CohortVariant,
    MaterializedEvaluationCase,
    calibration_feature_schema,
)
from archguard.benchmark.models import (
    BenchmarkRepository,
    Digest,
    GroundTruthCase,
    HybridTrainingRecord,
    Label,
    RuleFamily,
    RuleId,
    Task,
    relative_path,
    rule_family,
)
from archguard.core.model.base import DomainModel


class AIAssessmentManifest(DomainModel):
    case_id: UUID
    source: AISource = AISource.AI_UNAVAILABLE
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    context_strategy: ContextStrategy | None = None
    context_fingerprint: Digest | None = None
    assessment_artifact: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)

    @model_validator(mode="after")
    def safe_reference(self) -> Self:
        if self.assessment_artifact:
            relative_path(self.assessment_artifact)
        return self


class CalibrationTrainingRecord(HybridTrainingRecord):
    export_schema_version: Literal["calibration-cohort-v1"] = "calibration-cohort-v1"
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: Digest
    rule_id: RuleId
    task: Task
    variant: CohortVariant
    materialization: Literal["BENCHMARK_EVALUATION_ONLY"] = "BENCHMARK_EVALUATION_ONLY"
    ai_source: AISource
    calibration_eligible: bool
    eligibility_reasons: tuple[str, ...]
    channels: dict[str, bool]

    @model_validator(mode="after")
    def independent_features(self) -> Self:
        schema = calibration_feature_schema()
        if (
            self.task.family != self.rule_family
            or rule_family(self.rule_id) != self.rule_family
            or self.features.schema_version != schema.version
        ):
            raise ValueError("cohort task/feature schema mismatch")
        if tuple(f.name for f in self.features.values) != tuple(d.name for d in schema.definitions):
            raise ValueError("cohort features must use the exact label-free schema")
        if any(
            feature.value_type not in {definition.value_type, FeatureValueType.MISSING}
            for feature, definition in zip(self.features.values, schema.definitions, strict=True)
        ):
            raise ValueError("cohort feature types must match the schema")
        if self.feature_fingerprint != fingerprint(
            {
                "schema_version": schema.version,
                "values": [f.model_dump(mode="json") for f in self.features.values],
            }
        ):
            raise ValueError("cohort feature fingerprint mismatch")
        values = {f.name: f.value for f in self.features.values}
        if values["task.family"] != self.rule_family.value:
            raise ValueError("cohort task feature mismatch")
        if set(self.channels) != {"static", "graph", "discovery", "ai"} or any(
            values[f"channel.{name}_available"] != value for name, value in self.channels.items()
        ):
            raise ValueError("cohort channel availability mismatch")
        if self.channels["ai"] != (self.ai_source != AISource.AI_UNAVAILABLE):
            raise ValueError("AI provenance cannot be overridden")
        skipped = values["quality.metrics_skipped"]
        if self.calibration_eligible and (
            self.eligibility_reasons != ("INDEPENDENT_STRUCTURAL_EVIDENCE",)
            or values["quality.iam_complete"] is not True
            or (
                self.rule_family == RuleFamily.DETERMINISTIC_CONFORMANCE
                and not self.channels["static"]
            )
            or (
                (self.rule_family == RuleFamily.STRUCTURAL_GRAPH or self.rule_id == "ARCH003")
                and (not self.channels["graph"] or values["quality.graph_complete"] is not True)
            )
            or (
                self.rule_id == "ARCH105"
                and isinstance(skipped, tuple)
                and "betweenness" in skipped
            )
        ):
            raise ValueError("eligibility must follow actual complete channel evidence")
        if not self.eligibility_reasons:
            raise ValueError("eligibility requires reasons")
        if self.calibration_eligible and (
            self.ai_source != AISource.AI_UNAVAILABLE
            or self.rule_family == RuleFamily.SEMANTIC
            or self.ground_truth_label == Label.UNKNOWN
        ):
            raise ValueError("AI/unreviewed semantic/unknown records cannot enable calibration")
        return self


def join_label(
    materialized: MaterializedEvaluationCase,
    truth: GroundTruthCase,
    repo: BenchmarkRepository,
    dataset_id: str,
    version: str,
    dataset_fingerprint: Digest,
) -> CalibrationTrainingRecord:
    if (
        materialized.anchor.repository_id != truth.repository_id
        or materialized.anchor.rule_id != truth.rule_id
        or materialized.anchor.subjects != truth.subjects
        or repo.repository_id != truth.repository_id
    ):
        raise ValueError("exact anchor/truth join required")
    reasons = []
    bundle = materialized.bundle
    if truth.label == Label.UNKNOWN:
        reasons.append("UNKNOWN_TRUTH")
    if materialized.ai_source != AISource.AI_UNAVAILABLE:
        reasons.append(
            "OFFLINE_CONTRACT_ONLY"
            if materialized.ai_source == AISource.SCRIPTED_TEST
            else "REAL_AI_NOT_VALIDATED"
        )
    if truth.rule_family == RuleFamily.SEMANTIC:
        reasons.append("REAL_AI_AND_REVIEW_REQUIRED")
    if not bundle.completeness.iam_complete:
        reasons.append("INCOMPLETE_IAM")
    if (
        truth.rule_family == RuleFamily.DETERMINISTIC_CONFORMANCE
        and not materialized.static_available
    ):
        reasons.append("STATIC_CHANNEL_UNAVAILABLE")
    if truth.rule_family == RuleFamily.STRUCTURAL_GRAPH and (
        not materialized.graph_available or not bundle.completeness.graph_complete
    ):
        reasons.append("GRAPH_CHANNEL_UNAVAILABLE")
    if (
        truth.rule_id == "ARCH105"
        and bundle.completeness.metrics_skipped
        and "betweenness" in bundle.completeness.metrics_skipped
    ):
        reasons.append("REQUIRED_METRIC_SKIPPED")
    if truth.rule_id == "ARCH003" and not materialized.graph_available:
        reasons.append("GRAPH_CONFORMANCE_UNAVAILABLE")
    features = materialized.features
    return CalibrationTrainingRecord(
        repository_id=repo.repository_id,
        repository_family_id=repo.repository_family_id,
        split=repo.dataset_split,
        case_id=truth.case_id,
        hybrid_case_id=materialized.case.case_id,
        rule_family=truth.rule_family,
        subjects=truth.subjects,
        subject_ids=materialized.resolved_subject_ids,
        feature_schema_version=features.schema_version,
        feature_fingerprint=features.fingerprint,
        features=features,
        ground_truth_label=truth.label,
        annotation_status=truth.annotation_status,
        evidence_availability=tuple(f.availability.value for f in features.values),
        dataset_id=dataset_id,
        dataset_version=version,
        dataset_fingerprint=dataset_fingerprint,
        rule_id=truth.rule_id,
        task={
            RuleFamily.DETERMINISTIC_CONFORMANCE: Task.CONFIRMED_VIOLATION_DETECTION,
            RuleFamily.STRUCTURAL_GRAPH: Task.STRUCTURAL_SIGNAL_RETRIEVAL,
            RuleFamily.SEMANTIC: Task.SEMANTIC_CANDIDATE_DETECTION,
        }[truth.rule_family],
        variant=materialized.variant,
        ai_source=materialized.ai_source,
        calibration_eligible=not reasons,
        eligibility_reasons=tuple(reasons) or ("INDEPENDENT_STRUCTURAL_EVIDENCE",),
        channels={
            "static": materialized.static_available,
            "graph": materialized.graph_available,
            "discovery": materialized.discovery_available,
            "ai": materialized.ai_source != AISource.AI_UNAVAILABLE,
        },
    )


class CalibrationCohort(DomainModel):
    schema_version: Literal["calibration-cohort-v1"] = "calibration-cohort-v1"
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: Digest
    records: tuple[CalibrationTrainingRecord, ...]
    ai_assessments: tuple[AIAssessmentManifest, ...]
    diagnostics: tuple[str, ...] = ()
