"""Injected transport, blind scoped IO and resumable exactly-once assessment ledger."""

import contextvars
import fcntl
import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_positive_experiment import (
    PositiveAssessment,
    PositiveProtocol,
    RequestRecord,
    ordered_product,
)
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.core.model.base import DomainModel
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_positive_offline import (
    audit_metadata,
    capability_path,
    verify_execution_bundle,
)
from archguard.infrastructure.semantic_preflight import wire_payload


class ExecutionBindings(DomainModel):
    execution_freeze_fingerprint: str
    protocol_fingerprint: str
    context_manifest_fingerprint: str
    request_manifest_fingerprint: str
    truth_fingerprint: str


class PaidApproval(DomainModel):
    paid_execution_approved: bool = False
    bindings: ExecutionBindings
    spend_cap_usd: str = "5.00"
    truth_lineage_verified_externally: bool = False


class TransportOutcome(DomainModel):
    status: Literal[
        "OK",
        "TIMEOUT",
        "CONNECTION",
        "RATE_LIMIT",
        "TRANSIENT",
        "CONFIGURATION_ERROR",
        "TERMINAL_ERROR",
    ]
    raw_response: bytes = Field(repr=False)
    assessment_json: str | None = Field(default=None, repr=False)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    provider_usage: dict[str, Any] | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    error_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_seconds: float = Field(ge=0, allow_inf_nan=False)


_SCOPE: contextvars.ContextVar[tuple[Path, ...]] = contextvars.ContextVar(
    "p016_execution_io", default=()
)
_HOOK_INSTALLED = False


def _io_audit(event: str, args: tuple[Any, ...]) -> None:
    roots = _SCOPE.get()
    if event != "open" or not roots or isinstance(args[0], int):
        return
    path = Path(args[0]).resolve()
    if any(path.is_relative_to(root) for root in roots):
        return
    # Runtime imports/certificates are allowed; external experiment data is not.
    if path.suffix in {".py", ".pyc", ".so", ".pem", ".crt"} and not any(
        part in {"private", "experiments"} or part.startswith(".env") for part in path.parts
    ):
        return
    raise PermissionError("blind executor denied data outside execution capabilities")


@contextmanager
def blind_io(*roots: Path) -> Iterator[None]:
    global _HOOK_INSTALLED
    if not _HOOK_INSTALLED:
        sys.addaudithook(_io_audit)
        _HOOK_INSTALLED = True
    token = _SCOPE.set(tuple(root.resolve() for root in roots))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("duplicate response JSON keys")
    return dict(pairs)


def load_execution(
    root: Path, bindings: ExecutionBindings
) -> tuple[PositiveProtocol, tuple[RequestRecord, ...]]:
    verify_execution_bundle(root, bindings.execution_freeze_fingerprint)
    protocol = PositiveProtocol.model_validate_json((root / "protocol.json").read_bytes())
    contexts = json.loads((root / "context-manifest.json").read_bytes())
    requests = json.loads((root / "request-manifest.json").read_bytes())
    if (
        protocol.fingerprint,
        protocol.truth_fingerprint,
        contexts["fingerprint"],
        requests["fingerprint"],
    ) != (
        bindings.protocol_fingerprint,
        bindings.truth_fingerprint,
        bindings.context_manifest_fingerprint,
        bindings.request_manifest_fingerprint,
    ):
        raise ValueError("frozen execution bindings drift")
    rows = tuple(RequestRecord.model_validate(row) for row in contexts["requests"])
    if (
        len(rows) != 300
        or len({r.request_id for r in rows}) != 300
        or tuple((r.execution_case_id, r.strategy) for r in rows)
        != ordered_product(tuple(sorted({r.execution_case_id for r in rows})))
    ):
        raise ValueError("frozen300 logical request product drift")
    if (
        contexts["execution_order"] != [r.request_id for r in rows]
        or [r["request_id"] for r in requests["requests"]] != contexts["execution_order"]
    ):
        raise ValueError("frozen request order drift")
    return protocol, rows


def validated_assessment(text: str, request: StructuredLLMRequest) -> dict[str, Any]:
    data = json.loads(text, object_pairs_hook=unique_object)
    result = PositiveAssessment.model_validate_json(canonical(data), strict=True)
    return _grounded(result, request)


def _grounded(result: PositiveAssessment, request: StructuredLLMRequest) -> dict[str, Any]:
    context = cast(dict[str, Any], request.untrusted_context)
    fragments = context["source_fragments"]
    refs = {f["reference"]["evidence_id"] for f in fragments} | {
        e["evidence_id"] for e in context["evidence"]
    }
    if (
        result.request_id != request.task["request_id"]
        or result.candidate_rule_id != request.task["candidate_rule_id"]
        or request.task["subject_node_id"] not in result.subject_node_ids
        or not set(result.subject_node_ids) <= set(context["selected_node_ids"])
        or not set(result.evidence_refs) <= refs
        or len(set(result.subject_node_ids)) != len(result.subject_node_ids)
        or len(set(result.evidence_refs)) != len(result.evidence_refs)
        or (result.judgment == "SUPPORTED" and not result.evidence_refs)
    ):
        raise ValueError("response request/rule/subject/evidence binding invalid")
    prose = " ".join((result.short_reason, *result.limitations))
    if re.search(r"[`{}]|\b(?:line|lines|строк[аеуи]?)\s*[:#]?\s*\d", prose, re.I) or any(
        f["reference"]["relative_path"] in prose for f in fragments
    ):
        raise ValueError("source quotations/location claims forbidden")
    return result.model_dump(mode="json")


def _artifact(root: Path, row: RequestRecord, protocol: PositiveProtocol) -> StructuredLLMRequest:
    raw = json.loads(capability_path(root, "requests/" + row.request_id + ".json").read_bytes())
    audit_metadata(raw)
    request = StructuredLLMRequest.model_validate(raw["structured_request"])
    if (
        digest(request) != row.request_fingerprint
        or digest(request.untrusted_context) != row.context_fingerprint
        or raw["provider_payload"] != wire_payload(request, protocol.model)
        or request.max_output_tokens != 2000
        or request.timeout_seconds != 90
    ):
        raise ValueError("request payload/context drift")
    return request


def execute_future(
    root: Path,
    ledger: Path,
    bindings: ExecutionBindings,
    approval: PaidApproval,
    *,
    credential_available: bool,
    transport: Callable[[StructuredLLMRequest, PositiveProtocol], TransportOutcome],
    pricing: PricingAssumption,
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not approval.paid_execution_approved:
        raise PermissionError("WAITING_FOR_PAID_AI_EXECUTION_APPROVAL")
    if (
        approval.bindings != bindings
        or not approval.truth_lineage_verified_externally
        or not credential_available
    ):
        raise PermissionError("paid runtime approval/credential/external lineage missing")
    cap = Decimal(approval.spend_cap_usd)
    if not cap.is_finite() or cap <= 0 or cap > Decimal("5.00"):
        raise ValueError("configured spend cap must be finite, positive and <= frozen5USD")
    if (
        root.is_symlink()
        or ledger.is_symlink()
        or root.resolve() == ledger.resolve()
        or root.resolve().is_relative_to(ledger.resolve())
        or ledger.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError("isolated execution and ledger capabilities required")
    if any("final-human-ground-truth" in p.name for p in root.rglob("*")):
        raise ValueError("truth path visible inside execution capability")
    protocol, rows = load_execution(root, bindings)
    if (ledger / "assessment-freeze.json").exists():
        raise ValueError("assessment ledger already immutable")
    if ledger.exists() and (
        any(p.is_symlink() for p in ledger.rglob("*"))
        or not {p.name for p in ledger.iterdir()}
        <= {
            ".execution.lock",
            "run-metadata.json",
            "attempts",
            "results",
            "pending",
            "raw",
            "normalized-assessments.json",
            "attempt-usage-ledger.json",
            "raw-ledger.json",
            "execution-lineage.json",
            "transport-errors",
        }
    ):
        raise ValueError("unexpected data inside blind ledger capability")
    ledger.mkdir(parents=True, exist_ok=True, mode=0o700)
    metadata = {
        "schema_version": "p016-live-run-v1",
        "bindings": bindings.model_dump(),
        "provider": protocol.provider,
        "model": protocol.model,
        "pricing_assumption_fingerprint": pricing.fingerprint,
        "approval_fingerprint": digest(approval),
        "hard_spend_cap_usd": approval.spend_cap_usd,
    }
    with blind_io(root, ledger), (ledger / ".execution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (ledger / "run-metadata.json").exists():
            if (ledger / "run-metadata.json").read_bytes() != (canonical(metadata) + "\n").encode():
                raise ValueError("resume settings drift")
        else:
            write_new(ledger / "run-metadata.json", metadata)
        attempts_dir = ledger / "attempts"
        results_dir = ledger / "results"
        attempts_dir.mkdir(exist_ok=True, mode=0o700)
        results_dir.mkdir(exist_ok=True, mode=0o700)
        pending_dir = ledger / "pending"
        pending_dir.mkdir(exist_ok=True, mode=0o700)
        for pending in pending_dir.iterdir():
            event_path = attempts_dir / pending.name
            if not event_path.is_file():
                raise PermissionError("unresolved transport outcome; automatic repeat forbidden")
            event = json.loads(event_path.read_bytes())
            if (
                hashlib.sha256(
                    capability_path(ledger, event["raw_response_path"]).read_bytes()
                ).hexdigest()
                != event["raw_response_sha256"]
            ):
                raise ValueError("completed pending attempt raw response changed")
            pending.unlink()
        attempts = [json.loads(path.read_bytes()) for path in sorted(attempts_dir.glob("*.json"))]
        if {p.name for p in attempts_dir.iterdir()} != {
            f"{a['request_id']}-{a['attempt']}.json" for a in attempts
        }:
            raise ValueError("resume attempt inventory drift")
        if any(a["status"] in {"CONFIGURATION_ERROR", "TOKEN_LIMIT_DEVIATION"} for a in attempts):
            raise PermissionError(
                "previous configuration failure requires explicit new run authorization"
            )
        known_ids = {r.request_id for r in rows}
        if any(a["request_id"] not in known_ids for a in attempts) or any(
            p.stem not in known_ids for p in results_dir.iterdir()
        ):
            raise ValueError("resume ledger contains unknown requests")
        for row in rows:
            previous = sorted(
                (a for a in attempts if a["request_id"] == row.request_id),
                key=lambda a: a["attempt"],
            )
            for n, event in enumerate(previous, 1):
                if (
                    event["attempt"] != n
                    or n > 3
                    or event["request_fingerprint"] != row.request_fingerprint
                    or event["context_fingerprint"] != row.context_fingerprint
                    or event["provider"] != protocol.provider
                    or event["model"] != protocol.model
                    or hashlib.sha256(
                        capability_path(ledger, event["raw_response_path"]).read_bytes()
                    ).hexdigest()
                    != event["raw_response_sha256"]
                ):
                    raise ValueError("resume immutable attempt binding drift")
                prior_cost = (
                    pricing.charge(event["input_tokens"], event["output_tokens"])
                    if event["input_tokens"] is not None and event["output_tokens"] is not None
                    else pricing.charge(protocol.max_input_tokens, protocol.max_output_tokens)
                )
                if Decimal(event["reserved_cost_usd"]) != prior_cost or (
                    n > 1
                    and previous[n - 2]["status"]
                    not in {"TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"}
                ):
                    raise ValueError("resume accounting/retry drift")
            result_path = results_dir / (row.request_id + ".json")
            if result_path.exists():
                result = json.loads(result_path.read_bytes())
                if (
                    not previous
                    or result["request_id"] != row.request_id
                    or result["execution_case_id"] != row.execution_case_id
                    or result["strategy"] != row.strategy
                    or result["attempts"] != len(previous)
                    or result["assessment"] != previous[-1]["assessment"]
                    or result["status"]
                    != (
                        "ACCEPTED" if previous[-1]["assessment"] is not None else "TERMINAL_FAILURE"
                    )
                ):
                    raise ValueError("resume logical result drift")
                if result["status"] == "ACCEPTED":
                    _grounded(
                        PositiveAssessment.model_validate_json(canonical(result["assessment"])),
                        _artifact(root, row, protocol),
                    )
        reserved_spend = sum((Decimal(a["reserved_cost_usd"]) for a in attempts), Decimal(0))
        for row in rows:
            result_path = results_dir / (row.request_id + ".json")
            if result_path.exists():
                continue
            request = _artifact(root, row, protocol)
            previous = [a for a in attempts if a["request_id"] == row.request_id]
            outcome_data: dict[str, Any] | None = None
            # Recover a completed accepted response after interruption before result publication.
            if previous and previous[-1].get("assessment") is not None:
                outcome_data = previous[-1]["assessment"]
            technical = {"TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"}
            while (
                outcome_data is None
                and len(previous) < 3
                and (not previous or previous[-1]["status"] in technical)
            ):
                bound = pricing.charge(protocol.max_input_tokens, protocol.max_output_tokens)
                if reserved_spend + bound > cap:
                    return {
                        "status": "SPEND_CAP_STOP",
                        "completed_logical": len(list(results_dir.glob("*.json"))),
                        "remaining_logical": 300 - len(list(results_dir.glob("*.json"))),
                        "reserved_spend_usd": str(reserved_spend),
                    }
                pending = pending_dir / f"{row.request_id}-{len(previous) + 1}.json"
                started_at = datetime.now(UTC).isoformat()
                write_new(
                    pending,
                    {
                        "request_id": row.request_id,
                        "attempt": len(previous) + 1,
                        "request_fingerprint": row.request_fingerprint,
                        "started_at_utc": started_at,
                        "reserved_cost_usd": str(bound),
                    },
                )
                try:
                    outcome = transport(request, protocol)
                except Exception as error:
                    errors_dir = ledger / "transport-errors"
                    errors_dir.mkdir(exist_ok=True, mode=0o700)
                    write_new(
                        errors_dir / pending.name,
                        {
                            "request_id": row.request_id,
                            "attempt": len(previous) + 1,
                            "status": "PENDING_UNRESOLVED",
                            "exception_type": type(error).__name__,
                            "ended_at_utc": datetime.now(UTC).isoformat(),
                        },
                    )
                    raise RuntimeError(
                        "transport interrupted; unresolved attempt preserved"
                    ) from None
                if not isinstance(outcome, TransportOutcome):
                    raise ValueError("transport must return structured usage/error outcome")
                if re.search(
                    rb"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|Bearer\s+\S+|github_pat_[A-Za-z0-9_]{20,})",
                    outcome.raw_response,
                ):
                    raise ValueError("credential-bearing raw response rejected before persistence")
                ordinal = len(previous) + 1
                raw_name = f"raw/{row.request_id}-{ordinal}.bin"
                raw_path = ledger / raw_name
                raw_path.parent.mkdir(exist_ok=True, mode=0o700)
                with raw_path.open("xb") as raw_file:
                    raw_file.write(outcome.raw_response)
                raw_path.chmod(0o600)
                cost = None
                if outcome.input_tokens is not None and outcome.output_tokens is not None:
                    cost = pricing.charge(outcome.input_tokens, outcome.output_tokens)
                reserved = cost if cost is not None else bound
                if (outcome.input_tokens is not None and outcome.input_tokens > 32768) or (
                    outcome.output_tokens is not None and outcome.output_tokens > 2000
                ):
                    status = "TOKEN_LIMIT_DEVIATION"
                else:
                    status = outcome.status
                assessment = None
                if status == "OK":
                    try:
                        data = json.loads(
                            outcome.assessment_json or "", object_pairs_hook=unique_object
                        )
                        assessment = _grounded(
                            PositiveAssessment.model_validate_json(canonical(data), strict=True),
                            request,
                        )
                    except ValueError:
                        status = "TERMINAL_INVALID"
                event = {
                    "request_id": row.request_id,
                    "attempt": ordinal,
                    "request_fingerprint": row.request_fingerprint,
                    "context_fingerprint": row.context_fingerprint,
                    "provider": protocol.provider,
                    "model": protocol.model,
                    "started_at_utc": started_at,
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
                    "retry_classification": status if status in technical else "NOT_RETRYABLE",
                    "latency_seconds": outcome.latency_seconds,
                    "cost_usd": str(cost) if cost is not None else None,
                    "reserved_cost_usd": str(reserved),
                }
                write_new(attempts_dir / f"{row.request_id}-{ordinal}.json", event)
                pending.unlink()
                previous.append(event)
                attempts.append(event)
                reserved_spend += reserved
                if status in {"CONFIGURATION_ERROR", "TOKEN_LIMIT_DEVIATION"}:
                    raise PermissionError(
                        "provider configuration/usage deviation; further calls stopped"
                    )
                if assessment is not None:
                    outcome_data = assessment
            result = {
                "request_id": row.request_id,
                "execution_case_id": row.execution_case_id,
                "strategy": row.strategy,
                "provider": protocol.provider,
                "model": protocol.model,
                "status": "ACCEPTED" if outcome_data is not None else "TERMINAL_FAILURE",
                "assessment": outcome_data,
                "attempts": len(previous),
                "input_tokens": sum(a["input_tokens"] for a in previous)
                if all(a["input_tokens"] is not None for a in previous)
                else None,
                "output_tokens": sum(a["output_tokens"] for a in previous)
                if all(a["output_tokens"] is not None for a in previous)
                else None,
                "latency_seconds": sum(a["latency_seconds"] for a in previous),
                "cost_usd": str(sum((Decimal(a["cost_usd"]) for a in previous), Decimal(0)))
                if all(a["cost_usd"] is not None for a in previous)
                else None,
            }
            write_new(result_path, result)
            if checkpoint is not None:
                checkpoint(
                    {
                        "completed_logical": len(list(results_dir.glob("*.json"))),
                        "reserved_spend_usd": str(reserved_spend),
                    }
                )
        return {
            "status": "EXECUTION_COMPLETE_UNFROZEN",
            "logical_results": 300,
            "reserved_spend_usd": str(reserved_spend),
        }


def freeze_assessments(root: Path, ledger: Path, bindings: ExecutionBindings) -> dict[str, Any]:
    _, rows = load_execution(root, bindings)
    if (ledger / "assessment-freeze.json").exists() or (
        ledger / "assessment-freeze.json"
    ).is_symlink():
        raise ValueError("assessment freeze append-only")
    expected = {r.request_id for r in rows}
    if {p.stem for p in (ledger / "results").glob("*.json")} != expected:
        raise ValueError("incomplete assessment ledger cannot freeze")
    if any(p.is_symlink() for p in ledger.rglob("*")):
        raise ValueError("assessment symlinks forbidden")
    if (ledger / "pending").exists() and any((ledger / "pending").iterdir()):
        raise ValueError("unresolved provider outcome cannot freeze")
    run = json.loads((ledger / "run-metadata.json").read_bytes())
    if run["bindings"] != bindings.model_dump():
        raise ValueError("assessment run manifest mismatch")
    for row in rows:
        data = json.loads((ledger / "results" / (row.request_id + ".json")).read_bytes())
        if (
            data["request_id"] != row.request_id
            or data["execution_case_id"] != row.execution_case_id
            or data["strategy"] != row.strategy
            or not 1 <= data["attempts"] <= 3
        ):
            raise ValueError("assessment identity/retry drift")
        if data["status"] == "ACCEPTED":
            _grounded(
                PositiveAssessment.model_validate_json(canonical(data["assessment"])),
                _artifact(
                    root,
                    row,
                    PositiveProtocol.model_validate_json((root / "protocol.json").read_bytes()),
                ),
            )
        else:
            raise ValueError("complete freeze requires 300 valid accepted assessments")
        events = [
            json.loads((ledger / "attempts" / f"{row.request_id}-{n}.json").read_bytes())
            for n in range(1, data["attempts"] + 1)
        ]
        if (
            any(
                event["request_id"] != row.request_id or event["attempt"] != n
                for n, event in enumerate(events, 1)
            )
            or data["assessment"] != events[-1]["assessment"]
        ):
            raise ValueError("assessment does not match immutable provider attempt")
        if any(
            event["status"] not in {"TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"}
            for event in events[:-1]
        ) or events[-1]["status"] in {"CONFIGURATION_ERROR", "TOKEN_LIMIT_DEVIATION"}:
            raise ValueError("nontechnical retry/configuration failure cannot freeze")
    files = {
        p.relative_to(ledger).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(ledger.rglob("*"))
        if p.is_file()
    }
    for path in (ledger / "attempts").glob("*.json"):
        attempt = json.loads(path.read_bytes())
        if (
            hashlib.sha256(
                capability_path(ledger, attempt["raw_response_path"]).read_bytes()
            ).hexdigest()
            != attempt["raw_response_sha256"]
        ):
            raise ValueError("raw provider response changed")
    value = {
        "schema_version": "p016-assessment-freeze-v1",
        "bindings": bindings.model_dump(),
        "logical_results": 300,
        "complete": True,
        "files": files,
    }
    receipt = value | {"fingerprint": digest(value)}
    write_new(ledger / "assessment-freeze.json", receipt)
    return receipt


def verify_assessments(
    ledger: Path, bindings: ExecutionBindings, fingerprint: str
) -> dict[str, Any]:
    from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal

    receipt: dict[str, Any] = json.loads(
        verify_opaque_seal(ledger / "assessment-freeze.json", fingerprint)
    )
    if (
        receipt["bindings"] != bindings.model_dump()
        or receipt["logical_results"] != 300
        or receipt["complete"] is not True
        or any(p.is_symlink() for p in ledger.rglob("*"))
    ):
        raise ValueError("complete frozen assessment bindings required before truth access")
    actual = {p.relative_to(ledger).as_posix() for p in ledger.rglob("*") if p.is_file()}
    if actual != set(receipt["files"]) | {"assessment-freeze.json"}:
        raise ValueError("assessment frozen inventory changed")
    for name, sha in receipt["files"].items():
        if hashlib.sha256(capability_path(ledger, name).read_bytes()).hexdigest() != sha:
            raise ValueError("frozen assessment bytes changed")
    return receipt
