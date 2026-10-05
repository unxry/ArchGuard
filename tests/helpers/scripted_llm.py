import json
from collections.abc import Callable

from archguard.architecture.intelligence.models import (
    LLMUsage,
    ProviderCapabilities,
    StructuredLLMRequest,
    StructuredLLMResponse,
)


def assessment(request: StructuredLLMRequest, decision: str = "SUPPORTED") -> str:
    fragments = request.untrusted_context["source_fragments"]
    refs = [fragments[0]["reference"]["evidence_id"]] if fragments else []
    return json.dumps(
        {
            "candidate_rule_id": request.task["candidate_rule_id"],
            "decision": decision,
            "subject_node_ids": [request.task["subject_node_id"]],
            "short_reason": "Offline scripted assessment for pipeline verification.",
            "evidence_refs": refs,
            "suggested_role": None,
            "suggested_layer": None,
            "assumptions": [],
            "limitations": ["Scripted fixture, not LLM quality evidence."],
            "recommendation": None,
        }
    )


class ScriptedLLMProvider:
    provider_id = "scripted-test-only"
    model_id = "offline-fixture-v1"

    def __init__(
        self,
        script: list[str | Exception | Callable[[StructuredLLMRequest], str]] | None = None,
        remote: bool = False,
        input_count: int | None = None,
        usage: LLMUsage | None = None,
        request_id: str | None = None,
    ) -> None:
        self.script = script
        self.capabilities = ProviderCapabilities(
            remote=remote, input_token_counting=input_count is not None
        )
        self.input_count = input_count
        self.usage = usage or LLMUsage()
        self.request_id = request_id
        self.requests: list[StructuredLLMRequest] = []

    def count_input_tokens(self, request: StructuredLLMRequest) -> int | None:
        return self.input_count

    def complete_structured(self, request: StructuredLLMRequest) -> StructuredLLMResponse:
        index = len(self.requests)
        self.requests.append(request)
        item = self.script[index] if self.script is not None else assessment
        if isinstance(item, Exception):
            raise item
        return StructuredLLMResponse(
            structured_json=item(request) if callable(item) else item,
            provider_id=self.provider_id,
            model_id=self.model_id,
            request_id=self.request_id,
            usage=self.usage,
        )
