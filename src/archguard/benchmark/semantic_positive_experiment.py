"""Prospective P016 contracts and offline budgeting; no human labels or provider access."""

from collections import Counter
from decimal import Decimal
from math import ceil
from statistics import mean, median
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from archguard.architecture.intelligence.models import ContextSelectionConfig, ContextStrategy
from archguard.benchmark.oss.models import Sealed, digest
from archguard.benchmark.semantic_preflight import (
    SYSTEM,
    PricingAssumption,
    SemanticAssessmentJudgment,
)
from archguard.core.model.base import DomainModel

PROMPT_VERSION: Literal["positive-semantic-assessment-016-v1"] = (
    "positive-semantic-assessment-016-v1"
)
SYSTEM_PROMPT = SYSTEM + "\nEcho the supplied request_id exactly in your structured assessment."
STRATEGIES = tuple(ContextStrategy)


class PositiveAssessment(SemanticAssessmentJudgment):
    request_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class PositiveProtocol(Sealed):
    schema_version: Literal["positive-semantic-experiment-016-v1"] = (
        "positive-semantic-experiment-016-v1"
    )
    provider: Literal["openai"] = "openai"
    model: Literal["gpt-6-luna"] = "gpt-6-luna"
    processing: Literal["STANDARD"] = "STANDARD"
    sample_fingerprint: str
    source_freeze_fingerprint: str
    truth_fingerprint: str
    truth_freeze_fingerprint: str
    stage_a_commit: str
    cases: Literal[100] = 100
    logical_requests: Literal[300] = 300
    strategies: tuple[ContextSelectionConfig, ...]
    prompt_version: Literal["positive-semantic-assessment-016-v1"] = PROMPT_VERSION
    prompt_schema_fingerprint: str
    analysis_plan_fingerprint: str
    timeout_seconds: Literal[90] = 90
    max_input_tokens: Literal[32768] = 32768
    max_output_tokens: Literal[2000] = 2000
    expected_output_tokens: Literal[600] = 600
    max_technical_retries: Literal[2] = 2
    max_network_attempts: Literal[900] = 900
    concurrency: Literal[1] = 1
    order_policy: Literal["SHA256_CASE_RANK; ROTATING_STRATEGY_ORDER; SERIAL"] = (
        "SHA256_CASE_RANK; ROTATING_STRATEGY_ORDER; SERIAL"
    )
    retry_policy: Literal["TIMEOUT_CONNECTION_RATE_LIMIT_TRANSIENT_ONLY; INVALID_TERMINAL"] = (
        "TIMEOUT_CONNECTION_RATE_LIMIT_TRANSIENT_ONLY; INVALID_TERMINAL"
    )
    spend_cap_usd: Literal["5.00"] = "5.00"
    paid_execution_approved: Literal[False] = False
    context_policy: Literal["P014_UNCHANGED_SELECTION_PLUS_PRELABEL_ARCHITECTURE_CONTRACT"] = (
        "P014_UNCHANGED_SELECTION_PLUS_PRELABEL_ARCHITECTURE_CONTRACT"
    )

    @model_validator(mode="after")
    def frozen_contract(self) -> Self:
        expected = tuple(
            ContextSelectionConfig(
                strategy=s, include_spec=False, include_discovery=False, include_metrics=False
            )
            for s in STRATEGIES
        )
        if (
            self.strategies != expected
            or self.prompt_schema_fingerprint != digest(prompt_contract())
            or self.analysis_plan_fingerprint != digest(analysis_plan())
        ):
            raise ValueError("prospective strategy/prompt/analysis contract changed")
        return self


def prompt_contract() -> dict[str, Any]:
    from archguard.benchmark.semantic_preflight import QUESTIONS

    return {
        "prompt_version": PROMPT_VERSION,
        "system": SYSTEM_PROMPT,
        "questions": QUESTIONS,
        "response_schema": PositiveAssessment.model_json_schema(),
        "response_envelope": {
            "request_id": "bound locally",
            "provider": "openai",
            "model": "gpt-6-luna",
            "usage": "LIVE_ONLY",
            "latency": "LIVE_ONLY",
            "cost": "LIVE_ONLY",
        },
    }


def analysis_plan() -> dict[str, Any]:
    return {
        "version": "p016-prospective-analysis-v1",
        "purpose": ["RQ3 semantic effectiveness", "RQ5 context efficiency"],
        "reference": {
            "positive": "POSITIVE",
            "negative": "NEGATIVE",
            "excluded": ["UNCERTAIN", "OUT_OF_SCOPE"],
        },
        "AI_mapping": {
            "SUPPORTED": "positive",
            "NOT_SUPPORTED": "negative",
            "INSUFFICIENT_CONTEXT": "abstention",
            "NOT_APPLICABLE": "applicability_outcome",
        },
        "primary": {
            "TP": "POSITIVE + SUPPORTED",
            "FN": "POSITIVE + NOT_SUPPORTED",
            "TN": "NEGATIVE + NOT_SUPPORTED",
            "FP": "NEGATIVE + SUPPORTED",
            "precision": "TP/(TP+FP)",
            "recall_definitive": "TP/(TP+FN)",
            "F1_definitive": "2TP/(2TP+FP+FN)",
            "specificity_definitive": "TN/(TN+FP)",
            "FPR_definitive": "FP/(TN+FP)",
            "FNR_definitive": "FN/(TP+FN)",
            "effective_recall": "TP/all human POSITIVE",
            "effective_negative_correctness": "TN/all human NEGATIVE",
            "effective_correctness": "(TP+TN)/all binary eligible",
            "definitive_coverage": "(TP+FP+TN+FN)/all binary eligible",
            "abstention_rate": "INSUFFICIENT_CONTEXT/all binary eligible",
            "applicability_error_rate": "NOT_APPLICABLE/all binary eligible",
            "OOS_recognition": "NOT_APPLICABLE/all human OUT_OF_SCOPE",
            "nonbinary": "UNCERTAIN and OUT_OF_SCOPE remain separate descriptive cross-tabs",
            "zero_denominator": "null; never zero-filled",
        },
        "strata": [
            "strategy",
            "ARCH rule",
            "language",
            "IAM validity",
            "graph validity",
            "human category",
            "truncation",
        ],
        "small_N": "descriptive; no prevalence or significance claims",
        "paired": {
            "pairs": [
                ["GRAPH_GUIDED", "EXPANDED_BASELINE"],
                ["GRAPH_GUIDED", "LOCAL_ONLY"],
                ["LOCAL_ONLY", "EXPANDED_BASELINE"],
            ],
            "fields": [
                "correctness",
                "abstention",
                "coverage",
                "input_tokens",
                "latency_seconds",
                "cost_usd",
            ],
            "inferential_testing": "NOT_PLANNED; descriptive paired deltas only",
        },
        "RQ5": [
            "graph vs expanded input-token and context-char reduction",
            "latency/cost difference",
            "precision/recall/F1/coverage difference",
        ],
        "limits": [
            "controlled prospective mutation-based holdout; not natural prevalence",
            "N=100; binary eligible96; excluded4",
            "provider/model/version specificity",
        ],
        "boundary": "FROZEN_COMPLETE_AI_ASSESSMENTS_BEFORE_TRUTH_JOIN",
        "technical_failure": (
            "No semantic decision invented; report failure rate and all-case coverage. "
            "Technical failures remain in eligible denominators for effective correctness."
        ),
        "metrics_now": "NOT_CALCULATED",
    }


class RequestRecord(DomainModel):
    request_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_case_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    strategy: ContextStrategy
    target_rule: str = Field(pattern=r"^ARCH20[1-5]$")
    language: Literal["JAVA", "TYPESCRIPT"]
    context_fingerprint: str
    request_fingerprint: str
    context_chars: int = Field(ge=0, le=20000)
    source_chars: int = Field(ge=0)
    input_estimate: int = Field(ge=0)
    conservative_input_upper: int = Field(ge=0, le=32768)
    truncated: bool
    diagnostics: tuple[str, ...]
    iam_valid: bool
    graph_valid: bool


def ordered_product(case_ids: tuple[str, ...]) -> tuple[tuple[str, ContextStrategy], ...]:
    if len(case_ids) != 100 or len(set(case_ids)) != 100:
        raise ValueError("100 unique execution-safe cases required")
    return tuple(
        (case, STRATEGIES[(i + rotation) % 3])
        for rotation, case in enumerate(sorted(case_ids, key=digest))
        for i in range(3)
    )


def token_estimate(model_visible: str) -> tuple[int, int]:
    size = len(model_visible.encode("utf-8"))
    return ceil(size / 3) + 128, size + 2048


def preflight_cost(
    protocol: PositiveProtocol, rows: tuple[RequestRecord, ...], pricing: PricingAssumption
) -> dict[str, Any]:
    if (
        len(rows) != 300
        or len({r.request_id for r in rows}) != 300
        or Counter(r.strategy for r in rows) != dict.fromkeys(STRATEGIES, 100)
    ):
        raise ValueError("exact300 requests and100 per strategy required")
    if tuple((r.execution_case_id, r.strategy) for r in rows) != ordered_product(
        tuple(sorted({r.execution_case_id for r in rows}))
    ):
        raise ValueError("request product/order drift")
    expected = sum(
        (pricing.charge(r.input_estimate, protocol.expected_output_tokens) for r in rows),
        Decimal(0),
    )
    conservative = sum(
        (pricing.charge(r.conservative_input_upper, protocol.max_output_tokens) for r in rows),
        Decimal(0),
    )
    maximum = pricing.charge(protocol.max_input_tokens, protocol.max_output_tokens) * 300
    by_strategy = {}
    for strategy in STRATEGIES:
        selected = tuple(r for r in rows if r.strategy == strategy)
        tokens = [r.input_estimate for r in selected]
        by_strategy[strategy.value] = {
            "requests": len(selected),
            "context_chars": sum(r.context_chars for r in selected),
            "source_chars": sum(r.source_chars for r in selected),
            "estimated_input_tokens": sum(tokens),
            "mean_input_tokens": mean(tokens),
            "median_input_tokens": median(tokens),
            "maximum_input_tokens": max(tokens),
            "truncated": sum(r.truncated for r in selected),
            "missing_contexts": sum(not r.source_chars for r in selected),
        }
    return {
        "version": "p016-cost-preflight-v1",
        "experiment_fingerprint": protocol.fingerprint,
        "model": protocol.model,
        "pricing_assumption_fingerprint": pricing.fingerprint,
        "pricing_source": (
            "FROZEN P014 BUDGETING ASSUMPTION; NOT CURRENT PROVIDER PRICE VERIFICATION"
        ),
        "token_method": (
            "CEIL_MODEL_VISIBLE_UTF8_BYTES_DIV_3_PLUS_128; UPPER_BYTES_PLUS_2048; "
            "NO_LOCAL_MODEL_TOKENIZER; NOT_PROVIDER_USAGE"
        ),
        "by_strategy": by_strategy,
        "total_input_estimate": sum(r.input_estimate for r in rows),
        "expected_output_tokens_per_call": 600,
        "expected_output_budget": 180000,
        "max_output_tokens_per_call": 2000,
        "maximum_primary_output_budget": 600000,
        "maximum_output_with_retries": 1800000,
        "expected_usd": str(expected),
        "conservative_usd": str(conservative),
        "maximum_primary_usd": str(maximum),
        "one_retry_additional_max_usd": str(maximum),
        "one_retry_total_max_usd": str(maximum * 2),
        "bounded_retries_additional_max_usd": str(maximum * 2),
        "maximum_including_retries_usd": str(maximum * 3),
        "connectivity_check_separate": {
            "authorized": False,
            "assumed_input_tokens": 128,
            "assumed_output_tokens": 16,
            "planning_usd": str(pricing.charge(128, 16)),
            "configured_input_bound": 32768,
            "configured_output_bound": 16,
            "maximum_usd": str(pricing.charge(32768, 16)),
            "included_in_experiment": False,
        },
        "long_context_requests": sum(
            r.conservative_input_upper > pricing.short_context_input_cutoff for r in rows
        ),
        "approaching_context_window": sum(
            r.conservative_input_upper + 2000 >= pricing.context_window * 0.9 for r in rows
        ),
        "cache_savings_assumed": False,
        "paid_execution_approved": False,
        "live_api_calls": 0,
        "provider_usage": None,
        "spend_usd": "0",
    }
