"""Explicit recovery of proven non-frozen macOS metadata; no human correction or acceptance."""

import argparse
import hashlib
import json
import subprocess

from prompt015e3_corrected_acceptance import (
    CORRECTED,
    CORRECTED_SHA,
    CORRECTION,
    ROUND,
    prerequisites,
)
from prompt015e_acceptance import D_CLOSURE, FROZEN, PUBLIC, PUBLIC_RECEIPT, SOURCE, SOURCE_SHA

from archguard.benchmark.oss.models import digest
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_adjudication_corrected_acceptance import (
    CorrectedAcceptanceBlocked,
    corrected_sha_guard,
    recover_round_os_metadata,
)

AUDIT = PUBLIC / "adjudicator-os-metadata-recovery-verification-v1.json"
AUDIT_FINGERPRINT = "b9359b4cbefb197452c538bf1ed87c46c62ca7a2246798dce101f397bcc9fb79"


def corrected_input_guard():
    try:
        return corrected_sha_guard(CORRECTED, CORRECTED_SHA)
    except CorrectedAcceptanceBlocked as error:
        raise CorrectedAcceptanceBlocked(
            str(error).replace(
                "PROMPT_015_E_3_BLOCKED_CORRECTED_SHA_MISMATCH",
                "PROMPT_015_E_3_1_BLOCKED_CORRECTED_SHA_MISMATCH",
            )
        ) from None


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--recover-os-metadata", action="store_true")
    action.add_argument("--verify-recovery", action="store_true")
    args = parser.parse_args()
    corrected_before = corrected_input_guard()
    original_before = SOURCE.read_bytes()
    if hashlib.sha256(original_before).hexdigest() != SOURCE_SHA:
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT")
    if args.recover_os_metadata:
        if (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != D_CLOSURE
            or AUDIT.exists()
            or AUDIT.is_symlink()
            or FROZEN.exists()
            or FROZEN.is_symlink()
            or PUBLIC_RECEIPT.exists()
            or PUBLIC_RECEIPT.is_symlink()
        ):
            raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT")
        audit = recover_round_os_metadata(ROUND, CORRECTION["package"])
        prerequisites()
        if SOURCE.read_bytes() != original_before or CORRECTED.read_bytes() != corrected_before:
            raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT")
        audit.update(
            original_submission_sha256=SOURCE_SHA,
            corrected_submission_sha256=CORRECTED_SHA,
            correction_template_fingerprint=CORRECTION["template"],
            correction_public_audit_fingerprint=CORRECTION["audit"],
            human_input_files_unchanged=True,
            P015_D_verification="PASS",
            acceptance_artifacts_present_at_recovery=False,
            live_ai_calls=0,
            final_ground_truth_materialized=False,
        )
        audit["fingerprint"] = digest(audit)
        if audit["fingerprint"] != AUDIT_FINGERPRINT:
            raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT")
        write_new(AUDIT, audit)
    else:
        prerequisites()
        audit = json.loads(verify_opaque_seal(AUDIT, AUDIT_FINGERPRINT))
        if (
            audit["correction_package_fingerprint"] != CORRECTION["package"]
            or audit["correction_template_fingerprint"] != CORRECTION["template"]
            or audit["correction_public_audit_fingerprint"] != CORRECTION["audit"]
            or audit["corrected_submission_sha256"] != CORRECTED_SHA
            or audit["original_submission_sha256"] != SOURCE_SHA
        ):
            raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except CorrectedAcceptanceBlocked as error:
        raise SystemExit(str(error)) from None
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit("PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT") from None
