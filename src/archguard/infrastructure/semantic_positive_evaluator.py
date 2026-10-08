"""Truth join is available only after a complete immutable AI ledger passes integrity."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
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
from archguard.infrastructure.semantic_positive_offline import capability_path


def join_frozen_positive(
    execution: Path,
    ledger: Path,
    bindings: ExecutionBindings,
    assessment_freeze_fp: str,
    truth_root: Path,
    truth_sha: str,
    truth_receipt_fp: str,
    mapping_path: Path,
    mapping_fp: str,
    normalized_fp: str | None = None,
) -> dict[str, Any]:
    # This gate runs before reading any case-level truth or private evaluation mapping.
    freeze = verify_assessments(ledger, bindings, assessment_freeze_fp)
    protocol, requests = load_execution(execution, bindings)
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
    normalized = None
    if normalized_fp is not None:
        dataset = json.loads(
            verify_opaque_seal(ledger / "normalized-assessments.json", normalized_fp)
        )
        if dataset["bindings"] != bindings.model_dump():
            raise ValueError("normalized assessment bindings mismatch")
        normalized = {v["request_id"]: v for v in dataset["assessments"]}
        if (
            len(normalized) != len(dataset["assessments"])
            or set(normalized) != {r.request_id for r in requests}
            or set(freeze.get("accepted_result_paths", {})) != set(normalized)
        ):
            raise ValueError("exact300 unique normalized assessment identities required")
    rows = []
    for request in requests:
        if normalized is None:
            value = json.loads((ledger / "results" / (request.request_id + ".json")).read_bytes())
        else:
            value = normalized[request.request_id]
            path = freeze["accepted_result_paths"][request.request_id]
            if value["result_path"] != path or path not in freeze["files"]:
                raise ValueError("normalized accepted-path selection mismatch")
            selected = json.loads(capability_path(ledger, path).read_bytes())
            if selected != {k: v for k, v in value.items() if k != "result_path"}:
                raise ValueError("normalized assessment differs from frozen selected result")
            if value["status"] != "ACCEPTED":
                raise ValueError("P017 requires 300 accepted semantic assessments")
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
        final_usage = {}
        if normalized is not None:
            name = f"attempts/{request.request_id}-{value['attempts']}.json"
            if name not in freeze["files"]:
                raise ValueError("accepted provider attempt absent from freeze")
            event = json.loads(capability_path(ledger, name).read_bytes())
            if (
                event["request_id"] != request.request_id
                or event["assessment"] != value["assessment"]
                or event["request_fingerprint"] != request.request_fingerprint
                or event["context_fingerprint"] != request.context_fingerprint
            ):
                raise ValueError("accepted-response resource binding mismatch")
            final_usage = {
                key: event[key]
                for key in ("input_tokens", "output_tokens", "latency_seconds", "cost_usd")
            }
        rows.append(
            {
                "case_id": request.execution_case_id,
                "scientific_case_id": case.scientific_case_id,
                "request_id": request.request_id,
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
                "accepted_response_usage": final_usage,
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
    if (
        Counter(r["case_id"] for r in rows) != {c: 3 for c in reverse}
        or len({(r["case_id"], r["strategy"]) for r in rows}) != 300
    ):
        raise ValueError("exactly one assessment per case/strategy required")
    joined = {
        "schema_version": "p017-frozen-input-join-v1",
        "assessment_freeze_fingerprint": freeze["fingerprint"],
        "normalized_assessment_fingerprint": normalized_fp,
        "truth_fingerprint": truth.fingerprint,
        "truth_raw_sha256": truth_sha,
        "truth_receipt_fingerprint": truth_receipt_fp,
        "mapping_fingerprint": mapping_fp,
        "analysis_plan_fingerprint": protocol.analysis_plan_fingerprint,
        "execution_bindings": bindings.model_dump(),
        "resource_policy": {
            "primary": "FROZEN_CUMULATIVE_LOGICAL_RESULT; PAIRED_COMPLETE_KNOWN_CASES",
            "supplemental": "FINAL_ACCEPTED_PROVIDER_RESPONSE; ONE_PER_CASE_STRATEGY",
            "quality_denominator": "BINARY_ELIGIBLE_REFERENCE",
            "resource_denominator": "ALL_REFERENCE_CATEGORIES; NO_UNKNOWN_USAGE_ZERO_FILL",
        },
        "rows": sorted(rows, key=lambda r: (r["case_id"], r["strategy"])),
    }
    return joined | {"fingerprint": digest(joined)}


def evaluate_positive_join(joined: dict[str, Any]) -> dict[str, Any]:
    if digest({k: v for k, v in joined.items() if k != "fingerprint"}) != joined["fingerprint"]:
        raise ValueError("frozen input join fingerprint mismatch")
    rows = joined["rows"]
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
        "schema_version": "p017-frozen-semantic-evaluation-v1",
        "input_join_fingerprint": joined["fingerprint"],
        "assessment_freeze_fingerprint": joined["assessment_freeze_fingerprint"],
        "truth_fingerprint": joined["truth_fingerprint"],
        "by_strategy": {
            s: {
                "metrics": semantic_metrics(group),
                "usage": usage_summary(group),
                "accepted_response_usage": usage_summary(
                    [r | r["accepted_response_usage"] for r in group]
                ),
            }
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
    normalized_fp: str | None = None,
) -> dict[str, Any]:
    return evaluate_positive_join(
        join_frozen_positive(
            execution,
            ledger,
            bindings,
            assessment_freeze_fp,
            truth_root,
            truth_sha,
            truth_receipt_fp,
            mapping_path,
            mapping_fp,
            normalized_fp,
        )
    )
