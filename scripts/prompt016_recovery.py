"""Prospective P016 recovery coordinator. No human decision reader or evaluator invocation."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import prompt016_live as base

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.infrastructure.llm_provider import AIProviderSettings
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_positive_execution import blind_io, verify_assessments
from archguard.infrastructure.semantic_positive_live import OpenAIPositiveTransport
from archguard.infrastructure.semantic_positive_recovery import (
    RecoveryAmendment,
    append_json,
    execute_recovery,
    freeze_recovery,
    history_gate,
    prepare_recovery,
    recovery_report,
)

AMENDMENT = base.BASE / "p016-live-recovery-amendment-v1.json"
AUDIT = base.BASE / "p016-live-recovery-amendment-audit-v1.json"
PUBLIC = base.BASE / "p016-live-recovery-verification-v1.json"
INITIAL_FP = "f951172fd27562e25b5be5b66ea34bc3b88c65a2f49896cc543c8bdd5eaf25ec"
HISTORY_FP = "3e819e9438d53a9b3880aa24693852cce51fab8123653b6463ce55013ddef069"
IMPLEMENTATION = (
    "scripts/prompt016_recovery.py",
    "src/archguard/infrastructure/semantic_positive_recovery.py",
    "src/archguard/infrastructure/semantic_positive_live.py",
)
INTENDED = {
    *IMPLEMENTATION,
    "tests/intelligence/test_semantic_positive_recovery.py",
    "tests/intelligence/test_semantic_positive_live.py",
    "src/archguard/infrastructure/semantic_positive_evaluator.py",
    "docs/verification/PROMPT_016_LIVE_1.md",
    str(AMENDMENT),
    str(AUDIT),
    str(PUBLIC),
}


def amendment(pricing):
    return seal(
        RecoveryAmendment,
        bindings=base.BINDINGS,
        initial_ledger_fingerprint=HISTORY_FP,
        initial_public_verification_fingerprint=INITIAL_FP,
        pricing_fingerprint=pricing.fingerprint,
    )


def gates():
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", "c34ac13caf5e77ffb37ac7417366dd866664c412", "HEAD"],
        check=True,
    )
    base.INTENDED.update(INTENDED)
    base.repository_gate()
    base.opaque_truth_gate()
    protocol, rows, pricing = base.frozen_gate()
    verify_opaque_seal(base.PUBLIC, INITIAL_FP)
    return protocol, rows, pricing


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    protocol, rows, pricing = gates()
    manifest = amendment(pricing)
    if args.prepare:
        prepare_recovery(base.ROOT, base.LEDGER, manifest)
        append_json(AMENDMENT, manifest)
        audit = {
            "schema_version": "p016-recovery-amendment-audit-v1",
            "status": "RECOVERY_AMENDMENT_FROZEN_BEFORE_NEW_CALLS",
            "amendment_fingerprint": manifest.fingerprint,
            "initial_ledger_snapshot_fingerprint": HISTORY_FP,
            "initial_state": {
                "accepted": 106,
                "protocol_invalid": 1,
                "ambiguous_pending": 1,
                "unattempted": 192,
            },
            "frozen_bindings": base.BINDINGS.model_dump(),
            "implementation_sha256": {
                p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in IMPLEMENTATION
            },
            "truth_firewall": "PASS",
            "truth_joined": False,
            "scientific_payload_changed": False,
            "new_provider_calls": 0,
            "credentials_read": False,
            "scientific_limitation": (
                "OPERATIONAL_PROTOCOL_DEVIATION_AFTER_106_ACCEPTED; NO_TRUTH_JOIN; "
                "SAME_SCIENTIFIC_PAYLOAD; POSSIBLE_DUPLICATE_REMOTE_PROCESSING_DISCLOSED"
            ),
        }
        audit["fingerprint"] = digest(audit)
        append_json(AUDIT, audit)
        print(
            canonical(
                {
                    "status": audit["status"],
                    "amendment_fingerprint": manifest.fingerprint,
                    "audit_fingerprint": audit["fingerprint"],
                    "new_provider_calls": 0,
                }
            ),
            flush=True,
        )
        return
    verify_opaque_seal(AMENDMENT, manifest.fingerprint)
    history_gate(base.LEDGER, manifest)
    audit = json.loads(AUDIT.read_bytes())
    verify_opaque_seal(AUDIT, audit["fingerprint"])
    if audit["implementation_sha256"] != {
        p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in IMPLEMENTATION
    }:
        raise ValueError("frozen recovery implementation drift")
    amendment_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(AMENDMENT)], text=True
    ).strip()
    if not amendment_commit:
        raise PermissionError("recovery amendment must be committed before new calls")
    if (
        subprocess.check_output(["git", "show", f"{amendment_commit}:{AMENDMENT}"])
        != AMENDMENT.read_bytes()
    ):
        raise ValueError("amendment commit binding drift")
    if args.verify:
        public = json.loads(PUBLIC.read_bytes())
        verify_opaque_seal(PUBLIC, public["fingerprint"])
        verify_assessments(base.LEDGER, base.BINDINGS, public["ai_freeze_receipt_fingerprint"])
        with blind_io(base.ROOT, base.LEDGER):
            report = recovery_report(base.ROOT, base.LEDGER, manifest, pricing)
        if public["operational_statistics"] != report:
            raise ValueError("recovery aggregate drift")
        print(
            canonical(
                {
                    "status": "P016_COMPLETE_RECOVERY_FREEZE_VERIFIED",
                    "accepted": report["valid_accepted_assessments"],
                    "fingerprint": public["fingerprint"],
                }
            ),
            flush=True,
        )
        return
    if subprocess.check_output(["git", "status", "--porcelain"]):
        raise PermissionError("recovery implementation must be committed with clean working tree")
    try:
        env = Path(".env.ai.local")
        if env.exists() and (env.is_symlink() or env.stat().st_mode & 0o777 != 0o600):
            raise PermissionError("credential file permissions invalid")
        settings = AIProviderSettings(_env_file=env)
        provider = OpenAIPositiveTransport(settings)
    except Exception:
        raise PermissionError("P016_LIVE_BLOCKED_CREDENTIAL_UNAVAILABLE") from None
    for name in INTENDED:
        path = Path(name)
        if path.is_file():
            provider.assert_secret_free(path.read_bytes(), actual_key_only=True)

    def transport(request, protocol, capture):
        return provider(request, protocol, capture_response=capture)

    def decode(raw, metadata, protocol):
        return provider.decode_response(
            raw, metadata, protocol, metadata.get("latency_seconds", 0.0)
        )

    def checkpoint(value):
        if value["accepted"] % 10 == 0 or value["last_class"] != "RESUMED_UNATTEMPTED":
            print(canonical(value), flush=True)

    print(
        canonical(
            {
                "status": "P016_RECOVERY_PRE_LIVE_PASS",
                "amendment_commit": amendment_commit,
                "amendment_fingerprint": manifest.fingerprint,
                "new_provider_calls": 0,
            }
        ),
        flush=True,
    )
    result = (
        {"status": "P016_RECOVERY_COMPLETE_UNFROZEN"}
        if (base.LEDGER / "assessment-freeze.json").exists()
        else execute_recovery(
            base.ROOT,
            base.LEDGER,
            manifest,
            pricing,
            amendment_commit=amendment_commit,
            paid_approved=True,
            credential_available=True,
            transport=transport,
            decode=decode,
            checkpoint=checkpoint,
        )
    )
    with blind_io(base.ROOT, base.LEDGER):
        report = recovery_report(base.ROOT, base.LEDGER, manifest, pricing)
        for p in base.LEDGER.rglob("*"):
            if p.is_file():
                provider.assert_secret_free(p.read_bytes())
    if (
        result["status"] != "P016_RECOVERY_COMPLETE_UNFROZEN"
        or report["valid_accepted_assessments"] != 300
    ):
        print(
            canonical(
                {
                    "status": "P016_LIVE_EXECUTION_INCOMPLETE",
                    "stop_reason": result["status"],
                    "operational_statistics": report,
                }
            ),
            flush=True,
        )
        return
    frozen = freeze_recovery(base.ROOT, base.LEDGER, manifest, pricing)
    verify_assessments(base.LEDGER, base.BINDINGS, frozen["ai_freeze_receipt_fingerprint"])
    gates()
    public = {
        **frozen,
        "schema_version": "p016-complete-recovery-verification-v1",
        "status": "P016_LIVE_EXECUTION_COMPLETE",
        "ai_assessment_ledger_frozen": True,
        "next_state": "READY_FOR_P017_EVALUATION",
        "amendment_commit": amendment_commit,
        "original_incomplete_commit": "c34ac13caf5e77ffb37ac7417366dd866664c412",
        "original_history_snapshot_fingerprint": HISTORY_FP,
        "original_106_accepted_unchanged": True,
        "original_invalid_raw_preserved": True,
        "original_invalid_answer_remapped": False,
        "original_pending_preserved": True,
        "existing_concrete_response_handle_available": False,
        "original_pending_same_response_recovery_used": False,
        "original_pending_replacement_used": True,
        "original_pending_provider_processing": "UNKNOWN",
        "hidden_result_used_for_selection": False,
        "prompt_context_model_changed": False,
        "truth_firewall": "PASS",
        "truth_joined": False,
        "case_level_human_truth_accessed": False,
        "construction_intent_decoded": False,
        "evaluator_executed": False,
        "effectiveness_metrics_calculated": False,
        "p017_started": False,
        "leakage_findings": {"truth": 0, "reviewer": 0, "construction": 0, "v2_hybrid": 0},
        "credentials_printed_logged_hashed_copied": False,
        "secrets_persisted": False,
        "paid_execution_approved": True,
        "hard_spend_cap_usd": "4.50",
        "connectivity_calls": 0,
        "pricing_assumption_fingerprint": pricing.fingerprint,
    }
    public["fingerprint"] = digest(public)
    provider.assert_secret_free(canonical(public).encode())
    append_json(PUBLIC, public)
    print(canonical(public), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            canonical(
                {"status": "P016_LIVE_EXECUTION_INCOMPLETE", "error_type": type(error).__name__}
            ),
            flush=True,
        )
        sys.exit(1)
