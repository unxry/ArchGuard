"""Ephemeral synthetic transport fixtures only; no scientific AI ledger/provider calls."""

import json

import pytest

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical, seal
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.semantic_positive_execution import (
    ExecutionBindings,
    PaidApproval,
    TransportOutcome,
    blind_io,
    execute_future,
    freeze_assessments,
    validated_assessment,
    verify_assessments,
)
from archguard.infrastructure.semantic_positive_offline import freeze_execution_bundle
from tests.intelligence.test_semantic_positive_offline import material, source_inputs  # noqa: F401


@pytest.fixture
def execution(material, tmp_path):  # noqa: F811
    protocol, files, rows, _ = material
    root = tmp_path / "execution"
    receipt = freeze_execution_bundle(root, files)
    bindings = ExecutionBindings(
        execution_freeze_fingerprint=receipt["fingerprint"],
        protocol_fingerprint=protocol.fingerprint,
        context_manifest_fingerprint=files["context-manifest.json"]["fingerprint"],
        request_manifest_fingerprint=files["request-manifest.json"]["fingerprint"],
        truth_fingerprint=protocol.truth_fingerprint,
    )
    approval = PaidApproval(
        paid_execution_approved=True, bindings=bindings, truth_lineage_verified_externally=True
    )
    return root, tmp_path / "ledger", bindings, approval, seal(PricingAssumption), rows


def response(request, decision="NOT_SUPPORTED"):
    return {
        "request_id": request.task["request_id"],
        "candidate_rule_id": request.task["candidate_rule_id"],
        "subject_node_ids": [request.task["subject_node_id"]],
        "judgment": decision,
        "short_reason": "Synthetic unit-test response.",
        "evidence_refs": [
            request.untrusted_context["source_fragments"][0]["reference"]["evidence_id"]
        ],
        "limitations": [],
    }


def ok(request, protocol, decision="NOT_SUPPORTED"):
    data = response(request, decision)
    return TransportOutcome(
        status="OK",
        raw_response=canonical({"synthetic_unit_test": True, "assessment": data}).encode(),
        assessment_json=canonical(data),
        input_tokens=100,
        output_tokens=2,
        latency_seconds=0.01,
    )


def run(execution, transport=ok, **updates):
    root, ledger, bindings, approval, pricing, _ = execution
    return execute_future(
        root,
        ledger,
        bindings,
        updates.get("approval", approval),
        credential_available=updates.get("credential_available", True),
        transport=transport,
        pricing=pricing,
    )


@pytest.mark.parametrize(
    "guard", ["approval", "credential", "external_lineage", "bindings", "spend_cap"]
)
def test_no_transport_without_every_runtime_guard(execution, guard):
    root, ledger, bindings, approval, _, _ = execution
    if guard == "approval":
        approval = approval.model_copy(update={"paid_execution_approved": False})
    elif guard == "external_lineage":
        approval = approval.model_copy(update={"truth_lineage_verified_externally": False})
    elif guard == "bindings":
        approval = approval.model_copy(
            update={"bindings": bindings.model_copy(update={"protocol_fingerprint": "0" * 64})}
        )
    elif guard == "spend_cap":
        approval = approval.model_copy(update={"spend_cap_usd": "NaN"})
    with pytest.raises((PermissionError, ValueError)):
        run(
            execution,
            lambda *a: pytest.fail("transport forbidden"),
            approval=approval,
            credential_available=guard != "credential",
        )
    assert not ledger.exists()


def test_truth_path_is_unreadable_to_executor(execution, tmp_path):
    root, ledger, _, _, _, _ = execution
    truth = tmp_path / "private/final-human-ground-truth-v1/ground-truth-v1.json"
    truth.parent.mkdir(parents=True)
    truth.write_text("SYNTHETIC_PRIVATE_TRUTH")
    with blind_io(root, ledger), pytest.raises(PermissionError, match="denied"):
        truth.read_bytes()
    assert truth.read_text() == "SYNTHETIC_PRIVATE_TRUTH"


def test_manifest_drift_refuses_before_transport(execution):
    root = execution[0]
    (root / "request-manifest.json").write_bytes(
        (root / "request-manifest.json").read_bytes() + b" "
    )
    with pytest.raises(ValueError):
        run(execution, lambda *a: pytest.fail("transport forbidden"))


def test_complete_synthetic_ledger_exactly_once_and_raw_freeze(execution):
    calls = []

    def transport(request, protocol):
        calls.append(request.task["request_id"])
        return ok(request, protocol, "NOT_APPLICABLE")

    assert run(execution, transport)["logical_results"] == 300
    assert len(calls) == len(set(calls)) == 300
    assert (
        run(execution, lambda *a: pytest.fail("accepted answer repeated"))["logical_results"] == 300
    )
    root, ledger, bindings, _, _, _ = execution
    receipt = freeze_assessments(root, ledger, bindings)
    assert verify_assessments(ledger, bindings, receipt["fingerprint"]) == receipt
    assert all(
        json.loads(p.read_bytes())["assessment"]["judgment"] == "NOT_APPLICABLE"
        for p in (ledger / "results").iterdir()
    )
    with pytest.raises(ValueError, match="append-only"):
        freeze_assessments(root, ledger, bindings)
    with pytest.raises(ValueError, match="immutable"):
        run(execution, lambda *a: pytest.fail("frozen answer repeated"))
    raw = next((ledger / "raw").iterdir())
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(ValueError, match="bytes"):
        verify_assessments(ledger, bindings, receipt["fingerprint"])


@pytest.mark.parametrize(
    "decision", ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE"]
)
def test_all_four_semantic_outcomes_remain_distinct(execution, decision):
    root, _, _, _, _, rows = execution
    request = StructuredLLMRequest.model_validate(
        json.loads((root / "requests" / (rows[0].request_id + ".json")).read_bytes())[
            "structured_request"
        ]
    )
    assert (
        validated_assessment(canonical(response(request, decision)), request)["judgment"]
        == decision
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "0" * 64),
        ("candidate_rule_id", "ARCH999"),
        ("evidence_refs", ["unknown"]),
        ("subject_node_ids", ["unknown"]),
        ("judgment", "UNCERTAIN"),
    ],
)
def test_response_binding_rejects_invalid_fields(execution, field, value):
    root, _, _, _, _, rows = execution
    request = StructuredLLMRequest.model_validate(
        json.loads((root / "requests" / (rows[0].request_id + ".json")).read_bytes())[
            "structured_request"
        ]
    )
    data = response(request) | {field: value}
    with pytest.raises(ValueError):
        validated_assessment(canonical(data), request)


def test_duplicate_json_keys_rejected_before_acceptance(execution):
    root, _, _, _, _, rows = execution
    request = StructuredLLMRequest.model_validate(
        json.loads((root / "requests" / (rows[0].request_id + ".json")).read_bytes())[
            "structured_request"
        ]
    )
    with pytest.raises(ValueError, match="duplicate"):
        validated_assessment('{"judgment":"SUPPORTED","judgment":"NOT_SUPPORTED"}', request)


def test_only_two_technical_retries_and_failure_is_recorded(execution):
    first = execution[-1][0].request_id
    count = 0

    def transport(request, protocol):
        nonlocal count
        if request.task["request_id"] == first:
            count += 1
            return TransportOutcome(status="TIMEOUT", raw_response=b"", latency_seconds=0.1)
        return ok(request, protocol)

    run(execution, transport)
    assert count == 3
    result = json.loads((execution[1] / "results" / (first + ".json")).read_bytes())
    assert result["status"] == "TERMINAL_FAILURE" and result["assessment"] is None
    assert result["attempts"] == 3 and result["input_tokens"] is None
    assert result["cost_usd"] is None
    with pytest.raises(ValueError, match="300 valid accepted"):
        freeze_assessments(execution[0], execution[1], execution[2])
    assert not (execution[1] / "assessment-freeze.json").exists()


def test_invalid_response_is_terminal_without_semantic_retry(execution):
    first = execution[-1][0].request_id
    count = 0

    def transport(request, protocol):
        nonlocal count
        if request.task["request_id"] == first:
            count += 1
            return TransportOutcome(
                status="OK",
                raw_response=b'{"synthetic_invalid":true}',
                assessment_json="{}",
                input_tokens=100,
                output_tokens=2,
                latency_seconds=0.1,
            )
        return ok(request, protocol)

    run(execution, transport)
    assert count == 1
    result = json.loads((execution[1] / "results" / (first + ".json")).read_bytes())
    assert result["status"] == "TERMINAL_FAILURE" and result["attempts"] == 1
    with pytest.raises(ValueError, match="300 valid accepted"):
        freeze_assessments(execution[0], execution[1], execution[2])


def test_configuration_failure_is_not_retried(execution):
    count = 0

    def transport(*args):
        nonlocal count
        count += 1
        return TransportOutcome(
            status="CONFIGURATION_ERROR",
            raw_response=b'{"synthetic_config_error":true}',
            latency_seconds=0.01,
        )

    with pytest.raises(PermissionError, match="configuration"):
        run(execution, transport)
    assert count == 1
    with pytest.raises(PermissionError, match="configuration"):
        run(execution, lambda *a: pytest.fail("configuration error repeated"))


def test_transport_interruption_never_logs_error_or_automatically_repeats(execution, capsys):
    def transport(*args):
        raise RuntimeError("SYNTHETIC_CREDENTIAL_CANARY")

    with pytest.raises(RuntimeError, match="interrupted") as caught:
        run(execution, transport)
    assert "SYNTHETIC_CREDENTIAL_CANARY" not in str(caught.value)
    assert "SYNTHETIC_CREDENTIAL_CANARY" not in capsys.readouterr().out
    diagnostic = json.loads(next((execution[1] / "transport-errors").glob("*.json")).read_bytes())
    assert diagnostic["exception_type"] == "RuntimeError"
    assert "SYNTHETIC_CREDENTIAL_CANARY" not in canonical(diagnostic)
    with pytest.raises(PermissionError, match="unresolved"):
        run(execution, lambda *a: pytest.fail("ambiguous completed call repeated"))


def test_completed_attempt_recovers_without_second_transport_call(execution, monkeypatch):
    import archguard.infrastructure.semantic_positive_execution as module

    original = module.write_new
    first = execution[-1][0].request_id
    seen = []

    def crash(path, value):
        if path.parent.name == "results":
            raise RuntimeError("synthetic process interruption")
        original(path, value)

    def transport(request, protocol):
        seen.append(request.task["request_id"])
        return ok(request, protocol)

    monkeypatch.setattr(module, "write_new", crash)
    with pytest.raises(RuntimeError):
        run(execution, transport)
    assert seen == [first]
    monkeypatch.setattr(module, "write_new", original)
    run(execution, transport)
    assert len(seen) == len(set(seen)) == 300


def test_credential_echo_is_rejected_before_persistence(execution):
    def transport(*args):
        return TransportOutcome(
            status="TERMINAL_ERROR",
            raw_response=b"Bearer SYNTHETIC_CREDENTIAL_CANARY",
            latency_seconds=0.01,
        )

    with pytest.raises(ValueError, match="credential-bearing"):
        run(execution, transport)
    assert all(
        b"SYNTHETIC_CREDENTIAL_CANARY" not in p.read_bytes()
        for p in execution[1].rglob("*")
        if p.is_file()
    )


def test_incomplete_ledger_cannot_freeze(execution):
    root, ledger, bindings, _, _, _ = execution
    (ledger / "results").mkdir(parents=True)
    with pytest.raises(ValueError, match="incomplete"):
        freeze_assessments(root, ledger, bindings)


def test_spend_guard_stops_before_next_call(execution):
    approval = execution[3].model_copy(update={"spend_cap_usd": "0.0042768"})
    count = 0

    def transport(request, protocol):
        nonlocal count
        count += 1
        data = response(request)
        return TransportOutcome(
            status="OK",
            raw_response=canonical(data).encode(),
            assessment_json=canonical(data),
            input_tokens=32768,
            output_tokens=2000,
            latency_seconds=0.01,
        )

    result = run(execution, transport, approval=approval)
    assert count == 1 and result["status"] == "SPEND_CAP_STOP"
    assert result["completed_logical"] == 1 and result["remaining_logical"] == 299
