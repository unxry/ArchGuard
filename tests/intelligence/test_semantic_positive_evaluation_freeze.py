"""Synthetic 100-case identity joins; no real corpus, credentials, or provider."""

import hashlib
import json
import socket
from types import SimpleNamespace

import pytest

from archguard.architecture.intelligence.models import ContextStrategy
from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.infrastructure import semantic_positive_evaluator as evaluator
from archguard.infrastructure.semantic_final_truth import (
    LINEAGE_KEYS,
    FinalHumanTruth,
    TruthCase,
    freeze_final_truth,
)
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    DECISIONS,
    STRATEGIES,
    aggregate_results,
    append_sealed,
    evaluation_io,
    freeze_evaluation,
    prepare_join,
    validate_join,
    verify_evaluation,
    verify_truth,
)
from archguard.infrastructure.semantic_positive_execution import ExecutionBindings


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n")


def sealed(value):
    return value | {"fingerprint": digest(value)}


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir()
    truth_root = private / "final-human-ground-truth-v1"
    cases = []
    for rule in range(1, 6):
        for language in ("JAVA", "TYPESCRIPT"):
            for n in range(10):
                category = "POSITIVE" if n < 5 else "NEGATIVE"
                if rule == 3 and language == "JAVA" and n == 9:
                    category = "OUT_OF_SCOPE"
                if rule == 5 and ((language == "JAVA" and n >= 8) or n == 9):
                    category = "UNCERTAIN"
                cases.append(
                    TruthCase(
                        scientific_case_id=f"synthetic-{len(cases):03d}",
                        target_rule=f"ARCH20{rule}",
                        language=language,
                        final_category=category,
                        resolution_provenance="A_B_AGREEMENT"
                        if category in {"POSITIVE", "NEGATIVE"}
                        else "THIRD_HUMAN_ADJUDICATION",
                    )
                )
    truth = seal(FinalHumanTruth, lineage={k: "a" * 64 for k in LINEAGE_KEYS}, cases=tuple(cases))
    truth_receipt = freeze_final_truth(truth_root, truth)
    truth_public = tmp_path / "truth-public.json"
    public = append_sealed(truth_public, {"ground_truth_fingerprint": truth.fingerprint})
    expected = {
        "truth_sha256": truth_receipt["ground_truth_sha256"],
        "truth_fingerprint": truth.fingerprint,
        "truth_receipt_fingerprint": truth_receipt["fingerprint"],
        "truth_lineage_fingerprint": truth_receipt["lineage_fingerprint"],
        "truth_public_fingerprint": public["fingerprint"],
    }
    bindings = ExecutionBindings(
        execution_freeze_fingerprint="a" * 64,
        protocol_fingerprint="b" * 64,
        context_manifest_fingerprint="c" * 64,
        request_manifest_fingerprint="d" * 64,
        truth_fingerprint=truth.fingerprint,
    )
    ledger = private / "ai-ledger"
    ledger.mkdir()
    requests, normalized, mapping = [], [], {}
    for i, c in enumerate(cases):
        case_id = hashlib.sha256(("case-" + c.scientific_case_id).encode()).hexdigest()
        mapping[c.scientific_case_id] = case_id
        for strategy in STRATEGIES:
            request_id = hashlib.sha256((case_id + strategy).encode()).hexdigest()
            request = SimpleNamespace(
                request_id=request_id,
                execution_case_id=case_id,
                strategy=ContextStrategy(strategy),
                iam_valid=True,
                graph_valid=True,
                truncated=False,
                context_chars=50,
                request_fingerprint="e" * 64,
                context_fingerprint="f" * 64,
            )
            requests.append(request)
            decision = {
                "POSITIVE": "SUPPORTED",
                "NEGATIVE": "NOT_SUPPORTED",
                "UNCERTAIN": "INSUFFICIENT_CONTEXT",
                "OUT_OF_SCOPE": "NOT_APPLICABLE",
            }[c.final_category]
            if i == 0:
                decision = {
                    "LOCAL_ONLY": "INSUFFICIENT_CONTEXT",
                    "GRAPH_GUIDED": "SUPPORTED",
                    "EXPANDED_BASELINE": "NOT_SUPPORTED",
                }[strategy]
            if i == 5:
                decision = {
                    "LOCAL_ONLY": "NOT_APPLICABLE",
                    "GRAPH_GUIDED": "SUPPORTED",
                    "EXPANDED_BASELINE": "NOT_SUPPORTED",
                }[strategy]
            assessment = {"request_id": request_id, "judgment": decision}
            values = {
                "input_tokens": 100,
                "output_tokens": 2,
                "latency_seconds": 1.0,
                "cost_usd": "0.01",
            }
            result = {
                "request_id": request_id,
                "execution_case_id": case_id,
                "strategy": strategy,
                "provider": "openai",
                "model": "gpt-6-luna",
                "status": "ACCEPTED",
                "assessment": assessment,
                "attempts": 1,
                **values,
            }
            if i == 0 and strategy == "GRAPH_GUIDED":
                result.update({k: None for k in values})
            path = f"recovery/results/{request_id}.json"
            write(ledger / path, result)
            write(
                ledger / f"attempts/{request_id}-1.json",
                {
                    "request_id": request_id,
                    "assessment": assessment,
                    "request_fingerprint": "e" * 64,
                    "context_fingerprint": "f" * 64,
                    **values,
                },
            )
            normalized.append(result | {"result_path": path})
    write(ledger / "results/historical.json", {"status": "TERMINAL_FAILURE", "assessment": None})
    dataset = sealed({"bindings": bindings.model_dump(), "assessments": list(reversed(normalized))})
    write(ledger / "normalized-assessments.json", dataset)
    receipt = sealed(
        {
            "bindings": bindings.model_dump(),
            "logical_results": 300,
            "complete": True,
            "accepted_result_paths": {r["request_id"]: r["result_path"] for r in normalized},
            "files": {
                p.relative_to(ledger).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in ledger.rglob("*")
                if p.is_file()
            },
        }
    )
    write(ledger / "assessment-freeze.json", receipt)
    identity_map = sealed({"execution_case_mapping": mapping})
    mapping_path = private / "identity-map.json"
    write(mapping_path, identity_map)
    monkeypatch.setattr(
        evaluator,
        "load_execution",
        lambda *a: (SimpleNamespace(analysis_plan_fingerprint="9" * 64), tuple(reversed(requests))),
    )

    def join(**overrides):
        params = dict(
            execution=private / "execution",
            ledger=ledger,
            bindings=bindings,
            assessment_freeze_fp=receipt["fingerprint"],
            truth_root=truth_root,
            truth_sha=expected["truth_sha256"],
            truth_receipt_fp=truth_receipt["fingerprint"],
            mapping_path=mapping_path,
            mapping_fp=identity_map["fingerprint"],
            normalized_fp=dataset["fingerprint"],
        )
        return evaluator.join_frozen_positive(**(params | overrides))

    joined = join()
    distributions = {
        s: {
            d: sum(r["strategy"] == s and r["decision"] == d for r in joined["rows"])
            for d in DECISIONS
        }
        for s in STRATEGIES
    }
    operational = {"by_strategy": {s: {"input_tokens": 10000} for s in STRATEGIES}}
    return SimpleNamespace(
        root=tmp_path,
        private=private,
        ledger=ledger,
        truth_root=truth_root,
        truth_public=truth_public,
        expected=expected,
        joined=joined,
        distributions=distributions,
        mapping_path=mapping_path,
        join=join,
        operational=operational,
    )


@pytest.mark.parametrize(
    "key",
    [
        "truth_sha256",
        "truth_fingerprint",
        "truth_lineage_fingerprint",
        "truth_receipt_fingerprint",
        "truth_public_fingerprint",
    ],
)
def test_exact_truth_fingerprint_guards(synthetic, key):
    s = synthetic
    with pytest.raises(ValueError):
        verify_truth(s.truth_root, s.truth_public, s.expected | {key: "0" * 64})
    assert (
        verify_truth(s.truth_root, s.truth_public, s.expected)[1]["counts"]["binary_eligible"] == 96
    )


@pytest.mark.parametrize("key", ["assessment_freeze_fp", "normalized_fp"])
def test_exact_ai_freeze_guard(synthetic, key):
    with pytest.raises(ValueError):
        synthetic.join(**{key: "0" * 64})


def test_reversed_arrays_join_only_by_stable_identity(synthetic):
    rows = synthetic.joined["rows"]
    assert len(rows) == 300 and len({r["case_id"] for r in rows}) == 100
    assert len({(r["scientific_case_id"], r["strategy"]) for r in rows}) == 300
    assert all(r["human"] == "POSITIVE" for r in rows if r["scientific_case_id"] == "synthetic-000")
    assert all(r["human"] == "NEGATIVE" for r in rows if r["scientific_case_id"] == "synthetic-005")
    assert synthetic.join() == synthetic.joined


@pytest.mark.parametrize("kind", ["missing", "duplicate", "ambiguous", "distribution", "failure"])
def test_join_and_frozen_distribution_reconciliation(synthetic, kind):
    joined = json.loads(canonical(synthetic.joined))
    if kind == "missing":
        joined["rows"].pop()
    elif kind == "duplicate":
        joined["rows"][0] = joined["rows"][1]
    elif kind == "ambiguous":
        joined["rows"][0]["scientific_case_id"] = joined["rows"][-1]["scientific_case_id"]
    else:
        joined["rows"][0]["decision"] = "NOT_APPLICABLE" if kind == "distribution" else None
    with pytest.raises(ValueError):
        validate_join(joined, synthetic.distributions)


def prepare(s):
    destination = s.private / "p017-evaluation-v1"
    binding = prepare_join(destination, s.joined, s.expected, s.distributions)
    return destination, binding


def test_metrics_denominators_strata_exclusions_and_paired_alignment(synthetic):
    s = synthetic
    _, binding = prepare(s)
    result = aggregate_results(s.joined, binding, s.operational)
    local = result["by_strategy"]["LOCAL_ONLY"]["metrics"]
    assert [local[k] for k in ["TP", "FP", "TN", "FN"]] == [49, 0, 45, 0]
    assert local["ABSTAIN_POSITIVE"] == 1 and local["NOT_APPLICABLE_ON_NEGATIVE"] == 1
    assert local["binary_eligible"] == 96 and local["binary_excluded"] == 4
    assert local["definitive_count"] == 94 and local["definitive_coverage"] == 94 / 96
    assert (
        local["effective_recall"] == 49 / 50 and local["effective_negative_correctness"] == 45 / 46
    )
    assert local["effective_correctness"] == 94 / 96 and local["recall_definitive"] == 1
    assert local["category_decision_counts"]["UNCERTAIN"]["INSUFFICIENT_CONTEXT"] == 3
    for strategy in STRATEGIES:
        for field in ["rule", "language"]:
            strata = result["strata"][strategy][field]
            assert sum(g["metrics"]["binary_eligible"] for g in strata.values()) == 96
            assert all(g["descriptive_only"] for g in strata.values())
    pair = result["paired"]["GRAPH_GUIDED_VS_LOCAL_ONLY"]["comparisons"]
    assert pair["nondefinitive_transitions"]["second_abstains_first_definitive"] == 1
    assert pair["applicability"]["second_only"] == 1
    assert (
        sum(pair["correctness"][k] for k in ["both", "first_only", "second_only", "neither"]) == 96
    )
    assert pair["input_tokens"]["paired_N"] == 99
    assert result["by_strategy"]["GRAPH_GUIDED"]["usage"]["input_tokens"]["missing_N"] == 1
    assert (
        result["by_strategy"]["GRAPH_GUIDED"]["accepted_response_usage"]["input_tokens"][
            "measured_N"
        ]
        == 100
    )
    assert all(not p["significance_test_run"] for p in result["paired"].values())
    assert result["provider_calls"] == 0 and result["construction_intent_used"] is False


def test_deterministic_private_join_public_aggregate_and_append_only_freeze(synthetic):
    s = synthetic
    original = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in s.ledger.rglob("*") if p.is_file()
    }
    destination, binding = prepare(s)
    aggregate = aggregate_results(s.joined, binding, s.operational)
    assert aggregate == aggregate_results(s.joined, binding, s.operational)
    for row in s.joined["rows"]:
        assert row["case_id"] not in canonical(aggregate)
        assert row["scientific_case_id"] not in canonical(aggregate)
        assert row["request_id"] not in canonical(binding)
    receipt = freeze_evaluation(destination, s.joined, binding, aggregate)
    assert verify_evaluation(destination, receipt["fingerprint"]) == receipt
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in destination.iterdir())
    with pytest.raises(ValueError, match="append-only"):
        freeze_evaluation(destination, s.joined, binding, aggregate)
    with pytest.raises(ValueError):
        prepare(s)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == sha for p, sha in original.items())
    (destination / "input-join-v1.json").write_text("{}")
    with pytest.raises(ValueError):
        verify_evaluation(destination, receipt["fingerprint"])


def test_network_credentials_construction_and_ai_writes_are_denied(synthetic):
    s = synthetic
    construction = s.private / "construction-intent.json"
    construction.write_text('{"do_not_decode":true}')
    env = s.root / ".env.ai.local"
    env.write_text("SYNTHETIC_CREDENTIAL_CANARY")
    with evaluation_io(
        s.root, (s.ledger, s.truth_root, s.mapping_path, s.truth_public), s.private / "output"
    ):
        for path in [construction, env]:
            with pytest.raises(PermissionError):
                path.read_bytes()
        with pytest.raises(PermissionError):
            (s.ledger / "new.json").write_text("{}")
        with pytest.raises(PermissionError):
            socket.getaddrinfo("example.invalid", 443)
        assert synthetic.join() == synthetic.joined


def test_input_join_drift_rejected_before_metric_arithmetic(synthetic):
    s = synthetic
    _, binding = prepare(s)
    joined = json.loads(canonical(s.joined))
    joined["rows"][0]["decision"] = "NOT_APPLICABLE"
    with pytest.raises(ValueError, match="fingerprint"):
        aggregate_results(joined, binding, s.operational)
