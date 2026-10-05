import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.cohort import AIAssessmentManifest, CalibrationTrainingRecord, join_label
from archguard.benchmark.identity import case_id
from archguard.benchmark.materialization import (
    AISource,
    CohortVariant,
    EvaluationAnchor,
    MaterializeEvaluationCase,
)
from archguard.benchmark.models import Label, RuleFamily, Split, Subjects
from archguard.benchmark.readiness import CalibrationReadinessValidator, human_readiness
from archguard.cli import main
from archguard.core.model.enums import NodeKind
from archguard.infrastructure.benchmark import load_dataset, prepared, safe_path, validate_dataset
from archguard.infrastructure.calibration_cohort import export_cohort, extract_cohort
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.hybrid.conftest import semantic

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def expanded():
    return load_dataset(ROOT / "benchmarks/v1/dataset-1.1.json")


@pytest.fixture(scope="module")
def extracted(expanded):
    return extract_cohort(expanded)


def test_expanded_composition_and_readiness(expanded, extracted):
    summary, _ = validate_dataset(expanded)
    assert summary["status"] == "VALID" and not summary["diagnostics"]
    assert summary["labels"] == {"POSITIVE": 68, "NEGATIVE": 70}
    assert summary["families"] == 18 and summary["repositories"] == 56
    cohort, report = extracted
    assert len(cohort.records) == 552
    assert report.structural_hybrid.status == "READY"
    assert report.full_hybrid.status == "NOT_READY"
    assert "REAL_AI_ASSESSMENT_COHORT_AND_SEMANTIC_REVIEW_REQUIRED" in report.full_hybrid.reasons
    assert report.tasks[RuleFamily.SEMANTIC].status == "NOT_READY"
    assert report.dataset_valid
    assert set(report.split_composition) == {s.value for s in Split}
    for split, tasks in report.task_coverage.items():
        assert all(v["families"] >= (2 if split == "TRAIN" else 1) for v in tasks.values())
        assert all(v["positive"] and v["negative"] for v in tasks.values())
    assert all(
        report.export_coverage[s.value]["positive"] and report.export_coverage[s.value]["negative"]
        for s in Split
    )
    assert len(report.rule_coverage) == 15
    assert all(r.ground_truth_label != Label.UNKNOWN for r in cohort.records)
    assert all(r.ai_source == AISource.AI_UNAVAILABLE for r in cohort.records)
    assert all(
        not r.calibration_eligible for r in cohort.records if r.rule_family == RuleFamily.SEMANTIC
    )
    assert all(
        m.provider is None and m.model is None and m.usage.total_tokens is None
        for m in cohort.ai_assessments
    )
    assert all(t.review.status == "UNREVIEWED" and not t.review.annotators for t in expanded.truths)


@pytest.mark.parametrize("label", [Label.POSITIVE, Label.NEGATIVE])
def test_no_candidate_case_and_label_separation(expanded, label):
    truth = next(
        t
        for t in expanded.truths
        if t.repository_id == "semantic-shipping-java"
        and t.rule_id == "ARCH202"
        and t.label == label
    )
    _, inputs = prepared(expanded, truth.repository_id)
    materializer = MaterializeEvaluationCase(
        inputs.iam,
        inputs.static,
        inputs.graph,
        inputs.discovery,
        conformance=inputs.graph_conformance,
    )
    anchor = EvaluationAnchor(
        repository_id=truth.repository_id, rule_id=truth.rule_id, subjects=truth.subjects
    )
    value = materializer.execute(anchor)
    assert not value.candidate_present and not value.ai_target_selected
    features = {f.name: f.value for f in value.features.values}
    assert features["selection.candidate_present"] is False
    assert features["ai.target_selected"] is False
    assert features["graph.Ca"] is not None and features["graph.Ce"] is not None
    assert features["quality.iam_complete"] is True
    assert "ground_truth_label" not in canonical(value)
    repo = next(r for r in expanded.dataset.repositories if r.repository_id == truth.repository_id)
    record = join_label(
        value,
        truth,
        repo,
        expanded.dataset.dataset_id,
        expanded.dataset.dataset_version,
        expanded.fingerprint,
    )
    assert record.ground_truth_label == label and not record.calibration_eligible
    other_label = Label.NEGATIVE if label == Label.POSITIVE else Label.POSITIVE
    flipped = truth.model_copy(
        update={
            "label": other_label,
            "case_id": case_id(
                expanded.dataset.namespace,
                truth.repository_id,
                truth.rule_id,
                other_label,
                truth.subjects,
            ),
        }
    )
    other = join_label(
        value,
        flipped,
        repo,
        expanded.dataset.dataset_id,
        expanded.dataset.dataset_version,
        expanded.fingerprint,
    )
    assert (
        other.features == record.features
        and other.feature_fingerprint == record.feature_fingerprint
    )
    assert other.hybrid_case_id == record.hybrid_case_id
    with pytest.raises(ValidationError):
        EvaluationAnchor.model_validate({**anchor.model_dump(), "label": label})
    with pytest.raises(ValueError):
        join_label(
            value,
            truth.model_copy(update={"rule_id": "ARCH201"}),
            repo,
            expanded.dataset.dataset_id,
            expanded.dataset.dataset_version,
            expanded.fingerprint,
        )
    missing = truth.subjects.locators[0].model_copy(update={"qualified_name": "missing"})
    with pytest.raises(ValueError):
        materializer.execute(anchor.model_copy(update={"subjects": Subjects(locators=(missing,))}))


def test_negative_static_features_are_measured(expanded, extracted):
    cohort, _ = extracted
    negative = next(
        r
        for r in cohort.records
        if r.rule_id == "ARCH002"
        and r.ground_truth_label == Label.NEGATIVE
        and r.variant == CohortVariant.STRUCTURAL
    )
    values = {f.name: f.value for f in negative.features.values}
    assert values["selection.static_generated"] is False
    assert values["channel.static_available"] is True
    assert values["graph.source.Ce"] >= 1
    assert values["static.confirmed"] is None
    assert negative.calibration_eligible
    positive = next(
        r
        for r in cohort.records
        if r.rule_id == "ARCH002"
        and r.ground_truth_label == Label.POSITIVE
        and r.variant == CohortVariant.STRUCTURAL
    )
    assert (
        next(f.value for f in positive.features.values if f.name == "selection.static_generated")
        is True
    )
    cycles = [
        r
        for r in cohort.records
        if r.rule_id == "ARCH003" and r.variant == CohortVariant.WITHOUT_GRAPH
    ]
    assert cycles and all(not r.calibration_eligible for r in cycles)


def test_missing_and_partial_channels_are_explicit(extracted):
    cohort, _ = extracted
    for record in cohort.records:
        if record.variant == CohortVariant.WITHOUT_GRAPH:
            assert record.channels["graph"] is False and record.channels["discovery"] is False
        if record.variant == CohortVariant.WITHOUT_STATIC:
            assert record.channels["static"] is False
        if record.variant == CohortVariant.BOUNDED_METRICS and record.rule_id == "ARCH105":
            assert "REQUIRED_METRIC_SKIPPED" in record.eligibility_reasons
            assert not record.calibration_eligible
        assert all(
            name not in canonical(record.features)
            for name in (
                "ground_truth_label",
                "rationale",
                "raw_prompt",
                "source_fragments",
                "short_reason",
            )
        )


@pytest.mark.parametrize("decision", ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT"])
def test_scripted_ai_is_ineligible(expanded, decision):
    repo = next(
        r for r in expanded.dataset.repositories if r.repository_id == "semantic-shipping-java"
    )
    truth = next(
        t
        for t in expanded.truths
        if t.repository_id == repo.repository_id
        and t.rule_id == "ARCH202"
        and t.label == Label.NEGATIVE
    )
    _, inputs = prepared(expanded, repo.repository_id)
    resolver = MaterializeEvaluationCase(inputs.iam, inputs.static, inputs.graph, inputs.discovery)
    target = resolver.resolver.subjects(truth.subjects)[0]
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(safe_path(expanded.root, repo.source_path)),
        )
    ) as source:
        ai = semantic(inputs, source.workspace, target, "ARCH202", decision)
    value = MaterializeEvaluationCase(
        inputs.iam, inputs.static, inputs.graph, inputs.discovery, ai
    ).execute(
        EvaluationAnchor(
            repository_id=repo.repository_id, rule_id=truth.rule_id, subjects=truth.subjects
        )
    )
    assert value.ai_target_selected and value.ai_source == AISource.SCRIPTED_TEST
    record = join_label(
        value,
        truth,
        repo,
        expanded.dataset.dataset_id,
        expanded.dataset.dataset_version,
        expanded.fingerprint,
    )
    assert not record.calibration_eligible and "OFFLINE_CONTRACT_ONLY" in record.eligibility_reasons
    if decision == "INSUFFICIENT_CONTEXT":
        assert record.features.values[
            next(
                i for i, f in enumerate(record.features.values) if f.name == "ai.ARCH202.decisions"
            )
        ].value == ("INSUFFICIENT_CONTEXT",)
    with pytest.raises(ValidationError):
        CalibrationTrainingRecord.model_validate(
            record.model_copy(
                update={
                    "calibration_eligible": True,
                    "eligibility_reasons": ("INDEPENDENT_STRUCTURAL_EVIDENCE",),
                }
            )
        )
    with pytest.raises(ValidationError):
        CalibrationTrainingRecord.model_validate(
            record.model_copy(update={"ai_source": AISource.AI_UNAVAILABLE})
        )
    reserved = CalibrationTrainingRecord.model_validate(
        record.model_copy(
            update={
                "ai_source": AISource.REAL_PROVIDER,
                "eligibility_reasons": ("REAL_AI_NOT_VALIDATED", "REAL_AI_AND_REVIEW_REQUIRED"),
            }
        )
    )
    assert not reserved.calibration_eligible
    with pytest.raises(ValidationError):
        CalibrationTrainingRecord.model_validate(
            reserved.model_copy(update={"calibration_eligible": True})
        )


@pytest.mark.parametrize("channel", ["static", "graph", "discovery"])
def test_materialization_rejects_foreign_evidence(expanded, channel):
    _, inputs = prepared(expanded, "static-webshop-java-clean")
    _, foreign = prepared(expanded, "static-batch-workflow-java-clean")
    channels = {"static": inputs.static, "graph": inputs.graph, "discovery": inputs.discovery}
    channels[channel] = getattr(foreign, channel)
    with pytest.raises(ValueError):
        MaterializeEvaluationCase(inputs.iam, **channels)


def test_unknown_cannot_be_eligible(extracted):
    cohort, _ = extracted
    original = next(r for r in cohort.records if r.calibration_eligible)
    unknown = CalibrationTrainingRecord.model_validate(
        original.model_copy(
            update={
                "ground_truth_label": Label.UNKNOWN,
                "calibration_eligible": False,
                "eligibility_reasons": ("UNKNOWN_TRUTH",),
            }
        )
    )
    assert unknown.features == original.features
    with pytest.raises(ValidationError):
        CalibrationTrainingRecord.model_validate(
            unknown.model_copy(update={"calibration_eligible": True})
        )


@pytest.mark.parametrize(
    "problem",
    [
        "single_class_validation",
        "single_task_test",
        "one_eligible_family",
        "no_records",
        "invalid_dataset",
    ],
)
def test_readiness_failures(expanded, extracted, problem):
    cohort, _ = extracted
    records = cohort.records
    truths = expanded.truths
    valid = True
    if problem == "single_class_validation":
        records = tuple(
            r
            for r in records
            if r.split != Split.VALIDATION or r.ground_truth_label == Label.POSITIVE
        )
    elif problem == "single_task_test":
        records = tuple(
            r
            for r in records
            if r.split != Split.TEST or r.rule_family == RuleFamily.DETERMINISTIC_CONFORMANCE
        )
        selected_ids = {r.case_id for r in records}
        truths = tuple(t for t in truths if t.case_id in selected_ids)
    elif problem == "one_eligible_family":
        records = tuple(
            r
            for r in records
            if r.split != Split.TRAIN
            or r.rule_family != RuleFamily.STRUCTURAL_GRAPH
            or r.repository_family_id == "graph-fan-in"
        )
    elif problem == "no_records":
        records = ()
    else:
        valid = False
    report = CalibrationReadinessValidator().validate(
        expanded.dataset,
        truths,
        cohort.model_copy(update={"records": records}),
        dataset_valid=valid,
    )
    assert report.structural_hybrid.status == report.full_hybrid.status == "NOT_READY"
    assert report.structural_hybrid.reasons


@pytest.mark.parametrize(
    "problem",
    [
        "split",
        "family",
        "dataset",
        "fingerprint",
        "truth",
        "duplicate",
        "schema",
        "label_feature",
        "eligibility",
        "channels",
        "task_feature",
    ],
)
def test_cohort_invariants(expanded, extracted, problem):
    cohort, _ = extracted
    record = next(r for r in cohort.records if r.calibration_eligible)
    updates = {
        "split": {"split": next(s for s in Split if s != record.split)},
        "family": {"repository_family_id": "alien"},
        "dataset": {"dataset_version": "99"},
        "fingerprint": {"dataset_fingerprint": "0" * 64},
        "truth": {"ground_truth_label": Label.UNKNOWN},
        "schema": {"features": record.features.model_copy(update={"schema_version": "other"})},
        "eligibility": {"eligibility_reasons": ()},
        "channels": {"channels": {"ai": False}},
    }
    if problem in {"label_feature", "task_feature"}:
        values = list(record.features.values)
        if problem == "label_feature":
            values[0] = values[0].model_copy(update={"name": "label"})
        else:
            idx = next(i for i, f in enumerate(values) if f.name == "task.family")
            values[idx] = values[idx].model_copy(update={"value": "wrong"})
        updates[problem] = {
            "features": record.features.model_copy(update={"values": tuple(values)})
        }
    changed = record.model_copy(update=updates.get(problem, {}))
    records = (*cohort.records, record) if problem == "duplicate" else (changed,)
    with pytest.raises(ValueError):
        CalibrationReadinessValidator().validate(
            expanded.dataset, expanded.truths, cohort.model_copy(update={"records": records})
        )


def test_translation_isolation_and_context_strategies(expanded):
    from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
    from archguard.architecture.intelligence.models import (
        ContextSelectionConfig,
        ContextStrategy,
    )
    from archguard.benchmark.splits import validate_leakage

    members = [
        r for r in expanded.dataset.repositories if r.repository_family_id == "semantic-shipping"
    ]
    assert len(members) == 2 and len({r.dataset_split for r in members}) == 1
    changed = members[0].model_copy(
        update={"dataset_split": next(s for s in Split if s != members[0].dataset_split)}
    )
    dataset = expanded.dataset.model_copy(
        update={
            "repositories": tuple(
                changed if r.repository_id == changed.repository_id else r
                for r in expanded.dataset.repositories
            )
        }
    )
    with pytest.raises(ValueError):
        validate_leakage(dataset)
    repo = members[0]
    _, inputs = prepared(expanded, repo.repository_id)
    target = next(
        n.id for n in inputs.iam.nodes if n.kind == NodeKind.CLASS and n.name == "RequestEndpoint"
    )
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(safe_path(expanded.root, repo.source_path)),
        )
    ) as source:
        for strategy in ContextStrategy:
            config = ContextSelectionConfig(strategy=strategy)
            pack = GraphGuidedContextBuilder().build(
                target,
                inputs.iam,
                inputs.graph,
                source.workspace,
                config,
                inputs.spec,
                inputs.discovery,
            )
            assert pack.manifest.context_chars <= config.max_total_chars and pack.fragments


def test_extraction_boundary_is_label_free():
    path = ROOT / "src/archguard/benchmark/materialization.py"
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"label", "ground_truth_label", "rationale"}
        if isinstance(node, ast.Name):
            assert node.id not in {"GroundTruthCase", "Label", "HybridTrainingRecord"}
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {
                "archguard.benchmark.cohort",
                "archguard.benchmark.readiness",
            }


def test_export_cli_and_readiness_are_deterministic(expanded, extracted, tmp_path, capsys):
    cohort, report = extracted
    export_cohort(cohort, report, tmp_path / "a")
    export_cohort(cohort, report, tmp_path / "b")
    assert all(
        p.read_bytes() == (tmp_path / "b" / p.name).read_bytes() for p in (tmp_path / "a").iterdir()
    )
    with pytest.raises(ValueError):
        export_cohort(cohort, report, tmp_path / "a")
    dataset = str(expanded.root / "dataset-1.1.json")
    assert main(["benchmark", "readiness", dataset, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == report.model_dump(mode="json")
    assert "Structural Hybrid: READY" in human_readiness(report)
    assert "Full Hybrid: NOT_READY" in human_readiness(report)
    assert main(["benchmark", "readiness", dataset]) == 0
    assert "Tasks:" in capsys.readouterr().out
    assert main(["benchmark", "export-cohort", dataset]) == 2
    assert main(["benchmark", "export-cohort", dataset, "--output", str(tmp_path / "cli")]) == 0
    capsys.readouterr()
    assert (tmp_path / "cli/train.jsonl").read_bytes() == (tmp_path / "a/train.jsonl").read_bytes()
    for line in (tmp_path / "a/train.jsonl").read_text().splitlines():
        assert all(
            forbidden not in line
            for forbidden in (
                "/Users/",
                "raw_prompt",
                "source_fragments",
                "api_key",
                "short_reason",
            )
        )
    with pytest.raises(ValueError):
        AIAssessmentManifest(case_id=cohort.records[0].case_id, assessment_artifact="../escape")
