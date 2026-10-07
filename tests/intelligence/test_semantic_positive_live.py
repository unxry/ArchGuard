"""Synthetic HTTP envelopes and temporary ledgers only. No external provider calls."""

import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical
from archguard.infrastructure.llm_provider import AIProviderSettings
from archguard.infrastructure.semantic_positive_execution import load_execution, verify_assessments
from archguard.infrastructure.semantic_positive_live import (
    OpenAIPositiveTransport,
    freeze_live,
    operational_report,
)
from archguard.infrastructure.semantic_preflight import wire_payload
from tests.intelligence.test_semantic_positive_execution import (  # noqa: F401
    execution,
    ok,
    response,
    run,
)
from tests.intelligence.test_semantic_positive_offline import material, source_inputs  # noqa: F401

SYNTHETIC_KEY = "SYNTHETIC_CREDENTIAL_CANARY_0123456789"


@pytest.fixture
def request_protocol(execution):  # noqa: F811
    root, _, bindings, _, _, rows = execution
    protocol, _ = load_execution(root, bindings)
    request = StructuredLLMRequest.model_validate(
        json.loads((root / "requests" / (rows[0].request_id + ".json")).read_bytes())[
            "structured_request"
        ]
    )
    return request, protocol


def envelope(request):
    return {
        "id": "synthetic_response",
        "status": "completed",
        "model": "gpt-6-luna",
        "service_tier": "default",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 2,
            "total_tokens": 102,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": canonical(response(request))}],
            }
        ],
    }


class FakeResponse:
    status = 200
    headers = {"x-request-id": "synthetic_http_request"}

    def __init__(self, raw):
        self.raw = raw

    def read(self, limit):
        return self.raw[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def adapter(raw=None, error=None, calls=None):
    def open_fake(wire, timeout):
        if calls is not None:
            calls.append((json.loads(wire.data), timeout))
        if error is not None:
            raise error
        return FakeResponse(raw)

    return OpenAIPositiveTransport(
        AIProviderSettings(provider="openai", model="gpt-6-luna", api_key=SYNTHETIC_KEY),
        opener=SimpleNamespace(open=open_fake),
    )


def test_exact_frozen_payload_and_full_usage(request_protocol):
    request, protocol = request_protocol
    data = envelope(request)
    raw = canonical(data).encode()
    calls = []
    outcome = adapter(raw, calls=calls)(request, protocol)
    assert calls == [(wire_payload(request, protocol.model), 90)]
    assert outcome.status == "OK" and outcome.raw_response == raw
    assert outcome.provider_usage == data["usage"]
    assert outcome.total_tokens == 102 and outcome.provider_metadata["service_tier"] == "default"
    assert SYNTHETIC_KEY not in repr(outcome)


@pytest.mark.parametrize(
    "code,error_code,expected",
    [
        (401, "invalid_api_key", "CONFIGURATION_ERROR"),
        (404, "model_not_found", "CONFIGURATION_ERROR"),
        (429, "insufficient_quota", "CONFIGURATION_ERROR"),
        (429, "rate_limit_exceeded", "RATE_LIMIT"),
        (503, "server_error", "TRANSIENT"),
    ],
)
def test_http_errors_classified_once(request_protocol, code, error_code, expected):
    import io

    request, protocol = request_protocol
    raw = canonical(
        {"error": {"code": error_code, "message": "Synthetic provider failure"}}
    ).encode()
    error = HTTPError("https://api.openai.com/v1/responses", code, "synthetic", {}, io.BytesIO(raw))
    calls = []
    outcome = adapter(error=error, calls=calls)(request, protocol)
    assert len(calls) == 1 and outcome.status == expected
    assert outcome.raw_response == raw and outcome.error_metadata["code"] == error_code


@pytest.mark.parametrize("error", [TimeoutError("synthetic timeout"), URLError("synthetic reset")])
def test_uncertain_processing_never_retries_in_adapter(request_protocol, error):
    calls = []
    with pytest.raises(RuntimeError, match="pending"):
        adapter(error=error, calls=calls)(*request_protocol)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "change,status",
    [
        ({"model": "other"}, "CONFIGURATION_ERROR"),
        ({"service_tier": "priority"}, "CONFIGURATION_ERROR"),
        ({"usage": None}, "CONFIGURATION_ERROR"),
        ({"status": "incomplete"}, "TERMINAL_ERROR"),
        ({"output": []}, "TERMINAL_ERROR"),
    ],
)
def test_no_fallback_or_semantic_repair(request_protocol, change, status):
    request, protocol = request_protocol
    outcome = adapter(canonical(envelope(request) | change).encode())(request, protocol)
    assert outcome.status == status


def test_secret_echo_never_becomes_transport_artifact(request_protocol):
    request, protocol = request_protocol
    raw = canonical(envelope(request) | {"unexpected": SYNTHETIC_KEY}).encode()
    with pytest.raises(ValueError, match="credential echo") as caught:
        adapter(raw)(request, protocol)
    assert SYNTHETIC_KEY not in str(caught.value)


def test_authentication_echo_redacted_without_configuration_retry(request_protocol):
    import io

    request, protocol = request_protocol
    raw = canonical({"error": {"code": "invalid_api_key", "message": SYNTHETIC_KEY}}).encode()
    error = HTTPError("https://api.openai.com/v1/responses", 401, "synthetic", {}, io.BytesIO(raw))
    outcome = adapter(error=error)(request, protocol)
    assert outcome.status == "CONFIGURATION_ERROR"
    assert SYNTHETIC_KEY.encode() not in outcome.raw_response
    assert outcome.error_metadata["code"] == "invalid_api_key"
    assert outcome.provider_metadata["raw_error_redacted_for_credential_safety"]


def test_source_header_literals_are_not_credentials():
    transport = adapter()
    transport.assert_secret_free(b'headers={"Authorization":"Bearer "}', actual_key_only=True)
    with pytest.raises(ValueError, match="credential echo"):
        transport.assert_secret_free(SYNTHETIC_KEY.encode(), actual_key_only=True)


def test_ordinary_semantic_prose_does_not_match_credential_prefix():
    adapter().assert_secret_free(b"Task-based work has risk-bearing responsibilities.")


def test_live_normalization_freeze_usage_and_four_categories(execution):  # noqa: F811
    decisions = ("SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE")
    count = 0

    def transport(request, protocol):
        nonlocal count
        decision = decisions[count % 4]
        count += 1
        return ok(request, protocol, decision).model_copy(
            update={
                "total_tokens": 102,
                "provider_usage": {"input_tokens": 100, "output_tokens": 2, "total_tokens": 102},
                "provider_metadata": {"actual_model": "gpt-6-luna", "service_tier": "default"},
            }
        )

    run(execution, transport)
    root, ledger, bindings, _, _, rows = execution
    result = freeze_live(root, ledger, bindings)
    assert count == 300
    assert result["operational_statistics"]["valid_accepted_assessments"] == 300
    assert result["operational_statistics"]["provider_usage"]["total_tokens"] == 30600
    assert result["operational_statistics"]["spend"]["actual_invoice_cost_usd"] is None
    assert len(result["normalized_assessment_fingerprint"]) == 64
    verify_assessments(ledger, bindings, result["ai_freeze_receipt_fingerprint"])
    data = json.loads(next((ledger / "attempts").glob("*.json")).read_bytes())
    assert data["started_at_utc"] <= data["ended_at_utc"]
    assert data["request_fingerprint"] in {row.request_fingerprint for row in rows}
    with pytest.raises(ValueError, match="append-only"):
        freeze_live(root, ledger, bindings)


def test_resume_drift_blocks_provider_before_any_new_call(execution):  # noqa: F811
    run(execution)
    path = next((execution[1] / "attempts").glob("*.json"))
    data = json.loads(path.read_bytes())
    path.write_text(canonical(data | {"reserved_cost_usd": "0"}))
    with pytest.raises(ValueError, match="accounting"):
        run(execution, lambda *a: pytest.fail("provider must not run"))


def test_pending_spend_is_reserved_and_never_reported_as_zero_usage(execution):  # noqa: F811
    with pytest.raises(RuntimeError):
        run(execution, lambda *a: (_ for _ in ()).throw(TimeoutError()))
    report = operational_report(execution[1], execution[-1])
    assert report["pending_transport_outcomes"] == report["scientific_provider_calls"] == 1
    assert report["spend"]["estimated_scientific_cost_usd"] is None
    assert report["unknown_usage_attempts"] == 1
    assert report["spend"]["reserved_maximum_spend_usd"] == "0.0042768"
