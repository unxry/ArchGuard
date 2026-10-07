"""Synthetic interrupted runs only; recovery never uses real provider or human files."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.infrastructure import semantic_positive_recovery as recovery_module
from archguard.infrastructure.llm_provider import AIProviderSettings
from archguard.infrastructure.semantic_positive_execution import (
    TransportOutcome,
    blind_io,
    verify_assessments,
)
from archguard.infrastructure.semantic_positive_live import OpenAIPositiveTransport
from archguard.infrastructure.semantic_positive_recovery import (
    RecoveryAmendment,
    append_json,
    execute_recovery,
    freeze_recovery,
    inventory,
    prepare_recovery,
    recovery_report,
)
from tests.intelligence.test_semantic_positive_execution import (  # noqa: F401
    execution,
    response,
    run,
)
from tests.intelligence.test_semantic_positive_offline import material, source_inputs  # noqa: F401


def outcome(request, decision="NOT_SUPPORTED", invalid=False):
    assessment = response(request, decision)
    if invalid:
        assessment["request_id"] = "0" * 64
    raw = {
        "id": "resp_synthetic",
        "model": "gpt-6-luna",
        "service_tier": "default",
        "status": "completed",
        "usage": {"input_tokens": 100, "output_tokens": 2, "total_tokens": 102},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": canonical(assessment)}]}
        ],
    }
    return TransportOutcome(
        status="OK",
        raw_response=canonical(raw).encode(),
        assessment_json=canonical(assessment),
        input_tokens=100,
        output_tokens=2,
        total_tokens=102,
        provider_usage=raw["usage"],
        provider_metadata={
            "http_status": 200,
            "response_status": "completed",
            "response_id": "resp_synthetic",
        },
        latency_seconds=0.01,
    )


@pytest.fixture
def interrupted(execution):  # noqa: F811
    count = 0

    def transport(request, protocol):
        nonlocal count
        n = count
        count += 1
        if n == 107:
            raise RuntimeError("SYNTHETIC_UNKNOWN_TRANSPORT")
        return outcome(request, invalid=n == 31)

    with pytest.raises(RuntimeError):
        run(execution, transport)
    root, ledger, bindings, _, pricing, rows = execution
    original = inventory(ledger)
    amendment = seal(
        RecoveryAmendment,
        bindings=bindings,
        initial_ledger_fingerprint=digest(original),
        initial_public_verification_fingerprint="1" * 64,
        pricing_fingerprint=pricing.fingerprint,
    )
    plan = prepare_recovery(root, ledger, amendment)
    decoder_adapter = OpenAIPositiveTransport(
        AIProviderSettings(
            provider="openai", model="gpt-6-luna", api_key="SYNTHETIC_CREDENTIAL_CANARY"
        ),
        opener=SimpleNamespace(open=lambda *a, **k: pytest.fail("network forbidden")),
    )

    def decode(raw, metadata, protocol):
        return decoder_adapter.decode_response(
            raw, metadata, protocol, metadata.get("latency_seconds", 0.01)
        )

    return root, ledger, amendment, pricing, rows, original, plan, decode


def recover(fixture, transport, **options):
    root, ledger, amendment, pricing, _, _, _, decoder = fixture
    return execute_recovery(
        root,
        ledger,
        amendment,
        pricing,
        amendment_commit="a" * 40,
        paid_approved=True,
        credential_available=True,
        transport=transport,
        decode=decoder,
        **options,
    )


def test_106_immutable_same_payload_300_acceptance_and_all_history_frozen(interrupted):
    root, ledger, amendment, pricing, rows, original, plan, _ = interrupted
    calls = []
    expected = {
        r.request_id: json.loads((root / "requests" / (r.request_id + ".json")).read_bytes())[
            "structured_request"
        ]
        for r in rows
    }
    decisions = ("SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE")

    def transport(request, protocol, capture):
        assert request.model_dump(mode="json") == expected[request.task["request_id"]]
        calls.append(request.task["request_id"])
        result = outcome(request, decisions[len(calls) % 4])
        capture(result.raw_response, {"http_status": 200, "latency_seconds": 0.01})
        return result

    assert recover(interrupted, transport)["accepted"] == 300
    assert len(calls) == len(set(calls)) == 194
    assert calls[:2] == [plan["existing_schema_request"], plan["existing_pending_request"]]
    assert calls[2:] == [r.request_id for r in rows[108:]]
    assert all(inventory(ledger)[name] == sha for name, sha in original.items())
    assert (
        recover(interrupted, lambda *a: pytest.fail("accepted response repeated"))["accepted"]
        == 300
    )
    report = recovery_report(root, ledger, amendment, pricing)
    assert report["provider_invocations"] == 302 and report["maximum_attempts"] == 2
    assert report["confirmed_duplicate_provider_executions"] == 1
    assert report["possible_duplicate_provider_processing"] == 1
    assert (
        report["historical_ambiguous_invocations"] == 1 and report["active_unresolved_pending"] == 0
    )
    assert report["schema_recovery_invocations"] == report["ambiguous_recovery_invocations"] == 1
    assert report["hidden_result_used_for_selection"] is False
    frozen = freeze_recovery(root, ledger, amendment, pricing)
    receipt = verify_assessments(
        ledger, amendment.bindings, frozen["ai_freeze_receipt_fingerprint"]
    )
    assert len(receipt["accepted_result_paths"]) == 300
    assert (
        len(json.loads((ledger / "normalized-assessments.json").read_bytes())["assessments"]) == 300
    )
    assert any((ledger / "pending").iterdir())
    frozen_inventory = inventory(ledger)
    assert freeze_recovery(root, ledger, amendment, pricing) == frozen
    assert inventory(ledger) == frozen_inventory
    with pytest.raises(ValueError, match="immutable"):
        recover(interrupted, lambda *a: pytest.fail("frozen response repeated"))


def test_second_schema_failure_unrecoverable_and_never_remapped(interrupted):
    count = 0

    def transport(request, protocol, capture):
        nonlocal count
        count += 1
        return outcome(request, invalid=True)

    assert recover(interrupted, transport)["status"] == "SCHEMA_RECOVERY_EXHAUSTED"
    assert count == 1
    root, ledger, amendment, pricing, _, original, plan, _ = interrupted
    assert recovery_report(root, ledger, amendment, pricing)["valid_accepted_assessments"] == 106
    assert all(inventory(ledger)[name] == sha for name, sha in original.items())
    assert not (ledger / "recovery/results" / (plan["existing_schema_request"] + ".json")).exists()
    assert (
        recover(interrupted, lambda *a: pytest.fail("second schema recovery forbidden"))["status"]
        == "SCHEMA_RECOVERY_EXHAUSTED"
    )


@pytest.mark.parametrize("failure", ["schema", "ambiguous"])
def test_future_unattempted_requests_use_same_prospective_recovery_policy(interrupted, failure):
    calls = []

    def transport(request, protocol, capture):
        calls.append(request.task["request_id"])
        if len(calls) >= 3:
            if failure == "ambiguous":
                raise TimeoutError("synthetic transport interruption")
            return outcome(request, invalid=True)
        return outcome(request)

    expected = (
        "SCHEMA_RECOVERY_EXHAUSTED"
        if failure == "schema"
        else "P016_LIVE_1_INCOMPLETE_SECOND_AMBIGUITY"
    )
    assert recover(interrupted, transport)["status"] == expected
    assert len(calls) == 4 and calls[2] == calls[3]
    assert len(set(calls)) == 3
    assert (
        recover(interrupted, lambda *a: pytest.fail("exhausted future recovery repeated"))["status"]
        == expected
    )


def test_spend_guard_includes_reservation_before_any_new_call(interrupted, monkeypatch):
    real_state = recovery_module.state

    def capped(*args):
        accepted, events, _ = real_state(*args)
        return accepted, events, Decimal("4.499")

    monkeypatch.setattr(recovery_module, "state", capped)
    assert (
        recover(interrupted, lambda *a: pytest.fail("spend cap bypassed"))["status"]
        == "P016_LIVE_1_STOPPED_SPEND_CAP"
    )


def test_invalid_recorded_handle_cannot_be_invented_or_replaced(interrupted):
    ledger, plan = interrupted[1], interrupted[6]
    append_json(
        ledger / "recovery/captures" / (plan["existing_pending_request"] + "-1.json"),
        {"provider_response_id": "not_a_response_handle"},
    )
    calls = []

    def transport(request, protocol, capture):
        calls.append(request.task["request_id"])
        return outcome(request)

    assert (
        recover(interrupted, transport)["status"]
        == "P016_LIVE_1_INCOMPLETE_HANDLE_RECOVERY_UNAVAILABLE"
    )
    assert calls == [plan["existing_schema_request"]]


def test_second_ambiguity_stops_without_recursive_replacement(interrupted):
    plan = interrupted[6]
    calls = []

    def transport(request, protocol, capture):
        calls.append(request.task["request_id"])
        if request.task["request_id"] == plan["existing_pending_request"]:
            raise TimeoutError("SYNTHETIC_SECRET_NEVER_LOGGED")
        return outcome(request)

    assert recover(interrupted, transport)["status"] == "P016_LIVE_1_INCOMPLETE_SECOND_AMBIGUITY"
    assert calls == [plan["existing_schema_request"], plan["existing_pending_request"]]
    assert (
        recover(interrupted, lambda *a: pytest.fail("recursive replacement forbidden"))["status"]
        == "P016_LIVE_1_INCOMPLETE_SECOND_AMBIGUITY"
    )
    assert all(
        b"SYNTHETIC_SECRET_NEVER_LOGGED" not in p.read_bytes()
        for p in interrupted[1].rglob("*")
        if p.is_file()
    )


def test_replacement_transient_uses_only_remaining_attempt_budget(interrupted):
    root, ledger, amendment, pricing, _, _, plan, _ = interrupted
    calls = []

    def transport(request, protocol, capture):
        calls.append(request.task["request_id"])
        if len(calls) == 2:
            return TransportOutcome(
                status="RATE_LIMIT",
                raw_response=b'{"error":{"code":"rate_limit_exceeded"}}',
                latency_seconds=0.1,
            )
        if len(calls) == 3:
            return TransportOutcome(
                status="CONFIGURATION_ERROR",
                raw_response=b'{"synthetic_config_stop":true}',
                latency_seconds=0.1,
            )
        return outcome(request)

    assert recover(interrupted, transport)["status"].endswith("PROVIDER_CONFIGURATION_OR_TERMINAL")
    assert calls == [
        plan["existing_schema_request"],
        plan["existing_pending_request"],
        plan["existing_pending_request"],
    ]
    report = recovery_report(root, ledger, amendment, pricing)
    assert report["maximum_attempts"] == 3 and report["ordinary_transient_retries"] == 1
    assert report["attempt_limit_violations"] == 0


def test_recorded_handle_recovers_same_response_without_generation(interrupted):
    root, ledger, _, _, rows, _, plan, _ = interrupted
    pending = plan["existing_pending_request"]
    append_json(
        ledger / "recovery/captures" / (pending + "-1.json"),
        {"provider_response_id": "resp_saved_existing"},
    )
    calls = []
    retrieved = []

    def same_response(handle, request, protocol):
        assert handle == "resp_saved_existing" and request.task["request_id"] == pending
        retrieved.append(handle)
        return outcome(request).model_copy(
            update={"provider_metadata": {"response_id": handle, "response_status": "completed"}}
        )

    def transport(request, protocol, capture):
        calls.append(request.task["request_id"])
        if request.task["request_id"] == rows[108].request_id:
            return TransportOutcome(
                status="CONFIGURATION_ERROR", raw_response=b"{}", latency_seconds=0
            )
        return outcome(request)

    recover(interrupted, transport, recover_handle=same_response)
    assert retrieved == ["resp_saved_existing"] and pending not in calls
    assert not any(
        json.loads(p.read_bytes())["invocation_class"] == "AMBIGUOUS_TRANSPORT_RECOVERY"
        for p in (ledger / "recovery/intents").glob("*.json")
    )


def test_captured_raw_survives_exception_and_is_decoded_without_second_generation(interrupted):
    plan = interrupted[6]
    calls = []

    def transport(request, protocol, capture):
        calls.append(request.task["request_id"])
        if len(calls) == 1:
            result = outcome(request)
            capture(result.raw_response, {"http_status": 200, "latency_seconds": 0.01})
            raise RuntimeError("synthetic interruption after raw capture")
        return TransportOutcome(status="CONFIGURATION_ERROR", raw_response=b"{}", latency_seconds=0)

    recover(interrupted, transport)
    assert calls.count(plan["existing_schema_request"]) == 1
    assert (
        interrupted[1] / "recovery/results" / (plan["existing_schema_request"] + ".json")
    ).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "other"),
        ("max_attempts_per_request", 4),
        ("max_schema_recovery_invocations", 2),
        ("max_ambiguous_replacements", 2),
        ("spend_cap_usd", "5.00"),
        ("scientific_payload_policy", "ALTER_CONTEXT"),
    ],
)
def test_amendment_cannot_expand_scientific_or_budget_scope(interrupted, field, value):
    payload = interrupted[2].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        RecoveryAmendment.model_validate(payload)


def test_amendment_deterministic_source_free_and_truth_unavailable(interrupted, tmp_path):
    amendment = interrupted[2]
    assert RecoveryAmendment.model_validate_json(canonical(amendment)) == amendment
    assert "request_id" not in amendment.model_dump()
    with blind_io(interrupted[0], interrupted[1]):
        for p in (
            tmp_path / "private/final-human-ground-truth-v1/ground-truth-v1.json",
            tmp_path / "construction/intent.json",
        ):
            with pytest.raises(PermissionError):
                p.read_bytes()


def test_historical_accepted_change_blocks_all_new_calls(interrupted):
    p = next((interrupted[1] / "results").glob("*.json"))
    p.write_text("{}")
    with pytest.raises(ValueError, match="historical"):
        recover(interrupted, lambda *a: pytest.fail("changed history must block provider"))


def test_credential_and_commit_guard_precede_new_provider_calls(interrupted):
    root, ledger, amendment, pricing, _, _, _, decode = interrupted
    for commit, paid, credential in [
        ("", True, True),
        ("a" * 40, False, True),
        ("a" * 40, True, False),
    ]:
        with pytest.raises(PermissionError):
            execute_recovery(
                root,
                ledger,
                amendment,
                pricing,
                amendment_commit=commit,
                paid_approved=paid,
                credential_available=credential,
                transport=lambda *a: pytest.fail("provider forbidden"),
                decode=decode,
            )
