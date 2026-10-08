"""Prospective abstention-aware arithmetic; only unit fixtures may use this before live freeze."""

from decimal import Decimal
from typing import Any


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def semantic_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if any(
        r["human"] not in {"POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"}
        or r["decision"]
        not in {"SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE", None}
        for r in rows
    ):
        raise ValueError("distinct four-category reference and assessment enums required")
    binary = [r for r in rows if r["human"] in {"POSITIVE", "NEGATIVE"}]
    positive = sum(r["human"] == "POSITIVE" for r in binary)
    negative = len(binary) - positive
    tp = sum(r["human"] == "POSITIVE" and r["decision"] == "SUPPORTED" for r in binary)
    fn = sum(r["human"] == "POSITIVE" and r["decision"] == "NOT_SUPPORTED" for r in binary)
    tn = sum(r["human"] == "NEGATIVE" and r["decision"] == "NOT_SUPPORTED" for r in binary)
    fp = sum(r["human"] == "NEGATIVE" and r["decision"] == "SUPPORTED" for r in binary)
    abstain = sum(r["decision"] == "INSUFFICIENT_CONTEXT" for r in binary)
    scope = sum(r["decision"] == "NOT_APPLICABLE" for r in binary)
    oos = [r for r in rows if r["human"] == "OUT_OF_SCOPE"]
    cross = {
        category: {
            decision: sum(r["human"] == category and r["decision"] == decision for r in rows)
            for decision in (
                "SUPPORTED",
                "NOT_SUPPORTED",
                "INSUFFICIENT_CONTEXT",
                "NOT_APPLICABLE",
                None,
            )
        }
        for category in ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")
    }
    # JSON-safe failure column is explicitly distinguished from all four semantic decisions.
    cross = {
        category: {
            "TECHNICAL_FAILURE" if key is None else key: value for key, value in values.items()
        }
        for category, values in cross.items()
    }
    abstain_positive = cross["POSITIVE"]["INSUFFICIENT_CONTEXT"]
    abstain_negative = cross["NEGATIVE"]["INSUFFICIENT_CONTEXT"]
    scope_positive = cross["POSITIVE"]["NOT_APPLICABLE"]
    scope_negative = cross["NEGATIVE"]["NOT_APPLICABLE"]
    definitive = tp + fp + tn + fn
    failures = sum(r["decision"] is None for r in binary)
    if definitive + abstain + scope + failures != len(binary):
        raise ValueError("binary confusion reconciliation failed")
    return {
        "N": len(rows),
        "binary_eligible": len(binary),
        "binary_excluded": len(rows) - len(binary),
        "human_positive": positive,
        "human_negative": negative,
        "human_uncertain": sum(r["human"] == "UNCERTAIN" for r in rows),
        "human_out_of_scope": len(oos),
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "ABSTAIN_POSITIVE": abstain_positive,
        "ABSTAIN_NEGATIVE": abstain_negative,
        "NOT_APPLICABLE_ON_POSITIVE": scope_positive,
        "NOT_APPLICABLE_ON_NEGATIVE": scope_negative,
        "definitive_count": definitive,
        "denominators": {
            "precision": tp + fp,
            "recall_definitive": tp + fn,
            "F1_definitive": 2 * tp + fp + fn,
            "specificity_definitive": tn + fp,
            "FPR_definitive": tn + fp,
            "FNR_definitive": tp + fn,
            "coverage_abstention_applicability_effective_correctness": len(binary),
            "effective_recall": positive,
            "effective_negative_correctness": negative,
        },
        "precision": ratio(tp, tp + fp),
        "recall_definitive": ratio(tp, tp + fn),
        "F1_definitive": ratio(2 * tp, 2 * tp + fp + fn),
        "specificity_definitive": ratio(tn, tn + fp),
        "FPR_definitive": ratio(fp, tn + fp),
        "FNR_definitive": ratio(fn, tp + fn),
        "effective_recall": ratio(tp, positive),
        "effective_negative_correctness": ratio(tn, negative),
        "effective_correctness": ratio(tp + tn, len(binary)),
        "definitive_coverage": ratio(tp + fp + tn + fn, len(binary)),
        "abstention_rate": ratio(abstain, len(binary)),
        "applicability_error_rate": ratio(scope, len(binary)),
        "technical_failure_rate_binary": ratio(
            sum(r["decision"] is None for r in binary), len(binary)
        ),
        "technical_failure_count_all": sum(r["decision"] is None for r in rows),
        "OOS_recognition": ratio(sum(r["decision"] == "NOT_APPLICABLE" for r in oos), len(oos)),
        "category_decision_counts": cross,
    }


def usage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "latency_seconds", "context_chars"):
        values = [r[key] for r in rows if r.get(key) is not None]
        result[key] = {
            "measured_N": len(values),
            "missing_N": len(rows) - len(values),
            "total_known": sum(values) if values else None,
            "mean_known": sum(values) / len(values) if values else None,
        }
    costs = [Decimal(r["cost_usd"]) for r in rows if r.get("cost_usd") is not None]
    result["cost_usd"] = {
        "measured_N": len(costs),
        "missing_N": len(rows) - len(costs),
        "total_known": str(sum(costs, Decimal(0))) if costs else None,
    }
    return result


def paired_comparison(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> dict[str, Any]:
    a, b = ({r["case_id"]: r for r in group} for group in (first, second))
    if len(a) != len(first) or len(b) != len(second) or set(a) != set(b):
        raise ValueError("complete unique paired case identities required")
    binary = [case for case in sorted(a) if a[case]["human"] in {"POSITIVE", "NEGATIVE"}]
    if any(a[case]["human"] != b[case]["human"] for case in a):
        raise ValueError("paired truth mismatch")

    def flags(row: dict[str, Any]) -> dict[str, bool]:
        definitive = row["decision"] in {"SUPPORTED", "NOT_SUPPORTED"}
        correct = (row["human"], row["decision"]) in {
            ("POSITIVE", "SUPPORTED"),
            ("NEGATIVE", "NOT_SUPPORTED"),
        }
        return {
            "correctness": correct,
            "coverage": definitive,
            "abstention": row["decision"] == "INSUFFICIENT_CONTEXT",
            "applicability": row["decision"] == "NOT_APPLICABLE",
        }

    comparisons: dict[str, Any] = {}
    for name in ("correctness", "coverage", "abstention", "applicability"):
        pairs = [(flags(a[c])[name], flags(b[c])[name]) for c in binary]
        comparisons[name] = {
            "N": len(pairs),
            "both": sum(x and y for x, y in pairs),
            "first_only": sum(x and not y for x, y in pairs),
            "second_only": sum(y and not x for x, y in pairs),
            "neither": sum(not x and not y for x, y in pairs),
        }
    decisions = ("SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE")
    comparisons["decision_cross_tab_binary"] = {
        x: {
            y: sum(a[c]["decision"] == x and b[c]["decision"] == y for c in binary)
            for y in decisions
        }
        for x in decisions
    }
    comparisons["nondefinitive_transitions"] = {
        "first_abstains_second_definitive": sum(
            flags(a[c])["abstention"] and flags(b[c])["coverage"] for c in binary
        ),
        "second_abstains_first_definitive": sum(
            flags(b[c])["abstention"] and flags(a[c])["coverage"] for c in binary
        ),
        "both_abstain": sum(
            flags(a[c])["abstention"] and flags(b[c])["abstention"] for c in binary
        ),
        "both_incorrect_definitive": sum(
            flags(a[c])["coverage"]
            and flags(b[c])["coverage"]
            and not flags(a[c])["correctness"]
            and not flags(b[c])["correctness"]
            for c in binary
        ),
    }
    for key in ("input_tokens", "latency_seconds", "cost_usd", "context_chars"):
        numeric_pairs = [
            (Decimal(str(a[c][key])), Decimal(str(b[c][key])))
            for c in sorted(a)
            if a[c].get(key) is not None and b[c].get(key) is not None
        ]
        denominator = sum((y for _, y in numeric_pairs), Decimal(0))
        delta = sum((x - y for x, y in numeric_pairs), Decimal(0))
        comparisons[key] = {
            "paired_N": len(numeric_pairs),
            "mean_first_minus_second": str(delta / len(numeric_pairs)) if numeric_pairs else None,
            "relative_reduction_first_vs_second": float(-delta / denominator)
            if denominator
            else None,
        }
    ma, mb = semantic_metrics(first), semantic_metrics(second)
    comparisons["effectiveness_difference"] = {
        key: ma[key] - mb[key] if ma[key] is not None and mb[key] is not None else None
        for key in (
            "precision",
            "recall_definitive",
            "F1_definitive",
            "definitive_coverage",
            "effective_correctness",
            "effective_recall",
            "effective_negative_correctness",
            "specificity_definitive",
            "FPR_definitive",
            "FNR_definitive",
        )
    }
    return {"descriptive_only": True, "significance_test_run": False, "comparisons": comparisons}
