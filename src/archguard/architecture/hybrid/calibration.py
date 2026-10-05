"""Portable structural inference contracts. No benchmark, fitting or estimator dependency."""

import math
from collections.abc import Mapping
from typing import Literal, Self
from uuid import uuid5

from pydantic import Field, model_validator

from archguard.architecture.hybrid.features import VERSION, feature_schema
from archguard.architecture.hybrid.models import (
    CalibrationStatus,
    Digest,
    HybridCase,
    HybridCaseType,
    HybridDecision,
    HybridDecisionState,
    HybridEvidenceBundle,
    HybridFeatureVector,
    HybridPolicyMetadata,
)
from archguard.architecture.hybrid.policies import DeterministicPrecedencePolicy, HybridPolicyError
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.core.model.base import DomainModel

FEATURE_SPEC: Literal["structural-calibration-features-v1"] = "structural-calibration-features-v1"
FEATURE_NAMES = (
    "graph.Ca",
    "graph.Ce",
    "graph.coupling",
    "graph.I",
    "graph.scc_size",
    "graph.betweenness",
    "graph.pagerank",
    "graph.cyclic",
    "graph.source.Ca",
    "graph.source.Ce",
    "graph.source.I",
    "graph.target.Ca",
    "graph.target.Ce",
    "graph.target.I",
    "selection.candidate_present",
    "quality.unresolved",
)
FEATURE_SPEC_V2: Literal["structural-feature-spec-v2"] = "structural-feature-spec-v2"
FeatureSpec = Literal["structural-calibration-features-v1", "structural-feature-spec-v2"]
FEATURE_NAMES_V2 = tuple(n for n in FEATURE_NAMES if n != "selection.candidate_present")


def feature_names(spec: FeatureSpec) -> tuple[str, ...]:
    return FEATURE_NAMES_V2 if spec == FEATURE_SPEC_V2 else FEATURE_NAMES


class StructuralCalibrationError(HybridPolicyError):
    code = "INCOMPATIBLE_STRUCTURAL_CALIBRATION"


class PreprocessorColumn(DomainModel):
    name: str
    median: float
    mean: float
    scale: float = Field(gt=0)
    keep_value: bool
    missing_indicator: Literal[True] = True


class DroppedFeature(DomainModel):
    name: str
    reason: Literal["ALL_MISSING_ON_TRAIN", "CONSTANT_ON_TRAIN"]


class StructuralPreprocessorArtifact(DomainModel):
    schema_version: Literal["structural-preprocessor-v1"] = "structural-preprocessor-v1"
    input_schema: Literal["calibration-evidence-v1"] = "calibration-evidence-v1"
    feature_spec: FeatureSpec = FEATURE_SPEC
    selected_features: tuple[str, ...] = FEATURE_NAMES
    columns: tuple[PreprocessorColumn, ...]
    dropped_features: tuple[DroppedFeature, ...]
    output_features: tuple[str, ...]
    fingerprint: Digest

    @model_validator(mode="after")
    def coherent(self) -> Self:
        whitelist = feature_names(self.feature_spec)
        names = tuple(c.name for c in self.columns)
        dropped = tuple(d.name for d in self.dropped_features)
        expected = tuple(
            name
            for c in self.columns
            for name in ((c.name,) if c.keep_value else ()) + (c.name + ".missing",)
        )
        if (
            self.selected_features != whitelist
            or len(set(names + dropped)) != len(whitelist)
            or set(names + dropped) != set(whitelist)
            or names != tuple(n for n in whitelist if n in names)
            or self.output_features != expected
            or not expected
            or self.fingerprint
            != fingerprint(self.model_dump(mode="json", exclude={"fingerprint"}))
        ):
            raise ValueError("preprocessor schema/order/fingerprint mismatch")
        return self

    def transform(self, values: dict[str, float | None]) -> tuple[float, ...]:
        if tuple(values) != self.selected_features:
            raise StructuralCalibrationError("explicit structural whitelist/order required")
        result = []
        for c in self.columns:
            value = values[c.name]
            if value is not None and not math.isfinite(value):
                raise StructuralCalibrationError("nonfinite feature")
            if c.keep_value:
                result.append(((c.median if value is None else value) - c.mean) / c.scale)
            result.append(float(value is None))
        return tuple(result)


class PortableStructuralModel(DomainModel):
    family: Literal["WEIGHTED_LINEAR", "LOGISTIC_REGRESSION"]
    regularization: float = Field(gt=0)
    feature_order: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    solver: Literal["weighted-ridge-pivot-v1", "weighted-logistic-newton-v1"]
    iterations: int = Field(ge=1, le=200)
    converged: Literal[True] = True
    replay_max_error: float = Field(ge=0, le=1e-9)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if not self.coefficients or len(self.coefficients) != len(self.feature_order):
            raise ValueError("coefficient order/length mismatch")
        if (self.family == "WEIGHTED_LINEAR") != (self.solver == "weighted-ridge-pivot-v1"):
            raise ValueError("model/solver mismatch")
        return self

    def score(self, vector: tuple[float, ...]) -> float:
        if len(vector) != len(self.coefficients) or any(not math.isfinite(x) for x in vector):
            raise StructuralCalibrationError("portable model vector mismatch")
        z = self.intercept + math.fsum(
            w * x for w, x in zip(self.coefficients, vector, strict=True)
        )
        return stable_sigmoid(z) if self.family == "LOGISTIC_REGRESSION" else z


def stable_sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


class MetricValues(DomainModel):
    precision: float | None
    recall: float | None
    f1: float | None
    fpr: float | None
    fnr: float | None
    coverage: float


class FamilyMetric(DomainModel):
    family_fingerprint: Digest
    tp: int
    fp: int
    fn: int
    tn: int
    metrics: MetricValues


class StructuralMetrics(DomainModel):
    tp: int
    fp: int
    fn: int
    tn: int
    micro: MetricValues
    macro_family: MetricValues
    per_family: tuple[FamilyMetric, ...]
    undefined_policy: Literal["mean-defined-families; all-undefined=null"] = (
        "mean-defined-families; all-undefined=null"
    )


class FrozenStructuralHybridPolicyArtifact(DomainModel):
    schema_version: Literal["frozen-structural-policy-v1", "frozen-structural-policy-v2"] = (
        "frozen-structural-policy-v1"
    )
    artifact_version: Literal["1.0.0", "2.0.0"] = "1.0.0"
    status: Literal["FROZEN", "AWAITING_FRESH_HOLDOUT"] = "FROZEN"
    task: Literal["STRUCTURAL_SIGNAL_RETRIEVAL"] = "STRUCTURAL_SIGNAL_RETRIEVAL"
    calibration_status: Literal["DECISION_THRESHOLD_CALIBRATED"] = "DECISION_THRESHOLD_CALIBRATED"
    dataset_fingerprint: Digest
    dataset_version: Literal["1.1.0"] = "1.1.0"
    split_manifest_fingerprint: Digest
    train_fingerprint: Digest
    validation_fingerprint: Digest
    train_families: tuple[Digest, ...]
    validation_families: tuple[Digest, ...]
    experiment_fingerprint: Digest
    selection_fingerprint: Digest
    feature_schema_version: Literal["calibration-evidence-v1"] = "calibration-evidence-v1"
    preprocessor: StructuralPreprocessorArtifact
    model: PortableStructuralModel
    threshold: float
    selection_metric: Literal["macro-family-F1"] = "macro-family-F1"
    validation_metrics: StructuralMetrics
    train_cases: int = Field(gt=0)
    train_positive: int = Field(gt=0)
    train_negative: int = Field(gt=0)
    family_weighting: Literal["equal-family-total; sum-weights=N"] = (
        "equal-family-total; sum-weights=N"
    )
    seed: Literal[0] = 0
    tool_versions: tuple[tuple[str, str], ...]
    limitation: Literal["SMALL_ENGINEERING_SEED; NOT_FINAL_THESIS_RESULT"] = (
        "SMALL_ENGINEERING_SEED; NOT_FINAL_THESIS_RESULT"
    )
    artifact_id: str
    fingerprint: Digest

    @model_validator(mode="after")
    def coherent(self) -> Self:
        digest = fingerprint(self.model_dump(mode="json", exclude={"fingerprint", "artifact_id"}))
        if (
            (self.schema_version, self.artifact_version, self.status)
            != (
                ("frozen-structural-policy-v2", "2.0.0", "AWAITING_FRESH_HOLDOUT")
                if self.preprocessor.feature_spec == FEATURE_SPEC_V2
                else ("frozen-structural-policy-v1", "1.0.0", "FROZEN")
            )
            or self.fingerprint != digest
            or self.artifact_id != "structural-policy:" + digest
            or self.model.feature_order != self.preprocessor.output_features
            or self.train_positive + self.train_negative != self.train_cases
            or len(set(self.train_families)) < 2
            or not self.validation_families
            or set(self.train_families) & set(self.validation_families)
        ):
            raise ValueError("frozen artifact provenance/order/fingerprint mismatch")
        return self


def runtime_values(
    case: HybridCase,
    evidence: HybridEvidenceBundle,
    features: HybridFeatureVector,
    spec: FeatureSpec = FEATURE_SPEC,
) -> dict[str, float | None]:
    if features.schema_version != VERSION or tuple(f.name for f in features.values) != tuple(
        d.name for d in feature_schema().definitions
    ):
        raise StructuralCalibrationError("runtime feature schema mismatch")
    values = {f.name: f.value for f in features.values}
    if spec == FEATURE_SPEC:
        values["selection.candidate_present"] = case.origin == "GRAPH" or any(
            s.candidate_id in case.anchor_ids and s.rule_id == case.rule_id for s in evidence.graph
        )
    pair = case.subject_pairs[0] if case.subject_pairs else None
    for side in ("source", "target"):
        subject = (pair.source_id if side == "source" else pair.target_id) if pair else None
        measurement = next(
            (m for m in evidence.graph_measurements if m.subject_id == subject), None
        )
        for name, attribute in (
            ("Ca", "afferent_coupling"),
            ("Ce", "efferent_coupling"),
            ("I", "instability"),
        ):
            values[f"graph.{side}.{name}"] = (
                getattr(measurement.metrics, attribute) if measurement else None
            )
    return numeric_values(values, spec)


def numeric_values(
    values: Mapping[str, object], spec: FeatureSpec = FEATURE_SPEC
) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for name in feature_names(spec):
        value = values[name]
        if value is not None and not isinstance(value, (int, float, bool)):
            raise StructuralCalibrationError("whitelisted features must be numeric or missing")
        result[name] = round(float(value), 12) if value is not None else None
    return result


class CalibratedStructuralHybridPolicy:
    def __init__(
        self,
        artifact: FrozenStructuralHybridPolicyArtifact,
        *,
        expected_dataset_fingerprint: str | None = None,
        expected_train_fingerprint: str | None = None,
    ) -> None:
        self.artifact = FrozenStructuralHybridPolicyArtifact.model_validate(artifact)
        if (
            expected_dataset_fingerprint is not None
            and self.artifact.dataset_fingerprint != expected_dataset_fingerprint
            or expected_train_fingerprint is not None
            and self.artifact.train_fingerprint != expected_train_fingerprint
        ):
            raise StructuralCalibrationError("approved dataset/TRAIN fingerprint mismatch")
        self.precedence = DeterministicPrecedencePolicy()

    @property
    def metadata(self) -> HybridPolicyMetadata:
        return HybridPolicyMetadata(
            policy_id="calibrated-structural:" + self.artifact.fingerprint,
            policy_version=self.artifact.artifact_version,
            feature_schema_version=VERSION,
            calibration_status=CalibrationStatus.CALIBRATED,
        )

    def decide(
        self, case: HybridCase, evidence: HybridEvidenceBundle, features: HybridFeatureVector
    ) -> HybridDecision:
        if evidence.static:
            return self.precedence.decide(case, evidence, features).model_copy(
                update={"policy": self.metadata}
            )
        if case.rule_id not in {
            "ARCH101",
            "ARCH102",
            "ARCH103",
            "ARCH104",
            "ARCH105",
        } or case.case_type not in {HybridCaseType.GRAPH_STRUCTURAL, HybridCaseType.COMPOSITE}:
            raise StructuralCalibrationError("structural policy accepts ARCH101–105 only")
        if evidence.ai:
            raise StructuralCalibrationError("FULL_HYBRID_NOT_READY: AI evidence excluded")
        score = self.artifact.model.score(
            self.artifact.preprocessor.transform(
                runtime_values(case, evidence, features, self.artifact.preprocessor.feature_spec)
            )
        )
        state = (
            HybridDecisionState.STRUCTURAL_SIGNAL_SUPPORTED
            if score >= self.artifact.threshold
            else HybridDecisionState.STRUCTURAL_SIGNAL_NOT_SUPPORTED
        )
        bundle_hash = fingerprint(evidence)
        return HybridDecision(
            decision_id=uuid5(
                case.case_id, self.artifact.fingerprint + features.fingerprint + bundle_hash
            ),
            case_id=case.case_id,
            state=state,
            policy=self.metadata,
            calibration_status=CalibrationStatus.CALIBRATED,
            feature_fingerprint=features.fingerprint,
            evidence_fingerprint=bundle_hash,
            reason_codes=("ENGINEERING_SEED_CALIBRATED_STRUCTURAL_SIGNAL",),
            supporting_refs=tuple(
                f"graph-metric:{m.subject_id}" for m in evidence.graph_measurements
            ),
            contradicting_refs=(),
            missing_refs=(),
            model_score=score,
            model_artifact_fingerprint=self.artifact.fingerprint,
        )
