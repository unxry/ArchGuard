"""Freeze a blank third-human package; no submission acceptance or truth execution."""

import argparse
import hashlib
import json
import secrets
import subprocess
import sys
from pathlib import Path

from prompt015c_agreement import (
    COHORT,
    PRIVATE,
    verify_baseline,
)
from prompt015c_agreement import (
    PRIVATE_OUTPUT as CONFLICT_ROOT,
)
from prompt015c_agreement import (
    PUBLIC_OUTPUT as AGREEMENT_ROOT,
)

from archguard.benchmark.oss.models import digest
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication import (
    build_adjudicator_material,
    freeze_adjudicator_handoff,
    handoff_receipt,
    verify_adjudicator_handoff,
    verify_conflict_inputs,
)

C_CLOSURE = "088916a6b57e8c75c8d2753b7e6120cf925ddcf5"
EXPECTED = {
    "conflicts": "47926ff2491a73194037a2f954b2ae01dfbcf972fb065ae3d2cf67b7a26d2189",
    "index": "fb52bcde381fe4ba3357d18011bcca2c68b072ec5089edb55d8c989e793935db",
    "analysis": "13cc5a8975ef3e553ae4d729ab81fdaae5fcce818df82d527fd2563dd06a5389",
    "receipt": "d31d8237aca9b93a9aacf5baa6661dda83411da38f478e141ec3a1e7d52411ff",
}
HANDOFF = PRIVATE / "adjudicator-handoff-v1"
COORDINATOR = PRIVATE / "adjudicator-coordinator-v1"
SUBMISSIONS = PRIVATE / "adjudicator-submissions-v1"
PUBLIC_RECEIPT = Path("experiments/semantic-holdout/adjudicator-handoff-verification-v1.json")


def verify_inputs():
    subprocess.run(["git", "merge-base", "--is-ancestor", C_CLOSURE, "HEAD"], check=True)
    sample, lineage = verify_baseline()
    if subprocess.check_output(
        ["git", "diff", C_CLOSURE, "--name-only", "--", str(AGREEMENT_ROOT)]
    ):
        raise ValueError("published C freeze changed")
    verify_conflict_inputs(
        CONFLICT_ROOT / "conflict-manifest-v1.json",
        CONFLICT_ROOT / "adjudicator-safe-index-v1.json",
        AGREEMENT_ROOT / "agreement-analysis-v1.json",
        AGREEMENT_ROOT / "agreement-verification-v1.json",
        EXPECTED,
    )
    result = subprocess.run(
        [sys.executable, "scripts/prompt015c_agreement.py", "--verify"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError("C frozen-artifact verification failed")
    guidance = json.loads((COHORT / "reviewer-guidance-v1.json").read_bytes())
    if guidance["fingerprint"] != digest({k: v for k, v in guidance.items() if k != "fingerprint"}):
        raise ValueError("original frozen guidance changed")
    if SUBMISSIONS.exists() and (
        SUBMISSIONS.is_symlink() or not SUBMISSIONS.is_dir() or list(SUBMISSIONS.iterdir())
    ):
        raise ValueError("adjudicator return destination must contain no human answer")
    for path in (HANDOFF, COORDINATOR, SUBMISSIONS):
        subprocess.run(["git", "check-ignore", "-q", str(path / "private.json")], check=True)
    return sample.fingerprint, guidance["fingerprint"], lineage


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    sample_fp, guidance_fp, lineage = verify_inputs()
    if args.prepare:
        if any(
            path.exists() or path.is_symlink() for path in (HANDOFF, COORDINATOR, PUBLIC_RECEIPT)
        ):
            raise ValueError("existing adjudicator freeze cannot be overwritten")
        seed = secrets.token_bytes(32)
    else:
        mapping_path = COORDINATOR / "adjudicator-mapping-v1.json"
        if COORDINATOR.is_symlink() or mapping_path.is_symlink():
            raise ValueError("private blinding freeze cannot be symlinked")
        stored = json.loads(mapping_path.read_bytes())
        if stored["fingerprint"] != digest({k: v for k, v in stored.items() if k != "fingerprint"}):
            raise ValueError("private blinding/mapping seal mismatch")
        seed = bytes.fromhex(stored["private_blinding_key_hex"])
    bundle, mapping, contents = build_adjudicator_material(
        CONFLICT_ROOT / "adjudicator-safe-index-v1.json",
        COHORT / "sample-v1.json",
        PRIVATE / "semantic-positive-holdout-v1/packets",
        COHORT / "reviewer-guidance-v1.json",
        seed,
        expected_index_fingerprint=EXPECTED["index"],
        expected_sample_fingerprint=sample_fp,
        expected_guidance_fingerprint=guidance_fp,
    )
    receipt = handoff_receipt(bundle, contents)
    if args.prepare:
        freeze_adjudicator_handoff(HANDOFF, COORDINATOR, bundle, mapping, contents)
        SUBMISSIONS.mkdir(mode=0o700, parents=True, exist_ok=True)
        SUBMISSIONS.chmod(0o700)
    verify_adjudicator_handoff(HANDOFF, COORDINATOR, mapping, contents, receipt)
    verify_inputs()
    report = {
        "schema_version": "adjudicator-handoff-verification-v1",
        "status": "WAITING_FOR_ADJUDICATOR",
        "ground_truth_status": "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN",
        "C_input_verification": "PASS",
        "C_closure_commit": C_CLOSURE,
        "conflict_manifest_fingerprint": EXPECTED["conflicts"],
        "safe_index_fingerprint": EXPECTED["index"],
        "agreement_analysis_fingerprint": EXPECTED["analysis"],
        "source_lineage": lineage,
        "conflict_count": 4,
        "package_case_count": 4,
        "unique_adjudicator_ids": 4,
        "prepopulated_decisions": 0,
        "prepopulated_rationales": 0,
        "prepopulated_evidence": 0,
        "prepopulated_notes": 0,
        "A_B_category_leakage_findings": 0,
        "A_B_rationale_note_evidence_leakage_findings": 0,
        "construction_leakage_findings": 0,
        "model_detector_leakage_findings": 0,
        "package_fingerprint": receipt["fingerprint"],
        "bundle_fingerprint": bundle.fingerprint,
        "blank_template_fingerprint": hashlib.sha256(
            contents["response-template.json"]
        ).hexdigest(),
        "private_mapping_fingerprint": mapping["fingerprint"],
        "guidance_fingerprint": guidance_fp,
        "guidance_byte_identical": True,
        "source_evidence_unchanged": True,
        "old_freezes_unchanged": True,
        "human_answers_collected": 0,
        "adjudication_accepted": False,
        "final_ground_truth_materialized": False,
        "live_ai_calls": 0,
        "structural_v2_run": False,
        "hybrid_run": False,
        "semantic_effectiveness_metrics_run": False,
        "prompt015e_started": False,
        "prompt016_started": False,
        "identity_verification": "FUTURE_SELF_DECLARATION_ONLY",
        "handoff_directory": str(HANDOFF),
        "open_first": str(HANDOFF / "README.txt"),
        "completed_response_destination": str(SUBMISSIONS / "completed-response.json"),
    }
    report["fingerprint"] = digest(report)
    if args.prepare:
        write_new(PUBLIC_RECEIPT, report)
    elif json.loads(PUBLIC_RECEIPT.read_bytes()) != report:
        raise ValueError("public adjudicator verification receipt changed")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_D_BLOCKED: approved frozen-input/handoff verification failed"
        ) from None
