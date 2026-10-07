"""Blind serial execution of the approved immutable 120 requests; no truth access."""

import fcntl
import json
import platform
import re
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from prompt014_provider_validation import sanitized

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_preflight import (
    PricingAssumption,
    SemanticAssessmentJudgment,
    SemanticExperimentManifest,
)
from archguard.infrastructure.llm_provider import AIProviderSettings, _NoRedirect
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_preflight import wire_payload

FROZEN_EXPERIMENT = "92c4c909e5953d9e0ba07f00126eae75bf8225b128d1eb989a0df02d4c722a04"
FROZEN_CONTEXT = "f9502ddecd8db147c419edd28f3227fb6174a0c8522f59c1b22eb38982e53afe"


def now():
    return datetime.now(UTC).isoformat()


def unique_object(pairs):
    if len({k for k, _ in pairs}) != len(pairs):
        raise ValueError("duplicate response keys")
    return dict(pairs)


def accepted(text, request):
    raw = json.loads(text, object_pairs_hook=unique_object)
    result = SemanticAssessmentJudgment.model_validate_json(json.dumps(raw), strict=True)
    context = request.untrusted_context
    refs = {f["reference"]["evidence_id"] for f in context["source_fragments"]}
    refs |= {e["evidence_id"] for e in context["evidence"]}
    if (
        result.candidate_rule_id != request.task["candidate_rule_id"]
        or request.task["subject_node_id"] not in result.subject_node_ids
        or not set(result.subject_node_ids) <= set(context["selected_node_ids"])
        or not set(result.evidence_refs) <= refs
        or len(set(result.subject_node_ids)) != len(result.subject_node_ids)
        or len(set(result.evidence_refs)) != len(result.evidence_refs)
        or (result.judgment == "SUPPORTED" and not result.evidence_refs)
    ):
        raise ValueError("response not grounded in supplied subjects/rule/evidence")
    prose = " ".join((result.short_reason, *result.limitations))
    if re.search(r"[`{}]|\b(?:line|lines|строк[аеуи]?)\s*[:#]?\s*\d", prose, re.I):
        raise ValueError("source quotes/location claims prohibited")
    if any(f["reference"]["relative_path"] in prose for f in context["source_fragments"]):
        raise ValueError("source paths prohibited in free text")
    return result.model_dump(mode="json")


def exchange(payload, settings, timeout):
    secret = settings.api_key.get_secret_value()
    started = time.monotonic()
    result = {
        "usage": None,
        "assessment_text": None,
        "retryable": False,
        "configuration_error": False,
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=canonical(payload).encode(),
        method="POST",
        headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"},
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError("provider response too large")
            data = json.loads(raw, object_pairs_hook=unique_object)
            usage = data.get("usage")
            if isinstance(usage, dict) and all(
                isinstance(usage.get(k), int) and usage[k] >= 0
                for k in ("input_tokens", "output_tokens", "total_tokens")
            ):
                result["usage"] = {
                    k: usage[k] for k in ("input_tokens", "output_tokens", "total_tokens")
                }
                result["cached_input_tokens"] = (usage.get("input_tokens_details") or {}).get(
                    "cached_tokens"
                )
                result["reasoning_output_tokens"] = (usage.get("output_tokens_details") or {}).get(
                    "reasoning_tokens"
                )
            result |= {
                "http_status": response.status,
                "provider_status": sanitized(data.get("status"), secret),
                "response_id": sanitized(data.get("id"), secret),
                "request_id": sanitized(response.headers.get("x-request-id"), secret),
                "actual_model": sanitized(data.get("model"), secret),
                "service_tier": sanitized(data.get("service_tier"), secret),
            }
            if data.get("model") != settings.model:
                result |= {
                    "outcome": "TECHNICAL_FAILURE",
                    "error_code": "MODEL_ID_MISMATCH",
                    "configuration_error": True,
                }
            elif isinstance(data.get("error"), dict):
                error = data["error"]
                config = error.get("code") in {
                    "insufficient_quota",
                    "billing_hard_limit_reached",
                    "account_deactivated",
                    "invalid_api_key",
                    "model_not_found",
                    "unsupported_country_region_territory",
                }
                result |= {
                    "outcome": "TECHNICAL_FAILURE",
                    "error_code": "AI_PROVIDER_RESPONSE_ERROR",
                    "provider_error_code": sanitized(error.get("code"), secret),
                    "provider_error_message": sanitized(error.get("message"), secret),
                    "configuration_error": config,
                    "retryable": error.get("code") in {"server_error", "rate_limit_exceeded"},
                }
            elif data.get("status") != "completed":
                result |= {
                    "outcome": "INVALID_RESPONSE",
                    "error_code": "AI_PROVIDER_INCOMPLETE_RESPONSE",
                }
            else:
                texts = [
                    i["text"]
                    for o in data.get("output", [])
                    if o.get("type") == "message"
                    for i in o.get("content", [])
                    if i.get("type") == "output_text"
                ]
                refusal = any(
                    i.get("type") == "refusal"
                    for o in data.get("output", [])
                    for i in o.get("content", [])
                )
                if refusal or len(texts) != 1 or not isinstance(texts[0], str):
                    result |= {
                        "outcome": "INVALID_RESPONSE",
                        "error_code": "AI_PROVIDER_REFUSAL"
                        if refusal
                        else "AI_ANALYSIS_INVALID_RESPONSE",
                    }
                elif secret in texts[0] or any(
                    secret[i : i + 8] in texts[0] for i in range(len(secret) - 7)
                ):
                    result |= {
                        "outcome": "INVALID_RESPONSE",
                        "error_code": "SECRET_ECHO_BLOCKED",
                        "configuration_error": True,
                    }
                else:
                    result |= {"outcome": "SUCCESS", "assessment_text": texts[0]}
    except HTTPError as error:
        try:
            body = json.loads(error.read(262144)).get("error", {})
            if not isinstance(body, dict):
                body = {}
        except (ValueError, AttributeError):
            body = {}
        code = sanitized(body.get("code"), secret)
        config = (
            error.code in {400, 401, 402, 403, 404}
            or body.get("code")
            in {"insufficient_quota", "billing_hard_limit_reached", "account_deactivated"}
            or body.get("type") == "insufficient_quota"
        )
        retry = not config and (error.code == 429 or error.code >= 500)
        result |= {
            "outcome": "TECHNICAL_FAILURE",
            "http_status": error.code,
            "provider_error_code": code,
            "provider_error_type": sanitized(body.get("type"), secret),
            "provider_error_message": sanitized(body.get("message"), secret),
            "error_code": "AI_PROVIDER_RATE_LIMIT"
            if error.code == 429
            else "AI_PROVIDER_TRANSIENT_ERROR"
            if error.code >= 500
            else "AI_PROVIDER_HTTP_ERROR",
            "retryable": retry,
            "configuration_error": config,
        }
    except (URLError, TimeoutError) as error:
        result |= {
            "outcome": "TECHNICAL_FAILURE",
            "error_code": "AI_PROVIDER_TIMEOUT"
            if isinstance(error, TimeoutError)
            or isinstance(getattr(error, "reason", None), TimeoutError)
            else "AI_PROVIDER_CONNECTION_ERROR",
            "retryable": True,
        }
    except (ValueError, TypeError, KeyError, AttributeError):
        result |= {"outcome": "INVALID_RESPONSE", "error_code": "AI_ANALYSIS_INVALID_RESPONSE"}
    result["latency_seconds"] = time.monotonic() - started
    return result


def append_event(path, payload):
    payload = payload | {"fingerprint": digest(payload)}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(canonical(payload) + "\n")
        stream.flush()
        import os

        os.fsync(stream.fileno())


def logical_row(identity, event):
    row = {
        "case_id": event["case_id"],
        "strategy": event["strategy"],
        "status": event["outcome"],
        "request_fingerprint": identity["request_fingerprint"],
        "context_fingerprint": identity["context_fingerprint"],
        "assessment": event["accepted_assessment"],
        "attempt_count": event["attempt_number"],
        "actual_model": event.get("actual_model"),
        "response_id": event.get("response_id"),
        "error_code": event.get("error_code"),
        "usage": event["usage"],
        "estimated_cost_usd": event["estimated_cost_usd"],
        "latency_seconds": event["latency_seconds"],
    }
    return row | {"fingerprint": digest(row)}


def execute(
    manifest,
    context,
    requests,
    destination,
    settings,
    pricing,
    connectivity,
    transport=exchange,
    sleeper=time.sleep,
    answers=None,
):
    destination.mkdir(parents=True, exist_ok=True)
    results_dir = destination / "logical-results"
    results_dir.mkdir(exist_ok=True)
    ledger = destination / "attempt-ledger.jsonl"
    events = (
        [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    )
    assert all(
        e["fingerprint"] == digest({k: v for k, v in e.items() if k != "fingerprint"})
        for e in events
    )
    started_ids = {e["attempt_id"] for e in events if e["event"] == "STARTED"}
    ended_ids = {e["attempt_id"] for e in events if e["event"] == "RESULT"}
    if started_ids != ended_ids:
        raise ValueError("ambiguous interrupted attempt; never automatically replay")
    assert len(started_ids) == sum(e["event"] == "STARTED" for e in events)
    assert len(ended_ids) == sum(e["event"] == "RESULT" for e in events)
    attempts = [e for e in events if e["event"] == "RESULT"]
    results = {}
    for path in results_dir.glob("*.json"):
        row = json.loads(path.read_text())
        assert row["fingerprint"] == digest({k: v for k, v in row.items() if k != "fingerprint"})
        results[(row["case_id"], row["strategy"])] = row
    by_key = {(r["case_id"], r["strategy"]): r for r in context["requests"]}
    maximum_attempt = pricing.charge(
        manifest.max_input_tokens_per_request, manifest.max_output_tokens_per_request
    )

    def accounting(status):
        known = sum(
            (
                Decimal(a["estimated_cost_usd"])
                for a in attempts
                if a["estimated_cost_usd"] is not None
            ),
            Decimal(0),
        )
        unknown = sum(a["estimated_cost_usd"] is None for a in attempts)
        usage = {
            k: sum((a["usage"] or {}).get(k, 0) for a in attempts)
            for k in ("input_tokens", "output_tokens", "total_tokens")
        }
        return {
            "status": status,
            "logical_expected": manifest.logical_requests,
            "logical_terminal": len(results),
            "successful": sum(r["status"] == "SUCCESS" for r in results.values()),
            "remaining": manifest.logical_requests - len(results),
            "attempts": len(attempts),
            "retries": sum(a["attempt_number"] > 1 for a in attempts),
            "usage": usage,
            "known_estimated_cost_usd": str(known),
            "unknown_usage_attempts": unknown,
            "unknown_usage_maximum_usd": str(unknown * maximum_attempt),
            "connectivity_estimated_cost_usd": connectivity["estimated_usage_cost_usd"],
            "total_cost_exposure_usd": str(
                known
                + unknown * maximum_attempt
                + Decimal(connectivity["estimated_usage_cost_usd"])
            ),
            "provider_reported_cost_usd": None,
        }

    for case, strategy in manifest.execution_order:
        key = (case, strategy.value)
        identity = by_key[key]
        if key in results:
            assert results[key]["request_fingerprint"] == identity["request_fingerprint"]
            continue
        item = json.loads((requests / (digest(key) + ".json")).read_text())
        request = StructuredLLMRequest.model_validate(item["structured_request"])
        assert digest(request) == identity["request_fingerprint"]
        assert item["provider_payload"] == wire_payload(request, manifest.model)
        past = [a for a in attempts if (a["case_id"], a["strategy"]) == key]
        if past and past[-1].get("configuration_error"):
            return accounting("STOP_CONFIGURATION_ERROR") | {"safe_error": past[-1]}
        if past and (not past[-1]["retryable"] or len(past) > manifest.max_retries):
            row = logical_row(identity, past[-1])
            write_new(results_dir / (digest(key) + ".json"), row)
            results[key] = row
            continue
        for number in range(len(past) + 1, manifest.max_retries + 2):
            current = accounting("RUNNING")
            if Decimal(current["total_cost_exposure_usd"]) + maximum_attempt >= Decimal("0.95"):
                return accounting("STOP_COST_GUARD; WAITING_FOR_APPROVAL")
            attempt_id = digest((manifest.fingerprint, case, strategy.value, number))
            append_event(
                ledger,
                {
                    "event": "STARTED",
                    "attempt_id": attempt_id,
                    "case_id": case,
                    "strategy": strategy.value,
                    "attempt_number": number,
                    "started_at_utc": now(),
                    "request_fingerprint": identity["request_fingerprint"],
                },
            )
            response = transport(item["provider_payload"], settings, request.timeout_seconds)
            text = response.pop("assessment_text", None)
            if text is not None and answers is not None:
                answers.mkdir(parents=True, exist_ok=True)
                write_new(
                    answers / (attempt_id + ".json"),
                    {"case_id": case, "strategy": strategy.value, "provider_text": text},
                )
            assessment = None
            if response["outcome"] == "SUCCESS":
                try:
                    assessment = accepted(text, request)
                except (ValueError, TypeError):
                    response |= {
                        "outcome": "INVALID_RESPONSE",
                        "error_code": "AI_ANALYSIS_INVALID_RESPONSE",
                        "retryable": False,
                    }
            usage = response.get("usage")
            cost = (
                str(pricing.charge(usage["input_tokens"], usage["output_tokens"]))
                if usage
                else None
            )
            event = response | {
                "event": "RESULT",
                "attempt_id": attempt_id,
                "case_id": case,
                "strategy": strategy.value,
                "attempt_number": number,
                "estimated_cost_usd": cost,
                "finished_at_utc": now(),
                "accepted_assessment": assessment,
            }
            event |= {"fingerprint": digest(event)}
            append_event(ledger, {k: v for k, v in event.items() if k != "fingerprint"})
            attempts.append(event)
            if response.get("configuration_error"):
                return accounting("STOP_CONFIGURATION_ERROR") | {"safe_error": response}
            if usage and (
                usage["input_tokens"] > manifest.max_input_tokens_per_request
                or usage["output_tokens"] > manifest.max_output_tokens_per_request
            ):
                return accounting("STOP_PROVIDER_TOKEN_LIMIT_DEVIATION")
            if response["retryable"] and number <= manifest.max_retries:
                sleeper(min(number, 2))
                continue
            row = logical_row(identity, event)
            write_new(results_dir / (digest(key) + ".json"), row)
            results[key] = row
            print(canonical(accounting("RUNNING")), flush=True)
            break
    ordered = [results[(case, strategy.value)] for case, strategy in manifest.execution_order]
    payload = {
        "schema_version": "real-ai-assessments-v1",
        "experiment_fingerprint": manifest.fingerprint,
        "context_manifest_fingerprint": context["fingerprint"],
        "assessments": ordered,
        "attempts": attempts,
        "accounting": accounting("EXECUTION_COMPLETE"),
        "frozen_at_utc": now(),
    }
    path = destination / "real-ai-assessments-v1.json"
    if not path.exists():
        write_new(path, payload | {"fingerprint": digest(payload)})
    frozen = json.loads(path.read_text())
    assert frozen["fingerprint"] == digest({k: v for k, v in frozen.items() if k != "fingerprint"})
    return frozen["accounting"] | {"assessment_freeze_fingerprint": frozen["fingerprint"]}


def main():
    assert (
        subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                "dcacc6a8ea42231e4d0fb97dcf171caaaae02a56",
                "HEAD",
            ]
        ).returncode
        == 0
    )
    root = Path("experiments/ai/semantic-context-v1")
    manifest = SemanticExperimentManifest.model_validate_json(
        (root / "semantic-context-v1.json").read_text()
    )
    context = json.loads((root / "context-manifest-v1.json").read_text())
    assert manifest.fingerprint == FROZEN_EXPERIMENT and context["fingerprint"] == FROZEN_CONTEXT
    assert context["fingerprint"] == digest(
        {k: v for k, v in context.items() if k != "fingerprint"}
    )
    connectivity = json.loads(
        Path("experiments/ai/connectivity-v1/provider-validation-v1.json").read_text()
    )
    assert connectivity["status"] == "CONNECTIVITY_SUCCEEDED"
    assert connectivity["fingerprint"] == digest(
        {k: v for k, v in connectivity.items() if k != "fingerprint"}
    )
    pricing = PricingAssumption.model_validate_json(
        Path(
            "experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json"
        ).read_text()
    )
    settings = AIProviderSettings(_env_file=Path(".env.ai.local"))
    assert (
        settings.provider == manifest.provider
        and settings.model == manifest.model
        and settings.api_key
    )
    destination = Path("experiments/ai/semantic-context-live-v1")
    destination.mkdir(parents=True, exist_ok=True)
    private_lock = Path("experiments/ai/private/semantic-context-live-v1")
    private_lock.mkdir(parents=True, exist_ok=True)
    with (private_lock / "execution.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        metadata = destination / "run-metadata.json"
        if not metadata.exists():
            write_new(
                metadata,
                {
                    "approved_commit": "dcacc6a8ea42231e4d0fb97dcf171caaaae02a56",
                    "head": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True
                    ).strip(),
                    "python": platform.python_version(),
                    "os": platform.platform(),
                    "driver_code_fingerprint": digest(Path(__file__).read_text()),
                    "started_at_utc": now(),
                    "authorization": "EXPLICIT_USER_LIVE_APPROVAL",
                    "experiment_fingerprint": manifest.fingerprint,
                    "context_manifest_fingerprint": context["fingerprint"],
                },
            )
        result = execute(
            manifest,
            context,
            Path("experiments/ai/private/semantic-context-v1/requests"),
            destination,
            settings,
            pricing,
            connectivity,
            answers=private_lock / "answers",
        )
        print(canonical(result), flush=True)
        if result["status"] != "EXECUTION_COMPLETE":
            write_new(destination / "stop-receipt.json", result)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("blind executor stopped; exception contents suppressed") from None
