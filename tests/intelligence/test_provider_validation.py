import importlib.util
import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from archguard.benchmark.oss.models import seal
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.llm_provider import AIProviderSettings


@pytest.fixture
def probe():
    spec = importlib.util.spec_from_file_location(
        "provider_validation",
        Path(__file__).parents[2] / "scripts/prompt014_provider_validation.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def settings():
    return AIProviderSettings.model_validate(
        {
            "provider": "openai",
            "model": "gpt-6-luna",
            "api_key": "fictional-CREDENTIAL-AbCdEf987654",
        }
    )


class Response(BytesIO):
    status = 200


def test_connectivity_is_one_bounded_call_without_assessment_or_saved_text(probe, settings):
    class Local:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            payload = json.loads(request.data)
            assert payload["max_output_tokens"] == 64 and payload["store"] is False
            assert "untrusted_context" not in payload["input"]
            return Response(
                json.dumps(
                    {
                        "status": "incomplete",
                        "model": "gpt-6-luna",
                        "id": "resp_test",
                        "usage": {"input_tokens": 20, "output_tokens": 64, "total_tokens": 84},
                        "output": [{"text": "UNPERSISTED_TEST_TEXT"}],
                        "service_tier": "default",
                    }
                ).encode()
            )

    local = Local()
    result = probe.validate(settings, seal(PricingAssumption), local)
    assert local.calls == 1 and result["status"] == "CONNECTIVITY_SUCCEEDED"
    assert result["experiment_assessments_attempted"] == 0
    assert result["estimated_usage_cost_usd"] == "0.000034"
    assert "UNPERSISTED_TEST_TEXT" not in json.dumps(result)
    assert settings.api_key.get_secret_value() not in json.dumps(result)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "invalid_api_key"),
        (429, "insufficient_quota"),
        (404, "model_not_found"),
        (403, "unsupported_country_region_territory"),
    ],
)
def test_configuration_errors_stop_after_one_call_and_redact_key_fragments(
    probe, settings, status, code
):
    secret = settings.api_key.get_secret_value()

    class Local:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            body = json.dumps(
                {
                    "error": {
                        "type": "invalid_request_error",
                        "code": code,
                        "message": "Incorrect API key provided: "
                        + secret[:8]
                        + "***"
                        + secret[-4:],
                    }
                }
            ).encode()
            raise HTTPError(request.full_url, status, "failure", {}, BytesIO(body))

    local = Local()
    result = probe.validate(settings, seal(PricingAssumption), local)
    assert local.calls == 1 and result["status"] == "CONNECTIVITY_FAILED_STOP"
    assert result["http_status"] == status and result["provider_error_code"] == code
    assert secret[:8] not in result["provider_error_message"]
    assert secret[-4:] not in result["provider_error_message"]
    assert secret not in json.dumps(result)


def test_no_retry_on_connection_error_or_network_on_missing_key(probe, settings):
    class Local:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            raise URLError("synthetic network failure")

    local = Local()
    assert (
        probe.validate(settings, seal(PricingAssumption), local)["status"]
        == "CONNECTIVITY_FAILED_STOP"
    )
    assert local.calls == 1
    with pytest.raises(ValueError):
        probe.validate(
            settings.model_copy(update={"api_key": None}), seal(PricingAssumption), local
        )
    assert local.calls == 1
