"""Isolated serial development executor. Paid authorization is external; default is OFF."""

import contextvars
import fcntl
import json
import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_positive_experiment import PositiveProtocol, token_estimate
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.benchmark.unified_hybrid import UnifiedAssessment
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure.semantic_preflight import wire_payload

_ROOTS: contextvars.ContextVar[tuple[Path, Path] | None] = contextvars.ContextVar(
    "p022_roots", default=None
)
_NETWORK: contextvars.ContextVar[bool] = contextvars.ContextVar("p022_network", default=False)
_CREDENTIAL: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "p022_credential", default=None
)
_INSTALLED = False
_GUARDED: contextvars.ContextVar[bool] = contextvars.ContextVar("p022_guarded", default=False)
_RUNTIME = tuple(
    p.resolve() for p in (Path(__file__).parents[2], Path(sys.prefix), Path(sys.base_prefix))
)
FORBIDDEN = {
    "groundtruth",
    "truth",
    "expectedlabel",
    "positive",
    "negative",
    "mutation",
    "control",
    "pairrole",
    "pairid",
    "reviewer",
    "revieweridentity",
    "adjudication",
    "correctness",
    "tp",
    "fp",
    "tn",
    "fn",
    "finalcategory",
    "category",
    "split",
    "scientificcaseid",
    "constructionintent",
    "staticpredictions",
    "graphpredictions",
    "hybridpredictions",
}
PAYLOAD_KEYS = {
    "context",
    "context_manifest",
    "execution_id",
    "fingerprint",
    "request_id",
    "wire_payload",
}


def audit_payload(value: Any, *, source: bool = False, path: tuple[str, ...] = ()) -> None:
    """Inspect serialized metadata; ordinary source/contract prose is not a label."""
    if source:
        return
    if isinstance(value, dict):
        keys = {"".join(c for c in str(k).lower() if c.isalnum()) for k in value}
        if keys & FORBIDDEN:
            raise io.ReviewBlocked("P022_PAYLOAD_METADATA_LEAK")
        for k, v in value.items():
            text_source = (
                (k == "text" and "source_fragments" in path)
                or (
                    k == "architecture_contract"
                    and path
                    and path[-1] in {"context", "untrusted_context"}
                )
                or (k == "target_question" and path and path[-1] == "task")
            )
            audit_payload(v, source=bool(text_source), path=(*path, str(k)))
    elif isinstance(value, (list, tuple)):
        for v in value:
            audit_payload(v, path=(*path, "*"))
    elif isinstance(value, str):
        if any(
            s in value.lower()
            for s in (
                "/coordinator/",
                "human-intake/",
                "construction-intent",
                "ground-truth",
                "matched-control",
                "mutation-candidate",
            )
        ):
            raise io.ReviewBlocked("P022_PAYLOAD_PRIVATE_PATH_LEAK")
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except ValueError:
                return
            audit_payload(decoded, path=path)


def audit_hook(event: str, args: tuple[Any, ...]) -> None:
    if _ROOTS.get() is None and not _GUARDED.get():
        return
    if (
        event in {"socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"}
        and not _NETWORK.get()
    ):
        raise PermissionError("P022_OFFLINE_NO_NETWORK")
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if path.name.startswith(".env"):
        if path != _CREDENTIAL.get():
            raise PermissionError("P022_NO_CREDENTIAL_ACCESS")
        return
    roots = _ROOTS.get()
    if roots is None:
        return
    bundle, ledger = roots
    writes = any(c in (args[1] or "") for c in "wax+") or bool(
        args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
    )
    if path == ledger or ledger in path.parents:
        return
    if not writes and (path == bundle or bundle in path.parents):
        return
    if (
        not writes
        and path.suffix in {".py", ".pyc", ".so"}
        and any(path.is_relative_to(p) for p in _RUNTIME)
    ):
        return
    if (
        not writes
        and path.suffix in {".pem", ".crt"}
        and path.is_relative_to(Path("/etc/ssl").resolve())
    ):
        return
    raise PermissionError("P022_EXECUTOR_POSITIVE_ALLOWLIST_DENIED")


@contextmanager
def executor_scope(bundle: Path, ledger: Path, *, live: bool = False) -> Iterator[None]:
    global _INSTALLED
    if not _INSTALLED:
        sys.addaudithook(audit_hook)
        _INSTALLED = True
    token = _ROOTS.set((bundle.resolve(), ledger.resolve()))
    network = _NETWORK.set(live)
    try:
        yield
    finally:
        _NETWORK.reset(network)
        _ROOTS.reset(token)


def protocol(base: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "provider",
        "model",
        "processing",
        "concurrency",
        "max_technical_retries",
        "max_input_tokens",
        "max_output_tokens",
        "expected_output_tokens",
        "timeout_seconds",
        "context_strategy",
        "hops",
        "max_context_chars",
    )
    return {k: base[k] for k in keep} | dict(
        version="p022-development-live-protocol-v1",
        logical_requests=180,
        max_attempts=3,
        schema_id_recovery_max=1,
        invalid_response_amendment="P022_PRELIVE_VERSIONED_AMENDMENT_TO_P020_TERMINAL_INVALID",
        recovery_payload="BYTE_IDENTICAL; NO_EXTRA_INSTRUCTIONS; SHARED_TWO_RETRY_BUDGET",
        ambiguity=(
            "RECORDED_RAW_DECODE_ONLY; NO_AUTOMATIC_REPLACEMENT; "
            "HANDLE_WITHOUT_SUPPORTED_RETRIEVER_STOP"
        ),
        semantic_retry=False,
        accepted_resume_repeat=False,
        paid_execution_approved=False,
        approved_cap_usd=None,
        request_id_echo=True,
        normalized_fields=[
            "request_id",
            "target_rule_id",
            "decision",
            "subject_node_ids",
            "short_reason",
            "evidence_refs",
            "limitations",
        ],
        usage_policy=(
            "KNOWN_PROVIDER_USAGE_ELSE_FULL_RESERVED_EXPOSURE; "
            "NO_CACHED_DISCOUNT; ESTIMATE_NOT_INVOICE"
        ),
    )


def costs(rows: list[dict[str, Any]], pricing: PricingAssumption) -> dict[str, Any]:
    tokens = sorted(r["input_estimate"] for r in rows)
    n = len(rows)
    expected = sum((pricing.charge(r["input_estimate"], 600) for r in rows), Decimal(0))
    primary = sum((pricing.charge(r["input_estimate"], 2000) for r in rows), Decimal(0))
    conservative = sum((pricing.charge(r["input_upper"], 2000) for r in rows), Decimal(0))
    ceiling = pricing.charge(32768, 2000) * n
    return dict(
        requests=n,
        input_tokens=sum(tokens),
        mean=sum(tokens) / n,
        median=(tokens[(n - 1) // 2] + tokens[n // 2]) / 2,
        p95=tokens[(95 * n + 99) // 100 - 1],
        p95_method="NEAREST_RANK",
        max=max(tokens),
        input_upper=sum(r["input_upper"] for r in rows),
        long_context=sum(t > pricing.short_context_input_cutoff for t in tokens),
        long_context_upper=sum(r["input_upper"] > pricing.short_context_input_cutoff for r in rows),
        expected_output_per_call=600,
        max_output_per_call=2000,
        expected_output=n * 600,
        primary_max_output=n * 2000,
        expected_usd=str(expected),
        conservative_usd=str(conservative),
        conservative_method="P020_UPPER_BYTES_PLUS2048_WITH_MAX_OUTPUT; NO_RETRY_FRACTION_FROZEN",
        primary_max_estimated_input_usd=str(primary),
        one_full_retry_estimated_input_usd=str(primary * 2),
        two_full_retries_estimated_input_usd=str(primary * 3),
        configured_primary_ceiling_usd=str(ceiling),
        configured_one_full_retry_usd=str(ceiling * 2),
        configured_two_full_retries_usd=str(ceiling * 3),
        recommended_cap_usd=str((ceiling * 3).quantize(Decimal("0.01"), rounding="ROUND_CEILING")),
        token_method="LOCAL_UTF8_DIV3_PLUS128; UPPER_BYTES_PLUS2048; ESTIMATE_NOT_INVOICE",
        invoice=None,
        cached_savings=False,
    )


def visible_tokens(wire: dict[str, Any]) -> tuple[int, int]:
    return token_estimate(
        wire["input"][0]["content"]
        + wire["input"][1]["content"]
        + canonical(wire["text"]["format"]["schema"])
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
    allowed_files = {f"payloads/{r['request_id']}.json" for r in rows} | {
        "manifest.json",
        "protocol.json",
        "pricing.json",
        "response-schema.json",
        "order.json",
        "source-bindings.json",
    }
    if set(frozen["files"]) != allowed_files:
        raise io.ReviewBlocked("P022_FORBIDDEN_BUNDLE_ARTIFACT")
    if (
        len(rows) != 180
        or len({r["request_id"] for r in rows}) != 180
        or len({r["execution_id"] for r in rows}) != 180
    ):
        raise io.ReviewBlocked("P022_REQUEST_SET_DRIFT")
    if [r["execution_id"] for r in rows] != sorted((r["execution_id"] for r in rows), key=digest):
        raise io.ReviewBlocked("P022_ORDER_DRIFT")
    if (
        config["logical_requests"] != 180
        or config["concurrency"] != 1
        or config["max_attempts"] != 3
        or config["max_technical_retries"] != 2
        or config["schema_id_recovery_max"] != 1
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
        raise io.ReviewBlocked("P022_PROTOCOL_DRIFT")
    if (
        io.read_seal(root / "order.json")["request_ids"] != [r["request_id"] for r in rows]
        or io.read_seal(root / "response-schema.json")["schema"]
        != UnifiedAssessment.model_json_schema()
    ):
        raise io.ReviewBlocked("P022_SCHEMA_OR_ORDER_DRIFT")
    for row in rows:
        value = io.read_seal(root / "payloads" / f"{row['request_id']}.json")
        wire = value["wire_payload"]
        if (
            set(value) != PAYLOAD_KEYS
            or digest(wire) != row["request_fingerprint"]
            or digest(value["context"]) != row["context_fingerprint"]
        ):
            raise io.ReviewBlocked("P022_PAYLOAD_DRIFT")
        if (
            value["request_id"] != row["request_id"]
            or value["execution_id"] != row["execution_id"]
            or row["target_rule_id"].startswith("ARCH2")
            or wire["model"] != config["model"]
            or wire["max_output_tokens"] != config["max_output_tokens"]
            or wire["text"]["format"]["schema"] != UnifiedAssessment.model_json_schema()
            or row["input_upper"] > config["max_input_tokens"]
        ):
            raise io.ReviewBlocked("P022_STREAM_ISOLATION_DRIFT")
        audit_payload(value)
        if visible_tokens(wire) != (row["input_estimate"], row["input_upper"]):
            raise io.ReviewBlocked("P022_TOKEN_DRIFT")
    return manifest, config, pricing


@dataclass(frozen=True)
class Outcome:
    status: str
    raw: bytes = field(repr=False)
    assessment: str | None = field(default=None, repr=False)
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    latency: float = 0


Transport = Callable[[dict[str, Any], Callable[[bytes, dict[str, Any]], None]], Outcome]
Decoder = Callable[[bytes, dict[str, Any]], Outcome]


def approval_check(approval: dict[str, Any], bundle_fp: str) -> Decimal:
    if set(approval) != {
        "stage",
        "logical_requests",
        "bundle_fingerprint",
        "provider",
        "model",
        "paid_execution_approved",
        "hard_cap_usd",
        "final_calls_authorized",
        "hybrid_training_authorized",
    }:
        raise PermissionError("P022_EXPLICIT_APPROVAL_REQUIRED")
    if (
        approval["stage"] != "DEVELOPMENT_STRUCTURAL_LLM"
        or approval["logical_requests"] != 180
        or approval["bundle_fingerprint"] != bundle_fp
        or approval["provider"] != "openai"
        or approval["model"] != "gpt-6-luna"
        or approval["paid_execution_approved"] is not True
        or approval["final_calls_authorized"] is not False
        or approval["hybrid_training_authorized"] is not False
    ):
        raise PermissionError("P022_EXPLICIT_APPROVAL_REQUIRED")
    try:
        cap = Decimal(str(approval["hard_cap_usd"]))
    except ArithmeticError:
        raise PermissionError("P022_NUMERIC_APPROVED_CAP_REQUIRED") from None
    if not cap.is_finite() or cap <= 0:
        raise PermissionError("P022_NUMERIC_APPROVED_CAP_REQUIRED")
    return cap


def prepare_ledger(root: Path, bundle_fp: str) -> None:
    if root.exists():
        header = io.read_seal(root / "ledger-header.json")
        if header["bundle_fingerprint"] != bundle_fp:
            raise io.ReviewBlocked("P022_LEDGER_BINDING_DRIFT")
        return
    root.mkdir(parents=True, mode=0o700)
    io.append_seal(
        root / "ledger-header.json",
        dict(
            version="p022-live-ledger-v1",
            bundle_fingerprint=bundle_fp,
            logical_requests=180,
            paid_execution_approved=False,
        ),
    )


def ledger_state(
    root: Path, manifest: dict[str, Any], config: dict[str, Any], pricing: PricingAssumption
) -> dict[str, Any]:
    expected = {r["request_id"]: r for r in manifest["rows"]}
    accepted = {}
    attempts: dict[str, list[dict[str, Any]]] = {k: [] for k in expected}
    total = Decimal(0)
    invocations = 0
    ambiguous = []
    raw_reports = []
    paths = sorted(root.glob("attempt-*-[0-9][0-9].json"))
    allowed = {"ledger-header.json", "approval.json", "run.lock", "normalized-assessments.json"}
    for path in paths:
        record = io.read_seal(path)
        rid = record["request_id"]
        number = record["attempt"]
        if (
            rid not in expected
            or record["request_fingerprint"] != expected[rid]["request_fingerprint"]
            or record["execution_id"] != expected[rid]["execution_id"]
            or record["prefix"] != path.stem
            or path.stem != f"attempt-{rid}-{number:02}"
            or any(record[k] != config[k] for k in ("provider", "model", "processing"))
        ):
            raise io.ReviewBlocked("P022_LEDGER_REQUEST_DRIFT")
        if number != len(attempts[rid]) + 1 or number > config["max_attempts"]:
            raise io.ReviewBlocked("P022_LEDGER_ATTEMPT_DRIFT")
        if record["recovery_of"] != (attempts[rid][-1]["fingerprint"] if attempts[rid] else None):
            raise io.ReviewBlocked("P022_LEDGER_RECOVERY_DRIFT")
        if rid in accepted:
            raise io.ReviewBlocked("P022_ATTEMPT_AFTER_ACCEPTED")
        if Decimal(record["reserved_usd"]) != pricing.charge(
            config["max_input_tokens"], config["max_output_tokens"]
        ):
            raise io.ReviewBlocked("P022_RESERVATION_DRIFT")
        attempts[rid].append(record)
        invocations += 1
        allowed.add(path.name)
        prefix = path.stem
        capture = root / f"{prefix}.raw"
        capture_meta = root / f"{prefix}.capture.json"
        outpath = root / f"{prefix}.outcome.json"
        for p in (capture, capture_meta, outpath):
            if p.exists():
                allowed.add(p.name)
        exposure = Decimal(record["reserved_usd"])
        if capture_meta.exists() and (
            not capture.exists() or io.read_seal(capture_meta)["raw_sha256"] != io.sha(capture)
        ):
            raise io.ReviewBlocked("P022_CAPTURE_BINDING_DRIFT")
        if outpath.exists():
            result = io.read_seal(outpath)
            if result["attempt_fingerprint"] != record["fingerprint"]:
                raise io.ReviewBlocked("P022_LEDGER_BINDING_DRIFT")
            if not capture.exists() or io.sha(capture) != result["raw_response_sha256"]:
                raise io.ReviewBlocked("P022_RAW_DRIFT")
            if result["known_cost_usd"] is not None:
                if result["known_cost_usd"] != str(
                    pricing.charge(result["input_tokens"], result["output_tokens"])
                ):
                    raise io.ReviewBlocked("P022_COST_ACCOUNTING_DRIFT")
                exposure = Decimal(result["known_cost_usd"])
            raw_reports.append(result)
            if result["state"] == "ACCEPTED":
                if rid in accepted:
                    raise io.ReviewBlocked("P022_DUPLICATE_ACCEPTED")
                assessment = result["normalized"]
                if (
                    assessment["attempt_fingerprint"] != record["fingerprint"]
                    or assessment["response_fingerprint"] != result["response_fingerprint"]
                    or assessment["raw_response_sha256"] != result["raw_response_sha256"]
                    or assessment["usage"] != result["provider_usage"]
                ):
                    raise io.ReviewBlocked("P022_ACCEPTED_BINDING_DRIFT")
                parsed = UnifiedAssessment.model_validate(assessment["assessment"])
                if (
                    parsed.request_id != rid
                    or parsed.target_rule_id != expected[rid]["target_rule_id"]
                    or digest(parsed) != result["response_fingerprint"]
                ):
                    raise io.ReviewBlocked("P022_ACCEPTED_ID_OR_SCHEMA_DRIFT")
                accepted[rid] = assessment
            if result["state"] == "AMBIGUOUS_TRANSPORT":
                ambiguous.append(rid)
        else:
            ambiguous.append(rid)
        total += exposure
    if any(p.is_symlink() or not p.is_file() or p.name not in allowed for p in root.iterdir()):
        raise io.ReviewBlocked("P022_UNEXPECTED_LEDGER_ARTIFACT")
    return dict(
        accepted=accepted,
        attempts=attempts,
        exposure=total,
        provider_invocations=invocations,
        ambiguous=ambiguous,
        results=raw_reports,
    )


def store_outcome(
    root: Path,
    intent: dict[str, Any],
    row: dict[str, Any],
    outcome: Outcome,
    pricing: PricingAssumption,
    config: dict[str, Any],
) -> str:
    prefix = intent["prefix"]
    raw_path = root / f"{prefix}.raw"
    if not raw_path.exists():
        with raw_path.open("xb") as stream:
            stream.write(outcome.raw)
        raw_path.chmod(0o600)
    if raw_path.read_bytes() != outcome.raw:
        raise io.ReviewBlocked("P022_RAW_CAPTURE_DRIFT")
    state = (
        "TECHNICAL_FAILED"
        if outcome.status in {"TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"}
        else "TERMINAL_ERROR"
    )
    assessment = None
    if outcome.status == "OK":
        try:
            assessment = UnifiedAssessment.model_validate(
                io._json((outcome.assessment or "").encode())
            )
            state = (
                "ACCEPTED"
                if (
                    assessment.request_id == row["request_id"]
                    and assessment.target_rule_id == row["target_rule_id"]
                )
                else "REQUEST_ID_MISMATCH"
            )
        except ValueError:
            state = "SCHEMA_INVALID"
    elif outcome.status in {"AMBIGUOUS_TRANSPORT", "CONFIGURATION_ERROR", "TERMINAL_ERROR"}:
        state = outcome.status
    known = None
    if outcome.input_tokens is not None and outcome.output_tokens is not None:
        known = str(pricing.charge(outcome.input_tokens, outcome.output_tokens))
        if (
            outcome.input_tokens > config["max_input_tokens"]
            or outcome.output_tokens > config["max_output_tokens"]
        ):
            state = "USAGE_LIMIT_DEVIATION"
    elif state == "ACCEPTED":
        state = "PROVIDER_USAGE_UNAVAILABLE"
    normalized = None
    if state == "ACCEPTED" and assessment is not None:
        normalized = dict(
            assessment=assessment.model_dump(mode="json"),
            response_fingerprint=digest(assessment),
            attempt_fingerprint=intent["fingerprint"],
            raw_response_sha256=io.sha(raw_path),
            usage=outcome.provider_usage,
            request_id_echo=True,
        )
    io.append_seal(
        root / f"{prefix}.outcome.json",
        dict(
            state=state,
            normalized=normalized,
            transport_state=outcome.status,
            attempt_fingerprint=intent["fingerprint"],
            raw_response_sha256=io.sha(raw_path),
            response_fingerprint=digest(assessment) if assessment else None,
            request_id_echo=assessment is not None and assessment.request_id == row["request_id"],
            target_rule_binding=assessment is not None
            and assessment.target_rule_id == row["target_rule_id"],
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            provider_usage=outcome.provider_usage,
            transport_metadata=outcome.metadata,
            latency_seconds=outcome.latency,
            known_cost_usd=known,
        ),
    )
    return state


def execute(
    root: Path,
    ledger: Path,
    approval: dict[str, Any],
    transport: Transport,
    decoder: Decoder | None = None,
) -> dict[str, Any]:
    frozen = io.read_seal(root / "bundle-freeze.json")
    cap = approval_check(approval, frozen["fingerprint"])
    manifest, config, pricing = load_bundle(root)
    prepare_ledger(ledger, frozen["fingerprint"])
    approval_path = ledger / "approval.json"
    if approval_path.exists():
        if io.read_seal(approval_path) != approval | {"fingerprint": digest(approval)}:
            raise io.ReviewBlocked("P022_APPROVAL_DRIFT")
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
        if len(complete["accepted"]) != 180:
            raise io.ReviewBlocked("P022_INCOMPLETE_OUTPUT_SET")
        normalized = dict(
            version="p022-normalized-assessments-v1",
            bundle_fingerprint=frozen["fingerprint"],
            assessments=[complete["accepted"][r["request_id"]] for r in manifest["rows"]],
            logical_requests=180,
            accepted=180,
            missing=0,
            duplicates=0,
            provider_invocations=complete["provider_invocations"],
        )
        path = ledger / "normalized-assessments.json"
        if path.exists():
            if io.read_seal(path) != normalized | {"fingerprint": digest(normalized)}:
                raise io.ReviewBlocked("P022_NORMALIZED_FREEZE_DRIFT")
        else:
            io.append_seal(path, normalized)
        return operational(complete, "COMPLETE")


def operational(state: dict[str, Any], reason: str) -> dict[str, Any]:
    return dict(
        status=reason,
        logical_requests=180,
        attempted_logical=sum(bool(h) for h in state["attempts"].values()),
        accepted=len(state["accepted"]),
        missing=180 - len(state["accepted"]),
        accepted_duplicates=0,
        provider_invocations=state["provider_invocations"],
        technical_retries=sum(max(0, len(h) - 1) for h in state["attempts"].values()),
        possible_duplicate_processing=len(state["ambiguous"]),
        known_input_tokens=sum(r["input_tokens"] or 0 for r in state["results"]),
        known_output_tokens=sum(r["output_tokens"] or 0 for r in state["results"]),
        estimated_or_reserved_usd=str(state["exposure"]),
        known_usage_estimated_usd=str(
            sum(
                (
                    Decimal(r["known_cost_usd"])
                    for r in state["results"]
                    if r["known_cost_usd"] is not None
                ),
                Decimal(0),
            )
        ),
        uncertain_reserved_exposure_usd=str(
            state["exposure"]
            - sum(
                (
                    Decimal(r["known_cost_usd"])
                    for r in state["results"]
                    if r["known_cost_usd"] is not None
                ),
                Decimal(0),
            )
        ),
        invoice=None,
    )


class OpenAITransport:
    """Future-only wrapper around the unchanged P016 raw/usage/credential-safe adapter."""

    def __init__(self, config: dict[str, Any], settings: Any) -> None:
        from archguard.infrastructure.semantic_positive_live import OpenAIPositiveTransport

        self.adapter = OpenAIPositiveTransport(settings)
        self.protocol = cast(
            PositiveProtocol,
            SimpleNamespace(
                provider=config["provider"],
                model=config["model"],
                timeout_seconds=config["timeout_seconds"],
            ),
        )

    def decode(self, raw: bytes, metadata: dict[str, Any]) -> Outcome:
        result = self.adapter.decode_response(
            raw, metadata, self.protocol, metadata.get("latency_seconds", 0)
        )
        return Outcome(
            result.status,
            result.raw_response,
            result.assessment_json,
            result.input_tokens,
            result.output_tokens,
            result.provider_usage or {},
            result.provider_metadata | {"error": result.error_metadata},
            result.latency_seconds,
        )

    def __call__(
        self, wire: dict[str, Any], capture: Callable[[bytes, dict[str, Any]], None]
    ) -> Outcome:
        task = json.loads(wire["input"][1]["content"])
        request = StructuredLLMRequest(
            prompt_version="unified-structural-020-v1",
            schema_version="unified-assessment-020-v1",
            system_instructions=wire["input"][0]["content"],
            task=task["task"],
            untrusted_context=task["untrusted_context"],
            response_schema=wire["text"]["format"]["schema"],
            max_output_tokens=wire["max_output_tokens"],
            timeout_seconds=self.protocol.timeout_seconds,
        )
        if digest(wire_payload(request, self.protocol.model)) != digest(wire):
            raise io.ReviewBlocked("P022_TRANSPORT_PAYLOAD_DRIFT")
        result = self.adapter(request, self.protocol, capture_response=capture)
        return Outcome(
            result.status,
            result.raw_response,
            result.assessment_json,
            result.input_tokens,
            result.output_tokens,
            result.provider_usage or {},
            result.provider_metadata | {"error": result.error_metadata},
            result.latency_seconds,
        )
