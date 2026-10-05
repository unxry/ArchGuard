"""Actual TRAIN/VALIDATION fixtures; TEST isolation checks use synthetic unit rows."""

import inspect
import json
import math
from collections import defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.architecture.hybrid.analyzer import HybridAnalyzer
from archguard.architecture.hybrid.calibration import (
    FEATURE_NAMES,
    CalibratedStructuralHybridPolicy,
    FrozenStructuralHybridPolicyArtifact,
    PortableStructuralModel,
    StructuralCalibrationError,
    numeric_values,
    runtime_values,
    stable_sigmoid,
)
from archguard.architecture.hybrid.models import (
    FeatureAvailability,
    FeatureValueType,
    HybridDecisionState,
)
from archguard.architecture.hybrid.serialization import canonical, fingerprint
from archguard.benchmark.cohort import CalibrationTrainingRecord, join_label
from archguard.benchmark.materialization import (
    CohortVariant,
    EvaluationAnchor,
    MaterializeEvaluationCase,
)
from archguard.benchmark.models import BenchmarkDataset, GroundTruthCase, Label, Split
from archguard.calibration.models import PrimaryCohort, TrainingRunResult
from archguard.calibration.numeric import fit_coefficients, solve
from archguard.calibration.workflow import (
    evaluate_frozen,
    family_weights,
    fit_preprocessor,
    freeze,
    measure,
    primary_cohort,
    rank,
    scores,
    select_model,
    threshold_candidates,
    train_models,
    values,
)
from archguard.cli import main
from archguard.infrastructure.benchmark import LoadedBenchmark, prepared
from archguard.infrastructure.calibration import (
    load_experiment,
    load_policy,
    load_primary,
    save_new,
)

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def calibration_inputs():
    experiment = load_experiment(ROOT / "experiments/calibration/structural-v1.json")
    dataset = BenchmarkDataset.model_validate_json(
        (ROOT / "benchmarks/v1/dataset-1.1.json").read_text()
    )
    loaded = LoadedBenchmark(
        dataset, (), (), ROOT / "benchmarks/v1", experiment.dataset_fingerprint
    )
    records = []
    for repo in dataset.repositories:
        if repo.dataset_split == Split.TEST or not repo.repository_family_id.startswith("graph-"):
            continue
        # Never open held-out source/truth files while constructing fitting fixtures.
        _, inputs = prepared(loaded, repo.repository_id)
        materializer = MaterializeEvaluationCase(
            inputs.iam, inputs.static, inputs.graph, inputs.discovery
        )
        for raw in json.loads((loaded.root / repo.ground_truth).read_text()):
            truth = GroundTruthCase.model_validate(raw)
            anchor = EvaluationAnchor(
                repository_id=repo.repository_id, rule_id=truth.rule_id, subjects=truth.subjects
            )
            records.append(
                join_label(
                    materializer.execute(anchor),
                    truth,
                    repo,
                    dataset.dataset_id,
                    dataset.dataset_version,
                    loaded.fingerprint,
                )
            )
    train = primary_cohort(
        tuple(r for r in records if r.split == Split.TRAIN), Split.TRAIN, experiment
    )
    validation = primary_cohort(
        tuple(r for r in records if r.split == Split.VALIDATION), Split.VALIDATION, experiment
    )
    return experiment, train, validation, loaded


@pytest.fixture(scope="module")
def fitted(calibration_inputs):
    experiment, train, validation, _ = calibration_inputs
    training = train_models(train, experiment)
    selection = select_model(training, validation)
    artifact = freeze(selection)
    return training, selection, artifact


def changed_numeric(row, name, value):
    features = []
    for f in row.features.values:
        if f.name == name:
            f = f.model_copy(
                update={
                    "value": value,
                    "value_type": FeatureValueType.MISSING if value is None else f.value_type,
                    "availability": FeatureAvailability.MISSING
                    if value is None
                    else FeatureAvailability.AVAILABLE,
                    "provenance_refs": () if value is None else f.provenance_refs,
                }
            )
        features.append(f)
    digest = fingerprint(
        {
            "schema_version": row.features.schema_version,
            "values": [f.model_dump(mode="json") for f in features],
        }
    )
    vector = row.features.model_copy(update={"values": tuple(features), "fingerprint": digest})
    return CalibrationTrainingRecord.model_validate(
        row.model_copy(update={"features": vector, "feature_fingerprint": digest})
    )


def synthetic_test(train):
    pair = tuple(
        next(r for r in train.records if r.ground_truth_label == label)
        for label in (Label.POSITIVE, Label.NEGATIVE)
    )
    records = tuple(
        r.model_copy(update={"split": Split.TEST, "repository_family_id": "unit-holdout"})
        for r in pair
    )
    return PrimaryCohort(
        split=Split.TEST,
        records=records,
        fingerprint=fingerprint([r.model_dump(mode="json") for r in records]),
        excluded_records=0,
    )


def test_primary_counts_whitelist_weights(calibration_inputs):
    experiment, train, validation, _ = calibration_inputs
    assert len(train.records) == 42 and len(train.families) == 4
    assert len(validation.records) == 4 and len(validation.families) == 1
    assert sum(r.ground_truth_label == Label.POSITIVE for r in train.records) == 20
    assert all(
        r.rule_id.startswith("ARCH10") and r.variant == CohortVariant.STRUCTURAL
        for r in train.records
    )
    assert all(
        "ARCH" not in n and n not in {"label", "repository_id", "split", "task.family"}
        for n in FEATURE_NAMES
    )
    totals = defaultdict(float)
    for row, weight in zip(train.records, family_weights(train), strict=True):
        totals[row.repository_family_id] += weight
    assert all(v == pytest.approx(42 / 4) for v in totals.values())
    assert sum(family_weights(train)) == pytest.approx(42)
    with pytest.raises(StructuralCalibrationError):
        primary_cohort((*train.records, train.records[0]), Split.TRAIN, experiment)
    ignored = train.records[0].model_copy(update={"variant": CohortVariant.BOUNDED_METRICS})
    assert primary_cohort((*train.records, ignored), Split.TRAIN, experiment).excluded_records == 1


def test_preprocessing_is_train_only(calibration_inputs, fitted):
    experiment, train, validation, _ = calibration_inputs
    training, _, artifact = fitted
    before = canonical(training.preprocessor)
    extreme = changed_numeric(validation.records[0], "graph.Ca", 1000000)
    with pytest.raises(StructuralCalibrationError):
        primary_cohort((extreme, *validation.records[1:]), Split.VALIDATION, experiment)
    test = synthetic_test(train)
    extreme_test = test.model_copy(
        update={
            "records": (changed_numeric(test.records[0], "graph.Ca", 1000000), *test.records[1:])
        }
    )
    evaluate_frozen(artifact, extreme_test, experiment)
    assert before == canonical(fit_preprocessor(train)) == canonical(training.preprocessor)
    with pytest.raises(StructuralCalibrationError):
        fit_preprocessor(validation)
    missing = changed_numeric(train.records[0], "graph.Ca", None)
    pp = training.preprocessor
    transformed = pp.transform(values(missing))
    column = next(c for c in pp.columns if c.name == "graph.Ca")
    assert transformed[pp.output_features.index("graph.Ca.missing")] == 1
    assert transformed[pp.output_features.index("graph.Ca")] == pytest.approx(
        (column.median - column.mean) / column.scale
    )
    assert (
        next(d for d in pp.dropped_features if d.name == "quality.unresolved").reason
        == "CONSTANT_ON_TRAIN"
    )


def test_label_and_test_isolation(calibration_inputs, fitted):
    experiment, train, _, _ = calibration_inputs
    training, selection, artifact = fitted
    flipped = tuple(
        r.model_copy(
            update={
                "ground_truth_label": Label.NEGATIVE
                if r.ground_truth_label == Label.POSITIVE
                else Label.POSITIVE
            }
        )
        for r in train.records
    )
    assert tuple(values(r) for r in flipped) == tuple(values(r) for r in train.records)
    with pytest.raises(StructuralCalibrationError):
        primary_cohort(flipped, Split.TRAIN, experiment)
    test = synthetic_test(train)
    before = canonical(artifact)
    for function, args in ((train_models, (test, experiment)), (select_model, (training, test))):
        with pytest.raises(StructuralCalibrationError):
            function(*args)
    assert "test" not in inspect.signature(train_models).parameters
    assert "test" not in inspect.signature(select_model).parameters
    evaluated = evaluate_frozen(artifact, test, experiment)
    flipped_test = test.model_copy(
        update={
            "records": tuple(
                r.model_copy(
                    update={
                        "ground_truth_label": Label.NEGATIVE
                        if r.ground_truth_label == Label.POSITIVE
                        else Label.POSITIVE
                    }
                )
                for r in test.records
            )
        }
    )
    evaluated_other = evaluate_frozen(artifact, flipped_test, experiment)
    assert evaluated.test_fingerprint != evaluated_other.test_fingerprint
    assert before == canonical(artifact) == canonical(freeze(selection))
    assert "test" not in type(artifact).model_fields and "test" not in type(selection).model_fields


def test_native_solvers_and_portable_replay(calibration_inputs, fitted):
    experiment, train, _, _ = calibration_inputs
    coefficients, intercept, _ = fit_coefficients(
        ((0.0,), (1.0,)), (0, 1), (1.0, 1.0), 1.0, logistic=False
    )
    assert coefficients == pytest.approx((1 / 3,)) and intercept == pytest.approx(1 / 3)
    beta, intercept, _ = fit_coefficients(((-1.0,), (1.0,)), (0, 1), (1.0, 1.0), 1.0, logistic=True)
    assert intercept == pytest.approx(0, abs=1e-10)
    assert beta[0] == pytest.approx(2 / (1 + math.exp(beta[0])), abs=1e-9)
    assert stable_sigmoid(-1000) == 0 and stable_sigmoid(1000) == 1
    with pytest.raises(StructuralCalibrationError):
        solve([[0.0]], [1.0])
    with pytest.raises(StructuralCalibrationError):
        fit_coefficients(
            ((-1.0,), (1.0,)), (0, 1), (1.0, 1.0), 1.0, logistic=True, max_iterations=1
        )
    training, selection, artifact = fitted
    assert len(training.candidates) == len(selection.candidates) == 6
    assert canonical(training) == canonical(train_models(train, experiment))
    assert selection.chosen_index == max(range(6), key=lambda i: rank(selection.candidates[i]))
    replay = FrozenStructuralHybridPolicyArtifact.model_validate_json(canonical(artifact))
    assert scores(replay.model, replay.preprocessor, train) == scores(
        artifact.model, artifact.preprocessor, train
    )
    model = PortableStructuralModel(
        family="LOGISTIC_REGRESSION",
        regularization=1.0,
        feature_order=("a", "b"),
        coefficients=(2.0, -1.0),
        intercept=0.5,
        solver="weighted-logistic-newton-v1",
        iterations=1,
        replay_max_error=0,
    )
    assert model.score((1.0, 3.0)) == pytest.approx(stable_sigmoid(-0.5))
    with pytest.raises(StructuralCalibrationError):
        model.score((1.0,))


@pytest.mark.parametrize(
    "field", ["threshold", "dataset_fingerprint", "train_fingerprint", "feature_schema_version"]
)
def test_artifact_is_immutable_and_checked(fitted, field):
    training, _, artifact = fitted
    with pytest.raises(ValidationError):
        artifact.threshold = 0.1
    changed = artifact.model_copy(update={field: 0.0 if field == "threshold" else "0" * 64})
    with pytest.raises(ValidationError):
        FrozenStructuralHybridPolicyArtifact.model_validate(changed)
    with pytest.raises(StructuralCalibrationError):
        CalibratedStructuralHybridPolicy(artifact, expected_dataset_fingerprint="0" * 64)
    with pytest.raises(StructuralCalibrationError):
        CalibratedStructuralHybridPolicy(artifact, expected_train_fingerprint="0" * 64)
    with pytest.raises(ValidationError):
        TrainingRunResult.model_validate(
            training.model_copy(update={"train_fingerprint": "0" * 64})
        )
    with pytest.raises(ValidationError):
        type(artifact.preprocessor).model_validate(
            artifact.preprocessor.model_copy(update={"selected_features": ("label",)})
        )


def test_thresholds_metrics(calibration_inputs):
    _, train, _, _ = calibration_inputs
    assert threshold_candidates((0.2, 0.8, 0.2)) == (0.199999, 0.5, 0.800001)
    with pytest.raises(StructuralCalibrationError):
        threshold_candidates(())
    result = measure(train, (0.0,) * len(train.records), 1.0)
    assert result.micro.precision is None and result.micro.f1 == 0
    assert result.macro_family.f1 == 0 and result.micro.coverage == 1


@pytest.mark.parametrize("fit_fixture", ("fitted", "fitted_v2"))
def test_runtime_signals_static_bypass_and_semantic_rejection(
    calibration_inputs, fit_fixture, request, monkeypatch
):
    _, train, _, loaded = calibration_inputs
    _, _, artifact = request.getfixturevalue(fit_fixture)
    spec = artifact.preprocessor.feature_spec
    policy = CalibratedStructuralHybridPolicy(artifact)
    pipeline, inputs = prepared(loaded, "graph-fan-in-java")
    result = HybridAnalyzer(policy).analyze(
        inputs.iam,
        inputs.static,
        inputs.graph,
        inputs.discovery,
        spec=inputs.spec,
        graph_conformance=inputs.graph_conformance,
    )
    index = next(i for i, c in enumerate(result.cases) if c.rule_id == "ARCH102")
    case, bundle, feature = (
        result.cases[index],
        result.evidence_bundles[index],
        result.features[index],
    )
    decision = result.decisions[index]
    assert decision.state in {
        HybridDecisionState.STRUCTURAL_SIGNAL_SUPPORTED,
        HybridDecisionState.STRUCTURAL_SIGNAL_NOT_SUPPORTED,
    }
    assert (
        not decision.confirmed_finding_ids
        and decision.confidence is None
        and decision.severity is None
    )
    assert decision.model_score == artifact.model.score(
        artifact.preprocessor.transform(runtime_values(case, bundle, feature, spec))
    )
    record = next(
        r
        for r in train.records
        if r.repository_id == "graph-fan-in-java"
        and r.rule_id == "ARCH102"
        and r.ground_truth_label == Label.POSITIVE
    )
    assert runtime_values(case, bundle, feature, spec) == numeric_values(
        {f.name: f.value for f in record.features.values}, spec
    )
    with pytest.raises(StructuralCalibrationError):
        policy.decide(case.model_copy(update={"rule_id": "ARCH202"}), bundle, feature)
    _, static = prepared(loaded, "static-java-2-clean-arch002")
    baseline = HybridAnalyzer().analyze(
        static.iam,
        static.static,
        static.graph,
        static.discovery,
        spec=static.spec,
        graph_conformance=static.graph_conformance,
    )
    i = next(i for i, c in enumerate(baseline.cases) if c.rule_id == "ARCH002")

    def no_score(*args):
        raise AssertionError("deterministic proof invoked classifier")

    monkeypatch.setattr(PortableStructuralModel, "score", no_score)
    bypass = policy.decide(baseline.cases[i], baseline.evidence_bundles[i], baseline.features[i])
    original = baseline.decisions[i]
    assert bypass.state == HybridDecisionState.CONFIRMED_DETERMINISTIC
    assert (
        bypass.severity == original.severity
        and bypass.confirmed_finding_ids == original.confirmed_finding_ids
    )


def test_cli_stages_and_guards(calibration_inputs, fitted, tmp_path, capsys):
    experiment, train, validation, _ = calibration_inputs
    training, selection, artifact = fitted
    for cohort in (train, validation, synthetic_test(train)):
        (tmp_path / (cohort.split.value.lower() + ".jsonl")).write_text(
            "".join(canonical(r) + "\n" for r in cohort.records)
        )
    manifest = tmp_path / "experiment.json"
    save_new(manifest, experiment)
    for command, args in [
        ("train", ["--train", str(tmp_path / "train.jsonl"), "--manifest", str(manifest)]),
        (
            "select",
            [
                "--training",
                str(tmp_path / "training.json"),
                "--validation",
                str(tmp_path / "validation.jsonl"),
            ],
        ),
        ("freeze", ["--selection", str(tmp_path / "selection.json")]),
    ]:
        output = (
            tmp_path
            / {"train": "training.json", "select": "selection.json", "freeze": "policy.json"}[
                command
            ]
        )
        assert main(["calibration", command, *args, "--output", str(output)]) == 0
        capsys.readouterr()
    assert load_policy(tmp_path / "policy.json") == artifact
    assert (
        load_primary(tmp_path / "train.jsonl", Split.TRAIN, experiment).fingerprint
        == train.fingerprint
    )
    assert (
        main(
            [
                "calibration",
                "train",
                "--train",
                str(tmp_path / "test.jsonl"),
                "--manifest",
                str(manifest),
                "--output",
                str(tmp_path / "bad.json"),
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "calibration",
                "train",
                "--train",
                str(tmp_path / "train.jsonl"),
                "--manifest",
                str(manifest),
                "--channels",
                "static,graph,ai",
                "--output",
                str(tmp_path / "bad.json"),
            ]
        )
        == 2
    )
    assert "FULL_HYBRID_NOT_READY" in capsys.readouterr().err
    arguments = [
        "calibration",
        "evaluate",
        "--artifact",
        str(tmp_path / "policy.json"),
        "--test",
        str(tmp_path / "test.jsonl"),
        "--manifest",
        str(manifest),
        "--output",
        str(tmp_path / "test-result.json"),
    ]
    before = (tmp_path / "policy.json").read_bytes()
    assert main(arguments) == 0
    assert (tmp_path / "policy.json").read_bytes() == before
    arguments[-1] = str(tmp_path / "repeat.json")
    assert main(arguments) == 2 and not (tmp_path / "repeat.json").exists()
    with pytest.raises(FileExistsError):
        save_new(tmp_path / "policy.json", artifact)


@pytest.fixture(scope="module")
def fitted_v2(calibration_inputs):
    _, train, validation, _ = calibration_inputs
    experiment = load_experiment(ROOT / "experiments/calibration/structural-v2.json")
    training = train_models(train, experiment)
    selection = select_model(training, validation)
    return training, selection, freeze(selection)


def test_v2_predictors_ignore_decisions_labels_identity(calibration_inputs, fitted_v2):
    from uuid import uuid4

    from archguard.architecture.hybrid.calibration import FEATURE_NAMES_V2, FEATURE_SPEC_V2

    _, train, _, _ = calibration_inputs
    training, _, _ = fitted_v2
    assert training.preprocessor.selected_features == FEATURE_NAMES_V2
    assert "selection.candidate_present" not in FEATURE_NAMES_V2
    for row in train.records:
        original = values(row, FEATURE_SPEC_V2)
        flag = next(f.value for f in row.features.values if f.name == "selection.candidate_present")
        toggled = changed_numeric(row, "selection.candidate_present", not flag)
        renamed = row.model_copy(
            update={
                "repository_id": "renamed-repository",
                "repository_family_id": "renamed-family",
                "case_id": uuid4(),
                "rule_id": "ARCH105",
                "ground_truth_label": Label.NEGATIVE
                if row.ground_truth_label == Label.POSITIVE
                else Label.POSITIVE,
            }
        )
        assert values(toggled, FEATURE_SPEC_V2) == original == values(renamed, FEATURE_SPEC_V2)
        assert training.preprocessor.transform(original) == training.preprocessor.transform(
            values(renamed, FEATURE_SPEC_V2)
        )
    # Both labels have usable measurements even when detector selection is absent.
    for label in (Label.POSITIVE, Label.NEGATIVE):
        row = next(r for r in train.records if r.ground_truth_label == label)
        absent = changed_numeric(row, "selection.candidate_present", False)
        assert any(v is not None for v in values(absent, FEATURE_SPEC_V2).values())
        assert values(absent, FEATURE_SPEC_V2) == values(row, FEATURE_SPEC_V2)


@pytest.mark.parametrize("label", ("POSITIVE", "NEGATIVE"))
def test_v2_graph_candidates_do_not_change_raw_vector(calibration_inputs, fitted_v2, label):
    from archguard.architecture.hybrid.calibration import FEATURE_SPEC_V2

    _, train, _, loaded = calibration_inputs
    training, _, _ = fitted_v2
    _, inputs = prepared(loaded, "graph-fan-in-java")
    repo = next(r for r in loaded.dataset.repositories if r.repository_id == "graph-fan-in-java")
    truth = next(
        GroundTruthCase.model_validate(raw)
        for raw in json.loads((loaded.root / repo.ground_truth).read_text())
        if raw["rule_id"] == "ARCH102" and raw["label"] == label
    )
    anchor = EvaluationAnchor(
        repository_id=repo.repository_id, rule_id=truth.rule_id, subjects=truth.subjects
    )
    graphs = (
        inputs.graph.model_copy(update={"candidates": ()}),
        inputs.graph,
        inputs.graph.model_copy(update={"candidates": inputs.graph.candidates * 2}),
    )
    vectors = []
    for graph in graphs:
        assert graph.metrics == inputs.graph.metrics
        materialized = MaterializeEvaluationCase(
            inputs.iam, inputs.static, graph, inputs.discovery
        ).execute(anchor)
        raw = numeric_values(
            {f.name: f.value for f in materialized.features.values}, FEATURE_SPEC_V2
        )
        vectors.append(training.preprocessor.transform(raw))
    assert vectors[0] == vectors[1] == vectors[2]
    assert any(r.repository_id == anchor.repository_id for r in train.records)


def test_v2_no_test_files_and_reuse_block(
    calibration_inputs, fitted_v2, tmp_path, monkeypatch, capsys
):
    from archguard.calibration.workflow import direct_graph_baseline

    _, train, validation, _ = calibration_inputs
    training, _, artifact = fitted_v2
    experiment = training.experiment
    save_new(tmp_path / "manifest.json", experiment)
    for cohort in (train, validation):
        (tmp_path / (cohort.split.value.lower() + ".jsonl")).write_text(
            "".join(canonical(r) + "\n" for r in cohort.records)
        )
    assert not (tmp_path / "test.jsonl").exists()
    for command, args in (
        (
            "train",
            [
                "--train",
                str(tmp_path / "train.jsonl"),
                "--manifest",
                str(tmp_path / "manifest.json"),
            ],
        ),
        (
            "select",
            [
                "--training",
                str(tmp_path / "training.json"),
                "--validation",
                str(tmp_path / "validation.jsonl"),
            ],
        ),
        ("freeze", ["--selection", str(tmp_path / "selection.json")]),
        (
            "baseline",
            [
                "--train",
                str(tmp_path / "train.jsonl"),
                "--validation",
                str(tmp_path / "validation.jsonl"),
                "--manifest",
                str(tmp_path / "manifest.json"),
            ],
        ),
    ):
        name = {
            "train": "training",
            "select": "selection",
            "freeze": "policy",
            "baseline": "baseline",
        }[command]
        assert (
            main(["calibration", command, *args, "--output", str(tmp_path / (name + ".json"))]) == 0
        )
        capsys.readouterr()
    assert load_policy(tmp_path / "policy.json") == artifact
    assert artifact.status == "AWAITING_FRESH_HOLDOUT"
    baseline = direct_graph_baseline(train, validation, experiment)
    assert baseline.train_cases == 42 and baseline.validation_cases == 4
    predictions = tuple(
        float(next(f.value for f in r.features.values if f.name == "selection.candidate_present"))
        for r in validation.records
    )
    assert baseline.validation_metrics == measure(validation, predictions, 0.5)

    original_open = Path.open

    def guard_open(path, *args, **kwargs):
        if path.name == "test.jsonl":
            raise AssertionError("TEST opened before lineage guard")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard_open)
    with pytest.raises(StructuralCalibrationError, match="TEST_REUSE_FORBIDDEN"):
        load_primary(tmp_path / "test.jsonl", Split.TEST, experiment)
    with pytest.raises(StructuralCalibrationError, match="TEST_REUSE_FORBIDDEN"):
        primary_cohort((), Split.TEST, experiment)
    with pytest.raises(StructuralCalibrationError, match="TEST_REUSE_FORBIDDEN"):
        evaluate_frozen(artifact, train.model_copy(update={"split": Split.TEST}), experiment)
    assert (
        main(
            [
                "calibration",
                "evaluate",
                "--artifact",
                str(tmp_path / "policy.json"),
                "--manifest",
                str(tmp_path / "manifest.json"),
                "--test",
                str(tmp_path / "test.jsonl"),
                "--output",
                str(tmp_path / "forbidden.json"),
            ]
        )
        == 2
    )
    assert "TEST_REUSE_FORBIDDEN" in capsys.readouterr().err
    assert not (tmp_path / "forbidden.json").exists()
    assert not list(tmp_path.glob("*.heldout-receipt.json"))


def test_v1_artifact_remains_immutable_history():
    import hashlib

    policy = ROOT / "experiments/results/structural-v1/policy.json"
    assert (
        hashlib.sha256(policy.read_bytes()).hexdigest()
        == "5be4a82caa63f552d59ee3439dd45f281e56cfb3ac2c6ebfe452cc19e07ad1ee"
    )
    assert (
        load_policy(policy).fingerprint
        == "fdbb6eaeeb2e7099265c391c05b4996fb264d1f0398d1112be8b5012392d8395"
    )


def test_v2_whitelist_and_research_status_are_enforced(fitted_v2):
    from archguard.architecture.hybrid.calibration import FEATURE_NAMES, FEATURE_SPEC_V2
    from archguard.calibration.models import StructuralV2ExperimentManifest
    from archguard.calibration.workflow import seal

    training, _, artifact = fitted_v2
    pp = {
        n: getattr(artifact.preprocessor, n)
        for n in type(artifact.preprocessor).model_fields
        if n != "fingerprint"
    }
    pp["selected_features"] = FEATURE_NAMES
    with pytest.raises(ValidationError, match="preprocessor schema"):
        seal(type(artifact.preprocessor), **pp)
    raw = {
        n: getattr(artifact, n)
        for n in type(artifact).model_fields
        if n not in {"fingerprint", "artifact_id"}
    }
    for field, value in (("status", "FROZEN"), ("schema_version", "frozen-structural-policy-v1")):
        with pytest.raises(ValidationError, match="frozen artifact provenance"):
            seal(FrozenStructuralHybridPolicyArtifact, **(raw | {field: value}))
    exp = training.experiment.model_dump(mode="json")
    exp["excluded_predictors"] = []
    with pytest.raises(ValidationError, match="v2 exclusions"):
        StructuralV2ExperimentManifest.model_validate(exp)
    assert artifact.preprocessor.feature_spec == FEATURE_SPEC_V2
