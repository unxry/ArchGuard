import json
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest
from pydantic import SecretStr

from archguard.architecture.intelligence.models import AIAnalysisBudget, SemanticAnalysisTarget
from archguard.architecture.intelligence.ports import LLMProviderError
from archguard.architecture.intelligence.prompt import build_request
from archguard.architecture.intelligence.selection import resolve_node
from archguard.infrastructure.llm_provider import (
    AIProviderSettings,
    OpenAIResponsesProvider,
    _NoRedirect,
    _post,
    create_llm_provider,
)
from tests.helpers.scripted_llm import assessment
from tests.intelligence.test_context import pack


def request(chain):
    target = SemanticAnalysisTarget(
        node_id=resolve_node(chain[0].iam, "B"), candidate_rule_id="ARCH202", reason="EXPLICIT"
    )
    return build_request(target, pack(chain), AIAnalysisBudget())


def wire_response(req, **changes):
    response = {
        "id": "resp_offline",
        "model": "actual-model-version",
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": assessment(req)}]}
        ],
        "usage": {"input_tokens": 123, "output_tokens": 20, "total_tokens": 143},
    }
    response.update(changes)
    return json.dumps(response).encode()


def test_real_adapter_payload_and_actual_metadata_without_network(chain):
    req = request(chain)

    def transport(data, key, timeout):
        payload = json.loads(data)
        assert key == "synthetic-placeholder" and timeout == 30
        assert payload["store"] is False
        assert payload["text"]["format"]["strict"] is True
        assert "PRIVATE_SOURCE_MARKER" not in payload["input"][0]["content"]
        assert "PRIVATE_SOURCE_MARKER" in payload["input"][1]["content"]
        return wire_response(req)

    provider = OpenAIResponsesProvider(
        "requested-model", SecretStr("synthetic-placeholder"), transport
    )
    response = provider.complete_structured(req)
    assert response.model_id == "actual-model-version" and response.provider_id == "openai"
    assert response.usage.input_tokens == 123 and response.usage.provider_reported_cost is None
    assert provider.count_input_tokens(req) is None


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"status": "incomplete"}, "AI_PROVIDER_INCOMPLETE_RESPONSE"),
        (
            {"output": [{"type": "message", "content": [{"type": "refusal"}]}]},
            "AI_PROVIDER_REFUSAL",
        ),
        ({"output": []}, "AI_ANALYSIS_INVALID_RESPONSE"),
        ({"model": None}, "AI_ANALYSIS_INVALID_RESPONSE"),
        ({"output": [None]}, "AI_ANALYSIS_INVALID_RESPONSE"),
    ],
)
def test_adapter_rejects_incomplete_refused_and_malformed(chain, changes, code):
    req = request(chain)
    provider = OpenAIResponsesProvider(
        "requested", SecretStr("placeholder"), lambda *a: wire_response(req, **changes)
    )
    with pytest.raises(LLMProviderError, match=code):
        provider.complete_structured(req)


def test_adapter_usage_unknown_is_null_and_oversize_is_rejected(chain):
    req = request(chain)
    provider = OpenAIResponsesProvider(
        "requested", SecretStr("placeholder"), lambda *a: wire_response(req, usage=None)
    )
    assert provider.complete_structured(req).usage.input_tokens is None
    provider = OpenAIResponsesProvider(
        "requested", SecretStr("placeholder"), lambda *a: b"x" * 262145
    )
    with pytest.raises(LLMProviderError, match="AI_ANALYSIS_INVALID_RESPONSE"):
        provider.complete_structured(req)


@pytest.mark.parametrize(
    "settings,code",
    [
        (AIProviderSettings(provider="openai"), "CONFIGURATION_REQUIRED"),
        (AIProviderSettings(provider="openai", model="model"), "CONFIGURATION_REQUIRED"),
        (AIProviderSettings(provider="other"), "UNSUPPORTED"),
    ],
)
def test_configuration_is_truthful_without_fake_provider(settings, code):
    with pytest.raises(LLMProviderError, match=code):
        create_llm_provider(settings)
    assert create_llm_provider(AIProviderSettings()) is None


@pytest.mark.parametrize(
    "error,code",
    [
        (HTTPError("synthetic", 401, "auth", {}, BytesIO()), "AUTHENTICATION"),
        (HTTPError("synthetic", 403, "auth", {}, BytesIO()), "AUTHENTICATION"),
        (HTTPError("synthetic", 429, "rate", {}, BytesIO()), "RATE_LIMIT"),
        (HTTPError("synthetic", 503, "transient", {}, BytesIO()), "TRANSIENT_ERROR"),
        (HTTPError("synthetic", 400, "bad", {}, BytesIO()), "HTTP_ERROR"),
        (TimeoutError(), "TIMEOUT"),
        (URLError(TimeoutError()), "TIMEOUT"),
        (URLError("connection"), "CONNECTION_ERROR"),
    ],
)
def test_transport_failure_mapping_is_bounded_without_retries(error, code):
    # Imported function is real; the opener is replaced before any I/O.
    opener = Mock()
    opener.open.side_effect = error
    with (
        patch("archguard.infrastructure.llm_provider.build_opener", return_value=opener),
        pytest.raises(LLMProviderError, match=code),
    ):
        _post(b"{}", "placeholder", 1)
    assert opener.open.call_count == 1


def test_transport_bounds_response_and_disables_redirects():
    response = BytesIO(b"x" * 262145)
    opener = Mock()
    opener.open.return_value = response
    with (
        patch("archguard.infrastructure.llm_provider.build_opener", return_value=opener),
        pytest.raises(LLMProviderError, match="TOO_LARGE"),
    ):
        _post(b"{}", "placeholder", 1)
    assert (
        _NoRedirect().redirect_request(None, None, 302, "moved", None, "https://other.invalid")
        is None
    )
