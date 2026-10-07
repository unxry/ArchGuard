"""Prepare the frozen A handoff; import only subsequently supplied human answers."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_holdout import HoldoutSample
from archguard.infrastructure.semantic_holdout import verify_file_freeze
from archguard.infrastructure.semantic_review import (
    freeze_submission,
    load_bundle,
    prepare_handoff,
    verify_handoff,
    verify_submission_contract,
)

P014 = "f69a544a9b80911a471040b478173bb8bf7f9486"
P015 = "e91e6c13e6cc7dff7b640f9a968e52dd07745f11"
BUNDLE_FP = "54069d685872195aafa91692d4184d4790655915da8ac4ef18d61620794c6151"
PUBLIC = Path("experiments/semantic-holdout/semantic-positive-holdout-v1")
PRIVATE = Path("experiments/semantic-holdout/private/semantic-positive-holdout-v1")
HANDOFF = Path("experiments/semantic-holdout/private/reviewer-a-handoff-v1")
SUBMISSIONS = Path("experiments/semantic-holdout/private/reviewer-a-submissions-v1")
SUBMITTED_SHA256 = "b6d231701aa727966481868c51cf43261dcd5c799d6b4c430cbdbf77eff3973e"
EXPECTED_COUNTS = {"POSITIVE": 52, "NEGATIVE": 43, "UNCERTAIN": 4, "OUT_OF_SCOPE": 1}
OLD_PATHS = (
    "experiments/oss",
    "experiments/ai",
    "experiments/preflight",
    "experiments/pricing",
    "experiments/calibration",
    "experiments/results",
)


def verify_baseline():
    for commit in (P014, P015):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    if subprocess.check_output(
        ["git", "diff", P015, "--name-only", "--", *OLD_PATHS, str(PUBLIC)], text=True
    ):
        raise ValueError("P013/P014/P015 tracked artifacts changed")
    freeze = json.loads((PUBLIC / "sample-freeze-v1.json").read_bytes())
    private_freeze = json.loads((PRIVATE / "private-freeze-v1.json").read_bytes())
    verify_file_freeze(PUBLIC, freeze)
    verify_file_freeze(PRIVATE, private_freeze)
    if freeze["private_freeze_fingerprint"] != private_freeze["fingerprint"]:
        raise ValueError("private inventory fingerprint mismatch")
    if freeze["matched_pairs"] != 50 or freeze["human_labels"] != "NONE":
        raise ValueError("frozen cohort/annotation state mismatch")
    sample = HoldoutSample.model_validate_json((PUBLIC / "sample-v1.json").read_bytes())
    if Counter(p.language for p in sample.cases) != {"JAVA": 50, "TYPESCRIPT": 50}:
        raise ValueError("language balance mismatch")
    if Counter(p.rule_id for p in sample.cases) != {f"ARCH20{i}": 20 for i in range(1, 6)}:
        raise ValueError("rule balance mismatch")
    if Counter(p.technical_status for p in sample.cases) != {"VALID": 100}:
        raise ValueError("technical status mismatch")
    bundle = load_bundle(PRIVATE / "review/A/bundle-v1.json", BUNDLE_FP)
    if {p.blinded_id: p.fingerprint for p in bundle.packets} != {
        p.blinded_id: p.packet_fingerprint for p in sample.cases
    }:
        raise ValueError("Reviewer A packets differ from frozen sample")
    for path in (HANDOFF, SUBMISSIONS):
        if subprocess.run(["git", "check-ignore", "-q", str(path / "private.json")]).returncode:
            raise ValueError("private handoff/submissions must be Git ignored")
    return freeze


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--submit", type=Path)
    parser.add_argument("--accept-completed", action="store_true")
    args = parser.parse_args()
    if sum((args.prepare, bool(args.submit), args.accept_completed)) > 1:
        parser.error("prepare, submit and accept-completed are separate actions")
    if args.accept_completed:
        args.submit = SUBMISSIONS / "completed-response.json"
        actual_sha = hashlib.sha256(args.submit.read_bytes()).hexdigest()
        if actual_sha != SUBMITTED_SHA256:
            raise SystemExit("SUBMISSION_SHA256_MISMATCH: " + actual_sha)
    freeze = verify_baseline()
    if args.prepare:
        prepare_handoff(PRIVATE / "review/A/bundle-v1.json", BUNDLE_FP, HANDOFF)
        SUBMISSIONS.mkdir(mode=0o700, parents=True, exist_ok=True)
        SUBMISSIONS.chmod(0o700)
    if args.submit:
        handoff_fp = verify_submission_contract(HANDOFF, BUNDLE_FP)
        expected_handoff = json.loads(
            Path(
                "experiments/semantic-holdout/reviewer-a-handoff-verification-v1.json"
            ).read_bytes()
        )
        if handoff_fp != expected_handoff["handoff_fingerprint"]:
            raise ValueError("original handoff freeze fingerprint changed")
        fingerprint = freeze_submission(
            PRIVATE / "review/A/bundle-v1.json",
            BUNDLE_FP,
            args.submit,
            SUBMISSIONS / "frozen-v1",
            expected_sha256=SUBMITTED_SHA256 if args.accept_completed else None,
            expected_counts=EXPECTED_COUNTS if args.accept_completed else None,
            lineage={
                "p015_commit": P015,
                "corpus_fingerprint": freeze["corpus_fingerprint"],
                "sample_fingerprint": freeze["sample_fingerprint"],
                "sample_freeze_fingerprint": freeze["fingerprint"],
                "handoff_freeze_fingerprint": handoff_fp,
            },
        )
        verify_baseline()
        receipt = json.loads((SUBMISSIONS / "frozen-v1/submission-freeze-v1.json").read_bytes())
        if (
            digest({k: v for k, v in receipt.items() if k != "fingerprint"})
            != receipt["fingerprint"]
        ):
            raise ValueError("acceptance receipt fingerprint mismatch")
        if hashlib.sha256(args.submit.read_bytes()).hexdigest() != receipt["submission_sha256"]:
            raise ValueError("human source submission changed after freeze")
        print(
            json.dumps(
                {
                    "status": "REVIEWER_A_FROZEN",
                    "next_state": "READY_FOR_REVIEWER_B_HANDOFF",
                    "submission_fingerprint": fingerprint,
                    "acceptance_receipt_fingerprint": receipt["fingerprint"],
                    "submission_sha256": receipt["submission_sha256"],
                    "decision_counts": receipt["decision_counts"],
                    "responses": receipt["responses"],
                    "live_ai_calls": 0,
                    "old_freezes_unchanged": True,
                },
                sort_keys=True,
            )
        )
        return
    handoff_fp = verify_handoff(HANDOFF, BUNDLE_FP)
    if list(SUBMISSIONS.iterdir()):
        raise ValueError("submission destination is not empty; cannot report zero human answers")
    verify_baseline()
    report = {
        "status": "WAITING_FOR_REVIEWER_A",
        "case_count": 100,
        "matched_pairs": 50,
        "baseline_commits": {"P014": P014, "P015": P015},
        "language_counts": {"JAVA": 50, "TYPESCRIPT": 50},
        "rule_counts": {f"ARCH20{i}": 20 for i in range(1, 6)},
        "technical_counts": {"VALID": 100, "PARTIAL": 0, "INVALID": 0},
        "bundle_fingerprint": BUNDLE_FP,
        "handoff_fingerprint": handoff_fp,
        "sample_freeze_fingerprint": freeze["fingerprint"],
        "corpus_fingerprint": freeze["corpus_fingerprint"],
        "sample_fingerprint": freeze["sample_fingerprint"],
        "prepopulated_answers": 0,
        "human_labels_collected": 0,
        "live_ai_calls": 0,
        "frozen_artifacts_unchanged": True,
        "leakage_audit": "PASS",
        "identity_verification": "NONE; future human identity/attestation self-declared only",
        "handoff_path": str(HANDOFF),
        "return_path": str(SUBMISSIONS / "completed-response.json"),
        "submission_freeze_path": str(SUBMISSIONS / "frozen-v1"),
    }
    report["fingerprint"] = digest(report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_A_BLOCKED: validation failed; no human answers imported"
        ) from None
