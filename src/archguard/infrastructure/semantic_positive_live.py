"""Blind Responses transport and source-free operational accounting. No truth reader."""

import json
import re
import ssl
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_positive_experiment import PositiveProtocol, RequestRecord
from archguard.infrastructure.llm_provider import AIProviderSettings, _NoRedirect
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_positive_execution import (
    ExecutionBindings,
    TransportOutcome,
    blind_io,
    freeze_assessments,
    load_execution,
    unique_object,
)
from archguard.infrastructure.semantic_positive_offline import audit_metadata
from archguard.infrastructure.semantic_preflight import wire_payload

DECISIONS = ("SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE")
CONFIG_CODES = {
    "insufficient_quota",
    "billing_hard_limit_reached",
    "account_deactivated",
    "invalid_api_key",
    "model_not_found",
    "unsupported_country_region_territory",
    "organization_usage_limit_exceeded",
}


class OpenAIPositiveTransport:
    """One HTTP attempt per invocation; uncertain transport never automatically retries."""

    def __init__(self, settings: AIProviderSettings, *, opener: Any = None) -> None:
        if (
            settings.provider != "openai"
            or settings.model != "gpt-6-luna"
            or not settings.api_key
            or not settings.api_key.get_secret_value()
        ):
            raise PermissionError("P016_LIVE_BLOCKED_CREDENTIAL_UNAVAILABLE")
        self._key = settings.api_key
        self._opener = opener or build_opener(
            ProxyHandler({}), _NoRedirect(), HTTPSHandler(context=ssl.create_default_context())
        )

    def sanitized(self, value: object) -> str:
        secret = self._key.get_secret_value()
        text = str(value).replace(secret, "[REDACTED]")
        text = re.sub(r"(?:sk-[^\s\"'<>]+|Bearer\s+\S+)", "[REDACTED]", text)
        for n in range(max(0, len(secret) - 7)):
            text = text.replace(secret[n : n + 8], "[REDACTED]")
        return text[:2000]

    def assert_secret_free(self, raw: bytes, *, actual_key_only: bool = False) -> None:
        secret = self._key.get_secret_value().encode()
        if (
            secret in raw
            or any(secret[n : n + 8] in raw for n in range(len(secret) - 7))
            or (
                not actual_key_only
                and re.search(
                    rb"\b(?:sk-[A-Za-z0-9_-]{16,}|Bearer\s+\S+|github_pat_[A-Za-z0-9_]{20,})", raw
                )
            )
        ):
            raise ValueError("credential echo blocked before persistence")

    def __call__(
        self, request: StructuredLLMRequest, protocol: PositiveProtocol
    ) -> TransportOutcome:
        if protocol.provider != "openai" or protocol.model != "gpt-6-luna":
            raise PermissionError("frozen provider/model required")
        wire = Request(
            "https://api.openai.com/v1/responses",
            data=canonical(wire_payload(request, protocol.model)).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer " + self._key.get_secret_value(),
                "Content-Type": "application/json",
            },
        )
        started = time.monotonic()
        code = 200
        request_id = None
        try:
            with self._opener.open(wire, timeout=protocol.timeout_seconds) as response:
                raw = response.read(262145)
                code = response.status
                request_id = response.headers.get("x-request-id")
        except HTTPError as error:
            code = error.code
            raw = error.read(262145)
            request_id = error.headers.get("x-request-id") if error.headers else None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError(
                "uncertain provider processing; pending attempt must remain"
            ) from None
        if len(raw) > 262144:
            raise RuntimeError("provider response too large; pending attempt must remain")
        metadata: dict[str, Any] = {
            "http_status": code,
            "http_request_id": self.sanitized(request_id) if request_id else None,
        }
        result: dict[str, Any] = {
            "raw_response": raw,
            "latency_seconds": time.monotonic() - started,
            "provider_metadata": metadata,
            "status": "TERMINAL_ERROR",
        }
        try:
            self.assert_secret_free(raw)
        except ValueError:
            if code == 200:
                raise
            # Credential safety takes precedence over preserving a credential-bearing error.
            raw = self.sanitized(raw.decode("utf-8", errors="replace")).encode()
            self.assert_secret_free(raw)
            result["raw_response"] = raw
            metadata["raw_error_redacted_for_credential_safety"] = True
        try:
            data = json.loads(raw, object_pairs_hook=unique_object)
            if not isinstance(data, dict):
                raise ValueError("provider response must be an object")
        except ValueError:
            if code in {400, 401, 402, 403, 404}:
                result["status"] = "CONFIGURATION_ERROR"
            result["error_metadata"] = {"code": "MALFORMED_PROVIDER_JSON"}
            return TransportOutcome(**result)
        usage = data.get("usage")
        if isinstance(usage, dict):
            result["provider_usage"] = usage
            for field in ("input_tokens", "output_tokens", "total_tokens"):
                quantity = usage.get(field)
                if type(quantity) is int and quantity >= 0:
                    result[field] = quantity
        response_error = data.get("error")
        if code != 200 or response_error:
            body = response_error if isinstance(response_error, dict) else {}
            result["error_metadata"] = {
                k: self.sanitized(body[k])
                for k in ("code", "type", "message", "param")
                if body.get(k) is not None
            }
            configuration = (
                code in {400, 401, 402, 403, 404}
                or body.get("code") in CONFIG_CODES
                or body.get("type") == "insufficient_quota"
            )
            result["status"] = (
                "CONFIGURATION_ERROR"
                if configuration
                else "RATE_LIMIT"
                if code == 429 or body.get("code") == "rate_limit_exceeded"
                else "TRANSIENT"
                if 500 <= code <= 599 or body.get("code") == "server_error"
                else "TERMINAL_ERROR"
            )
            return TransportOutcome(**result)
        metadata.update(
            {
                "response_id": data.get("id"),
                "actual_model": data.get("model"),
                "service_tier": data.get("service_tier"),
                "response_status": data.get("status"),
            }
        )
        if data.get("model") != protocol.model or data.get("service_tier") != "default":
            result.update(
                status="CONFIGURATION_ERROR",
                error_metadata={"code": "MODEL_OR_STANDARD_PROCESSING_MISMATCH"},
            )
        elif (
            not all(field in result for field in ("input_tokens", "output_tokens", "total_tokens"))
            or result["total_tokens"] != result["input_tokens"] + result["output_tokens"]
        ):
            result.update(
                status="CONFIGURATION_ERROR",
                error_metadata={"code": "PROVIDER_USAGE_UNAVAILABLE_OR_INCONSISTENT"},
            )
        elif data.get("status") != "completed":
            result["error_metadata"] = {
                "code": "PROVIDER_RESPONSE_INCOMPLETE",
                "details": data.get("incomplete_details"),
            }
        else:
            try:
                texts = [
                    item["text"]
                    for message in data.get("output", [])
                    if message.get("type") == "message"
                    for item in message.get("content", [])
                    if item.get("type") == "output_text"
                ]
                if len(texts) == 1 and isinstance(texts[0], str):
                    result.update(status="OK", assessment_json=texts[0])
                else:
                    result["error_metadata"] = {"code": "MISSING_SINGLE_STRUCTURED_RESPONSE"}
            except (TypeError, KeyError, AttributeError):
                result["error_metadata"] = {"code": "MALFORMED_RESPONSE_ENVELOPE"}
        self.assert_secret_free(canonical(metadata).encode())
        return TransportOutcome(**result)


def operational_report(ledger: Path, rows: tuple[RequestRecord, ...]) -> dict[str, Any]:
    events = [json.loads(p.read_bytes()) for p in sorted((ledger / "attempts").glob("*.json"))]
    results = [json.loads(p.read_bytes()) for p in sorted((ledger / "results").glob("*.json"))]
    pending = [json.loads(p.read_bytes()) for p in sorted((ledger / "pending").glob("*.json"))]
    by_id = {row.request_id: row for row in rows}
    groups = {}
    for strategy in ("LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE"):
        selected = [event for event in events if by_id[event["request_id"]].strategy == strategy]
        accepted = [r for r in results if r["strategy"] == strategy and r["status"] == "ACCEPTED"]
        distribution = Counter(r["assessment"]["judgment"] for r in accepted)
        groups[strategy] = {
            "accepted": len(accepted),
            "attempts": len(selected),
            "response_distribution": {d: distribution[d] for d in DECISIONS},
            **{
                field: sum(e[field] for e in selected)
                if all(e.get(field) is not None for e in selected)
                else None
                for field in ("input_tokens", "output_tokens", "total_tokens")
            },
            **{
                "mean_" + field: mean(e[field] for e in selected)
                if selected and all(e.get(field) is not None for e in selected)
                else None
                for field in ("input_tokens", "output_tokens")
            },
            "latency_total_seconds": sum(e["latency_seconds"] for e in selected),
            "latency_mean_seconds": mean(e["latency_seconds"] for e in selected)
            if selected
            else None,
            "latency_median_seconds": median(e["latency_seconds"] for e in selected)
            if selected
            else None,
            "retry_attempts": sum(e["attempt"] > 1 for e in selected),
            "estimated_cost_usd": str(
                sum(
                    (Decimal(e["cost_usd"]) for e in selected if e["cost_usd"] is not None),
                    Decimal(0),
                )
            )
            if all(e["cost_usd"] is not None for e in selected)
            else None,
        }
    accepted = [r for r in results if r["status"] == "ACCEPTED"]
    accepted_ids = [r["request_id"] for r in accepted]
    terminal_ids = {r["request_id"] for r in results if r["status"] == "TERMINAL_FAILURE"}
    technical = {"TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"}
    cost = sum((Decimal(e["cost_usd"]) for e in events if e["cost_usd"] is not None), Decimal(0))
    reserve = sum((Decimal(e["reserved_cost_usd"]) for e in events + pending), Decimal(0))
    expanded = groups["EXPANDED_BASELINE"]["input_tokens"]
    return {
        "expected_logical_requests": 300,
        "by_strategy": groups,
        "attempted_logical_requests": len({e["request_id"] for e in events + pending}),
        "terminal_logical_records": len(results),
        "valid_accepted_assessments": len(accepted),
        "scientific_provider_calls": len(events) + len(pending),
        "terminal_technical_failures": sum(
            e["status"] in technical
            for e in events
            if e["request_id"] in terminal_ids and e["attempt"] == 3
        ),
        "terminal_protocol_failures": sum(
            e["status"] in {"TERMINAL_INVALID", "TERMINAL_ERROR"}
            for e in events
            if e["request_id"] in terminal_ids
        ),
        "configuration_failures": sum(e["status"] == "CONFIGURATION_ERROR" for e in events),
        "pending_transport_outcomes": len(pending),
        "duplicate_accepted_assessments": len(accepted_ids) - len(set(accepted_ids)),
        "duplicate_provider_executions": len(events)
        - len({(e["request_id"], e["attempt"]) for e in events}),
        "retries": {
            "first_attempt_successes": sum(r["attempts"] == 1 for r in accepted),
            "one_retry_successes": sum(r["attempts"] == 2 for r in accepted),
            "two_retry_successes": sum(r["attempts"] == 3 for r in accepted),
            "total_retry_attempts": sum(e["attempt"] > 1 for e in events),
            "maximum_retries": max((e["attempt"] - 1 for e in events), default=0),
            "policy_violations": 0,
        },
        "provider_usage": {
            field: sum(e[field] for e in events)
            if not pending and all(e.get(field) is not None for e in events)
            else None
            for field in ("input_tokens", "output_tokens", "total_tokens")
        },
        "unknown_usage_attempts": sum(e.get("total_tokens") is None for e in events) + len(pending),
        "retry_usage": {
            field: sum(e[field] for e in events if e["attempt"] > 1)
            if all(e.get(field) is not None for e in events if e["attempt"] > 1)
            else None
            for field in ("input_tokens", "output_tokens", "total_tokens")
        },
        "spend": {
            "estimated_scientific_cost_usd": str(cost)
            if all(e["cost_usd"] is not None for e in events) and not pending
            else None,
            "known_usage_estimated_cost_usd": str(cost),
            "connectivity_estimated_cost_usd": "0",
            "connectivity_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "estimated_retry_cost_usd": str(
                sum(
                    (
                        Decimal(e["cost_usd"])
                        for e in events
                        if e["attempt"] > 1 and e["cost_usd"] is not None
                    ),
                    Decimal(0),
                )
            ),
            "reserved_maximum_spend_usd": str(reserve),
            "hard_spend_cap_usd": "4.50",
            "cap_exceeded": reserve > Decimal("4.50"),
            "actual_invoice_cost_usd": None,
        },
        "operational_input_reduction_percent": {
            strategy: 100 * (1 - groups[strategy]["input_tokens"] / expanded)
            if expanded and groups[strategy]["input_tokens"] is not None
            else None
            for strategy in ("LOCAL_ONLY", "GRAPH_GUIDED")
        },
        "provider_errors": [e["error_metadata"] for e in events if e.get("error_metadata")],
        "long_context_requests": sum((e["input_tokens"] or 0) > 272000 for e in events),
    }


def freeze_live(root: Path, ledger: Path, bindings: ExecutionBindings) -> dict[str, Any]:
    protocol, rows = load_execution(root, bindings)
    with blind_io(root, ledger):
        report = operational_report(ledger, rows)
        if (
            report["valid_accepted_assessments"] != 300
            or report["pending_transport_outcomes"]
            or report["spend"]["cap_exceeded"]
        ):
            raise ValueError("complete live freeze requires 300 accepted assessments within cap")
        for path in ledger.rglob("*.json"):
            audit_metadata(json.loads(path.read_bytes()))
        normalized = {
            "schema_version": "p016-normalized-assessments-v1",
            "bindings": bindings.model_dump(),
            "assessments": [
                json.loads((ledger / "results" / (r.request_id + ".json")).read_bytes())
                for r in rows
            ],
        }
        events = [json.loads(p.read_bytes()) for p in (ledger / "attempts").glob("*.json")]
        events.sort(
            key=lambda e: ([r.request_id for r in rows].index(e["request_id"]), e["attempt"])
        )
        usage = {
            "schema_version": "p016-attempt-usage-ledger-v1",
            "bindings": bindings.model_dump(),
            "attempts": events,
        }
        raw = {
            "schema_version": "p016-raw-ledger-v1",
            "raw_responses": [
                {
                    k: e[k]
                    for k in ("request_id", "attempt", "raw_response_path", "raw_response_sha256")
                }
                for e in events
            ],
        }
        lineage = {
            "schema_version": "p016-execution-lineage-v1",
            "bindings": bindings.model_dump(),
            "provider": protocol.provider,
            "model": protocol.model,
            "prompt_schema_fingerprint": protocol.prompt_schema_fingerprint,
            "raw_ledger_fingerprint": digest(raw),
            "normalized_assessment_fingerprint": digest(normalized),
            "usage_ledger_fingerprint": digest(usage),
        }
        artifacts: dict[str, dict[str, Any]] = {
            "normalized-assessments.json": normalized,
            "attempt-usage-ledger.json": usage,
            "raw-ledger.json": raw,
            "execution-lineage.json": lineage,
        }
        for name, value in artifacts.items():
            payload = value | {"fingerprint": digest(value)}
            path = ledger / name
            if path.exists():
                if path.read_bytes() != (canonical(payload) + "\n").encode():
                    raise ValueError("append-only live normalization drift")
            else:
                write_new(path, payload)
        receipt = freeze_assessments(root, ledger, bindings)
        return {
            **lineage,
            "execution_lineage_fingerprint": digest(lineage),
            "ai_freeze_receipt_fingerprint": receipt["fingerprint"],
            "all_300_accepted_before_freeze": True,
            "ai_assessment_ledger_frozen": True,
            "freeze_before_truth_join": True,
            "operational_statistics": report,
        }
