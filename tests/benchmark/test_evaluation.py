from uuid import uuid5

import pytest

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.adapters import prediction
from archguard.benchmark.evaluation import evaluate, metrics
from archguard.benchmark.models import (
    AnnotationScope,
    Confusion,
    Label,
    Mode,
    PredictionState,
    Subjects,
    Task,
)


def run(
    loaded,
    validated,
    truths,
    predictions=(),
    mode=Mode.STATIC_ONLY,
    task=Task.CONFIRMED_VIOLATION_DETECTION,
    dataset=None,
):
    return evaluate(
        dataset or loaded.dataset,
        truths,
        predictions,
        validated[1],
        loaded.fingerprint,
        task=task,
        mode=mode,
    )


def predicted(
    loaded,
    truth,
    state=PredictionState.POSITIVE,
    mode=Mode.STATIC_ONLY,
    task=Task.CONFIRMED_VIOLATION_DETECTION,
):
    return prediction(
        loaded.dataset.namespace,
        truth.repository_id,
        truth.rule_id,
        truth.subjects,
        state,
        mode,
        task,
    )


def test_handcrafted_matrix(loaded, validated):
    truths = tuple(t for t in loaded.truths if t.rule_id.startswith("ARCH00"))
    positive = [t for t in truths if t.label == Label.POSITIVE]
    negative = [t for t in truths if t.label == Label.NEGATIVE]
    predictions = tuple(predicted(loaded, t) for t in positive[:8] + negative[:2])
    result = run(loaded, validated, truths, predictions)
    c = result.confusion
    assert (c.tp, c.fp, c.fn, c.tn) == (8, 2, 2, 8)
    assert result.metrics.precision == result.metrics.recall == result.metrics.f1 == 0.8
    assert result.metrics.fpr == result.metrics.fnr == 0.2
    assert len(result.per_rule) == 5
    assert len(result.per_language) == 2
    assert len(result.per_repository) == 20
    assert canonical(result) == canonical(
        run(loaded, validated, truths, tuple(reversed(predictions)))
    )


@pytest.mark.parametrize(
    "counts,expected",
    [
        ({}, (None, None, None, None, None)),
        ({"fn": 1}, (None, 0.0, None, None, 1.0)),
        ({"fp": 1}, (0.0, None, None, None, None)),
        ({"tn": 5, "explicit_negatives": 5}, (None, None, None, 0.0, None)),
        (
            {"tp": 2, "fp": 1, "tn": 2, "explicit_negatives": 2, "scoped_extra_fp": 1},
            (2 / 3, 1.0, 0.8, None, 0.0),
        ),
    ],
)
def test_zero_and_negative_universe(counts, expected):
    m = metrics(Confusion(**counts))
    assert (m.precision, m.recall, m.f1, m.fpr, m.fnr) == expected


@pytest.mark.parametrize(
    "state,label,outcome",
    [
        (PredictionState.CANDIDATE, Label.POSITIVE, "tp"),
        (PredictionState.CANDIDATE, Label.NEGATIVE, "fp"),
        (PredictionState.NEGATIVE, Label.POSITIVE, "fn"),
        (PredictionState.NEGATIVE, Label.NEGATIVE, "tn"),
        (PredictionState.ABSTAIN, Label.POSITIVE, "abstain"),
        (PredictionState.ABSTAIN, Label.NEGATIVE, "abstain"),
    ],
)
def test_semantic_states(loaded, validated, state, label, outcome):
    truth = next(t for t in loaded.truths if t.rule_id == "ARCH202" and t.label == label)
    p = predicted(loaded, truth, state, Mode.LLM_ONLY, Task.SEMANTIC_CANDIDATE_DETECTION)
    result = run(
        loaded, validated, (truth,), (p,), Mode.LLM_ONLY, Task.SEMANTIC_CANDIDATE_DETECTION
    )
    assert getattr(result.confusion, outcome) == 1
    assert (
        result.confusion.tp + result.confusion.fp + result.confusion.fn + result.confusion.tn
        == (0 if outcome == "abstain" else 1)
    )
    assert result.metrics.prediction_coverage == (0.0 if outcome == "abstain" else 1.0)


def test_missing_ai_is_coverage_miss(loaded, validated):
    truth = next(t for t in loaded.truths if t.rule_id == "ARCH202")
    r = run(loaded, validated, (truth,), mode=Mode.LLM_ONLY, task=Task.SEMANTIC_CANDIDATE_DETECTION)
    assert r.confusion.no_prediction == 1
    assert r.confusion.fn == r.confusion.tn == 0
    assert r.metrics.prediction_coverage == 0.0


def test_unknown_and_unresolved_are_not_negative(loaded, validated):
    truth = next(t for t in loaded.truths if t.rule_id == "ARCH002")
    unknown = truth.model_copy(update={"label": Label.UNKNOWN})
    p = predicted(loaded, truth)
    r = run(loaded, validated, (unknown,), (p,))
    assert r.confusion.unknown_truth == r.confusion.out_of_scope == 1
    assert r.confusion.fp == r.confusion.tn == 0
    missing = truth.subjects.locators[0].model_copy(update={"qualified_name": "missing"})
    bad = truth.model_copy(update={"subjects": Subjects(locators=(missing,))})
    r = run(loaded, validated, (bad,))
    assert r.status == "PARTIAL"
    assert r.confusion.unresolved_truth == 1 and r.confusion.fn == 0


def test_direction_and_partial_scope(loaded, validated):
    truth = next(t for t in loaded.truths if t.rule_id == "ARCH002")
    reverse = truth.model_copy(
        update={
            "subjects": Subjects(locators=tuple(reversed(truth.subjects.locators)), directed=True)
        }
    )
    p = predicted(loaded, reverse)
    r = run(loaded, validated, (truth,), (p,))
    assert r.confusion.out_of_scope == 1
    assert r.confusion.fp == 0
    repos = tuple(
        repo.model_copy(
            update={
                "annotation_scope": AnnotationScope(
                    rules=("ARCH002",), fully_annotated_rules=("ARCH002",)
                )
            }
        )
        if repo.repository_id == truth.repository_id
        else repo
        for repo in loaded.dataset.repositories
    )
    r = run(
        loaded,
        validated,
        (truth,),
        (p,),
        dataset=loaded.dataset.model_copy(update={"repositories": repos}),
    )
    assert r.confusion.fp == r.confusion.scoped_extra_fp == 1
    assert r.metrics.fpr is None


def test_duplicates_and_conflicts(loaded, validated):
    truth = next(t for t in loaded.truths if t.rule_id == "ARCH002" and t.label == Label.POSITIVE)
    p = predicted(loaded, truth)
    dup = p.model_copy(update={"prediction_id": uuid5(p.prediction_id, "duplicate")})
    r = run(loaded, validated, (truth,), (p, dup))
    assert r.confusion.tp == 1 and len(r.predictions) == 1
    assert r.diagnostics == ("DUPLICATE_PREDICTION",)
    r = run(loaded, validated, (truth,), (p, predicted(loaded, truth, PredictionState.NEGATIVE)))
    assert r.confusion.abstain == 1 and r.confusion.tp == 0
    assert r.diagnostics[0].startswith("CONFLICTING")


@pytest.mark.parametrize(
    "error",
    [
        "repository",
        "mode",
        "task",
        "ids",
        "locator",
        "truth_duplicate",
        "truth_conflict",
        "calibrated",
    ],
)
def test_invalid_inputs(loaded, validated, error):
    truth = next(t for t in loaded.truths if t.rule_id == "ARCH002")
    p = predicted(loaded, truth)
    truths = (truth,)
    task = Task.CONFIRMED_VIOLATION_DETECTION
    updates = {
        "repository": {"repository_id": "missing"},
        "mode": {"source": Mode.HYBRID},
        "task": {"task": Task.STRUCTURAL_SIGNAL_RETRIEVAL},
        "ids": {"subject_ids": (uuid5(p.prediction_id, "bad-id"),)},
        "locator": {
            "subjects": Subjects(
                locators=(
                    truth.subjects.locators[0].model_copy(update={"qualified_name": "missing"}),
                )
            )
        },
    }
    if error in updates:
        p = p.model_copy(update=updates[error])
    elif error == "calibrated":
        task = Task.CALIBRATED_HYBRID_DETECTION
    else:
        truths = (
            truth,
            truth
            if error == "truth_duplicate"
            else truth.model_copy(update={"case_id": uuid5(truth.case_id, "conflicting")}),
        )
    with pytest.raises(ValueError):
        run(loaded, validated, truths, (p,), task=task)


def test_signature_is_optional_locator_identity(loaded, validated):
    from archguard.benchmark.resolver import LocatorResolver
    from archguard.core.model.enums import NodeKind

    truth = next(
        t for t in loaded.truths if t.repository_id == "semantic-java" and t.rule_id == "ARCH202"
    )
    resolver = LocatorResolver(validated[1][truth.repository_id])
    method = next(n for n in resolver.iam.nodes if n.kind == NodeKind.METHOD)
    actual = resolver.locator(method)
    truth = truth.model_copy(
        update={
            "label": Label.POSITIVE,
            "subjects": Subjects(locators=(actual.model_copy(update={"signature": None}),)),
        }
    )
    p = predicted(
        loaded, truth, PredictionState.CANDIDATE, Mode.LLM_ONLY, Task.SEMANTIC_CANDIDATE_DETECTION
    )
    p = p.model_copy(update={"subjects": Subjects(locators=(actual,))})
    assert (
        run(
            loaded, validated, (truth,), (p,), Mode.LLM_ONLY, Task.SEMANTIC_CANDIDATE_DETECTION
        ).confusion.tp
        == 1
    )


def test_split_selection_excludes_other_partitions(loaded, validated):
    from archguard.benchmark.models import Split

    r = evaluate(
        loaded.dataset,
        loaded.truths,
        (),
        validated[1],
        loaded.fingerprint,
        task=Task.CONFIRMED_VIOLATION_DETECTION,
        mode=Mode.STATIC_ONLY,
        splits=(Split.TEST,),
    )
    assert r.confusion.eligible == 4
