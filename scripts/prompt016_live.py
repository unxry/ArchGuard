"""Authorized blind P016 execution. No evaluator, human decision parser or identity map."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.llm_provider import AIProviderSettings
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_positive_execution import (
    ExecutionBindings,
    PaidApproval,
    _artifact,
    blind_io,
    execute_future,
    load_execution,
    verify_assessments,
)
from archguard.infrastructure.semantic_positive_live import (
    OpenAIPositiveTransport,
    freeze_live,
    operational_report,
)
from archguard.infrastructure.semantic_positive_offline import audit_metadata

BASE = Path("experiments/semantic-holdout")
ROOT = BASE / "private/p016-execution-v1"
LEDGER = BASE / "private/p016-live-v1"
PUBLIC = BASE / "p016-live-verification-v1.json"
PRICING = Path("experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json")
TRUTH = BASE / "private/final-human-ground-truth-v1"
BINDINGS = ExecutionBindings(
    execution_freeze_fingerprint="086244727c8240a4b7f7fec8f6f58a5a7661476be78cdbe973f81d344e90a57d",
    protocol_fingerprint="1263e3129c8f60b5c938240af52de91fd786bb6d9738f89689ca185f03344011",
    context_manifest_fingerprint="812c5f0e282bb5a8b19b3acb4ed35ba88a77a20e12855036b1c7d48621641fdc",
    request_manifest_fingerprint="ec83ee1485a1275846b7c14ecfafad9db4749f0ca15e06d633d6ee9254c071b5",
    truth_fingerprint="1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276",
)
FILES = {
    "execution-cases.json": "835416078ae2739b8ed016ebc6e1e3fd2b9bf10fed3c21fbb7319e5753aae420",
    "prompt-schema.json": "e1cbd3604299b7423966a90f5441a639484e480b5b467798eed74a8aad9e338b",
    "strategy-config.json": "d161290904e511fe0e9facef7e1307e3086845d3df0a6fda33e8c5d9c2dec784",
    "analysis-plan.json": "8659f3683603e60218e8baf2d14104f50b86d722caf4d491770e199614739bf5",
}
INTENDED = {
    "scripts/prompt016_live.py",
    "src/archguard/infrastructure/semantic_positive_execution.py",
    "src/archguard/infrastructure/semantic_positive_live.py",
    "tests/intelligence/test_semantic_positive_execution.py",
    "tests/intelligence/test_semantic_positive_live.py",
    "docs/verification/PROMPT_016_LIVE.md",
    PUBLIC.as_posix(),
}


def repository_gate():
    for commit in (
        "c4e2ed358568e8b0992f8cc3838e688443bbfb5d",
        "08082d793d5962cee1bdc51dccc54ca79ac46bfd",
    ):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    if subprocess.check_output(["git", "branch", "--show-current"], text=True).strip() != "main":
        raise ValueError("P016_LIVE_BLOCKED_REPOSITORY_DRIFT")
    changes = subprocess.check_output(["git", "diff", "HEAD", "--name-only", "-z"])
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"])
    paths = {p.decode() for p in (changes + untracked).split(b"\0") if p}
    if not paths <= INTENDED:
        raise ValueError("P016_LIVE_BLOCKED_REPOSITORY_DRIFT")
    for path in (ROOT, LEDGER, Path(".env.ai.local")):
        subprocess.run(["git", "check-ignore", "-q", str(path)], check=True)


def opaque_truth_gate():
    # Separate coordinator process hashes opaque truth bytes, never parses case decisions.
    code = """
import hashlib
from pathlib import Path
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
p=Path("experiments/semantic-holdout/private/final-human-ground-truth-v1")
assert not p.is_symlink() and not any(x.is_symlink() for x in p.iterdir())
assert {x.name for x in p.iterdir()}=={"ground-truth-v1.json","ground-truth-freeze-v1.json"}
sha=hashlib.sha256((p/"ground-truth-v1.json").read_bytes()).hexdigest()
assert sha=="db4872615247e856d416e76653d0396a3aee1c430b5fdd8de33bc5e39afabfd1"
verify_opaque_seal(p/"ground-truth-freeze-v1.json","3e8596e27f968df9ed6ca3a74d9592d53409da1f1bfa624852077c63ed0da62d")
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)


def frozen_gate():
    protocol, rows = load_execution(ROOT, BINDINGS)
    for name, fp in FILES.items():
        if digest(json.loads((ROOT / name).read_bytes())) != fp:
            raise ValueError("P016_LIVE_BLOCKED_FROZEN_INPUT_DRIFT")
    verify_opaque_seal(
        BASE / "p016-offline-v1/verification-v1.json",
        "a9ac2b5f1ffe8946c76bd1bfcdeae135324adf212a8b912ea63ab279487bc4ca",
    )
    verify_opaque_seal(
        BASE / "p016-offline-safety-verification-v1.json",
        "f404069244c612c376194fa8a3808dd3361626082712d48cb412ac0aa0c25220",
    )
    pricing = PricingAssumption.model_validate_json(PRICING.read_bytes())
    if pricing.fingerprint != "2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b":
        raise ValueError("P016_LIVE_BLOCKED_FROZEN_INPUT_DRIFT")
    with blind_io(ROOT, LEDGER):
        for row in rows:
            _artifact(ROOT, row, protocol)
        for denied in (
            TRUTH / "ground-truth-v1.json",
            BASE / "private/p016-coordinator-v1/identity-map.json",
            BASE / "private/reviewer-a/decisions.json",
            BASE / "private/reviewer-b/decisions.json",
            BASE / "private/adjudicator/decisions.json",
            BASE / "private/construction/intent.json",
            Path("experiments/ai/semantic-context-live-v1/assessment-freeze.json"),
            Path("experiments/v2/results.json"),
            Path("experiments/hybrid/results.json"),
        ):
            try:
                denied.read_bytes()
            except PermissionError:
                pass
            else:
                raise PermissionError("P016_LIVE_BLOCKED_EXECUTOR_BLINDNESS_FAILURE")
    return protocol, rows, pricing


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    repository_gate()
    opaque_truth_gate()
    protocol, rows, pricing = frozen_gate()
    if args.verify:
        public = json.loads(PUBLIC.read_bytes())
        verify_opaque_seal(PUBLIC, public["fingerprint"])
        if public["ai_assessment_ledger_frozen"]:
            verify_assessments(LEDGER, BINDINGS, public["ai_freeze_receipt_fingerprint"])
        else:
            with blind_io(ROOT, LEDGER):
                if LEDGER.is_symlink() or any(p.is_symlink() for p in LEDGER.rglob("*")):
                    raise ValueError("ledger symlinks forbidden")
                snapshot = {
                    p.relative_to(LEDGER).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(LEDGER.rglob("*"))
                    if p.is_file()
                }
            if (LEDGER / "assessment-freeze.json").exists() or digest(snapshot) != public[
                "unfrozen_ledger_snapshot_fingerprint"
            ]:
                raise ValueError("incomplete ledger snapshot drift")
        with blind_io(ROOT, LEDGER):
            report = operational_report(LEDGER, rows)
        if public["operational_statistics"] != report:
            raise ValueError("public live aggregate drift")
        print(
            canonical(
                {
                    "status": "P016_LIVE_FREEZE_VERIFIED"
                    if public["ai_assessment_ledger_frozen"]
                    else "P016_INCOMPLETE_LEDGER_VERIFIED",
                    "logical_requests": 300,
                    "accepted": report["valid_accepted_assessments"],
                    "fingerprint": public["fingerprint"],
                }
            )
        )
        return
    try:
        env = Path(".env.ai.local")
        if env.exists() and (env.is_symlink() or env.stat().st_mode & 0o777 != 0o600):
            raise PermissionError("credential file permissions invalid")
        settings = AIProviderSettings(_env_file=env)
        transport = OpenAIPositiveTransport(settings)
    except Exception:
        raise PermissionError("P016_LIVE_BLOCKED_CREDENTIAL_UNAVAILABLE") from None
    approval = PaidApproval(
        paid_execution_approved=True,
        bindings=BINDINGS,
        spend_cap_usd="4.50",
        truth_lineage_verified_externally=True,
    )
    for name in INTENDED:
        path = Path(name)
        if path.is_file():
            transport.assert_secret_free(path.read_bytes(), actual_key_only=True)
    print(
        canonical(
            {
                "status": "P016_PRE_LIVE_GATES_PASS",
                "logical_requests": len(rows),
                "connectivity_calls": 0,
                "credential_available": True,
                "hard_spend_cap_usd": "4.50",
            }
        ),
        flush=True,
    )

    def checkpoint(value):
        if value["completed_logical"] % 10 == 0:
            for path in LEDGER.rglob("*"):
                if path.is_file():
                    transport.assert_secret_free(path.read_bytes())
            print(canonical(value), flush=True)

    stopped = None
    try:
        result = execute_future(
            ROOT,
            LEDGER,
            BINDINGS,
            approval,
            credential_available=True,
            transport=transport,
            pricing=pricing,
            checkpoint=checkpoint,
        )
        if result["status"] == "SPEND_CAP_STOP":
            stopped = "P016_LIVE_STOPPED_SPEND_CAP"
    except Exception:
        stopped = "P016_LIVE_EXECUTION_INCOMPLETE"
    with blind_io(ROOT, LEDGER):
        report = operational_report(LEDGER, rows)
        for path in LEDGER.rglob("*"):
            if path.is_file():
                transport.assert_secret_free(path.read_bytes())
                if path.suffix == ".json":
                    audit_metadata(json.loads(path.read_bytes()))
    if report["pending_transport_outcomes"]:
        stopped = "P016_LIVE_INCOMPLETE_PENDING_TRANSPORT"
    if stopped or report["valid_accepted_assessments"] != 300:
        print(
            canonical(
                {
                    "status": stopped or "P016_LIVE_EXECUTION_INCOMPLETE",
                    "ai_assessment_ledger_frozen": False,
                    "operational_statistics": report,
                }
            ),
            flush=True,
        )
        return
    frozen = freeze_live(ROOT, LEDGER, BINDINGS)
    verify_assessments(LEDGER, BINDINGS, frozen["ai_freeze_receipt_fingerprint"])
    opaque_truth_gate()
    frozen_gate()
    public = {
        **frozen,
        "schema_version": "p016-live-verification-v1",
        "status": "P016_LIVE_EXECUTION_COMPLETE",
        "next_state": "READY_FOR_P017_EVALUATION",
        "repository_offline_head": "c4e2ed358568e8b0992f8cc3838e688443bbfb5d",
        "repository_prior_truth_head": "08082d793d5962cee1bdc51dccc54ca79ac46bfd",
        "input_fingerprints": {**FILES, **BINDINGS.model_dump()},
        "paid_execution_approved": True,
        "credential_available": True,
        "credential_printed_logged_hashed_copied": False,
        "connectivity_calls": 0,
        "connectivity_result": "SKIPPED_NOT_REQUIRED_BY_FROZEN_PROTOCOL",
        "pricing_assumption_fingerprint": pricing.fingerprint,
        "truth_lineage_verified_opaquely": True,
        "case_level_truth_opened_by_executor": False,
        "human_truth_joined": False,
        "effectiveness_metrics_calculated": False,
        "construction_intent_decoded": False,
        "evaluator_executed": False,
        "p017_started": False,
        "leakage_findings": {"truth": 0, "reviewer": 0, "construction": 0, "v2_hybrid": 0},
        "secrets_persisted": False,
        "request_context_prompt_strategy_drift": 0,
    }
    public["fingerprint"] = digest(public)
    for path in LEDGER.rglob("*"):
        if path.is_file():
            transport.assert_secret_free(path.read_bytes())
    transport.assert_secret_free(canonical(public).encode())
    write_new(PUBLIC, public)
    print(canonical(public), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        safe = (
            str(error)
            if str(error).startswith("P016_LIVE_BLOCKED_")
            else "P016_LIVE_STOPPED_LOCAL_VALIDATION"
        )
        print(canonical({"status": safe, "error_type": type(error).__name__}), flush=True)
        sys.exit(1)
