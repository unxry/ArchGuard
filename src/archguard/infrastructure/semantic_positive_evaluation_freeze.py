"""Offline, identity-bound P017 joins and append-only aggregate evaluation freezes."""

import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_positive_evaluation import ratio
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_final_truth import FinalHumanTruth, verify_final_truth
from archguard.infrastructure.semantic_positive_evaluator import evaluate_positive_join

STRATEGIES = ("LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE")
DECISIONS = ("SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE")
_IO: ContextVar[tuple[Path, tuple[Path, ...], Path] | None] = ContextVar("p017_io", default=None)


def _audit(event: str, args: tuple[Any, ...]) -> None:
    policy = _IO.get()
    if policy is None:
        return
    if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"}:
        raise PermissionError("P017 prohibits network/provider calls")
    if event != "open" or isinstance(args[0], int):
        return
    root, allowed, output = policy
    path = Path(os.fsdecode(args[0])).resolve()
    if path.name.startswith(".env"):
        raise PermissionError("P017 does not read credentials")
    writes = any(c in (args[1] or "") for c in "wax+") or bool(
        args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
    )
    if writes and any(path == p or p in path.parents for p in allowed):
        raise PermissionError("frozen scientific inputs are read-only")
    if path == root or root in path.parents:
        if path == output or output in path.parents:
            return
        if not writes and any(path == p or p in path.parents for p in allowed):
            return
        raise PermissionError("P017 construction/private capability denied")


sys.addaudithook(_audit)


@contextmanager
def evaluation_io(artifact_root: Path, inputs: tuple[Path, ...], output: Path) -> Iterator[None]:
    token = _IO.set((artifact_root.resolve(), tuple(p.resolve() for p in inputs), output.resolve()))
    try:
        yield
    finally:
        _IO.reset(token)


def append_sealed(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    if "fingerprint" not in value:
        value = value | {"fingerprint": digest(value)}
    elif digest({k: v for k, v in value.items() if k != "fingerprint"}) != value["fingerprint"]:
        raise ValueError("artifact fingerprint mismatch")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)
    return value


def verify_truth(
    root: Path, public_path: Path, expected: dict[str, str]
) -> tuple[FinalHumanTruth, dict[str, Any]]:
    raw = (root / "ground-truth-v1.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected["truth_sha256"]:
        raise ValueError("P017_BLOCKED_TRUTH_DRIFT")
    truth = FinalHumanTruth.model_validate_json(raw)
    receipt = verify_final_truth(root, truth)
    if (
        truth.fingerprint != expected["truth_fingerprint"]
        or receipt["fingerprint"] != expected["truth_receipt_fingerprint"]
        or receipt["lineage_fingerprint"] != expected["truth_lineage_fingerprint"]
    ):
        raise ValueError("P017_BLOCKED_TRUTH_DRIFT")
    public = json.loads(verify_opaque_seal(public_path, expected["truth_public_fingerprint"]))
    if public["ground_truth_fingerprint"] != truth.fingerprint:
        raise ValueError("P017_BLOCKED_TRUTH_DRIFT")
    for i, u, o in ((1, 0, 0), (2, 0, 0), (3, 0, 1), (4, 0, 0), (5, 3, 0)):
        c = receipt["by_rule"][f"ARCH20{i}"]
        if [c[k] for k in ("N", "POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")] != [
            20,
            10,
            10 - u - o,
            u,
            o,
        ]:
            raise ValueError("P017_BLOCKED_TRUTH_DRIFT")
    for language, n, u, o in (("JAVA", 22, 2, 1), ("TYPESCRIPT", 24, 1, 0)):
        c = receipt["by_language"][language]
        if [c[k] for k in ("N", "POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")] != [
            50,
            25,
            n,
            u,
            o,
        ]:
            raise ValueError("P017_BLOCKED_TRUTH_DRIFT")
    return truth, receipt


def validate_join(joined: dict[str, Any], distributions: dict[str, dict[str, int]]) -> None:
    rows = joined["rows"]
    if len(rows) != 300 or len({r["request_id"] for r in rows}) != 300:
        raise ValueError("exact300 unique joined request identities required")
    if (
        len({r["case_id"] for r in rows}) != 100
        or len({r["scientific_case_id"] for r in rows}) != 100
    ):
        raise ValueError("exact100 scientific/execution identities required")
    identity = {(r["case_id"], r["strategy"]) for r in rows}
    if identity != {(c, s) for c in {r["case_id"] for r in rows} for s in STRATEGIES}:
        raise ValueError("missing/duplicate case-strategy join")
    forward: dict[str, str] = {}
    for r in rows:
        if r["case_id"] in forward and forward[r["case_id"]] != r["scientific_case_id"]:
            raise ValueError("ambiguous scientific/execution mapping")
        forward[r["case_id"]] = r["scientific_case_id"]
        if r["decision"] not in DECISIONS:
            raise ValueError("accepted dataset cannot fabricate technical failures")
    for case in forward:
        if len({(r["human"], r["rule"], r["language"]) for r in rows if r["case_id"] == case}) != 1:
            raise ValueError("paired human reference mismatch")
    for strategy in STRATEGIES:
        group = [r for r in rows if r["strategy"] == strategy]
        if Counter(r["human"] for r in group) != {
            "POSITIVE": 50,
            "NEGATIVE": 46,
            "UNCERTAIN": 3,
            "OUT_OF_SCOPE": 1,
        }:
            raise ValueError("P017_BLOCKED_TRUTH_DRIFT")
        actual = Counter(r["decision"] for r in group)
        if {k: actual[k] for k in DECISIONS} != distributions[strategy]:
            raise ValueError("P017_BLOCKED_AI_DISTRIBUTION_MISMATCH")


def prepare_join(
    destination: Path,
    joined: dict[str, Any],
    inputs: dict[str, str],
    distributions: dict[str, dict[str, int]],
) -> dict[str, Any]:
    validate_join(joined, distributions)
    if destination.parent.name != "private" or destination.exists() or destination.is_symlink():
        raise ValueError("new private append-only evaluation destination required")
    destination.mkdir(mode=0o700)
    append_sealed(destination / "input-join-v1.json", joined)
    raw = (destination / "input-join-v1.json").read_bytes()
    binding = {
        "schema_version": "p017-evaluation-input-binding-v1",
        "status": "EVALUATION_INPUT_JOIN_FROZEN_BEFORE_METRICS",
        "inputs": inputs,
        "input_join_fingerprint": joined["fingerprint"],
        "private_join_sha256": hashlib.sha256(raw).hexdigest(),
        "scientific_cases": 100,
        "joined_assessments": 300,
        "missing_joins": 0,
        "duplicate_joins": 0,
        "resource_policy": joined["resource_policy"],
        "metrics_calculated": False,
        "provider_calls": 0,
        "construction_intent_decoded": False,
    }
    return binding | {"fingerprint": digest(binding)}


def resource_differences(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in ("input_tokens", "output_tokens", "latency_seconds", "cost_usd"):
        x, y = first[key]["total_known"], second[key]["total_known"]
        a, b = Decimal(str(x)), Decimal(str(y))
        result[key] = {
            "first_minus_second_total": str(a - b),
            "relative_reduction_first_vs_second": float((b - a) / b) if b else None,
            "first_measured_N": first[key]["measured_N"],
            "second_measured_N": second[key]["measured_N"],
        }
    return result


def aggregate_results(
    joined: dict[str, Any], binding: dict[str, Any], operational: dict[str, Any]
) -> dict[str, Any]:
    if joined["fingerprint"] != binding["input_join_fingerprint"]:
        raise ValueError("metrics must use the prospectively frozen input join")
    result = evaluate_positive_join(joined)
    for strategy, group in result["by_strategy"].items():
        m = group["metrics"]
        if (
            m["N"],
            m["binary_eligible"],
            m["binary_excluded"],
            m["technical_failure_count_all"],
        ) != (100, 96, 4, 0):
            raise ValueError("P017 confusion/reference reconciliation failed")
        for field in ("rule", "language"):
            groups = result["strata"][strategy][field].values()
            for key in (
                "N",
                "binary_eligible",
                "TP",
                "FP",
                "TN",
                "FN",
                "ABSTAIN_POSITIVE",
                "ABSTAIN_NEGATIVE",
                "NOT_APPLICABLE_ON_POSITIVE",
                "NOT_APPLICABLE_ON_NEGATIVE",
            ):
                if sum(g["metrics"][key] for g in groups) != m[key]:
                    raise ValueError("stratum reconciliation failed")
    quality = result["by_strategy"]
    resources = {
        first + "_VS_" + second: {
            "primary_prospective_paired": result["paired"][first + "_VS_" + second]["comparisons"],
            "supplemental_final_accepted_100_per_strategy": resource_differences(
                quality[first]["accepted_response_usage"],
                quality[second]["accepted_response_usage"],
            ),
            "operational_known_input_reduction": ratio(
                operational["by_strategy"][second]["input_tokens"]
                - operational["by_strategy"][first]["input_tokens"],
                operational["by_strategy"][second]["input_tokens"],
            ),
        }
        for first, second in (
            ("GRAPH_GUIDED", "EXPANDED_BASELINE"),
            ("GRAPH_GUIDED", "LOCAL_ONLY"),
            ("LOCAL_ONLY", "EXPANDED_BASELINE"),
        )
    }
    readiness = {
        "PRIMARY_SEMANTIC_EFFECTIVENESS_EVALUATED": True,
        **{
            "SEMANTIC_" + name + "_AVAILABLE": all(
                g["metrics"][key] is not None for g in quality.values()
            )
            for name, key in (
                ("PRECISION", "precision"),
                ("RECALL", "recall_definitive"),
                ("F1", "F1_definitive"),
                ("FPR", "FPR_definitive"),
                ("FNR", "FNR_definitive"),
            )
        },
        "RQ3_EVIDENCE_AVAILABLE": True,
        "RQ5_TRUTH_AWARE_EVIDENCE_AVAILABLE": True,
    }
    result.update(
        {
            "input_binding_fingerprint": binding["fingerprint"],
            "frozen_inputs": binding["inputs"],
            "resource_policy": binding["resource_policy"],
            "RQ5": resources,
            "measured_operational_history": operational,
            "readiness": readiness,
            "provider_calls": 0,
            "significance_test_run": False,
            "limitations": [
                "CONTROLLED_HOLDOUT; NOT_NATURAL_PREVALENCE; N100_BINARY96_EXCLUDED4",
                "RULE_AND_LANGUAGE_STRATA_DESCRIPTIVE; NO_CAUSAL_OR_GENERAL_SUPERIORITY_CLAIM",
                "P016_INTERRUPTED_AFTER106; BLINDED_AMENDMENT_COMMITTED_BEFORE_SUBSEQUENT_CALLS",
                "SCHEMA_RECOVERY3; AMBIGUOUS_REPLACEMENT1; ACCEPTED_DUPLICATES0",
                "CONFIRMED_REPEATED_COMPLETED_EXECUTIONS3; POSSIBLE_DUPLICATE_PROCESSING1",
                "NO_EXACTLY_ONCE_REMOTE_PROCESSING_CLAIM; TRUTH_UNAVAILABLE_DURING_RECOVERY",
                "UNKNOWN_ORIGINAL_INVOCATION_USAGE; ESTIMATED_COST_NOT_ACTUAL_INVOICE",
                "PRIMARY_RESOURCE_PAIRS_USE_COMPLETE_KNOWN_LOGICAL_TOTALS; MISSING_NOT_ZERO_FILLED",
                "SUPPLEMENTAL_ACCEPTED_RESPONSE_USAGE_EXCLUDES_INVALID_ATTEMPT_OVERHEAD",
                "NO_CONSTRUCTION_INTENT; NO_STATIC_GRAPH_V2_HYBRID_SECURITY_OR_ABLATION_EVALUATION",
            ],
        }
    )
    return result | {"fingerprint": digest(result)}


def freeze_evaluation(
    destination: Path, joined: dict[str, Any], binding: dict[str, Any], aggregate: dict[str, Any]
) -> dict[str, Any]:
    if (destination / "evaluation-freeze-v1.json").exists():
        raise ValueError("evaluation freeze append-only")
    verify_opaque_seal(destination / "input-join-v1.json", joined["fingerprint"])
    append_sealed(destination / "aggregate-evaluation-v1.json", aggregate)
    receipt = {
        "schema_version": "p017-evaluation-freeze-v1",
        "status": "SEMANTIC_EFFECTIVENESS_RESULTS_FROZEN",
        "input_join_fingerprint": joined["fingerprint"],
        "input_binding_fingerprint": binding["fingerprint"],
        "aggregate_fingerprint": aggregate["fingerprint"],
        "files": {
            name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
            for name in ("input-join-v1.json", "aggregate-evaluation-v1.json")
        },
        "provider_calls": 0,
        "construction_intent_decoded": False,
    }
    return append_sealed(destination / "evaluation-freeze-v1.json", receipt)


def verify_evaluation(destination: Path, fingerprint: str) -> dict[str, Any]:
    receipt: dict[str, Any] = json.loads(
        verify_opaque_seal(destination / "evaluation-freeze-v1.json", fingerprint)
    )
    if destination.is_symlink() or {p.name for p in destination.iterdir()} != {
        "input-join-v1.json",
        "aggregate-evaluation-v1.json",
        "evaluation-freeze-v1.json",
    }:
        raise ValueError("frozen evaluation inventory drift")
    for name, sha in receipt["files"].items():
        p = destination / name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError("frozen evaluation bytes drift")
    return receipt
