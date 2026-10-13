"""FINAL-only acquisition: isolated requests, scoped approval, no fitting/evaluation."""

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.benchmark.unified_hybrid import RULES, UnifiedAssessment
from archguard.infrastructure import development_llm_executor as core
from archguard.infrastructure import unified_human_review as io

Outcome = core.Outcome
Transport = core.Transport
Decoder = core.Decoder
OpenAITransport = core.OpenAITransport
visible_tokens = core.visible_tokens
store_outcome = core.store_outcome
ROOT = io.PRIVATE / "p024-final-execution-v2"
LEDGER = io.PRIVATE / "p024-final-live-ledger-v1"
APPROVAL_ROOT = io.PRIVATE / "p024-final-live-approval-v1"
REGISTRY_FP = "269e4fe3cdcab8b3461e8f7b24b4eb9f49b0cf455a843b776fb5e490de53a9df"
MODEL_FP = "fb908199217bad69ff2fd41770ad6756065828a9c9837b124fe96a05d2f7101b"
REQUEST_FP = "efa1dec52b7694122e6b13779ed1b9683b771c0fc6cd4031f5c16b8671d2e507"
CONTEXT_FP = "852f827060673d7189aecf72b1d4f81d19617d7c9e171868dd3230ac568d8c22"
APPROVAL_FIELDS = {
    "stage",
    "paid_execution_approved",
    "logical_requests_authorized",
    "hard_cap_usd",
    "provider",
    "model",
    "processing_tier",
    "hybrid_retraining_authorized",
    "final_evaluation_authorized",
    "security_authorized",
    "request_manifest_fingerprint",
    "context_manifest_fingerprint",
    "protocol_fingerprint",
    "bundle_fingerprint",
    "cost_preflight_fingerprint",
    "p023_selected_registry_fingerprint",
}


def costs(rows: list[dict[str, Any]], pricing: PricingAssumption) -> dict[str, Any]:
    return core.costs(rows, pricing) | dict(
        near_context_window=sum(
            r["input_upper"] + 2000 >= int(pricing.context_window * 0.9) for r in rows
        ),
        model_context_window=pricing.context_window,
        model_max_output=pricing.max_model_output,
    )


def protocol(base: dict[str, Any]) -> dict[str, Any]:
    return core.protocol(base) | dict(
        version="p024-final-live-protocol-v1",
        scope="FINAL_300_LLM",
        logical_requests=300,
        schema_id_recovery_max=0,
        invalid_response_amendment=None,
        invalid_response_policy="TERMINAL_INVALID; NO_RETRY_WITHOUT_VERSIONED_AMENDMENT",
    )


def audit_payload(value: Any, *, source: bool = False, path: tuple[str, ...] = ()) -> None:
    source = source and isinstance(value, str)
    core.audit_payload(value, source=source, path=path)
    if source:
        return
    if isinstance(value, dict):
        forbidden = {
            "truthlabel",
            "groundtruthlabel",
            "hybridprediction",
            "selectedmodelcorrect",
            "expectedoutcome",
            "developmentlabels",
            "validationmetrics",
            "candidateranking",
            "constructionrole",
            "expecteddirection",
            "reviewerresponses",
        }
        if {"".join(c for c in str(k).lower() if c.isalnum()) for k in value} & forbidden:
            raise io.ReviewBlocked("P024_PAYLOAD_METADATA_LEAK")
        for k, v in value.items():
            prose = (
                (k == "text" and "source_fragments" in path)
                or (
                    k == "architecture_contract"
                    and path
                    and path[-1] in {"context", "untrusted_context"}
                )
                or (k == "target_question" and path and path[-1] == "task")
            )
            audit_payload(v, source=bool(prose), path=(*path, str(k)))
    elif isinstance(value, (list, tuple)):
        for item in value:
            audit_payload(item, path=(*path, "*"))
    elif isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(value)
        except ValueError:
            return
        audit_payload(parsed, path=path)


@contextmanager
def final_scope(root: Path, ledger: Path, *, live: bool = False) -> Iterator[None]:
    io._safe_path(root)
    io._safe_path(ledger)
    if (
        root.resolve() == ledger.resolve()
        or root.resolve().is_relative_to(ledger.resolve())
        or ledger.resolve().is_relative_to(root.resolve())
    ):
        raise PermissionError("P024_DISJOINT_EXECUTION_ROOTS_REQUIRED")
    with core.executor_scope(root, ledger, live=live):
        yield


def approval_bindings(root: Path) -> dict[str, Any]:
    frozen = io.read_seal(root / "bundle-freeze.json")
    config = io.read_seal(root / "protocol.json")
    manifest = io.read_seal(root / "manifest.json")
    cost = io.read_seal(root / "cost-preflight.json")
    lock = io.read_seal(root / "model-lock.json")
    audit_payload(lock)
    return dict(
        stage="FINAL_300_LLM",
        logical_requests_authorized=300,
        provider=config["provider"],
        model=config["model"],
        processing_tier=config["processing"],
        hybrid_retraining_authorized=False,
        final_evaluation_authorized=False,
        security_authorized=False,
        request_manifest_fingerprint=manifest["fingerprint"],
        context_manifest_fingerprint=manifest["context_manifest_fingerprint"],
        protocol_fingerprint=config["fingerprint"],
        bundle_fingerprint=frozen["fingerprint"],
        cost_preflight_fingerprint=cost["fingerprint"],
        p023_selected_registry_fingerprint=lock["selected_registry_fingerprint"],
    )


def approval_check(approval: dict[str, Any], root: Path) -> Decimal:
    expected = approval_bindings(root)
    if (
        set(approval) != APPROVAL_FIELDS
        or any(approval[k] != v for k, v in expected.items())
        or approval["paid_execution_approved"] is not True
    ):
        raise PermissionError("P024_EXPLICIT_FINAL_APPROVAL_REQUIRED")
    if any(
        approval[k] is not False
        for k in (
            "hybrid_retraining_authorized",
            "final_evaluation_authorized",
            "security_authorized",
        )
    ):
        raise PermissionError("P024_EXPLICIT_FINAL_APPROVAL_REQUIRED")
    try:
        if isinstance(approval["hard_cap_usd"], bool):
            raise ValueError
        cap = Decimal(str(approval["hard_cap_usd"]))
    except (ArithmeticError, ValueError):
        raise PermissionError("P024_NUMERIC_APPROVED_CAP_REQUIRED") from None
    if not cap.is_finite() or cap <= 0:
        raise PermissionError("P024_NUMERIC_APPROVED_CAP_REQUIRED")
    return cap


def prepare_ledger(root: Path, bundle_fp: str) -> None:
    header = dict(
        version="p024-final-ledger-v1",
        scope="FINAL_300_LLM",
        bundle_fingerprint=bundle_fp,
        logical_requests=300,
        paid_execution_approved=False,
    )
    if root.exists():
        if io.read_seal(root / "ledger-header.json") != header | {"fingerprint": digest(header)}:
            raise io.ReviewBlocked("P024_FINAL_LEDGER_SCOPE_DRIFT")
    else:
        io.append_seal(root / "ledger-header.json", header)


def ledger_state(
    root: Path, manifest: dict[str, Any], config: dict[str, Any], pricing: PricingAssumption
) -> dict[str, Any]:
    header = io.read_seal(root / "ledger-header.json")
    if header["logical_requests"] != 300 or header["scope"] != "FINAL_300_LLM":
        raise io.ReviewBlocked("P024_FINAL_LEDGER_SCOPE_DRIFT")
    return core.ledger_state(root, manifest, config, pricing)


def operational(state: dict[str, Any], reason: str) -> dict[str, Any]:
    return core.operational(state, reason) | dict(
        logical_requests=300, missing=300 - len(state["accepted"])
    )


def load_bundle(root: Path) -> tuple[dict[str, Any], dict[str, Any], PricingAssumption]:
    frozen = io.read_seal(root / "bundle-freeze.json")
    io.verify_files(
        root, frozen["files"] | {"bundle-freeze.json": io.sha(root / "bundle-freeze.json")}
    )
    manifest = io.read_seal(root / "manifest.json")
    config = io.read_seal(root / "protocol.json")
    pricing = PricingAssumption.model_validate_json((root / "pricing.json").read_bytes())
    rows = manifest["rows"]
    if manifest["fingerprint"] != REQUEST_FP:
        raise io.ReviewBlocked("P024_FROZEN_SOURCE_MANIFEST_DRIFT")
    if manifest.get("stream") != "FINAL" or config.get("scope") != "FINAL_300_LLM":
        raise io.ReviewBlocked("P024_FINAL_SCOPE_REQUIRED")
    lock = io.read_seal(root / "model-lock.json")
    audit_payload(lock)
    if (
        lock["selected_registry_fingerprint"] != REGISTRY_FP
        or lock["final_model_fingerprint"] != MODEL_FP
    ):
        raise io.ReviewBlocked("P024_P023_MODEL_LOCK_DRIFT")
    if (
        io.read_seal(root / "contexts.json")["fingerprint"]
        != manifest["context_manifest_fingerprint"]
        or manifest["context_manifest_fingerprint"] != CONTEXT_FP
    ):
        raise io.ReviewBlocked("P024_CONTEXT_FREEZE_DRIFT")
    allowed_files = {f"payloads/{r['request_id']}.json" for r in rows} | {
        "manifest.json",
        "protocol.json",
        "pricing.json",
        "response-schema.json",
        "order.json",
        "source-bindings.json",
        "contexts.json",
        "cost-preflight.json",
        "model-lock.json",
        "approval-contract.json",
    }
    if set(frozen["files"]) != allowed_files:
        raise io.ReviewBlocked("P024_FORBIDDEN_BUNDLE_ARTIFACT")
    if (
        len(rows) != 300
        or len({r["request_id"] for r in rows}) != 300
        or len({r["execution_id"] for r in rows}) != 300
    ):
        raise io.ReviewBlocked("P024_REQUEST_SET_DRIFT")
    if [r["execution_id"] for r in rows] != sorted((r["execution_id"] for r in rows), key=digest):
        raise io.ReviewBlocked("P024_ORDER_DRIFT")
    if (
        config["logical_requests"] != 300
        or config["concurrency"] != 1
        or config["max_attempts"] != 3
        or config["max_technical_retries"] != 2
        or config["schema_id_recovery_max"] != 0
        or config["provider"] != "openai"
        or config["model"] != "gpt-6-luna"
        or config["processing"] != "STANDARD"
        or config["max_input_tokens"] != 32768
        or config["max_output_tokens"] != 2000
        or config["expected_output_tokens"] != 600
        or config["timeout_seconds"] != 90
        or config["context_strategy"] != "GRAPH_GUIDED"
        or config["hops"] != 1
        or config["max_context_chars"] != 20000
        or config != protocol(config) | {"fingerprint": digest(protocol(config))}
        or pricing.fingerprint != digest(pricing.model_dump(mode="json", exclude={"fingerprint"}))
    ):
        raise io.ReviewBlocked("P024_PROTOCOL_DRIFT")
    if (
        io.read_seal(root / "order.json")["request_ids"] != [r["request_id"] for r in rows]
        or io.read_seal(root / "response-schema.json")["schema"]
        != UnifiedAssessment.model_json_schema()
    ):
        raise io.ReviewBlocked("P024_SCHEMA_OR_ORDER_DRIFT")
    for row in rows:
        value = io.read_seal(root / "payloads" / f"{row['request_id']}.json")
        wire = value["wire_payload"]
        if (
            set(value) != core.PAYLOAD_KEYS
            or digest(wire) != row["request_fingerprint"]
            or digest(value["context"]) != row["context_fingerprint"]
        ):
            raise io.ReviewBlocked("P024_PAYLOAD_DRIFT")
        if (
            value["request_id"] != row["request_id"]
            or value["execution_id"] != row["execution_id"]
            or row["target_rule_id"] not in RULES
            or wire["model"] != config["model"]
            or wire["max_output_tokens"] != config["max_output_tokens"]
            or wire["text"]["format"]["schema"] != UnifiedAssessment.model_json_schema()
            or row["input_upper"] > config["max_input_tokens"]
        ):
            raise io.ReviewBlocked("P024_STREAM_ISOLATION_DRIFT")
        audit_payload(value)
        if visible_tokens(wire) != (row["input_estimate"], row["input_upper"]):
            raise io.ReviewBlocked("P024_TOKEN_DRIFT")
    measured = costs(rows, pricing)
    if io.read_seal(root / "cost-preflight.json") != measured | {"fingerprint": digest(measured)}:
        raise io.ReviewBlocked("P024_COST_PREFLIGHT_DRIFT")
    return manifest, config, pricing


def execute(
    root: Path,
    ledger: Path,
    approval: dict[str, Any],
    transport: Transport,
    decoder: Decoder | None = None,
) -> dict[str, Any]:
    frozen = io.read_seal(root / "bundle-freeze.json")
    cap = approval_check(approval, root)
    manifest, config, pricing = load_bundle(root)
    prepare_ledger(ledger, frozen["fingerprint"])
    approval_path = ledger / "approval.json"
    if approval_path.exists():
        if io.read_seal(approval_path) != approval | {"fingerprint": digest(approval)}:
            raise io.ReviewBlocked("P024_APPROVAL_DRIFT")
    else:
        io.append_seal(approval_path, approval)
    with (ledger / "run.lock").open("a") as lock:
        (ledger / "run.lock").chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for row in manifest["rows"]:
            rid = row["request_id"]
            while True:
                status = ledger_state(ledger, manifest, config, pricing)
                if rid in status["accepted"]:
                    break
                history = status["attempts"][rid]
                if status["ambiguous"]:
                    # Captured same response may be decoded offline; no second generation.
                    unresolved = next(
                        (
                            h
                            for h in history
                            if not (ledger / f"{h['prefix']}.outcome.json").exists()
                        ),
                        None,
                    )
                    if (
                        unresolved
                        and decoder
                        and (ledger / f"{unresolved['prefix']}.raw").exists()
                        and (ledger / f"{unresolved['prefix']}.capture.json").exists()
                    ):
                        raw = (ledger / f"{unresolved['prefix']}.raw").read_bytes()
                        meta = io.read_seal(ledger / f"{unresolved['prefix']}.capture.json")[
                            "metadata"
                        ]
                        store_outcome(ledger, unresolved, row, decoder(raw, meta), pricing, config)
                        continue
                    return operational(status, "AMBIGUOUS_TRANSPORT")
                if history:
                    last = io.read_seal(ledger / f"{history[-1]['prefix']}.outcome.json")
                    if last["state"] in {"SCHEMA_INVALID", "REQUEST_ID_MISMATCH"}:
                        return operational(status, last["state"])
                    invalid = sum(
                        io.read_seal(ledger / f"{h['prefix']}.outcome.json")["state"]
                        in {"SCHEMA_INVALID", "REQUEST_ID_MISMATCH"}
                        for h in history
                    )
                    if last["state"] not in {
                        "TECHNICAL_FAILED",
                        "SCHEMA_INVALID",
                        "REQUEST_ID_MISMATCH",
                    }:
                        return operational(status, last["state"])
                    if (
                        invalid > config["schema_id_recovery_max"]
                        or len(history) >= config["max_attempts"]
                    ):
                        return operational(status, "RETRY_EXHAUSTED")
                reserved = pricing.charge(config["max_input_tokens"], config["max_output_tokens"])
                if status["exposure"] + reserved > cap:
                    return operational(status, "PAID_CAP_REACHED")
                number = len(history) + 1
                prefix = f"attempt-{rid}-{number:02}"
                intent = io.append_seal(
                    ledger / f"{prefix}.json",
                    dict(
                        prefix=prefix,
                        request_id=rid,
                        execution_id=row["execution_id"],
                        attempt=number,
                        request_fingerprint=row["request_fingerprint"],
                        reserved_usd=str(reserved),
                        provider=config["provider"],
                        model=config["model"],
                        processing=config["processing"],
                        timestamp=datetime.now(UTC).isoformat(),
                        recovery_of=history[-1]["fingerprint"] if history else None,
                    ),
                )

                def capture(raw: bytes, metadata: dict[str, Any], *, prefix: str = prefix) -> None:
                    with (ledger / f"{prefix}.raw").open("xb") as stream:
                        stream.write(raw)
                    (ledger / f"{prefix}.raw").chmod(0o600)
                    io.append_seal(
                        ledger / f"{prefix}.capture.json",
                        dict(metadata=metadata, raw_sha256=io.sha(ledger / f"{prefix}.raw")),
                    )

                wire = io.read_seal(root / "payloads" / f"{rid}.json")["wire_payload"]
                try:
                    outcome = transport(wire, capture)
                except Exception:
                    return operational(
                        ledger_state(ledger, manifest, config, pricing), "AMBIGUOUS_TRANSPORT"
                    )
                store_outcome(ledger, intent, row, outcome, pricing, config)
        complete = ledger_state(ledger, manifest, config, pricing)
        if len(complete["accepted"]) != 300:
            raise io.ReviewBlocked("P024_INCOMPLETE_OUTPUT_SET")
        normalized = dict(
            version="p024-normalized-assessments-v1",
            bundle_fingerprint=frozen["fingerprint"],
            assessments=[complete["accepted"][r["request_id"]] for r in manifest["rows"]],
            logical_requests=300,
            accepted=300,
            missing=0,
            duplicates=0,
            provider_invocations=complete["provider_invocations"],
        )
        path = ledger / "normalized-assessments.json"
        if path.exists():
            if io.read_seal(path) != normalized | {"fingerprint": digest(normalized)}:
                raise io.ReviewBlocked("P024_NORMALIZED_FREEZE_DRIFT")
        else:
            io.append_seal(path, normalized)
        return operational(complete, "COMPLETE")
