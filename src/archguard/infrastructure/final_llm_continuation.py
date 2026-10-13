"""Coordinator-bound FINAL suffix acquisition; immutable history and cumulative cap."""

import contextvars
import fcntl
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure import development_llm_executor as core
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import final_llm_preflight as p
from archguard.infrastructure import unified_human_review as io

PARTIAL = io.PRIVATE / "p024-final-live-freeze-v1"
PARTIAL_PUBLIC = io.BASE / "p024-live-scientific-freeze-v1.json"
PARTIAL_PUBLIC_FP = "182893c62a0723261ff833620dc5908c643f23cd49f849548d4629a521fbe191"
ROOT = io.PRIVATE / "p024-final-continuation-plan-v1"
LEDGER = io.PRIVATE / "p024-final-live-continuation-v1"
APPROVAL = io.PRIVATE / "p024-final-continuation-approval-v1"
FREEZE = io.PRIVATE / "p024-final-continuation-freeze-v1"
COMPOSITE = io.PRIVATE / "p024-final-composite-acquisition-v1"
PUBLIC = io.BASE / "p024-live1-acquisition-v1.json"
HEAD = "0c5b467264488dc6e08a54bfd0de8f4ffe3f6096"
CAP = Decimal("3.85")
SOURCES = (
    "src/archguard/infrastructure/final_llm_continuation.py",
    "scripts/prompt024_continuation.py",
    "tests/intelligence/test_final_llm_continuation.py",
)
_ALLOWED: contextvars.ContextVar[tuple[tuple[Path, ...], tuple[Path, ...]] | None] = (
    contextvars.ContextVar("p024_continuation_io", default=None)
)
_INSTALLED = False


def audit_hook(event: str, args: tuple[Any, ...]) -> None:
    active = _ALLOWED.get()
    if active is None or event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    reads, writes = active
    writing = any(c in (args[1] or "") for c in "wax+") or bool(
        args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
    )
    if path.name.startswith(".env"):
        raise PermissionError("P024_CONTINUATION_NO_CREDENTIAL_READ")
    if any(path.is_relative_to(r) for r in writes):
        return
    if not writing and any(path.is_relative_to(r) for r in reads):
        return
    if (
        not writing
        and path.suffix in {".py", ".pyc", ".so"}
        and any(path.is_relative_to(r) for r in core._RUNTIME)
    ):
        return
    if (
        not writing
        and path.suffix in {".pem", ".crt"}
        and path.is_relative_to(Path("/etc/ssl").resolve())
    ):
        return
    raise PermissionError("P024_CONTINUATION_PRIVATE_ALLOWLIST_DENIED")


@contextmanager
def scope(
    reads: tuple[Path, ...], writes: tuple[Path, ...] = (), *, live: bool = False
) -> Iterator[None]:
    global _INSTALLED
    for path in (*reads, *writes):
        io._safe_path(path)
    if not _INSTALLED:
        sys.addaudithook(audit_hook)
        _INSTALLED = True
    if not core._INSTALLED:
        sys.addaudithook(core.audit_hook)
        core._INSTALLED = True
    tokens = (
        _ALLOWED.set((tuple(r.resolve() for r in reads), tuple(r.resolve() for r in writes))),
        core._GUARDED.set(True),
        core._NETWORK.set(live),
        core._ROOTS.set(None),
    )
    try:
        yield
    finally:
        _ALLOWED.reset(tokens[0])
        core._GUARDED.reset(tokens[1])
        core._NETWORK.reset(tokens[2])
        core._ROOTS.reset(tokens[3])


def git_gate(*, initial: bool = False, closed: bool = False) -> None:
    allowed: tuple[str, ...] = () if initial else SOURCES
    if closed:
        allowed += (
            str(PUBLIC),
            "docs/verification/PROMPT_024_LIVE_1.md",
            str(io.BASE / "p024-live1-verification-v1.json"),
            str(io.BASE / "p025-acquisition-handoff-v1.json"),
        )
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    anchors = [*p.ANCHORS.values(), "d609a312bdf5ce2af67026008bf2f055c6898962", HEAD]
    for sha in anchors:
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P024_CONTINUATION_LINEAGE_DRIFT")
    if initial and subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != HEAD:
        raise io.ReviewBlocked("P024_CONTINUATION_INITIAL_HEAD_DRIFT")
    chain = [
        "1891fa553218200139f027ed9c3a82d100f61462",
        p.ANCHORS["P021.B"],
        p.ANCHORS["P022"],
        p.ANCHORS["P022.LIVE"],
        p.ANCHORS["P023"],
        "d609a312bdf5ce2af67026008bf2f055c6898962",
        HEAD,
    ]
    for a, b in zip(chain, chain[1:], strict=False):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P024_CONTINUATION_LINEAGE_ORDER_DRIFT")


def history() -> tuple[
    dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any], dict[str, Any]
]:
    public = io.read_seal(PARTIAL_PUBLIC, PARTIAL_PUBLIC_FP)
    receipt = io.read_seal(
        PARTIAL / "freeze-receipt.json", public["fingerprints"]["freeze-receipt.json"]
    )
    io.verify_files(
        PARTIAL, receipt["files"] | {"freeze-receipt.json": io.sha(PARTIAL / "freeze-receipt.json")}
    )
    io.verify_files(e.LEDGER, receipt["original_ledger_files"])
    for name, fp in receipt["fingerprints"].items():
        io.read_seal(PARTIAL / name, fp)
        if public["fingerprints"].get(name) != fp:
            raise io.ReviewBlocked("P024_CONTINUATION_PARTIAL_FREEZE_DRIFT")
    manifest, config, pricing = e.load_bundle(e.ROOT)
    state = e.ledger_state(e.LEDGER, manifest, config, pricing)
    ids = [r["request_id"] for r in manifest["rows"]]
    attempted = [rid for rid in ids if state["attempts"][rid]]
    bad = [r for r in state["results"] if r["state"] != "ACCEPTED"]
    if (
        len(ids) != 300
        or attempted != ids[:75]
        or len(state["accepted"]) != 74
        or set(state["accepted"]) != set(ids[:74])
        or state["provider_invocations"] != 75
        or state["ambiguous"]
        or len(bad) != 1
        or bad[0]["state"] != "REQUEST_ID_MISMATCH"
        or bad[0]["request_id_echo"]
        or not bad[0]["target_rule_binding"]
        or bad[0]["response_fingerprint"] is None
        or any(len(h) != 1 for h in state["attempts"].values() if h)
        or state["exposure"] != Decimal("0.0363906")
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_STATE_RECONCILIATION")
    failed = state["attempts"][ids[74]][0]
    if bad[0]["attempt_fingerprint"] != failed["fingerprint"]:
        raise io.ReviewBlocked("P024_CONTINUATION_TERMINAL_BINDING_DRIFT")
    starts = [state["attempts"][rid][0]["timestamp"] for rid in attempted]
    if starts != sorted(starts):
        raise io.ReviewBlocked("P024_CONTINUATION_PREFIX_CHRONOLOGY_DRIFT")
    normalized = io.read_seal(PARTIAL / "normalized-assessments.json")
    if normalized["assessments"] != [state["accepted"][rid] for rid in ids[:74]]:
        raise io.ReviewBlocked("P024_CONTINUATION_ACCEPTED_HISTORY_DRIFT")
    approval = io.read_seal(e.LEDGER / "approval.json")
    if (
        approval["fingerprint"] != public["fingerprints"]["runtime-approval"]
        or e.approval_check({k: v for k, v in approval.items() if k != "fingerprint"}, e.ROOT)
        != CAP
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_ORIGINAL_APPROVAL_DRIFT")
    return manifest, config, pricing, state, public


def prepare() -> dict[str, Any]:
    git_gate()
    runtime_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with p.offline_scope():
        model = p.model_gate()
    with scope((e.ROOT, e.LEDGER, PARTIAL, PARTIAL_PUBLIC), (ROOT,)):
        manifest, config, pricing, state, public = history()
        terminal = manifest["rows"][74]
        binding = p.seal(
            ROOT / "terminal-invalid-binding.json",
            dict(
                version="p024-terminal-invalid-binding-v1",
                request_id=terminal["request_id"],
                execution_id=terminal["execution_id"],
                request_fingerprint=terminal["request_fingerprint"],
                original_attempt_fingerprint=state["attempts"][terminal["request_id"]][0][
                    "fingerprint"
                ],
                partial_freeze_fingerprint=public["fingerprints"]["freeze-receipt.json"],
                llm_evidence_status="TERMINAL_INVALID_REQUEST_ID_MISMATCH",
                llm_accepted_assessment=None,
                llm_technical_missing=True,
                retry_allowed=False,
                semantic_decision=None,
            ),
        )
        allow = p.seal(
            ROOT / "allowlist.json",
            dict(
                version="p024-continuation-allowlist-v1",
                rows=manifest["rows"][75:],
                count=225,
                original_request_manifest_fingerprint=manifest["fingerprint"],
                partial_freeze_fingerprint=public["fingerprints"]["freeze-receipt.json"],
            ),
        )
        order = p.seal(
            ROOT / "order.json",
            dict(
                request_ids=[r["request_id"] for r in allow["rows"]],
                original_order_fingerprint=io.read_seal(e.ROOT / "order.json")["fingerprint"],
            ),
        )
        p.seal(
            ROOT / "protocol.json",
            dict(
                version="p024-continuation-protocol-v1",
                runtime_head=runtime_head,
                stage="FINAL_300_LLM_CONTINUATION",
                original_protocol_fingerprint=config["fingerprint"],
                original_bundle_fingerprint=io.read_seal(e.ROOT / "bundle-freeze.json")[
                    "fingerprint"
                ],
                allowlist_fingerprint=allow["fingerprint"],
                order_fingerprint=order["fingerprint"],
                terminal_binding_fingerprint=binding["fingerprint"],
                partial_freeze_fingerprint=public["fingerprints"]["freeze-receipt.json"],
                original_approval_fingerprint=public["fingerprints"]["human-approval"],
                hard_cap_usd_total_stage=str(CAP),
                initial_known_or_reserved_usd=str(state["exposure"]),
                initial_provider_invocations=75,
                original_accepted=74,
                model_lock_fingerprint=digest(model),
                p023_registry_fingerprint=e.REGISTRY_FP,
                expected_continuation=225,
                schema_id_recovery_max=0,
                old_terminal_retry=False,
            ),
        )
    sources = {n: io.sha(Path(n)) for n in (*SOURCES, *p.SOURCES, *p.SHARED)}
    with scope((ROOT,), (ROOT,)):
        p.seal(ROOT / "source-bindings.json", dict(files=sources))
        frozen = p.seal(
            ROOT / "plan-freeze.json",
            dict(
                files={
                    n: io.sha(ROOT / n)
                    for n in (
                        "allowlist.json",
                        "order.json",
                        "protocol.json",
                        "terminal-invalid-binding.json",
                        "source-bindings.json",
                    )
                }
            ),
        )
    return dict(
        status="P024_CONTINUATION_PREPARED",
        logical_requests=225,
        plan_fingerprint=frozen["fingerprint"],
        provider_invocations=0,
    )


def approval_bindings() -> dict[str, Any]:
    protocol = io.read_seal(ROOT / "protocol.json")
    return dict(
        stage="FINAL_300_LLM_CONTINUATION",
        continuation_only=True,
        new_logical_requests_authorized=225,
        previously_accepted_locked=74,
        terminal_invalid_locked=1,
        terminal_invalid_retry_authorized=False,
        hard_cap_usd_total_stage=str(CAP),
        hard_cap_increase=False,
        provider="openai",
        model="gpt-6-luna",
        processing_tier="STANDARD",
        hybrid_retraining_authorized=False,
        final_evaluation_authorized=False,
        security_authorized=False,
        plan_fingerprint=io.read_seal(ROOT / "plan-freeze.json")["fingerprint"],
        original_request_manifest_fingerprint=e.REQUEST_FP,
        original_protocol_fingerprint=protocol["original_protocol_fingerprint"],
        original_bundle_fingerprint=protocol["original_bundle_fingerprint"],
        original_approval_fingerprint=protocol["original_approval_fingerprint"],
        partial_freeze_fingerprint=protocol["partial_freeze_fingerprint"],
        continuation_allowlist_fingerprint=protocol["allowlist_fingerprint"],
        continuation_order_fingerprint=protocol["order_fingerprint"],
        terminal_binding_fingerprint=protocol["terminal_binding_fingerprint"],
        p023_registry_fingerprint=e.REGISTRY_FP,
        model_lock_fingerprint=protocol["model_lock_fingerprint"],
    )


def load(
    approval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any], dict[str, Any]]:
    frozen = io.read_seal(ROOT / "plan-freeze.json")
    io.verify_files(ROOT, frozen["files"] | {"plan-freeze.json": io.sha(ROOT / "plan-freeze.json")})
    expected = approval_bindings() | {"paid_execution_approved": True}
    if approval != expected:
        raise PermissionError("P024_CONTINUATION_EXPLICIT_APPROVAL_REQUIRED")
    manifest, config, pricing, old, public = history()
    allow = io.read_seal(ROOT / "allowlist.json")
    order = io.read_seal(ROOT / "order.json")
    protocol = io.read_seal(ROOT / "protocol.json")
    binding = io.read_seal(ROOT / "terminal-invalid-binding.json")
    for value in (allow, order, protocol, binding):
        e.audit_payload(value)
    ids = [r["request_id"] for r in manifest["rows"]]
    if (
        allow["rows"] != manifest["rows"][75:]
        or allow["count"] != 225
        or order["request_ids"] != ids[75:]
        or len(set(order["request_ids"])) != 225
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_NEVER_EXECUTED_ALLOWLIST_REQUIRED")
    if (
        binding["request_id"] != ids[74]
        or binding["semantic_decision"] is not None
        or binding["llm_accepted_assessment"] is not None
        or binding["llm_evidence_status"] != "TERMINAL_INVALID_REQUEST_ID_MISMATCH"
        or binding["retry_allowed"] is not False
        or binding["llm_technical_missing"] is not True
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_TERMINAL_MISSING_DRIFT")
    if (
        protocol["allowlist_fingerprint"] != allow["fingerprint"]
        or protocol["order_fingerprint"] != order["fingerprint"]
        or protocol["terminal_binding_fingerprint"] != binding["fingerprint"]
        or protocol["partial_freeze_fingerprint"] != public["fingerprints"]["freeze-receipt.json"]
        or protocol["initial_known_or_reserved_usd"] != str(old["exposure"])
        or protocol["hard_cap_usd_total_stage"] != str(CAP)
        or protocol["schema_id_recovery_max"] != 0
        or protocol["old_terminal_retry"] is not False
        or protocol["original_protocol_fingerprint"] != config["fingerprint"]
        or protocol["original_bundle_fingerprint"]
        != io.read_seal(e.ROOT / "bundle-freeze.json")["fingerprint"]
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_PROTOCOL_DRIFT")
    for row in allow["rows"]:
        if old["attempts"][row["request_id"]]:
            raise io.ReviewBlocked("P024_CONTINUATION_OLD_REQUEST_PROHIBITED")
    if pricing.charge(config["max_input_tokens"], config["max_output_tokens"]) != Decimal(
        "0.0042768"
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_RESERVATION_DRIFT")
    return {"rows": allow["rows"]}, config, pricing, old, protocol


def segment_state(
    manifest: dict[str, Any], config: dict[str, Any], pricing: PricingAssumption
) -> dict[str, Any]:
    header = io.read_seal(LEDGER / "ledger-header.json")
    if header != dict(
        version="p024-continuation-ledger-v1",
        scope="FINAL_300_LLM_CONTINUATION",
        logical_requests=225,
        plan_fingerprint=io.read_seal(ROOT / "plan-freeze.json")["fingerprint"],
    ) | {"fingerprint": digest({k: v for k, v in header.items() if k != "fingerprint"})}:
        raise io.ReviewBlocked("P024_CONTINUATION_SEGMENT_SCOPE_DRIFT")
    state = core.ledger_state(LEDGER, manifest, config, pricing)
    ordered = [r["request_id"] for r in manifest["rows"]]
    attempted = [rid for rid in ordered if state["attempts"][rid]]
    if attempted != ordered[: len(attempted)] or any(
        rid not in state["accepted"] for rid in attempted[:-1]
    ):
        raise io.ReviewBlocked("P024_CONTINUATION_SERIAL_PREFIX_DRIFT")
    return state


def guard_request(
    rid: str, manifest: dict[str, Any], old: dict[str, Any], new: dict[str, Any]
) -> None:
    if (
        rid not in {r["request_id"] for r in manifest["rows"]}
        or old["attempts"].get(rid)
        or rid in new["accepted"]
    ):
        raise PermissionError("P024_CONTINUATION_OLD_OR_ACCEPTED_REQUEST_PROHIBITED")
    history = new["attempts"][rid]
    if history:
        last = io.read_seal(LEDGER / f"{history[-1]['prefix']}.outcome.json")
        if last["state"] != "TECHNICAL_FAILED" or len(history) >= 3:
            raise PermissionError("P024_CONTINUATION_TERMINAL_OR_EXHAUSTED_REQUEST_PROHIBITED")


def operational(new: dict[str, Any], old: dict[str, Any], reason: str) -> dict[str, Any]:
    r = core.operational(new, reason)
    r.update(
        logical_requests=225,
        missing=225 - len(new["accepted"]),
        original_accepted=74,
        total_accepted=74 + len(new["accepted"]),
        original_provider_invocations=75,
        total_provider_invocations=75 + new["provider_invocations"],
        original_terminal_invalid=1,
        estimated_or_reserved_usd=str(old["exposure"] + new["exposure"]),
        original_estimated_usd=str(old["exposure"]),
    )
    return r


def initialize(
    approval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any], dict[str, Any]]:
    loaded = load(approval)
    p.seal(
        LEDGER / "ledger-header.json",
        dict(
            version="p024-continuation-ledger-v1",
            scope="FINAL_300_LLM_CONTINUATION",
            logical_requests=225,
            plan_fingerprint=io.read_seal(ROOT / "plan-freeze.json")["fingerprint"],
        ),
    )
    p.seal(LEDGER / "approval.json", approval)
    return loaded


def execute(
    approval: dict[str, Any], transport: e.Transport, decoder: e.Decoder | None = None
) -> dict[str, Any]:
    manifest, config, pricing, old, protocol = initialize(approval)
    reserve = pricing.charge(config["max_input_tokens"], config["max_output_tokens"])
    with (LEDGER / "run.lock").open("a") as lock:
        (LEDGER / "run.lock").chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for row in manifest["rows"]:
            rid = row["request_id"]
            while True:
                new = segment_state(manifest, config, pricing)
                terminal = next(
                    (
                        r["state"]
                        for r in new["results"]
                        if r["state"] not in {"ACCEPTED", "TECHNICAL_FAILED"}
                    ),
                    None,
                )
                if terminal:
                    return operational(new, old, terminal)
                if rid in new["accepted"]:
                    break
                h = new["attempts"][rid]
                if new["ambiguous"]:
                    pending = next(
                        (a for a in h if not (LEDGER / f"{a['prefix']}.outcome.json").exists()),
                        None,
                    )
                    if (
                        pending
                        and decoder
                        and (LEDGER / f"{pending['prefix']}.raw").exists()
                        and (LEDGER / f"{pending['prefix']}.capture.json").exists()
                    ):
                        core.store_outcome(
                            LEDGER,
                            pending,
                            row,
                            decoder(
                                (LEDGER / f"{pending['prefix']}.raw").read_bytes(),
                                io.read_seal(LEDGER / f"{pending['prefix']}.capture.json")[
                                    "metadata"
                                ],
                            ),
                            pricing,
                            config,
                        )
                        continue
                    return operational(new, old, "AMBIGUOUS_TRANSPORT")
                if h:
                    last = io.read_seal(LEDGER / f"{h[-1]['prefix']}.outcome.json")
                    if last["state"] != "TECHNICAL_FAILED":
                        return operational(new, old, last["state"])
                    if len(h) >= config["max_attempts"]:
                        return operational(new, old, "RETRY_EXHAUSTED")
                guard_request(rid, manifest, old, new)
                exposure = old["exposure"] + new["exposure"]
                if exposure + reserve > CAP:
                    return operational(new, old, "PAID_CAP_REACHED")
                payload_path = e.ROOT / "payloads" / f"{rid}.json"
                frozen = io.read_seal(e.ROOT / "bundle-freeze.json")
                if io.sha(payload_path) != frozen["files"][f"payloads/{rid}.json"]:
                    raise io.ReviewBlocked("P024_CONTINUATION_REQUEST_BYTE_DRIFT")
                wire = io.read_seal(payload_path)["wire_payload"]
                if digest(wire) != row["request_fingerprint"]:
                    raise io.ReviewBlocked("P024_CONTINUATION_REQUEST_BINDING_DRIFT")
                e.audit_payload(io.read_seal(payload_path))
                n = len(h) + 1
                prefix = f"attempt-{rid}-{n:02}"
                intent = io.append_seal(
                    LEDGER / f"{prefix}.json",
                    dict(
                        prefix=prefix,
                        request_id=rid,
                        execution_id=row["execution_id"],
                        attempt=n,
                        request_fingerprint=row["request_fingerprint"],
                        reserved_usd=str(reserve),
                        provider=config["provider"],
                        model=config["model"],
                        processing=config["processing"],
                        timestamp=datetime.now(UTC).isoformat(),
                        recovery_of=h[-1]["fingerprint"] if h else None,
                        segment="p024-final-live-continuation-v1",
                        global_logical_state="NEVER_EXECUTED" if n == 1 else "TECHNICAL_RETRY",
                        total_stage_reserved_at_intent_usd=str(exposure + reserve),
                        partial_freeze_fingerprint=protocol["partial_freeze_fingerprint"],
                    ),
                )

                def capture(raw: bytes, metadata: dict[str, Any], *, prefix: str = prefix) -> None:
                    with (LEDGER / f"{prefix}.raw").open("xb") as stream:
                        stream.write(raw)
                    (LEDGER / f"{prefix}.raw").chmod(0o600)
                    io.append_seal(
                        LEDGER / f"{prefix}.capture.json",
                        dict(metadata=metadata, raw_sha256=io.sha(LEDGER / f"{prefix}.raw")),
                    )

                try:
                    outcome = transport(wire, capture)
                except Exception:
                    return operational(
                        segment_state(manifest, config, pricing), old, "AMBIGUOUS_TRANSPORT"
                    )
                core.store_outcome(LEDGER, intent, row, outcome, pricing, config)
        new = segment_state(manifest, config, pricing)
        p.seal(
            LEDGER / "normalized-assessments.json",
            dict(
                version="p024-continuation-normalized-v1",
                assessments=[new["accepted"][r["request_id"]] for r in manifest["rows"]],
                accepted=225,
                duplicates=0,
            ),
        )
        return operational(new, old, "COMPLETE")


def composite_rows(
    manifest: dict[str, Any], old: dict[str, Any], new: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = manifest["rows"]
    original_ids = {r["request_id"] for r in rows[:74]}
    suffix_ids = {r["request_id"] for r in rows[75:]}
    if (
        len(rows) != 300
        or set(old["accepted"]) != original_ids
        or not set(new["accepted"]).issubset(suffix_ids)
    ):
        raise io.ReviewBlocked("P024_COMPOSITE_ACCEPTED_SCOPE_DRIFT")
    accepted = old["accepted"] | new["accepted"]
    states = []
    for pos, row in enumerate(rows):
        rid = row["request_id"]
        if rid in accepted:
            assessment = accepted[rid]["assessment"]
            if assessment["request_id"] != rid:
                raise io.ReviewBlocked("P024_COMPOSITE_ACCEPTED_ID_DRIFT")
            value = dict(
                request_id=rid,
                execution_id=row["execution_id"],
                llm_evidence_status="ACCEPTED",
                llm_technical_missing=False,
                semantic_decision=assessment["decision"],
            )
        elif pos == 74:
            value = dict(
                request_id=rid,
                execution_id=row["execution_id"],
                llm_evidence_status="TERMINAL_INVALID_REQUEST_ID_MISMATCH",
                llm_technical_missing=True,
            )
        else:
            h = new["attempts"].get(rid, [])
            result = next(
                (
                    r
                    for r in new["results"]
                    if h and r["attempt_fingerprint"] == h[-1]["fingerprint"]
                ),
                None,
            )
            status = (
                "NEVER_EXECUTED"
                if not h
                else (result["state"] if result else "AMBIGUOUS_TRANSPORT")
            )
            value = dict(
                request_id=rid,
                execution_id=row["execution_id"],
                llm_evidence_status=status,
                llm_technical_missing=True,
            )
        states.append(value)
    return [accepted[r["request_id"]] for r in rows if r["request_id"] in accepted], states


def freeze(approval: dict[str, Any]) -> dict[str, Any]:
    """Offline, time-free scientific registries; operational timestamps stay in raw ledger."""
    from archguard.infrastructure.component_holdout import public_privacy

    with (LEDGER / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with p.offline_scope():
            model = p.model_gate()
        with scope(
            (ROOT, e.ROOT, e.LEDGER, PARTIAL, PARTIAL_PUBLIC, APPROVAL, LEDGER), (FREEZE, COMPOSITE)
        ):
            suffix, config, pricing, old, protocol = load(approval)
            new = segment_state(suffix, config, pricing)
            if digest(model) != protocol["model_lock_fingerprint"]:
                raise io.ReviewBlocked("P024_CONTINUATION_MODEL_DRIFT")
            manifest = io.read_seal(e.ROOT / "manifest.json")
            assessments, statuses = composite_rows(manifest, old, new)
            complete = len(new["accepted"]) == 225 and not new["ambiguous"]
            inventory = {f.name: io.sha(f) for f in LEDGER.iterdir() if f.is_file()}
            by_attempt = {r["attempt_fingerprint"]: r for r in new["results"]}
            records = []
            exposure = old["exposure"]
            technical = 0
            for row in suffix["rows"]:
                prior = None
                for intent in new["attempts"][row["request_id"]]:
                    result = by_attempt.get(intent["fingerprint"])
                    reserve = Decimal(intent["reserved_usd"])
                    if (
                        exposure + reserve > CAP
                        or intent["total_stage_reserved_at_intent_usd"] != str(exposure + reserve)
                        or intent["partial_freeze_fingerprint"]
                        != protocol["partial_freeze_fingerprint"]
                    ):
                        raise io.ReviewBlocked("P024_CONTINUATION_CUMULATIVE_CAP_REPLAY_DRIFT")
                    if prior:
                        if prior["state"] != "TECHNICAL_FAILED":
                            raise io.ReviewBlocked("P024_CONTINUATION_NONTECHNICAL_RETRY")
                        technical += 1
                    usage = result["provider_usage"] if result else {}
                    inp = result["input_tokens"] if result else None
                    out = result["output_tokens"] if result else None
                    total = usage.get("total_tokens")
                    if (
                        total is not None
                        and inp is not None
                        and out is not None
                        and total != inp + out
                    ):
                        raise io.ReviewBlocked("P024_CONTINUATION_USAGE_RECONCILIATION_DRIFT")
                    records.append(
                        dict(
                            request_id=row["request_id"],
                            execution_id=row["execution_id"],
                            attempt=intent["attempt"],
                            attempt_fingerprint=intent["fingerprint"],
                            state=result["state"] if result else "AMBIGUOUS_TRANSPORT",
                            input_tokens=inp,
                            output_tokens=out,
                            total_tokens=total,
                            cached_tokens=usage.get("input_tokens_details", {}).get(
                                "cached_tokens"
                            ),
                            provider_usage=usage,
                            known_cost_usd=result["known_cost_usd"] if result else None,
                            reserved_usd=str(reserve),
                            total_stage_reserved_at_intent_usd=str(exposure + reserve),
                            raw_sha256=result["raw_response_sha256"]
                            if result
                            else inventory.get(intent["prefix"] + ".raw"),
                        )
                    )
                    exposure += (
                        Decimal(result["known_cost_usd"])
                        if result and result["known_cost_usd"] is not None
                        else reserve
                    )
                    prior = result
            if exposure != old["exposure"] + new["exposure"]:
                raise io.ReviewBlocked("P024_CONTINUATION_EXPOSURE_DRIFT")
            known = sum(
                (Decimal(r["known_cost_usd"]) for r in records if r["known_cost_usd"] is not None),
                Decimal(0),
            )
            reason = (
                "COMPLETE"
                if complete
                else (
                    "AMBIGUOUS_TRANSPORT"
                    if new["ambiguous"]
                    else next(
                        (r["state"] for r in reversed(new["results"]) if r["state"] != "ACCEPTED"),
                        "PAID_CAP_REACHED",
                    )
                )
            )
            if reason == "TECHNICAL_FAILED" and any(len(h) >= 3 for h in new["attempts"].values()):
                reason = "RETRY_EXHAUSTED"
            parts = {
                "raw-ledger.json": dict(
                    version="p024-continuation-raw-v1",
                    files=inventory,
                    provider_invocations=new["provider_invocations"],
                ),
                "normalized-assessments.json": dict(
                    version="p024-continuation-assessments-v1",
                    assessments=[
                        new["accepted"][r["request_id"]]
                        for r in suffix["rows"]
                        if r["request_id"] in new["accepted"]
                    ],
                    accepted=len(new["accepted"]),
                    missing=225 - len(new["accepted"]),
                ),
                "usage-ledger.json": dict(
                    version="p024-continuation-usage-v1",
                    records=records,
                    known_estimated_cost_usd=str(known),
                    exposure_usd=str(new["exposure"]),
                    invoice=None,
                ),
                "execution-lineage.json": dict(
                    version="p024-continuation-lineage-v1",
                    partial_freeze_fingerprint=protocol["partial_freeze_fingerprint"],
                    original_protocol_fingerprint=config["fingerprint"],
                    runtime_head=protocol["runtime_head"],
                    plan_fingerprint=io.read_seal(ROOT / "plan-freeze.json")["fingerprint"],
                    allowlist_fingerprint=protocol["allowlist_fingerprint"],
                    order_fingerprint=protocol["order_fingerprint"],
                    terminal_binding_fingerprint=protocol["terminal_binding_fingerprint"],
                    source_bindings=io.read_seal(ROOT / "source-bindings.json")["files"],
                    model_lock_fingerprint=protocol["model_lock_fingerprint"],
                ),
                "approval-receipt.json": dict(
                    approval_fingerprint=digest(approval), approval=approval
                ),
                "completion-receipt.json": dict(
                    version="p024-continuation-completion-v1",
                    complete=complete,
                    stop_reason=reason,
                    expected=225,
                    accepted=len(new["accepted"]),
                    missing=225 - len(new["accepted"]),
                    provider_invocations=new["provider_invocations"],
                    original_terminal_repeated=False,
                ),
            }
            for name, value in parts.items():
                p.seal(FREEZE / name, value)
            for name, sha in inventory.items():
                target = FREEZE / "ledger" / name
                if target.exists():
                    if io.sha(target) != sha:
                        raise io.ReviewBlocked("P024_CONTINUATION_RAW_SNAPSHOT_DRIFT")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with target.open("xb") as stream:
                        stream.write((LEDGER / name).read_bytes())
                    target.chmod(0o600)
            segment_receipt = p.seal(
                FREEZE / "freeze-receipt.json",
                dict(
                    version="p024-continuation-freeze-v1",
                    files={
                        f.relative_to(FREEZE).as_posix(): io.sha(f)
                        for f in FREEZE.rglob("*")
                        if f.is_file() and f.name != "freeze-receipt.json"
                    },
                    fingerprints={
                        name: io.read_seal(FREEZE / name)["fingerprint"] for name in parts
                    },
                    original_segment_files=inventory,
                    complete=complete,
                ),
            )
            io.verify_files(
                FREEZE,
                segment_receipt["files"]
                | {"freeze-receipt.json": io.sha(FREEZE / "freeze-receipt.json")},
            )

            def total(key: str) -> int | None:
                available = [r[key] for r in records if r[key] is not None]
                return sum(available) if available else (0 if not records else None)

            original = io.read_seal(PARTIAL_PUBLIC, PARTIAL_PUBLIC_FP)
            totals = {
                key: total(key)
                for key in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens")
            }
            composite_usage = dict(
                version="p024-composite-usage-v1",
                original_usage_fingerprint=original["fingerprints"]["usage-ledger.json"],
                continuation_usage_fingerprint=io.read_seal(FREEZE / "usage-ledger.json")[
                    "fingerprint"
                ],
                original_known_cost_usd=str(old["exposure"]),
                continuation_known_cost_usd=str(known),
                total_known_cost_usd=str(old["exposure"] + known),
                total_exposure_usd=str(exposure),
                uncertain_exposure_usd=str(new["exposure"] - known),
                hard_cap_usd=str(CAP),
                remaining_cap_usd=str(CAP - exposure),
                invoice=None,
            )
            composite_parts = {
                "accepted-assessments.json": dict(
                    version="p024-composite-assessments-v1",
                    assessments=assessments,
                    accepted=len(assessments),
                ),
                "technical-status.json": dict(
                    version="p024-composite-status-v1",
                    rows=statuses,
                    logical_requests=300,
                    terminal_binding_fingerprint=protocol["terminal_binding_fingerprint"],
                ),
                "usage.json": composite_usage,
                "lineage.json": dict(
                    version="p024-composite-lineage-v1",
                    original_partial_freeze_fingerprint=protocol["partial_freeze_fingerprint"],
                    continuation_freeze_fingerprint=segment_receipt["fingerprint"],
                    original_request_manifest_fingerprint=e.REQUEST_FP,
                    p023_registry_fingerprint=e.REGISTRY_FP,
                    model_lock_fingerprint=protocol["model_lock_fingerprint"],
                    final_truth_accessed=False,
                    hybrid_predictions=0,
                ),
            }
            for name, value in composite_parts.items():
                p.seal(COMPOSITE / name, value)
            composite_receipt = p.seal(
                COMPOSITE / "freeze-receipt.json",
                dict(
                    version="p024-final-acquisition-freeze-v1",
                    files={name: io.sha(COMPOSITE / name) for name in composite_parts},
                    fingerprints={
                        name: io.read_seal(COMPOSITE / name)["fingerprint"]
                        for name in composite_parts
                    },
                    complete=complete,
                    logical_requests=300,
                    accepted=len(assessments),
                    original_terminal_missing=1,
                ),
            )
            io.verify_files(
                COMPOSITE,
                composite_receipt["files"]
                | {"freeze-receipt.json": io.sha(COMPOSITE / "freeze-receipt.json")},
            )
            distribution = Counter(a["assessment"]["decision"] for a in assessments)
            counts = Counter(r["state"] for r in new["results"])
            result = dict(
                version="p024-live1-public-acquisition-v1",
                status="P024_LIVE_1_CONTINUATION_COMPLETE"
                if complete
                else "P024_LIVE_1_EXECUTION_INCOMPLETE",
                stop_reason=reason,
                next_stage="READY_FOR_P025_FINAL_EVALUATION_WITH_ONE_LLM_MISSING"
                if complete
                else "WAITING_FOR_COORDINATOR_REVIEW",
                original_attempted=75,
                original_accepted=74,
                original_terminal_invalid=1,
                original_provider_invocations=75,
                continuation_expected=225,
                continuation_attempted=sum(bool(h) for h in new["attempts"].values()),
                continuation_accepted=len(new["accepted"]),
                continuation_missing=225 - len(new["accepted"]),
                continuation_provider_invocations=new["provider_invocations"],
                total_provider_invocations=75 + new["provider_invocations"],
                total_accepted=len(assessments),
                logical_benchmark_cases=300,
                original_terminal_retried=False,
                terminal_semantic_decision_used=False,
                terminal_mapped_to_semantic_category=False,
                continuation_technical_retries=technical,
                continuation_schema_invalid=counts["SCHEMA_INVALID"],
                continuation_request_id_mismatch=counts["REQUEST_ID_MISMATCH"],
                continuation_ambiguity=len(new["ambiguous"]),
                accepted_duplicates=0,
                unexecuted=sum(r["llm_evidence_status"] == "NEVER_EXECUTED" for r in statuses),
                technical_missing=300 - len(assessments),
                decisions={
                    x: distribution[x]
                    for x in (
                        "SUPPORTED",
                        "NOT_SUPPORTED",
                        "INSUFFICIENT_CONTEXT",
                        "NOT_APPLICABLE",
                    )
                },
                original_input_tokens=original["reported_input_tokens"],
                original_output_tokens=original["reported_output_tokens"],
                continuation_input_tokens=totals["input_tokens"],
                continuation_output_tokens=totals["output_tokens"],
                composite_input_tokens=original["reported_input_tokens"]
                + (totals["input_tokens"] or 0),
                composite_output_tokens=original["reported_output_tokens"]
                + (totals["output_tokens"] or 0),
                composite_total_tokens=original["reported_total_tokens"]
                + (totals["total_tokens"] or 0),
                cached_tokens=original["reported_cached_input_tokens"]
                + (totals["cached_tokens"] or 0),
                usage_missing=sum(r["known_cost_usd"] is None for r in records),
                **{
                    k: v
                    for k, v in composite_usage.items()
                    if k
                    not in {
                        "version",
                        "original_usage_fingerprint",
                        "continuation_usage_fingerprint",
                    }
                },
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                cap_increased=False,
                cap_exceeded=exposure > CAP,
                beyond_cap_call=False,
                final_truth_accessed=False,
                development_truth_accessed=False,
                reviewer_data_accessed=False,
                construction_intent_accessed=False,
                correctness_accessed=False,
                hybrid_retraining=False,
                final_hybrid_predictions=0,
                final_ablation_predictions=0,
                final_evaluation=False,
                hypothesis_conclusion=False,
                security=False,
                provider_calls_after_freeze=0,
                allowlist_count=225,
                allowlist_duplicates=0,
                accepted_or_terminal_ids_in_allowlist=0,
                development_ids_in_allowlist=0,
                original_relative_order_verified=True,
                partial_history_preserved=True,
                segment_fingerprints=segment_receipt["fingerprints"]
                | {
                    "freeze-receipt.json": segment_receipt["fingerprint"],
                    "human-approval": digest(approval),
                },
                composite_fingerprints=composite_receipt["fingerprints"]
                | {"freeze-receipt.json": composite_receipt["fingerprint"]},
                terminal_binding_fingerprint=protocol["terminal_binding_fingerprint"],
                allowlist_fingerprint=protocol["allowlist_fingerprint"],
                order_fingerprint=protocol["order_fingerprint"],
            )
        public = p.seal(PUBLIC, result)
        public_privacy([PUBLIC])
        return public
