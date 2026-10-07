"""Join human truth only after verifying the independent real-AI assessment freeze."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_evaluation import evaluate
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.oss_benchmark import write_new


def verified(path):
    result = json.loads(path.read_text())
    assert result["fingerprint"] == digest(
        {k: v for k, v in result.items() if k != "fingerprint"}
    ), str(path)
    return result


def publish(path, payload):
    sealed = payload | {"fingerprint": digest(payload)}
    if path.exists():
        assert verified(path) == sealed, "existing evaluation differs; never overwrite"
    else:
        write_new(path, sealed)
    return sealed


def evaluation_gate(path, manifest, context):
    frozen = verified(path)
    assert frozen["experiment_fingerprint"] == manifest["fingerprint"]
    assert frozen["context_manifest_fingerprint"] == context["fingerprint"]
    assert frozen["accounting"]["status"] == "EXECUTION_COMPLETE"
    assert frozen["accounting"]["logical_terminal"] == 120
    assert frozen["accounting"]["remaining"] == 0
    expected = [tuple(pair) for pair in manifest["execution_order"]]
    rows = frozen["assessments"]
    assert [(r["case_id"], r["strategy"]) for r in rows] == expected
    identities = {(r["case_id"], r["strategy"]): r for r in context["requests"]}
    for row in rows:
        assert row["fingerprint"] == digest({k: v for k, v in row.items() if k != "fingerprint"})
        identity = identities[(row["case_id"], row["strategy"])]
        assert row["request_fingerprint"] == identity["request_fingerprint"]
        assert row["context_fingerprint"] == identity["context_fingerprint"]
    for attempt in frozen["attempts"]:
        assert attempt["fingerprint"] == digest(
            {k: v for k, v in attempt.items() if k != "fingerprint"}
        )
    return frozen


def main():
    protocol = Path("experiments/ai/semantic-context-v1")
    manifest = verified(protocol / "semantic-context-v1.json")
    context = verified(protocol / "context-manifest-v1.json")
    assert manifest["fingerprint"] == (
        "92c4c909e5953d9e0ba07f00126eae75bf8225b128d1eb989a0df02d4c722a04"
    )
    assert context["fingerprint"] == (
        "f9502ddecd8db147c419edd28f3227fb6174a0c8522f59c1b22eb38982e53afe"
    )
    results = Path("experiments/ai/semantic-context-live-v1")
    freeze_path = results / "real-ai-assessments-v1.json"
    frozen = evaluation_gate(freeze_path, manifest, context)
    before = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    pricing_path = Path(
        "experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json"
    )
    pricing_raw = verified(pricing_path)
    pricing = PricingAssumption.model_validate(pricing_raw)
    connectivity = verified(Path("experiments/ai/connectivity-v1/provider-validation-v1.json"))
    connectivity_usage = {
        key: connectivity[key] for key in ("input_tokens", "output_tokens", "total_tokens")
    }
    actual = frozen["accounting"]
    maximum_attempt = pricing.charge(
        manifest["max_input_tokens_per_request"], manifest["max_output_tokens_per_request"]
    )
    cost = publish(
        results / "cost-accounting-v1.json",
        {
            "schema_version": "actual-usage-cost-accounting-v1",
            "assessment_freeze_fingerprint": frozen["fingerprint"],
            "pricing_assumption_path": str(pricing_path),
            "pricing_assumption_fingerprint": pricing.fingerprint,
            "pricing_basis": "VERSIONED_USER_PROVIDED_STANDARD; no cache discounts assumed",
            "provider_reported_cost_usd": None,
            "experiment": actual,
            "connectivity_usage": connectivity_usage,
            "all_live_calls": actual["attempts"] + 1,
            "combined_usage": {
                key: value + connectivity_usage[key] for key, value in actual["usage"].items()
            },
            "configured_primary_maximum_usd": str(maximum_attempt * 120),
            "configured_additional_retry_maximum_usd": str(maximum_attempt * 240),
            "configured_absolute_exposure_usd": str(maximum_attempt * 360),
            "actual_retry_estimated_cost_usd": str(
                sum(
                    (
                        Decimal(a["estimated_cost_usd"])
                        for a in frozen["attempts"]
                        if a["attempt_number"] > 1 and a["estimated_cost_usd"] is not None
                    ),
                    Decimal(0),
                )
            ),
            "long_context_attempt_ids": [
                a["attempt_id"]
                for a in frozen["attempts"]
                if a["usage"] and a["usage"]["input_tokens"] > pricing.short_context_input_cutoff
            ],
            "approaching_context_window_attempt_ids": [
                a["attempt_id"]
                for a in frozen["attempts"]
                if a["usage"]
                and a["usage"]["input_tokens"] + manifest["max_output_tokens_per_request"]
                >= manifest["model_context_window_tokens"] * 0.9
            ],
        },
    )
    usage_inventory = publish(
        results / "context-usage-v1.json",
        {
            "schema_version": "real-context-usage-v1",
            "assessment_freeze_fingerprint": frozen["fingerprint"],
            "context_manifest_fingerprint": context["fingerprint"],
            "requests": [
                {
                    "context": row,
                    "attempts": [
                        {
                            key: attempt.get(key)
                            for key in (
                                "attempt_number",
                                "outcome",
                                "usage",
                                "latency_seconds",
                                "estimated_cost_usd",
                                "cached_input_tokens",
                                "reasoning_output_tokens",
                                "request_id",
                                "response_id",
                            )
                        }
                        for attempt in frozen["attempts"]
                        if (attempt["case_id"], attempt["strategy"])
                        == (row["case_id"], row["strategy"])
                    ],
                }
                for row in context["requests"]
            ],
        },
    )

    # This import and all human-truth access are downstream of the freeze gate.
    from prompt014_cost_preflight import verify_frozen_lineage

    lineage = verify_frozen_lineage()
    truth = verified(Path("experiments/oss/annotation-results/prompt013-f/ground-truth.json"))
    assert truth["fingerprint"] == manifest["ground_truth_fingerprint"]
    assert lineage["freeze"] == manifest["annotation_freeze_fingerprint"]
    cases = truth["cases"]
    context_rows = {(r["case_id"], r["strategy"]): r for r in context["requests"]}
    joined = []
    for case in cases:
        case_id = case["annotation_case_id"]
        assessments = [r for r in frozen["assessments"] if r["case_id"] == case_id]
        joined.append(
            {
                "case_id": case_id,
                "final_human_label": case["final_human_label"],
                "rule_id": case["rule_id"],
                "language": case["language"],
                "repository_id": case["repository_id"],
                "iam_stratum": "PARTIAL_INVALID_IAM"
                if context_rows[(case_id, "LOCAL_ONLY")]["context_diagnostics"]
                else "VALID_IAM",
                "strategies": {
                    r["strategy"]: {
                        "status": r["status"],
                        "judgment": r["assessment"]["judgment"] if r["assessment"] else None,
                        "assessment_fingerprint": r["fingerprint"],
                    }
                    for r in assessments
                },
            }
        )
    join = publish(
        results / "truth-join-v1.json",
        {
            "schema_version": "semantic-truth-join-v1",
            "assessment_freeze_fingerprint": frozen["fingerprint"],
            "ground_truth_fingerprint": truth["fingerprint"],
            "annotation_freeze_fingerprint": lineage["freeze"],
            "cases": joined,
        },
    )
    evaluation = publish(
        results / "evaluation-v1.json",
        {
            "schema_version": "negative-oos-semantic-evaluation-v1",
            "assessment_freeze_fingerprint": frozen["fingerprint"],
            "truth_join_fingerprint": join["fingerprint"],
            "experiment_fingerprint": manifest["fingerprint"],
            "context_manifest_fingerprint": context["fingerprint"],
            "evaluation_driver_fingerprint": digest(Path(__file__).read_text()),
            "metrics_code_fingerprint": digest(
                Path("src/archguard/benchmark/semantic_evaluation.py").read_text()
            ),
            "results": evaluate(cases, frozen, context),
        },
    )
    assert hashlib.sha256(freeze_path.read_bytes()).hexdigest() == before
    receipt = publish(
        results / "post-evaluation-verification-v1.json",
        {
            "status": "PROMPT_014_COMPLETE",
            "assessment_freeze_fingerprint": frozen["fingerprint"],
            "assessment_freeze_file_sha256": before,
            "assessment_freeze_unchanged_after_truth_join": True,
            "truth_join_fingerprint": join["fingerprint"],
            "evaluation_fingerprint": evaluation["fingerprint"],
            "context_usage_fingerprint": usage_inventory["fingerprint"],
            "cost_accounting_fingerprint": cost["fingerprint"],
            "p013_fingerprints": lineage,
            "p013_unchanged": True,
            "structural_v2_evaluation": "NOT_RUN",
            "hybrid_evaluation": "NOT_RUN",
            "security_analysis": "NOT_RUN",
            "prompt015": "NOT_STARTED",
            "provider_reported_cost_usd": None,
        },
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
