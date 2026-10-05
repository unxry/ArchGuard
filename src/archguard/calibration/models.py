"""Immutable research run contracts, separate from portable production inference."""

from typing import Literal, Self

from pydantic import Field, model_validator

from archguard.architecture.hybrid.calibration import (
    FEATURE_SPEC,
    FEATURE_SPEC_V2,
    FeatureSpec,
    PortableStructuralModel,
    StructuralMetrics,
    StructuralPreprocessorArtifact,
)
from archguard.architecture.hybrid.models import Digest
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.benchmark.cohort import CalibrationTrainingRecord
from archguard.benchmark.models import Split
from archguard.core.model.base import DomainModel


class ExperimentManifest(DomainModel):
    experiment_id: Literal["structural-v1"] = "structural-v1"
    version: Literal["1.0.0"] = "1.0.0"
    dataset_version: Literal["1.1.0"] = "1.1.0"
    dataset_fingerprint: Digest
    split_manifest_fingerprint: Digest
    train_fingerprint: Digest
    validation_fingerprint: Digest
    task: Literal["STRUCTURAL_SIGNAL_RETRIEVAL"] = "STRUCTURAL_SIGNAL_RETRIEVAL"
    channels: Literal["STATIC_GRAPH"] = "STATIC_GRAPH"
    feature_spec: FeatureSpec = FEATURE_SPEC
    variant: Literal["STRUCTURAL"] = "STRUCTURAL"
    family_weighting: Literal["equal-family-total; sum-weights=N"] = (
        "equal-family-total; sum-weights=N"
    )
    ridge_alpha: tuple[float, ...] = (0.1, 1.0, 10.0)
    logistic_c: tuple[float, ...] = (0.1, 1.0, 10.0)
    preprocessing: Literal["TRAIN-median; TRAIN-population-standardization; explicit-missing"] = (
        "TRAIN-median; TRAIN-population-standardization; explicit-missing"
    )
    selection_metric: Literal["macro-family-F1"] = "macro-family-F1"
    tie_breaks: Literal[
        "macro-precision; macro-recall; stronger-L2; weighted-before-logistic; lower-threshold"
    ] = "macro-precision; macro-recall; stronger-L2; weighted-before-logistic; lower-threshold"
    thresholds: Literal["unique-score-midpoints-and-outside-boundaries"] = (
        "unique-score-midpoints-and-outside-boundaries"
    )
    seed: Literal[0] = 0
    max_iterations: int = Field(default=200, ge=10, le=200)
    tolerance: float = Field(default=1e-10, gt=0, le=1e-8)
    precision: Literal[12] = 12
    limitation: Literal["SMALL_ENGINEERING_SEED; NOT_FINAL_THESIS_RESULT"] = (
        "SMALL_ENGINEERING_SEED; NOT_FINAL_THESIS_RESULT"
    )

    @model_validator(mode="after")
    def finite_grid(self) -> Self:
        if self.experiment_id == "structural-v1" and self.feature_spec != FEATURE_SPEC:
            raise ValueError("v1 experiment requires historical v1 feature specification")
        for grid in (self.ridge_alpha, self.logistic_c):
            if not 1 <= len(grid) <= 5 or tuple(sorted(set(grid))) != grid or min(grid) <= 0:
                raise ValueError("positive finite ordered preregistered grid required")
        return self

    @property
    def fingerprint(self) -> str:
        return fingerprint(self)


class StructuralV2ExperimentManifest(ExperimentManifest):
    experiment_id: Literal["structural-v2"] = "structural-v2"  # type: ignore[assignment]
    version: Literal["2.0.0"] = "2.0.0"  # type: ignore[assignment]
    feature_spec: Literal["structural-feature-spec-v2"] = FEATURE_SPEC_V2
    excluded_predictors: tuple[str, ...]
    evaluation_policy: Literal["FRESH_INDEPENDENT_FAMILIES_REQUIRED; NO_TEST_ACCESS"] = (
        "FRESH_INDEPENDENT_FAMILIES_REQUIRED; NO_TEST_ACCESS"
    )
    consumed_test_lineage: Literal["dataset-1.1.0/TEST; consumed by structural-v1"] = (
        "dataset-1.1.0/TEST; consumed by structural-v1"
    )
    consumed_by_artifact: Literal[
        "fdbb6eaeeb2e7099265c391c05b4996fb264d1f0398d1112be8b5012392d8395"
    ] = "fdbb6eaeeb2e7099265c391c05b4996fb264d1f0398d1112be8b5012392d8395"
    terminology: Literal["GRAPH STRUCTURAL META-CLASSIFIER"] = "GRAPH STRUCTURAL META-CLASSIFIER"
    model_family_tie_break: Literal["DETERMINISTIC_ADMINISTRATIVE_PREFERENCE"] = (
        "DETERMINISTIC_ADMINISTRATIVE_PREFERENCE"
    )

    @model_validator(mode="after")
    def excluded_decisions(self) -> Self:
        if self.excluded_predictors != V2_EXCLUDED_PREDICTORS:
            raise ValueError("v2 exclusions must match preregistered leakage audit")
        return self


V2_EXCLUDED_PREDICTORS = (
    "selection.candidate_present",
    "graph.candidate_rules",
    "graph.ARCH101-105",
    "GraphCandidate flags and threshold decisions",
    "configured thresholds",
    "rule IDs and Finding labels",
    "ground-truth labels, annotation status and rationale",
    "split, case, repository, family and node identities",
    "names and paths",
)
Experiment = ExperimentManifest | StructuralV2ExperimentManifest


class PrimaryCohort(DomainModel):
    split: Split
    records: tuple[CalibrationTrainingRecord, ...]
    fingerprint: Digest
    excluded_records: int

    @property
    def families(self) -> tuple[str, ...]:
        return tuple(sorted({fingerprint(r.repository_family_id) for r in self.records}))


class TrainingRunResult(DomainModel):
    schema_version: Literal["structural-training-v1"] = "structural-training-v1"
    experiment: Experiment = Field(discriminator="experiment_id")
    experiment_fingerprint: Digest
    train_fingerprint: Digest
    train_families: tuple[str, ...]
    train_cases: int
    train_positive: int
    train_negative: int
    preprocessor: StructuralPreprocessorArtifact
    candidates: tuple[PortableStructuralModel, ...]
    tool_versions: tuple[tuple[str, str], ...]
    fingerprint: Digest

    @model_validator(mode="after")
    def sealed(self) -> Self:
        expected = tuple(("WEIGHTED_LINEAR", a) for a in self.experiment.ridge_alpha) + tuple(
            ("LOGISTIC_REGRESSION", round(1 / c, 12)) for c in self.experiment.logistic_c
        )
        if (
            self.experiment_fingerprint != self.experiment.fingerprint
            or self.train_fingerprint != self.experiment.train_fingerprint
            or self.fingerprint
            != fingerprint(self.model_dump(mode="json", exclude={"fingerprint"}))
            or tuple((m.family, m.regularization) for m in self.candidates) != expected
            or any(m.feature_order != self.preprocessor.output_features for m in self.candidates)
            or self.preprocessor.feature_spec != self.experiment.feature_spec
            or self.train_positive + self.train_negative != self.train_cases
            or not self.train_positive
            or not self.train_negative
            or len(self.train_families) < 2
        ):
            raise ValueError("training run manifest/provenance/model mismatch")
        return self


class CandidateValidation(DomainModel):
    model: PortableStructuralModel
    threshold: float
    metrics: StructuralMetrics
    thresholds_evaluated: int


class ModelSelectionReport(DomainModel):
    schema_version: Literal["structural-selection-v1"] = "structural-selection-v1"
    training: TrainingRunResult
    validation_fingerprint: Digest
    validation_families: tuple[str, ...]
    validation_cases: int
    validation_positive: int
    validation_negative: int
    candidates: tuple[CandidateValidation, ...]
    chosen_index: int
    tie_break_reason: str
    fingerprint: Digest

    @model_validator(mode="after")
    def sealed(self) -> Self:
        if (
            self.fingerprint != fingerprint(self.model_dump(mode="json", exclude={"fingerprint"}))
            or self.validation_fingerprint != self.training.experiment.validation_fingerprint
            or not 0 <= self.chosen_index < len(self.candidates)
            or tuple(c.model for c in self.candidates) != self.training.candidates
            or set(self.validation_families) & set(self.training.train_families)
            or not self.validation_positive
            or not self.validation_negative
            or self.validation_positive + self.validation_negative != self.validation_cases
        ):
            raise ValueError("selection report provenance/candidates mismatch")
        return self


class HeldoutEvaluationResult(DomainModel):
    status: Literal["ENGINEERING_SEED_HELDOUT_EVALUATION"] = "ENGINEERING_SEED_HELDOUT_EVALUATION"
    artifact_fingerprint: Digest
    experiment_fingerprint: Digest
    test_fingerprint: Digest
    cases: int
    positive: int
    negative: int
    metrics: StructuralMetrics
    limitation: Literal["SMALL_ENGINEERING_SEED; NOT_FINAL_THESIS_RESULT"] = (
        "SMALL_ENGINEERING_SEED; NOT_FINAL_THESIS_RESULT"
    )


class DirectGraphBaselineResult(DomainModel):
    schema_version: Literal["direct-graph-rule-baseline-v1"] = "direct-graph-rule-baseline-v1"
    experiment_fingerprint: Digest
    train_fingerprint: Digest
    validation_fingerprint: Digest
    train_cases: int
    validation_cases: int
    train_metrics: StructuralMetrics
    validation_metrics: StructuralMetrics
    predictor: Literal["metadata-only: selection.candidate_present"] = (
        "metadata-only: selection.candidate_present"
    )
    interpretation: Literal["DESCRIPTIVE_RULE_REPLAY; NO_ML_ADDED_VALUE_CLAIM"] = (
        "DESCRIPTIVE_RULE_REPLAY; NO_ML_ADDED_VALUE_CLAIM"
    )
    fingerprint: Digest

    @model_validator(mode="after")
    def sealed(self) -> Self:
        if self.fingerprint != fingerprint(self.model_dump(mode="json", exclude={"fingerprint"})):
            raise ValueError("baseline fingerprint mismatch")
        return self
