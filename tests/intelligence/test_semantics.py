import json
from uuid import uuid4

import pytest

from archguard.architecture.intelligence.analyzer import SemanticArchitectureAnalyzer
from archguard.architecture.intelligence.models import (
    RULES,
    AIAnalysisBudget,
    AIAnalysisConfig,
    LLMUsage,
    SemanticDecision,
    TargetSelectionConfig,
    serialize_ai,
)
from archguard.architecture.intelligence.ports import LLMProviderError
from archguard.architecture.intelligence.selection import SemanticAnalysisTargetSelector
from tests.helpers.scripted_llm import ScriptedLLMProvider, assessment


def analyze(chain, provider=None, dry_run=False, **overrides):
    config = AIAnalysisConfig(
        targets=TargetSelectionConfig(explicit_targets=("A", "B", "C")), **overrides
    )
    inputs, workspace, _ = chain
    return SemanticArchitectureAnalyzer().analyze(
        inputs.iam, inputs.graph, workspace, config, provider, inputs.discovery, dry_run=dry_run
    )


@pytest.mark.parametrize("rule", list(RULES))
@pytest.mark.parametrize("decision", list(SemanticDecision))
def test_all_semantic_rules_and_decisions_are_candidates(chain, rule, decision):
    inputs, workspace, _ = chain
    provider = ScriptedLLMProvider([lambda request: assessment(request, decision)])
    config = AIAnalysisConfig(targets=TargetSelectionConfig(explicit_targets=("B",), rules=(rule,)))
    result = SemanticArchitectureAnalyzer().analyze(
        inputs.iam, inputs.graph, workspace, config, provider, inputs.discovery
    )
    assert result.status == "COMPLETE"
    assert result.candidates[0].assessment.decision == decision
    assert result.candidates[0].not_calibrated is True
    assert "findings" not in result.model_dump() and "confidence" not in serialize_ai(result)
    assert result.invocations[0].usage.input_tokens is None


def mutated(field, value):
    def script(request):
        result = json.loads(assessment(request))
        result[field] = value
        return json.dumps(result)

    return script


@pytest.mark.parametrize(
    "script",
    [
        "invalid-json",
        "[]",
        '"string"',
        '{"decision":"SUPPORTED","decision":"NOT_SUPPORTED"}',
        *[
            mutated("candidate_rule_id", rule)
            for rule in (
                "SEC001",
                "ARCH001",
                "ARCH002",
                "ARCH003",
                "ARCH004",
                "ARCH005",
                "ARCH101",
                "ARCH999",
            )
        ],
        mutated("evidence_refs", ["SRC999"]),
        mutated("evidence_refs", []),
        mutated("subject_node_ids", [str(uuid4())]),
        mutated("subject_node_ids", []),
        mutated("code_snippet", "private class Secret {}"),
        mutated("short_reason", "line 72 has misplaced responsibility"),
        mutated("short_reason", "See Missing.java for actual implementation"),
        mutated("short_reason", "x" * 1501),
        mutated("short_reason", 12),
        mutated("limitations", ["x"] * 11),
        mutated("decision", "VIOLATION"),
        " " * 32769,
    ],
)
def test_invalid_schema_catalog_evidence_and_claims_are_isolated(chain, script):
    result = analyze(chain, ScriptedLLMProvider([script, assessment, assessment]))
    assert result.status == "PARTIAL" and result.calls == 3 and len(result.candidates) == 2
    assert result.invocations[0].diagnostic.code == "AI_ANALYSIS_INVALID_RESPONSE"
    assert "private class Secret" not in serialize_ai(result)


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("PRIVATE_SOURCE_MARKER"), "AI_PROVIDER_TIMEOUT"),
        (LLMProviderError("AI_PROVIDER_AUTHENTICATION"), "AI_PROVIDER_AUTHENTICATION"),
        (LLMProviderError("AI_PROVIDER_RATE_LIMIT"), "AI_PROVIDER_RATE_LIMIT"),
        (LLMProviderError("AI_PROVIDER_TRANSIENT_ERROR"), "AI_PROVIDER_TRANSIENT_ERROR"),
        (RuntimeError("PRIVATE_SOURCE_MARKER"), "AI_PROVIDER_FAILURE"),
    ],
)
def test_middle_provider_failure_keeps_other_results(chain, error, code):
    provider = ScriptedLLMProvider([assessment, error, assessment])
    result = analyze(chain, provider)
    assert (
        result.status == "PARTIAL" and len(result.candidates) == 2 and len(provider.requests) == 3
    )
    assert result.invocations[1].diagnostic.code == code
    assert "PRIVATE_SOURCE_MARKER" not in serialize_ai(result)


def test_dry_run_and_remote_permissions_make_zero_calls(chain):
    provider = ScriptedLLMProvider(remote=True)
    dry = analyze(chain, provider, dry_run=True)
    denied = analyze(chain, provider)
    assert dry.status == "DRY_RUN" and denied.status == "UNAVAILABLE"
    assert dry.calls == denied.calls == 0 and not provider.requests
    assert analyze(chain, provider, allow_remote_source=True).calls == 3
    assert analyze(chain).status == "UNAVAILABLE"
    assert "PRIVATE_SOURCE_MARKER" not in serialize_ai(dry)


def test_prompt_injection_is_only_untrusted_data_in_actual_request(chain):
    provider = ScriptedLLMProvider()
    analyze(chain, provider)
    request = next(
        r for r in provider.requests if "PRIVATE_SOURCE_MARKER" in json.dumps(r.untrusted_context)
    )
    assert "PRIVATE_SOURCE_MARKER" not in request.system_instructions
    assert "SEC001" not in json.dumps(request.task)
    assert request.untrusted_context["trust"] == "UNTRUSTED_DATA"
    assert "never instructions" in request.system_instructions
    assert request.response_schema["additionalProperties"] is False
    assert set(request.response_schema["required"]) == set(request.response_schema["properties"])


def test_candidate_identity_excludes_decision_request_and_run_ids(chain):
    one = analyze(chain, ScriptedLLMProvider(request_id="first"))
    two = analyze(
        chain,
        ScriptedLLMProvider(
            request_id="second",
            script=[lambda r: assessment(r, "NOT_SUPPORTED"), assessment, assessment],
        ),
    )
    assert [c.candidate_id for c in one.candidates] == [c.candidate_id for c in two.candidates]
    assert one.invocations[0].invocation_id != two.invocations[0].invocation_id
    assert one.invocations[0].provider_request_id == "first"


@pytest.mark.parametrize(
    "budget", [AIAnalysisBudget(max_calls=1), AIAnalysisBudget(max_candidates=1)]
)
def test_call_and_candidate_limits(chain, budget):
    result = analyze(chain, ScriptedLLMProvider(), budget=budget)
    assert result.calls == 1 and len(result.candidates) == 1 and result.skipped_targets == 2
    assert result.status == "PARTIAL"


def test_exact_preflight_token_budget_reserves_failed_calls(chain):
    provider = ScriptedLLMProvider(
        [TimeoutError(), assessment],
        input_count=100,
        usage=LLMUsage(input_tokens=100, output_tokens=20, total_tokens=120),
    )
    result = analyze(chain, provider, budget=AIAnalysisBudget(max_total_input_tokens=200))
    assert result.calls == 2 and result.skipped_targets == 1
    assert result.invocations[1].usage.total_tokens == 120
    unknown = analyze(
        chain, ScriptedLLMProvider(), budget=AIAnalysisBudget(max_total_input_tokens=200)
    )
    assert unknown.calls == 0 and unknown.skipped_targets == 3
    assert any(d.code == "AI_TOKEN_BUDGET_UNMEASURABLE" for d in unknown.diagnostics)


def test_target_selector_is_bounded_deterministic_and_not_all_nodes(chain):
    inputs = chain[0]
    selector = SemanticAnalysisTargetSelector()
    config = TargetSelectionConfig(explicit_targets=("C", "A", "B", "B"), max_targets=2)
    targets, skipped = selector.select(inputs.iam, inputs.graph, inputs.discovery, config)
    assert len(targets) == 2 and skipped == 1
    assert (targets, skipped) == selector.select(inputs.iam, inputs.graph, inputs.discovery, config)
    defaults, _ = selector.select(
        inputs.iam, inputs.graph, inputs.discovery, TargetSelectionConfig()
    )
    assert defaults == ()
    unknown, _ = selector.select(
        inputs.iam, inputs.graph, inputs.discovery, TargetSelectionConfig(include_unknown=True)
    )
    assert len(unknown) == 4
