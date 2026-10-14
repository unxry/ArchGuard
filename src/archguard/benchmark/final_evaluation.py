"""Frozen FINAL metric semantics, descriptive comparisons and hypothesis rule."""

from collections import Counter
from fractions import Fraction
from typing import Any

from archguard.benchmark.oss.models import digest

METHODS = tuple(f"A{i}" for i in range(1, 8))
MISSING = ("TERMINAL_INVALID_REQUEST_ID_MISMATCH", "AMBIGUOUS_TRANSPORT_NO_CAPTURE")
DECISIONS = (
    "SUPPORTED",
    "NOT_SUPPORTED",
    "INSUFFICIENT_CONTEXT",
    "INSUFFICIENT_EVIDENCE",
    "NOT_APPLICABLE",
    *MISSING,
)
HYPOTHESIS = (
    "Joint Static + Graph + Semantic LLM analysis improves architectural "
    "violation recall/completeness while maintaining precision compared "
    "with individual methods."
)
HYPOTHESIS_RULE = {
    "SUPPORTED": (
        "A7 Recall strictly greater than EACH A1/A2/A3 AND Precision at least "
        "EACH; exact rational comparisons, zero tolerance"
    ),
    "PARTIALLY_SUPPORTED": (
        "Some individual-component Recall gain, but the literal joint claim "
        "does not hold across all three comparisons"
    ),
    "NOT_SUPPORTED": "No Recall gain against any individual component",
    "undefined": "Cannot establish a comparison with an undefined metric",
    "selection": "A7 remains FULL HYBRID regardless of final ranking",
}


def unique(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("P025_DUPLICATE_STABLE_ID")
    return result


def metrics(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    if method not in METHODS or any(
        r["label"] not in (0, 1) or r["predictions"][method]["decision"] not in DECISIONS
        for r in rows
    ):
        raise ValueError("P025_METRIC_CONTRACT_DRIFT")
    outputs = [(r["label"], r["predictions"][method]["decision"]) for r in rows]
    tp = sum(y == 1 and d == "SUPPORTED" for y, d in outputs)
    fp = sum(y == 0 and d == "SUPPORTED" for y, d in outputs)
    tn = sum(y == 0 and d == "NOT_SUPPORTED" for y, d in outputs)
    fn = sum(y == 1 and d != "SUPPORTED" for y, d in outputs)
    counts = Counter(d for _, d in outputs)
    n = len(rows)
    fractions = dict(
        Precision=(tp, tp + fp),
        Recall=(tp, tp + fn),
        F1=(2 * tp, 2 * tp + fp + fn),
        Specificity=(tn, tn + fp),
        FPR=(fp, tn + fp),
        FNR=(fn, tp + fn),
        effective_correctness=(tp + tn, n),
        definitive_coverage=(counts["SUPPORTED"] + counts["NOT_SUPPORTED"], n),
        abstention_rate=(counts["INSUFFICIENT_CONTEXT"] + counts["INSUFFICIENT_EVIDENCE"], n),
        applicability_rate=(
            n - counts["NOT_APPLICABLE"],
            0 if sum(counts[d] for d in MISSING) else n,
        ),
    )
    return dict(
        N=n,
        positive=sum(y == 1 for y, _ in outputs),
        negative=sum(y == 0 for y, _ in outputs),
        TP=tp,
        FP=fp,
        TN=tn,
        FN=fn,
        **{key: float(Fraction(a, b)) if b else None for key, (a, b) in fractions.items()},
        exact_ratios={key: [a, b] if b else None for key, (a, b) in fractions.items()},
        definitive_positive=tp + fp,
        definitive_negative=tn + sum(y == 1 and d == "NOT_SUPPORTED" for y, d in outputs),
        abstention=counts["INSUFFICIENT_CONTEXT"] + counts["INSUFFICIENT_EVIDENCE"],
        nondefinitive=sum(d not in {"SUPPORTED", "NOT_SUPPORTED"} for _, d in outputs),
        non_applicability=counts["NOT_APPLICABLE"],
        technical_missing=sum(counts[d] for d in MISSING),
        negative_nondefinitive=sum(
            y == 0 and d not in {"SUPPORTED", "NOT_SUPPORTED"} for y, d in outputs
        ),
        applicability_unknown=sum(counts[d] for d in MISSING),
    )


def ratio(value: dict[str, Any], key: str) -> Fraction | None:
    pair = value["exact_ratios"][key]
    return Fraction(*pair) if pair is not None else None


def deltas(first: dict[str, Any], second: dict[str, Any]) -> dict[str, float | None]:
    result = {}
    for key in ("Precision", "Recall", "F1", "effective_correctness", "definitive_coverage"):
        a, b = ratio(first, key), ratio(second, key)
        result[key] = float(100 * (a - b)) if a is not None and b is not None else None
    return result


def correct(row: dict[str, Any], method: str) -> bool:
    decision = row["predictions"][method]["decision"]
    return bool(
        (row["label"] == 1 and decision == "SUPPORTED")
        or (row["label"] == 0 and decision == "NOT_SUPPORTED")
    )


def paired(rows: list[dict[str, Any]], comparator: str) -> dict[str, Any]:
    counts = Counter((correct(r, "A7"), correct(r, comparator)) for r in rows)
    return dict(
        N=len(rows),
        both_correct=counts[True, True],
        A7_only=counts[True, False],
        comparator_only=counts[False, True],
        neither=counts[False, False],
        comparator_nondefinitive_to_A7_correct=sum(
            correct(r, "A7") and r["predictions"][comparator]["binary"] is None for r in rows
        ),
        comparator_correct_to_A7_not_correct=counts[False, True],
        delta_percentage_points=deltas(metrics(rows, "A7"), metrics(rows, comparator)),
    )


def hypothesis(primary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    comparisons = {}
    for method in METHODS[:3]:
        recall_a, recall_b = ratio(primary["A7"], "Recall"), ratio(primary[method], "Recall")
        precision_a, precision_b = (
            ratio(primary["A7"], "Precision"),
            ratio(primary[method], "Precision"),
        )
        comparisons[method] = dict(
            recall_improved=recall_a is not None and recall_b is not None and recall_a > recall_b,
            precision_maintained=precision_a is not None
            and precision_b is not None
            and precision_a >= precision_b,
            delta_percentage_points=deltas(primary["A7"], primary[method]),
            component_metrics=primary[method],
        )
    complete = all(c["recall_improved"] for c in comparisons.values())
    precision = all(c["precision_maintained"] for c in comparisons.values())
    status = (
        "SUPPORTED"
        if complete and precision
        else "PARTIALLY_SUPPORTED"
        if any(c["recall_improved"] for c in comparisons.values())
        else "NOT_SUPPORTED"
    )
    return dict(
        hypothesis=HYPOTHESIS,
        final_status=status,
        interpretation_rule=HYPOTHESIS_RULE,
        input_metric_fingerprint=digest(primary),
        A7=primary["A7"],
        individual_comparisons=comparisons,
        completeness_claim_holds_across_individuals=complete,
        precision_claim_holds_across_individuals=precision,
        reason=(
            f"Recall improvement across all individual components: {complete}; "
            f"exact precision maintenance across all: {precision}. See individual "
            f"deltas and A7 F1, effective correctness and coverage."
        ),
    )


def aggregate(
    rows: list[dict[str, Any]], static_rules: list[str], graph_rules: list[str]
) -> dict[str, Any]:
    unique(rows, "case_id")
    primary = {method: metrics(rows, method) for method in METHODS}
    coverage = {
        method: {
            key: value[key]
            for key in (
                "N",
                "definitive_positive",
                "definitive_negative",
                "definitive_coverage",
                "abstention",
                "nondefinitive",
                "non_applicability",
                "technical_missing",
                "negative_nondefinitive",
                "applicability_rate",
                "applicability_unknown",
            )
        }
        for method, value in primary.items()
    }
    native = {
        "A1_STATIC_NATIVE": metrics([r for r in rows if r["rule"] in static_rules], "A1"),
        "A2_GRAPH_NATIVE": metrics([r for r in rows if r["rule"] in graph_rules], "A2"),
        "A3_AVAILABLE_ONLY": metrics(
            [r for r in rows if r["predictions"]["A3"]["decision"] not in MISSING], "A3"
        ),
    }
    strata = {}
    for field in ("family", "rule", "language"):
        strata[field] = {
            key: {
                method: metrics([r for r in rows if r[field] == key], method) for method in METHODS
            }
            for key in sorted({r[field] for r in rows})
        }
    missing_rows = [r for r in rows if r["predictions"]["A3"]["decision"] in MISSING]
    missing = dict(
        N=len(missing_rows),
        positive=sum(r["label"] == 1 for r in missing_rows),
        negative=sum(r["label"] == 0 for r in missing_rows),
        hybrid_outputs={
            method: dict(Counter(r["predictions"][method]["decision"] for r in missing_rows))
            for method in ("A5", "A6", "A7")
        },
        imputation=False,
        available_only_supplemental=True,
    )
    return {
        "final-primary-metrics.json": dict(view="FINAL TEST — PRIMARY N=300", methods=primary),
        "final-coverage-metrics.json": dict(methods=coverage, missingness=missing),
        "final-native-scope-metrics.json": dict(view="SUPPLEMENTAL ONLY", methods=native),
        "final-family-strata.json": dict(strata=strata["family"]),
        "final-rule-strata.json": dict(strata=strata["rule"]),
        "final-language-strata.json": dict(strata=strata["language"]),
        "final-ablation.json": dict(
            methods=primary,
            A7_minus={method: deltas(primary["A7"], primary[method]) for method in METHODS[:-1]},
            units="percentage points",
            interpretation=(
                "Whole-system differences under independently selected frozen models; "
                "not isolated causal effects"
            ),
        ),
        "final-paired-comparisons.json": dict(
            comparisons={method: paired(rows, method) for method in METHODS[:-1]}, p_values=False
        ),
        "final-hypothesis.json": hypothesis(primary),
    }
