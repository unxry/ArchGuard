"""Post-freeze negative/OOS evaluation; never imported by the blind executor."""

from collections import Counter
from math import ceil
from statistics import mean, median
from typing import Any

from archguard.architecture.intelligence.models import ContextStrategy


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def descriptive(values: list[int | float]) -> dict[str, int | float | None]:
    ordered = sorted(values)
    return {
        "n": len(values),
        "sum": sum(ordered),
        "mean": mean(ordered) if values else None,
        "median": median(ordered) if values else None,
        "p95_nearest_rank": ordered[ceil(len(values) * 0.95) - 1] if values else None,
        "maximum": max(values) if values else None,
    }


def metrics(cases: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    negatives = [c for c in cases if c["final_human_label"] == "NEGATIVE"]
    oos = [c for c in cases if c["final_human_label"] == "OUT_OF_SCOPE"]
    assert len(negatives) + len(oos) == len(cases), (
        "this evaluator supports the frozen zero-positive cohort only"
    )

    def judgment(case: dict[str, Any]) -> str:
        row = outcomes.get(case["annotation_case_id"])
        if not row or row["status"] != "SUCCESS":
            return "MISSING_OR_FAILED"
        return str(row["assessment"]["judgment"])

    neg = Counter(judgment(c) for c in negatives)
    scope = Counter(judgment(c) for c in oos)
    tn, fp = neg["NOT_SUPPORTED"], neg["SUPPORTED"]
    successful = sum(judgment(c) != "MISSING_OR_FAILED" for c in cases)
    return {
        "cases": len(cases),
        "successful": successful,
        "missing_or_failed": len(cases) - successful,
        "negative_cases": len(negatives),
        "oos_cases": len(oos),
        "response_distribution": dict(Counter(judgment(c) for c in cases)),
        "negative_response_distribution": dict(neg),
        "oos_response_distribution": dict(scope),
        "TN": tn,
        "FP": fp,
        "abstain": neg["INSUFFICIENT_CONTEXT"],
        "not_applicable_on_negative": neg["NOT_APPLICABLE"],
        "specificity": ratio(tn, tn + fp),
        "FPR": ratio(fp, tn + fp),
        "definitive_coverage": ratio(tn + fp, len(negatives)),
        "abstention_rate": ratio(neg["INSUFFICIENT_CONTEXT"], len(negatives)),
        "negative_scope_error_rate": ratio(neg["NOT_APPLICABLE"], len(negatives)),
        "effective_negative_correctness": ratio(tn, len(negatives)),
        "oos_correct": scope["NOT_APPLICABLE"],
        "oos_recognition": ratio(scope["NOT_APPLICABLE"], len(oos)),
        "TP": 0,
        "Recall": None,
        "F1": None,
        "FNR": None,
    }


def evaluate(
    cases: list[dict[str, Any]], frozen: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    assert len(cases) == 40
    assert Counter(c["final_human_label"] for c in cases) == {"NEGATIVE": 32, "OUT_OF_SCOPE": 8}
    ids = {c["annotation_case_id"] for c in cases}
    outcomes = {
        strategy.value: {
            r["case_id"]: r for r in frozen["assessments"] if r["strategy"] == strategy.value
        }
        for strategy in ContextStrategy
    }
    assert all(set(rows) == ids for rows in outcomes.values())
    context_rows = {(r["case_id"], r["strategy"]): r for r in context["requests"]}
    strata: dict[str, str] = {}
    for case in ids:
        modes = {
            bool(context_rows[(case, s.value)]["context_diagnostics"]) for s in ContextStrategy
        }
        assert len(modes) == 1
        strata[case] = "PARTIAL_INVALID_IAM" if modes.pop() else "VALID_IAM"
    complete = {
        case
        for case in ids
        if all(outcomes[s.value][case]["status"] == "SUCCESS" for s in ContextStrategy)
    }
    summaries: dict[str, Any] = {}

    def operations(name: str, selected: set[str]) -> dict[str, Any]:
        attempts = [
            a for a in frozen["attempts"] if a["strategy"] == name and a["case_id"] in selected
        ]
        rows = [context_rows[(c, name)] for c in selected]
        return {
            "attempts": len(attempts),
            "retries": sum(a["attempt_number"] > 1 for a in attempts),
            "input_tokens": descriptive(
                [a["usage"]["input_tokens"] for a in attempts if a["usage"]]
            ),
            "output_tokens": descriptive(
                [a["usage"]["output_tokens"] for a in attempts if a["usage"]]
            ),
            "total_tokens": descriptive(
                [a["usage"]["total_tokens"] for a in attempts if a["usage"]]
            ),
            "latency_seconds": descriptive([a["latency_seconds"] for a in attempts]),
            "successful_logical_latency_seconds": descriptive(
                [
                    sum(a["latency_seconds"] for a in attempts if a["case_id"] == c)
                    for c in selected
                    if outcomes[name][c]["status"] == "SUCCESS"
                ]
            ),
            "known_estimated_cost_usd": sum(
                float(a["estimated_cost_usd"])
                for a in attempts
                if a["estimated_cost_usd"] is not None
            ),
            "context_chars": descriptive([r["context_chars"] for r in rows]),
            "source_chars": descriptive([r["source_chars"] for r in rows]),
            "context_measurements": {
                key: descriptive([r[key] for r in rows])
                for key in ("nodes", "files", "fragments", "input_estimate")
                if all(key in r for r in rows)
            },
            "truncated_requests": sum(bool(r.get("truncated")) for r in rows),
        }

    for strategy in ContextStrategy:
        name = strategy.value
        summary = metrics(cases, outcomes[name])
        attempts = [a for a in frozen["attempts"] if a["strategy"] == name]
        rows = [context_rows[(c, name)] for c in ids]
        summary |= {
            "attempts": len(attempts),
            "retries": sum(a["attempt_number"] > 1 for a in attempts),
            "failures": dict(
                Counter(r["status"] for r in outcomes[name].values() if r["status"] != "SUCCESS")
            ),
            "error_codes": dict(
                Counter(a.get("error_code") for a in attempts if a.get("error_code"))
            ),
            "input_tokens": descriptive(
                [a["usage"]["input_tokens"] for a in attempts if a["usage"]]
            ),
            "output_tokens": descriptive(
                [a["usage"]["output_tokens"] for a in attempts if a["usage"]]
            ),
            "total_tokens": descriptive(
                [a["usage"]["total_tokens"] for a in attempts if a["usage"]]
            ),
            "latency_seconds": descriptive([a["latency_seconds"] for a in attempts]),
            "logical_latency_seconds": descriptive(
                [sum(a["latency_seconds"] for a in attempts if a["case_id"] == c) for c in ids]
            ),
            "known_estimated_cost_usd": sum(
                float(a["estimated_cost_usd"])
                for a in attempts
                if a["estimated_cost_usd"] is not None
            ),
            "unknown_usage_attempts": sum(a["usage"] is None for a in attempts),
            "context_chars": descriptive([r["context_chars"] for r in rows]),
            "source_chars": descriptive([r["source_chars"] for r in rows]),
            "per_rule": {
                rule: metrics([c for c in cases if c["rule_id"] == rule], outcomes[name])
                for rule in sorted({c["rule_id"] for c in cases})
            },
            "per_language": {
                lang: metrics([c for c in cases if c["language"] == lang], outcomes[name])
                | operations(
                    name, {c["annotation_case_id"] for c in cases if c["language"] == lang}
                )
                for lang in sorted({c["language"] for c in cases})
            },
            "per_repository": {
                repo: metrics([c for c in cases if c["repository_id"] == repo], outcomes[name])
                for repo in sorted({c["repository_id"] for c in cases})
            },
            "iam_sensitivity": {
                mode: metrics(
                    [c for c in cases if strata[c["annotation_case_id"]] == mode], outcomes[name]
                )
                for mode in ("VALID_IAM", "PARTIAL_INVALID_IAM")
            },
            "primary_paired_quality": metrics(
                [c for c in cases if c["annotation_case_id"] in complete], outcomes[name]
            ),
        }
        summary["successful_logical_latency_seconds"] = operations(name, ids)[
            "successful_logical_latency_seconds"
        ]
        summary["context_measurements"] = operations(name, ids)["context_measurements"]
        summary["truncated_requests"] = operations(name, ids)["truncated_requests"]
        summaries[name] = summary
    pairs = []
    for left, right in (
        ("LOCAL_ONLY", "GRAPH_GUIDED"),
        ("GRAPH_GUIDED", "EXPANDED_BASELINE"),
        ("LOCAL_ONLY", "EXPANDED_BASELINE"),
    ):
        valid = {
            c
            for c in ids
            if outcomes[left][c]["status"] == outcomes[right][c]["status"] == "SUCCESS"
        }
        transitions = Counter(
            (
                outcomes[left][c]["assessment"]["judgment"],
                outcomes[right][c]["assessment"]["judgment"],
            )
            for c in valid
        )
        matched = [c for c in cases if c["annotation_case_id"] in valid]
        left_quality = metrics(matched, outcomes[left])
        right_quality = metrics(matched, outcomes[right])
        pairs.append(
            {
                "from": left,
                "to": right,
                "expected_pairs": 40,
                "complete_pairs": len(valid),
                "missing_pair_case_ids": sorted(ids - valid),
                "raw_judgment_agreement": ratio(
                    sum(n for (a, b), n in transitions.items() if a == b), len(valid)
                ),
                "transitions": [
                    {"from": a, "to": b, "count": n} for (a, b), n in sorted(transitions.items())
                ],
                "transitions_by_human_class": {
                    label: [
                        {"from": a, "to": b, "count": n}
                        for (a, b), n in sorted(
                            Counter(
                                (
                                    outcomes[left][c["annotation_case_id"]]["assessment"][
                                        "judgment"
                                    ],
                                    outcomes[right][c["annotation_case_id"]]["assessment"][
                                        "judgment"
                                    ],
                                )
                                for c in matched
                                if c["final_human_label"] == label
                            ).items()
                        )
                    ]
                    for label in ("NEGATIVE", "OUT_OF_SCOPE")
                },
                "from_matched_quality": left_quality,
                "to_matched_quality": right_quality,
                "quality_delta_to_minus_from": {
                    key: right_quality[key] - left_quality[key]
                    if left_quality[key] is not None and right_quality[key] is not None
                    else None
                    for key in (
                        "specificity",
                        "FPR",
                        "effective_negative_correctness",
                        "definitive_coverage",
                        "abstention_rate",
                        "oos_recognition",
                    )
                },
                "operational_comparison_population": (
                    "All 40 logical requests per strategy, including retry/failure attempts"
                ),
                "input_token_reduction_of_from_vs_to": 1
                - summaries[left]["input_tokens"]["sum"] / summaries[right]["input_tokens"]["sum"]
                if summaries[right]["input_tokens"]["sum"]
                else None,
                "context_char_reduction_of_from_vs_to": 1
                - summaries[left]["context_chars"]["sum"]
                / summaries[right]["context_chars"]["sum"],
                "source_char_reduction_of_from_vs_to": 1
                - summaries[left]["source_chars"]["sum"] / summaries[right]["source_chars"]["sum"],
                "mean_attempt_latency_delta_from_minus_to": summaries[left]["latency_seconds"][
                    "mean"
                ]
                - summaries[right]["latency_seconds"]["mean"],
                "estimated_cost_delta_from_minus_to": summaries[left]["known_estimated_cost_usd"]
                - summaries[right]["known_estimated_cost_usd"],
            }
        )
    return {
        "strategies": summaries,
        "pairwise": pairs,
        "complete_successful_triples": len(complete),
        "incomplete_triple_case_ids": sorted(ids - complete),
        "positive_class": {
            "present": False,
            "Recall": None,
            "F1": None,
            "FNR": None,
            "primary_semantic_effectiveness_ready": False,
        },
        "interpretation": (
            "Descriptive negative/OOS/context-sensitivity only; "
            "no sensitivity, significance or overall superiority claim"
        ),
    }
