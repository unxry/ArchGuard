"""Versioned blind recovery, immutable history and exactly-once assessment acceptance."""

import fcntl
import hashlib
import json
import os
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from typing import Any, Literal

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import Sealed, canonical, digest
from archguard.benchmark.semantic_positive_experiment import PositiveProtocol, RequestRecord
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.semantic_positive_execution import (
    ExecutionBindings,
    TransportOutcome,
    _artifact,
    blind_io,
    load_execution,
    validated_assessment,
    verify_assessments,
)
from archguard.infrastructure.semantic_positive_live import DECISIONS
from archguard.infrastructure.semantic_positive_offline import audit_metadata, capability_path

TECHNICAL = {"TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"}
SCHEMA = {"TERMINAL_INVALID", "TERMINAL_ERROR"}
Capture = Callable[[bytes, dict[str, Any]], None]
Transport = Callable[[StructuredLLMRequest, PositiveProtocol, Capture], TransportOutcome]
Decoder = Callable[[bytes, dict[str, Any], PositiveProtocol], TransportOutcome]


class RecoveryAmendment(Sealed):
    schema_version: Literal["p016-live-recovery-amendment-v1"] = "p016-live-recovery-amendment-v1"
    bindings: ExecutionBindings
    initial_ledger_fingerprint: str
    initial_public_verification_fingerprint: str
    pricing_fingerprint: str
    provider: Literal["openai"] = "openai"
    model: Literal["gpt-6-luna"] = "gpt-6-luna"
    processing: Literal["STANDARD"] = "STANDARD"
    logical_requests: Literal[300] = 300
    max_attempts_per_request: Literal[3] = 3
    max_schema_recovery_invocations: Literal[1] = 1
    max_ambiguous_replacements: Literal[1] = 1
    spend_cap_usd: Literal["4.50"] = "4.50"
    introduced_after_operational_interruption: Literal[True] = True
    introduced_before_truth_join_and_new_calls: Literal[True] = True
    scientific_payload_policy: Literal["BYTE_IDENTICAL_FROZEN_REQUESTS; NO_SETTINGS_CHANGE"] = (
        "BYTE_IDENTICAL_FROZEN_REQUESTS; NO_SETTINGS_CHANGE"
    )
    selection_policy: Literal["STRUCTURAL_VALIDITY_ONLY; NEVER_SEMANTIC_CORRECTNESS"] = (
        "STRUCTURAL_VALIDITY_ONLY; NEVER_SEMANTIC_CORRECTNESS"
    )
    recovery_order: Literal[
        "EXISTING_SCHEMA_FAILURE; EXISTING_PENDING; ORIGINAL_UNATTEMPTED_ORDER"
    ] = "EXISTING_SCHEMA_FAILURE; EXISTING_PENDING; ORIGINAL_UNATTEMPTED_ORDER"
    handle_policy: Literal["RECORDED_SAME_RESPONSE_FIRST; NO_INVENTED_HANDLE_OR_HISTORY_SEARCH"] = (
        "RECORDED_SAME_RESPONSE_FIRST; NO_INVENTED_HANDLE_OR_HISTORY_SEARCH"
    )
    ambiguity_policy: Literal[
        "ONE_BLIND_REPLACEMENT; ORIGINAL_PROCESSING_UNKNOWN; SECOND_AMBIGUITY_STOP"
    ] = "ONE_BLIND_REPLACEMENT; ORIGINAL_PROCESSING_UNKNOWN; SECOND_AMBIGUITY_STOP"
    invalid_policy: Literal["PRESERVE_UNUSABLE_RAW; NEVER_REMAP; SECOND_SCHEMA_FAILURE_STOP"] = (
        "PRESERVE_UNUSABLE_RAW; NEVER_REMAP; SECOND_SCHEMA_FAILURE_STOP"
    )
    initial_accepted: Literal[106] = 106
    initial_schema_failures: Literal[1] = 1
    initial_pending: Literal[1] = 1
    initial_unattempted: Literal[192] = 192
    rationale: Literal[
        "UNUSABLE_REQUEST_BINDING_AND_UNRECOVERED_TRANSPORT_PREVENT_COMPLETE_300"
    ] = "UNUSABLE_REQUEST_BINDING_AND_UNRECOVERED_TRANSPORT_PREVENT_COMPLETE_300"
    truth_joined: Literal[False] = False


def inventory(ledger: Path) -> dict[str, str]:
    if ledger.is_symlink() or any(p.is_symlink() for p in ledger.rglob("*")):
        raise ValueError("ledger symlinks forbidden")
    return {
        p.relative_to(ledger).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(ledger.rglob("*"))
        if p.is_file()
    }


def append_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


def prepare_recovery(root: Path, ledger: Path, amendment: RecoveryAmendment) -> dict[str, Any]:
    load_execution(root, amendment.bindings)
    with blind_io(root, ledger):
        files = inventory(ledger)
        if digest(files) != amendment.initial_ledger_fingerprint:
            raise ValueError("P016_LIVE_1_BLOCKED_INCOMPLETE_STATE_DRIFT")
        results = [json.loads(p.read_bytes()) for p in (ledger / "results").glob("*.json")]
        pending = list((ledger / "pending").glob("*.json"))
        if (
            sum(r["status"] == "ACCEPTED" for r in results) != 106
            or sum(r["status"] == "TERMINAL_FAILURE" for r in results) != 1
            or len(pending) != 1
        ):
            raise ValueError("P016_LIVE_1_BLOCKED_INCOMPLETE_STATE_DRIFT")
        recovery = ledger / "recovery"
        if recovery.exists():
            raise ValueError("recovery amendment append-only")
        failed = next(r for r in results if r["status"] == "TERMINAL_FAILURE")
        attempt = json.loads(
            (ledger / "attempts" / (failed["request_id"] + "-1.json")).read_bytes()
        )
        if attempt["status"] != "TERMINAL_INVALID":
            raise ValueError("original schema recovery class drift")
        recovery.mkdir(mode=0o700)
        append_json(
            recovery / "original-history.json", {"files": files, "fingerprint": digest(files)}
        )
        append_json(recovery / "amendment.json", amendment)
        plan = {
            "amendment_fingerprint": amendment.fingerprint,
            "existing_schema_request": failed["request_id"],
            "existing_pending_request": json.loads(pending[0].read_bytes())["request_id"],
        }
        append_json(recovery / "plan.json", plan)
        return plan


def history_gate(ledger: Path, amendment: RecoveryAmendment) -> dict[str, str]:
    saved = json.loads(capability_path(ledger, "recovery/original-history.json").read_bytes())
    files: dict[str, str] = saved["files"]
    if (
        saved["fingerprint"] != digest(files)
        or digest(files) != amendment.initial_ledger_fingerprint
    ):
        raise ValueError("recovery history baseline drift")
    for name, sha in files.items():
        if hashlib.sha256(capability_path(ledger, name).read_bytes()).hexdigest() != sha:
            raise ValueError("historical attempt/result/pending changed")
    stored = RecoveryAmendment.model_validate_json(
        capability_path(ledger, "recovery/amendment.json").read_bytes()
    )
    if stored != amendment:
        raise ValueError("amendment drift")
    return files


def state(
    root: Path,
    ledger: Path,
    amendment: RecoveryAmendment,
    pricing: PricingAssumption,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], Decimal]:
    _, rows = load_execution(root, amendment.bindings)
    history_gate(ledger, amendment)
    if pricing.fingerprint != amendment.pricing_fingerprint:
        raise ValueError("frozen pricing drift")
    lookup = {r.request_id: r for r in rows}
    accepted: dict[str, dict[str, Any]] = {}
    events: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((ledger / "attempts").glob("*.json")):
        event = json.loads(path.read_bytes())
        row = lookup[event["request_id"]]
        if (
            path.name != f"{row.request_id}-{event['attempt']}.json"
            or not 1 <= event["attempt"] <= 3
        ):
            raise ValueError("attempt identity/limit drift")
        if (
            event["request_fingerprint"] != row.request_fingerprint
            or event["context_fingerprint"] != row.context_fingerprint
        ):
            raise ValueError("attempt scientific binding drift")
        raw = capability_path(ledger, event["raw_response_path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != event["raw_response_sha256"]:
            raise ValueError("raw response drift")
        if event["assessment"] is not None:
            request = _artifact(
                root,
                row,
                PositiveProtocol.model_validate_json((root / "protocol.json").read_bytes()),
            )
            if validated_assessment(canonical(event["assessment"]), request) != event["assessment"]:
                raise ValueError("accepted response drift")
        if event.get("amendment_fingerprint") not in {None, amendment.fingerprint}:
            raise ValueError("attempt amendment drift")
        bound = pricing.charge(32768, 2000)
        cost = (
            pricing.charge(event["input_tokens"], event["output_tokens"])
            if event["input_tokens"] is not None and event["output_tokens"] is not None
            else bound
        )
        if Decimal(event["reserved_cost_usd"]) != cost:
            raise ValueError("attempt spend drift")
        events.setdefault(row.request_id, []).append(event)
    for directory in (ledger / "results", ledger / "recovery/results"):
        for path in directory.glob("*.json"):
            result = json.loads(path.read_bytes())
            if result["status"] != "ACCEPTED":
                continue
            row = lookup[result["request_id"]]
            if row.request_id in accepted or path.stem != row.request_id:
                raise ValueError("duplicate accepted assessment")
            matches = [e for e in events.get(row.request_id, []) if e["assessment"] is not None]
            if len(matches) != 1 or matches[0]["assessment"] != result["assessment"]:
                raise ValueError("accepted result does not match exactly one immutable attempt")
            accepted[row.request_id] = result | {"result_path": path.relative_to(ledger).as_posix()}
    # An accepted attempt survives a crash even if result publication was interrupted.
    for attempts in events.values():
        valid = [e for e in attempts if e["assessment"] is not None]
        if len(valid) > 1:
            raise ValueError("duplicate accepted provider assessments")
    intents: dict[tuple[str, int], dict[str, Any]] = {}
    for directory in (ledger / "pending", ledger / "recovery/intents"):
        for path in directory.glob("*.json"):
            intent = json.loads(path.read_bytes())
            key = (intent["request_id"], intent["attempt"])
            if (
                key in intents
                or intent["request_id"] not in lookup
                or not 1 <= intent["attempt"] <= 3
            ):
                raise ValueError("invocation intent identity drift")
            intents[key] = intent
    recorded = {(e["request_id"], e["attempt"]) for group in events.values() for e in group}
    exposure = sum(
        (Decimal(e["reserved_cost_usd"]) for group in events.values() for e in group), Decimal(0)
    )
    exposure += sum(
        (Decimal(i["reserved_cost_usd"]) for key, i in intents.items() if key not in recorded),
        Decimal(0),
    )
    return accepted, events, exposure


def _intents(ledger: Path, request_id: str) -> list[dict[str, Any]]:
    return sorted(
        (
            json.loads(p.read_bytes())
            for d in (ledger / "pending", ledger / "recovery/intents")
            for p in d.glob(request_id + "-*.json")
        ),
        key=lambda i: i["attempt"],
    )


def _store_outcome(
    root: Path,
    ledger: Path,
    row: RequestRecord,
    protocol: PositiveProtocol,
    amendment: RecoveryAmendment,
    pricing: PricingAssumption,
    intent: dict[str, Any],
    outcome: TransportOutcome,
) -> dict[str, Any]:
    ordinal = intent["attempt"]
    raw_name = f"raw/{row.request_id}-{ordinal}.bin"
    raw_path = ledger / raw_name
    if raw_path.exists():
        if raw_path.read_bytes() != outcome.raw_response:
            raise ValueError("immutable captured response changed")
    else:
        raw_path.parent.mkdir(exist_ok=True, mode=0o700)
        with raw_path.open("xb") as stream:
            stream.write(outcome.raw_response)
            stream.flush()
            os.fsync(stream.fileno())
        raw_path.chmod(0o600)
    status: str = outcome.status
    if (outcome.input_tokens is not None and outcome.input_tokens > 32768) or (
        outcome.output_tokens is not None and outcome.output_tokens > 2000
    ):
        status = "TOKEN_LIMIT_DEVIATION"
    if status == "TERMINAL_ERROR" and outcome.provider_metadata.get("http_status", 200) != 200:
        status = "PROVIDER_TERMINAL_ERROR"
    assessment = None
    if status == "OK":
        try:
            assessment = validated_assessment(
                outcome.assessment_json or "", _artifact(root, row, protocol)
            )
        except ValueError:
            status = "TERMINAL_INVALID"
    cost = (
        pricing.charge(outcome.input_tokens, outcome.output_tokens)
        if outcome.input_tokens is not None and outcome.output_tokens is not None
        else None
    )
    event = {
        "request_id": row.request_id,
        "attempt": ordinal,
        "request_fingerprint": row.request_fingerprint,
        "context_fingerprint": row.context_fingerprint,
        "provider": protocol.provider,
        "model": protocol.model,
        "started_at_utc": intent["started_at_utc"],
        "ended_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "assessment": assessment,
        "raw_response_path": raw_name,
        "raw_response_sha256": hashlib.sha256(outcome.raw_response).hexdigest(),
        "input_tokens": outcome.input_tokens,
        "output_tokens": outcome.output_tokens,
        "total_tokens": outcome.total_tokens,
        "provider_usage": outcome.provider_usage,
        "provider_metadata": outcome.provider_metadata,
        "error_metadata": outcome.error_metadata,
        "latency_seconds": outcome.latency_seconds,
        "cost_usd": str(cost) if cost is not None else None,
        "reserved_cost_usd": str(cost if cost is not None else pricing.charge(32768, 2000)),
        "amendment_fingerprint": amendment.fingerprint,
        "invocation_class": intent.get("invocation_class", "ORIGINAL_PENDING_RECOVERED"),
        "retry_classification": status if status in TECHNICAL else "NOT_TECHNICAL_RETRY",
    }
    append_json(ledger / "attempts" / f"{row.request_id}-{ordinal}.json", event)
    return event


def _publish(
    ledger: Path, row: RequestRecord, event: dict[str, Any], amendment: RecoveryAmendment
) -> None:
    attempts = [
        json.loads(p.read_bytes()) for p in (ledger / "attempts").glob(row.request_id + "-*.json")
    ]
    unknown = any(
        i["attempt"] not in {a["attempt"] for a in attempts}
        for i in _intents(ledger, row.request_id)
    )
    append_json(
        ledger / "recovery/results" / (row.request_id + ".json"),
        {
            "request_id": row.request_id,
            "execution_case_id": row.execution_case_id,
            "strategy": row.strategy,
            "provider": "openai",
            "model": "gpt-6-luna",
            "status": "ACCEPTED",
            "assessment": event["assessment"],
            "attempts": event["attempt"],
            **{
                field: sum(a[field] for a in attempts)
                if not unknown and all(a[field] is not None for a in attempts)
                else None
                for field in ("input_tokens", "output_tokens", "total_tokens")
            },
            "latency_seconds": sum(a["latency_seconds"] for a in attempts) if not unknown else None,
            "cost_usd": str(sum((Decimal(a["cost_usd"]) for a in attempts), Decimal(0)))
            if not unknown and all(a["cost_usd"] is not None for a in attempts)
            else None,
            "amendment_fingerprint": amendment.fingerprint,
        },
    )


def execute_recovery(
    root: Path,
    ledger: Path,
    amendment: RecoveryAmendment,
    pricing: PricingAssumption,
    *,
    amendment_commit: str,
    paid_approved: bool,
    credential_available: bool,
    transport: Transport,
    decode: Decoder,
    recover_handle: Callable[[str, StructuredLLMRequest, PositiveProtocol], TransportOutcome]
    | None = None,
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not paid_approved or not credential_available or len(amendment_commit) != 40:
        raise PermissionError("committed amendment and paid credential guard required")
    protocol, rows = load_execution(root, amendment.bindings)
    if (ledger / "assessment-freeze.json").exists():
        raise ValueError("AI ledger already immutable")
    with blind_io(root, ledger), (ledger / ".execution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        history_gate(ledger, amendment)
        runtime = {
            "amendment_fingerprint": amendment.fingerprint,
            "amendment_commit": amendment_commit,
            "paid_execution_approved": True,
            "hard_spend_cap_usd": "4.50",
        }
        runtime_path = ledger / "recovery/runtime.json"
        if runtime_path.exists():
            if runtime_path.read_bytes() != (canonical(runtime) + "\n").encode():
                raise ValueError("recovery runtime lineage drift")
        else:
            append_json(runtime_path, runtime)
        plan = json.loads((ledger / "recovery/plan.json").read_bytes())
        lookup = {r.request_id: r for r in rows}
        order = [lookup[plan["existing_schema_request"]], lookup[plan["existing_pending_request"]]]
        order += [r for r in rows if r.request_id not in {x.request_id for x in order}]
        for row in order:
            while True:
                accepted, events, exposure = state(root, ledger, amendment, pricing)
                if exposure > Decimal("4.50"):
                    return {"status": "P016_LIVE_1_STOPPED_SPEND_CAP"}
                if row.request_id in accepted:
                    break
                previous = sorted(events.get(row.request_id, []), key=lambda e: e["attempt"])
                if previous and previous[-1]["assessment"] is not None:
                    _publish(ledger, row, previous[-1], amendment)
                    continue
                intents = _intents(ledger, row.request_id)
                last_recorded = max((e["attempt"] for e in previous), default=0)
                unresolved = [i for i in intents if i["attempt"] > last_recorded]
                last_unresolved = unresolved[-1] if unresolved else None
                if last_unresolved is not None:
                    n = last_unresolved["attempt"]
                    capture_path = ledger / "recovery/captures" / f"{row.request_id}-{n}.json"
                    raw_path = ledger / "raw" / f"{row.request_id}-{n}.bin"
                    metadata = (
                        json.loads(capture_path.read_bytes()) if capture_path.exists() else {}
                    )
                    handle = metadata.get("provider_response_id")
                    if raw_path.exists():
                        if (
                            not metadata
                            or hashlib.sha256(raw_path.read_bytes()).hexdigest()
                            != metadata["raw_response_sha256"]
                        ):
                            return {"status": "P016_LIVE_1_INCOMPLETE_CAPTURE_INTEGRITY"}
                        outcome = decode(raw_path.read_bytes(), metadata, protocol)
                        _store_outcome(
                            root,
                            ledger,
                            row,
                            protocol,
                            amendment,
                            pricing,
                            last_unresolved,
                            outcome,
                        )
                        continue
                    if handle is not None:
                        if (
                            not isinstance(handle, str)
                            or not handle.startswith("resp_")
                            or recover_handle is None
                        ):
                            return {"status": "P016_LIVE_1_INCOMPLETE_HANDLE_RECOVERY_UNAVAILABLE"}
                        outcome = recover_handle(handle, _artifact(root, row, protocol), protocol)
                        if outcome.provider_metadata.get("response_id") != handle:
                            raise ValueError("same-response recovery handle mismatch")
                        append_json(
                            ledger / "recovery/same-response" / f"{row.request_id}-{n}.json",
                            {"provider_response_id": handle, "semantic_generation": False},
                        )
                        _store_outcome(
                            root,
                            ledger,
                            row,
                            protocol,
                            amendment,
                            pricing,
                            last_unresolved,
                            outcome,
                        )
                        continue
                    if any(
                        i.get("invocation_class") == "AMBIGUOUS_TRANSPORT_RECOVERY" for i in intents
                    ):
                        return {"status": "P016_LIVE_1_INCOMPLETE_SECOND_AMBIGUITY"}
                    invocation_class = "AMBIGUOUS_TRANSPORT_RECOVERY"
                elif previous:
                    status = previous[-1]["status"]
                    if status in SCHEMA:
                        if any(i.get("invocation_class") == "SCHEMA_RECOVERY" for i in intents):
                            return {"status": "SCHEMA_RECOVERY_EXHAUSTED"}
                        invocation_class = "SCHEMA_RECOVERY"
                    elif status in TECHNICAL:
                        invocation_class = "ORDINARY_TRANSIENT_RETRY"
                    else:
                        return {
                            "status": "P016_LIVE_1_INCOMPLETE_PROVIDER_CONFIGURATION_OR_TERMINAL"
                        }
                else:
                    invocation_class = "RESUMED_UNATTEMPTED"
                ordinal = (
                    max([e["attempt"] for e in previous] + [i["attempt"] for i in intents] + [0])
                    + 1
                )
                if ordinal > 3:
                    return {"status": "P016_LIVE_1_INCOMPLETE_ATTEMPT_LIMIT"}
                bound = pricing.charge(32768, 2000)
                if exposure + bound > Decimal("4.50"):
                    return {"status": "P016_LIVE_1_STOPPED_SPEND_CAP"}
                request = _artifact(root, row, protocol)
                lineage = {
                    "request_id": row.request_id,
                    "attempt": ordinal,
                    "invocation_class": invocation_class,
                    "parent_attempt": ordinal - 1 if ordinal > 1 else None,
                    "request_fingerprint": row.request_fingerprint,
                    "context_fingerprint": row.context_fingerprint,
                    "amendment_fingerprint": amendment.fingerprint,
                    "amendment_commit": amendment_commit,
                    "original_provider_processing": "UNKNOWN" if last_unresolved else "RECORDED",
                    "possible_duplicate_provider_processing": bool(last_unresolved),
                    "existing_recovery_handle": None,
                    "hidden_result_used_for_selection": False,
                    "started_at_utc": datetime.now(UTC).isoformat(),
                    "reserved_cost_usd": str(bound),
                }
                append_json(
                    ledger / "recovery/intents" / f"{row.request_id}-{ordinal}.json", lineage
                )

                def capture(
                    raw: bytes,
                    meta: dict[str, Any],
                    row: RequestRecord = row,
                    ordinal: int = ordinal,
                ) -> None:
                    raw_path = ledger / "raw" / f"{row.request_id}-{ordinal}.bin"
                    with raw_path.open("xb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                    raw_path.chmod(0o600)
                    try:
                        provider_id = json.loads(raw).get("id")
                    except (ValueError, AttributeError):
                        provider_id = None
                    append_json(
                        ledger / "recovery/captures" / f"{row.request_id}-{ordinal}.json",
                        meta
                        | {
                            "provider_response_id": provider_id,
                            "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
                        },
                    )

                try:
                    outcome = transport(request, protocol, capture)
                except Exception as error:
                    append_json(
                        ledger / "recovery/errors" / f"{row.request_id}-{ordinal}.json",
                        {
                            "request_id": row.request_id,
                            "attempt": ordinal,
                            "exception_type": type(error).__name__,
                            "processing": "UNKNOWN",
                            "ended_at_utc": datetime.now(UTC).isoformat(),
                        },
                    )
                    # Prefer captured-response replay before the one-replacement policy.
                    continue
                event = _store_outcome(
                    root, ledger, row, protocol, amendment, pricing, lineage, outcome
                )
                if event["assessment"] is not None:
                    _publish(ledger, row, event, amendment)
                if checkpoint is not None:
                    checkpoint(
                        {
                            "accepted": len(accepted) + int(event["assessment"] is not None),
                            "exposure_usd": str(exposure + Decimal(event["reserved_cost_usd"])),
                            "last_class": invocation_class,
                        }
                    )
        accepted, _, exposure = state(root, ledger, amendment, pricing)
        return {
            "status": "P016_RECOVERY_COMPLETE_UNFROZEN",
            "accepted": len(accepted),
            "tracked_exposure_usd": str(exposure),
        }


def recovery_report(
    root: Path, ledger: Path, amendment: RecoveryAmendment, pricing: PricingAssumption
) -> dict[str, Any]:
    _, rows = load_execution(root, amendment.bindings)
    accepted, grouped, exposure = state(root, ledger, amendment, pricing)
    events = [e for group in grouped.values() for e in group]
    intents = [
        json.loads(p.read_bytes())
        for d in (ledger / "pending", ledger / "recovery/intents")
        for p in d.glob("*.json")
    ]
    recorded = {(e["request_id"], e["attempt"]) for e in events}
    unknown = [i for i in intents if (i["request_id"], i["attempt"]) not in recorded]
    lookup = {r.request_id: r for r in rows}

    def usage(selected: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "recorded_attempts": len(selected),
            **{
                f: sum(e[f] for e in selected) if all(e[f] is not None for e in selected) else None
                for f in ("input_tokens", "output_tokens", "total_tokens")
            },
            "latency_total_seconds": sum(e["latency_seconds"] for e in selected),
            "latency_mean_seconds": mean(e["latency_seconds"] for e in selected)
            if selected
            else None,
            "latency_median_seconds": median(e["latency_seconds"] for e in selected)
            if selected
            else None,
            "estimated_cost_usd": str(
                sum((Decimal(e["reserved_cost_usd"]) for e in selected), Decimal(0))
            ),
        }

    completed_counts = Counter(
        e["request_id"]
        for e in events
        if e.get("provider_metadata", {}).get("response_status") == "completed"
    )
    by_strategy = {}
    for strategy in ("LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE"):
        chosen = [r for r in accepted.values() if r["strategy"] == strategy]
        distribution = Counter(r["assessment"]["judgment"] for r in chosen)
        by_strategy[strategy] = {
            **usage([e for e in events if lookup[e["request_id"]].strategy == strategy]),
            "accepted": len(chosen),
            "response_distribution": {d: distribution[d] for d in DECISIONS},
            "unknown_usage_invocations": sum(
                lookup[i["request_id"]].strategy == strategy for i in unknown
            ),
        }
    classes = Counter(i.get("invocation_class", "ORIGINAL_PRE_STOP") for i in intents)
    all_invocations = recorded | {(i["request_id"], i["attempt"]) for i in intents}
    maximum = max((n for _, n in all_invocations), default=0)
    return {
        "expected_logical_requests": 300,
        "valid_accepted_assessments": len(accepted),
        "provider_invocations": len(all_invocations),
        "recorded_provider_responses": len(events),
        "unattempted_logical_requests": 300 - len({k[0] for k in all_invocations}),
        "logical_requests_without_valid_assessment": 300 - len(accepted),
        "active_unresolved_pending": sum(i["request_id"] not in accepted for i in unknown),
        "historical_ambiguous_invocations": len(unknown),
        "invalid_responses": sum(e["status"] in SCHEMA for e in events),
        "transient_failures": sum(e["status"] in TECHNICAL for e in events),
        "remaining_terminal_protocol_failures": sum(
            any(e["status"] in SCHEMA for e in group)
            for k, group in grouped.items()
            if k not in accepted
        ),
        "remaining_terminal_technical_failures": sum(
            len(group) >= 3 and group[-1]["status"] in TECHNICAL
            for k, group in grouped.items()
            if k not in accepted
        ),
        "by_strategy": by_strategy,
        "known_usage": usage(events),
        "all_invocations_usage": None if unknown else usage(events),
        "by_run_phase": {
            name: usage(
                [e for e in events if e.get("invocation_class", "ORIGINAL_PRE_STOP") == name]
            )
            for name in (
                "ORIGINAL_PRE_STOP",
                "SCHEMA_RECOVERY",
                "AMBIGUOUS_TRANSPORT_RECOVERY",
                "RESUMED_UNATTEMPTED",
                "ORDINARY_TRANSIENT_RETRY",
            )
        },
        "ordinary_transient_retries": classes["ORDINARY_TRANSIENT_RETRY"],
        "schema_recovery_invocations": classes["SCHEMA_RECOVERY"],
        "ambiguous_recovery_invocations": classes["AMBIGUOUS_TRANSPORT_RECOVERY"],
        "maximum_attempts": maximum,
        "requests_reaching_three_attempts": len({k for k, n in all_invocations if n == 3}),
        "attempt_limit_violations": int(maximum > 3),
        "duplicate_accepted_assessments": 0,
        "confirmed_duplicate_provider_executions": sum(
            max(0, n - 1) for n in completed_counts.values()
        ),
        "possible_duplicate_provider_processing": sum(
            bool(i.get("possible_duplicate_provider_processing")) for i in intents
        ),
        "hidden_result_used_for_selection": False,
        "tracked_exposure_usd": str(exposure),
        "estimated_known_usage_cost_usd": str(
            sum((Decimal(e["cost_usd"]) for e in events if e["cost_usd"] is not None), Decimal(0))
        ),
        "unknown_usage_reserved_cost_usd": str(
            sum((Decimal(i["reserved_cost_usd"]) for i in unknown), Decimal(0))
        ),
        "actual_invoice_cost_usd": None,
        "hard_spend_cap_usd": "4.50",
        "cap_exceeded": exposure > Decimal("4.50"),
    }


def freeze_recovery(
    root: Path, ledger: Path, amendment: RecoveryAmendment, pricing: PricingAssumption
) -> dict[str, Any]:
    protocol, rows = load_execution(root, amendment.bindings)
    with blind_io(root, ledger):
        accepted, grouped, _ = state(root, ledger, amendment, pricing)
        report = recovery_report(root, ledger, amendment, pricing)
        if len(accepted) != 300 or report["active_unresolved_pending"] or report["cap_exceeded"]:
            raise ValueError("complete recovery freeze requires 300 valid accepted assessments")
        if (ledger / "assessment-freeze.json").exists():
            receipt = json.loads((ledger / "assessment-freeze.json").read_bytes())
            verify_assessments(ledger, amendment.bindings, receipt["fingerprint"])
            lineage = json.loads((ledger / "execution-lineage.json").read_bytes())
            return {
                **{k: v for k, v in lineage.items() if k != "fingerprint"},
                "execution_lineage_fingerprint": lineage["fingerprint"],
                "ai_freeze_receipt_fingerprint": receipt["fingerprint"],
                "operational_statistics": report,
            }
        for path in ledger.rglob("*.json"):
            audit_metadata(json.loads(path.read_bytes()))
        events = [
            e for r in rows for e in sorted(grouped[r.request_id], key=lambda e: e["attempt"])
        ]
        raw = {
            "schema_version": "p016-recovered-raw-ledger-v1",
            "raw_responses": [
                {
                    k: e[k]
                    for k in ("request_id", "attempt", "raw_response_path", "raw_response_sha256")
                }
                for e in events
            ],
        }
        normalized = {
            "schema_version": "p016-normalized-assessments-v1",
            "bindings": amendment.bindings.model_dump(),
            "assessments": [accepted[r.request_id] for r in rows],
        }
        usage = {
            "schema_version": "p016-recovered-usage-ledger-v1",
            "attempts": events,
            "historical_unknown_intents": [
                i
                for r in rows
                for i in _intents(ledger, r.request_id)
                if (i["request_id"], i["attempt"])
                not in {(e["request_id"], e["attempt"]) for e in events}
            ],
            "operational_statistics": report,
        }
        lineage = {
            "bindings": amendment.bindings.model_dump(),
            "provider": protocol.provider,
            "model": protocol.model,
            "prompt_schema_fingerprint": protocol.prompt_schema_fingerprint,
            "amendment_fingerprint": amendment.fingerprint,
            "amendment_commit": json.loads((ledger / "recovery/runtime.json").read_bytes())[
                "amendment_commit"
            ],
            "raw_ledger_fingerprint": digest(raw),
            "normalized_assessment_fingerprint": digest(normalized),
            "usage_ledger_fingerprint": digest(usage),
        }
        artifacts: dict[str, dict[str, Any]] = {
            "raw-ledger.json": raw,
            "normalized-assessments.json": normalized,
            "attempt-usage-ledger.json": usage,
            "execution-lineage.json": lineage,
        }
        for name, value in artifacts.items():
            payload = value | {"fingerprint": digest(value)}
            path = ledger / name
            if path.exists():
                if path.read_bytes() != (canonical(payload) + "\n").encode():
                    raise ValueError("freeze artifact drift")
            else:
                append_json(path, payload)
        receipt = {
            "schema_version": "p016-assessment-freeze-v1",
            "bindings": amendment.bindings.model_dump(),
            "logical_results": 300,
            "complete": True,
            "accepted_result_paths": {
                r.request_id: accepted[r.request_id]["result_path"] for r in rows
            },
            "recovery_amendment_fingerprint": amendment.fingerprint,
            "files": inventory(ledger),
        }
        receipt["fingerprint"] = digest(receipt)
        append_json(ledger / "assessment-freeze.json", receipt)
        return {
            **lineage,
            "execution_lineage_fingerprint": digest(lineage),
            "ai_freeze_receipt_fingerprint": receipt["fingerprint"],
            "operational_statistics": report,
        }
