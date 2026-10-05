"""TRAIN fitting, VALIDATION selection and frozen TEST evaluation are separate APIs."""

import math
import statistics
from collections import Counter
from typing import Any

from archguard import __version__
from archguard.architecture.hybrid.calibration import (
    FEATURE_SPEC,
    FEATURE_SPEC_V2,
    DroppedFeature,
    FamilyMetric,
    FeatureSpec,
    FrozenStructuralHybridPolicyArtifact,
    MetricValues,
    PortableStructuralModel,
    PreprocessorColumn,
    StructuralCalibrationError,
    StructuralMetrics,
    StructuralPreprocessorArtifact,
    feature_names,
    numeric_values,
)
from archguard.architecture.hybrid.serialization import canonical, fingerprint
from archguard.benchmark.cohort import CalibrationTrainingRecord
from archguard.benchmark.materialization import AISource, CohortVariant
from archguard.benchmark.models import Label, RuleFamily, Split, Task
from archguard.calibration.models import (
    CandidateValidation,
    DirectGraphBaselineResult,
    Experiment,
    HeldoutEvaluationResult,
    ModelSelectionReport,
    PrimaryCohort,
    TrainingRunResult,
)
from archguard.calibration.numeric import fit_coefficients
from archguard.core.model.base import DomainModel


def seal[T: DomainModel](contract: type[T], **values: Any) -> T:
    provisional = contract.model_construct(**values)
    payload = provisional.model_dump(mode="json", exclude={"fingerprint", "artifact_id"})
    digest = fingerprint(payload)
    payload["fingerprint"] = digest
    if contract is FrozenStructuralHybridPolicyArtifact:
        payload["artifact_id"] = "structural-policy:" + digest
    return contract.model_validate_json(canonical(payload))


def primary_cohort(
    records: tuple[CalibrationTrainingRecord, ...], split: Split, experiment: Experiment
) -> PrimaryCohort:
    assert_split_allowed(split, experiment)
    selected = []
    seen = set()
    for raw in records:
        row = CalibrationTrainingRecord.model_validate_json(canonical(raw))
        if (
            row.split != split
            or row.dataset_fingerprint != experiment.dataset_fingerprint
            or row.dataset_version != experiment.dataset_version
        ):
            raise StructuralCalibrationError("split/dataset fingerprint mismatch")
        key = (row.case_id, row.variant)
        if key in seen:
            raise StructuralCalibrationError("duplicate calibration case/profile")
        seen.add(key)
        if row.task != Task.STRUCTURAL_SIGNAL_RETRIEVAL or row.variant != CohortVariant.STRUCTURAL:
            continue
        if not row.calibration_eligible:
            continue
        if (
            row.ai_source != AISource.AI_UNAVAILABLE
            or row.rule_family != RuleFamily.STRUCTURAL_GRAPH
        ):
            raise StructuralCalibrationError("AI or different-task evidence cannot enter fitting")
        selected.append(row)
    ordered = tuple(sorted(selected, key=lambda r: (r.repository_id, str(r.case_id))))
    if {r.ground_truth_label for r in ordered} != {Label.POSITIVE, Label.NEGATIVE} or len(
        {r.repository_family_id for r in ordered}
    ) < (2 if split == Split.TRAIN else 1):
        raise StructuralCalibrationError(
            "primary cohort needs independent families and both classes"
        )
    primary = PrimaryCohort(
        split=split,
        records=ordered,
        fingerprint=fingerprint(ordered_dump(ordered)),
        excluded_records=len(records) - len(ordered),
    )
    expected = (
        experiment.train_fingerprint
        if split == Split.TRAIN
        else experiment.validation_fingerprint
        if split == Split.VALIDATION
        else None
    )
    if expected is not None and primary.fingerprint != expected:
        raise StructuralCalibrationError(
            "primary cohort changed from preregistered split fingerprint"
        )
    return primary


def ordered_dump(records: tuple[CalibrationTrainingRecord, ...]) -> list[dict[str, object]]:
    return [r.model_dump(mode="json") for r in records]


def assert_split_allowed(split: Split, experiment: Experiment) -> None:
    if split == Split.TEST and experiment.feature_spec == FEATURE_SPEC_V2:
        raise StructuralCalibrationError(
            "TEST_REUSE_FORBIDDEN: dataset-1.1 TEST consumed by v1; "
            "AWAITING_FRESH_HOLDOUT requires new independent lineage and protocol"
        )


def assert_evaluation_allowed(
    artifact: FrozenStructuralHybridPolicyArtifact, experiment: Experiment
) -> None:
    if artifact.preprocessor.feature_spec == FEATURE_SPEC_V2:
        raise StructuralCalibrationError("TEST_REUSE_FORBIDDEN: v2 AWAITING_FRESH_HOLDOUT")
    assert_split_allowed(Split.TEST, experiment)


def values(
    row: CalibrationTrainingRecord, spec: FeatureSpec = FEATURE_SPEC
) -> dict[str, float | None]:
    return numeric_values({f.name: f.value for f in row.features.values}, spec)


def family_weights(cohort: PrimaryCohort) -> tuple[float, ...]:
    counts = Counter(r.repository_family_id for r in cohort.records)
    return tuple(
        len(cohort.records) / (len(counts) * counts[r.repository_family_id]) for r in cohort.records
    )


def fit_preprocessor(
    train: PrimaryCohort, spec: FeatureSpec = FEATURE_SPEC
) -> StructuralPreprocessorArtifact:
    if train.split != Split.TRAIN:
        raise StructuralCalibrationError("preprocessing fit accepts TRAIN only")
    rows = tuple(values(r, spec) for r in train.records)
    columns = []
    dropped = []
    output = []
    for name in feature_names(spec):
        observed = [value for r in rows if (value := r[name]) is not None]
        if not observed:
            dropped.append(DroppedFeature(name=name, reason="ALL_MISSING_ON_TRAIN"))
            continue
        median = float(statistics.median(observed))
        imputed = [median if (value := r[name]) is None else value for r in rows]
        mean = math.fsum(imputed) / len(imputed)
        variance = math.fsum((v - mean) ** 2 for v in imputed) / len(imputed)
        missing = {r[name] is None for r in rows}
        if variance == 0 and len(missing) == 1:
            dropped.append(DroppedFeature(name=name, reason="CONSTANT_ON_TRAIN"))
            continue
        keep = variance > 0
        columns.append(
            PreprocessorColumn(
                name=name,
                median=median,
                mean=mean,
                scale=math.sqrt(variance) if keep else 1.0,
                keep_value=keep,
            )
        )
        if keep:
            output.append(name)
        output.append(name + ".missing")
    return seal(
        StructuralPreprocessorArtifact,
        feature_spec=spec,
        selected_features=feature_names(spec),
        columns=tuple(columns),
        dropped_features=tuple(dropped),
        output_features=tuple(output),
    )


def train_models(train: PrimaryCohort, experiment: Experiment) -> TrainingRunResult:
    if train.split != Split.TRAIN:
        raise StructuralCalibrationError("training accepts TRAIN only; no TEST input")
    # Validate even direct API callers, independently of file adapters.
    train = primary_cohort(train.records, Split.TRAIN, experiment)
    preprocessor = fit_preprocessor(train, experiment.feature_spec)
    x = tuple(preprocessor.transform(values(r, experiment.feature_spec)) for r in train.records)
    y = tuple(int(r.ground_truth_label == Label.POSITIVE) for r in train.records)
    weights = family_weights(train)
    candidates = []
    for family, grid in (
        ("WEIGHTED_LINEAR", experiment.ridge_alpha),
        ("LOGISTIC_REGRESSION", experiment.logistic_c),
    ):
        logistic = family == "LOGISTIC_REGRESSION"
        for hyperparameter in grid:
            l2 = 1 / hyperparameter if logistic else hyperparameter
            coefficients, intercept, iterations = fit_coefficients(
                x,
                y,
                weights,
                l2,
                logistic=logistic,
                max_iterations=experiment.max_iterations,
                tolerance=experiment.tolerance,
            )
            model = PortableStructuralModel(
                family="LOGISTIC_REGRESSION" if logistic else "WEIGHTED_LINEAR",
                regularization=l2,
                feature_order=preprocessor.output_features,
                coefficients=coefficients,
                intercept=intercept,
                solver="weighted-logistic-newton-v1" if logistic else "weighted-ridge-pivot-v1",
                iterations=iterations,
                replay_max_error=0.0,
            )
            portable = PortableStructuralModel.model_validate_json(canonical(model))
            error = max(abs(model.score(row) - portable.score(row)) for row in x)
            if error > 1e-9:
                raise StructuralCalibrationError("canonical precision changed inference")
            candidates.append(portable.model_copy(update={"replay_max_error": error}))
    return seal(
        TrainingRunResult,
        experiment=experiment,
        experiment_fingerprint=experiment.fingerprint,
        train_fingerprint=train.fingerprint,
        train_families=train.families,
        train_cases=len(y),
        train_positive=sum(y),
        train_negative=len(y) - sum(y),
        preprocessor=preprocessor,
        candidates=tuple(candidates),
        tool_versions=(
            ("archguard", __version__),
            ("numeric-solver", "native-python-v1"),
            ("coefficient-decimal-places", "12"),
        ),
    )


def metric_values(tp: int, fp: int, fn: int, tn: int) -> MetricValues:
    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    return MetricValues(
        precision=ratio(tp, tp + fp),
        recall=ratio(tp, tp + fn),
        f1=ratio(2 * tp, 2 * tp + fp + fn),
        fpr=ratio(fp, fp + tn),
        fnr=ratio(fn, fn + tp),
        coverage=1.0,
    )


def measure(
    cohort: PrimaryCohort, scores: tuple[float, ...], threshold: float
) -> StructuralMetrics:
    if len(scores) != len(cohort.records) or any(not math.isfinite(s) for s in scores):
        raise StructuralCalibrationError("score/primary cohort mismatch")
    buckets: dict[str, list[int]] = {}
    for row, score in zip(cohort.records, scores, strict=True):
        positive = row.ground_truth_label == Label.POSITIVE
        predicted = score >= threshold
        counts = buckets.setdefault(fingerprint(row.repository_family_id), [0, 0, 0, 0])
        counts[0 if positive and predicted else 1 if predicted else 2 if positive else 3] += 1
    families = tuple(
        FamilyMetric(
            family_fingerprint=f, tp=c[0], fp=c[1], fn=c[2], tn=c[3], metrics=metric_values(*c)
        )
        for f, c in sorted(buckets.items())
    )
    totals = [sum(c[i] for c in buckets.values()) for i in range(4)]
    macro: dict[str, float | None] = {}
    for name in MetricValues.model_fields:
        defined = [value for f in families if (value := getattr(f.metrics, name)) is not None]
        macro[name] = math.fsum(defined) / len(defined) if defined else None
    return StructuralMetrics(
        tp=totals[0],
        fp=totals[1],
        fn=totals[2],
        tn=totals[3],
        micro=metric_values(*totals),
        macro_family=MetricValues.model_validate(macro),
        per_family=families,
    )


def scores(
    model: PortableStructuralModel,
    preprocessor: StructuralPreprocessorArtifact,
    cohort: PrimaryCohort,
) -> tuple[float, ...]:
    return tuple(
        model.score(preprocessor.transform(values(r, preprocessor.feature_spec)))
        for r in cohort.records
    )


def threshold_candidates(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(set(values))
    if not ordered or any(not math.isfinite(s) for s in ordered):
        raise StructuralCalibrationError("finite validation scores required")
    margin = max(1.0, abs(ordered[0]), abs(ordered[-1])) * 1e-6
    return tuple(
        sorted(
            {
                round(v, 12)
                for v in [
                    ordered[0] - margin,
                    *(a + (b - a) / 2 for a, b in zip(ordered, ordered[1:], strict=False)),
                    ordered[-1] + margin,
                ]
            }
        )
    )


def rank(candidate: CandidateValidation) -> tuple[float, ...]:
    m = candidate.metrics.macro_family
    return (
        m.f1 if m.f1 is not None else -1,
        m.precision if m.precision is not None else -1,
        m.recall if m.recall is not None else -1,
        candidate.model.regularization,
        float(candidate.model.family == "WEIGHTED_LINEAR"),
        -candidate.threshold,
    )


def select_model(training: TrainingRunResult, validation: PrimaryCohort) -> ModelSelectionReport:
    training = TrainingRunResult.model_validate(training)
    if validation.split != Split.VALIDATION:
        raise StructuralCalibrationError("selection accepts VALIDATION only; no TEST metrics")
    validation = primary_cohort(validation.records, Split.VALIDATION, training.experiment)
    if set(validation.families) & set(training.train_families):
        raise StructuralCalibrationError("TRAIN/VALIDATION family leakage")
    candidates = []
    for model in training.candidates:
        predictions = scores(model, training.preprocessor, validation)
        thresholds = threshold_candidates(predictions)
        options = tuple(
            CandidateValidation(
                model=model,
                threshold=t,
                metrics=measure(validation, predictions, t),
                thresholds_evaluated=len(thresholds),
            )
            for t in thresholds
        )
        candidates.append(max(options, key=rank))
    chosen = max(range(len(candidates)), key=lambda i: rank(candidates[i]))
    return seal(
        ModelSelectionReport,
        training=training,
        validation_fingerprint=validation.fingerprint,
        validation_families=validation.families,
        validation_cases=len(validation.records),
        validation_positive=sum(r.ground_truth_label == Label.POSITIVE for r in validation.records),
        validation_negative=sum(r.ground_truth_label == Label.NEGATIVE for r in validation.records),
        candidates=tuple(candidates),
        chosen_index=chosen,
        tie_break_reason=training.experiment.tie_breaks,
    )


def freeze(selection: ModelSelectionReport) -> FrozenStructuralHybridPolicyArtifact:
    selection = ModelSelectionReport.model_validate(selection)
    if selection.chosen_index != max(
        range(len(selection.candidates)), key=lambda i: rank(selection.candidates[i])
    ):
        raise StructuralCalibrationError("winner violates preregistered selection rank")
    train = selection.training
    chosen = selection.candidates[selection.chosen_index]
    return seal(
        FrozenStructuralHybridPolicyArtifact,
        schema_version=(
            "frozen-structural-policy-v2"
            if train.experiment.feature_spec == FEATURE_SPEC_V2
            else "frozen-structural-policy-v1"
        ),
        artifact_version="2.0.0" if train.experiment.feature_spec == FEATURE_SPEC_V2 else "1.0.0",
        status=(
            "AWAITING_FRESH_HOLDOUT"
            if train.experiment.feature_spec == FEATURE_SPEC_V2
            else "FROZEN"
        ),
        dataset_fingerprint=train.experiment.dataset_fingerprint,
        split_manifest_fingerprint=train.experiment.split_manifest_fingerprint,
        train_fingerprint=train.train_fingerprint,
        validation_fingerprint=selection.validation_fingerprint,
        train_families=train.train_families,
        validation_families=selection.validation_families,
        experiment_fingerprint=train.experiment_fingerprint,
        selection_fingerprint=selection.fingerprint,
        preprocessor=train.preprocessor,
        model=chosen.model,
        threshold=chosen.threshold,
        validation_metrics=chosen.metrics,
        train_cases=train.train_cases,
        train_positive=train.train_positive,
        train_negative=train.train_negative,
        tool_versions=train.tool_versions,
    )


def evaluate_frozen(
    artifact: FrozenStructuralHybridPolicyArtifact,
    test: PrimaryCohort,
    experiment: Experiment,
) -> HeldoutEvaluationResult:
    assert_evaluation_allowed(artifact, experiment)
    artifact = FrozenStructuralHybridPolicyArtifact.model_validate(artifact)
    if test.split != Split.TEST:
        raise StructuralCalibrationError("held-out evaluation accepts TEST only")
    if (
        artifact.experiment_fingerprint != experiment.fingerprint
        or artifact.dataset_fingerprint != experiment.dataset_fingerprint
        or artifact.split_manifest_fingerprint != experiment.split_manifest_fingerprint
    ):
        raise StructuralCalibrationError("frozen experiment/dataset mismatch")
    test = primary_cohort(test.records, Split.TEST, experiment)
    if set(test.families) & set(artifact.train_families + artifact.validation_families):
        raise StructuralCalibrationError("TEST family leakage")
    return HeldoutEvaluationResult(
        artifact_fingerprint=artifact.fingerprint,
        experiment_fingerprint=experiment.fingerprint,
        test_fingerprint=test.fingerprint,
        cases=len(test.records),
        positive=sum(r.ground_truth_label == Label.POSITIVE for r in test.records),
        negative=sum(r.ground_truth_label == Label.NEGATIVE for r in test.records),
        metrics=measure(
            test, scores(artifact.model, artifact.preprocessor, test), artifact.threshold
        ),
    )


def direct_graph_baseline(
    train: PrimaryCohort, validation: PrimaryCohort, experiment: Experiment
) -> DirectGraphBaselineResult:
    if train.split != Split.TRAIN or validation.split != Split.VALIDATION:
        raise StructuralCalibrationError("baseline accepts TRAIN/VALIDATION only")
    train = primary_cohort(train.records, Split.TRAIN, experiment)
    validation = primary_cohort(validation.records, Split.VALIDATION, experiment)
    if set(train.families) & set(validation.families):
        raise StructuralCalibrationError("baseline TRAIN/VALIDATION family leakage")

    def replay(cohort: PrimaryCohort) -> StructuralMetrics:
        predictions = []
        for row in cohort.records:
            present = next(
                f.value for f in row.features.values if f.name == "selection.candidate_present"
            )
            if not isinstance(present, bool):
                raise StructuralCalibrationError("baseline requires actual candidate metadata")
            predictions.append(float(present))
        return measure(cohort, tuple(predictions), 0.5)

    return seal(
        DirectGraphBaselineResult,
        experiment_fingerprint=experiment.fingerprint,
        train_fingerprint=train.fingerprint,
        validation_fingerprint=validation.fingerprint,
        train_cases=len(train.records),
        validation_cases=len(validation.records),
        train_metrics=replay(train),
        validation_metrics=replay(validation),
    )
