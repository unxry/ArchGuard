"""Accept only the approved third-human file; no primary judgment decoding or truth merge."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from prompt015c_agreement import EXPECTATIONS, P015, PRIVATE, verify_baseline

from archguard.benchmark.oss.models import digest
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication_acceptance import (
    SubmissionMismatch,
    freeze_completed_adjudication,
    validate_completed_adjudication,
    verify_adjudicator_prerequisites,
    verify_opaque_seal,
    verify_primary_integrity,
)

C_CLOSURE = "088916a6b57e8c75c8d2753b7e6120cf925ddcf5"
D_CLOSURE = "0665c0533e28f63b02a3c4e88ccabe9c0790da90"
SOURCE_SHA = "df749173ff5ea783d4bbf6a582d3394c3eee6361b5abbd55bba874c79bcc9d8f"
EXPECTED_COUNTS = {"POSITIVE": 1, "NEGATIVE": 3, "UNCERTAIN": 0, "OUT_OF_SCOPE": 0}
EXPECTED = {
    "conflicts": "47926ff2491a73194037a2f954b2ae01dfbcf972fb065ae3d2cf67b7a26d2189",
    "index": "fb52bcde381fe4ba3357d18011bcca2c68b072ec5089edb55d8c989e793935db",
    "analysis": "13cc5a8975ef3e553ae4d729ab81fdaae5fcce818df82d527fd2563dd06a5389",
    "c_receipt": "d31d8237aca9b93a9aacf5baa6661dda83411da38f478e141ec3a1e7d52411ff",
    "package": "cec7af09c40b78e6afca5626f87b860a2e591fb6153eea0f0795fad83be488ac",
    "blank": "ba9d11aee3e19c00e255a45d9e4fe67306645928b905ef9db6edd5bd1ad125d1",
    "mapping": "fa0e5c568ca255129bd5e44435e69f48736072f0227b5cbf1e9cf62822e9d24f",
    "d_receipt": "b7b66eeb7905729fe0d0f76cf924974f03cda5852925f6694058bc85506406c5",
    "bundle": "83c9ebd641819381722797232ed1f22401e77a8f5adacc714a90cc65d78ccddd",
}
PUBLIC = Path("experiments/semantic-holdout")
SOURCE = PRIVATE / "adjudicator-submissions-v1/completed-response.json"
FROZEN = SOURCE.parent / "frozen-v1"
PUBLIC_RECEIPT = PUBLIC / "adjudicator-acceptance-verification-v1.json"


def verify_prerequisites():
    for commit in (C_CLOSURE, D_CLOSURE):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    sample, original = verify_baseline()
    protected = [
        PUBLIC / "inter-reviewer-agreement-v1",
        PUBLIC / "adjudicator-handoff-verification-v1.json",
    ]
    protected.extend(
        PUBLIC / name
        for name in (
            "reviewer-a-handoff-verification-v1.json",
            "reviewer-a-acceptance-verification-v1.json",
            "reviewer-b-handoff-verification-v1.json",
            "reviewer-b-acceptance-verification-v1.json",
        )
    )
    if subprocess.check_output(
        ["git", "diff", D_CLOSURE, "--name-only", "--", *(str(p) for p in protected)]
    ):
        raise ValueError("prior public human-review freezes changed")
    for expected in EXPECTATIONS:
        verify_primary_integrity(
            PRIVATE / f"reviewer-{expected.reviewer_slot.lower()}-submissions-v1/frozen-v1",
            source_sha=expected.submission_sha256,
            receipt_fp=expected.acceptance_receipt_fingerprint,
        )
    bundle, lineage = verify_adjudicator_prerequisites(PUBLIC, PRIVATE, EXPECTED)
    lineage.update(
        {
            "p015_commit": P015,
            "C_closure_commit": C_CLOSURE,
            "D_closure_commit": D_CLOSURE,
            "sample_freeze_fingerprint": original["sample_freeze_fingerprint"],
            "corpus_fingerprint": original["corpus_fingerprint"],
            "sample_fingerprint": sample.fingerprint,
            **{
                e.reviewer_slot + "_receipt_fingerprint": e.acceptance_receipt_fingerprint
                for e in EXPECTATIONS
            },
        }
    )
    for path in (SOURCE, FROZEN / "submission-v1.json", FROZEN / "submission-freeze-v1.json"):
        subprocess.run(["git", "check-ignore", "-q", str(path)], check=True)
    return bundle, lineage


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify-prerequisites", action="store_true")
    action.add_argument("--validate", action="store_true")
    action.add_argument("--accept-completed", action="store_true")
    action.add_argument("--verify-accepted", action="store_true")
    args = parser.parse_args()
    actual_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if actual_sha != SOURCE_SHA:
        raise SubmissionMismatch("SUBMITTED_SHA256_MISMATCH: " + actual_sha)
    bundle, lineage = verify_prerequisites()
    if args.verify_prerequisites:
        print(
            json.dumps(
                {
                    "C_freeze_verification": "PASS",
                    "D_freeze_verification": "PASS",
                    "A_B_opaque_integrity": "PASS",
                    "cohort_cases": 100,
                    "conflict_count": 4,
                    "bundle_fingerprint": bundle.fingerprint,
                    "submitted_sha256": actual_sha,
                },
                sort_keys=True,
            )
        )
        return
    if args.accept_completed:
        if PUBLIC_RECEIPT.exists() or PUBLIC_RECEIPT.is_symlink():
            raise ValueError("public acceptance audit immutable; cannot overwrite")
        receipt = freeze_completed_adjudication(
            SOURCE,
            FROZEN,
            bundle,
            expected_sha=SOURCE_SHA,
            expected_counts=EXPECTED_COUNTS,
            lineage=lineage,
        )
        verify_prerequisites()
        public = {k: v for k, v in receipt.items() if k not in {"fingerprint", "schema_version"}}
        public.update(
            schema_version="adjudicator-acceptance-verification-v1",
            acceptance_receipt_fingerprint=receipt["fingerprint"],
            old_freezes_unchanged=True,
        )
        public["fingerprint"] = digest(public)
        write_new(PUBLIC_RECEIPT, public)
    else:
        raw, submission, counts = validate_completed_adjudication(
            SOURCE, bundle, expected_sha=SOURCE_SHA, expected_counts=EXPECTED_COUNTS
        )
        if args.validate:
            print(
                json.dumps(
                    {
                        "submission_validation": "PASS",
                        "bundle_binding_validation": "PASS",
                        "submitted_sha256": SOURCE_SHA,
                        "canonical_submission_fingerprint": digest(submission),
                        "responses": 4,
                        "decision_counts": counts,
                        "snapshot_created": False,
                    },
                    sort_keys=True,
                )
            )
            return
        public = json.loads(PUBLIC_RECEIPT.read_bytes())
        if public["fingerprint"] != digest({k: v for k, v in public.items() if k != "fingerprint"}):
            raise ValueError("public acceptance audit seal changed")
        receipt = json.loads(
            verify_opaque_seal(
                FROZEN / "submission-freeze-v1.json", public["acceptance_receipt_fingerprint"]
            )
        )
        if (
            FROZEN.is_symlink()
            or (FROZEN / "submission-v1.json").is_symlink()
            or PUBLIC_RECEIPT.is_symlink()
            or (FROZEN / "submission-v1.json").read_bytes() != raw
            or receipt["submission_fingerprint"] != digest(submission)
            or receipt["submission_sha256"] != SOURCE_SHA
            or receipt["lineage"] != lineage
            or receipt["decision_counts"] != counts
        ):
            raise ValueError("accepted snapshot/canonical/lineage mismatch")
        if FROZEN.is_symlink() or {p.name for p in FROZEN.iterdir()} != {
            "submission-v1.json",
            "submission-freeze-v1.json",
        }:
            raise ValueError("private acceptance inventory changed")
        if {
            k: v
            for k, v in public.items()
            if k
            not in {
                "fingerprint",
                "schema_version",
                "acceptance_receipt_fingerprint",
                "old_freezes_unchanged",
            }
        } != {k: v for k, v in receipt.items() if k not in {"fingerprint", "schema_version"}}:
            raise ValueError("public audit differs from private source-free receipt")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "next_state": receipt["next_state"],
                "ground_truth_status": receipt["ground_truth_status"],
                "submitted_sha256": SOURCE_SHA,
                "submission_fingerprint": receipt["submission_fingerprint"],
                "acceptance_receipt_fingerprint": receipt["fingerprint"],
                "public_receipt_fingerprint": public["fingerprint"],
                "responses": receipt["responses"],
                "decision_counts": receipt["decision_counts"],
                "human_content_modified": False,
                "snapshot_byte_identical": True,
                "old_freezes_unchanged": True,
                "final_ground_truth_materialized": False,
                "live_ai_calls": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SubmissionMismatch as error:
        raise SystemExit("PROMPT_015_E_BLOCKED: " + str(error)) from None
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_E_BLOCKED: formal frozen-input/submission verification failed"
        ) from None
