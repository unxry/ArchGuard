"""Synthetic arithmetic and refusal gates, never evaluate the actual absent P016 outputs."""

import pytest

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_positive_evaluation import (
    paired_comparison,
    ratio,
    semantic_metrics,
    usage_summary,
)
from archguard.infrastructure.semantic_positive_evaluator import evaluate_frozen_positive
from archguard.infrastructure.semantic_positive_execution import ExecutionBindings


def row(i, human, decision, **extras):
    return dict(
        case_id=f"synthetic-{i}",
        human=human,
        decision=decision,
        input_tokens=10,
        output_tokens=2,
        latency_seconds=0.1,
        cost_usd="0.01",
        context_chars=30,
        **extras,
    )


def test_confusion_definitive_and_effective_denominators():
    rows = [
        row(0, "POSITIVE", "SUPPORTED"),
        row(1, "POSITIVE", "NOT_SUPPORTED"),
        row(2, "NEGATIVE", "SUPPORTED"),
        row(3, "NEGATIVE", "NOT_SUPPORTED"),
        row(4, "POSITIVE", "INSUFFICIENT_CONTEXT"),
        row(5, "NEGATIVE", "NOT_APPLICABLE"),
        row(6, "NEGATIVE", None),
        row(7, "UNCERTAIN", "SUPPORTED"),
        row(8, "OUT_OF_SCOPE", "NOT_APPLICABLE"),
    ]
    m = semantic_metrics(rows)
    assert [m[k] for k in ["TP", "FP", "TN", "FN"]] == [1, 1, 1, 1]
    assert m["binary_eligible"] == 7 and m["binary_excluded"] == 2
    assert all(
        m[k] == 0.5
        for k in [
            "precision",
            "recall_definitive",
            "F1_definitive",
            "specificity_definitive",
            "FPR_definitive",
            "FNR_definitive",
        ]
    )
    assert m["effective_recall"] == 1 / 3 and m["effective_negative_correctness"] == 1 / 4
    assert m["definitive_coverage"] == 4 / 7 and m["effective_correctness"] == 2 / 7
    assert m["abstention_rate"] == 1 / 7 and m["applicability_error_rate"] == 1 / 7
    assert m["technical_failure_rate_binary"] == 1 / 7
    assert m["OOS_recognition"] == 1
    assert m["category_decision_counts"]["UNCERTAIN"]["SUPPORTED"] == 1


@pytest.mark.parametrize("decision", ["INSUFFICIENT_CONTEXT", "NOT_APPLICABLE", None])
def test_nondefinitive_never_coerced_to_negative(decision):
    m = semantic_metrics([row(0, "POSITIVE", decision), row(1, "NEGATIVE", decision)])
    assert [m[k] for k in ["TP", "FP", "TN", "FN"]] == [0, 0, 0, 0]
    assert all(
        m[k] is None
        for k in [
            "precision",
            "recall_definitive",
            "F1_definitive",
            "specificity_definitive",
            "FPR_definitive",
            "FNR_definitive",
        ]
    )
    assert m["definitive_coverage"] == 0
    assert m["effective_recall"] == 0 and m["effective_negative_correctness"] == 0


@pytest.mark.parametrize(
    "rows", [[], [row(0, "UNCERTAIN", "SUPPORTED")], [row(0, "OUT_OF_SCOPE", "NOT_APPLICABLE")]]
)
def test_null_safe_empty_binary_reference(rows):
    m = semantic_metrics(rows)
    assert m["binary_eligible"] == 0
    assert m["precision"] is None and m["definitive_coverage"] is None
    assert m["effective_recall"] is None
    assert ratio(1, 0) is None


@pytest.mark.parametrize(
    "human,decision",
    [("unknown", "SUPPORTED"), ("POSITIVE", "UNCERTAIN"), ("POSITIVE", "negative")],
)
def test_category_enums_not_collapsed_or_invented(human, decision):
    with pytest.raises(ValueError):
        semantic_metrics([row(0, human, decision)])


def test_excluded_reference_cannot_change_binary_metrics():
    binary = [row(0, "POSITIVE", "SUPPORTED"), row(1, "NEGATIVE", "NOT_SUPPORTED")]
    m = semantic_metrics(
        binary + [row(2, "UNCERTAIN", "NOT_SUPPORTED"), row(3, "OUT_OF_SCOPE", "SUPPORTED")]
    )
    assert m["precision"] == m["recall_definitive"] == m["F1_definitive"] == 1
    assert m["OOS_recognition"] == 0


def test_known_usage_never_zero_fills_absent_provider_measurements():
    rows = [
        row(0, "POSITIVE", "SUPPORTED"),
        dict(
            case_id="synthetic2",
            human="NEGATIVE",
            decision=None,
            input_tokens=None,
            output_tokens=None,
            latency_seconds=0.2,
            cost_usd=None,
            context_chars=20,
        ),
    ]
    m = usage_summary(rows)
    assert m["input_tokens"] == {
        "measured_N": 1,
        "missing_N": 1,
        "total_known": 10,
        "mean_known": 10,
    }
    assert m["cost_usd"]["missing_N"] == 1 and m["cost_usd"]["total_known"] == "0.01"
    assert usage_summary([])["cost_usd"]["total_known"] is None


def test_paired_order_independent_deltas_no_significance():
    a = [row(0, "POSITIVE", "SUPPORTED"), row(1, "NEGATIVE", "INSUFFICIENT_CONTEXT")]
    b = [row(1, "NEGATIVE", "NOT_SUPPORTED"), row(0, "POSITIVE", "NOT_SUPPORTED")]
    m = paired_comparison(a, b)
    assert m["descriptive_only"] is True and m["significance_test_run"] is False
    assert m["comparisons"]["correctness"] == {
        "N": 2,
        "both": 0,
        "first_only": 1,
        "second_only": 1,
        "neither": 0,
    }
    assert m["comparisons"]["coverage"]["first_only"] == 0
    assert m["comparisons"]["coverage"]["second_only"] == 1
    assert m["comparisons"]["abstention"]["first_only"] == 1
    assert m["comparisons"]["input_tokens"]["paired_N"] == 2
    assert m["comparisons"]["input_tokens"]["relative_reduction_first_vs_second"] == 0


@pytest.mark.parametrize("kind", ["missing", "duplicate", "truth"])
def test_paired_mismatches_rejected(kind):
    a = [row(0, "POSITIVE", "SUPPORTED"), row(1, "NEGATIVE", "NOT_SUPPORTED")]
    b = list(a)
    if kind == "missing":
        b.pop()
    elif kind == "duplicate":
        b = [a[0], a[0]]
    else:
        b[0] = row(0, "NEGATIVE", "SUPPORTED")
    with pytest.raises(ValueError):
        paired_comparison(a, b)


@pytest.mark.parametrize("kind", ["absent", "incomplete", "bindings"])
def test_evaluator_refuses_before_any_truth_read(tmp_path, monkeypatch, kind):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    bindings = ExecutionBindings(
        execution_freeze_fingerprint="a" * 64,
        protocol_fingerprint="b" * 64,
        context_manifest_fingerprint="c" * 64,
        request_manifest_fingerprint="d" * 64,
        truth_fingerprint="e" * 64,
    )
    receipt = {
        "bindings": bindings.model_dump(),
        "logical_results": 300,
        "complete": False,
        "files": {},
    }
    if kind == "bindings":
        receipt["complete"] = True
        receipt["bindings"]["truth_fingerprint"] = "f" * 64
    receipt["fingerprint"] = digest(receipt)
    if kind != "absent":
        (ledger / "assessment-freeze.json").write_text(canonical(receipt) + "\n")
    from pathlib import Path

    original = Path.read_bytes
    reads = []

    def read(path):
        reads.append(path)
        assert "truth" not in path.name, "truth accessed before ledger freeze gate"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises((ValueError, FileNotFoundError)):
        evaluate_frozen_positive(
            tmp_path / "execution",
            ledger,
            bindings,
            receipt["fingerprint"],
            tmp_path / "truth",
            "0" * 64,
            "1" * 64,
            tmp_path / "mapping.json",
            "2" * 64,
        )
    assert all(p.parent == ledger for p in reads)
