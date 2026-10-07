"""Verify old freezes; prepare B or accept its explicitly authorized human submission."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_holdout import HoldoutSample
from archguard.infrastructure.semantic_holdout import verify_file_freeze
from archguard.infrastructure.semantic_review_b import (
    freeze_b_submission,
    load_b_bundle,
    prepare_b_handoff,
    verify_b_handoff,
    verify_b_submission_contract,
)

P014 = "f69a544a9b80911a471040b478173bb8bf7f9486"
P015 = "e91e6c13e6cc7dff7b640f9a968e52dd07745f11"
A_CLOSURE = "091bbf1eade51d3c4915624d599c371f8df9df68"
BUNDLE_FP = "e8dd9955c0b3151fbe98d24024d74c09ec0e6d259ae7b49e80d75805629f682a"
A_RECEIPT_FP = "58488f51c3050266ecdc930e8c24814d7d4040ba1101765ed2180d8a1c0ffb08"
B_SOURCE_SHA = "dd3d7d4f97bd088eeca6e9cedbfec6a6d9732d6e05a906863f91df44e757be9f"
EXPECTED_B_COUNTS = {"POSITIVE": 49, "NEGATIVE": 46, "UNCERTAIN": 4, "OUT_OF_SCOPE": 1}
PUBLIC = Path("experiments/semantic-holdout/semantic-positive-holdout-v1")
PRIVATE = Path("experiments/semantic-holdout/private/semantic-positive-holdout-v1")
BUNDLE = PRIVATE / "review/B/bundle-v1.json"
HANDOFF = Path("experiments/semantic-holdout/private/reviewer-b-handoff-v1")
SUBMISSIONS = Path("experiments/semantic-holdout/private/reviewer-b-submissions-v1")
A_RECEIPT = Path(
    "experiments/semantic-holdout/private/reviewer-a-submissions-v1/"
    "frozen-v1/submission-freeze-v1.json"
)
OLD_PATHS = (
    "experiments/oss",
    "experiments/ai",
    "experiments/preflight",
    "experiments/pricing",
    "experiments/calibration",
    "experiments/results",
)


def verify_baseline():
    for commit in (P014, P015, A_CLOSURE):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    if subprocess.check_output(
        ["git", "diff", P015, "--name-only", "--", *OLD_PATHS, str(PUBLIC)], text=True
    ):
        raise ValueError("prior experiment artifacts changed")
    freeze = json.loads((PUBLIC / "sample-freeze-v1.json").read_bytes())
    private_freeze = json.loads((PRIVATE / "private-freeze-v1.json").read_bytes())
    verify_file_freeze(PUBLIC, freeze)
    verify_file_freeze(PRIVATE, private_freeze)
    if private_freeze["fingerprint"] != freeze["private_freeze_fingerprint"]:
        raise ValueError("private inventory fingerprint mismatch")
    sample = HoldoutSample.model_validate_json((PUBLIC / "sample-v1.json").read_bytes())
    if Counter(p.language for p in sample.cases) != {"JAVA": 50, "TYPESCRIPT": 50}:
        raise ValueError("language counts changed")
    if Counter(p.rule_id for p in sample.cases) != {f"ARCH20{i}": 20 for i in range(1, 6)}:
        raise ValueError("rule counts changed")
    if Counter(p.technical_status for p in sample.cases) != {"VALID": 100}:
        raise ValueError("technical counts changed")
    if freeze["matched_pairs"] != 50 or freeze["human_labels"] != "NONE":
        raise ValueError("frozen cohort/truth state changed")
    bundle = load_b_bundle(BUNDLE, BUNDLE_FP)
    if {p.blinded_id: p.fingerprint for p in bundle.packets} != {
        p.blinded_id: p.packet_fingerprint for p in sample.cases
    }:
        raise ValueError("B cases differ from frozen sample")
    receipt = json.loads(A_RECEIPT.read_bytes())
    if (
        receipt["fingerprint"] != A_RECEIPT_FP
        or digest({k: v for k, v in receipt.items() if k != "fingerprint"}) != A_RECEIPT_FP
    ):
        raise ValueError("A source-free acceptance receipt changed")
    if receipt["reviewer_slot"] != "A" or receipt["final_ground_truth"] is not False:
        raise ValueError("A acceptance scope changed")
    if receipt["submission_sha256"] != (
        "b6d231701aa727966481868c51cf43261dcd5c799d6b4c430cbdbf77eff3973e"
    ):
        raise ValueError("A acceptance source SHA metadata changed")
    for path in (HANDOFF, SUBMISSIONS):
        if subprocess.run(["git", "check-ignore", "-q", str(path / "private.json")]).returncode:
            raise ValueError("private B handoff/submissions must be Git ignored")
    return freeze


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--accept-completed", action="store_true")
    args = parser.parse_args()
    if args.prepare and args.accept_completed:
        parser.error("handoff preparation and acceptance are separate actions")
    if args.accept_completed:
        source = SUBMISSIONS / "completed-response.json"
        actual_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual_sha != B_SOURCE_SHA:
            raise SystemExit("B_SUBMISSION_SHA256_MISMATCH: " + actual_sha)
    freeze = verify_baseline()
    if args.accept_completed:
        handoff_fp = verify_b_submission_contract(HANDOFF, BUNDLE_FP)
        audit = json.loads(
            Path(
                "experiments/semantic-holdout/reviewer-b-handoff-verification-v1.json"
            ).read_bytes()
        )
        if audit["fingerprint"] != digest({k: v for k, v in audit.items() if k != "fingerprint"}):
            raise ValueError("B handoff public audit seal changed")
        if handoff_fp != audit["handoff_fingerprint"]:
            raise ValueError("B handoff freeze changed")
        fingerprint = freeze_b_submission(
            BUNDLE,
            BUNDLE_FP,
            source,
            SUBMISSIONS / "frozen-v1",
            expected_sha256=B_SOURCE_SHA,
            expected_counts=EXPECTED_B_COUNTS,
            lineage={
                "p015_commit": P015,
                "A_workflow_closure_commit": A_CLOSURE,
                "corpus_fingerprint": freeze["corpus_fingerprint"],
                "sample_fingerprint": freeze["sample_fingerprint"],
                "sample_freeze_fingerprint": freeze["fingerprint"],
                "B_handoff_freeze_fingerprint": handoff_fp,
            },
        )
        verify_baseline()
        receipt = json.loads((SUBMISSIONS / "frozen-v1/submission-freeze-v1.json").read_bytes())
        if receipt["fingerprint"] != digest(
            {k: v for k, v in receipt.items() if k != "fingerprint"}
        ):
            raise ValueError("B acceptance receipt seal mismatch")
        if hashlib.sha256(source.read_bytes()).hexdigest() != B_SOURCE_SHA:
            raise ValueError("B human source changed after validation")
        if (SUBMISSIONS / "frozen-v1/submission-v1.json").read_bytes() != source.read_bytes():
            raise ValueError("B snapshot differs from human source")
        print(
            json.dumps(
                {
                    "status": "REVIEWER_B_FROZEN",
                    "next_state": "READY_FOR_INTER_REVIEWER_AGREEMENT",
                    "submission_sha256": B_SOURCE_SHA,
                    "submission_fingerprint": fingerprint,
                    "acceptance_receipt_fingerprint": receipt["fingerprint"],
                    "responses": receipt["responses"],
                    "decision_counts": receipt["decision_counts"],
                    "human_content_modified": False,
                    "snapshot_byte_identical": True,
                    "A_freeze_unchanged": True,
                    "old_freezes_unchanged": True,
                    "final_ground_truth": False,
                    "live_ai_calls": 0,
                    "agreement_performed": False,
                    "adjudication_performed": False,
                },
                sort_keys=True,
            )
        )
        return
    if SUBMISSIONS.exists() and (SUBMISSIONS.is_symlink() or list(SUBMISSIONS.iterdir())):
        raise ValueError("B submission destination must be empty; no acceptance authorized")
    if args.prepare:
        prepare_b_handoff(BUNDLE, BUNDLE_FP, HANDOFF)
        SUBMISSIONS.mkdir(mode=0o700, parents=True, exist_ok=True)
        SUBMISSIONS.chmod(0o700)
    handoff_fp = verify_b_handoff(BUNDLE, BUNDLE_FP, HANDOFF)
    if not SUBMISSIONS.is_dir() or list(SUBMISSIONS.iterdir()):
        raise ValueError("private B submission destination not ready/empty")
    verify_baseline()
    report = {
        "schema_version": "reviewer-b-handoff-verification-v1",
        "status": "WAITING_FOR_REVIEWER_B",
        "A_closure_commit": A_CLOSURE,
        "A_closure_push": "SUCCESS_NORMAL_ORIGIN_MAIN",
        "A_freeze_valid": True,
        "A_receipt_only_no_answers_consumed": True,
        "A_final_ground_truth": False,
        "bundle_fingerprint": BUNDLE_FP,
        "handoff_fingerprint": handoff_fp,
        "case_count": 100,
        "unique_blinded_ids": 100,
        "matched_pairs": 50,
        "language_counts": {"JAVA": 50, "TYPESCRIPT": 50},
        "rule_counts": {f"ARCH20{i}": 20 for i in range(1, 6)},
        "technical_counts": {"VALID": 100, "PARTIAL": 0, "INVALID": 0},
        "missing_cases": 0,
        "extra_cases": 0,
        "duplicate_ids": 0,
        "prepopulated_decisions": 0,
        "prepopulated_rationales": 0,
        "prepopulated_evidence": 0,
        "A_to_B_leakage_findings": 0,
        "construction_leakage_findings": 0,
        "prediction_leakage_findings": 0,
        "human_B_labels_collected": 0,
        "B_accepted": False,
        "live_ai_calls": 0,
        "old_freezes_unchanged": True,
        "sample_freeze_fingerprint": freeze["fingerprint"],
        "identity_verification": "NONE; future identity/distinct-person/independence self-declared",
        "handoff_path": str(HANDOFF),
        "open_first": str(HANDOFF / "README.txt"),
        "response_template": str(HANDOFF / "response-template.json"),
        "return_path": str(SUBMISSIONS / "completed-response.json"),
    }
    report["fingerprint"] = digest(report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_B_BLOCKED: validation failed; no B acceptance performed"
        ) from None
