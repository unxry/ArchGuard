"""FINAL acquisition segment C: locked historical failures, original 55-request suffix."""

import fcntl
import os
import subprocess
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure import development_llm_executor as core
from archguard.infrastructure import final_llm_continuation as c
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import final_llm_preflight as p
from archguard.infrastructure import unified_human_review as io

HEAD = "3395b500379530bb5c898b7e7fdeb177326e213b"
B_PUBLIC_FP = "88b5518a5bfc9daab0a2962c78ba1496335e9dd91d5e0a0592d0b464fd806e3e"
B_QUALITY_FP = "43954ed8b1d950b6e92ba7b831f91614e1a1044037f42f1497ab164154cbecba"
ROOT = io.PRIVATE / "p024-final-completion-plan-v1"
LEDGER = io.PRIVATE / "p024-final-live-completion-v1"
APPROVAL = io.PRIVATE / "p024-final-completion-approval-v1"
FREEZE = io.PRIVATE / "p024-final-completion-freeze-v1"
COMPOSITE = io.PRIVATE / "p024-final-composite-acquisition-v2"
PUBLIC = io.BASE / "p024-live2-acquisition-v1.json"
HANDOFF = io.BASE / "p025-acquisition-handoff-v2.json"
QUALITY = io.BASE / "p024-live2-verification-v1.json"
DOC = "docs/verification/PROMPT_024_LIVE_2.md"
SOURCES = (
    "src/archguard/infrastructure/final_llm_completion.py",
    "scripts/prompt024_completion.py",
    "tests/intelligence/test_final_llm_completion.py",
)
CAP = c.CAP
RESERVE = Decimal("0.0042768")
READS = (
    ROOT,
    APPROVAL,
    LEDGER,
    e.ROOT,
    e.LEDGER,
    c.PARTIAL,
    c.PARTIAL_PUBLIC,
    c.ROOT,
    c.APPROVAL,
    c.LEDGER,
    c.FREEZE,
    c.COMPOSITE,
    c.PUBLIC,
    io.BASE / "p024-live1-verification-v1.json",
)


def git_gate(*, initial: bool = False, closed: bool = False) -> None:
    allowed = SOURCES + ((str(PUBLIC), str(HANDOFF), str(QUALITY), DOC) if closed else ())
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        () if initial else allowed,
    )
    chain = [
        "1891fa553218200139f027ed9c3a82d100f61462",
        p.ANCHORS["P021.B"],
        p.ANCHORS["P022"],
        p.ANCHORS["P022.LIVE"],
        p.ANCHORS["P023"],
        "d609a312bdf5ce2af67026008bf2f055c6898962",
        c.HEAD,
        "46320397944273c766bd2723d8354773c8a7ccb2",
        HEAD,
    ]
    for a, b in zip(chain, [*chain[1:], "HEAD"], strict=True):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P024_COMPLETION_LINEAGE_DRIFT")
    if initial and subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != HEAD:
        raise io.ReviewBlocked("P024_COMPLETION_INITIAL_HEAD_DRIFT")


def verify_snapshot(root: Path, fp: str, original: Path | None = None) -> dict[str, Any]:
    receipt = io.read_seal(root / "freeze-receipt.json", fp)
    io.verify_files(
        root, receipt["files"] | {"freeze-receipt.json": io.sha(root / "freeze-receipt.json")}
    )
    for name, expected in receipt["fingerprints"].items():
        io.read_seal(root / name, expected)
    if original is not None:
        io.verify_files(original, receipt["original_segment_files"])
    return receipt


def usage_records(
    root: Path,
    rows: list[dict[str, Any]],
    state: dict[str, Any],
    base: Decimal,
    binding_key: str,
    binding_fp: str,
) -> tuple[list[dict[str, Any]], int]:
    by_attempt = {r["attempt_fingerprint"]: r for r in state["results"]}
    records = []
    exposure = base
    retries = 0
    for row in rows:
        prior = None
        for intent in state["attempts"][row["request_id"]]:
            result = by_attempt.get(intent["fingerprint"])
            if (
                Decimal(intent["reserved_usd"]) != RESERVE
                or exposure + RESERVE > CAP
                or intent["total_stage_reserved_at_intent_usd"] != str(exposure + RESERVE)
                or intent[binding_key] != binding_fp
            ):
                raise io.ReviewBlocked("P024_COMPLETION_CUMULATIVE_CAP_REPLAY_DRIFT")
            if intent["attempt"] > 1:
                if prior is None or prior["state"] != "TECHNICAL_FAILED":
                    raise io.ReviewBlocked("P024_COMPLETION_NONTECHNICAL_RETRY")
                retries += 1
            usage = result["provider_usage"] if result else {}
            inp = result["input_tokens"] if result else None
            out = result["output_tokens"] if result else None
            total = usage.get("total_tokens")
            if total is not None and inp is not None and out is not None and total != inp + out:
                raise io.ReviewBlocked("P024_COMPLETION_USAGE_DRIFT")
            raw = root / f"{intent['prefix']}.raw"
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
                    cached_tokens=usage.get("input_tokens_details", {}).get("cached_tokens"),
                    provider_usage=usage,
                    known_cost_usd=result["known_cost_usd"] if result else None,
                    reserved_usd=str(RESERVE),
                    total_stage_reserved_at_intent_usd=str(exposure + RESERVE),
                    raw_sha256=result["raw_response_sha256"]
                    if result
                    else (io.sha(raw) if raw.exists() else None),
                )
            )
            exposure += (
                Decimal(result["known_cost_usd"])
                if result and result["known_cost_usd"] is not None
                else RESERVE
            )
            prior = result
    if exposure != base + state["exposure"]:
        raise io.ReviewBlocked("P024_COMPLETION_EXPOSURE_DRIFT")
    return records, retries


def history() -> tuple[dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any]]:
    manifest, config, pricing, a, public_a = c.history()
    public_b = io.read_seal(c.PUBLIC, B_PUBLIC_FP)
    quality = io.read_seal(io.BASE / "p024-live1-verification-v1.json", B_QUALITY_FP)
    if quality["acquisition_fingerprint"] != public_b["fingerprint"]:
        raise io.ReviewBlocked("P024_COMPLETION_PRIOR_QUALITY_DRIFT")
    snapshot = verify_snapshot(
        c.FREEZE, public_b["segment_fingerprints"]["freeze-receipt.json"], c.LEDGER
    )
    verify_snapshot(c.COMPOSITE, public_b["composite_fingerprints"]["freeze-receipt.json"])
    if snapshot["fingerprints"] != {
        k: v
        for k, v in public_b["segment_fingerprints"].items()
        if k not in {"freeze-receipt.json", "human-approval"}
    }:
        raise io.ReviewBlocked("P024_COMPLETION_PRIOR_SEGMENT_BINDINGS_DRIFT")
    sealed = io.read_seal(
        c.LEDGER / "approval.json", public_b["segment_fingerprints"]["human-approval"]
    )
    suffix, _, _, _, protocol_b = c.load({k: v for k, v in sealed.items() if k != "fingerprint"})
    b = c.segment_state(suffix, config, pricing)
    rows = manifest["rows"]
    ids = [r["request_id"] for r in rows]
    attempted = [rid for rid in ids if a["attempts"].get(rid) or b["attempts"].get(rid)]
    accepted = a["accepted"] | b["accepted"]
    if (
        attempted != ids[:245]
        or len(accepted) != 243
        or set(a["accepted"]) & set(b["accepted"])
        or b["provider_invocations"] != 170
        or len(b["accepted"]) != 169
        or b["ambiguous"] != [ids[244]]
        or len(b["results"]) != 169
        or any(r["state"] != "ACCEPTED" for r in b["results"])
        or len(b["attempts"][ids[244]]) != 1
    ):
        raise io.ReviewBlocked("P024_COMPLETION_PRIOR_ACCOUNTING_DRIFT")
    pending = b["attempts"][ids[244]][0]
    if any(
        (c.LEDGER / f"{pending['prefix']}.{s}").exists()
        for s in ("raw", "capture.json", "outcome.json")
    ):
        raise io.ReviewBlocked("P024_COMPLETION_HISTORICAL_NO_CAPTURE_DRIFT")
    starts = [
        (a["attempts"].get(rid) or b["attempts"].get(rid))[0]["timestamp"] for rid in attempted
    ]
    if starts != sorted(starts):
        raise io.ReviewBlocked("P024_COMPLETION_HISTORY_CHRONOLOGY_DRIFT")
    assessments, statuses = c.composite_rows(manifest, a, b)
    if (
        io.read_seal(c.COMPOSITE / "accepted-assessments.json")["assessments"] != assessments
        or io.read_seal(c.COMPOSITE / "technical-status.json")["rows"] != statuses
        or io.read_seal(c.FREEZE / "normalized-assessments.json")["assessments"]
        != [b["accepted"][rid] for rid in ids if rid in b["accepted"]]
    ):
        raise io.ReviewBlocked("P024_COMPLETION_PRIOR_REGISTRY_DRIFT")
    records, retries = usage_records(
        c.LEDGER,
        suffix["rows"],
        b,
        a["exposure"],
        "partial_freeze_fingerprint",
        protocol_b["partial_freeze_fingerprint"],
    )
    known_b = sum(
        (Decimal(r["known_cost_usd"]) for r in records if r["known_cost_usd"] is not None),
        Decimal(0),
    )
    if (
        retries != 0
        or io.read_seal(c.FREEZE / "usage-ledger.json")["records"] != records
        or a["exposure"] + known_b != Decimal("0.1183723")
        or a["exposure"] + b["exposure"] != Decimal("0.1226491")
        or b["exposure"] - known_b != RESERVE
        or public_b["total_known_cost_usd"] != str(a["exposure"] + known_b)
        or public_b["total_exposure_usd"] != str(a["exposure"] + b["exposure"])
    ):
        raise io.ReviewBlocked("P024_COMPLETION_PRIOR_COST_DRIFT")
    return (
        manifest,
        config,
        pricing,
        dict(
            a=a,
            b=b,
            public_a=public_a,
            public_b=public_b,
            accepted=accepted,
            attempts={rid: h for s in (a, b) for rid, h in s["attempts"].items() if h},
            exposure=a["exposure"] + b["exposure"],
            known_cost=a["exposure"] + known_b,
            ambiguous_intent=pending,
        ),
    )


def prepare() -> dict[str, Any]:
    git_gate()
    runtime = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with p.offline_scope():
        model = p.model_gate()
    with c.scope(READS, (ROOT,)):
        manifest, config, pricing, old = history()
        rows = manifest["rows"]
        bindings = {}
        for name, row, state, status in (
            ("mismatch-binding.json", rows[74], old["a"], "TERMINAL_INVALID_REQUEST_ID_MISMATCH"),
            ("ambiguity-binding.json", rows[244], old["b"], "AMBIGUOUS_TRANSPORT_NO_CAPTURE"),
        ):
            binding = p.seal(
                ROOT / name,
                dict(
                    request_id=row["request_id"],
                    execution_id=row["execution_id"],
                    request_fingerprint=row["request_fingerprint"],
                    original_attempt_fingerprint=state["attempts"][row["request_id"]][0][
                        "fingerprint"
                    ],
                    llm_evidence_status=status,
                    accepted_assessment=None,
                    semantic_decision=None,
                    technical_missing=True,
                    retry_allowed=False,
                    provider_replacement_allowed=False,
                    historical_provider_processing_possible=status
                    == "AMBIGUOUS_TRANSPORT_NO_CAPTURE",
                    provider_processing_known="UNKNOWN"
                    if status == "AMBIGUOUS_TRANSPORT_NO_CAPTURE"
                    else "YES",
                    retained_uncertain_reservation_usd=str(RESERVE)
                    if status == "AMBIGUOUS_TRANSPORT_NO_CAPTURE"
                    else "0",
                    historical_a_freeze=old["public_a"]["fingerprints"]["freeze-receipt.json"],
                    historical_b_freeze=old["public_b"]["segment_fingerprints"][
                        "freeze-receipt.json"
                    ],
                ),
            )
            bindings[name] = binding["fingerprint"]
        allow = p.seal(
            ROOT / "allowlist.json",
            dict(rows=rows[245:], count=55, original_request_manifest_fingerprint=e.REQUEST_FP),
        )
        order = p.seal(
            ROOT / "order.json",
            dict(
                request_ids=[r["request_id"] for r in rows[245:]],
                original_order_fingerprint=io.read_seal(e.ROOT / "order.json")["fingerprint"],
            ),
        )
        proof = p.seal(
            ROOT / "never-executed-proof.json",
            dict(
                benchmark_logical=300,
                previously_attempted=245,
                previously_accepted=243,
                prior_attempted_ids=[r["request_id"] for r in rows[:245]],
                never_executed_ids=order["request_ids"],
                never_executed=55,
                prior_attempts_in_allowlist=0,
                a_freeze_fingerprint=old["public_a"]["fingerprints"]["freeze-receipt.json"],
                b_freeze_fingerprint=old["public_b"]["segment_fingerprints"]["freeze-receipt.json"],
                allowlist_fingerprint=allow["fingerprint"],
                order_fingerprint=order["fingerprint"],
            ),
        )
        p.seal(
            ROOT / "protocol.json",
            dict(
                version="p024-completion-protocol-v1",
                stage="FINAL_300_LLM_CONTINUATION_2",
                runtime_head=runtime,
                original_protocol_fingerprint=config["fingerprint"],
                original_bundle_fingerprint=io.read_seal(e.ROOT / "bundle-freeze.json")[
                    "fingerprint"
                ],
                original_approval_fingerprint=old["public_a"]["fingerprints"]["human-approval"],
                a_freeze_fingerprint=proof["a_freeze_fingerprint"],
                b_freeze_fingerprint=proof["b_freeze_fingerprint"],
                prior_composite_fingerprint=old["public_b"]["composite_fingerprints"][
                    "freeze-receipt.json"
                ],
                allowlist_fingerprint=allow["fingerprint"],
                order_fingerprint=order["fingerprint"],
                never_executed_proof_fingerprint=proof["fingerprint"],
                missing_bindings=bindings,
                hard_cap_usd_total_stage=str(CAP),
                initial_known_cost_usd=str(old["known_cost"]),
                initial_uncertain_reserved_usd=str(RESERVE),
                initial_known_or_reserved_usd=str(old["exposure"]),
                maximum_new_invocations=55 * config["max_attempts"],
                maximum_new_exposure_usd=str(55 * config["max_attempts"] * RESERVE),
                maximum_total_exposure_usd=str(
                    old["exposure"] + 55 * config["max_attempts"] * RESERVE
                ),
                model_lock_fingerprint=digest(model),
                p023_registry_fingerprint=e.REGISTRY_FP,
                expected_continuation=55,
                schema_id_recovery_max=0,
                prior_failure_retry=False,
            ),
        )
        if pricing.charge(config["max_input_tokens"], config["max_output_tokens"]) != RESERVE:
            raise io.ReviewBlocked("P024_COMPLETION_RESERVATION_DRIFT")
    sources = {n: io.sha(Path(n)) for n in (*SOURCES, *c.SOURCES, *p.SOURCES, *p.SHARED)}
    with c.scope((ROOT,), (ROOT,)):
        p.seal(ROOT / "source-bindings.json", dict(files=sources))
        frozen = p.seal(
            ROOT / "plan-freeze.json",
            dict(files={f.name: io.sha(f) for f in ROOT.iterdir() if f.name != "plan-freeze.json"}),
        )
    return dict(
        status="P024_COMPLETION_PREPARED",
        logical_requests=55,
        plan_fingerprint=frozen["fingerprint"],
        new_provider_invocations=0,
    )


def approval_bindings() -> dict[str, Any]:
    protocol = io.read_seal(ROOT / "protocol.json")
    return dict(
        stage="FINAL_300_LLM_CONTINUATION_2",
        paid_execution_approved=True,
        continuation_only=True,
        new_logical_requests_authorized=55,
        previously_accepted_locked=243,
        request_id_mismatch_locked=1,
        ambiguous_no_capture_locked=1,
        request_id_mismatch_retry_authorized=False,
        ambiguous_retry_authorized=False,
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
        **{
            k: protocol[k]
            for k in (
                "original_protocol_fingerprint",
                "original_bundle_fingerprint",
                "original_approval_fingerprint",
                "a_freeze_fingerprint",
                "b_freeze_fingerprint",
                "allowlist_fingerprint",
                "order_fingerprint",
                "never_executed_proof_fingerprint",
                "missing_bindings",
                "model_lock_fingerprint",
                "p023_registry_fingerprint",
            )
        },
    )


def load(
    approval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any], dict[str, Any]]:
    frozen = io.read_seal(ROOT / "plan-freeze.json")
    io.verify_files(ROOT, frozen["files"] | {"plan-freeze.json": io.sha(ROOT / "plan-freeze.json")})
    if approval != approval_bindings():
        raise PermissionError("P024_COMPLETION_EXPLICIT_APPROVAL_REQUIRED")
    manifest, config, pricing, old = history()
    allow = io.read_seal(ROOT / "allowlist.json")
    order = io.read_seal(ROOT / "order.json")
    protocol = io.read_seal(ROOT / "protocol.json")
    proof = io.read_seal(ROOT / "never-executed-proof.json")
    ids = [r["request_id"] for r in manifest["rows"]]
    if (
        allow["rows"] != manifest["rows"][245:]
        or allow["count"] != 55
        or order["request_ids"] != ids[245:]
        or len(set(order["request_ids"])) != 55
        or proof["prior_attempted_ids"] != ids[:245]
        or proof["never_executed_ids"] != ids[245:]
        or protocol["allowlist_fingerprint"] != allow["fingerprint"]
        or protocol["order_fingerprint"] != order["fingerprint"]
        or protocol["never_executed_proof_fingerprint"] != proof["fingerprint"]
        or any(old["attempts"].get(rid) for rid in ids[245:])
    ):
        raise io.ReviewBlocked("P024_COMPLETION_EXACT_NEVER_EXECUTED_SUFFIX_REQUIRED")
    for name, pos, status in (
        ("mismatch-binding.json", 74, "TERMINAL_INVALID_REQUEST_ID_MISMATCH"),
        ("ambiguity-binding.json", 244, "AMBIGUOUS_TRANSPORT_NO_CAPTURE"),
    ):
        binding = io.read_seal(ROOT / name, protocol["missing_bindings"][name])
        if (
            binding["request_id"] != ids[pos]
            or binding["llm_evidence_status"] != status
            or binding["accepted_assessment"] is not None
            or binding["semantic_decision"] is not None
            or binding["retry_allowed"] is not False
            or binding["provider_replacement_allowed"] is not False
            or binding["technical_missing"] is not True
            or binding["original_attempt_fingerprint"]
            != old["attempts"][ids[pos]][0]["fingerprint"]
            or binding["historical_provider_processing_possible"] is not (pos == 244)
            or binding["provider_processing_known"] != ("UNKNOWN" if pos == 244 else "YES")
            or binding["retained_uncertain_reservation_usd"]
            != (str(RESERVE) if pos == 244 else "0")
        ):
            raise io.ReviewBlocked("P024_COMPLETION_MISSINGNESS_BINDING_DRIFT")
    if (
        protocol["initial_known_or_reserved_usd"] != str(old["exposure"])
        or protocol["initial_known_cost_usd"] != str(old["known_cost"])
        or protocol["initial_uncertain_reserved_usd"] != str(RESERVE)
        or protocol["hard_cap_usd_total_stage"] != str(CAP)
        or protocol["original_protocol_fingerprint"] != config["fingerprint"]
        or protocol["a_freeze_fingerprint"]
        != old["public_a"]["fingerprints"]["freeze-receipt.json"]
        or protocol["b_freeze_fingerprint"]
        != old["public_b"]["segment_fingerprints"]["freeze-receipt.json"]
        or protocol["schema_id_recovery_max"] != 0
        or protocol["prior_failure_retry"] is not False
        or pricing.charge(config["max_input_tokens"], config["max_output_tokens"]) != RESERVE
    ):
        raise io.ReviewBlocked("P024_COMPLETION_PROTOCOL_DRIFT")
    for value in (allow, order, protocol, proof):
        e.audit_payload(value)
    return dict(rows=allow["rows"]), config, pricing, old, protocol


def initialize(
    approval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any], dict[str, Any]]:
    loaded = load(approval)
    p.seal(
        LEDGER / "ledger-header.json",
        dict(
            version="p024-completion-ledger-v1",
            scope="FINAL_300_LLM_CONTINUATION_2",
            logical_requests=55,
            plan_fingerprint=io.read_seal(ROOT / "plan-freeze.json")["fingerprint"],
        ),
    )
    p.seal(LEDGER / "approval.json", approval)
    return loaded


def segment_state(
    manifest: dict[str, Any], config: dict[str, Any], pricing: PricingAssumption
) -> dict[str, Any]:
    header = io.read_seal(LEDGER / "ledger-header.json")
    expected = dict(
        version="p024-completion-ledger-v1",
        scope="FINAL_300_LLM_CONTINUATION_2",
        logical_requests=55,
        plan_fingerprint=io.read_seal(ROOT / "plan-freeze.json")["fingerprint"],
    )
    if header != expected | {"fingerprint": digest(expected)}:
        raise io.ReviewBlocked("P024_COMPLETION_LEDGER_SCOPE_DRIFT")
    state = core.ledger_state(LEDGER, manifest, config, pricing)
    ordered = [r["request_id"] for r in manifest["rows"]]
    attempted = [rid for rid in ordered if state["attempts"][rid]]
    if attempted != ordered[: len(attempted)] or any(
        rid not in state["accepted"] for rid in attempted[:-1]
    ):
        raise io.ReviewBlocked("P024_COMPLETION_SERIAL_PREFIX_DRIFT")
    starts = [state["attempts"][rid][0]["timestamp"] for rid in attempted]
    if starts != sorted(starts):
        raise io.ReviewBlocked("P024_COMPLETION_CHRONOLOGY_DRIFT")
    return state


def guard_request(
    rid: str, manifest: dict[str, Any], old: dict[str, Any], new: dict[str, Any]
) -> None:
    if (
        rid not in {r["request_id"] for r in manifest["rows"]}
        or old["attempts"].get(rid)
        or rid in old["accepted"]
        or rid in new["accepted"]
    ):
        raise PermissionError("P024_COMPLETION_PRIOR_OR_ACCEPTED_REQUEST_PROHIBITED")
    h = new["attempts"][rid]
    if h:
        last = io.read_seal(LEDGER / f"{h[-1]['prefix']}.outcome.json")
        if last["state"] != "TECHNICAL_FAILED" or len(h) >= 3:
            raise PermissionError("P024_COMPLETION_TERMINAL_OR_EXHAUSTED_REQUEST_PROHIBITED")


def operational(new: dict[str, Any], old: dict[str, Any], reason: str) -> dict[str, Any]:
    result = core.operational(new, reason)
    result.update(
        logical_requests=55,
        missing=55 - len(new["accepted"]),
        previously_accepted=243,
        total_accepted=243 + len(new["accepted"]),
        historical_technical_missing=2,
        total_provider_invocations=245 + new["provider_invocations"],
        estimated_or_reserved_usd=str(old["exposure"] + new["exposure"]),
        historical_uncertain_reserved_usd=str(RESERVE),
    )
    return result


def durable_intent(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    intent = io.append_seal(path, payload)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return intent


def execute(
    approval: dict[str, Any], transport: e.Transport, decoder: e.Decoder | None = None
) -> dict[str, Any]:
    manifest, config, pricing, old, protocol = initialize(approval)
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
                        and all(
                            (LEDGER / f"{pending['prefix']}.{s}").exists()
                            for s in ("raw", "capture.json")
                        )
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
                if exposure + RESERVE > CAP:
                    return operational(new, old, "PAID_CAP_REACHED")
                payload = e.ROOT / "payloads" / f"{rid}.json"
                frozen = io.read_seal(e.ROOT / "bundle-freeze.json")
                if io.sha(payload) != frozen["files"][f"payloads/{rid}.json"]:
                    raise io.ReviewBlocked("P024_COMPLETION_REQUEST_BYTE_DRIFT")
                sealed = io.read_seal(payload)
                wire = sealed["wire_payload"]
                if digest(wire) != row["request_fingerprint"]:
                    raise io.ReviewBlocked("P024_COMPLETION_REQUEST_BINDING_DRIFT")
                e.audit_payload(sealed)
                n = len(h) + 1
                prefix = f"attempt-{rid}-{n:02}"
                intent = durable_intent(
                    LEDGER / f"{prefix}.json",
                    dict(
                        prefix=prefix,
                        request_id=rid,
                        execution_id=row["execution_id"],
                        attempt=n,
                        request_fingerprint=row["request_fingerprint"],
                        reserved_usd=str(RESERVE),
                        provider=config["provider"],
                        model=config["model"],
                        processing=config["processing"],
                        timestamp=datetime.now(UTC).isoformat(),
                        recovery_of=h[-1]["fingerprint"] if h else None,
                        segment="p024-final-live-completion-v1",
                        global_logical_state="NEVER_EXECUTED" if n == 1 else "TECHNICAL_RETRY",
                        total_stage_reserved_at_intent_usd=str(exposure + RESERVE),
                        segment_c_plan_fingerprint=approval["plan_fingerprint"],
                        segment_c_approval_fingerprint=digest(approval),
                        allowlist_fingerprint=protocol["allowlist_fingerprint"],
                        original_request_manifest_fingerprint=e.REQUEST_FP,
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
                assessments=[new["accepted"][r["request_id"]] for r in manifest["rows"]],
                accepted=55,
                duplicates=0,
            ),
        )
        return operational(new, old, "COMPLETE")


def composite_rows(
    manifest: dict[str, Any], old: dict[str, Any], new: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = manifest["rows"]
    allowed = {r["request_id"] for r in rows[245:]}
    if (
        len(rows) != 300
        or len(old["accepted"]) != 243
        or not set(new["accepted"]).issubset(allowed)
        or set(old["accepted"]) & set(new["accepted"])
    ):
        raise io.ReviewBlocked("P024_COMPLETION_COMPOSITE_SCOPE_DRIFT")
    accepted = old["accepted"] | new["accepted"]
    results = {r["attempt_fingerprint"]: r for r in new["results"]}
    statuses = []
    for pos, row in enumerate(rows):
        rid = row["request_id"]
        value = dict(request_id=rid, execution_id=row["execution_id"])
        if rid in accepted:
            assessment = accepted[rid]["assessment"]
            if assessment["request_id"] != rid:
                raise io.ReviewBlocked("P024_COMPLETION_COMPOSITE_ID_DRIFT")
            value.update(
                llm_evidence_status="ACCEPTED",
                llm_technical_missing=False,
                semantic_decision=assessment["decision"],
            )
        else:
            h = new["attempts"].get(rid, [])
            result = results.get(h[-1]["fingerprint"]) if h else None
            status = {
                74: "TERMINAL_INVALID_REQUEST_ID_MISMATCH",
                244: "AMBIGUOUS_TRANSPORT_NO_CAPTURE",
            }.get(
                pos,
                "NEVER_EXECUTED"
                if not h
                else (result["state"] if result else "AMBIGUOUS_TRANSPORT"),
            )
            value.update(
                llm_evidence_status=status, llm_technical_missing=bool(h) or pos in {74, 244}
            )
        statuses.append(value)
    return [accepted[r["request_id"]] for r in rows if r["request_id"] in accepted], statuses


def readiness(new: dict[str, Any], statuses: list[dict[str, Any]]) -> bool:
    counts = Counter(r["llm_evidence_status"] for r in statuses)
    return (
        len(statuses) == 300
        and counts
        == {
            "ACCEPTED": 298,
            "TERMINAL_INVALID_REQUEST_ID_MISMATCH": 1,
            "AMBIGUOUS_TRANSPORT_NO_CAPTURE": 1,
        }
        and len(new["accepted"]) == 55
        and sum(bool(h) for h in new["attempts"].values()) == 55
        and not new["ambiguous"]
        and all(r["state"] in {"ACCEPTED", "TECHNICAL_FAILED"} for r in new["results"])
    )


def freeze(approval: dict[str, Any]) -> dict[str, Any]:
    """Idempotent offline derivation; immutable raw audit timestamps are not regenerated."""
    from archguard.infrastructure.component_holdout import public_privacy

    with (LEDGER / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with p.offline_scope():
            model = p.model_gate()
        with c.scope(READS, (FREEZE, COMPOSITE)):
            suffix, config, pricing, old, protocol = load(approval)
            new = segment_state(suffix, config, pricing)
            if digest(model) != protocol["model_lock_fingerprint"]:
                raise io.ReviewBlocked("P024_COMPLETION_MODEL_DRIFT")
            full = io.read_seal(e.ROOT / "manifest.json")
            assessments, statuses = composite_rows(full, old, new)
            complete = readiness(new, statuses)
            records, retries = usage_records(
                LEDGER,
                suffix["rows"],
                new,
                old["exposure"],
                "segment_c_plan_fingerprint",
                approval["plan_fingerprint"],
            )
            for row in records:
                intent = io.read_seal(
                    LEDGER / f"attempt-{row['request_id']}-{row['attempt']:02}.json"
                )
                if (
                    intent["segment_c_approval_fingerprint"] != digest(approval)
                    or intent["allowlist_fingerprint"] != protocol["allowlist_fingerprint"]
                    or intent["original_request_manifest_fingerprint"] != e.REQUEST_FP
                ):
                    raise io.ReviewBlocked("P024_COMPLETION_INTENT_BINDING_DRIFT")
            known = sum(
                (Decimal(r["known_cost_usd"]) for r in records if r["known_cost_usd"] is not None),
                Decimal(0),
            )
            exposure = old["exposure"] + new["exposure"]
            counts = Counter(r["state"] for r in new["results"])
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
            inventory = {f.name: io.sha(f) for f in LEDGER.iterdir() if f.is_file()}
            parts = {
                "raw-ledger.json": dict(
                    files=inventory, provider_invocations=new["provider_invocations"]
                ),
                "normalized-assessments.json": dict(
                    assessments=[
                        new["accepted"][r["request_id"]]
                        for r in suffix["rows"]
                        if r["request_id"] in new["accepted"]
                    ],
                    accepted=len(new["accepted"]),
                ),
                "usage-ledger.json": dict(
                    records=records,
                    known_estimated_cost_usd=str(known),
                    exposure_usd=str(new["exposure"]),
                    invoice=None,
                ),
                "execution-lineage.json": dict(
                    protocol_fingerprint=protocol["fingerprint"],
                    runtime_head=protocol["runtime_head"],
                    plan_fingerprint=approval["plan_fingerprint"],
                    source_bindings=io.read_seal(ROOT / "source-bindings.json")["files"],
                    model_lock_fingerprint=protocol["model_lock_fingerprint"],
                ),
                "approval-receipt.json": dict(
                    approval_fingerprint=digest(approval), approval=approval
                ),
                "completion-receipt.json": dict(
                    complete=complete,
                    stop_reason=reason,
                    expected=55,
                    attempted=sum(bool(h) for h in new["attempts"].values()),
                    accepted=len(new["accepted"]),
                    unexecuted=sum(not h for h in new["attempts"].values()),
                    provider_invocations=new["provider_invocations"],
                    prior_failures_repeated=False,
                ),
            }
            for name, value in parts.items():
                p.seal(FREEZE / name, value)
            for name, sha in inventory.items():
                target = FREEZE / "ledger" / name
                if target.exists():
                    if io.sha(target) != sha:
                        raise io.ReviewBlocked("P024_COMPLETION_RAW_SNAPSHOT_DRIFT")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with target.open("xb") as stream:
                        stream.write((LEDGER / name).read_bytes())
                    target.chmod(0o600)
            segment = p.seal(
                FREEZE / "freeze-receipt.json",
                dict(
                    files={
                        f.relative_to(FREEZE).as_posix(): io.sha(f)
                        for f in FREEZE.rglob("*")
                        if f.is_file() and f.name != "freeze-receipt.json"
                    },
                    fingerprints={n: io.read_seal(FREEZE / n)["fingerprint"] for n in parts},
                    original_segment_files=inventory,
                    complete=complete,
                ),
            )
            verify_snapshot(FREEZE, segment["fingerprint"], LEDGER)
            totals = {
                key: sum(r[key] or 0 for r in records)
                for key in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens")
            }
            previous = old["public_b"]
            usage = dict(
                a_provider_invocations=75,
                b_provider_invocations=170,
                c_provider_invocations=new["provider_invocations"],
                total_provider_invocations=245 + new["provider_invocations"],
                a_input_tokens=previous["original_input_tokens"],
                a_output_tokens=previous["original_output_tokens"],
                b_input_tokens=previous["continuation_input_tokens"],
                b_output_tokens=previous["continuation_output_tokens"],
                c_input_tokens=totals["input_tokens"],
                c_output_tokens=totals["output_tokens"],
                composite_input_tokens=previous["composite_input_tokens"] + totals["input_tokens"],
                composite_output_tokens=previous["composite_output_tokens"]
                + totals["output_tokens"],
                composite_total_tokens=previous["composite_total_tokens"] + totals["total_tokens"],
                cached_tokens=previous["cached_tokens"] + totals["cached_tokens"],
                usage_unavailable_invocations=previous["usage_missing"]
                + sum(r["known_cost_usd"] is None for r in records),
                pre_c_known_cost_usd=str(old["known_cost"]),
                c_known_cost_usd=str(known),
                total_known_cost_usd=str(old["known_cost"] + known),
                historical_uncertain_reserved_usd=str(RESERVE),
                new_uncertain_reserved_usd=str(new["exposure"] - known),
                total_exposure_usd=str(exposure),
                hard_cap_usd=str(CAP),
                remaining_cap_usd=str(CAP - exposure),
                invoice=None,
            )
            composite_parts = {
                "accepted-assessments.json": dict(
                    assessments=assessments, accepted=len(assessments)
                ),
                "technical-status.json": dict(
                    rows=statuses,
                    logical_requests=300,
                    missing_bindings=protocol["missing_bindings"],
                ),
                "usage.json": usage,
                "lineage.json": dict(
                    a_freeze_fingerprint=protocol["a_freeze_fingerprint"],
                    b_freeze_fingerprint=protocol["b_freeze_fingerprint"],
                    c_freeze_fingerprint=segment["fingerprint"],
                    original_request_manifest_fingerprint=e.REQUEST_FP,
                    p023_registry_fingerprint=e.REGISTRY_FP,
                    model_lock_fingerprint=protocol["model_lock_fingerprint"],
                    final_truth_accessed=False,
                    hybrid_predictions=0,
                ),
            }
            for name, value in composite_parts.items():
                p.seal(COMPOSITE / name, value)
            composite = p.seal(
                COMPOSITE / "freeze-receipt.json",
                dict(
                    files={n: io.sha(COMPOSITE / n) for n in composite_parts},
                    fingerprints={
                        n: io.read_seal(COMPOSITE / n)["fingerprint"] for n in composite_parts
                    },
                    complete=complete,
                    logical_requests=300,
                    accepted=len(assessments),
                ),
            )
            verify_snapshot(COMPOSITE, composite["fingerprint"])
            distribution = Counter(a["assessment"]["decision"] for a in assessments)
            states = Counter(r["llm_evidence_status"] for r in statuses)
            result = dict(
                version="p024-live2-public-acquisition-v1",
                status="P024_LIVE_2_FINAL_CONTINUATION_COMPLETE"
                if complete
                else "P024_LIVE_2_EXECUTION_INCOMPLETE",
                stop_reason=reason,
                next_stage="READY_FOR_P025_FINAL_EVALUATION_WITH_TWO_LLM_MISSING"
                if complete
                else "WAITING_FOR_COORDINATOR_REVIEW",
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                initial_head=HEAD,
                previous_accepted=243,
                previous_unexecuted=55,
                previous_provider_invocations=245,
                c_expected=55,
                c_attempted=sum(bool(h) for h in new["attempts"].values()),
                c_accepted=len(new["accepted"]),
                c_unexecuted=sum(not h for h in new["attempts"].values()),
                c_technical_retries=retries,
                c_schema_invalid=counts["SCHEMA_INVALID"],
                c_request_id_mismatch=counts["REQUEST_ID_MISMATCH"],
                c_ambiguity=len(new["ambiguous"]),
                total_accepted=len(assessments),
                logical_benchmark_cases=300,
                technical_status_counts=dict(states),
                technical_missing=sum(r["llm_technical_missing"] for r in statuses),
                unexecuted=states["NEVER_EXECUTED"],
                accepted_duplicates=0,
                historical_ambiguous_events=1,
                active_unresolved_execution_stops=0 if complete else 1,
                historical_provider_processing_known="UNKNOWN",
                historical_ambiguity_reservation_retained=True,
                existing_failures_repeated=False,
                prior_accepted_repeated=False,
                technical_missing_semantic_decision_used=False,
                decisions={
                    d: distribution[d]
                    for d in (
                        "SUPPORTED",
                        "NOT_SUPPORTED",
                        "INSUFFICIENT_CONTEXT",
                        "NOT_APPLICABLE",
                    )
                },
                **usage,
                cap_increased=False,
                cap_exceeded=exposure > CAP,
                beyond_cap_call=False,
                final_truth_accessed=False,
                final_semantic_truth_accessed=False,
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
                allowlist_count=55,
                allowlist_duplicates=0,
                prior_ids_in_allowlist=0,
                original_relative_order_verified=True,
                a_b_history_preserved=True,
                p025_acquisition_readiness=complete,
                segment_fingerprints=segment["fingerprints"]
                | {
                    "freeze-receipt.json": segment["fingerprint"],
                    "human-approval": digest(approval),
                },
                composite_fingerprints=composite["fingerprints"]
                | {"freeze-receipt.json": composite["fingerprint"]},
                **{
                    k: protocol[k]
                    for k in (
                        "allowlist_fingerprint",
                        "order_fingerprint",
                        "never_executed_proof_fingerprint",
                        "missing_bindings",
                        "a_freeze_fingerprint",
                        "b_freeze_fingerprint",
                        "model_lock_fingerprint",
                        "p023_registry_fingerprint",
                    )
                },
            )
        public = p.seal(PUBLIC, result)
        handoff = p.seal(
            HANDOFF,
            dict(
                version="p025-acquisition-handoff-v2",
                ready=complete,
                acquisition_fingerprint=public["fingerprint"],
                logical_benchmark_cases=300,
                static_graph_evidence_records=300,
                accepted_llm_assessments=len(assessments),
                technical_missing_llm=result["technical_missing"],
                request_id_mismatch_missing=1,
                ambiguous_no_capture_missing=1,
                unexecuted=result["unexecuted"],
                composite_fingerprints=public["composite_fingerprints"],
                model_lock_fingerprint=protocol["model_lock_fingerprint"],
                p023_registry_fingerprint=e.REGISTRY_FP,
                model_configurations=["A1", "A2", "A3", "A4", "A5", "A6", "A7"],
                truth="NOT OPENED",
                final_hybrid_predictions=0,
                final_evaluation="NOT STARTED",
                final_evaluation_authorized=False,
                primary_benchmark_must_remain_300=True,
                available_only_llm_n=298 if complete else len(assessments),
                available_only_metrics_supplemental=True,
                a3_transport_missing_is_nondefinitive_coverage=True,
                llm_semantic_imputation_forbidden=True,
                hybrid_must_use_frozen_missing_feature_behavior=True,
                a1_a2_a4_llm_missingness_irrelevant=True,
                truth_opening_requires_verified_all_freezes=True,
                required_next_stage=public["next_stage"],
            ),
        )
        public_privacy([PUBLIC, HANDOFF])
        return public | {"handoff_fingerprint": handoff["fingerprint"]}
