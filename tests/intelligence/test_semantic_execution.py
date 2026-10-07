import ast
import importlib.util
import json
from pathlib import Path

import pytest

from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.selection import resolve_node
from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.semantic_evaluation import evaluate, metrics
from archguard.benchmark.semantic_preflight import (
    PricingAssumption,
    experiment_manifest,
    research_request,
)
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_preflight import wire_payload


@pytest.fixture
def executor(monkeypatch):
    scripts = Path(__file__).parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "blind_executor", scripts / "prompt014_execute.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def frozen_requests(tmp_path, chain):
    m = experiment_manifest("a" * 64, "b" * 64, "c" * 64, tuple(f"case-{i}" for i in range(40)))
    inputs, workspace, _ = chain
    packs = {
        c.strategy: GraphGuidedContextBuilder().build(
            resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, workspace, c
        )
        for c in m.strategies
    }
    requests = tmp_path / "requests"
    requests.mkdir()
    rows = []
    for case, strategy in m.execution_order:
        pack = packs[strategy]
        request = research_request(case, "ARCH201", pack, m)
        rows.append(
            {
                "case_id": case,
                "strategy": strategy.value,
                "request_fingerprint": digest(request),
                "context_fingerprint": pack.manifest.context_fingerprint,
            }
        )
        write_new(
            requests / (digest((case, strategy.value)) + ".json"),
            {"structured_request": request, "provider_payload": wire_payload(request, m.model)},
        )
    payload = {"experiment_fingerprint": m.fingerprint, "requests": rows}
    return m, payload | {"fingerprint": digest(payload)}, requests


def response(payload, invalid=False):
    task = json.loads(payload["input"][1]["content"])["task"]
    assessment = {
        "candidate_rule_id": task["candidate_rule_id"],
        "subject_node_ids": [task["subject_node_id"]],
        "judgment": "NOT_SUPPORTED",
        "short_reason": "Evidence does not support the concern.",
        "evidence_refs": ["BOGUS"] if invalid else [],
        "limitations": [],
    }
    return {
        "outcome": "SUCCESS",
        "assessment_text": json.dumps(assessment),
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        "actual_model": "gpt-6-luna",
        "response_id": "resp_fixture",
        "latency_seconds": 0.01,
        "retryable": False,
        "configuration_error": False,
    }


def test_bounded_retries_invalid_terminal_and_resume_without_repeating_success(
    executor, frozen_requests, tmp_path
):
    m, c, requests = frozen_requests
    calls = []

    def transport(payload, settings, timeout):
        calls.append(payload)
        if len(calls) <= 2:
            return {
                "outcome": "TECHNICAL_FAILURE",
                "error_code": "AI_PROVIDER_TIMEOUT",
                "assessment_text": None,
                "usage": None,
                "latency_seconds": 0.01,
                "retryable": True,
                "configuration_error": False,
            }
        return response(payload, invalid=len(calls) == 4)

    out = tmp_path / "run"
    result = executor.execute(
        m,
        c,
        requests,
        out,
        None,
        seal(PricingAssumption),
        {"estimated_usage_cost_usd": "0.0000045"},
        transport=transport,
        sleeper=lambda _: None,
    )
    assert result["status"] == "EXECUTION_COMPLETE" and result["successful"] == 119
    assert result["attempts"] == 122 and result["retries"] == 2
    from prompt014_evaluate import evaluation_gate

    path = out / "real-ai-assessments-v1.json"
    assert evaluation_gate(path, m.model_dump(mode="json"), c)["accounting"] == {
        k: v for k, v in result.items() if k != "assessment_freeze_fingerprint"
    }
    tampered = json.loads(path.read_text())
    tampered["assessments"][0]["request_fingerprint"] = "0" * 64
    row = tampered["assessments"][0]
    row["fingerprint"] = digest({k: v for k, v in row.items() if k != "fingerprint"})
    tampered["fingerprint"] = digest({k: v for k, v in tampered.items() if k != "fingerprint"})
    write_new(out / "tampered-freeze.json", tampered)
    with pytest.raises(AssertionError):
        evaluation_gate(out / "tampered-freeze.json", m.model_dump(mode="json"), c)
    frozen = (out / "real-ai-assessments-v1.json").read_bytes()
    first = next((out / "logical-results").glob("*.json"))
    first.unlink()

    def never(*args):
        raise AssertionError("completed or terminal assessment repeated")

    resumed = executor.execute(
        m,
        c,
        requests,
        out,
        None,
        seal(PricingAssumption),
        {"estimated_usage_cost_usd": "0.0000045"},
        transport=never,
    )
    assert resumed["assessment_freeze_fingerprint"] == result["assessment_freeze_fingerprint"]
    assert (out / "real-ai-assessments-v1.json").read_bytes() == frozen
    assert len(list((out / "logical-results").glob("*.json"))) == 120


def test_cost_guard_and_configuration_failure_stop_before_further_calls(
    executor, frozen_requests, tmp_path
):
    m, c, requests = frozen_requests
    calls = []

    def config(*args):
        calls.append(1)
        return {
            "outcome": "TECHNICAL_FAILURE",
            "error_code": "AI_PROVIDER_HTTP_ERROR",
            "assessment_text": None,
            "usage": None,
            "latency_seconds": 0.01,
            "retryable": False,
            "configuration_error": True,
        }

    stopped = executor.execute(
        m,
        c,
        requests,
        tmp_path / "cost",
        None,
        seal(PricingAssumption),
        {"estimated_usage_cost_usd": "0.946"},
        transport=config,
    )
    assert stopped["status"].startswith("STOP_COST_GUARD") and not calls
    stopped = executor.execute(
        m,
        c,
        requests,
        tmp_path / "config",
        None,
        seal(PricingAssumption),
        {"estimated_usage_cost_usd": "0.0000045"},
        transport=config,
    )
    assert stopped["status"] == "STOP_CONFIGURATION_ERROR" and len(calls) == 1
    assert not (tmp_path / "config/real-ai-assessments-v1.json").exists()


def test_duplicate_keys_grounding_and_missing_evidence_are_invalid(executor, frozen_requests):
    m, c, requests = frozen_requests
    item = json.loads(next(requests.glob("*.json")).read_text())
    from archguard.architecture.intelligence.models import StructuredLLMRequest

    request = StructuredLLMRequest.model_validate(item["structured_request"])
    text = response(item["provider_payload"], invalid=True)["assessment_text"]
    with pytest.raises(ValueError):
        executor.accepted(text, request)
    value = json.loads(response(item["provider_payload"])["assessment_text"])
    value["judgment"] = "SUPPORTED"
    with pytest.raises(ValueError):
        executor.accepted(json.dumps(value), request)
    with pytest.raises(ValueError):
        executor.unique_object([("judgment", "SUPPORTED"), ("judgment", "NOT_SUPPORTED")])


def test_executor_has_no_truth_or_evaluator_dependency():
    source = (Path(__file__).parents[2] / "scripts/prompt014_execute.py").read_text()
    imports = [n.module for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom)]
    assert not any(
        any(word in (name or "") for word in ("oss_review", "oss_cli", "semantic_evaluation"))
        for name in imports
    )
    assert "ground-truth.json" not in source and "final_human_label" not in source


def test_negative_abstention_and_oos_denominators():
    cases = [{"annotation_case_id": str(i), "final_human_label": "NEGATIVE"} for i in range(10)]
    cases += [
        {"annotation_case_id": str(i), "final_human_label": "OUT_OF_SCOPE"} for i in range(10, 18)
    ]
    decisions = (
        ["NOT_SUPPORTED"] * 7
        + ["SUPPORTED"] * 2
        + ["INSUFFICIENT_CONTEXT"]
        + ["NOT_APPLICABLE"] * 6
        + ["SUPPORTED"]
        + ["INSUFFICIENT_CONTEXT"]
    )
    outcomes = {
        str(i): {"status": "SUCCESS", "assessment": {"judgment": d}}
        for i, d in enumerate(decisions)
    }
    result = metrics(cases, outcomes)
    assert result["specificity"] == 7 / 9 and result["FPR"] == 2 / 9
    assert result["effective_negative_correctness"] == 0.7 and result["definitive_coverage"] == 0.9
    assert result["abstention_rate"] == 0.1 and result["oos_recognition"] == 0.75
    assert result["Recall"] is result["F1"] is result["FNR"] is None


def test_pairs_and_iam_strata_report_incomplete_cases():
    cases = [
        {
            "annotation_case_id": str(i),
            "final_human_label": "OUT_OF_SCOPE" if i >= 32 else "NEGATIVE",
            "rule_id": "ARCH202" if i >= 32 else "ARCH201",
            "language": "JAVA",
            "repository_id": "fixture",
        }
        for i in range(40)
    ]
    rows = []
    contexts = []
    attempts = []
    for strategy in ("LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE"):
        for i in range(40):
            rows.append(
                {
                    "case_id": str(i),
                    "strategy": strategy,
                    "status": "INVALID_RESPONSE"
                    if i == 39 and strategy == "GRAPH_GUIDED"
                    else "SUCCESS",
                    "assessment": {"judgment": "NOT_APPLICABLE" if i >= 32 else "NOT_SUPPORTED"},
                }
            )
            contexts.append(
                {
                    "case_id": str(i),
                    "strategy": strategy,
                    "context_diagnostics": ["PARTIAL"] if i >= 10 else [],
                    "context_chars": 100,
                    "source_chars": 50,
                }
            )
            attempts.append(
                {
                    "case_id": str(i),
                    "strategy": strategy,
                    "attempt_number": 1,
                    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                    "estimated_cost_usd": "0.000035",
                    "latency_seconds": 1.0,
                }
            )
    report = evaluate(cases, {"assessments": rows, "attempts": attempts}, {"requests": contexts})
    assert report["complete_successful_triples"] == 39 and report["incomplete_triple_case_ids"] == [
        "39"
    ]
    assert [p["complete_pairs"] for p in report["pairwise"]] == [39, 39, 40]
    assert report["strategies"]["GRAPH_GUIDED"]["oos_recognition"] == 7 / 8
    assert report["strategies"]["LOCAL_ONLY"]["iam_sensitivity"]["VALID_IAM"]["cases"] == 10
    assert report["strategies"]["LOCAL_ONLY"]["per_rule"]["ARCH202"]["specificity"] is None
