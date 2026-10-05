import json
from collections.abc import Callable
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from archguard.architecture.intelligence.models import (
    LLMUsage,
    ProviderCapabilities,
    StructuredLLMRequest,
    StructuredLLMResponse,
    canonical,
)
from archguard.architecture.intelligence.ports import LLMProviderError


class AIProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARCHGUARD_AI_", extra="ignore", frozen=True, hide_input_in_errors=True
    )
    provider: str | None = None
    model: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    api_key: SecretStr | None = None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def _post(data: bytes, key: str, timeout: float) -> bytes:
    request = Request(
        "https://api.openai.com/v1/responses",
        data=data,
        method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw: bytes = response.read(262145)
        if len(raw) > 262144:
            raise LLMProviderError("AI_PROVIDER_RESPONSE_TOO_LARGE")
        return raw
    except HTTPError as error:
        code = (
            "AI_PROVIDER_AUTHENTICATION"
            if error.code in {401, 403}
            else "AI_PROVIDER_RATE_LIMIT"
            if error.code == 429
            else "AI_PROVIDER_TRANSIENT_ERROR"
            if error.code >= 500
            else "AI_PROVIDER_HTTP_ERROR"
        )
        raise LLMProviderError(code) from None
    except (TimeoutError, URLError) as error:
        raise LLMProviderError(
            "AI_PROVIDER_TIMEOUT"
            if isinstance(error, TimeoutError)
            or isinstance(getattr(error, "reason", None), TimeoutError)
            else "AI_PROVIDER_CONNECTION_ERROR"
        ) from None


class OpenAIResponsesProvider:
    provider_id = "openai"
    capabilities = ProviderCapabilities(remote=True)

    def __init__(
        self,
        model_id: str,
        api_key: SecretStr,
        transport: Callable[[bytes, str, float], bytes] | None = None,
    ) -> None:
        self.model_id = model_id
        self._api_key = api_key
        self._transport = transport or _post

    def count_input_tokens(self, request: StructuredLLMRequest) -> None:
        return None

    def complete_structured(self, request: StructuredLLMRequest) -> StructuredLLMResponse:
        payload = {
            "model": self.model_id,
            "store": False,
            "max_output_tokens": request.max_output_tokens,
            "input": [
                {"role": "system", "content": request.system_instructions},
                {
                    "role": "user",
                    "content": canonical(
                        {"task": request.task, "untrusted_context": request.untrusted_context}
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "architecture_assessment",
                    "strict": True,
                    "schema": request.response_schema,
                }
            },
        }
        raw = self._transport(
            canonical(payload).encode("utf-8"),
            self._api_key.get_secret_value(),
            request.timeout_seconds,
        )
        try:
            if len(raw) > 262144:
                raise ValueError("response too large")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("status") != "completed":
                raise LLMProviderError("AI_PROVIDER_INCOMPLETE_RESPONSE")
            texts = []
            for output in data.get("output", []):
                if output.get("type") == "message":
                    for item in output.get("content", []):
                        if item.get("type") == "refusal":
                            raise LLMProviderError("AI_PROVIDER_REFUSAL")
                        if item.get("type") == "output_text":
                            texts.append(item["text"])
            if len(texts) != 1 or not isinstance(data.get("model"), str):
                raise ValueError("missing assessment or actual model identity")
            usage = data.get("usage") or {}
            return StructuredLLMResponse(
                structured_json=texts[0],
                provider_id=self.provider_id,
                model_id=data["model"],
                request_id=data.get("id"),
                usage=LLMUsage(
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise LLMProviderError("AI_ANALYSIS_INVALID_RESPONSE") from None


def create_llm_provider(settings: AIProviderSettings) -> OpenAIResponsesProvider | None:
    if settings.provider is None:
        return None
    if settings.provider != "openai":
        raise LLMProviderError("AI_PROVIDER_UNSUPPORTED")
    if (
        not settings.model
        or not settings.api_key
        or not settings.api_key.get_secret_value().strip()
    ):
        raise LLMProviderError("AI_PROVIDER_CONFIGURATION_REQUIRED")
    return OpenAIResponsesProvider(settings.model, settings.api_key)
