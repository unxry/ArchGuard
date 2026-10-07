"""One authorized source-free connectivity probe; no assessment or evaluation execution."""

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.llm_provider import AIProviderSettings, _NoRedirect
from archguard.infrastructure.oss_benchmark import write_new


def sanitized(value, secret):
    if value is None:
        return None
    text = str(value)
    text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"sk-[^\s\"'<>]+", "[REDACTED]", text)
    for i in range(len(secret) - 3):
        text = text.replace(secret[i : i + 4], "[REDACTED]")
    return text[:2000]


def validate(settings, pricing, opener=None):
    if settings.provider != "openai" or settings.model != "gpt-6-luna" or not settings.api_key:
        raise ValueError("required runtime configuration unavailable")
    secret = settings.api_key.get_secret_value()
    payload = {
        "model": "gpt-6-luna",
        "store": False,
        "max_output_tokens": 64,
        "input": "Reply OK. This is a connectivity check, not an architecture assessment.",
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=canonical(payload).encode(),
        method="POST",
        headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"},
    )
    started = time.monotonic()
    result = {
        "purpose": "CONNECTIVITY_ONLY",
        "model_requested": "gpt-6-luna",
        "attempts": 1,
        "experiment_assessments_attempted": 0,
        "max_output_tokens": 64,
    }
    try:
        with (opener or build_opener(_NoRedirect())).open(request, timeout=90) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError("provider validation response exceeds size limit")
            data = json.loads(raw)
            if data.get("error") or data.get("status") not in {"completed", "incomplete"}:
                raise ValueError("provider validation returned a failed state")
            usage = data.get("usage")
            if not isinstance(usage, dict) or not isinstance(data.get("model"), str):
                raise ValueError("provider response lacks model or usage")
            incoming, outgoing = usage.get("input_tokens"), usage.get("output_tokens")
            if not isinstance(incoming, int) or not isinstance(outgoing, int):
                raise ValueError("provider response lacks token quantities")
            result |= {
                "status": "CONNECTIVITY_SUCCEEDED",
                "http_status": response.status,
                "provider_response_status": sanitized(data.get("status"), secret),
                "actual_model": sanitized(data["model"], secret),
                "response_id": sanitized(data.get("id"), secret),
                "service_tier": sanitized(data.get("service_tier"), secret),
                "input_tokens": incoming,
                "output_tokens": outgoing,
                "total_tokens": usage.get("total_tokens"),
                "estimated_usage_cost_usd": str(pricing.charge(incoming, outgoing)),
                "provider_reported_cost_usd": None,
            }
    except HTTPError as error:
        try:
            body = json.loads(error.read(262144)).get("error", {})
        except (ValueError, AttributeError):
            body = {}
        result |= {
            "status": "CONNECTIVITY_FAILED_STOP",
            "http_status": error.code,
            "provider_error_type": sanitized(body.get("type"), secret),
            "provider_error_code": sanitized(body.get("code"), secret),
            "provider_error_param": sanitized(body.get("param"), secret),
            "provider_error_message": sanitized(body.get("message"), secret),
            "provider_usage": None,
            "estimated_usage_cost_usd": None,
        }
    except (URLError, TimeoutError, ValueError, TypeError, AttributeError) as error:
        result |= {
            "status": "CONNECTIVITY_FAILED_STOP",
            "local_error_type": type(error).__name__,
            "provider_usage": None,
            "estimated_usage_cost_usd": None,
        }
    result["latency_seconds"] = time.monotonic() - started
    return result


def main():
    destination = Path("experiments/ai/connectivity-v1")
    destination.mkdir(parents=True, exist_ok=True)
    ledger = destination / "attempt.json"
    write_new(
        ledger,
        {
            "status": "STARTED; NEVER_AUTOMATICALLY_REPEAT",
            "started_at_utc": datetime.now(UTC).isoformat(),
            "attempts": 1,
        },
    )
    settings = AIProviderSettings(_env_file=Path(".env.ai.local"))
    pricing = PricingAssumption.model_validate_json(
        Path(
            "experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json"
        ).read_text()
    )
    result = validate(settings, pricing)
    result |= {
        "experiment_fingerprint": (
            "92c4c909e5953d9e0ba07f00126eae75bf8225b128d1eb989a0df02d4c722a04"
        ),
        "context_manifest_fingerprint": (
            "f9502ddecd8db147c419edd28f3227fb6174a0c8522f59c1b22eb38982e53afe"
        ),
        "pricing_fingerprint": pricing.fingerprint,
    }
    write_new(destination / "provider-validation-v1.json", result | {"fingerprint": digest(result)})
    print(canonical(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("validation driver stopped; exception details suppressed") from None
