"""Truth join is available only after a complete immutable AI ledger passes integrity."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from archguard.benchmark.semantic_positive_evaluation import (
    paired_comparison,
    semantic_metrics,
    usage_summary,
)
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_final_truth import FinalHumanTruth, verify_final_truth
from archguard.infrastructure.semantic_positive_execution import (
    ExecutionBindings,
    load_execution,
    verify_assessments,
)


def evaluate_frozen_positive(
    execution: Path,
    ledger: Path,
    bindings: ExecutionBindings,
    assessment_freeze_fp: str,
    truth_root: Path,
    truth_sha: str,
    truth_receipt_fp: str,
    mapping_path: Path,
    mapping_fp: str,
) -> dict[str, Any]:
    # This gate runs before reading any case-level truth or private evaluation mapping.
    freeze = verify_assessments(ledger, bindings, assessment_freeze_fp)
    _, requests = load_execution(execution, bindings)
    raw = (truth_root / "ground-truth-v1.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != truth_sha:
        raise ValueError("approved final human truth raw SHA drift")
    truth = FinalHumanTruth.model_validate_json(raw)
    if truth.fingerprint != bindings.truth_fingerprint:
        raise ValueError("final truth lineage differs from AI experiment")
    receipt = verify_final_truth(truth_root, truth)
    if receipt["fingerprint"] != truth_receipt_fp:
        raise ValueError("approved final truth receipt drift")
    mapping = json.loads(verify_opaque_seal(mapping_path, mapping_fp))["execution_case_mapping"]
    by_case = {c.scientific_case_id: c for c in truth.cases}
    if (
        set(mapping) != set(by_case)
        or len(set(mapping.values())) != 100
        or set(mapping.values()) != {r.execution_case_id for r in requests}
    ):
        raise ValueError("exact100 scientific/execution identity mapping required")
    reverse = {value: key for key, value in mapping.items()}
    rows = []
    for request in requests:
        value = json.loads((ledger / "results" / (request.request_id + ".json")).read_bytes())
        if (value["request_id"], value["execution_case_id"], value["strategy"]) != (
            request.request_id,
            request.execution_case_id,
            request.strategy,
        ):
            raise ValueError("frozen assessment request identity mismatch")
        if value["status"] not in {"ACCEPTED", "TERMINAL_FAILURE"} or (
            value["status"] == "TERMINAL_FAILURE" and value["assessment"] is not None
        ):
            raise ValueError("frozen assessment decision/status invalid")
        case = by_case[reverse[request.execution_case_id]]
        rows.append(
            {
                "case_id": request.execution_case_id,
                "strategy": request.strategy.value,
                "rule": case.target_rule,
                "language": case.language,
                "human": case.final_category,
                "decision": value["assessment"]["judgment"]
                if value["status"] == "ACCEPTED"
                else None,
                "iam_valid": request.iam_valid,
                "graph_valid": request.graph_valid,
                "truncated": request.truncated,
                "context_chars": request.context_chars,
                **{
                    key: value[key]
                    for key in ("input_tokens", "output_tokens", "latency_seconds", "cost_usd")
                },
            }
        )
    if len(rows) != 300 or Counter(r["strategy"] for r in rows) != {
        s: 100 for s in ("LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE")
    }:
        raise ValueError("complete strategy comparison required")
    strategies = {
        s: [r for r in rows if r["strategy"] == s]
        for s in ("LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE")
    }
    stratified = {}
    for strategy, group in strategies.items():
        stratified[strategy] = {
            field: {
                str(value): {
                    "descriptive_only": True,
                    "metrics": semantic_metrics([r for r in group if r[field] == value]),
                }
                for value in sorted({r[field] for r in group}, key=str)
            }
            for field in ("rule", "language", "human", "iam_valid", "graph_valid", "truncated")
        }
    return {
        "schema_version": "p016-frozen-semantic-evaluation-v1",
        "assessment_freeze_fingerprint": freeze["fingerprint"],
        "truth_fingerprint": truth.fingerprint,
        "by_strategy": {
            s: {"metrics": semantic_metrics(group), "usage": usage_summary(group)}
            for s, group in strategies.items()
        },
        "strata": stratified,
        "paired": {
            first + "_VS_" + second: paired_comparison(strategies[first], strategies[second])
            for first, second in (
                ("GRAPH_GUIDED", "EXPANDED_BASELINE"),
                ("GRAPH_GUIDED", "LOCAL_ONLY"),
                ("LOCAL_ONLY", "EXPANDED_BASELINE"),
            )
        },
        "construction_intent_used": False,
        "natural_prevalence_claim": False,
    }
