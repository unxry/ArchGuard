"""Recover only the approved missing blank; independently verify the original D bytes."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from prompt015c_agreement import COHORT, EXPECTATIONS, PRIVATE, verify_baseline
from prompt015e_acceptance import (
    D_CLOSURE,
    EXPECTED,
    PUBLIC,
    SOURCE,
    SOURCE_SHA,
    verify_prerequisites,
)

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication import (
    build_adjudicator_material,
    handoff_receipt,
    verify_adjudicator_handoff,
)
from archguard.infrastructure.semantic_adjudication_acceptance import (
    HandoffRecoveryBlocked,
    recover_exact_blank,
    verify_opaque_seal,
    verify_primary_integrity,
    verify_recoverable_handoff,
)

HANDOFF = PRIVATE / "adjudicator-handoff-v1"
COORDINATOR = PRIVATE / "adjudicator-coordinator-v1"
AUDIT = PUBLIC / "adjudicator-handoff-recovery-verification-v1.json"
BUILDER_PATHS = (
    "src/archguard/infrastructure/semantic_adjudication.py",
    "src/archguard/benchmark/semantic_adjudication.py",
    "src/archguard/benchmark/semantic_holdout.py",
    "src/archguard/benchmark/semantic_review.py",
    "src/archguard/benchmark/oss/models.py",
    "src/archguard/core/model/base.py",
    "scripts/prompt015d_adjudicator.py",
)


def original_material():
    if subprocess.check_output(["git", "diff", D_CLOSURE, "--name-only", "--", *BUILDER_PATHS]):
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_TEMPLATE_UNRECOVERABLE")
    sample, _ = verify_baseline()
    for expectation in EXPECTATIONS:
        verify_primary_integrity(
            PRIVATE / f"reviewer-{expectation.reviewer_slot.lower()}-submissions-v1/frozen-v1",
            source_sha=expectation.submission_sha256,
            receipt_fp=expectation.acceptance_receipt_fingerprint,
        )
    for path, key in (
        (PRIVATE / "inter-reviewer-agreement-v1/conflict-manifest-v1.json", "conflicts"),
        (PRIVATE / "inter-reviewer-agreement-v1/adjudicator-safe-index-v1.json", "index"),
        (PUBLIC / "inter-reviewer-agreement-v1/agreement-analysis-v1.json", "analysis"),
        (PUBLIC / "inter-reviewer-agreement-v1/agreement-verification-v1.json", "c_receipt"),
        (PUBLIC / "adjudicator-handoff-verification-v1.json", "d_receipt"),
        (HANDOFF / "handoff-freeze.json", "package"),
    ):
        verify_opaque_seal(path, EXPECTED[key])
    stored = json.loads(
        verify_opaque_seal(COORDINATOR / "adjudicator-mapping-v1.json", EXPECTED["mapping"])
    )
    bundle, mapping, contents = build_adjudicator_material(
        PRIVATE / "inter-reviewer-agreement-v1/adjudicator-safe-index-v1.json",
        COHORT / "sample-v1.json",
        PRIVATE / "semantic-positive-holdout-v1/packets",
        COHORT / "reviewer-guidance-v1.json",
        bytes.fromhex(stored["private_blinding_key_hex"]),
        expected_index_fingerprint=EXPECTED["index"],
        expected_sample_fingerprint=sample.fingerprint,
        expected_guidance_fingerprint=stored["guidance_fingerprint"],
    )
    receipt = handoff_receipt(bundle, contents)
    if (
        bundle.fingerprint != EXPECTED["bundle"]
        or mapping != stored
        or mapping["fingerprint"] != EXPECTED["mapping"]
        or receipt["fingerprint"] != EXPECTED["package"]
        or hashlib.sha256(contents["response-template.json"]).hexdigest() != EXPECTED["blank"]
    ):
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_TEMPLATE_UNRECOVERABLE")
    if COORDINATOR.is_symlink() or {p.name for p in COORDINATOR.iterdir()} != {
        "adjudicator-mapping-v1.json"
    }:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT")
    for name, body in contents.items():
        if name != "response-template.json" and (HANDOFF / name).read_bytes() != body:
            raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT")
    if (HANDOFF / "handoff-freeze.json").read_bytes() != (canonical(receipt) + "\n").encode():
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT")
    return mapping, contents, receipt


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--recover", action="store_true")
    action.add_argument("--verify-handoff", action="store_true")
    parser.add_argument("--preserved-copy", type=Path)
    args = parser.parse_args()
    raw = SOURCE.read_bytes()
    if SOURCE.is_symlink() or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HUMAN_FILE_DIVERGENCE")
    if args.recover:
        if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != D_CLOSURE:
            raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT")
        if AUDIT.exists() or AUDIT.is_symlink():
            raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT")
        verify_recoverable_handoff(
            SOURCE,
            HANDOFF,
            source_sha=SOURCE_SHA,
            package_fp=EXPECTED["package"],
            blank_sha=EXPECTED["blank"],
        )
    mapping, contents, receipt = original_material()
    if args.recover:
        candidate = contents["response-template.json"]
        method = "deterministic-regeneration"
        if args.preserved_copy:
            if args.preserved_copy.is_symlink():
                raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_TEMPLATE_UNRECOVERABLE")
            candidate = args.preserved_copy.read_bytes()
            method = "preserved-copy"
        recover_exact_blank(
            SOURCE,
            HANDOFF,
            candidate,
            source_sha=SOURCE_SHA,
            package_fp=EXPECTED["package"],
            blank_sha=EXPECTED["blank"],
        )
    verify_adjudicator_handoff(HANDOFF, COORDINATOR, mapping, contents, receipt)
    verify_prerequisites()
    if SOURCE.read_bytes() != raw:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HUMAN_FILE_DIVERGENCE")
    if args.recover:
        audit = {
            "schema_version": "adjudicator-handoff-recovery-verification-v1",
            "recovery_status": "PASS",
            "canonical_submission_sha256": SOURCE_SHA,
            "misplaced_submission_sha256": SOURCE_SHA,
            "human_files_byte_identical": True,
            "blank_recovery_source": method,
            "blank_template_sha256": EXPECTED["blank"],
            "blank_exact_expected_hash": True,
            "handoff_inventory_validation": "PASS",
            "original_D_full_byte_verification": "PASS",
            "D_builder_commit": D_CLOSURE,
            "expected_fingerprints": EXPECTED,
            "package_case_count": 4,
            "unique_adjudicator_ids": 4,
            "other_frozen_files_modified": False,
            "human_content_modified": False,
            "prepopulated_answers": 0,
            "leakage_findings": 0,
            "final_ground_truth_materialized": False,
            "live_ai_calls": 0,
        }
        audit["fingerprint"] = digest(audit)
        write_new(AUDIT, audit)
    else:
        audit = json.loads(AUDIT.read_bytes())
        verify_opaque_seal(AUDIT, audit["fingerprint"])
        if (
            audit["expected_fingerprints"] != EXPECTED
            or audit["canonical_submission_sha256"] != SOURCE_SHA
        ):
            raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except HandoffRecoveryBlocked as error:
        raise SystemExit(str(error)) from None
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit("PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT") from None
