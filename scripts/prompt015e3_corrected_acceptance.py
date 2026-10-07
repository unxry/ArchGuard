"""One-time corrected human acceptance; preserve rejected input and correction history."""

import argparse
import json
import subprocess

from prompt015e1_recover_handoff import COORDINATOR, HANDOFF, original_material
from prompt015e_acceptance import (
    EXPECTED,
    EXPECTED_COUNTS,
    FROZEN,
    PUBLIC,
    PUBLIC_RECEIPT,
    SOURCE,
    SOURCE_SHA,
    verify_prerequisites,
)

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication import verify_adjudicator_handoff
from archguard.infrastructure.semantic_adjudication_acceptance import (
    SubmissionMismatch,
    verify_opaque_seal,
)
from archguard.infrastructure.semantic_adjudication_corrected_acceptance import (
    CorrectedAcceptanceBlocked,
    corrected_sha_guard,
    freeze_corrected_adjudication,
    validate_corrected_adjudication,
    verify_frozen_correction_lineage,
)

CORRECTED = SOURCE.parent / "completed-response-corrected-v1.json"
CORRECTED_SHA = "aa87b0b34a69ec660b0e83e0c91d5a379cf4f173ffb492c869b7d7de0157c66d"
ROUND = SOURCE.parent / "corrections-v1/round-1"
CORRECTION_AUDIT = PUBLIC / "adjudicator-correction-verification-v1.json"
CORRECTION = {
    "package": "559537a7892df24eb57e6edf8bdd8936e46eb627da40f2f76c8d09e5ecbfe207",
    "template": "d652de3742d9592a463259876b027fb39481e0ad2ed2686ceff77cfb10f7a533",
    "audit": "d350af5f8ecd5de414516832ab3b9921324e8c8291d354d5dcd534687722fff8",
}


def prerequisites():
    try:
        bundle, lineage = verify_prerequisites()
        mapping, contents, receipt = original_material()
        verify_adjudicator_handoff(HANDOFF, COORDINATOR, mapping, contents, receipt)
        verify_frozen_correction_lineage(
            SOURCE,
            ROUND,
            CORRECTION_AUDIT,
            bundle,
            original_sha=SOURCE_SHA,
            package_fp=EXPECTED["package"],
            expected=CORRECTION,
        )
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_BLOCKED_PREREQUISITE_DRIFT") from None
    return bundle, lineage


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify-correction-round", action="store_true")
    action.add_argument("--validate", action="store_true")
    action.add_argument("--accept-corrected", action="store_true")
    action.add_argument("--verify-accepted", action="store_true")
    args = parser.parse_args()
    corrected_sha_guard(CORRECTED, CORRECTED_SHA)
    bundle, lineage = prerequisites()
    for path in (CORRECTED, FROZEN / "submission-v1.json", FROZEN / "submission-freeze-v1.json"):
        subprocess.run(["git", "check-ignore", "-q", str(path)], check=True)
    if args.verify_correction_round:
        print(
            json.dumps(
                {
                    "correction_round_verification": "PASS",
                    "regenerated": False,
                    "original_rejected_attempt_preserved": True,
                    "C_D_freeze_verification": "PASS",
                    "correction_fingerprints": CORRECTION,
                },
                sort_keys=True,
            )
        )
        return
    parameters = {
        "corrected_sha": CORRECTED_SHA,
        "original_sha": SOURCE_SHA,
        "package_fp": EXPECTED["package"],
        "expected_correction": CORRECTION,
        "expected_counts": EXPECTED_COUNTS,
    }
    raw, submission, counts, scope, correction_lineage = validate_corrected_adjudication(
        CORRECTED, SOURCE, ROUND, CORRECTION_AUDIT, bundle, **parameters
    )
    if args.validate:
        print(
            json.dumps(
                {
                    "corrected_validation": "PASS",
                    "corrected_sha256": CORRECTED_SHA,
                    "submission_fingerprint": digest(submission),
                    "decision_counts": counts,
                    "correction_scope": scope,
                    "snapshot_created": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.accept_corrected:
        if PUBLIC_RECEIPT.exists() or PUBLIC_RECEIPT.is_symlink():
            raise ValueError("public acceptance audit is immutable")
        receipt = freeze_corrected_adjudication(
            CORRECTED,
            SOURCE,
            ROUND,
            CORRECTION_AUDIT,
            FROZEN,
            bundle,
            lineage=lineage,
            **parameters,
        )
        prerequisites()
        public = {k: v for k, v in receipt.items() if k not in {"fingerprint", "schema_version"}}
        public.update(
            schema_version="adjudicator-acceptance-verification-v1",
            acceptance_receipt_fingerprint=receipt["fingerprint"],
            old_freezes_unchanged=True,
        )
        public["fingerprint"] = digest(public)
        write_new(PUBLIC_RECEIPT, public)
    else:
        if (
            FROZEN.is_symlink()
            or (FROZEN / "submission-v1.json").is_symlink()
            or PUBLIC_RECEIPT.is_symlink()
            or {p.name for p in FROZEN.iterdir()}
            != {"submission-v1.json", "submission-freeze-v1.json"}
        ):
            raise ValueError("accepted private inventory changed")
        public = json.loads(PUBLIC_RECEIPT.read_bytes())
        verify_opaque_seal(PUBLIC_RECEIPT, public["fingerprint"])
        receipt = json.loads(
            verify_opaque_seal(
                FROZEN / "submission-freeze-v1.json", public["acceptance_receipt_fingerprint"]
            )
        )
        if (
            (FROZEN / "submission-v1.json").read_bytes() != raw
            or receipt["submission_sha256"] != CORRECTED_SHA
            or receipt["submission_fingerprint"] != digest(submission)
            or receipt["lineage"] != lineage | correction_lineage
            or receipt["decision_counts"] != counts
            or receipt["correction_scope"] != scope
            or receipt["accepted_input"] != "CORRECTED_HUMAN_SUBMISSION"
            or receipt["original_rejected_attempt_preserved"] is not True
            or receipt["final_ground_truth_materialized"] is not False
            or public["old_freezes_unchanged"] is not True
            or {
                k: v
                for k, v in public.items()
                if k
                not in {
                    "fingerprint",
                    "schema_version",
                    "acceptance_receipt_fingerprint",
                    "old_freezes_unchanged",
                }
            }
            != {k: v for k, v in receipt.items() if k not in {"fingerprint", "schema_version"}}
            or PUBLIC_RECEIPT.read_bytes() != (canonical(public) + "\n").encode()
        ):
            raise ValueError("accepted corrected source/lineage/receipt changed")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "next_state": receipt["next_state"],
                "ground_truth_status": receipt["ground_truth_status"],
                "corrected_sha256": CORRECTED_SHA,
                "submission_fingerprint": receipt["submission_fingerprint"],
                "acceptance_receipt_fingerprint": receipt["fingerprint"],
                "public_receipt_fingerprint": public["fingerprint"],
                "responses": 4,
                "unique_ids": 4,
                "missing_cases": 0,
                "extra_cases": 0,
                "duplicate_ids": 0,
                "invalid_evidence_ids": 0,
                "invalid_line_ranges": 0,
                "schema_validation": "PASS",
                "attestation_validation": "PASS",
                "membership_validation": "PASS",
                "decision_counts": counts,
                "correction_scope": scope,
                "human_content_modified": False,
                "snapshot_byte_identical": True,
                "original_rejected_attempt_preserved": True,
                "old_freezes_unchanged": True,
                "construction_intent_compared": False,
                "final_ground_truth_materialized": False,
                "live_ai_calls": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except CorrectedAcceptanceBlocked as error:
        raise SystemExit(str(error)) from None
    except SubmissionMismatch as error:
        raise SystemExit("PROMPT_015_E_3_BLOCKED_FORMAL_VALIDATION: " + str(error)) from None
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_E_3_BLOCKED: formal acceptance/integrity guard failed"
        ) from None
